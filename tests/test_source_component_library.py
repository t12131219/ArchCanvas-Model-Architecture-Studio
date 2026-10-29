"""Conservative deduplication and portable source boundaries, without Torch."""
import copy
import importlib.util
import json
import unittest
import tempfile
from pathlib import Path

spec = importlib.util.spec_from_file_location('components', Path(__file__).parents[1] / 'scripts/build_source_component_library.py')
components = importlib.util.module_from_spec(spec)
spec.loader.exec_module(components)


def example():
    nodes = [dict(id='root', label='VeryLongExample', source_class='VeryLongExample', kind='composite', parent=None, source=[]),
             dict(id='x', label='x', kind='interface', parent='root', role='input', slot='x'),
             dict(id='linear', label='self.long_linear_name', kind='compute', parent='root', operator='linear', framework_type='torch.nn.Linear', constructor={'args': [8, 16]}),
             dict(id='weight', label='weight', kind='parameter', parent='root', parameter_scope='long_linear_name'),
             dict(id='out', label='out', kind='interface', parent='root', role='output', slot='out')]
    edges = [dict(id='a', source='x', target='linear', source_port='out', target_port='arg:0', kind='data'),
             dict(id='b', source='weight', target='linear', source_port='out', target_port='in', kind='parameter-read'),
             dict(id='c', source='linear', target='out', source_port='out', target_port='in', kind='data')]
    return dict(nodes=nodes, edges=edges, sources=[])


class SourceComponentsTest(unittest.TestCase):
    def test_source_identifiers_are_never_translated_and_matching_is_pure(self):
        node = dict(source_class='PositionwiseFeedForward', label='self.feed_forward')
        self.assertEqual(components.short_name(node), 'PositionwiseFeedForward')
        module = components.extract(example(), example()['nodes'][0])
        before = copy.deepcopy(module)
        components.fingerprints(module)
        self.assertEqual(module, before)

    def test_shipped_library_is_reproducible_and_owns_all_its_assets(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            catalog = components.build(output=output)
            self.assertEqual(catalog['stats']['families'], 100)
            for generated in output.glob('*.json'):
                self.assertEqual(generated.read_bytes(), (components.OUTPUT / generated.name).read_bytes(), generated.name)
            self.assertEqual(len(list(output.glob('*.json'))), len(list(components.OUTPUT.glob('*.json'))))

    def test_renamed_instances_merge_but_semantic_differences_do_not(self):
        ir = example()
        module = components.extract(ir, ir['nodes'][0])
        renamed = json.loads(json.dumps(ir).replace('root', 'another-root').replace('long_linear_name', 'other_name').replace('VeryLongExample', 'Short'))
        self.assertEqual(components.fingerprints(module), components.fingerprints(components.extract(renamed, renamed['nodes'][0])))
        changed = copy.deepcopy(module)
        changed['ir']['nodes'][2]['constructor']['args'][1] = 32
        a, b = components.fingerprints(module), components.fingerprints(changed)
        self.assertEqual(a[0], b[0], 'parameter variants share a structural family')
        self.assertNotEqual(a[1], b[1], 'literal parameter values remain distinct')
        for field, value in [('operator', 'add'), ('framework_type', 'torch.nn.Conv2d')]:
            changed = copy.deepcopy(module)
            changed['ir']['nodes'][2][field] = value
            self.assertNotEqual(a[0], components.fingerprints(changed)[0])
        changed = copy.deepcopy(module)
        changed['ir']['edges'][0]['target_port'] = 'arg:1'
        self.assertNotEqual(a[1], components.fingerprints(changed)[1])

    def test_standalone_atom_keeps_resources_and_exact_crossing_slots(self):
        ir = example()
        ir['nodes'].append(dict(id='other_call', label='other_call', kind='compute', parent='root'))
        ir['edges'].append(dict(id='shared', source='weight', target='other_call', source_port='out', target_port='in', kind='parameter-read'))
        original = copy.deepcopy(ir)
        module = components.extract(ir, ir['nodes'][2])
        nodes = {n['id']: n for n in module['ir']['nodes']}
        self.assertEqual(module['title'], 'Linear')
        self.assertIn('weight', nodes)
        self.assertEqual([n['slot'] for n in nodes.values() if n['kind'] == 'interface'], ['arg:0', 'out'])
        self.assertTrue(any(e['target'] == 'linear' and e['target_port'] == 'arg:0' for e in module['ir']['edges']))
        self.assertTrue(all(e['source'] in nodes and e['target'] in nodes for e in module['ir']['edges']))
        self.assertEqual(ir, original, 'extraction never mutates the source IR')

    def test_existing_module_ports_are_not_duplicated_and_runtime_is_excluded(self):
        ir = example()
        ir['nodes'].extend([dict(id='external', label='external', kind='compute', parent=None),
                            dict(id='runtime:call', label='sample', kind='compute', parent='root', evidence_status='runtime-only')])
        ir['edges'].append(dict(id='outer', source='external', target='x', source_port='out', target_port='x', kind='interface-binding'))
        module = components.extract(ir, ir['nodes'][0])
        self.assertEqual(sum(n['kind'] == 'interface' and n['role'] == 'input' for n in module['ir']['nodes']), 1)
        self.assertFalse(any(n['id'].startswith('runtime:') for n in module['ir']['nodes']))
        self.assertEqual([n['id'] for n in components.candidates(ir)], ['root', 'linear'])

    def test_sharing_and_constant_changes_are_not_erased(self):
        module = components.extract(example(), example()['nodes'][0])
        changed = copy.deepcopy(module)
        changed['ir']['nodes'].append(dict(id='second', kind='parameter', label='second', parent='root', parameter_scope='other'))
        changed['ir']['edges'][1]['source'] = 'second'
        self.assertNotEqual(components.fingerprints(module), components.fingerprints(changed))


if __name__ == '__main__':
    unittest.main()
