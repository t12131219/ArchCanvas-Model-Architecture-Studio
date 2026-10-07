"""Independent source-AST/saved-draft/public-port audit; no product imports."""
from __future__ import annotations
import argparse,ast,hashlib,json,math,re
import xml.etree.ElementTree as ET
from datetime import datetime,timezone
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
CONTRACT=HERE/'contract.json'

def binding(path:Path)->dict:
 raw=path.read_bytes();return {'path':str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path),'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}

def read(path:Path):return json.loads(path.read_text())
def name(expression):
 if isinstance(expression,ast.Name):return expression.id
 if isinstance(expression,ast.Attribute):return f'{name(expression.value)}.{expression.attr}'
 raise AssertionError(f'unsupported independent AST name {ast.dump(expression)}')

def literal(expression):
 if isinstance(expression,ast.Attribute):return {'symbol':name(expression)}
 return ast.literal_eval(expression)

def ast_contract(source:str,kind_expected:list[str],params_expected:list[dict],output_id:str)->dict:
 tree=ast.parse(source)
 classes=[item for item in tree.body if isinstance(item,ast.ClassDef)]
 assert len(classes)==1 and classes[0].name=='AuthoredModel'
 cls=classes[0];assert [name(base) for base in cls.bases]==['nn.Module']
 initial=next(item for item in cls.body if isinstance(item,ast.FunctionDef) and item.name=='__init__')
 forward=next(item for item in cls.body if isinstance(item,ast.FunctionDef) and item.name=='forward')
 constructors={};order=[]
 for statement in initial.body:
  if isinstance(statement,ast.Assign):
   assert len(statement.targets)==1 and isinstance(statement.targets[0],ast.Attribute) and name(statement.targets[0].value)=='self'
   call=statement.value;assert isinstance(call,ast.Call) and not call.args
   kind=name(call.func);assert kind.startswith('nn.')
   keywords={item.arg:literal(item.value) for item in call.keywords};assert None not in keywords
   identity=statement.targets[0].attr;assert identity not in constructors
   constructors[identity]={'kind':kind[3:],'parameters':keywords};order.append(identity)
 expected=[kind for kind in kind_expected if kind not in ['Input','Output']]
 assert [constructors[identity]['kind'] for identity in order]==expected
 expected_params=[params for kind,params in zip(kind_expected,params_expected) if kind not in ['Input','Output']]
 for identity,kind,params in zip(order,expected,expected_params):
  actual=constructors[identity]['parameters'];required=dict(params)
  if kind in ['Linear','Conv2d']:required['dtype']={'symbol':'torch.float32'}
  assert actual==required,(kind,actual,required)
 args=[arg.arg for arg in forward.args.args];assert len(args)==2 and args[0]=='self'
 producer=args[1];calls=[]
 for statement in forward.body[:-1]:
  assert isinstance(statement,ast.Assign) and len(statement.targets)==1 and isinstance(statement.targets[0],ast.Name)
  call=statement.value;assert isinstance(call,ast.Call) and name(call.func).startswith('self.') and len(call.args)==1 and not call.keywords
  attribute=name(call.func).split('.',1)[1];assert attribute in constructors and name(call.args[0])==producer
  producer=statement.targets[0].id;calls.append({'constructor':attribute,'output':producer,'input':name(call.args[0])})
 assert [call['constructor'] for call in calls]==order
 returned=forward.body[-1];assert isinstance(returned,ast.Return) and isinstance(returned.value,ast.Dict)
 assert len(returned.value.keys)==1 and literal(returned.value.keys[0])==output_id and name(returned.value.values[0])==producer
 return {'constructors':constructors,'constructorOrder':order,'inputArgument':args[1],'forwardCalls':calls,'returnOutputId':output_id,'returnProducer':producer,'sourceSha256':hashlib.sha256(source.encode()).hexdigest(),'modelImportedOrExecuted':False}

def ordered_draft(draft:dict)->list[dict]:
 assert draft['schemaVersion']==1 and draft['mode']=='authored-draft'
 nodes={node['id']:node for node in draft['nodes']};assert len(nodes)==len(draft['nodes'])
 assert len({edge['id'] for edge in draft['edges']})==len(draft['edges'])
 starts=[node for node in nodes.values() if node['kind']=='Input'];assert len(starts)==1
 ordered=[starts[0]];used=set()
 while ordered[-1]['kind']!='Output':
  outgoing=[edge for edge in draft['edges'] if edge['source']['nodeId']==ordered[-1]['id']];assert len(outgoing)==1
  edge=outgoing[0];assert edge['source']['portId']=='output' and edge['target']['portId']=='input'
  assert edge['id'] not in used and edge['target']['nodeId'] in nodes
  used.add(edge['id']);ordered.append(nodes[edge['target']['nodeId']]);assert len(ordered)<=len(nodes)
 assert len(ordered)==len(nodes) and len(used)==len(draft['edges'])==len(nodes)-1
 return ordered

def declared_shapes(ordered:list[dict])->list[list[int]]:
 shapes=[]
 for node in ordered:
  kind,p=node['kind'],node['parameters']
  if kind=='Input':
   assert p['dtype']=='float32';shape=list(p['shape'])
  elif kind=='Linear':
   assert shape[-1]==p['in_features'];shape=[*shape[:-1],p['out_features']]
  elif kind=='Conv2d':
   assert len(shape)==4 and shape[1]==p['in_channels']
   spatial=[math.floor((shape[axis+2]+2*p['padding'][axis]-p['dilation'][axis]*(p['kernel_size'][axis]-1)-1)/p['stride'][axis]+1) for axis in range(2)]
   assert min(spatial)>0;shape=[shape[0],p['out_channels'],*spatial]
  elif kind=='MaxPool2d':
   assert len(shape)==4 and p['ceil_mode'] is False
   spatial=[math.floor((shape[axis+2]+2*p['padding'][axis]-p['dilation'][axis]*(p['kernel_size'][axis]-1)-1)/p['stride'][axis]+1) for axis in range(2)]
   shape=[*shape[:2],*spatial]
  elif kind=='AdaptiveAvgPool2d':shape=[*shape[:-2],*p['output_size']]
  elif kind=='Flatten':
   start=p['start_dim']%len(shape);end=p['end_dim']%len(shape);assert start<=end
   shape=[*shape[:start],math.prod(shape[start:end+1]),*shape[end+1:]]
  else:assert kind in ['GELU','ReLU','Output']
  shapes.append(list(shape))
 return shapes

def svg_public(value:dict)->dict:
 xml=ET.fromstring(value['svg'])
 nodes={};ports={};edges={}
 for group in xml.iter():
  identity=group.get('data-draft-node')
  if identity:
   transform=re.fullmatch(r'translate\(([-+.\d]+) ([-+.\d]+)\)',group.get('transform',''));assert transform
   kind=next(element.text for element in group if element.get('class')=='draft-node-kind')
   label=next(element.text for element in group if element.get('class')=='draft-node-title')
   nodes[identity]={'kind':kind,'label':label,'x':float(transform[1]),'y':float(transform[2]),'xml':ET.tostring(group,encoding='unicode')}
   for port in group:
    if port.get('data-draft-port'):
     circle=next(element for element in port if element.tag.split('}')[-1]=='circle' and element.get('r')=='5')
     key=(identity,port.get('data-draft-port'));assert key not in ports
     ports[key]={'x':float(transform[1])+float(circle.get('cx')),'y':float(transform[2])+float(circle.get('cy')),'class':port.get('class'),'label':port.get('aria-label')}
  edge=group.get('data-draft-edge')
  if edge:
   paths=[element for element in group if element.tag.split('}')[-1]=='path' and element.get('marker-end')];assert len(paths)==1
   assert edge not in edges;edges[edge]={'path':paths[0].get('d'),'xml':ET.tostring(group,encoding='unicode')}
 return {'nodes':nodes,'ports':ports,'edges':edges,'scripts':value.get('scripts',[]),'url':value.get('url')}

def line_points(path:str)->list[tuple[float,float]]:
 tokens=re.findall(r'[MHV]|[-+]?(?:\d*\.)?\d+(?:e[-+]?\d+)?',path,re.I);points=[];i=0;x=y=0.
 while i<len(tokens):
  command=tokens[i];i+=1
  if command=='M':x=float(tokens[i]);y=float(tokens[i+1]);i+=2
  elif command=='H':x=float(tokens[i]);i+=1
  elif command=='V':y=float(tokens[i]);i+=1
  else:raise AssertionError(f'Unsupported public draft path token {command}')
  points.append((x,y))
 return points

def draft_case(envelope_path:Path,public_path:Path,source_path:Path,expected:dict)->dict:
 envelope=read(envelope_path);draft=envelope['draft'];ordered=ordered_draft(draft)
 assert [node['kind'] for node in ordered]==expected['kindsInProducerOrder']
 assert [node['parameters'] for node in ordered]==expected['parameters']
 shapes=declared_shapes(ordered);assert shapes==expected['declaredShapes']
 public=svg_public(read(public_path));assert set(public['nodes'])=={node['id'] for node in ordered}
 assert set(public['edges'])=={edge['id'] for edge in draft['edges']}
 for node in ordered:
  actual=public['nodes'][node['id']];assert actual['kind']==node['kind'] and actual['label']==node['label']
  assert actual['x']==node['position']['x'] and actual['y']==node['position']['y']
 bindings=[]
 for edge in draft['edges']:
  start=public['ports'][(edge['source']['nodeId'],edge['source']['portId'])];end=public['ports'][(edge['target']['nodeId'],edge['target']['portId'])]
  assert 'out' in start['class'].split() and 'in' in end['class'].split()
  points=line_points(public['edges'][edge['id']]['path'])
  assert points[0]==(start['x'],start['y']) and points[-1]==(end['x'],end['y'])
  assert all(a[0]==b[0] or a[1]==b[1] for a,b in zip(points,points[1:]))
  bindings.append({'edgeId':edge['id'],'source':edge['source'],'target':edge['target'],'points':points})
 ast_result=ast_contract(source_path.read_text(),expected['kindsInProducerOrder'],expected['parameters'],ordered[-1]['id'])
 return {'draftId':draft['id'],'draftRevision':draft['revision'],'storeRevision':envelope['revision'],'kinds':[node['kind'] for node in ordered],
         'nodeIds':[node['id'] for node in ordered],'edgeIds':[edge['id'] for edge in draft['edges']],
         'publicPortPathBindings':bindings,'publicScripts':public['scripts'],'declaredShapesExpected':expected['declaredShapes'],'declaredShapesIndependentlyCalculatedFromActualParameters':shapes,
         'shapeScope':'Static input declarations and literal constructor algebra; not observed runtime tensors.','sourceAst':ast_result,'passed':True}

def managed_case(envelope_path:Path,before_path:Path,after_path:Path,source_path:Path,ast_result:dict)->dict:
 envelope=read(envelope_path);document=envelope['document'];architecture=document['architecture'];source=source_path.read_text()
 assert len(architecture['sources'])==1 and architecture['sources'][0]['path']=='model.py'
 assert architecture['sources'][0]['content']==source and architecture['sources'][0]['digest']==hashlib.sha256(source.encode()).hexdigest()
 nodes={node['id']:node for node in architecture['nodes']};root=[node for node in nodes.values() if node['kind']=='Module'];assert len(root)==1
 root=root[0];assert len(nodes)==5 and len(root['children'])==4 and set(root['children'])==set(nodes)-{root['id']}
 input_id=f"input:model.AuthoredModel:{ast_result['inputArgument']}";output_id='output:model.AuthoredModel:0'
 operator_ids=[f"call:instance:model.AuthoredModel.{identity}" for identity in ast_result['constructorOrder']]
 assert set(nodes)=={root['id'],input_id,output_id,*operator_ids}
 for identity,canonical in zip(ast_result['constructorOrder'],operator_ids):
  expected=ast_result['constructors'][identity];actual=nodes[canonical];assert actual['kind']==expected['kind']
  parameters=dict(expected['parameters']);dtype=parameters.pop('dtype',None)
  actual_params=dict(actual['parameters']);actual_dtype=actual_params.pop('dtype',None)
  assert actual_params==parameters
  if dtype:assert actual_dtype=={'expression':'torch.float32','origin':'unknown'}
  assert actual['parentId']==root['id'] and actual['evidence']=='contract'
 assert nodes[output_id]['outputPath']==[{'kind':'key','key':ast_result['returnOutputId']}]
 expected_edges=[(input_id,input_id+':out:'+ast_result['inputArgument'],root['id'],root['id']+':in:'+ast_result['inputArgument'],'tensor:'+input_id+':'+ast_result['inputArgument'],'data')]
 sequence=[input_id,*operator_ids,output_id]
 for index,(start,end) in enumerate(zip(sequence,sequence[1:])):
  out_name=ast_result['inputArgument'] if index==0 else 'output';in_name='value' if end==output_id else 'input'
  expected_edges.append((start,start+':out:'+out_name,end,end+':in:'+in_name,'tensor:'+start+':'+out_name,'data'))
 actual_edges=[(edge['source']['nodeId'],edge['source']['portId'],edge['target']['nodeId'],edge['target']['portId'],edge['tensorId'],edge['role']) for edge in architecture['edges']]
 assert sorted(actual_edges)==sorted(expected_edges)
 source_lines=source.splitlines(keepends=True);source_witnesses=[]
 for node in nodes.values():
  witness=node['source'];assert witness['path']=='model.py'
  actual=''.join(source_lines[witness['line']-1:witness['endLine']]).strip()
  assert actual==witness['expression']
  source_witnesses.append({'nodeId':node['id'],'line':witness['line'],'endLine':witness['endLine'],'expressionExact':True})
  for parameter,origin in node.get('parameterOrigins',{}).items():
   assert origin['path']=='model.py' and origin['line']==origin['endLine']
   line=source_lines[origin['line']-1].encode();segment=line[origin['column']:origin['endColumn']].decode()
   assert segment==origin['expression']
   if parameter!='dtype':assert ast.literal_eval(segment)==node['parameters'][parameter]
 before,after=read(before_path),read(after_path);assert before['svg']==after['svg'] and before['metadata']==after['metadata']
 assert before['metadata']['documentId']==document['id'] and before['metadata']['revision']==document['revision']==0
 assert before['metadata']['sourceDigest']==architecture['sourceDigest']==document['sourceBindingDigest']
 assert before['metadata']['irDigest']==architecture['irDigest']
 assert {item['canonicalNodeId'] for item in before['metadata']['renderedNodes']}==set(nodes)
 canonical_edges={edge['id']:edge for edge in architecture['edges']}
 rendered=before['metadata']['renderedBindings'];assert len(rendered)==3
 for item in rendered:
  assert len(item['canonicalEdgeIds'])==1;edge=canonical_edges[item['canonicalEdgeIds'][0]]
  assert all(item[key]==edge[key] for key in ['source','target','tensorId','role'])
 return {'documentId':document['id'],'documentRevision':document['revision'],'storeRevision':envelope['revision'],
         'architectureNodes':len(nodes),'architectureEdges':len(actual_edges),'publicRenderedEdges':len(rendered),
         'sourceSha256':hashlib.sha256(source.encode()).hexdigest(),'exactSourceAstAndCanonicalPortBindings':True,
         'sourceLineWitnesses':source_witnesses,'literalParameterOriginUtf8SpansExact':True,
         'sameRevisionBeforeAfterPublicSvgExact':True,'publicationExportOrRuntimeVerified':False,'passed':True}

def main()->None:
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--spec',type=Path,required=True);parser.add_argument('--output-dir',type=Path,required=True);args=parser.parse_args()
 specification=read(args.spec);work=(ROOT/specification['artifactRoot']).resolve();out=args.output_dir.resolve();out.mkdir(parents=True,exist_ok=False)
 contract=read(CONTRACT);live=[ROOT/item['source'] for item in read(work/specification['copyReceipt'])['records']]
 inputs=[Path(__file__).resolve(),CONTRACT,args.spec.resolve(),*live,*[p for p in work.rglob('*') if p.is_file()]];inputs=sorted(set(inputs));before=[binding(path) for path in inputs]
 for index,path in enumerate(inputs):
  destination=out/'inputs'/f'{index:03d}-{path.name}';destination.parent.mkdir(parents=True,exist_ok=True)
  with destination.open('xb') as stream:stream.write(path.read_bytes())
 results=[]
 for label,expected_name in [('fourNode','fourNodeExpected'),('cnnPreset','cnnPresetExpected')]:
  case=specification[label]
  try:result=draft_case(work/case['envelope'],work/case['public'],work/case['source'],contract[expected_name]);result['case']=label
  except Exception as error:result={'case':label,'passed':False,'error':f'{type(error).__name__}: {error}'}
  results.append(result)
 if specification.get('managedFourNode'):
  case=specification['managedFourNode']
  try:
   first=next(result for result in results if result['case']=='fourNode');assert first['passed']
   result=managed_case(work/case['envelope'],work/case['before'],work/case['after'],work/specification['fourNode']['source'],first['sourceAst']);result['case']='managedFourNode'
  except Exception as error:result={'case':'managedFourNode','passed':False,'error':f'{type(error).__name__}: {error}'}
  results.append(result)
 if specification.get('identityUndo'):
  case=specification['identityUndo']
  try:
   prior,added,undone=[svg_public(read(work/case[key])) for key in ['before','added','undone']]
   assert set(added['nodes'])-set(prior['nodes']) and len(set(added['nodes'])-set(prior['nodes']))==1
   new_id=next(iter(set(added['nodes'])-set(prior['nodes'])));assert added['nodes'][new_id]['kind']=='Identity'
   assert set(prior['nodes']).issubset(added['nodes']) and added['edges']==prior['edges']
   def visible_node_fact(node):return {name:node[name] for name in ['kind','label','x','y']}
   for identity in prior['nodes']:assert visible_node_fact(added['nodes'][identity])==visible_node_fact(prior['nodes'][identity])
   assert {identity:visible_node_fact(node) for identity,node in undone['nodes'].items()}=={identity:visible_node_fact(node) for identity,node in prior['nodes'].items()}
   assert undone['edges']==prior['edges']
   result={'case':'identityUndo','passed':True,'priorNodes':len(prior['nodes']),'addedNodes':len(added['nodes']),'undoneNodes':len(undone['nodes']),'addedIdentityId':new_id,'existingNodeKindLabelPositionsAndEdgesRestoredExact':True,'selectedAndWarningPresentationIsNotCanonicalState':True}
  except Exception as error:result={'case':'identityUndo','passed':False,'error':f'{type(error).__name__}: {error}'}
  results.append(result)
 try:
  copies=read(work/specification['copyReceipt'])['records'];associations=[]
  for item in copies:
   actual=ROOT/item['source'];copied=ROOT/item['copy'];left,right=binding(actual),binding(copied)
   assert left['bytes']==right['bytes']==item['bytes'] and left['sha256']==right['sha256']==item['sha256']
   associations.append({'actualSource':left,'copy':right,'receiptBindingExact':True})
  assert (work/'actual-managed-model.py').read_bytes()==(work/specification['fourNode']['source']).read_bytes()
  assert (work/'generated-source-visible.py').read_bytes()==(work/specification['fourNode']['source']).read_bytes()
  assert read(work/'saved-draft-envelope.json')==read(work/specification['fourNode']['envelope'])
  inventory=(work/'final-build-reopened-four-node-dom.txt').read_text();kinds=re.findall(r'button "添加 ([A-Za-z0-9]+)"',inventory)
  expected_catalog=['Input','Output','Linear','ReLU','GELU','SiLU','Dropout','Identity','Flatten','Conv2d','MaxPool2d','AdaptiveAvgPool2d','BatchNorm2d','LayerNorm','Embedding','Add','Concat']
  assert sorted(kinds)==sorted(expected_catalog)
  preset_labels=re.findall(r'button "([^"\n]+)"',inventory)
  actual_presets=[label for label in preset_labels if label in ['添加 最小 MLP','添加 小型 CNN','添加 残差 MLP']];assert len(actual_presets)==3
  failed_drag=(work/'final-build-identity-drag-nine-dom.txt').read_text();failed_undo=(work/'final-build-identity-undo-eight-dom.txt').read_text()
  assert '8 模块 7 连接' in failed_drag and '0 模块 0 连接' in failed_undo
  click_added=(work/'final-build-identity-click-nine-dom.txt').read_text();click_undo=(work/'final-build-identity-click-undo-eight-dom.txt').read_text()
  assert '9 模块 7 连接' in click_added and '8 模块 7 连接' in click_undo
  declaration=read(work/'root-native-action-declaration.json')
  assert declaration['initialBuild']=='index-BfOQqeU2.js' and declaration['finalBuild']=='index-BKbgeBjI.js'
  results.append({'case':'liveCopiesAndActualUiInventory','passed':True,'copyAssociations':associations,'fourNodeOldFinalManagedSourceBytesExact':True,
                  'oldSavedAndLiveSavedDraftJsonExact':True,'basicModuleIds':sorted(kinds),'basicModuleCount':len(kinds),
                  'presetLabelsObserved':actual_presets,'firstIdentityDragRetained8NodesAndUndoRemovedPriorInsertionTo0':True,
                  'laterClickAdded9AndUndo8':True,'nativeActionProvenance':{'scope':declaration['scope'],'initialBuild':declaration['initialBuild'],'finalBuild':declaration['finalBuild'],'misleadingNamesRetained':declaration['misleadingHistoricalFilenames']},
                  'perModuleRuntimeOrHumanCertified':False})
 except Exception as error:results.append({'case':'liveCopiesAndActualUiInventory','passed':False,'error':f'{type(error).__name__}: {error}'})
 after=[binding(path) for path in inputs]
 report={'protocol':'archcanvas-authoring-browser-independent-readback/1','createdUtc':datetime.now(timezone.utc).isoformat(),'cases':results,
         'inputBindingsBefore':before,'inputBindingsAfter':after,'inputsUnchanged':before==after,'allInputsCopiedExact':all(hashlib.sha256((out/'inputs'/f'{index:03d}-{path.name}').read_bytes()).hexdigest()==before[index]['sha256'] for index,path in enumerate(inputs)),
         'allCasesPassed':all(result['passed'] for result in results),'browserOperatedByAuditor':False,'productImportedOrExecutedByAuditor':False,'modelsExecuted':False,
         'scope':'Static actual saved/source/public-port artifact audit. Native actions need root raw tool provenance; no per-module, runtime, training, publication, human or fullM4 certification.','humanParticipants':0,'runtimeCertified':False,'publicationCertified':False,'m4Complete':False}
 with (out/'receipt.json').open('x') as stream:json.dump(report,stream,ensure_ascii=False,indent=2);stream.write('\n')
 print(json.dumps({'receipt':binding(out/'receipt.json'),'passedCases':sum(result['passed'] for result in results),'allCases':len(results),'inputsUnchanged':before==after}));raise SystemExit(0 if before==after and report['allCasesPassed'] else 2)

if __name__=='__main__':main()
