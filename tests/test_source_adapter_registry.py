"""Independent data-adapter contract and no-execution regression fixtures."""
import copy
import json
import tempfile
import unittest
from pathlib import Path

from archcanvas_adapters import (
    AdapterError, AdapterRegistry, scaffold_adapter, scaffold_adapter_files,
    validate_adapter_files, apply_preview_adapters, enrich_preview,
)
from archcanvas_preview.analyze import Analyzer

def analyze(files, entry):
    return Analyzer(files).run(entry)

SOURCE = '''from torch import nn
class CopperSprig(nn.Module):
 def __init__(self):
  super().__init__()
  self.stem=nn.Linear(4,4); self.head=nn.GELU()
 def forward(self,x,flag=None):
  if flag:
   y=self.stem(x)
   y=self.head(y)
  else:
   y=self.head(x)
  return y, {"original": x}
'''
FILES = {'foreign.py': SOURCE}


class SourceAdapterRegistryTests(unittest.TestCase):
    def setUp(self):
        self.adapter = scaffold_adapter_files(FILES, 'foreign:CopperSprig')

    def test_scaffold_is_reproducible_and_preserves_slots(self):
        self.assertEqual(self.adapter, scaffold_adapter_files(FILES, 'foreign:CopperSprig'))
        self.assertEqual(self.adapter, validate_adapter_files(self.adapter, FILES))
        self.assertEqual([port['name'] for port in self.adapter['inputs']], ['x', 'flag'])
        self.assertEqual([port['path'] for port in self.adapter['outputs']], [
            [{'kind': 'index', 'index': 0}],
            [{'kind': 'index', 'index': 1}, {'kind': 'key', 'key': 'original'}],
        ])
        self.assertTrue(self.adapter['children'])
        self.assertTrue(all(node['ports'] == [] and node['sourceStructure'] for node in self.adapter['children']))
        self.assertIsNone(self.adapter['generationContract'])

    def test_scaffold_and_registry_do_not_execute_source(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            marker = root / 'MODEL_EXECUTED'
            source = f"open({str(marker)!r}, 'w').write('executed')\n" + SOURCE
            (root / 'foreign.py').write_text(source)
            definition = scaffold_adapter(root, 'foreign:CopperSprig')
            store = AdapterRegistry(root / 'data' / 'adapters')
            receipt = store.register(definition, root)
            self.assertEqual(receipt['status'], 'registered')
            self.assertFalse(marker.exists())
            self.assertEqual(store.resolve(root, 'foreign:CopperSprig'), definition)

    def test_presentation_is_reusable_and_original_source_unchanged(self):
        with tempfile.TemporaryDirectory() as temporary:
            store = AdapterRegistry(temporary)
            definition = copy.deepcopy(self.adapter)
            definition['presentation']['labels'][definition['children'][0]['id']] = '局部条件'
            definition['presentation']['notes'] = ['Both authored paths are inspected; execution remains unresolved.']
            saved = store.register_files(definition, FILES)
            self.assertTrue(Path(saved['path']).is_file())
            self.assertEqual(store.list_files(FILES)[0]['status'], 'valid')
            self.assertEqual(store.matching_files(FILES), [definition])
            self.assertEqual(store.resolve_files(FILES, 'foreign:CopperSprig'), definition)
            self.assertEqual(FILES['foreign.py'], SOURCE)

    def test_changed_source_missing_file_or_wrong_hash_rejected(self):
        mutations = [
            {'foreign.py': SOURCE + '\n# changed\n'},
            {**FILES, 'added.py': '# a new source file\n'},
        ]
        for changed in mutations:
            with self.subTest(changed=list(changed)):
                with self.assertRaisesRegex(AdapterError, 'stale'):
                    validate_adapter_files(self.adapter, changed)
        forged = copy.deepcopy(self.adapter)
        forged['binding']['sourceFiles'][0]['sha256'] = '0' * 64
        with self.assertRaisesRegex(AdapterError, 'stale'):
            validate_adapter_files(forged, FILES)

    def test_stale_records_are_listed_and_never_silently_applied(self):
        with tempfile.TemporaryDirectory() as temporary:
            store = AdapterRegistry(temporary)
            store.register_files(self.adapter, FILES)
            changed = {'foreign.py': SOURCE.replace('flag=None', 'flag=False')}
            self.assertEqual(store.list_files(changed)[0]['status'], 'stale')
            self.assertEqual(store.matching_files(changed), [])
            with self.assertRaisesRegex(AdapterError, 'stale'):
                store.resolve_files(changed, 'foreign:CopperSprig')

    def test_changed_generator_revision_is_stale_even_when_source_is_identical(self):
        previous = copy.deepcopy(self.adapter)
        previous.pop('generatorRevision')
        with self.assertRaisesRegex(AdapterError, 'stale: source inspection rules changed'):
            validate_adapter_files(previous, FILES)
        with tempfile.TemporaryDirectory() as temporary:
            Path(temporary, previous['id'] + '.json').write_text(json.dumps(previous))
            store = AdapterRegistry(temporary)
            self.assertEqual(store.list_files(FILES)[0]['status'], 'stale')
            self.assertEqual(store.matching_files(FILES), [])

    def test_forged_evidence_ports_generation_and_dependency_rejected(self):
        mutations = [
            lambda a: a['children'][0]['source'].__setitem__('line', 999),
            lambda a: a['children'][0].__setitem__('ports', [{'id': 'fake', 'direction': 'out'}]),
            lambda a: a.__setitem__('generationContract', {'python': "__import__('os').system('anything')"}),
            lambda a: a.__setitem__('pythonPlugin', 'arbitrary.py'),
            lambda a: a['inputs'][0].__setitem__('name', 'invented'),
            lambda a: a['outputs'][0].__setitem__('path', [{'kind': 'index', 'index': 93}]),
        ]
        for mutation in mutations:
            forged = copy.deepcopy(self.adapter)
            mutation(forged)
            with self.subTest(mutation=mutation), self.assertRaises(AdapterError):
                validate_adapter_files(forged, FILES)

    def test_unknown_dependencies_and_containment_cycles_rejected(self):
        forged = copy.deepcopy(self.adapter)
        forged['children'][0]['parentId'] = forged['children'][0]['id']
        with self.assertRaisesRegex(AdapterError, 'cyclic'):
            validate_adapter_files(forged, FILES)
        forged = copy.deepcopy(self.adapter)
        a, b = forged['children'][:2]
        source = forged['children'][0]['source']
        forged['dependencies'] = [
            {'id': 'a', 'sourceId': a['id'], 'targetId': b['id'], 'kind': 'value-dependency', 'source': source},
            {'id': 'b', 'sourceId': b['id'], 'targetId': a['id'], 'kind': 'value-dependency', 'source': source},
        ]
        with self.assertRaisesRegex(AdapterError, 'cycle'):
            validate_adapter_files(forged, FILES)
        forged['dependencies'][0]['sourceId'] = 'nonexistent'
        with self.assertRaisesRegex(AdapterError, 'invalid'):
            validate_adapter_files(forged, FILES)

    def test_config_is_identity_bound_and_finite(self):
        configured = scaffold_adapter_files(FILES, 'foreign:CopperSprig', config={'branch': True})
        self.assertNotEqual(self.adapter['id'], configured['id'])
        with self.assertRaises(AdapterError):
            scaffold_adapter_files(FILES, 'foreign:CopperSprig', config={'bad': float('nan')})

    def test_preview_appends_source_subtree_preserving_original_edges(self):
        original = analyze(FILES, 'foreign:CopperSprig')
        enriched = apply_preview_adapters(original, FILES, [self.adapter])
        self.assertGreater(len(enriched['ir']['nodes']), len(original['ir']['nodes']))
        self.assertEqual(enriched['ir']['edges'][:len(original['ir']['edges'])], original['ir']['edges'])
        self.assertEqual(enriched['ir']['nodes'][:len(original['ir']['nodes'])][0], original['ir']['nodes'][0])
        added = enriched['ir']['nodes'][len(original['ir']['nodes']):]
        self.assertTrue(all(node['sourceStructure'] and node['certainty'] == 'syntax' for node in added))
        self.assertEqual(enriched['files'], original['files'])
        self.assertEqual(enriched['sourceSha256'], original['sourceSha256'])
        self.assertEqual(json.loads(enriched['canonicalIR']), enriched['ir'])

    def test_explicit_then_automatic_is_idempotent_and_keeps_labels(self):
        original = analyze(FILES, 'foreign:CopperSprig')
        enriched = enrich_preview(original, FILES, [self.adapter])
        again = enrich_preview(enriched, FILES, [self.adapter])
        self.assertEqual(enriched, again)
        ids = [node['id'] for node in again['ir']['nodes']]
        self.assertEqual(len(ids), len(set(ids)))

    def test_registered_labels_replace_automatic_tree_without_duplicate_ids(self):
        original = analyze(FILES, 'foreign:CopperSprig')
        automatic = enrich_preview(original, FILES)
        registered = copy.deepcopy(self.adapter)
        child = registered['children'][0]
        registered['presentation']['labels'][child['id']] = 'Reviewed branch label'
        enriched = apply_preview_adapters(automatic, FILES, [registered])
        self.assertTrue(any(node['label'] == 'Reviewed branch label' for node in enriched['ir']['nodes']))
        self.assertEqual(len(automatic['ir']['nodes']), len(enriched['ir']['nodes']))
        self.assertEqual(len(enriched['ir']['nodes']), len({node['id'] for node in enriched['ir']['nodes']}))
        self.assertEqual(enriched, enrich_preview(enriched, FILES, [registered]))

    def test_preview_cannot_attach_an_adapter_to_other_source(self):
        original = analyze(FILES, 'foreign:CopperSprig')
        original['files'][0]['text'] += '\n# replaced source\n'
        with self.assertRaisesRegex(AdapterError, 'source does not match'):
            apply_preview_adapters(original, FILES, [self.adapter])

    def test_unknown_local_helper_can_be_registered_and_inspected(self):
        files = {'foreign.py': '''from torch import nn
def shape_unseen(x):
 a=x.sin()
 return a.cos()
class CopperSprig(nn.Module):
 def forward(self,x):
  return shape_unseen(x)
'''}
        helper = scaffold_adapter_files(files, 'foreign:shape_unseen')
        original = analyze(files, 'foreign:CopperSprig')
        enriched = enrich_preview(original, files, [helper])
        self.assertTrue(any(node.get('sourceAdapterId') == helper['id'] for node in enriched['ir']['nodes']))
        self.assertTrue(any(node['label'] == 'a.cos' for node in enriched['ir']['nodes']))

    def test_call_entry_and_multi_file_import_are_source_data(self):
        files = {'entry.py': '''from torch import nn
from cells import Petal
class Outer(nn.Module):
 def __init__(self):
  super().__init__(); self.cell=Petal()
 def __call__(self, x):
  return self.cell(x)
''', 'cells.py': '''from torch import nn
class Petal(nn.Module):
 def forward(self,x):
  return x.sin()
'''}
        definition = scaffold_adapter_files(files, 'entry:Outer')
        self.assertEqual(definition['binding']['method'], '__call__')
        self.assertTrue(any(node['source']['path'] == 'cells.py' for node in definition['children']))
        self.assertEqual(validate_adapter_files(definition, files), definition)

    def test_custom_call_overrides_forward_and_explicit_forward_can_be_selected(self):
        files = {'foreign.py': """from torch import nn
class Cedar(nn.Module):
 def forward(self, forward_x):
  return forward_x.sin()
 def __call__(self, call_x):
  return call_x.cos()
"""}
        default = scaffold_adapter_files(files, 'foreign:Cedar')
        explicit = scaffold_adapter_files(files, 'foreign:Cedar', method='forward')
        self.assertEqual(default['binding']['method'], '__call__')
        self.assertEqual(default['inputs'][0]['name'], 'call_x')
        self.assertEqual(explicit['binding']['method'], 'forward')
        self.assertEqual(explicit['inputs'][0]['name'], 'forward_x')
        self.assertEqual(validate_adapter_files(default, files), default)

    def test_inherited_method_binds_actual_source_and_preserves_entry_symbol(self):
        files = {'base.py': """from torch import nn
class Cedar(nn.Module):
 def forward(self, inherited_x):
  return inherited_x.sin()
""", 'foreign.py': """from base import Cedar
class Cypress(Cedar):
 pass
"""}
        adapter = scaffold_adapter_files(files, 'foreign:Cypress')
        self.assertEqual(adapter['binding']['entry'], 'foreign:Cypress')
        self.assertEqual(adapter['binding']['symbol']['path'], 'foreign.py')
        self.assertEqual(adapter['binding']['methodSpan']['path'], 'base.py')
        self.assertEqual(adapter['inputs'][0]['name'], 'inherited_x')
        self.assertTrue(all(child['source']['path'] == 'base.py' for child in adapter['children']))
        self.assertEqual(validate_adapter_files(adapter, files), adapter)

    def test_nested_local_opaque_region_uses_actual_method_owner(self):
        files = {'foreign.py': """from torch import nn
class Hidden(nn.Module):
 def forward(self,x):
  if x.sum() > 0:
   return x.sin()
  return x
class Wrapper(nn.Module):
 def __init__(self):
  super().__init__(); self.part=Hidden()
 def __call__(self,x):
  return self.part(x)
"""}
        preview = enrich_preview(analyze(files, 'foreign:Wrapper'), files)
        self.assertTrue(any(node.get('sourceStructure') for node in preview['ir']['nodes']))
        self.assertTrue(any('foreign:Hidden' in request['sourceSymbols'] for request in preview['adaptationRequests']))

    def test_registry_validates_source_paths_even_when_empty(self):
        with tempfile.TemporaryDirectory() as temporary:
            store = AdapterRegistry(temporary)
            for operation in (store.list_files, store.matching_files):
                with self.subTest(operation=operation), self.assertRaises(AdapterError):
                    operation({'../escape.py': SOURCE})

    def test_path_traversal_and_corrupt_registry_record_rejected(self):
        with self.assertRaises(AdapterError):
            scaffold_adapter_files({'../bad.py': SOURCE}, 'bad:CopperSprig')
        with tempfile.TemporaryDirectory() as temporary:
            store = AdapterRegistry(temporary)
            Path(temporary, 'adapter-' + '0' * 24 + '.json').write_text('{bad')
            self.assertEqual(store.list_files(FILES)[0]['status'], 'invalid')
            self.assertEqual(store.matching_files(FILES), [])
            malformed = {'id': 'adapter-' + '1' * 24, 'binding': []}
            Path(temporary, malformed['id'] + '.json').write_text(json.dumps(malformed))
            self.assertEqual([item['status'] for item in store.list_files(FILES)], ['invalid', 'invalid'])
            self.assertEqual(store.matching_files(FILES), [])


if __name__ == '__main__':
    unittest.main()
