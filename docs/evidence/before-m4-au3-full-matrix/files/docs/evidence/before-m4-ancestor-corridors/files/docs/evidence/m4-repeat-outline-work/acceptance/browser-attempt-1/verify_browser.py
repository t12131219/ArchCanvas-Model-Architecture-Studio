"""Independent read-only evidence bindings, XML preservation, and move review."""
from pathlib import Path
from collections import Counter
from copy import deepcopy
import hashlib, html, json, re, xml.etree.ElementTree as ET
from PIL import Image

ROOT = Path(__file__).resolve().parents[5]
OUT = Path(__file__).resolve().parent
WORK = ROOT / 'docs/evidence/m4-repeat-outline-work'
BROWSER = WORK / 'browser/attempt-1'
NS = '{http://www.w3.org/2000/svg}'
ET.register_namespace('', 'http://www.w3.org/2000/svg')
CASES = ['transformer-l0', 'cnn-l0', 'mlp-l0', 'transformer-encoder-detail']
FIXTURE = dict(zip(CASES, ['transformer', 'residual_cnn', 'mlp', 'transformer']))

def sha(data): return hashlib.sha256(data).hexdigest()
def binding(p):
    data = p.read_bytes()
    return {'path': str(p.relative_to(ROOT)), 'bytes': len(data), 'sha256': sha(data)}
def read(p): return json.loads(p.read_text())
def write(name, value):
    with (OUT / name).open('x') as stream: json.dump(value, stream, ensure_ascii=False, indent=2); stream.write('\n')
def matches(p, expected):
    got = binding(p)
    return got['bytes'] == expected['bytes'] and got['sha256'] == expected['sha256']
def xml_diff(a, b, path='/svg'):
    found = []
    if a.tag != b.tag: found.append({'path': path, 'field': 'tag', 'actual': a.tag, 'expected': b.tag})
    if a.attrib != b.attrib: found.append({'path': path, 'field': 'attributes', 'actual': a.attrib, 'expected': b.attrib})
    if a.text != b.text: found.append({'path': path, 'field': 'text', 'actual': a.text, 'expected': b.text})
    if a.tail != b.tail: found.append({'path': path, 'field': 'tail', 'actual': a.tail, 'expected': b.tail})
    if len(a) != len(b): found.append({'path': path, 'field': 'children', 'actual': len(a), 'expected': len(b)})
    for i, (ac, bc) in enumerate(zip(a, b)): found += xml_diff(ac, bc, f'{path}/{ac.tag.rsplit("}", 1)[-1]}[{i}]')
    return found
def metadata(root): return json.loads(root.find(NS + 'metadata').text)
def direct_cards(root):
    return {g.attrib['data-node-id']: [dict(r.attrib) for r in g if r.tag == NS + 'rect']
            for g in root.iter(NS + 'g') if 'data-canonical-id' in g.attrib}
def normalise_revision(svg):
    root = ET.fromstring(svg)
    del root.attrib['data-revision']
    m = root.find(NS + 'metadata'); d = json.loads(m.text); del d['revision']
    m.text = json.dumps(d, separators=(',', ':'), ensure_ascii=False)
    return ET.tostring(root, encoding='utf-8')
def canonical_digest(value): return sha(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode())

# Discovery preceded supplemental binding; this is a review stability record.
preparation = read(WORK / 'root/browser-baseline-preparation.json')
build = read(WORK / 'root/build-attempt-1/receipt.json')
extra = {ROOT / c['input'] for c in preparation['copies']}
extra |= {ROOT / c['path'] for c in build['sourceBindings']}
extra |= {ROOT / c['path'] for c in build['buildFiles']}
extra |= {ROOT / 'docs/evidence/m4-chs-browser-matrix-current-verification-sealed.json'}
for case in CASES:
    obs = read(BROWSER / case / 'observation.json')
    ep = Path(obs['actualExport']['sourcePath']).parent
    extra |= set(ep.iterdir())
    doc = read(BROWSER / case / 'saved-envelope.json')['document']
    extra |= {ROOT / 'fixtures' / FIXTURE[case] / source['path'] for source in doc['architecture']['sources']}
extra_before = [binding(p) for p in sorted(extra)]
write('supplemental-inputs-before.json', {'scope': 'Discovered exact stored export UUID artifacts, old baselines, fixtures and build/source receipt inputs; review binding, not acquisition certification.', 'inputs': extra_before})

report = {'schemaVersion': 1, 'scope': 'Four representative BG browser cases, plus four native drag directions. Read-only review; no model execution or fresh matrix/human acceptance.', 'cases': [], 'movement': {}, 'imagesActuallyViewed': [], 'limits': [
    'Nine source JPGs actually opened at original detail: four final main-canvas screenshots, four directional screenshots, one modal primer. No screenshot of the full exported detail page.',
    'Viewport 1280x720 is recorded; UA, DPR, browser engine, fonts and hardware are not independently recorded in this new capture.',
    'Nominal rectangle/routing geometry is reported separately; exact rounded strokes, marker extent and raster line crossings are not certified.',
    'Only SVG export was captured for these cases; PDF/PNG font embedding and physical publication quality are not established.',
    'Captured mutable current store is not treated as historical storage; exact per-export UUID document snapshots are compared instead.'
]}
prior_by_fixture = {copy['fixture']: copy for copy in preparation['copies']}
for case in CASES:
    folder = BROWSER / case
    env = read(folder / 'saved-envelope.json'); doc = env['document']; architecture = doc['architecture']
    initial = read(folder / 'initial.json'); obs = read(folder / 'observation.json'); receipt = read(folder / 'figure.svg.receipt.json')
    interactive_bytes = (folder / 'browser-scene.svg').read_bytes(); actual = ET.fromstring(interactive_bytes)
    expected_bytes = (OUT / 'replay' / f'{case}.whole-interactive.svg').read_bytes(); expected = ET.fromstring(expected_bytes)
    expected_static_bytes = (OUT / 'replay' / f'{case}.export-static.svg').read_bytes(); expected_static = ET.fromstring(expected_static_bytes)
    export_bytes = (folder / 'figure.svg').read_bytes(); exported = ET.fromstring(export_bytes)
    # Only publication root physical width/height precision may change.
    before_publication_diffs = xml_diff(exported, expected_static)
    height = 180 * float(expected_static.attrib['viewBox'].split()[3]) / float(expected_static.attrib['viewBox'].split()[2])
    expected_static.set('width', f'{180:.8g}mm'); expected_static.set('height', f'{height:.8g}mm')
    serialised = ET.tostring(expected_static, encoding='utf-8', xml_declaration=False)
    ep = Path(obs['actualExport']['sourcePath']).parent
    baseline = read(ROOT / prior_by_fixture[FIXTURE[case]]['input'])['document']
    source_records = []
    for source in architecture['sources']:
        fixture_bytes = (ROOT / 'fixtures' / FIXTURE[case] / source['path']).read_bytes()
        source_records.append({'path': source['path'], 'embeddedContentDigestExact': sha(source['content'].encode()) == source['digest'], 'fixtureBytesExact': fixture_bytes == source['content'].encode(), 'sha256': source['digest']})
    source_digest = canonical_digest([{k: v for k, v in source.items() if k != 'content'} for source in architecture['sources']])
    semantic_nodes = []
    for node in architecture['nodes']:
        item = {k: v for k, v in node.items() if k not in ('source', 'parameterOrigins')}
        if 'parameterOrigins' in node: item['parameterOrigins'] = {name: {k: origin[k] for k in ('kind', 'expression', 'path')} for name, origin in node['parameterOrigins'].items()}
        semantic_nodes.append(item)
    ir_digest = canonical_digest({'entry': architecture['entry'], 'nodes': semantic_nodes, 'edges': architecture['edges']})
    nodes = [g for g in actual.iter(NS + 'g') if 'data-canonical-id' in g.attrib]
    static_nodes = [g for g in exported.iter(NS + 'g') if 'data-canonical-id' in g.attrib]
    all_props = {k for k in doc if doc[k] != baseline.get(k)}
    case_report = {
        'id': case, 'documentId': doc['id'], 'visualRevision': doc['revision'], 'storageEnvelopeRevision': env['revision'],
        'mainCanvasRootAttributes': dict(actual.attrib), 'exportRootAttributes': dict(exported.attrib),
        'mainCanvasSvgEqualsCapturedInitialString': initial['svg'].encode() == interactive_bytes,
        'mainCanvasInteractiveReplayXmlDifferences': xml_diff(actual, expected),
        'mainCanvasInteractiveReplayRawBytesEqual': interactive_bytes == expected_bytes,
        'exportPrePublicationXmlDifferences': before_publication_diffs,
        'exportAfterExact8SignificantDigitPhysicalRootNormalizationXmlDifferences': xml_diff(exported, expected_static),
        'exportAfterPublicationXmlSerializationBytesEqual': export_bytes == serialised,
        'interactiveNodeCount': len(nodes), 'interactiveNodeAttributeSets': dict(Counter(','.join(sorted(g.attrib)) for g in nodes)),
        'staticNodeCount': len(static_nodes), 'staticNodeAttributeSets': dict(Counter(','.join(sorted(g.attrib)) for g in static_nodes)),
        'interactiveExpandControls': sum('data-expand-id' in el.attrib for el in actual.iter()),
        'exportExpandControls': sum('data-expand-id' in el.attrib for el in exported.iter()),
        'interactivePortGroups': sum(el.tag == NS + 'g' and 'data-port-id' in el.attrib for el in actual.iter()),
        'exportStaticPortCircles': sum(el.tag == NS + 'circle' and 'data-port-id' in el.attrib for el in exported.iter()),
        'binding': {
            'sourceRecords': source_records, 'sourceDigestRecomputed': source_digest, 'sourceDigestExact': source_digest == architecture['sourceDigest'] == doc['sourceBindingDigest'],
            'irDigestRecomputedFromDeclaredSemanticContract': ir_digest, 'irDigestExact': ir_digest == architecture['irDigest'],
            'entireArchitectureEqualsExactPriorBaseline': architecture == baseline['architecture'],
            'changedCanvasFieldsAgainstPriorBaseline': sorted(all_props),
            'perExportUuidDocumentDeepEqualCapturedEnvelopeDocument': read(ep / 'document.json') == doc,
            'perExportUuidFigureBytesExact': (ep / 'figure.svg').read_bytes() == export_bytes,
            'perExportUuidReceiptBytesExact': (ep / 'figure.svg.receipt.json').read_bytes() == (folder / 'figure.svg.receipt.json').read_bytes(),
            'observedExportDigestExact': obs['actualExport']['sha256'] == sha(export_bytes),
            'observedCapturedEnvelopeDigestExact': obs['actualStored']['sha256'] == sha((folder / 'saved-envelope.json').read_bytes()),
            'receiptInputSceneDigestExact': receipt['inputSvgDigest'] == receipt['sceneSvgDigest'] == sha(expected_static_bytes),
            'receiptOutputDigestExact': receipt['svgDigest'] == receipt['outputDigest'] == sha(export_bytes),
            'receiptIdentityAndDigestsExact': all(receipt[k] == metadata(actual)[k] for k in ('documentId', 'revision', 'sourceDigest', 'irDigest')),
            'initialObservationIdentityExact': initial['documentBinding'] == obs['documentBinding'] == {k: metadata(actual)[k] for k in ('documentId', 'revision', 'sourceDigest', 'irDigest')},
            'expandedIdsExact': initial['expandedIds'] == obs['expandedIds'] == doc['expandedIds'],
            'loadedAssetsMatchBuildReceipt': all(any(asset['path'] == x['path'].removeprefix('studio/dist/') for x in build['buildFiles']) for asset in initial['loadedBuildAssets']) and initial['loadedBuildAssets'] == obs['loadedBuildAssets'],
        },
        'exportScope': receipt['exportScope'], 'physicalPreflight': receipt['physicalPreflight'],
        'screenshotSurface': 'Main canvas; detail case shows encoder expanded within Transformer, not exported detail page.',
        'dialogCount': obs['dialogCount'], 'finalDomSavedStateObserved': 'generic: 已保存' in (folder / 'final.dom.txt').read_text(),
    }
    if case.endswith('detail'):
        preview = (folder / 'preview.svg').read_bytes()
        case_report['previewStaticDetailXmlDifferences'] = xml_diff(ET.fromstring(preview), ET.fromstring(expected_static_bytes))
        case_report['previewStaticDetailRawBytesEqual'] = preview == expected_static_bytes
        scope = receipt['exportScope']
        inside = set(scope['canonicalNodeIds']); edges = architecture['edges']
        classified = {'internal': [e['id'] for e in edges if e['source']['nodeId'] in inside and e['target']['nodeId'] in inside], 'boundary': [e['id'] for e in edges if (e['source']['nodeId'] in inside) != (e['target']['nodeId'] in inside)], 'omitted': [e['id'] for e in edges if e['source']['nodeId'] not in inside and e['target']['nodeId'] not in inside]}
        case_report['detailCounts'] = {'canonicalNodes': len(inside), 'internalEdges': len(classified['internal']), 'hiddenInternalEdges': len(scope['hiddenInternalEdgeIds']), 'boundaryEdges': len(classified['boundary']), 'incomingBoundaryEdges': sum(x['direction'] == 'in' for x in scope['boundaryEdges']), 'outgoingBoundaryEdges': sum(x['direction'] == 'out' for x in scope['boundaryEdges']), 'omittedEdges': len(classified['omitted']), 'renderedDetailNodes': len(static_nodes), 'renderedDetailRoutes': len(metadata(exported)['renderedBindings']), 'scopeClassificationExact': classified['internal'] == scope['internalEdgeIds'] and classified['boundary'] == [e['edgeId'] for e in scope['boundaryEdges']] and classified['omitted'] == scope['omittedEdgeIds']}
    report['cases'].append(case_report)

mb = BROWSER / 'transformer-moves'
moves = {p.stem: read(p) for p in mb.glob('*.json') if not p.stem.endswith('-input')}
before = moves['before']; base_root = ET.fromstring(before['svg']); base_cards = direct_cards(base_root); encoder = 'repeat:instance:model.Transformer.encoder'
base_front = base_cards[encoder][-1]
movement = {'baseline': {'revision': before['documentBinding']['revision'], 'encoderFrontRectangle': base_front, 'camera': before['camera']}, 'directions': []}
for direction in ('right', 'left', 'up', 'down'):
    capture = moves[direction]; root = ET.fromstring(capture['svg']); cards = direct_cards(root); front = cards[encoder][-1]; drag = read(mb / f'{direction}-input.json')
    dx = float(front['x']) - float(base_front['x']); dy = float(front['y']) - float(base_front['y'])
    intended = [drag['to'][i] - drag['from'][i] for i in (0, 1)]
    undo = moves[direction + '-undo']
    movement['directions'].append({'direction': direction, 'nativeDragReported': drag['nativeDrag'], 'inputScreenDelta': intended, 'actualSvgFrontDelta': [dx, dy], 'deltaExactAtRecorded1xCamera': [dx, dy] == intended, 'revision': capture['documentBinding']['revision'], 'encoderFrontRectangle': front, 'otherNodeCardAttributesUnchanged': all(cards[node] == card for node, card in base_cards.items() if node != encoder), 'cameraUnchangedDuringDrag': capture['camera'] == before['camera'], 'undoRevision': undo['documentBinding']['revision'], 'undoSvgRevisionOnlyNormalizedExact': normalise_revision(undo['svg']) == normalise_revision(before['svg']), 'undoRawSvgExact': undo['svg'] == before['svg'], 'sourceIrIdentityUnchanged': all(capture['documentBinding'][k] == before['documentBinding'][k] == undo['documentBinding'][k] for k in ('documentId', 'sourceDigest', 'irDigest')), 'upBlockedRouteStatusRetained': direction != 'up' or 'source_mask' in (mb / 'up.dom.txt').read_text() and '连线缺少畅通路径' in (mb / 'up.dom.txt').read_text()})
movement['downPersistence'] = {'downVsRedoRevisionOnlyNormalizedExact': normalise_revision(moves['down']['svg']) == normalise_revision(moves['down-redo']['svg']), 'redoSavedReopenedFullSvgStringExact': moves['down-redo']['svg'] == moves['saved']['svg'] == moves['reopened']['svg'], 'redoSavedReopenedFullSvgSha256': sha(moves['down-redo']['svg'].encode()), 'redoSavedReopenedRevision': [moves[name]['documentBinding']['revision'] for name in ('down-redo', 'saved', 'reopened')], 'savedFooter': moves['saved']['footer'], 'saveCaptureIsPendingStatus': '正在处理' in moves['saved']['footer'], 'reopenedFooter': moves['reopened']['footer'], 'reopenedStatusObservesSavedCanvas': '已重开保存的画布' in moves['reopened']['footer'], 'reopenedCamera': moves['reopened']['camera'], 'cameraChangesOnReopen': moves['saved']['camera'] != moves['reopened']['camera'], 'collapsedAfterDetailEqualsDownRedoRevisionOnlyNormalized': normalise_revision(moves['collapsed-after-detail']['svg']) == normalise_revision(moves['down-redo']['svg'])}
report['movement'] = movement

image_notes = {
    'transformer-l0/screenshot.jpg': 'Main canvas fitted at 54%; front cards, encoder layers stack, decoder and legends visible. Small labels and dense dashed routes limit eye-level line judgments.',
    'cnn-l0/screenshot.jpg': 'Main canvas fitted at 46%; narrow vertical ResidualCNN body and stacked blocks visible; entire paper fits. Small labels remain an AI-view limitation.',
    'mlp-l0/screenshot.jpg': 'Main canvas fitted at 79%; features, collapsed network three-card stack, output and legend visible.',
    'transformer-encoder-detail/screenshot.jpg': 'Main canvas fitted at 53%; encoder expanded into two EncoderLayer cards; decoder/output remain present. This is not a full detail export screenshot.',
    'transformer-moves/right.jpg': '100% zoom; selected encoder shifted right, property x108 y410. Lower page clipped by viewport; not a whole-figure image.',
    'transformer-moves/left.jpg': '100% zoom; selected encoder shifted left, property x52 y410. Lower page clipped by viewport.',
    'transformer-moves/up.jpg': '100% zoom; selected encoder moved up, property x80 y382. Visible banner states source_mask→encoder lacks unobstructed route; blocked state retained.',
    'transformer-moves/down.jpg': '100% zoom; selected encoder moved down, property x80 y438. Its lower card and paper extend beyond viewport; no full-figure completeness claim.',
    'transformer-encoder-detail/preview-primer.jpg': 'Modal detail export preview, page180x584.6mm; scrollbars and cropped preview show encoder/FROM source embedding. PDF tile selected in primer, but actual captured output is SVG; not PDF conversion evidence.',
}
for relative, notes in image_notes.items():
    path = BROWSER / relative
    with Image.open(path) as img: decoded = {'format': img.format, 'size': list(img.size), 'mode': img.mode}
    report['imagesActuallyViewed'].append({**binding(path), **decoded, 'actualTool': 'tools.view_image(detail="original")', 'notes': notes})

oldseal = ROOT / 'docs/evidence/m4-chs-browser-matrix-current-verification-sealed.json'
seal = read(oldseal); prefixes = ['docs/evidence/m4-chs-browser-matrix-work/raw/', 'docs/evidence/browser-visual-matrix-chs-current/']
old_selected = [b for b in seal['bindings'] if any(b['path'].startswith(p) for p in prefixes)]
old_actual = {str(p.relative_to(ROOT)) for prefix in prefixes for p in (ROOT / prefix).rglob('*') if p.is_file()}
old_expected = {b['path'] for b in old_selected}
old_checks = [{**b, 'currentExact': matches(ROOT / b['path'], b)} for b in old_selected]
old_audit = {'scope': 'Current old matrix raw/collected only; historical current product/docs not required to match old seal.', 'sealBinding': binding(oldseal), 'sealedExpectedCount': len(old_selected), 'actualCurrentCount': len(old_actual), 'countsByPrefix': {p: sum(b['path'].startswith(p) for b in old_selected) for p in prefixes}, 'extraPaths': sorted(old_actual - old_expected), 'missingPaths': sorted(old_expected - old_actual), 'all806Exact': len(old_checks) == 806 and all(x['currentExact'] for x in old_checks), 'bindings': old_checks}
write('old-matrix-806-rehash.json', old_audit)
report['oldMatrix806'] = {k: v for k, v in old_audit.items() if k != 'bindings'}
before_inputs = read(OUT / 'inputs-before.json')['inputs']
stability = [{**b, 'currentExact': matches(Path(b['path']), b)} for b in before_inputs]
extra_stability = [{**b, 'currentExact': matches(ROOT / b['path'], b)} for b in extra_before]
build_source_checks = [{**b, 'currentExact': matches(ROOT / b['path'], b)} for b in build['sourceBindings']]
build_file_checks = [{**b, 'currentExact': matches(ROOT / b['path'], b)} for b in build['buildFiles']]
report['build'] = {'receipt': binding(WORK / 'root/build-attempt-1/receipt.json'), 'claimedBuildExit': build['exitCode'], 'modelExecution': build['modelExecution'], 'sourceChecks': build_source_checks, 'buildFileChecks': build_file_checks, 'allSourceAndBuildBindingsExact': all(x['currentExact'] for x in build_source_checks + build_file_checks)}
report['inputStability'] = {'startBoundCount': len(stability), 'startBoundAllExact': all(x['currentExact'] for x in stability), 'supplementalCount': len(extra_stability), 'supplementalAllExact': all(x['currentExact'] for x in extra_stability), 'initialBindings': stability, 'supplementalBindings': extra_stability}
report['selectorTimeoutPreserved'] = {'binding': binding(BROWSER / 'selector-timeout.json'), 'content': read(BROWSER / 'selector-timeout.json'), 'interpretation': 'AI incorrect literal locator before CNN actions, then corrected; not a product error, successful capture or export.'}
write('browser-review.json', report)
print(json.dumps({'cases': len(report['cases']), 'mainXmlExact': all(not c['mainCanvasInteractiveReplayXmlDifferences'] for c in report['cases']), 'exportXmlExactAfterOnlyPhysicalRootPrecision': all(not c['exportAfterExact8SignificantDigitPhysicalRootNormalizationXmlDifferences'] for c in report['cases']), 'exportBytesExact': all(c['exportAfterPublicationXmlSerializationBytesEqual'] for c in report['cases']), 'undo4Exact': all(x['undoSvgRevisionOnlyNormalizedExact'] for x in movement['directions']), 'persistence': movement['downPersistence'], 'old806Exact': old_audit['all806Exact'], 'start98Exact': report['inputStability']['startBoundAllExact'], 'buildExact': report['build']['allSourceAndBuildBindingsExact']}, ensure_ascii=False))
