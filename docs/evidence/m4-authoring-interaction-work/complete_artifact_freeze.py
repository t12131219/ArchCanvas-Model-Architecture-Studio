"""Finish manifest after sandbox blocked the first HTTP observation."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[3]
WORK = ROOT / 'docs/evidence/m4-authoring-interaction-work'
ART = WORK / 'actual-artifacts-attempt-1'
STORE = ROOT / '.archcanvas/m4-collapse-preview-20261006-attempt-1'
def binding(p):
    b=p.read_bytes()
    return dict(path=str(p.relative_to(ROOT)),bytes=len(b),sha256=hashlib.sha256(b).hexdigest())
titles={'M4 · 端口与纵向链':'vertical','M4 · 合并端口':'residual','M4 · 合并端口原生':'merge','M4 · MLP 起点':'mlp','M4 · CNN 拖入起点':'cnn'}
pairs=[]
for p in sorted((STORE/'drafts').glob('*.json')):
    title=json.loads(p.read_text())['draft']['title']
    if title in titles:pairs.append((p,ART/(titles[title]+'-draft-envelope.json')))
pairs.append((STORE/'documents/canvas-architecture-model.AuthoredModel-306378c82c52-704b0c13.json',ART/'vertical-managed-envelope.json'))
for p in sorted((STORE/'projects').glob('*/project.json')):
    source=p.parent/'source/model.py'
    if source.read_bytes()==(ART/'vertical-model.py').read_bytes():
        pairs.extend([(p,ART/'vertical-project.json'),(source,ART/'vertical-model.py')])
for name in ['figure.svg','figure.svg.receipt.json','document.json']:
    pairs.append((STORE/'exports/a6ea97deb11a440fbc9aee3aacf1d340'/name,ART/'vertical-export'/name))
copies=[]
for source,target in pairs:
    assert source.read_bytes()==target.read_bytes()
    copies.append(dict(source=binding(source),copy=binding(target)))
assets=[]
inventory=json.loads((WORK/'browser-attempt-1/observed-assets.json').read_text())
for a in inventory['assets']:
    if a['kind'] not in ('script','stylesheet'):continue
    with urlopen(a['url'],timeout=10) as r:data=r.read();status=r.status
    p=ART/('http-'+a['name']);assert not p.exists();p.write_bytes(data)
    disk=ROOT/'studio/dist/assets'/a['name']
    assets.append(dict(url=a['url'],status=status,observation='Read-only HTTP read of already observed URL. Does not independently read browser cache.',received=binding(p),disk=binding(disk),exact=data==disk.read_bytes()))
assert all(a['exact'] for a in assets)
x=dict(schemaVersion=1,generatedAt=datetime.now(timezone.utc).isoformat(),scope='Actual saved draft, project, source, managed document and native SVG copies. No model execution.',firstAttemptFailure='freeze_browser.py copied 11 actual files then its first HTTP asset read was denied by sandbox socket PermissionError. Copies preserved, not repeated or rewritten. This sequential authorized HTTP read completes the manifest.',copies=copies,assets=assets)
p=ART/'manifest.json';assert not p.exists();p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(dict(copies=len(copies),assets=len(assets),manifest=binding(p)),ensure_ascii=False))
