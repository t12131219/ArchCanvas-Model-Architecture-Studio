"""Bounded constructor contexts, pure factories and framework state contracts."""
import unittest
from archcanvas_python import analyze_source


class ConstructorContextTests(unittest.TestCase):
    def test_assignment_factory_and_keyword_constructor_binding(self):
        source='''from torch import nn
def cell(width):
 first=nn.Linear(width,width)
 result=nn.Sequential(first,nn.GELU())
 return result
class Garden(nn.Module):
 def __init__(self,*,width=5):
  super().__init__(); self.layers=cell(width)
 def forward(self,x): return self.layers(x)
'''
        architecture=analyze_source(source,'Garden')
        self.assertEqual([node['parameters'] for node in architecture['nodes'] if node['kind']=='Linear'], [{'in_features':5,'out_features':5}])
        self.assertEqual(sum(node['kind']=='GELU' for node in architecture['nodes']),1)
        for changed in [source.replace('first=nn.Linear(width,width)', 'open("must-not-run","w"); first=nn.Linear(width,width)'),
                        source.replace('result=nn.Sequential(first,nn.GELU())', 'result=mystery(first)')]:
            actual=analyze_source(changed,'Garden')
            self.assertFalse(any(node['kind']=='Linear' for node in actual['nodes']))

    def test_inherited_initializer_super_arguments_and_sequential_index(self):
        source='''from torch import nn
class Stem(nn.Module):
 def __init__(self,width):
  super().__init__(); self.proj=nn.Linear(width,width)
 def forward(self,x): return self.proj(x)
class Inherited(Stem): pass
class Leaf(Stem):
 def __init__(self): super().__init__(7)
class Pair(nn.Sequential):
 def __init__(self): super().__init__(Inherited(4),Leaf())
 def forward(self,x): return self[1](self[0](x))
'''
        architecture=analyze_source(source,'Pair')
        self.assertEqual([node['parameters'] for node in architecture['nodes'] if node['kind']=='Linear'],
                         [{'in_features':4,'out_features':4},{'in_features':7,'out_features':7}])
        self.assertEqual(len({node['instanceId'] for node in architecture['nodes'] if node['kind']=='Linear'}),2)

    def test_buffer_registration_preserves_unrelated_modules_but_not_overrides(self):
        source='''import torch
from torch import nn
class Orchard(nn.Module):
 def __init__(self):
  super().__init__(); self.proj=nn.Linear(4,3)
  self.register_buffer('memory', torch.zeros(4))
 def forward(self,x): return self.proj(x)
'''
        self.assertEqual(sum(node['kind']=='Linear' for node in analyze_source(source,'Orchard')['nodes']),1)
        for addition in [" def register_buffer(self,*a): self.proj=dangerous()\n", '']:
            unsafe=source+addition if addition else source.replace("torch.zeros(4)", "mutate(self.proj)")
            self.assertFalse(any(node['kind']=='Linear' for node in analyze_source(unsafe,'Orchard')['nodes']))
        inherited=source+'''class Shadow(Orchard):
 def register_buffer(self,*args): self.proj=dangerous()
'''
        self.assertFalse(any(node['kind']=='Linear' for node in analyze_source(inherited,'Shadow')['nodes']))


if __name__=='__main__': unittest.main()
