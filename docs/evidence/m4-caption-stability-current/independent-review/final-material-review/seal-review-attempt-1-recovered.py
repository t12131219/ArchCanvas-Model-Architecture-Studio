"""Hash-bind this completed static review; no product imports or execution."""
from __future__ import annotations
from datetime import datetime,timezone
import hashlib,json
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
OUT=HERE/'independent-seal'
def raw_binding(path):
 raw=path.read_bytes();return {'path':str(path.relative_to(ROOT)),'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}
def load(path):return json.loads(path.read_bytes())
def exact(path,row):
 actual=raw_binding(path);return actual['bytes']==row['bytes']and actual['sha256']==row['sha256']
def main():
 assert not OUT.exists();OUT.mkdir()
 current=load(HERE/'production-label-only-audit/report.json');assert current['passed']==current['total']==2708
 exact_readback=load(HERE/'production-label-only-audit/production-exact-readback.json');assert exact_readback['passed']==exact_readback['relations']==765
 checks=[];captures=0;snapshots=0
 for capture_path in sorted(HERE.glob('*/capture.json')):
  value=load(capture_path)
  for r in value['documentRecords']:
   row=r['binding'];path=HERE/row['path'];checks.append({'kind':'capture-document','path':str(path.relative_to(ROOT)),'passed':exact(path,row)});captures+=1
  for r in value['sceneRecords']:
   for key in ['sceneBinding','svgBinding']:
    row=r[key];path=HERE/row['path'];checks.append({'kind':'capture-scene-svg','path':str(path.relative_to(ROOT)),'passed':exact(path,row)});captures+=1
 for manifest_path in sorted((HERE/'snapshots').glob('*/manifest.json')):
  value=load(manifest_path)
  for row in value['files']:
   path=manifest_path.parent/row['path']if row['path'].startswith('core/')else ROOT/row['path']
   checks.append({'kind':'frozen-core','path':str(path.relative_to(ROOT)),'passed':exact(path,row)});snapshots+=1
 production=load(HERE/'snapshots/production-label-only/manifest.json')
 for row in production['files']:
  path=ROOT/row['originalPath'];checks.append({'kind':'current-production-core','path':str(path.relative_to(ROOT)),'passed':exact(path,row)})
 for name in ['blocks.py','model.py']:
  checks.append({'kind':'source-fixture-original-bytes','path':f'fixtures/transformer/{name}','passed':(HERE/name).read_bytes()==(ROOT/'fixtures/transformer'/name).read_bytes()})
 before_manifest=ROOT/'docs/evidence/m4-caption-stability-current/before-change/manifest.json'
 checks.append({'kind':'root-before-freeze','path':str(before_manifest.relative_to(ROOT)),'passed':hashlib.sha256(before_manifest.read_bytes()).hexdigest()=='dbe53e05754636a4e5ebe191eccb106f30038cda2245ccf6243f9356eb187344'})
 assert all(c['passed']for c in checks),[c for c in checks if not c['passed']]
 report={'schema':'archcanvas-caption-stability-independent-static-seal/1','createdUtc':datetime.now(timezone.utc).isoformat(),'passed':len(checks),'total':len(checks),'checks':checks,'captureBindings':captures,'frozenCoreBindings':snapshots,'currentCoreBindings':18,'sourceModels':1,'productionDetachedInputs':45,'productionScenes':360,'productionMatrix':{'passed':2708,'total':2708,'labelFailures':0,'unsafeCaptionWithoutWarning':0,'nominalUnsafeCaptionWithWarning':24},'exactProductionVsFrozenLabelOnly':{'passed':765,'total':765},'productionSceneSHA256':'b4647b6c87a2fd7cb0b4424c64869c51657f0f6227d3126cc883835f8ce2274f','rejectedSideCandidates':raw_binding(HERE/'rejected-candidates.json'),'oracleCorrections':raw_binding(HERE/'oracle-corrections.md'),'knownLimitation':current['thresholdPortDiscontinuity'],'status':'production label-only static checks pass; side/residual route candidate failures rejected and preserved','scope':'One Transformer and detached finite presentation inputs. These counts are bindings/relations, not additional product tests, models, users or humans. No source/runtime model execution, browser gestures, font measurement, global aesthetic/physical publication or performance acceptance. Camera behavior is reviewed separately. M4 remains partial, human participants zero.'}
 (OUT/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
 files=[p for p in sorted(HERE.rglob('*'))if p.is_file()and 'independent-seal'not in p.relative_to(HERE).parts and 'final-material-review'not in p.relative_to(HERE).parts and '__pycache__'not in p.parts]
 rows=[raw_binding(p)for p in files];rows.extend([raw_binding(OUT/'report.json')]);rows.extend(raw_binding(ROOT/r['originalPath'])for r in production['files'])
 manifest={'schema':'archcanvas-caption-stability-independent-static-seal-manifest/1','status':'sealed production label-only static evidence and rejected side candidates','files':rows,'exclusions':['Python bytecode cache','independent-seal output except report itself','later separate final-material-review'],'scope':report['scope']}
 path=OUT/'manifest.json';path.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'checks':len(checks),'captureBindings':captures,'frozenCoreBindings':snapshots,'manifestRows':len(rows),'manifestSHA256':hashlib.sha256(path.read_bytes()).hexdigest()}))
if __name__=='__main__':main()
