"""Unknown-name source copies preserve unresolved regions without tensor lowering."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from archcanvas_authoring import DraftError, generate_model, import_source_draft, validate_draft
from archcanvas_python import analyze_source, analyze_project

ROOT = Path(__file__).resolve().parents[1]

SOURCE = '''from torch import nn
class Meadow(nn.Module):
 def __init__(self):
  super().__init__(); self.head=nn.Linear(4, 3); self.drop=nn.Dropout(0.1)
 def forward(self, x, flag):
  if flag:
   x=self.head(x)
  return self.drop(x)
'''


def source_draft(architecture):
    script = """import fs from 'node:fs';
import {createDocument,applyVisualBatch,buildScene} from './src/core/index.ts';
let document=createDocument(JSON.parse(fs.readFileSync(0,'utf8')));
document=applyVisualBatch(document,document.architecture.nodes.filter(n=>n.children.length&&!n.id.startsWith('instance:')).map(n=>({type:'expand',id:n.id,expanded:true})));
process.stdout.write(JSON.stringify({document,scene:buildScene(document)}));"""
    result = subprocess.run(['node', '--experimental-strip-types', '--input-type=module', '-e', script],
                            cwd=ROOT/'studio', input=json.dumps(architecture), text=True, capture_output=True, check=True)
    view = json.loads(result.stdout)
    return import_source_draft(view['document'], view['scene'])['draft']


class SourcePreservationTests(unittest.TestCase):
    def test_original_dynamic_source_can_generate_an_unchanged_managed_copy(self):
        original = analyze_source(SOURCE, 'model:Meadow')
        draft = source_draft(original)
        draft['nodes'][0]['position']['x'] += 17
        before = deepcopy(draft)
        self.assertEqual(validate_draft(draft)['generation']['mode'], 'source-preserved-copy')
        result = generate_model(draft)
        self.assertEqual(result['architecture'], original)
        self.assertEqual(result['source'], SOURCE)
        self.assertEqual(result['verification']['literalEdits'], 0)
        self.assertEqual(result['verification']['topology'], 'preserved')
        self.assertEqual(draft, before)

    def test_literal_parameter_edit_reanalyzes_source_and_retains_branch_bytes(self):
        draft = source_draft(analyze_source(SOURCE, 'model:Meadow'))
        refs = draft['sourceProvenance']['nodeRefs']
        drop = next(node for node in draft['nodes'] if refs[node['id']]['kind'] == 'Dropout')
        drop['parameters']['p'] = 0.25
        result = generate_model(draft)
        self.assertEqual(result['source'], SOURCE.replace('nn.Dropout(0.1)', 'nn.Dropout(0.25)'))
        self.assertEqual(result['verification']['literalEdits'], 1)
        self.assertEqual(next(node['parameters']['p'] for node in result['architecture']['nodes'] if node['kind']=='Dropout'), 0.25)
        self.assertTrue(any(node.get('sourceStructure') for node in result['architecture']['nodes']))
        with tempfile.TemporaryDirectory() as directory:
            for item in result['architecture']['sources']:
                path = Path(directory)/item['path']; path.parent.mkdir(parents=True,exist_ok=True); path.write_text(item['content'])
            self.assertEqual(analyze_project(directory,result['entry']), result['architecture'])

    def test_structural_or_inspection_parameters_are_not_silently_ignored(self):
        original = source_draft(analyze_source(SOURCE, 'model:Meadow'))
        deleted = deepcopy(original)
        deleted['nodes'].pop(0)
        deleted['edges'] = [edge for edge in deleted['edges'] if all(end['nodeId'] in {node['id'] for node in deleted['nodes']} for end in [edge['source'],edge['target']])]
        self.assertFalse(validate_draft(deleted)['generation']['supported'])
        with self.assertRaises(DraftError): generate_model(deleted)
        rewired = deepcopy(original)
        refs = rewired['sourceProvenance']['nodeRefs']
        input_node = next(node for node in rewired['nodes'] if refs[node['id']]['kind']=='Input' and node['label']=='x')
        input_spec = next(spec for spec in rewired['sourceProvenance']['modules'] if spec['kind']==input_node['kind'])
        output_node = next(node for node in rewired['nodes'] if refs[node['id']]['kind']=='Output')
        edge = next(edge for edge in rewired['edges'] if edge['target']['nodeId']==output_node['id'])
        edge['source'] = {'nodeId':input_node['id'], 'portId':next(port['id'] for port in input_spec['ports'] if port['direction']=='out')}
        # A complete acyclic visual graph still does not authorize changing the
        # preserved model's actual data flow through its unresolved branches.
        self.assertTrue(validate_draft(rewired)['complete'])
        self.assertFalse(validate_draft(rewired)['generation']['supported'])
        with self.assertRaises(DraftError) as caught: generate_model(rewired)
        self.assertEqual(caught.exception.diagnostics[0]['code'], 'unsupported-source-preserving-edit')
        changed = deepcopy(original)
        inspected = next(node for node in changed['nodes'] if 'condition' in node['parameters'])
        inspected['parameters']['condition'] = 'invented'
        with self.assertRaises(DraftError): generate_model(changed)
        cached = deepcopy(original)
        cached['sourceCache'] = {'nodes': [], 'edges': [], 'removedNodeIds': ['hidden'], 'removedCanonicalEdgeIds': []}
        self.assertFalse(validate_draft(cached)['generation']['supported'])
        with self.assertRaises(DraftError): generate_model(cached)

    def test_symbolic_constructor_arguments_remain_noneditable(self):
        source = SOURCE.replace('def __init__(self):', 'def __init__(self, rate=0.1):').replace('nn.Dropout(0.1)', 'nn.Dropout(rate)')
        draft = source_draft(analyze_source(source, 'model:Meadow'))
        refs = draft['sourceProvenance']['nodeRefs']
        next(node for node in draft['nodes'] if refs[node['id']]['kind']=='Dropout')['parameters']['p'] = 0.3
        self.assertFalse(validate_draft(draft)['generation']['supported'])
        with self.assertRaises(DraftError): generate_model(draft)

    def test_proven_literal_updates_its_exact_shared_inspection_spelling(self):
        source=SOURCE.replace('x=self.head(x)', 'x=self.drop(x)')
        draft=source_draft(analyze_source(source,'model:Meadow'))
        refs=draft['sourceProvenance']['nodeRefs']
        next(node for node in draft['nodes'] if refs[node['id']]['kind']=='Dropout')['parameters']['p']=0.5
        result=generate_model(draft)
        self.assertEqual(result['source'],source.replace('nn.Dropout(0.1)','nn.Dropout(0.5)'))
        inspected=[node for node in result['architecture']['nodes'] if node.get('sourceStructure') and node['parameters'].get('construction','').startswith('nn.Dropout(')]
        self.assertTrue(inspected)
        self.assertTrue(all(node['parameters']['construction']=='nn.Dropout(0.5)' for node in inspected))
        self.assertEqual(set(result['nodeBindings'])|set(result['containerBindings']),{node['id'] for node in draft['nodes']})
        self.assertTrue(set(result['nodeBindings'].values())|set(result['containerBindings'].values()) <= {node['id'] for node in result['architecture']['nodes']})
        changed=deepcopy(draft)
        inspection=next(node for node in changed['nodes'] if 'construction' in node['parameters'])
        inspection['parameters']['construction']='nn.Dropout(0.9)'
        with self.assertRaises(DraftError): generate_model(changed)

    def test_utf8_bom_crlf_and_comments_survive_exact_literal_replacement(self):
        source = SOURCE.replace(' self.head', ' self.head').replace('class Meadow', '# 树状模型\nclass Meadow').replace('\n','\r\n')
        original = analyze_source(source, 'model:Meadow', raw_bytes=b'\xef\xbb\xbf'+source.encode())
        draft = source_draft(original)
        refs = draft['sourceProvenance']['nodeRefs']
        next(node for node in draft['nodes'] if refs[node['id']]['kind']=='Dropout')['parameters']['p']=0.125
        result=generate_model(draft)
        self.assertEqual(result['source'],source.replace('nn.Dropout(0.1)','nn.Dropout(0.125)'))
        import hashlib
        self.assertEqual(result['architecture']['sources'][0]['digest'],hashlib.sha256(b'\xef\xbb\xbf'+result['source'].encode()).hexdigest())

    def test_project_copy_preserves_nested_import_helpers_and_unused_source_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            source=SOURCE.replace('  if flag:', '  if flag:\n   from hidden import transform\n   x=transform(x)')
            (root/'model.py').write_text(source)
            helper=b'\xef\xbb\xbf# \xe6\xba\x90\xe7\xa0\x81\r\ndef transform(x):\r\n return x\r\n'
            (root/'hidden.py').write_bytes(helper)
            (root/'unused.py').write_bytes(b'# preserved as selected corpus\n')
            architecture=analyze_project(root,'model:Meadow')
            self.assertEqual({source['path'] for source in architecture['sources']},{'model.py','hidden.py','unused.py'})
            result=generate_model(source_draft(architecture))
            self.assertEqual(result['architecture']['sources'],architecture['sources'])
            self.assertEqual(next(source['digest'] for source in result['architecture']['sources'] if source['path']=='hidden.py'),hashlib.sha256(helper).hexdigest())


if __name__ == '__main__': unittest.main()
