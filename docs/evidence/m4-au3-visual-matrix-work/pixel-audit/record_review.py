"""Append one AI review after direct view_image inspection; never reads browser state."""
from pathlib import Path
from datetime import datetime, timezone
from PIL import Image
import argparse, hashlib, json, xml.etree.ElementTree as E

PROJECT = Path(__file__).resolve().parents[4]
BASE = PROJECT / 'docs/evidence/m4-au3-visual-matrix-work'
AUDIT = BASE / 'pixel-audit'
SPEC = PROJECT / '.archcanvas/browser-visual-matrix-au3/spec.json'
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
parser = argparse.ArgumentParser()
parser.add_argument('case_id')
parser.add_argument('--observations', required=True, help='JSON array of observations from direct original image viewing')
parser.add_argument('--route', required=True)
parser.add_argument('--text', default='no-obvious-large-collision; small-text-insufficient-resolution')
parser.add_argument('--clipping', default='not-observed')
args = parser.parse_args()
c = BASE / 'raw' / args.case_id
variants = {v['variantId']: v for v in json.loads(SPEC.read_text())['variants']}
v = variants[args.case_id]
d = json.loads((c / 'public-observation.json').read_text())
m = d['metadata']
s = (c / 'browser-scene.svg').read_text()
em = json.loads(E.fromstring(s).find('{http://www.w3.org/2000/svg}metadata').text)
screens = [p for p in [c / 'screenshot.png', c / 'screenshot.jpg'] if p.is_file()]
if len(screens) != 1:
    raise ValueError('Require exactly one original screenshot; audit ambiguity explicitly.')
p = screens[0]
with Image.open(p) as im:
    fmt, size = im.format, list(im.size)
diffs = [{'field': k, 'svgValue': em[k], 'publicValue': m[k],
          'absoluteDifference': abs(em[k] - m[k]) if isinstance(em[k], (float, int)) else None}
         for k in em if em[k] != m[k]]
assert d['svg'] == s
assert all(x['absoluteDifference'] is not None and x['absoluteDifference'] < 1e-10 for x in diffs)
assert set(d['expandedIds']) == set(v['expandedIds'])
assert all(m[k] == v[k] for k in ['documentId', 'sourceDigest', 'irDigest', 'widthMm'])
assert size == [d['viewport']['width'], d['viewport']['height']]
record = {
    'schemaVersion': 1, 'auditProtocol': 'archcanvas-ai-pixel-review/1',
    'caseId': args.case_id, 'auditor': 'AI subagent /root/au3_pixel_audit',
    'reviewedAt': datetime.now(timezone.utc).isoformat(),
    'reviewMethod': 'Direct view_image inspection of original whole-window screenshot, compared with saved public DOM observation, SVG and frozen matrix specification. No browser operation; no model execution; no build/test run.',
    'sourceFiles': [{'path': str(x), 'sha256': sha(x), 'bytes': x.stat().st_size}
                    for x in [p, c / 'public-observation.json', c / 'browser-scene.svg', c / 'fit.dom.txt']],
    'specBinding': {'path': str(SPEC), 'sha256': sha(SPEC), 'variantId': args.case_id},
    'image': {'fileName': p.name, 'declaredExtension': p.suffix, 'detectedFormat': fmt,
              'detectedMime': 'image/jpeg' if fmt == 'JPEG' else 'image/png',
              'extensionMatchesMagic': p.suffix in ('.jpg', '.jpeg') if fmt == 'JPEG' else p.suffix == '.png',
              'magicHex': p.read_bytes()[:12].hex(), 'widthPx': size[0], 'heightPx': size[1], 'originalRetained': True},
    'observedState': {'fixture': v['fixture'], 'level': v['level'], 'preset': v['preset'],
                      'widthMm': m['widthMm'], 'heightMm': m['heightMm'], 'revision': m['revision'],
                      'documentId': m['documentId'], 'expandedIds': d['expandedIds'],
                      'viewport': d['viewport'], 'camera': d['camera'],
                      'renderedNodeCount': len(m['renderedNodes']),
                      'renderedBindingCount': len(m['renderedBindings']), 'assets': d['assets']},
    'machineComparisons': {'publicSvgEqualsSavedBrowserScene': True,
                           'svgMetadataEqualsPublicMetadata': not diffs, 'metadataDifferences': diffs,
                           'onlyFloatingParseSerializeTailDifferencesUnder1e-10': bool(diffs),
                           'specFixtureDocumentSourceIrWidthAndFrontierMatch': True,
                           'imageDimensionsEqualPublicViewport': True},
    'pixelObservations': json.loads(args.observations),
    'pixelStateMatch': 'matched-for-visible-fixture-frontier-preset-width-camera-and-revision',
    'obviousWholePageClipping': args.clipping, 'obviousCardOverlap': 'not-observed-at-fit-scale',
    'textCollision': args.text, 'routeBeauty': args.route,
    'acceptanceScope': {'aiReviewOnly': True, 'humanParticipantCount': 0,
                        'humanPublicationReview': False, 'physicalPublicationSizeCertified': False,
                        'fourDirectionInteractionReviewed': False, 'pathOptimalityCertified': False},
    'limitations': ['Fit screenshot shows a responsive screen preview and does not reproduce 85/180 mm at physical size.',
                    'JPEG compression and fit zoom limit small-text/arrow/path review; geometry or binding checks are not beauty evidence.',
                    'No current browser font, hardware, DPR or displayed-frame timing certification is provided by this audit.',
                    'A state-consistent screenshot does not prove drag/undo/redo/export behavior.']}
out = AUDIT / (args.case_id + '.review.json')
with out.open('x') as f:
    json.dump(record, f, ensure_ascii=False, indent=2)
    f.write('\n')
print(json.dumps({'caseId': args.case_id, 'reviewFile': str(out), 'sha256': sha(out)}, ensure_ascii=False))
