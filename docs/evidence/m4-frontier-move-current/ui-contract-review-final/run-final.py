"""Read-only post-TS7022 correction audit and focused14 rerun; no full build."""
from pathlib import Path
import difflib
import hashlib
import json
import subprocess
from datetime import datetime,timezone

OWNER=Path(__file__).resolve().parent
ROOT=OWNER.parents[3]
STAGE=OWNER.parent
OLD=STAGE/'ui-contract-review'
OUT=OWNER/'focused-attempt-1'
if OUT.exists():raise SystemExit('Do not overwrite evidence')
OUT.mkdir()
def load(p):return json.loads(p.read_text())
def bind(p):
    p=Path(p)
    if not p.is_absolute():p=ROOT/p
    data=p.read_bytes()
    return {'path':str(p.relative_to(ROOT)),'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}
def write(path,data):
    with path.open('x') as file:json.dump(data,file,ensure_ascii=False,indent=2);file.write('\n')
old_receipt=load(OLD/'focused-attempt-2/receipt.json')
test_path='studio/tests/move-command-independent.test.ts'
snapshot=STAGE/'checks-attempt-1/inputs'/test_path
original=next(b for b in old_receipt['inputBindings'] if b['path']==test_path)
old=snapshot.read_text();current=(ROOT/test_path).read_text()
oldblock="""  for (const prefix of ['仅当前视图','只在当前视图','在当前视图','当前视图']) for (const fallback of [all,local]) {
    assert.deepEqual(parseMoveCommand(`${prefix}，向下移动 1.5`, ['output'], fallback),
      { status:'ready',operation:{type:'move',ids:['output'],dx:0,dy:1.5,scope:local} });
  }
  for (const prefix of ['所有视图','全部视图','在所有视图']) for (const fallback of [all,local]) {
    assert.deepEqual(parseMoveCommand(`${prefix} 向左移动 2.75`, ['output'], fallback),
      { status:'ready',operation:{type:'move',ids:['output'],dx:-2.75,dy:0,scope:all} });
  }
"""
newblock="""  for (const prefix of ['仅当前视图','只在当前视图','在当前视图','当前视图']) {
    for (let i = 0; i < 2; i += 1) {
      const fallback: MoveScope = i === 0 ? all : local;
      assert.deepEqual(parseMoveCommand(`${prefix}，向下移动 1.5`, ['output'], fallback),
        { status:'ready',operation:{type:'move',ids:['output'],dx:0,dy:1.5,scope:local} });
    }
  }
  for (const prefix of ['所有视图','全部视图','在所有视图']) {
    for (let i = 0; i < 2; i += 1) {
      const fallback: MoveScope = i === 0 ? all : local;
      assert.deepEqual(parseMoveCommand(`${prefix} 向左移动 2.75`, ['output'], fallback),
        { status:'ready',operation:{type:'move',ids:['output'],dx:-2.75,dy:0,scope:all} });
    }
  }
"""
snapshot_exact=bind(snapshot)['sha256']==original['sha256'] and bind(snapshot)['bytes']==original['bytes']
only_iteration=old.count(oldblock)==1 and current==old.replace(oldblock,newblock)
diff=''.join(difflib.unified_diff(old.splitlines(True),current.splitlines(True),fromfile=str(snapshot.relative_to(ROOT)),tofile=test_path))
(OWNER/'iteration-type-only.patch').write_text(diff)
if not snapshot_exact or not only_iteration:raise SystemExit('Change exceeds literal iteration/type correction')
common=[{'path':b['path'],'exact':bind(b['path'])==b} for b in old_receipt['inputBindings']]
assertions=lambda s:[' '.join(line.strip().split()) for line in s.splitlines() if 'assert.' in line or "{ status:'ready',operation:" in line]
assertions_same=assertions(old)==assertions(current)
if not assertions_same:raise SystemExit('Assertion literal text changed')
paths={b['path'] for b in old_receipt['inputBindings']}
paths.update([str(Path(__file__).relative_to(ROOT)),str(snapshot.relative_to(ROOT)),
              str((OLD/'focused-attempt-2/receipt.json').relative_to(ROOT)),str((OLD/'manifest.json').relative_to(ROOT)),
              str((OLD/'oracle-correction.json').relative_to(ROOT)),
              str((STAGE/'checks-attempt-1/strict-build.txt').relative_to(ROOT)),
              str((STAGE/'checks-attempt-2-studio.txt').relative_to(ROOT)),
              str((STAGE/'checks-attempt-2-strict-build.txt').relative_to(ROOT)),
              'studio/dist/assets/index-CW7T4YOE.js','studio/dist/assets/index--unhoRTb.css','studio/dist/index.html'])
before=[bind(p) for p in sorted(paths)]
command=['node','--experimental-strip-types','--test','--test-isolation=none','tests/move-command-independent.test.ts']
started=datetime.now(timezone.utc).isoformat()
result=subprocess.run(command,cwd=ROOT/'studio',capture_output=True,text=True)
(OUT/'stdout.txt').write_text(result.stdout);(OUT/'stderr.txt').write_text(result.stderr)
after=[bind(b['path']) for b in before]
report={'schema':'archcanvas-frontier-ui-command-final-independent/1','startedUtc':started,'endedUtc':datetime.now(timezone.utc).isoformat(),
        'command':command,'cwd':str(ROOT/'studio'),'exitCode':result.returncode,
        'inputBindings':before,'inputAfter':after,'inputsUnchanged':before==after,
        'stdout':bind(OUT/'stdout.txt'),'stderr':bind(OUT/'stderr.txt'),
        'iterationReview':{'priorFocusedTestSnapshotExact':snapshot_exact,'onlyLiteralIterationTypeExpressionReplacement':only_iteration,
                           'assertionLiteralLinesUnchanged':assertions_same,'assertionLiteralLines':len(assertions(current)),
                           'priorBindingComparisons':common,'priorCurrentBindingMatches':sum(c['exact'] for c in common),
                           'priorBindingRows':len(common),'prior26CurrentExactInherited':False,
                           'unchangedCaseEnumeration':'Four local prefixes and three all prefixes each still exercise both all-frontiers,current-frontier defaults; only inner iteration/explicit type inference expression changed.'},
        'rootChecks':{'reportedBuild':'index-CW7T4YOE.js','priorStrictFailurePreserved':str((STAGE/'checks-attempt-1/strict-build.txt').relative_to(ROOT)),
                      'latestStudioLog':str((STAGE/'checks-attempt-2-studio.txt').relative_to(ROOT)),
                      'latestBuildLog':str((STAGE/'checks-attempt-2-strict-build.txt').relative_to(ROOT)),
                      'scope':'Bound existing root logs/current artifacts only; this independent reviewer does not rerun complete suite/build or claim served browser bytes.'},
        'scope':'Current focused parser and actual AST-extracted App callback tests. Read-only product/test audit; controlled harness, not mounted React/native effects or browser paint. World distances and operated-container/ancestor/pin toggle constraints retain earlier limits.',
        'modelExecuted':False,'sourceWriteback':False,'browserManipulated':False,'humanParticipants':0,'M4':'partial','M5':'not_started'}
write(OUT/'report.json',report)
print(result.stdout)
print(json.dumps({'exitCode':result.returncode,'inputs':len(before),'inputsUnchanged':before==after,
                  'onlyIterationTypeCorrection':only_iteration,'assertionLiteralLinesSame':assertions_same,
                  'priorBindingsCurrentlyExact':sum(c['exact'] for c in common),'priorRows':len(common)}))
raise SystemExit(result.returncode or (0 if before==after else 1))
