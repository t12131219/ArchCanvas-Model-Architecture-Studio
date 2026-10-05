#!/usr/bin/env python3
"""Independent read-only frozen control receipt audit; no browser/product imports."""
from pathlib import Path
import datetime,hashlib,json,math,subprocess,tempfile
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2];BYTES={}
def sha(b):return hashlib.sha256(b).hexdigest()
def freeze(p):
 p=Path(p);p=p if p.is_absolute() else ROOT/p;p=p.resolve()
 if p not in BYTES:BYTES[p]=p.read_bytes()
 sha(BYTES[p]);return BYTES[p]
def j(p):return json.loads(freeze(p))
def bnd(p):
 p=Path(p);p=p if p.is_absolute() else ROOT/p;p=p.resolve();b=freeze(p)
 return {'path':str(p.relative_to(ROOT)),'bytes':len(b),'sha256':sha(b)}
def require(c,m):
 if not c:raise AssertionError(m)
def exact(a,b,m):require(a==b,m)
def rnd(x):return round(x,6)
def dist(v):
 if not v:return dict(samples=0,minMs=None,meanMs=None,p50Ms=None,p95Ms=None,p99Ms=None,maxMs=None,sumMs=None)
 s=sorted(v);return {'samples':len(v),'minMs':rnd(s[0]),'meanMs':rnd(sum(v)/len(v)),'p50Ms':rnd(s[math.ceil(len(s)*.5)-1]),'p95Ms':rnd(s[math.ceil(len(s)*.95)-1]),'p99Ms':rnd(s[math.ceil(len(s)*.99)-1]),'maxMs':rnd(s[-1]),'sumMs':rnd(sum(v))}
started=datetime.datetime.now(datetime.timezone.utc).isoformat()
rp=HERE/'control-raw.json';vp=ROOT/'scripts/validate_scheduling_control.mjs';r=j(rp);v=j(HERE/'control-validation.json');freeze(vp);freeze(__file__);freeze(HERE/'control-validation-stderr.txt')
product=j(HERE/'independent-product-audit.json');visibility=j(HERE/'visibility-readings.json')
context=[]
for category in ['productionAssets','probeSources']:
 for d in r['context'][category]:
  actual=bnd(d['path']);exact(actual,d,'declared context exact '+d['path']);context.append({'category':category,**actual})
exact(v['inputBinding'],bnd(rp),'saved raw input binding');exact(v['validatorBinding'],bnd(vp),'saved validator binding')
exact(r['schema'],'archcanvas-scheduling-control/1','schema');exact(r['stopReason'],'timer-20-seconds','actual automatic stop');exact(r['viewport'],dict(width=1280,height=720,dpr=1),'actual viewport');exact(r['environmentChanges'],[],'no recorded env change');exact(r['truncated'],{},'no truncated flags')
t=r['frames'];iv=[z-a for a,z in zip(t,t[1:])];window=r['stoppedAt']-r['startedAt'];exact(window,20000.399999976158,'actual raw twenty-second window');exact(len(t),38,'actual38 timestamps')
exact(dist(iv),v['frameCadence']['intervalDistribution'],'nearest rank distribution exact')
bins=dict(lte20Ms=0,gt20Lte50Ms=0,gt50Lte100Ms=0,gt100Lte500Ms=0,gt500Ms=0)
for x in iv:bins['lte20Ms' if x<=20 else 'gt20Lte50Ms' if x<=50 else 'gt50Lte100Ms' if x<=100 else 'gt100Lte500Ms' if x<=500 else 'gt500Ms']+=1
exact(bins,v['frameCadence']['intervalBins'],'interval bins exact')
buckets=[];i=0
while r['startedAt']+i*1000<r['stoppedAt']:
 a=r['startedAt']+i*1000;z=min(a+1000,r['stoppedAt']);buckets.append({'index':i,'startAt':a,'endAt':z,'durationMs':rnd(z-a),'completeOneSecondWindow':z==a+1000,'callbacks':sum(a<=x<z for x in t)});i+=1
exact(buckets,v['frameCadence']['oneSecondWindows'],'every one-second/tail window exact')
exactframes=[x for x in t if r['startedAt']<=x<r['stoppedAt']]
rate=rnd(len(exactframes)*1000/window);cad=rnd(len(iv)*1000/(t[-1]-t[0]));exact(rate,v['frameCadence']['callbackRateOverExactSessionWindowHz'],'exact session callback rate');exact(cad,v['frameCadence']['intervalCadenceHz'],'first-last callback cadence')
gaps=[{'frameIndexBefore':i,'frameIndexAfter':i+1,'startAt':t[i],'endAt':t[i+1],'durationMs':rnd(x)} for i,x in enumerate(iv) if x>100]
exact(gaps,v['frameCadence']['gapsOver100Ms'],'all long callback gaps exact');exact(v['frameCadence']['presentedFrameRateHz'],None,'presented fps null');exact(v['frameCadence']['estimatedMissedPresentedFrames'],None,'missed presented frames null')
# Bidirectional candidates for all captured trusted target inputs; ignore nonmatching start PO entries.
e=[(i,x) for i,x in enumerate(r['inputs']) if x['trusted'] and x['targetId']=='target'];candidates={};uses={}
for i,x in e:
 c=[z for z,n in enumerate(r['eventTiming']) if n['interactionId']>0 and n['targetId']=='target' and n['name']==x['type'] and abs(n['startTime']-x['at'])<=8];candidates[i]=c
 for z in c:uses.setdefault(z,[]).append(i)
match=[];interactions={}
for i,x in e:
 c=candidates[i];z=c[0] if len(c)==1 and len(uses[c[0]])==1 else None;n=r['eventTiming'][z] if z is not None else None
 m={'rawInputIndex':i,'type':x['type'],'targetId':'target','trusted':True,'inputAt':x['at'],'capturedAt':x['capturedAt'],'inputCaptureDelayMs':rnd(x['capturedAt']-x['at']),'candidateNativeEntryIndexes':c,'nativeEntryIndex':z,'nativeDurationMs':n['duration'] if n else None,'interactionId':n['interactionId'] if n else None,'nativeInputQueueMs':rnd(n['processingStart']-n['startTime']) if n else None,'nativeProcessingMs':rnd(n['processingEnd']-n['processingStart']) if n else None,'missingReason':None if n else 'unavailable-below-threshold-detached-or-unobserved'};match.append(m)
 if n:interactions[n['interactionId']]=max(interactions.get(n['interactionId'],0),n['duration'])
exact(match,v['eventTiming']['matches'],'all native match/cost scalars exact');exact(len(match),3,'three trusted target inputs');exact(len(interactions),1,'one actual interaction');exact(dist(list(interactions.values())),v['eventTiming']['matchedInteractionDurationDistribution'],'native interaction duration distribution exact')
exact(r['inputs'][1]['at']-r['inputs'][0]['at'],1,'actual down-up1ms')
for key in ['rafCallbackCosts','inputCallbackCosts','performanceCallbackCosts']:
 expected={**dist(r[key]),'completeCapturedBuffer':True};exact(expected,v['callbackSelfCost']['categories'][key],'independent local cost distribution '+key)
# Fresh cloned validator/raw. Compare all semantic fields; CLI run metadata and paths have honest new values.
with tempfile.TemporaryDirectory(prefix='archcanvas-visible-control-audit-') as td:
 p=Path(td);(p/'validator.mjs').write_bytes(freeze(vp));(p/'raw.json').write_bytes(freeze(rp));f=subprocess.run(['node',str(p/'validator.mjs'),str(p/'raw.json'),'--root',str(ROOT)],capture_output=True,timeout=30)
exact(f.returncode,0,'fresh validator exit0');fv=json.loads(f.stdout)
excluded=['inputBinding','validatorBinding','validationRuntime']
for key in set(v)|set(fv):
 if key not in excluded:exact(fv.get(key),v.get(key),'fresh complete semantic field '+key)
exact(f.stderr,freeze(HERE/'control-validation-stderr.txt'),'fresh stderr exact')
for p,b in BYTES.items():exact(p.read_bytes(),b,'all frozen inputs stable '+str(p))
ended=datetime.datetime.now(datetime.timezone.utc).isoformat()
result={'schema':'archcanvas-hierarchy-visible-control-independent-audit/1','status':'passed-scoped-control-with-visibility-false-and-no-studio-exoneration','auditStartedAt':started,'auditEndedAt':ended,'scope':'Independent frozen-byte raw/callback/native matching and fresh offline validator; no browser replay, product change, screenshot pixel review, complete CPU cause or presented performance claim.',
 'hashedBytesAreParsedBytes':True,'allInputsUnchanged':True,'sourceBindingCount':len(BYTES),'sourceBindings':[bnd(p) for p in sorted(BYTES)],'raw':bnd(rp),'contextDiskBindings':context,
 'freshValidator':{'exitCode':f.returncode,'allSemanticFieldsExact':True,'excludedFreshCliMetadataFields':excluded,'savedRawAndValidatorBindingsIndependentlyExact':True,'stdoutBytes':len(f.stdout),'stdoutSha256':sha(f.stdout),'stderrExact':True},
 'window':{'startedAt':r['startedAt'],'stoppedAt':r['stoppedAt'],'durationMs':window,'stopReason':r['stopReason'],'actualTrustedTargetDownUpMs':r['inputs'][1]['at']-r['inputs'][0]['at']},
 'frames':{'timestamps':len(t),'intervals':len(iv),'distribution':dist(iv),'bins':bins,'callbackRateExactSessionHz':rate,'firstLastCallbackCadenceHz':cad,'secondBuckets':buckets,'gapsOver100Ms':gaps,'presentedFrameRateHz':None,'estimatedMissedPresentedFrames':None},
 'native':{'capturedTrustedEligibleTargetInputs':len(match),'matchedInputs':sum(m['nativeEntryIndex'] is not None for m in match),'matchedInteractions':len(interactions),'interactionMaximumDurationMs':interactions,'durationDistribution':dist(list(interactions.values())),'matches':match,'rawNativeEntries':len(r['eventTiming']),'startButtonCapturedInputs':sum(x['targetId']=='start' for x in r['inputs']),'overallINP':None,'continuousInputToPaintMs':None},
 'environment':{'viewport':r['viewport'],'userAgent':r['userAgent'],'hardwareConcurrency':r['hardwareConcurrency'],'beginDocument':r['beginEnvironment'],'endDocument':r['endEnvironment'],'recordedChanges':r['environmentChanges'],'hardwarePhysicallyLocked':False,'resolvedBrowserFontsCertified':False},
 'visibility':{'rawCapabilityFile':bnd(HERE/'visibility-readings.json'),'allReadings':visibility,'controlReadings':[x for x in visibility if x['phase'].startswith('control-')],'validatorConsumedVisibilityFile':v.get('visibilityInputBinding') is not None,'savedValidatorHostPresentation':v['environment']['hostPresentation'],'hostPresentationCertified':False},
 'callbackSelfCost':v['callbackSelfCost'],'comparisonToProduct':{'productAudit':bnd(HERE/'independent-product-audit.json'),'productLatencies':{k:product['latency'][k] for k in ['eligibleDiscreteInputs','matchedDiscreteInputs','matchedInteractions','matchedInteractionP95Ms']},'productSessionCallbackRateHz':product['sessionCallbacksPerStartStopSecond'],'controlNativeSingleInteractionMs':list(interactions.values())[0],'controlExactWindowCallbackRateHz':rate,'productIsSameOriginIframe':True,'controlIsTopLevel':True,'sharedNominalOuterViewport':{'width':1280,'height':720,'dpr':1},'simultaneousRandomizedEquivalentWindows':False,'schedulingCauseEstablished':False,'studioWorkloadExcluded':False},
 'longTasksObserved':None,'longTaskObserverExistsInControl':False,'humanParticipants':0,'humanCertified':False,'studioPerformanceCertified':False,'presentedFrameRateCertified':False,'pixelReviewPerformed':False,
 'limits':['Capability before/after false despite raw document visible/focused; no successful continuous host presentation.', '38 rAF callbacks in20s,37 intervals and seconds1,1,then eighteen2-callback buckets are callback scheduling only; not presented frames/FPS.', 'All three target inputs map to one2008ms interaction, not three interactions or representative p95/overall INP.', 'Control has no React/SVG/model/Studio telemetry but differs from product iframe and is a sequential nonrandom window; it cannot exonerate product costs or locate scheduler cause.', 'Control module does not subscribe longtask; absence of field is unknown, not zero longtasks.', 'Local callback costs omit browser delivery/rendering/timer/target-handler/system; zero quantized samples do not prove zero overhead.', 'Fresh CLI runtime/binding path fields differ honestly; saved original bindings independently exact. No browser/sample/suite rerun.']}
(HERE/'independent-control-audit.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
md=f'''# 本轮一次20秒simple control独立审核

状态：**{result['status']}**。本审计未操作浏览器、重采窗口或改product/raw；{len(BYTES)}个输入先hash后parse同份冻结bytes，末读全部稳定。新的离线validator exit0、全部semantic字段exact；fresh inputBinding/validatorBinding/runtime反映临时路径/新时刻，三类metadata明确排除对等，原saved绑定另独立核准确。

Raw {bnd(rp)['bytes']}bytes，SHA256 `{bnd(rp)['sha256']}`。实际自动`timer-20-seconds`窗为{window:.4f}ms。

| 事实 | 独立重算 |
|---|---:|
| rAF timestamps/intervals | 38 /37 |
| interval p50/p95/max | {dist(iv)['p50Ms']} /{dist(iv)['p95Ms']} /{dist(iv)['maxMs']}ms |
| ≤20ms / >500ms间隔 | {bins['lte20Ms']} /{bins['gt500Ms']} |
| exact start→stop callback rate | {rate}Hz |
| first→last interval cadence | {cad}Hz |
| 一秒桶 | 前2秒各1；之后18秒各2；0.4ms尾桶0 |
| trusted target inputs/matched | 3 /3 |
| matched interactions | 1 |
| native interaction maximum duration | 2008ms |
| target真实down→up | 1ms |

三个pointerdown/up/click共interaction5202，duration均2008ms。native双向唯一type/target/±8ms匹配和queue/processing独立精确；start按钮2条PO记录没有captured start input，不填目标分母。单interaction的p95=2008仅是本有界样本，不是代表性p95或整个页面INP。rAF按每秒桶保留长期低频，不用均值/某个16.6ms间隔掩盖stall；presentedFrameRate/掉帧/continuousInputToPaint均null。

实际viewport1280×720/DPR1、Chrome154/Linux、hardwareConcurrency16；这些不锁定真实硬件/字体。document start/end visible/focused、changes空，宿主capability control-before/control-after均**false**。root display request仍false，实验label或document visible不能证明向用户持续呈现。saved validator没摄入另存capability文件，hostPresentation仍unconfirmed；本报告新增其原bytes绑定和精确读数，不改原validator/raw。

simple页面没有React/SVG/model/Studio telemetry，但它是top-level、产品是iframe，采样非同时、非随机；相同名义viewport与两者低频只能支持环境/调度疑点。**不能因此排除产品SVG替换、React、telemetry或renderer成本，不能定位CUA/宿主/系统/产品因果，也不能用control清除失败性能门。** 产品另保持14/13/5、p95=4008ms与精确公共SVGundo/redo恢复；两个分母不合并。

control没有longtask订阅/字段，不当0长任务。局部callback成本不含浏览器delivery、rescheduling、rendering、timer、target handler或系统总成本，量化0不是零开销。截图未做像素审核，无真人、字体/硬件认证或持续presented FPS。此次独立报告和本轮一窗已足够记录该诊断，不建议在条件未变时重复直到出现较快结果。

[完整JSON](independent-control-audit.json)保留全部frames/native配对、秒桶、bindings、vis读数与fresh差异范围；[脚本](independent-control-audit.py)离线复核本scope，不改输入或产品。
'''
(HERE/'independent-control-audit.md').write_text(md)
print(json.dumps({'status':result['status'],'inputs':len(BYTES),'callbacks':len(t),'windowMs':window,'matchedInputs':3,'interactions':1,'durationMs':2008,'jsonSha256':sha((HERE/'independent-control-audit.json').read_bytes()),'mdSha256':sha((HERE/'independent-control-audit.md').read_bytes())},ensure_ascii=False,indent=2))
