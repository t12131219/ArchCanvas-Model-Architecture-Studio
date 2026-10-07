"""Finite independent raw JSON/XML/geometry audit. Never imports product or observer."""
from pathlib import Path
from datetime import datetime, timezone
from collections import Counter
import hashlib
import json
import math
import xml.etree.ElementTree as ET

OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[4]
RAW=OUT.parent/'01-seven-attempts-full.raw.json'
WORK=OUT.parents[1]/'continuous-observer-work'
NS='{http://www.w3.org/2000/svg}'
r=json.loads(RAW.read_text())
v=json.loads((OUT/'validator.stdout.json').read_text())
candidate=json.loads((WORK/'inputs/09-candidate.canvas.json').read_text())
arch=candidate['architecture']
canonical={n['id']:n for n in arch['nodes']}
edges={e['id']:e for e in arch['edges']}
relations=[]

def add(name,passed,detail=None):
    relations.append({'relation':name,'passed':bool(passed),**({'detail':detail} if detail is not None else {})})

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def near(a,b,eps=1e-7):return abs(a-b)<=eps
def p95(values):return sorted(values)[math.ceil(len(values)*.95)-1] if values else None
def metadata(g):return json.loads(ET.fromstring(g['svgMarkup']).find(NS+'metadata').text)
def stable_sha(value):return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
def stripped_svg(g):
    t=ET.fromstring(g['svgMarkup']);t.attrib.pop('data-revision')
    m=t.find(NS+'metadata');x=json.loads(m.text);x.pop('revision');m.text=json.dumps(x,sort_keys=True)
    return ET.tostring(t)
def changed_world(a,b):return [i for i in a['objects'] if a['objects'][i]['canvas']!=b['objects'][i]['canvas']]

bound=json.loads((OUT/'input-manifest.json').read_text())['files']
add('finite-input-bindings-exact',bool(bound) and all((ROOT/b['path']).stat().st_size==b['bytes'] and sha(ROOT/b['path'])==b['sha256'] for b in bound),len(bound))
add('actual-context-frozen-dist-and-probe-exact',len(r['context']['productionAssets'])==3 and len(r['context']['probeSources'])==4 and all((ROOT/b['path']).stat().st_size==b['bytes'] and sha(ROOT/b['path'])==b['sha256'] for b in r['context']['productionAssets']+r['context']['probeSources']))
add('independent-validator-exit0',json.loads((OUT/'validator.process.json').read_text())['exitCode']==0)
full=[('session-start',r['bindingAtStart']),('session-end',r['bindingAtEnd'])]+[(t['id']+':'+side,t[side]) for t in r['trials'] for side in ('before','after') if t[side]]
metas=[metadata(g) for _,g in full]
source_inputs=[{k:val for k,val in s.items() if k!='content'} for s in arch['sources']]
semantic_nodes=[]
for node in arch['nodes']:
    item={k:value for k,value in node.items() if k not in ('source','parameterOrigins')}
    if 'parameterOrigins' in node:item['parameterOrigins']={k:{q:origin[q] for q in ('kind','expression','path')} for k,origin in node['parameterOrigins'].items()}
    semantic_nodes.append(item)
add('embedded-source-and-ir-digests-recomputed',all(hashlib.sha256(s['content'].encode()).hexdigest()==s['digest'] for s in arch['sources']) and stable_sha(source_inputs)==arch['sourceDigest'] and stable_sha({'entry':arch['entry'],'nodes':semantic_nodes,'edges':arch['edges']})==arch['irDigest'])
add('all-boundaries-document-source-ir-identities',all(g['documentId']==candidate['id'] and g['sourceDigest']==arch['sourceDigest'] and g['irDigest']==arch['irDigest'] and m['documentId']==g['documentId'] and m['revision']==g['revision'] and m['sourceDigest']==g['sourceDigest'] and m['irDigest']==g['irDigest'] for (_,g),m in zip(full,metas)),len(full))
facts_ok=True
for m in metas:
    facts=m['sourceFacts'];facts_ok &= len(facts)==len({f['id'] for f in facts})==304 and {f['id'] for f in facts}==set(canonical)
    for f in facts:
        n=canonical[f['id']]
        count=len({q['callId'] for q in arch['nodes'] if q.get('instanceId')==n.get('instanceId') and q.get('callId')}) if n.get('instanceId') else None
        facts_ok &= f['sourceLabel']==n['label'] and all(f.get(k)==n.get(k) for k in ('kind','category','evidence','source','instanceId','callId','repeat','outputPath')) and f.get('callCount')==count
add('all-boundaries304-canonical-source-facts-exact',facts_ok,{'boundaries':len(full),'canonicalNodes':304})
bindings_ok=True;binding_counts=[]
for m in metas:
    represented=[]
    for b in m['renderedBindings']:
        ids=b['canonicalEdgeIds'];represented+=ids
        bindings_ok &= bool(ids) and all(edges[i]['source']==b['source'] and edges[i]['role']==b['role'] and edges[i]['tensorId']==b['tensorId'] for i in ids) and edges[ids[0]]['target']==b['target']
    bindings_ok &= len(represented)==len(set(represented))==302
    binding_counts.append({'rendered':len(m['renderedBindings']),'representedCanonical':len(represented),'notRenderedCanonical':len(set(edges)-set(represented))})
add('all-boundaries302-rendered-canonical-bindings-faithful',bindings_ok,{'canonicalEdges':len(edges),'firstCounts':binding_counts[0]})
xml_world_ok=True;screen_ok=True;coverage_ok=True;max_screen_error=0.0;coverage=[]
for name,g in full:
    svg=ET.fromstring(g['svgMarkup']);groups={n.get('data-node-id'):n for n in svg.iter() if n.get('data-canonical-id')}
    xml_world_ok &= set(groups)==set(g['objects'])==set(g['visibleIds'])==set(canonical)
    counts=Counter();intersections=inside=0
    for id,n in groups.items():
        o=g['objects'][id];body=next(c for c in list(n) if c.tag==NS+'rect' and c.get('stroke-width') is not None)
        xml_world_ok &= n.get('data-canonical-id')==o['canonicalId']==id and n.get('aria-label')==o['label'] and all(near(float(body.get(k)),o['canvas'][k],1e-9) for k in ('x','y','width','height'))
        b=o['canvas'];mat=o['screenMatrix'];corners=[(mat['a']*x+mat['c']*y+mat['e'],mat['b']*x+mat['d']*y+mat['f']) for x,y in [(b['x'],b['y']),(b['x']+b['width'],b['y']),(b['x'],b['y']+b['height']),(b['x']+b['width'],b['y']+b['height'])]]
        calculated={'x':min(p[0] for p in corners),'y':min(p[1] for p in corners),'width':max(p[0] for p in corners)-min(p[0] for p in corners),'height':max(p[1] for p in corners)-min(p[1] for p in corners)}
        error=max(abs(calculated[k]-o['screen'][k]) for k in calculated);max_screen_error=max(error,max_screen_error);screen_ok &= error<=1e-7
        s=o['screen'];vp=g['viewport'];intersect=s['x']+s['width']>vp['x'] and s['x']<vp['x']+vp['width'] and s['y']+s['height']>vp['y'] and s['y']<vp['y']+vp['height'];fully=s['x']>=vp['x'] and s['y']>=vp['y'] and s['x']+s['width']<=vp['x']+vp['width'] and s['y']+s['height']<=vp['y']+vp['height']
        screen_ok &= o['intersectsViewport']==intersect and o['fullyInsideViewport']==fully
        intersections+=intersect;inside+=fully;counts[canonical[id]['category']]+=1
    coverage_ok &= g['coverage']['renderedCanonicalBodies']==g['coverage']['measuredBodies']==304 and g['coverage']['viewportIntersectingBodies']==intersections and g['coverage']['fullyInsideBodies']==inside
    coverage.append({'boundary':name,'revision':g['revision'],'intersecting':intersections,'fullyInside':inside})
add('all304-body-world-coordinates-match-public-svg-at15-boundaries',xml_world_ok)
add('all-body-screen-transforms-and-viewport-membership-recomputed',screen_ok,{'maxAbsoluteCoordinateError':max_screen_error,'bound':1e-7})
add('boundary-viewport-coverage-counts-exact',coverage_ok,coverage)
add('same4096x2700-frame-and3599x2506-canvas-during-recorded-boundaries',r['environment']['viewport']=={'width':4096,'height':2700,'devicePixelRatio':1} and r['responsiveHarness']['frameViewport']=={'width':4096,'height':2700} and all(g['viewport']=={'x':230,'y':115,'width':3599,'height':2506} for _,g in full))

events=r['events'];d=r['inputDenominator'];counts=Counter(e['type'] for e in events)
add('complete60-received-trusted-event-ledger',len(events)==len({e['id'] for e in events})==d['observed']==d['trusted']==d['retained']==60 and d['untrusted']==d['dropped']==d['failed']==0 and all(e['trusted'] for e in events) and d['rawEventCompleteness'] is True and counts==Counter({k:x['observed'] for k,x in d['byType'].items()}),dict(counts))
add('coalesced32-is-separate-not-extra-primary-events',sum(len(e.get('coalesced',[])) for e in events)==d['coalescedPointerSamples']==32)
add('every-recorded-buffer-has-exact-seen-count-and-no-drops',all(b['seen']==len((r[name.split('.')[0]][name.split('.')[1]] if '.' in name else r[name])) and b['dropped']==0 for name,b in r['buffers'].items()))
add('capture-window-drain-boundaries-honest',all(r['startedAt']<=e['capturedAt']<=r['stopProtocol']['captureEndedAt'] for e in events) and near(r['stopProtocol']['drainEndedAt']-r['stopProtocol']['captureEndedAt'],2000.2,.001) and r['stopProtocol']['unformedEntriesGuaranteed'] is False)

trial1,trial2,trial3,trial4,trial5,trial6,trial7=r['trials']
add('pan1-terminal40-24-css-with-public-svg-world-pin-exact',near(trial1['after']['camera']['matrix']['e']-trial1['before']['camera']['matrix']['e'],40,1e-9) and near(trial1['after']['camera']['matrix']['f']-trial1['before']['camera']['matrix']['f'],24,1e-9) and changed_world(trial1['before'],trial1['after'])==[] and trial1['before']['svgMarkup']==trial1['after']['svgMarkup'] and trial1['before']['pinnedIds']==trial1['after']['pinnedIds']==['input:model.DenseStress300:features'])
outside=[e for e in events if e['trialId'] is None and trial2['armedAt']<=e['capturedAt']<=trial2['finishedAt']];down=next(e for e in outside if e['type']=='pointerdown');up=next(e for e in outside if e['type']=='pointerup');delta=[up['x']-down['x'],up['y']-down['y']]
add('failed-drag2-retained-no-input-with-actual-pan-tool-sequence',trial2['status']=='no-input' and trial2['before'] is None and down['target']['nodeId']==trial2['spec']['targetIds'][0] and down['target']['canvasTool']=='pan' and down['target']['handToolPressed'] is True and delta==[30,18] and trial2['after']['camera']['matrix']['e']-trial1['after']['camera']['matrix']['e']==30 and trial2['after']['camera']['matrix']['f']-trial1['after']['camera']['matrix']['f']==18 and changed_world(trial1['after'],trial2['after'])==[],{'receivedOutsideEvents':len(outside),'pointerDeltaCss':delta,'limitation':'No requested drag before geometry; prior settled boundary is used only for camera/world difference, not a successful requested drag trial.'})
add('undo3-is-pin-removal-and-redo4-restores-pin',trial3['before']['pinnedIds']==['input:model.DenseStress300:features'] and trial3['after']['pinnedIds']==trial4['before']['pinnedIds']==[] and trial4['after']['pinnedIds']==['input:model.DenseStress300:features'] and changed_world(trial3['before'],trial3['after'])==changed_world(trial4['before'],trial4['after'])==[] and stripped_svg(trial3['before'])==stripped_svg(trial4['after']),{'revisions':[6,7,8],'requestedDragRestoration':False})
target='call:instance:model.DenseStress300.network.0';a=trial5['before']['objects'][target]['canvas'];b=trial5['after']['objects'][target]['canvas']
add('successful-drag5-only-one-body40-24-world-with303-unrelated-exact',changed_world(trial5['before'],trial5['after'])==[target] and [b['x']-a['x'],b['y']-a['y']]==[40,24] and trial5['before']['pinnedIds']==trial5['after']['pinnedIds']==['input:model.DenseStress300:features'] and trial5['after']['revision']==trial5['before']['revision']+1)
add('undo6-restores-drag5-whole-public-svg-except-revision',stripped_svg(trial6['after'])==stripped_svg(trial5['before']) and changed_world(trial6['before'],trial6['after'])==[target] and trial6['after']['objects'][target]['canvas']==a and trial6['after']['pinnedIds']==trial5['before']['pinnedIds'])
add('wheel7-changes-camera-and-reduces-coverage-with-all-world-bodies-exact',trial7['before']['svgMarkup']==trial7['after']['svgMarkup'] and changed_world(trial7['before'],trial7['after'])==[] and trial7['before']['camera']['matrix']['a']!=trial7['after']['camera']['matrix']['a'] and trial7['before']['coverage']['fullyInsideBodies']==304 and trial7['after']['coverage']['fullyInsideBodies']==84,{'endIntersections':128,'endFullyInsideBodies':84,'endFullyInside300Leaves':84,'inputPinIntersectsAtEnd':trial7['after']['objects']['input:model.DenseStress300:features']['intersectsViewport']})
add('final-all304-world-bodies-frontier-and-pin-membership-restored',changed_world(r['bindingAtStart'],r['bindingAtEnd'])==[] and r['bindingAtStart']['visibleIds']==r['bindingAtEnd']['visibleIds'] and r['bindingAtStart']['expandedIds']==r['bindingAtEnd']['expandedIds'] and r['bindingAtStart']['pinnedIds']==r['bindingAtEnd']['pinnedIds'])

# Restrict signatures to the declared trial targets/anchors/pins at every boundary,
# so a full304 start and a partial per-frame observation do not invent a change.
proxy_rows=[]
for t in r['trials']:
    if not t['before']:continue
    ids=sorted(set(t['spec']['targetIds']+t['spec']['anchorIds']+t['spec']['pinnedIds']))
    def signature(g):return [g['revision'],g['camera']['matrix'],[[id,g['objects'].get(id)] for id in ids]]
    last=signature(t['before']);changed=[]
    for f in r['frames']:
        if f['trialId']!=t['id'] or f['geometry'] is None:continue
        next_value=signature(f['geometry'])
        if next_value!=last:changed.append(f)
        last=next_value
    eligible=[e for e in events if e['trialId']==t['id'] and e['trusted'] and e['type'] in ('pointermove','wheel')]
    proxies=[]
    for e in eligible:
        next_frame=next((f for f in changed if f['observedAt']>=e['capturedAt']),None)
        proxies.append({'inputId':e['id'],'eventToCaptureMs':e['capturedAt']-e['eventAt'],'firstChangeProxyMs':next_frame['observedAt']-e['eventAt'] if next_frame else None,'claimedFirstChangeProxyMs':next((c['inputToObservedChangeProxyMs'] for z in v['base']['trials'] if z['id']==t['id'] for c in z.get('continuousProxies',[]) if c['inputId']==e['id']),None)})
    claimed=next(x for x in v['base']['trials'] if x['id']==t['id']).get('continuousProxies',[])
    add(t['id']+':independent-continuous-proxy-reconstruction',len(proxies)==len(claimed) and all(p['inputId']==c['inputId'] and (p['firstChangeProxyMs']==c['inputToObservedChangeProxyMs'] if p['firstChangeProxyMs'] is None else near(p['firstChangeProxyMs'],c['inputToObservedChangeProxyMs'])) for p,c in zip(proxies,claimed)))
    if proxies:
        values=[p['firstChangeProxyMs'] for p in proxies if p['firstChangeProxyMs'] is not None]
        proxy_rows.append({'trial':t['id'],'operation':t['spec']['operation'],'eligible':len(eligible),'measured':len(values),'proxyP95Ms':p95(values),'proxyMinMs':min(values) if values else None,'proxyMaxMs':max(values) if values else None,'eventToCaptureP95Ms':p95([p['eventToCaptureMs'] for p in proxies]),'rows':proxies})
add('continuous-raw33-retained-assigned17-and-unassigned16-remain-distinct',sum(e['type'] in ('pointermove','wheel') for e in events)==33 and sum(x['eligible'] for x in proxy_rows)==17 and sum(e['type'] in ('pointermove','wheel') and e['trialId'] is None for e in events)==16)
failure=[x for x in relations if not x['passed']]
report={'schema':'archcanvas-responsive-browser-independent/1','createdUtc':datetime.now(timezone.utc).isoformat(),'relationGroups':len(relations),'passedGroups':len(relations)-len(failure),'failedGroups':len(failure),'failures':failure,'relationships':relations,
 'knownValidatorProxyDefect':'Old validator uses entire full-boundary304object signature versus partial frame target/pin signature, inventing the first geometry change. Independent same-object-set first-change values are authoritative bounded proxies; three mismatch relation groups remain false. No sealed validator/raw/product changed.','summary':{'actualRawBytes':RAW.stat().st_size,'actualRawCharacters':len(RAW.read_text()),'attempts':7,'observerSucceeded':6,'failedRequestedDrag':1,'trustedReceivedRetainedEvents':60,'rawDrops':0,'rawFailures':0,'coalescedSamplesSeparate':32,'inputTypeCounts':dict(counts),'canonical304BodyBoundaries':len(full),'actualFrameViewport':[4096,2700],'actualCanvasViewport':[3599,2506],'beforeFullyInsideBodies':304,'afterWheelFullyInsideBodies':84,'eligibleDiscreteAssignedInputs':v['base']['latency']['eligibleDiscreteInputs'],'matchedDiscreteAssignedInputs':v['base']['latency']['matchedDiscreteInputs'],'matchedDiscreteInteractions':v['base']['latency']['matchedInteractions'],'matchedSubsetP95Ms':v['base']['latency']['matchedInteractionP95Ms'],'rAFWholeSession':v['base']['frameCadence'],'observerSelfCost':v['base']['observerSelfCost'],'longTaskCount':len(r['longTasks']),'maxLongTaskMs':max(x['durationMs'] for x in r['longTasks']),'continuousProxyGroups':proxy_rows,'presentedFps':None,'continuousInputToPaintMs':None,'performanceGatePassed':False,'humanParticipants':0},
 'limits':['60/60 is completeness of received declared-type events in the capture window, not all OS inputs or native paint timing.32coalesced samples are separate, not extra primary events.','6observer successes do not mean7requested tasks passed: drag2 remainedno-input/actualpan; undo3 removedpin, redo4restoredpin.','Three inherited validator proxy groups disagree with independent same-object-set reconstruction because its first partial frame is treated as changed against full304body start. Pan firstproxy960→965.4ms; drag firstproxy772.9→1015.4ms; wheel39.5→45.2ms. Old values and failures retained. DOM first-change proxy is not causal input-to-paint. Pan/drag proxy p95 greatly exceeds50ms; wheel39.5ms cannot establish300object≤50ms gate.','Wholewindow and active rAF cadence include automation pauses; no actual presented frame stream.','300 leaf bodies initially fit geometrically, but font bytes/hardware/power, occlusion and legibility are unproved. Wheel leaves only84leaf bodies fully inside and makes pin offscreen.','Known collapsed-output candidate defect is unchanged; no toggle/full-workload certification.','Allbody publicSVG and metadata continuity does not certify hidden CanvasDocument/history persistence; no save/export/model execution here.','The final screenshot/AX timeout and pre-session failed checkbox are root observations outside this raw trial ledger. The audit does not convert them to successes.','No medium-workload <500ms, fixed A/Bx3, publication human review or real participant evidence is added.'], 'productsChanged':False,'modelExecuted':False}
(OUT/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'relationGroups':len(relations),'passedGroups':len(relations)-len(failure),'failedGroups':failure,'proxyGroups':[{k:x[k] for k in ('trial','eligible','measured','proxyP95Ms','proxyMinMs','proxyMaxMs')} for x in proxy_rows]},ensure_ascii=False))
raise SystemExit(bool(failure))
