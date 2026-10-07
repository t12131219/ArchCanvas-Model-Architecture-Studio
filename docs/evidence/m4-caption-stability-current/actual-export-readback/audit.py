"""Read-only export audit. Independent XML/PDF/hash oracle, not a production validator."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import math
import re
import subprocess
import xml.etree.ElementTree as ET

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
BROWSER = OUT.parent / 'browser'
NS = '{http://www.w3.org/2000/svg}'
rows = []

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def read(path):
    return json.loads(path.read_text())

def add(name, passed, detail=None):
    rows.append({'relation': name, 'passed': bool(passed), 'detail': detail})

def meta(tree):
    return json.loads(tree.find(NS + 'metadata').text)

def structural(tree, omit_root_height=False):
    # Attribute ordering/namespace prefixes do not carry drawing meaning.
    attrs = dict(tree.attrib)
    if omit_root_height:
        attrs.pop('height', None)
    return [tree.tag, sorted(attrs.items()), tree.text or '',
            [structural(child) for child in tree]]

def path_points(value):
    # Actual current paths use absolute M/H/V/L. Any unsupported command fails closed.
    tokens = re.findall(r'[A-Za-z]|[-+]?(?:\d*\.\d+|\d+)(?:[Ee][-+]?\d+)?', value)
    points = []
    x = y = 0.0
    i = 0
    while i < len(tokens):
        op = tokens[i]
        i += 1
        if op in ('M', 'L'):
            x, y = float(tokens[i]), float(tokens[i + 1])
            i += 2
        elif op == 'H':
            x = float(tokens[i]); i += 1
        elif op == 'V':
            y = float(tokens[i]); i += 1
        else:
            raise ValueError('Unsupported independent path token: ' + op)
        points.append((x, y))
    return points

def near(a, b, epsilon=1e-10):
    return math.isclose(a, b, rel_tol=0, abs_tol=epsilon)

capture = read(OUT / 'capture-receipt.json')
frozen = capture['inputs']
add('capture:no-in-memory-document-mutation', capture['inputDocumentMutation'] is False)
add('capture:frozen-inputs-identical-before-after', capture['inputsAfter'] == frozen)
for index, row in enumerate(frozen):
    file = Path(row['path'])
    add('capture:still-exact-input-' + str(index),
        file.stat().st_size == row['bytes'] and digest(file) == row['sha256'], row['path'])

saved = read(OUT / 'saved-rev31-envelope.json')
document = saved['document']
architecture = document['architecture']
canonical_nodes = {node['id']: node for node in architecture['nodes']}
canonical_edges = {edge['id']: edge for edge in architecture['edges']}
add('saved:visual-revision31-storage-counter5', document['revision'] == 31 and saved['revision'] == 5)
add('saved:canonical-denominator49nodes71edges', len(canonical_nodes) == 49 and len(canonical_edges) == 71)
identities = read(OUT / 'ui-export-identities.json')
exports = {}

for label, ext in [('wholePdf', 'pdf'), ('wholeSvg', 'svg'), ('detailSvg', 'svg')]:
    directory = OUT / label
    file = directory / ('figure.' + ext)
    receipt = read(directory / ('figure.' + ext + '.receipt.json'))
    exported_document = read(directory / 'document.json')
    original = Path(receipt['path'])
    add(label + ':same-saved-document', exported_document == document)
    add(label + ':output-byte-digest', receipt['bytes'] == file.stat().st_size and receipt['outputDigest'] == digest(file))
    add(label + ':actual-service-output-copy-exact', original.exists() and original.read_bytes() == file.read_bytes())
    original_receipt = original.with_name(original.name + '.receipt.json')
    add(label + ':actual-service-receipt-copy-exact', original_receipt.exists() and original_receipt.read_bytes() == (directory / original_receipt.name).read_bytes())
    original_document = original.parent / 'document.json'
    add(label + ':actual-service-document-copy-exact', original_document.exists() and original_document.read_bytes() == (directory / 'document.json').read_bytes())
    add(label + ':id-revision-source-ir', receipt['documentId'] == document['id'] and receipt['revision'] == 31
        and receipt['sourceDigest'] == architecture['sourceDigest'] and receipt['irDigest'] == architecture['irDigest'])
    add(label + ':publication-width180', receipt['widthMm'] == 180)
    add(label + ':formal-publication-origin', receipt['publicationOrigin'] == str(ROOT / 'src/archcanvas_publication/exporter.py'))
    add(label + ':actual-export-id', original.parent.name == identities[label])
    exports[label] = {'receipt': receipt, 'artifact': str(file.relative_to(ROOT)), 'serviceArtifact': str(original)}

for label in ['whole', 'detail']:
    file = OUT / (label + 'Svg') / 'figure.svg'
    actual = ET.parse(file).getroot()
    raw = ET.parse(OUT / (label + '.raw.svg')).getroot()
    scene = read(OUT / (label + '.scene.json'))
    receipt = exports[label + 'Svg']['receipt']
    metadata = meta(actual)
    bounds = scene['bounds']
    viewbox = [float(value) for value in actual.get('viewBox').split()]
    add(label + ':raw-scene-digest', receipt['inputSvgDigest'] == receipt['sceneSvgDigest'] == digest(OUT / (label + '.raw.svg')))
    add(label + ':normalized-svg-digest', receipt['svgDigest'] == receipt['outputDigest'] == digest(file))
    add(label + ':complete-xml-exact-except-height-normalization', structural(actual, True) == structural(raw, True))
    add(label + ':metadata-exact', metadata == meta(raw))
    add(label + ':viewbox-exact', viewbox == receipt['viewBox'] == [bounds[k] for k in ['x', 'y', 'width', 'height']])
    expected_height = 180 * viewbox[3] / viewbox[2]
    add(label + ':physical-height-aspect', near(receipt['heightMm'], expected_height)
        and near(metadata['heightMm'], expected_height)
        and near(float(actual.get('height').removesuffix('mm')), expected_height, 5.1e-6)
        and actual.get('width') == '180mm')
    add(label + ':source-facts-scene-and-denominator', metadata['sourceFacts'] == scene['sourceFacts']
        and len(metadata['sourceFacts']) == 49 and {fact['id'] for fact in metadata['sourceFacts']} == set(canonical_nodes))
    for fact in metadata['sourceFacts']:
        canonical = canonical_nodes[fact['id']]
        add(label + ':source-fact:' + fact['id'], fact['sourceLabel'] == canonical['label']
            and all(fact.get(k) == canonical.get(k) for k in ['kind', 'category', 'evidence', 'source',
                                                         'instanceId', 'callId', 'repeat', 'outputPath'])
            and fact.get('callCount') == (len({n['callId'] for n in architecture['nodes']
                if n.get('instanceId') == canonical['instanceId'] and n.get('callId')}) if canonical.get('instanceId') else None))
    rendered_nodes = [node for node in actual.iter() if node.get('data-canonical-id')]
    add(label + ':rendered-node-frontier12', len(rendered_nodes) == len(scene['nodes']) == len(metadata['renderedNodes']) == 12
        and {node.get('data-node-id') for node in rendered_nodes} == {node['id'] for node in scene['nodes']})
    for node in scene['nodes']:
        xml = next(n for n in rendered_nodes if n.get('data-node-id') == node['id'])
        add(label + ':visible-node:' + node['id'], xml.get('data-canonical-id') == node.get('canonicalNodeId', node['id'])
            and xml.get('aria-label') == node['label'] and node.get('sourceFact', {}).get('id') == node.get('canonicalNodeId', node['id']))

    xml_edges = {node.get('data-edge-id'): node for node in actual.iter() if node.get('data-edge-id')}
    xml_ports = {node.get('data-port-id'): node for node in actual.iter() if node.get('data-port-id')}
    scene_nodes = {node['id']: node for node in scene['nodes']}
    scene_edges = {edge['id']: edge for edge in scene['edges']}
    scene_ports = {port['id']: port for node in scene['nodes'] for port in node['ports']}
    bindings = metadata['renderedBindings']
    add(label + ':binding-frontier12', len(xml_edges) == len(scene_edges) == len(bindings) == 12 and set(xml_edges) == set(scene_edges))
    add(label + ':port-set-exact', set(xml_ports) == set(scene_ports))
    for pid, port in scene_ports.items():
        xml = xml_ports[pid]
        add(label + ':port-coordinate:' + pid, near(float(xml.get('cx')), port['x'], .0051)
            and near(float(xml.get('cy')), port['y'], .0051))
        expected_bindings = [canonical_edges[i]['source' if port['direction'] == 'out' else 'target'] for i in port['canonicalEdgeIds']]
        add(label + ':port-canonical:' + pid, expected_bindings == port['canonicalBindings']
            and all(binding['portId'] in {p['id'] for p in canonical_nodes[binding['nodeId']]['ports']} for binding in expected_bindings))
    represented = []
    for binding in bindings:
        edge = scene_edges[binding['sceneEdgeId']]
        ids = binding['canonicalEdgeIds']
        represented.extend(ids)
        add(label + ':canonical-binding:' + edge['id'], len(ids) > 0
            and all(canonical_edges[i]['source'] == binding['source'] for i in ids)
            and all(canonical_edges[i]['role'] == binding['role'] for i in ids)
            and all(canonical_edges[i]['tensorId'] == binding['tensorId'] for i in ids)
            and canonical_edges[ids[0]]['target'] == binding['target']
            and all(edge.get(k) == binding.get(k) for k in ['canonicalEdgeIds', 'source', 'target', 'role', 'tensorId']))
        xml = xml_edges[edge['id']]
        route = xml.find(NS + 'path')
        texts = xml.findall(NS + 'text')
        add(label + ':route-style-caption:' + edge['id'], route.get('d') == edge['path']
            and route.get('stroke') == edge['stroke'] and near(float(route.get('stroke-width')), edge['width'])
            and xml.get('data-tensor-id') == edge['tensorId'] and route.get('marker-end', '').startswith('url(#archcanvas-arrow-')
            and ((len(texts) == 1 and texts[0].text == edge['label']
                  and near(float(texts[0].get('x')), edge['labelX'], .0051)
                  and near(float(texts[0].get('y')), edge['labelY'], .0051)) if edge['label'] else len(texts) == 0))
        points = path_points(route.get('d'))
        endpoint_checks = []
        endpoint_distances = []
        for direction, nodeid, endpoint, point in [('out', edge['sourceId'], edge['source'], points[0]),
                                                  ('in', edge['targetId'], edge['target'], points[-1])]:
            candidates = [port for port in scene_nodes[nodeid]['ports'] if port['direction'] == direction
                          and endpoint in port['canonicalBindings'] and ids[0] in port['canonicalEdgeIds']]
            distances = [max(abs(point[0] - port['x']), abs(point[1] - port['y'])) for port in candidates]
            endpoint_checks.append(bool(distances) and min(distances) <= .050000001)
            endpoint_distances.append(min(distances) if distances else None)
        add(label + ':orthogonal-route-port-endpoints:' + edge['id'], all(endpoint_checks)
            and all(near(a[0], b[0]) or near(a[1], b[1]) for a, b in zip(points, points[1:])),
            {'independentMaximumCoordinateError': endpoint_distances, 'publicPathRoundingBound': .05})
    add(label + ':canonical-partition-full71', len(represented) == len(set(represented))
        and not set(represented).intersection(scene['hiddenEdges'])
        and set(represented).union(scene['hiddenEdges']) == set(canonical_edges)
        and len(scene['hiddenEdges']) == 46, {'visibleCanonicalBindings': len(represented), 'hidden': len(scene['hiddenEdges'])})
    guides = [node for node in actual.iter() if node.get('data-caption-guide-id')]
    decorations = metadata.get('presentationDecorations', [])
    add(label + ':one-guide-scene-decoration', len(guides) == len(decorations) == len(scene['captionGuides']) == 1)
    guide = guides[0]
    decoration = decorations[0]
    scene_guide = scene['captionGuides'][0]
    add(label + ':memory-guide-presentation-only', guide.get('data-caption-guide-id') == decoration['id'] == scene_guide['id'] == 'caption-guide:edge:44'
        and guide.get('data-caption-for-edge') == decoration['sceneEdgeId'] == scene_guide['sceneEdgeId'] == 'edge:44'
        and decoration['kind'] == scene_guide['kind'] == 'caption-guide'
        and guide.get('d') == decoration['path'] == scene_guide['path']
        and decoration['id'] not in scene_edges and decoration['id'] not in canonical_edges
        and all(binding['sceneEdgeId'] != decoration['id'] for binding in bindings))
    add(label + ':memory-guide-inert-unarrowed', not any(attr.startswith('marker-') for attr in guide.attrib)
        and guide.get('pointer-events') == 'none' and guide.get('fill') == 'none' and guide.get('stroke-width') == '0.8'
        and guide.get('data-edge-id') is None and guide.get('data-tensor-id') is None)
    memory = scene_edges['edge:44']
    gp = path_points(guide.get('d'))
    mp = path_points(memory['path'])
    add(label + ':memory-caption-owned-guide', memory['label'] == 'memory' and len(mp) == 2 and len(gp) == 2
        and near(gp[0][0], (mp[0][0] + mp[1][0]) / 2) and near(gp[0][1], mp[0][1])
        and near(gp[1][0], gp[0][0]) and near(memory['labelY'] - gp[1][1], 11)
        and near(abs(gp[1][1] - gp[0][1]), 29))
    text_sizes = [float(node.get('font-size')) for node in actual.iter(NS + 'text') if node.get('font-size')]
    min_pt = min(text_sizes) * 180 / viewbox[2] / 25.4 * 72
    add(label + ':independent-minimum-nominal-text-pt', near(min_pt, receipt['physicalPreflight']['minTextPt']))
    exports[label + 'Svg'].update({'independentMinTextPt': min_pt, 'sceneNodes': len(scene['nodes']), 'sceneBindings': len(scene['edges']),
        'facts': len(metadata['sourceFacts']), 'ports': len(scene_ports), 'canonicalRepresented': len(represented),
        'hiddenCanonical': len(scene['hiddenEdges']), 'guideAttributes': guide.attrib})

detail = read(OUT / 'detail.scene.json')
scope = detail['exportScope']
inside = set()
def collect(nodeid):
    inside.add(nodeid)
    for child in canonical_nodes[nodeid]['children']:
        collect(child)
collect('call:instance:model.Transformer')
internal = [e['id'] for e in architecture['edges'] if e['source']['nodeId'] in inside and e['target']['nodeId'] in inside]
boundary = [e for e in architecture['edges'] if (e['source']['nodeId'] in inside) != (e['target']['nodeId'] in inside)]
omitted = [e['id'] for e in architecture['edges'] if e['source']['nodeId'] not in inside and e['target']['nodeId'] not in inside]
visible_canonical = {i for e in detail['edges'] for i in e['canonicalEdgeIds']}
add('detail:scope-receipt-metadata-scene-exact', scope == exports['detailSvg']['receipt']['exportScope']
    == meta(ET.parse(OUT / 'detailSvg/figure.svg').getroot())['exportScope'])
add('detail:independent-selected-hierarchy49', scope['kind'] == 'detail' and scope['selectedNodeId'] == 'call:instance:model.Transformer'
    and scope['selectedLabel'] == canonical_nodes[scope['selectedNodeId']]['label'] == 'Transformer'
    and set(scope['canonicalNodeIds']) == inside == set(canonical_nodes) and len(scope['canonicalNodeIds']) == 49)
add('detail:independent-edge-partition71', scope['internalEdgeIds'] == internal and len(internal) == 71
    and boundary == scope['boundaryEdges'] == [] and omitted == scope['omittedEdgeIds'] == []
    and set(scope['hiddenInternalEdgeIds']) == set(internal) - visible_canonical == set(detail['hiddenEdges']))
add('detail:source-annotation-scope-empty', scope['includedAnnotationIds'] == scope['omittedAnnotationIds'] == document['annotations'] == [])
add('detail:derived-provenance-annotation-separate', len(detail['annotations']) == 1
    and detail['annotations'][0]['id'] == 'detail-provenance'
    and detail['annotations'][0]['text'] == 'Transformer · Transformer · rev 31\n0 boundary bindings shown; 46 internal adapter/hidden bindings retained in metadata.'
    and detail['annotations'][0]['id'] not in canonical_nodes and detail['annotations'][0]['id'] not in canonical_edges)

pdf_file = OUT / 'wholePdf/figure.pdf'
pdf = pdf_file.read_bytes()
pdf_receipt = exports['wholePdf']['receipt']
whole_receipt = exports['wholeSvg']['receipt']
box = re.search(rb'/MediaBox\s*\[([^\]]+)\]', pdf)
box_values = [float(value) for value in box.group(1).split()]
page_pt = [box_values[2] - box_values[0], box_values[3] - box_values[1]]
result = subprocess.run(['/usr/bin/pdfinfo', str(pdf_file)], capture_output=True, text=True, check=False)
(OUT / 'pdfinfo.stdout.txt').write_text(result.stdout)
(OUT / 'pdfinfo.stderr.txt').write_text(result.stderr)
add('pdf:actual-parser-success', result.returncode == 0)
add('pdf:format-page-count-and-eof', pdf.startswith(b'%PDF-1.5') and pdf.rstrip().endswith(b'%%EOF')
    and re.search(r'^Pages:\s+1$', result.stdout, re.M) is not None and re.search(r'^PDF version:\s+1.5$', result.stdout, re.M) is not None)
normalized_svg_height = float(ET.parse(OUT / 'wholeSvg/figure.svg').getroot().get('height').removesuffix('mm'))
add('pdf:physical-page-size', near(page_pt[0], 180 / 25.4 * 72, 1e-6)
    and near(page_pt[1], normalized_svg_height / 25.4 * 72, 1e-6)
    and near(page_pt[1], pdf_receipt['heightMm'] / 25.4 * 72, .000015)
    and all(near(a, b, 1e-6) for a, b in zip(page_pt, pdf_receipt['pageSizePt'])), page_pt)
add('pdf:whole-svg-raw-normalized-input-exact', all(pdf_receipt[key] == whole_receipt[key]
    for key in ['inputSvgDigest', 'sceneSvgDigest', 'svgDigest', 'viewBox', 'exportScope', 'widthMm', 'heightMm', 'physicalPreflight']))
add('pdf:formal-python-and-converter', pdf_receipt['pythonExecutable'] == str(ROOT / '.venv/bin/python')
    and pdf_receipt['converterVersion'] == '2.8.2' and pdf_receipt['converterOrigin'].startswith(str(ROOT / '.venv/')))
exports['wholePdf'].update({'actualPageSizePt': page_pt, 'pdfinfoExitCode': result.returncode})

reopened = read(BROWSER / '34-final-saved-reopened.json')
reopened_xml = ET.parse(BROWSER / '34-final-saved-reopened.svg').getroot()
whole_raw = ET.parse(OUT / 'whole.raw.svg').getroot()
add('browser:reopened-current-document-metadata-exact', meta(reopened_xml) == meta(whole_raw) == json.loads(reopened['metadata']))
add('browser:reopened100-and-status-rev31', 'scale(1)' in reopened['paper'] and 'rev 31' in reopened['bodyText']
    and '已重开保存的画布' in reopened['bodyText'])
for attr in ['data-edge-id', 'data-caption-guide-id']:
    observed = {node.get(attr): structural(node) for node in reopened_xml.iter() if node.get(attr)}
    expected = {node.get(attr): structural(node) for node in whole_raw.iter() if node.get(attr)}
    add('browser:reopened-whole-publication-exact:' + attr, observed == expected)
reopened_ports = {node.get('data-port-id'): node for node in reopened_xml.iter() if node.get('data-port-id')}
raw_ports = {node.get('data-port-id'): node for node in whole_raw.iter() if node.get('data-port-id')}
add('browser:reopened-port-set-exact', set(reopened_ports) == set(raw_ports))
for pid, port in raw_ports.items():
    visible_circles = [node for node in reopened_ports[pid].iter(NS + 'circle') if node.get('r') == '2.6']
    add('browser:reopened-visible-port:' + pid, len(visible_circles) == 1 and visible_circles[0].get('cx') == port.get('cx')
        and visible_circles[0].get('cy') == port.get('cy') and visible_circles[0].get('fill') == port.get('fill'))
for name, label, ext in [('35-whole-180-pdf-ui', 'wholePdf', 'pdf'), ('36-whole-180-svg-ui', 'wholeSvg', 'svg'), ('37-detail-180-svg-ui', 'detailSvg', 'svg')]:
    ui = read(BROWSER / (name + '.json'))
    identifier = identities[label]
    file_url = f'http://127.0.0.1:42937/api/exports/{identifier}/figure.{ext}'
    receipt_url = f'http://127.0.0.1:42937/api/exports/{identifier}/receipt'
    add('browser:' + name + ':actual-export-links', sum(link['href'] == file_url for link in ui['links']) == 2
        and any(link['href'] == receipt_url for link in ui['links']))
    add('browser:' + name + ':current-build', ui['scripts'] == ['http://127.0.0.1:42937/assets/index-CXutz4Vh.js'])
    if 'text' in ui:
        add('browser:' + name + ':recorded-svg-success-rev31', '文件已生成 · SVG' in ui['text'] and '视觉版本 31' in ui['text'] and 'ApiError' not in ui['text'])
add('browser:pdf-ui-evidence-limited-to-links', 'text' not in read(BROWSER / '35-whole-180-pdf-ui.json')
    and 'bodyText' not in read(BROWSER / '35-whole-180-pdf-ui.json'))

checks = read(OUT.parent / 'checks-final-attempt-2/receipt.json')
for kind in ['inputs', 'build', 'publicationInputs']:
    for row in checks[kind]:
        file = ROOT / row['path']
        add('checks:' + kind + ':' + row['path'], digest(file) == row['sha256'] and file.stat().st_size == row['bytes'])
add('checks:unified-command-success', all(row['exitCode'] == 0 for row in checks['checks']))
studio_log = (OUT.parent / 'checks-final-attempt-2/studio.txt').read_text()
publication_log = (OUT.parent / 'checks-final-attempt-2/publication.txt').read_text()
add('checks:studio409-no-skips', all(needle in studio_log for needle in ['tests 409', 'pass 409', 'fail 0', 'cancelled 0', 'skipped 0']))
add('checks:publication11-no-skips', 'Ran 11 tests' in publication_log and '\nOK\n' in publication_log and 'skipped' not in publication_log)

report = {'schema': 'archcanvas-current-actual-export-independent-audit/1', 'createdUtc': datetime.now(timezone.utc).isoformat(),
    'relations': rows, 'relationCount': len(rows), 'failedRelations': [row for row in rows if not row['passed']], 'exports': exports,
    'frozenInputs': len(frozen), 'currentBindings': {'sourceTestConfig': len(checks['inputs']), 'build': len(checks['build']),
                                               'sourceAndBuild': len(checks['inputs']) + len(checks['build']), 'publicationSeparate': len(checks['publicationInputs'])},
    'physicalMeasurements': {'whole180MinTextPt': exports['wholeSvg']['independentMinTextPt'],
        'detail180MinTextPt': exports['detailSvg']['independentMinTextPt'],
        'whole85CalculatedPreviewMinTextPt': exports['wholeSvg']['independentMinTextPt'] * 85 / 180,
        'actual85Artifact': False, 'humanPublicationApproval': False},
    'pixelObservations': {'personallyViewedByThisAuditor': [], 'owner': '/root', 'claim': 'No pixel or glyph assessment by this independent parser audit.'},
    'limits': ['AI audit is not a human participant; humans remain zero.', 'No user model imported or executed.',
               'Complete XML equality excludes only root height precision normalization; it does not establish glyph fidelity or font embedding.',
               'Nominal physical text sizes are not human physical publication approval.',
               'Only these three actual UI exports and this revision31 saved document are certified here; no global routing or general usability claim.',
               'PDF UI snapshot has links only, not recorded success text; actual file/parser/provenance establish artifact creation.',
               'No continuous gesture or presented-frame performance assertion.']}
(OUT / 'report.json').write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n')
print(json.dumps({'relations': len(rows), 'failedRelations': report['failedRelations'], 'physical': report['physicalMeasurements'], 'currentBindings': report['currentBindings']}, ensure_ascii=False))
raise SystemExit(1 if report['failedRelations'] else 0)
