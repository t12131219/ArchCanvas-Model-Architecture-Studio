"""Agent-authored source rules must add structure and survive source reuse.

Expected structure is asserted from the supplied Python, independently of the
old source inspector. Original canonical bindings must remain byte-identical.
"""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from archcanvas_adapters import AdapterError, AdapterRegistry, scaffold_adapter_files, validate_adapter_files, apply_preview_adapters
from archcanvas_preview import analyze

ROOT = Path(__file__).resolve().parents[1]
RULE = {
    'schema': 'archcanvas-source-rule/1', 'name': 'Comprehension call inputs',
    'match': {'type': 'ListComp', 'fields': {
        'elt': {'type': 'Call', 'fields': {'args': [{'type': 'Name'}]}},
        'generators': [{'type': 'comprehension', 'fields': {'is_async': 0}}],
    }},
    'nodes': [
        {'key': 'region', 'at': [], 'parent': None, 'kind': 'SourceLoop'},
        {'key': 'iterator', 'at': ['generators', 0, 'iter'], 'parent': 'region', 'kind': 'SourceExpression'},
        {'key': 'input', 'at': ['elt', 'args', 0], 'parent': 'region', 'kind': 'SourceExpression'},
        {'key': 'operation', 'at': ['elt'], 'parent': 'region', 'kind': 'SourceCall'},
    ],
    'relations': [
        {'source': 'iterator', 'target': 'operation', 'proof': 'comprehension-iteration'},
        {'source': 'input', 'target': 'operation', 'proof': 'expression-input'},
    ],
}
SOURCE = '''from torch import nn
class CopperSprig(nn.Module):
 def __init__(self):
  super().__init__(); self.parts=nn.ModuleList([nn.Identity()])
 def forward(self,x):
  values=[part(x) for part in self.parts]
  return values
'''
FILES = {'foreign.py': SOURCE}


class SourceRuleRegistryTests(unittest.TestCase):
    def setUp(self):
        self.definition = scaffold_adapter_files(FILES, 'foreign:CopperSprig', rules=[RULE])

    def test_new_structure_is_not_just_relabeling_old_parser_output(self):
        before = analyze(FILES, 'foreign:CopperSprig')
        self.assertFalse(any(node.get('expression') == 'self.parts' for node in before['ir']['nodes']))
        after = apply_preview_adapters(before, FILES, [self.definition])
        added = [node for node in after['ir']['nodes'] if node['id'] not in {n['id'] for n in before['ir']['nodes']}]
        self.assertEqual({node['expression'] for node in added}, {'self.parts', 'x'})
        original_nodes = {node['id']: node for node in before['ir']['nodes']}
        self.assertTrue(all(node == original_nodes[node['id']] for node in after['ir']['nodes'] if node['id'] in original_nodes))
        original_edges = {edge['id']: edge for edge in before['ir']['edges']}
        self.assertTrue(all(edge == original_edges[edge['id']] for edge in after['ir']['edges'] if edge['id'] in original_edges))
        self.assertEqual(after['sourceSha256'], before['sourceSha256'])
        self.assertEqual(len(after['sourceRuleApplications']), 1)
        proof_edges = [edge for edge in after['ir']['edges'] if edge.get('sourceRuleId')]
        self.assertEqual(len(proof_edges), 2)
        self.assertTrue(all(edge['syntaxOnly'] and edge['role'] == 'source_dependency' for edge in proof_edges))
        call = next(node for node in before['ir']['nodes'] if node.get('expression') == 'part(x)')
        self.assertTrue(all(edge['target'] == call['id'] for edge in proof_edges))
        self.assertEqual(apply_preview_adapters(after, FILES, [self.definition]), after)

    def test_registered_template_rebinds_different_names_files_and_source_hash(self):
        with tempfile.TemporaryDirectory() as temporary:
            store = AdapterRegistry(temporary)
            receipt = store.register_files(self.definition, FILES)
            self.assertEqual(len(receipt['rules']), 1)
            self.assertEqual(len(AdapterRegistry(temporary).rules()), 1)
            second = {'other.py': SOURCE.replace('CopperSprig', 'SilverBranch').replace('parts', 'stages').replace('part(', 'stage(').replace('for part in', 'for stage in').replace('(self,x)', '(self,inputs)').replace('stage(x)', 'stage(inputs)')}
            with self.assertRaisesRegex(AdapterError, 'stale'):
                validate_adapter_files(self.definition, second)
            raw = analyze(second, 'other:SilverBranch')
            result = AdapterRegistry(temporary).preview(raw, second)
            self.assertEqual(len(result['sourceRuleApplications']), 1)
            self.assertTrue(any(node.get('expression') == 'self.stages' for node in result['ir']['nodes']))
            self.assertTrue(any(node.get('expression') == 'inputs' and node.get('sourceRuleId') for node in result['ir']['nodes']))
            self.assertNotEqual(result['sourceRuleApplications'][0]['adapter'], self.definition['id'])
            self.assertEqual(store.list_files(second)[0]['status'], 'stale')
            self.assertEqual(result['availableSourceRules'], [receipt['rules'][0]['id']])

    def test_registered_template_rebinds_current_config_without_reusing_other_config_facts(self):
        files = {'foreign.py': SOURCE.replace('def __init__(self):', 'def __init__(self,width=4):')}
        saved = scaffold_adapter_files(files, 'foreign:CopperSprig', config={'width': 4}, rules=[RULE])
        current = scaffold_adapter_files(files, 'foreign:CopperSprig', config={'width': 8}, rules=[RULE])
        with tempfile.TemporaryDirectory() as temporary:
            store = AdapterRegistry(temporary)
            store.register_files(saved, files)
            raw = analyze(files, 'foreign:CopperSprig', {'width': 8})
            result = AdapterRegistry(temporary).preview(raw, files)
            self.assertEqual(len(result['sourceRuleApplications']), 1)
            self.assertEqual(result['sourceRuleApplications'][0]['adapter'], current['id'])
            self.assertNotEqual(current['id'], saved['id'])
            self.assertFalse(result.get('ruleDiagnostics'))
            self.assertTrue(any(node.get('expression') == 'self.parts' and node.get('sourceRuleId')
                                for node in result['ir']['nodes']))
            # Saving the new configuration must still produce one application,
            # without allowing the old exact instance to suppress or duplicate it.
            store.register_files(current, files)
            repeated = AdapterRegistry(temporary).preview(raw, files)
            self.assertEqual(repeated['sourceRuleApplications'], result['sourceRuleApplications'])
            self.assertEqual(repeated['ir'], result['ir'])

    def test_registered_explicit_method_does_not_suppress_default_entry_template_rebinding(self):
        files = {'foreign.py': SOURCE + ''' def inspect(self,x):
  return [helper(x) for helper in self.parts]
'''}
        saved = scaffold_adapter_files(files, 'foreign:CopperSprig', method='inspect', rules=[RULE])
        current = scaffold_adapter_files(files, 'foreign:CopperSprig', rules=[RULE])
        self.assertEqual(saved['binding']['method'], 'inspect')
        self.assertEqual(current['binding']['method'], 'forward')
        with tempfile.TemporaryDirectory() as temporary:
            store = AdapterRegistry(temporary)
            store.register_files(saved, files)
            result = AdapterRegistry(temporary).preview(analyze(files, 'foreign:CopperSprig'), files)
            self.assertEqual(len(result['sourceRuleApplications']), 1)
            application = result['sourceRuleApplications'][0]
            self.assertEqual(application['adapter'], current['id'])
            self.assertTrue(any(node.get('expression') == 'self.parts' and node.get('sourceRuleId')
                                for node in result['ir']['nodes']))
            self.assertTrue(all('helper(x)' not in node.get('expression', '')
                                for node in result['ir']['nodes'] if node.get('sourceRuleId')))

    def test_rule_cannot_attach_to_a_neighboring_opaque_region(self):
        files = {'foreign.py': SOURCE.replace('  return values', '  unrelated = x.unknown()\n  return values, unrelated')}
        definition = scaffold_adapter_files(files, 'foreign:CopperSprig', rules=[RULE])
        raw = analyze(files, 'foreign:CopperSprig')
        result = apply_preview_adapters(raw, files, [definition])
        applications = result['sourceRuleApplications']
        self.assertEqual(len(applications), 1)
        boundary = next(node for node in raw['ir']['nodes'] if node['id'] == applications[0]['boundary'])
        self.assertIn('ListComp', boundary['label'])
        self.assertNotIn('unknown', boundary['expression'])

    def test_each_match_stays_in_its_actual_if_else_branch(self):
        files = {'branch.py': '''from torch import nn
class Split(nn.Module):
 def forward(self,x,flag):
  if flag:
   return [v.sin() for v in x]
  else:
   return [v.cos() for v in x]
'''}
        rule = copy.deepcopy(RULE)
        rule['match'] = {'type': 'ListComp'}
        rule['nodes'] = [node for node in rule['nodes'] if node['key'] != 'input']
        rule['relations'] = [rule['relations'][0]]
        definition = scaffold_adapter_files(files, 'branch:Split', rules=[rule])
        result = apply_preview_adapters(analyze(files, 'branch:Split'), files, [definition])
        self.assertEqual(len(result['sourceRuleApplications']), 2)
        by_id = {node['id']: node for node in result['ir']['nodes']}
        for receipt in result['sourceRuleApplications']:
            branch = by_id[receipt['boundary']]
            self.assertEqual(branch['sourceKind'], 'SourceBranch')
            expressions = {by_id[identity]['expression'] for identity in receipt['nodes']}
            expected = 'sin' if branch['sourceParameters']['condition'] == 'flag' else 'cos'
            self.assertTrue(any(f'v.{expected}()' == expression for expression in expressions))
            self.assertFalse(any(f'v.{"cos" if expected == "sin" else "sin"}()' == expression for expression in expressions))

    def test_unrelated_saved_instance_in_same_corpus_does_not_warn(self):
        files = {**FILES, 'other.py': SOURCE.replace('CopperSprig', 'Other')}
        definition = scaffold_adapter_files(files, 'foreign:CopperSprig', rules=[RULE])
        with tempfile.TemporaryDirectory() as temporary:
            registry = AdapterRegistry(temporary); registry.register_files(definition, files)
            result = registry.preview(analyze(files, 'other:Other'), files)
            self.assertEqual(len(result['sourceRuleApplications']), 1)
            self.assertFalse(result.get('ruleDiagnostics'))

    def test_branch_source_formatting_does_not_change_its_membership(self):
        files = {'foreign.py': SOURCE.replace('  values=', '  if (x)  is not None:\n   values=').replace('  return values', '   return values\n  else:\n   return x')}
        definition = scaffold_adapter_files(files, 'foreign:CopperSprig', rules=[RULE])
        result = apply_preview_adapters(analyze(files, 'foreign:CopperSprig'), files, [definition])
        self.assertEqual(len(result['sourceRuleApplications']), 1)
        branch = next(node for node in result['ir']['nodes'] if node['id'] == result['sourceRuleApplications'][0]['boundary'])
        self.assertEqual(branch['sourceParameters']['condition'], 'x is not None')

    def test_overlapping_rules_reuse_proven_arrows(self):
        weaker = copy.deepcopy(RULE); weaker['name'] = 'Call arguments without iteration dependency'
        weaker['relations'] = [weaker['relations'][1]]
        definition = scaffold_adapter_files(FILES, 'foreign:CopperSprig', rules=[weaker, RULE])
        result = apply_preview_adapters(analyze(FILES, 'foreign:CopperSprig'), FILES, [definition])
        self.assertEqual(len(result['sourceRuleApplications']), 2)
        self.assertEqual(len([edge for edge in result['ir']['edges'] if edge.get('sourceRuleId')]), 2)
        edge_sets = [set(receipt['edges']) for receipt in result['sourceRuleApplications']]
        self.assertEqual(len(edge_sets[0] & edge_sets[1]), 1)
        self.assertEqual(apply_preview_adapters(result, FILES, [definition]), result)

    def test_shared_fstring_spans_do_not_merge_distinct_ast_occurrences(self):
        files = {'string.py': '''from torch import nn
class Formatter(nn.Module):
 def forward(self,x):
  return f"{x}{x}"
'''}
        rule = {'schema': 'archcanvas-source-rule/1', 'name': 'Formatted parts',
            'match': {'type': 'FormattedValue'}, 'nodes': [
                {'key': 'part', 'at': [], 'parent': None, 'kind': 'SourceExpression'},
                {'key': 'value', 'at': ['value'], 'parent': 'part', 'kind': 'SourceExpression'}],
            'relations': []}
        definition = scaffold_adapter_files(files, 'string:Formatter', rules=[rule])
        raw = analyze(files, 'string:Formatter'); result = apply_preview_adapters(raw, files, [definition])
        self.assertEqual(len(result['sourceRuleApplications']), 2)
        first, second = result['sourceRuleApplications']
        self.assertFalse(set(first['nodes']) & set(second['nodes']))
        by_id = {node['id']: node for node in result['ir']['nodes']}
        self.assertEqual(by_id[first['nodes'][0]]['parent'], first['anchor'])
        self.assertEqual(by_id[second['nodes'][0]]['parent'], second['anchor'])
        self.assertEqual(apply_preview_adapters(result, files, [definition]), result)

    def test_explicit_method_on_class_without_forward_does_not_break_other_preview(self):
        files = {**FILES, 'helper.py': '''class Helper:
 def inspect(self, x):
  return [part(x) for part in self.parts]
'''}
        definition = scaffold_adapter_files(files, 'helper:Helper', method='inspect', rules=[RULE])
        raw = analyze(files, 'foreign:CopperSprig')
        result = apply_preview_adapters(raw, files, [definition])
        self.assertEqual(result['ir'], raw['ir'])
        self.assertFalse(result.get('ruleDiagnostics'))

    def test_updated_display_labels_preserve_original_ir_facts(self):
        raw = analyze(FILES, 'foreign:CopperSprig')
        first = apply_preview_adapters(raw, FILES, [self.definition])
        changed = copy.deepcopy(self.definition)
        fact = next(node for node in changed['children'] if node['source']['expression'] == 'part(x)')
        changed['presentation']['labels'][fact['id']] = 'Shared operation'
        second = apply_preview_adapters(first, FILES, [changed])
        self.assertEqual(first['ir'], second['ir'])
        self.assertIn('Shared operation', second['sourceRuleApplications'][0]['labels'].values())

    def test_saved_rule_restarts_invalid_record_is_visible_and_does_not_apply(self):
        with tempfile.TemporaryDirectory() as temporary:
            store = AdapterRegistry(temporary); receipt = store.register_files(self.definition, FILES)
            rule_path = Path(receipt['rules'][0]['path']); rule_path.write_text('{"schema":"python-hook"}')
            reopened = AdapterRegistry(temporary)
            self.assertEqual(reopened.rules()[0]['status'], 'invalid')
            changed = {key: value + '\n# new version\n' for key, value in FILES.items()}
            result = reopened.preview(analyze(changed, 'foreign:CopperSprig'), changed)
            self.assertFalse(result.get('sourceRuleApplications'))

    def test_empty_match_cannot_be_registered_as_a_successful_adaptation(self):
        files = {'empty.py': 'from torch import nn\nclass Empty(nn.Module):\n def forward(self,x): return x\n'}
        definition = scaffold_adapter_files(files, 'empty:Empty', rules=[RULE])
        self.assertEqual(definition['applications'], [])
        with tempfile.TemporaryDirectory() as temporary, self.assertRaisesRegex(AdapterError, 'at least one'):
            AdapterRegistry(temporary).register_files(definition, files)

    def test_agent_cli_has_full_rule_register_and_cross_source_reuse_path(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary); source = folder / 'source'; source.mkdir()
            (source / 'foreign.py').write_text(SOURCE)
            rule = folder / 'rule.json'; rule.write_text(json.dumps(RULE))
            definition_file = folder / 'adapter.json'; registry = folder / 'registry'
            def command(*args):
                result = subprocess.run([sys.executable, '-B', '-m', 'archcanvas_cli', 'adapter', *args],
                    cwd=ROOT, env={**os.environ, 'PYTHONPATH': str(ROOT / 'src')}, capture_output=True, text=True, timeout=45)
                self.assertEqual(result.returncode, 0, result.stderr)
                return json.loads(result.stdout) if result.stdout.strip() else None
            template = command('rule-validate', '--rule', str(rule))
            definition = command('scaffold', '--root', str(source), '--entry', 'foreign:CopperSprig', '--rules', str(rule), '--output', str(definition_file))
            self.assertIsNone(definition)
            self.assertEqual(json.loads(definition_file.read_text())['schema'], 'archcanvas-source-adapter/2')
            command('validate', '--root', str(source), '--definition', str(definition_file))
            command('register', '--root', str(source), '--definition', str(definition_file), '--registry', str(registry))
            self.assertEqual(command('rules', '--registry', str(registry))[0]['id'], template['id'])
            (source / 'foreign.py').write_text(SOURCE.replace('CopperSprig', 'SilverBranch'))
            rebound = command('scaffold', '--root', str(source), '--entry', 'foreign:SilverBranch', '--registry', str(registry))
            self.assertNotEqual(rebound['id'], json.loads(definition_file.read_text())['id'])
            preview = command('preview', '--root', str(source), '--entry', 'foreign:SilverBranch', '--registry', str(registry))
            self.assertEqual(len(preview['sourceRuleApplications']), 1)


if __name__ == '__main__':
    unittest.main()
