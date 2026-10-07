"""Independent byte/JSON/XML/image audit; never import or execute product code.

Writes exclusively to this supplemental audit directory. Each report is fresh.
The live browser capture process remains owned by root.
"""
from pathlib import Path
from datetime import datetime, timezone
from collections import Counter
import argparse
import hashlib
import io
import json
import traceback
import math
import re
from urllib.parse import urlsplit
import xml.etree.ElementTree as ET
from PIL import Image

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
WORK = OUT.parent
MATRIX = ROOT / '.archcanvas/browser-visual-matrix-au3'
CORE = ROOT / 'docs/evidence/visual-golds-au3-matrix'
NS = '{http://www.w3.org/2000/svg}'
cache = {}


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(value):
    return sha(json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False,
                          separators=(',', ':')).encode())


def read(path):
    path = Path(path).absolute()
    if not path.is_file() or path.is_symlink():
        raise ValueError(f'Missing/symlink input: {path}')
    raw = path.read_bytes()
    if path in cache and cache[path] != raw:
        raise ValueError(f'Input changed during read: {path}')
    cache[path] = raw
    return raw


def load(path):
    return json.loads(read(path))


def binding(path, raw=None):
    path = Path(path).absolute()
    raw = read(path) if raw is None else raw
    return {'path': str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path),
            'bytes': len(raw), 'sha256': sha(raw)}


def verify(record, parent=ROOT):
    path = Path(parent) / record['path']
    raw = read(path)
    assert len(raw) == record['bytes'] and sha(raw) == record['sha256'], path
    return raw


def svg(raw):
    assert len(raw) <= 8_000_000 and b'<!DOCTYPE' not in raw and b'<!ENTITY' not in raw
    root = ET.fromstring(raw)
    assert root.tag == NS + 'svg'
    meta = root.find(NS + 'metadata')
    assert meta is not None and meta.text
    return root, json.loads(meta.text)


def semantic_svg(raw):
    root = ET.fromstring(raw)
    def element(node):
        return [node.tag, sorted(node.attrib.items()), node.text or '', node.tail or '',
                [element(child) for child in node]]
    return canonical(element(root))


def architecture_check(fixture):
    architecture = load(CORE / (fixture + '.architecture.json'))
    for source in architecture['sources']:
        source_raw = read(ROOT / 'fixtures' / fixture / source['path'])
        assert sha(source_raw) == source['digest'] == sha(source['content'].encode())
    assert architecture['sourceDigest'] == canonical([
        {key: value for key, value in source.items() if key != 'content'}
        for source in architecture['sources']])
    semantic_nodes = []
    for node in architecture['nodes']:
        item = {key: value for key, value in node.items() if key not in ('source', 'parameterOrigins')}
        if 'parameterOrigins' in node:
            item['parameterOrigins'] = {name: {key: origin[key] for key in ('kind', 'expression', 'path')}
                                        for name, origin in node['parameterOrigins'].items()}
        semantic_nodes.append(item)
    assert architecture['irDigest'] == canonical({'entry': architecture['entry'],
                                                  'nodes': semantic_nodes, 'edges': architecture['edges']})
    by_id = {node['id']: node for node in architecture['nodes']}
    assert len(by_id) == len(architecture['nodes'])
    def depth(node):
        result, seen = 0, set()
        while node.get('parentId'):
            assert node['id'] not in seen
            seen.add(node['id'])
            result += 1
            node = by_id[node['parentId']]
        return result
    max_depth = max(depth(node) for node in architecture['nodes'] if node['children'])
    frontiers = []
    for level in range(min(3, max_depth) + 1):
        expanded = [node['id'] for node in architecture['nodes'] if node['children'] and depth(node) <= level]
        visible = set()
        def visit(identity):
            assert identity not in visible
            visible.add(identity)
            if identity in expanded:
                for child in by_id[identity]['children']:
                    assert by_id[child].get('parentId') == identity
                    visit(child)
        for node in architecture['nodes']:
            if not node.get('parentId'):
                visit(node['id'])
        frontiers.append({'fixture': fixture, 'level': level, 'expandedIds': expanded,
                          'visibleIds': sorted(visible), 'maximumDepth': max_depth})
    return architecture, frontiers


def static_check():
    preparation = load(WORK / 'preparation-receipt.json')
    assert preparation['inputBindings'] == preparation['afterBindings']
    for record in preparation['inputBindings']:
        verify(record)
    for index, run in enumerate(preparation['runs'], 1):
        assert run['exitCode'] == 0
        assert load(WORK / f'prepare-command-{index}.json') == run
        for log in run['logs']:
            verify(log)
        assert read(WORK / f'prepare-command-{index}.stderr.log') == b''
    verify(preparation['coreReport'])
    verify(preparation['matrixSpec'])
    spec, report = load(MATRIX / 'spec.json'), load(CORE / 'visual-gold-report.json')
    assert spec['coreReportDigest'] == sha(read(CORE / 'visual-gold-report.json'))
    for field, parent in [('implementationFiles', ROOT), ('buildFiles', ROOT / 'studio/dist'), ('coreFiles', CORE)]:
        for record in spec[field]:
            verify(record, parent)
    assert report['auditCompleted'] and report['geometryPassed'] and report['spatialCorePassed']
    assert spec['expectedBaselineCount'] == len(spec['variants']) == len(report['variants']) == 36
    assert len(spec['frontiers']) == 9
    assert preparation['browserCasesCollected'] == preparation['humans'] == 0
    assert preparation['modelExecuted'] is False and preparation['nextPhaseStarted'] is False
    assert spec['visualAcceptance'] == report['visualAcceptance'] == 'pending-human-and-browser-review'
    variants = {item['variantId']: item for item in spec['variants']}
    assert len(variants) == 36
    report_variants = {item['name']: item for item in report['variants']}
    rows = []
    for fixture in ('transformer', 'mlp', 'residual_cnn'):
        architecture, frontiers = architecture_check(fixture)
        for frontier in frontiers:
            matches = [row for row in spec['frontiers'] if row['fixture'] == fixture and row['level'] == frontier['level']]
            assert len(matches) == 1 and matches[0]['expandedIds'] == frontier['expandedIds']
            assert matches[0]['maxAuthoredContainerDepth'] == frontier['maximumDepth']
            rows.append(frontier)
            for preset in ('paper', 'monochrome'):
                for width in (85, 180):
                    identity = f"{fixture}-level{frontier['level']}-{preset}-{width}"
                    variant = variants[identity]
                    document = load(variant['canvasFile'])
                    scene = load(CORE / (identity + '.scene.json'))
                    svg_root, metadata = svg(read(variant['svgFile']))
                    assert document['architecture'] == architecture
                    assert sorted(document['expandedIds']) == sorted(variant['expandedIds']) == sorted(frontier['expandedIds'])
                    assert document['pageSpec']['widthMm'] == variant['widthMm'] == width
                    assert document['pageSpec']['preset'] == variant['preset'] == preset
                    assert canonical(document) == variant['baselineCanvasCanonicalDigest']
                    assert variant['documentId'] == document['id']
                    assert variant['sourceDigest'] == architecture['sourceDigest']
                    assert variant['irDigest'] == architecture['irDigest']
                    assert sorted(node['id'] for node in scene['nodes']) == frontier['visibleIds']
                    assert variant['visibleNodes'] == report_variants[identity]['visibleNodes'] == len(scene['nodes'])
                    assert metadata['sourceDigest'] == architecture['sourceDigest'] and metadata['irDigest'] == architecture['irDigest']
                    assert metadata['widthMm'] == width
    return spec, {'preparationReceipt': binding(WORK / 'preparation-receipt.json'),
                  'spec': binding(MATRIX / 'spec.json'), 'coreReport': binding(CORE / 'visual-gold-report.json'),
                  'preparationInputs': len(preparation['inputBindings']),
                  'implementationBindings': len(spec['implementationFiles']), 'coreBindings': len(spec['coreFiles']),
                  'buildBindings': len(spec['buildFiles']), 'frontiers': rows, 'variantsChecked': 36,
                  'scope': 'Static candidates and contracts only; no browser collection or aesthetics implied.'}


def case_check(path, spec):
    case_dir = path.parent
    receipt = load(path)
    assert receipt['exitCode'] == 0 and receipt['protocol'] == 'archcanvas-au3-evidence-case-binding/1'
    assert receipt['inputsBefore'] == receipt['inputsAfter']
    assert receipt['sourceBuildBefore'] == receipt['sourceBuildAfter']
    for record in receipt['sourceBuildBefore']:
        verify(record)
    assert receipt['matrixSpec']['sha256'] == sha(read(MATRIX / 'spec.json'))
    for record in receipt['copiedFiles']:
        verify(record, case_dir)
    if (case_dir / 'helper-source.py').exists():
        assert sha(read(case_dir / 'helper-source.py')) == receipt['script']['sha256']
    else:
        # During helper rollout this remains an explicit limitation, not a fabricated snapshot.
        pass
    original_inputs_verified = 0
    for record in receipt['inputsBefore']:
        if record['path'] == receipt['script']['path']:
            assert (case_dir / 'helper-source.py').exists()
            helper_raw = read(case_dir / 'helper-source.py')
            assert len(helper_raw) == record['bytes'] and sha(helper_raw) == record['sha256']
        else:
            verify(record)
        original_inputs_verified += 1
    capture = receipt['capture']
    variant = next(row for row in spec['variants'] if row['variantId'] == capture['variantId'])
    document = load(case_dir / capture['canvas'])
    baseline = load(variant['canvasFile'])
    assert document['architecture'] == baseline['architecture']
    assert document['id'] == variant['documentId']
    assert sorted(document['expandedIds']) == sorted(variant['expandedIds'])
    assert document['pageSpec']['widthMm'] == variant['widthMm'] and document['pageSpec']['preset'] == variant['preset']
    fields = ('displayAliases', 'nodeStyleOverrides', 'edgeStyleOverrides', 'legendItems', 'annotations', 'layout', 'pinnedObjects', 'title', 'pageSpec')
    changed = [field for field in fields if document.get(field) != baseline.get(field)]
    assert changed == receipt['changedVisualFields']
    if capture['state'] == 'baseline':
        assert all(field == 'layout' for field in changed)
    else:
        assert changed
    public = load(case_dir / 'public-observation.json')
    browser_raw = read(case_dir / capture['browserScene'])
    assert public['svg'].encode() == browser_raw
    browser_root, metadata = svg(browser_raw)
    metadata_exact = public['metadata'] == metadata
    metadata_height_delta = None
    if not metadata_exact:
        assert {key: value for key, value in public['metadata'].items() if key != 'heightMm'} == {key: value for key, value in metadata.items() if key != 'heightMm'}
        assert all(type(value) in (int, float) and math.isfinite(value) and value > 0
                   for value in [public['metadata']['heightMm'], metadata['heightMm']])
        metadata_height_delta = abs(public['metadata']['heightMm'] - metadata['heightMm'])
        assert 0 < metadata_height_delta <= 1e-10
        comparison = receipt.get('publicSvgMetadataComparison')
        assert isinstance(comparison, dict), 'Height mismatch needs explicit receipt disclosure'
        assert comparison['exact'] is False and comparison['numericToleranceApplied'] is True
        assert comparison['absoluteTolerance'] == 1e-10 and comparison['field'] == 'heightMm'
        assert comparison['publicValue'] == public['metadata']['heightMm'] and comparison['svgValue'] == metadata['heightMm']
        assert comparison['difference'] == public['metadata']['heightMm'] - metadata['heightMm']
        assert receipt.get('publicPublicationMetadataExact') is False
        assert receipt.get('capturedSvgPublicationMetadataExact') is True
    publication_raw = read(case_dir / capture['svg'])
    _, publication_metadata = svg(publication_raw)
    assert publication_metadata == metadata
    for key, value in [('documentId', document['id']), ('revision', document['revision']),
                       ('sourceDigest', variant['sourceDigest']), ('irDigest', variant['irDigest']),
                       ('widthMm', variant['widthMm'])]:
        assert metadata[key] == value
    export = load(case_dir / capture['exportReceipt'])
    assert export['outputDigest'] == export['svgDigest'] == sha(publication_raw)
    assert export['bytes'] == len(publication_raw) and export['exportScope'] == {'kind': 'document'}
    links = load(case_dir / 'export-links.json')
    actual_urls = set()
    for link in links:
        url = urlsplit(link['href'])
        match = re.fullmatch(r'/api/exports/([a-f0-9]{32})/figure\.svg', url.path)
        if match:
            assert not url.query and not url.fragment
            actual_urls.add((url.geturl(), match.group(1)))
    assert len(actual_urls) == 1
    observed_url, uuid = next(iter(actual_urls))
    assert uuid == receipt['actualObservedExportUuid']
    export_dir = ROOT / '.archcanvas/m4-au3-visual-matrix-session/exports' / uuid
    assert read(export_dir / 'document.json') == read(case_dir / capture['canvas'])
    assert read(export_dir / 'figure.svg') == publication_raw
    assert read(export_dir / 'figure.svg.receipt.json') == read(case_dir / capture['exportReceipt'])
    screen = load(case_dir / capture['screenReceipt'])
    assert screen['actualExport']['serviceArtifactId'] == uuid
    assert screen['actualExport']['observedUrl'].endswith(urlsplit(observed_url).path)
    assert screen['documentBinding'] == {key: metadata[key] for key in ('documentId', 'revision', 'sourceDigest', 'irDigest')}
    unstamped = load(case_dir / 'screen-receipt-unstamped.json')
    exclude = {'screenshotDigest', 'browserSceneDigest'}
    assert {k:v for k,v in screen.items() if k not in exclude} == {k:v for k,v in unstamped.items() if k not in exclude}
    shot_raw = read(case_dir / capture['screenshot'])
    image = Image.open(io.BytesIO(shot_raw))
    dimensions, actual_format = image.size, image.format
    image.verify()
    image = Image.open(io.BytesIO(shot_raw)); image.load()
    assert actual_format == 'JPEG' and capture['screenshot'].endswith('.jpg') or actual_format == 'PNG' and capture['screenshot'].endswith('.png')
    assert list(dimensions) == receipt['screenshotDimensions']
    assert screen['screenshotDigest'] in (None, sha(shot_raw))
    assert screen['browserSceneDigest'] in (None, semantic_svg(browser_raw))
    provenance = screen['environmentProvenance']
    historical = json.loads(verify(provenance['source']))
    assert provenance['currentNavigatorObserved'] is False
    assert screen['environment']['userAgent'] == historical['environment']['userAgent']
    assert screen['environment']['devicePixelRatio'] == historical['environment']['viewport']['devicePixelRatio']
    assert screen['environment']['viewport'] == public['viewport']
    assert screen['environment']['browserVersion'] is None and screen['environment']['hardware'] is None
    assert screen['environment']['fontEvidence'] == []
    envelope_path = case_dir / 'saved-envelope.json'
    if envelope_path.exists():
        envelope = load(envelope_path)
        assert envelope['document'] == document
        assert receipt['savedExportCanvasExact'] is True
        snapshot = load(case_dir / 'saved-envelope.json.receipt.json')
        assert snapshot['bytes'] == len(read(envelope_path)) and snapshot['sha256'] == sha(read(envelope_path))
    else:
        assert receipt['savedExportCanvasExact'] is False and receipt['storageRevision'] is None
        assert receipt['storedEnvelopeReadback']['kind'] == 'actual-export-Canvas-only-no-stored-envelope'
    correction = case_dir / 'screenshot-format-correction.json'
    if correction.exists():
        corrected = load(correction)
        original_raw = verify(corrected['original'])
        assert verify(corrected['corrected']) == original_raw == shot_raw
        assert corrected['originalPreserved'] and corrected['byteExactCopy'] and not corrected['reencoded']
    return {'caseId': capture['caseId'], 'variantId': capture['variantId'], 'state': capture['state'],
            'receipt': binding(path), 'visualRevision': document['revision'],
            'storageRevision': receipt['storageRevision'], 'storedEnvelopeCaptured': envelope_path.exists(),
            'imageFormat': actual_format, 'imageDimensions': list(dimensions), 'imageDecoded': True,
            'formatCorrection': correction.exists(), 'currentNavigatorObserved': False,
            'hashesStamped': screen['screenshotDigest'] is not None and screen['browserSceneDigest'] is not None,
            'helperSourceSnapshotCaptured': (case_dir / 'helper-source.py').exists(),
            'actualObservedExportUuid': uuid, 'changedVisualFields': changed,
            'originalInputsVerified': original_inputs_verified,
            'publicMetadataExact': metadata_exact, 'publicMetadataHeightDelta': metadata_height_delta,
            'renderedComparisonOrPixelReview': False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--label', required=True)
    parser.add_argument('--include-bound', action='store_true')
    args = parser.parse_args()
    started = datetime.now(timezone.utc).isoformat()
    auditor_source = read(Path(__file__))
    destination = OUT / args.label
    assert not destination.exists() and '/' not in args.label and args.label not in ('.', '..')
    result = {'protocol': 'archcanvas-au3-independent-matrix-audit/1', 'startedAt': started,
              'testsRun': False, 'buildRun': False, 'modelExecuted': False,
              'browserOperated': False, 'humanAcceptanceCertified': False,
              'formalCollectorRunByAuditor': False,
              'auditorSource': binding(Path(__file__), auditor_source)}
    try:
        spec, result['static'] = static_check()
        cases = sorted((WORK / 'bound').glob('*/binding-receipt.json')) if args.include_bound else []
        result['cases'] = [case_check(path, spec) for path in cases]
        result['boundCasesChecked'] = len(cases)
        result['status'] = 'passed-with-stated-scope'
    except Exception as error:
        result['status'] = 'audit-failed'
        result['error'] = f'{type(error).__name__}: {error}'
        result['traceback'] = traceback.format_exc()
    after = [binding(path, path.read_bytes()) for path in sorted(cache)]
    before = [binding(path, raw) for path, raw in sorted(cache.items())]
    result['inputsBefore'], result['inputsAfter'] = before, after
    result['inputsUnchanged'] = before == after
    if before != after:
        result['status'] = 'audit-failed-input-changed'
    result['finishedAt'] = datetime.now(timezone.utc).isoformat()
    destination.mkdir()
    with (destination / 'auditor-source.py').open('xb') as handle:
        handle.write(auditor_source)
    raw = (json.dumps(result, ensure_ascii=False, allow_nan=False, indent=2) + '\n').encode()
    with (destination / 'report.json').open('xb') as handle:
        handle.write(raw)
    print(json.dumps({'report': binding(destination / 'report.json', raw), 'status': result['status'],
                      'inputs': len(cache), 'unchanged': result['inputsUnchanged'],
                      'cases': result.get('boundCasesChecked'), 'error': result.get('error')}, ensure_ascii=False))
    return 0 if result['status'] == 'passed-with-stated-scope' else 1


if __name__ == '__main__':
    raise SystemExit(main())
