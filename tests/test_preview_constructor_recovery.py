"""Preview topology recovery uses framework contracts, never model names."""
from pathlib import Path
import tempfile
import unittest

from archcanvas_preview import analyze


SOURCE = '''import torch
from torch import nn
class ReviewCell(nn.Module):
 def __init__(self):
  super().__init__(); self.activation=nn.Tanh()
 def forward(self,x): return self.activation(x)
class Orchard(nn.Module):
 def __init__(self, state_name='memory'):
  super().__init__()
  self.proj=nn.Linear(4,4)
  self.register_buffer(state_name, make_state(4), persistent=False)
  self.review=ReviewCell()
 def forward(self,x): return self.review(self.proj(x))
'''


class PreviewConstructorRecoveryTests(unittest.TestCase):
    def module_types(self, source=SOURCE, entry='Orchard'):
        bundle = analyze({'model.py': source}, entry)
        return bundle, [node.get('moduleType') for node in bundle['ir']['nodes']
                        if node.get('kind') != 'opaque']

    def test_state_registration_keeps_modules_before_and_after_it(self):
        bundle, types = self.module_types()
        self.assertIn('Linear', types)
        self.assertIn('ReviewCell', types)
        self.assertIn('Tanh', types)
        self.assertEqual(bundle['diagnostics'], [])
        self.assertFalse(bundle['ir']['modelExecuted'])
        linear = next(node for node in bundle['ir']['nodes'] if node.get('moduleType') == 'Linear')
        activation = next(node for node in bundle['ir']['nodes'] if node.get('moduleType') == 'Tanh')
        self.assertTrue(any(edge['source'] == linear['id'] for edge in bundle['ir']['edges']))
        self.assertTrue(any(edge['target'] == activation['id'] for edge in bundle['ir']['edges']))

    def test_parameter_registration_and_keyword_binding_keep_children(self):
        for registration in ["self.register_parameter(name=state_name, param=make_state(4))",
                             "name=state_name\n  self.register_buffer(name=name, tensor=make_state(4))"]:
            with self.subTest(registration=registration):
                bundle, types = self.module_types(SOURCE.replace("self.register_buffer(state_name, make_state(4), persistent=False)", registration))
                self.assertIn('Linear', types)
                self.assertIn('Tanh', types)
                self.assertEqual(bundle['diagnostics'], [])
        inherited = SOURCE + 'class Inherited(Orchard): pass\n'
        self.assertIn('Linear', self.module_types(inherited, 'Inherited')[1])

    def test_unknown_helpers_overrides_dynamic_names_and_child_arguments_stay_opaque(self):
        cases = [SOURCE.replace('make_state(4)', 'mutate(self.proj)'),
                 SOURCE.replace('state_name, make_state(4)', 'unknown_name, make_state(4)'),
                 SOURCE.replace('state_name, make_state(4)', "'proj', make_state(4)"),
                 SOURCE.replace('persistent=False', 'persistent=unknown'),
                 SOURCE.replace('persistent=False', 'tensor=other'),
                 SOURCE.replace('state_name, make_state(4)', '*registration_args'),
                 SOURCE.replace('self.register_buffer(state_name, make_state(4), persistent=False)', 'self.initialize_unknown()'),
                 SOURCE.replace(' def forward(self,x): return self.review(self.proj(x))',
                                ' def register_buffer(self,*args,**kwargs): self.proj=unknown()\n def forward(self,x): return self.review(self.proj(x))'),
                 SOURCE.replace('  self.register_buffer', '  alias=self.proj\n  self.register_buffer').replace('make_state(4)', 'mutate(alias)')]
        for source in cases:
            with self.subTest(source=source):
                bundle, types = self.module_types(source)
                self.assertNotIn('Linear', types)
                self.assertTrue(any(node['kind'] == 'opaque' for node in bundle['ir']['nodes']))
        inherited = SOURCE + '''class Shadow(Orchard):
 def register_buffer(self,*args,**kwargs): self.proj=unknown()
'''
        self.assertNotIn('Linear', self.module_types(inherited, 'Shadow')[1])

    def test_producers_and_module_source_are_never_executed(self):
        with tempfile.TemporaryDirectory() as directory:
            marker = Path(directory) / 'model-executed'
            producer = f"def make_state(size):\n open({str(marker)!r},'w').write('executed')\n return unknown()\n"
            bundle, types = self.module_types(SOURCE.replace('class ReviewCell', producer + 'class ReviewCell'))
            self.assertIn('Linear', types)
            self.assertFalse(bundle['ir']['modelExecuted'])
            self.assertFalse(marker.exists())

    def test_rebound_receiver_or_super_cannot_claim_child_topology(self):
        for source in [SOURCE.replace("state_name='memory'", "state_name='memory', super=None"),
                       SOURCE.replace('  super().__init__()', '  super=foreign\n  super().__init__()'),
                       SOURCE.replace('  super().__init__()', '  self=foreign\n  super().__init__()'),
                       'super=foreign\n' + SOURCE,
                       'from helpers import other as super\n' + SOURCE,
                       'def super(): return foreign\n' + SOURCE,
                       'if flag: super=foreign\n' + SOURCE]:
            with self.subTest(source=source):
                self.assertNotIn('Linear', self.module_types(source)[1])

    def test_call_after_unknown_branch_is_source_inspection_only(self):
        source = SOURCE.replace(' def forward(self,x): return self.review(self.proj(x))', ''' def forward(self,x):
  if flag: x=external(x)
  x=self.review(self.proj(x))
  return x
''')
        bundle, _ = self.module_types(source)
        source_cells = [node for node in bundle['ir']['nodes']
                        if node.get('sourceStructure') and node.get('sourceKind') == 'SourceModule']
        self.assertTrue(any(node.get('sourceParameters', {}).get('sourceType') == 'ReviewCell' for node in source_cells))
        self.assertTrue(any(node.get('sourceParameters', {}).get('sourceType') == 'nn.Linear' for node in source_cells))
        self.assertFalse(any(node.get('moduleType') == 'ReviewCell' and node['kind'] != 'opaque' for node in bundle['ir']['nodes']))
        ids = {node['id'] for node in source_cells}
        self.assertTrue(all(edge.get('syntaxOnly') for edge in bundle['ir']['edges']
                            if edge['source'] in ids or edge['target'] in ids))


if __name__ == '__main__':
    unittest.main()
