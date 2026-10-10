"""Unselected branches still expose real source; they never become tensor facts."""
import json
from pathlib import Path
import tempfile
import unittest

from archcanvas_python import analyze_source
from archcanvas_python.source_structure import MAX_STRUCTURE_NODES

SOURCE = '''from torch import nn
class MossBlock(nn.Module):
 def __init__(self):
  super().__init__(); self.projection=nn.Linear(7,7); self.activation=nn.GELU()
 def forward(self,x): return self.activation(self.projection(x))
class Tide(nn.Module):
 def __init__(self, configs):
  super().__init__(); self.flag=configs.decomposition
  if self.flag:
   self.residual=MossBlock(); self.trend=MossBlock()
  else: self.base=MossBlock()
 def forward(self,x):
  if self.flag: x=self.residual(x)+self.trend(x)
  else: x=self.base(x)
  return x
'''


class SourceRegionStructureTests(unittest.TestCase):
    def test_unknown_config_exposes_both_source_branches_and_nested_local_modules(self):
        architecture = analyze_source(SOURCE, 'model:Tide')
        facts = {n['id']: n for n in architecture['nodes']}
        region = next(n for n in facts.values() if n['kind'] == 'ConditionalRegion')
        self.assertEqual(region['evidence'], 'opaque')
        self.assertEqual([facts[id]['label'] for id in region['children']], ['if self.flag', 'else'])
        modules = [n for n in facts.values() if n.get('sourceStructure') and n['kind'] == 'SourceModule']
        self.assertEqual([n['label'] for n in modules if n['parameters']['sourceType'] == 'MossBlock'], ['residual', 'trend', 'base'])
        self.assertEqual(sum(n['parameters']['sourceType'] == 'nn.Linear' for n in modules), 3)
        self.assertEqual(sum(n['parameters']['sourceType'] == 'nn.GELU' for n in modules), 3)
        for node in facts.values():
            if node.get('sourceStructure'):
                self.assertEqual(node['ports'], [])
                self.assertNotIn('instanceId', node)
                self.assertNotIn('parameterOrigins', node)
                self.assertIn('source', node)
                self.assertEqual(node['evidence'], 'source')
        self.assertFalse(any(facts[e[end]['nodeId']].get('sourceStructure') for e in architecture['edges'] for end in ('source','target')))
        output = next(n for n in facts.values() if n['kind']=='Output')
        self.assertTrue(any(e['source']['nodeId']==region['id'] and e['target']['nodeId']==output['id'] for e in architecture['edges']))
        before = architecture
        after = analyze_source('# a comment must not rename inspection objects\n' + SOURCE, 'model:Tide')
        self.assertEqual([n['id'] for n in before['nodes']], [n['id'] for n in after['nodes']])
        self.assertEqual(before['irDigest'], after['irDigest'])
        self.assertNotEqual(before['sourceDigest'], after['sourceDigest'])

    def test_known_branch_is_selected_and_unknown_external_names_are_syntax_only(self):
        known = analyze_source(SOURCE.replace('configs.decomposition', 'False'), 'model:Tide')
        self.assertFalse(any(n.get('sourceStructure') for n in known['nodes']))
        self.assertEqual(sum(n['kind']=='Linear' for n in known['nodes']), 1)
        external = analyze_source(SOURCE.replace('MossBlock()', 'ExternalPlugin()'), 'model:Tide')
        self.assertFalse(any(n.get('sourceStructure') and n['parameters'].get('sourceType')=='nn.Linear' for n in external['nodes']))
        self.assertFalse(any(n['kind']=='Linear' for n in external['nodes']))

    def test_inspection_does_not_execute_source_or_unroll_symbolic_counts(self):
        with tempfile.TemporaryDirectory() as directory:
            sentinel=Path(directory)/'executed'
            source=f'''from torch import nn
open({str(sentinel)!r},'w').write('executed')
class Cell(nn.Module):
 def __init__(self):
  super().__init__(); self.linear=nn.Linear(4,4)
 def forward(self,x): return self.linear(x)
class Stack(nn.Module):
 def __init__(self, count):
  super().__init__(); self.layers=nn.ModuleList([Cell() for i in range(count)])
 def forward(self,x):
  for layer in self.layers: x=layer(x)
  return x
class Birch(nn.Module):
 def __init__(self, config):
  super().__init__(); self.flag=config.enabled
  if self.flag: self.stack=Stack(config.layers)
 def forward(self,x):
  if self.flag: x=self.stack(x)
  return x
'''
            a=analyze_source(source,'Birch')
            self.assertFalse(sentinel.exists())
            loops=[n for n in a['nodes'] if n.get('sourceStructure') and n['kind']=='SourceLoop']
            self.assertTrue(any('range(count)' in n['parameters'].get('repeatExpression','') for n in loops))
            self.assertFalse(any(n.get('repeat') for n in a['nodes'] if n.get('sourceStructure')))
            self.assertTrue(any(n['kind']=='SourceModule' and n['parameters'].get('sourceType')=='Cell' for n in a['nodes']))
            self.assertTrue(any(n['kind']=='SourceModule' and n['parameters'].get('sourceType')=='nn.Linear' for n in a['nodes']))
            self.assertLessEqual(sum(bool(n.get('sourceStructure')) for n in a['nodes']),MAX_STRUCTURE_NODES)
            json.dumps(a,allow_nan=False)

    def test_large_first_branch_cannot_hide_else_and_truncation_is_explicit(self):
        source=SOURCE.replace('  if self.flag: x=self.residual(x)+self.trend(x)', '  if self.flag:\n' + '\n'.join('   x=external_%d(x)' % i for i in range(600)))
        a=analyze_source(source, 'model:Tide')
        facts={n['id']:n for n in a['nodes']}
        region=next(n for n in a['nodes'] if n['kind']=='ConditionalRegion')
        self.assertEqual([facts[id]['label'] for id in region['children']], ['if self.flag','else'])
        self.assertTrue(facts[region['children'][1]]['children'], 'the smaller else branch is inspected before the first branch exhausts leaf budget')
        self.assertTrue(any('inspectionLimit' in n['parameters'] for n in a['nodes']))
        self.assertTrue(any('budget' in d['message'] for d in a['diagnostics']))
        self.assertLessEqual(sum(bool(n.get('sourceStructure')) for n in a['nodes']),MAX_STRUCTURE_NODES)
