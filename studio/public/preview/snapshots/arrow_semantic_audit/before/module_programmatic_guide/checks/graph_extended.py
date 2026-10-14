"""Fresh static graph/multimodal IR, pinned AST contracts and semantic negatives.

Imports only our local drawing adapters. Upstream modules, notebooks, model
constructors, torch/numpy/scipy computations and library kernels never run.
"""
from pathlib import Path
import sys
HERE=Path(__file__).resolve().parents[1]
if str(HERE) not in sys.path:sys.path.insert(0,str(HERE))
import bootstrap
import ast,copy,importlib,json,tempfile
from evidence import collect,semantic_ir,symbols_in
from verify import source_checks

KEYS=['sparse_gcn','ggnn_step','capsule_routing','bilinear_attention',
      'weighted_bilinear_pooling','compact_bilinear_pooling','appnp_propagation',
      'inner_product_decoder','graphsage_mean','mixhop_layer','mixhop_dense',
      'signed_graphconv','signed_graphconv_base','graph_attention','vgae_posterior',
      'graphwavelet_sparse','graphwavelet_dense','simgnn_readout','simgnn_tensor','tucker_core']

CRITICAL_LINKS={
 'sparse_gcn':('adj','aggregate.spmm','A'),
 'ggnn_step':('state','reset_state','state'),
 'capsule_routing':('votes','agreement','votes'),
 'bilinear_attention':('v','mask','mask_input'),
 'weighted_bilinear_pooling':('w','einsum','weights'),
 'compact_bilinear_pooling':('y','ysketch.sign','in'),
 'appnp_propagation':('h0','restart','in'),
 'inner_product_decoder':('z','product.mm','left'),
 'graphsage_mean':('features','selflookup','callable'),
 'mixhop_layer':('adj','branch2.prop1','A'),
 'mixhop_dense':('bias','biasadd','bias'),
 'signed_graphconv':('x2','negmean','features'),
 'signed_graphconv_base':('x','concat','self'),
 'graph_attention':('projection.heads','message','ft'),
 'vgae_posterior':('features','noise','N'),
 'graphwavelet_sparse':('theta','rescale','theta_values'),
 'graphwavelet_dense':('inverse','kernel','phi_inverse'),
 'simgnn_readout':('embedding','score.mm','X'),
 'simgnn_tensor':('e2','bilinear.second','embedding2'),
 'tucker_core':('core','condition.mm','W'),
}

def expressions(path,contracts):
 symbols=symbols_in(path.read_text(),str(path));labels=[]
 for symbol,code in contracts:
  expected=ast.dump(ast.parse(code,mode='eval').body,include_attributes=False)
  if symbol not in symbols or not any(ast.dump(n,include_attributes=False)==expected for n in ast.walk(symbols[symbol])):
   raise ValueError('Source AST contract changed: '+symbol+' / '+code)
  labels.append(dict(path=str(path.relative_to(HERE/'sources')),symbol=symbol,expression=code))
 return labels

def source_order(key,adapter):
 """Independent ordering/branch contracts beyond symbol and expression presence."""
 s=symbols_in((HERE/'sources'/adapter.SOURCE).read_text(),adapter.SOURCE);checks=[]
 def ensure(ok,label):
  if not ok:raise ValueError(key+': independent source contract changed: '+label)
  checks.append(label)
 def expressions_in(symbol):return [n for n in ast.walk(s[symbol]) if isinstance(n,ast.Call)]
 def callname(n):return ast.unparse(n.func)
 def location(symbol,expression):
  expected=ast.dump(ast.parse(expression,mode='eval').body,include_attributes=False)
  return next(n.lineno for n in ast.walk(s[symbol]) if ast.dump(n,include_attributes=False)==expected)
 def ordered(symbol,*expressions):
  positions=[location(symbol,expr) for expr in expressions]
  ensure(positions==sorted(positions) and len(set(positions))==len(positions),'operation order: '+' -> '.join(expressions))
 if key=='sparse_gcn':
  ordered('GraphConvolution.forward','torch.mm(input, self.weight)','torch.spmm(adj, support)','output + self.bias')
  ensure(not any('relu' in callname(n).lower() for n in expressions_in('GraphConvolution.forward')),'no layer activation')
 elif key=='ggnn_step':
  ordered('Propogator.forward','torch.cat((a_in, a_out, state_cur), 2)','torch.cat((a_in, a_out, r * state_cur), 2)','(1 - z) * state_cur + z * h_hat')
  init=s['GGNN.__init__'];forward=s['GGNN.forward']
  ensure(any(isinstance(n,ast.Call) and callname(n)=='nn.Linear' for n in ast.walk(init)) and not any(isinstance(n,ast.Call) and callname(n)=='nn.Linear' for n in ast.walk(forward)),'typed Linear instances constructed outside time loop')
 elif key=='capsule_routing':
  ordered('AgreementRouting.forward','F.softmax(self.b)','self.b.expand((batch_size, input_caps, output_caps))','range(self.n_iterations)')
  ensure(not any('detach' in callname(n) for n in expressions_in('AgreementRouting.forward')),'vote tensors are not detached')
  sq=s['squash'];ensure(not any(isinstance(n,ast.Constant) and isinstance(n.value,float) and 0<n.value<1 for n in ast.walk(sq)),'squash adds no small epsilon constant')
 elif key=='bilinear_attention':
  ordered('BiAttention.forward_all','logits.data.masked_fill_(mask.data, mask_with)','nn.functional.softmax(logits.view(-1, self.glimpse, v_num * q_num), 2)')
  init=s['BiAttention.__init__'];ensure(any(isinstance(n,ast.keyword) and n.arg=='name' and isinstance(n.value,ast.Constant) and n.value.value=='h_mat' for n in ast.walk(init)),'h_mat receives weight_norm reparameterization')
 elif key=='weighted_bilinear_pooling':
  ensure(not any(callname(n)=='self.dropout' for n in expressions_in('BCNet.forward_with_weights')),'weighted path has no extra attention Dropout')
  ordered('BCNet.forward_with_weights',"torch.einsum('bvk,bvq,bqk->bk', (v_, w, q_))",'self.p_net(logits).squeeze(1) * self.k')
 elif key=='compact_bilinear_pooling':
  ensure(not any(isinstance(n,ast.Call) and ('Parameter' in callname(n)) for n in expressions_in('CountSketch.__init__')),'CountSketch h/s are buffers, no learned Parameter')
 elif key=='appnp_propagation':
  symbol='APPNPModel.forward';calls=expressions_in(symbol)
  dropout=[n for n in calls if 'dropout' in callname(n)];loops=[n for n in ast.walk(s[symbol]) if isinstance(n,ast.For)]
  ensure(len(dropout)>=1 and all(not(n.lineno<=d.lineno<=n.end_lineno) for n in loops for d in dropout),'edge Dropout outside propagation loop')
 elif key=='inner_product_decoder':
  ensure(len(s['VGAEModel.decoder'].body)==2,'decoder contains only score assignment and return')
 elif key=='graphsage_mean':
  args=s['Encoder.__init__'].args;defaults={a.arg:ast.unparse(v) for a,v in zip(args.args[-len(args.defaults):],args.defaults)}
  ensure(defaults['num_sample']=='10' and defaults['gcn']=='False','source sampling/gcn defaults')
 elif key in ('mixhop_layer','mixhop_dense'):
  p=HERE/'sources'/('mixhop-modules/src/layers.py');ls=symbols_in(p.read_text(),str(p))
  def line(symbol,expr):
   want=ast.dump(ast.parse(expr,mode='eval').body);return next(n.lineno for n in ast.walk(ls[symbol]) if ast.dump(n)==want)
  if key=='mixhop_layer':
   f='SparseNGCNLayer.forward';ensure(line(f,'base_features + self.bias')<line(f,'torch.nn.functional.relu(base_features)')<line(f,'range(self.iterations-1)'),'sparse bias and ReLU before adjacency loop')
  else:
   f='DenseNGCNLayer.forward';ensure(line(f,'range(self.iterations-1)')<line(f,'base_features + self.bias'),'dense bias after adjacency loop')
   ensure(not any(isinstance(n,ast.Call) and 'relu' in ast.unparse(n.func).lower() for n in ast.walk(ls[f])),'dense layer has no ReLU')
 elif key in ('signed_graphconv','signed_graphconv_base'):
  name='SignedSAGEConvolution'+('Deep' if key=='signed_graphconv' else 'Base')+'.forward'
  names=[callname(n) for n in expressions_in(name)]
  ensure(names.count('add_self_loops')==(2 if key=='signed_graphconv' else 0),'actual add_self_loops call count')
 elif key=='graph_attention':
  ordered('GATConv.forward','fn.u_add_v("el", "er", "e")','self.attn_drop(edge_softmax(graph, e))','graph.update_all(fn.u_mul_e("ft", "a", "m"), fn.sum("m", "ft"))')
  ensure(any(isinstance(n,ast.Assign) and len(n.targets)==2 and [ast.unparse(t) for t in n.targets]==['feat_src','feat_dst'] for n in ast.walk(s['GATConv.forward'])),'homogeneous feat_src and feat_dst alias same projection')
 elif key=='vgae_posterior':
  ensure(not any(isinstance(n,ast.If) for n in ast.walk(s['VGAEModel.encoder'])),'sampling has no train/eval conditional')
  init=s['VGAEModel.__init__'];ensure(sum(isinstance(n,ast.Call) and callname(n)=='GraphConv' for n in ast.walk(init))==3,'exact three independent GraphConv constructor calls')
 elif key in ('graphwavelet_sparse','graphwavelet_dense'):
  defs=s['GraphWaveletLayer.define_parameters'];ensure(not any(isinstance(n,ast.Call) and 'register_buffer' in callname(n) for n in ast.walk(defs)),'diagonal indices are ordinary attribute, not registered buffer')
  ensure(sum(isinstance(n,ast.Call) and 'Parameter' in callname(n) for n in ast.walk(defs))==2,'exact two learned Parameter instances theta and W')
  f=('Sparse' if key=='graphwavelet_sparse' else 'Dense')+'GraphWaveletLayer.forward'
  ensure(sum(callname(n)=='spspmm' for n in expressions_in(f))==2,'two sparse-sparse products before localization')
  if key=='graphwavelet_dense':ensure(not any('dropout' in callname(n) or 'relu' in callname(n) for n in expressions_in(f)),'dense returns no ReLU or Dropout')
 elif key=='simgnn_readout':
  ordered('AttentionModule.forward','torch.mean(torch.matmul(embedding, self.weight_matrix), dim=0)','torch.tanh(global_context)','torch.sigmoid(torch.mm(embedding, transformed_global.view(-1, 1)))','torch.mm(torch.t(embedding), sigmoid_scores)')
  ensure(not any('softmax' in callname(n) for n in expressions_in('AttentionModule.forward')),'node gates are not Softmax-normalized')
 elif key=='simgnn_tensor':
  ensure(sum(isinstance(n,ast.Call) and 'Parameter' in callname(n) for n in expressions_in('TenorNetworkModule.setup_weights'))==3,'three separate learned tensor/block/bias Parameters')
  ordered('TenorNetworkModule.forward','torch.mm(torch.t(embedding_1), self.weight_matrix.view(self.args.filters_3, -1))','scoring.view(self.args.filters_3, self.args.tensor_neurons)','torch.mm(torch.t(scoring), embedding_2)')
 elif key=='tucker_core':
  ordered('TuckER.forward','torch.mm(r, self.W.view(r.size(1), -1))','W_mat.view(-1, e1.size(1), e1.size(1))','self.hidden_dropout1(W_mat)','torch.bmm(x, W_mat)')
  ensure(any(isinstance(n,ast.keyword) and n.arg=='device' and isinstance(n.value,ast.Constant) and n.value.value=='cuda' for n in ast.walk(s['TuckER.__init__'])),'core constructor device is literal CUDA boundary')
 return checks

def run():
 manifest=json.loads((HERE/'source_manifest.json').read_text())
 for slug,p in json.loads((HERE/'staging/graph_source_manifest.json').read_text()).items():
  if slug in manifest:
   assert manifest[slug]['commit']==p['commit'];manifest[slug]['files'].update(p['files'])
  else:manifest[slug]=p
 reports={};negatives=[]
 with tempfile.TemporaryDirectory(prefix='graph-extended-static-') as tmp:
  base=Path(tmp);mp=base/'manifest.json';mp.write_text(json.dumps(manifest))
  for key in KEYS:
   adapter=importlib.import_module('module_adapters.'+key);model=adapter.build();folder=base/key;folder.mkdir()
   ev=collect(model,HERE/'sources',folder,manifest_path=mp);ir=semantic_ir(model,ev)
   source=expressions(HERE/'sources'/adapter.SOURCE,adapter.CONTRACTS)
   for path,contracts in getattr(adapter,'EXTRA_CONTRACTS',{}).items():source+=expressions(HERE/'sources'/path,contracts)
   semantic=adapter.validate_ir(ir);order=source_order(key,adapter)
   integrity=source_checks(folder,ev,ir,manifest_path=mp,source_root=HERE/'sources')
   reports[key]=dict(passed=True,source_ast_contracts=source,independent_source_contracts=order,semantic_checks=semantic,source_integrity=integrity,node_count=len(ir['nodes']),edge_count=len(ir['edges']))
   def reject(changed,label):
    try:adapter.validate_ir(changed)
    except ValueError as error:negatives.append(dict(module=key,case=label,rejected=True,error=str(error)))
    else:raise AssertionError(key+': negative accepted: '+label)
   src,dst,port=CRITICAL_LINKS[key];changed=copy.deepcopy(ir)
   edge=next(e for e in changed['edges'] if e['src']==key+'.'+src and e['dst']==key+'.'+dst and e['dst_port']==port)
   alternatives=[n['id'] for n in changed['nodes'] if n['id'] not in (edge['src'],edge['dst']) and n['kind']!='group']
   edge['src']=alternatives[0];reject(changed,'wrong REAL source endpoint for '+src+' -> '+dst+':'+port)
   changed=copy.deepcopy(ir);identity,fields=next(iter(adapter.REQUIRED.items()));field=next(iter(fields))
   next(n for n in changed['nodes'] if n['id']==key+'.'+identity)[field]='__wrong_source_semantics__'
   reject(changed,'wrong operator/parameter/state identity '+identity+':'+field)
   for src,dst,port,source_port in getattr(adapter,'SOURCE_PORTS',[]):
    changed=copy.deepcopy(ir)
    edge=next(e for e in changed['edges'] if e['src']==key+'.'+src and e['dst']==key+'.'+dst and e['dst_port']==port)
    edge['src_port']='__wrong_operand_field__'
    reject(changed,'wrong REAL source output field '+src+':'+source_port)
   changed=copy.deepcopy(ir);changed['profile']['model_executed']=True;reject(changed,'false upstream execution claim')
   # Remove exactly the first required AST expression in a parsed COPY of
   # fixed source. This exercises detection of a changed real statement.
   symbol,expr=adapter.CONTRACTS[0];text=(HERE/'sources'/adapter.SOURCE).read_text();tree=ast.parse(text);wanted=ast.dump(ast.parse(expr,mode='eval').body)
   class Mutate(ast.NodeTransformer):
    done=False
    def visit(self,node):
     if not self.done and ast.dump(node)==wanted:self.done=True;return ast.copy_location(ast.Constant('__changed_expression__'),node)
     return super().visit(node)
   mutation=Mutate();changed_tree=mutation.visit(tree);ast.fix_missing_locations(changed_tree);assert mutation.done
   changed_path=base/(key+'_mutated.py');changed_path.write_text(ast.unparse(changed_tree))
   try:expressions(changed_path,adapter.CONTRACTS[:1])
   except ValueError as error:negatives.append(dict(module=key,case='alter actual source AST expression',rejected=True,error=str(error)))
   else:raise AssertionError(key+': changed source expression accepted')
 return dict(passed=True,modules=reports,module_count=len(reports),source_ast_contract_count=sum(len(r['source_ast_contracts']) for r in reports.values()),independent_source_contract_count=sum(len(r['independent_source_contracts']) for r in reports.values()),semantic_check_count=sum(len(r['semantic_checks']) for r in reports.values()),negative_cases=negatives,negative_case_count=len(negatives),upstream_executed=False,scope='pinned source hashes + static AST + fresh declared module IR; no arbitrary-source or runtime support claimed')

if __name__=='__main__':print(json.dumps(run(),ensure_ascii=False,indent=2,allow_nan=False))
