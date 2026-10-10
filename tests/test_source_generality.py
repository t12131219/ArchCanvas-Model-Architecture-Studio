"""Independent unknown-name and negative-boundary contracts; no model runs."""
import tempfile
import unittest
from pathlib import Path
from archcanvas_python import analyze_source

class SourceGeneralityTests(unittest.TestCase):
    def test_unseen_helpers_module_arguments_and_copy_factory(self):
        source = '''from torch import nn
import copy
def replicate_unit(unit, count):
    return nn.ModuleList([copy.deepcopy(unit) for unused in range(count)])
class UnseenCell(nn.Module):
    def __init__(self):
        super().__init__(); self.proj = nn.Linear(7,7)
    def forward(self, x): return self.proj(x)
class UnseenStack(nn.Module):
    def __init__(self, cell, count=3):
        super().__init__(); self.units = replicate_unit(cell, count)
    def forward(self, x):
        for unit in self.units: x = unit(x)
        return x
class OrchardNetwork(nn.Module):
    def __init__(self):
        super().__init__(); cell = UnseenCell(); self.stack = UnseenStack(cell)
        self.choice = True; self.activation = nn.GELU()
    def prepare(self, x, *, activate=True):
        if activate: return self.activation(self.stack(x))
        return self.stack(x)
    def forward(self, first, second):
        if self.choice: return {"primary": self.prepare(first), "secondary": self.prepare(second, activate=False)}
        return first
'''
        a = analyze_source(source, 'model:OrchardNetwork')
        leaves = [n for n in a['nodes'] if n['kind'] == 'Linear']
        self.assertEqual(len(leaves), 6)
        self.assertEqual(len({n['instanceId'] for n in leaves}), 3)
        self.assertEqual(sum(n['kind'] == 'GELU' for n in a['nodes']), 1)
        self.assertEqual([n['repeat'] for n in a['nodes'] if n.get('repeat')], [{'count':3,'sharing':'independent'}]*2)
        self.assertFalse(any(n['evidence']=='opaque' for n in a['nodes']), a['diagnostics'])
        self.assertEqual([n['outputPath'] for n in a['nodes'] if n['kind']=='Output'], [[{'kind':'key','key':'primary'}],[{'kind':'key','key':'secondary'}]])

    def test_unproven_helpers_factories_and_dynamic_paths_remain_opaque(self):
        with tempfile.TemporaryDirectory() as directory:
            sentinel = Path(directory) / 'must-not-exist'
            source = f'''from torch import nn
import copy
open({str(sentinel)!r}, 'w').write('executed')
def unsafe_factory(cell, count):
    open({str(sentinel)!r}, 'w').write('factory')
    return nn.ModuleList([copy.deepcopy(cell) for i in range(count)])
class UnknownNetwork(nn.Module):
    def __init__(self):
        super().__init__(); self.layers=unsafe_factory(nn.Linear(4,4),2)
    @unregistered_decorator
    def transform(self,x): return self.layers(x)
    def forward(self,x,flag):
        y = self.transform(x)
        if flag: return y
        return mystery(x)
'''
            a = analyze_source(source, 'model:UnknownNetwork')
            self.assertFalse(sentinel.exists())
            self.assertTrue(any(n['kind']=='self.transform' and n['evidence']=='opaque' for n in a['nodes']))
            self.assertTrue(any(n['kind']=='ConditionalRegion' and n['evidence']=='opaque' for n in a['nodes']))
            self.assertFalse(any(n['kind']=='Linear' for n in a['nodes']))

    def test_factory_rebinding_does_not_inherit_pure_contract(self):
        source = '''from torch import nn
import copy
def builder(cell, n): return nn.ModuleList([copy.deepcopy(cell) for i in range(n)])
builder = other_function
class Novel(nn.Module):
 def __init__(self):
  super().__init__(); self.layers=builder(nn.Linear(2,2),2)
 def forward(self,x): return self.layers(x)
'''
        a=analyze_source(source,'Novel')
        self.assertTrue(any(n['evidence']=='opaque' for n in a['nodes']))
        self.assertFalse(any(n.get('repeat') for n in a['nodes']))

if __name__ == '__main__': unittest.main()

class ParameterInitializerContracts(unittest.TestCase):
    def test_parameter_only_helper_preserves_topology_without_running(self):
        source = '''from torch import nn
class UnknownName(nn.Module):
 def __init__(self):
  super().__init__(); self.layer=nn.Linear(3,3); self.initialize_tensors()
 def initialize_tensors(self):
  for tensor in self.parameters():
   if tensor.dim()>1: nn.init.xavier_uniform_(tensor)
 def forward(self,x): return self.layer(x)
'''
        a = analyze_source(source, 'UnknownName')
        self.assertEqual(sum(n['kind']=='Linear' for n in a['nodes']),1)
        for body in ['self.layer = dangerous()', 'dangerous(tensor)', 'self.replace_modules(tensor)']:
            bad = source.replace('if tensor.dim()>1: nn.init.xavier_uniform_(tensor)', body)
            result = analyze_source(bad, 'UnknownName')
            self.assertFalse(any(n['kind']=='Linear' for n in result['nodes']))
            self.assertTrue(any(n['evidence']=='opaque' for n in result['nodes']))

class AbstractModuleAliasTests(unittest.TestCase):
 def test_unknown_local_module_mutation_cannot_leave_a_proven_contract(self):
  for mutation in ['dangerous(cell)', 'result = dangerous(cell)', 'cell.forward = foreign_forward']:
   source=f'''from torch import nn
class Garden(nn.Module):
 def __init__(self):
  super().__init__(); cell=nn.Linear(3,3); self.alias=cell
  {mutation}
  self.layer=cell
 def forward(self,x): return self.layer(self.alias(x))
'''
   a=analyze_source(source,'Garden')
   self.assertFalse(any(n['kind']=='Linear' for n in a['nodes']))
   self.assertEqual(sum(n['kind']=='OpaqueModule' for n in a['nodes']),2)
