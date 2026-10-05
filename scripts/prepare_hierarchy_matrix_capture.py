#!/usr/bin/env python3
"""Bind operator-saved DOM/images to an exact existing local Studio export.

This helper never controls a browser, exports a figure, invents observations,
stamps screenshot hashes, or certifies a human review. A stale direct link is
an error. It deliberately does not search for a replacement export.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit
import xml.etree.ElementTree as ET

from browser_visual_matrix import (CAPTURE_PROTOCOL, FIELDS, PROTOCOL,
                                  semantic_svg_digest, verified_spec)

HELPER_PROTOCOL = 'archcanvas-hierarchy-matrix-capture-helper/1'
SAFE_CASE = re.compile(r'[A-Za-z0-9_-]{1,100}\Z')
SAFE_DOCUMENT = re.compile(r'[A-Za-z0-9._-]{1,250}\Z')
EXPORT_PATH = re.compile(r'/api/exports/([a-f0-9]{32})/figure\.svg\Z')
NAMES = {'canvas': 'canvas.json', 'svg': 'figure.svg',
         'exportReceipt': 'export-receipt.json', 'screenshot': 'screenshot.jpg',
         'browserScene': 'browser-scene.svg', 'screenReceipt': 'screen-receipt.json'}


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def encode(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2) + '\n').encode()


def obj(value: object, name: str) -> dict:
    if not isinstance(value, dict):
        raise ValueError(f'{name} must be an object.')
    return value


def decoded(raw: bytes, name: str) -> dict:
    return obj(json.loads(raw), name)


def frozen(path: Path) -> tuple[Path, bytes]:
    """Read/hash/parse the same bytes, never silently follow an evidence symlink."""
    path = path.absolute()
    current = path
    while current != current.parent:
        if current.is_symlink():
            raise ValueError(f'Symlinks are not accepted as evidence inputs: {path}')
        current = current.parent
    if not path.is_file():
        raise ValueError(f'Missing actual input: {path}')
    return path, path.read_bytes()


def binding(path: Path, raw: bytes, parent: Path | None = None) -> dict:
    return {'path': str(path.relative_to(parent)) if parent else str(path),
            'sha256': sha(raw), 'bytes': len(raw)}


def recheck(inputs: list[tuple[Path, bytes]]) -> None:
    for path, raw in inputs:
        if frozen(path)[1] != raw:
            raise ValueError(f'Input changed during helper validation: {path}')


def finite(value: object, *, positive: bool = False) -> bool:
    return type(value) in (int, float) and math.isfinite(value) and (not positive or value > 0)


def local_origin(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError('studioUrl must be an operator-observed URL.')
    parsed = urlsplit(value)
    if (parsed.scheme != 'http' or parsed.hostname not in ('127.0.0.1', 'localhost')
            or parsed.username or parsed.password or not parsed.port):
        raise ValueError('An actual loopback Studio URL with explicit port is required.')
    return f'{parsed.scheme}://{parsed.netloc}'


def timezone_timestamp(value: object, label: str) -> str:
    if not isinstance(value, str) or datetime.fromisoformat(value.replace('Z', '+00:00')).utcoffset() is None:
        raise ValueError(f'{label} must be an actual ISO timestamp with timezone.')
    return value


def validate_environment(raw: dict) -> tuple[dict, dict]:
    environment = obj(raw.get('environment'), 'observed environment')
    viewport = obj(environment.get('viewport'), 'observed viewport')
    if (not isinstance(environment.get('userAgent'), str) or not environment['userAgent']
            or not all(finite(viewport.get(field), positive=True) for field in ('width', 'height'))
            or not finite(environment.get('devicePixelRatio'), positive=True)):
        raise ValueError('Actual userAgent, finite positive viewport and DPR are required.')
    # Unknown values remain explicit, rather than inferred from the machine running this helper.
    for key in ('browserVersion', 'hardware', 'fontEvidence'):
        if key not in environment:
            raise ValueError(f'Observed environment must explicitly retain {key}, including null/empty when unknown.')
    if not isinstance(environment['fontEvidence'], list):
        raise ValueError('fontEvidence must be an observed list; an empty list means unknown.')
    camera = obj(raw.get('camera'), 'observed camera')
    bounds = obj(camera.get('sceneScreenBounds'), 'observed Scene screen bounds')
    if (not isinstance(camera.get('transform'), str) or not camera['transform']
            or not all(finite(bounds.get(key), positive=key in ('width', 'height'))
                       for key in ('x', 'y', 'width', 'height'))):
        raise ValueError('Actual camera transform and finite positive Scene bounds are required.')
    return environment, camera


def prepare_case(matrix: Path, store: Path, raw_path: Path, browser_scene: Path,
                 screenshot: Path, output: Path, saved_envelope: Path | None = None) -> dict:
    matrix, store, output = matrix.absolute(), store.absolute(), output.absolute()
    if output.exists():
        raise ValueError('Case output already exists; use a fresh case to preserve prior evidence.')
    spec = verified_spec(matrix)
    spec_input = frozen(matrix / 'spec.json')
    if decoded(spec_input[1], 'matrix spec') != spec:
        raise ValueError('Matrix spec changed between formal verification and input freeze.')
    inputs = [spec_input, frozen(raw_path), frozen(browser_scene), frozen(screenshot)]
    raw = decoded(inputs[1][1], 'operator DOM observation')
    case, variant_id, state = raw.get('caseId'), raw.get('variantId'), raw.get('state')
    if not isinstance(case, str) or not SAFE_CASE.fullmatch(case) or state not in ('baseline', 'edited'):
        raise ValueError('Operator observation requires a safe caseId and baseline/edited state.')
    variants = [item for item in spec['variants'] if item['variantId'] == variant_id]
    if len(variants) != 1:
        raise ValueError('variantId must uniquely identify a current frozen matrix variant.')
    variant = variants[0]
    timestamp = timezone_timestamp(raw.get('capturedAt'), 'capturedAt')
    if raw.get('captureScope') != 'studio-viewport' or not isinstance(raw.get('limitations'), list):
        raise ValueError('The observation must explicitly state studio-viewport scope and limitations.')
    origin = local_origin(raw.get('studioUrl'))
    environment, camera = validate_environment(raw)
    observed = obj(raw.get('actualExport'), 'observed export')
    export_url = observed.get('observedUrl')
    if not isinstance(export_url, str):
        raise ValueError('A freshly observed actual export direct link is required for each case.')
    parsed = urlsplit(export_url)
    if parsed.query or parsed.fragment or (parsed.netloc and f'{parsed.scheme}://{parsed.netloc}' != origin):
        raise ValueError('The observed direct export link must use the current Studio origin without query/fragment.')
    match = EXPORT_PATH.fullmatch(parsed.path)
    if not match:
        raise ValueError('The observed direct link must identify one concrete SVG artifact.')
    identity = match.group(1)
    export_dir = store.parent / 'exports' / identity
    # No newest-by-time, same-source or unique-match fallback: exact observed ID only.
    export_inputs = [frozen(export_dir / name) for name in ('document.json', 'figure.svg', 'figure.svg.receipt.json')]
    inputs.extend(export_inputs)
    document = decoded(export_inputs[0][1], 'actual export CanvasDocument')
    doc_id = document.get('id')
    if not isinstance(doc_id, str) or not SAFE_DOCUMENT.fullmatch(doc_id):
        raise ValueError('Actual export document identity is invalid.')
    observed_store_path = store / f'{doc_id}.json'
    if saved_envelope is None:
        stored_input = frozen(observed_store_path)
        storage_observation = {'kind': 'live-document-store', 'sourcePath': str(observed_store_path)}
    else:
        stored_input = frozen(saved_envelope)
        snapshot_receipt_input = frozen(Path(str(stored_input[0]) + '.receipt.json'))
        snapshot_receipt = decoded(snapshot_receipt_input[1], 'operator saved-envelope snapshot receipt')
        snapshot_observation = obj(raw.get('actualStoredEnvelope'), 'operator saved-envelope snapshot observation')
        if snapshot_receipt != snapshot_observation:
            raise ValueError('Raw actualStoredEnvelope differs from the copied snapshot metadata receipt.')
        for field in ('observedSourcePath', 'snapshotPath'):
            if not isinstance(snapshot_observation.get(field), str):
                raise ValueError(f'Operator snapshot observation requires {field}.')
        if (Path(snapshot_observation['observedSourcePath']).resolve() != observed_store_path.resolve()
                or Path(snapshot_observation['snapshotPath']).resolve() != stored_input[0].resolve()):
            raise ValueError('Saved-envelope observed source/snapshot paths differ from the declared store/document and exact input argument.')
        timezone_timestamp(snapshot_observation.get('copiedAt'), 'snapshot copiedAt')
        if (snapshot_observation.get('sha256') != sha(stored_input[1])
                or type(snapshot_observation.get('bytes')) is not int
                or snapshot_observation['bytes'] != len(stored_input[1])):
            raise ValueError('Operator snapshot metadata does not bind the exact frozen envelope bytes.')
        inputs.append(snapshot_receipt_input)
        storage_observation = {'kind': 'operator-document-store-snapshot', **snapshot_observation,
            'provenanceScope': 'Operator-declared direct file copy, not a native provenance certification.'}
    inputs.append(stored_input)
    stored = decoded(stored_input[1], 'actual DocumentStore envelope')
    if type(stored.get('revision')) is not int or stored['revision'] < 1:
        raise ValueError('Actual DocumentStore storage revision is invalid.')
    if stored.get('document') != document:
        raise ValueError('Observed export link is stale or current Canvas was not saved: full DocumentStore/export Canvas mismatch. No fallback attempted.')
    document_binding = {'documentId': doc_id, 'revision': document.get('revision'),
                        'sourceDigest': variant['sourceDigest'], 'irDigest': variant['irDigest']}
    if type(document_binding['revision']) is not int or document_binding['revision'] < 0:
        raise ValueError('Actual visual revision is invalid.')
    if raw.get('documentBinding') != document_binding:
        raise ValueError('Actual exported/saved Canvas binding differs from current operator DOM observation. No fallback attempted.')
    expected_page = {'widthMm': variant['widthMm'], 'preset': variant['preset']}
    if raw.get('pageSpec') != expected_page or sorted(raw.get('expandedIds', [])) != sorted(variant['expandedIds']):
        raise ValueError('Observed page/frontier differs from the declared matrix variant.')
    baseline_input = frozen(Path(variant['canvasFile']))
    inputs.append(baseline_input)
    baseline = decoded(baseline_input[1], 'frozen baseline Canvas')
    if (document.get('architecture') != baseline['architecture'] or doc_id != variant['documentId']
            or document.get('sourceBindingDigest') != variant['sourceDigest']
            or sorted(document.get('expandedIds', [])) != sorted(variant['expandedIds'])
            or {key: document.get('pageSpec', {}).get(key) for key in expected_page} != expected_page):
        raise ValueError('Saved/exported Canvas differs from declared source/frontier/page.')
    changed = [key for key in FIELDS if document.get(key) != baseline.get(key)]
    if state == 'baseline' and any(key != 'layout' for key in changed):
        raise ValueError('An edited visual field cannot be declared an unedited baseline.')
    if state == 'edited' and not changed:
        raise ValueError('An edited case requires changed visual fields.')
    scene_bytes = inputs[2][1]
    semantic_svg_digest(scene_bytes)  # Declared XML and budget checks, on the exact copied bytes.
    scene = ET.fromstring(scene_bytes)
    metadata_element = scene.find('{http://www.w3.org/2000/svg}metadata')
    metadata = decoded((metadata_element.text or '').encode() if metadata_element is not None else b'', 'actual SVG metadata')
    if (scene.attrib.get('data-document-id') != doc_id or scene.attrib.get('data-revision') != str(document['revision'])
            or {key: metadata.get(key) for key in document_binding} != document_binding
            or metadata.get('widthMm') != variant['widthMm']):
        raise ValueError('Actual browser Scene does not bind the same document/source/revision/page as the observed export.')
    receipt = decoded(export_inputs[2][1], 'actual publication receipt')
    figure_bytes = export_inputs[1][1]
    if (receipt.get('format') != 'svg' or {key: receipt.get(key) for key in document_binding} != document_binding
            or receipt.get('widthMm') != variant['widthMm'] or receipt.get('exportScope') != {'kind': 'document'}
            or receipt.get('outputDigest') != sha(figure_bytes) or receipt.get('bytes') != len(figure_bytes)):
        raise ValueError('Exact observed export receipt fails its current whole-document binding.')
    shot_bytes = inputs[3][1]
    if not shot_bytes.startswith(b'\xff\xd8\xff'):
        raise ValueError('This capture helper requires an actual operator-saved JPEG screenshot.')
    expected_assets = {item['path']: item for item in spec['buildFiles'] if item['path'].endswith(('.js', '.css'))}
    loaded, asset_inputs, seen = [], [], set()
    if not isinstance(raw.get('loadedBuildAssets'), list):
        raise ValueError('Actual loaded JS/CSS observations are required per case.')
    for asset in raw['loadedBuildAssets']:
        asset = obj(asset, 'observed loaded asset')
        path, url = asset.get('path'), asset.get('url')
        expected = expected_assets.get(path)
        if (expected is None or path in seen or not isinstance(url, str)
                or url != origin + '/' + path):
            raise ValueError('Observed loaded asset is duplicated, undeclared or not from current Studio origin.')
        build_input = frozen(Path(__file__).resolve().parents[1] / 'studio/dist' / path)
        if sha(build_input[1]) != expected['sha256'] or len(build_input[1]) != expected['bytes']:
            raise ValueError('Actual local loaded-build candidate changed from the frozen matrix.')
        asset_inputs.append(build_input)
        loaded.append({**asset, 'sha256': expected['sha256']})
        seen.add(path)
    if seen != set(expected_assets):
        raise ValueError('Observed loaded assets omit a frozen JS/CSS build file.')
    inputs.extend(asset_inputs)
    screen = {'schemaVersion': 1, 'protocol': CAPTURE_PROTOCOL, 'caseId': case,
              'variantId': variant_id, 'state': state, 'captureKind': 'studio-browser',
              'capturedAt': timestamp, 'documentBinding': document_binding,
              'pageSpec': raw['pageSpec'], 'expandedIds': raw['expandedIds'],
              'environment': environment, 'camera': camera, 'loadedBuildAssets': loaded,
              'captureScope': raw['captureScope'], 'limitations': raw['limitations'] + [
                  'This helper copied actual input bytes; screenshot/Scene hash stamping and formal collection remain separate.',
                  'Loaded asset hashes bind observed URLs to local frozen files, not a browser-response-byte read.',
                  'Local consistency does not certify screenshot pixels, human review, font resolution or physical readability.'],
              'actualExport': {'observedUrl': export_url, 'serviceArtifactId': identity,
                               'sourceDirectory': str(export_dir)},
              'actualStoredEnvelope': storage_observation,
              'screenshotDigest': None, 'browserSceneDigest': None}
    copied = {'canvas.json': export_inputs[0][1], 'figure.svg': figure_bytes,
              'export-receipt.json': export_inputs[2][1], 'screenshot.jpg': shot_bytes,
              'browser-scene.svg': scene_bytes, 'screen-receipt.json': encode(screen),
              'screen-receipt-unstamped.json': encode(screen),
              'dom-observation.json': inputs[1][1], 'actual-document-store.json': stored_input[1]}
    if saved_envelope is not None:
        copied['actual-document-store-snapshot-receipt.json'] = snapshot_receipt_input[1]
        screen['limitations'].append('Saved envelope snapshot is an operator-declared direct file copy with bound paths/time/bytes; this does not certify native provenance.')
        copied['screen-receipt.json'] = copied['screen-receipt-unstamped.json'] = encode(screen)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix='.hierarchy-matrix-case-', dir=output.parent))
    try:
        for name, data in copied.items():
            (temporary / name).write_bytes(data)
        result = {'schemaVersion': 1, 'protocol': HELPER_PROTOCOL,
                  'caseId': case, 'variantId': variant_id, 'state': state,
                  'matrixSpecDigest': sha(spec_input[1]), 'observedStudioUrl': raw['studioUrl'],
                  'exactExportArtifactId': identity, 'replacementExportSearch': 'not-attempted',
                  'fullSavedAndExportCanvasEquality': True, 'storageRevision': stored['revision'],
                  'savedEnvelopeObservation': storage_observation,
                  'changedVisualFields': changed, 'screenHashesStamped': False,
                  'formalCollectionExecuted': False, 'humanAcceptanceCertified': False,
                  'inputBindings': [binding(path, data) for path, data in inputs],
                  # screen receipt is intentionally omitted: the explicit stamp step changes it.
                  'copiedFiles': [binding(temporary / name, data, temporary) for name, data in copied.items()
                                  if name != 'screen-receipt.json'],
                  'capture': {'caseId': case, 'variantId': variant_id, 'state': state, **NAMES}}
        (temporary / 'case-helper.json').write_bytes(encode(result))
        recheck(inputs)
        if output.exists():
            raise ValueError('Case output appeared during validation; refusing replacement.')
        temporary.rename(output)
        return result
    except Exception:
        shutil.rmtree(temporary)
        raise


def prepare_index(matrix: Path, cases: Path, output: Path) -> dict:
    matrix, cases, output = matrix.absolute(), cases.absolute(), output.absolute()
    if output.exists():
        raise ValueError('Capture index already exists; preserve prior inputs and use a fresh path.')
    spec = verified_spec(matrix)
    spec_input = frozen(matrix / 'spec.json')
    if decoded(spec_input[1], 'matrix spec') != spec:
        raise ValueError('Matrix spec changed between formal verification and input freeze.')
    inputs, captures, seen, baseline_seen = [spec_input], [], set(), set()
    helpers = sorted(cases.glob('*/case-helper.json'))
    if not helpers:
        raise ValueError('No prepared actual case helpers found.')
    for helper_path in helpers:
        helper_input = frozen(helper_path)
        inputs.append(helper_input)
        helper = decoded(helper_input[1], 'case helper')
        if helper.get('protocol') != HELPER_PROTOCOL or helper.get('matrixSpecDigest') != sha(spec_input[1]):
            raise ValueError('Case helper is not bound to the exact current matrix spec.')
        case_files = {}
        for item in helper['copiedFiles']:
            file_input = frozen(helper_path.parent / item['path'])
            inputs.append(file_input)
            if binding(file_input[0], file_input[1], helper_path.parent) != item:
                raise ValueError('Prepared actual input bytes changed after helper copy.')
            case_files[item['path']] = file_input[1]
        record = helper['capture']
        if record['caseId'] in seen or (record['state'] == 'baseline' and record['variantId'] in baseline_seen):
            raise ValueError('Duplicate case or baseline variant in prepared cases.')
        seen.add(record['caseId'])
        if record['state'] == 'baseline':
            baseline_seen.add(record['variantId'])
        screen_input = frozen(helper_path.parent / NAMES['screenReceipt'])
        inputs.append(screen_input)
        screen = decoded(screen_input[1], 'operator screen receipt')
        original_screen = decoded(case_files['screen-receipt-unstamped.json'], 'retained unstamped screen receipt')
        if {key: value for key, value in screen.items() if key not in ('screenshotDigest', 'browserSceneDigest')} != {
                key: value for key, value in original_screen.items() if key not in ('screenshotDigest', 'browserSceneDigest')}:
            raise ValueError('Screen observation facts changed during the separate hash stamp step.')
        shot, scene = case_files[NAMES['screenshot']], case_files[NAMES['browserScene']]
        if (screen.get('screenshotDigest') != sha(shot)
                or screen.get('browserSceneDigest') != semantic_svg_digest(scene)):
            raise ValueError('Run the separate actual stamp-hashes step before preparing the collect input index.')
        located = {key: str((helper_path.parent / name).relative_to(output.parent)) for key, name in NAMES.items()}
        captures.append({'caseId': record['caseId'], 'variantId': record['variantId'], 'state': record['state'], **located})
    result = {'schemaVersion': 1, 'protocol': PROTOCOL, 'captures': captures}
    recheck(inputs)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('xb') as handle:
        handle.write(encode(result))
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    case = commands.add_parser('case', help='Copy one exact observed, saved export and retain raw observations; no stamping')
    for name in ('matrix', 'store', 'raw', 'browser-scene', 'screenshot', 'output'):
        case.add_argument('--' + name, required=True, type=Path)
    case.add_argument('--saved-envelope', type=Path,
                      help='Use the exact operator-copied store envelope and its .receipt.json metadata instead of the live store file')
    index = commands.add_parser('index', help='Create a collect input list after the separate stamp step')
    for name in ('matrix', 'cases', 'output'):
        index.add_argument('--' + name, required=True, type=Path)
    args = parser.parse_args()
    try:
        if args.command == 'case':
            result = prepare_case(args.matrix, args.store, args.raw, args.browser_scene, args.screenshot, args.output, args.saved_envelope)
        else:
            result = prepare_index(args.matrix, args.cases, args.output)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (OSError, ValueError, TypeError, KeyError, ET.ParseError) as error:
        parser.exit(1, f'{error}\n')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
