#!/usr/bin/env python3
"""Independently audit a collected actual-browser matrix without calling collect."""
from __future__ import annotations
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[3]
WORK = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'src'))
from archcanvas_publication import export_svg
import archcanvas_publication.exporter as exporter

FIELDS = ('canvas', 'svg', 'exportReceipt', 'screenshot', 'browserScene', 'screenReceipt')
VISUAL_FIELDS = ('displayAliases', 'nodeStyleOverrides', 'edgeStyleOverrides', 'legendItems',
                 'annotations', 'layout', 'pinnedObjects', 'title', 'pageSpec')
SVG = '{http://www.w3.org/2000/svg}'


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(value):
    return sha(json.dumps(value, ensure_ascii=False, allow_nan=False,
                          sort_keys=True, separators=(',', ':')).encode())


def xml_value(raw):
    assert not re.search(rb'<!\s*(?:DOCTYPE|ENTITY)|<\?', raw, re.I)
    root = ET.fromstring(raw)
    assert root.tag == SVG + 'svg'
    def node(el):
        return [el.tag, sorted(el.attrib.items()), el.text or '', el.tail or '',
                [node(child) for child in el]]
    return node(root)


def audit(index, collection):
    bindings = {}
    def raw(path):
        path = path.resolve()
        assert path.is_file() and not path.is_symlink()
        data = path.read_bytes()
        key = str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path)
        value = {'path': key, 'sha256': sha(data), 'bytes': len(data)}
        if key in bindings:
            assert bindings[key] == value, f'Concurrent input modification: {key}'
        bindings[key] = value
        return data
    def read(path):
        return json.loads(raw(path))
    def child(directory, relative):
        path = directory / relative
        assert path.resolve().is_relative_to(directory.resolve())
        # Reject symlink parents as well as leaf symlinks.
        current = path
        while current != directory:
            assert not current.is_symlink()
            current = current.parent
        return path

    raw(Path(__file__))
    raw(Path(exporter.__file__))
    raw(ROOT / 'scripts/browser_visual_core.mjs')
    spec_path = ROOT / '.archcanvas/browser-visual-matrix-boundary-final/spec.json'
    spec_raw = raw(spec_path)
    spec = json.loads(spec_raw)
    assert spec['expectedBaselineCount'] == 36 and len(spec['frontiers']) == 9
    assert len(spec['variants']) == 36
    frozen_count = 0
    for key, parent in [('implementationFiles', ROOT), ('buildFiles', ROOT / 'studio/dist'),
                        ('coreFiles', Path(spec['coreDirectory']))]:
        for entry in spec[key]:
            value = raw(child(parent, entry['path']))
            assert sha(value) == entry['sha256'] and len(value) == entry['bytes']
            frozen_count += 1
    core_report = raw(Path(spec['coreDirectory']) / 'visual-gold-report.json')
    assert sha(core_report) == spec['coreReportDigest']
    records = read(index)
    manifest = read(collection / 'manifest.json')
    review = read(collection / 'review-template.json')
    raw(collection / 'index.html')
    assert records['schemaVersion'] == 1 and records['protocol'] == spec['protocol']
    assert manifest['protocol'] == spec['protocol'] and manifest['specDigest'] == sha(spec_raw)
    assert len(records['captures']) == len(manifest['captures']) == 39
    assert len({r['caseId'] for r in records['captures']}) == 39
    by_case = {item['caseId']: item for item in manifest['captures']}
    assert len(by_case) == 39
    variants = {v['variantId']: v for v in spec['variants']}
    baseline_ids = [r['variantId'] for r in records['captures'] if r['state'] == 'baseline']
    assert len(baseline_ids) == len(set(baseline_ids)) == 36
    assert set(baseline_ids) == set(variants)
    assert Counter(r['state'] for r in records['captures']) == {'baseline': 36, 'edited': 3}
    edited_fixtures = [variants[r['variantId']]['fixture'] for r in records['captures'] if r['state'] == 'edited']
    assert sorted(edited_fixtures) == ['mlp', 'residual_cnn', 'transformer']
    assert manifest['capturedBaselineCount'] == manifest['expectedBaselineCount'] == 36
    assert manifest['missingBaselineVariants'] == manifest['editedAfterModelsMissing'] == []
    assert manifest['editedAfterModelsCaptured'] == sorted(edited_fixtures)
    assert manifest['artifactCoverage'] == 'complete'
    assert manifest['humanAcceptanceCertified'] is False
    assert manifest['visualAcceptance'] == review['status'] == 'pending-human-review'
    assert review['humanAcceptanceCertified'] is False
    assert len(review['cases']) == 39 and all(v['status'] == 'pending' for v in review['cases'])
    assert {v['caseId'] for v in review['cases']} == set(by_case)
    for case_review in review['cases']:
        assert case_review['physicalSizeViewed'] == case_review['browserPixelContentReviewed'] == 'pending'
        assert all(v == {'status': 'pending', 'notes': ''} for v in case_review['criteria'].values())
    assert manifest['environmentConsistency'] == 'requires-independent-review'

    inputs = []
    prepared = []
    artifact_count = 0
    physical_values = []
    environments = []
    for record in records['captures']:
        case = record['caseId']
        variant = variants[record['variantId']]
        item = by_case[case]
        assert item['variantId'] == record['variantId'] and item['state'] == record['state']
        files = {}
        for field in FIELDS:
            value = raw(child(index.parent, record[field]))
            bound = item['files'][field]
            copied = raw(child(collection, bound['path']))
            assert copied == value, (case, field, 'collected bytes differ from source input')
            assert sha(copied) == bound['sha256'] and len(copied) == bound['bytes']
            files[field] = value
            artifact_count += 1
        document = json.loads(files['canvas'])
        assert document['architecture'] == read(Path(variant['canvasFile']))['architecture']
        assert document['id'] == variant['documentId']
        assert document['sourceBindingDigest'] == variant['sourceDigest']
        assert document['architecture']['irDigest'] == variant['irDigest']
        assert sorted(document['expandedIds']) == sorted(variant['expandedIds'])
        assert document['pageSpec']['preset'] == variant['preset']
        assert document['pageSpec']['widthMm'] == variant['widthMm']
        baseline = read(Path(variant['canvasFile']))
        changed = [field for field in VISUAL_FIELDS if document.get(field) != baseline.get(field)]
        assert changed == item['changedVisualFields']
        if record['state'] == 'baseline':
            assert set(changed) <= {'layout'}
        else:
            assert changed and 'annotations' in changed
        assert canonical(document) == item['canvasCanonicalDigest']
        receipt = json.loads(files['exportReceipt'])
        screen = json.loads(files['screenReceipt'])
        binding = {'documentId': document['id'], 'revision': document['revision'],
                   'sourceDigest': variant['sourceDigest'], 'irDigest': variant['irDigest']}
        assert screen['documentBinding'] == item['documentBinding'] == binding
        assert screen['caseId'] == case and screen['variantId'] == variant['variantId']
        assert screen['state'] == record['state']
        assert screen['pageSpec'] == item['pageSpec'] == {'widthMm': variant['widthMm'], 'preset': variant['preset']}
        assert sorted(screen['expandedIds']) == sorted(document['expandedIds'])
        assert screen['screenshotDigest'] == sha(files['screenshot'])
        assert screen['browserSceneDigest'] == item['browserSceneDigest'] == canonical(xml_value(files['browserScene']))
        assert receipt['format'] == 'svg' and receipt['exportScope'] == {'kind': 'document'}
        for key, value in binding.items():
            assert receipt[key] == value
        assert receipt['outputDigest'] == receipt['svgDigest'] == sha(files['svg'])
        assert receipt['bytes'] == len(files['svg']) and receipt['widthMm'] == variant['widthMm']
        assert screen['captureScope'] == 'studio-viewport'
        stamp_time = datetime.fromisoformat(screen['capturedAt'].replace('Z', '+00:00'))
        assert stamp_time.utcoffset() is not None
        env = screen['environment']
        assert env == item['environment']
        assert env['viewport'] == {'width': 1280, 'height': 720} and env['devicePixelRatio'] == 1
        assert env['hardware'] is None and env['browserVersion'] is None and env['fontEvidence'] == []
        assert screen['camera'] == item['camera']
        for key in ('x', 'y', 'width', 'height'):
            assert math.isfinite(screen['camera']['sceneScreenBounds'][key])
        assert screen['camera']['sceneScreenBounds']['width'] > 0
        assert screen['camera']['sceneScreenBounds']['height'] > 0
        actual_assets = {a['path']: a['sha256'] for a in screen['loadedBuildAssets']}
        frozen_assets = {a['path']: a['sha256'] for a in spec['buildFiles'] if a['path'].endswith(('.js', '.css'))}
        assert actual_assets == frozen_assets

        case_dir = child(index.parent, record['canvas']).parent
        observed = read(case_dir / 'dom-observation.json')
        store_bytes = raw(case_dir / 'actual-document-store.json')
        store = json.loads(store_bytes)
        assert store['document'] == document, 'Whole exported Canvas differs from actual store snapshot.'
        snapshot = screen['actualStoredEnvelope']
        assert snapshot['sha256'] == sha(store_bytes) and snapshot['bytes'] == len(store_bytes)
        source_snapshot = raw(Path(snapshot['snapshotPath']))
        assert source_snapshot == store_bytes
        assert observed['documentBinding'] == binding
        assert observed['actualExport']['observedUrl'] == screen['actualExport']['observedUrl']
        source = observed['environmentProvenance']
        source_bytes = raw(Path(source['path']))
        assert source['sha256'] == sha(source_bytes) and source['fields'] == ['userAgent']
        assert env['userAgent'] == json.loads(source_bytes)['environment']['userAgent']
        assert 'Earlier same' in source['scope'] and 'current UA' in source['scope']
        for source_file in document['architecture']['sources']:
            fixture_bytes = raw(ROOT / 'fixtures' / variant['fixture'] / source_file['path'])
            assert fixture_bytes == source_file['content'].encode()
            assert sha(fixture_bytes) == source_file['digest']
        preflight = receipt['physicalPreflight']
        assert item['physicalPreflight'] == preflight
        physical_values.append({'caseId': case, 'state': record['state'], 'minTextPt': preflight['minTextPt']})
        environments.append({'caseId': case, 'viewport': env['viewport'], 'devicePixelRatio': env['devicePixelRatio'],
                             'userAgentProvenance': source})
        inputs.append({'document': document})
        prepared.append((record, variant, item, files, receipt))

    assert artifact_count == 234
    core_checks = []
    with tempfile.TemporaryDirectory(prefix='archcanvas-independent-matrix-audit-') as temp:
        temp = Path(temp)
        inp, expected = temp / 'input.json', temp / 'expected'
        inp.write_text(json.dumps(inputs, ensure_ascii=False))
        proc = subprocess.run(['node', str(ROOT / 'scripts/browser_visual_core.mjs'),
                               str(inp), str(expected)], cwd=ROOT, capture_output=True, text=True, timeout=60)
        assert proc.returncode == 0, proc.stderr
        facts_bytes = (expected / 'facts.json').read_bytes()
        assert raw(collection / 'expected/facts.json') == facts_bytes
        facts = json.loads(facts_bytes)
        assert len(facts) == 39
        for i, (record, variant, item, files, receipt) in enumerate(prepared):
            interactive = (expected / f'{i}.interactive.svg').read_bytes()
            publication = (expected / f'{i}.publication.svg').read_bytes()
            assert raw(collection / 'expected' / f'{i}.interactive.svg') == interactive
            assert raw(collection / 'expected' / f'{i}.publication.svg') == publication
            assert xml_value(interactive) == xml_value(files['browserScene'])
            assert receipt['sceneSvgDigest'] == receipt['inputSvgDigest'] == sha(publication)
            normalized = export_svg(publication.decode(), format='svg', width_mm=variant['widthMm'], dpi=receipt['dpi'])['data']
            assert normalized == files['svg']
            assert facts[i]['documentId'] == item['documentBinding']['documentId']
            assert facts[i]['revision'] == item['documentBinding']['revision']
            assert facts[i]['irDigest'] == variant['irDigest'] and facts[i]['sourceDigest'] == variant['sourceDigest']
            core_checks.append({'caseId': record['caseId'], 'interactiveFullXmlMatches': True,
                                'publicationSceneDigestMatches': True, 'normalizedPublicationExactBytesMatch': True,
                                'wholeActualStoreMatchesWholeExportCanvas': True,
                                'coreFacts': facts[i]})
    for variant in spec['variants']:
        assert raw(collection / 'core-previews' / (variant['variantId'] + '.svg')) == raw(Path(variant['svgFile']))
    for key, value in list(bindings.items()):
        path = ROOT / key if not Path(key).is_absolute() else Path(key)
        data = path.read_bytes()
        assert {'path': key, 'sha256': sha(data), 'bytes': len(data)} == value
    baseline_physical = [x for x in physical_values if x['state'] == 'baseline']
    return {'schemaVersion': 1, 'protocol': 'archcanvas-independent-matrix-collection-audit/1',
        'auditedAt': datetime.now(timezone.utc).isoformat(), 'auditCompleted': True,
        'index': str(index.relative_to(ROOT)), 'collection': str(collection.relative_to(ROOT)),
        'frozenFileBindingsVerified': frozen_count, 'baselineCases': 36, 'editedCases': 3,
        'capturedFilesExactInputCopies': artifact_count, 'corePreviewFilesExactFrozenCopies': 36,
        'collectedExpectedFilesExactIndependentCoreCopies': 79,
        'artifactCoverage': 'complete', 'humanAcceptanceCertified': False,
        'coreReconstructionChecks': core_checks, 'environmentObservations': environments,
        'physicalPreflight': {'baselineMinPt': min(x['minTextPt'] for x in baseline_physical),
            'baselineMaxPt': max(x['minTextPt'] for x in baseline_physical),
            'baselineAtLeast7Pt': sum(x['minTextPt'] >= 7 for x in baseline_physical),
            'cases': physical_values},
        'publicationModuleResolvedPath': str(Path(exporter.__file__).resolve()),
        'bindings': sorted(bindings.values(), key=lambda x: x['path']),
        'limitations': [
            'This independent script does not import or invoke browser_visual_matrix.collect; it does reuse the frozen formal core and publication normalization to reconstruct saved Canvas.',
            'Screenshot provenance and visual pixels are not established by these hashes; pixel review and actual browser operation journals are separate evidence.',
            'UserAgent comes from an earlier same-IAB observation; current viewport and DPR are recorded, font/hardware/browser-version resolution remains unknown.',
            'The native viewport preview is not a calibrated physical-size print sample. The 7pt preflight is a suggested measurement threshold, not publication acceptance.',
            'No publication human scores, real researcher identity/tasks or sustained painted performance are certified.']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--index', required=True, type=Path)
    parser.add_argument('--collection', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    output = args.output.resolve()
    assert output.is_relative_to(WORK) and not output.exists()
    result = audit(args.index.resolve(), args.collection.resolve())
    with output.open('x', encoding='utf-8') as stream:
        stream.write(json.dumps(result, ensure_ascii=False, allow_nan=False, indent=2) + '\n')
    print(json.dumps({'output': str(output), 'sha256': sha(output.read_bytes()),
        'bindings': len(result['bindings']), 'artifactCoverage': result['artifactCoverage']}))


if __name__ == '__main__':
    main()
