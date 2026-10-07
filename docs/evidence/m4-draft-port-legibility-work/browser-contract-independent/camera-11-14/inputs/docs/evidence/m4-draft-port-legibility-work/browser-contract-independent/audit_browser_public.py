"""Independent readback of already captured browser public geometry.

Only this fresh evidence directory is written. Product modules are neither
imported nor called; fixed contracts and geometry sensors are authored here.
"""
from pathlib import Path
import argparse
import hashlib
import json
import math
import re
import sys

ROOT = Path(__file__).resolve().parents[4]
WORK = ROOT / 'docs/evidence/m4-draft-port-legibility-work'
SOURCE = WORK / 'browser-current-attempt-2'
EPS = .025
ASSETS = ['/assets/index-Bf83amY-.js', '/assets/index--unhoRTb.css']
parser = argparse.ArgumentParser()
parser.add_argument('--stage', required=True)
parser.add_argument('--prefixes', required=True)
args = parser.parse_args()
OUT = Path(__file__).parent / args.stage
OUT.mkdir(exist_ok=False)
checks, bindings, rows = [], [], []

def check(name, value, detail=None):
    checks.append({'name': name, 'pass': bool(value), 'detail': detail})

def archive(path):
    data = path.read_bytes()
    destination = OUT / 'inputs' / path.relative_to(ROOT)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(data)
    binding = {'path': str(path.relative_to(ROOT)), 'sha256': hashlib.sha256(data).hexdigest(), 'bytes': len(data), 'snapshot': str(destination.relative_to(OUT))}
    bindings.append(binding)
    return data

def numbers(value):
    return [float(item) for item in re.findall(r'[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?', value)]

def same(a, b):
    return len(a) == len(b) and all(abs(x-y) < EPS for x,y in zip(a,b))

def decode(path):
    tokens = re.findall(r'[A-Za-z]|[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?', path)
    points=[]
    while tokens:
        command=tokens.pop(0)
        if command in ('M','L'): point=(float(tokens.pop(0)),float(tokens.pop(0)))
        elif command=='H' and points: point=(float(tokens.pop(0)),points[-1][1])
        elif command=='V' and points: point=(points[-1][0],float(tokens.pop(0)))
        else: raise ValueError('unsupported captured route '+command)
        points.append(point)
    return points

def body_hits(a,b,box):
    x,y,width,height=box
    if abs(a[0]-b[0]) < EPS:
        return x+EPS < a[0] < x+width-EPS and max(min(a[1],b[1]),y+EPS) < min(max(a[1],b[1]),y+height-EPS)
    return y+EPS < a[1] < y+height-EPS and max(min(a[0],b[0]),x+EPS) < min(max(a[0],b[0]),x+width-EPS)

def intersect(a,b,c,d):
    av=abs(a[0]-b[0])<EPS;cv=abs(c[0]-d[0])<EPS
    if av != cv:
        v0,v1,h0,h1=(a,b,c,d) if av else (c,d,a,b)
        if min(h0[0],h1[0])-EPS <= v0[0] <= max(h0[0],h1[0])+EPS and min(v0[1],v1[1])-EPS <= h0[1] <= max(v0[1],v1[1])+EPS:
            return {'kind':'contact','point':[v0[0],h0[1]],'length':0}
        return None
    if abs(a[0 if av else 1]-c[0 if cv else 1])>=EPS: return None
    axis=1 if av else 0
    low=max(min(a[axis],b[axis]),min(c[axis],d[axis]));high=min(max(a[axis],b[axis]),max(c[axis],d[axis]))
    if high<low-EPS:return None
    return {'kind':'overlap' if high-low>EPS else 'contact','point':[a[0],low] if av else [low,a[1]],'length':max(0,high-low)}

def clean_node(node):
    return {**node, 'ports':[{key:value for key,value in port.items() if key!='selected'} for port in node['ports']]}

base=json.loads((SOURCE/'01-residual-fit.public.json').read_text())['after']
archive(SOURCE/'01-residual-fit.public.json')
role_names=['input','hidden','relu','projection','add','output']
expected_kinds=['Input','Linear','ReLU','Linear','Add','Output']
expected_positions=[(72,172),(320,172),(568,172),(816,172),(1064,172),(1312,172)]
node_ids=[node['id'] for node in base['nodes']]
edge_ids=[edge['id'] for edge in base['edges']]
expected_bindings=[(0,'output',1,'input'),(1,'output',2,'input'),(2,'output',3,'input'),(3,'output',4,'left'),(0,'output',4,'right'),(4,'output',5,'input')]
base_camera=numbers(base['camera'])
check('baseline has six expected ordered kinds',[node['kind'] for node in base['nodes']]==expected_kinds)
check('baseline has six unique visible node and edge identities',len(set(node_ids))==6 and len(set(edge_ids))==6)
check('baseline expected hand-authored positions',all(same(numbers(node['transform']),position) for node,position in zip(base['nodes'],expected_positions)))
check('baseline camera is observed53percent overview',same(base_camera,[-6.216216216216214,123.89189189189189,.5304054054054054]))
saved_baseline_path=ROOT/'docs/evidence/m4-native-matching-work/authoring-artifacts/drafts/draft-e3158996-40d4-4a98-a8f3-c93fc6b79a56.json'
saved_baseline=json.loads(archive(saved_baseline_path))['draft']
check('exact historical residual save has same visible node/edge IDs',[node['id'] for node in saved_baseline['nodes']]==node_ids and [edge['id'] for edge in saved_baseline['edges']]==edge_ids)
check('historical saved residual baseline literal schema/mode',saved_baseline['schemaVersion']==1 and saved_baseline['mode']=='authored-draft')
check('historical saved residual baseline parameters', [node['parameters'] for node in saved_baseline['nodes']]==[{'shape':[1,16],'dtype':'float32'},{'in_features':16,'out_features':32,'bias':True},{},{'in_features':32,'out_features':16,'bias':True},{},{}])
for index,(source,source_port,target,target_port) in enumerate(expected_bindings):
    edge=saved_baseline['edges'][index]
    check('historical saved residual exact binding '+str(index),edge['source']=={'nodeId':node_ids[source],'portId':source_port} and edge['target']=={'nodeId':node_ids[target],'portId':target_port})
for index,node in enumerate(saved_baseline['nodes']):
    check('historical saved residual baseline title/kind/position '+str(index),node['label']==base['nodes'][index]['title'] and node['kind']==expected_kinds[index] and same([node['position']['x'],node['position']['y']],expected_positions[index]))
expected_add={1:(1064,172),2:(1064,172),3:(1064,172),4:(1019,172),5:(1019,172),6:(1109,172),7:(1064,127),8:(1064,217),9:(1064,172),10:(1064,172)}
selected_files=[]
for prefix in args.prefixes.split(','):
    matches=sorted(SOURCE.glob(prefix+'-*.public.json'))
    check('exactly one capture for '+prefix,len(matches)==1,[str(path.relative_to(ROOT)) for path in matches])
    selected_files.extend(matches)
for path in selected_files:
    case=path.name.removesuffix('.public.json');number=int(case[:2]);data=json.loads(archive(path))
    for suffix in ['.dom.txt','-initial.jpg','-settled.jpg']:
        artifact=SOURCE/(case+suffix)
        check(case+' artifact '+suffix+' exists',artifact.exists())
        if artifact.exists():archive(artifact)
    stable=data['before']==data['middle']==data['after']
    check(case+' actual three public captures are equal',stable)
    check(case+' declared stability matches comparison',data['publicStable']==stable)
    state=data['after'];camera=numbers(state['camera'])
    check(case+' observed build assets',state['assets']==ASSETS)
    check(case+' preserved viewport1280x720dpr1',state['viewport']=={'dpr':1,'height':720,'width':1280})
    check(case+' ordered visible IDs', [node['id'] for node in state['nodes']]==node_ids and [edge['id'] for edge in state['edges']]==edge_ids)
    check(case+' retained horizontal projection',state['flow']=='horizontal')
    check(case+' expected Add world position',same(numbers(state['nodes'][4]['transform']),expected_add.get(number,(1064,172))))
    camera_delta={11:(24,0),12:(-24,0),13:(0,-24),14:(0,24)}.get(number,(0,0))
    expected_camera=[base_camera[0]+camera_delta[0],base_camera[1]+camera_delta[1],base_camera[2]]
    check(case+' exact expected camera translation',same(camera,expected_camera))
    expected_nodes=[]
    for index,node in enumerate(state['nodes']):
        expected=clean_node(base['nodes'][index])
        if index==4:expected['transform']=node['transform']
        check(case+' preserves node '+role_names[index]+' identity/body/port facts',clean_node(node)==expected)
        expected_nodes.append(expected)
    boxes=[];anchors=[]
    for index,node in enumerate(state['nodes']):
        x,y=numbers(node['transform']);height=140 if index==4 else 100
        check(case+' literal body '+role_names[index],node['body']=={'width':'176','height':str(height)})
        box=(x,y,176,height);boxes.append(box)
        expected_ports=[('output',176,66)] if index==0 else [('input',0,66)] if index==5 else [('left',0,66),('right',0,98),('output',176,66)] if index==4 else [('input',0,66),('output',176,66)]
        actual_ports={port['text']:port for port in node['ports']};anchor={}
        check(case+' literal ordered ports '+role_names[index],[port['text'] for port in node['ports']]==[name for name,_,_ in expected_ports])
        for name,px,py in expected_ports:
            port=actual_ports[name];check(case+' literal dot '+role_names[index]+'.'+name,same([float(port['cx']),float(port['cy'])],[px,py]))
            anchor[name]=(x+px,y+py)
            close_css=abs(float(port['font'].removesuffix('px'))*camera[2]-8.1)<.0001
            check(case+' compensated port CSS estimate '+role_names[index]+'.'+name,close_css)
        anchors.append(anchor)
    body_overlaps=[]
    for index,a in enumerate(boxes):
        for later,b in enumerate(boxes[index+1:],index+1):
            if min(a[0]+a[2],b[0]+b[2])>max(a[0],b[0])+EPS and min(a[1]+a[3],b[1]+b[3])>max(a[1],b[1])+EPS:body_overlaps.append([node_ids[index],node_ids[later]])
    check(case+' independent body overlaps absent',not body_overlaps,body_overlaps)
    route_rows=[];all_points=[]
    for index,edge in enumerate(state['edges']):
        source,source_port,target,target_port=expected_bindings[index]
        check(case+' transparent hit and visible path coincide '+str(index),len(edge['paths'])==2 and edge['paths'][0]['d']==edge['paths'][1]['d'])
        visible=edge['paths'][1];points=decode(visible['d']);all_points.append(points)
        check(case+' ordered exact source and target anchors '+str(index),same(points[0],anchors[source][source_port]) and same(points[-1],anchors[target][target_port]))
        check(case+' source and target normals '+str(index),abs(points[0][1]-points[1][1])<EPS and points[1][0]>points[0][0] and abs(points[-1][1]-points[-2][1])<EPS and points[-1][0]>points[-2][0])
        axis_aligned=all(abs(a[0]-b[0])<EPS or abs(a[1]-b[1])<EPS for a,b in zip(points,points[1:]))
        check(case+' orthogonal path '+str(index),axis_aligned)
        no_retrace=all((b[0]-a[0])*(c[0]-b[0])+(b[1]-a[1])*(c[1]-b[1])>=-EPS for a,b,c in zip(points,points[1:],points[2:]))
        check(case+' no immediate retracing '+str(index),no_retrace)
        hits=[node_ids[body] for body,box in enumerate(boxes) if any(body_hits(a,b,box) for a,b in zip(points,points[1:]))]
        check(case+' independent actual body penetration absent '+str(index),not hits,hits)
        bends=sum((abs(a[0]-b[0])<EPS)!=(abs(b[0]-c[0])<EPS) for a,b,c in zip(points,points[1:],points[2:]))
        role='residual' if index==4 else 'data';selected='selected' in edge['class'].split()
        if number in (10,16) and index==4:check(case+' named skip selection is publicly selected',selected)
        check(case+' residual role '+str(index),edge['role']==role)
        check(case+' residual dash '+str(index),visible['dash']==('7px, 4px' if role=='residual' else 'none'))
        check(case+' arrow marker '+str(index),visible['marker']==('url(#draft-selected-arrow)' if selected else 'url(#draft-skip-arrow)' if role=='residual' else 'url(#draft-arrow)'))
        route_rows.append({'edgeId':edge['id'],'bindingByVisiblePortContract':{'sourceNode':node_ids[source],'sourcePort':source_port,'targetNode':node_ids[target],'targetPort':target_port},'points':points,'bendCount':bends,'length':sum(abs(a[0]-b[0])+abs(a[1]-b[1]) for a,b in zip(points,points[1:])),'bodyHitIds':hits,'role':role})
    contacts=[];shared=[]
    for first,points in enumerate(all_points):
        for second,other in enumerate(all_points[first+1:],first+1):
            shared_source=expected_bindings[first][:2]==expected_bindings[second][:2]
            for ai,(a,b) in enumerate(zip(points,points[1:])):
                for bi,(c,d) in enumerate(zip(other,other[1:])):
                    hit=intersect(a,b,c,d)
                    if hit:
                        entry={'first':edge_ids[first],'second':edge_ids[second],'firstSegment':ai,'secondSegment':bi,**hit}
                        (shared if shared_source else contacts).append(entry)
    check(case+' different-producer contact/overlap absent',not contacts,contacts)
    check(case+' no UI warnings',state['warnings'] is None)
    if number==2:check(case+' left tooltip resolves projection',state['tooltip']=='残差相加 · left输入端口 · 来自 投影层 32 → 16声明 float32 · 1×16先选择输出端口，再连接到这里。')
    if number==3:check(case+' keyboard right tooltip resolves Input',state['tooltip']=='残差相加 · right输入端口 · 来自 输入声明 float32 · 1×16先选择输出端口，再连接到这里。')
    rows.append({'case':case,'addPosition':numbers(state['nodes'][4]['transform']),'camera':camera,'publicCaptureStable':stable,'bodyOverlaps':body_overlaps,'routes':route_rows,'differentProducerSegmentContacts':contacts,'sharedProducerSegmentContacts':shared,'totalBends':sum(route['bendCount'] for route in route_rows),'publicTooltip':state['tooltip']})
by_number={int(row['case'][:2]):row for row in rows}
if 4 in by_number and 5 in by_number:check('left redo repeats entire public world geometry',by_number[4]['routes']==by_number[5]['routes'])
if 1 in by_number and 9 in by_number:check('restored reproduces baseline world geometry',by_number[1]['routes']==by_number[9]['routes'])
for relative in ['studio/dist/index.html','studio/dist/assets/index-Bf83amY-.js','studio/dist/assets/index--unhoRTb.css','docs/evidence/m4-draft-port-legibility-work/checks-final-attempt-2/receipt.json']:
    archive(ROOT/relative)
archive(Path(__file__))
report={'schema':'archcanvas-independent-browser-public-contract/1','cases':rows,'checks':checks,'pass':all(row['pass'] for row in checks),'counts':{'cases':len(rows),'publicSamples':len(rows)*3,'checks':len(checks),'passed':sum(row['pass'] for row in checks),'failed':sum(not row['pass'] for row in checks)},'scope':{'productImported':False,'typedDraftEnvelopePresent':'historical exact baseline saved draft, no current per-move envelope','publicNodePortRouteContractOnly':True,'nativeGestureEvidence':'root-collected action provenance; this readback verifies resulting public data, not gesture execution','pixelInspection':False,'globalOptimality':False,'humanTrial':False}}
(OUT/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
readback=[]
for row in bindings:
    unchanged=hashlib.sha256((ROOT/row['path']).read_bytes()).hexdigest()==row['sha256']
    saved=hashlib.sha256((OUT/row['snapshot']).read_bytes()).hexdigest()==row['sha256']
    readback.append({'path':row['path'],'sourceUnchanged':unchanged,'snapshotMatches':saved})
(OUT/'manifest.json').write_text(json.dumps({'inputs':bindings,'bindingReadback':readback,'pass':all(row['sourceUnchanged'] and row['snapshotMatches'] for row in readback)},ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'pass':report['pass'],'counts':report['counts'],'inputs':len(bindings),'failedChecks':[row for row in checks if not row['pass']],'bends':{row['case']:row['totalBends'] for row in rows}},ensure_ascii=False))
sys.exit(0 if report['pass'] else 2)
