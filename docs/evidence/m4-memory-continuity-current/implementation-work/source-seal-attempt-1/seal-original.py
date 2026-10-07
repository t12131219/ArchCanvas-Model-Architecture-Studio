"""Freeze this stage's product bytes and finite implementation evidence.

Uses only the formal project Python. Never edits an existing evidence attempt.
"""
from pathlib import Path
from datetime import datetime, timezone
import difflib
import hashlib
import json
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[3]
STAGE = ROOT / 'docs/evidence/m4-memory-continuity-current'
WORK = STAGE / 'implementation-work'
OUT = WORK / 'source-seal-attempt-1'
OUT.mkdir(exist_ok=False)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def bind(path):
    raw = path.read_bytes()
    return {'path': str(path.relative_to(ROOT)), 'bytes': len(raw), 'sha256': digest(raw)}


before_path = STAGE / 'before-change/manifest.json'
receipt_path = STAGE / 'checks-final-attempt-2/receipt.json'
before = json.loads(before_path.read_text())
receipt = json.loads(receipt_path.read_text())
current = receipt['inputs'] + receipt['build'] + receipt['publicationInputs']
prior_map = {row['path']: row for row in before['files'] if row['category'] == 'current-runtime-check-input'}
current_map = {row['path']: row for row in current}
checks = []


def relation(name, actual, expected):
    checks.append({'name': name, 'passed': actual == expected,
                   **({} if actual == expected else {'actual': actual, 'expected': expected})})


for row in current:
    actual = bind(ROOT / row['path'])
    relation('current-receipt:' + row['path'], actual,
             {key: row[key] for key in ['path', 'bytes', 'sha256']})
for row in before['files']:
    raw = (ROOT / row['snapshot']).read_bytes()
    relation('before-copy:' + row['path'], [len(raw), digest(raw)], [row['bytes'], row['sha256']])

changed = [p for p in current_map if p in prior_map and current_map[p]['sha256'] != prior_map[p]['sha256']]
added = [p for p in current_map if p not in prior_map]
removed = [p for p in prior_map if p not in current_map]
expected_changed = ['studio/src/core/exportScene.ts', 'studio/src/core/scene.ts',
                    'studio/tests/historical-memory-caption-compat.ts',
                    'studio/tests/memory-caption-stability-independent.test.ts', 'studio/dist/index.html']
expected_added = ['studio/src/core/memoryContinuity.ts', 'studio/tests/historical-memory-continuity-compat.ts',
                  'studio/tests/memory-continuity-independent.test.ts', 'studio/dist/assets/index-CU5JhnoS.js']
relation('only-authorized-changed-inputs', sorted(changed), sorted(expected_changed))
relation('only-authorized-added-inputs', sorted(added), sorted(expected_added))
relation('only-previous-generated-js-replaced', removed, ['studio/dist/assets/index-_KAUBMcR.js'])

# Bind actual old test helper locations plus the new immediately-before core.
historical = [ROOT / row['path'] for row in before['files'] if row['category'] != 'current-runtime-check-input']
immediate_core = sorted((STAGE / 'before-change/inputs/studio/src/core').glob('*.ts'))
fixture = WORK / 'detail-consumer-literal.json'
paths = [ROOT / row['path'] for row in current] + historical + immediate_core + [fixture]
frozen = []
for p in paths:
    snapshot = OUT / 'inputs' / p.relative_to(ROOT)
    snapshot.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(p, snapshot)
    row = bind(p)
    relation('sealed-copy:' + row['path'], snapshot.read_bytes(), p.read_bytes())
    frozen.append({**row, 'snapshot': str(snapshot.relative_to(ROOT))})
manifest = {'schema': 'archcanvas-memory-implementation-source-freeze/1',
            'createdUtc': datetime.now(timezone.utc).isoformat(), 'files': frozen,
            'currentCheckInputs': len(current), 'historicalPreCaptionCore': len(historical),
            'immediatelyBeforeCore': len(immediate_core), 'externalNewTestFixture': 1,
            'scope': '115 Studio source/test/config+3 dist+11 publication; historical cores18+18 and external new fixture1 are explicitly separate. This is not full test-fixture, node_modules, Python/environment or application transitive closure.'}
(OUT / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')

# Diff exclusively against the saved immediately prior formal stage. The
# repository HEAD includes earlier work and is not this change's baseline.
diff = []
source_changed = [p for p in changed + added if p.startswith('studio/') and '/dist/' not in p]
whitespace = []
for rel in source_changed:
    prior_path = ROOT / prior_map[rel]['snapshot'] if rel in prior_map else Path('/dev/null')
    old_text = prior_path.read_text() if rel in prior_map else ''
    new_text = (ROOT / rel).read_text()
    diff.extend(difflib.unified_diff(old_text.splitlines(True), new_text.splitlines(True),
                                   fromfile='before/' + rel, tofile='current/' + rel))
    result = subprocess.run(['git', 'diff', '--no-index', '--check', str(prior_path), str(ROOT / rel)],
                            cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    whitespace.append({'path': rel, 'exitCode': result.returncode, 'output': result.stdout})
    relation('scoped-diff-check:' + rel, [result.returncode, result.stdout], [0, ''])
(OUT / 'source.diff').write_text(''.join(diff))
(OUT / 'scoped-diff-check.json').write_text(json.dumps(whitespace, indent=2) + '\n')
result = subprocess.run(['git', 'diff', '--check', '--', *source_changed], cwd=ROOT, text=True,
                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
relation('git-scoped-diff-check', [result.returncode, result.stdout], [0, ''])

report = {'schema': 'archcanvas-memory-implementation-source-seal/1',
          'createdUtc': datetime.now(timezone.utc).isoformat(),
          'beforeManifest': bind(before_path), 'currentCheckReceipt': bind(receipt_path),
          'manifest': bind(OUT / 'manifest.json'), 'currentBindings': len(current),
          'frozenBindings': len(frozen), 'changed': changed, 'added': added, 'removed': removed,
          'unchangedCurrentBeforeInputs': sum(p in prior_map and row['sha256'] == prior_map[p]['sha256'] for p, row in current_map.items()),
          'beforeFrozenCopies': len(before['files']), 'relations': len(checks),
          'passed': sum(row['passed'] for row in checks), 'failures': [r for r in checks if not r['passed']],
          'checks': checks,
          'scope': 'Product and new external detail fixture freeze only; no browser or global acceptance. Old144 copies remain exact. No App/camera, nonmemory router, Python source/publication or original golden files changed.'}
(OUT / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps({key: report[key] for key in ['currentBindings', 'frozenBindings', 'beforeFrozenCopies', 'relations', 'passed', 'failures']}, indent=2))
raise SystemExit(0 if all(row['passed'] for row in checks) else 1)
