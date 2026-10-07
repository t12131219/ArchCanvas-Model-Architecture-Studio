"""Current DuFX native-move/save/source readback, without product imports."""
from pathlib import Path
import ast
import hashlib
import json
import re
import sys

ROOT=Path(__file__).resolve().parents[4];WORK=ROOT/'docs/evidence/m4-draft-port-legibility-work';SOURCE=WORK/'browser-current-attempt-3'
OUT=Path(__file__).parent/'current-moves-save-source-05-10';OUT.mkdir(exist_ok=False);EPS=.025
inputs=[];checks=[];rows=[]
def check(name,value,detail=None):checks.append({'name':name,'pass':bool(value),'detail':detail})
def capture(path):
    data=path.read_bytes();target=OUT/'inputs'/path.relative_to(ROOT) if path.is_relative_to(ROOT) else OUT/'inputs/external'/path.name
    target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data);inputs.append({'path':str(path),'snapshot':str(target.relative_to(OUT)),'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data)});return data
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
        return {'kind':'contact','point':[v0[0],h0[1]],'length':0} if min(h0[0],h1[0])-EPS<=v0[0]<=max(h0[0],h1[0])+EPS and min(v0[1],v1[1])-EPS<=h0[1]<=max(v0[1],v1[1])+EPS else None
    if abs(a[0 if av else 1]-c[0 if cv else 1])>=EPS:return None
    axis=1 if av else 0;lo=max(min(a[axis],b[axis]),min(c[axis],d[axis]));hi=min(max(a[axis],b[axis]),max(c[axis],d[axis]))
    return {'kind':'overlap' if hi-lo>EPS else 'contact','length':max(0,hi-lo)} if hi>=lo-EPS else None
def clean(node):return {**node,'ports':[{k:v for k,v in port.items() if k!='selected'} for port in node['ports']]}
base=json.loads(capture(SOURCE/'04-residual-preset-current.public.json'))['after'];base_camera=nums(base['camera']);node_ids=[node['id'] for node in base['nodes']];edge_ids=[edge['id'] for edge in base['edges']]
bindings=[(0,'output',1,'input'),(1,'output',2,'input'),(2,'output',3,'input'),(3,'output',4,'left'),(0,'output',4,'right'),(4,'output',5,'input')]
add_positions={5:(617,152),6:(707,152),7:(662,107),8:(662,197),9:(662,152),10:(662,152)}
metadata=json.loads(capture(WORK/'saved-artifacts/current-residual/manifest.json'));entry=metadata['files'][0]
saved_bytes=capture(ROOT/entry['snapshot']);actual_bytes=capture(Path(entry['source']));saved=json.loads(saved_bytes);draft=saved['draft']
check('current saved service bytes exactly match bound snapshot',saved_bytes==actual_bytes and hashlib.sha256(saved_bytes).hexdigest()==entry['sha256'] and len(saved_bytes)==entry['bytes'])
check('current new draft declared schema/title/mode',draft['schemaVersion']==1 and draft['mode']=='authored-draft' and draft['title']=='我的模型')
check('current saved revision9/storage1 after one preset and four moved+undo edits',draft['revision']==9 and saved['revision']==1)
check('current saved exact node/edge identities',[node['id'] for node in draft['nodes']]==node_ids and [edge['id'] for edge in draft['edges']]==edge_ids)
check('current saved fixed parameters',[node['parameters'] for node in draft['nodes']]==[{'shape':[1,16],'dtype':'float32'},{'in_features':16,'out_features':32,'bias':True},{},{'in_features':32,'out_features':16,'bias':True},{},{}])
for index,node in enumerate(draft['nodes']):check('current saved baseline node '+str(index),node['kind']==base['nodes'][index]['kind'] and node['label']==base['nodes'][index]['title'] and same([node['position']['x'],node['position']['y']],nums(base['nodes'][index]['transform'])))
for index,(s,sp,t,tp) in enumerate(bindings):check('current saved full typedbinding '+str(index),draft['edges'][index]=={'id':edge_ids[index],'source':{'nodeId':node_ids[s],'portId':sp},'target':{'nodeId':node_ids[t],'portId':tp}})
for prefix in ['05','06','07','08','09','10']:
    files=list(SOURCE.glob(prefix+'-*.public.json'));check('one current capture '+prefix,len(files)==1);path=files[0];case=path.name.removesuffix('.public.json');data=json.loads(capture(path));state=data['after'];number=int(prefix)
    for suffix in ['.dom.txt','-initial.jpg','-settled.jpg']:capture(SOURCE/(case+suffix))
    check(case+' three captures stable',data['before']==data['middle']==data['after'] and data['publicStable'])
    check(case+' current asset URLs',state['assets']==['/assets/index-DuFXKOwG.js','/assets/index--unhoRTb.css'])
    check(case+' frozen camera',same(nums(state['camera']),base_camera))
    check(case+' expected Add world position',same(nums(state['nodes'][4]['transform']),add_positions[number]))
    check(case+' same node/edge IDs',[node['id'] for node in state['nodes']]==node_ids and [edge['id'] for edge in state['edges']]==edge_ids)
    check(case+' horizontal flow and no UI warnings',state['flow']=='horizontal' and state['warnings'] is None)
    boxes=[];anchors=[]
    for index,node in enumerate(state['nodes']):
        expected=clean(base['nodes'][index]);expected['transform']=node['transform'] if index==4 else expected['transform'];check(case+' other visible node facts unchanged '+str(index),clean(node)==expected)
        x,y=nums(node['transform']);height=140 if index==4 else 100;boxes.append((x,y,176,height));check(case+' actual literal body '+str(index),node['body']=={'width':'176','height':str(height)})
        ports=[('output',176,66)] if index==0 else [('input',0,66)] if index==5 else [('left',0,66),('right',0,98),('output',176,66)] if index==4 else [('input',0,66),('output',176,66)];anchor={}
        check(case+' literal ordered ports '+str(index),[port['text'] for port in node['ports']]==[name for name,_,_ in ports])
        for port,(name,px,py) in zip(node['ports'],ports):check(case+' actual dot '+str(index)+'.'+name,same([float(port['cx']),float(port['cy'])],[px,py]));anchor[name]=(x+px,y+py)
        anchors.append(anchor)
    body_overlaps=[]
    for i,(x,y,w,h) in enumerate(boxes):
        for j,(xx,yy,ww,hh) in enumerate(boxes[i+1:],i+1):
            if min(x+w,xx+ww)>max(x,xx)+EPS and min(y+h,yy+hh)>max(y,yy)+EPS:body_overlaps.append([node_ids[i],node_ids[j]])
    check(case+' independent actual body overlaps absent',not body_overlaps,body_overlaps)
    paths=[];routes=[]
    for index,edge in enumerate(state['edges']):
        s,sp,t,tp=bindings[index];points=decode(edge['paths'][1]['d']);paths.append(points)
        check(case+' precise source/target anchors '+str(index),same(points[0],anchors[s][sp]) and same(points[-1],anchors[t][tp]))
        check(case+' source and target normals '+str(index),abs(points[0][1]-points[1][1])<EPS and points[1][0]>points[0][0] and abs(points[-1][1]-points[-2][1])<EPS and points[-1][0]>points[-2][0])
        check(case+' orthogonal nonzero path '+str(index),all((abs(a[0]-b[0])<EPS or abs(a[1]-b[1])<EPS) and not same(a,b) for a,b in zip(points,points[1:])))
        check(case+' no immediate retrace '+str(index),all((b[0]-a[0])*(c[0]-b[0])+(b[1]-a[1])*(c[1]-b[1])>=-EPS for a,b,c in zip(points,points[1:],points[2:])))
        check(case+' transparent and visible path identical '+str(index),edge['paths'][0]['d']==edge['paths'][1]['d'])
        residual=index==4;check(case+' correct role/dash/marker '+str(index),edge['role']==('residual' if residual else 'data') and edge['paths'][1]['dash']==('7px, 4px' if residual else 'none') and edge['paths'][1]['marker']==('url(#draft-skip-arrow)' if residual else 'url(#draft-arrow)'))
        hits=[node_ids[j] for j,box in enumerate(boxes) if any(body_hit(a,b,box) for a,b in zip(points,points[1:]))];check(case+' actual140body penetration absent '+str(index),not hits,hits)
        bends=sum((abs(a[0]-b[0])<EPS)!=(abs(b[0]-c[0])<EPS) for a,b,c in zip(points,points[1:],points[2:]));routes.append({'id':edge['id'],'points':points,'bends':bends,'bodyHitIds':hits})
    contacts=[];shared=[]
    for first,points in enumerate(paths):
        for second,other in enumerate(paths[first+1:],first+1):
            same_source=bindings[first][:2]==bindings[second][:2]
            for ai,(a,b) in enumerate(zip(points,points[1:])):
                for bi,(c,d) in enumerate(zip(other,other[1:])):
                    hit=contact(a,b,c,d)
                    if hit is not None:(shared if same_source else contacts).append({'first':edge_ids[first],'second':edge_ids[second],'segments':[ai,bi],**hit})
    check(case+' no different-producer contacts',not contacts,contacts)
    if number>=9:check(case+' restored reproduces every baseline path',[edge['paths'][1]['d'] for edge in state['edges']]==[edge['paths'][1]['d'] for edge in base['edges']])
    rows.append({'case':case,'addPosition':nums(state['nodes'][4]['transform']),'camera':nums(state['camera']),'routes':routes,'totalBends':sum(row['bends'] for row in routes),'bodyOverlaps':body_overlaps,'differentProducerContacts':contacts,'sameProducerContacts':shared})
generated=capture(SOURCE/'10-current-residual-generated-model.py');tree=ast.parse(generated)
classes=[item for item in tree.body if isinstance(item,ast.ClassDef)];check('generated source one AuthoredModel subclass',len(classes)==1 and classes[0].name=='AuthoredModel' and [ast.unparse(base) for base in classes[0].bases]==['nn.Module'])
methods={item.name:item for item in classes[0].body if isinstance(item,ast.FunctionDef)};check('generated source only constructor and forward',set(methods)=={'__init__','forward'})
constructor=methods['__init__'];check('constructor exact three operators after super',len(constructor.body)==4 and ast.unparse(constructor.body[0])=='super().__init__()')
attributes=[]
for index,statement in enumerate(constructor.body[1:]):
    attributes.append(statement.targets[0].attr);call=statement.value;keywords={item.arg:ast.unparse(item.value) for item in call.keywords}
    expected={'in_features':'16','out_features':'32','bias':'True','dtype':'torch.float32'} if index==0 else {} if index==1 else {'in_features':'32','out_features':'16','bias':'True','dtype':'torch.float32'}
    check('constructor literal operator '+str(index),ast.unparse(call.func)==('nn.ReLU' if index==1 else 'nn.Linear') and not call.args and keywords==expected)
forward=methods['forward'];args=[item.arg for item in forward.args.args];check('forward has one declared input argument',len(args)==2 and args[0]=='self' and not forward.args.defaults and not forward.args.vararg and not forward.args.kwarg and not forward.args.kwonlyargs)
check('forward exactly three calls, one add and Output return',len(forward.body)==5 and all(isinstance(item,ast.Assign) for item in forward.body[:4]) and isinstance(forward.body[4],ast.Return))
values=[item.targets[0].id for item in forward.body[:4]]
for index,statement in enumerate(forward.body[:3]):
    call=statement.value;check('exact forward producer '+str(index),ast.unparse(call.func)=='self.'+attributes[index] and len(call.args)==1 and call.args[0].id==(args[1] if index==0 else values[index-1]) and not call.keywords)
addition=forward.body[3].value;check('residual preserves projection on left and original Input on right',isinstance(addition,ast.BinOp) and isinstance(addition.op,ast.Add) and addition.left.id==values[2] and addition.right.id==args[1])
returned=forward.body[4].value;check('generated return exactly saved Output ID and residual result',isinstance(returned,ast.Dict) and len(returned.keys)==1 and returned.keys[0].value==node_ids[5] and returned.values[0].id==values[3])
capture(Path(__file__))
report={'schema':'archcanvas-dufx-current-moves-save-source-independent/1','pass':all(row['pass'] for row in checks),'checks':checks,'counts':{'cases':len(rows),'publicSamples':len(rows)*3,'checks':len(checks),'passed':sum(row['pass'] for row in checks),'failed':sum(not row['pass'] for row in checks)},'cases':rows,'sourceAST':{'operatorAttributes':attributes,'forwardInput':args[1],'residualOrder':'projection + original Input','savedOutputId':node_ids[5]},'scope':{'productImported':False,'modelExecuted':False,'pixelInspection':False,'fourDirectionMovesOnCurrentRenderer':True,'currentRedoReceipt':False,'fourDirectionCameraOnCurrentRenderer':False,'generationPreviewASTOnly':True,'underlyingParameterSnapshotsPerTransientMove':False,'currentSavedParametersChecked':True,'globalOptimality':False,'humanTrial':False}}
(OUT/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');readback=[{'path':row['path'],'sourceUnchanged':hashlib.sha256(Path(row['path']).read_bytes()).hexdigest()==row['sha256'],'snapshotMatches':hashlib.sha256((OUT/row['snapshot']).read_bytes()).hexdigest()==row['sha256']} for row in inputs]
(OUT/'manifest.json').write_text(json.dumps({'inputs':inputs,'readback':readback,'pass':all(row['sourceUnchanged'] and row['snapshotMatches'] for row in readback)},indent=2)+'\n')
print(json.dumps({'pass':report['pass'],'counts':report['counts'],'inputs':len(inputs),'failed':[row for row in checks if not row['pass']],'bends':{row['case']:row['totalBends'] for row in rows}},ensure_ascii=False));sys.exit(0 if report['pass'] else 2)
