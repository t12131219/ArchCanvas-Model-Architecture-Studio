"""Source inspection preserves call evidence and shares a finite view budget."""
import copy
import unittest

from archcanvas_adapters import AdapterError, apply_preview_adapters, scaffold_adapter_files, validate_adapter_files
from archcanvas_preview import analyze
from archcanvas_preview.analyze import Analyzer


def source_with_helpers(sizes):
    functions = []
    for index, size in enumerate(sizes):
        functions.append(f'def inspect_{index}(x):\n' + ''.join(f' x=inside_{index}_{leaf}(x)\n' for leaf in range(size)) + ' return x\n')
    return 'from torch import nn\n' + ''.join(functions) + 'class Orchard(nn.Module):\n def forward(self,x):\n' + ''.join(f'  x=inspect_{index}(x)\n' for index in range(len(sizes))) + '  return x\n'


class PreviewInspectionCoverageTests(unittest.TestCase):
    def test_small_later_regions_do_not_cause_unnecessary_first_region_truncation(self):
        source = source_with_helpers([80])
        source = source.replace('  return x\n', ''.join(f'  unused=outside_{index}(x)\n' for index in range(10)) + '  return x\n')
        bundle = analyze({'model.py': source}, 'Orchard')
        self.assertEqual(bundle['coverage']['opaqueBoundaries'], 11)
        self.assertEqual(bundle['coverage']['inspectedOpaqueBoundaries'], 11)
        self.assertEqual(bundle['coverage']['truncatedInspections'], 0)
        self.assertTrue(any(node['label'] == 'inside_0_79' for node in bundle['ir']['nodes']))
        self.assertLess(len(bundle['ir']['nodes']), 480)

    def test_oversized_siblings_each_keep_source_cards_with_explicit_truncation(self):
        bundle = analyze({'model.py': source_with_helpers([300, 300, 3])}, 'Orchard')
        records = bundle['sourceAdapters']
        self.assertEqual(len(records), 3)
        self.assertGreater(records[0]['nodes'], 0)
        self.assertLessEqual(abs(records[0]['nodes'] - records[1]['nodes']), 1)
        self.assertTrue(records[0]['truncated'])
        self.assertTrue(records[1]['truncated'])
        self.assertFalse(records[2]['truncated'])
        self.assertEqual(len(bundle['ir']['nodes']), 480)

    def test_registered_replacement_reuses_full_budget_without_losing_other_regions(self):
        files = {'model.py': source_with_helpers([300, 300, 3])}
        automatic = analyze(files, 'Orchard')
        definitions = [scaffold_adapter_files(files, f'model:inspect_{index}') for index in range(3)]
        for index, definition in enumerate(definitions):
            definition['presentation']['labels'][definition['children'][0]['id']] = f'Reviewed region {index}'
        registered = apply_preview_adapters(automatic, files, definitions)
        self.assertEqual(len(registered['ir']['nodes']), 480)
        self.assertEqual(len({node['id'] for node in registered['ir']['nodes']}), 480)
        self.assertEqual(len(registered['sourceAdapters']), 3)
        for index in range(3):
            self.assertTrue(any(node['label'] == f'Reviewed region {index}' for node in registered['ir']['nodes']))
        self.assertEqual(apply_preview_adapters(registered, files, definitions), registered)

    def test_call_sites_bind_exact_multifile_source_without_changing_tensor_edges(self):
        files = {'entry.py': '''from torch import nn
from cells import Cell
class Orchard(nn.Module):
 def __init__(self):
  super().__init__(); self.first=Cell(); self.second=Cell()
 def __call__(self,x,flag):
  if flag: x=self.first(x)
  else: x=self.second(x)
  return x
''', 'cells.py': '''from torch import nn
class Cell(nn.Module):
 def __init__(self):
  super().__init__(); self.proj=nn.Linear(4,4)
 def forward(self,x): return self.proj(x)
'''}
        adapter = scaffold_adapter_files(files, 'entry:Orchard')
        self.assertEqual(validate_adapter_files(adapter, files), adapter)
        modules = [node for node in adapter['children'] if node['kind'] == 'SourceModule']
        self.assertEqual({node['label'] for node in modules if node['parameters']['sourceType'] == 'Cell'}, {'first', 'second'})
        for module in modules:
            for site in module['parameters']['callSites']:
                self.assertIn(site['expression'], '\n'.join(files[site['path']].splitlines()[site['line']-1:site['endLine']]))
        original = Analyzer(files).run('Orchard')
        enriched = apply_preview_adapters(original, files, [adapter])
        self.assertEqual(enriched['ir']['edges'][:len(original['ir']['edges'])], original['ir']['edges'])
        added = enriched['ir']['nodes'][len(original['ir']['nodes']):]
        self.assertEqual({node['sourceParameters'].get('sourceType') for node in added if node.get('sourceKind') == 'SourceModule'}, {'Cell', 'nn.Linear'})
        self.assertTrue(all(node['certainty'] == 'syntax' and node['generationContract'] is None for node in added))
        self.assertTrue(all(edge.get('syntaxOnly') for edge in enriched['ir']['edges'][len(original['ir']['edges']):]))

    def test_forged_call_evidence_and_previous_generator_revision_are_rejected(self):
        files = {'model.py': '''from torch import nn
class Orchard(nn.Module):
 def __init__(self): super().__init__(); self.proj=nn.Linear(4,4)
 def forward(self,x,flag):
  if flag: return self.proj(x)
  return x
'''}
        adapter = scaffold_adapter_files(files, 'model:Orchard')
        forged = copy.deepcopy(adapter)
        module = next(node for node in forged['children'] if node['kind'] == 'SourceModule')
        module['parameters']['callSites'][0]['expression'] = 'invented_tensor_path(x)'
        with self.assertRaises(AdapterError):
            validate_adapter_files(forged, files)
        previous = copy.deepcopy(adapter)
        previous['generatorRevision'] = 'source-inspection/2'
        with self.assertRaisesRegex(AdapterError, 'stale: source inspection rules changed'):
            validate_adapter_files(previous, files)


if __name__ == '__main__':
    unittest.main()
