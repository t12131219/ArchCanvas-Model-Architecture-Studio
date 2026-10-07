from pathlib import Path
import json, re, math, xml.etree.ElementTree as ET
p=Path(__file__).parent
keys=['01-new-cnn-before-arrange', '02-new-cnn-after-arrange', '03-new-cnn-zoom-out', '04-new-cnn-zoom-restored', '05-new-cnn-conv-baseline', '06-new-cnn-conv-up', '07-new-cnn-conv-down', '08-new-cnn-conv-left', '09-new-cnn-conv-right', '10-new-cnn-conv-undo-restored', '11-new-cnn-config-out10', '12-new-cnn-config-error-located', '13-new-cnn-config-fixed', '14-new-cnn-saved', '15-new-cnn-unsaved-eleven', '16-new-cnn-reopened', '17-new-cnn-reopened-conv-ten', '18-final-three-row-settled', '19-final-zoom75-first', '20-final-zoom75-settled', '21-final-zoom91-first', '22-final-zoom91-settled']
def numbers(s):return [float(v) for v in re.findall(r'-?\d+(?:\.\d+)?(?:e[-+]?\d+)?',s or '',re.I)]
def route(d):
    tokens=re.findall(r'[MLHV]|-?\d+(?:\.\d+)?',d); pts=[];i=0;x=y=0
    while i<len(tokens):
        op=tokens[i];i+=1
        if op in ('M','L'):x=float(tokens[i]);y=float(tokens[i+1]);i+=2
        elif op=='H':x=float(tokens[i]);i+=1
        elif op=='V':y=float(tokens[i]);i+=1
        else:raise ValueError(d)
        if not pts or pts[-1]!=(x,y):pts.append((x,y))
    return pts
out={'scope':'AI simulated public-DOM geometry audit; no pixel equivalence, presented FPS, human review, or global crossing/bend optimality claim','states':{}}
for key in keys:
    raw=json.loads((p/(key+'.geometry.json')).read_text());svg=ET.fromstring(raw['svg']);nodes={};ports=[]
    for g in svg.iter('g'):
        if 'data-draft-node' not in g.attrib:continue
        x,y=numbers(g.attrib['transform']);rect=next(c for c in g if c.tag=='rect');w=float(rect.attrib['width']);h=float(rect.attrib['height']);node=g.attrib['data-draft-node'];nodes[node]=(x,y,w,h)
        for port in g.iter('g'):
            if 'data-draft-port' not in port.attrib:continue
            circle=next(c for c in port if c.tag=='circle');px=x+float(circle.attrib['cx']);py=y+float(circle.attrib['cy']);ports.append({'node':node,'port':port.attrib['data-draft-port'],'direction':'out' if ' out ' in ' '+port.attrib.get('class','')+' ' else 'in','point':(px,py)})
    details=[]
    for edge in raw['edges']:
        path=edge['paths'][-1];pts=route(path['d']);start,end=pts[0],pts[-1]
        def match(point,direction):
            candidates=[q for q in ports if q['direction']==direction];q=min(candidates,key=lambda q:math.dist(point,q['point']));return {**q,'distance':math.dist(point,q['point'])}
        source=match(start,'out');target=match(end,'in');hits=[]
        for node,(x,y,w,h) in nodes.items():
            if node in (source['node'],target['node']):continue
            for j,(a,b) in enumerate(zip(pts,pts[1:])):
                horizontal=a[1]==b[1];vertical=a[0]==b[0]
                if horizontal and y<a[1]<y+h and max(min(a[0],b[0]),x)<min(max(a[0],b[0]),x+w) or vertical and x<a[0]<x+w and max(min(a[1],b[1]),y)<min(max(a[1],b[1]),y+h):hits.append({'node':node,'segment':j})
        details.append({'edge':edge['id'],'role':edge['role'],'source':source,'target':target,'points':pts,'bends':max(0,len(pts)-2),'unrelatedCardInteriorHits':hits,'marker':path['marker']})
    out['states'][key]={'assets':raw['assets'],'nodes':len(nodes),'edges':len(details),'routes':details,'maxEndpointDistanceWorld':max(q['distance'] for d in details for q in (d['source'],d['target'])),'unrelatedCardInteriorHits':sum(len(d['unrelatedCardInteriorHits']) for d in details),'allMarkersPresent':all(d['marker'] for d in details)}
(p/'public-geometry-audit.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:{a:v[a] for a in ['nodes','edges','maxEndpointDistanceWorld','unrelatedCardInteriorHits','allMarkersPresent']} for k,v in out['states'].items()},indent=2))
