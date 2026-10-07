"""Freeze narrow pre-family actual paths for the style-identity counterexample."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent


def bind(path):
    raw = path.read_bytes()
    return {'path': str(path.relative_to(ROOT)), 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


capture = ROOT / 'docs/evidence/m4-ancestor-corridor-work/baseline/capture.json'
record = next(item for item in json.loads(capture.read_text())['records'] if item['key'] == 'transformer-level3-paper-180')
folder = HERE / 'memory-control'
folder.mkdir()
before = [bind(capture), bind(Path(__file__))]
records = []
for key in ['input', 'scene']:
    original = ROOT / record[key]['path']
    archive = ROOT / record[key]['archivedSource']['archivePath']
    expected = {name: record[key][name] for name in ['path', 'bytes', 'sha256']}
    assert bind(original) == expected
    assert original.read_bytes() == archive.read_bytes()
    before.extend([bind(original), bind(archive)])
    target = folder / ('canvas.json' if key == 'input' else 'scene.json')
    with target.open('xb') as stream:
        stream.write(original.read_bytes())
    records.append({'source': bind(original), 'archive': bind(archive), 'copy': bind(target)})
after = [bind(ROOT / item['path']) for item in before]
assert after == before
receipt = {'protocol': 'archcanvas-monochrome-role-memory-control-freeze/1', 'capturedAt': datetime.now(timezone.utc).isoformat(),
           'records': records, 'inputsBefore': before, 'inputsAfter': after, 'inputsUnchanged': True,
           'literalOldRoutes': {'edge:44': 'M 237 2772 V 2785 H 855 V 397 H 621.6 V 410',
                                'edge:55': 'M 237 2772 V 2778 H 430 V 766 H 623 V 772'},
           'literalEqualStyleFamily': {'edge:44': 'M 237 2772 V 2778 H 467 V 397 H 621.6 V 410',
                                      'edge:55': 'M 237 2772 V 2778 H 467 V 766 H 623 V 772'},
           'limits': 'Two actual historical path inputs and independent literals only; no product call, model execution, new browser or human acceptance.'}
out = folder / 'capture.json'
with out.open('x') as stream:
    json.dump(receipt, stream, indent=2); stream.write('\n')
print(json.dumps({'receipt': bind(out), 'inputsUnchanged': True}))
