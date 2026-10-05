#!/usr/bin/env python3
"""Synthetic copy/rejection self-check; this is not browser capture evidence."""
from __future__ import annotations

import copy
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'scripts'))
import prepare_hierarchy_matrix_capture as helper


def expect_error(label, action, contains):
    try:
        action()
    except ValueError as error:
        if contains not in str(error):
            raise AssertionError(f'{label}: unexpected rejection: {error}') from error
        return {'check': label, 'passed': True, 'observedError': str(error)}
    raise AssertionError(label + ': expected rejection did not occur')


def main():
    matrix = ROOT / '.archcanvas/browser-visual-matrix-hierarchy-final'
    spec = helper.verified_spec(matrix)
    variant = next(item for item in spec['variants'] if item['variantId'] == 'mlp-level0-paper-180')
    document = json.loads(Path(variant['canvasFile']).read_bytes())
    scene = Path(variant['svgFile']).read_bytes()
    identity = 'a' * 32
    binding = {'documentId': document['id'], 'revision': document['revision'],
               'sourceDigest': variant['sourceDigest'], 'irDigest': variant['irDigest']}
    results = []
    with tempfile.TemporaryDirectory(prefix='archcanvas-synthetic-capture-helper-') as directory:
        temporary = Path(directory)
        store = temporary / 'service/documents'
        artifact = temporary / 'service/exports' / identity
        store.mkdir(parents=True)
        artifact.mkdir(parents=True)
        document_bytes = helper.encode(document)
        stored_bytes = helper.encode({'document': document, 'revision': 1})
        (store / (document['id'] + '.json')).write_bytes(stored_bytes)
        (artifact / 'document.json').write_bytes(document_bytes)
        (artifact / 'figure.svg').write_bytes(scene)
        (artifact / 'figure.svg.receipt.json').write_bytes(helper.encode({
            'format': 'svg', **binding, 'widthMm': variant['widthMm'],
            'exportScope': {'kind': 'document'}, 'outputDigest': helper.sha(scene), 'bytes': len(scene)}))
        raw = {'caseId': 'synthetic-helper-only', 'variantId': variant['variantId'], 'state': 'baseline',
               'capturedAt': '2026-10-05T00:00:00Z', 'studioUrl': 'http://127.0.0.1:8896/',
               'documentBinding': binding, 'pageSpec': {'widthMm': 180, 'preset': 'paper'},
               'expandedIds': document['expandedIds'],
               'environment': {'userAgent': 'SYNTHETIC-SELF-CHECK-NOT-A-BROWSER', 'browserVersion': None,
                   'viewport': {'width': 1280, 'height': 720}, 'devicePixelRatio': 1,
                   'hardware': None, 'fontEvidence': []},
               'camera': {'transform': 'SYNTHETIC', 'sceneScreenBounds': {'x': 1, 'y': 2, 'width': 3, 'height': 4}},
               'loadedBuildAssets': [{'path': item['path'], 'url': 'http://127.0.0.1:8896/' + item['path']}
                   for item in spec['buildFiles'] if item['path'].endswith(('.js', '.css'))],
               'actualExport': {'observedUrl': '/api/exports/' + identity + '/figure.svg'},
               'captureScope': 'studio-viewport', 'limitations': ['SYNTHETIC: no browser, image or provenance claim.']}
        raw_path, scene_path, shot_path = [temporary / name for name in ('raw.json', 'scene.svg', 'fake.jpg')]
        raw_path.write_bytes(helper.encode(raw))
        scene_path.write_bytes(scene)
        # Only the file-type guard is tested, never a legitimate screenshot/image decoder.
        fake_jpeg = b'\xff\xd8\xffSYNTHETIC-INVALID-IMAGE-SELF-CHECK-ONLY'
        shot_path.write_bytes(fake_jpeg)
        cases = temporary / 'cases'
        first = cases / 'synthetic-helper-only'
        result = helper.prepare_case(matrix, store, raw_path, scene_path, shot_path, first)
        assert result['fullSavedAndExportCanvasEquality'] is True
        assert result['replacementExportSearch'] == 'not-attempted'
        assert (first / 'canvas.json').read_bytes() == document_bytes
        assert (first / 'actual-document-store.json').read_bytes() == stored_bytes
        assert (first / 'browser-scene.svg').read_bytes() == scene
        assert (first / 'screenshot.jpg').read_bytes() == fake_jpeg
        screen = json.loads((first / 'screen-receipt.json').read_bytes())
        assert screen['screenshotDigest'] is None and screen['browserSceneDigest'] is None
        results.append({'check': 'exact-frozen-byte-copy-and-unstamped-receipt', 'passed': True})
        results.append(expect_error('refuse-output-replacement',
            lambda: helper.prepare_case(matrix, store, raw_path, scene_path, shot_path, first), 'already exists'))
        results.append(expect_error('refuse-unstamped-index',
            lambda: helper.prepare_index(matrix, cases, temporary / 'captures.json'), 'stamp-hashes'))
        newer = copy.deepcopy(document)
        newer['revision'] += 1
        (store / (document['id'] + '.json')).write_bytes(helper.encode({'document': newer, 'revision': 2}))
        results.append(expect_error('stale-link-full-canvas-refusal-no-replacement',
            lambda: helper.prepare_case(matrix, store, raw_path, scene_path, shot_path, cases / 'stale'), 'No fallback attempted'))
        assert not (cases / 'stale').exists()
        # The snapshot branch retains the previously copied exact store bytes
        # while later case saves replace the live store file.
        snapshot = temporary / 'captured-document-store.json'
        snapshot.write_bytes(stored_bytes)
        snapshot_receipt = {'observedSourcePath': str(store / (document['id'] + '.json')),
                            'snapshotPath': str(snapshot), 'copiedAt': '2026-10-05T00:00:00Z',
                            'sha256': helper.sha(stored_bytes), 'bytes': len(stored_bytes)}
        snapshot_metadata = Path(str(snapshot) + '.receipt.json')
        snapshot_metadata.write_bytes(helper.encode(snapshot_receipt))
        snapshot_raw = copy.deepcopy(raw)
        snapshot_raw['caseId'] = 'synthetic-snapshot-helper-only'
        snapshot_raw['actualStoredEnvelope'] = snapshot_receipt
        raw_path.write_bytes(helper.encode(snapshot_raw))
        copied_snapshot = helper.prepare_case(matrix, store, raw_path, scene_path, shot_path,
                                              temporary / 'snapshot-case', snapshot)
        assert copied_snapshot['savedEnvelopeObservation']['kind'] == 'operator-document-store-snapshot'
        assert copied_snapshot['fullSavedAndExportCanvasEquality'] is True
        assert (temporary / 'snapshot-case/actual-document-store.json').read_bytes() == stored_bytes
        results.append({'check': 'snapshot-copy-remains-exact-after-live-store-replaced', 'passed': True})
        relative_raw = copy.deepcopy(snapshot_raw)
        relative_raw['caseId'] = 'synthetic-relative-snapshot-helper-only'
        relative_raw['actualStoredEnvelope']['observedSourcePath'] = os.path.relpath(store / (document['id'] + '.json'))
        relative_raw['actualStoredEnvelope']['snapshotPath'] = os.path.relpath(snapshot)
        raw_path.write_bytes(helper.encode(relative_raw))
        snapshot_metadata.write_bytes(helper.encode(relative_raw['actualStoredEnvelope']))
        relative_case = helper.prepare_case(matrix, store, raw_path, scene_path, shot_path,
                                           temporary / 'relative-case', Path(os.path.relpath(snapshot)))
        assert relative_case['fullSavedAndExportCanvasEquality'] is True
        results.append({'check': 'relative-snapshot-and-declared-source-paths-accepted', 'passed': True})
        raw_path.write_bytes(helper.encode(snapshot_raw))
        snapshot_metadata.write_bytes(helper.encode(snapshot_receipt))
        results.append(expect_error('snapshot-argument-omitted-still-strict-live-store',
            lambda: helper.prepare_case(matrix, store, raw_path, scene_path, shot_path, temporary / 'omitted'), 'No fallback attempted'))
        wrong_snapshot = copy.deepcopy(snapshot_raw)
        wrong_snapshot['actualStoredEnvelope']['observedSourcePath'] = str(store / 'different-document.json')
        raw_path.write_bytes(helper.encode(wrong_snapshot))
        snapshot_metadata.write_bytes(helper.encode(wrong_snapshot['actualStoredEnvelope']))
        results.append(expect_error('snapshot-wrong-source-path',
            lambda: helper.prepare_case(matrix, store, raw_path, scene_path, shot_path, temporary / 'wrong-source', snapshot), 'source/snapshot paths differ'))
        wrong_snapshot = copy.deepcopy(snapshot_raw)
        wrong_snapshot['actualStoredEnvelope']['sha256'] = '0' * 64
        raw_path.write_bytes(helper.encode(wrong_snapshot))
        snapshot_metadata.write_bytes(helper.encode(wrong_snapshot['actualStoredEnvelope']))
        results.append(expect_error('snapshot-wrong-byte-binding',
            lambda: helper.prepare_case(matrix, store, raw_path, scene_path, shot_path, temporary / 'wrong-hash', snapshot), 'exact frozen envelope bytes'))
        raw_path.write_bytes(helper.encode(snapshot_raw))
        results.append(expect_error('snapshot-raw-and-sidecar-disagree',
            lambda: helper.prepare_case(matrix, store, raw_path, scene_path, shot_path, temporary / 'wrong-meta', snapshot), 'snapshot metadata receipt'))
        snapshot_metadata.write_bytes(helper.encode(snapshot_receipt))
        wrong_snapshot = copy.deepcopy(snapshot_raw)
        wrong_snapshot['actualStoredEnvelope']['copiedAt'] = '2026-10-05T00:00:00'
        raw_path.write_bytes(helper.encode(wrong_snapshot))
        snapshot_metadata.write_bytes(helper.encode(wrong_snapshot['actualStoredEnvelope']))
        results.append(expect_error('snapshot-timezone-required',
            lambda: helper.prepare_case(matrix, store, raw_path, scene_path, shot_path, temporary / 'wrong-time', snapshot), 'timezone'))
        raw_path.write_bytes(helper.encode(raw))
        (store / (document['id'] + '.json')).write_bytes(stored_bytes)
        absent = copy.deepcopy(raw)
        absent['actualExport']['observedUrl'] = '/api/exports/' + ('b' * 32) + '/figure.svg'
        raw_path.write_bytes(helper.encode(absent))
        results.append(expect_error('missing-id-no-same-document-fallback',
            lambda: helper.prepare_case(matrix, store, raw_path, scene_path, shot_path, cases / 'missing'), 'Missing actual input'))
        raw_path.write_bytes(helper.encode(raw))
        wrong = copy.deepcopy(raw)
        wrong['documentBinding']['revision'] += 1
        raw_path.write_bytes(helper.encode(wrong))
        results.append(expect_error('observed-revision-mismatch',
            lambda: helper.prepare_case(matrix, store, raw_path, scene_path, shot_path, cases / 'wrong'), 'No fallback attempted'))
        raw_path.write_bytes(helper.encode(raw))
        screen['screenshotDigest'] = helper.sha(fake_jpeg)
        screen['browserSceneDigest'] = helper.semantic_svg_digest(scene)
        (first / 'screen-receipt.json').write_bytes(helper.encode(screen))
        indexed = helper.prepare_index(matrix, cases, temporary / 'captures.json')
        assert len(indexed['captures']) == 1
        results.append({'check': 'separate-synthetic-stamp-then-index', 'passed': True})
        screen['environment']['devicePixelRatio'] = 2
        (first / 'screen-receipt.json').write_bytes(helper.encode(screen))
        results.append(expect_error('reject-changed-observation-facts',
            lambda: helper.prepare_index(matrix, cases, temporary / 'captures-2.json'), 'observation facts changed'))
        (first / 'canvas.json').write_bytes(b'{}')
        results.append(expect_error('reject-changed-copied-bytes',
            lambda: helper.prepare_index(matrix, cases, temporary / 'captures-3.json'), 'input bytes changed'))
    print(json.dumps({'protocol': 'archcanvas-hierarchy-capture-helper-self-check/1',
        'scope': 'Synthetic inputs in a removed temporary directory; not browser capture or matrix acceptance.',
        'realBrowserCaptured': False, 'humanAcceptanceCertified': False,
        'checksPassed': len(results), 'checks': results}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
