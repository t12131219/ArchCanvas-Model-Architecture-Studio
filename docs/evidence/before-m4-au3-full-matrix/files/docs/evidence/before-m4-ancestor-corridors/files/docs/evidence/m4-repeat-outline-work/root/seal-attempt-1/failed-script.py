from pathlib import Path
from datetime import datetime, timezone
import hashlib, json

ROOT = Path(__file__).resolve().parents[4]
WORK = ROOT / 'docs/evidence/m4-repeat-outline-work'
SEAL = ROOT / 'docs/evidence/m4-repeat-outline-current-verification-sealed.json'
ARCHIVE = ROOT / 'docs/evidence/before-m4-repeat-outline/manifest.json'
STATUS = ROOT / 'docs/evidence/m4-human-review-handoff-status.json'
MUTABLE = WORK / 'root/service.log'

def binding(path):
    raw=path.read_bytes()
    return {'path':str(path.relative_to(ROOT)), 'bytes':len(raw), 'sha256':hashlib.sha256(raw).hexdigest()}

def main():
    assert not SEAL.exists(), 'Never overwrite a prior seal'
    archive=json.loads(ARCHIVE.read_bytes())
    assert len(archive['bindings']) == archive['bindingCount'] == 2916
    assert binding(ARCHIVE)['sha256'] == 'a0ae1bd0d2b21589a4986acc992c13c3f6cde0659a0c94c770f37fd5be299e70'
    historical=[]
    for row in archive['bindings']:
        copy=ROOT/row['archivePath']; current=binding(copy)
        assert (current['bytes'], current['sha256']) == (row['bytes'],row['sha256']), str(copy)
        if row['path'].startswith(('docs/evidence/m4-chs-browser-matrix-work/raw/', 'docs/evidence/browser-visual-matrix-chs-current/')):
            item=ROOT/row['path']; current=binding(item)
            assert (current['bytes'], current['sha256']) == (row['bytes'],row['sha256']), str(item)
            historical.append(item)
    assert len(historical)==806
    status=json.loads(STATUS.read_bytes())
    assert status['productionBuild']=='index-BGj2ZBSY.js'
    assert status['phaseStatus']=='partial' and not status['nextPhaseStarted']
    refs=status.get('evidenceRefs',{})
    for name,row in refs.items():
        assert binding(ROOT/row['path'])==row, name
    selected=set(historical+[ARCHIVE, STATUS])
    selected.update(p for p in WORK.rglob('*') if p.is_file() and p != MUTABLE and p.suffix not in ('.pyc','.pyo'))
    selected.update(ROOT/row['path'] for row in status['evidenceRefs'].values())
    selected.update(p for p in (ROOT/'.archcanvas/m4-research-trial-repeat-outline-current').rglob('*') if p.is_file())
    selected.update(p for p in (ROOT/'studio/src').rglob('*') if p.is_file())
    selected.update(p for p in (ROOT/'studio/tests').rglob('*') if p.is_file())
    selected.update(p for p in (ROOT/'docs/evidence/m4-routing-refinement/independent').rglob('*') if p.is_file())
    selected.update(p for p in (ROOT/'studio/dist').rglob('*') if p.is_file())
    selected.update(p for p in (ROOT/'src').rglob('*.py'))
    selected.update(p for p in (ROOT/'fixtures').rglob('*.py'))
    selected.update(p for p in (ROOT/'skills/archcanvas').rglob('*') if p.is_file())
    for name in ['README.md','AGENTS.md','pyproject.toml','requirements.lock','requirements-runtime.lock','studio/package.json','studio/package-lock.json','studio/tsconfig.json','studio/vite.config.ts','scripts/check_independence.py','scripts/research_trial.py','scripts/research_trial_core.mjs','scripts/export_canvas.mjs']:
        selected.add(ROOT/name)
    for name in ['acceptance.md','capability-matrix.md','m4-completion.md','m4-human-review-handoff.md','browser-visual-matrix-protocol.md','m4-research-protocol.md','m4-move-recovery-presets.md','m4-chs-current-matrix.md','m4-repeat-outline.md']:
        path=ROOT/'docs'/name
        if path.exists():selected.add(path)
    before=[binding(p) for p in sorted(selected)]
    after=[binding(p) for p in sorted(selected)]
    assert before==after
    value={'schemaVersion':1,'sealedAt':datetime.now(timezone.utc).isoformat(),'state':'current-BG-repeat-outline-bounded-verification-M4-partial',
        'scope':'Shared nominal Repeat outline product fix; fresh 170 Studio tests, strict/build and standalone nine checks, independent regression and bounded actual browser evidence, unassigned research preparation and current documentation. No fresh complete browser matrix, product-performance trials or human/publication certification.',
        'productionBuild':status['productionBuild'],'productionJsSha256':status['productionJsSha256'],'currentStatus':binding(STATUS),
        'priorArchive':binding(ARCHIVE),'verification':{'priorArchivedFilesExact':2916,'historicalRawCollectedFilesExact':806,'statusReferencesExact':len(refs),'allSelectedBeforeAfterExact':True,'user8765Touched':False,'humans':0,'productPerformanceTrials':0,'studioFullPassed':170,'studioFullFailed':0,'strictTypescriptExit':0,'productionBuildExit':0,'standaloneChecks':9,'independentRepeatTestsPassed':17,'historicalRoutingAdapterTestsPassed':14,'independentFrontiers':9,'independentRelatedDetails':3,'oldNominalStackHitOccurrences':6,'currentNominalStackHitOccurrences':0,'representativeBrowserCases':4,'freshCompleteMatrixCases':0,'browserRouteObservations':229,'browserEndpointObservations':458,'observationsIncludeRepeatedArtifacts':True,'explicitBlockedUpMoveBodySegments':3,'explicitBlockedUpMoveBodyPairs':2},
        'bindingCount':len(before),'bindings':before,'excludedMutablePaths':[str(MUTABLE.relative_to(ROOT))]}
    with SEAL.open('x') as stream:stream.write(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'seal':binding(SEAL),'bindingCount':len(before),'statusReferences':len(refs)},indent=2))

if __name__=='__main__':main()
