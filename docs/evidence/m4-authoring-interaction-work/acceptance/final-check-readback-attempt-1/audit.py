from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import re

ROOT = Path(__file__).resolve().parents[5]
OUT = Path(__file__).resolve().parent
CHECKS = ROOT / 'docs/evidence/m4-authoring-interaction-work/checks'


def binding(path):
    data = path.read_bytes()
    return {'path': str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path),
            'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}


def resolve(item):
    path = Path(item['path'])
    return path if path.is_absolute() else ROOT / path


cache = {}
paths = {Path(__file__)}
receipt_data = []
for name in ['target-attempt-2', 'suite-attempt-2', 'build-attempt-2']:
    path = CHECKS / name / 'receipt.json'
    receipt = json.loads(path.read_text())
    receipt_data.append((path, receipt))
    paths.add(path)
    for category in ['inputsBefore', 'inputsAfter', 'infrastructure', 'logs', 'builtFiles']:
        paths.update(resolve(item) for item in receipt.get(category, []))
before = [binding(path) for path in sorted(paths)]
cache = {item['path']: item for item in before}
audits = []
for path, receipt in receipt_data:
    readbacks = {}
    for category in ['inputsBefore', 'inputsAfter', 'infrastructure', 'logs', 'builtFiles']:
        values = []
        for item in receipt.get(category, []):
            current = cache[binding(resolve(item))['path']]
            values.append({'recorded': item, 'current': current,
                           'matches': item['bytes'] == current['bytes'] and item['sha256'] == current['sha256']})
        readbacks[category] = values
    stdout = (path.parent / 'stdout.txt').read_text()
    counts = {key: int(re.search(r'^. ' + key + r' (\d+)$', stdout, re.MULTILINE).group(1))
              for key in ['tests', 'pass', 'fail']} if receipt['kind'] != 'build' else None
    audits.append({'receipt': binding(path), 'kind': receipt['kind'], 'argv': receipt['argv'],
                   'exitCode': receipt['exitCode'], 'sourceBeforeAfterExact': receipt['sourceBeforeAfterExact'],
                   'counts': counts, 'readbacks': readbacks,
                   'allRecordedInputsExact': all(value['matches'] for values in readbacks.values() for value in values),
                   'reportedDependenciesInstalled': receipt['dependenciesInstalled'],
                   'reportedModelsExecuted': receipt['modelsExecuted']})
after = [binding(path) for path in sorted(paths)]
checks = {'allThreeReceiptsSuccessful': all(item['exitCode'] == 0 and item['sourceBeforeAfterExact'] for item in audits),
          'allRecordedSourceInfrastructureLogsAndBuildExact': all(item['allRecordedInputsExact'] for item in audits),
          'target28Pass': audits[0]['counts'] == {'tests': 28, 'pass': 28, 'fail': 0},
          'suite264Pass': audits[1]['counts'] == {'tests': 264, 'pass': 264, 'fail': 0},
          'reportedNoInstallOrModelExecution': all(not item['reportedDependenciesInstalled'] and not item['reportedModelsExecuted'] for item in audits),
          'inputsUnchangedDuringReadback': before == after}
report = {'protocol': 'archcanvas-authoring-interaction-independent-final-check-readback/1',
          'reviewedAt': datetime.now(timezone.utc).isoformat(), 'checks': checks, 'pass': all(checks.values()),
          'inputsBefore': before, 'inputsAfter': after, 'receipts': audits,
          'builtFiles': receipt_data[2][1]['builtFiles'],
          'limits': ['This independently reads already-run receipt logs and byte bindings. It does not rerun the tests/build or independently establish browser-loaded bytes.',
                     'Later review/evidence files outside each recorded input inventory do not alter the byte identity of the recorded implementation inputs.'],
          'testsOrBuildRunByAuditor': False, 'modelsExecutedByAuditor': False,
          'productEditedByAuditor': False, 'humanParticipants': 0, 'M4': 'partial', 'M5': 'not-started'}
target = OUT / 'report.json'
with target.open('x') as stream:
    json.dump(report, stream, ensure_ascii=False, indent=2)
    stream.write('\n')
print(json.dumps({'report': binding(target), 'checks': checks, 'distinctInputCount': len(before)}, ensure_ascii=False))
