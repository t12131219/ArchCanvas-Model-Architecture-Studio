"""Independent source-only def/use fixtures for incomplete values and statements."""
import unittest

from archcanvas_adapters import scaffold_adapter_files, enrich_preview
from archcanvas_preview.analyze import Analyzer
from archcanvas_python import analyze_source


def adapter(body, declarations=''):
    source = '''from torch import nn
class Fern(nn.Module):
 def __init__(self):
  super().__init__()
''' + declarations + '\n def forward(self,x):\n' + body
    files = {'foreign.py': source}
    return files, scaffold_adapter_files(files, 'foreign:Fern')


def pairs(definition):
    facts = {node['id']: node for node in definition['children']}
    return {(facts[relation['sourceId']]['label'], facts[relation['targetId']]['label'])
            for relation in definition['dependencies']}


class SourceStatementDependenciesTests(unittest.TestCase):
    def test_unknown_nested_unpack_retains_whole_call_producer(self):
        _, definition = adapter('''  a,b,(c,d)=unseen(x)
  p=consume_a(a)
  q=consume_b(b)
  r=consume_c(c)
  s=consume_d(d)
  independent=other(x)
  return p,q,r,s
''')
        relations = pairs(definition)
        self.assertTrue({('unseen', 'consume_a'), ('unseen', 'consume_b'),
                         ('unseen', 'consume_c'), ('unseen', 'consume_d')}.issubset(relations))
        self.assertFalse(any(source == 'other' and target.startswith('consume_') for source, target in relations))
        self.assertTrue(all(node['ports'] == [] and node['sourceStructure'] for node in definition['children']))
        self.assertIsNone(definition['generationContract'])

    def test_unknown_starred_unpack_has_no_invented_return_slot(self):
        _, definition = adapter('''  first,*middle,last=unseen(x)
  return head(first), core(middle), tail(last)
''')
        self.assertTrue({('unseen', 'head'), ('unseen', 'core'), ('unseen', 'tail')}.issubset(pairs(definition)))
        self.assertFalse(any('slot' in relation or 'tensor' in relation for relation in definition['dependencies']))

    def test_known_local_method_tuple_remains_slot_specific(self):
        _, definition = adapter('''  a,b=self.prepare(x)
  return left(a),right(b)
''', ''' def prepare(self,x):
  return x.sin(),x.cos()
''')
        relations = pairs(definition)
        self.assertIn(('x.sin', 'left'), relations)
        self.assertIn(('x.cos', 'right'), relations)
        self.assertNotIn(('x.sin', 'right'), relations)
        self.assertNotIn(('x.cos', 'left'), relations)

    def test_partly_unknown_literal_return_does_not_mix_known_sibling_slots(self):
        _, definition = adapter('''  a,b=self.prepare(x)
  return left(a),right(b)
''', ''' def prepare(self,x):
  return unseen(*x),x.cos()
''')
        relations = pairs(definition)
        self.assertIn(('unseen', 'left'), relations)
        self.assertIn(('x.cos', 'right'), relations)
        self.assertNotIn(('x.cos', 'left'), relations)
        self.assertNotIn(('unseen', 'right'), relations)

    def test_assignment_arithmetic_alias_and_return_cards_consume_rhs(self):
        _, definition = adapter('''  a=make(x)
  b=other(x)
  alias=a
  total=alias+b
  return total
''')
        relations = pairs(definition)
        self.assertEqual(relations, {('make', 'alias'), ('make', 'total'), ('other', 'total'),
                                     ('make', 'return'), ('other', 'return')})
        self.assertNotIn(('make', 'other'), relations)
        self.assertFalse(any(source in ('alias', 'total') for source, _ in relations),
                         'source aliases remain transparent instead of becoming tensor operations')

    def test_tuple_swap_uses_old_values_and_keeps_both_statement_inputs(self):
        _, definition = adapter('''  a=make(x)
  b=other(x)
  a,b=b,a
  return left(a),right(b)
''')
        relations = pairs(definition)
        self.assertTrue({('make', 'a, b'), ('other', 'a, b'), ('other', 'left'), ('make', 'right')}.issubset(relations))
        self.assertNotIn(('make', 'left'), relations)
        self.assertNotIn(('other', 'right'), relations)

    def test_returning_one_branch_never_feeds_the_following_branch(self):
        _, definition = adapter('''  if x.flag:
   a=make(x)
   return a
  b=other(x)
  return consume(b)
''')
        self.assertTrue({('make', 'return'), ('other', 'consume')}.issubset(pairs(definition)))
        self.assertNotIn(('make', 'consume'), pairs(definition))
        self.assertFalse(any(source.startswith('if ') or target == 'else' for source, target in pairs(definition)))

    def test_subscript_store_rhs_is_visible_without_assuming_mutation_slots(self):
        _, definition = adapter('''  values={}
  a=make(x)
  values['answer']=a
  return values
''')
        self.assertIn(('make', "values['answer']"), pairs(definition))
        self.assertNotIn(("values['answer']", 'return'), pairs(definition),
                         'a store card does not prove aliasing, mutation propagation or a return slot')

    def test_preview_keeps_all_original_edges_and_marks_new_arrows_syntax_only(self):
        files, definition = adapter('''  if x.flag:
   a,b=unseen(x)
   y=consume(a)
   return y
  return x
''')
        original = Analyzer(files).run('foreign:Fern')
        result = enrich_preview(original, files, [definition])
        self.assertEqual(result['ir']['edges'][:len(original['ir']['edges'])], original['ir']['edges'])
        new_edges = result['ir']['edges'][len(original['ir']['edges']):]
        self.assertTrue(new_edges)
        self.assertTrue(all(edge['syntaxOnly'] for edge in new_edges))

    def test_unknown_unpack_does_not_certify_boundary_completeness(self):
        source = '''from torch import nn
class Fir(nn.Module):
 def __init__(self,config):
  super().__init__(); self.flag=config.enabled; self.head=nn.GELU()
 def forward(self,x):
  if self.flag:
   a,b=unseen(x)
   x=self.head(a)
  return x
'''
        architecture = analyze_source(source, 'model:Fir')
        facts = {node['id']: node for node in architecture['nodes']}
        relations = [relation for relation in architecture['sourceRelations']
                     if relation.get('boundary') and facts[relation['sourceId']]['label'] == 'head']
        self.assertTrue(relations)
        self.assertTrue(all(not relation['boundary']['complete'] for relation in relations))


if __name__ == '__main__':
    unittest.main()
