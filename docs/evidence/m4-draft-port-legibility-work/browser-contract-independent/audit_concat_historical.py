"""Independent Bf83 saved Concat/public geometry/source AST readback."""
from pathlib import Path
import ast
import hashlib
import json
import re
import sys

ROOT=Path(__file__).resolve().parents[4];WORK=ROOT/'docs/evidence/m4-draft-port-legibility-work'
SOURCE=WORK/'browser-current-attempt-2';OUT=Path(__file__).parent/'concat-bf83-historical-17-20';OUT.mkdir(exist_ok=False)
checks=[];inputs=[];rows=[];EPS=.025
def check(name,value,detail=None):checks.append({'name':name,'pass':bool(value),'detail':detail})
def capture(path):
    data=path.read_bytes();target=OUT/'inputs'/path.relative_to(ROOT) if path.is_relative_to(ROOT) else OUT/'inputs/external'/path.name
    target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
    inputs.append({'path':str(path),'snapshot':str(target.relative_to(OUT)),'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data)})
    return data
def nums(value):return [float(item) for item in re.findall(r'[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?',value)]
def same(a,b):return len(a)==len(b) and all(abs(x-y)<EPS for x,y in zip(a,b))
def decode(value):
    tokens=re.findall(r'[A-Za-z]|[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?',value);points=[]
    while tokens:
        cmd=tokens.pop(0)
        if cmd in ('M','L'):point=(float(tokens.pop(0)),float(tokens.pop(0)))
        elif cmd=='H':point=(float(tokens.pop(0)),points[-1][1])
        elif cmd=='V':point=(points[-1][0],float(tokens.pop(0)))
        else:raise ValueError(cmd)
        points.append(point)
    return points
def body_hit(a,b,box):
    x,y,w,h=box
    return x+EPS<a[0]<x+w-EPS and max(min(a[1],b[1]),y+EPS)<min(max(a[1],b[1]),y+h-EPS) if abs(a[0]-b[0])<EPS else y+EPS<a[1]<y+h-EPS and max(min(a[0],b[0]),x+EPS)<min(max(a[0],b[0]),x+w-EPS)
def contact(a,b,c,d):
    av=abs(a[0]-b[0])<EPS;cv=abs(c[0]-d[0])<EPS
    if av!=cv:
        v0,v1,h0,h1=(a,b,c,d) if av else (c,d,a,b)
        return [v0[0],h0[1]] if min(h0[0],h1[0])-EPS<=v0[0]<=max(h0[0],h1[0])+EPS and min(v0[1],v1[1])-EPS<=h0[1]<=max(v0[1],v1[1])+EPS else None
    if abs(a[0 if av else 1]-c[0 if cv else 1])>=EPS:return None
    axis=1 if av else 0;lo=max(min(a[axis],b[axis]),min(c[axis],d[axis]));hi=min(max(a[axis],b[axis]),max(c[axis],d[axis]))
    return {'kind':'overlap' if hi-lo>EPS else 'contact','length':max(0,hi-lo)} if hi>=lo-EPS else None
def intersect_boxes(a,b):return min(a[0]+a[2],b[0]+b[2])>max(a[0],b[0]) and min(a[1]+a[3],b[1]+b[3])>max(a[1],b[1])
metadata=json.loads(capture(WORK/'saved-artifacts/concat/manifest.json'));saved=None;model_bytes=None;managed=None
for entry in metadata['files']:
    data=capture(ROOT/entry['snapshot']);actual=capture(Path(entry['source']))
    check('actual service bytes exact '+entry['snapshot'],data==actual and hashlib.sha256(data).hexdigest()==entry['sha256'] and len(data)==entry['bytes'])
    if entry['snapshot'].endswith('/model.py'):model_bytes=data
    elif entry['snapshot'].endswith('/project.json'):managed=json.loads(data)
    else:saved=json.loads(data)
draft=saved['draft'];node_ids=[node['id'] for node in draft['nodes']];edge_ids=[edge['id'] for edge in draft['edges']]
expected_kinds=['Input','Input','Concat','Output'];positions=[(290,172),(290,300),(290,428),(290,596)]
check('new draft exact schema title mode',draft['schemaVersion']==1 and draft['mode']=='authored-draft' and draft['title']=='双输入拼接 · 视图搭建')
check('new saved draft revisions10and1',draft['revision']==10 and saved['revision']==1)
check('new draft four distinct nodes and three distinct edges',len(set(node_ids))==4 and len(set(edge_ids))==3)
check('new draft expected ordered kinds',[node['kind'] for node in draft['nodes']]==expected_kinds)
check('new declared parameter facts',[node['parameters'] for node in draft['nodes']]==[{'shape':[1,16],'dtype':'float32'},{'shape':[1,16],'dtype':'float32'},{'dim':1},{}])
bindings=[(0,'output',2,'a'),(1,'output',2,'b'),(2,'output',3,'input')]
for index,(s,sp,t,tp) in enumerate(bindings):
    check('exact saved binding '+str(index),draft['edges'][index]=={'id':edge_ids[index],'source':{'nodeId':node_ids[s],'portId':sp},'target':{'nodeId':node_ids[t],'portId':tp}})
    check('saved node position '+str(index),same([draft['nodes'][index]['position']['x'],draft['nodes'][index]['position']['y']],positions[index]))
check('saved output position',same([draft['nodes'][3]['position']['x'],draft['nodes'][3]['position']['y']],positions[3]))
for prefix in ['17','18','19','20']:
    paths=list(SOURCE.glob(prefix+'-*.public.json'));check('one complete public capture '+prefix,len(paths)==1)
    path=paths[0];case=path.name.removesuffix('.public.json');data=json.loads(capture(path));state=data['after'];camera=nums(state['camera'])
    for suffix in ['.dom.txt','-initial.jpg','-settled.jpg']:capture(SOURCE/(case+suffix))
    check(case+' three public samples stable',data['before']==data['middle']==data['after'] and data['publicStable'])
    check(case+' Bf83 historical assets',state['assets']==['/assets/index-Bf83amY-.js','/assets/index--unhoRTb.css'])
    check(case+' vertical flow without warnings',state['flow']=='vertical' and state['warnings'] is None)
    check(case+' visible saved IDs',[node['id'] for node in state['nodes']]==node_ids and [edge['id'] for edge in state['edges']]==edge_ids)
    boxes=[];anchors=[];text_boxes=[]
    for index,node in enumerate(state['nodes']):
        x,y=nums(node['transform']);height=140 if index==2 else 100;boxes.append((x,y,176,height));anchor={};paint={}
        check(case+' literal kind/alias/position '+str(index),node['kind']==expected_kinds[index] and node['title']==draft['nodes'][index]['label'] and same([x,y],positions[index]))
        check(case+' actual body '+str(index),node['body']=={'width':'176','height':str(height)})
        expected=[('output',88,100)] if index in (0,1) else [('a',176/3,0),('b',352/3,0),('output',88,140)] if index==2 else [('input',88,0)]
        check(case+' ordered ports '+str(index),[port['text'] for port in node['ports']]==[name for name,_,_ in expected])
        for port,(name,px,py) in zip(node['ports'],expected):
            font=float(port['font'].removesuffix('px'));output=name=='output';advance={'output':3.36,'input':2.56,'a':.56,'b':.56}[name]
            check(case+' actual dot '+str(index)+'.'+name,same([float(port['cx']),float(port['cy'])],[px,py]));anchor[name]=(x+px,y+py)
            check(case+' historical xoffset '+str(index)+'.'+name,abs(float(port['textX'])-(px+(-12 if output else 12)))<EPS)
            check(case+' exterior nominal baseline '+str(index)+'.'+name,abs(float(port['textY'])-(py+font+4 if output else py-4))<.0001)
            check(case+' label CSS estimate '+str(index)+'.'+name,abs(font*camera[2]-8.1)<.0001)
            tx=x+float(port['textX']);ty=y+float(port['textY']);paint[name]=(tx-advance*font if output else tx,ty-font,advance*font,font)
        anchors.append(anchor);text_boxes.append(paint)
    overlaps=[]
    for index,box in enumerate(boxes):
        for later,other in enumerate(boxes[index+1:],index+1):
            if intersect_boxes(box,other):overlaps.append([node_ids[index],node_ids[later]])
    check(case+' independent nonoverlap actual140body',not overlaps,overlaps)
    routes=[];paths=[]
    for index,edge in enumerate(state['edges']):
        s,sp,t,tp=bindings[index];points=decode(edge['paths'][-1]['d']);paths.append(points)
        check(case+' exact route endpoints '+str(index),same(points[0],anchors[s][sp]) and same(points[-1],anchors[t][tp]))
        check(case+' identical transparent and visible route '+str(index),edge['paths'][0]['d']==edge['paths'][1]['d'])
        check(case+' vertical endpoint normals '+str(index),abs(points[0][0]-points[1][0])<EPS and points[1][1]>points[0][1] and abs(points[-1][0]-points[-2][0])<EPS and points[-1][1]>points[-2][1])
        check(case+' full data role '+str(index),edge['role']=='data' and edge['paths'][1]['dash']=='none' and edge['paths'][1]['marker']=='url(#draft-arrow)')
        hits=[node_ids[j] for j,box in enumerate(boxes) if any(body_hit(a,b,box) for a,b in zip(points,points[1:]))]
        check(case+' body penetration absent '+str(index),not hits,hits)
        bends=sum((abs(a[0]-b[0])<EPS)!=(abs(b[0]-c[0])<EPS) for a,b,c in zip(points,points[1:],points[2:]))
        routes.append({'id':edge['id'],'points':points,'bends':bends,'bodyHits':hits})
    contacts=[]
    for first,points in enumerate(paths):
        for second,other in enumerate(paths[first+1:],first+1):
            for ai,(a,b) in enumerate(zip(points,points[1:])):
                for bi,(c,d) in enumerate(zip(other,other[1:])):
                    hit=contact(a,b,c,d)
                    if hit is not None:contacts.append({'first':edge_ids[first],'second':edge_ids[second],'segments':[ai,bi],'intersection':hit})
    check(case+' different producer contacts absent',not contacts,contacts)
    bbox_overlap=intersect_boxes(text_boxes[1]['output'],text_boxes[2]['a'])
    if prefix=='18':check('historical56percent recorded label overlap is preserved',bbox_overlap,{'output':text_boxes[1]['output'],'concatA':text_boxes[2]['a']})
    rows.append({'case':case,'camera':camera,'routes':routes,'totalBends':sum(row['bends'] for row in routes),'contacts':contacts,'nominalInputBOutputConcatALabelOverlap':bbox_overlap,'nominalOutputLabelBox':text_boxes[1]['output'],'nominalConcatALabelBox':text_boxes[2]['a'],'rendererHistorical':True})
check('save and generate preserve exactly same public geometry',rows[0]['routes']==rows[1]['routes']==rows[2]['routes']==rows[3]['routes'])
generated=capture(SOURCE/'20-concat-generated-model.py');check('browser generated preview equals actual managed source bytes',generated==model_bytes)
tree=ast.parse(generated);imports=tree.body[1:3]
check('source imports torch and nn only',ast.dump(imports[0],include_attributes=False)=="Import(names=[alias(name='torch')])" and ast.dump(imports[1],include_attributes=False)=="ImportFrom(module='torch', names=[alias(name='nn')], level=0)")
classes=[item for item in tree.body if isinstance(item,ast.ClassDef)];check('one AuthoredModel nn.Module class',len(classes)==1 and classes[0].name=='AuthoredModel' and ast.unparse(classes[0].bases[0])=='nn.Module')
methods={item.name:item for item in classes[0].body if isinstance(item,ast.FunctionDef)};check('only constructor and forward',set(methods)=={'__init__','forward'})
check('constructor has only super initialization',len(methods['__init__'].body)==1 and ast.unparse(methods['__init__'].body[0])=='super().__init__()')
forward=methods['forward'];args=[item.arg for item in forward.args.args];check('forward declares exactly two positional tensor arguments',len(args)==3 and args[0]=='self' and not forward.args.defaults and not forward.args.vararg and not forward.args.kwarg and not forward.args.kwonlyargs)
check('forward has only cat assignment and return',len(forward.body)==2 and isinstance(forward.body[0],ast.Assign) and isinstance(forward.body[1],ast.Return))
assignment=forward.body[0];call=assignment.value;check('cat uses ordered Input A/B with exact dim1',isinstance(call,ast.Call) and ast.unparse(call.func)=='torch.cat' and len(call.args)==1 and isinstance(call.args[0],ast.Tuple) and [item.id for item in call.args[0].elts]==args[1:] and len(call.keywords)==1 and call.keywords[0].arg=='dim' and isinstance(call.keywords[0].value,ast.Constant) and call.keywords[0].value.value==1)
ret=forward.body[1].value;check('return binds saved Output identity to cat result',isinstance(ret,ast.Dict) and len(ret.keys)==1 and ret.keys[0].value==node_ids[3] and ret.values[0].id==assignment.targets[0].id)
check('managed project exact entry and copy scope',managed=={'id':'09a609c0d0734463800a5c095cf49867','entry':'model:AuthoredModel','scope':'managed-copy'})
capture(Path(__file__))
report={'schema':'archcanvas-bf83-concat-independent-historical/1','pass':all(row['pass'] for row in checks),'checks':checks,'counts':{'cases':len(rows),'publicSamples':len(rows)*3,'checks':len(checks),'passed':sum(row['pass'] for row in checks),'failed':sum(not row['pass'] for row in checks)},'cases':rows,'sourceAST':{'forwardArguments':args[1:],'concatDim':1,'returnedOutputId':node_ids[3]},'scope':{'rendererHistorical':'Bf83amY- prior vertical output offset repair','nominalLabelOverlapRecorded':True,'productImported':False,'modelExecuted':False,'pixelInspection':False,'globalOptimality':False,'humanTrial':False}}
(OUT/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');readback=[{'path':row['path'],'sourceUnchanged':hashlib.sha256(Path(row['path']).read_bytes()).hexdigest()==row['sha256'],'snapshotMatches':hashlib.sha256((OUT/row['snapshot']).read_bytes()).hexdigest()==row['sha256']} for row in inputs]
(OUT/'manifest.json').write_text(json.dumps({'inputs':inputs,'readback':readback,'pass':all(row['sourceUnchanged'] and row['snapshotMatches'] for row in readback)},indent=2)+'\n')
print(json.dumps({'pass':report['pass'],'counts':report['counts'],'inputs':len(inputs),'failed':[row for row in checks if not row['pass']],'bends':{row['case']:row['totalBends'] for row in rows},'historicalLabelOverlap':{row['case']:row['nominalInputBOutputConcatALabelOverlap'] for row in rows}},ensure_ascii=False))
sys.exit(0 if report['pass'] else 2)
