#!/usr/bin/env python3
"""Bind completed operator captures, preserving every case/attempt and raw byte.

This wrapper only calls the frozen formal local artifact helper and hash stamper.
It never controls the browser, reads the mutable live store, searches for a
replacement export, creates a collection/index, or grants image/human acceptance.
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[3]
WORK = Path(__file__).resolve().parent
MATRIX = ROOT / '.archcanvas/browser-visual-matrix-chs-current'
STORE = ROOT / '.archcanvas/m4-chs-browser-session/documents'


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def digest(data):
    return hashlib.sha256(data).hexdigest()


def frozen(path):
    path = path.absolute()
    if not path.is_file() or path.is_symlink():
        raise ValueError(f'Expected regular input file: {path}')
    data = path.read_bytes()
    return {'path': str(path), 'bytes': len(data), 'sha256': digest(data)}


def emit(path, value):
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write('\n')


def run(argv, directory, prefix):
    started = now()
    completed = subprocess.run(argv, cwd=ROOT, capture_output=True, timeout=120)
    for suffix, data in (('stdout.txt', completed.stdout), ('stderr.txt', completed.stderr)):
        with (directory / f'{prefix}-{suffix}').open('xb') as stream:
            stream.write(data)
    result = {'argv': argv, 'startedAt': started, 'finishedAt': now(), 'exitCode': completed.returncode}
    emit(directory / f'{prefix}-command.json', result)
    if completed.returncode:
        raise ValueError(f'{prefix} failed with exit {completed.returncode}; exact output preserved.')
    return result


def bind(case):
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,100}', case):
        raise ValueError('Unsafe case identity.')
    raw = WORK / 'raw' / case
    output = WORK / 'bound' / case
    if output.exists():
        raise ValueError(f'Existing bound case preserved; do not rerun: {case}')
    log_base = WORK / 'binding-process' / case
    log_base.mkdir(parents=True, exist_ok=True)
    attempt = 1
    while (log_base / f'attempt-{attempt}').exists():
        attempt += 1
    logs = log_base / f'attempt-{attempt}'
    logs.mkdir(exist_ok=False)
    try:
        items = [MATRIX / 'spec.json', Path(__file__), ROOT / 'scripts/prepare_hierarchy_matrix_capture.py',
                 ROOT / 'scripts/browser_visual_matrix.py', ROOT / 'scripts/browser_visual_core.mjs',
                 *(raw / name for name in ('dom-observation.json', 'browser-scene.svg', 'screenshot.jpg',
                                          'saved-envelope.json', 'saved-envelope.json.receipt.json'))]
        observation = json.loads((raw / 'dom-observation.json').read_bytes())
        if observation.get('caseId') != case or observation.get('dialogCount') != 0:
            raise ValueError('Completed raw identity/dialog observation differs from expected case.')
        if observation.get('studioUrl') != 'http://127.0.0.1:8985/':
            raise ValueError('Current actual capture origin must be the isolated 8985 service.')
        environment_source = observation['environment']['provenance']['userAgentDevicePixelRatio']
        environment_path = ROOT / environment_source['path']
        environment_binding = frozen(environment_path)
        if environment_binding['bytes'] != environment_source['bytes'] or environment_binding['sha256'] != environment_source['sha256']:
            raise ValueError('Current support-frame environment provenance binding changed.')
        items.append(environment_path)
        sidecar = json.loads((raw / 'saved-envelope.json.receipt.json').read_bytes())
        if sidecar != observation.get('actualStoredEnvelope'):
            raise ValueError('Snapshot observation and sidecar must match exactly.')
        snapshot = frozen(raw / 'saved-envelope.json')
        if snapshot['bytes'] != sidecar['bytes'] or snapshot['sha256'] != sidecar['sha256']:
            raise ValueError('Copied envelope snapshot bytes do not match sidecar.')
        saved = json.loads((raw / 'saved-envelope.json').read_bytes())['document']
        link = urlsplit(observation['actualExport']['observedUrl'])
        match = re.fullmatch(r'/api/exports/([a-f0-9]{32})/figure\.svg', link.path)
        if not match or link.query or link.fragment or (link.netloc and f'{link.scheme}://{link.netloc}' != 'http://127.0.0.1:8985'):
            raise ValueError('Exact current SVG direct-link UUID required; no fallback.')
        exact_export = STORE.parent / 'exports' / match.group(1)
        items.extend(exact_export / name for name in ('document.json', 'figure.svg', 'figure.svg.receipt.json'))
        if saved != json.loads((exact_export / 'document.json').read_bytes()):
            raise ValueError('Exact UUID export Canvas differs from copied saved envelope; no fallback.')
        before = [frozen(path) for path in items]
        emit(logs / 'inputs-before.json', {'caseId': case, 'createdAt': now(), 'bindings': before,
             'exactExportArtifactId': match.group(1), 'liveStoreRead': False, 'replacementExportSearch': 'not-attempted'})
        python = str(ROOT / '.venv/bin/python')
        helper = run([python, '-B', 'scripts/prepare_hierarchy_matrix_capture.py', 'case',
                      '--matrix', str(MATRIX), '--store', str(STORE), '--raw', str(raw / 'dom-observation.json'),
                      '--browser-scene', str(raw / 'browser-scene.svg'), '--screenshot', str(raw / 'screenshot.jpg'),
                      '--saved-envelope', str(raw / 'saved-envelope.json'), '--output', str(output)], logs, 'helper')
        unstamped = (output / 'screen-receipt-unstamped.json').read_bytes()
        if (output / 'screen-receipt.json').read_bytes() != unstamped:
            raise ValueError('Formal helper screen output differs before stamping.')
        stamp = run([python, '-B', 'scripts/browser_visual_matrix.py', 'stamp-hashes',
                     '--receipt', str(output / 'screen-receipt.json'), '--screenshot', str(output / 'screenshot.jpg'),
                     '--browser-scene', str(output / 'browser-scene.svg')], logs, 'stamp')
        screen = json.loads((output / 'screen-receipt.json').read_bytes())
        original = json.loads(unstamped)
        keys = {'screenshotDigest', 'browserSceneDigest'}
        if {k: v for k, v in screen.items() if k not in keys} != {k: v for k, v in original.items() if k not in keys}:
            raise ValueError('Stamper changed more than the two declared hash fields.')
        if screen['screenshotDigest'] != digest((output / 'screenshot.jpg').read_bytes()):
            raise ValueError('Stamped screenshot digest differs from copied JPEG.')
        if (output / 'screen-receipt-unstamped.json').read_bytes() != unstamped:
            raise ValueError('Retained unstamped screen was changed.')
        after = [frozen(Path(item['path'])) for item in before]
        if before != after:
            raise ValueError('Inputs changed during package/stamp; output retained for audit.')
        emit(logs / 'inputs-after.json', {'caseId': case, 'checkedAt': now(), 'bindings': after, 'allBeforeAfterExact': True})
        receipt = {'schemaVersion': 1, 'caseId': case, 'createdAt': now(), 'state': 'bound-and-hash-stamped',
                   'exactExportArtifactId': match.group(1), 'helper': helper, 'stamp': stamp,
                   'inputCount': len(before), 'allInputsUnchanged': True, 'onlyTwoScreenHashFieldsChanged': True,
                   'rawMutation': False, 'liveStoreRead': False, 'replacementExportSearch': 'not-attempted',
                   'formalCollectionExecuted': False, 'humanAcceptanceCertified': False,
                   'scope': 'Exact saved/export/source/page/frontier/build local-byte consistency only; pixels/native capture/humans/performance not certified.',
                   'boundFiles': [frozen(path) for path in sorted(output.iterdir()) if path.is_file()]}
        emit(logs / 'binding-receipt.json', receipt)
        return {'caseId': case, 'boundDirectory': str(output), 'processDirectory': str(logs),
                'exactExportArtifactId': match.group(1), 'inputsUnchanged': len(before), 'boundAndStamped': True}
    except Exception as error:
        emit(logs / 'failure.json', {'caseId': case, 'failedAt': now(), 'error': str(error),
                                    'partialBoundRetained': output.exists(), 'fallbackAttempted': False})
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('cases', nargs='+')
    arguments = parser.parse_args()
    results = []
    try:
        for case in arguments.cases:
            results.append(bind(case))
    except Exception as error:
        print(json.dumps({'error': str(error), 'completedCases': results}, ensure_ascii=False), file=sys.stderr)
        return 1
    print(json.dumps({'cases': results}, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
