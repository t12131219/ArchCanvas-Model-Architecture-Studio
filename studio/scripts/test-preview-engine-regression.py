#!/usr/bin/env python3
"""Copy test definitions into a temporary CommonJS harness; link only formal assets.

No reference runtime is loaded and no source-model code is executed.
"""
from pathlib import Path
import tempfile, json, hashlib, re, subprocess, time, argparse

parser=argparse.ArgumentParser(description="Run reference engine test definitions against only the formal vendored runtime.")
parser.add_argument("--reference-tests",type=Path,help="Read-only Summary_Merge root containing reference tests and the audit helper")
parser.add_argument("--output-directory",type=Path,help="New evidence directory")
parser.add_argument("--concurrency",type=int,choices=[1,2],default=2)
parser.add_argument("--prepare-only",action="store_true")
args=parser.parse_args()
project=Path(__file__).resolve().parents[2]
prototype=(args.reference_tests or project.parent/'prototype/Summary_Merge').resolve()
formal=project/'studio/public/preview'
scratch=Path(tempfile.mkdtemp(prefix='archcanvas-preview-expansion-regression-'))
output=(args.output_directory or project/'docs/evidence/preview-expansion-20261014').resolve()
output.mkdir(parents=True,exist_ok=True)
(scratch/'tests').mkdir(); (scratch/'tools').mkdir()
(scratch/'package.json').write_text('{"private":true,"type":"commonjs"}\n')
for name in ['yworks_edge_router_lab','data','snapshots']:
 (scratch/name).symlink_to(formal/name,target_is_directory=True)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
names=['graph-engine.test.cjs','recursive-expansion.test.cjs','boundary-lanes.test.cjs','interaction-mode.test.cjs']
test_definitions={}
fixture_from="../yworks_edge_router_lab/evidence/verification/overlap-fixture.json"
fixture_to="snapshots/yworks_edge_router_lab/evidence/verification/overlap-fixture.json"
version_match=re.search(r'const PRESENTATION_VERSION=(\d+);',(formal/'yworks_edge_router_lab/recursive-graph.js').read_text())
assert version_match, 'Formal recursive presentation version must be declared'
presentation_version=int(version_match.group(1))
test_adaptations={}
for name in names:
 src=prototype/'tests'/name; text=src.read_text()
 if name=='graph-engine.test.cjs':
  assert text.count(fixture_from)==1
  text=text.replace(fixture_from,fixture_to)
  test_adaptations[name]={'fixtureRemap':{'from':fixture_from,'to':fixture_to}}
 if name=='recursive-expansion.test.cjs':
  expected='assert.equal(restored.recursive.presentationVersion,10);'
  assert text.count(expected)==1
  text=text.replace(expected,f'assert.equal(restored.recursive.presentationVersion,{presentation_version});')
  test_adaptations[name]={'presentationVersionExpectation':{'from':10,'to':presentation_version,'reason':'The formal presentation migration has advanced; retain the original upgrade/state/source assertions.'}}
 dest=scratch/'tests'/name; dest.write_text(text)
 test_definitions[name]={'origin':str(src),'sourceSha256':sha(src),'scratchSha256':sha(dest),'declaredTestCases':len(re.findall(r'\btest\(',text))}
audit=prototype/'tools/recursive-audit.cjs'
assert audit.read_text().strip()=='''// Graph-level checks complement the per-edge source and geometry validator.
const overlaps=graph=>globalThis.SummaryEngine.layoutConflicts(graph);
module.exports={overlaps};'''
(scratch/'tools/recursive-audit.cjs').write_bytes(audit.read_bytes())
files=['router.js','physical-ports.js','junction-markers.js','route-labels.js','source-contracts.js','semantic-constraints.js','graph-engine.js','recursive-graph.js','interaction-mode.js']
engine_hashes={name:sha(formal/'yworks_edge_router_lab'/name) for name in files}
catalog=json.loads((formal/'data/catalog.json').read_text())
fixture_paths={'data/catalog.json',fixture_to}
fixture_paths.update(view['json'] for case in catalog['cases'] for view in case['views'] if view.get('json'))
fixture_hashes={name:sha(formal/name) for name in sorted(fixture_paths)}
# Report module resolution under symlink-preserving CJS before running any test.
probe=subprocess.run(['node','--preserve-symlinks','-e',"const fs=require('node:fs');require('./yworks_edge_router_lab/router.js');const E=require('./yworks_edge_router_lab/graph-engine.js');const F=require('./yworks_edge_router_lab/recursive-graph.js');if(typeof E.validateView!=='function'||typeof F.toggle!=='function')throw Error('runtime exports unavailable');console.log(JSON.stringify({resolved:fs.realpathSync(require.resolve('./yworks_edge_router_lab/graph-engine.js')),recursive:fs.realpathSync(require.resolve('./yworks_edge_router_lab/recursive-graph.js'))}));"],cwd=scratch,check=True,text=True,capture_output=True)
resolved=json.loads(probe.stdout)
assert Path(resolved['resolved'])==formal/'yworks_edge_router_lab/graph-engine.js'
assert Path(resolved['recursive'])==formal/'yworks_edge_router_lab/recursive-graph.js'
command=['node','--preserve-symlinks','--test','--test-reporter=tap','--test-isolation=none',f'--test-concurrency={args.concurrency}',*[f'tests/{name}' for name in names]]
plan={'scratch':str(scratch),'command':command,'runtimeEngineFiles':engine_hashes,'testDefinitions':test_definitions,'runtimeResolved':resolved,'runtimeFixtureFiles':fixture_hashes,'testAdaptations':test_adaptations}
(output/'engine-regression-plan.json').write_text(json.dumps(plan,indent=2)+'\n')
print(json.dumps({'status':'prepared','scratch':str(scratch),'runtimeResolved':resolved}),flush=True)
if args.prepare_only:raise SystemExit(0)
log=output/'engine-regression.log'; started=time.perf_counter()
with log.open('w') as stream:
 result=subprocess.run(command,cwd=scratch,stdout=stream,stderr=subprocess.STDOUT,text=True)
text=log.read_text(); elapsed=time.perf_counter()-started
counts={m.group(1):int(m.group(2)) for m in re.finditer(r'^# (tests|suites|pass|fail|cancelled|skipped|todo) (\d+)\s*$',text,re.M)}
current={name:sha(formal/'yworks_edge_router_lab'/name) for name in files}
changes=[{'file':name,'testedSha256':engine_hashes[name],'currentSha256':current[name]} for name in files if current[name]!=engine_hashes[name]]
fixture_changes=[name for name,digest in fixture_hashes.items() if sha(formal/name)!=digest]
report={'schema':'archcanvas-vendored-preview-engine-regression/1','date':'2026-10-14','command':' '.join(command),'node':subprocess.check_output(['node','--version'],text=True).strip(),'exitCode':result.returncode,'seconds':elapsed,**counts,'declaredTestCases':sum(v['declaredTestCases'] for v in test_definitions.values()),'declaredTestCasesByFile':{k:v['declaredTestCases'] for k,v in test_definitions.items()},'testDefinitions':test_definitions,'scratch':str(scratch),'runtimeEngineFiles':engine_hashes,'runtimeResolved':resolved,'runtimeData':'formal studio/public/preview/data and snapshots, linked from temporary CommonJS harness','prototypeRuntimeUsed':False,'fixtureRemap':fixture_to,'recursiveAuditHelperSha256':sha(audit),'log':str(log.relative_to(project)) if log.is_relative_to(project) else str(log),'logSha256':sha(log),'runtimeHashesStillMatchFormalTree':not changes,'changedAfterFullRegression':changes}
# Preserve the actual TAP counts; source declarations can include inactive tests.
report['reportingNote']='Node TAP counters are reported verbatim. Declared case total is counted independently from source test declarations, not assumed to equal the runner counter.'
report['runtimeFixtureFiles']=fixture_hashes
report['testAdaptations']=test_adaptations
report['runtimeFixtureHashesStillMatchFormalTree']=not fixture_changes
report['fixturesChangedAfterFullRegression']=fixture_changes
(output/'engine-regression.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report),flush=True)
raise SystemExit(result.returncode if not changes and not fixture_changes else 2)
