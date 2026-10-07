"""DuFX current target readback; no product import or model execution."""
from pathlib import Path
import hashlib
import json
import re
import sys

ROOT=Path(__file__).resolve().parents[4];WORK=ROOT/'docs/evidence/m4-draft-port-legibility-work'
SOURCE=WORK/'browser-current-attempt-3';OUT=Path(__file__).parent/'current-target-01-04';OUT.mkdir(exist_ok=False)
checks=[];inputs=[];rows=[];EPS=.025
def check(name,value,detail=None):checks.append({'name':name,'pass':bool(value),'detail':detail})
def capture(path):
    data=path.read_bytes();target=OUT/'inputs'/path.relative_to(ROOT);target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
    inputs.append({'path':str(path.relative_to(ROOT)),'snapshot':str(target.relative_to(OUT)),'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data)});return data
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
def box_overlap(a,b):return min(a[0]+a[2],b[0]+b[2])>max(a[0],b[0]) and min(a[1]+a[3],b[1]+b[3])>max(a[1],b[1])
saved=json.loads(capture(WORK/'saved-artifacts/concat/draft-df40f773-5f17-4a9a-a535-a2b20ded78b5.json'))['draft']
historical=json.loads(capture(WORK/'browser-current-attempt-2/18-concat-56percent-checked.public.json'))['after']
historical_paths=[edge['paths'][1]['d'] for edge in historical['edges']]
for prefix in ['01','02','03','04']:
    files=list(SOURCE.glob(prefix+'-*.public.json'));check('one current capture '+prefix,len(files)==1);path=files[0];case=path.name.removesuffix('.public.json');data=json.loads(capture(path));state=data['after'];camera=nums(state['camera']);vertical=prefix!='04'
    for suffix in ['.dom.txt','-initial.jpg','-settled.jpg']:capture(SOURCE/(case+suffix))
    check(case+' three public reads stable',data['before']==data['middle']==data['after'] and data['publicStable'])
    check(case+' current DuFX assets',state['assets']==['/assets/index-DuFXKOwG.js','/assets/index--unhoRTb.css'])
    check(case+' retained viewport1280x720dpr1',state['viewport']=={'dpr':1,'height':720,'width':1280})
    check(case+' expected axis and no warnings',state['flow']==('vertical' if vertical else 'horizontal') and state['warnings'] is None)
    kinds=['Input','Input','Concat','Output'] if vertical else ['Input','Linear','ReLU','Linear','Add','Output']
    positions=[(290,172),(290,300),(290,428),(290,596)] if vertical else [(-330,152),(-82,152),(166,152),(414,152),(662,152),(910,152)]
    bindings=[(0,'output',2,'a'),(1,'output',2,'b'),(2,'output',3,'input')] if vertical else [(0,'output',1,'input'),(1,'output',2,'input'),(2,'output',3,'input'),(3,'output',4,'left'),(0,'output',4,'right'),(4,'output',5,'input')]
    check(case+' expected ordered kinds',[node['kind'] for node in state['nodes']]==kinds)
    check(case+' expected distinct node/edge identities',len(set(node['id'] for node in state['nodes']))==len(kinds) and len(set(edge['id'] for edge in state['edges']))==len(bindings))
    if vertical:
        check(case+' saved draft exact ordered node/edge IDs',[node['id'] for node in state['nodes']]==[node['id'] for node in saved['nodes']] and [edge['id'] for edge in state['edges']]==[edge['id'] for edge in saved['edges']])
        check(case+' retained baseline paths under text-only repair',[edge['paths'][1]['d'] for edge in state['edges']]==historical_paths)
        check(case+' current56percent overview',abs(camera[2]-.5603977702191989)<1e-12)
    else:check(case+' current53percent overview',abs(camera[2]-.5304054054054054)<1e-12)
    boxes=[];anchors=[];paint=[]
    for index,node in enumerate(state['nodes']):
        x,y=nums(node['transform']);height=140 if node['kind'] in ('Add','Concat') else 100;boxes.append((x,y,176,height));anchor={};label_boxes={}
        check(case+' fixed placement '+str(index),same([x,y],positions[index]));check(case+' actual body '+str(index),node['body']=={'width':'176','height':str(height)})
        if vertical:ports=[('output',88,100)] if index in (0,1) else [('a',176/3,0),('b',352/3,0),('output',88,140)] if index==2 else [('input',88,0)]
        else:ports=[('output',176,66)] if index==0 else [('input',0,66)] if index==5 else [('left',0,66),('right',0,98),('output',176,66)] if index==4 else [('input',0,66),('output',176,66)]
        check(case+' literal ordered ports '+str(index),[port['text'] for port in node['ports']]==[name for name,_,_ in ports])
        for port,(name,px,py) in zip(node['ports'],ports):
            output=name=='output';font=float(port['font'].removesuffix('px'));check(case+' dot '+str(index)+'.'+name,same([float(port['cx']),float(port['cy'])],[px,py]));anchor[name]=(x+px,y+py)
            expected_x=px+(-22 if vertical and output else -12 if output else 12)
            check(case+' correct offset '+str(index)+'.'+name,abs(float(port['textX'])-expected_x)<1e-9)
            expected_y=py+font+4 if vertical and output else py-4 if vertical else py+font/3
            check(case+' exterior/side baseline '+str(index)+'.'+name,abs(float(port['textY'])-expected_y)<.0001)
            check(case+' compensated CSS estimate '+str(index)+'.'+name,abs(font*camera[2]-8.1)<.0001)
            advance={'output':3.36,'input':2.56,'left':2,'right':2.56,'a':.56,'b':.56}[name];tx=x+float(port['textX']);ty=y+float(port['textY']);label_boxes[name]=(tx-advance*font if output else tx,ty-font,advance*font,font)
        anchors.append(anchor);paint.append(label_boxes)
    body_overlaps=[[state['nodes'][i]['id'],state['nodes'][j]['id']] for i,box in enumerate(boxes) for j,other in enumerate(boxes[i+1:],i+1) if box_overlap(box,other)]
    check(case+' independent body overlaps absent',not body_overlaps,body_overlaps)
    if vertical:
        check(case+' InputB output and Concat a nominal paint disjoint',not box_overlap(paint[1]['output'],paint[2]['a']),{'output':paint[1]['output'],'concatA':paint[2]['a']})
        check(case+' observed horizontal label gap4.666667world',abs(paint[2]['a'][0]-(paint[1]['output'][0]+paint[1]['output'][2])-14/3)<1e-9)
        check(case+' output paint starts fourworld below card bottom',abs(paint[2]['output'][1]-(428+140+4))<.0001)
    routes=[];paths=[]
    for index,edge in enumerate(state['edges']):
        s,sp,t,tp=bindings[index];points=decode(edge['paths'][1]['d']);paths.append(points);check(case+' exact port endpoints '+str(index),same(points[0],anchors[s][sp]) and same(points[-1],anchors[t][tp]))
        check(case+' orthogonal finite polyline '+str(index),all(abs(a[0]-b[0])<EPS or abs(a[1]-b[1])<EPS for a,b in zip(points,points[1:])))
        check(case+' outward/inward normal '+str(index),abs(points[0][0 if vertical else 1]-points[1][0 if vertical else 1])<EPS and points[1][1 if vertical else 0]>points[0][1 if vertical else 0] and abs(points[-1][0 if vertical else 1]-points[-2][0 if vertical else 1])<EPS and points[-1][1 if vertical else 0]>points[-2][1 if vertical else 0])
        check(case+' coincident transparent and visible paths '+str(index),edge['paths'][0]['d']==edge['paths'][1]['d'])
        residual=not vertical and index==4
        check(case+' correct role/dash/marker '+str(index),edge['role']==('residual' if residual else 'data') and edge['paths'][1]['dash']==('7px, 4px' if residual else 'none') and edge['paths'][1]['marker']==('url(#draft-skip-arrow)' if residual else 'url(#draft-arrow)'))
        hits=[state['nodes'][j]['id'] for j,box in enumerate(boxes) if any(body_hit(a,b,box) for a,b in zip(points,points[1:]))];check(case+' actual140body not penetrated '+str(index),not hits,hits)
        bends=sum((abs(a[0]-b[0])<EPS)!=(abs(b[0]-c[0])<EPS) for a,b,c in zip(points,points[1:],points[2:]));routes.append({'id':edge['id'],'points':points,'bends':bends,'bodyHitIds':hits})
    contacts=[];shared=[]
    for first,points in enumerate(paths):
        for second,other in enumerate(paths[first+1:],first+1):
            same_producer=bindings[first][:2]==bindings[second][:2]
            for ai,(a,b) in enumerate(zip(points,points[1:])):
                for bi,(c,d) in enumerate(zip(other,other[1:])):
                    hit=contact(a,b,c,d)
                    if hit is not None:(shared if same_producer else contacts).append({'first':routes[first]['id'],'second':routes[second]['id'],'segments':[ai,bi],**hit})
    check(case+' no different-producer contacts',not contacts,contacts)
    if prefix=='02':check('actual keyboard b tooltip identifies InputB',state['tooltip']=='张量拼接 · b输入端口 · 来自 输入 B声明 float32 · 1×16先选择输出端口，再连接到这里。')
    rows.append({'case':case,'camera':camera,'routes':routes,'totalBends':sum(row['bends'] for row in routes),'differentProducerContacts':contacts,'sameProducerContacts':shared,'bodyOverlaps':body_overlaps,'InputBOutputConcatALabelGapWorld':14/3 if vertical else None,'publicTooltip':state['tooltip']})
generated=capture(SOURCE/'03-concat-generated-model.py');historical_source=capture(WORK/'saved-artifacts/concat/projects/09a609c0d0734463800a5c095cf49867/source/model.py');check('current generated preview retains exact independently AST-reviewed source bytes',generated==historical_source)
receipt=json.loads(capture(WORK/'checks-final-attempt-3/receipt.json'))
for entry in receipt['build']:
    data=capture(ROOT/entry['path']);check('current build bytes match checks receipt '+entry['path'],hashlib.sha256(data).hexdigest()==entry['sha256'] and len(data)==entry['bytes'])
for path in ['studio/src/draftPortPresentation.ts','studio/tests/draft-port-geometry-independent.test.ts']:
    data=capture(ROOT/path);binding=next(row for row in receipt['inputs'] if row['path']==path);check('frozen repaired source matches checks receipt '+path,hashlib.sha256(data).hexdigest()==binding['sha256'] and len(data)==binding['bytes'])
capture(Path(__file__))
report={'schema':'archcanvas-dufx-current-target-independent/1','pass':all(row['pass'] for row in checks),'checks':checks,'counts':{'cases':len(rows),'publicSamples':len(rows)*3,'checks':len(checks),'passed':sum(row['pass'] for row in checks),'failed':sum(not row['pass'] for row in checks)},'cases':rows,'scope':{'currentAssets':['index-DuFXKOwG.js','index--unhoRTb.css'],'productImported':False,'modelExecuted':False,'pixelInspection':False,'currentTargetOnly':True,'fourDirectionMovesOnCurrentRenderer':False,'globalOptimality':False,'humanTrial':False}}
(OUT/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');readback=[{'path':row['path'],'sourceUnchanged':hashlib.sha256((ROOT/row['path']).read_bytes()).hexdigest()==row['sha256'],'snapshotMatches':hashlib.sha256((OUT/row['snapshot']).read_bytes()).hexdigest()==row['sha256']} for row in inputs]
(OUT/'manifest.json').write_text(json.dumps({'inputs':inputs,'readback':readback,'pass':all(row['sourceUnchanged'] and row['snapshotMatches'] for row in readback)},indent=2)+'\n')
print(json.dumps({'pass':report['pass'],'counts':report['counts'],'inputs':len(inputs),'failed':[row for row in checks if not row['pass']],'bends':{row['case']:row['totalBends'] for row in rows}},ensure_ascii=False))
sys.exit(0 if report['pass'] else 2)
