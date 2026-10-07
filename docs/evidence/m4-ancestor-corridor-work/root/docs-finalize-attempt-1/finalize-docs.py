import json,re,sys,hashlib,subprocess
from pathlib import Path
from datetime import datetime,timezone
root=Path.cwd();work=root/'docs/evidence/m4-ancestor-corridor-work';out=work/'root/docs-finalize-attempt-1';out.mkdir(parents=True,exist_ok=False)
def ref(p):
 p=Path(p);b=p.read_bytes();return {'path':str(p.relative_to(root)) if p.is_relative_to(root) else str(p),'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}
def write(p,d):p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
skillfiles=sorted((root/'skills/archcanvas').rglob('*.md'));before=[ref(p) for p in skillfiles]
validator=Path('/home/fzg/.codex/skills/.system/skill-creator/scripts/quick_validate.py');started=datetime.now(timezone.utc).isoformat()
argv=[sys.executable,str(validator),'skills/archcanvas'];result=subprocess.run(argv,cwd=root,text=True,capture_output=True)
(out/'skill.stdout.log').write_text(result.stdout);(out/'skill.stderr.log').write_text(result.stderr)
after=[ref(p) for p in skillfiles];skillreceipt=out/'skill-validation.json'
write(skillreceipt,{'schemaVersion':1,'argv':argv,'cwd':str(root),'startedAt':started,'finishedAt':datetime.now(timezone.utc).isoformat(),'exitCode':result.returncode,'interpreter':str(Path(sys.executable).resolve()),'pythonVersion':sys.version,'validator':ref(validator),'skillFilesBefore':before,'skillFilesAfter':after,'skillBeforeAfterExact':before==after,'stdout':ref(out/'skill.stdout.log'),'stderr':ref(out/'skill.stderr.log'),'scope':'Host Python validates Skill Markdown/YAML only; no product/model execution or dependency installation. Formal publication venv lacks yaml and is not substituted.'})
assert result.returncode==0 and before==after,result.stderr
statusfile=root/'docs/evidence/m4-human-review-handoff-status.json';status=json.loads(statusfile.read_text());status['generatedAt']=datetime.now(timezone.utc).isoformat();status['tests']['skillMarkdownValidation']={'exitCode':0,'receipt':str(skillreceipt.relative_to(root)),'skillBeforeAfterExact':True,'scope':'Host Python Markdown/YAML only; no product/model execution or dependency installation'};status['evidenceRefs'].append(ref(skillreceipt));write(statusfile,status)
paths=['README.md','docs/acceptance.md','docs/browser-visual-matrix-protocol.md','docs/capability-matrix.md','docs/evidence/README.md','docs/m4-ai-usability-audit.md','docs/m4-authoring-feedback.md','docs/m4-authoring.md','docs/m4-bcf-browser-matrix.md','docs/m4-completion.md','docs/m4-exit-audit.md','docs/m4-human-review-handoff.md','docs/m4-performance.md','docs/m4-research-protocol.md','docs/m4-routing-refinement.md','docs/m4-repeat-outline.md','docs/m4-move-recovery-presets.md','docs/m4-chs-current-matrix.md','docs/m4-ancestor-corridors.md','docs/evidence/m4-ancestor-corridor-work/README.md']
mdfiles=sorted(set([root/p for p in paths]+skillfiles));missing=[];links=0
for p in mdfiles:
 for m in re.finditer(r'\[[^\]\n]*\]\(([^)]+)\)',p.read_text()):
  target=m.group(1).strip()
  if target.startswith('<'):target=target[1:target.index('>')]
  else:target=target.split()[0]
  if target.startswith(('http:','https:','app:','#','codex:')):continue
  target=target.split('#')[0];links+=1
  if not (p.parent/target).exists():missing.append({'path':str(p.relative_to(root)),'target':target})
badrefs=[]
for r in status['evidenceRefs']:
 if ref(root/r['path'])!=r:badrefs.append(r['path'])
currentdocs=[root/'README.md']+[root/f'docs/{name}.md' for name in ['acceptance','capability-matrix','m4-completion','m4-human-review-handoff','browser-visual-matrix-protocol']]+[root/'docs/evidence/README.md']
notices=[]
for p in currentdocs:
 first=p.read_text().split('\n\n')[1];notices.append({'path':str(p.relative_to(root)),'currentBuild':('index-au3IB_0Q.js' in first and 'index-B6WbMowt.css' in first),'current179':('179/179' in first),'currentBoundedBrowser':('4节点3边' in first and '单L3' in first),'staleHistory':('stale' in first),'zeroHumans':('0分配/收集/真人' in first),'noPendingBrowser':('待最终绑定' not in first and '待末读' not in first)})
oldreadme=root/'docs/evidence/m4-repeat-outline-work/README.md';oldarchive=root/'docs/evidence/before-m4-ancestor-corridors/files/docs/evidence/m4-repeat-outline-work/README.md'
checks={
 'allLocalLinksExist':not missing,'allStatusEvidenceReferencesExact':not badrefs,'schema9ListEvidenceRefs':status['schemaVersion']==9 and isinstance(status['evidenceRefs'],list),
 'allCurrentNoticesConsistent':all(all(v for k,v in n.items() if k!='path') for n in notices),
 'partialNoM5NoHumans':status['phaseStatus']=='partial' and status['nextPhaseStarted'] is False and status['humanAcceptanceCertified'] is False and status['research']['humanResearcherCount']==0,
 'currentResearchUnpreparedAndOldSlotsUnassignable':status['research']['currentAu3PackagePrepared'] is False and status['research']['currentAu3PackageVerified'] is False and status['research']['oldSlotsMayBeAssigned'] is False,
 'draftAndImportedPersistenceSeparate':status['currentBrowser']['authoredDraft']['saveReopenObserved'] is True and status['currentBrowser']['freshImportedCanvasAliasSaveReopenCertified'] is False,
 'historicalAiVersionExplicit':status['historicalAiSmokeThisRound']['build']=='index-BGj2ZBSY.js' and status['historicalAiSmokeThisRound']['staleForCurrentAu3'] is True,
 'familyGuardNotGeneric':status['ancestorCorridors']['sameTensorPerPairCrossingGuardScope'].startswith('new family stage only'),
 'perRefinement80NotLifetime':status['ancestorCorridors']['budget']['genericPerRefinementCandidates']==80 and 'not lifetime' in status['ancestorCorridors']['budget']['scope'],
 'oldRepeatEvidenceReadmeRestoredExact':oldreadme.read_bytes()==oldarchive.read_bytes(),
 'skillValidAndUnmodified':result.returncode==0 and before==after
}
manifest=out/'document-bindings.json';docrefs=[ref(p) for p in mdfiles]+[ref(statusfile)];write(manifest,{'schemaVersion':1,'frozenAt':datetime.now(timezone.utc).isoformat(),'scope':'Current documentation/Skill instructions and machine status only; no raw evidence, sealed historical artifacts or product changes. Current browser and standalone evidence are separately version/scope bound.','files':docrefs})
receipt=out/'receipt.json';write(receipt,{'schemaVersion':1,'checkedAt':datetime.now(timezone.utc).isoformat(),'exitCode':0 if all(checks.values()) else 1,'checks':checks,'markdownFilesChecked':len(mdfiles),'localLinksChecked':links,'missingLinks':missing,'statusEvidenceReferences':len(status['evidenceRefs']),'badStatusReferences':badrefs,'currentNotices':notices,'documents':ref(manifest),'skillValidation':ref(skillreceipt),'restoredOldEvidenceReadme':ref(oldreadme),'scope':'Final read-only consistency/byte binding after documented scope synchronization. No product/model/browser/test execution or dependency installation; Markdown/YAML helper is host only. Original old evidence README restored from exact1911 archive before checks.'})
print(json.dumps({'exitCode':0 if all(checks.values()) else 1,'markdownFiles':len(mdfiles),'links':links,'statusRefs':len(status['evidenceRefs']),'checks':checks,'receipt':ref(receipt),'documentManifest':ref(manifest),'skillReceipt':ref(skillreceipt)},ensure_ascii=False))
assert all(checks.values()),checks
