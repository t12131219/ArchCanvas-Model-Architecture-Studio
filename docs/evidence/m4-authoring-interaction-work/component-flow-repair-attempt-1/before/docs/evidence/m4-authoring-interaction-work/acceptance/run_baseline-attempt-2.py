from pathlib import Path
import datetime
import hashlib
import json
import os
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[4]
ACCEPT = Path(__file__).resolve().parent
OBSERVED = ROOT / 'docs/evidence/m4-authoring-interaction-work/before-implementation-attempt-1/files/studio/src/authoring.ts'
OUT = ACCEPT / 'baseline-attempt-2'
OUT.mkdir()

def binding(p):
    raw = p.read_bytes()
    name = str(p.relative_to(ROOT)) if p.is_relative_to(ROOT) else str(p)
    return {'path': name, 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}

node = Path(shutil.which('node')).resolve()
files = {node, Path(__file__).resolve(), ACCEPT / 'flow-contract.json',
    ACCEPT / 'authoring-flow-independent.test.ts', ACCEPT / 'before-manifest.json',
    ROOT / 'studio/tests/authoring-flow-independent.test.ts'}
for directory in [ACCEPT / 'frozen-before', OBSERVED.parent]:
    files.update(p for p in directory.rglob('*') if p.is_file())
before = [binding(p) for p in sorted(files)]
argv = [str(node), '--experimental-strip-types', '--test', '--test-isolation=none', str(ACCEPT / 'authoring-flow-independent.test.ts')]
env = dict(os.environ)
env['ARCHCANVAS_AUTHORING_FLOW_OBSERVED_MODULE'] = OBSERVED.as_uri()
started = datetime.datetime.now(datetime.timezone.utc).isoformat()
result = subprocess.run(argv, cwd=ROOT, env=env, capture_output=True)
(OUT / 'stdout.txt').write_bytes(result.stdout)
(OUT / 'stderr.txt').write_bytes(result.stderr)
after = [binding(p) for p in sorted(files)]
receipt = {'protocol': 'archcanvas-authored-flow-independent-baseline/1',
    'startedAt': started, 'finishedAt': datetime.datetime.now(datetime.timezone.utc).isoformat(),
    'argv': argv, 'cwd': str(ROOT), 'observedModule': str(OBSERVED.relative_to(ROOT)),
    'observedModuleExpectedSource': 'Frozen formal implementation before this stage; product observations do not create expected values.',
    'envOverride': {'ARCHCANVAS_AUTHORING_FLOW_OBSERVED_MODULE': OBSERVED.as_uri()},
    'exitCode': result.returncode, 'inputsBefore': before, 'inputsAfter': after,
    'inputBytesUnchanged': before == after, 'stdout': binding(OUT / 'stdout.txt'), 'stderr': binding(OUT / 'stderr.txt'),
    'productEditedByAuditor': False, 'fullSuiteOrBuildRun': False, 'modelsExecuted': False, 'humanParticipants': 0}
(OUT / 'receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
print(json.dumps({'exitCode': result.returncode, 'inputBytesUnchanged': before == after,
                  'inputBindings': len(before), 'output': result.stdout.decode()[-1200:]}))
