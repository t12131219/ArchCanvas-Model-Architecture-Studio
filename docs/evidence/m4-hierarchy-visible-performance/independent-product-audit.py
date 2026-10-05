#!/usr/bin/env python3
"""Independent frozen-byte product input audit; no product/probe imports or browser."""
from pathlib import Path
import ast, datetime, hashlib, json, math, re, subprocess, tempfile
import xml.etree.ElementTree as ET
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
FROZEN={}
NS='{http://www.w3.org/2000/svg}'
def check(ok,msg):
 if not ok:raise AssertionError(msg)
def eq(a,b,msg):check(a==b,msg)
def sha(b):return hashlib.sha256(b).hexdigest()
def fr(p):
 p=Path(p);p=p if p.is_absolute() else ROOT/p;p=p.resolve()
 if p not in FROZEN:FROZEN[p]=p.read_bytes()
 sha(FROZEN[p])
 return FROZEN[p]
def js(p):return json.loads(fr(p))
def bind(p):
 p=Path(p);p=p if p.is_absolute() else ROOT/p;p=p.resolve();b=fr(p)
 return {'path':str(p.relative_to(ROOT)),'bytes':len(b),'sha256':sha(b)}
def q(v,p=.95):return sorted(v)[math.ceil(len(v)*p)-1] if v else None
def can(v):return sha(json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode())
def close(a,b,msg,tol=.001):check(abs(a-b)<tol,msg)
def norm(s):
 a,n=re.subn(r'\bdata-revision="[0-9]+"','data-revision="0"',s)
 a,m=re.subn(r'"revision":[0-9]+','"revision":0',a)
 eq((n,m),(1,1),'exactly two revision scalars normalized')
 return a
def xml(s):
 root=ET.fromstring(s);meta=json.loads(root.find(NS+'metadata').text)
 groups={e.attrib['data-node-id']:e for e in root.iter() if 'data-canonical-id' in e.attrib}
 bodies={i:{k:float(next(c for c in g if c.tag==NS+'rect' and 'stroke-width' in c.attrib).attrib[k]) for k in ['x','y','width','height']} for i,g in groups.items()}
 return root,meta,groups,bodies
def sig(g):return [g['camera']['matrix'],[[k,v['canvas'] if v else None,v['screen'] if v else None,v.get('label') if v else None] for k,v in g['objects'].items()]]
def cad(fs):
 t=[f['at'] for f in fs];iv=[b-a for a,b in zip(t,t[1:])]
 return {'callbacks':len(t),'intervalP95Ms':q(iv),'maxIntervalMs':max(iv) if iv else None,'callbackCadenceHz':(len(t)-1)*1000/(t[-1]-t[0]) if len(t)>1 and t[-1]>t[0] else None,'notPresentedFPS':True}
started=datetime.datetime.now(datetime.timezone.utc).isoformat()
rawpath=HERE/'product-raw.json';valpath=HERE/'product-validation.json';vp=ROOT/'scripts/validate_input_observation.mjs'
r=js(rawpath);v=js(valpath);fr(vp);fr(HERE/'product-validation-stderr.txt');fr(__file__)
readv1=js(HERE/'receipt-read.json');read=js(HERE/'receipt-read-v2.json');eq(readv1['ranges'],read['ranges'],'v2 preserves131 ranges');lifecycle=js(HERE/'prestart-lifecycle.json')
# Bind an exact visibility snapshot because root may still append control-after reads.
vispath=HERE/'visibility-readings.json';viscopy=HERE/'product-audit-visibility-snapshot.json'
if not viscopy.exists():
 visbytes=vispath.read_bytes();sha(visbytes);viscopy.write_bytes(visbytes)
vis=js(viscopy)
visobs={'originalPath':str(vispath.relative_to(ROOT)),'snapshot':bind(viscopy),'capturedAtAudit':started,'originalMayReceiveLaterControlReads':True,'productRelatedReadings':[x for x in vis if 'product' in x['phase']]}
ctx=[]
for category in ['productionAssets','probeSources']:
 for d in r['context'][category]:
  a=bind(d['path']);eq(a,d,'context current bytes '+d['path']);ctx.append({'category':category,**a})
build=js('docs/evidence/m4-hierarchy-optimization/build-context.json')
for d in build['bindings']:eq(bind(d['path']),d,'current source/build context')
eq(len(ctx),9,'three production/six probe declarations')
eq(r['environment']['scripts'],['http://127.0.0.1:8897/assets/index-oI5sT67U.js'],'actual 8897 script URL')
eq(r['environment']['viewport'],{'width':1280,'height':720,'devicePixelRatio':1},'actual iframe viewport')
eq(r['schemaVersion'],2,'v2');eq(r['protocol'],'archcanvas-input-observation/2','protocol')
eq(r['errors'],[],'observer errors empty')
eq(r['harness']['humanParticipants'],0,'no human')
for name,x in r['buffers'].items():
 eq(x['dropped'],0,'no dropped '+name)
 a=r
 for p in name.split('.'):a=a[p]
 check(len(a)<=x['limit'],'bounded '+name)
# Source/IR independent reconstruction from an unchanged formally analyzed source-bound architecture.
env=js('docs/evidence/m4-hierarchy-optimization/react-probe-dist/fixture.json')
a=env['document']['architecture'];nodes={n['id']:n for n in a['nodes']};eq(len(nodes),304,'304 canonical nodes');eq(len(a['edges']),304,'304 canonical edges')
for s in a['sources']:
 b=fr(ROOT/'fixtures/stress_300'/s['path']);eq(sha(b),s['digest'],'fixture source digest');eq(b.decode(),s['content'],'included actual source bytes')
 calls=[x for x in ast.walk(ast.parse(b)) if isinstance(x,ast.Call) and isinstance(x.func,ast.Attribute) and isinstance(x.func.value,ast.Name) and x.func.value.id=='nn' and x.func.attr=='Sequential']
 eq(len(calls),1,'one authored Sequential');eq([x.func.attr for x in calls[0].args],['Linear','ReLU']*150,'300 authored layers')
eq(can([{k:v for k,v in s.items() if k!='content'} for s in a['sources']]),a['sourceDigest'],'source aggregate independently computed')
sn=[]
for n in a['nodes']:
 d={k:v for k,v in n.items() if k not in ['source','parameterOrigins']}
 if 'parameterOrigins' in n:d['parameterOrigins']={k:{z:o[z] for z in ['kind','expression','path']} for k,o in n['parameterOrigins'].items()}
 sn.append(d)
eq(can({'entry':a['entry'],'nodes':sn,'edges':a['edges']}),a['irDigest'],'semantic IR digest independently computed')
instances={}
for n in a['nodes']:
 if n.get('instanceId') and n.get('callId'):instances.setdefault(n['instanceId'],set()).add(n['callId'])
facts=[]
for n in a['nodes']:
 f={k:n[z] for k,z in [('id','id'),('sourceLabel','label'),('kind','kind'),('category','category'),('evidence','evidence')]}
 if n.get('instanceId'):f.update(instanceId=n['instanceId'],callCount=len(instances[n['instanceId']]))
 for k in ['callId','repeat','outputPath','source']:
  if k in n:f[k]=n[k]
 facts.append(f)
full=[('start',r['bindingAtStart'])]+[(t['id']+'.'+s,t[s]) for t in r['trials'] for s in ['before','after']]
snapshots=[]
for name,g in full:
 root,m,groups,bodies=xml(g['svgMarkup'])
 for k in ['sourceDigest','irDigest']:eq(g[k],a[k],name+' architecture binding')
 eq(g['documentId'],env['document']['id'],name+' doc id');eq(int(root.attrib['data-revision']),g['revision'],name+' svg revision');eq(m['revision'],g['revision'],name+' metadata revision')
 for k in ['sourceDigest','irDigest','documentId']:eq(m[k],g[k],name+' svg metadata binding')
 eq(m['sourceFacts'],facts,name+' full canonical facts');eq(sorted(groups),g['visibleIds'],name+' svg/frontier IDs')
 eq(sorted(x['sceneNodeId'] for x in m['renderedNodes']),g['visibleIds'],name+' rendered metadata IDs')
 eq(g['pinnedIds'],[],name+' no pins')
 for i,o in g['objects'].items():
  if o: eq(bodies[i],o['canvas'],name+' body rect exact');eq(groups[i].attrib['aria-label'],o['label'],name+' label exact')
 snapshots.append({'snapshot':name,'revision':g['revision'],'visibleFrontierCount':len(groups),'sourceFactCount':len(m['sourceFacts']),'renderedBindingCount':len(m['renderedBindings']),
  'svgBytes':len(g['svgMarkup'].encode()),'svgSha256':sha(g['svgMarkup'].encode()),'normalizedSvgSha256':sha(norm(g['svgMarkup']).encode()),'camera':g['camera'],'tool':g['canvasTool'],'handToolPressed':g['handToolPressed'],'pinnedIds':g['pinnedIds'],'selectionMarkup':g['selectionMarkup'],'frameRect':g['frameRect']})
for _,g in full+[(str(i),f['geometry']) for i,f in enumerate(r['frames']) if f['geometry']]:
 for i,o in g['objects'].items():
  if not o:continue
  b=o['canvas'];m=o['screenMatrix'];corners=[(b['x'],b['y']),(b['x']+b['width'],b['y']),(b['x'],b['y']+b['height']),(b['x']+b['width'],b['y']+b['height'])]
  p=[(m['a']*x+m['c']*y+m['e'],m['b']*x+m['d']*y+m['f']) for x,y in corners]
  expected={'x':min(x for x,y in p),'y':min(y for x,y in p),'width':max(x for x,y in p)-min(x for x,y in p),'height':max(y for x,y in p)-min(y for x,y in p)}
  for k in expected:close(expected[k],o['screen'][k],'independent CTM '+i)
  s=o['screen'];vpt=g['viewport'];visible=s['x']+s['width']>vpt['x'] and s['x']<vpt['x']+vpt['width'] and s['y']+s['height']>vpt['y'] and s['y']<vpt['y']+vpt['height']
  eq(visible,o['intersectsViewport'],'independent viewport intersection')
# Entire bidirectional candidate graph (outside-trial inputs also compete).
disc=[e for e in r['events'] if e['trusted'] and e['type'] in ['pointerdown','pointerup','click','keydown','keyup'] and e['target']['token']]
ic={};ec={}
for e in disc:
 c=[i for i,n in enumerate(r['eventTiming']) if n['interactionId']>0 and n['name']==e['type'] and n['targetToken']==e['target']['token'] and abs(n['startAt']-e['eventAt'])<=8];ic[e['id']]=c
 for i in c:ec.setdefault(i,[]).append(e['id'])
match=[]
for e in disc:
 if not e['trialId']:continue
 c=ic[e['id']];i=c[0] if len(c)==1 and len(ec[c[0]])==1 else None;n=r['eventTiming'][i] if i is not None else None
 match.append({'inputId':e['id'],'trialId':e['trialId'],'nativeEntryIndex':i,'nativeDurationMs':n['durationMs'] if n else None,'interactionId':n['interactionId'] if n else None,'inputCandidateCount':len(c),'candidateEntryInputCounts':[{'nativeEntryIndex':z,'inputs':len(ec[z])} for z in c],'missingReason':None if n else 'ambiguous' if c else 'unavailable-below-threshold-detached-or-truncated'})
eq(match,v['latency']['matches'],'all matching candidates/native fields exact')
durations={}
for m in match:
 if m['interactionId'] is not None:durations[m['interactionId']]=max(durations.get(m['interactionId'],0),m['nativeDurationMs'])
lat={'eligibleDiscreteInputs':len(match),'matchedDiscreteInputs':sum(m['nativeEntryIndex'] is not None for m in match),'matchedInteractions':len(durations),'matchedInteractionP95Ms':q(list(durations.values()))}
for k,z in lat.items():eq(z,v['latency'][k],'latency '+k)
lat.update(matches=match,perInteractionMaximumDurationMs=durations,missingRemainNull=True,scope='matched discrete subset only, not representative p95, overall INP or continuous input-to-paint')
ops=['toggle','pan','drag','undo','redo'];eq([t['spec']['operation'] for t in r['trials']],ops,'five requested operations')
trialchecks=[];windows=[]
target='call:instance:model.DenseStress300.network.0';network='call:instance:model.DenseStress300.network'
for t,rv in zip(r['trials'],v['trials']):
 es=[e for e in r['events'] if e['trialId']==t['id'] and e['trusted']];d=next(e for e in es if e['type']=='pointerdown');u=next(e for e in es if e['type']=='pointerup' and e['pointerId']==d['pointerId'] and e['eventAt']>=d['eventAt'])
 active=es[es.index(d):es.index(u)];moves=[e for e in active if e['type']=='pointermove' and e['pointerId']==d['pointerId']];cancel=[e for e in active if e['type'] in ['pointercancel','lostpointercapture'] and e['pointerId']==d['pointerId'] or e['type']=='blur' or e['type']=='keydown' and e['key']=='Escape']
 eq(cancel,[],'no active native cancellation');eq(d['id'],t['firstEventId'],'actual trigger ID');eq(es[-1]['id'],t['lastEventId'],'last event ID');eq(t['status'],'finished','finished trial')
 b,c=t['before'],t['after'];op=t['spec']['operation'];rev=c['revision']-b['revision'];delta={k:c['objects'][t['spec']['targetIds'][0]]['canvas'][k]-b['objects'][t['spec']['targetIds'][0]]['canvas'][k] for k in ['x','y','width','height']}
 fullframes=[f for f in r['frames'] if f['trialId']==t['id']];eventframes=[f for f in fullframes if d['eventAt']<=f['at']<=u['eventAt']];obsframes=[f for f in fullframes if d['capturedAt']<=f['observedAt']<=u['capturedAt']]
 prev=sig(b);changes=[]
 for f in fullframes:
  nxt=sig(f['geometry'])
  if nxt!=prev:changes.append(f)
  prev=nxt
 proxies=[]
 for e in [e for e in es if e['type'] in ['pointermove','wheel']]:
  f=next((f for f in changes if f['observedAt']>=e['capturedAt']),None)
  proxies.append({'inputId':e['id'],'observedAt':f['observedAt'] if f else None,'inputToObservedChangeProxyMs':f['observedAt']-e['eventAt'] if f else None,'presentedPaintCertified':False,'causalInputIdentified':False})
 eq(proxies,rv['continuousProxies'],'independent continuous proxy values');eq(len(moves),rv['trustedPointerMoves'],'trusted move count');eq(len(es),rv['trustedInputs'],'trusted input count');eq(False,rv['cancelled'],'no active cancel classifier')
 tasks=[x for x in r['longTasks'] if x['at']<t['finishedAt'] and x['at']+x['durationMs']>b['at']];eq(len(tasks),rv['activeLongTasks'],'active long task count');eq(max(x['durationMs'] for x in tasks) if tasks else None,rv['maxActiveLongTaskMs'],'active long task max')
 if op=='toggle':
  eq(d['target']['kind'],'toggle','toggle trigger');eq(d['target']['nodeId'],network,'toggle exact target');eq((len(b['visibleIds']),len(c['visibleIds'])),(4,304),'rendered frontier 4 to 304');eq(rev,1,'toggle revision');eq(b['camera'],c['camera'],'toggle camera exact');check(network not in b['expandedIds'] and network in c['expandedIds'],'network expanded');success=True
 elif op=='pan':
  eq(d['target']['kind'],'viewport','pan viewport trigger');eq(d['target']['canvasTool'],'pan','public pan mode');eq(d['target']['handToolPressed'],True,'hand tool pressed');eq(len(moves),8,'eight pan moves');eq(rev,0,'pan no document revision');eq(delta,dict(x=0,y=0,width=0,height=0),'pan canvas target unchanged')
  for k in ['svgMarkup','visibleIds','expandedIds','pinnedIds','selectionMarkup']:eq(b[k],c[k],'pan full public continuity '+k)
  pd={k:(u[k]-u['viewport'][k])-(d[k]-d['viewport'][k]) for k in ['x','y']};eq(pd,dict(x=40,y=24),'recorded pan terminal delta');expected={**b['camera']['matrix'],'e':b['camera']['matrix']['e']+pd['x'],'f':b['camera']['matrix']['f']+pd['y']};eq(expected,c['camera']['matrix'],'pan camera exact');eq(rv['panTerminal']['expectedCamera'],expected,'validator expected terminal camera');success=True
 else:
  eq(b['camera'],c['camera'],op+' camera unchanged');eq(b['visibleIds'],c['visibleIds'],op+' frontier unchanged');eq(b['expandedIds'],c['expandedIds'],op+' expansion unchanged');eq(rev,1,op+' one committed revision')
  if op=='drag':
   eq(d['target']['kind'],'node','drag actual body');eq(d['target']['nodeId'],target,'drag exact Linear1');eq(d['target']['canvasTool'],'select','drag selection tool');eq(len(moves),8,'eight drag moves');eq(delta,dict(x=40,y=24,width=0,height=0),'Linear1 actual canvas move');scale=b['camera']['matrix']['a'];native={'x':(u['x']-u['viewport']['x'])-(d['x']-d['viewport']['x']),'y':(u['y']-u['viewport']['y'])-(d['y']-d['viewport']['y'])};eq(native,dict(x=30,y=18),'actual drag client delta');eq({k:math.floor(native[k]/scale/4+.5)*4 for k in ['x','y']},dict(x=40,y=24),'snap independent transform');success=True
  else:eq(d['target']['action'],op,'actual undo/redo toolbar');eq(delta,dict(x=-40 if op=='undo' else 40,y=-24 if op=='undo' else 24,width=0,height=0),'history body delta');success=True
 eq(success,rv['operationSucceeded'],'independent requested success')
 dur=u['eventAt']-d['eventAt'];boundedchanges=[f for f in changes if d['capturedAt']<=f['observedAt']<=u['capturedAt']]
 windows.append({'trialId':t['id'],'operation':op,'actualTargetKind':d['target']['kind'],'actualTargetNodeId':d['target']['nodeId'],'downInputId':d['id'],'upInputId':u['id'],'pointerId':d['pointerId'],'downEventAt':d['eventAt'],'upEventAt':u['eventAt'],'downToUpEventWindowMs':dur,'downCoordinates':{'x':d['x'],'y':d['y'],'viewport':d['viewport']},'upCoordinates':{'x':u['x'],'y':u['y'],'viewport':u['viewport']},'trustedMoves':len(moves),'coalescedSamples':sum(len(e.get('coalesced',[])) for e in moves),'eventToCaptureMoveMs':[e['capturedAt']-e['eventAt'] for e in moves],'eventTimestampWindow':{**cad(eventframes),'times':[f['at'] for f in eventframes],'callbacksPerActualEventWindowSecond':len(eventframes)*1000/dur if dur else None},'observedTimestampWindow':{**cad(obsframes),'geometryChangeCount':len(boundedchanges),'changedObservedAt':[f['observedAt'] for f in boundedchanges]},'postUpInterruptEvents':[{'id':e['id'],'type':e['type'],'eventAt':e['eventAt'],'capturedAt':e['capturedAt']} for e in es[es.index(u)+1:] if e['type'] in ['blur','lostpointercapture','pointercancel']], 'activeCancellationCount':0,'presentedFramesCertified':False,'humanDurationCertified':False})
 _,_,_,bb=xml(b['svgMarkup']);_,_,_,cb=xml(c['svgMarkup'])
 changedbody={i:{'before':bb[i],'after':cb[i]} for i in bb.keys()&cb.keys() if bb[i]!=cb[i]}
 trialchecks.append({'id':t['id'],'operation':op,'operationSucceeded':success,'revisionBefore':b['revision'],'revisionAfter':c['revision'],'canvasTargetDelta':delta,'fullTrialCallbackCadence':cad(fullframes),'trialDurationIncludingPreparationMs':t['finishedAt']-t['armedAt'],'activeLongTasks':tasks,'changedRenderedBodies':changedbody,'fullSvgChangedExceptRevision':norm(b['svgMarkup'])!=norm(c['svgMarkup'])})
drag,undo,redo=r['trials'][2:];rest=[]
for name,l,z in [('undo-restores-pre-drag',drag['before'],undo['after']),('redo-restores-moved',drag['after'],redo['after']),('drag-after-equals-undo-before',drag['after'],undo['before']),('undo-after-equals-redo-before',undo['after'],redo['before'])]:
 eq(norm(l['svgMarkup']),norm(z['svgMarkup']),name+' full SVG exact except revisions')
 for k in ['objects','camera','visibleIds','expandedIds','pinnedIds','selectionMarkup','canvasTool','handToolPressed','sourceDigest','irDigest','documentId']:eq(l[k],z[k],name+' '+k)
 rest.append({'pair':name,'leftRevision':l['revision'],'rightRevision':z['revision'],'fullSvgExactExceptTwoRevisionScalars':True,'objectsCameraSelectionFrontierToolSourceIrExact':True,'normalizedSvgSha256':sha(norm(l['svgMarkup']).encode())})
readlength=len(fr(rawpath).decode().encode('utf-16-le'))//2;eq(readlength,read['length'],'saved raw JS UTF16 length exact');eq(len(read['ranges']),131,'131 actual read ranges');eq(read['ranges'][0]['start'],0,'slice starts zero');eq(read['ranges'][-1]['end'],readlength,'slice ends exact length')
for a1,b1 in zip(read['ranges'],read['ranges'][1:]):eq(a1['end'],b1['start'],'contiguous slice journal')
# Fresh validator from the same frozen source/raw bytes, temp only; compare complete JSON.
with tempfile.TemporaryDirectory(prefix='archcanvas-visible-audit-') as td:
 p=Path(td);(p/'validator.mjs').write_bytes(fr(vp));(p/'raw.json').write_bytes(fr(rawpath));f=subprocess.run(['node',str(p/'validator.mjs'),str(p/'raw.json')],capture_output=True,timeout=30)
eq(f.returncode,0,'fresh offline validator exit');eq(json.loads(f.stdout),v,'fresh validator entire parsed output');eq(f.stderr,fr(HERE/'product-validation-stderr.txt'),'fresh stderr exact')
for p,b in FROZEN.items():eq(p.read_bytes(),b,'frozen input unchanged '+str(p))
ended=datetime.datetime.now(datetime.timezone.utc).isoformat()
out={'schema':'archcanvas-hierarchy-visible-product-independent-audit/1','status':'passed-scoped-diagnostic-with-visibility-false-and-performance-gates-open','auditStartedAt':started,'auditEndedAt':ended,
 'scope':'Read-only five-trial native/raw/public SVG and same-frozen-source validation; no browser operation, actual response body capture, presented performance, persistence or human certification.',
 'hashedBytesAreParsedBytes':True,'allScopedInputsUnchanged':True,'scopedInputCount':len(FROZEN),'sourceBindings':[bind(p) for p in sorted(FROZEN)],
 'raw':bind(rawpath),'rawCharactersUtf16':readlength,'rawReadJournal':bind(HERE/'receipt-read-v2.json'),'earlierReadJournalPreserved':bind(HERE/'receipt-read.json'),'rawReadFailureTranscription':{'corrected':read['firstAttempt'],'correctionScope':read['corrects'],'fullOriginalFailedToolLogsCaptured':False},'rawReadRanges':131,'receiptReadLimit':'Journal continuity/length proves captured file matches declared count; it does not independently reproduce browser acquisition.',
 'freshValidator':{'exitCode':f.returncode,'completeParsedOutputExact':True,'stdoutBytes':len(f.stdout),'stdoutSha256':sha(f.stdout),'stderrExact':True},
 'contextDiskBindings':ctx,'buildContextExact':True,'declaredAssetNetworkBodySeparatelyCaptured':False,
 'sourceFacts':{'entry':a['entry'],'canonicalNodes':len(a['nodes']),'canonicalEdges':len(a['edges']),'sourceDigest':a['sourceDigest'],'irDigest':a['irDigest'],'authoredLayerDeclarations':300,'fullSnapshotsChecked':len(full),'sourceFactsEachSnapshot':304,'sourceAndIrIndependentlyRecomputed':True,'architectureReference':bind('docs/evidence/m4-hierarchy-optimization/react-probe-dist/fixture.json'),'modelExecuted':False},
 'counts':{k:len(r[k]) for k in ['trials','events','frames','eventTiming','longTasks','visibility','errors']},'latency':lat,'trials':trialchecks,'gestureWindows':windows,'snapshots':snapshots,'fullSvgUndoRedoRestoration':rest,
 'sessionCallbackCadence':cad(r['frames']),'sessionStartStopMs':r['stoppedAt']-r['startedAt'],'sessionCallbacksPerStartStopSecond':len(r['frames'])*1000/(r['stoppedAt']-r['startedAt']),
 'visibility':{'capabilitySnapshot':visobs,'documentStates':sorted(set(x['state'] for x in r['visibility'])),'iframeFocusValues':sorted(set(x['hasFocus'] for x in r['visibility'])),'topFocusValues':sorted(set(x['topHasFocus'] for x in r['visibility'])),'rawLabel':r['label'],'labelIsSuccessfulVisibilityEvidence':False,'hostPresentationCertified':False},
 'coordinates':{'viewport':r['environment']['viewport'],'frameRects':sorted(set(json.dumps(g['frameRect'],sort_keys=True) for _,g in full)),'publicScreenIsIframeClientCSSPixels':True,'fixedHostScreenCertified':False},
 'fontLoading':r['environment']['fonts'],'pinProtectionMeasured':False,'nativeActiveCancellationTested':False,'saveReopenTested':False,'humanParticipants':0,'performanceGateCertified':False,'presentedFrameRateCertified':False,'continuousInputToPaintCertified':False,'hardwareAndResolvedBrowserFontsCertified':False,'screenshotsPixelAudited':False,
 'limits':['Capability product-before/product-after/after-display-request is false; visible label is experiment intent only, not successful display.', 'Matched subset p95 4008ms is five interactions, not overall INP or representative full performance p95; drag down is missing and remains null.', 'rAF cadence and DOM proxies are not presented FPS or causal continuous input-to-paint; coalesced/move times are automation input diagnostics.', 'Rendered frontier304 is not proof that300 bodies simultaneously intersect viewport or are legible.', 'No pins, native active cancellation, current save/reopen or actual human participants.', '11 full SVG snapshots restore public scene/selection/camera/tool; hidden Canvas/history bytes are not exposed here.', 'FrameRect changes y -8 to144; no fixed host-screen continuity claim.', 'Same frozen context hashes do not separately certify HTTP response body/historical service lifecycle.', 'Fresh validators are offline consistency checks, not new browser samples; no suite rerun.']}
(HERE/'independent-product-audit.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
lines=['# 本轮五项产品原生输入独立审核','',f'状态：{out["status"]}。本次未操作浏览器或改product/raw。{len(FROZEN)}输入使用先hash后parse的同份冻结bytes，末尾重读一致；fresh离线validator exit0且完整parsed output exact。','',f'实际服务是8897，当前JS oI5，raw {bind(rawpath)["bytes"]:,}bytes / SHA256 `{bind(rawpath)["sha256"]}`。131个read ranges连续覆盖{readlength:,}UTF16字符，UTF8 bytes不同正常；原getAXState/native frame limit按v2转录保留；v1误归因getAttribute仍保留且只修转录、不改raw，不认证原工具读取过程。','', '## 请求与公共场景恢复','', '| 请求 | 判定 | 原始事实 |','|---|---|---|','| network toggle | true | rev0→1，frontier4→304，camera不变 |','| viewport pan | true | 手工具/可信左键，+40/+24 CSSpx，rev1与完整SVG/frontier/pins/selection不变 |','| 指定Linear1 drag | true | first down确为network.0，client+30/+18经0.789091缩放和4px网格成为canvas+40/+24；rev1→2 |','| undo | true | rev2→3，完整SVG除恰好两个revision标量恢复pre-drag；对象/camera/selection/tool/frontier exact |','| redo | true | rev3→4，完整SVG除两个revision标量恢复moved状态；同字段exact |','', '全文11SVG snapshot的304 canonical sourceFacts、source/IR、XML对象body和frontier映射与冻结正式architecture精确；源码AST独立确认150 Linear/ReLU pairs，source aggregate和IR digest独立重算。Architecture参考是同source的既有正式分析工件；没有导入/执行模型或重新跑frontend。渲染frontier304不等于300对象同时在viewport可读。','', '## 原生匹配与实际手势窗口','',f'全部双向唯一type/target/±8ms/positive interaction配对从raw独立重算：**{lat["eligibleDiscreteInputs"]}eligible /{lat["matchedDiscreteInputs"]}matched /{lat["matchedInteractions"]}interactions；matched subset p95={lat["matchedInteractionP95Ms"]}ms**。每interaction按最大duration仅计一次；drag pointerdown input-38缺失保持null，不能补0或当<50ms。不是整个页面INP、代表性任务p95或连续input-to-paint。','', '| 真实down→up事件窗 | duration ms | trusted moves | event窗口rAF | observed窗口rAF | observed几何变化 |','|---|---:|---:|---:|---:|---:|']
for w in windows:lines.append(f'| {w["operation"]} | {w["downToUpEventWindowMs"]:.4f} | {w["trustedMoves"]} | {w["eventTimestampWindow"]["callbacks"]} | {w["observedTimestampWindow"]["callbacks"]} | {w["observedTimestampWindow"]["geometryChangeCount"]} |')
lines+=['','这些窗口严格使用真实trusted first down与同pointer up，不包括arm/finish外页等待；observedAt窗与eventAt窗分开。Pan/drag有8moves，各coalesced原始值与event→capture延迟列在JSON；输入约7秒是代理自动化事实，不是人类耗时。普通up之后lostcapture、后续blur原样保留，活动区间无Esc/cancel/blur/lostcapture，不计取消。','',f'全session {len(r["frames"])}rAF /{out["sessionStartStopMs"]:.4f}ms；start→stop回调率{out["sessionCallbacksPerStartStopSecond"]:.6f}Hz。完整trial cadence混入准备/等待，validator fps字段与本报告Hz都是回调节奏，不能当presented FPS、掉帧或持续性能通过。','', '## 实际可见性与边界','', '产品前后capability false，display request前false/后false；`visible`label是实验意图。冻结副本[product-audit-visibility-snapshot.json](product-audit-visibility-snapshot.json)保留读取时原bytes；root visibility原路径可能后续追加control-after，本报告不重绑定未来内容。Document观测visible、iframe focus true/false、top focus true，不能否定capability false或证明持续host呈现。','', '11首末snapshot frameRect有y−8/144外页滚动；几何screen为iframe client CSSpx，不能升级固定host屏幕。字体loaded/loadedFaces=[]不认证font文件；hardware未知，无pins/活动取消/保存重开/真人，截图未做像素审核。4条longtask与trial overlap保留，没观测到某条不证明系统无stall。','', '当前数值仍未达声明性能目标；现有工具不能取得presented-frame证据，simplecontrol另采另审，不把两个场景合并、解释成产品已排除或改旧raw。','', '[完整JSON](independent-product-audit.json)列所有sourceBindings、candidate graph、真实window/coordinates、scene恢复、changed bodies及fresh validator摘要。[脚本](independent-product-audit.py)可离线复核本scope；会重写本审计结果，不改输入/product。']
(HERE/'independent-product-audit.md').write_text('\n'.join(lines)+'\n')
print(json.dumps({'status':out['status'],'inputs':len(FROZEN),'latency':{k:lat[k] for k in ['eligibleDiscreteInputs','matchedDiscreteInputs','matchedInteractions','matchedInteractionP95Ms']},'windows':[{'operation':w['operation'],'durationMs':w['downToUpEventWindowMs'],'eventRaf':w['eventTimestampWindow']['callbacks'],'observedChanges':w['observedTimestampWindow']['geometryChangeCount']} for w in windows],'jsonSha256':sha((HERE/'independent-product-audit.json').read_bytes()),'mdSha256':sha((HERE/'independent-product-audit.md').read_bytes())},ensure_ascii=False,indent=2))
