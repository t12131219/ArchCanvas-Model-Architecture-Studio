from pathlib import Path
from datetime import datetime, timezone
import difflib
import hashlib
import json
import re

ROOT = Path(__file__).resolve().parents[5]
OUT = Path(__file__).resolve().parent
WORK = ROOT / 'docs/evidence/m4-authoring-interaction-work'
BASE = WORK / 'before-implementation-attempt-1/files'
ACCEPT = WORK / 'acceptance'


def binding(path):
    data = path.read_bytes()
    return {'path': str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path),
            'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}


def output(name, data):
    target = OUT / name
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open('xb') as stream:
        stream.write(data if isinstance(data, bytes) else data.encode())
    return binding(target)


def segment(text, name):
    # Stable pre-existing export spans are compared as source bytes, not executed.
    start = text.index('export function ' + name + '(')
    end = text.find('\nexport function ', start + 1)
    return text[start:end if end >= 0 else None].strip()


subject_paths = ['studio/src/authoring.ts', 'studio/src/AuthoringStudio.tsx',
                 'studio/src/AuthoringStudio.css', 'studio/src/draftPortPresentation.ts',
                 'studio/src/core/scene.ts']
schema_paths = ['schemas/authored-draft.schema.json', 'schemas/architecture.schema.json',
                'schemas/canvas-document.schema.json', 'studio/src/core/orthogonalRouter.ts']
receipts = [ACCEPT / name / 'receipt.json' for name in
            ['baseline-attempt-2', 'component-baseline-attempt-1', 'current-target-attempt-3']]
original_ten = ACCEPT / 'hit-contract-extension-attempt-1/test.before.ts'
current_test = ACCEPT / 'authoring-flow-independent.test.ts'
source_inputs = [ROOT / path for path in subject_paths + schema_paths]
source_inputs += [BASE / path for path in subject_paths + schema_paths if (BASE / path).exists()]
source_inputs += receipts + [original_ten, current_test, ACCEPT / 'flow-contract.json',
                            WORK / 'before-implementation-attempt-1/manifest.json',
                            ACCEPT / 'global-flow-before-repair-attempt-1/manifest.json',
                            ROOT / 'studio/tests/authoring-flow-independent.test.ts', Path(__file__)]
before_bindings = [binding(path) for path in source_inputs]
snapshots = [output('current/' + path, (ROOT / path).read_bytes()) for path in subject_paths]
diffs = []
for path in subject_paths:
    previous = (BASE / path).read_text() if (BASE / path).exists() else ''
    current = (ROOT / path).read_text()
    diffs.append(output('diffs/' + Path(path).name + '.diff', ''.join(difflib.unified_diff(
        previous.splitlines(keepends=True), current.splitlines(keepends=True),
        fromfile='frozen-before/' + path, tofile='current/' + path))))

old_authoring = (BASE / 'studio/src/authoring.ts').read_text()
current_authoring = (ROOT / 'studio/src/authoring.ts').read_text()
unchanged_exports = []
for name in ['parseDraftCache', 'nextDraftPosition', 'blankDraft', 'draftHistory', 'changeDraft',
             'travelDraft', 'addDraftNode', 'removeDraftNode', 'connectDraft', 'arrangeDraft']:
    old = segment(old_authoring, name)
    new = segment(current_authoring, name)
    unchanged_exports.append({'export': name, 'sourceBytesEqual': old == new,
                              'frozenSpanSha256': hashlib.sha256(old.encode()).hexdigest(),
                              'currentSpanSha256': hashlib.sha256(new.encode()).hexdigest()})
type_end = 'export type DraftFlow'
old_types = old_authoring[:old_authoring.index('export function parseDraftCache')].rstrip()
# The new explanatory comment is outside the old declarations.
old_types = old_types[:old_types.index('export function')] if 'export function' in old_types else old_types
new_types = current_authoring[:current_authoring.index(type_end)].rstrip()
unchanged_files = [{'path': path, 'sourceBytesEqual': (BASE / path).read_bytes() == (ROOT / path).read_bytes(),
                    'frozen': binding(BASE / path), 'current': binding(ROOT / path)} for path in schema_paths]
receipt_audit = []
for path in receipts:
    receipt = json.loads(path.read_text())
    inputs = receipt['inputsAfter']
    readback = []
    for item in inputs:
        target = Path(item['path'])
        if not target.is_absolute():
            target = ROOT / target
        actual = binding(target)
        readback.append({'recorded': item, 'actual': actual,
                         'matches': item['bytes'] == actual['bytes'] and item['sha256'] == actual['sha256']})
    stdout_path = ROOT / receipt['stdout']['path']
    stderr_path = ROOT / receipt['stderr']['path']
    stdout = stdout_path.read_text()
    stdout_match = binding(stdout_path)['sha256'] == receipt['stdout']['sha256']
    stderr_match = binding(stderr_path)['sha256'] == receipt['stderr']['sha256']
    # Earlier attempts intentionally bind the previous test version. Their immutable input
    # copies are retained, so their current mutable-test mismatch is explicitly reported.
    counts = {key: int(re.search(r'^. ' + key + r' (\d+)$', stdout, re.MULTILINE).group(1))
              for key in ['tests', 'pass', 'fail']}
    receipt_audit.append({'receipt': binding(path), 'exitCode': receipt['exitCode'], 'counts': counts,
                          'reportedUnchangedDuringRun': receipt['inputBytesUnchanged'],
                          'stdout': binding(stdout_path), 'stderr': binding(stderr_path),
                          'stdoutMatches': stdout_match, 'stderrMatches': stderr_match,
                          'currentReadback': readback, 'currentReadbackMismatchCount': sum(not item['matches'] for item in readback)})
original_prefix_equal = current_test.read_bytes().startswith(original_ten.read_bytes())
after_bindings = [binding(path) for path in source_inputs]
checks = {
    'tenOriginalCasesByteExactPrefix': original_prefix_equal,
    'preexistingDraftDeclarationsUnchanged': old_types == new_types,
    'tenPreexistingExportSpansUnchanged': all(item['sourceBytesEqual'] for item in unchanged_exports),
    'schemasAndSharedRouterUnchanged': all(item['sourceBytesEqual'] for item in unchanged_files),
    'finalTarget11Pass0Fail': receipt_audit[-1]['counts'] == {'tests': 11, 'pass': 11, 'fail': 0},
    'finalTargetInputsExactAtReview': receipt_audit[-1]['currentReadbackMismatchCount'] == 0,
    'receiptOutputsExact': all(item['stdoutMatches'] and item['stderrMatches'] for item in receipt_audit),
    'reviewInputsUnchanged': before_bindings == after_bindings,
}
report = {
    'protocol': 'archcanvas-authored-flow-independent-source-review/1',
    'reviewedAt': datetime.now(timezone.utc).isoformat(),
    'checks': checks, 'pass': all(checks.values()), 'inputsBefore': before_bindings,
    'inputsAfter': after_bindings, 'snapshots': snapshots, 'diffs': diffs,
    'unchangedExports': unchanged_exports, 'unchangedFiles': unchanged_files,
    'testReceiptAudit': receipt_audit,
    'reviewFindings': [
        {'finding': 'Draft projection uses one weak-component flow map for requests, public circles and pending source endpoint. Overall draft flow is informational.',
         'files': ['studio/src/authoring.ts', 'studio/src/AuthoringStudio.tsx']},
        {'finding': 'Aligned unobstructed paths have direct preferred segments; offset, obstructed and reverse cases remain subject to the same unchanged shared router.',
         'files': ['studio/src/authoring.ts', 'studio/src/core/orthogonalRouter.ts']},
        {'finding': 'Transparent hit rect and text belong to the same public endpoint group; pointer handlers still resolve closest endpoint identity. Dot CSS uses a stable class after hit-rect addition.',
         'files': ['studio/src/AuthoringStudio.tsx', 'studio/src/AuthoringStudio.css']},
        {'finding': 'Enter and Space select an output or connect an input, subject to busy/pan guards. Active source uses aria-pressed and a visible dot style.',
         'files': ['studio/src/AuthoringStudio.tsx', 'studio/src/AuthoringStudio.css']},
    ],
    'nativeEvidenceStillRequired': [
        'Rendered saved four-node path/public-circle/pending endpoint coordinates against literal frozen expectations.',
        'Actual font text bbox and group center/label/circle clicks; helper width estimates are not browser click evidence.',
        'No-edge side ports becoming component top/bottom ports after the first connection.',
        'Distinct Add/Concat input identity, duplicate producer rejection without added history, keyboard connection and Escape cancellation.',
        'Four directional pointer/camera actions, undo/redo and saved/reopened byte bindings where native observations are supplied.',
    ],
    'limits': [
        'Direction may change within a component when its topology or major arrangement changes; separate components are protected by case 11.',
        'Isolated unconnected nodes retain horizontal side ports.',
        'Peer clipping and deterministic text width do not certify every long label or browser font.',
        'These tests do not certify arbitrary dense-graph global optimality or publication aesthetics.',
        'Source-review binds the final current pure-contract target; old baseline readbacks can differ at mutable product/test paths and are reported without rewriting earlier receipts.',
    ],
    'testsRunByThisReview': False, 'fullSuiteOrBuildRun': False, 'modelsExecuted': False,
    'productEditedByAuditor': False, 'humanParticipants': 0, 'M4': 'partial', 'M5': 'not-started',
}
target = OUT / 'report.json'
output('report.json', json.dumps(report, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({'report': binding(target), 'checks': checks,
                  'baselineCounts': [item['counts'] for item in receipt_audit],
                  'receiptCurrentMismatchCounts': [item['currentReadbackMismatchCount'] for item in receipt_audit]}, ensure_ascii=False))
