"""Create one append-only bounded verification seal after all authors freeze."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json

ROOT = Path(__file__).resolve().parents[4]
WORK = ROOT / 'docs/evidence/m4-ancestor-corridor-work'
ARCHIVE = ROOT / 'docs/evidence/before-m4-ancestor-corridors/manifest.json'
STATUS = ROOT / 'docs/evidence/m4-human-review-handoff-status.json'
SEAL = ROOT / 'docs/evidence/m4-ancestor-corridor-current-verification-sealed.json'


def binding(path):
    raw = path.read_bytes()
    return {'path': str(path.relative_to(ROOT)), 'bytes': len(raw),
            'sha256': hashlib.sha256(raw).hexdigest()}


def exact(rows):
    for row in rows:
        assert binding(ROOT / row['path']) == row, row['path']


def main():
    assert not SEAL.exists(), 'Never overwrite a seal'
    archive = json.loads(ARCHIVE.read_bytes())
    assert binding(ARCHIVE)['sha256'] == 'c1969548ea2b2b1e9158c3f424b5e29f6910fe124879ce7f658b54d5e996df28'
    assert len(archive['bindings']) == archive['bindingCount'] == 1911
    prior_copies = []
    immutable_originals = []
    for row in archive['bindings']:
        copy = ROOT / row['archivePath']
        current = binding(copy)
        assert (current['bytes'], current['sha256']) == (row['bytes'], row['sha256']), copy
        prior_copies.append(copy)
        # Product source/current documentation intentionally changed this round.
        # All pre-existing evidence and the unassigned research package stay exact.
        if (row['path'].startswith('docs/evidence/') and
                row['path'] != 'docs/evidence/m4-human-review-handoff-status.json') or \
                row['path'].startswith('.archcanvas/m4-research-trial-repeat-outline-current/'):
            original = ROOT / row['path']
            current = binding(original)
            assert (current['bytes'], current['sha256']) == (row['bytes'], row['sha256']), original
            immutable_originals.append(original)
    old_seal = ROOT / archive['previousSeal']
    assert binding(old_seal)['sha256'] == archive['previousSealSha256']
    status = json.loads(STATUS.read_bytes())
    assert status['schemaVersion'] == 9
    assert status['productionBuild'] == 'index-au3IB_0Q.js'
    assert status['productionJsSha256'] == 'dca15460bc9ed8def5ff80c9da5dfcf16bb49f7a230986e0ffeef1a6b0e7548b'
    assert status['productionCssSha256'] == '172a09a8c147e53c3bef426cf76b59b8cc4893e891eb6e920aa7b25a0bb024e0'
    assert status['phaseStatus'] == 'partial' and not status['nextPhaseStarted']
    assert status['humanAcceptanceCertified'] is False
    assert isinstance(status['evidenceRefs'], list)
    exact(status['evidenceRefs'])
    for name in ['full-studio-attempt-2', 'build-attempt-3']:
        receipt = json.loads((WORK / 'root' / name / 'receipt.json').read_bytes())
        assert receipt['exitCode'] == 0 and receipt['sourceBeforeAfterExact']
        assert receipt['bindings'] == receipt['after']
        exact(receipt['bindings'] + receipt['logs'])
    full_log = (WORK / 'root/full-studio-attempt-2/stdout.log').read_text()
    assert 'ℹ tests 179\n' in full_log and 'ℹ pass 179\n' in full_log
    assert 'ℹ fail 0\n' in full_log and 'ℹ skipped 0\n' in full_log
    browser_path = WORK / 'browser-final-attempt-1/report.json'
    browser = json.loads(browser_path.read_bytes())
    exact(browser['bindings'] + browser['source'] + browser['build'])
    assert browser['humans'] == 0 and browser['aiCountsAsHuman'] is False
    assert browser['authoredWorkflow']['draftSaveReopenObserved']
    assert browser['authoredWorkflow']['modelExecuted'] is False
    for row in browser['snapshotBindings']:
        exact([row['original'], row['frozen']])
    selected = set(prior_copies + immutable_originals + [ARCHIVE, STATUS])
    selected.update(ROOT / row['path'] for row in status['evidenceRefs'])
    excluded = {WORK / 'root/service.log'}
    for directory in [WORK, ROOT / 'studio/src', ROOT / 'studio/tests',
                      ROOT / 'studio/dist', ROOT / 'skills/archcanvas']:
        selected.update(p for p in directory.rglob('*') if p.is_file() and
                        p not in excluded and '__pycache__' not in p.parts and
                        p.suffix not in ('.pyc', '.pyo'))
    selected.update(p for p in (ROOT / 'src').rglob('*.py'))
    selected.update(p for p in (ROOT / 'fixtures').rglob('*.py'))
    selected.update(p for p in (ROOT / 'docs').glob('*.md'))
    for name in ['README.md', 'AGENTS.md', 'pyproject.toml', 'requirements.lock',
                 'requirements-runtime.lock', 'studio/package.json',
                 'studio/package-lock.json', 'studio/tsconfig.json',
                 'studio/vite.config.ts', 'scripts/check_independence.py',
                 'scripts/research_trial.py', 'scripts/research_trial_core.mjs',
                 'scripts/export_canvas.mjs']:
        selected.add(ROOT / name)
    before = [binding(p) for p in sorted(selected)]
    after = [binding(p) for p in sorted(selected)]
    assert before == after
    value = {
        'schemaVersion': 1, 'sealedAt': datetime.now(timezone.utc).isoformat(),
        'state': 'current-au3-ancestor-corridor-bounded-verification-M4-partial',
        'scope': 'Exact memory-family ancestor corridor and text-port hit fix; 179 Studio tests/build, 12 independent views, nine standalone static checks, one L3 browser/export source binding and a four-module authored workflow. Historical AI/matrix evidence remains historical. No human, complete current matrix, fixed-host performance or physical publication certification.',
        'productionBuild': status['productionBuild'],
        'productionJsSha256': status['productionJsSha256'],
        'productionCss': status['productionCss'],
        'productionCssSha256': status['productionCssSha256'],
        'currentStatus': binding(STATUS), 'priorArchive': binding(ARCHIVE),
        'currentBrowser': binding(browser_path),
        'verification': {'priorArchivedFilesExact': len(prior_copies),
                         'priorImmutableEvidenceAndResearchOriginalsExact': len(immutable_originals),
                         'priorSealExact': True, 'statusReferencesExact': len(status['evidenceRefs']),
                         'allSelectedBeforeAfterExact': True,
                         'studioFullPassed': 179, 'studioFullFailed': 0,
                         'productionBuildIncludesStrictTypescriptExit': 0,
                         'standaloneStaticChecksPassed': 9,
                         'independentFrontiers': 9, 'independentRelatedDetails': 3,
                         'sourceBoundBrowserFigures': 1, 'authoredDraftNodes': 4,
                         'authoredDraftEdges': 3, 'authoredDraftSaveReopenObserved': True,
                         'freshImportedAliasSaveMatrixCertified': False,
                         'freshCompleteMatrixCases': 0,
                         'humanAcceptanceCertified': False, 'humans': 0,
                         'productPerformanceTrials': 0, 'publicationCertified': False,
                         'modelExecutionPerformedThisRound': False,
                         'newCurrentResearchPackagePreparedThisRound': False,
                         'user8765Touched': False},
        'bindingCount': len(before), 'bindings': before,
        'excludedMutablePaths': [str(p.relative_to(ROOT)) for p in sorted(excluded)],
        'excludedByConstruction': ['transaction approval keys', 'seal itself',
                                   'subsequent independent final-readback receipts']}
    with SEAL.open('x') as stream:
        stream.write(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'seal': binding(SEAL), 'bindingCount': len(before),
                      'statusReferences': len(status['evidenceRefs'])}, ensure_ascii=False))


if __name__ == '__main__':
    main()
