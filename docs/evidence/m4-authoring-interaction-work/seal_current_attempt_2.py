"""Validate current documentation and bind bounded evidence, never promote gates."""
from pathlib import Path
from datetime import datetime, timezone
from urllib.parse import unquote
import hashlib
import json
import re
import subprocess

ROOT=Path(__file__).resolve().parents[3]
WORK=Path(__file__).resolve().parent
OUT=WORK/'doc-validation-attempt-2'
SEAL=ROOT/'docs/evidence/m4-authoring-interaction-verification-sealed.json'
DOCS=['README.md','docs/m4-completion.md','docs/m4-exit-audit.md','docs/m4-ai-usability-audit.md','docs/m4-human-review-handoff.md','docs/m4-performance.md','docs/m4-authoring.md','docs/acceptance.md','docs/capability-matrix.md','docs/evidence/README.md','skills/archcanvas/SKILL.md','skills/archcanvas/references/formal-alpha.md','skills/archcanvas/references/runtime-compatibility.md','docs/m4-authoring-interaction.md','docs/evidence/m4-authoring-interaction-work/README.md']
def now():return datetime.now(timezone.utc).isoformat()
def bind(p):
    if isinstance(p,str):p=ROOT/p
    b=p.read_bytes();return dict(path=str(p.relative_to(ROOT)) if p.is_relative_to(ROOT) else str(p),bytes=len(b),sha256=hashlib.sha256(b).hexdigest())
def dump(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
assert not SEAL.exists() and not OUT.exists()
OUT.mkdir()
before=[bind(p) for p in DOCS]
links=[]
for name in DOCS:
    for match in re.finditer(r'\[[^\]\n]*\]\((<[^>]+>|[^\s)]+)(?:\s+"[^"]*")?\)',(ROOT/name).read_text()):
        raw=match.group(1).strip('<>');target=unquote(raw.split('#',1)[0])
        if not target or re.match(r'^[a-zA-Z][a-zA-Z0-9+.-]*:',target):continue
        resolved=Path(target) if target.startswith('/') else (ROOT/name).parent/target
        links.append(dict(document=name,target=raw,exists=resolved.exists()))
validator=Path('/home/fzg/.codex/skills/.system/skill-creator/scripts/quick_validate.py')
(OUT/'quick_validate.py').write_bytes(validator.read_bytes())
argv=['/home/fzg/anaconda3/bin/python',str(validator),'skills/archcanvas']
started=now();run=subprocess.run(argv,cwd=ROOT,capture_output=True,check=False)
(OUT/'skill.stdout.txt').write_bytes(run.stdout);(OUT/'skill.stderr.txt').write_bytes(run.stderr)
status=json.loads((ROOT/'docs/evidence/m4-human-review-handoff-status.json').read_text());assert status['schemaVersion']==12
refs=[dict(expected=r,actual=bind(r['path']),exact=r==bind(r['path'])) for r in status['evidenceRefs']]
prior_manifest=json.loads((WORK/'before-implementation-attempt-1/manifest.json').read_text())
map_old={r['source']:r['copy'] for r in prior_manifest['records']}
# Two current mutable docs were retained in the separate pre-doc-update archive.
prior_docs=json.loads((WORK/'before-current-doc-update-attempt-1/manifest.json').read_text())
map_old.update({r['source']['path']:r['copy']['path'] for r in prior_docs['records']})
prior=ROOT/'docs/evidence/m4-collapse-continuity-verification-sealed.json'
prior_records=json.loads(prior.read_text())['records']
resolved_prior=[]
for r in prior_records:
    actual=bind(map_old.get(r['path'],r['path']))
    resolved_prior.append(dict(expected=r,resolved=actual,exact=r['bytes']==actual['bytes'] and r['sha256']==actual['sha256']))
cg=ROOT/'docs/evidence/m4-monochrome-role-verification-sealed.json'
cg_records=json.loads(cg.read_text())['records']
cg_results=[dict(expected=r,actual=bind(r['path']),exact=r==bind(r['path'])) for r in cg_records]
after=[bind(p) for p in DOCS]
receipt=dict(protocol='archcanvas-authoring-interaction-docs-skill-prior-seal-readback/1',startedAt=started,finishedAt=now(),documents=before,documentsAfter=after,documentInputsUnchanged=before==after,inlineLocalLinks=links,localLinksCount=len(links),missingLocalLinks=[r for r in links if not r['exists']],skillValidator=dict(argv=argv,exitCode=run.returncode,stdout=bind(OUT/'skill.stdout.txt'),stderr=bind(OUT/'skill.stderr.txt'),source=bind(validator),sourceCopy=bind(OUT/'quick_validate.py'),scope='Existing system Python/PyYAML only validates the instruction package, not formal model/runtime execution.'),statusRefs=refs,priorBkSeal=bind(prior),priorBkBindings=len(prior_records),priorBkResolved=resolved_prior,priorCgSeal=bind(cg),priorCgBindings=len(cg_records),priorCgReadback=cg_results,modelExecution=False,dependenciesInstalled=False,productTestsRerun=False,M4='partial',M5='not_started',humans=0)
dump(OUT/'receipt.json',receipt)
assert run.returncode==0 and not receipt['missingLocalLinks'] and before==after
assert all(r['exact'] for r in refs+resolved_prior+cg_results)
trees=['src','tests','schemas','fixtures','scripts','skills/archcanvas','studio/src','studio/tests','studio/dist','docs/evidence/m4-authoring-interaction-work']
paths=set()
for tree in trees:
    for p in (ROOT/tree).rglob('*'):
        if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc':paths.add(p)
for name in DOCS+['AGENTS.md','pyproject.toml','requirements.lock','requirements-runtime.lock','studio/package.json','studio/package-lock.json','studio/tsconfig.json','studio/vite.config.ts','studio/index.html','docs/evidence/m4-human-review-handoff-status.json','docs/evidence/m4-collapse-continuity-verification-sealed.json','docs/evidence/m4-monochrome-role-verification-sealed.json','docs/m4-collapse-continuity.md','docs/m4-monochrome-role.md','docs/evidence/m4-monochrome-width-pixel-supplement-attempt-1/receipt.json','docs/evidence/m4-performance-controls-work/analysis-attempt-3/receipt.json']:
    paths.add(ROOT/name)
# Exact originals/copies required by actual-artifact manifest, never approval keys.
artifact=json.loads((WORK/'actual-artifacts-attempt-1/manifest.json').read_text())
for rec in artifact['copies']:
    for side in ('source','copy'):
        r=rec[side];assert bind(r['path'])==r;paths.add(ROOT/r['path'])
records=[bind(p) for p in sorted(paths)];assert records==[bind(p) for p in sorted(paths)]
x=dict(schemaVersion=1,protocol='archcanvas-authoring-interaction-bounded-verification-seal/1',createdAt=now(),status='bounded-contract-native-artifact-pass-with-explicit-aesthetic-and-presentation-failures',scope=status['scope'],currentBuild=status['productionBuild'],currentJsSha256=status['productionJsSha256'],milestones=dict(M4='partial',M5='not_started',humans=0),records=records,boundFileCount=len(records),selectedTrees=trees,documentationReceipt=bind(OUT/'receipt.json'),priorBkSeal=bind(prior),priorBkBindingsResolvedExact=len(prior_records),priorMutableMap=bind(WORK/'before-implementation-attempt-1/manifest.json'),priorCgSeal=bind(cg),priorCgOriginalBindingsExact=len(cg_records),checks=status['tests'],authoring=status['authoring'],interaction=status['authoringInteraction'],aiReview=status['aiReview'],implementationDirection=status['implementationDirection'],openItems=status['openItems'],preservedFailures=status['preservedFailures'],bindingIsNotCertificationOfEveryFileClaim=True,allSelectedBytesExact=True,noClaims=['human acceptance','global aesthetics or shortest/crossing-free routes','dedicated four-pan pixel validation','true100-percent merge screenshot certification','pending raster/footer equivalence','current Studio A/B/presented FPS','general held-pointer cancellation','actual physical publication readability','current full39 matrix/full standalone release','every catalog module/runtime/training'],independentFinalReadback='separate receipt outside selected trees; pending, does not mutate this seal')
dump(SEAL,x)
print(json.dumps(dict(seal=bind(SEAL),records=len(records),localLinks=len(links),skillExit=run.returncode,priorBkExact=len(prior_records),cgExact=len(cg_records)),ensure_ascii=False))
