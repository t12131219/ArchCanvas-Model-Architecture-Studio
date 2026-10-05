import json, re, math, hashlib, pathlib, xml.etree.ElementTree as ET
ROOT=pathlib.Path('/home/fzg/PycharmProjects/ArchCanvas/ArchCanvas_Model_Architecture_Studio')
OUT=pathlib.Path(__file__).parent
def points(path):
    tokens=re.findall(r'[A-Za-z]|[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?',path)
    result=[];i=0;x=y=0
    while i<len(tokens):
        cmd=tokens[i];i+=1
        if cmd in ('M','L'): x=float(tokens[i]);y=float(tokens[i+1]);i+=2
        elif cmd=='H':x=float(tokens[i]);i+=1
        elif cmd=='V':y=float(tokens[i]);i+=1
        else:raise ValueError(cmd)
        if not result or result[-1]!=(x,y):result.append((x,y))
    for a,b in zip(result,result[1:]):assert a[0]==b[0] or a[1]==b[1]
    return result
def compact(points):
    result=[]
    for p in points:
        if result and result[-1]==p:continue
        while len(result)>1:
            a,b=result[-2:]
            if a[0]==b[0]==p[0] and (b[1]-a[1])*(p[1]-b[1])>=0 or a[1]==b[1]==p[1] and (b[0]-a[0])*(p[0]-b[0])>=0:result.pop()
            else:break
        result.append(p)
    return result
def segment_cross(a,b,c,d):
    if a[0]==b[0] and c[1]==d[1] and min(c[0],d[0])<a[0]<max(c[0],d[0]) and min(a[1],b[1])<c[1]<max(a[1],b[1]):return a[0],c[1]
    if a[1]==b[1] and c[0]==d[0] and min(a[0],b[0])<c[0]<max(a[0],b[0]) and min(c[1],d[1])<a[1]<max(c[1],d[1]):return c[0],a[1]
def overlap(a,b,c,d):
    if a[0]==b[0]==c[0]==d[0]:return max(0,min(max(a[1],b[1]),max(c[1],d[1]))-max(min(a[1],b[1]),min(c[1],d[1])))
    if a[1]==b[1]==c[1]==d[1]:return max(0,min(max(a[0],b[0]),max(c[0],d[0]))-max(min(a[0],b[0]),min(c[0],d[0])))
    return 0
def edge_stats(edges):
    crosses=[];coincidences=[];per_edge=[]
    for e in edges:
        p=compact(e['points']);directions=[0 if a[1]==b[1] else 1 for a,b in zip(p,p[1:])]
        length=sum(abs(a[0]-b[0])+abs(a[1]-b[1]) for a,b in zip(p,p[1:]));minimum=abs(p[0][0]-p[-1][0])+abs(p[0][1]-p[-1][1])
        reversals=sum((b[0]-a[0])*(c[0]-b[0])+(b[1]-a[1])*(c[1]-b[1])<0 for a,b,c in zip(p,p[1:],p[2:]))
        per_edge.append({'id':e['id'],'role':e['role'],'tensorId':e['tensorId'],'source':e['source'],'target':e['target'],'path':e['path'],'points':p,'bends':sum(a!=b for a,b in zip(directions,directions[1:])),'reversals':reversals,'length':length,'manhattanMinimum':minimum,'excessLength':length-minimum})
    for i,e in enumerate(edges):
        for f in edges[i+1:]:
            if e['tensorId']==f['tensorId']:continue
            disjoint=not {e['source']['nodeId'],e['target']['nodeId']} & {f['source']['nodeId'],f['target']['nodeId']}
            local_cross=set();coincident=[]
            for a,b in zip(e['points'],e['points'][1:]):
                for c,d in zip(f['points'],f['points'][1:]):
                    q=segment_cross(a,b,c,d)
                    if q:local_cross.add(q)
                    shared=overlap(a,b,c,d)
                    if shared>.01:coincident.append({'firstSegment':[a,b],'secondSegment':[c,d],'length':shared})
            for q in sorted(local_cross):crosses.append({'first':e['id'],'second':f['id'],'point':q,'disjointOwners':disjoint})
            if coincident:coincidences.append({'first':e['id'],'second':f['id'],'disjointOwners':disjoint,'segmentOverlapLength':sum(x['length'] for x in coincident),'segments':coincident})
    return {'edges':len(edges),'totalBends':sum(e['bends'] for e in per_edge),'maxBends':max((e['bends'] for e in per_edge),default=0),'totalReversals':sum(e['reversals'] for e in per_edge),'distinctTensorCrossingPairPoints':len(crosses),'disjointOwnerCrossingPairPoints':sum(x['disjointOwners'] for x in crosses),'uniqueDistinctTensorCrossingLocations':len({tuple(x['point']) for x in crosses}),'distinctTensorOverlapPairs':len(coincidences),'disjointOwnerOverlapPairs':sum(x['disjointOwners'] for x in coincidences),'distinctTensorOverlapSegmentLength':sum(x['segmentOverlapLength'] for x in coincidences),'crossings':crosses,'overlaps':coincidences,'routes':per_edge}
def from_svg(svg):
    root=ET.fromstring(svg); metadata=json.loads(next(e.text for e in root if e.tag.split('}')[-1]=='metadata'))
    by_id={e['sceneEdgeId']:e for e in metadata['renderedBindings']};edges=[]
    for g in root.iter():
        if g.get('data-edge-id'):
            id=g.get('data-edge-id');p=next(e.get('d') for e in g if e.tag.split('}')[-1]=='path');edges.append({'id':id,**by_id[id],'path':p,'points':points(p)})
    return edges
assert segment_cross((0,5),(20,5),(10,0),(10,10))==(10,5)
assert segment_cross((0,5),(20,5),(20,0),(20,10)) is None
assert overlap((0,5),(20,5),(10,5),(25,5))==10
assert overlap((0,5),(20,5),(20,5),(25,5))==0
assert compact([(0,0),(0,0),(0,10),(0,20),(5,20)])==[(0,0),(0,20),(5,20)]
cases=[]
for p in sorted((ROOT/'docs/evidence/visual-golds-routing-visible').glob('*paper-180.scene.json')):
    d=json.loads(p.read_text());edges=[{**e,'points':points(e['path'])} for e in d['edges']];cases.append({'scope':'frozen-source-cpu','caseId':p.stem,'input':str(p.relative_to(ROOT)),'inputSha256':hashlib.sha256(p.read_bytes()).hexdigest(),**edge_stats(edges)})
browser_dir=ROOT/'docs/evidence/m4-ai-usability-next/current-browser-visible'
for case in ['transformer-l1','transformer-l2-preff','transformer-l3-fit','cnn-l2-fit']+[f'{direction}-{phase}' for direction in ['left','right','up','down'] for phase in ['before','moved','undo','redo','restored']]:
    p=browser_dir/f'{case}.json'
    if not p.exists():continue
    d=json.loads(p.read_text());cases.append({'scope':'actual-public-browser-artifact','caseId':case,'input':str(p.relative_to(ROOT)),'inputSha256':hashlib.sha256(p.read_bytes()).hexdigest(),**edge_stats(from_svg(d['dom']['svg']))})
result={'schemaVersion':1,'scope':'Independent geometric readability diagnostics; pair-point and overlap counts are not aesthetic, browser performance, human or publication acceptance. No browser operations.', 'cases':cases}
(OUT/'metrics.json').write_text(json.dumps(result,indent=2)+'\n')
for c in cases:print(c['caseId'],{k:c[k] for k in ['edges','totalBends','maxBends','totalReversals','distinctTensorCrossingPairPoints','disjointOwnerCrossingPairPoints','distinctTensorOverlapPairs','disjointOwnerOverlapPairs']})
