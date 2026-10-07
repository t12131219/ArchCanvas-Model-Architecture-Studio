"""Replay existing raw facts with the corrected checker; never modify old evidence."""
from pathlib import Path
import hashlib
import json
import subprocess
import sys

STAGE = Path(__file__).resolve().parent
ROOT = STAGE.parents[2]
OLD = ROOT / 'docs/evidence/m4-readable-grid-browser-next/continuous-browser'


def read(path):
    return json.loads(path.read_text())


def binding(path):
    data = path.read_bytes()
    return {'path': str(path.relative_to(ROOT)), 'bytes': len(data),
            'sha256': hashlib.sha256(data).hexdigest()}


out = STAGE / (sys.argv[1] if len(sys.argv) > 1 else 'replay-attempt-1')
out.mkdir(exist_ok=False)
raw_path = OLD / '01-seven-attempts-full.raw.json'
old_report = OLD / 'independent-readback-attempt-2/report.json'
old_validator = OLD / 'independent-readback-attempt-2/validator.stdout.json'
expected_path = STAGE / 'before-change/expected-proxies.json'
receipt_path = ROOT / 'docs/evidence/m4-memory-continuity-current/checks-final-attempt-2/receipt.json'
script = ROOT / 'scripts/validate_continuous_observation.mjs'
input_paths = [raw_path, old_report, old_validator, expected_path, receipt_path,
               STAGE / 'before-change/manifest.json', script,
               ROOT / 'scripts/validate_input_observation.mjs']
inputs_before = [binding(p) for p in input_paths]
process = subprocess.run(['node', str(script), str(raw_path)], cwd=ROOT, capture_output=True, text=True)
(out / 'validator.stdout.json').write_text(process.stdout)
(out / 'validator.stderr.log').write_text(process.stderr)
relations = []


def check(name, passed, detail=None):
    relations.append({'relation': name, 'passed': bool(passed), 'detail': detail})


check('corrected-wrapper-exit0', process.returncode == 0)
if process.returncode != 0:
    (out / 'process.json').write_text(json.dumps({'exitCode': process.returncode}, indent=2))
    raise SystemExit(process.returncode)
new = json.loads(process.stdout)
old = read(old_validator)
expect = read(expected_path)
raw = read(raw_path)
current = new['base']
prior = old['base']
check('definition-and-nonpaint-scope', new['continuousProxyDefinition'] == 'same-declared-ids-dom-state/1'
      and new['presentedFps'] is None and new['continuousInputToPaintMs'] is None
      and not new['performanceGatePassed'] and not current['humanCertified'])
check('discrete-matching-unchanged', current['latency'] == prior['latency'])
for key in ['frameCadence', 'idleCadence', 'observerSelfCost', 'errors', 'completeBuffers', 'dropped']:
    check(key + '-unchanged', current[key] == prior[key])
check('received-ledger-and-boundary-coverage-unchanged', new['inputDenominator'] == old['inputDenominator']
      and new['viewportCoverage'] == old['viewportCoverage'])
check('capture-and-drain-duration-unchanged', new['captureDurationMs'] == old['captureDurationMs']
      and new['drainDurationMs'] == old['drainDurationMs'])
summary = current['continuousInputSummary']
check('continuous-retained33-assigned17-outside16',
      (summary['retainedTrustedContinuousInputs'], summary['assignedEligibleInputs'],
       summary['retainedOutsideTrialInputs'], summary['measuredInputs'], summary['unmeasuredInputs']) == (33, 17, 16, 17, 0))
rows = []
for group in expect['groups']:
    trial = next(t for t in current['trials'] if t['id'] == group['trial'])
    actual_ids = [p['inputId'] for p in trial['continuousProxies']]
    check(group['trial'] + '-independent-input-set-exact', actual_ids == [p['inputId'] for p in group['rows']])
    for expected in group['rows']:
        actual = next(p for p in trial['continuousProxies'] if p['inputId'] == expected['inputId'])
        exact = actual['inputToObservedChangeProxyMs'] == expected['firstChangeProxyMs']
        rows.append({'trial': group['trial'], 'inputId': expected['inputId'], 'exact': exact,
                     'actualMs': actual['inputToObservedChangeProxyMs'], 'expectedMs': expected['firstChangeProxyMs'],
                     'oldMs': expected['claimedFirstChangeProxyMs']})
    check(group['trial'] + '-independent-per-input-values-exact', all(p['exact'] for p in rows if p['trial'] == group['trial']))
    check(group['trial'] + '-independent-p95-exact', trial['continuousCoverage']['measuredSubsetP95Ms'] == group['proxyP95Ms'])
for trial, previous in zip(current['trials'], prior['trials'], strict=True):
    retained = {k: v for k, v in trial.items() if not k.startswith('continuous')}
    prior_retained = {k: v for k, v in previous.items() if not k.startswith('continuous')}
    check(trial['id'] + '-operation-and-full-boundary-diagnostics-unchanged', retained == prior_retained)
check('no-input-requested-drag-remains-failed', current['trials'][1] == prior['trials'][1]
      and not current['trials'][1]['operationSucceeded'])
check('old26of29-failures-preserved', (read(old_report)['passedGroups'], read(old_report)['failedGroups']) == (26, 3))
before = read(STAGE / 'before-change/manifest.json')
historical_exact = []
for item in before['bindings']:
    path = ROOT / item.get('snapshot', item['path'])
    got = binding(path)
    historical_exact.append(got['bytes'] == item['bytes'] and got['sha256'] == item['sha256'])
check('six-historical-inputs-or-original-snapshots-exact', all(historical_exact), len(historical_exact))
receipt = read(receipt_path)
product = receipt['inputs'] + receipt['build'] + receipt['publicationInputs']
product_failures = [p['path'] for p in product if any(
    binding(ROOT / p['path'])[k] != p[k] for k in ['bytes', 'sha256'])]
check('129-finite-product-bindings-unchanged', len(product) == 129 and not product_failures, product_failures)
check('eight-replay-inputs-unchanged-through-readback', inputs_before == [binding(p) for p in input_paths])
report = {'schema': 'archcanvas-corrected-continuous-replay/1', 'relationships': relations,
          'passedRelations': sum(r['passed'] for r in relations), 'totalRelations': len(relations),
          'failures': [r for r in relations if not r['passed']], 'independentPerInputRows': rows,
          'exactIndependentRows': sum(p['exact'] for p in rows), 'inputBindings': inputs_before,
          'summary': summary, 'productChanged': False, 'browserRerun': False, 'modelExecuted': False,
          'humanParticipants': 0, 'performanceGatePassed': False,
          'scope': 'New derived replay only. Whole-boundary/canonical correctness belongs to the retained old audit; these relations do not make its old 26/29 report green or certify current browser paint/readability.'}
(out / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({'passed': report['passedRelations'], 'total': report['totalRelations'],
                  'exactPerInput': report['exactIndependentRows'], 'failures': report['failures']}, indent=2))
raise SystemExit(0 if all(r['passed'] for r in relations) else 1)
