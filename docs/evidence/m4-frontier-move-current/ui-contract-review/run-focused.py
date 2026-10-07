"""Record the bounded independent command/App-callback tests without a full build."""
from pathlib import Path
import hashlib
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone

OWNER=Path(__file__).resolve().parent
ROOT=OWNER.parents[3]
OUT=OWNER/(sys.argv[1] if len(sys.argv)>1 else 'focused-attempt-1')
if OUT.exists():raise SystemExit('Do not overwrite evidence')
OUT.mkdir()
def bind(p):
    p=Path(p)
    if not p.is_absolute():p=ROOT/p
    data=p.read_bytes()
    return {'path':str(p.relative_to(ROOT)),'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}
inputs=sorted([*ROOT.joinpath('studio/src/core').glob('*.ts'),ROOT/'studio/src/App.tsx',ROOT/'studio/src/moveCommand.ts',
               ROOT/'studio/tests/move-command-independent.test.ts',ROOT/'studio/package.json',
               ROOT/'studio/node_modules/typescript/package.json',ROOT/'studio/node_modules/typescript/lib/typescript.js',
               Path(__file__).resolve()])
before=[bind(p) for p in inputs]
command=['node','--experimental-strip-types','--test','--test-isolation=none','tests/move-command-independent.test.ts']
started=datetime.now(timezone.utc).isoformat()
result=subprocess.run(command,cwd=ROOT/'studio',capture_output=True,text=True)
(OUT/'stdout.txt').write_text(result.stdout)
(OUT/'stderr.txt').write_text(result.stderr)
after=[bind(p) for p in inputs]
node=shutil.which('node')
receipt={'schema':'archcanvas-frontier-ui-command-independent-focused/1','startedUtc':started,
         'endedUtc':datetime.now(timezone.utc).isoformat(),'command':command,'cwd':str(ROOT/'studio'),
         'nodeExecutable':node,'nodeResolved':str(Path(node).resolve()) if node else None,
         'exitCode':result.returncode,'inputBindings':before,'inputAfter':after,'inputsUnchanged':before==after,
         'stdout':bind(OUT/'stdout.txt'),'stderr':bind(OUT/'stderr.txt'),
         'scope':'Hand-authored literal parser results and real App AST-extracted callbacks in a controlled state/rAF/viewport/capture harness, plus actual core cache/anchor relations. React is not mounted and browser paint/native event freshness is not certified. Distances are world canvas units. Focused only; root runs final full suite/build separately.',
         'humanParticipants':0,'modelExecuted':False,'semanticWriteback':False,'browserManipulated':False,
         'M4':'partial','M5':'not_started'}
(OUT/'receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
print(result.stdout)
if result.stderr:print(result.stderr,file=sys.stderr)
print(json.dumps({'exitCode':result.returncode,'bindings':len(before),'inputsUnchanged':before==after}))
raise SystemExit(result.returncode or (0 if before==after else 1))
