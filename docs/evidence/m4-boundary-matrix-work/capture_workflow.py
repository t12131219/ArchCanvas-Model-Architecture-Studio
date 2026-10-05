#!/usr/bin/env python3
"""Exclusive local-byte capture packaging; never controls or requests a browser.

The operator must first save genuine current DOM, SVG and native screenshot
bytes. This adapter checks frozen formal contracts, copies the exact named
service files, and creates immutable receipts/indices. It grants no human or
pixel acceptance and does not change the frozen product/helper implementation.
"""
from __future__ import annotations

import argparse
import base64
import json
import re
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
import prepare_hierarchy_matrix_capture as formal
from browser_visual_matrix import PROTOCOL, verified_spec, semantic_svg_digest

MATRIX = ROOT / '.archcanvas/browser-visual-matrix-boundary-final'
SEAL = ROOT / 'docs/evidence/m4-boundary-final-verification.json'
STORE = Path('/tmp/archcanvas-m4-boundary-matrix/documents')
ORIGIN = 'http://127.0.0.1:8906'
GUARD = HERE / 'preparation-guard.json'
STAMPED = 'screen-receipt-stamped.json'


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def read(path: Path) -> tuple[Path, bytes]:
    return formal.frozen(path)


def emit(path: Path, data: bytes) -> None:
    # No evidence symlinks or replacement. A race at open is also rejected.
    current = path.absolute()
    while current != current.parent:
        if current.is_symlink():
            raise ValueError(f'Output symlink refused: {path}')
        current = current.parent
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as handle:
        handle.write(data)


def guarded() -> list[tuple[Path, bytes]]:
    guard_input = read(GUARD)
    guard = formal.decoded(guard_input[1], 'preparation guard')
    inputs = [guard_input]
    for item in guard['frozenInputs']:
        frozen_input = read(Path(item['path']))
        if formal.binding(*frozen_input) != item:
            raise ValueError(f'Frozen capture preparation input changed: {item["path"]}')
        inputs.append(frozen_input)
    spec = verified_spec(MATRIX)
    if len(spec['variants']) != 36 or len(spec['frontiers']) != 9:
        raise ValueError('Expected exactly the frozen 36-variant / 9-frontier matrix.')
    # Bind all actual matrix implementation/build/core inputs before and after.
    for field, parent in (('implementationFiles', ROOT), ('buildFiles', ROOT / 'studio/dist'),
                          ('coreFiles', Path(spec['coreDirectory']))):
        for item in spec[field]:
            value = read(parent / item['path'])
            if formal.binding(value[0], value[1], parent) != item:
                raise ValueError('A frozen spec input changed during guard validation.')
            inputs.append(value)
    inputs.append(read(Path(spec['coreDirectory']) / 'visual-gold-report.json'))
    formal.recheck(inputs)
    return inputs


def raw_case(raw_path: Path) -> tuple[dict, tuple[Path, bytes]]:
    raw_input = read(raw_path)
    raw = formal.decoded(raw_input[1], 'operator-observed current DOM')
    case = raw.get('caseId')
    if not isinstance(case, str) or not formal.SAFE_CASE.fullmatch(case):
        raise ValueError('The actual observation must contain a safe caseId.')
    if raw.get('studioUrl') != ORIGIN + '/':
        raise ValueError('Current matrix observations must use the isolated 8906 origin.')
    if 'actualStoredEnvelope' in raw:
        raise ValueError('Use the initial unbound raw observation; this command creates a new bound copy.')
    return raw, raw_input


def bind_observation(raw_path: Path) -> dict:
    inputs = guarded()
    raw, raw_input = raw_case(raw_path)
    inputs.append(raw_input)
    case = raw['caseId']
    output = HERE / 'bound-observations' / case
    if output.exists():
        raise ValueError('A bound observation already exists; preserve it and use a fresh case.')
    document_id = formal.obj(raw.get('documentBinding'), 'document binding').get('documentId')
    if not isinstance(document_id, str) or not formal.SAFE_DOCUMENT.fullmatch(document_id):
        raise ValueError('The current DOM document identity must name the exact saved envelope.')
    source = STORE / (document_id + '.json')
    stored_input = read(source)
    inputs.append(stored_input)
    envelope = formal.decoded(stored_input[1], 'current actual saved envelope')
    document = formal.obj(envelope.get('document'), 'actual saved Canvas')
    if document.get('id') != document_id or document.get('revision') != raw['documentBinding'].get('revision'):
        raise ValueError('The exact saved envelope has a different identity/revision than the current DOM.')
    snapshot = output / 'actual-document-store.json'
    copy_receipt = {'observedSourcePath': str(source), 'snapshotPath': str(snapshot),
                    'copiedAt': now(), 'sha256': formal.sha(stored_input[1]), 'bytes': len(stored_input[1])}
    bound = {**raw, 'actualStoredEnvelope': copy_receipt}
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix='.bound-observation-', dir=output.parent))
    try:
        emit(temporary / 'actual-document-store.json', stored_input[1])
        emit(temporary / 'actual-document-store.json.receipt.json', formal.encode(copy_receipt))
        emit(temporary / 'dom-observation.json', formal.encode(bound))
        receipt = {'schemaVersion': 1, 'protocol': 'archcanvas-boundary-matrix-bound-observation/1',
                   'caseId': case, 'createdAt': now(), 'sourceObservation': formal.binding(*raw_input),
                   'actualStoredEnvelope': copy_receipt, 'inputBindings': [formal.binding(*value) for value in inputs],
                   'scope': 'Direct local file copy declared by operator, not native provenance certification.',
                   'browserOperationExecuted': False, 'exportRequestExecuted': False,
                   'humanAcceptanceCertified': False}
        emit(temporary / 'binding-receipt.json', formal.encode(receipt))
        formal.recheck(inputs)
        if output.exists():
            raise ValueError('Bound observation appeared during validation; refusing replacement.')
        temporary.rename(output)
        return receipt
    except Exception:
        shutil.rmtree(temporary)
        raise


def package_case(case: str, scene_path: Path, screenshot_path: Path) -> dict:
    if not formal.SAFE_CASE.fullmatch(case):
        raise ValueError('Safe case ID required.')
    inputs = guarded()
    observation = HERE / 'bound-observations' / case
    receipt_input = read(observation / 'binding-receipt.json')
    inputs.append(receipt_input)
    receipt = formal.decoded(receipt_input[1], 'bound observation receipt')
    if receipt.get('caseId') != case:
        raise ValueError('Case ID differs from the bound observation receipt.')
    output = HERE / 'cases' / case
    if output.exists():
        raise ValueError('Prepared case already exists; preserve it and use a fresh case.')
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix='.boundary-case-', dir=output.parent))
    try:
        result = formal.prepare_case(MATRIX, STORE, observation / 'dom-observation.json',
                                     scene_path, screenshot_path, temporary / 'prepared',
                                     observation / 'actual-document-store.json')
        formal.recheck(inputs)
        if output.exists():
            raise ValueError('Prepared case appeared during validation; refusing replacement.')
        (temporary / 'prepared').rename(output)
        temporary.rmdir()
        return result
    except Exception:
        shutil.rmtree(temporary)
        raise


def stamp_case(case: str) -> dict:
    if not formal.SAFE_CASE.fullmatch(case):
        raise ValueError('Safe case ID required.')
    inputs = guarded()
    directory = HERE / 'cases' / case
    for name in ('screen-receipt-unstamped.json', 'screenshot.jpg', 'browser-scene.svg', 'case-helper.json'):
        inputs.append(read(directory / name))
    original = formal.decoded(inputs[-4][1], 'unstamped screen receipt')
    if original.get('caseId') != case or original.get('screenshotDigest') is not None or original.get('browserSceneDigest') is not None:
        raise ValueError('Only the actual retained unstamped receipt can be stamped once.')
    stamped = {**original, 'screenshotDigest': formal.sha(inputs[-3][1]),
               'browserSceneDigest': semantic_svg_digest(inputs[-2][1])}
    output = directory / STAMPED
    formal.recheck(inputs)
    emit(output, formal.encode(stamped))
    return {'caseId': case, 'stampedReceipt': formal.binding(*read(output)),
            'scope': 'Two hashes added to a new receipt; original bytes remain unchanged.',
            'humanAcceptanceCertified': False}


def index_cases(output: Path) -> dict:
    # Follow formal index validation while referencing a separately stamped file.
    if output.parent != HERE or not re.fullmatch(r'captures-\d{3}\.json', output.name):
        raise ValueError('Use a new captures-NNN.json directly in this work directory, so cases stay inside the collect input root.')
    inputs = guarded()
    spec_input = read(MATRIX / 'spec.json')
    inputs.append(spec_input)
    captures, seen, baseline_seen = [], set(), set()
    helpers = sorted((HERE / 'cases').glob('*/case-helper.json'))
    if not helpers:
        raise ValueError('No prepared actual case helpers; a template is not a capture.')
    for path in helpers:
        helper_input = read(path)
        inputs.append(helper_input)
        helper = formal.decoded(helper_input[1], 'actual case helper')
        if (helper.get('protocol') != formal.HELPER_PROTOCOL
                or helper.get('matrixSpecDigest') != formal.sha(spec_input[1])):
            raise ValueError('Case helper is not bound to the exact current matrix spec.')
        files = {}
        for item in helper['copiedFiles']:
            file_input = read(path.parent / item['path'])
            if formal.binding(file_input[0], file_input[1], path.parent) != item:
                raise ValueError('A copied actual case input changed after preparation.')
            inputs.append(file_input)
            files[item['path']] = file_input[1]
        record = helper['capture']
        if record['caseId'] in seen or (record['state'] == 'baseline' and record['variantId'] in baseline_seen):
            raise ValueError('Duplicate case or baseline variant.')
        seen.add(record['caseId'])
        if record['state'] == 'baseline':
            baseline_seen.add(record['variantId'])
        stamped_input = read(path.parent / STAMPED)
        inputs.append(stamped_input)
        stamped = formal.decoded(stamped_input[1], 'separately stamped screen receipt')
        original = formal.decoded(files['screen-receipt-unstamped.json'], 'actual unstamped screen receipt')
        if {k:v for k,v in stamped.items() if k not in ('screenshotDigest','browserSceneDigest')} != {
                k:v for k,v in original.items() if k not in ('screenshotDigest','browserSceneDigest')}:
            raise ValueError('Screen observation facts changed during stamping.')
        if (stamped.get('screenshotDigest') != formal.sha(files[formal.NAMES['screenshot']])
                or stamped.get('browserSceneDigest') != semantic_svg_digest(files[formal.NAMES['browserScene']])):
            raise ValueError('Actual screenshot/scene hashes differ from the separate stamp receipt.')
        names = {**formal.NAMES, 'screenReceipt': STAMPED}
        locations = {key: str((path.parent / name).relative_to(output.parent)) for key,name in names.items()}
        captures.append({'caseId':record['caseId'], 'variantId':record['variantId'], 'state':record['state'], **locations})
    result = {'schemaVersion':1, 'protocol':PROTOCOL, 'captures':captures}
    receipt = {'schemaVersion':1, 'protocol':'archcanvas-boundary-matrix-index/1', 'createdAt':now(),
               'captures':len(captures), 'baselines':len(baseline_seen),
               'matrixSpecDigest':formal.sha(spec_input[1]), 'inputBindings':[formal.binding(*v) for v in inputs],
               'scope':'Validated local copied files only; formal collect and actual pixel review remain separate.',
               'humanAcceptanceCertified':False}
    formal.recheck(inputs)
    if output.exists() or Path(str(output)+'.receipt.json').exists():
        raise ValueError('Capture index or receipt already exists; use a new numbered path.')
    emit(output, formal.encode(result))
    emit(Path(str(output)+'.receipt.json'), formal.encode(receipt))
    return receipt


def save_jpeg(input_path: Path, output: Path) -> dict:
    inputs = guarded()
    source_input = read(input_path)
    inputs.append(source_input)
    encoded = source_input[1].decode('ascii').strip()
    if encoded.startswith('data:image/jpeg;base64,'):
        encoded = encoded.removeprefix('data:image/jpeg;base64,')
    decoded = base64.b64decode(''.join(encoded.split()), validate=True)
    if not decoded.startswith(b'\xff\xd8\xff') or not decoded.endswith(b'\xff\xd9'):
        raise ValueError('Expected complete exact JPEG bytes from the actual native image block.')
    receipt = {'schemaVersion':1, 'protocol':'archcanvas-native-tool-image-copy/1', 'savedAt':now(),
               'sourceBase64':formal.binding(*source_input), 'output':formal.binding(output.absolute(),decoded),
               'scope':'Exact base64 byte decoding only; tool provenance is declared by operator.',
               'reencoded':False, 'nativeProvenanceCertified':False, 'humanAcceptanceCertified':False}
    if output.exists() or Path(str(output)+'.receipt.json').exists():
        raise ValueError('Native image output or receipt already exists.')
    formal.recheck(inputs)
    emit(output, decoded)
    emit(Path(str(output)+'.receipt.json'),formal.encode(receipt))
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command',required=True)
    commands.add_parser('verify-frozen')
    bind = commands.add_parser('bind-observation')
    bind.add_argument('--raw',type=Path,required=True)
    case = commands.add_parser('case')
    case.add_argument('--case',required=True)
    case.add_argument('--browser-scene',type=Path,required=True)
    case.add_argument('--screenshot',type=Path,required=True)
    stamp = commands.add_parser('stamp')
    stamp.add_argument('--case',required=True)
    index = commands.add_parser('index')
    index.add_argument('--output',type=Path,required=True)
    jpeg = commands.add_parser('save-jpeg')
    jpeg.add_argument('--base64-input',type=Path,required=True)
    jpeg.add_argument('--output',type=Path,required=True)
    args = parser.parse_args()
    try:
        if args.command == 'verify-frozen':
            inputs = guarded()
            result = {'frozenUnchanged':True,'inputCount':len(inputs),'baselineCaptureCount':0,
                      'scope':'Freeze check only; does not evaluate captures.'}
        elif args.command == 'bind-observation':
            result = bind_observation(args.raw)
        elif args.command == 'case':
            result = package_case(args.case,args.browser_scene,args.screenshot)
        elif args.command == 'stamp':
            result = stamp_case(args.case)
        elif args.command == 'index':
            result = index_cases(args.output.absolute())
        else:
            result = save_jpeg(args.base64_input,args.output.absolute())
        print(json.dumps(result,ensure_ascii=False,indent=2))
    except (OSError,ValueError,TypeError,KeyError) as error:
        parser.exit(1,str(error)+'\n')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
