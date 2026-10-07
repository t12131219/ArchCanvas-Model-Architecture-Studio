"""Convert copied actual SVGs for separate AI pixel inspection; do not certify UI frames."""
from pathlib import Path
import hashlib
import json
import sys
import xml.etree.ElementTree as ET

import cairosvg
from PIL import Image

FORMAL = Path(__file__).resolve().parents[5]
WORK = Path(__file__).resolve().parent
SOURCE = FORMAL / 'docs/evidence/m4-collapse-continuity-work/browser-current-attempt-2'
OLD = FORMAL / 'docs/evidence/m4-monochrome-role-work/browser-current/cnn-level0-paper-180/figure.svg'

def binding(path):
    raw = path.read_bytes()
    return {'path': str(path.relative_to(FORMAL)), 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}

def node_rects(root, suffix):
    group = next(e for e in root.iter() if e.tag.endswith('g') and e.attrib.get('data-node-id', '').endswith(suffix))
    return [e.attrib for e in group if e.tag.endswith('rect')]

originals = json.loads((WORK / 'inputs-before.json').read_text())
old_before = binding(OLD)
svg = SOURCE / 'cnn-compact-paper180/figure.svg'
root = ET.fromstring(svg.read_bytes())
viewbox = list(map(float, root.attrib['viewBox'].split()))
png = WORK / 'actual-publication-svg-converted-full.png'
if png.exists():
    raise FileExistsError(png)
cairosvg.svg2png(bytestring=svg.read_bytes(), write_to=str(png), output_width=round(viewbox[2] * 2), output_height=round(viewbox[3] * 2))
im = Image.open(png)
cropbox = [80, 490, 640, 1270]
crop = WORK / 'actual-publication-svg-converted-route-local.png'
im.crop(tuple(cropbox)).save(crop)

facts = []
for label, xml in [('before-failed', ET.fromstring(OLD.read_bytes())), ('after-compact', root)]:
    blocks = node_rects(xml, '.blocks')
    pool = node_rects(xml, '.pool')[0]
    blocks_bottom = max(float(r['y']) + float(r['height']) for r in blocks)
    pool_top = float(pool['y'])
    edge = next(e for e in xml.iter() if e.attrib.get('data-edge-id') == 'edge:20')
    paths = [e.attrib for e in edge if e.tag.endswith('path') and e.attrib.get('stroke') != 'transparent']
    facts.append({'label': label, 'viewBox': xml.attrib['viewBox'], 'blocksRects': blocks, 'poolRect': pool,
                  'actualGapSceneUnits': pool_top - blocks_bottom, 'edge20Paths': paths})

pairs = []
for before in sorted(SOURCE.glob('*-before.json')):
    after = before.with_name(before.name.replace('-before', '-after'))
    b = json.loads(before.read_text()); a = json.loads(after.read_text())
    keys = ['camera', 'dataset', 'viewport', 'url']
    bm = {k: b.get(k) for k in keys}; am = {k: a.get(k) for k in keys}
    pairs.append({'before': binding(before), 'after': binding(after), 'beforePublicState': bm, 'afterPublicState': am, 'equal': bm == am})

receipt = {'kind': 'actual-copied-publication-svg-conversion-for-AI-pixel-review', 'notBrowserPngExport': True,
           'notHumanAcceptance': True, 'modelsExecuted': False, 'physicalFontCertification': False,
           'viewBox': viewbox, 'scale': 2, 'svg': binding(svg), 'full': binding(png), 'routeCrop': {**binding(crop), 'box': cropbox},
           'interpreter': sys.executable, 'cairoSvgOrigin': cairosvg.__file__, 'pillowOrigin': Image.__file__,
           'gapComparisonActualXmlFacts': facts, 'publicImageStatePairs': pairs,
           'originalsBefore': originals, 'originalsAfter': [binding(FORMAL / f['path']) for f in originals],
           'oldSvgBefore': old_before, 'oldSvgAfter': binding(OLD)}
receipt['allOriginalsExact'] = receipt['originalsBefore'] == receipt['originalsAfter'] and receipt['oldSvgBefore'] == receipt['oldSvgAfter']
with (WORK / 'conversion-receipt.json').open('x') as out:
    json.dump(receipt, out, indent=2, ensure_ascii=False); out.write('\n')
print(json.dumps({'gapFacts': facts, 'originals': len(originals), 'allExact': receipt['allOriginalsExact'], 'statePairsExact': all(p['equal'] for p in pairs)}, ensure_ascii=False))
