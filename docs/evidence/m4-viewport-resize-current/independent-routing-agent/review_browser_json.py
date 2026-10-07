"""Independent public DOM geometry readback; no browser input or product writes."""
from pathlib import Path
import datetime, hashlib, json, re, sys, xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[4]
STAGE = ROOT / 'docs/evidence/m4-viewport-resize-current'
OUT = STAGE / 'independent-routing-agent' / sys.argv[1]
if OUT.exists():
    raise SystemExit('Append-only evidence: choose a fresh output name')
OUT.mkdir()
MAX_SAMPLE = int(sys.argv[2]) if len(sys.argv) > 2 else 9999
FILES = sorted(p for p in (STAGE / 'browser').glob('*.json') if p.name.split('-')[0].isdigit() and int(p.name.split('-')[0]) <= MAX_SAMPLE)
checks, observations, rows = [], [], []
def binding(p):
    data = p.read_bytes()
    return {'path': p.relative_to(ROOT).as_posix(), 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}
def check(name, passed, **detail):
    checks.append({'name': name, 'passed': bool(passed), **detail})
def geometry(x):
    m = re.search(r'translate\(([-.\d]+)px, ([-.\d]+)px\) scale\(([-.\d]+)\)', x['paper'])
    if not m:
        raise ValueError('Unknown public paper CSS transform')
    px, py, zoom = map(float, m.groups())
    size = x['viewport']
    return {'translation': {'x': px, 'y': py}, 'zoom': zoom,
            'viewport': {'width': size['width'], 'height': size['height']},
            'worldCenter': {'x': (size['width'] / 2 - px) / zoom,
                            'y': (size['height'] / 2 - py) / zoom}}
def centered(g):
    return abs(g['worldCenter']['x'] - 350) <= 1e-6 and abs(g['worldCenter']['y'] - 405) <= 1e-6
source = STAGE / 'checks-final-attempt-2/receipt.json'
receipt = json.loads(source.read_text())
rows.append(binding(source))
assets = [('/assets/' + Path(x['path']).name) for x in receipt['build'] if x['path'].endswith('.js')]
samples = []
svg_reference = None
for p in FILES:
    raw = json.loads(p.read_text())
    rows.append(binding(p))
    if not all(k in raw for k in ('paper', 'viewport', 'svg', 'metadata', 'assets')):
        observations.append({'file': p.name, 'status': 'other-public-UI-evidence', 'keys': list(raw)})
        continue
    number = int(p.name.split('-')[0])
    metadata = json.loads(raw['metadata'])
    svg = ET.fromstring(raw['svg'])
    ns = {'s': 'http://www.w3.org/2000/svg'}
    embedded = json.loads(svg.find('s:metadata', ns).text)
    check(p.name + ' DOM/embedded metadata exact', metadata == embedded)
    check(p.name + ' revision31 source scene bound', metadata['revision'] == 31 and svg.attrib['data-revision'] == '31' and
          metadata['documentId'] == 'canvas-architecture-model.Transformer-01ac6cd61f05-b0bd5bf0' and
          metadata['sourceDigest'] == '01ac6cd61f058e9de5230b0c371527a1fa2b4f73842019e0e5785d5f0deb0916' and
          metadata['irDigest'] == 'b0bd5bf01fa364bf415f6aba9707f5d74d9b7bb058534c0dac54fc48fd3729e6')
    if svg_reference is None:
        svg_reference = raw['svg']
    check(p.name + ' camera-only figure SVG bytes exact', raw['svg'] == svg_reference)
    pre = geometry(raw)
    post = geometry(raw['afterScreenshot']) if 'afterScreenshot' in raw else None
    record = {'file': p.name, 'createdUtc': raw['createdUtc'], 'publicDomBeforeScreenshot': pre,
              'beforeCenter350405': centered(pre), 'assets': raw['assets']}
    if number >= 9:
        check(p.name + ' frozen JS public filename matches', raw['assets'] == assets)
    if post is not None:
        record.update({'publicDomAfterScreenshot': post, 'afterCenter350405': centered(post)})
        observed_stability = all(raw[k] == raw['afterScreenshot'][k] for k in ['paper', 'viewport', 'footer'])
        check(p.name + ' recorded screenshot stability flag exact for its three captured fields',
              raw['publicDomStableAcrossScreenshot'] == observed_stability)
        record['recordedPublicDomStableAcrossScreenshot'] = raw['publicDomStableAcrossScreenshot']
        if 9 <= number <= 23:
            check(p.name + ' post-screenshot restored centre350405 and zoom1', centered(post) and post['zoom'] == 1)
    image = p.with_suffix('.jpg')
    record['screenshotExists'] = image.exists()
    if image.exists():
        rows.append(binding(image))
    samples.append(record)
# Historical failure is evidence; relation checks must never relabel it success.
by_number = {int(x['file'].split('-')[0]): x for x in samples}
for previous, current, delta in [(23, 24, (32, 0)), (24, 25, (-32, 0)), (25, 26, (0, 32)), (26, 27, (0, -32))]:
    if previous in by_number and current in by_number:
        a = by_number[previous]['publicDomAfterScreenshot']; b = by_number[current]['publicDomAfterScreenshot']
        check('four-way native camera delta %s-to-%s' % (previous, current),
              abs(b['translation']['x'] - a['translation']['x'] - delta[0]) <= 1e-6 and
              abs(b['translation']['y'] - a['translation']['y'] - delta[1]) <= 1e-6 and a['zoom'] == b['zoom'] and a['viewport'] == b['viewport'])
for number in [11, 12, 16]:
    if number in by_number:
        row = by_number[number]
        observations.append({'id': 'uncoordinated-pre-screenshot-public-DOM-' + str(number),
            'status': 'centre-requirement-failed-in-initial-DOM-sample',
            'file': row['file'], 'before': row['publicDomBeforeScreenshot'], 'after': row['publicDomAfterScreenshot'],
            'firstPaintCertified': False,
            'reason': 'Initial public DOM retains old/default translation; later readback after screenshot is coordinated. No presented-frame timestamps bind which paint was sampled.'})
# Freeze pre-read inputs again: sources are produced by another agent, so a
# concurrent addition does not retroactively change this bounded file list.
readback = [binding(ROOT / x['path']) for x in rows]
check('all captured input bytes unchanged during bounded readback', rows == readback)
summary = {'schema': 'archcanvas-independent-browser-public-DOM-geometry-readback/1',
    'createdUtc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
    'passed': sum(x['passed'] for x in checks), 'total': len(checks), 'checks': checks,
    'samples': samples, 'otherOrFailedObservations': observations,
    'scope': 'Existing finite CUA public DOM JSON and screenshot-byte inventory; no browser inputs by this auditor. Center is independently derived from CSS translate/scale and viewport dimensions. Checks verify recorded relations, not universal UX success.',
    'limitations': ['Initial public DOM failures are kept separate from passing relation checks.',
        'No first presented frame or paint timestamps were captured; post-screenshot DOM and screenshot content cannot establish first-paint continuity.',
        'afterScreenshot captures only viewport/paper/footer; stability is limited to those fields.',
        'This auditor does not visually inspect screenshots or certify clipping/global routing aesthetics.',
        'Public asset filename matches frozen receipt, but HTTP served bytes were not fetched independently.',
        'No mounted React, actual ResizeObserver timing, presented FPS, human trial, source execution or publication acceptance is established.'],
    'servedBytesHashVerified': False}
p = OUT / 'report.json'
p.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n')
rows.append(binding(p))
script = Path(__file__).resolve()
rows.append(binding(script))
p = OUT / 'manifest.json'
p.write_text(json.dumps({'schema': 'archcanvas-independent-browser-readback-manifest/1', 'rows': rows}, indent=2) + '\n')
print(json.dumps({'passed': summary['passed'], 'total': summary['total'], 'sourceSceneSamples': len(samples),
    'observations': len(observations), 'manifestRows': len(rows), 'manifestSha256': hashlib.sha256(p.read_bytes()).hexdigest()}))
