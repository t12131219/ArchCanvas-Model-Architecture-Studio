"""Real grouped source generation: hierarchy and boundary ports remain analyzable."""
import hashlib
import unittest
from archcanvas_authoring import DraftError, generate_grouped_source, generate_model, import_source_draft
from archcanvas_python import analyze_source


def authored():
    node=lambda i,k,p={}: {'id':i,'kind':k,'label':i,'parameters':p,'position':{'x':0,'y':0}}
    nodes=[node('x','Input',{'shape':[2,4]}),node('g','Identity'),node('fc','Linear',{'in_features':4,'out_features':3}),node('o','Output')]
    for n in nodes:n['presentation']={'width':176,'height':100,'fill':'#fff','stroke':'#000','group':n['id']=='g','ports':{}}
    nodes[2]['presentation']['parentId']='g'
    edge=lambda i,s,t:{'id':i,'source':{'nodeId':s,'portId':'output'},'target':{'nodeId':t,'portId':'input'}}
    return {'schemaVersion':1,'mode':'authored-draft','id':'grouped','title':'grouped','revision':0,'nodes':nodes,'edges':[edge('a','x','fc'),edge('b','fc','o')]}

class GroupGenerationTests(unittest.TestCase):
    def test_grouped_lstm_unpacks_named_state_tuple(self):
        def make(identity, kind, parameters):
            node = {'id': identity, 'kind': kind, 'label': identity, 'parameters': parameters, 'position': {'x': 0, 'y': 0}}
            node['presentation'] = {'width': 176, 'height': 100, 'fill': '#fff', 'stroke': '#000', 'group': identity == 'g', 'ports': {}}
            if identity == 'l': node['presentation']['parentId'] = 'g'
            return node
        lstm = {'input_size': 4, 'hidden_size': 8, 'num_layers': 1, 'bias': True, 'batch_first': True, 'dropout': 0.0, 'bidirectional': False}
        draft = {'schemaVersion': 1, 'mode': 'authored-draft', 'id': 'lstm-group', 'title': 'lstm-group', 'revision': 0,
                 'nodes': [make('x', 'Input', {'shape': [2, 5, 4], 'dtype': 'float32'}), make('g', 'Identity', {}), make('l', 'LSTM', lstm), make('o', 'Output', {})],
                 'edges': [{'id': 'in', 'source': {'nodeId': 'x', 'portId': 'output'}, 'target': {'nodeId': 'l', 'portId': 'input'}},
                           {'id': 'out', 'source': {'nodeId': 'l', 'portId': 'output'}, 'target': {'nodeId': 'o', 'portId': 'input'}}]}
        result = generate_grouped_source(draft)
        self.assertIn(', (node_', result['source'])
        self.assertNotIn('[2]', result['source'])
        self.assertFalse(any(node.get('kind') == 'Select' for node in result['architecture']['nodes']))

    def test_grouped_generation_rejects_missing_boundary_edge(self):
        broken = authored()
        broken['edges'] = broken['edges'][:1]
        with self.assertRaises(DraftError):
            generate_grouped_source(broken)

    def test_authored_group_is_a_real_nested_module_and_exact_bindings(self):
        result=generate_grouped_source(authored())
        self.assertEqual(result['verification']['modelExecution'],'not_run')
        self.assertIn('class GraphGroup_g_',result['source'])
        self.assertIn('self.node_',result['source'])
        self.assertIn('g',result['containerBindings']); self.assertIn('fc',result['nodeBindings'])
        grouped=next(n for n in result['architecture']['nodes'] if n.get('instanceId')==next(n['instanceId'] for n in result['architecture']['nodes'] if n.get('instanceId','').endswith('AuthoredModel'))+'.node_'+hashlib.sha256(b'g').hexdigest()[:12])
        self.assertEqual(grouped['kind'],'Module')
        linear=result['nodeBindings']['fc']; self.assertEqual(next(n for n in result['architecture']['nodes'] if n['id']==linear)['parentId'],grouped['id'])
        self.assertTrue(result['edgeBindings']['a']); self.assertTrue(result['edgeBindings']['b'])

    def test_plain_generate_dispatches_only_for_persisted_groups(self):
        result = generate_grouped_source(authored())
        with self.assertRaises(DraftError):
            # A presentation group is required for the source-specific path;
            # the ordinary semantic generator never silently invents one.
            generate_model({k: v for k, v in authored().items() if k != 'nodes'} | {'nodes': [{k: v for k, v in n.items() if k != 'presentation'} for n in authored()['nodes']]})
        self.assertEqual(result['entry'], 'archcanvas_grouped:AuthoredModel')

    def test_imported_source_dynamic_ports_group_without_flat_alias(self):
        source='from torch import nn\nclass Imported(nn.Module):\n def __init__(self):\n  super().__init__(); self.keep=nn.Linear(4,3)\n def forward(self,x): return self.keep(x)\n'
        architecture=analyze_source(source,'model:Imported')
        document={'schemaVersion':1,'id':'doc','title':'import','revision':1,'sourceBindingDigest':architecture['sourceDigest'],'architecture':architecture}
        scene_nodes=[]
        for index,node in enumerate(architecture['nodes']):
            scene_nodes.append({'id':node['id'],'canonicalNodeId':node['id'],'label':node.get('label',node['kind']),'x':index*220,'y':0,'width':176,'height':100,'expanded':False,
                                'ports':[{'id':port['id'],'name':port['name'],'direction':port['direction'],'x':0,'y':0} for port in node['ports']]})
        scene_edges=[]
        for edge in architecture['edges']:
            scene_edges.append({'id':edge['id'],'sourceId':edge['source']['nodeId'],'targetId':edge['target']['nodeId'],'source':{'portId':edge['source']['portId']},'target':{'portId':edge['target']['portId']},'canonicalEdgeIds':[edge['id']]})
        imported=import_source_draft(document,{'documentId':'doc','revision':1,'sourceDigest':architecture['sourceDigest'],'irDigest':architecture['irDigest'],'nodes':scene_nodes,'edges':scene_edges})['draft']
        for node in imported['nodes']: node['presentation']={'width':176,'height':100,'fill':'#fff','stroke':'#000','group':False,'ports':{}}
        root=next(node for node in imported['nodes'] if imported['sourceProvenance']['nodeRefs'][node['id']]['kind']=='Module');root['presentation']['group']=True
        for node in imported['nodes']:
            if node['id']!=root['id'] and imported['sourceProvenance']['nodeRefs'][node['id']]['kind'] not in ('Input','Output'): node['presentation']['parentId']=root['id']
        result=generate_grouped_source(imported)
        self.assertEqual(result['verification']['status'],'passed')
        dispatched=generate_model(imported)
        self.assertEqual(dispatched['entry'],'archcanvas_grouped:AuthoredModel')
        self.assertEqual(dispatched['verification']['modelExecution'],'not_run')
        self.assertTrue(result['containerBindings']); self.assertTrue(result['nodeBindings'])
        self.assertTrue(any(node['kind']=='Module' and node.get('parentId') for node in result['architecture']['nodes']))
        self.assertEqual(result['entry'],'archcanvas_grouped:AuthoredModel')

if __name__=='__main__': unittest.main()
