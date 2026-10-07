"""Append-only implementation summary for the source owner's finite scope."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import re

ROOT = Path(__file__).resolve().parents[3]
STAGE = ROOT / 'docs/evidence/m4-memory-continuity-current'
WORK = STAGE / 'implementation-work'


def read(relative):
    return json.loads((STAGE / relative).read_text())


def bind(path):
    raw = path.read_bytes()
    return {'path': str(path.relative_to(ROOT)), 'bytes': len(raw),
            'sha256': hashlib.sha256(raw).hexdigest()}


report_path = WORK / 'report.json'
assert not report_path.exists(), 'Never overwrite an implementation report'
receipt = read('checks-final-attempt-2/receipt.json')
matrix = read('production-matrix-attempt-2/report.json')
guards = read('independent-guard-review/summary-final.json')
frontier = read('independent-frontier-review/summary-final.json')
general = read('independent-frontier-review/summary-generalization.json')
adopt = read('independent-adopt-review/summary-final.json')
gap = read('independent-adopt-review/summary-gap.json')
source_seal = read('implementation-work/source-seal-attempt-2/report.json')
studio_log = (STAGE / 'checks-final-attempt-2/studio.txt').read_text()
test_totals = {name: int(re.search(r'^[#ℹ] ' + name + r' (\d+)$', studio_log, re.M)[1])
               for name in ['tests', 'pass', 'fail', 'cancelled', 'skipped', 'todo']}
assert test_totals == {'tests': 436, 'pass': 436, 'fail': 0, 'cancelled': 0, 'skipped': 0, 'todo': 0}
assert receipt['inputsUnchanged'] and receipt['publicationInputsUnchanged']
assert all(c['exitCode'] == 0 for c in receipt['checks'])
assert matrix['passed'] == matrix['relations'] and matrix['inputsUnchanged']
assert source_seal['passed'] == source_seal['relations']
assert adopt['passed'] == adopt['relations']
assert gap['passed'] == gap['relations']
checks = []
for row in receipt['inputs'] + receipt['build'] + receipt['publicationInputs']:
    current = bind(ROOT / row['path'])
    expected = {k: row[k] for k in ['path', 'bytes', 'sha256']}
    checks.append({'path': row['path'], 'passed': current == expected, 'expected': expected, 'actual': current})
assert all(c['passed'] for c in checks)

report = {
    'schema': 'archcanvas-memory-continuity-implementation-final/1',
    'createdUtc': datetime.now(timezone.utc).isoformat(),
    'implementation': {
        'baseline': 'Complete final batch from the current formal algorithm in the same scene. No persisted cache, prototype runtime or previous version is a production fallback.',
        'adoption': 'Late deterministic collapsed-memory Repeat-aware side/midpoint projection. Full fixed batch and earlier adopted peers remain guards; unknown/exhausted/invalid geometry retains the batch.',
        'ports': 'Accepted route and displayed source/target memory coverage change atomically; retained consumers retain geometry; architecture order binds canonical identities. Nonmemory routes never rerun.',
        'detail': 'Compute an original-policy whole scene using current code; compute the complete original-policy detail batch; only then apply late projection. Adopted whole paths do not feed another peer optimizer.',
        'historicalTests': 'Narrow independent midpoint/consumer adaptation first verifies exact protected facts/nonmemory paths/ports against a hash-frozen immediately prior scene. Original gold/oracles untouched.',
        'scope': 'Only collapsed effective cards sharing a nominal vertical band with rounded two six-unit leads and no new nominal body/header/peer stroke contact. Necessary bend is allowed only to repair an incorrect target-side arrival normal; route length does not increase.'
    },
    'sourceSeal': {'report': bind(STAGE / 'implementation-work/source-seal-attempt-2/report.json'),
                   'manifest': bind(STAGE / 'implementation-work/source-seal-attempt-2/manifest.json'),
                   'relations': 450, 'passed': 450, 'current': 129, 'frozen': 166, 'beforeCopiesExact': 144,
                   'inventory': '115Studio source/test/config+3dist+11publication;18precaption historical core+18immediatebefore core+1external detail test fixture. No full transitive environment/fixture inventory claim.'},
    'checks': {'receipt': bind(STAGE / 'checks-final-attempt-2/receipt.json'),
               'studio': test_totals, 'strictTypeScriptAndViteExit': 0,
               'publication': {'tests': 11, 'passed': 11, 'skips': 0, 'exitCode': 0, 'interpreter': str(ROOT / '.venv/bin/python')},
               'currentBindings': len(checks), 'currentBindingPassed': sum(c['passed'] for c in checks), 'currentReadback': checks},
    'productionMatrix': {'report': bind(STAGE / 'production-matrix-attempt-2/report.json'),
                         'rows': matrix['rows'], 'relations': matrix['relations'], 'passed': matrix['passed'],
                         'yRows': matrix['yRows'], 'gapRows': matrix['horizontalGapRows'],
                         'adoptedOccurrences': matrix['adoptedOccurrences'], 'transitionPairs': matrix['transitionPairs'],
                         'thresholdExample': {'beforeLength14To15': [49, 644.3], 'currentLength14To15': [49, 50], 'currentEndpointJumps': [1, 0]},
                         'scope': 'Two signed endpoint sweeps with fractional neighbors x3captions x2presets x2widths x2scopes;9gap neighbors x24combinations; typed undo/redo/JSON reopen. Geometry only, not UI persistence/export files.'},
    'independentGuards': {'summary': bind(STAGE / 'independent-guard-review/summary-final.json'),
                          'literal': guards['reports']['literal-attempt-5'], 'ports': guards['reports']['ports-attempt-3'],
                          'currentBindingRelations': guards['currentBindingRelations'], 'currentBindingPassed': guards['currentBindingPassed']},
    'independentAdopt': {'summary': bind(STAGE / 'independent-adopt-review/summary-final.json'),
                         'evidence': adopt},
    'independentActualGap': {'summary': bind(STAGE / 'independent-adopt-review/summary-gap.json'),
                             'evidence': gap},
    'independentFrontiers': {'summary': bind(STAGE / 'independent-frontier-review/summary-final.json'),
                             'cases': frontier['cases'], 'relations': frontier['relations'], 'passed': frontier['passed'],
                             'statistics': frontier['statistics'], 'scope': 'Nine distinct layer/frontier documents, not9independentmodels.168memory retained incl72expandedendpoint. Zero adoption in this matrix.'},
    'independentOpaqueShared': {'summary': bind(STAGE / 'independent-frontier-review/summary-generalization.json'),
                                'cases': general['cases'], 'relations': general['auditRelations'], 'passed': general['auditPassed'],
                                'sourceAssociationRelations': general['sourceAssociationRelations'], 'sourceAssociationPassed': general['sourceAssociationPassed'],
                                'statistics': general['statistics'], 'scope': '3historically source-grounded models x8presentationcases. Visibleopaque16, sharedcalls8, no memory edges; preservation only.'},
    'actualIssuesFound': [
        'Missing budget own keys could accept geometry: all seven own integer keys required and extra keys rejected; count guards run before simplification.',
        'Mixed detail proxy consumers rebuilt canonicalBindings in insertion order: both rebuilding sites now sort by original architecture order.',
        'Unnecessary no-op straight projection could rebuild public port order: exact original-path proposal is skipped.'
    ],
    'retainedAttempts': [
        {'path': 'implementation-work/initial-suite-attempt-1.txt', 'result': '425/430;5historical label-only geometry assertions incompatible with intended new display geometry.'},
        {'path': 'checks-final-attempt-1/receipt.json', 'result': '423/436;13assertion failures; strictbuild/publication passed. Undefined-key adapter, frozen unique proxy binding representation and no-op/detail order corrected narrowly.'},
        {'path': 'implementation-work/continuity-focused-attempt-1.txt', 'result': 'Wrong cwd failed initial file creation; no test completion claim.'},
        {'path': 'production-matrix-attempt-1/report.json', 'result': '14203/14623;420observer failures: expected undefined whole exportScope became defaulttrue. Actualgeometry checks passed. Original harness SHA-exact reconstructed copy and explicit oracle-correction retained.'},
        {'path': 'implementation-work/source-seal-attempt-1/report.json', 'result': '443/450;7observer failures: git no-index ordinarydifference exit1 with empty diagnostics incorrectly expected0. All bytecopies passed. Original harness and explicit correction retained.'},
        {'path': 'implementation-work/summary-preparation-attempt-1/report.json', 'result': 'Summary parser expected TAP hash-prefix but actual formal Node log uses info-symbol prefix. No summary was written; actual totals unchanged436pass/0fail/skip/cancel/todo. Corrected parser and original harness retained.'},
        {'path': 'independent-guard-review/literal-attempt-1/report.json', 'result': 'Two midpoint rounding oracle errors; original retained; literal independent coordinate corrections appended.'},
        {'path': 'independent-guard-review/ports-attempt-1/report.json', 'result': 'Eight expanded-parent/effective-collapsed-leaf oracle errors; true expandedleaf negative appended.'},
        {'path': 'independent-guard-review/literal-attempt-4/report.json', 'result': 'Seven actual missingbudget guard failures retained; fullbudgetkeys corrected beforefinal.'},
        {'path': 'independent-guard-review/detail-order-counterexample-attempt-1/provenance-correction.json', 'result': 'Actual public binding order issue recorded during source change. captureStableSourceHashVerified=false; never attach old output to new source hash.'},
        {'path': 'independent-guard-review/source-review.md', 'result': 'Ancillary unintended436suite observation truncated/unfrozen, never counted as authoritative checks.'}
    ],
    'unverified': ['This owner did not operate or inspect browser pixels. Root native CUA/export evidence is separate.',
                   'Nominal centerlines/rectangles/strokes do not prove arrowheads, rounded pixels, resolved fonts or physical85/180mm readability.',
                   'Retained old routes may remain blocked/unaesthetic; finite guards do not prove global minimal crossings/bends.',
                   'No new model execution, presentedFPS, latency gate, firstpaint freshness, native save/export fidelity or human task completion is certified here.'],
    'milestones': {'M4': 'partial', 'M5': 'not_started', 'humanParticipants': 0,
                   'automatedReviewersAreHumans': False},
    'prototypeReuse': {'runtimeFallback': False, 'newCertifiedReuseCandidate': False},
}
report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
groups = ['before-change', 'implementation-work', 'checks-final-attempt-1', 'checks-final-attempt-2',
          'independent-guard-review', 'production-matrix-attempt-1', 'production-matrix-attempt-2',
          'independent-frontier-review', 'independent-adopt-review']
files = {p for group in groups for p in (STAGE / group).rglob('*') if p.is_file()}
files.update(STAGE / p for p in ['run_checks.py', 'capture_production_matrix.mjs', 'seal_implementation.py', 'seal_summary.py'])
evidence = [bind(p) for p in sorted(files)]
manifest_path = WORK / 'final-evidence-manifest.json'
assert not manifest_path.exists()
manifest_path.write_text(json.dumps({'schema': 'archcanvas-memory-implementation-evidence-manifest/1',
                                     'scope': 'Source owner implementation, historical copies, independent nominal audits and all retained attempts. Parent browser/export/performance work is outside this manifest.',
                                     'files': evidence}, ensure_ascii=False, indent=2) + '\n')
exact = [bind(ROOT / row['path']) == row for row in evidence]
assert all(exact)
readback = {'schema': 'archcanvas-memory-implementation-final-readback/1', 'rows': len(exact), 'passed': sum(exact),
            'manifest': bind(manifest_path), 'implementationReport': bind(report_path)}
(WORK / 'final-evidence-readback.json').write_text(json.dumps(readback, ensure_ascii=False, indent=2) + '\n')
print(json.dumps(readback, indent=2))
