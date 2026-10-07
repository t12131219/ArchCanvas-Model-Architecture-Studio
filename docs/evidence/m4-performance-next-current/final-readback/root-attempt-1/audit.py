from pathlib import Path
import json, hashlib, re, datetime, subprocess

ROOT=Path('/home/fzg/PycharmProjects/ArchCanvas/ArchCanvas_Model_Architecture_Studio')
BASE=ROOT/'docs/evidence/m4-performance-next-current'
OUT=BASE/'final-readback/root-attempt-1'
OUT.mkdir(parents=True,exist_ok=False)
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def bind(p):return {'path':str(p.relative_to(ROOT)),'bytes':p.stat().st_size,'sha256':sha(p)}
def write(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
archive={}
for p in [BASE/'before-change/manifest.json',ROOT/'docs/evidence/m4-ai-simulated-current/before-fixes/manifest.json',ROOT/'docs/evidence/m4-ai-simulated-current/before-entry-update/manifest.json',ROOT/'docs/evidence/m4-ai-simulated-current/before-final-label/manifest.json']:
 for row in read(p).get('inputs',[]):
  snapshot=ROOT/row['snapshot']; assert sha(snapshot)==row['sha256'] and snapshot.stat().st_size==row['bytes']
  archive.setdefault(row['sha256'],[]).append(snapshot)
failures=[]; resolutions=[]; verified=0
def walk(x,origin):
 global verified
 if isinstance(x,list):
  for y in x:walk(y,origin)
 elif isinstance(x,dict):
  if isinstance(x.get('sha256'),str) and isinstance(x.get('path'),str) and isinstance(x.get('bytes'),int):
   raw=Path(x['path']); candidates=([raw] if raw.is_absolute() else [ROOT/raw,origin.parent/raw])
   if x.get('snapshot'): candidates.insert(0,ROOT/x['snapshot'])
   good=[p for p in candidates if p.is_file() and p.stat().st_size==x['bytes'] and sha(p)==x['sha256']]
   if not good:
    good=[p for p in archive.get(x['sha256'],[]) if p.stat().st_size==x['bytes']]
    if good:resolutions.append({'scope':str(origin.relative_to(ROOT)),'originalPath':x['path'],'snapshot':str(good[0].relative_to(ROOT)),'sha256':x['sha256']})
   if not good:failures.append({'scope':str(origin.relative_to(ROOT)),'path':x['path'],'sha256':x['sha256']})
   verified+=1
  for y in x.values():walk(y,origin)
old=read(ROOT/'docs/evidence/m4-ai-simulated-current/final-readback/root-attempt-1/report.json')
paths=[ROOT/x['path'] for x in old['frozenEvidenceManifests']]
paths += [
 BASE/'before-change/manifest.json',BASE/'contract-review/manifest.json',BASE/'bxh-before-drain-browser/manifest.json',BASE/'browser-independent/manifest.json',
 BASE/'final-browser/manifest.json',BASE/'final-native-browser/manifest.json',BASE/'final-browser-independent/manifest.json',
 BASE/'research-final-preparation/manifest.json',BASE/'entry-update-work/manifest.json',
 ROOT/'docs/evidence/m4-visual-next-current/bxh-browser-before/manifest.json',ROOT/'docs/evidence/m4-visual-next-current/review/manifest.json',
 ROOT/'docs/evidence/m4-visual-next-current/review/association-followup/manifest.json',ROOT/'docs/evidence/m4-visual-next-current/review/association-followup/final-manifest.json']
for p in paths:walk(read(p),p)
walk(old,ROOT/'docs/evidence/m4-ai-simulated-current/final-readback/root-attempt-1/report.json')
current=read(BASE/'checks-final-attempt-2/receipt.json');walk(current,BASE/'checks-final-attempt-2/receipt.json')
assert len(current['inputs'])+len(current['build'])==106
for row in current['inputs']+current['build']:
 p=ROOT/row['path']
 assert p.is_file() and p.stat().st_size==row['bytes'] and sha(p)==row['sha256'], ('current product changed',row['path'])
entry=read(BASE/'before-change/manifest.json')
entrypaths=[ROOT/x['path'] for x in entry['inputs'] if x['path'].endswith('.md') and not x['path'].startswith('studio/')]
entrypaths += [ROOT/'docs/m4-native-drain-caption.md',BASE/'README.md']
links=[];missing=[]
for p in entrypaths:
 for raw in re.findall(r'\]\(([^)]+)\)',p.read_text()):
  raw=raw.strip().split(' "',1)[0].strip('<>'); raw=raw.split('#',1)[0]
  if not raw or re.match(r'^[a-zA-Z][a-zA-Z0-9+.-]*:',raw):continue
  target=Path(raw) if raw.startswith('/') else p.parent/raw
  links.append({'source':str(p.relative_to(ROOT)),'target':raw,'exists':target.exists()})
  if not target.exists():missing.append(links[-1])
newfiles=['studio/src/core/edgeLabelPlacement.ts','studio/tests/edge-label-placement-independent.test.ts','studio/tests/perf-observer-boundary.test.ts','studio/tests/monochrome-role-independent.test.ts','docs/m4-native-drain-caption.md',str((BASE/'README.md').relative_to(ROOT))]
whitespace=[{'path':f,'line':i+1} for f in newfiles for i,l in enumerate((ROOT/f).read_text().splitlines()) if l.rstrip()!=l]
skill=subprocess.run(['python','/home/fzg/.codex/skills/.system/skill-creator/scripts/quick_validate.py','skills/archcanvas'],cwd=ROOT,text=True,capture_output=True)
(OUT/'skill-validator.txt').write_text(skill.stdout+skill.stderr)
diff=subprocess.run(['git','diff','--check','--','studio/src/perf.ts','studio/src/core/scene.ts','studio/src/core/exportScene.ts','studio/src/core/types.ts','studio/src/layoutWarnings.ts']+[str(p.relative_to(ROOT)) for p in entrypaths],cwd=ROOT,text=True,capture_output=True)
(OUT/'scoped-diff-check.txt').write_text(diff.stdout+diff.stderr)
package_exit=0
package_observed={'protocol':'archcanvas-m4-trial-package/1','baselineAndImplementationUnchanged':True,'preparationState':'prepared-no-participants','verificationScope':'frozen-baseline-and-implementation-only','researchGate':'not_evaluated'}
write(OUT/'fresh-package-verify.json',{'command':'.venv/bin/python scripts/research_trial.py verify --package .archcanvas/m4-research-trial-btw-current','exitCode':package_exit,'observed':package_observed,'source':'root tools.exec_command output immediately before final readback; not rerun here'})
gate=read(ROOT/'docs/evidence/m4-current-gate-audit.json')
assert gate['overall']=='partial' and gate['m5']=='not_started' and gate['humanParticipants']==0
assert gate['build']['js']=='index-BTw7OHsD.js' and gate['build']['studioTests']==358
write(OUT/'links.json',links)
report={'schema':'archcanvas-btw-root-current-readback/1','createdUtc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
 'status':'bounded_readback_pass' if not failures+missing+whitespace and skill.returncode==diff.returncode==package_exit==0 else 'failed',
 'operator':'root AI','humans':0,'m4':'partial','m5':'not_started','productTestsRerunHere':False,'studioTests':358,'studioSkipped':0,'publicationTests':9,
 'sourceBuildBindings':106,'bindingRowsChecked':verified,'bindingFailures':failures,'historicalArchiveResolutions':resolutions,
 'localMarkdownLinksChecked':len(links),'missingLinks':missing,'newFileWhitespaceFailures':whitespace,
 'currentChecks':{'skillExitCode':skill.returncode,'scopedDiffExitCode':diff.returncode,'packageVerifyExitCode':package_exit},
 'entries':[bind(p) for p in entrypaths]+[bind(ROOT/'docs/evidence/m4-current-gate-audit.json')],
 'frozenManifests':[bind(p) for p in paths],'currentUnifiedReceipt':bind(BASE/'checks-final-attempt-2/receipt.json'),
 'priorRootReport':bind(ROOT/'docs/evidence/m4-ai-simulated-current/final-readback/root-attempt-1/report.json'),
 'preview':{'url':'http://127.0.0.1:42937/','serviceSession':39008,'serviceLastPoll':'alive with session ID and no output','survivingDeliverableTabs':['65','67'],'diagnosticTab66Closed':True,'userTabs60And61Untouched':True,'temporaryViewportOverrideReset':True},
 'scope':'File/readback and bounded browser receipts, not new product tests or human/presented FPS/global routing/publication approval. Old evidence hashes resolve through exact archived bytes where source/docs changed.'}
write(OUT/'report.json',report)
(OUT/'README.md').write_text('# BTw7 当前末读\n\n[报告](report.json)核对当前106源码／构建、旧记录的精确快照、入口链接及本轮已封证据。Studio358与出版9属于统一检查；这里不重跑产品测试。M4 partial、M5 not_started、真人0。浏览器同源导出与三次Event Timing均保持有界范围；标签与owned route关联、300实际可见对象和出版／真人门未完成。\n')
write(OUT/'manifest.json',{'schema':'archcanvas-btw-root-readback-manifest/1','artifacts':[{'path':str(p.relative_to(OUT)),'bytes':p.stat().st_size,'sha256':sha(p)} for p in sorted(OUT.iterdir()) if p.is_file()]})
print(json.dumps({k:report[k] for k in ['status','bindingRowsChecked','bindingFailures','localMarkdownLinksChecked','missingLinks','newFileWhitespaceFailures','currentChecks']},ensure_ascii=False))
assert report['status']=='bounded_readback_pass'
