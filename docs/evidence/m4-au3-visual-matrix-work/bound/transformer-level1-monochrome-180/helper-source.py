#!/usr/bin/env python3
"""Bind actual image/DOM/store/export observations without operating Studio.

This evidence-only helper never renders, exports, runs models or grants coverage.
It accepts one exact observed UUID, freezes input bytes, and rejects stale saves.
UA/DPR are explicitly historical same-browser observations; current viewport,
camera, assets and document facts must come from this case's public DOM capture.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import shutil
import struct
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[3]
WORK = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'scripts'))
from browser_visual_matrix import (CAPTURE_PROTOCOL, FIELDS, PROTOCOL,
                                   semantic_svg_digest)

DEFAULT_MATRIX = ROOT / '.archcanvas/browser-visual-matrix-au3'
DEFAULT_STORE = ROOT / '.archcanvas/m4-au3-visual-matrix-session/documents'
DEFAULT_ENV = ROOT / 'docs/evidence/input-observation/stress300-final-observer-raw.json'
SAFE_CASE = re.compile(r'[A-Za-z0-9_-]{1,100}\Z')
SAFE_DOC = re.compile(r'[A-Za-z0-9._-]{1,250}\Z')
EXPORT = re.compile(r'/api/exports/([a-f0-9]{32})/figure\.svg\Z')
SVG_NS = '{http://www.w3.org/2000/svg}'
NAMES = {'canvas': 'canvas.json', 'svg': 'figure.svg',
         'exportReceipt': 'export-receipt.json', 'screenshot': 'screenshot.png',
         'browserScene': 'browser-scene.svg', 'screenReceipt': 'screen-receipt.json'}


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def relative(path: Path) -> str:
    return str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path)


def binding(path: Path, raw: bytes) -> dict:
    return {'path': relative(path), 'bytes': len(raw), 'sha256': digest(raw)}


def encoded(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2) + '\n').encode()


def decode(raw: bytes, name: str, kind: type = dict):
    value = json.loads(raw)
    if not isinstance(value, kind):
        raise ValueError(f'{name} must be {kind.__name__}.')
    return value


def finite(value: object, positive: bool = False) -> bool:
    return type(value) in (int, float) and math.isfinite(value) and (not positive or value > 0)


def timestamp(value: object) -> str:
    if not isinstance(value, str) or datetime.fromisoformat(value.replace('Z', '+00:00')).utcoffset() is None:
        raise ValueError('Actual capture/copy time requires ISO text with timezone.')
    return value


def regular(path: Path) -> Path:
    path = path.absolute()
    current = path
    while current != current.parent:
        if current.is_symlink():
            raise ValueError(f'Evidence symlinks are forbidden: {path}')
        current = current.parent
    if not path.is_file():
        raise ValueError(f'Missing regular evidence file: {path}')
    return path


class FrozenInputs:
    def __init__(self):
        self.files: dict[Path, bytes] = {}

    def read(self, path: Path) -> bytes:
        path = regular(path)
        raw = path.read_bytes()
        if path in self.files and self.files[path] != raw:
            raise ValueError(f'Input changed between reads: {path}')
        self.files[path] = raw
        return raw

    def before(self) -> list[dict]:
        return [binding(path, raw) for path, raw in sorted(self.files.items())]

    def after(self) -> list[dict]:
        result = []
        for path in sorted(self.files):
            if not path.is_file() or path.is_symlink():
                result.append({'path': relative(path), 'missingOrSymlink': True})
            else:
                result.append(binding(path, path.read_bytes()))
        return result

    def recheck(self) -> None:
        if self.before() != self.after():
            raise ValueError('Frozen inputs changed during binding; no successful output published.')


def protected_paths() -> list[Path]:
    paths = set()
    for directory in ('studio/src', 'studio/dist', 'src', 'fixtures'):
        paths.update(p for p in (ROOT / directory).rglob('*')
                     if p.is_file() and '__pycache__' not in p.parts and p.suffix != '.pyc')
    paths.update((ROOT / 'scripts').glob('*.py'))
    paths.update((ROOT / 'scripts').glob('*.mjs'))
    paths.update(ROOT / p for p in ('studio/package.json', 'studio/package-lock.json',
                                  'studio/tsconfig.json', 'studio/vite.config.ts'))
    return sorted(paths)


def protected_bindings() -> list[dict]:
    return [binding(regular(path), path.read_bytes()) for path in protected_paths()]


def matrix_spec(inputs: FrozenInputs, matrix: Path) -> dict:
    spec = decode(inputs.read(matrix / 'spec.json'), 'matrix spec')
    if spec.get('schemaVersion') != 1 or spec.get('protocol') != PROTOCOL:
        raise ValueError('Unsupported frozen matrix protocol.')
    for field, directory in (('implementationFiles', ROOT), ('buildFiles', ROOT / 'studio/dist'),
                             ('coreFiles', Path(spec['coreDirectory']))):
        for record in spec[field]:
            path = directory / record['path']
            if not path.absolute().is_relative_to(directory.absolute()):
                raise ValueError('Frozen matrix file escapes declared root.')
            raw = inputs.read(path)
            if {'path': record['path'], 'bytes': len(raw), 'sha256': digest(raw)} != record:
                raise ValueError(f'Frozen {field} changed: {path}')
    report = inputs.read(Path(spec['coreDirectory']) / 'visual-gold-report.json')
    if digest(report) != spec['coreReportDigest']:
        raise ValueError('Frozen core report changed.')
    if spec.get('expectedBaselineCount') != 36 or len(spec['variants']) != 36 or len(spec['frontiers']) != 9:
        raise ValueError('Expected actual-source 9-frontier/36-variant matrix.')
    return spec


def svg_metadata(raw: bytes) -> tuple[ET.Element, dict]:
    semantic_svg_digest(raw)  # Existing collector's safe XML and byte-budget contract.
    root = ET.fromstring(raw)
    metadata = root.find(SVG_NS + 'metadata')
    if metadata is None or not metadata.text:
        raise ValueError('Actual model SVG metadata missing; an icon is not a Scene.')
    return root, decode(metadata.text.encode(), 'actual SVG metadata')


def exact_export_url(links: list, origin: str) -> tuple[str, str]:
    actual = set()
    for link in links:
        if not isinstance(link, dict) or not isinstance(link.get('href'), str):
            raise ValueError('Actual export links must contain observed href text.')
        parsed = urlsplit(link['href'])
        match = EXPORT.fullmatch(parsed.path)
        if match:
            if parsed.query or parsed.fragment or (parsed.netloc and f'{parsed.scheme}://{parsed.netloc}' != origin):
                raise ValueError('SVG export link has a different origin/query/fragment.')
            actual.add((origin + parsed.path, match.group(1)))
        elif re.search(r'/figure\.', parsed.path):
            raise ValueError('Unexpected figure extension; select and capture actual whole SVG first.')
    if len(actual) != 1:
        raise ValueError('Require exactly one concrete observed SVG UUID; no replacement search.')
    return next(iter(actual))


def image_info(raw: bytes) -> tuple[str, tuple[int, int]]:
    if raw.startswith(b'\x89PNG\r\n\x1a\n'):
        if len(raw) < 33 or raw[12:16] != b'IHDR' or raw[8:12] != b'\0\0\0\r':
            raise ValueError('Actual PNG must have a complete IHDR.')
        width, height = struct.unpack('>II', raw[16:24])
        if not width or not height:
            raise ValueError('PNG dimensions invalid.')
        return '.png', (width, height)
    if raw.startswith(b'\xff\xd8\xff') and raw.endswith(b'\xff\xd9'):
        offset = 2
        frames = {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}
        while offset < len(raw):
            if raw[offset] != 0xFF:
                raise ValueError('Malformed JPEG marker stream.')
            while offset < len(raw) and raw[offset] == 0xFF:
                offset += 1
            if offset >= len(raw):
                break
            marker = raw[offset]
            offset += 1
            if marker in {0x01, 0xD8, 0xD9, *range(0xD0, 0xD8)}:
                continue
            if offset + 2 > len(raw):
                break
            length = int.from_bytes(raw[offset:offset + 2], 'big')
            if length < 2 or offset + length > len(raw):
                raise ValueError('JPEG segment is truncated.')
            if marker in frames:
                if length < 8:
                    raise ValueError('JPEG frame is truncated.')
                height, width = struct.unpack('>HH', raw[offset + 3:offset + 7])
                if width and height:
                    return '.jpg', (width, height)
                raise ValueError('JPEG frame dimensions invalid.')
            if marker == 0xDA:
                break
            offset += length
    raise ValueError('Only actual, complete PNG/JPEG screenshot bytes are accepted.')


def screenshot_input(inputs: FrozenInputs, raw_case: Path) -> tuple[Path, bytes, str, tuple[int, int]]:
    candidates = [p for p in sorted(raw_case.glob('screenshot.*')) if p.suffix.lower() in ('.png', '.jpg', '.jpeg')]
    if not candidates:
        raise ValueError('Actual screenshot input missing.')
    original = raw_case / 'screenshot.png'
    # The first captures were written to screenshot.png regardless of actual
    # magic. A later stray jpg is not evidence of that original capture.
    if not original.exists():
        if len(candidates) != 1:
            raise ValueError('Ambiguous screenshots without original screenshot.png; preserve/investigate.')
        original = candidates[0]
    raw = inputs.read(original)
    suffix, dimensions = image_info(raw)
    if original.suffix.lower() in (('.jpg', '.jpeg') if suffix == '.jpg' else ('.png',)):
        return original, raw, suffix, dimensions
    corrected = raw_case / ('screenshot' + suffix)
    excluded = []
    if corrected.exists():
        sidecar = Path(str(corrected) + '.format-correction.json')
        existing = inputs.read(corrected)
        if sidecar.exists():
            previous = decode(inputs.read(sidecar), 'prior screenshot format correction')
            if (existing == raw and previous.get('original') == binding(original, raw)
                    and previous.get('corrected') == binding(corrected, raw)
                    and previous.get('byteExactCopy') is True and previous.get('reencoded') is False):
                return corrected, raw, suffix, dimensions
            raise ValueError('Prior screenshot correction does not bind original bytes; preserve/investigate.')
        excluded.append({**binding(corrected, existing),
                         'reason': 'Existing sibling has no format-correction receipt; it is excluded, never selected over original screenshot.png.'})
        corrected = raw_case / ('screenshot-format-corrected' + suffix)
        if corrected.exists() or Path(str(corrected) + '.format-correction.json').exists():
            raise ValueError('Disambiguated corrected screenshot path already exists; preserve/investigate.')
    with corrected.open('xb') as handle:
        handle.write(raw)
    provenance = {'schemaVersion': 1, 'generatedAt': now(), 'original': binding(original, raw),
                  'corrected': binding(corrected, raw), 'originalExtension': original.suffix,
                  'actualFormat': 'jpeg' if suffix == '.jpg' else 'png', 'byteExactCopy': True,
                  'reencoded': False, 'originalPreserved': True,
                  'excludedSiblingCandidates': excluded,
                  'scope': 'Filename-only correction by actual image magic. No recapture, pixel change or PNG assertion for JPEG bytes.'}
    sidecar = Path(str(corrected) + '.format-correction.json')
    with sidecar.open('xb') as handle:
        handle.write(encoded(provenance))
    inputs.read(corrected)
    inputs.read(sidecar)
    return corrected, raw, suffix, dimensions


def historical_environment(inputs: FrozenInputs, source: Path, viewport: dict) -> tuple[dict, dict]:
    raw = inputs.read(source)
    observation = decode(raw, 'historical same-IAB environment')
    old = observation['environment']
    ua, dpr = old.get('userAgent'), old.get('viewport', {}).get('devicePixelRatio')
    if not isinstance(ua, str) or not ua or not finite(dpr, True):
        raise ValueError('Historical actual observer UA/DPR missing.')
    if not isinstance(viewport, dict) or not all(finite(viewport.get(key), True) for key in ('width', 'height')):
        raise ValueError('Current public DOM viewport must be positive and finite.')
    time_origin = old.get('timeOrigin')
    origin_utc = datetime.fromtimestamp(time_origin / 1000, timezone.utc).isoformat() if finite(time_origin) else None
    provenance = {'kind': 'historical-same-browser-environment-observation',
                  'source': binding(source.absolute(), raw),
                  'userAgentJsonPointer': '/environment/userAgent',
                  'devicePixelRatioJsonPointer': '/environment/viewport/devicePixelRatio',
                  'historicalObserverUrl': old.get('url'), 'historicalObserverLabel': observation.get('label'),
                  'historicalTimeOriginEpochMs': time_origin, 'historicalTimeOriginUtc': origin_utc,
                  'historicalStartedAtPerformanceMs': observation.get('startedAt'),
                  'historicalStoppedAtPerformanceMs': observation.get('stoppedAt'),
                  'browserAssociation': 'Root identifies historical receipt and current CUA as same IAB browser2; not independently native-certified.',
                  'currentNavigatorObserved': False,
                  'currentNavigatorLimitation': 'Root reported CUA navigator read unavailable (TypeError/undefined). UA/DPR values are historical, not read from this case.',
                  'currentViewportSource': 'This case public-observation.json /viewport',
                  'scope': 'No current browser-version, hardware, resolved-font or physical-pixel calibration certification.'}
    return {'userAgent': ua, 'devicePixelRatio': dpr, 'viewport': viewport,
            'browserVersion': None, 'hardware': None, 'fontEvidence': [],
            'provenance': provenance}, provenance


def bind_case(args, inputs: FrozenInputs, source_before: list[dict], started: str) -> dict:
    case = args.case
    if not SAFE_CASE.fullmatch(case):
        raise ValueError('Unsafe caseId.')
    raw_dir, bound_root = args.raw_root.absolute(), args.bound_root.absolute()
    raw_case, output = raw_dir / case, bound_root / case
    if output.exists():
        raise ValueError('Bound case already exists; preserve it and use a fresh caseId.')
    spec = matrix_spec(inputs, args.matrix.absolute())
    variant_id = args.variant or case
    variants = [variant for variant in spec['variants'] if variant['variantId'] == variant_id]
    if len(variants) != 1:
        raise ValueError('Require exact declared variant; edited/recapture case needs explicit --variant.')
    variant = variants[0]
    if not raw_case.is_dir():
        raise ValueError('Raw case directory missing.')
    for path in sorted(raw_case.rglob('*')):
        if path.is_file() or path.is_symlink():
            inputs.read(path)
    public_bytes = inputs.read(raw_case / 'public-observation.json')
    public = decode(public_bytes, 'public observation')
    captured_at = timestamp(public.get('capturedAt'))
    parsed = urlsplit(public.get('url', ''))
    if parsed.scheme != 'http' or parsed.hostname not in ('127.0.0.1', 'localhost') or not parsed.port or parsed.username or parsed.password:
        raise ValueError('Observed current Studio URL must be explicit loopback origin.')
    origin = f'{parsed.scheme}://{parsed.netloc}'
    svg_bytes = inputs.read(raw_case / 'browser-scene.svg')
    if not isinstance(public.get('svg'), str) or public['svg'].encode() != svg_bytes:
        raise ValueError('Public svg text differs from raw browser-scene.svg bytes.')
    svg_root, metadata = svg_metadata(svg_bytes)
    public_metadata = public.get('metadata')
    public_metadata_exact = public_metadata == metadata
    metadata_comparison = {'exact': public_metadata_exact, 'numericToleranceApplied': False,
                           'scope': 'Public parsed metadata versus metadata parsed from exact captured SVG text.'}
    if not public_metadata_exact:
        tolerance = 1e-10
        if (not isinstance(public_metadata, dict)
                or {key: value for key, value in public_metadata.items() if key != 'heightMm'}
                != {key: value for key, value in metadata.items() if key != 'heightMm'}
                or not finite(public_metadata.get('heightMm'), True)
                or not finite(metadata.get('heightMm'), True)
                or abs(public_metadata['heightMm'] - metadata['heightMm']) > tolerance):
            raise ValueError('Public metadata differs from actual SVG metadata beyond authorized derived-height serialization tolerance.')
        metadata_comparison.update({'numericToleranceApplied': True, 'field': 'heightMm',
                                    'publicValue': public_metadata['heightMm'], 'svgValue': metadata['heightMm'],
                                    'difference': public_metadata['heightMm'] - metadata['heightMm'],
                                    'absoluteTolerance': tolerance,
                                    'reason': 'Only finite derived physical-height numeric serialization across languages is allowed to differ; every other metadata field remains strictly equal. Metadata equality is not byte-exact.'})
    links = decode(inputs.read(raw_case / 'export-links.json'), 'actual export links', list)
    export_url, export_id = exact_export_url(links, origin)
    export_dir = args.store.absolute().parent / 'exports' / export_id
    exported_document_bytes = inputs.read(export_dir / 'document.json')
    document = decode(exported_document_bytes, 'actual exported Canvas')
    doc_id = document.get('id')
    if not isinstance(doc_id, str) or not SAFE_DOC.fullmatch(doc_id):
        raise ValueError('Invalid actual exported document identity.')
    store_path = args.store.absolute() / (doc_id + '.json')
    snapshot_input = raw_case / 'saved-envelope.json'
    snapshot_receipt_bytes = None
    envelope_bytes = None
    envelope = None
    envelope_observation = None
    if snapshot_input.exists():
        envelope_bytes = inputs.read(snapshot_input)
        snapshot_sidecar = Path(str(snapshot_input) + '.receipt.json')
        if not snapshot_sidecar.exists():
            candidate_envelope = decode(envelope_bytes, 'operator-copied stored envelope')
            if candidate_envelope.get('document') != document:
                raise ValueError('Existing raw snapshot differs from observed export; no sidecar generated.')
            sidecar = {'observedSourcePath': str(store_path), 'snapshotPath': str(snapshot_input),
                       'copiedAt': now(), 'bytes': len(envelope_bytes), 'sha256': digest(envelope_bytes),
                       'copiedAtMeaning': 'Current metadata sidecar generation time; original file-copy time was not captured.',
                       'originalCopiedAt': None, 'copyTimeKnown': False,
                       'provenanceScope': 'Root reports direct saved-envelope copy during this case; this helper only reads back snapshot/export/public bytes. Native copy provenance is not certified.'}
            with snapshot_sidecar.open('xb') as handle:
                handle.write(encoded(sidecar))
        snapshot_receipt_bytes = inputs.read(snapshot_sidecar)
        envelope_observation = decode(snapshot_receipt_bytes, 'operator-copied envelope metadata')
        if (Path(envelope_observation.get('observedSourcePath', '')).absolute() != store_path
                or Path(envelope_observation.get('snapshotPath', '')).absolute() != snapshot_input
                or envelope_observation.get('sha256') != digest(envelope_bytes)
                or type(envelope_observation.get('bytes')) is not int
                or envelope_observation['bytes'] != len(envelope_bytes)):
            raise ValueError('Raw envelope snapshot paths/bytes/hash differ from its actual copy receipt.')
        timestamp(envelope_observation.get('copiedAt'))
        envelope = decode(envelope_bytes, 'operator-copied stored envelope')
        envelope_kind = 'operator-frozen-document-store-snapshot'
    elif args.export_only:
        envelope_kind = 'actual-export-Canvas-only-no-stored-envelope'
    else:
        envelope_bytes = inputs.read(store_path)
        envelope = decode(envelope_bytes, 'actual live stored envelope')
        envelope_kind = 'live-document-store-exact-readback'
    if envelope is not None and (type(envelope.get('revision')) is not int or envelope['revision'] < 1 or envelope.get('document') != document):
        raise ValueError('Actual store/export Canvas mismatch; save incomplete or stale UUID. No fallback attempted.')
    baseline = decode(inputs.read(Path(variant['canvasFile'])), 'frozen source-bound baseline')
    if (document.get('architecture') != baseline['architecture'] or doc_id != variant['documentId']
            or document.get('sourceBindingDigest') != variant['sourceDigest']
            or sorted(document.get('expandedIds', [])) != sorted(variant['expandedIds'])
            or document.get('pageSpec', {}).get('widthMm') != variant['widthMm']
            or document.get('pageSpec', {}).get('preset') != variant['preset']):
        raise ValueError('Actual Canvas source/frontier/page differs from declared variant.')
    if type(document.get('revision')) is not int or document['revision'] < 0:
        raise ValueError('Visual revision must be a nonnegative integer.')
    changed = [field for field in FIELDS if document.get(field) != baseline.get(field)]
    if args.state == 'baseline' and any(field != 'layout' for field in changed):
        raise ValueError('Edited alias/style/legend/annotation/pin/title/page cannot be baseline.')
    if args.state == 'edited' and not changed:
        raise ValueError('Edited case needs actual changed visual fields.')
    doc_binding = {'documentId': doc_id, 'revision': document['revision'],
                   'sourceDigest': variant['sourceDigest'], 'irDigest': variant['irDigest']}
    if ({key: metadata.get(key) for key in doc_binding} != doc_binding
            or svg_root.get('data-document-id') != doc_id or svg_root.get('data-revision') != str(document['revision'])
            or metadata.get('widthMm') != variant['widthMm']
            or sorted(public.get('expandedIds', [])) != sorted(variant['expandedIds'])):
        raise ValueError('Public Scene binding/source/revision/width/frontier differs from saved export.')
    figure_bytes = inputs.read(export_dir / 'figure.svg')
    figure_root, figure_metadata = svg_metadata(figure_bytes)
    if figure_metadata != metadata or figure_root.get('data-document-id') != doc_id or figure_root.get('data-revision') != str(document['revision']):
        raise ValueError('Actual publication SVG metadata differs from current public Scene.')
    receipt_bytes = inputs.read(export_dir / 'figure.svg.receipt.json')
    receipt = decode(receipt_bytes, 'actual publication receipt')
    if (receipt.get('format') != 'svg' or {key: receipt.get(key) for key in doc_binding} != doc_binding
            or receipt.get('widthMm') != variant['widthMm'] or receipt.get('exportScope') != {'kind': 'document'}
            or receipt.get('outputDigest') != digest(figure_bytes) or receipt.get('svgDigest') != digest(figure_bytes)
            or receipt.get('bytes') != len(figure_bytes)):
        raise ValueError('Actual SVG receipt does not bind same whole Canvas/output bytes.')
    shot_path, shot, shot_suffix, dimensions = screenshot_input(inputs, raw_case)
    environment, env_provenance = historical_environment(inputs, args.environment_source.absolute(), public.get('viewport'))
    expected_dimensions = tuple(environment['viewport'][key] * environment['devicePixelRatio'] for key in ('width', 'height'))
    if tuple(dimensions) != expected_dimensions:
        raise ValueError('Actual image dimensions differ from current viewport times historically supplied DPR; preserve and investigate.')
    camera = public.get('camera')
    if not isinstance(camera, dict) or not isinstance(camera.get('transform'), str) or not camera['transform']:
        raise ValueError('Current public camera transform missing.')
    bounds = camera.get('sceneScreenBounds')
    if not isinstance(bounds, dict) or not all(finite(bounds.get(key), key in ('width', 'height')) for key in ('x', 'y', 'width', 'height')):
        raise ValueError('Current Scene screen bounds invalid.')
    expected_assets = {item['path']: item for item in spec['buildFiles'] if item['path'].endswith(('.js', '.css'))}
    assets = []
    seen = set()
    for asset in public.get('assets', []):
        if not isinstance(asset, dict) or not isinstance(asset.get('url'), str):
            raise ValueError('Observed asset URL invalid.')
        url = urlsplit(asset['url'])
        if url.query or url.fragment or (url.netloc and f'{url.scheme}://{url.netloc}' != origin):
            raise ValueError('Loaded asset URL is not exact current origin.')
        path = url.path.removeprefix('/')
        if path not in expected_assets or path in seen or asset.get('kind') != ('js' if path.endswith('.js') else 'css'):
            raise ValueError('Loaded asset is duplicate, unsupported or from another build.')
        record = expected_assets[path]
        assets.append({'path': path, 'url': origin + '/' + path, 'sha256': record['sha256']})
        seen.add(path)
    if seen != set(expected_assets):
        raise ValueError('Current public assets omit a frozen JS/CSS file.')
    snapshot_path = output / 'saved-envelope.json'
    snapshot_meta = envelope_observation
    if envelope is not None and snapshot_meta is None:
        snapshot_meta = {'observedSourcePath': str(store_path), 'snapshotPath': str(snapshot_path),
                         'copiedAt': now(), 'bytes': len(envelope_bytes), 'sha256': digest(envelope_bytes)}
    screen = {'schemaVersion': 1, 'protocol': CAPTURE_PROTOCOL, 'caseId': case,
              'variantId': variant_id, 'state': args.state, 'capturedAt': captured_at,
              'captureKind': 'studio-browser', 'documentBinding': doc_binding,
              'pageSpec': {'widthMm': variant['widthMm'], 'preset': variant['preset']},
              'expandedIds': public['expandedIds'], 'environment': environment,
              'environmentProvenance': env_provenance, 'camera': camera,
              'loadedBuildAssets': assets, 'captureScope': 'studio-viewport',
              'screenshotDigest': None, 'browserSceneDigest': None,
              'actualExport': {'observedUrl': export_url, 'serviceArtifactId': export_id},
              'publicSvgMetadataComparison': metadata_comparison,
              'actualStoredEnvelope': snapshot_meta,
              'storedEnvelopeReadback': {'kind': envelope_kind, 'captured': envelope is not None,
                                         'savedExportCanvasExact': envelope is not None},
              'limitations': ['Image/DOM/store/export are exact operator observations, not native provenance or screenshot pixel certification.',
                              'UA/DPR are historical same-IAB values with file/time/JSON-pointer provenance, not current navigator reads.',
                              'Current viewport/camera/asset URLs come from this case public DOM; local build hashes are not browser-response-byte captures.',
                              'Font evidence is empty; host font candidates do not certify resolved font faces.',
                              'No rendered comparison, model execution, performance, physical readability, human review or formal collection was performed.']}
    copied = {'canvas.json': exported_document_bytes, 'figure.svg': figure_bytes,
              'export-receipt.json': receipt_bytes, 'screenshot' + shot_suffix: shot,
              'browser-scene.svg': svg_bytes, 'screen-receipt.json': encoded(screen),
              'public-observation.json': public_bytes,
              'export-links.json': inputs.read(raw_case / 'export-links.json')}
    copied['helper-source.py'] = inputs.read(Path(__file__))
    copied['screen-receipt-unstamped.json'] = encoded(screen)
    correction_sidecar = Path(str(shot_path) + '.format-correction.json')
    if correction_sidecar.exists():
        copied['screenshot-format-correction.json'] = inputs.read(correction_sidecar)
    if envelope is not None:
        copied['saved-envelope.json'] = envelope_bytes
        copied['saved-envelope.json.receipt.json'] = snapshot_receipt_bytes or encoded(snapshot_meta)
    else:
        screen['limitations'].append('No stored envelope was captured for this case before the live store changed. Export Canvas and public save DOM are retained, without storage snapshot certification.')
        copied['screen-receipt.json'] = encoded(screen)
        copied['screen-receipt-unstamped.json'] = encoded(screen)
    if not (raw_case / 'fit.dom.txt').is_file() or not any(
            (raw_case / name).is_file() for name in ('saved.dom.txt', 'export-complete.dom.txt')):
        raise ValueError('Require actual fit and saved/export-complete public DOM evidence; no synthetic DOM aliases.')
    for path in sorted(raw_case.glob('*.dom.txt')):
        copied[path.name] = inputs.read(path)
    bound_root.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix='.bind-case-', dir=bound_root))
    try:
        for name, raw in copied.items():
            (temporary / name).write_bytes(raw)
        inputs.recheck()
        source_after = protected_bindings()
        if source_after != source_before:
            raise ValueError('Product source/build files changed during binding.')
        names = {**NAMES, 'screenshot': 'screenshot' + shot_suffix}
        record = {'caseId': case, 'variantId': variant_id, 'state': args.state, **names}
        result = {'schemaVersion': 1, 'protocol': 'archcanvas-au3-evidence-case-binding/1',
                  'argv': sys.argv, 'cwd': str(Path.cwd()), 'startedAt': started, 'finishedAt': now(), 'exitCode': 0,
                  'caseId': case, 'variantId': variant_id, 'state': args.state,
                  'script': binding(Path(__file__).absolute(), inputs.read(Path(__file__))),
                  'matrixSpec': binding(args.matrix.absolute() / 'spec.json', inputs.read(args.matrix / 'spec.json')),
                  'actualObservedExportUuid': export_id, 'replacementExportSearch': 'not-attempted',
                  'savedExportCanvasExact': envelope is not None,
                  'publicPublicationMetadataExact': public_metadata == figure_metadata,
                  'publicSvgMetadataComparison': metadata_comparison,
                  'capturedSvgPublicationMetadataExact': True,
                  'storedEnvelopeReadback': {'kind': envelope_kind, 'captured': envelope is not None,
                                             'observation': snapshot_meta},
                  'storageRevision': envelope['revision'] if envelope is not None else None, 'visualRevision': document['revision'],
                  'changedVisualFields': changed, 'screenshotActualFormat': shot_suffix.removeprefix('.'),
                  'screenshotDimensions': list(dimensions), 'screenshotInput': binding(shot_path, shot),
                  'screenHashesStamped': False,
                  'inputsBefore': inputs.before(), 'inputsAfter': inputs.after(), 'inputsBeforeAfterExact': True,
                  'sourceBuildBefore': source_before, 'sourceBuildAfter': source_after, 'sourceBuildBeforeAfterExact': True,
                  'copiedFiles': [{'path': name, 'bytes': len(raw), 'sha256': digest(raw)} for name, raw in copied.items()
                                  if name != 'screen-receipt.json'],
                  'capture': record, 'formalCollectionExecuted': False, 'coverageCertified': False,
                  'modelExecuted': False, 'dependenciesInstalled': False, 'humans': 0,
                  'scope': 'Exact file/DOM/source-bound evidence binding only. Formal collect, independent rendered/pixel review and human acceptance remain separate.'}
        (temporary / 'binding-receipt.json').write_bytes(encoded(result))
        inputs.recheck()
        if protected_bindings() != source_before or output.exists():
            raise ValueError('Protected product changed or output appeared; refusing publication.')
        temporary.rename(output)
        return {'boundCase': relative(output), 'caseId': case, 'variantId': variant_id, 'state': args.state,
                'actualExportUuid': export_id, 'inputsExact': True, 'sourceBuildExact': True,
                'formalCollectionExecuted': False, 'coverageCertified': False,
                'receipt': binding(output / 'binding-receipt.json', (output / 'binding-receipt.json').read_bytes())}
    except Exception:
        shutil.rmtree(temporary)
        raise


def prepare_index(args, inputs: FrozenInputs, source_before: list[dict], started: str) -> dict:
    output = args.output.absolute()
    if output.exists() or Path(str(output) + '.receipt.json').exists():
        raise ValueError('Index/receipt exists; choose fresh path.')
    matrix_spec(inputs, args.matrix.absolute())
    captures, seen, baselines = [], set(), set()
    candidates = sorted(args.bound_root.absolute().glob('*/binding-receipt.json'))
    if not candidates:
        raise ValueError('No bound cases found.')
    for path in candidates:
        receipt = decode(inputs.read(path), 'bound-case receipt')
        if receipt.get('protocol') != 'archcanvas-au3-evidence-case-binding/1' or receipt['matrixSpec']['sha256'] != digest(inputs.read(args.matrix / 'spec.json')):
            raise ValueError('Case was not bound to this exact matrix spec.')
        for file in receipt['copiedFiles']:
            raw = inputs.read(path.parent / file['path'])
            if {'path': file['path'], 'bytes': len(raw), 'sha256': digest(raw)} != file:
                raise ValueError('Bound file changed after binding; preserve original case.')
        record = receipt['capture']
        screen = decode(inputs.read(path.parent / record['screenReceipt']), 'actual screen receipt')
        unstamped = decode(inputs.read(path.parent / 'screen-receipt-unstamped.json'), 'unstamped observations')
        hashes = {'screenshotDigest', 'browserSceneDigest'}
        if ({key: value for key, value in screen.items() if key not in hashes}
                != {key: value for key, value in unstamped.items() if key not in hashes}):
            raise ValueError('Screen observation fields changed after binding; only separate hash stamping is allowed.')
        if (screen.get('screenshotDigest') != digest(inputs.read(path.parent / record['screenshot']))
                or screen.get('browserSceneDigest') != semantic_svg_digest(inputs.read(path.parent / record['browserScene']))):
            raise ValueError('Root must run the separate stamp-hashes step before creating a collect index.')
        if record['caseId'] in seen or (record['state'] == 'baseline' and record['variantId'] in baselines):
            raise ValueError('Duplicate caseId or baseline variant; choose an explicit case set.')
        seen.add(record['caseId'])
        if record['state'] == 'baseline':
            baselines.add(record['variantId'])
        capture = {key: record[key] for key in ('caseId', 'variantId', 'state')}
        capture.update({key: os.path.relpath(path.parent / record[key], output.parent) for key in NAMES})
        captures.append(capture)
    inputs.recheck()
    if protected_bindings() != source_before:
        raise ValueError('Product source/build changed during index creation.')
    output.parent.mkdir(parents=True, exist_ok=True)
    raw = encoded({'schemaVersion': 1, 'protocol': PROTOCOL, 'captures': captures})
    with output.open('xb') as handle:
        handle.write(raw)
    sidecar = {'schemaVersion': 1, 'argv': sys.argv, 'cwd': str(Path.cwd()), 'startedAt': started,
               'finishedAt': now(), 'exitCode': 0, 'output': binding(output, raw),
               'inputsBefore': inputs.before(), 'inputsAfter': inputs.after(), 'inputsBeforeAfterExact': True,
               'sourceBuildBefore': source_before, 'sourceBuildAfter': protected_bindings(),
               'sourceBuildBeforeAfterExact': True, 'listedCases': len(captures),
               'listedBaselineVariants': len(baselines), 'formalCollectionExecuted': False,
               'coverageCertified': False, 'humans': 0,
               'scope': 'Input list only; listed cases are not collector passes or accepted screenshots.'}
    with Path(str(output) + '.receipt.json').open('xb') as handle:
        handle.write(encoded(sidecar))
    return {'index': relative(output), 'listedCases': len(captures), 'listedBaselines': len(baselines),
            'formalCollectionExecuted': False, 'coverageCertified': False}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    for name in ('case', 'index'):
        command = commands.add_parser(name)
        command.add_argument('--matrix', type=Path, default=DEFAULT_MATRIX)
        command.add_argument('--bound-root', type=Path, default=WORK / 'bound')
        if name == 'case':
            command.add_argument('--case', required=True)
            command.add_argument('--variant')
            command.add_argument('--state', choices=('baseline', 'edited'), default='baseline')
            command.add_argument('--store', type=Path, default=DEFAULT_STORE)
            command.add_argument('--raw-root', type=Path, default=WORK / 'raw')
            command.add_argument('--environment-source', type=Path, default=DEFAULT_ENV)
            command.add_argument('--export-only', action='store_true',
                                 help='Explicitly retain an actual export/public Canvas without claiming a missing stored envelope; existing snapshot mismatches still fail')
        else:
            command.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    inputs = FrozenInputs()
    started = now()
    source_before = protected_bindings()
    inputs.read(Path(__file__))
    try:
        result = bind_case(args, inputs, source_before, started) if args.command == 'case' else prepare_index(args, inputs, source_before, started)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, TypeError, KeyError, ET.ParseError) as error:
        failure = WORK / 'failed-binding-attempts'
        failure.mkdir(exist_ok=True)
        receipt = {'schemaVersion': 1, 'argv': sys.argv, 'cwd': str(Path.cwd()), 'startedAt': started,
                   'finishedAt': now(), 'exitCode': 1, 'error': str(error), 'inputsBefore': inputs.before(),
                   'inputsAfter': inputs.after(), 'inputsBeforeAfterExact': inputs.before() == inputs.after(),
                   'sourceBuildBefore': source_before, 'sourceBuildAfter': protected_bindings(),
                   'sourceBuildBeforeAfterExact': source_before == protected_bindings(),
                   'formalCollectionExecuted': False, 'coverageCertified': False}
        destination = failure / (datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ') + '.json')
        destination.write_bytes(encoded(receipt))
        print(json.dumps({'error': str(error), 'failureReceipt': relative(destination)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
