"""Unknown views retain source authority and reach the current native graph."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from archcanvas_adapters import AdapterError, AdapterRegistry, scaffold_adapter_files, validate_adapter_files
from archcanvas_adapters.handoff import build_handoff, starter_rules
from archcanvas_preview import analyze
from archcanvas_summary_semantic.schema import validate_ir

ROOT = Path(__file__).resolve().parents[1]
SOURCE = '''from torch import nn
raise RuntimeError("DO_NOT_EXECUTE_THIS_SOURCE")
class ForeignModel(nn.Module):
 def forward(self, values):
  return [item.hidden_transform() for item in values if item is not None]
'''
FILES = {'foreign.py': SOURCE}


class AgentViewCompletionTests(unittest.TestCase):
    def test_unavailable_probe_handoff_preserves_requests_and_rejects_rebound_receipt(self):
        from archcanvas_runtime.summary import observe_summary
        spec = {'schema': 'semantic-inputs/1', 'modes': ['eval'], 'cases': [
            {'id': 'one', 'inputs': {'values': {'shape': [1], 'fill': 'ones'}}}]}
        # Missing explicit environment is a real unavailable path, not a worker mock.
        observation = observe_summary(FILES, 'foreign:ForeignModel', spec)
        result = build_handoff(FILES, 'foreign:ForeignModel', probe_result=observation)
        self.assertEqual(result['probe']['status'], 'unavailable')
        self.assertFalse(result['modelExecuted'])
        self.assertTrue(result['requests'])
        self.assertFalse(result['probe']['runtimeVerified'])
        rebound = copy.deepcopy(observation)
        rebound['receipt']['binding']['source_generation'] = {}
        with self.assertRaisesRegex(AdapterError, 'does not match'):
            build_handoff(FILES, 'foreign:ForeignModel', probe_result=rebound)
        with self.assertRaisesRegex(AdapterError, 'does not match'):
            build_handoff(FILES, 'foreign:ForeignModel', {'width': 7}, probe_result=observation)

    def test_handoff_is_source_bound_and_does_not_create_registry_or_execute(self):
        with tempfile.TemporaryDirectory() as directory:
            registry = Path(directory) / 'absent-registry'
            handoff = build_handoff(FILES, 'foreign:ForeignModel', registry=registry)
            self.assertFalse(registry.exists())
        self.assertTrue(handoff['requests'])
        self.assertFalse(handoff['modelExecuted'])
        self.assertFalse(handoff['probe']['runByHandoff'])
        self.assertTrue(all(item['source'] and item['generationContract'] is None for item in handoff['requests']))
        self.assertEqual(handoff['sourceFiles'][0]['path'], 'foreign.py')

    def test_registered_rules_reach_native_ir_and_keep_computation_byte_identical(self):
        before = analyze(FILES, 'foreign:ForeignModel', semantic_mode='summary')
        base = before['ir']['semantic_ir']
        with tempfile.TemporaryDirectory() as directory:
            registry = AdapterRegistry(directory)
            for rule in starter_rules().values():
                registry.register_files(scaffold_adapter_files(FILES, 'foreign:ForeignModel', rules=[rule]), FILES)
            after = registry.preview(before, FILES)
            self.assertEqual(after, registry.preview(after, FILES))
        native = after['ir']['semantic_ir']
        original_nodes = {n['id']: n for n in base['nodes']}
        original_edges = {e['id']: e for e in base['edges']}
        self.assertTrue(validate_ir(native)['ok'], validate_ir(native))
        self.assertEqual(original_nodes, {n['id']: n for n in native['nodes'] if n['id'] in original_nodes})
        self.assertEqual(original_edges, {e['id']: e for e in native['edges'] if e['id'] in original_edges})
        cards = [n for n in native['nodes'] if n['id'] not in original_nodes]
        self.assertTrue(cards)
        self.assertTrue(all(n['inspection_only'] and n['kind'] == 'opaque' and n['generationContract'] is None for n in cards))
        self.assertTrue(all(e['syntaxOnly'] and e['kind'] == 'source-inspection' for e in native['edges'] if e['id'] not in original_edges))
        self.assertEqual(native['source_inspection_views']['base_ir_digest'], base['ir_digest'])
        self.assertEqual(after['sourceSha256'], before['sourceSha256'])
        self.assertEqual(after['coverage']['opaqueBoundaries'], sum(n['kind'] == 'opaque' for n in base['nodes']))
        self.assertFalse(native['coverage']['complete'])
        self.assertTrue(after['sourceRuleApplications'])

    def test_rules_rebind_renamed_models_and_reject_false_proof_stale_source_and_plugins(self):
        rule = starter_rules()['list-comprehension']
        definition = scaffold_adapter_files(FILES, 'foreign:ForeignModel', rules=[rule])
        renamed = {'new_package/other.py': SOURCE.replace('ForeignModel', 'Unseen').replace('values', 'tokens').replace('item', 'token')}
        moved = scaffold_adapter_files(renamed, 'new_package.other:Unseen', rules=[rule])
        self.assertEqual(definition['rules'], moved['rules'])
        with self.assertRaisesRegex(AdapterError, 'stale'):
            validate_adapter_files(definition, {'foreign.py': SOURCE + '\n# changed\n'})
        unrelated = {'foreign.py': SOURCE.replace('item.hidden_transform()', 'self.constant')}
        with self.assertRaisesRegex(AdapterError, 'Comprehension'):
            scaffold_adapter_files(unrelated, 'foreign:ForeignModel', rules=[rule])
        forged = copy.deepcopy(definition)
        forged['generationContract'] = {'python': 'execute_me()'}
        with self.assertRaises(AdapterError):
            validate_adapter_files(forged, FILES)

    def test_unavailable_external_implementation_remains_an_opaque_boundary(self):
        source = {'external.py': 'from torch import nn\nimport absent_backend\nclass Closed(nn.Module):\n def forward(self,x):\n  return absent_backend.secret(x)\n'}
        request = build_handoff(source, 'external:Closed')
        self.assertTrue(request['requests'])
        self.assertTrue(all(r['generationContract'] is None for r in request['requests']))

    def test_explicit_decorated_body_is_inspectable_without_resolving_its_runtime_callable(self):
        files = {'decorated.py': '''from torch import nn
def replace(fn):
 raise RuntimeError("DECORATOR_MUST_NOT_RUN")
class Foreign(nn.Module):
 @replace
 def hidden(self,x):
  return x.permute(0,2,1).contiguous()
 def forward(self,x):
  return self.hidden(x)
'''}
        before = analyze(files, 'decorated:Foreign', semantic_mode='summary')
        unknown = [n for n in before['ir']['semantic_ir']['nodes'] if n.get('reason') == 'decorated-callable-unresolved']
        self.assertTrue(unknown)
        definition = scaffold_adapter_files(files, 'decorated:Foreign', method='hidden', rules=[starter_rules()['attribute-call']])
        with tempfile.TemporaryDirectory() as directory:
            registry = AdapterRegistry(directory)
            registry.register_files(definition, files)
            after = registry.preview(before, files)
        self.assertTrue(after['sourceRuleApplications'])
        self.assertTrue(any(n.get('inspection_only') for n in after['ir']['semantic_ir']['nodes']))
        originals = {n['id']: n for n in after['ir']['semantic_ir']['nodes']}
        for node in unknown:
            self.assertEqual(node, originals[node['id']])

    def test_bound_skill_launcher_exposes_the_real_handoff(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'foreign.py').write_text(SOURCE)
            run = subprocess.run([sys.executable, '-I', '-B', str(ROOT / 'skills/archcanvas/scripts/archcanvas_runtime.py'),
                                  'adapter', 'handoff', '--root', str(root), '--entry', 'foreign:ForeignModel'],
                                 capture_output=True, text=True, timeout=30)
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertEqual(json.loads(run.stdout)['schema'], 'archcanvas-agent-view-handoff/1')
