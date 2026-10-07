"""Readback of current successful receipts and frozen helper dependencies.

This script reads and hashes evidence; it does not run the product or tests.
"""
from __future__ import annotations
from datetime import datetime,timezone
import hashlib,json,re
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[4]
STAGE=ROOT/'docs/evidence/m4-caption-stability-current'
OUT=HERE/'checks-readback'
def load(path):return json.loads(path.read_bytes())
def binding(path):
 raw=path.read_bytes();return {'path':str(path.relative_to(ROOT)),'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}
def exact(path,row):
 actual=binding(path);return actual['bytes']==row['bytes']and actual['sha256']==row['sha256']
def main():
 assert not OUT.exists();OUT.mkdir()
 receipt_path=STAGE/'checks-final-attempt-2/receipt.json';receipt=load(receipt_path);checks=[];materials=set()
 def check(name,value):checks.append({'name':name,'passed':bool(value)})
 def keep(path):materials.add(path);return path
 keep(receipt_path)
 check('receipt scopes current110 publication11 build3',len(receipt['inputs'])==110 and len(receipt['publicationInputs'])==11 and len(receipt['build'])==3)
 check('recorded checks all exit0 and inputs unchanged',receipt['inputsUnchanged']and receipt['publicationInputsUnchanged']and len(receipt['checks'])==3 and all(c['exitCode']==0 for c in receipt['checks']))
 for group in ['inputs','publicationInputs']:
  for row in receipt[group]:check('current exact '+row['path'],exact(keep(ROOT/row['path']),row))
 for row in receipt['build']:
  check('current build exact '+row['path'],exact(keep(ROOT/row['path']),row))
  check('frozen build exact '+row['snapshot'],exact(keep(ROOT/row['snapshot']),row))
 for row in receipt['checks']:
  path=keep(ROOT/row['log']);log=path.read_text()
  if row['label']=='studio':check('Studio actual409pass0fail log',re.search(r'ℹ tests 409\b',log)and re.search(r'ℹ pass 409\b',log)and re.search(r'ℹ fail 0\b',log))
  elif row['label']=='publication':check('publication actual11pass log','Ran 11 tests'in log and re.search(r'\nOK\s*$',log))
  else:check('strict build includes TypeScript and actual built log','tsc -b && vite build'in log and 'built in'in log)
 # Capture the exact original18 core modules imported transitively by the
 # compatibility helper. The110 current-input receipt is not that inventory.
 before_manifest_path=keep(STAGE/'before-change/manifest.json');before=load(before_manifest_path)
 check('root before freeze dbe53 digest',binding(before_manifest_path)['sha256']=='dbe53e05754636a4e5ebe191eccb106f30038cda2245ccf6243f9356eb187344')
 core=[]
 for row in before['inputs']:
  snapshot=keep(ROOT/row['snapshot']);check('historical frozen input exact '+row['snapshot'],exact(snapshot,row))
  if row['path'].startswith('studio/src/core/'):
   core.append(row);copy=ROOT/'docs/evidence/m4-caption-stability-current/independent-review/snapshots/before/core'/Path(row['path']).name
   check('helper transitive18 independent snapshot exact '+row['path'],exact(keep(copy),row)and copy.read_bytes()==snapshot.read_bytes())
 check('exactly18 frozen helper core inputs',len(core)==18)
 helper=keep(ROOT/'studio/tests/historical-memory-caption-compat.ts');test=keep(ROOT/'studio/tests/historical-memory-caption-compat.test.ts');source=helper.read_text()
 protections=['serial(current.nodes), serial(before.nodes)','serial(protectedEdges(current)), serial(protectedEdges(before))',"'documentId', 'revision', 'sourceDigest', 'irDigest', 'sourceFacts', 'hiddenEdges', 'pageSpec', 'annotations', 'legend', 'exportScope'",'const copy = structuredClone(current)',"assert.equal(edge.role, 'memory')","assert.equal(old.role, 'memory')","assert.equal(old.label, '')","assert.equal(edge.label, 'memory')","assert.equal(canonical.label, undefined",'edge.label = old.label;','return copy;']
 check('helper literal only default memory text plus protected geometry facts',all(value in source for value in protections))
 check('helper imports actual18 frozen baseline index',"../../docs/evidence/m4-caption-stability-current/before-change/inputs/studio/src/core/index.ts"in source)
 test_source=test.read_text();check('meaningful corruption controls present',all(value in test_source for value in ["path = 'M 1 1 V 2'",'s.nodes.flatMap(n => n.ports)[0].x += .01',"canonicalEdgeIds = ['forged']",'assert.throws(() => normalizeDefaultMemoryLabels(authored, scene, before)',"JSON.stringify({ document, scene, before }), bytes"]))
 fixture=keep(ROOT/'docs/evidence/m4-caption-route-current/browser/pre-ui/saved-transformer-final-envelope.json');check('compatibility actual saved fixture equals independent source-envelope',fixture.read_bytes()==keep(ROOT/'docs/evidence/m4-caption-stability-current/independent-review/source-envelope.json').read_bytes())
 for path in sorted((STAGE/'checks-final-attempt-1').rglob('*')):
  if path.is_file():keep(path)
 failed=load(STAGE/'checks-final-attempt-1/receipt.json');check('first failed attempt preserved exact logical status',next(c for c in failed['checks']if c['label']=='studio')['exitCode']==1)
 check('current scene production labelonly b4647 digest',binding(ROOT/'studio/src/core/scene.ts')['sha256']=='b4647b6c87a2fd7cb0b4424c64869c51657f0f6227d3126cc883835f8ce2274f')
 static_seal=keep(ROOT/'docs/evidence/m4-caption-stability-current/independent-review/independent-seal-attempt-2/manifest.json');check('independent static seal e1c1 exact',binding(static_seal)['sha256']=='e1c1da11335dce6d92a780ae8a56ff641c71ff978322556c1b9b57673a74ec59')
 report={'schema':'archcanvas-caption-stability-independent-final-material-readback/1','createdUtc':datetime.now(timezone.utc).isoformat(),'passed':sum(c['passed']for c in checks),'total':len(checks),'checks':checks,'failedChecks':[c for c in checks if not c['passed']],'currentStudioReceiptInputs':110,'publicationReceiptInputs':11,'currentBuildFiles':3,'helperFrozenTransitiveCoreInputs':18,'frozenBeforeInputs':len(before['inputs']),'observedPassedTests':{'studio':409,'publication':11},'receipt':binding(receipt_path),'scope':'Read-only file bytes/hash and literal receipt/log/helper-source review. Current110 receipt inventory is not the full transitive fixture/gold or Node/Python toolchain inventory;18 helper frozen core inputs are separately bound. Does not rerun tests or product, approve pixels, browser actions, fonts, physical publication, performance or humans. Static2708 relations and765 bytes readback remain separately sealed; M4 partial/humans0.'}
 (OUT/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');materials.update([OUT/'report.json',Path(__file__).resolve()]);rows=[binding(path)for path in sorted(materials)]
 manifest={'schema':'archcanvas-caption-stability-independent-final-material-manifest/1','files':rows,'scope':report['scope']};path=OUT/'manifest.json';path.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'passed':report['passed'],'total':report['total'],'manifestRows':len(rows),'manifestSHA256':binding(path)['sha256']}));raise SystemExit(0 if report['passed']==report['total']else 1)
if __name__=='__main__':main()
