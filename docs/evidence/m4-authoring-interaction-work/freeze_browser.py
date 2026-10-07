"""Freeze actual UI-produced artifacts; no model import or execution."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[3]
WORK = ROOT / 'docs/evidence/m4-authoring-interaction-work'
RAW = WORK / 'browser-attempt-1'
STORE = ROOT / '.archcanvas/m4-collapse-preview-20261006-attempt-1'
ART = WORK / 'actual-artifacts-attempt-1'
ART.mkdir(exist_ok=False)

def binding(p):
    b = p.read_bytes()
    return dict(path=str(p.relative_to(ROOT)), bytes=len(b), sha256=hashlib.sha256(b).hexdigest())

copies = []
def copy(p, name):
    target = ART / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(p.read_bytes())
    assert p.read_bytes() == target.read_bytes()
    copies.append(dict(source=binding(p), copy=binding(target)))

titles = {'M4 · 端口与纵向链': 'vertical', 'M4 · 合并端口': 'residual', 'M4 · 合并端口原生': 'merge', 'M4 · MLP 起点': 'mlp', 'M4 · CNN 拖入起点': 'cnn'}
for p in sorted((STORE / 'drafts').glob('*.json')):
    title = json.loads(p.read_text())['draft']['title']
    if title in titles:
        copy(p, titles[title] + '-draft-envelope.json')
doc = STORE / 'documents/canvas-architecture-model.AuthoredModel-306378c82c52-704b0c13.json'
copy(doc, 'vertical-managed-envelope.json')
for p in sorted((STORE / 'projects').glob('*/project.json')):
    source = p.parent / 'source/model.py'
    if source.read_bytes() == (RAW / 'vertical-generated-source-visible.py').read_bytes():
        copy(p, 'vertical-project.json')
        copy(source, 'vertical-model.py')
export = STORE / 'exports/a6ea97deb11a440fbc9aee3aacf1d340'
for name in ['figure.svg', 'figure.svg.receipt.json', 'document.json']:
    copy(export / name, 'vertical-export/' + name)

asset_results = []
inventory = json.loads((RAW / 'observed-assets.json').read_text())
for asset in inventory['assets']:
    if asset['kind'] not in ('script', 'stylesheet'):
        continue
    with urlopen(asset['url'], timeout=10) as response:
        data = response.read()
        status = response.status
    path = ART / ('http-' + asset['name'])
    path.write_bytes(data)
    disk = ROOT / 'studio/dist/assets' / asset['name']
    asset_results.append(dict(url=asset['url'], status=status, observation='Read-only HTTP read of URL already observed by pageAssets; this is not an independent read of browser cache memory.', received=binding(path), disk=binding(disk), exact=data == disk.read_bytes()))
assert all(a['exact'] for a in asset_results)
manifest = dict(schemaVersion=1, generatedAt=datetime.now(timezone.utc).isoformat(), scope='Copies of actual saved drafts and fresh managed project, source and native SVG export. No model execution. HTTP asset comparison is bounded to observed URLs and current service bytes.', copies=copies, assets=asset_results)
(ART / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
print(json.dumps(dict(copies=len(copies), assets=len(asset_results), manifest=binding(ART / 'manifest.json')), ensure_ascii=False))
