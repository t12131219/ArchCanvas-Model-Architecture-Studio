#!/usr/bin/env python3
"""Authorized evidence stamping/collection with immutable pre-stamp observations.

This work-only runner calls the existing official commands. It does not capture
screenshots, operate Studio, execute model code, or certify pixels/humans/perf.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

WORK = Path(__file__).resolve().parent
ROOT = WORK.parents[2]
MATRIX = ROOT / '.archcanvas/browser-visual-matrix-au3'
BOUND = WORK / 'bound'
INDEX = WORK / 'captures-attempt-1.json'
OUTPUT = ROOT / 'docs/evidence/browser-visual-matrix-au3-current'
UNSTAMPED = WORK / 'unstamped-screen-receipts'
ATTEMPT = WORK / 'collection-attempt-1'
INPUTS = WORK / 'collector-inputs-attempt-1'
HASH_FIELDS = {'screenshotDigest', 'browserSceneDigest'}

specification = importlib.util.spec_from_file_location('au3_case_binder', WORK / 'bind_case.py')
binder = importlib.util.module_from_spec(specification)
specification.loader.exec_module(binder)


def now():
    return datetime.now(timezone.utc).isoformat()


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def record(path):
    path = binder.regular(path)
    return binder.binding(path, path.read_bytes())


def write_new(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as handle:
        handle.write(binder.encoded(value))


def copy_new(source, target):
    raw = binder.regular(source).read_bytes()
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open('xb') as handle:
        handle.write(raw)
    if target.read_bytes() != raw:
        raise ValueError(f'Exact evidence copy failed: {target}')
    return {'source': binder.binding(source, raw), 'snapshot': binder.binding(target, raw), 'byteExact': True}


def inventory(directory):
    return [record(path) for path in sorted(directory.rglob('*')) if path.is_file()]


def command(stage, argv, inputs):
    start, clock = now(), time.monotonic()
    before = [record(path) for path in inputs]
    result = subprocess.run(argv, cwd=ROOT, capture_output=True, timeout=120)
    stdout, stderr = ATTEMPT / (stage + '.stdout.log'), ATTEMPT / (stage + '.stderr.log')
    with stdout.open('xb') as handle:
        handle.write(result.stdout)
    with stderr.open('xb') as handle:
        handle.write(result.stderr)
    receipt = {'schemaVersion': 1, 'stage': stage, 'argv': [str(a) for a in argv],
               'cwd': str(ROOT), 'startedAt': start, 'finishedAt': now(),
               'elapsedSeconds': time.monotonic() - clock, 'exitCode': result.returncode,
               'inputsBefore': before, 'inputsAfter': [record(path) for path in inputs],
               'stdout': record(stdout), 'stderr': record(stderr)}
    write_new(ATTEMPT / (stage + '.command.json'), receipt)
    if result.returncode:
        raise ValueError(f'Official command failed: {stage}; exact logs and receipt retained.')
    return receipt


def main():
    if any(path.exists() for path in (UNSTAMPED, ATTEMPT, INPUTS, INDEX, OUTPUT)):
        raise ValueError('Attempt/snapshot/index/output already exists; preserve and use a new independent attempt.')
    ATTEMPT.mkdir()
    started = now()
    summary = {'schemaVersion': 1, 'startedAt': started,
               'authorization': 'Root explicitly authorized 39-case unstamped preservation, official stamp/index/collect after all-ready.',
               'scope': 'Artifact consistency only. No screenshot pixel, rendered aesthetic, physical readability, human, or performance acceptance.',
               'humans': 0, 'modelExecuted': False, 'productChanged': False,
               'formalCollectionExecuted': False, 'exitCode': None}
    try:
        copy_new(Path(__file__), ATTEMPT / 'runner-source.py')
        copy_new(WORK / 'bind_case.py', ATTEMPT / 'binder-source.py')
        source_before = binder.protected_bindings()
        bound_before = inventory(BOUND)
        cases = []
        for path in sorted(BOUND.glob('*/binding-receipt.json')):
            receipt = json.loads(path.read_bytes())
            for file in receipt['copiedFiles']:
                actual = record(path.parent / file['path'])
                if {key: actual[key] for key in ('bytes', 'sha256')} != {key: file[key] for key in ('bytes', 'sha256')}:
                    raise ValueError(f'Immutable bound evidence changed: {path.parent / file["path"]}')
            capture = receipt['capture']
            screen_path = path.parent / capture['screenReceipt']
            screen_raw = screen_path.read_bytes()
            if screen_raw != (path.parent / 'screen-receipt-unstamped.json').read_bytes():
                raise ValueError(f'Original screen receipt changed before authorized stamp: {path.parent.name}')
            screen = json.loads(screen_raw)
            if any(screen.get(field) is not None for field in HASH_FIELDS):
                raise ValueError('All screen hashes must be null before this attempt.')
            cases.append((path.parent, receipt))
        baselines = [r['variantId'] for _, r in cases if r['state'] == 'baseline']
        edited = [r['variantId'] for _, r in cases if r['state'] == 'edited']
        matrix = json.loads((MATRIX / 'spec.json').read_bytes())
        if (len(cases) != 39 or len(baselines) != 36 or len(set(baselines)) != 36
                or set(baselines) != {v['variantId'] for v in matrix['variants']}
                or len(edited) != 3 or {v.split('-level')[0] for v in edited} != {'transformer', 'mlp', 'residual_cnn'}):
            raise ValueError('Require actual 36 declared baselines plus three edited source models.')
        UNSTAMPED.mkdir()
        frozen = [copy_new(directory / r['capture']['screenReceipt'], UNSTAMPED / (r['caseId'] + '.json'))
                  for directory, r in cases]
        write_new(UNSTAMPED / 'preservation-receipt.json', {'schemaVersion': 1,
                  'preservedAt': now(), 'caseCount': len(frozen), 'copies': frozen,
                  'oldBoundUnstampedBytesExact': True,
                  'historicalInventory': record(WORK / 'bound-baseline-inventory-attempt-1.json'),
                  'allHashesOriginallyNull': True, 'observationsModified': False})
        write_new(ATTEMPT / 'before-inventory.json', {'bound': bound_before, 'sourceBuild': source_before})
        print('39 original unstamped screen receipts preserved exactly.', flush=True)
        transitions = []
        for directory, receipt in cases:
            capture = receipt['capture']
            screen_path = directory / capture['screenReceipt']
            original = json.loads(screen_path.read_bytes())
            stage = 'stamp-' + receipt['caseId']
            cmd = command(stage, [str(ROOT / '.venv/bin/python'), '-B', str(ROOT / 'scripts/browser_visual_matrix.py'),
                         'stamp-hashes', '--receipt', str(screen_path), '--screenshot', str(directory / capture['screenshot']),
                         '--browser-scene', str(directory / capture['browserScene'])],
                         [ROOT / 'scripts/browser_visual_matrix.py', screen_path,
                          directory / capture['screenshot'], directory / capture['browserScene']])
            stamped = json.loads(screen_path.read_bytes())
            if ({k: v for k, v in original.items() if k not in HASH_FIELDS}
                    != {k: v for k, v in stamped.items() if k not in HASH_FIELDS}
                    or stamped['screenshotDigest'] != sha((directory / capture['screenshot']).read_bytes())
                    or stamped['browserSceneDigest'] != binder.semantic_svg_digest((directory / capture['browserScene']).read_bytes())):
                raise ValueError('Stamp changed observations or supplied incorrect file hashes.')
            transitions.append({'caseId': receipt['caseId'], 'before': cmd['inputsBefore'][1],
                                'after': cmd['inputsAfter'][1], 'onlyTwoHashFieldsChanged': True,
                                'beforeHashes': {k: original[k] for k in sorted(HASH_FIELDS)},
                                'afterHashes': {k: stamped[k] for k in sorted(HASH_FIELDS)},
                                'unstampedPreserved': record(UNSTAMPED / (receipt['caseId'] + '.json')),
                                'commandReceipt': record(ATTEMPT / (stage + '.command.json'))})
        write_new(ATTEMPT / 'stamp-transitions.json', {'schemaVersion': 1, 'caseCount': len(transitions),
                                                     'allOnlyTwoHashFieldsChanged': True, 'cases': transitions})
        after_stamp = inventory(BOUND)
        old = {r['path']: r for r in bound_before}
        changed = [r['path'] for r in after_stamp if old.get(r['path']) != r]
        expected = sorted(binder.relative(directory / r['capture']['screenReceipt']) for directory, r in cases)
        if sorted(changed) != expected or len(old) != len(after_stamp) or binder.protected_bindings() != source_before:
            raise ValueError('Unexpected bound/source/build changes during authorized stamping.')
        print('39 official stamp commands passed; only two hashes changed per case.', flush=True)
        command('index', [str(ROOT / '.venv/bin/python'), '-B', str(WORK / 'bind_case.py'), 'index', '--output', str(INDEX)],
                [WORK / 'bind_case.py', MATRIX / 'spec.json'])
        collector_paths = {INDEX, MATRIX / 'spec.json', ROOT / 'scripts/browser_visual_matrix.py',
                           ROOT / 'scripts/browser_visual_core.mjs', Path(matrix['coreDirectory']) / 'visual-gold-report.json'}
        collector_paths.update(ROOT / item['path'] for item in matrix['implementationFiles'])
        collector_paths.update(ROOT / 'studio/dist' / item['path'] for item in matrix['buildFiles'])
        collector_paths.update(Path(matrix['coreDirectory']) / item['path'] for item in matrix['coreFiles'])
        for variant in matrix['variants']:
            collector_paths.update(Path(variant[key]) for key in ('canvasFile', 'svgFile'))
        for capture in json.loads(INDEX.read_bytes())['captures']:
            collector_paths.update((INDEX.parent / capture[key]).absolute() for key in
                                   ('canvas', 'svg', 'exportReceipt', 'screenshot', 'browserScene', 'screenReceipt'))
        INPUTS.mkdir()
        input_copies = [copy_new(path, INPUTS / path.relative_to(ROOT)) for path in sorted(collector_paths)]
        python_path = (ROOT / '.venv/bin/python').resolve()
        node_path = Path(shutil.which('node')).resolve()
        write_new(INPUTS / 'inputs-receipt.json', {'schemaVersion': 1, 'preservedAt': now(),
                  'inputCount': len(input_copies), 'copies': input_copies,
                  'runtimePaths': {'python': record(python_path), 'node': record(node_path)},
                  'scope': 'Exact complete explicit collector file inputs plus frozen implementation/build/core and runtime binary identities. Environment is not dumped.'})
        print('Index and exact collector inputs preserved; running official collect.', flush=True)
        summary['formalCollectionExecuted'] = True
        collector = command('collect', [str(ROOT / '.venv/bin/python'), '-B', str(ROOT / 'scripts/browser_visual_matrix.py'),
                            'collect', '--matrix', str(MATRIX), '--captures', str(INDEX), '--output', str(OUTPUT)],
                            sorted(collector_paths))
        if collector['inputsBefore'] != collector['inputsAfter'] or binder.protected_bindings() != source_before:
            raise ValueError('Collector input/product/source/build changed during collection.')
        manifest = json.loads((OUTPUT / 'manifest.json').read_bytes())
        summary.update({'finishedAt': now(), 'exitCode': 0, 'caseCount': len(cases),
                        'baselineCount': len(baselines), 'editedCount': len(edited),
                        'artifactCoverage': manifest['artifactCoverage'],
                        'visualAcceptance': manifest['visualAcceptance'],
                        'humanAcceptanceCertified': manifest['humanAcceptanceCertified'],
                        'sourceBuildBefore': source_before, 'sourceBuildAfter': binder.protected_bindings(),
                        'sourceBuildBeforeAfterExact': True, 'boundBefore': bound_before,
                        'boundAfter': inventory(BOUND), 'changedBoundPaths': changed,
                        'onlyScreenReceiptHashStampingMutatedBoundInputs': True,
                        'collectorInputsBeforeAfterExact': True,
                        'collectorOutput': inventory(OUTPUT), 'index': record(INDEX),
                        'stampTransitions': record(ATTEMPT / 'stamp-transitions.json')})
        write_new(ATTEMPT / 'attempt-receipt.json', summary)
        print(json.dumps({'exitCode': 0, 'caseCount': len(cases), 'output': binder.relative(OUTPUT),
                          'artifactCoverage': manifest['artifactCoverage'], 'visualAcceptance': manifest['visualAcceptance'],
                          'humanAcceptanceCertified': manifest['humanAcceptanceCertified'],
                          'receipt': binder.relative(ATTEMPT / 'attempt-receipt.json')}, indent=2), flush=True)
        return 0
    except Exception as error:
        summary.update({'finishedAt': now(), 'exitCode': 1, 'error': str(error)})
        write_new(ATTEMPT / 'attempt-receipt.json', summary)
        print(json.dumps({'exitCode': 1, 'error': str(error), 'receipt': binder.relative(ATTEMPT / 'attempt-receipt.json')}), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
