"""Repeatable static source contracts and ten semantic negatives for graph modules.

Only local drawing adapters are imported. Upstream notebooks, model modules,
tensor calculations, initializers and SciPy decomposition are never executed.
"""
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parents[1]
if str(HERE) not in sys.path:sys.path.insert(0,str(HERE))
import bootstrap
import ast
import copy
import importlib
import json
import tempfile
from evidence import collect,semantic_ir


def _symbols(source):
    tree=ast.parse(source)
    symbols={'__module__':tree}
    for node in tree.body:
        if isinstance(node,(ast.FunctionDef,ast.ClassDef)):
            symbols[node.name]=node
            if isinstance(node,ast.ClassDef):
                for child in node.body:
                    if isinstance(child,ast.FunctionDef):symbols[node.name+'.'+child.name]=child
    return symbols


def source_contracts(key,source):
    """AST comparisons distinguish live statements from comments/string content."""
    symbols=_symbols(source);labels=[]
    def statement(symbol,expected,label):
        wanted=ast.dump(ast.parse(expected).body[0],include_attributes=False)
        if not any(ast.dump(node,include_attributes=False)==wanted for node in ast.walk(symbols[symbol])):
            raise ValueError(key+': source contract changed: '+label)
        labels.append(label)
    def condition(ok,label):
        if not ok:raise ValueError(key+': source contract changed: '+label)
        labels.append(label)
    if key=='edge_predictor':
        statement('make_coordinate_array','coord = np.stack((col, row), axis=2).reshape(-1, 2)',
                  'grid coordinate order is col,row')
        statement('make_coordinate_array','coord = (coord - np.mean(coord, axis=0)) / (np.std(coord, axis=0) + 1e-5)',
                  'per-coordinate standardization and epsilon')
        statement('make_coordinate_array','coord = torch.from_numpy(coord).float()',
                  'fixed coordinates converted to float tensor')
        statement('make_coordinate_array','coord = torch.cat((coord.unsqueeze(0).repeat(n_rows, 1, int(out_size/2-1)), coord.unsqueeze(1).repeat(1, n_rows, 1)), dim=2)',
                  'ordered pairs place j coordinates before i coordinates')
        statement('GraphNet.__init__',"self.register_buffer('coord', coord)",'coord actual buffer registration')
        statement('GraphNet.__init__','self.pred_edge_fc = nn.Sequential(nn.Linear(coord_features,32),nn.ReLU(),nn.Linear(32,1),nn.Tanh())',
                  'one actual shared MLP with default Linear biases and Tanh')
        statement('GraphNet.forward','self.A = self.pred_edge_fc(self.coord).squeeze()',
                  'module expression depends only on coord and MLP, then ordinary attribute assignment')
        condition([ast.literal_eval(n) for n in symbols['GraphNet.__init__'].args.defaults]==[28,4,10],
                  'source default img_size28 and coord_features4')
        registrations=[node for node in ast.walk(symbols['GraphNet.__init__'])
                       if isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute)
                       and node.func.attr in ('register_buffer','register_parameter')
                       and node.args and isinstance(node.args[0],ast.Constant)]
        condition(not any(node.args[0].value=='A' for node in registrations),
                  'A is not constructor-registered buffer or parameter')
    elif key=='spectral_filter':
        statement('precompute_adjacency_matrix','coord = np.stack((col, row), axis=2).reshape(-1, 2) / img_size',
                  'grid coords use division by img_size')
        statement('precompute_adjacency_matrix',"dist = cdist(coord, coord, metric='euclidean')",'Euclidean distance library call')
        statement('precompute_adjacency_matrix','A = np.exp(- dist / sigma ** 2)','actual unsquared-distance kernel')
        statement('precompute_adjacency_matrix','A[A < 0.01] = 0','actual adjacency threshold')
        helper=symbols['precompute_adjacency_matrix']
        condition(any(isinstance(n,ast.Return) and isinstance(n.value,ast.Name) and n.value.id=='A' for n in helper.body)
                  and not any(isinstance(n,ast.Return) and isinstance(n.value,ast.Name) and n.value.id=='A_hat' for n in ast.walk(helper)),
                  'helper returns A; triple-quoted normalization is not executable AST')
        statement('get_graph_laplacian','D = np.sum(A, 0)','degree sum uses axis0')
        statement('get_graph_laplacian','D_hat = np.diag((D + 1e-5)**(-0.5))','Laplacian epsilon and inverse sqrt')
        statement('get_graph_laplacian','L = np.identity(N) - np.dot(D_hat,A).dot(D_hat)','normalized Laplacian expression')
        statement('GraphNet.__init__',"Λ,V = eigsh(L.numpy(), k=20, which='SM')",'eigsh exact20-mode SM library boundary')
        statement('GraphNet.__init__','V = torch.from_numpy(V)','V is not explicitly cast to float32')
        statement('GraphNet.__init__','W_spectral = nn.Parameter(torch.ones((img_size**2,num_filters))).float()',
                  'W originates from Parameter followed by runtime-dependent float conversion')
        statement('GraphNet.__init__','torch.nn.init.kaiming_uniform_(W_spectral)','constructor Kaiming initialization')
        for name in ('A','L','V','W_spectral'):
            statement('GraphNet.__init__',"self.register_buffer('"+name+"', "+name+")",name+' real buffer registration')
        condition([ast.literal_eval(n) for n in symbols['GraphNet.__init__'].args.defaults]==[28,2,10],
                  'source default img_size28 and num_filters2')
        for code,label in [
            ('V_tensor = self.V.expand(B,-1,-1)','V batch view reads self.V directly'),
            ('V_tensor_T = self.V.T.expand(B,-1,-1)','V transpose batch view reads self.V.T directly'),
            ('W_spectral_tensor = self.W_spectral.expand(B,-1,-1)','W batch view reads registered W directly'),
            ('x_reshape = x.view(B,-1,1)','single-channel image node view'),
            ('X_hat = V_tensor_T.bmm(x_reshape)','ordered signal projection operands'),
            ('W_hat = V_tensor_T.bmm(W_spectral_tensor)','ordered node-domain filter projection operands'),
            ('Y = V_tensor.bmm(X_hat * W_hat)','elementwise product then V reconstruction')]:
            statement('GraphNet.forward',code,label)
        live=symbols['GraphNet.forward'].body
        for variable,first,second in [
            ('V_tensor','self.V.unsqueeze(0)','self.V.expand(B,-1,-1)'),
            ('V_tensor_T','self.V.T.unsqueeze(0)','self.V.T.expand(B,-1,-1)'),
            ('W_spectral_tensor','self.W_spectral.unsqueeze(0)','self.W_spectral.expand(B,-1,-1)')]:
            assignments=[(i,node.value) for i,node in enumerate(live) if isinstance(node,ast.Assign)
                         and any(isinstance(t,ast.Name) and t.id==variable for t in node.targets)]
            condition(len(assignments)==2 and assignments[1][0]==assignments[0][0]+1
                      and ast.dump(assignments[0][1])==ast.dump(ast.parse(first,mode='eval').body)
                      and ast.dump(assignments[1][1])==ast.dump(ast.parse(second,mode='eval').body),
                      variable+' unsqueeze result is immediately overwritten')
        condition(not any(isinstance(n,ast.Name) and n.id=='Λ' and isinstance(n.ctx,ast.Load)
                          for n in ast.walk(symbols['GraphNet.forward'])),
                  'Lambda eigenvalues unused in filtering forward')
        statement('__module__','optimizer = torch.optim.SGD(model.parameters(), lr=LEARNING_RATE)',
                  'optimizer discovers model parameters, not W buffer by registration')
    else:raise ValueError('Unknown graph module: '+key)
    return labels


NEGATIVES={
    'edge_predictor':[
        ('image-conditioned adjacency','edge.output','image_conditioned',True),
        ('unshared per-pair Linear','edge.linear1','shared_across','N*N independent MLP instances'),
        ('Softmax replacing Tanh','edge.tanh','activation','softmax'),
        ('A misregistered as parameter','edge.squeeze','registered_parameter',True)],
    'spectral_filter':[
        ('buffer mislabeled optimizer parameter','spectral.wbuffer','optimizer_parameter',True),
        ('unconditional no-grad assumption','spectral.wbuffer','requires_grad',False),
        ('one-channel output','spectral.output','output_shape',['B',784]),
        ('reversed signal bmm operands','spectral.xproject.bmm','ordered_operands',['spectral.reshape','spectral.vt']),
        ('invented squared-distance kernel','spectral.adj','distance_squared',True)],
}


def run():
    modules={};negatives=[]
    for key in NEGATIVES:
        adapter=importlib.import_module('module_adapters.'+key);model=adapter.build()
        source=(HERE/'sources'/adapter.SOURCE).read_text()
        source_checks=source_contracts(key,source)
        with tempfile.TemporaryDirectory(prefix='graph-module-contracts-') as folder:
            evidence=collect(model,HERE/'sources',Path(folder),manifest_path=HERE/'source_manifest.json')
            ir=semantic_ir(model,evidence)
        labels=adapter.validate_ir(ir)
        modules[key]=dict(passed=True,source_checks=source_checks,semantic_checks=labels,
                          source=ir['source'],node_count=len(ir['nodes']),edge_count=len(ir['edges']))
        def reject(changed,description):
            try:adapter.validate_ir(changed)
            except ValueError as error:
                negatives.append(dict(module=key,case=description,rejected=True,error=str(error)))
            else:raise AssertionError('Graph-module semantic negative accepted: '+description)
        for description,identity,field,value in NEGATIVES[key]:
            changed=copy.deepcopy(ir)
            next(n for n in changed['nodes'] if n['id']==identity)[field]=value
            reject(changed,description)
        if key=='spectral_filter':
            changed=copy.deepcopy(ir)
            changed['edges']=[e for e in changed['edges'] if not(e['dst']=='spectral.vt' and e['dst_port']=='B')]
            reject(changed,'missing V transpose batch shape source')
    return dict(passed=True,modules=modules,negative_cases=negatives,upstream_executed=False,
                scope='frozen-source AST contracts + newly built module IR + ten semantic negatives')


if __name__=='__main__':print(json.dumps(run(),ensure_ascii=False,indent=2))
