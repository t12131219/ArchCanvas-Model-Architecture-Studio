import json, copy, pathlib, math, hashlib, time
import metrics as oracle
ROOT=oracle.ROOT;OUT=oracle.OUT
def body_hit(a,b,box):
    x,y,w,h=box['x'],box['y'],box['width'],box['height'];m=.02
    if a[0]==b[0]:return x+m<a[0]<x+w-m and max(min(a[1],b[1]),y+m)<min(max(a[1],b[1]),y+h-m)
    return y+m<a[1]<y+h-m and max(min(a[0],b[0]),x+m)<min(max(a[0],b[0]),x+w-m)
def geometry_scene(scene):return [{**e,'points':oracle.compact(oracle.points(e['path']))} for e in scene['edges']]
def conflict(edge,candidate,others):
    crossing=overlap_pairs=0;overlap_length=0
    for other in others:
        if edge['id']==other['id'] or edge['tensorId']==other['tensorId']:continue
        # Distinct tensors sharing an owner can still obscure one another. Only
        # identical tensor streams are allowed to share a geometric trunk here.
        cross=set();length=0
        for a,b in zip(candidate,candidate[1:]):
            for c,d in zip(other['points'],other['points'][1:]):
                p=oracle.segment_cross(a,b,c,d)
                if p:cross.add(p)
                length+=oracle.overlap(a,b,c,d)
        crossing+=len(cross);overlap_pairs+=length>.02;overlap_length+=length
    return crossing,overlap_pairs,overlap_length
def path(ps):return ' '.join((f'M {x:g} {y:g}' if i==0 else f'V {y:g}' if x==ps[i-1][0] else f'H {x:g}') for i,(x,y) in enumerate(ps))
def plan(scene):
    nodes={n['id']:n for n in scene['nodes']};edges=geometry_scene(scene);before=oracle.edge_stats(edges)
    def ancestors(id):
        result=set();parent=nodes[id].get('parentId')
        while parent and parent not in result:result.add(parent);parent=nodes.get(parent,{}).get('parentId')
        return result
    changes=[];began=time.monotonic()
    # Keep authored/canonical order. No global layout mutation or hidden cache.
    for passnum in range(2):
        for edge in edges:
            original=edge['points'];source,target=edge['sourceId'],edge['targetId'];related=ancestors(source)|ancestors(target)
            obstacles=[n for n in nodes.values() if n['id'] not in related]
            obstacles+=[{**nodes[id],'height':nodes[id]['headerHeight']} for id in related if id not in [source,target] and nodes[id]['expanded']]
            if any(body_hit(a,b,n) for a,b in zip(original,original[1:]) for n in obstacles):continue
            initial=conflict(edge,original,edges)
            if initial[0]==initial[1]==0:continue
            start,end=original[0],original[-1]
            sa,sb=original[0],original[1];ta,tb=original[-1],original[-2]
            sdir=(0 if sb[0]==sa[0] else (1 if sb[0]>sa[0] else -1),0 if sb[1]==sa[1] else (1 if sb[1]>sa[1] else -1))
            tdir=(0 if tb[0]==ta[0] else (1 if tb[0]>ta[0] else -1),0 if tb[1]==ta[1] else (1 if tb[1]>ta[1] else -1))
            best=original;bestscore=None;bestmetric=initial
            def score(ps):
                metric=conflict(edge,ps,edges);length=sum(abs(a[0]-b[0])+abs(a[1]-b[1]) for a,b in zip(ps,ps[1:]));bends=len(ps)-2
                # Never increase crossing or overlap-pair counts for the target
                # edge. Then shorten remaining coincidences and the route.
                if metric[0]>initial[0] or metric[1]>initial[1]:return None,metric
                return (metric[0]+metric[1],metric[2],length+bends*18),metric
            bestscore,_=score(original)
            xs=sorted({round(v,2) for n in scene['nodes'] for v in [n['x']-6,n['x']-14,n['x']-22,n['x']+n['width']+6,n['x']+n['width']+14,n['x']+n['width']+22]}|{p[0]+delta for p in original for delta in [-16,-8,0,8,16]})
            ys=sorted({round(v,2) for n in scene['nodes'] for v in [n['y']-6,n['y']-14,n['y']+n['height']+6,n['y']+n['height']+14]}|{p[1]+delta for p in original for delta in [-16,-8,0,8,16]})
            for lead in [6,14,22]:
                a=(start[0]+sdir[0]*lead,start[1]+sdir[1]*lead);b=(end[0]+tdir[0]*lead,end[1]+tdir[1]*lead)
                candidates=[[start,a,(b[0],a[1]),b,end],[start,a,(a[0],b[1]),b,end]]
                candidates.extend([start,a,(x,a[1]),(x,b[1]),b,end] for x in xs)
                candidates.extend([start,a,(a[0],y),(b[0],y),b,end] for y in ys)
                for ps in candidates:
                    ps=oracle.compact(ps)
                    if any((v[0]-u[0])*(w[0]-v[0])+(v[1]-u[1])*(w[1]-v[1])<0 for u,v,w in zip(ps,ps[1:],ps[2:])):continue
                    if ((ps[1][0]-ps[0][0])*sdir[0]+(ps[1][1]-ps[0][1])*sdir[1]<=0 or
                        (ps[-2][0]-ps[-1][0])*tdir[0]+(ps[-2][1]-ps[-1][1])*tdir[1]<=0):continue
                    if any(body_hit(u,v,n) for u,v in zip(ps,ps[1:]) for n in obstacles):continue
                    candidate_score,metric=score(ps)
                    if candidate_score is not None and candidate_score<bestscore:best,bestscore,bestmetric=ps,candidate_score,metric
            if best!=original:
                changes.append({'pass':passnum,'edgeId':edge['id'],'oldPath':edge['path'],'newPath':path(best),'oldConflict':initial,'newConflict':bestmetric})
                edge['points']=best;edge['path']=path(best)
    after=oracle.edge_stats(edges)
    assert after['distinctTensorCrossingPairPoints']<=before['distinctTensorCrossingPairPoints']
    assert after['distinctTensorOverlapPairs']<=before['distinctTensorOverlapPairs']
    assert after['totalReversals']==0
    for original,modified in zip(geometry_scene(scene),edges):assert original['points'][0]==modified['points'][0] and original['points'][-1]==modified['points'][-1]
    return {'before':before,'after':after,'changes':changes,'elapsedSeconds':time.monotonic()-began,'endpointAnchorsPreserved':True,'newBodyHeaderPenetrations':0,'uTurns':0}
results=[]
for case in ['transformer-level0-paper-180','transformer-level1-paper-180','transformer-level2-paper-180','transformer-level3-paper-180']:
    p=ROOT/'docs/evidence/visual-golds-routing-visible'/f'{case}.scene.json';scene=json.loads(p.read_text())
    result=plan(scene);results.append({'caseId':case,'input':str(p.relative_to(ROOT)),'inputSha256':hashlib.sha256(p.read_bytes()).hexdigest(),**result})
    print('EXPERIMENT',case,'time',round(result['elapsedSeconds'],2),'changes',len(result['changes']))
    for phase in ['before','after']:print(phase,{k:result[phase][k] for k in ['totalBends','distinctTensorCrossingPairPoints','disjointOwnerCrossingPairPoints','distinctTensorOverlapPairs','disjointOwnerOverlapPairs','distinctTensorOverlapSegmentLength']})
(OUT/'experiment.json').write_text(json.dumps({'schemaVersion':1,'scope':'Unpromoted independent Python candidate path experiment only. No product/core/build/browser mutation; not performance or aesthetic acceptance. Collision-free single-corridor candidates evaluated even when original body route clear. No added crossing/overlap pair count per edge permitted.','cases':results},indent=2)+'\n')
