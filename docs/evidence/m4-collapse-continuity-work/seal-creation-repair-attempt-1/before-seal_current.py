"""Validate documentation, retain the actual validator result, and bind this scope."""
from pathlib import Path
from datetime import datetime, timezone
from urllib.parse import unquote
import hashlib
import json
import re
import subprocess

ROOT = Path(__file__).resolve().parents[3]
WORK = Path(__file__).resolve().parent
SEAL = ROOT / 'docs/evidence/m4-collapse-continuity-verification-sealed.json'
OUT = WORK / 'doc-validation-attempt-1'
DOCS = [
    'README.md', 'docs/m4-completion.md', 'docs/m4-exit-audit.md',
    'docs/m4-ai-usability-audit.md', 'docs/m4-human-review-handoff.md',
    'docs/m4-performance.md', 'docs/m4-authoring.md', 'docs/acceptance.md',
    'docs/capability-matrix.md', 'docs/evidence/README.md',
    'skills/archcanvas/SKILL.md', 'skills/archcanvas/references/formal-alpha.md',
    'skills/archcanvas/references/runtime-compatibility.md',
    'docs/m4-collapse-continuity.md',
    'docs/evidence/m4-collapse-continuity-work/README.md',
]

def now(): return datetime.now(timezone.utc).isoformat()
def binding(path):
    path = Path(path)
    data = path.read_bytes()
    return {'path': path.relative_to(ROOT).as_posix(), 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}
def dump(path, value): path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')

assert not SEAL.exists()
OUT.mkdir(exist_ok=False)
before = [binding(ROOT / p) for p in DOCS]
links = []
for path in DOCS:
    for match in re.finditer(r'\[[^\]\n]*\]\((<[^>]+>|[^\s)]+)(?:\s+"[^"]*")?\)', (ROOT / path).read_text()):
        raw = match.group(1).strip('<>')
        target = unquote(raw.split('#', 1)[0])
        if not target or re.match(r'^[a-zA-Z][a-zA-Z0-9+.-]*:', target): continue
        resolved = Path(target) if target.startswith('/') else (ROOT / path).parent / target
        links.append({'document': path, 'target': raw, 'exists': resolved.exists()})

# Preserve the prior tool-observed failure, without re-running it or pretending
# this reconstructed note is an original redirected process log.
dump(OUT / 'venv-validator-failure-tool-transcription.json', {
    'provenance': 'Root transcription of the preceding exec_command result; not a redirected process log',
    'argv': ['.venv/bin/python', '/home/fzg/.codex/skills/.system/skill-creator/scripts/quick_validate.py', 'skills/archcanvas'],
    'exitCode': 1, 'reason': "ModuleNotFoundError: No module named 'yaml'",
    'dependenciesInstalled': False,
})
validator = Path('/home/fzg/.codex/skills/.system/skill-creator/scripts/quick_validate.py')
(OUT / 'quick_validate.py').write_bytes(validator.read_bytes())
argv = ['/home/fzg/anaconda3/bin/python', str(validator), 'skills/archcanvas']
started = now()
run = subprocess.run(argv, cwd=ROOT, capture_output=True, check=False)
(OUT / 'skill.stdout.txt').write_bytes(run.stdout)
(OUT / 'skill.stderr.txt').write_bytes(run.stderr)
old_seal = ROOT / 'docs/evidence/m4-monochrome-role-verification-sealed.json'
old = json.loads(old_seal.read_text())
old_mismatches = []
for expected in old['records']:
    actual = binding(ROOT / expected['path'])
    if actual != expected: old_mismatches.append({'expected': expected, 'actual': actual})
status_path = ROOT / 'docs/evidence/m4-human-review-handoff-status.json'
status = json.loads(status_path.read_text())
refs = []
for expected in status['evidenceRefs']:
    actual = binding(ROOT / expected['path'])
    refs.append({'expected': expected, 'actual': actual, 'exact': actual == expected})
after = [binding(ROOT / p) for p in DOCS]
receipt = {
    'protocol': 'm4-current-doc-links-skill-and-historical-seal-readback/1',
    'startedAt': started, 'finishedAt': now(), 'documents': before,
    'documentsAfter': after, 'documentInputsUnchanged': before == after,
    'inlineLocalLinks': links, 'localLinksCount': len(links),
    'missingLocalLinks': [item for item in links if not item['exists']],
    'skillValidator': {'argv': argv, 'exitCode': run.returncode, 'stdout': binding(OUT / 'skill.stdout.txt'), 'stderr': binding(OUT / 'skill.stderr.txt'), 'sourceCopy': binding(OUT / 'quick_validate.py'), 'scope': 'Existing system Python/PyYAML used only for instruction-package validation; not the formal model/runtime interpreter'},
    'oldRoleSeal': binding(old_seal), 'oldRoleBindingsRead': len(old['records']),
    'oldRoleMismatches': old_mismatches, 'statusEvidenceRefs': refs,
    'humanParticipants': 0, 'modelsExecuted': False, 'dependenciesInstalled': False,
    'productTestsRerun': False, 'M4': 'partial', 'M5': 'not_started',
}
dump(OUT / 'receipt.json', receipt)
assert run.returncode == 0, 'Skill validation failed; original stdout/stderr retained'
assert not receipt['missingLocalLinks']
assert not old_mismatches
assert before == after
assert all(item['exact'] for item in refs)

paths = set()
tree_roots = [
    'src', 'tests', 'schemas', 'fixtures', 'scripts', 'skills/archcanvas',
    'studio/src', 'studio/tests', 'studio/dist',
    'docs/evidence/m4-collapse-continuity-work',
    'docs/evidence/m4-performance-controls-work',
    'docs/evidence/m4-monochrome-width-pixel-supplement-attempt-1',
]
for root in tree_roots:
    for path in (ROOT / root).rglob('*'):
        if path.is_file() and '__pycache__' not in path.parts and path.suffix != '.pyc': paths.add(path)
for path in DOCS + [
    'AGENTS.md', 'pyproject.toml', 'requirements.lock', 'requirements-runtime.lock',
    'studio/package.json', 'studio/package-lock.json', 'studio/tsconfig.json',
    'studio/vite.config.ts', 'studio/index.html',
    'docs/evidence/m4-human-review-handoff-status.json',
    'docs/m4-monochrome-role.md',
    'docs/evidence/m4-monochrome-role-verification-sealed.json',
]: paths.add(ROOT / path)

# Bind the actual final native/source/draft store inputs declared by the auditors.
for receipt_path, key in [
    ('authoring-independent-audit/attempt-3/receipt.json', 'inputBindingsBefore'),
    ('acceptance/final-native-audit-attempt-4/report.json', 'inputsBefore'),
]:
    audit = json.loads((WORK / receipt_path).read_text())
    for rec in audit[key]:
        path = Path(rec['path'])
        resolved = path if path.is_absolute() else ROOT / path
        assert resolved.is_file(), rec['path']
        assert resolved.is_relative_to(ROOT), rec['path']
        actual = binding(resolved)
        assert actual['bytes'] == rec['bytes'] and actual['sha256'] == rec['sha256'], rec['path']
        paths.add(resolved)
records = [binding(path) for path in sorted(paths)]
again = [binding(path) for path in sorted(paths)]
assert records == again
seal = {
    'schemaVersion': 1, 'protocol': 'm4-collapse-continuity-bounded-verification-seal/1',
    'createdAt': now(), 'status': 'bounded-current-artifact-contract-and-ai-pixel-pass-with-open-gates',
    'scope': 'Current BK collapse continuity, native CNN movement/history/save/export, bounded authoring actual artifacts and AI pixels, docs/Skill. Retention bindings include historical failures/tools; a binding alone does not certify every claim inside that file.',
    'milestones': {'M4': 'partial', 'M5': 'not_started', 'humans': 0},
    'currentBuild': status['productionBuild'], 'currentJsSha256': status['productionJsSha256'],
    'records': records, 'boundFileCount': len(records), 'allSelectedBytesBeforeAfterExact': records == again,
    'selectedTrees': tree_roots, 'documentationReceipt': binding(OUT / 'receipt.json'),
    'sourceDirection': status['implementationDirection'], 'checks': status['tests'],
    'native': status['collapseContinuity'], 'authoring': status['authoring'],
    'independentAiRoles': status['aiReview'],
    'priorRoleSeal': binding(old_seal), 'priorRoleBindingsReadExact': len(old['records']),
    'historicalPerformanceControlScope': status['performance'], 'widthSupplementScope': status['widthOverride'],
    'preservedFailures': status['preservedFailures'], 'openItems': status['openItems'],
    'noClaims': ['human acceptance', 'global route aesthetics or shortest paths', 'new full39 matrix', 'actual85/180mm physical publication review', 'presented FPS or current Studio A/B performance', 'expansion screen-anchor invariance', 'new full standalone release', 'per-module authoring execution or training'],
    'modelExecution': False, 'dependenciesInstalled': False, 'oldRoleEvidenceModified': False,
    'independentFinalReadback': 'pending; independent auditor records a separate receipt without mutating this seal',
}
dump(SEAL, seal)
print(json.dumps({'seal': binding(SEAL), 'boundFileCount': len(records), 'localLinks': len(links), 'skillValidationExit': run.returncode, 'oldRoleBindingsExact': len(old['records'])}, ensure_ascii=False))
