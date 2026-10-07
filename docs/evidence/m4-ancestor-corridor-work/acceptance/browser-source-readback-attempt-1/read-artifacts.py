"""Read-only independent XML/storage/export/bundle checks; no product execution."""
import hashlib
import json
import math
import re
import xml.etree.ElementTree as ET
from pathlib import Path

root = Path(__file__).resolve().parents[5]
out = Path(__file__).parent
browser = root / 'docs/evidence/m4-ancestor-corridor-work/browser-final-attempt-1'
exports = root / '.archcanvas/m4-ancestor-corridor-session/exports'

def binding(path):
    raw = path.read_bytes()
    return {'path': str(path.relative_to(root)), 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}

def load(path):
    return json.loads(path.read_text())

def write(name, value):
    with (out / name).open('x') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write('\n')

def canonical(element):
    return [element.tag, sorted(element.attrib.items()), element.text or '', element.tail or '', [canonical(child) for child in element]]

session = load(root / 'docs/evidence/m4-ancestor-corridor-work/root/session-inputs.json')
record = next(row for row in session['records'] if row['case'] == 'transformer-level3-paper-180')
saved = load(root / record['storedPath'])['document']
replay = load(out / 'renderer-readback.json')
build_receipt_path = root / 'docs/evidence/m4-ancestor-corridor-work/root/build-attempt-3/receipt.json'
build_receipt = load(build_receipt_path)
assert build_receipt['exitCode'] == 0 and build_receipt['sourceBeforeAfterExact']
for item in build_receipt['after'] + build_receipt['logs']:
    assert binding(root / item['path']) == item
assert build_receipt['bindings'] == build_receipt['after']
index = (root / 'studio/dist/index.html').read_text()
assert '/assets/index-au3IB_0Q.js' in index and '/assets/index-B6WbMowt.css' in index
assert binding(root / 'studio/dist/assets/index-au3IB_0Q.js')['sha256'] == 'dca15460bc9ed8def5ff80c9da5dfcf16bb49f7a230986e0ffeef1a6b0e7548b'
assert binding(root / 'studio/dist/assets/index-B6WbMowt.css')['sha256'] == '172a09a8c147e53c3bef426cf76b59b8cc4893e891eb6e920aa7b25a0bb024e0'
export_records = []
for identity, kind in [('72f21096acbc4dc1a3d98e1193baa8c9', 'svg'), ('187559f6e5984e84bddbf16eff24a613', 'pdf')]:
    folder = exports / identity
    document_path = folder / 'document.json'
    artifact_path = folder / ('figure.' + kind)
    receipt_path = folder / ('figure.' + kind + '.receipt.json')
    receipt = load(receipt_path)
    assert load(document_path) == saved
    actual = binding(artifact_path)
    assert actual['bytes'] == receipt['bytes'] and actual['sha256'] == receipt['outputDigest']
    assert receipt['path'] == str(artifact_path)
    assert receipt['documentId'] == saved['id'] and receipt['revision'] == saved['revision']
    assert receipt['sourceDigest'] == saved['architecture']['sourceDigest'] and receipt['irDigest'] == saved['architecture']['irDigest']
    assert receipt['sourceDigest'] == saved['sourceBindingDigest']
    assert receipt['sceneSvgDigest'] == receipt['inputSvgDigest'] == binding(out / 'renderer-replay-static.svg')['sha256']
    assert receipt['renderer'] == 'archcanvas-svg/1.0' and receipt['exportScope'] == {'kind': 'document'}
    assert Path(receipt['publicationOrigin']).resolve() == (root / 'src/archcanvas_publication/exporter.py').resolve()
    assert receipt['viewBox'] == [0, 0, 941, 3166]
    assert receipt['widthMm'] == 180
    assert abs(receipt['heightMm'] - 180 * 3166 / 941) < 1e-8
    details = {'id': identity, 'format': kind, 'document': binding(document_path), 'artifact': actual, 'receipt': binding(receipt_path),
               'documentAndSourceBindingExact': True, 'actualOutputDigestExact': True, 'rendererInputDigestExact': True,
               'widthMm': receipt['widthMm'], 'heightMm': receipt['heightMm'], 'physicalPreflight': receipt['physicalPreflight'],
               'fonts': receipt['fonts']}
    if kind == 'svg':
        actual_tree = ET.parse(artifact_path).getroot()
        browser_tree = ET.parse(browser / 'l3-export-browser.svg').getroot()
        assert canonical(actual_tree) == canonical(browser_tree)
        details['actualAndBrowserSvgXmlTreeExact'] = True
        assert receipt['svgDigest'] == actual['sha256']
    else:
        raw = artifact_path.read_bytes()
        assert raw.startswith(b'%PDF-')
        pages = len(re.findall(rb'/Type\s*/Page\b', raw))
        boxes = re.findall(rb'/MediaBox\s*\[\s*([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)\s*\]', raw)
        assert pages == 1 and len(boxes) == 1
        page = list(map(float, boxes[0]))
        assert page[:2] == [0, 0]
        assert abs(page[2] - receipt['pageSizePt'][0]) < .00001 and abs(page[3] - receipt['pageSizePt'][1]) < .00001
        assert abs(page[2] - 180 / 25.4 * 72) < .00001 and abs(page[3] - receipt['heightMm'] / 25.4 * 72) < .00001
        details['pdfSignaturePagesAndMediaBoxChecked'] = {'pages': pages, 'mediaBox': page}
    export_records.append(details)
links = load(browser / 'export-links.json')
assert {row['href'] for row in links} == {'/api/exports/72f21096acbc4dc1a3d98e1193baa8c9/figure.svg', '/api/exports/72f21096acbc4dc1a3d98e1193baa8c9/receipt'}
icon = ET.parse(browser / 'l3-export-preview.svg').getroot()
assert icon.get('width') == '18' and icon.get('height') == '18' and icon.get('aria-hidden') == 'true'
assert not list(icon.iter('metadata'))

port_records = []
for name in ['port-role-connected.svg', 'port-native-connected.svg']:
    tree = ET.parse(browser / name).getroot()
    nodes = [e for e in tree.iter('g') if e.get('data-draft-node')]
    edges = [e for e in tree.iter('g') if e.get('data-draft-edge')]
    ports = [e for e in tree.iter('g') if e.get('data-draft-port')]
    assert len(nodes) == 2 and len(edges) == 1 and len(ports) == 3
    circles = {}
    for node in nodes:
        match = re.fullmatch(r'translate\(([-\d.]+) ([-\d.]+)\)', node.get('transform', ''))
        assert match
        nx, ny = map(float, match.groups())
        for port in node:
            if not port.get('data-draft-port'):
                continue
            assert port.get('data-node') == node.get('data-draft-node') and port.get('role') == 'button'
            visible = [circle for circle in port if circle.tag == 'circle' and circle.get('r') == '5']
            assert len(visible) == 1
            circle = visible[0]
            circles[(node.get('data-draft-node'), port.get('data-draft-port'))] = [nx + float(circle.get('cx')), ny + float(circle.get('cy'))]
    route_elements = [e for e in edges[0] if e.tag == 'path']
    assert len(route_elements) == 2 and route_elements[0].get('d') == route_elements[1].get('d')
    route = route_elements[1].get('d')
    assert route == 'M 466 254 H 472 V 288 H 284 V 382 H 290'
    source = next(node for node in nodes if any(child.tag == 'text' and child.text == 'Input' for child in node))
    target = next(node for node in nodes if any(child.tag == 'text' and child.text == 'Linear' for child in node))
    assert circles[(source.get('data-draft-node'), 'output')] == [466, 254]
    assert circles[(target.get('data-draft-node'), 'input')] == [290, 382]
    port_records.append({'raw': binding(browser / name), 'nodes': len(nodes), 'edges': len(edges), 'ports': len(ports),
                         'edgeId': edges[0].get('data-draft-edge'), 'nodeIds': [node.get('data-draft-node') for node in nodes],
                         'route': route, 'sourceCircle': [466, 254], 'targetCircle': [290, 382], 'visibleAndHitPathsEqual': True})
port_trees = [ET.parse(browser / name).getroot() for name in ['port-role-connected.svg', 'port-native-connected.svg']]
port_differences = []
for index, (first, second) in enumerate(zip(port_trees[0].iter(), port_trees[1].iter())):
    if first.attrib != second.attrib or first.text != second.text:
        port_differences.append({'elementIndex': index, 'tag': first.tag, 'roleAttributes': first.attrib, 'nativeAttributes': second.attrib,
                                 'roleText': first.text, 'nativeText': second.text})
assert len(list(port_trees[0].iter())) == len(list(port_trees[1].iter()))
assert all(row['tag'] == 'g' and {k: v for k, v in row['roleAttributes'].items() if k != 'data-draft-edge'} == {k: v for k, v in row['nativeAttributes'].items() if k != 'data-draft-edge'} and row['roleText'] == row['nativeText'] for row in port_differences)
raw_port_extras = [binding(browser / name) for name in ['port-rects.json', 'port-role-connected.dom.txt', 'port-native-connected.ax.txt', 'port-native-start.ax.txt', 'port-start.dom.txt']]
report = {'schemaVersion': 1, 'scope': 'Read-only artifacts/storage/receipts/bundle/port raw source comparison; no new tests/browser/services',
          'rendererReadback': binding(out / 'renderer-readback.json'), 'buildReceipt': binding(build_receipt_path),
          'currentBuildInputAndLogBindingsExact': True, 'buildAssets': [binding(root / 'studio/dist/index.html'), binding(root / 'studio/dist/assets/index-au3IB_0Q.js'), binding(root / 'studio/dist/assets/index-B6WbMowt.css')],
          'exports': export_records, 'exportLinks': binding(browser / 'export-links.json'),
          'previewIconOnly': binding(browser / 'l3-export-preview.svg'), 'ports': port_records, 'rawPortExtras': raw_port_extras, 'rawPortDraftEdgeIdDifferences': port_differences,
          'sourceAndTestsUnmodified': True,
          'limits': ['14% overview is not publication clarity acceptance.', 'Actual export screenshot covers only the top region.', 'No new matrix or human review exists for this round.',
                    'Port artifacts are draft presentation raw only and contain no canonical Canvas/Scene metadata. Two nodes/one edge with circle/path agreement does not establish saved/reopened persistence.',
                    'Fresh port save/reopen remains root-owned and is not claimed by this readback.', 'PDF bytes/page dimensions verified; glyph/font and rendered pixel fidelity are not independently certified here.']}
write('artifact-readback.json', report)
print(json.dumps({'actualSvgOutputDigestExact': True, 'actualPdfOutputDigestExact': True, 'actualSvgBrowserXmlTreeExact': True, 'draftNodes': 2, 'draftEdges': 1, 'report': str((out / 'artifact-readback.json').relative_to(root))}))
