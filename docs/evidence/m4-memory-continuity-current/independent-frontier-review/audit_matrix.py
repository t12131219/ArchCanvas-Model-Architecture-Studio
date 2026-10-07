"""Independent public-scene audit; no product geometry imports or execution."""
from __future__ import annotations
import hashlib,json,math,re,sys
from collections import Counter
from datetime import datetime,timezone
from pathlib import Path
sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
EPS=1e-7

def binding(p):
    b=p.read_bytes();return {'path':str(p.relative_to(ROOT)),'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}
def read(p):return json.loads(p.read_text())
def exact(a,b):return a==b
def points(value):
    tokens=re.findall(r'[A-Za-z]|[-+]?(?:\d*\.\d+|\d+\.?\d*)(?:[eE][-+]?\d+)?',value)
    assert ''.join(tokens)==re.sub(r'\s+','',value)
    result=[];i=0
    while i<len(tokens):
        c=tokens[i];i+=1
        if c in ['M','L']:point=(float(tokens[i]),float(tokens[i+1]));i+=2
        elif c=='H':point=(float(tokens[i]),result[-1][1]);i+=1
        elif c=='V':point=(result[-1][0],float(tokens[i]));i+=1
        else:raise ValueError(c)
        assert all(math.isfinite(x) for x in point)
        assert not result or point[0]==result[-1][0] or point[1]==result[-1][1]
        if not result or point!=result[-1]:result.append(point)
    assert len(result)>=2
    return result
def length(p):return sum(abs(a[0]-b[0])+abs(a[1]-b[1]) for a,b in zip(p,p[1:]))
def round2(v):return math.floor(v*100+.5)/100
def rects(n):
    shifts=[0,3.5,7] if n.get('repeat') and not n['expanded'] else [0]
    return [(n['x']+s,n['y']+s,n['x']+n['width']+s,n['y']+n['height']+s) for s in shifts]
def side(n,right):
    y=n['y']+n['height']*.55;at=[r for r in rects(n) if r[1]<=y<=r[3]]
    return ((max(r[2] for r in at) if right else min(r[0] for r in at)),y)
def dist(a,b,c,d):
    dx=max(min(a[0],b[0])-max(c[0],d[0]),min(c[0],d[0])-max(a[0],b[0]),0)
    dy=max(min(a[1],b[1])-max(c[1],d[1]),min(c[1],d[1])-max(a[1],b[1]),0)
    return math.hypot(dx,dy)
def enters(a,b,r):
    l,t,x,y=r
    return a[0]>l+EPS and a[0]<x-EPS and max(min(a[1],b[1]),t)<min(max(a[1],b[1]),y)-EPS if a[0]==b[0] else a[1]>t+EPS and a[1]<y-EPS and max(min(a[0],b[0]),l)<min(max(a[0],b[0]),x)-EPS
def pair(a,b,self_check=False):
    contacts=set();spans=[]
    for i,(s,t) in enumerate(zip(a,a[1:])):
        for j,(u,v) in enumerate(zip(b,b[1:])):
            if self_check and j<i+2:continue
            av=s[0]==t[0];bv=u[0]==v[0]
            if av!=bv:
                c,d,e,f=(s,t,u,v) if av else (u,v,s,t)
                if min(e[0],f[0])-EPS<=c[0]<=max(e[0],f[0])+EPS and min(c[1],d[1])-EPS<=e[1]<=max(c[1],d[1])+EPS:contacts.add((c[0],e[1]))
            elif abs((s[0] if av else s[1])-(u[0] if bv else u[1]))<=EPS:
                axis=1 if av else 0;low=max(min(s[axis],t[axis]),min(u[axis],v[axis]));high=min(max(s[axis],t[axis]),max(u[axis],v[axis]))
                if high<low-EPS:continue
                if high<=low+EPS:contacts.add((s[0],low) if av else (low,s[1]))
                else:spans.append(('v' if av else 'h',s[1-axis],low,high))
    return contacts,spans
def subset(after,before):
    c,spans=after;oldc,oldsp=before
    if not c.issubset(oldc):return False
    for axis,pos,l,h in spans:
        cover=l
        for a,b in sorted((a,b) for direction,where,a,b in oldsp if direction==axis and abs(where-pos)<=EPS):
            if a>cover+EPS:break
            cover=max(cover,b)
        if cover<h-EPS:return False
    return True
def strip(d,*keys):return {k:v for k,v in d.items() if k not in keys}
def main():
    attempt=sys.argv[1] if len(sys.argv)>1 else ''
    if not re.fullmatch(r'audit-attempt-[1-9][0-9]*',attempt):raise ValueError('append-only audit-attempt-N required')
    output=HERE/attempt;assert not output.exists();output.mkdir()
    capture_path=HERE/'capture-attempt-1/capture.json';capture=read(capture_path)
    input_rows=[binding(capture_path),binding(Path(__file__).resolve())]
    checks=[];rows=[]
    def check(case,name,actual,expected=True):checks.append({'case':case,'name':name,'actual':actual,'expected':expected,'passed':exact(actual,expected)})
    for b in capture['inputBindings']:
        current=binding(ROOT/b['path']);input_rows.append(current);check('provenance',b['path'],current,b)
    for record in capture['rows']:
        key=record['key']
        for field in ['documentBinding','beforeBinding','currentBinding']:
            b=record[field];actual=binding(ROOT/b['path']);input_rows.append(actual);check(key,f'{field}-hash',actual,b)
        document=read(ROOT/record['documentBinding']['path']);before=read(ROOT/record['beforeBinding']['path']);scene=read(ROOT/record['currentBinding']['path'])
        check(key,'input-document-immutable',record['inputUnchanged']);check(key,'detached-rebuild-deterministic',record['detachedDeterministic'])
        arch={e['id']:e for e in document['architecture']['edges']};arch_index={e['id']:i for i,e in enumerate(document['architecture']['edges'])}
        oldedges={e['id']:e for e in before['edges']};nodes={n['id']:n for n in scene['nodes']};oldnodes={n['id']:n for n in before['nodes']}
        check(key,'node-identities-order',[n['id'] for n in scene['nodes']],[n['id'] for n in before['nodes']]);check(key,'edge-identities-order',[e['id'] for e in scene['edges']],[e['id'] for e in before['edges']])
        for field in ['documentId','revision','title','sourceDigest','irDigest','sourceFacts','hiddenEdges','pageSpec','exportScope','legend','annotations']:
            check(key,f'protected-{field}',scene.get(field),before.get(field))
        memory_ports={};accepted=[];retained=[];expanded_memory=[]
        def memory_port(p):return p['canonicalEdgeIds'] and all(arch[eid]['role']=='memory' for eid in p['canonicalEdgeIds'])
        for edge in scene['edges']:
            old=oldedges[edge['id']];check(key,f'{edge["id"]}-canonical-style',strip(edge,'path','labelX','labelY'),strip(old,'path','labelX','labelY'))
            parsed=points(edge['path']);original=points(old['path'])
            if edge['role']!='memory':check(key,f'{edge["id"]}-nonmemory-path',edge['path'],old['path']);continue
            source=nodes[edge['sourceId']];target=nodes[edge['targetId']];changed=edge['path']!=old['path'];expected_label={'default':'memory','empty':'','custom':'独立 memory 说明'}[record['caption']]
            check(key,f'{edge["id"]}-caption-rule',edge['label'],expected_label)
            if source['expanded'] or target['expanded']:expanded_memory.append(edge['id']);check(key,f'{edge["id"]}-expanded-endpoint-retained',changed,False)
            if changed:
                accepted.append(edge['id']);a=tuple(round2(x) for x in side(source,True));b=tuple(round2(x) for x in side(target,False));lane=round2((a[0]+b[0])/2)
                expected=[a,b] if a[1]==b[1] else [a,(lane,a[1]),(lane,b[1]),b]
                check(key,f'{edge["id"]}-collapsed-endpoints',[source['expanded'],target['expanded']],[False,False]);check(key,f'{edge["id"]}-derived-midpoint-path',parsed,expected)
                check(key,f'{edge["id"]}-rounded-two-leads',min(lane-a[0],b[0]-lane)>=6-EPS)
                check(key,f'{edge["id"]}-shared-band',min(max(r[3] for r in rects(source)),max(r[3] for r in rects(target)))>max(source['y'],target['y'])+EPS)
                check(key,f'{edge["id"]}-length-no-increase',length(parsed)<=length(original)+EPS)
                sc,sp=pair(parsed,parsed,True);check(key,f'{edge["id"]}-no-nonadjacent-self-contact',not sc and not sp)
                ancestors=set()
                for endpoint in [source,target]:
                    parent=endpoint.get('parentId');seen=set()
                    while parent:
                        assert parent not in seen and parent in nodes;seen.add(parent);ancestors.add(parent);parent=nodes[parent].get('parentId')
                hits=[]
                for n in scene['nodes']:
                    boxes=[(n['x'],n['y'],n['x']+n['width'],n['y']+n['headerHeight'])] if n['id'] in ancestors and n['expanded'] else [] if n['id'] in ancestors else rects(n)
                    for segment,(p,q) in enumerate(zip(parsed,parsed[1:])):
                        terminal=n['id']==source['id'] and segment==0 or n['id']==target['id'] and segment==len(parsed)-2
                        padding=0 if terminal else max(6,edge['width']/2+(.65 if n['expanded'] else .75))
                        for l,t,r,bottom in boxes:
                            if enters(p,q,(l-padding,t-padding,r+padding,bottom+padding)):hits.append({'node':n['id'],'segment':segment})
                check(key,f'{edge["id"]}-body-header-nominal-clear',hits,[])
                for peer in before['edges']:
                    if peer['id']==edge['id']:continue
                    oldpeer=points(peer['path']);newpair=pair(parsed,oldpeer);oldpair=pair(original,oldpeer)
                    check(key,f'{edge["id"]}-fixed-peer-{peer["id"]}-contact-subset',subset(newpair,oldpair))
                    threshold=(edge['width']+peer['width'])/2
                    minimum=min(dist(a,b,c,d) for a,b in zip(parsed,parsed[1:]) for c,d in zip(oldpeer,oldpeer[1:]))
                    check(key,f'{edge["id"]}-fixed-peer-{peer["id"]}-nominal-stroke-clear',minimum>threshold+EPS)
                for peer in scene['edges']:
                    if peer['id']==edge['id']:continue
                    currentpeer=points(peer['path']);threshold=(edge['width']+peer['width'])/2
                    minimum=min(dist(a,b,c,d) for a,b in zip(parsed,parsed[1:]) for c,d in zip(currentpeer,currentpeer[1:]))
                    check(key,f'{edge["id"]}-chosen-peer-{peer["id"]}-nominal-stroke-clear',minimum>threshold+EPS)
            else:retained.append(edge['id'])
            for direction in ['out','in']:
                owner=source if direction=='out' else target;oldowner=oldnodes[owner['id']];endpoint=original[0] if direction=='out' else original[-1]
                templates=[p for p in oldowner['ports'] if p['direction']==direction and all(eid in p['canonicalEdgeIds'] for eid in old['canonicalEdgeIds']) and abs(p['x']-endpoint[0])<=.051 and abs(p['y']-endpoint[1])<=.051]
                check(key,f'{edge["id"]}-{direction}-prior-public-port-exists',len(templates)>0)
                if not templates:continue
                template=templates[0];side_name='right' if direction=='out' else 'left';port_id=f'{template["canonicalNodeId"]}:{template["canonicalPortId"]}:memory:{side_name}' if changed else template['id'];groups=memory_ports.setdefault(owner['id'],{})
                if port_id not in groups:
                    groups[port_id]={**template,'id':port_id,'canonicalEdgeIds':[],'canonicalBindings':[]}
                    if changed:groups[port_id].update(dict(zip(['x','y'],side(owner,direction=='out'))))
                group=groups[port_id]
                for eid in edge['canonicalEdgeIds']:
                    if eid not in group['canonicalEdgeIds']:group['canonicalEdgeIds'].append(eid)
                ordered=sorted(group['canonicalEdgeIds'],key=arch_index.__getitem__);group['canonicalBindings']=[arch[eid]['source' if direction=='out' else 'target'] for eid in ordered]
        for n in scene['nodes']:
            old=oldnodes[n['id']];check(key,f'{n["id"]}-protected-body-facts',strip(n,'ports'),strip(old,'ports'))
            check(key,f'{n["id"]}-nonmemory-port-array-exact',[p for p in n['ports'] if not memory_port(p)],[p for p in old['ports'] if not memory_port(p)])
            actual={p['id']:p for p in n['ports'] if memory_port(p)};expected=memory_ports.get(n['id'],{})
            check(key,f'{n["id"]}-memory-port-identities',sorted(actual),sorted(expected))
            for port_id in actual:check(key,f'{n["id"]}-{port_id}-chosen-coverage-geometry',actual[port_id],expected.get(port_id))
        facts=scene['sourceFacts'];multi=[{'nodeId':n['id'],'portId':p['id'],'canonicalEdges':len(p['canonicalEdgeIds'])} for n in scene['nodes'] for p in n['ports'] if len(p['canonicalEdgeIds'])>1]
        rowchecks=[c for c in checks if c['case']==key]
        rows.append({'key':key,'originalKey':record['originalKey'],'caption':record['caption'],'preset':record['preset'],'widthMm':record['widthMm'],'scope':record['scope'],'relations':len(rowchecks),'passed':sum(c['passed'] for c in rowchecks),
          'acceptedMemoryEdges':accepted,'retainedMemoryEdges':retained,'expandedEndpointMemoryEdges':expanded_memory,
          'repeatVisible':sum(bool(n.get('repeat')) for n in scene['nodes']),'repeatFacts':sum(bool(f.get('repeat')) for f in facts),
          'opaqueVisible':sum(n['evidence']=='opaque' for n in scene['nodes']),'opaqueFacts':sum(f['evidence']=='opaque' for f in facts),
          'sharedCallFacts':sum(f.get('callCount',0)>1 for f in facts),'multipleConsumers':multi})
    before_bindings=list(input_rows);after=[binding(ROOT/b['path']) for b in before_bindings]
    for b,a in zip(before_bindings,after):check('final-provenance',b['path'],a,b)
    report={'schema':'archcanvas-independent-nine-frontier-memory-audit/1','createdUtc':datetime.now(timezone.utc).isoformat(),'cases':len(rows),'relations':len(checks),'passed':sum(c['passed'] for c in checks),'failures':[c for c in checks if not c['passed']],
      'acceptedRouteOccurrences':sum(len(r['acceptedMemoryEdges']) for r in rows),'retainedMemoryOccurrences':sum(len(r['retainedMemoryEdges']) for r in rows),'expandedEndpointRetainedOccurrences':sum(len(r['expandedEndpointMemoryEdges']) for r in rows),
      'acceptedSceneCases':sum(bool(r['acceptedMemoryEdges']) for r in rows),'repeatSceneCases':sum(r['repeatVisible']>0 for r in rows),'opaqueSceneCases':sum(r['opaqueVisible']>0 for r in rows),'sharedCallSceneCases':sum(r['sharedCallFacts']>0 for r in rows),'multipleConsumerSceneCases':sum(bool(r['multipleConsumers']) for r in rows),
      'inputBindings':before_bindings,'inputsAfter':after,'inputsUnchanged':before_bindings==after,'rows':rows,'checks':checks,
      'scope':'216 presentation cases over nine actual source-bound frozen Canvas frontiers, current formal core versus immediate-before formal core. Independent nominal centreline/rectangular/stroke geometry and canonical facts/ports; nonmemory routes exact. No new source analysis/model execution, browser/pixels, font/arrowhead geometry, global aesthetics, physical publication, presented performance or human tasks.'}
    (output/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:report[k] for k in ['cases','relations','passed','acceptedRouteOccurrences','retainedMemoryOccurrences','expandedEndpointRetainedOccurrences','acceptedSceneCases','repeatSceneCases','opaqueSceneCases','sharedCallSceneCases','multipleConsumerSceneCases','inputsUnchanged']}))
    print(json.dumps({'failures':report['failures'][:30],'failureCount':len(report['failures'])},ensure_ascii=False))
if __name__=='__main__':main()
