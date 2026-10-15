"""Source inventory facts, unknown boundaries and actual entry dispatch."""
import json
from pathlib import Path
import tempfile
import unittest

from archcanvas_python.discovery import (DiscoveryError, ModelIndex, discover_directory,
                                         discover_files, read_directory_files)
from archcanvas_python.frontend import AnalysisError, analyze_project, analyze_source
from archcanvas_preview.analyze import AdapterError, analyze


class ModelDiscoveryTests(unittest.TestCase):
    def test_alias_indirect_inheritance_custom_call_and_non_model(self):
        files = {
            'pkg/__init__.py': 'from .base import Child as Exported\n',
            'pkg/base.py': '''import torch.nn as layers
BaseAlias = layers.Module
class Base(BaseAlias):
    def forward(self, x): return x + x
class Child(Base): pass
class Callable(Base):
    def __call__(self, x): return x * x
class NotAModel:
    def forward(self, x): return x
''',
            'top.py': '''from pkg import Exported
class Final(Exported): pass
''',
        }
        result = discover_files(files)
        models = {item['id']: item for item in result['models']}
        self.assertEqual(set(models), {'pkg.base:Base', 'pkg.base:Child', 'pkg.base:Callable', 'top:Final'})
        self.assertEqual(models['top:Final']['methodOwner'], 'pkg.base:Base')
        self.assertEqual(models['pkg.base:Callable']['entryMethod'], '__call__')
        self.assertEqual(len(result['classes']), 5)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name, content in files.items():
                target = root / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(content)
            graph = analyze_project(root, 'top:Final')
            self.assertTrue(any(node['kind'] == 'Add' for node in graph['nodes']))
            self.assertTrue(any(node['source']['path'] == 'pkg/base.py' for node in graph['nodes'] if node.get('source')))
        preview = analyze(files, 'top:Final')
        self.assertTrue(any(node['kind'] == 'add' for node in preview['ir']['nodes']))

    def test_factory_tuple_argument_alias_and_unknown_repeat_containment(self):
        source = '''from torch import nn
import copy
raise RuntimeError("source must never run")
class Leaf(nn.Module):
    def forward(self, x): return x
class Stack(nn.Module):
    def __init__(self, layer, count):
        super().__init__()
        self.layers = clones(layer, count)
    def forward(self, x): return x
class Parent(nn.Module):
    def __init__(self):
        super().__init__()
        model, optimizer = build()
        self.encoder = model
        self.shared = self.encoder
    def forward(self, x): return x
def clones(module, n):
    return nn.ModuleList([copy.deepcopy(module) for i in range(n)])
def build():
    layer = Leaf()
    model = Stack(layer, unknown_count)
    optimizer = unavailable_optimizer(model)
    return model, optimizer
'''
        result = discover_files({'network.py': source})
        self.assertFalse(result['modelExecuted'])
        edges = result['relationships']
        self.assertTrue(any(row['owner'] == 'network:Parent' and row['target'] == 'network:Stack' and row['slot'] == 'encoder' for row in edges))
        leaves = [row for row in edges if row['owner'] == 'network:Stack' and row['target'] == 'network:Leaf']
        self.assertTrue(leaves)
        self.assertTrue(all(row['count'] is None for row in leaves))
        self.assertTrue(all(row['targetEvidence']['expression'] == 'Leaf()' for row in leaves))
        self.assertTrue(all(row['copyEvidence']['expression'] == 'copy.deepcopy(module)' for row in leaves))
        self.assertTrue(all(row['ownership'] == 'copy-candidate' for row in leaves))
        self.assertFalse(result['hierarchyComplete'])
        aliases = [row for row in edges if row['owner'] == 'network:Parent' and row['target'] == 'network:Stack']
        self.assertEqual(len({row['instanceId'] for row in aliases}), 1)
        self.assertEqual(aliases[0]['targetEvidence']['expression'], 'Stack(layer, unknown_count)')
        self.assertTrue(result['inventoryComplete'])

    def test_conditional_factories_do_not_select_a_runtime_arm(self):
        result = discover_files({'module.py': '''import torch.nn as nn
class A(nn.Module):
    def forward(self,x): return x
class B(nn.Module):
    def forward(self,x): return x
class Root(nn.Module):
    def __init__(self):
        self.child = choose(runtime_flag)
    def forward(self,x): return x
def choose(flag):
    if flag:
        return A()
    return B()
'''})
        children = [row for row in result['relationships'] if row['owner'] == 'module:Root']
        self.assertEqual({row['target'] for row in children}, {'module:A', 'module:B'})
        self.assertTrue(all(row['certainty'] == 'possible' for row in children))

    def test_call_dispatch_precedes_even_a_direct_forward(self):
        source = '''import torch.nn as nn
class Base(nn.Module):
    def __call__(self, x, /, *, mask=None): return x * x
class Model(Base):
    def forward(self, x): return x + x
'''
        formal = analyze_source(source, 'Model')
        kinds = {node['kind'] for node in formal['nodes']}
        self.assertIn('Multiply', kinds)
        self.assertNotIn('Add', kinds)
        preview = analyze({'model.py': source}, 'Model')
        self.assertTrue(any(node['kind'] == 'multiply' for node in preview['ir']['nodes']))
        self.assertFalse(any(node['kind'] == 'add' for node in preview['ir']['nodes']))

    def test_inherited_forward_uses_defining_globals_not_child_or_init_locals(self):
        files={'base.py':'''import torch.nn as nn
FLAG=True
class Base(nn.Module):
 def __init__(self): self.activation=nn.ReLU()
 def forward(self,x):
  if FLAG: return self.activation(x)
  return x
''','model.py':'''from base import Base
FLAG=False
class Model(Base):
 def __init__(self): super().__init__()
'''}
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            for path,text in files.items(): (root/path).write_text(text)
            graph=analyze_project(root,'model:Model')
            self.assertTrue(any(node['kind']=='ReLU' and node.get('evidence')=='contract' for node in graph['nodes']))
        # A bare initializer parameter is not a variable in a method's scope.
        source='''import torch.nn as nn
class Model(nn.Module):
 def __init__(self, flag=True): self.activation=nn.ReLU()
 def forward(self,x):
  if flag: return self.activation(x)
  return x
'''
        graph=analyze_source(source,'Model')
        self.assertTrue(any(node['kind']=='ConditionalRegion' for node in graph['nodes']))
        self.assertFalse(any(node['kind']=='ReLU' and node.get('evidence')=='contract' for node in graph['nodes']))

    def test_c3_diamond_resolution_and_invalid_order(self):
        source = '''import torch.nn as nn
class A(nn.Module):
    def forward(self,x): return x
class B(A): pass
class C(A):
    def forward(self,x): return x + x
class D(B,C): pass
class Broken(A,B): pass
'''
        index = ModelIndex({'model.py': source})
        method = index.effective_method('model:D')
        self.assertEqual(method[1].lineno, 6)
        self.assertIsNone(index.effective_method('model:Broken'))
        result = discover_files({'model.py': source})
        self.assertFalse(next(row for row in result['models'] if row['id'] == 'model:Broken')['openable'])

    def test_reassigned_call_decorators_and_external_mixins_block_dispatch(self):
        source = '''import torch.nn as nn
from absent import Mixin
class Rebound(nn.Module):
    def forward(self,x): return x
    __call__ = unknown_callable
@replace_class
class Decorated(nn.Module):
    def forward(self,x): return x
class Mixed(Mixin,nn.Module):
    def forward(self,x): return x
'''
        result = discover_files({'model.py': source})
        self.assertEqual(len(result['models']), 3)
        self.assertTrue(all(not row['openable'] for row in result['models']))
        for entry in ('Rebound','Decorated','Mixed'):
            with self.assertRaises((AnalysisError, AdapterError)):
                analyze_source(source, entry)

    def test_local_torch_cannot_license_framework_contract(self):
        result = discover_files({'torch/__init__.py': 'class Module: pass',
                                 'model.py': 'from torch import nn\nclass Fake(nn.Module):\n def forward(self,x): return x\n'})
        self.assertEqual(result['models'], [])
        self.assertEqual(result['candidates'], [])

    def test_rebound_class_is_inventory_only_and_cannot_open_old_definition(self):
        source = 'import torch.nn as nn\nclass Model(nn.Module):\n def forward(self,x): return x\nModel = replace_model()\n'
        result = discover_files({'model.py': source})
        self.assertEqual(len(result['models']), 1)
        self.assertFalse(result['models'][0]['openable'])
        self.assertEqual(result['candidates'], [])
        with self.assertRaises(AnalysisError): analyze_source(source, 'Model')
        with self.assertRaises(AdapterError): analyze({'model.py': source}, 'Model')

    def test_module_scope_patches_never_license_old_entry_methods(self):
        prefix = '''import torch.nn as nn
class Base(nn.Module):
    def forward(self,x): return x + x
class Child(Base): pass
'''
        for patch in ('Base.forward = foreign_fn', 'if unknown:\n Base.forward = foreign_fn',
                      'del Base.forward', 'setattr(Base, "forward", foreign_fn)',
                      'if unknown:\n setattr(Base, "__call__", foreign_fn)',
                      'setattr(Base, unknown_name, foreign_fn)', 'Base.__dict__["forward"] = foreign_fn'):
            with self.subTest(patch=patch):
                source = prefix + patch + '\n'
                index = ModelIndex({'model.py': source})
                self.assertIsNone(index.effective_method('model:Child'))
                with self.assertRaises(AnalysisError): analyze_source(source, 'Child')
                with self.assertRaises(AdapterError): analyze({'model.py': source}, 'Child')
        conditional_rebind = prefix + 'if unknown:\n Base = replacement\n'
        self.assertFalse(next(row for row in discover_files({'model.py':conditional_rebind})['models'] if row['id']=='model:Base')['openable'])

    def test_imported_alias_patch_and_constructor_patch_keep_unknown_attributes(self):
        files = {'base.py': '''import torch.nn as nn
class Base(nn.Module):
    def __init__(self): self.layer = nn.ReLU()
    def forward(self,x): return self.layer(x)
''', 'model.py': '''from base import Base as Alias
class Child(Alias): pass
if unknown:
 setattr(Alias, '__init__', foreign_init)
'''}
        index = ModelIndex(files)
        self.assertTrue(index.method_blocked('model:Child','__init__'))
        self.assertIsNone(index.method('model:Child','__init__'))
        preview = analyze(files, 'model:Child')
        self.assertEqual(preview['ir']['nodes'][0]['kind'], 'opaque')
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for path,text in files.items(): (root/path).write_text(text)
            graph=analyze_project(root,'model:Child')
            self.assertFalse(any(node['kind']=='ReLU' and not node.get('sourceStructure') for node in graph['nodes']))
            self.assertTrue(any(node['category']=='opaque' for node in graph['nodes']))

    def test_invalid_or_expanded_arguments_cannot_establish_containment(self):
        prefix = '''import torch.nn as nn
class Leaf(nn.Module):
 def forward(self,x): return x
class Holder(nn.Module):
 def __init__(self, child, /): self.child = child
 def forward(self,x): return x
'''
        for call in ('Holder(Leaf(), child=Leaf())', 'Holder(child=Leaf())',
                     'Holder(Leaf(), unrelated=Leaf())', 'Holder(Leaf(), Leaf())',
                     'Holder(*unknown_items)', 'Holder(**unknown_keywords)'):
            with self.subTest(call=call):
                result=discover_files({'model.py':prefix+'def build():\n return '+call+'\n'})
                self.assertFalse(any(row['owner']=='model:Holder' and row['target']=='model:Leaf' for row in result['relationships']))
                self.assertFalse(result['hierarchyComplete'])
                self.assertTrue(result['invalidBindings'])

    def test_retired_assignment_does_not_survive_but_shared_alias_does(self):
        result=discover_files({'model.py':'''import torch.nn as nn
class A(nn.Module):
 def forward(self,x): return x
class R(nn.Module):
 def __init__(self):
  self.a=A()
  self.alias=self.a
  self.a=None
 def forward(self,x): return x
'''})
        children=[row for row in result['relationships'] if row['owner']=='model:R']
        self.assertEqual([(row['slot'],row['target']) for row in children],[('alias','model:A')])
        self.assertTrue(result['assignmentOverrides'])
        self.assertTrue(result['hierarchyComplete'])

    def test_conditional_overwrite_preserves_both_possible_candidates(self):
        result=discover_files({'model.py':'''import torch.nn as nn
class A(nn.Module):
 def forward(self,x): return x
class B(nn.Module):
 def forward(self,x): return x
class R(nn.Module):
 def __init__(self):
  self.a=A()
  if unknown:
   self.a=B()
 def forward(self,x): return x
'''})
        children=[row for row in result['relationships'] if row['owner']=='model:R']
        self.assertEqual({row['target'] for row in children},{'model:A','model:B'})
        self.assertTrue(all(row['certainty']=='possible' for row in children))
        self.assertFalse(result['hierarchyComplete'])

    def test_partial_syntax_errors_are_explicit_and_other_models_survive(self):
        result = discover_files({'bad.py': 'class [invalid', 'good.py': 'from torch.nn import Module\nclass M(Module):\n def forward(self,x): return x\n'})
        self.assertEqual(result['candidates'], ['good:M'])
        self.assertFalse(result['complete'])
        self.assertEqual(result['syntaxErrors'][0]['file'], 'bad.py')

    def test_nested_classes_are_listed_as_unresolved_without_invented_entry(self):
        result = discover_files({'model.py': 'from torch.nn import Module\nclass Namespace:\n class Nested(Module):\n  def forward(self,x): return x\n'})
        self.assertFalse(result['inventoryComplete'])
        self.assertEqual(result['unindexedClasses'][0]['name'], 'Nested')
        self.assertEqual(result['candidates'], [])

    def test_directory_budgets_symlinks_and_ignored_cache(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root/'m.py').write_text('from torch.nn import Module\nclass M(Module):\n def forward(self,x): return x\n')
            (root/'__pycache__').mkdir()
            (root/'__pycache__'/'bad.py').write_text('invalid syntax @')
            before = (root/'m.py').stat().st_mtime_ns
            self.assertEqual(list(read_directory_files(root)), ['m.py'])
            self.assertEqual(discover_directory(root)['candidates'], ['m:M'])
            self.assertEqual((root/'m.py').stat().st_mtime_ns, before)
            with self.assertRaises(DiscoveryError): read_directory_files(root,max_bytes=1)
            (root/'alias.py').symlink_to(root/'m.py')
            with self.assertRaises(DiscoveryError): read_directory_files(root)


if __name__ == '__main__': unittest.main()
