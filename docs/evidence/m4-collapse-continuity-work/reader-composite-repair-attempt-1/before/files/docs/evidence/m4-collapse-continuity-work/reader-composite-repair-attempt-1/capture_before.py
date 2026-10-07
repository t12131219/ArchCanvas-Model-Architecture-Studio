"""Freeze critical Bf source/build/check/witness bytes before bounded reader fix."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
WORK=HERE.parent
files=[Path(__file__).resolve(),ROOT/'studio/src/core/document.ts',ROOT/'studio/src/core/scene.ts',ROOT/'studio/src/core/types.ts',ROOT/'studio/src/core/validate.ts',ROOT/'studio/src/core/index.ts']
files += [p for p in (ROOT/'studio/dist').rglob('*') if p.is_file()]
files += [p for p in (WORK/'checks').rglob('*') if p.is_file()]
files += [p for p in (WORK/'acceptance/final-check-audit-attempt-1').glob('legacy-composite-ambiguity*') if p.is_file()]
files=sorted(set(files))
def binding(path):
 b=path.read_bytes();return {'path':str(path.relative_to(ROOT)),'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}
before=[binding(p) for p in files]
folder=HERE/'before';folder.mkdir(exist_ok=False)
for p in files:
 target=folder/'files'/p.relative_to(ROOT);target.parent.mkdir(parents=True,exist_ok=True)
 with target.open('xb') as f:f.write(p.read_bytes())
after=[binding(p) for p in files]
report={'protocol':'archcanvas-composite-legacy-reader-critical-before/1','createdUtc':datetime.now(timezone.utc).isoformat(),'scope':'Only critical currentdocument/core/Bfbuild/oldrootchecks and independentcompositewitness, no giantrepo/archivecopy.','fileCount':len(files),'inputBindingsBefore':before,'inputBindingsAfter':after,'inputsUnchanged':before==after,'copiesExact':all(hashlib.sha256((folder/'files'/p.relative_to(ROOT)).read_bytes()).hexdigest()==before[i]['sha256'] for i,p in enumerate(files)),'productEdited':False,'modelExecuted':False,'testsOrBuildRun':False}
with (folder/'manifest.json').open('x') as f:json.dump(report,f,ensure_ascii=False,indent=2);f.write('\n')
print(json.dumps({'manifest':binding(folder/'manifest.json'),'files':len(files),'inputsUnchanged':before==after}));assert before==after
