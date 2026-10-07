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


def collection_protocol_check(directory):
    attempt_dir = WORK / 'collection-attempt-1'
    receipt = load(attempt_dir / 'attempt-receipt.json')
    assert receipt['exitCode'] == 0 and receipt['formalCollectionExecuted'] is True
    assert receipt['caseCount'] == 39 and receipt['baselineCount'] == 36 and receipt['editedCount'] == 3
    assert receipt['sourceBuildBefore'] == receipt['sourceBuildAfter']
    assert receipt['sourceBuildBeforeAfterExact'] and receipt['collectorInputsBeforeAfterExact']
    assert receipt['onlyScreenReceiptHashStampingMutatedBoundInputs']
    assert read(attempt_dir / 'runner-source.py') == read(WORK / 'collect_attempt_1.py')
    assert read(attempt_dir / 'binder-source.py') == read(WORK / 'bind_case.py')
    for record in receipt['sourceBuildBefore']:
        verify(record)
    preserved = load(WORK / 'unstamped-screen-receipts/preservation-receipt.json')
    assert preserved['caseCount'] == 39 and preserved['allHashesOriginallyNull']
    assert preserved['oldBoundUnstampedBytesExact'] and preserved['observationsModified'] is False
    archived_by_path = {}
    for copy in preserved['copies']:
        assert copy['byteExact'] is True
        archived_raw = verify(copy['snapshot'])
        source_record = copy['source']
        assert len(archived_raw) == source_record['bytes'] and sha(archived_raw) == source_record['sha256']
        source_path = ROOT / source_record['path']
        assert archived_raw == read(source_path.with_name('screen-receipt-unstamped.json'))
        archived_by_path[source_record['path']] = (source_record, copy['snapshot'])
        old_screen = json.loads(archived_raw)
        assert old_screen['screenshotDigest'] is None and old_screen['browserSceneDigest'] is None
    assert len(archived_by_path) == 39
    verify(preserved['historicalInventory'])
    transitions = json.loads(verify(receipt['stampTransitions']))
    assert transitions['caseCount'] == 39 and transitions['allOnlyTwoHashFieldsChanged'] is True
    assert len(transitions['cases']) == 39
    commands = []
    fields = {'screenshotDigest', 'browserSceneDigest'}
    for transition in transitions['cases']:
        assert transition['onlyTwoHashFieldsChanged'] is True
        assert all(value is None for value in transition['beforeHashes'].values())
        old_record, archived_record = archived_by_path[transition['before']['path']]
        assert old_record == transition['before'] and archived_record == transition['unstampedPreserved']
        old_screen = json.loads(verify(archived_record))
        current_screen = json.loads(verify(transition['after']))
        assert {k:v for k,v in old_screen.items() if k not in fields} == {
            k:v for k,v in current_screen.items() if k not in fields}
        assert transition['afterHashes'] == {key: current_screen[key] for key in fields}
        command = json.loads(verify(transition['commandReceipt']))
        assert command['stage'] == 'stamp-' + transition['caseId']
        assert command['inputsBefore'][1] == transition['before'] and command['inputsAfter'][1] == transition['after']
        assert len(command['inputsBefore']) == len(command['inputsAfter']) == 4
        for i in (0, 2, 3):
            assert command['inputsBefore'][i] == command['inputsAfter'][i]
            verify(command['inputsBefore'][i])
        assert current_screen['screenshotDigest'] == command['inputsAfter'][2]['sha256']
        assert current_screen['browserSceneDigest'] == semantic_svg(verify(command['inputsAfter'][3]))
        commands.append(command)
    before_by_path = {r['path']: r for r in receipt['boundBefore']}
    after_by_path = {r['path']: r for r in receipt['boundAfter']}
    assert len(before_by_path) == len(receipt['boundBefore']) == len(after_by_path) == len(receipt['boundAfter'])
    assert set(before_by_path) == set(after_by_path)
    changed = sorted(path for path in before_by_path if before_by_path[path] != after_by_path[path])
    assert changed == sorted(receipt['changedBoundPaths']) == sorted(archived_by_path)
    for record in receipt['boundBefore']:
        if record['path'] in archived_by_path:
            assert record == archived_by_path[record['path']][0]
        else:
            verify(record)
    for record in receipt['boundAfter']:
        verify(record)
    for stage in ('index', 'collect'):
        command = load(attempt_dir / (stage + '.command.json'))
        assert command['stage'] == stage and command['inputsBefore'] == command['inputsAfter']
        for record in command['inputsBefore']:
            verify(record)
        commands.append(command)
    for command in commands:
        assert command['exitCode'] == 0 and command['cwd'] == str(ROOT)
        assert command['elapsedSeconds'] >= 0
        verify(command['stdout'])
        assert verify(command['stderr']) == b''
    copies = load(WORK / 'collector-inputs-attempt-1/inputs-receipt.json')
    assert copies['inputCount'] == len(copies['copies'])
    copied_source_paths = set()
    for copy in copies['copies']:
        assert copy['byteExact'] is True and verify(copy['source']) == verify(copy['snapshot'])
        assert copy['source']['path'] not in copied_source_paths
        copied_source_paths.add(copy['source']['path'])
    collect_command = commands[-1]
    assert copied_source_paths == {record['path'] for record in collect_command['inputsBefore']}
    for record in copies['runtimePaths'].values():
        verify(record)
    verify(receipt['index'])
    for record in receipt['collectorOutput']:
        verify(record)
    assert {str(path.relative_to(ROOT)) for path in directory.rglob('*') if path.is_file()} == {
        record['path'] for record in receipt['collectorOutput']}
    return {'receipt': binding(attempt_dir / 'attempt-receipt.json'),
            'commands': len(commands), 'allExitZeroAndEmptyStderr': True,
            'unstampedOriginalsPreservedExact': 39, 'twoHashOnlyTransitions': 39,
            'collectorInputsPreservedExact': copies['inputCount'], 'runtimeIdentitiesHashReadback': True,
            'allOtherBoundAndSourceBuildBindingsUnchanged': True,
            'collectorOutputInventoryExact': len(receipt['collectorOutput']),
            'collectorNotReexecutedByAuditor': True}


def collected_check(directory, spec, cases):
    directory = directory.absolute()
    manifest_path = directory / 'manifest.json'
    manifest = load(manifest_path)
    assert manifest['protocol'] == 'archcanvas-browser-visual-matrix/1'
    assert manifest['specDigest'] == sha(read(MATRIX / 'spec.json'))
    assert manifest['variants'] == spec['variants'] and manifest['buildFiles'] == spec['buildFiles']
    assert manifest['capturedBaselineCount'] == manifest['expectedBaselineCount'] == 36
    assert manifest['missingBaselineVariants'] == [] and manifest['editedAfterModelsMissing'] == []
    assert sorted(manifest['editedAfterModelsCaptured']) == ['mlp', 'residual_cnn', 'transformer']
    assert manifest['artifactCoverage'] == 'complete'
    assert manifest['humanAcceptanceCertified'] is False and manifest['visualAcceptance'] == 'pending-human-review'
    assert manifest['environmentConsistency'] == 'requires-independent-review'
    assert len(manifest['captures']) == 39
    bound = {case['caseId']: case for case in cases}
    assert len(bound) == len(cases) == 39
    observed, baselines, edited, artifact_paths = set(), set(), set(), set()
    for capture in manifest['captures']:
        identity = capture['caseId']
        assert identity not in observed
        observed.add(identity)
        bound_receipt = load(WORK / 'bound' / identity / 'binding-receipt.json')
        record = bound_receipt['capture']
        assert capture['variantId'] == record['variantId'] and capture['state'] == record['state']
        if capture['state'] == 'baseline':
            assert capture['variantId'] not in baselines
            baselines.add(capture['variantId'])
        else:
            edited.add(capture['fixture'])
        assert capture['fileConsistency'] == 'verified' and capture['visualReview'] == 'pending-human-review'
        assert set(capture['files']) == {'canvas','svg','exportReceipt','screenshot','browserScene','screenReceipt'}
        for key, binding_record in capture['files'].items():
            raw = verify(binding_record, directory)
            assert raw == read(WORK / 'bound' / identity / record[key])
            assert binding_record['path'] not in artifact_paths
            artifact_paths.add(binding_record['path'])
        document = load(directory / capture['files']['canvas']['path'])
        screen = load(directory / capture['files']['screenReceipt']['path'])
        assert capture['canvasCanonicalDigest'] == canonical(document)
        assert capture['documentBinding'] == screen['documentBinding']
        assert capture['environment'] == screen['environment'] and capture['camera'] == screen['camera']
        assert capture['browserSceneDigest'] == semantic_svg(read(directory / capture['files']['browserScene']['path']))
        assert screen['screenshotDigest'] == sha(read(directory / capture['files']['screenshot']['path']))
        assert screen['browserSceneDigest'] == capture['browserSceneDigest']
    assert observed == set(bound)
    assert baselines == {variant['variantId'] for variant in spec['variants']}
    assert sorted(edited) == ['mlp','residual_cnn','transformer']
    assert len(artifact_paths) == 234
    actual = {str(path.relative_to(directory)) for path in (directory / 'captures').rglob('*') if path.is_file()}
    assert actual == artifact_paths
    for variant in spec['variants']:
        assert read(directory / 'core-previews' / (variant['variantId'] + '.svg')) == read(variant['svgFile'])
    review = load(directory / 'review-template.json')
    assert review['reviewer'] is None and review['humanAcceptanceCertified'] is False
    assert len(review['cases']) == 39 and all(case['status'] == 'pending' for case in review['cases'])
    read(directory / 'index.html')
    return {'manifest': binding(manifest_path), 'baselineVariants': len(baselines),
            'editedModels': sorted(edited), 'captures': len(observed), 'artifactBindings': len(artifact_paths),
            'artifactFileSetExact': True, 'allCopiesEqualBoundBytes': True,
            'corePreviewCopies':36,'humanAcceptanceCertified':False,
            'rendererReexecutedByAuditor':False,'pixelCoverageCertified':False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--label', required=True)
    parser.add_argument('--include-bound', action='store_true')
    parser.add_argument('--baseline-report', type=Path)
    parser.add_argument('--collected-directory', type=Path)
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
        prior_cases = []
        stamping_transitions = []
        if args.baseline_report:
            baseline_path = args.baseline_report.absolute()
            prior = load(baseline_path)
            assert prior['status'] == 'passed-with-stated-scope' and prior['inputsUnchanged']
            for record in prior['inputsBefore']:
                if record['path'] == str(Path(__file__).absolute().relative_to(ROOT)):
                    raw = read(baseline_path.parent / 'auditor-source.py')
                    assert len(raw) == record['bytes'] and sha(raw) == record['sha256']
                elif record['path'].endswith('/screen-receipt.json'):
                    # A prior successful audit may predate the separately authorized
                    # two-field hash stamp. Preserve its exact unstamped bytes; certify
                    # only this disclosed transition instead of calling it unchanged.
                    current_path = ROOT / record['path']
                    current_raw = read(current_path)
                    if len(current_raw) == record['bytes'] and sha(current_raw) == record['sha256']:
                        continue
                    unstamped_path = current_path.with_name('screen-receipt-unstamped.json')
                    old_raw = read(unstamped_path)
                    assert len(old_raw) == record['bytes'] and sha(old_raw) == record['sha256']
                    old_screen, current_screen = json.loads(old_raw), json.loads(current_raw)
                    stamp_fields = {'screenshotDigest', 'browserSceneDigest'}
                    assert {k:v for k,v in current_screen.items() if k not in stamp_fields} == {
                        k:v for k,v in old_screen.items() if k not in stamp_fields}
                    assert all(old_screen[key] is None for key in stamp_fields)
                    case_receipt = load(current_path.parent / 'binding-receipt.json')
                    capture = case_receipt['capture']
                    assert current_screen['screenshotDigest'] == sha(read(current_path.parent / capture['screenshot']))
                    assert current_screen['browserSceneDigest'] == semantic_svg(read(current_path.parent / capture['browserScene']))
                    stamping_transitions.append({'caseId': capture['caseId'],
                        'priorReceipt': record, 'exactPriorBytesPreserved': binding(unstamped_path),
                        'currentStampedReceipt': binding(current_path),
                        'onlyFieldsChanged': sorted(stamp_fields), 'newDigestsVerified': True})
                else:
                    verify(record)
            spec = load(MATRIX / 'spec.json')
            result['static'] = prior['static']
            result['priorAudit'] = binding(baseline_path)
            result['priorBindingHashesRechecked'] = len(prior['inputsBefore'])
            result['priorBindingsVerifiedUnchangedOrExactArchivedSource'] = len(prior['inputsBefore']) - len(stamping_transitions)
            result['authorizedScreenReceiptHashTransitions'] = stamping_transitions
            result['staticRecomputed'] = False
            prior_cases = prior['cases']
            transitioned_ids = {transition['caseId'] for transition in stamping_transitions}
            for case in prior_cases:
                if case['caseId'] in transitioned_ids:
                    case['hashesStampedAtPriorAudit'] = case['hashesStamped']
                    case['hashesStamped'] = True
                    case['screenReceiptStampTransitionIndependentlyChecked'] = True
        else:
            spec, result['static'] = static_check()
            result['staticRecomputed'] = True
        cases = sorted((WORK / 'bound').glob('*/binding-receipt.json')) if args.include_bound else []
        known = {case['caseId']: case for case in prior_cases}
        new_cases = [path for path in cases if path.parent.name not in known]
        result['cases'] = prior_cases + [case_check(path, spec) for path in new_cases]
        result['previouslyValidatedCases'] = len(prior_cases)
        result['newlyValidatedCases'] = len(new_cases)
        result['boundCasesChecked'] = len(cases)
        if args.collected_directory:
            result['collectionProtocol'] = collection_protocol_check(args.collected_directory.absolute())
            result['collected'] = collected_check(args.collected_directory, spec, result['cases'])
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
