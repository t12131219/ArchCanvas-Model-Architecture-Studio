"""Independent public authored-SVG evidence checker; no product/model imports."""
from __future__ import annotations
from pathlib import Path
from datetime import datetime, timezone
import copy, hashlib, json, math, re, xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[4]
RAW = ROOT / 'docs/evidence/m4-authoring-next/browser'
OUT = Path(__file__).resolve().parent
SCRIPT = 'index-CIVB6v-J.js'
KINDS = ['Input', 'Linear', 'ReLU', 'Output']
EXPECTED_POSITIONS = [(50,70), (298,70), (546,70), (794,70)]
EXPECTED_PORTS = {'Input': [('output','out')], 'Linear':[('input','in'),('output','out')], 'ReLU':[('input','in'),('output','out')], 'Output':[('input','in')]}

class Rejected(ValueError): pass
def need(value, reason):
    if not value: raise Rejected(reason)
def close(a,b,tolerance=1e-8): return abs(a-b)<=tolerance
def tag(element): return element.tag.split('}')[-1]
def transform(value, camera=False):
    pattern = r'translate\(([-+\deE.]+)\s+([-+\deE.]+)\)' + (r'\s+scale\(([-+\deE.]+)\)' if camera else '')
    matched = re.fullmatch(pattern,value or '')
    need(matched is not None,'unsupported transform')
    result=tuple(float(v) for v in matched.groups());need(all(math.isfinite(v) for v in result),'nonfinite transform');return result
def points(path):
    tokens=re.findall(r'[A-Za-z]|[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?',path or '')
    result=[];i=0;x=y=0
    while i<len(tokens):
        op=tokens[i];i+=1
        if op in ('M','L'):x=float(tokens[i]);y=float(tokens[i+1]);i+=2
        elif op=='H' and result:x=float(tokens[i]);i+=1
        elif op=='V' and result:y=float(tokens[i]);i+=1
        else:raise Rejected('unsupported route command')
        need(math.isfinite(x) and math.isfinite(y),'nonfinite point')
        if not result or result[-1]!=(x,y):result.append((x,y))
    need(len(result)>1,'empty route')
    for a,b in zip(result,result[1:]):need(a[0]==b[0] or a[1]==b[1],'diagonal route')
    compact=[]
    for p in result:
        while len(compact)>1:
            a,b=compact[-2:]
            forward=(a[0]==b[0]==p[0] and (b[1]-a[1])*(p[1]-b[1])>=0) or (a[1]==b[1]==p[1] and (b[0]-a[0])*(p[0]-b[0])>=0)
            if not forward:break
            compact.pop()
        compact.append(p)
    return compact
def hit(a,b,body):
    x,y,w,h=body;m=.02
    if a[0]==b[0]:return x+m<a[0]<x+w-m and max(min(a[1],b[1]),y+m)<min(max(a[1],b[1]),y+h-m)
    return y+m<a[1]<y+h-m and max(min(a[0],b[0]),x+m)<min(max(a[0],b[0]),x+w-m)
def cross(a,b,c,d):
    if a[0]==b[0] and c[1]==d[1] and min(c[0],d[0])<a[0]<max(c[0],d[0]) and min(a[1],b[1])<c[1]<max(a[1],b[1]):return a[0],c[1]
    if a[1]==b[1] and c[0]==d[0] and min(a[0],b[0])<c[0]<max(a[0],b[0]) and min(c[1],d[1])<a[1]<max(c[1],d[1]):return c[0],a[1]
def overlap(a,b,c,d):
    if a[0]==b[0]==c[0]==d[0]:return max(0,min(max(a[1],b[1]),max(c[1],d[1]))-max(min(a[1],b[1]),min(c[1],d[1])))
    if a[1]==b[1]==c[1]==d[1]:return max(0,min(max(a[0],b[0]),max(c[0],d[0]))-max(min(a[0],b[0]),min(c[0],d[0])))
    return 0
def inspect(record):
    need(any(url.endswith('/'+SCRIPT) for url in record.get('scripts',[])),'different or missing product build')
    need(record.get('summary')=='4 模块 3 连接','module/connection summary drift')
    root=ET.fromstring(record['svg']);need(root.get('aria-label')=='模型搭建画布','wrong view')
    camera_group=next((e for e in root if tag(e)=='g' and e.get('transform')),None);need(camera_group is not None,'missing camera')
    camera=transform(camera_group.get('transform'),True);need(camera==transform(record['camera'],True),'camera summary differs from actual SVG')
    nodes=[];routes=[];ports={};edge_ids=set();node_ids=set()
    marker_ids={e.get('id') for e in root.iter() if tag(e)=='marker'}
    for group in camera_group:
        identity=group.get('data-draft-node')
        if identity:
            need(identity not in node_ids,'duplicate node identity');node_ids.add(identity)
            local=transform(group.get('transform'));body=next((e for e in group if tag(e)=='rect' and e.get('class') is None),None);need(body is not None,'missing body')
            size=(float(body.get('width')),float(body.get('height')));need(size==(176,100),'body dimension drift')
            label=next((e.text for e in group if tag(e)=='text' and e.get('class')=='draft-node-title'),None)
            kind=next((e.text for e in group if tag(e)=='text' and e.get('class')=='draft-node-kind'),None);need(kind in EXPECTED_PORTS,'unknown module kind')
            entries=[]
            for p in group:
                if not p.get('data-draft-port'):continue
                need(p.get('data-node')==identity,'foreign port owner');direction=p.get('class');need(direction in ['draft-port in','draft-port out'],'wrong port direction')
                direction=direction.rsplit(' ',1)[1];port_id=p.get('data-draft-port');need((port_id,direction) in EXPECTED_PORTS[kind],'wrong declared kind/port')
                dots=[e for e in p if tag(e)=='circle' and e.get('fill')!='transparent'];need(len(dots)==1,'missing semantic port dot')
                point=(local[0]+float(dots[0].get('cx')),local[1]+float(dots[0].get('cy')))
                need(close(point[0],local[0]+(176 if direction=='out' else 0)) and close(point[1],local[1]+66),'role-specific port coordinate drift')
                need((identity,port_id) not in ports,'duplicate port identity');ports[identity,port_id]={'point':point,'direction':direction};entries.append((port_id,direction))
            need(sorted(entries)==sorted(EXPECTED_PORTS[kind]),'missing/extra module port')
            nodes.append({'id':identity,'kind':kind,'label':label,'position':local,'body':(*local,*size),'ports':entries})
        identity=group.get('data-draft-edge')
        if identity:
            need(identity not in edge_ids,'duplicate edge identity');edge_ids.add(identity)
            paths=[e for e in group if tag(e)=='path'];need(len(paths)==2,'missing edge hit-target or appearance path')
            need(paths[0].get('stroke')=='transparent' and paths[0].get('d')==paths[1].get('d'),'visible/hit-target route mismatch')
            marker=re.fullmatch(r'url\(#([^)]*)\)',paths[1].get('marker-end') or '');need(marker and marker.group(1) in marker_ids,'missing/detached arrow marker')
            routes.append({'id':identity,'path':paths[1].get('d'),'points':points(paths[1].get('d'))})
    need([n['kind'] for n in nodes]==KINDS,'kind/node ordering drift');need(len(routes)==3,'route count drift')
    need([(n['id'],n['label'],n['position']) for n in nodes]==[(n['id'],n['label'],transform(n['transform'])) for n in record['positions']],'node summary differs from actual SVG')
    need([(e['id'],e['path']) for e in routes]==[(e['id'],e['path']) for e in record['edges']],'route summary differs from actual SVG')
    for i,edge in enumerate(routes):
        source=nodes[i];target=nodes[i+1];a=ports[source['id'],'output']['point'];b=ports[target['id'],'input']['point']
        need(all(close(x,y,.02) for x,y in zip(a,edge['points'][0])),'detached source endpoint')
        need(all(close(x,y,.02) for x,y in zip(b,edge['points'][-1])),'wrong/detached target endpoint')
        edge['inferredBinding']={'source':{'nodeId':source['id'],'portId':'output'},'target':{'nodeId':target['id'],'portId':'input'}}
        for a,b in zip(edge['points'],edge['points'][1:]):
            for node in nodes:need(not hit(a,b,node['body']),'route penetrates node body')
        edge['bends']=len(edge['points'])-2
        edge['reversals']=sum((b[0]-a[0])*(c[0]-b[0])+(b[1]-a[1])*(c[1]-b[1])<0 for a,b,c in zip(edge['points'],edge['points'][1:],edge['points'][2:]));need(edge['reversals']==0,'route U-turn')
        edge['manhattanMinimum']=abs(edge['points'][0][0]-edge['points'][-1][0])+abs(edge['points'][0][1]-edge['points'][-1][1])
        edge['length']=sum(abs(a[0]-b[0])+abs(a[1]-b[1]) for a,b in zip(edge['points'],edge['points'][1:]))
        need(close(edge['length'],edge['manhattanMinimum']),'unnecessary route detour in simple chain')
    for i,node in enumerate(nodes):
        x,y,w,h=node['body']
        for other in nodes[i+1:]:
            a,b,c,d=other['body'];need(min(x+w,a+c)<=max(x,a) or min(y+h,b+d)<=max(y,b),'node body overlap')
    crossings=[];overlaps=[]
    for i,e in enumerate(routes):
        for f in routes[i+1:]:
            for a,b in zip(e['points'],e['points'][1:]):
                for c,d in zip(f['points'],f['points'][1:]):
                    if cross(a,b,c,d):crossings.append([e['id'],f['id'],cross(a,b,c,d)])
                    if overlap(a,b,c,d)>.02:overlaps.append([e['id'],f['id'],overlap(a,b,c,d)])
    need(not crossings and not overlaps,'chain arrows intersect/overlap')
    return {'camera':camera,'nodes':nodes,'routes':routes,'crossings':crossings,'overlaps':overlaps,'totalBends':sum(e['bends'] for e in routes)}

def graph(state):return {k:state[k] for k in ['nodes','routes']}
def check_move(base,moved,dx,dy):
    need(base['camera']==moved['camera'],'move changed camera')
    need([e['id'] for e in base['routes']]==[e['id'] for e in moved['routes']],'move changed edge identities')
    for i,(a,b) in enumerate(zip(base['nodes'],moved['nodes'])):
        need(a['id']==b['id'] and a['kind']==b['kind'] and a['label']==b['label'] and a['ports']==b['ports'],'move changed node/port identity')
        need(b['position']==(a['position'][0]+(dx if i==1 else 0),a['position'][1]+(dy if i==1 else 0)),'wrong move delta or unrelated node moved')
def check_pan(base,moved,restored,dx,dy):
    need(graph(base)==graph(moved)==graph(restored),'pan changed graph geometry/binding')
    need(all(close(b,a+d) for a,b,d in zip(base['camera'],moved['camera'],[dx,dy,0])),'wrong pan delta')
    need(all(close(a,b) for a,b in zip(base['camera'],restored['camera'])),'pan not restored')
def load(name):return json.loads((RAW/(name+'.json')).read_text())
def run():
    names=sorted(p.stem for p in RAW.glob('*.json') if {'camera','svg','positions','edges'}.issubset(json.loads(p.read_text())))
    states={name:inspect(load(name)) for name in names};base=states['saved-baseline']
    need([n['position'] for n in base['nodes']]==EXPECTED_POSITIONS,'baseline positions differ from predeclared chain')
    for name,dx,dy in [('move-left',-16,0),('move-right',16,0),('move-up',0,-16),('move-down',0,16)]:check_move(base,states[name],dx,dy)
    need(graph(states['left-undo'])==graph(base),'left undo mismatch');need(graph(states['left-redo'])==graph(states['move-left']),'left redo mismatch')
    need(graph(states['moves-restored'])==graph(base),'final move restore mismatch')
    pan_records=[]
    for direction,dx,dy in [('left',-40,0),('right',40,0),('up',0,-40),('down',0,40)]:
        before='pan-left-round2-base' if direction=='left' else 'pan-base';moved='pan-left-round2' if direction=='left' else f'pan-{direction}';restored='pan-left-round2-restored' if direction=='left' else f'pan-{direction}-restored'
        check_pan(states[before],states[moved],states[restored],dx,dy);pan_records.append({'direction':direction,'before':before,'moved':moved,'restored':restored,'deltaCss':[dx,dy]})
    recovery=states['pan-recovery-state'];recovery_delta=[b-a for a,b in zip(states['pan-base']['camera'][:2],recovery['camera'][:2])]
    need(graph(recovery)==graph(states['pan-base']),'interrupted recovery changed graph');need(all(close(a,b) for a,b in zip(recovery_delta,[-15,0])),'recovery discrepancy changed')
    need(graph(states['reopened-before-open'])==graph(base),'reopened public geometry differs from saved baseline')
    counters=counterexamples(load('saved-baseline'),base)
    result={'schemaVersion':1,'recordedAt':datetime.now(timezone.utc).isoformat(),'scope':'New CIVB6v-J authored public DOM artifacts. No previous browser/human/FPS coverage inherited.','scriptSha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'build':SCRIPT,'captures':len(states),'files':{name+'.json':hashlib.sha256((RAW/(name+'.json')).read_bytes()).hexdigest() for name in names},'states':states,'fourSignedNodeMovesPassed':True,'leftUndoRedoPassed':True,'finalMovesRestored':True,'fourPanRecords':pan_records,'interruptedLeftRoundOne':{'status':'excluded-incomplete-input-chain','interruptedCameraDeltaCss':recovery_delta,'finalRestoredStatePresent':True,'successfulRange':'left-round2 only'},'reopenedPublicGeometryEqual':True,'counterexamples':counters,'canonicalBindingScope':'Exact draft SVG edge/node/port identities and endpoint-inferred chain. Authored SVG has no canonical binding/revision/parameter metadata; actual DraftStore bytes are needed for a complete binding claim.','limits':['Right/up/down lack separate undo/redo raw records; only moved and final collective restore are certified.','No raw trusted input event chronology or active held cancellation certified.','SVG geometry does not measure viewport visibility, device frames, font resolution, FPS, INP or human readability.','Parameters/revisions/title/draft identity are not contained in these public captures.'], 'humanAcceptanceCertified':False,'publicationAcceptanceCertified':False,'browserPerformanceCertified':False}
    (OUT/'audit.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'captures':len(states),'moveDirections':4,'panDirections':4,'counterexamples':len(counters),'maxBends':max(s['totalBends'] for s in states.values()),'script':SCRIPT},ensure_ascii=False))
def counterexamples(raw,baseline):
    cases=[]
    def reject(name,callback):
        try:callback()
        except (Rejected,ValueError,IndexError,ET.ParseError):cases.append({'name':name,'rejected':True})
        else:raise AssertionError('missed corruption '+name)
    def mutation(name,mutate):
        value=copy.deepcopy(raw);mutate(value);reject(name,lambda:inspect(value))
    mutation('different-build',lambda v:v.update(scripts=['assets/index-C7L6p5cl.js']))
    mutation('missing-build',lambda v:v.update(scripts=[]))
    mutation('stale-summary-position',lambda v:v['positions'][1].update(transform='translate(299 70)'))
    mutation('stale-summary-route',lambda v:v['edges'][0].update(path='M 226 136 H 299'))
    mutation('missing-arrow-marker',lambda v:v.update(svg=v['svg'].replace('marker-end="url(#draft-arrow)"','marker-end="url(#absent)"',1)))
    mutation('foreign-port-owner',lambda v:v.update(svg=v['svg'].replace('data-node="'+v['positions'][0]['id']+'"','data-node="foreign"',1)))
    mutation('wrong-port-role',lambda v:v.update(svg=v['svg'].replace('class="draft-port out"','class="draft-port in"',1)))
    mutation('wrong-kind-port',lambda v:v.update(svg=v['svg'].replace('data-draft-port="output"','data-draft-port="foreign"',1)))
    mutation('malformed-xml',lambda v:v.update(svg=v['svg'][:-6]))
    mutation('camera-summary-drift',lambda v:v.update(camera='translate(5 6) scale(1)'))
    bad=copy.deepcopy(baseline);bad['nodes'][1]['position']=(299,70);reject('wrong-move-delta',lambda:check_move(baseline,bad,-16,0))
    bad=copy.deepcopy(baseline);bad['nodes'][0]['position']=(66,70);reject('move-unrelated-node',lambda:check_move(baseline,bad,0,0))
    bad=copy.deepcopy(baseline);bad['camera']=(baseline['camera'][0]-39,*baseline['camera'][1:]);reject('wrong-pan-delta',lambda:check_pan(baseline,bad,baseline,-40,0))
    bad=copy.deepcopy(baseline);bad['camera']=(baseline['camera'][0]-15,*baseline['camera'][1:]);moved=copy.deepcopy(baseline);moved['camera']=(baseline['camera'][0]-40,*baseline['camera'][1:]);reject('interrupted-restoration',lambda:check_pan(baseline,moved,bad,-40,0))
    need(cross((0,5),(20,5),(10,0),(10,10))==(10,5),'cross primitive positive');need(cross((0,5),(20,5),(20,0),(20,10)) is None,'endpoint touch primitive');need(overlap((0,5),(20,5),(10,5),(25,5))==10,'overlap primitive');need(points('M 0 0 H 10 V 0 H 20')==[(0,0),(20,0)],'redundant zero bend primitive')
    return cases
if __name__=='__main__':run()
