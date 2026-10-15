from pathlib import Path
from datetime import datetime, timezone
import hashlib,json,re
root=Path(__file__).resolve().parents[3]
evidence=root/'docs/evidence/preview-generalization-20261014'
def read(name):return json.loads((evidence/name).read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
version=18
standard=read('final/standard-report.json');mixed=read('final/mixed-report.json')
for report in [standard,mixed]:
 assert report.get('finished') and report['engineHashesStillMatch'] and len(report['results'])==report['testedCatalogCases']
 for name,digest in report['engineHashes'].items():assert sha(root/'studio/public/preview/yworks_edge_router_lab'/name)==digest
 assert all(item['status']=='passed' for item in report['results'] if not item.get('historical'))
assert mixed['counts']['failedCases']==0
integrity=read('build-integrity.json');assert all(r['manifestMatches'] and r['distMatches'] and r['servedMatches'] for r in integrity['files'])
assert integrity['integrationManifestDistMatches'] and integrity['index']['servedMatches'] and all(a['servedMatches'] for a in integrity['assets'])
for item in integrity['files']:
 assert sha(root/'studio/public/preview'/item['path'])==item['sha256'] and sha(root/'studio/dist/preview'/item['path'])==item['sha256']
assert sha(root/'studio/dist/index.html')==integrity['index']['sha256']
for item in integrity['assets']:assert sha(root/'studio/dist'/item['path'].lstrip('/'))==item['sha256']
parent=read('parent-verification.json');assert all(sha(root/name)==digest for name,digest in parent['implementation'].items())
engine=read('engine-regression.json');assert engine['exitCode']==0 and engine['fail']==0 and engine['runtimeHashesStillMatchFormalTree']
for name,digest in engine['runtimeEngineFiles'].items():assert sha(root/'studio/public/preview/yworks_edge_router_lab'/name)==digest
for name,digest in engine['runtimeFixtureFiles'].items():assert sha(root/'studio/public/preview'/name)==digest
log=(evidence/'frontend-targeted.log').read_text();match=re.search(r'ℹ tests (\d+).*?ℹ pass (\d+).*?ℹ fail (\d+).*?ℹ skipped (\d+)',log,re.S);assert match and int(match[1])==int(match[2])+int(match[4]) and match[3]=='0'
dom=(evidence/'frontend-publication-dom.log').read_text();dm=re.search(r'ℹ tests (\d+).*?ℹ pass (\d+).*?ℹ fail (\d+).*?ℹ skipped (\d+)',dom,re.S);assert dm and dm[1]==dm[2]=='3' and dm[3]==dm[4]=='0'
assert 'real DOM SVG sanitization preserves path, transform, marker and physical proportions, and passes the publication validator' in dom and int(match[4])==1
backend=(evidence/'bundle-budget.log').read_text();assert 'Ran 4 tests' in backend and re.search(r'\nOK\s*$',backend)
frontend={'declaredTests':int(match[1]),'passed':int(match[2]),'failed':int(match[3]),'sandboxSkipped':int(match[4]),'verifiedUniqueTests':int(match[1]),'log':'frontend-targeted.log','logSha256':sha(evidence/'frontend-targeted.log'),'domSupplement':{'tests':3,'passed':3,'skipped':0,'log':'frontend-publication-dom.log','logSha256':sha(evidence/'frontend-publication-dom.log'),'note':'Rechecks two passing publication tests and executes the one previously blocked by the sandbox; unique coverage is not double-counted.'}}
browser={}
for phase in ['cases','portable','transactions','no-worker','shared-trunks']:
 file=f'final-v{version}-{phase}/report.json';r=read(file);assert not r['errors'];assert all(x.get('ok',True) for x in r.get('results',[]))
 for item in r['servedAssets']:
  if '/preview/' in item['url']:
   path=item['url'].split('/preview/',1)[1].split('?',1)[0];assert sha(root/'studio/public/preview'/path)==item['sha256']
 browser[phase]={'report':file,'reportSha256':sha(evidence/file),'checks':len(r.get('results',r.get('checks',[])))}
auditFile=f'final-v{version}-browser-audit.json';audit=read(auditFile)
assert len(audit['reports'])==9 and len(audit['servedAssets'])==11
for path,digest in audit['servedAssets'].items():assert sha(root/'studio/dist'/path.lstrip('/'))==digest
auditedReports=[]
for item in audit['reports']:
 assert item['servedResourceCount']==11 and item['matchesFrozenV18'] and item['browserErrors']==0
 reportPath=root/item['report'];r=json.loads(reportPath.read_text());assert not r['errors']
 assets=r.get('servedAssets',r.get('assets'))
 assert len(assets)==11
 for asset in assets:
  path='/'+asset['url'].split('://',1)[1].split('/',1)[1].split('?',1)[0]
  if 'status' in asset:assert asset['status']==200
  assert asset['sha256']==audit['servedAssets'][path]
 for stage in r.get('stages',[]):
  v=stage['validation'];assert v['source']['ok'] and v['layout']['ok'] and all(c['ok'] for _,c in v['edges']) and not v['routing']['contacts'] and not stage['studio']['unrelatedOverlaps']
 auditedReports.append({'report':item['report'],'sha256':sha(reportPath)})
assert audit['vaeFullOrderGeometryEqual'] and audit['vaeOriginalDetailedRectanglesPreserved']==28 and audit['lstmInitialAndCollapseGeometryEqual']
browser['audit']={'report':auditFile,'sha256':sha(evidence/auditFile),'groups':9,'servedResourcesPerGroup':11,'browserErrors':0,'reports':auditedReports}
caseReport=read(f'final-v{version}-cases/report.json')
times=[a['ms'] for item in caseReport['results'] for a in item['actions'] if a['action'] in ('expand','collapse')]
browser['cases']['nativeToggles']={'count':len(times),'minimumMs':min(times),'maximumMs':max(times),'averageMs':sum(times)/len(times),'scope':'Clean native action plus settled snapshot and validation; catalog CPU matrix held.'}
vaePath=root/f'docs/evidence/preview-vae-layout-20261014/final-v{version}/report.json';vae=json.loads(vaePath.read_text());assert not vae['errors'] and len(vae['stages'])==5
for item in vae['assets']:
 path=item['url'].split('://',1)[1].split('/',1)[1].split('?',1)[0]
 assert item['status']==200 and sha(root/'studio/dist'/path)==item['sha256']
for stage in vae['stages']:
 v=stage['validation'];assert v['source']['ok'] and v['layout']['ok'] and all(c['ok'] for _,c in v['edges']) and not v['routing']['contacts'] and not stage['studio']['unrelatedOverlaps']
classification=read('final/failure-classification.json');fixed=read('historical-fixed-interface-conflicts.json');quality=read('final/quality-comparison.json')
assert classification['counts']['active']==0 and quality['counts']['legalToInvalid']==0
replay=read('baseline-v14-contact-audit/routing-replay-integrity.json');metric=read('baseline-v14-contact-audit/metric-equivalence.json')
assert replay['passed'] and not replay['differences'] and replay['checkedStages']==quality['counts']['matchedStages']
assert metric['functionTextIdentical'] and metric['productionFunctionSha256']==metric['diagnosticFunctionSha256']
assert sha(evidence/'baseline-v14-contact-audit/wire-contact-metric.js')==metric['helperSha256']
assert sha(root/'studio/public/preview/yworks_edge_router_lab/router.js')==metric['routerSha256']
for phase in replay['phases']:
 assert sha(root/phase['archiveReport'])==phase['archiveReportSha256'] and sha(root/phase['replayReport'])==phase['replayReportSha256']
for phase in quality['phases']:
 assert not phase['unmatched'] and sha(root/phase['baselineReport'])==phase['baselineReportSha256'] and sha(root/phase['currentReport'])==phase['currentReportSha256']
assert not quality['stagesWithUnavailableMetrics']
qualityReports={}
for filename in ['quality-comparison.json','v16-to-v18-quality-comparison.json','v17-to-v18-quality-comparison.json']:
 q=read('final/'+filename)
 assert q['counts']['matchedStages']==1396 and not q['stagesWithUnavailableMetrics'] and q['counts']['legalToInvalid']==0
 for phase in q['phases']:
  assert not phase['unmatched'] and sha(root/phase['baselineReport'])==phase['baselineReportSha256'] and sha(root/phase['currentReport'])==phase['currentReportSha256']
  assert phase['currentEngineHashes']==standard['engineHashes']
 qualityReports[filename]={'report':'final/'+filename,'sha256':sha(evidence/'final'/filename),'counts':q['counts']}
assert qualityReports['v16-to-v18-quality-comparison.json']['counts']['stagesWithAnyWorsening']==0
summary={'schema':'archcanvas-preview-generalized-final-validation/1','verifiedAt':datetime.now(timezone.utc).isoformat(),'presentationVersion':version,'runtime':'formal Studio vendored Summary_Merge-derived preview only','sourceModelExecuted':False,'engineHashes':standard['engineHashes'],'integration':{'files':len(integrity['files']),'publicDistServedAllMatch':True,'report':'build-integrity.json'},'frontend':frontend,'referenceEngine':{'tests':engine['tests'],'passed':engine['pass'],'failed':engine['fail'],'declaredTests':engine['declaredTestCases'],'report':'engine-regression.json'},'backendBundle':{'tests':4,'passed':4,'log':'bundle-budget.log','logSha256':sha(evidence/'bundle-budget.log')},'parent':{'implementationHashesStillMatch':True,'report':'parent-verification.json'},'browser':browser,'vae':{'report':str(vaePath.relative_to(root)),'sha256':sha(vaePath),'transitions':vae['transitions'],'stages':[{'name':s['name'],'nodes':s['studio']['nodes'],'edges':s['studio']['edges'],'length':s['studio']['totalLength'],'bends':s['studio']['totalBends'],'unrelatedSegmentCrossings':s['studio']['unrelatedCrossingCount'],'nearParallelPairs':s['studio']['nearParallelPairs']} for s in vae['stages']]},'catalog':{'standard':standard['counts'],'activeTested':sum(not r.get('historical',False) for r in standard['results']),'activePassed':sum(not r.get('historical',False) and r['status']=='passed' for r in standard['results']),'historicalTested':sum(r.get('historical',False) for r in standard['results']),'historicalPassed':sum(r.get('historical',False) and r['status']=='passed' for r in standard['results']),'skippedWithoutRegisteredGraph':standard['skippedWithoutRegisteredGraph'],'mixed':mixed['counts'],'failureClassification':classification['counts'],'fixedTargetProof':fixed['counts']},'qualityComparison':quality['counts'],'contactRegression':{'beforeProof':'t-contact-regression/before-proof.json','regressionTest':'studio/tests/previewWireContacts.test.ts','scope':'Unique independent contact points, including internal bends; shared wire and licensed complete shared-presentation exemptions retained.'},'limitations':['Historical source/containment or independent fixed-terminal contradictions remain rejected; no bindings or source files are guessed or weakened.','Unrelated crossings and source-constrained short near-parallel approaches can remain; metrics and native closeups are retained.','Clean browser timing covers the measured models and frontier depths; concurrent matrix timings are functional evidence only.']}
summary['qualityReports']=qualityReports
summary['reviewedQualityTradeoffs']={'versusV14':{'stagesWithAnyWorsening':quality['counts']['stagesWithAnyWorsening'],'aspp':'Three stages: length +87 px, bends -4, strict crossings -2, no increased independent contacts or crowding. True external producer axis keeps the central branch and output straight.','timeMixer':'Three stages: strict crossings +1, independent contacts 14 to 12 and T touches 3 to 0, with no newly intersecting pair or increased crowding.'},'versusV16':'All 1396 stages have no worsening in any of the nine measured metrics.','versusV17':'Six stages have a worsening: four stages of a historical MI-LSTM case and a current Transformer-XL case lose incidental early-terminal-pass improvements; two active MI-LSTM stages trade 28 px more close parallel length for two fewer bends. All remain no worse than v16.'}
summary['baselineReplay']={'report':'baseline-v14-contact-audit/routing-replay-integrity.json','sha256':sha(evidence/'baseline-v14-contact-audit/routing-replay-integrity.json'),'passed':True,'checkedCases':replay['checkedCases'],'checkedStages':replay['checkedStages'],'routingEngineModified':False,'diagnosticFunctionMatchesProduction':True,'metricEquivalence':'baseline-v14-contact-audit/metric-equivalence.json','metricEquivalenceSha256':sha(evidence/'baseline-v14-contact-audit/metric-equivalence.json')}
(evidence/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
rows=''.join('| '+item['name']+' | '+', '.join(str(a['ms']) for a in item['actions'] if a['action'] in ('expand','collapse'))+' |\n' for item in caseReport['results'])
text=f'''# Generalized preview final verification — 2026-10-14

The final acceptance uses frozen presentation version {version}. The original Summary_Merge source remains read-only; every test runs the formal vendored engine. Model Python code is not imported or executed. Studio panels, source authority, reviewed authoring contracts, visual drafts and browser history remain distinct and connected through the existing bridge.

## Final checks

- Frontend targeted regression: **{frontend['passed']} passed, 0 failed** (`frontend-targeted.log`). One Chromium DOM test was skipped by the sandbox, then the publication file passed **3 / 3** outside it (`frontend-publication-dom.log`), covering all **{frontend['verifiedUniqueTests']} declared unique checks** without double-counting the two repeated tests. Source corpus identities, authoring projection, race/transaction guards, recursive routing, source wires, labels, manual knots, source spine and provisional move reservations are covered.
- Original prototype engine tests against only formal runtime: **{engine['pass']} / {engine['tests']} actual TAP tests** (`engine-regression.json`). Source definitions contain {engine['declaredTestCases']} declarations, including inactive definitions; the count is not substituted for executed tests.
- Backend archive budget/inventory regression: **4 / 4** (`bundle-budget.log`).
- Build and integrity: 16 integration resources match the manifest, public tree, built dist and actual 8891 response. Main page assets match too (`build-integrity.json`).
- Native browser: 10 / 10 model families, 40 real expand/fold gestures. Every family covers nested reopen geometry, container movement, Apply layout and undo/redo. Portable state/load/recovery checks: 6 / 6; Transformer atomic transactions: 7; no-Worker fallback: 3. The additional standard/compact shared-trunk native gesture suite is recorded in `final-v{version}-shared-trunks/report.json`.
- The unified `final-v{version}-browser-audit.json` binds all nine browser groups to the same 11 actually served resource hashes, with zero browser errors. Targeted PatchTST placement/gates, TimeMixer terminal lanes and LayerNorm LSTM initial/fold return geometry are included; these supplemental checks are not latency measurements.
- Parent implementation and CPU projection evidence remain bound to their unchanged 13 implementation hashes (`parent-verification.json`); those CPU measurements do not stand in for browser latency.

## Clean native timing

All matrix and other CPU tests were held during `final-v{version}-cases` and the five-stage VAE inspection. Forty native gestures took **{min(times)}–{max(times)} ms**. These include the action, settled snapshots and diagnostics; they are not isolated router CPU costs.

| Model | Native expand / nested / fold / reopen (ms) |
| --- | --- |
{rows}
VAE final native closeups and five-stage measurements are documented in `../preview-vae-layout-20261014/README.md`. They include equal-depth comparison, exact source node positions, full-direct versus mixed-first stability, and residual crossings/near-parallel approaches.

## Full catalog and mixed frontiers

The final standard matrix covers **{standard['counts']['cases']} cases / {standard['counts']['stages']} stages**, including historical snapshots. All **{summary['catalog']['activePassed']} / {summary['catalog']['activeTested']} current cases with registered graphs** pass. One current SVG-only case has no registered graph and is listed explicitly in the report. Historical cases pass **{summary['catalog']['historicalPassed']} / {summary['catalog']['historicalTested']}**; the remaining {classification['counts']['historical']} fail source/geometry constraints and remain rejected.

The mixed matrix covers **{mixed['counts']['cases']} cases / {mixed['counts']['stages']} stages**, all passing. Nested targets are selected by hierarchy depth/branching rather than model names. Both matrices check source authority, node containment, every edge, headings, frame clearance, fold/reopen geometry and retained route identity. Their timings ran concurrently with functional validation and must not be presented as clean latency measurements.

`final/failure-classification.json` preserves all failing stage categories and violations. `historical-fixed-interface-conflicts.json` proves {fixed['counts']['cases']} historical cases / {fixed['counts']['uniquePairsAtSelectedStages']} independent fixed-terminal pairs from saved failure graphs; each pair requires a shared positive terminal ray under its original policies. Other historical cases contain invalid source/containment and sometimes separate wire overlaps. No evidence was rewritten to make these snapshots pass.

## Nonregression and provenance

Three quality comparisons pair identical source/catalog bytes and stage names across **1396 stages and nine measured metrics**. Against v16, v{version} has **zero stages with any measured worsening**, with shorter paths in 24 stages and less close parallel length in 19. Against the earlier v14, **{quality['counts']['stagesWithAnyWorsening']} stages have a measured increase**, all reviewed: three ASPP stages add 87 px while removing four bends and two strict crossings; three TimeMixer stages add one strict crossing while independent contacts fall from 14 to 12 and T touches fall from three to zero. No new intersecting pair or increased crowding is introduced in those TimeMixer stages. Against v17, a historical MI-LSTM case and a current Transformer-XL case lose incidental early-pass improvements in four stages, and two active MI-LSTM stages have 28 px more close length but two fewer bends. All six remain no worse than v16. The complete per-stage figures are in `final/quality-comparison.json`, `final/v16-to-v18-quality-comparison.json` and `final/v17-to-v18-quality-comparison.json`.

There are **{quality['counts']['legalToInvalid']} previously legal stages becoming invalid**. This legality result is separate from the visual cost comparisons; it does not establish universal visual optimality. Earlier v13–v17 matrices and failures remain in version-labelled archives. Final results never use older engine bytes as current proof.

The early v14 original-engine run exposed two real regressions despite successful browser and catalog checks: asymmetric frame padding displaced an aligned shared input, and provisional invalid peer routes blocked a norm move. Version 15 fixed those two regressions, but the expanded quality comparison then exposed overly broad content-axis alignment in other pipelines. Version 16 restricts the content axis to explicit shared-value boundary fanout with a source-aligned central terminal, and retains complete move transaction validation. The rule uses source evidence rather than model names or case IDs. New synthetic tests and native standard/compact Transformer gestures retain these failure modes as ongoing checks. A separate real optional-cleanup counterexample showed one new internal corner contact without changing strict crossing count; deduplicated geometric contacts now participate in the nonregression guard, while source-authorized sharing stays licensed. `t-contact-regression/` preserves the counterexample and its runtime bytes. Version 17 additionally excludes a container’s own input proxy from shared-axis authority, removing the PatchTST length-only regression without disabling genuine single-boundary fanout. A bounded terminal-band follow-up reuses neighboring fixed value slots and shares the same cleanup budgets. It accepts only less crowding with no increased contacts, strict crossings, length or bends and preserves ordered manual knots and exact gates. `spine-proxy-regression/` and `terminal-band-regression/` retain old failing examples, isolated runtime receipts and reflection/rotation tests. The complete v17 matrix exposed a cleanup-order regression in layer-normalized LSTM and a bend tradeoff in MI-LSTM. Version 18 finishes all existing lane shifting and shortening before the terminal follow-up. The follow-up additionally guards near-parallel run count, total length and minimum gap, and cannot consume the normal simplification budget before it finishes. Whole-pipeline failing and passing receipts are preserved under `terminal-band-regression/post-loop/`.

## Reproduction

Run these commands from the full source checkout, which supplies `studio/public/preview`, the test fixtures and development dependencies. The distributable bundle retains the reviewed reports and bounded historical isolation materials as evidence; it does not include the complete development checkout. In particular, the historical post-loop runner requires the checkout's public fixture tree and is not a standalone bundle command.

```bash
node studio/scripts/check-preview-frontiers.cjs --phase standard --include-historical --output docs/evidence/preview-generalization-20261014/recheck-standard
node studio/scripts/check-preview-frontiers.cjs --phase mixed --cases "$(cat docs/evidence/preview-generalization-20261014/final-mixed-selection.txt)" --output docs/evidence/preview-generalization-20261014/recheck-mixed
node studio/scripts/test-preview-generalization.mjs --phase final --cases "UNet,DenseNet,Autoformer,VAE,Flow Sequential,Graph Attention,ResNet,TCN Block,MobileNetV3,WaveNet Block" --output-dir docs/evidence/preview-generalization-20261014/recheck-browser
node studio/scripts/test-preview-expansion.mjs --phase final --shared-trunks-only --output-dir docs/evidence/preview-generalization-20261014/recheck-shared-trunks
python3 studio/scripts/test-preview-engine-regression.py --output-directory docs/evidence/preview-generalization-20261014/recheck-engine
```

`summary.json` records final report paths and hashes. Large graph/SVG artifacts are compressed deterministically; reports and screenshots remain directly readable.
'''
# The selector is stored as JSON in the repository; avoid inventing a text file.
text=text.replace('--cases "$(cat docs/evidence/preview-generalization-20261014/final-mixed-selection.txt)" ', '--selection docs/evidence/preview-generalization-20261014/final-mixed-selection.json ')
(evidence/'README.md').write_text(text)
print(json.dumps({'version':version,'active':summary['catalog']['activePassed'],'mixed':mixed['counts']['passedCases'],'tests':frontend['passed'],'engine':engine['pass']}))
