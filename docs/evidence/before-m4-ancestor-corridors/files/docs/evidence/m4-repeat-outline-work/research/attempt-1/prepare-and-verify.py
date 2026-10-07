#!/usr/bin/env python3
"""Prepare a fresh unassigned repeat-outline trial package and preserve exact receipts.

No services, assignment, model execution, dependency installation, or edits of
prior packages/sealed files. This evidence directory and package must be new.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[5]
WORK = Path(__file__).resolve().parent
PACKAGE = ROOT / '.archcanvas/m4-research-trial-repeat-outline-current'
SEAL = ROOT / 'docs/evidence/m4-chs-browser-matrix-current-verification-sealed.json'
EXPECTED_SEAL_SHA = '332f9b84a085efa95ef0cb09fdfd152bbbef072fc97c5268f355191a597a4581'
EXPECTED_JS_SHA = '8755924c0ca77285927550f88bf0a49e43c73856c1888294b356e34fc0bcea53'


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def binding(path):
    raw = path.read_bytes()
    return {'path': str(path.relative_to(ROOT)), 'sha256': sha(raw), 'bytes': len(raw)}


def new_json(name, value):
    with (WORK / name).open('x') as stream:
        stream.write(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def seal_guard():
    raw = SEAL.read_bytes()
    assert sha(raw) == EXPECTED_SEAL_SHA
    archive_path = ROOT / 'docs/evidence/before-m4-repeat-outline/manifest.json'
    archive_raw = archive_path.read_bytes()
    assert sha(archive_raw) == 'a0ae1bd0d2b21589a4986acc992c13c3f6cde0659a0c94c770f37fd5be299e70'
    archive = json.loads(archive_raw)
    assert archive['bindingCount'] == len(archive['bindings']) == 2916
    unchanged_raw = 0
    for row in archive['bindings']:
        contents = (ROOT / row['archivePath']).read_bytes()
        assert sha(contents) == row['sha256'] and len(contents) == row['bytes'], row['archivePath']
        if row['path'].startswith(('docs/evidence/m4-chs-browser-matrix-work/raw/', 'docs/evidence/browser-visual-matrix-chs-current/')):
            current = (ROOT / row['path']).read_bytes()
            assert sha(current) == row['sha256'] and len(current) == row['bytes'], row['path']
            unchanged_raw += 1
    assert unchanged_raw == 806
    return {'sealSha256': sha(raw), 'archiveManifestSha256': sha(archive_raw), 'archivedFiles': 2916,
            'allArchiveBindingsExact': True, 'currentHistoricalRawAndCollectedExact': unchanged_raw,
            'changedProductAndDocumentsCheckedThroughArchiveOnly': True}


def inputs():
    files = [ROOT / 'scripts/research_trial.py', ROOT / 'scripts/research_trial_core.mjs',
             ROOT / 'scripts/export_canvas.mjs', ROOT / 'scripts/summarize_research_tasks.py',
             ROOT / 'scripts/check_research_trial.py', ROOT / 'tests/test_research_trial.py',
             ROOT / 'docs/m4-research-protocol.md']
    files += sorted((ROOT / 'src').rglob('*.py'))
    files += sorted(path for path in (ROOT / 'studio/src').rglob('*') if path.suffix in ['.ts', '.tsx', '.css'])
    files += sorted(path for path in (ROOT / 'studio/dist').rglob('*') if path.is_file())
    files += sorted((ROOT / 'fixtures/transformer').rglob('*.py'))
    return [binding(path) for path in sorted(set(files))]


def command(label, argv):
    environment = os.environ.copy()
    environment['PYTHONDONTWRITEBYTECODE'] = '1'
    started = datetime.now(timezone.utc).isoformat()
    completed = subprocess.run(argv, cwd=ROOT, env=environment, capture_output=True, timeout=60)
    ended = datetime.now(timezone.utc).isoformat()
    logs = {}
    for suffix, contents in [('stdout.txt', completed.stdout), ('stderr.txt', completed.stderr)]:
        file = WORK / (label + '.' + suffix)
        with file.open('xb') as stream:
            stream.write(contents)
        logs[suffix.split('.', 1)[0]] = binding(file)
    receipt = {'argv': [str(value) for value in argv], 'cwd': str(ROOT),
               'environmentOverrides': {'PYTHONDONTWRITEBYTECODE': '1'},
               'startedAt': started, 'endedAt': ended, 'exitCode': completed.returncode, **logs}
    new_json(label + '.process.json', receipt)
    assert completed.returncode == 0, completed.stderr.decode()
    return receipt


def main():
    assert not PACKAGE.exists() and not PACKAGE.is_symlink(), 'Use a fresh package path'
    assert not (WORK / 'preparation-verification.json').exists(), 'Never overwrite prior evidence'
    assert sha((ROOT / 'studio/dist/assets/index-BGj2ZBSY.js').read_bytes()) == EXPECTED_JS_SHA
    before_seal = seal_guard()
    before = inputs()
    new_json('inputs-before.json', before)
    new_json('sealed-inputs-before.json', before_seal)
    python = ROOT / '.venv/bin/python'
    prepare = command('prepare', [str(python), 'scripts/research_trial.py', 'prepare',
                                  '--output', str(PACKAGE), '--slots', '5', '--first-port', '9001'])
    verify = command('verify', [str(python), 'scripts/research_trial.py', 'verify', '--package', str(PACKAGE)])
    manifest = json.loads((PACKAGE / 'manifest.json').read_bytes())
    assert manifest == json.loads((WORK / 'prepare.stdout.txt').read_bytes())
    assert manifest['state'] == 'prepared-no-participants' and manifest['researcherCount'] == 0 and manifest['researchGate'] == 'not_run'
    assert manifest['formalRoot'] == str(ROOT)
    assert manifest['preparationRuntime']['analyzerOrigin'] == str(ROOT / 'src/archcanvas_python/frontend.py')
    assert manifest['preparationRuntime']['pythonExecutable'] == str(python)
    implementation = {row['path']: row['sha256'] for row in manifest['implementationFiles']}
    assert implementation['studio/dist/assets/index-BGj2ZBSY.js'] == EXPECTED_JS_SHA
    for row in manifest['implementationFiles']:
        current = binding(ROOT / row['path'])
        assert current == row, row['path']
    for row in manifest['baseline']['files']:
        contents = (PACKAGE / row['path']).read_bytes()
        assert sha(contents) == row['sha256'] and len(contents) == row['bytes']
    baseline = json.loads((PACKAGE / 'baseline/canvas.json').read_bytes())
    assert baseline['revision'] == 0 and baseline['displayAliases'] == {} and baseline['nodeStyleOverrides'] == {} and baseline['edgeStyleOverrides'] == {} and baseline['pinnedObjects'] == []
    assert baseline['architecture'] == json.loads((PACKAGE / 'baseline/architecture.json').read_bytes())
    assert [slot['port'] for slot in manifest['slots']] == list(range(9001, 9006))
    assert len(set(slot['dataDir'] for slot in manifest['slots'])) == 5
    assert len(set(slot['baselineEnvelope']['sha256'] for slot in manifest['slots'])) == 1
    for slot in manifest['slots']:
        assert slot['participantCode'] is None and slot['assignment'] == 'unassigned'
        envelope = json.loads((PACKAGE / slot['baselineEnvelope']['path']).read_bytes())
        assert envelope['document'] == baseline and envelope['revision'] == 1
        path = PACKAGE / 'slots' / slot['slotId']
        assert not (path / 'assignment.json').exists() and not (path / 'collected').exists()
        for name in ['incoming', 'workspace/exports', 'workspace/projects', 'workspace/transactions']:
            directory = path / name
            assert not directory.exists() or not list(directory.iterdir())
        template = json.loads((path / 'review-template.json').read_bytes())
        assert template['reviewer'] is None and template['participantCode'] is None and template['overallOutcome'] == 'pending'
    after = inputs()
    assert after == before
    after_seal = seal_guard()
    assert after_seal == before_seal
    new_json('inputs-after.json', after)
    new_json('sealed-inputs-after.json', after_seal)
    result = {'schemaVersion': 1, 'at': datetime.now(timezone.utc).isoformat(),
              'status': 'prepared-and-verified-no-participants',
              'package': str(PACKAGE.relative_to(ROOT)), 'manifest': binding(PACKAGE / 'manifest.json'),
              'productionBuild': 'index-BGj2ZBSY.js', 'productionJsSha256': EXPECTED_JS_SHA,
              'implementationBindings': len(manifest['implementationFiles']),
              'baselineBindings': len(manifest['baseline']['files']), 'slots': 5,
              'ports': list(range(9001, 9006)), 'portAvailabilityChecked': False,
              'assignedParticipants': 0, 'collectedParticipants': 0, 'researcherCount': 0,
              'humanSuccessCertified': False, 'researchGate': 'not_run',
              'prepareProcess': prepare, 'verifyProcess': verify,
              'inputBindingsUnchanged': len(before), 'priorArchive2916Unchanged': after_seal,
              'packageBindings': [binding(path) for path in sorted(PACKAGE.rglob('*')) if path.is_file()],
              'modelExecution': 'not_run', 'servicesStarted': False,
              'taskContract': 'Existing five-step same-source Transformer visual editing only. New authoring/preset/recovery exploration is separately proposed; no observations or timing supplied.',
              'limits': ['Preparation freezes bytes and baselines, not participant identity or human success.',
                         'The fixed five-task recorder does not observe draft-builder state or accept a changed document/source/IR.',
                         '180 seconds is an existing target, not a newly measured result.',
                         'Only prepare and verify were run; check_research_trial.py was inspected as source, not rerun.']}
    new_json('preparation-verification.json', result)
    print(json.dumps({key: value for key, value in result.items() if key not in ['packageBindings', 'prepareProcess', 'verifyProcess']}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
