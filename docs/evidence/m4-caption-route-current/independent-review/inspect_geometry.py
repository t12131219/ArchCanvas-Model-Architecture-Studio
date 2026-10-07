#!/usr/bin/env python3
"""Independent stdlib oracle. Does not import product or earlier geometry helpers.

A caption rectangle is an intentionally nominal text envelope, not a font or
pixel measurement. Segment sets are derived independently from saved outputs.
"""
import json, math, re, sys, hashlib
from pathlib import Path
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
TOL = 1e-7

def points(path):
    tokens = re.findall(r'[MLHV]|[-+]?(?:\d*\.\d+|\d+\.?\d*)(?:[eE][-+]?\d+)?', path)
    if re.sub(r'[MLHV]|[-+]?(?:\d*\.\d+|\d+\.?\d*)(?:[eE][-+]?\d+)?|[\s,]+', '', path):
        raise ValueError('unsupported path syntax')
    out = []; i = 0
    while i < len(tokens):
        command = tokens[i]; i += 1
        if command in ('M','L'):
            p=(float(tokens[i]),float(tokens[i+1])); i+=2
        elif command=='H' and out:
            p=(float(tokens[i]),out[-1][1]); i+=1
        elif command=='V' and out:
            p=(out[-1][0],float(tokens[i])); i+=1
        else: raise ValueError('missing command or initial moveto')
        if not all(map(math.isfinite,p)): raise ValueError('nonfinite')
        if out and p[0]!=out[-1][0] and p[1]!=out[-1][1]: raise ValueError('diagonal')
        if not out or p!=out[-1]: out.append(p)
    if len(out)<2: raise ValueError('empty route')
    return out

def segments(poly): return list(zip(poly,poly[1:]))
def key(p): return tuple(round(v,6) for v in p)
def equal(a,b): return math.dist(a,b)<TOL
def direction(a,b): return tuple(0 if abs(y-x)<TOL else (1 if y>x else -1) for x,y in zip(a,b))
def length(poly): return sum(abs(a[0]-b[0])+abs(a[1]-b[1]) for a,b in segments(poly))
def bends(poly): return sum(direction(a,b)!=direction(b,c) for a,b,c in zip(poly,poly[1:],poly[2:]))
def contains(p,a,b,strict=False):
    if a[0]==b[0]:
        return abs(p[0]-a[0])<TOL and (min(a[1],b[1])+TOL<p[1]<max(a[1],b[1])-TOL if strict else min(a[1],b[1])-TOL<=p[1]<=max(a[1],b[1])+TOL)
    return abs(p[1]-a[1])<TOL and (min(a[0],b[0])+TOL<p[0]<max(a[0],b[0])-TOL if strict else min(a[0],b[0])-TOL<=p[0]<=max(a[0],b[0])+TOL)

def incident(poly,p):
    rays=set()
    for a,b in segments(poly):
        if contains(p,a,b):
            if not equal(p,a): rays.add(direction(p,a))
            if not equal(p,b): rays.add(direction(p,b))
    return rays

def pair(first,second):
    contacts=set(); intervals={}
    for a,b in segments(first):
        for c,d in segments(second):
            vertical=a[0]==b[0]; other=c[0]==d[0]
            if vertical!=other:
                p=(a[0],c[1]) if vertical else (c[0],a[1])
                if contains(p,a,b) and contains(p,c,d): contacts.add(key(p))
            elif (abs(a[0]-c[0]) if vertical else abs(a[1]-c[1]))<TOL:
                axis=1 if vertical else 0
                lo=max(min(a[axis],b[axis]),min(c[axis],d[axis])); hi=min(max(a[axis],b[axis]),max(c[axis],d[axis]))
                if hi>lo+TOL: intervals.setdefault((vertical,round(a[1-axis],6)),[]).append((lo,hi))
                elif hi>=lo-TOL: contacts.add(key((a[0],lo) if vertical else (lo,a[1])))
    unions={}
    for axis,ranges in intervals.items():
        merged=[]
        for lo,hi in sorted(ranges):
            if merged and lo<=merged[-1][1]+TOL: merged[-1][1]=max(merged[-1][1],hi)
            else: merged.append([lo,hi])
        unions[axis]=merged
    crosses=set()
    horiz={(-1,0),(1,0)}; vert={(0,-1),(0,1)}
    for p in contacts:
        x=incident(first,p); y=incident(second,p)
        if (horiz<=x and vert<=y) or (vert<=x and horiz<=y): crosses.add(p)
    return {'contacts':contacts,'crossings':crosses,'overlaps':unions}

def occupied(p,geometry):
    if p in geometry['contacts']: return True
    return any(abs((p[0] if vertical else p[1])-coordinate)<TOL and any(lo-TOL<=(p[1] if vertical else p[0])<=hi+TOL for lo,hi in ranges)
               for (vertical,coordinate),ranges in geometry['overlaps'].items())

def introduced(after,before):
    result=[]
    for p in after['contacts']:
        if not occupied(p,before): result.append({'kind':'contact','point':p})
    for p in after['crossings']-before['crossings']: result.append({'kind':'proper-crossing','point':p})
    for axis,ranges in after['overlaps'].items():
        for lo,hi in ranges:
            if not any(a<=lo+TOL and b>=hi-TOL for a,b in before['overlaps'].get(axis,[])):
                result.append({'kind':'overlap','axis':axis,'interval':[lo,hi]})
    return result

def rect(raw,pad=0): return (raw['x']-pad,raw['y']-pad,raw['x']+raw['width']+pad,raw['y']+raw['height']+pad)
def caption(edge,pad=0): return (edge['labelX']-2-pad,edge['labelY']-11-pad,edge['labelX']+len(edge['label'])*9+2+pad,edge['labelY']+5+pad)
def penetrates(poly,box):
    l,t,r,b=box
    for a,z in segments(poly):
        if a[0]==z[0] and l+TOL<a[0]<r-TOL and max(min(a[1],z[1]),t+TOL)<min(max(a[1],z[1]),b-TOL): return True
        if a[1]==z[1] and t+TOL<a[1]<b-TOL and max(min(a[0],z[0]),l+TOL)<min(max(a[0],z[0]),r-TOL): return True
    return False

def body_rects(scene,pad=0):
    out=[]
    for node in scene['nodes']:
        if node['expanded']:
            outline=dict(node,height=node['headerHeight']); out.append((node['id'],rect(outline,pad)))
        else:
            out.append((node['id'],rect(node,pad)))
            if node.get('repeat'):
                for offset in (3.5,7): out.append((node['id']+':repeat'+str(offset),rect(dict(node,x=node['x']+offset,y=node['y']+offset),pad)))
    out.extend((a['id'],rect(a,pad)) for a in scene.get('annotations',[]))
    return out

def gap(poly,box):
    l,t,r,b=box
    return min(math.hypot(max(l-max(a[0],z[0]),min(a[0],z[0])-r,0),max(t-max(a[1],z[1]),min(a[1],z[1])-b,0)) for a,z in segments(poly))

def geometry(scene,old=None,svg=None):
    failures=[]; notices=[]; stats={'edges':len(scene['edges']),'guides':len(scene.get('captionGuides',[])),'pairs':0,'changedRoutes':0,'savedLength':0,'savedBends':0,'unresolvedCaptions':0}
    routes={e['id']:points(e['path']) for e in scene['edges']}; edges={e['id']:e for e in scene['edges']}
    oldRoutes={e['id']:points(e['path']) for e in old['edges']} if old else {}
    bodies=body_rects(scene); captions={e['id']:caption(e) for e in scene['edges'] if e.get('label')}
    guideByEdge={g['sceneEdgeId']:g for g in scene.get('captionGuides',[])}
    warnings={d.get('edgeId') for d in scene['diagnostics'] if d.get('code') in ('layout-edge-label-blocked','layout-edge-label-association')}
    for eid,new in routes.items():
        if not old: continue
        previous=oldRoutes[eid]
        if new!=previous:
            stats['changedRoutes']+=1; stats['savedLength']+=length(previous)-length(new); stats['savedBends']+=bends(previous)-bends(new)
            if not equal(previous[0],new[0]) or not equal(previous[-1],new[-1]): failures.append({'edge':eid,'kind':'endpoint-changed'})
            if direction(previous[0],previous[1])!=direction(new[0],new[1]) or direction(previous[-1],previous[-2])!=direction(new[-1],new[-2]): failures.append({'edge':eid,'kind':'endpoint-direction-changed'})
            if math.dist(new[0],new[1])+TOL<min(6,math.dist(previous[0],previous[1])) or math.dist(new[-1],new[-2])+TOL<min(6,math.dist(previous[-1],previous[-2])): failures.append({'edge':eid,'kind':'endpoint-lead-shortened-below-contract'})
            if length(new)>length(previous)+.01 or bends(new)>bends(previous): failures.append({'edge':eid,'kind':'shortcut-cost-increased'})
            for bid,box in bodies:
                if penetrates(new,box) and not penetrates(previous,box): failures.append({'edge':eid,'body':bid,'kind':'new-body-incursion'})
        for otherid,other in routes.items():
            if eid>=otherid: continue
            stats['pairs']+=1
            if new==previous and other==oldRoutes[otherid]: continue
            for introducedItem in introduced(pair(new,other),pair(previous,oldRoutes[otherid])):
                failures.append({'edges':[eid,otherid],**introducedItem})
    for eid,box in captions.items():
        if penetrates(routes[eid],box):
            if eid not in warnings: failures.append({'edge':eid,'kind':'caption-on-owned-route-without-warning'})
        ownGap=gap(routes[eid],box)
        if ownGap>18+TOL and eid not in guideByEdge:
            if eid not in warnings: failures.append({'edge':eid,'kind':'unassociated-caption-without-warning','gap':ownGap})
            else: stats['unresolvedCaptions']+=1; notices.append({'edge':eid,'kind':'diagnosed-unassociated-caption','gap':ownGap})
    guidePaths={g['id']:points(g['path']) for g in scene.get('captionGuides',[])}
    for g in scene.get('captionGuides',[]):
        gid=g['id']; owner=g['sceneEdgeId']; p=guidePaths[gid]; box=captions.get(owner)
        if owner not in routes or box is None: failures.append({'guide':gid,'kind':'unknown-caption-owner'}); continue
        if len(p)!=2 or length(p)>48+TOL or length(p)<=TOL: failures.append({'guide':gid,'kind':'invalid-guide-length','length':length(p)})
        if g['kind']!='caption-guide' or abs(g['width']-.8)>TOL: failures.append({'guide':gid,'kind':'guide-contract'})
        if not any(contains(p[0],a,b,True) for a,b in segments(routes[owner])) or equal(p[0],routes[owner][0]) or equal(p[0],routes[owner][-1]): failures.append({'guide':gid,'kind':'noninterior-owner-attachment'})
        ownedContact=pair(p,routes[owner])
        if ownedContact['contacts']!={key(p[0])} or ownedContact['overlaps']: failures.append({'guide':gid,'kind':'guide-owner-extra-contact'})
        if gid in edges or any(n['id']==gid for n in scene['nodes']) or any(a['id']==gid for a in scene.get('annotations',[])): failures.append({'guide':gid,'kind':'guide-identity-collision'})
        l,t,r,b=box; finish=p[-1]
        if not ((abs(finish[0]-l)<TOL or abs(finish[0]-r)<TOL) and t-TOL<=finish[1]<=b+TOL or (abs(finish[1]-t)<TOL or abs(finish[1]-b)<TOL) and l-TOL<=finish[0]<=r+TOL): failures.append({'guide':gid,'kind':'guide-not-on-caption-boundary'})
        for bid,body in body_rects(scene,g['width']/2):
            if penetrates(p,body): failures.append({'guide':gid,'body':bid,'kind':'guide-body-collision'})
        for eid,e in edges.items():
            if eid!=owner and pair(p,routes[eid])['contacts']: failures.append({'guide':gid,'edge':eid,'kind':'guide-unrelated-route-contact'})
            if eid!=owner and pair(p,routes[eid])['overlaps']: failures.append({'guide':gid,'edge':eid,'kind':'guide-unrelated-route-overlap'})
            if eid!=owner and e.get('label') and penetrates(p,caption(e,g['width']/2)): failures.append({'guide':gid,'edge':eid,'kind':'guide-unrelated-caption-collision'})
        for oid,other in guidePaths.items():
            if oid>gid and (pair(p,other)['contacts'] or pair(p,other)['overlaps']): failures.append({'guide':gid,'otherGuide':oid,'kind':'guide-guide-contact'})
        for point in p:
            bd=scene['bounds']
            if not bd['x']-TOL<=point[0]<=bd['x']+bd['width']+TOL or not bd['y']-TOL<=point[1]<=bd['y']+bd['height']+TOL: failures.append({'guide':gid,'kind':'guide-outside-scene'})
    if svg:
        tree=ET.fromstring(svg)
        decorated=[p for p in tree.iter() if p.attrib.get('data-caption-guide-id')]
        if len(decorated)!=len(guidePaths): failures.append({'kind':'svg-guide-count'})
        for element in decorated:
            if any(k.startswith('marker') or k in ('data-edge-id','data-tensor-id') for k in element.attrib): failures.append({'kind':'svg-guide-canonical-or-arrowed','guide':element.attrib})
        metadata=json.loads(next(p.text for p in tree.iter() if p.tag.endswith('metadata')))
        for binding in metadata.get('renderedBindings',[]):
            if binding.get('sceneEdgeId',binding.get('id')) in guidePaths: failures.append({'kind':'guide-in-canonical-metadata'})
        decorations=metadata.get('presentationDecorations',[])
        if len(decorations)!=len(guidePaths): failures.append({'kind':'svg-guide-metadata-count'})
    return {'stats':stats,'failures':failures,'notices':notices}

def main():
    tag=sys.argv[1] if len(sys.argv)>1 else 'attempt-1'; directory=HERE/tag
    capture=json.loads((directory/'capture.json').read_text()); results=[]
    for item in capture['records']:
        stem=item['stem']; old=json.loads((directory/(stem+'.old.scene.json')).read_text()); new=json.loads((directory/(stem+'.new.scene.json')).read_text())
        result=geometry(new,old,(directory/(stem+'.new.svg')).read_text()); result.update(stem=stem,input=item['input'],scope=item['nodeId']); results.append(result)
    totals={name:sum(r['stats'][name] for r in results) for name in results[0]['stats']}
    failed=[{'stem':r['stem'],**f} for r in results for f in r['failures']]
    report={'schema':'archcanvas-independent-nominal-geometry/1','tag':tag,'sourceDocuments':capture['inputs'],'captures':len(results),'totals':totals,
        'semanticFailures':capture['failedInvariants'],'geometryFailures':failed,'results':results,'limits':['AI simulated, no human study','nominal geometry; no resolved fonts, pixels or physical approval','work caps are not wall-clock or FPS proof','source models never executed']}
    (directory/'geometry-report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'tag':tag,'captures':len(results),'totals':totals,'semanticFailures':len(report['semanticFailures']),'geometryFailures':len(failed),'firstFailures':failed[:8]}))

if __name__=='__main__': main()
