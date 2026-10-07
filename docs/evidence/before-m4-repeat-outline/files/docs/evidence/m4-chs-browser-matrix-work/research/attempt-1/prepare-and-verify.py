#!/usr/bin/env python3
"""Prepare a fresh unassigned ChS trial package and preserve exact receipts.

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
PACKAGE = ROOT / '.archcanvas/m4-research-trial-chs-current'
SEAL = ROOT / 'docs/evidence/m4-move-recovery-presets-current-verification-sealed.json'
EXPECTED_SEAL_SHA = 'e5ea650eaff31d30faf01352590fc12591b143968415078ca437964f208b82af'
EXPECTED_JS_SHA = '05019f89f0de0c0c622df7a2cc1a13ed58477c456244c97209a0f37db79139c9'


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
    receipt = json.loads(raw)
    assert receipt['bindingCount'] == len(receipt['bindings']) == 799
    for row in receipt['bindings']:
        contents = (ROOT / row['path']).read_bytes()
        assert sha(contents) == row['sha256'] and len(contents) == row['bytes'], row['path']
    return {'sealSha256': sha(raw), 'boundFiles': 799, 'allDeclaredBindingsExact': True}


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
    assert sha((ROOT / 'studio/dist/assets/index-ChS0wIgb.js').read_bytes()) == EXPECTED_JS_SHA
    before_seal = seal_guard()
    before = inputs()
    new_json('inputs-before.json', before)
    new_json('sealed-inputs-before.json', before_seal)
    python = ROOT / '.venv/bin/python'
    prepare = command('prepare', [str(python), 'scripts/research_trial.py', 'prepare',
                                  '--output', str(PACKAGE), '--slots', '5', '--first-port', '8991'])
    verify = command('verify', [str(python), 'scripts/research_trial.py', 'verify', '--package', str(PACKAGE)])
    manifest = json.loads((PACKAGE / 'manifest.json').read_bytes())
    assert manifest == json.loads((WORK / 'prepare.stdout.txt').read_bytes())
    assert manifest['state'] == 'prepared-no-participants' and manifest['researcherCount'] == 0 and manifest['researchGate'] == 'not_run'
    assert manifest['formalRoot'] == str(ROOT)
    assert manifest['preparationRuntime']['analyzerOrigin'] == str(ROOT / 'src/archcanvas_python/frontend.py')
    assert manifest['preparationRuntime']['pythonExecutable'] == str(python)
    implementation = {row['path']: row['sha256'] for row in manifest['implementationFiles']}
    assert implementation['studio/dist/assets/index-ChS0wIgb.js'] == EXPECTED_JS_SHA
    for row in manifest['implementationFiles']:
        current = binding(ROOT / row['path'])
        assert current == row, row['path']
    for row in manifest['baseline']['files']:
        contents = (PACKAGE / row['path']).read_bytes()
        assert sha(contents) == row['sha256'] and len(contents) == row['bytes']
    baseline = json.loads((PACKAGE / 'baseline/canvas.json').read_bytes())
    assert baseline['revision'] == 0 and baseline['displayAliases'] == {} and baseline['nodeStyleOverrides'] == {} and baseline['edgeStyleOverrides'] == {} and baseline['pinnedObjects'] == []
    assert baseline['architecture'] == json.loads((PACKAGE / 'baseline/architecture.json').read_bytes())
    assert [slot['port'] for slot in manifest['slots']] == list(range(8991, 8996))
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
              'productionBuild': 'index-ChS0wIgb.js', 'productionJsSha256': EXPECTED_JS_SHA,
              'implementationBindings': len(manifest['implementationFiles']),
              'baselineBindings': len(manifest['baseline']['files']), 'slots': 5,
              'ports': list(range(8991, 8996)), 'portAvailabilityChecked': False,
              'assignedParticipants': 0, 'collectedParticipants': 0, 'researcherCount': 0,
              'humanSuccessCertified': False, 'researchGate': 'not_run',
              'prepareProcess': prepare, 'verifyProcess': verify,
              'inputBindingsUnchanged': len(before), 'priorSeal799Unchanged': after_seal,
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
