"""Anchored source surgery must preserve unknown code and refuse ambiguous edits."""
import ast
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest

from archcanvas_authoring import generate_model, validate_draft, DraftError
from archcanvas_authoring.custom_modules import preview_custom_module
from archcanvas_python import analyze_source, analyze_project
from tests.test_source_preservation import source_draft, SOURCE


def fact_node(draft, kind):
    refs = draft['sourceProvenance']['nodeRefs']
    return next(node for node in draft['nodes'] if refs.get(node['id'], {}).get('kind') == kind)


def insert(draft, kind='Identity', parameters=None, target_kind='Output', definition=None):
    target = fact_node(draft, target_kind)
    edge = next(edge for edge in draft['edges'] if edge['target']['nodeId'] == target['id'])
    source = deepcopy(edge['source'])
    draft['nodes'].append({'id': 'new_module', 'kind': kind, 'label': 'Inserted module',
                           'parameters': parameters or {}, 'position': {'x': 600, 'y': 500}})
    edge['source'] = {'nodeId': 'new_module', 'portId': 'output'}
    port = definition['inputs'][0]['id'] if definition else 'input'
    draft['edges'].append({'id': 'new_input', 'source': source, 'target': {'nodeId': 'new_module', 'portId': port}})
    if definition:
        draft['customModules'] = [definition]
    return draft


def delete(draft, kind='Dropout'):
    node = fact_node(draft, kind)
    original = next(edge['source'] for edge in draft['edges'] if edge['target']['nodeId'] == node['id'])
    for edge in draft['edges']:
        if edge['source']['nodeId'] == node['id']:
            edge['source'] = deepcopy(original)
    draft['nodes'] = [item for item in draft['nodes'] if item['id'] != node['id']]
    draft['edges'] = [edge for edge in draft['edges'] if edge['target']['nodeId'] != node['id']]
    return draft


class SourceSurgeryTests(unittest.TestCase):
    def test_expanding_edited_region_keeps_source_generation_and_exact_new_module_chain(self):
        import json
        import subprocess
        from archcanvas_authoring.source_import import import_source_draft, rebase_source_frontier
        from tests.test_source_preservation import ROOT
        complete = source_draft(analyze_source(SOURCE, 'model:Meadow'))
        # A frontier rebase stores live edit edges and the replaced canonical
        # edge in its cache. This is independent persistence, not a hidden edit.
        script = """import fs from 'node:fs';
import {buildScene} from './src/core/index.ts';
const document=JSON.parse(fs.readFileSync(0,'utf8'));
const folded=structuredClone(document);
folded.expandedIds=folded.expandedIds.filter(id=>!document.architecture.nodes.some(node=>node.id===id&&node.kind==='SourceBranch'));
process.stdout.write(JSON.stringify({document,scene:buildScene(document),folded:{document:folded,scene:buildScene(folded)}}));"""
        result = subprocess.run(['node', '--experimental-strip-types', '--input-type=module', '-e', script],
                                cwd=ROOT/'studio', input=json.dumps(complete['sourceProvenance']['canvas']),
                                text=True, capture_output=True, check=True)
        view = json.loads(result.stdout)
        draft = insert(import_source_draft(view['folded']['document'], view['folded']['scene'])['draft'])
        direct = generate_model(draft)
        rebased = rebase_source_frontier(draft, view['document'], view['scene'])['draft']
        self.assertGreater(len(rebased['nodes']), len(draft['nodes']))
        self.assertTrue(rebased['sourceCache']['edges'])
        self.assertTrue(rebased['sourceCache']['removedCanonicalEdgeIds'])
        self.assertTrue(validate_draft(rebased)['generation']['supported'])
        actual = generate_model(json.loads(json.dumps(rebased)))
        self.assertEqual(actual['source'], direct['source'])
        self.assertEqual(actual['architecture'], direct['architecture'])

    def test_materialized_live_cache_does_not_authorize_hidden_or_stale_edge_changes(self):
        draft = insert(source_draft(analyze_source(SOURCE, 'model:Meadow')))
        original_edges = draft['sourceProvenance']['originalGraph']['edges']
        deleted_edge = next(edge for edge in original_edges if not any(current == edge for current in draft['edges']))
        replaced = draft['sourceProvenance']['edgeRefs'][deleted_edge['id']]
        draft['sourceCache'] = {'nodes': [], 'edges': deepcopy(draft['edges']), 'removedNodeIds': [], 'removedCanonicalEdgeIds': deepcopy(replaced)}
        self.assertTrue(validate_draft(draft)['generation']['supported'])
        hidden = deepcopy(draft)
        hidden['sourceCache']['edges'][0]['id'] = 'hidden_unmaterialized_edge'
        self.assertFalse(validate_draft(hidden)['generation']['supported'])
        with self.assertRaisesRegex(DraftError, 'Hidden structural edits'):
            generate_model(hidden)
        stale = deepcopy(draft)
        stale['sourceCache']['removedCanonicalEdgeIds'].append('unknown-edge')
        self.assertFalse(validate_draft(stale)['generation']['supported'])
        unchanged = next(edge for edge in original_edges if edge != deleted_edge)
        stale = deepcopy(draft)
        stale['sourceCache']['removedCanonicalEdgeIds'].extend(draft['sourceProvenance']['edgeRefs'][unchanged['id']])
        self.assertFalse(validate_draft(stale)['generation']['supported'])

    def test_unary_insertion_changes_only_constructor_and_exact_return_leaf(self):
        original = analyze_source(SOURCE, 'model:Meadow')
        draft = insert(source_draft(original))
        self.assertTrue(validate_draft(draft)['generation']['supported'])
        result = generate_model(draft)
        self.assertEqual(result['entry'], 'model:Meadow')
        self.assertEqual(result['verification']['topology'], 'anchored-edits')
        self.assertEqual(result['verification']['insertedModules'], 1)
        self.assertIn('  if flag:\n   x=self.head(x)\n', result['source'])
        self.assertIn('self.drop(x)', result['source'])
        identity = next(node for node in result['architecture']['nodes'] if node['id'] == result['nodeBindings']['new_module'])
        self.assertEqual(identity['kind'], 'Identity')
        self.assertEqual(set(result['nodeBindings']) | set(result['containerBindings']), {node['id'] for node in draft['nodes']})
        self.assertTrue(any(edge['source']['nodeId'] == identity['id'] for edge in result['architecture']['edges']))

    def test_insertion_on_call_argument_preserves_unresolved_region_and_literal_edit(self):
        draft = insert(source_draft(analyze_source(SOURCE, 'model:Meadow')), target_kind='Dropout')
        fact_node(draft, 'Dropout')['parameters']['p'] = 0.4
        result = generate_model(draft)
        self.assertIn('nn.Dropout(0.4)', result['source'])
        self.assertEqual(result['verification']['literalEdits'], 1)
        self.assertIn('  if flag:\n   x=self.head(x)\n', result['source'])
        self.assertEqual(result['architecture']['entry'], 'model:Meadow')

    def test_deletion_removes_call_and_unshared_constructor_without_changing_branch(self):
        draft = delete(source_draft(analyze_source(SOURCE, 'model:Meadow')))
        result = generate_model(draft)
        self.assertIn('  return x\n', result['source'])
        self.assertNotIn('nn.Dropout(', result['source'])
        self.assertNotIn('self.drop(', result['source'])
        self.assertIn('  if flag:\n   x=self.head(x)\n', result['source'])
        self.assertFalse(any(node['kind'] == 'Dropout' for node in result['architecture']['nodes']))

    def test_replacement_is_a_deleted_call_and_an_inserted_module(self):
        draft = source_draft(analyze_source(SOURCE, 'model:Meadow'))
        delete(draft)
        insert(draft, 'Tanh')
        result = generate_model(draft)
        self.assertNotIn('Dropout', result['source'])
        self.assertEqual(result['verification']['deletedCalls'], 1)
        self.assertEqual(result['verification']['insertedModules'], 1)
        self.assertTrue(any(node['kind'] == 'Tanh' for node in result['architecture']['nodes']))

    def test_custom_source_module_is_copied_and_bound_without_execution(self):
        custom = preview_custom_module({'source': 'from torch import nn\nclass CustomReview(nn.Module):\n def __init__(self):\n  super().__init__(); self.inner=nn.Tanh()\n def forward(self, x):\n  return self.inner(x)\n',
                                        'entry': 'CustomReview', 'label': 'Custom Review', 'constructorValues': {}})['definition']
        draft = insert(source_draft(analyze_source(SOURCE, 'model:Meadow')), custom['kind'], definition=custom)
        result = generate_model(draft)
        self.assertTrue(any(source['path'].startswith('archcanvas_custom_') for source in result['architecture']['sources']))
        all_bindings = {**result['nodeBindings'], **result['containerBindings']}
        self.assertIn('new_module', all_bindings)
        self.assertTrue(any(node['kind'] == 'Tanh' for node in result['architecture']['nodes']))
        with tempfile.TemporaryDirectory() as directory:
            for source in result['architecture']['sources']:
                path = Path(directory) / source['path']; path.parent.mkdir(parents=True, exist_ok=True); path.write_text(source['content'])
            self.assertEqual(analyze_project(directory, result['entry']), result['architecture'])

    def test_rewire_uses_preceding_local_value_without_reexecuting_producer(self):
        source = SOURCE.replace('  return self.drop(x)', '  y=self.drop(x)\n  z=self.head(x)\n  return y, z')
        draft = source_draft(analyze_source(source, 'model:Meadow'))
        output = fact_node(draft, 'Output')
        refs = draft['sourceProvenance']['nodeRefs']
        facts = {node['id']: node for node in draft['sourceProvenance']['architecture']['nodes']}
        head = next(node for node in draft['nodes'] if refs.get(node['id'], {}).get('kind') == 'Linear'
                    and facts[refs[node['id']]['nodeId']].get('source', {}).get('expression') == 'self.head(x)')
        port = next(port['id'] for module in draft['sourceProvenance']['modules'] if module['kind'] == head['kind'] for port in module['ports'] if port['direction'] == 'out')
        next(edge for edge in draft['edges'] if edge['target']['nodeId'] == output['id'])['source'] = {'nodeId': head['id'], 'portId': port}
        result = generate_model(draft)
        self.assertIn('  return z, z\n', result['source'])
        self.assertEqual(result['source'].count('z=self.head(x)'), 1)

    def test_unconsumed_new_module_and_unknown_relation_edits_are_rejected(self):
        draft = insert(source_draft(analyze_source(SOURCE, 'model:Meadow')))
        output = fact_node(draft, 'Output')
        edge = next(edge for edge in draft['edges'] if edge['target']['nodeId'] == output['id'])
        edge['source'] = deepcopy(next(edge for edge in draft['edges'] if edge['target']['nodeId'] == 'new_module')['source'])
        self.assertFalse(validate_draft(draft)['generation']['supported'])
        with self.assertRaises(DraftError): generate_model(draft)
        draft = source_draft(analyze_source(SOURCE, 'model:Meadow'))
        target = fact_node(draft, 'ConditionalRegion')
        incoming = next(edge for edge in draft['edges'] if edge['target']['nodeId'] == target['id'])
        draft['nodes'].append({'id': 'new_module', 'kind': 'Identity', 'label': 'New', 'parameters': {}, 'position': {'x': 0, 'y': 0}})
        old = deepcopy(incoming['source']); incoming['source'] = {'nodeId': 'new_module', 'portId': 'output'}
        draft['edges'].append({'id': 'new_edge', 'source': old, 'target': {'nodeId': 'new_module', 'portId': 'input'}})
        self.assertFalse(validate_draft(draft)['generation']['supported'])
        with self.assertRaises(DraftError): generate_model(draft)

    def test_shared_new_value_and_non_dominating_input_are_not_guessed(self):
        source = SOURCE.replace('  return self.drop(x)', '  y=self.drop(x)\n  return y, x')
        draft = insert(source_draft(analyze_source(source, 'model:Meadow')))
        outputs = [node for node in draft['nodes'] if draft['sourceProvenance']['nodeRefs'].get(node['id'], {}).get('kind') == 'Output']
        other = outputs[1]
        next(edge for edge in draft['edges'] if edge['target']['nodeId'] == other['id'])['source'] = {'nodeId': 'new_module', 'portId': 'output'}
        self.assertFalse(validate_draft(draft)['generation']['supported'])
        with self.assertRaises(DraftError): generate_model(draft)

    def test_whole_region_output_wraps_every_branch_return_with_inspection_receipt(self):
        source = SOURCE.replace('  return self.drop(x)', '  if flag:\n   return self.drop(x)\n  else:\n   return x')
        draft = insert(source_draft(analyze_source(source, 'model:Meadow')))
        result = generate_model(draft)
        tree = ast.parse(result['source'])
        returns = [node for node in ast.walk(tree) if isinstance(node, ast.Return)]
        self.assertEqual(len(returns), 2)
        self.assertTrue(all(isinstance(node.value, ast.Call) and node.value.func.attr.startswith('_archcanvas_') for node in returns))
        occurrence = result['verification']['operationOccurrences'][0]
        self.assertEqual(occurrence['binding'], 'source-inspection')
        self.assertEqual(len(occurrence['canonicalIds']), 2)

    def test_constructor_ownership_rejects_shadowed_super_and_rebound_self(self):
        for source in [SOURCE.replace('class Meadow', 'super = lambda: None\nclass Meadow'),
                       SOURCE.replace('super().__init__();', 'self = None; super().__init__();')]:
            with self.subTest(source=source):
                draft = insert(source_draft(analyze_source(source, 'model:Meadow')))
                self.assertFalse(validate_draft(draft)['generation']['supported'])
                with self.assertRaises(DraftError): generate_model(draft)

    def test_new_source_is_never_executed(self):
        with tempfile.TemporaryDirectory() as directory:
            sentinel = Path(directory) / 'executed'
            source = SOURCE.replace('class Meadow', f'open({str(sentinel)!r}, "w").write("executed")\nclass Meadow')
            draft = insert(source_draft(analyze_source(source, 'model:Meadow')))
            result = generate_model(draft)
            self.assertFalse(sentinel.exists())
            self.assertIn(f'open({str(sentinel)!r}', result['source'])

    def test_dynamic_attribute_consumers_keep_deleted_call_constructor(self):
        source = SOURCE + " def auxiliary(self,x):\n  return getattr(self,'drop')(x)\n"
        result = generate_model(delete(source_draft(analyze_source(source, 'model:Meadow'))))
        self.assertIn('self.drop=nn.Dropout(0.1)', result['source'])
        self.assertIn("getattr(self,'drop')(x)", result['source'])
        self.assertIn('  return x\n', result['source'])

    def test_instance_hooks_are_rejected_and_initializer_tail_follows_reset(self):
        source = SOURCE + " def __setattr__(self, name, value):\n  if name.startswith('_archcanvas_'): return\n  super().__setattr__(name, value)\n"
        draft = insert(source_draft(analyze_source(source, 'model:Meadow')))
        self.assertFalse(validate_draft(draft)['generation']['supported'])
        with self.assertRaises(DraftError): generate_model(draft)
        source = SOURCE.replace('self.drop=nn.Dropout(0.1)', 'self.drop=nn.Dropout(0.1); self.reset_modules()') + " def reset_modules(self):\n  self._modules.clear()\n"
        result = generate_model(insert(source_draft(analyze_source(source, 'model:Meadow'))))
        self.assertLess(result['source'].index('self.reset_modules()'), result['source'].index('self._archcanvas_'))

    def test_nested_deleted_calls_are_not_partially_composed(self):
        source = SOURCE.replace('return self.drop(x)', 'return self.drop(self.head(x))')
        draft = source_draft(analyze_source(source, 'model:Meadow'))
        delete(draft, 'Dropout'); delete(draft, 'Linear'); insert(draft)
        self.assertFalse(validate_draft(draft)['generation']['supported'])
        with self.assertRaises(DraftError): generate_model(draft)

    def test_rewire_rejects_mutation_unknown_call_and_alias_intervals(self):
        for mutation in ['y.add_(1)', 'unknown(y)', 'alias=y; alias.add_(1)']:
            source = SOURCE.replace('  if flag:\n   x=self.head(x)\n  return self.drop(x)', f'  y=self.head(x)\n  {mutation}\n  if flag:\n   x=unknown(x)\n  return x')
            draft = source_draft(analyze_source(source, 'model:Meadow'))
            head, output = fact_node(draft, 'Linear'), fact_node(draft, 'Output')
            spec = next(item for item in draft['sourceProvenance']['modules'] if item['kind'] == head['kind'])
            port = next(item['id'] for item in spec['ports'] if item['direction'] == 'out')
            next(edge for edge in draft['edges'] if edge['target']['nodeId'] == output['id'])['source'] = {'nodeId': head['id'], 'portId': port}
            self.assertFalse(validate_draft(draft)['generation']['supported'])
            with self.assertRaises(DraftError): generate_model(draft)

    def test_entry_callable_rebinding_cannot_produce_an_unused_edited_method(self):
        source = SOURCE.replace('self.drop=nn.Dropout(0.1)', 'self.drop=nn.Dropout(0.1); self.forward=self.identity') + ' def identity(self,x,flag):\n  return x\n'
        draft = insert(source_draft(analyze_source(source, 'model:Meadow')))
        self.assertFalse(validate_draft(draft)['generation']['supported'])
        with self.assertRaises(DraftError): generate_model(draft)

    def test_rewire_rejects_sibling_mutation_in_the_same_return_statement(self):
        source = SOURCE.replace('  if flag:\n   x=self.head(x)\n  return self.drop(x)', '  if flag:\n   x=unknown(x)\n  y=self.head(x)\n  return y.add_(1), x')
        draft = source_draft(analyze_source(source, 'model:Meadow'))
        refs = draft['sourceProvenance']['nodeRefs']
        facts = {node['id']: node for node in draft['sourceProvenance']['architecture']['nodes']}
        head = fact_node(draft, 'Linear')
        output = next(node for node in draft['nodes'] if refs[node['id']]['kind'] == 'Output'
                      and facts[refs[node['id']]['nodeId']]['outputPath'] == [{'kind': 'index', 'index': 1}])
        module = next(item for item in draft['sourceProvenance']['modules'] if item['kind'] == head['kind'])
        port = next(item['id'] for item in module['ports'] if item['direction'] == 'out')
        next(edge for edge in draft['edges'] if edge['target']['nodeId'] == output['id'])['source'] = {'nodeId': head['id'], 'portId': port}
        self.assertFalse(validate_draft(draft)['generation']['supported'])
        with self.assertRaises(DraftError): generate_model(draft)


if __name__ == '__main__': unittest.main()
