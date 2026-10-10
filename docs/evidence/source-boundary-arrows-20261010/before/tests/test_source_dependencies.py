"""Source def/use relations are independent of verified tensor topology."""
import unittest
from archcanvas_python import analyze_source


def inspect(body, declarations=''):
    source = '''from torch import nn
class Sprig(nn.Module):
 def __init__(self):
  super().__init__()
  self.proj=nn.Linear(4,4); self.other=nn.Linear(4,4)
  self.act=nn.GELU(); self.head=nn.Linear(4,2)
''' + declarations + '\n def forward(self,x):\n' + body + '''
class Unseen(nn.Module):
 def __init__(self,config):
  super().__init__(); self.flag=config.enabled; self.branch=Sprig()
 def forward(self,x):
  if self.flag: x=self.branch(x)
  return x
'''
    return analyze_source(source, 'model:Unseen')


def pairs(architecture):
    facts = {node['id']: node for node in architecture['nodes']}
    return {(facts[r['sourceId']]['label'], facts[r['targetId']]['label']) for r in architecture.get('sourceRelations', [])}


class SourceDependencyTests(unittest.TestCase):
    def test_nested_calls_have_arrows_and_keep_tensor_inventory_conservative(self):
        a = inspect('  return self.head(self.act(self.proj(x)))\n')
        self.assertEqual(pairs(a), {('proj', 'act'), ('act', 'head')})
        facts = {node['id']: node for node in a['nodes']}
        for relation in a['sourceRelations']:
            self.assertEqual(relation['kind'], 'value-dependency')
            self.assertIn('self.', relation['source']['expression'])
            for end in ('sourceId', 'targetId'):
                self.assertTrue(facts[relation[end]]['sourceStructure'])
                self.assertEqual(facts[relation[end]]['ports'], [])
        self.assertFalse(any(facts[e[end]['nodeId']].get('sourceStructure') for e in a['edges'] for end in ('source', 'target')))

    def test_assignment_alias_fanout_merge_and_independent_calls(self):
        a = inspect('''  a=self.proj(x)
  independent=self.other(x)
  alias=a
  y=self.act(alias)
  return self.head(y+a)
''')
        self.assertEqual(pairs(a), {('proj','act'), ('act','head'), ('proj','head')})

    def test_mutually_exclusive_branches_do_not_get_chained(self):
        a = inspect('''  if x.enabled:
   y=self.proj(x)
  else:
   y=self.other(x)
  return self.head(y)
''')
        self.assertEqual(pairs(a), {('proj','head'), ('other','head')})

    def test_returned_branch_does_not_feed_later_consumers(self):
        a = inspect('''  if x.enabled:
   y=self.proj(x)
   return y
  else:
   y=self.other(x)
  return self.head(y)
''')
        self.assertEqual(pairs(a), {('other','head')})

    def test_tuple_swap_reads_all_old_values_before_writing(self):
        a = inspect('''  a=self.proj(x)
  b=self.other(x)
  a,b=b,a
  y=self.act(a)
  return self.head(b+y)
''')
        self.assertEqual(pairs(a), {('other','act'), ('proj','head'), ('act','head')})

    def test_sequential_order_is_declared_but_modulelist_is_storage(self):
        a = inspect('  return self.head(self.seq(x))\n', '  self.seq=nn.Sequential(nn.Linear(4,4),nn.GELU())\n  self.unused=nn.ModuleList([nn.Linear(4,4),nn.GELU()])')
        self.assertIn(('nn.Linear','nn.GELU'), pairs(a))
        b = inspect('  return self.head(self.seq(x))\n', '  self.seq=nn.ModuleList([nn.Linear(4,4),nn.GELU()])')
        self.assertNotIn(('nn.Linear','nn.GELU'), pairs(b))

    def test_no_adjacency_arrows_or_self_loops_for_independent_or_shared_calls(self):
        a = inspect('''  a=self.proj(x)
  b=self.other(x)
  c=self.proj(b)
  return c+a
''')
        self.assertEqual(pairs(a), {('other','proj')})
        self.assertTrue(all(r['sourceId'] != r['targetId'] for r in a['sourceRelations']))

    def test_equal_sequential_constructor_occurrences_are_distinct_source_cards(self):
        a = inspect('  return self.seq(x)\n', '  self.seq=nn.Sequential(nn.Linear(4,4),nn.Linear(4,4))')
        facts = {n['id']: n for n in a['nodes']}
        relations = [r for r in a['sourceRelations'] if facts[r['sourceId']]['label'] == facts[r['targetId']]['label'] == 'nn.Linear']
        self.assertEqual(len(relations), 1)
        self.assertNotEqual(relations[0]['sourceId'], relations[0]['targetId'])
