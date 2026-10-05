from pathlib import Path
import hashlib
import json
from datetime import datetime, timezone

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
target = OUT / 'manifest.json'
assert not target.exists(), 'Refusing to overwrite final manifest'

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

audit = json.loads((OUT / 'audit-after.json').read_text())
assert audit['passed'] == 73 and audit['failures'] == []
browser = json.loads((OUT / 'browser-audit.json').read_text())
assert browser['passed']
export = json.loads((OUT / 'actual-export-audit.json').read_text())
assert export['passed']
for report in [browser, export]:
    for path, binding in report['inputs'].items():
        expected = binding if isinstance(binding, str) else binding['sha256']
        canonical = path if isinstance(binding, str) else binding['path']
        assert sha(ROOT / canonical) == expected, canonical
capture = json.loads((OUT / 'after/capture.json').read_text())
assert capture['sourceStableDuringCapture']
for name, expected in capture['sourceFiles'].items():
    assert sha(ROOT / 'studio/src/core' / name) == expected, name
controls = json.loads((OUT / 'controls.json').read_text())
assert controls['negativeControls'] == controls['rejected'] == 15
files = {str(path.relative_to(ROOT)): sha(path) for path in sorted(OUT.rglob('*')) if path.is_file() and '__pycache__' not in path.parts and path != target}
test = ROOT / 'studio/tests/routing-readability-independent.test.ts'
files[str(test.relative_to(ROOT))] = sha(test)
for report in [browser, export]:
    for path, binding in report['inputs'].items():
        canonical = path if isinstance(binding, str) else binding['path']
        files[canonical] = sha(ROOT / canonical)
target.write_text(json.dumps(dict(schemaVersion=1, createdAt=datetime.now(timezone.utc).isoformat(),
    scope='AI independent geometry/public API/browser-artifact verification. Raw before/intermediate/final captures bound separately. Does not certify human researcher/publication review, a complete current browser visual matrix or native presented performance.',
    checks=dict(publicTests=13, sourceBoundScenes=73, frontiers=9, detailPages=28, moves=36, syntheticSemanticFixtures=3,
                negativeControls=15, rejectedNegativeControls=15, actualBrowserRepresentative=1, actualServiceSvg=1),
    sourceFiles=capture['sourceFiles'], files=files), indent=2) + '\n')
print(json.dumps(dict(boundFiles=len(files), manifestSha256=sha(target))))
