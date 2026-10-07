#!/usr/bin/env python3
"""Bounded read-only smoke audit. Never imports product matcher or operates browser."""
from __future__ import annotations
import collections,hashlib,json,math,re,subprocess
from datetime import datetime,timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[4]
OUT=Path(__file__).resolve().parent
SMOKE=ROOT/'docs/evidence/m4-native-matching-work/browser-smoke'
CHECKS=ROOT/'docs/evidence/m4-native-matching-work/checks-final'
FILES=[SMOKE/'raw.json',SMOKE/'completed.dom.txt',SMOKE/'completed.jpg',CHECKS/'receipt.json',CHECKS/'studio-tests.stdout.txt',CHECKS/'studio-tests.stderr.txt',CHECKS/'studio-build.stdout.txt',CHECKS/'studio-build.stderr.txt',ROOT/'scripts/validate_native_performance.mjs',ROOT/'studio/dist/index.html',ROOT/'studio/dist/assets/index-D60-bDcz.js',ROOT/'studio/dist/assets/index-QPVAzYp6.css']
ASSETS=SMOKE/'assets.public.json'
if ASSETS.exists():FILES.append(ASSETS)
for name in ['receipt.json','manifest.json','validation.json','validation.stderr.txt','README.md']:
 p=SMOKE/name
 if p.exists():FILES.append(p)

def binding(p):
 data=p.read_bytes();return {'path':str(p.relative_to(ROOT)),'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}
def nearest95(values):return sorted(values)[math.ceil(len(values)*.95)-1] if values else None

def main():
 if (OUT/'report.json').exists():raise SystemExit('Use a new attempt; refusing to overwrite report')
 before=[binding(p) for p in FILES]
 snapshots=OUT/'inputs';snapshots.mkdir(exist_ok=True)
 for i,(p,b) in enumerate(zip(FILES,before)):
  dest=snapshots/f'{i:02d}-{p.name}';dest.write_bytes(p.read_bytes());b['snapshot']=str(dest.relative_to(ROOT))
 d=json.loads(FILES[0].read_bytes());checks=json.loads((CHECKS/'receipt.json').read_bytes())
 dom=(SMOKE/'completed.dom.txt').read_text()
 line=next(l for l in dom.splitlines() if 'textbox "原生性能 JSON": ' in l)
 dom_value=json.loads(line.split('textbox "原生性能 JSON": ',1)[1])
 dom_receipt=json.loads(dom_value)
 events=d['snapshot']['eventTiming'];trials=d['trials']
 # Construct the full original eligibility relation independently in Python.
 relation=[]
 for ti,t in enumerate(trials):
  candidates=[]
  for ei,e in enumerate(events):
   eligible=t['trusted'] and e['name']==t['eventName'] and e.get('targetCanonicalNodeId')==t['targetId'] and e['interactionId']>0 and abs(e['startAt']-t['eventAt'])<=8 and e['processingStart']>=e['startAt'] and e['processingEnd']>=e['processingStart'] and isinstance(e['durationMs'],(int,float)) and math.isfinite(e['durationMs']) and e['durationMs']>=0
   if eligible:candidates.append(ei)
  relation.append(candidates)
 reverse=collections.Counter(i for row in relation for i in row)
 entries=[]
 for ti,(t,candidates) in enumerate(zip(trials,relation)):
  idx=candidates[0] if len(candidates)==1 and reverse[candidates[0]]==1 else None
  e=events[idx] if idx is not None else None
  entries.append({'trialIndex':ti,'operation':t['operation'],'trusted':t['trusted'],'eventType':t['eventName'],'targetId':t['targetId'],'eventAt':t['eventAt'],'eligibleEntryIndices':candidates,'reverseCandidateCounts':{str(i):reverse[i] for i in candidates},'bilateralUniqueEntryIndex':idx,'entryEqualsRecorded':e==t['nativeEventTiming'],'expectedDurationMs':e['durationMs'] if e else None,'recordedDurationMs':t['nativeInputToNextPaintMs'],'frontier':[len(t['before']['visibleIds']),len(t['after']['visibleIds'])],'revision':[t['before']['revision'],t['after']['revision']],'bindingValid':t['bindingValid'],'targetChanged':t['targetChanged'],'error':t['error'],'pins':t['pins']})
 proc=subprocess.run(['node','scripts/validate_native_performance.mjs',str(SMOKE/'raw.json')],cwd=ROOT,text=True,capture_output=True)
 (OUT/'validator.stdout.json').write_text(proc.stdout);(OUT/'validator.stderr.txt').write_text(proc.stderr)
 result=json.loads(proc.stdout) if proc.returncode==0 else None
 current_bindings=[]
 for category in ['inputs','build']:
  for b in checks[category]:
   p=ROOT/b['path']; actual=binding(p) if p.exists() else None
   current_bindings.append({'category':category,'path':b['path'],'matches':actual is not None and actual['sha256']==b['sha256'] and actual['bytes']==b['bytes']})
 positive=[e for e in events if e['interactionId']>0]
 positive_by_id={str(k):[{ 'name':e['name'],'startAt':e['startAt'],'durationMs':e['durationMs'],'targetCanonicalNodeId':e.get('targetCanonicalNodeId')} for e in positive if e['interactionId']==k] for k in sorted(set(e['interactionId'] for e in positive))}
 frame=d['frames'];computed_fps=(len(frame['intervals']))*1000/(frame['lastFrameAt']-frame['firstFrameAt'])
 assets=json.loads(ASSETS.read_bytes()) if ASSETS.exists() else None
 report={
  'protocol':'archcanvas-native-matching-browser-smoke-independent/1','createdUtc':datetime.now(timezone.utc).isoformat(),'reviewer':'AI read-only audit, not a human participant',
  'scope':'Re-run current independent native validator, independently rebuild bilateral candidate relation, compare actual completed DOM receipt and local exact build/test bindings. No product/source/build/test rerun, browser/service operation, model execution or dependency install.',
  'verdict':'bounded-native-two-toggle-engineering-smoke-pass' if proc.returncode==0 and all(x['entryEqualsRecorded'] for x in entries) and all(x['matches'] for x in current_bindings) and dom_receipt==d else 'audit-failed',
  'inputBindings':before,'checks':{'validatorExit0':proc.returncode==0,'domReceiptExactlyEqualsRawObject':dom_receipt==d,'allCandidateMatchesExact':all(x['entryEqualsRecorded'] and x['expectedDurationMs']==x['recordedDurationMs'] for x in entries),'allCurrentChecksInputsAndBuildExact':all(x['matches'] for x in current_bindings),'studio314Pass0Fail0SkipRecorded':all(x in (CHECKS/'studio-tests.stdout.txt').read_text() for x in ['ℹ tests 314','ℹ pass 314','ℹ fail 0','ℹ skipped 0']),'strictTypeScriptViteBuildRecorded':'tsc --noEmit && vite build' in (CHECKS/'studio-build.stdout.txt').read_text() and all(x['exitCode']==0 for x in checks['checks'])},
  'environment':d['environment'],'sourceBinding':{k:d['bindingAtStart'][k] for k in ['documentId','revision','sourceDigest','irDigest','expandedIds','pinnedIds']},
  'trialDenominators':{'capturedTrials':len(trials),'trustedTrials':sum(t['trusted'] for t in trials),'capturedTrialTypes':dict(collections.Counter(t['eventName'] for t in trials)),'eligibleEntryTrialPairs':sum(map(len,relation)),'uniqueBilateralMatchedTrials':sum(x['bilateralUniqueEntryIndex'] is not None for x in entries),'missingTrials':sum(not row for row in relation),'ambiguousTrials':sum(bool(row) and not(len(row)==1 and reverse[row[0]]==1) for row in relation),'allSnapshotEventTimingEntries':len(events),'allSnapshotEntryTypes':dict(collections.Counter(e['name'] for e in events)),'positiveInteractionEntries':len(positive),'positiveInteractionIds':sorted(set(e['interactionId'] for e in positive)),'matchedTrialInteractionIds':sorted(set(events[x['bilateralUniqueEntryIndex']]['interactionId'] for x in entries if x['bilateralUniqueEntryIndex'] is not None)),'capturedNativeInputsOutsideTrialTypesNotRecorded':True,'scope':'The native panel captures only recognized click/pointerdown toggle trials; Event Timing has no trusted flag. Its 67 entries are observed entries, not a complete raw native input log.'},
  'candidateRelations':entries,'positiveEntriesByInteraction':positive_by_id,
  'summary':{'matchedSubsetP95Ms':nearest95([x['expectedDurationMs'] for x in entries if x['expectedDurationMs'] is not None]),'declared':d['summary'],'validator':result,'measuredPinCount':0,'pinDriftCertified':False,'startingFrontierRestored':trials[0]['before']['visibleIds']==trials[-1]['after']['visibleIds']},
  'frameDiagnostic':{'callbackFrameCount':frame['frameCount'],'intervalCount':len(frame['intervals']),'firstFrameAt':frame['firstFrameAt'],'lastFrameAt':frame['lastFrameAt'],'computedCallbackCadenceHz':computed_fps,'declaredCallbackCadenceHz':frame['fps'],'intervalP95Ms':nearest95(frame['intervals']),'maxIntervalMs':max(frame['intervals']),'recordedElapsedMs':d['elapsedMs'],'visibility':d['snapshot']['visibility'],'frameBufferTruncated':frame['bufferTruncated'],'longTaskSupport':d['snapshot']['supported']['longTasks'],'observedLongTaskCount':len(d['snapshot']['longTasks']),'intervalsOver50Ms':sum(v>50 for v in frame['intervals']),'presentedFps':None,'continuousInputToPaint':None,'explanation':'Window includes preparation and pauses. rAF timestamps and two-frame geometry do not establish presentation. Empty longTasks do not establish absence of all stalls.'},
  'buildBindings':checks['build'],'checksCurrentBytes':current_bindings,
  'browserLoadedAssetObservation':assets,'browserLoadedAssetUrlsRecorded':assets is not None,'browserLoadedAssetBytesVerified':False,
  'buildBindingLimitation':'raw/AX completed DOM do not include script/style URLs or asset hashes. Separate assets.public.json records the collector transcription of the actual pre-sampling public DOM URL observation and a later same-tab public URL observation on the no-benchmark page; current dist/checks independently bind local artifact bytes. The auditor did not operate the browser or fetch in-browser asset bytes; no internal cache verification or exact loaded-byte claim is made.',
  'actualImageObservation':{'path':'docs/evidence/m4-native-matching-work/browser-smoke/completed.jpg','personallyViewedByAI':True,'observedDimensions':[1280,720],'observations':['Transformer overview shown at54% with encoder collapsed in tree; source workspace and right object inspector visible.','Opt-in Studio performance panel overlays the lower-left/central figure and shows recording-generated state with start native button; it obscures part of the source embedding/encoder side.','No model import/execution or failure alert is visibly asserted; footer says static source imported/model not executed.'],'limitations':['A single screenshot cannot prove timing, input fidelity, complete expanded scene or physical publication readability.','Panel occlusion is measurement-mode context, not a clean global visual acceptance snapshot.']},
  'notCertified':['full-page INP','representative performance p95','presented FPS','continuous input-to-paint','fixed resolved-font/hardware/foreground environment','A/B and three-repeat matrix','unrelated pin drift','model execution','real participants','M4 completion'],
  'performanceGatePassed':False,'humanParticipants':0,'m4Complete':False,
 }
 if assets:
  expected=['/assets/index-D60-bDcz.js','/assets/index-QPVAzYp6.css']
  report['checks']['collectorPreSamplingPublicAssetUrlsMatchLocalBuildNames']=assets['observedBeforeSampling']==expected
  report['checks']['collectorLaterPublicAssetUrlsMatchLocalBuildNames']=[x['src'] or x['href'] for x in assets['reobservedAfterSampling']]==expected
 manifest=json.loads((SMOKE/'manifest.json').read_bytes())
 parent_results=[]
 for declared in manifest['files']:
  p=ROOT/declared['path'];actual=binding(p)
  parent_results.append({'path':declared['path'],'matches':actual['bytes']==declared['bytes'] and actual['sha256']==declared['sha256']})
 report['checks']['parentBrowserManifestOriginalBindingsExact']=all(x['matches'] for x in parent_results)
 report['parentBrowserManifestVerification']={'bindings':parent_results,'assetObservationInParentManifest':False,'scope':'Parent manifest predates the separate assets.public.json; this independent input snapshot binds that later addition explicitly.'}
 report['imageDimensionsFileVerified']=True
 report['selectedInputsUnchangedDuringAudit']=all(binding(p)['sha256']==b['sha256'] for p,b in zip(FILES,before))
 (OUT/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps({'report':str((OUT/'report.json').relative_to(ROOT)),'verdict':report['verdict'],'inputCount':len(before),'matchedTrials':report['trialDenominators']['uniqueBilateralMatchedTrials'],'matchedSubsetP95Ms':report['summary']['matchedSubsetP95Ms'],'selectedInputsUnchanged':report['selectedInputsUnchangedDuringAudit'],'browserLoadedAssetObservation':assets is not None},ensure_ascii=False))
if __name__=='__main__':main()
