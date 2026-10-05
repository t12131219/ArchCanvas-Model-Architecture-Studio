#!/usr/bin/env python3
"""Record final bounded Python suites and preserve their independent-copy provenance.

Writes only new evidence files with exclusive creation. Does not import or
execute model fixture modules or overwrite previous receipts.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
WORK = Path(__file__).resolve().parent
OLD = ROOT / 'docs/evidence/before-m4-boundary-corrections'
INDEPENDENT = Path('/tmp/archcanvas-independent-d9fxdd15/m4-holdout-report.json')
FINAL_SHA = {
    'src/archcanvas_python/frontend.py': 'ce7f7f733da28cb31ecff80ca029a53094e88f8451bffc3874f8167f80a07d00',
    'tests/test_m4_unknown_boundaries.py': '7234d21e22350639404ff6ce11d4852a74b1ecfcf592375053e4ff0ea476578c',
}


def now():
    return datetime.now(timezone.utc).isoformat()


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def write_new(path, raw):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as stream:
        stream.write(raw)


def json_new(path, value):
    write_new(path, (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode())


def binding(path):
    raw = path.read_bytes()
    return {'path': str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path),
            'sha256': sha(raw), 'bytes': len(raw)}


def main():
    originals = {name: (ROOT / name).read_bytes() for name in FINAL_SHA}
    assert all(sha(raw) == FINAL_SHA[name] for name, raw in originals.items()), 'Final source/test changed.'
    previous = json.loads((OLD / 'manifest.json').read_bytes())
    old_frontend = next(item for item in previous['files'] if item['originalPath'] == 'src/archcanvas_python/frontend.py')
    assert binding(ROOT / old_frontend['archivePath'])['sha256'] == old_frontend['sha256']
    assert not any(item['originalPath'] == 'tests/test_m4_unknown_boundaries.py' for item in previous['files'])
    environment = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', PYTHONPATH='src:tests')
    suites = [
        ('python-final-62', ['tests/test_m4_unknown_boundaries.py', 'tests/test_runtime_analysis.py',
                            'tests/test_m4_holdout.py', 'tests/test_residual_roles.py',
                            'tests/test_m4_base_models.py', 'tests/test_m4_stress.py'], 62),
        ('python-final-static-21', ['tests/test_rebind_analysis.py', 'tests/test_output_paths.py'], 21),
    ]
    processes = []
    for name, tests, expected in suites:
        arguments = [sys.executable, '-m', 'unittest', *tests]
        started = now()
        result = subprocess.run(arguments, cwd=ROOT, env=environment, capture_output=True, timeout=120)
        ended = now()
        stdout, stderr = WORK / (name + '.stdout.txt'), WORK / (name + '.stderr.txt')
        write_new(stdout, result.stdout)
        write_new(stderr, result.stderr)
        text = (result.stdout + result.stderr).decode()
        actual = re.search(r'^Ran (\d+) tests? in ', text, re.M)
        passed = result.returncode == 0 and actual and int(actual.group(1)) == expected and '\nOK\n' in text and 'skipped=' not in text
        receipt = {'schemaVersion': 1, 'scope': 'final-static-Python-regression', 'command':
                   'PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:tests python -m unittest ' + ' '.join(tests),
                   'argv': arguments, 'cwd': str(ROOT), 'pythonExecutable': sys.executable,
                   'environmentOverrides': {'PYTHONDONTWRITEBYTECODE': '1', 'PYTHONPATH': 'src:tests'},
                   'startedAt': started, 'endedAt': ended, 'exitCode': result.returncode,
                   'expectedTests': expected, 'observedTests': int(actual.group(1)) if actual else None,
                   'passed': bool(passed), 'stdout': binding(stdout), 'stderr': binding(stderr),
                   'implementationBindings': [binding(ROOT / item) for item in FINAL_SHA],
                   'limitations': ['Static analysis and supporting regressions; fixture model source is not imported or executed.',
                                   'Counts refer to these exact commands and are not added to earlier suite results.']}
        json_new(WORK / (name + '.process.json'), receipt)
        processes.append(receipt)
        assert passed, name + ' did not pass.'

    independent = json.loads(INDEPENDENT.read_bytes())
    release = Path(independent['standaloneCopy'])
    assert independent['passed'] is True and independent['formalProject'] == str(ROOT)
    assert all((release / item).read_bytes() == raw for item, raw in originals.items())
    artifacts = {INDEPENDENT, Path(independent['independenceReport'])}
    for check in independent['checks']:
        for field in ('source', 'oracle', 'stdout', 'architecture'):
            if field in check:
                artifacts.add(Path(check[field]))
    artifacts.update(release / name for name in FINAL_SHA)
    copies = []
    temporary = release.parent
    for source in sorted(artifacts):
        destination = WORK / 'independent-holdout-final' / source.relative_to(temporary)
        raw = source.read_bytes()
        write_new(destination, raw)
        copies.append({'originalPath': str(source), 'preservedCopy': binding(destination),
                       'byteExactCopy': raw == destination.read_bytes()})
    for name, raw in originals.items():
        assert (ROOT / name).read_bytes() == raw, name + ' changed during collection.'
    summary = {'schemaVersion': 1, 'passed': True, 'capturedAt': now(),
               'scope': 'exact-final-Python-command-logs-and-preserved-independent-holdout-provenance',
               'beforeFrontend': old_frontend,
               'beforeNewTest': {'path': 'tests/test_m4_unknown_boundaries.py', 'existedInArchive': False},
               'afterBindings': [binding(ROOT / name) for name in FINAL_SHA],
               'processes': processes, 'independentRun': {
                   'executedCommand': 'PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python scripts/check_m4_holdout.py --project .',
                   'originalToolChunk': 'c9f5ed', 'observedExitCode': 0,
                   'standaloneCopy': str(release), 'formalProject': str(ROOT),
                   'pythonIsolation': independent['pythonIsolation'], 'sourceCopiesExactlyFinal': True,
                   'freshRunRepeated': False, 'preservedInputs': copies},
               'limitations': ['No browser behavior, performance, physical-size publication or human task certification.',
                               'Independent report absolute original paths are retained byte-exact; preservedInputs resolves the new copies.']}
    json_new(WORK / 'python-final-command-receipts.json', summary)
    print(json.dumps({'passed': True, 'report': str(WORK / 'python-final-command-receipts.json'),
                      'tests': [process['observedTests'] for process in processes]}, indent=2))


if __name__ == '__main__':
    main()
