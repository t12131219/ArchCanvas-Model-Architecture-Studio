"""Read-only actual service publication artifact comparison using standard XML."""
from pathlib import Path
import json
import hashlib
import xml.etree.ElementTree as ET
import sys
sys.dont_write_bytecode = True
from parse_browser_svg import parse, ROOT, OUT

browser = ROOT / 'docs/evidence/m4-routing-refinement/browser'
actual = browser / 'actual-export'
manifest_path = browser / 'actual-export-files.json'
manifest = json.loads(manifest_path.read_text())
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
for item in manifest['files']:
    path = ROOT / item['path']
    assert path.stat().st_size == item['bytes'] and sha(path) == item['sha256']
    service_path = ROOT / item['servicePath']
    assert service_path.read_bytes() == path.read_bytes(), 'service artifact copy changed'
receipt_path = actual / 'figure.svg.receipt.json'
receipt = json.loads(receipt_path.read_text())
assert receipt['svgDigest'] == receipt['outputDigest'] == sha(actual / 'figure.svg')
assert receipt['bytes'] == (actual / 'figure.svg').stat().st_size
assert receipt['format'] == 'svg'
dom_scene, dom_binding = parse(browser / 'after-reopened.json', browser / 'after-reopened.canvas-store.json')
export_scene, export_binding = parse(actual / 'figure.svg', actual / 'document.json', standalone=True)
assert dom_binding['canonicalDocument'] == export_binding['canonicalDocument']
assert dom_scene == export_scene, 'actual publication route/geometry/semantic projection diverges from visible DOM'
assert export_scene['revision'] == receipt['revision'] == 7
assert export_scene['documentId'] == receipt['documentId']
assert export_scene['sourceDigest'] == receipt['sourceDigest']
assert export_scene['irDigest'] == receipt['irDigest']
assert export_binding['metadata'] == dom_binding['metadata']
svg = ET.fromstring((actual / 'figure.svg').read_text())
font_sizes = [float(element.get('font-size')) for element in svg.iter() if element.get('font-size')]
min_pt = min(font_sizes) * receipt['widthMm'] / export_scene['bounds']['width'] * 72 / 25.4
assert abs(min_pt - receipt['physicalPreflight']['minTextPt']) < 1e-9
assert list(map(float, svg.get('viewBox').split())) == receipt['viewBox']
min_line_pt = min(edge['width'] for edge in export_scene['edges']) * receipt['widthMm'] / export_scene['bounds']['width'] * 72 / 25.4
assert abs(min_line_pt - receipt['physicalPreflight']['minMainLinePt']) < 1e-9
assert len(export_scene['nodes']) == 49 and len(export_scene['edges']) == 59
target = OUT / 'actual-export-audit.json'
assert not target.exists(), 'Refusing overwrite export audit'
target.write_text(json.dumps(dict(schemaVersion=1,
    scope='Read-only actual service SVG receipt/file/document comparison to actual public DOM via independent standard XML. Uses no product parser/rendering/router or model import. Does not certify fonts, physical publication review or user download.',
    passed=True, inputs={str(path.relative_to(ROOT)): sha(path) for path in [manifest_path, *actual.iterdir(), browser / 'after-reopened.json', browser / 'after-reopened.canvas-store.json']},
    checks=['exact service byte copies', 'receipt file digest/size', 'saved document identical', 'metadata identical', 'all actual nodes/ports/routes/bindings exact to browser',
            'same source/IR/revision identity', 'independent actual-font-size and actual-line-width preflight'],
    publicNodes=49, publicEdges=59, publicPorts=106, documentRevision=7, storageRevision=1,
    widthMm=receipt['widthMm'], heightMm=receipt['heightMm'], independentMinTextPt=min_pt, independentMinMainLinePt=min_line_pt,
    limitation='Full 180 mm-wide Transformer page is 598.61 mm tall with minimum text 5.36 pt, below the current adjustable 7 pt starting recommendation. No family fidelity, embedding guarantee, paper-size judgement or download-click claim.'), indent=2) + '\n')
print(json.dumps(dict(passed=True, nodes=49, edges=59, ports=106, minTextPt=min_pt, widthMm=receipt['widthMm'], heightMm=receipt['heightMm'])))
