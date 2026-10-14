"""Bounded AST adapter for frozen torchvision InceptionB/C/D/E.

Interprets only literal conv construction, known functional pool, explicit lists
and cat in those classes; refuses unfamiliar syntax. No upstream execution.
"""
import ast
from pathlib import Path
from module_adapters._vision_common import Author,shape,validate_declaration
from module_adapters.support import ref
SOURCE='torchvision-v0.9.0-modules/torchvision/models/inception.py'
PROFILES={
 'inception_reduction':('InceptionB',288,35,None,'InceptionReduction.md'),
 'inception_factorized':('InceptionC',768,17,128,'InceptionFactorized.md'),
 'inception_reduction_factorized':('InceptionD',768,17,None,'InceptionReductionFactorized.md'),
 'inception_split':('InceptionE',1280,8,None,'InceptionSplit.md'),
}
def build_variant(key):
 symbol,cin,h,c7,doc=PROFILES[key];a=Author(key,SOURCE,symbol)
 tree=ast.parse((Path(__file__).resolve().parents[1]/'sources'/SOURCE).read_text())
 cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name==symbol)
 methods={n.name:n for n in cls.body if isinstance(n,ast.FunctionDef)}
 refs=[a.init,ref(SOURCE,symbol+'._forward'),a.forward,ref(SOURCE,'BasicConv2d.__init__'),ref(SOURCE,'BasicConv2d.forward')]
 def literal(n):
  if isinstance(n,ast.Name):
   if n.id=='in_channels':return cin
   if n.id=='c7':return c7
   raise ValueError('Unsupported constructor value '+n.id)
  return ast.literal_eval(n)
 configs={}
 for n in methods['__init__'].body:
  if isinstance(n,ast.Assign) and isinstance(n.targets[0],ast.Attribute) and isinstance(n.value,ast.Call) and isinstance(n.value.func,ast.Name) and n.value.func.id=='conv_block':
   configs[n.targets[0].attr]=(literal(n.value.args[0]),literal(n.value.args[1]),{k.arg:literal(k.value) for k in n.value.keywords})
 def pair(x):return x if isinstance(x,(tuple,list)) else [x,x]
 def basic(attr,ins):
  ci,co,kw=configs[attr];k=kw.get('kernel_size',1);s=kw.get('stride',1);p=kw.get('padding',0)
  assert ci==ins[0];hh,ww=[(n+2*pad-kk)//stride+1 for n,pad,kk,stride in zip(ins[1:],pair(p),pair(k),pair(s))];out=shape(co,hh,ww)
  conv=a.conv(attr+'.conv',attr+'.conv',ci,co,k,s,p,bias=False,out=out);bn=a.bn(attr+'.bn',attr+'.bn',co,out,.001);relu=a.relu(attr+'.relu',out,True)
  for n in [conv,bn,relu]:n['source']=refs
  block=a.chain(attr,attr,[conv,bn,relu],out,expand=2,source=refs,role='conv',source_class='BasicConv2d',parameter_scope=attr)
  return block,(co,hh,ww)
 sequences={};dims={};outputs=[]
 for statement in methods['_forward'].body:
  if isinstance(statement,ast.Return):continue
  if not isinstance(statement,ast.Assign) or len(statement.targets)!=1 or not isinstance(statement.targets[0],ast.Name):raise ValueError('Unsupported Inception statement')
  target=statement.targets[0].id;v=statement.value
  if target=='outputs':
   assert isinstance(v,ast.List);outputs=[n.id for n in v.elts];continue
  if isinstance(v,ast.Call) and isinstance(v.func,ast.Attribute) and isinstance(v.func.value,ast.Name) and v.func.value.id=='self':
   operand=v.args[0].id;ins=(cin,h,h) if operand=='x' else dims[operand];b,out=basic(v.func.attr,ins)
   if operand=='x':sequences[target]=[]
   sequences[target].append(b);dims[target]=out
  elif isinstance(v,ast.Call) and ast.unparse(v.func) in ['F.avg_pool2d','F.max_pool2d']:
   kw={k.arg:literal(k.value) for k in v.keywords};k=kw['kernel_size'];s=kw.get('stride',k);p=kw.get('padding',0);size=(h+2*p-k)//s+1;mode='average' if v.func.attr=='avg_pool2d' else 'max'
   n=a.node(target+'.pool',f'{mode}Pool {k} / {s}','pool',shape(cin,size),pool_type=mode,kernel_size=k,stride=s,padding=p,source=[ref(SOURCE,symbol+'._forward')]);sequences[target]=[n];dims[target]=(cin,size,size)
  elif isinstance(v,ast.List):
   branches=[];sizes=[]
   for call in v.elts:
    assert isinstance(call,ast.Call) and call.args[0].id==target
    b,out=basic(call.func.attr,dims[target]);branches.append(b);sizes.append(out)
   fork=a.parallel(target+'.split','Factorized split kernels',branches,'2 independent tensors',expand=2,source=refs)
   sequences[target].append(fork);dims[target]=sizes
  elif isinstance(v,ast.Call) and ast.unparse(v.func)=='torch.cat':
   assert v.args[0].id==target and literal(v.args[1])==1
   sizes=dims[target];out=(sum(x[0] for x in sizes),sizes[0][1],sizes[0][2]);assert all(x[1:]==out[1:] for x in sizes)
   sequences[target].append(a.node(target+'.concat','Concat split outputs','concat',shape(*out),role='concat',dim=1,source=[ref(SOURCE,symbol+'._forward')]));dims[target]=out
  else:raise ValueError('Unsupported Inception value: '+ast.unparse(v))
 branches=[]
 for output in outputs:
  items=sequences[output]
  # In a five-block factorized path, preserve all nodes in IR while folding
  # repeated initial BasicConv bodies in detailed view for compactness.
  if len(items)>4:
   for n in items[:3]:
    if n.get('source_class')=='BasicConv2d':n['expand']=3
  branches.append(a.chain('path.'+output,output,items,shape(*dims[output]),expand=1,source=refs,role='group'))
 total=sum(dims[o][0] for o in outputs);oh,ow=dims[outputs[0]][1:];assert all(dims[o][1:]==(oh,ow) for o in outputs)
 fork=a.parallel('branches','Source-ordered independent paths',branches,'ordered branch list',expand=1,source=refs,branch_order=outputs)
 body=a.chain('module',symbol,[fork,a.node('concat','Concat channel dim=1','concat',shape(total,oh,ow),role='concat',dim=1,ordered_inputs=outputs)],shape(total,oh,ow),expand=1,role='encoder',source=refs)
 return a.model(symbol+' / independent module',doc,body,shape(cin,h),shape(total,oh,ow),dict(scope=symbol+' only; no complete Inception network',constructor=f'{symbol}({cin}'+(f',channels_7x7={c7}' if c7 else '')+')',in_channels=cin,channels_7x7=c7,conv_block=None,output_channels=total,branch_order=outputs,branch_channels=[dims[o][0] for o in outputs]),['Bounded AST adapter reads actual attribute order, kernels, stride/padding, list order and nested cats.','Every BasicConv is Conv(biasFalse) -> BN(eps.001) -> inplace ReLU; real .conv/.bn attributes own independent parameters.','Four or three source paths receive the same x; lists are collected and then channel concatenated.','Repeated initial BasicConv bodies in the five-block path remain folded at detailed view; all operators and identities remain in IR.'],['Do not interchange average/max pool, square/factorized kernels, or source concat order.','InceptionE has two nested kernel splits and three actual Concat operations; no branch summation.'],symbols=[symbol,symbol+'.__init__',symbol+'._forward',symbol+'.forward','BasicConv2d.__init__','BasicConv2d.forward'])
def validate_variant(ir,key):return validate_declaration(ir,build_variant(key))
