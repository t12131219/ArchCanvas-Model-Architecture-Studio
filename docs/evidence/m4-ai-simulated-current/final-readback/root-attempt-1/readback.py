"""Read-only final hashes and current-link readback; no product execution."""
from pathlib import Path
import hashlib
import json
import re
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[5]
OUT = Path(__file__).resolve().parent
BASE = ROOT / 'docs/evidence/m4-ai-simulated-current'


def bind(path):
    data = path.read_bytes()
    return {'path': str(path.relative_to(ROOT)), 'bytes': len(data),
            'sha256': hashlib.sha256(data).hexdigest()}


checks = []
archive_index = {}
for archive_name in ['before-entry-update/manifest.json', 'before-fixes/manifest.json',
                     'before-final-label/manifest.json']:
    for row in json.loads((BASE / archive_name).read_text())['inputs']:
        archive_index[(row['path'], row['sha256'])] = ROOT / row['snapshot']


def exact(path, row, scope, allow_historical_snapshot=False):
    original = path
    data = path.read_bytes() if path.is_file() else b''
    ok = path.is_file() and hashlib.sha256(data).hexdigest() == row['sha256']
    if 'bytes' in row:
        ok = ok and len(data) == row['bytes']
    archived = False
    if not ok and allow_historical_snapshot:
        path = archive_index.get((row['path'], row['sha256']), original)
        data = path.read_bytes() if path.is_file() else b''
        ok = path.is_file() and hashlib.sha256(data).hexdigest() == row['sha256']
        if 'bytes' in row:
            ok = ok and len(data) == row['bytes']
        archived = path != original
    checks.append({'scope': scope, 'originalPath': str(original), 'path': str(path),
                   'historicalArchiveResolution': archived, 'exact': ok})


receipt_path = BASE / 'checks-final-attempt-3/receipt.json'
receipt = json.loads(receipt_path.read_text())
for row in receipt['inputs'] + receipt['build']:
    exact(ROOT / row['path'], row, 'final-source-build')

manifest_names = [
    'before-entry-update/manifest.json', 'before-fixes/manifest.json',
    'before-final-label/manifest.json', 'novice/manifest.json',
    'gestures/manifest.json', 'catalog-visual/manifest.json',
    'fix-independent/final-manifest.json', 'catalog-followup/manifest.json',
    'browser-fixes/manifest.json', 'final-browser/manifest.json',
    'zoom-followup/manifest.json', 'novice-followup/manifest.json',
    'research-final-preparation/manifest.json',
    'final-readback/catalog-independent/manifest.json',
    'entry-independent-attempt-1/manifest.json',
]
manifest_paths = [BASE / name for name in manifest_names]
manifest_paths += [
    ROOT / 'docs/evidence/m4-dufx-performance-visibility/manifest.json',
    ROOT / 'docs/evidence/m4-current-performance-condition-review/manifest.json',
]
for path in manifest_paths:
    manifest = json.loads(path.read_text())
    for field in ['inputs', 'files', 'artifacts', 'externalBindings']:
        for row in manifest.get(field, []):
            if not isinstance(row, dict) or 'sha256' not in row:
                continue
            if row.get('snapshot'):
                resolved = ROOT / row['snapshot']
            elif field == 'externalBindings':
                resolved = ROOT / row['path']
            else:
                resolved = path.parent / row['path']
                if not resolved.exists():
                    resolved = ROOT / row['path']
            exact(resolved, row, str(path.relative_to(ROOT)),
                  allow_historical_snapshot=field == 'externalBindings')

archive = json.loads((BASE / 'before-entry-update/manifest.json').read_text())
entry_paths = [ROOT / row['path'] for row in archive['inputs']]
entry_paths += [ROOT / 'docs/m4-ai-simulated-current.md', BASE / 'README.md']
missing_links = []
link_count = 0
for path in entry_paths:
    if path.suffix != '.md':
        continue
    text = path.read_text()
    if '## 当前状态：' in text:
        start = text.index('## 当前状态：')
        end = text.index('## 历史', start + 2)
        text = text[start:end]
    elif '## Current formal checkout:' in text:
        start = text.index('## Current formal checkout:')
        end = text.find('## Historical', start + 2)
        if end == -1:
            end = text.index('Use this reference for figure creation', start)
        text = text[start:end]
    for link in re.findall(r'\]\(([^\s)]+)\)', text):
        if link.startswith(('http:', 'https:', '#', 'codex:')):
            continue
        link_count += 1
        if not (path.parent / link.split('#')[0]).exists():
            missing_links.append({'entry': str(path.relative_to(ROOT)), 'link': link})

gate_path = ROOT / 'docs/evidence/m4-current-gate-audit.json'
gate = json.loads(gate_path.read_text())
for requirement in gate['requirements']:
    for path in requirement['evidence']:
        link_count += 1
        if not (ROOT / path).exists():
            missing_links.append({'entry': requirement['id'], 'link': path})
assert gate['build']['js'] == 'index-B_XHk-wz.js'
assert gate['build']['studioTests'] == receipt['studioTests'] == 347
assert gate['humanParticipants'] == 0 and gate['overall'] == 'partial'
assert gate['m5'] == 'not_started' and gate['aiSimulatedRoles']['count'] == 3
assert gate['currentResearchPackage']['humans'] == 0
assert gate['currentResearchPackage']['assigned'] == gate['currentResearchPackage']['collected'] == 0

passed = all(row['exact'] for row in checks) and not missing_links
report = {
    'schema': 'archcanvas-m4-ai-root-final-readback/1',
    'createdUtc': datetime.now(timezone.utc).isoformat(),
    'status': 'bounded_readback_pass' if passed else 'failed',
    'operator': 'root AI', 'humans': 0, 'm4': 'partial', 'm5': 'not_started',
    'sourceBuildBindings': 103, 'studioTests': 347, 'skipped': 0,
    'focusedTestsAreSubset': True, 'productTestsRerunHere': False,
    'bindingsChecked': len(checks), 'bindingFailures': [r for r in checks if not r['exact']],
    'historicalArchiveResolutions': [r for r in checks if r['historicalArchiveResolution']],
    'currentAndStageLinksChecked': link_count, 'missingLinks': missing_links,
    'entries': [bind(p) for p in entry_paths],
    'frozenEvidenceManifests': [bind(p) for p in manifest_paths],
    'currentChecks': {
        'skillValidation': {'command': 'python /home/fzg/.codex/skills/.system/skill-creator/scripts/quick_validate.py skills/archcanvas',
                            'exitCode': 0, 'observedOutput': 'Skill is valid!',
                            'source': 'root tool output in this continuation'},
        'scopedGitDiffCheck': {'exitCode': 0, 'source': 'root tool output in this continuation'},
        'freshPackageVerify': {'command': '.venv/bin/python scripts/research_trial.py verify --package .archcanvas/m4-research-trial-bxh-current',
                               'exitCode': 0, 'baselineAndImplementationUnchanged': True,
                               'preparationState': 'prepared-no-participants', 'researchGate': 'not_evaluated',
                               'source': 'root tool output after entry update'},
    },
    'preview': {'url': 'http://127.0.0.1:42937/', 'tab': '65', 'markedDeliverable': True,
                'serviceSession': 39008, 'oldAgentTab63Closed': True,
                'userTabs60And61Untouched': True},
    'scope': 'Hash/link/current-gate final readback; repeated bindings are not new tests. '
             'No model execution, extra browser matrix, performance/physical publication/human acceptance; '
             'old failures/packages and snapshots are preserved.',
}
(OUT / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
manifest = {'schema': 'archcanvas-m4-ai-root-final-readback-manifest/1',
            'artifacts': [bind(OUT / 'readback.py'), bind(OUT / 'report.json')],
            'externalBindings': [bind(p) for p in entry_paths + manifest_paths + [receipt_path]],
            'scope': 'Sealed current entries and immutable evidence manifest fingerprints; no human acceptance.'}
(OUT / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({k: report[k] for k in ['status', 'bindingsChecked', 'bindingFailures',
                                       'currentAndStageLinksChecked', 'missingLinks']}, ensure_ascii=False, indent=2))
raise SystemExit(0 if passed else 1)
