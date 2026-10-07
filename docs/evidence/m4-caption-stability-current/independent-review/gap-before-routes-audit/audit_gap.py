"""Independent literal horizontal-frontier checks; imports no product code."""
from __future__ import annotations
from argparse import ArgumentParser
from datetime import datetime,timezone
import hashlib,json,sys
from pathlib import Path
import xml.etree.ElementTree as ET
sys.dont_write_bytecode=True
from audit_matrix import actual_geometry,load,projection,semantic_projection,without_revision,points,NS
HERE=Path(__file__).resolve().parent

def main():
 p=ArgumentParser();p.add_argument('--tag',choices=['before','label-only','after'],required=True);p.add_argument('--suite',choices=['port-gap','side-gap'],required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 assert not a.output.exists();a.output.mkdir(parents=True)
 prefix='gap'if a.suite=='port-gap'else'side-gap';directory=f'{prefix}-{a.tag}'
 capture=load(HERE/directory/'capture.json');prior=load(HERE/f'{prefix}-before/capture.json');source=load(HERE/'source-envelope.json')['document'];checks=[];geometries=[];frontier=[]
 def check(name,value):checks.append({'name':name,'passed':bool(value)})
 def exact(row):
  raw=(HERE/row['path']).read_bytes();return len(raw)==row['bytes']and hashlib.sha256(raw).hexdigest()==row['sha256']
 check('one source9documents72scenes',len(capture['documentRecords'])==9 and len(capture['sceneRecords'])==72 and capture['sourceInputUnchanged']and capture['sourceRevision']==source['revision']==20)
 for r in capture['documentRecords']:
  obj=load(HERE/r['binding']['path']);base=obj['base'];h=[obj[k]for k in ['applied','undo','redo']]
  check('document capture binding '+r['mode']+r['move']['name'],exact(r['binding']))
  check('history immutable IR facts and undo redo '+r['mode']+r['move']['name'],obj['historyInputUnchanged']and all(x['document']['architecture']==base['architecture']and x['document']['sourceBindingDigest']==source['sourceBindingDigest']for x in h)and without_revision(h[1]['document'])==without_revision(base)and without_revision(h[2]['document'])==without_revision(h[0]['document'])and[x['document']['revision']for x in h]==[21,22,23])
  if a.tag!='before':check('same oldnew document history '+r['mode']+r['move']['name'],obj==load(HERE/f'{prefix}-before'/Path(r['binding']['path']).name))
 old={r['stem']:r for r in prior['sceneRecords']}
 for r in capture['sceneRecords']:
  scene=load(HERE/r['sceneBinding']['path']);was=load(HERE/old[r['stem']]['sceneBinding']['path']);svg=ET.fromstring((HERE/r['svgBinding']['path']).read_bytes());meta=json.loads(svg.find(NS+'metadata').text)
  check('exact captures deterministic immutable '+r['stem'],exact(r['sceneBinding'])and exact(r['svgBinding'])and r['documentUnchanged']and r['deterministic'])
  check('same oldnew facts '+r['stem'],semantic_projection(scene)==semantic_projection(was)if a.tag=='after'else projection(scene)==projection(was))
  check('SVG metadata bindings '+r['stem'],meta['documentId']==source['id']and meta['sourceDigest']==source['sourceBindingDigest']and meta['irDigest']==source['architecture']['irDigest']and meta['sourceFacts']==scene['sourceFacts']and meta['renderedBindings']==[{'sceneEdgeId':e['id'],'canonicalEdgeIds':e['canonicalEdgeIds'],'source':e['source'],'target':e['target'],'tensorId':e['tensorId'],'role':e['role']}for e in scene['edges']])
  for e in scene['edges']:
   if e['role']!='memory':continue
   expected=''if r['mode']=='empty'else'memory context'if r['mode']=='custom'else'memory'
   check('default empty custom literal '+r['stem']+'/'+e['id'],e['label']==expected)
   if e['label']:
    geometry=actual_geometry(scene,e);warning=any(d.get('edgeId')==e['id']and d.get('code')in ['layout-edge-label-blocked','layout-edge-label-association']for d in scene['diagnostics']);geometry.update({'case':r['stem'],'edgeId':e['id'],'explicitWarning':warning});geometries.append(geometry)
    check('caption geometry safe or explicit diagnosis '+r['stem']+'/'+e['id'],geometry['safe']or warning)
   if r['mode']=='default'and r['preset']=='paper'and r['widthMm']==180 and r['scope']=='whole':
    src=next(n for n in scene['nodes']if n['id']==e['sourceId']);dst=next(n for n in scene['nodes']if n['id']==e['targetId']);route=points(e['path'])
    frontier.append({'move':r['move'],'frontCardGap':dst['x']-(src['x']+src['width']),'repeatVisibleGap':dst['x']-(src['x']+src['width']+7),'path':e['path'],'sourceEndpoint':route[0],'targetEndpoint':route[-1],'label':e['label'],'warnings':scene['diagnostics']})
 report={'schema':'archcanvas-horizontal-gap-independent-oracle/1','createdUtc':datetime.now(timezone.utc).isoformat(),'tag':a.tag,'suite':a.suite,'checks':checks,'passed':sum(c['passed']for c in checks),'total':len(checks),'failedChecks':[c for c in checks if not c['passed']],'captionGeometries':geometries,'frontier':frontier,'sourceModels':1,'detachedLabelMoveInputs':9,'scenes':72,'scope':'Finite literal frontier over one Transformer. Static outputs only; no browser gestures, model execution, visual or physical publication or performance acceptance.'}
 (a.output/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:report[k]for k in ['tag','suite','passed','total','frontier']}));raise SystemExit(0 if report['passed']==report['total']else 1)
if __name__=='__main__':main()
