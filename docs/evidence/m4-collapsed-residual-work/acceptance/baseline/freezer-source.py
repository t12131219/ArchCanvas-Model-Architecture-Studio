"""Copy frozen au3 evidence and compute literal route facts without product imports."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import re
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[4]
OUT=Path(__file__).resolve().parent
DEST=OUT/'baseline'
CORE=ROOT/'docs/evidence/visual-golds-au3-matrix'
BOUND=ROOT/'docs/evidence/m4-au3-visual-matrix-work/bound'
NS='{http://www.w3.org/2000/svg}'
CACHE={}

def read(path):
    raw=path.read_bytes();assert path not in CACHE or CACHE[path]==raw;CACHE[path]=raw;return raw
def bind(path,raw):return {'path':str(path.relative_to(ROOT)),'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}
def points(path):
    tokens=re.findall(r'[A-Za-z]|[-+]?(?:\d*\.\d+|\d+\.?\d*)(?:[eE][-+]?\d+)?',path)
    assert re.sub(r'\s+','', ''.join(tokens))==re.sub(r'\s+','',path)
    result=[];i=0
    while i<len(tokens):
        c=tokens[i];i+=1
        if c in ('M','L'):p=[float(tokens[i]),float(tokens[i+1])];i+=2
        elif c=='H':p=[float(tokens[i]),result[-1][1]];i+=1
        elif c=='V':p=[result[-1][0],float(tokens[i])];i+=1
        else:raise ValueError(c)
        assert not result or p[0]==result[-1][0] or p[1]==result[-1][1]
        result.append(p)
    return result
def route_stats(path):
    p=points(path);segments=[(a,b) for a,b in zip(p,p[1:]) if a!=b]
    axes=[int(a[0]==b[0]) for a,b in segments]
    return {'points':p,'length':sum(abs(a[0]-b[0])+abs(a[1]-b[1]) for a,b in segments),
            'bends':sum(a!=b for a,b in zip(axes,axes[1:]))}
def copy(path,target):
    raw=read(path);target.open('xb').write(raw);assert target.read_bytes()==raw
    return {'source':bind(path,raw),'copy':bind(target,raw)}

assert not DEST.exists();DEST.mkdir(parents=True)
records=[]
for fixture,count in [('residual_cnn',3),('mlp',2),('transformer',4)]:
    for level in range(count):
        key=f'{fixture}-level{level}-paper-180'
        files={name:copy(source,DEST/(key+'.'+name)) for name,source in [
            ('canvas.json',CORE/(key+'.canvas.json')),('scene.json',CORE/(key+'.scene.json')),
            ('svg',CORE/(key+'.svg')),('actual-canvas.json',BOUND/key/'canvas.json'),
            ('public.svg',BOUND/key/'browser-scene.svg')]}
        canvas=json.loads(read(CORE/(key+'.canvas.json')));scene=json.loads(read(CORE/(key+'.scene.json')))
        actual=json.loads(read(BOUND/key/'canvas.json'))
        assert {k:v for k,v in canvas.items() if k!='revision'}=={k:v for k,v in actual.items() if k!='revision'}
        svg=ET.fromstring(read(CORE/(key+'.svg')));public=ET.fromstring(read(BOUND/key/'browser-scene.svg'))
        meta=json.loads(svg.find(NS+'metadata').text);pmeta=json.loads(public.find(NS+'metadata').text)
        assert {k:v for k,v in meta.items() if k!='revision'}=={k:v for k,v in pmeta.items() if k!='revision'}
        def svgpaths(root):
            return {g.get('data-edge-id'):next(x for x in g if x.tag==NS+'path').get('d') for g in root.iter() if g.get('data-edge-id')}
        paths=svgpaths(svg);assert paths==svgpaths(public)=={e['id']:e['path'] for e in scene['edges']}
        routes=[{'id':e['id'],'sourceId':e['sourceId'],'targetId':e['targetId'],
                 'canonicalEdgeIds':e['canonicalEdgeIds'],'source':e['source'],'target':e['target'],
                 'tensorId':e['tensorId'],'role':e['role'],'stroke':e['stroke'],'width':e['width'],'dashed':e['dashed'],
                 'path':e['path'],**route_stats(e['path'])} for e in scene['edges']]
        records.append({'key':key,'fixture':fixture,'level':level,'files':files,
                        'sourceDigest':scene['sourceDigest'],'irDigest':scene['irDigest'],
                        'nodes':len(scene['nodes']),'canonicalEdges':len(canvas['architecture']['edges']),
                        'renderedEdges':len(routes),'hiddenEdges':scene['hiddenEdges'],'routes':routes})
cnn=records[0];edge=next(e for e in cnn['routes'] if e['id']=='edge:9')
assert edge['path']=='M 209.3 316 V 329 H 326 V 341 H 209.3 V 354'
assert abs(edge['length']-271.4)<1e-9 and edge['bends']==4
candidate='M 209.3 316 V 354';assert route_stats(candidate)['length']==38 and route_stats(candidate)['bends']==0
source=read(Path(__file__));(DEST/'freezer-source.py').open('xb').write(source)
before=[bind(p,r) for p,r in sorted(CACHE.items())];after=[bind(p,p.read_bytes()) for p in sorted(CACHE)]
assert before==after
manifest={'protocol':'archcanvas-collapsed-residual-independent-baseline/1','createdAt':datetime.now(timezone.utc).isoformat(),
          'productExecuted':False,'modelsExecuted':False,'rendererExecuted':False,'browserOperated':False,
          'expectedDerivedFrom':'Frozen au3 actual public SVG and independently parsed archived core Scene/Canvas; no post-change product helper.',
          'records':records,'literalCnn':{'edgeId':'edge:9','oldPath':edge['path'],'oldLength':271.4,'oldBends':4,
                                      'candidatePath':candidate,'candidateLength':38,'candidateBends':0,
                                      'canonicalTargetRemainsHiddenAdd':edge['target'],'displayTarget':edge['targetId'],
                                      'preserveRoleAndSeparateDataLane':True},
          'inputsBefore':before,'inputsAfter':after,'inputsUnchanged':True,'freezerSource':bind(Path(__file__),source)}
raw=(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n').encode();(DEST/'capture.json').open('xb').write(raw)
print(json.dumps({'capture':bind(DEST/'capture.json',raw),'cases':len(records),'inputs':len(before),'unchanged':True}))
