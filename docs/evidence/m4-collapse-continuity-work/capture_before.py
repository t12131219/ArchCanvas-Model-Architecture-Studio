"""Exclusive source/testing/build snapshot before the continuity implementation."""
from __future__ import annotations
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]

def binding(path:Path)->dict:
    body=path.read_bytes()
    return {'path':str(path.relative_to(ROOT)),'bytes':len(body),'sha256':hashlib.sha256(body).hexdigest()}

def main()->None:
    destination=HERE/'before-implementation-attempt-1'
    destination.mkdir(exist_ok=False)
    files=[]
    for folder in ['src','studio/src','studio/tests','studio/dist']:
        files.extend(path for path in (ROOT/folder).rglob('*') if path.is_file() and '__pycache__' not in path.parts and path.suffix not in ['.pyc','.pyo'])
    for name in ['AGENTS.md','pyproject.toml','studio/package.json','studio/package-lock.json','studio/tsconfig.json','studio/tsconfig.node.json','studio/vite.config.ts']:
        path=ROOT/name
        if path.is_file():files.append(path)
    files.extend([Path(__file__).resolve(),HERE/'repair-contract.json'])
    files=sorted(set(files))
    before=[binding(path) for path in files]
    for path in files:
        target=destination/'files'/path.relative_to(ROOT);target.parent.mkdir(parents=True,exist_ok=True)
        with target.open('xb') as stream:stream.write(path.read_bytes())
    after=[binding(path) for path in files]
    report={'protocol':'archcanvas-collapse-continuity-before-implementation/1','createdUtc':datetime.now(timezone.utc).isoformat(),
            'scope':'Formal src, Studio src/tests/current dist/config and pre-implementation contract. Does not copy node_modules, venv, historical evidence or failed prototype.',
            'fileCount':len(files),'inputBindingsBefore':before,'inputBindingsAfter':after,'inputsUnchanged':before==after,
            'copiesExact':all(hashlib.sha256((destination/'files'/path.relative_to(ROOT)).read_bytes()).hexdigest()==before[index]['sha256'] for index,path in enumerate(files)),
            'testsRun':False,'buildRun':False,'modelExecuted':False,'productEditedByThisHelper':False}
    with (destination/'manifest.json').open('x') as stream:json.dump(report,stream,ensure_ascii=False,indent=2);stream.write('\n')
    print(json.dumps({'manifest':binding(destination/'manifest.json'),'files':len(files),'inputsUnchanged':before==after}))
    assert before==after and report['copiesExact']

if __name__=='__main__':main()
