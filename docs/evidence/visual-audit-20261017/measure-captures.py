"""Measure the captured DOM SVGs, not screenshots or export files.
Crossings count orthogonal proper segment intersections between distinct wires.
Coincident/collinear segments are reported separately and need semantic review.
"""
from pathlib import Path
import json,re,math,hashlib,xml.etree.ElementTree as ET
from collections import defaultdict
root=Path(__file__).parent
num=r'[-+]?(?:\d*\.\d+|\d+)(?:e[-+]?\d+)?'
def points(d):
    return [tuple(map(float,p)) for p in re.findall(r'[ML]\s*('+num+r')[ ,]+('+num+')',d or '',re.I)]
def length(ps):return sum(math.dist(a,b) for a,b in zip(ps,ps[1:]))
def segs(ps):return list(zip(ps,ps[1:]))
def horizontal(s):return abs(s[0][1]-s[1][1])<1e-6
def vertical(s):return abs(s[0][0]-s[1][0])<1e-6
def overlap(a,b):
    if horizontal(a) and horizontal(b) and abs(a[0][1]-b[0][1])<1e-6: axis=0
    elif vertical(a) and vertical(b) and abs(a[0][0]-b[0][0])<1e-6:axis=1
    else:return 0
    return max(0,min(max(p[axis] for p in a),max(p[axis] for p in b))-max(min(p[axis] for p in a),min(p[axis] for p in b)))
rows=[]
for p in sorted(root.glob('*.svg')):
    r=ET.fromstring(p.read_text());edges=[];controls=[];nodes={}
    for g in r.iter():
        if g.get('data-edge-id'):
            wire=next((c for c in g if c.get('class')=='wire-path'),None)
            if wire is None:continue
            binding=json.loads(g.get('data-semantic-binding','{}'))
            edges.append({'id':g.get('data-edge-id'),'wire':binding.get('wire_identity',g.get('data-edge-id')),'source':g.get('data-source'),'target':g.get('data-target'),'binding':binding,'points':points(wire.get('d'))})
        if g.get('data-source-control-id'):
            route=next(c for c in g if c.tag.endswith('path'))
            ps=points(route.get('d'));turnbacks=[]
            for i in range(len(ps)-3):
                a,b,c,d=ps[i:i+4]
                if horizontal((a,b)) and horizontal((c,d)) and (b[0]-a[0])*(d[0]-c[0])<0:
                    turnbacks.append({'segment':i,'gap':abs(b[1]-c[1]),'returnLength':min(abs(b[0]-a[0]),abs(d[0]-c[0]))})
            controls.append({'id':g.get('data-source-control-id'),'points':ps,'length':length(ps),'bends':max(0,len(ps)-2),'turnbacks':turnbacks})
        if g.get('data-node-id'):nodes[g.get('data-node-id')]={'parent':g.get('data-parent'),'expanded':g.get('data-expanded')=='true'}
    crossings=0;overlaps=[]
    for i,e in enumerate(edges):
        for f in edges[i+1:]:
            if e['wire']==f['wire']:continue
            total=0
            for a in segs(e['points']):
                for b in segs(f['points']):
                    total+=overlap(a,b)
                    if vertical(a) and horizontal(b):a,b=b,a
                    if horizontal(a) and vertical(b) and min(x[0] for x in a)<b[0][0]<max(x[0] for x in a) and min(x[1] for x in b)<a[0][1]<max(x[1] for x in b):crossings+=1
            if total>1e-6:overlaps.append({'edges':[e['id'],f['id']],'length':total})
    depth=lambda n,seen=(): 0 if not nodes[n]['parent'] or nodes[n]['parent'] not in nodes or n in seen else 1+depth(nodes[n]['parent'],seen+(n,))
    rows.append({'capture':p.stem,'nodes':len(nodes),'edges':len(edges),'visibleDepth':max((depth(n) for n in nodes),default=0),'totalRouteLength':round(sum(length(e['points']) for e in edges),3),'bends':sum(max(0,len(e['points'])-2) for e in edges),'properCrossings':crossings,'distinctWireCollinearOverlaps':overlaps,'sourceControls':controls,'semanticBindingSha256':hashlib.sha256(json.dumps([(e['id'],e['source'],e['target'],e['binding']) for e in edges],sort_keys=True).encode()).hexdigest(),'validation':{k:r.get(k) for k in ['data-layout-constraint-valid','data-source-constraint-valid','data-frontier-ms','data-render-ms']}})
(root/'capture-metrics.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'captures':len(rows),'hardPassClaim':False,'note':'DOM snapshots; crossing/overlap measures are diagnostics requiring source and pixel review.'}))
