#!/usr/bin/env python3
"""Use an explicitly supplied root variant-only correction, preserving originals.

This local workflow adapter never corrects files itself. The unchanged formal
helper still requires exact canonical frontier, page, source and export UUID.
"""
from __future__ import annotations

import argparse
import json
import re
import runpy
from pathlib import Path

BASE = Path(__file__).resolve().parent / 'bind-completed-cases.py'
shared = runpy.run_path(str(BASE))
ROOT, WORK, MATRIX, STORE = (shared[key] for key in ('ROOT', 'WORK', 'MATRIX', 'STORE'))
now, frozen, emit, run = (shared[key] for key in ('now', 'frozen', 'emit', 'run'))


def bind_corrected(case):
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,100}', case):
        raise ValueError('Unsafe case identity.')
    raw, output = WORK / 'raw' / case, WORK / 'bound' / case
    if output.exists():
        raise ValueError(f'Existing bound case preserved: {case}')
    base = WORK / 'binding-process' / case
    base.mkdir(parents=True, exist_ok=True)
    attempt = 1
    while (base / f'attempt-{attempt}').exists():
        attempt += 1
    logs = base / f'attempt-{attempt}'
    logs.mkdir(exist_ok=False)
    try:
        original_path = raw / 'dom-observation.json'
        correct_path = raw / 'dom-observation-correct-variant.json'
        original = json.loads(original_path.read_bytes())
        correct = json.loads(correct_path.read_bytes())
        if (correct.get('caseId') != case or original.get('caseId') != case
                or correct.get('variantId') == original.get('variantId')
                or {key: value for key, value in correct.items() if key != 'variantId'}
                != {key: value for key, value in original.items() if key != 'variantId'}):
            raise ValueError('Supplied correction must differ only in variantId, retaining the exact original case.')
        if (raw / 'dom-observation-original-caseid.json').read_bytes() != original_path.read_bytes():
            raise ValueError('Root original-caseid copy differs from original raw bytes.')
        href = (raw / 'observed-href.txt').read_text().strip()
        if href != correct['actualExport']['observedUrl'] or not re.fullmatch(r'/api/exports/[a-f0-9]{32}/figure\.svg', href):
            raise ValueError('Exact observed href differs from raw corrected input; no fallback.')
        if correct.get('studioUrl') != 'http://127.0.0.1:8985/' or correct.get('dialogCount') != 0:
            raise ValueError('Completed current Studio origin/no-dialog observation required.')
        environment = correct['environment']['provenance']['userAgentDevicePixelRatio']
        environment_path = ROOT / environment['path']
        environment_binding = frozen(environment_path)
        if environment_binding['bytes'] != environment['bytes'] or environment_binding['sha256'] != environment['sha256']:
            raise ValueError('Environment provenance file changed.')
        exact_export = STORE.parent / 'exports' / href.split('/')[3]
        envelope = json.loads((raw / 'saved-envelope.json').read_bytes())
        if envelope['document'] != json.loads((exact_export / 'document.json').read_bytes()):
            raise ValueError('Exact UUID export Canvas differs from saved snapshot; no fallback.')
        paths = [MATRIX / 'spec.json', BASE, Path(__file__), ROOT / 'scripts/prepare_hierarchy_matrix_capture.py',
                 ROOT / 'scripts/browser_visual_matrix.py', environment_path,
                 *(raw / name for name in ('dom-observation.json', 'dom-observation-original-caseid.json',
                     'dom-observation-correct-variant.json', 'browser-scene.svg', 'screenshot.jpg',
                     'saved-envelope.json', 'saved-envelope.json.receipt.json', 'observed-href.txt')),
                 *(exact_export / name for name in ('document.json', 'figure.svg', 'figure.svg.receipt.json'))]
        before = [frozen(path) for path in paths]
        emit(logs / 'inputs-before.json', {'bindings': before, 'scope': 'Explicit root variant-only correction; all original raw bytes retained.'})
        python = str(ROOT / '.venv/bin/python')
        helper = run([python, '-B', 'scripts/prepare_hierarchy_matrix_capture.py', 'case', '--matrix', str(MATRIX),
            '--store', str(STORE), '--raw', str(correct_path), '--browser-scene', str(raw / 'browser-scene.svg'),
            '--screenshot', str(raw / 'screenshot.jpg'), '--saved-envelope', str(raw / 'saved-envelope.json'),
            '--output', str(output)], logs, 'helper')
        unstamped = (output / 'screen-receipt-unstamped.json').read_bytes()
        if (output / 'screen-receipt.json').read_bytes() != unstamped:
            raise ValueError('Formal helper screen output differs before stamping.')
        stamp = run([python, '-B', 'scripts/browser_visual_matrix.py', 'stamp-hashes',
            '--receipt', str(output / 'screen-receipt.json'), '--screenshot', str(output / 'screenshot.jpg'),
            '--browser-scene', str(output / 'browser-scene.svg')], logs, 'stamp')
        screen, original_screen = json.loads((output / 'screen-receipt.json').read_bytes()), json.loads(unstamped)
        keys = {'screenshotDigest', 'browserSceneDigest'}
        if ({key: value for key, value in screen.items() if key not in keys}
                != {key: value for key, value in original_screen.items() if key not in keys}
                or (output / 'screen-receipt-unstamped.json').read_bytes() != unstamped):
            raise ValueError('Stamp changed fields beyond the two screen digests or altered retained original.')
        after = [frozen(path) for path in paths]
        if before != after:
            raise ValueError('Inputs changed during helper/stamp; output retained.')
        emit(logs / 'inputs-after.json', {'bindings': after, 'allBeforeAfterExact': True})
        receipt = {'schemaVersion': 1, 'caseId': case, 'variantId': correct['variantId'], 'createdAt': now(),
            'state': 'bound-and-hash-stamped', 'exactExportArtifactId': exact_export.name, 'helper': helper, 'stamp': stamp,
            'inputCount': len(before), 'allInputsUnchanged': True, 'rawOriginalsPreserved': True,
            'onlyTwoScreenHashFieldsChanged': True, 'liveStoreRead': False, 'replacementExportSearch': 'not-attempted',
            'formalCollectionExecuted': False, 'humanAcceptanceCertified': False,
            'scope': 'Local exact source/page/canonical-frontier/export binding only; no pixel/human/performance certification.',
            'boundFiles': [frozen(path) for path in sorted(output.iterdir()) if path.is_file()]}
        emit(logs / 'binding-receipt.json', receipt)
        return {'caseId': case, 'boundAndStamped': True, 'inputCount': len(before), 'exactExportArtifactId': exact_export.name}
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
            results.append(bind_corrected(case))
    except Exception as error:
        print(json.dumps({'error': str(error), 'completedCases': results}, ensure_ascii=False))
        return 1
    print(json.dumps({'cases': results}, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
