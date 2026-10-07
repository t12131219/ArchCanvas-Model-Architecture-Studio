"""Literal independent scene/caption geometry oracle: no product imports.

Static source-backed cases and adversarial cases are input variations, not
additional models, users, native gestures, physical font or FPS evidence.
"""
from __future__ import annotations
from argparse import ArgumentParser
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
import xml.etree.ElementTree as ET

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
EPS=1e-6
NS='{http://www.w3.org/2000/svg}'

def load(path):return json.loads(path.read_bytes())
def binding(path):
 raw=path.read_bytes();return {'path':str(path.relative_to(ROOT)),'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}
def points(path):
 result=[];at=0
 for token in re.finditer(r'([MHVL])\s*([-+\d.eE]+)(?:[ ,]+([-+\d.eE]+))?',path):
  assert not path[at:token.start()].strip(),path;at=token.end();cmd,a,b=token.groups();a=float(a)
  point=(a,float(b))if cmd in ['M','L']else(a,result[-1][1])if cmd=='H'else(result[-1][0],a)
  if not result or point!=result[-1]:result.append(point)
 assert not path[at:].strip() and len(result)>=2,path
 assert all(a[0]==b[0]or a[1]==b[1]for a,b in zip(result,result[1:])),path
 return result
def box(x,y,width,height):return(x,y,x+width,y+height)
def label_box(edge):return box(edge['labelX']-2,edge['labelY']-11,len(edge['label'])*9+4,16)
def inflate(b,p):return(b[0]-p,b[1]-p,b[2]+p,b[3]+p)
def overlap(a,b):return min(a[2],b[2])>max(a[0],b[0])and min(a[3],b[3])>max(a[1],b[1])
def enters(segment,b):
 a,c=segment
 return (b[0]<a[0]<b[2]and max(min(a[1],c[1]),b[1])<min(max(a[1],c[1]),b[3]))if a[0]==c[0]else(b[1]<a[1]<b[3]and max(min(a[0],c[0]),b[0])<min(max(a[0],c[0]),b[2]))
def contacts(segment,b):
 a,c=segment
 return(b[0]-EPS<=a[0]<=b[2]+EPS and max(a[1],c[1])>=b[1]-EPS and min(a[1],c[1])<=b[3]+EPS)if a[0]==c[0]else(b[1]-EPS<=a[1]<=b[3]+EPS and max(a[0],c[0])>=b[0]-EPS and min(a[0],c[0])<=b[2]+EPS)
def envelope(segment,p=0):
 a,b=segment;return inflate((min(a[0],b[0]),min(a[1],b[1]),max(a[0],b[0]),max(a[1],b[1])),p)
def gap(body,route):
 return min(math.hypot(max(body[0]-max(a[0],b[0]),min(a[0],b[0])-body[2],0),max(body[1]-max(a[1],b[1]),min(a[1],b[1])-body[3],0))for a,b in zip(route,route[1:]))
def on(point,segment,strict=False):
 a,b=segment
 if a[0]==b[0]:return abs(point[0]-a[0])<EPS and (min(a[1],b[1])+EPS<point[1]<max(a[1],b[1])-EPS if strict else min(a[1],b[1])-EPS<=point[1]<=max(a[1],b[1])+EPS)
 return abs(point[1]-a[1])<EPS and(min(a[0],b[0])+EPS<point[0]<max(a[0],b[0])-EPS if strict else min(a[0],b[0])-EPS<=point[0]<=max(a[0],b[0])+EPS)
def body_boxes(scene):
 result=[]
 for n in scene['nodes']:
  if n['expanded']:result.append((n['id'],box(n['x'],n['y'],n['width'],n['headerHeight'])))
  else:
   for offset in [0,3.5,7]if n.get('repeat')else[0]:result.append((n['id'],box(n['x']+offset,n['y']+offset,n['width'],n['height'])))
 for n in scene['annotations']:result.append((n['id'],box(n['x'],n['y'],n['width'],n['height'])))
 return result
def actual_geometry(scene,edge):
 text=label_box(edge);route=points(edge['path']);bodies=body_boxes(scene);issues=[]
 guides=[g for g in scene.get('captionGuides',[])if g['sceneEdgeId']==edge['id']]
 if any(overlap(text,b)for _,b in bodies):issues.append('nominal-text-body')
 if any(overlap(text,label_box(e))for e in scene['edges']if e['id']!=edge['id']and e['label']):issues.append('nominal-text-caption')
 if any(enters(s,text)for e in scene['edges']for s in zip(points(e['path']),points(e['path'])[1:])):issues.append('nominal-text-route')
 if any(enters(s,inflate(text,.4))for g in scene.get('captionGuides',[])if g['sceneEdgeId']!=edge['id']for s in zip(points(g['path']),points(g['path'])[1:])):issues.append('nominal-text-guide')
 direct=gap(text,route)
 if not guides and direct>18+EPS:issues.append('unassisted-association-over18')
 if len(guides)>1:issues.append('multiple-owned-guides')
 for g in guides:
  p=points(g['path']);length=sum(abs(a[0]-b[0])+abs(a[1]-b[1])for a,b in zip(p,p[1:]))
  if len(p)!=2 or not(0<length<=48+EPS):issues.append('guide-length-or-shape')
  if not any(on(p[0],s,True)for s in zip(route,route[1:])):issues.append('guide-start-not-owner-strict-interior')
  if not(text[0]-EPS<=p[-1][0]<=text[2]+EPS and text[1]-EPS<=p[-1][1]<=text[3]+EPS and any(abs(p[-1][i]-text[j])<EPS for i,j in [(0,0),(1,1),(0,2),(1,3)])):issues.append('guide-end-not-caption-envelope')
  if any(enters((p[0],p[-1]),inflate(b,.4))for _,b in bodies):issues.append('guide-body-stroke')
  if any(enters((p[0],p[-1]),inflate(label_box(e),.4))for e in scene['edges']if e['id']!=edge['id']and e['label']):issues.append('guide-caption-stroke')
  if any(contacts((p[0],p[-1]),envelope(s,.4+e['width']/2))for e in scene['edges']if e['id']!=edge['id']for s in zip(points(e['path']),points(e['path'])[1:])):issues.append('guide-peer-stroke')
  departure=(p[0][0]+math.copysign(EPS*10,p[-1][0]-p[0][0])if p[-1][0]!=p[0][0]else p[0][0],p[0][1]+math.copysign(EPS*10,p[-1][1]-p[0][1])if p[-1][1]!=p[0][1]else p[0][1])
  if any(contacts((departure,p[-1]),envelope(s))for s in zip(route,route[1:])):issues.append('guide-extra-own-contact')
  if any(contacts((p[0],p[-1]),envelope(s,.8))for other in scene.get('captionGuides',[])if other['id']!=g['id']for s in zip(points(other['path']),points(other['path'])[1:])):issues.append('guide-guide-stroke')
 return {'safe':not issues,'issues':sorted(set(issues)),'directGapWorld':direct,'guideCount':len(guides)}
def projection(scene):
 return {'nodes':scene['nodes'],'edges':[{k:v for k,v in e.items()if k not in ['label','labelX','labelY']}for e in scene['edges']],
         'documentId':scene['documentId'],'revision':scene['revision'],'sourceDigest':scene['sourceDigest'],'irDigest':scene['irDigest'],'sourceFacts':scene['sourceFacts'],'hiddenEdges':scene['hiddenEdges'],'exportScope':scene.get('exportScope')}
def without_revision(doc):return{k:v for k,v in doc.items()if k!='revision'}

def main():
 parser=ArgumentParser();parser.add_argument('--tag',choices=['before','after'],required=True);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
 assert not args.output.exists();args.output.mkdir(parents=True)
 current=load(HERE/args.tag/'capture.json');before=load(HERE/'before/capture.json');source=load(HERE/'source-envelope.json')['document'];architecture=source['architecture'];checks=[];label_failures=[];unsafe_without_warning=[];geometries=[]
 def check(name,condition):checks.append({'name':name,'passed':bool(condition)})
 check('literal360scope45docinventory',len(current['sceneRecords'])==360 and len(current['documentRecords'])==45)
 check('sourceCanvas20nevermutated',current['sourceInputUnchanged']and current['sourceRevision']==source['revision']==20)
 for name in ['blocks.py','model.py']:check('sourcePythonbytes unchanged '+name,(HERE/name).read_bytes()==(ROOT/'fixtures/transformer'/name).read_bytes())
 for record in current['documentRecords']:
  obj=load(HERE/record['binding']['path']);base=obj['base'];applied=obj['applied'];undo=obj['undo'];redo=obj['redo']
  check('history pure '+record['mode']+record['move']['name'],obj['historyInputUnchanged']and len(applied['past'])==1 and not applied['future']and not undo['past']and len(undo['future'])==1 and len(redo['past'])==1 and not redo['future'])
  check('sourceIR conserved undermove '+record['mode']+record['move']['name'],all(h['document']['architecture']==base['architecture']and h['document']['sourceBindingDigest']==source['sourceBindingDigest']for h in [applied,undo,redo]))
  check('undo redo exact documents '+record['mode']+record['move']['name'],without_revision(undo['document'])==without_revision(base)and without_revision(redo['document'])==without_revision(applied['document']))
  check('history revisions20212223 '+record['mode']+record['move']['name'],[h['document']['revision']for h in [applied,undo,redo]]==[21,22,23])
  if args.tag=='after':check('oldnewdocument/history exact '+record['mode']+record['move']['name'],obj==load(HERE/'before'/Path(record['binding']['path']).name))
 old_scenes={r['stem']:r for r in before['sceneRecords']}
 for record in current['sceneRecords']:
  scene=load(HERE/record['sceneBinding']['path']);old=load(HERE/old_scenes[record['stem']]['sceneBinding']['path']);svg=ET.fromstring((HERE/record['svgBinding']['path']).read_bytes());meta=json.loads(svg.find(NS+'metadata').text)
  check('immutable deterministic '+record['stem'],record['documentUnchanged']and record['deterministic'])
  check('canonical route facts projection exact to oldmoved '+record['stem'],projection(scene)==projection(old))
  check('SVG metadata/source rendered binding exact '+record['stem'],meta['documentId']==source['id']and meta['sourceDigest']==source['sourceBindingDigest']and meta['irDigest']==architecture['irDigest']and
        meta['sourceFacts']==scene['sourceFacts']and meta['renderedBindings']==[{'sceneEdgeId':e['id'],'canonicalEdgeIds':e['canonicalEdgeIds'],'source':e['source'],'target':e['target'],'tensorId':e['tensorId'],'role':e['role']}for e in scene['edges']])
  edges=[e for e in scene['edges']if e['role']=='memory'];expected=''if record['mode']=='empty'else'memory context'if record['mode']=='custom'else'memory'
  for edge in edges:
   actual=edge['label']==expected
   if not actual:label_failures.append({'case':record['stem'],'edgeId':edge['id'],'expected':expected,'actual':edge['label']})
   check('memory literal label '+record['stem']+'/'+edge['id'],actual)
   check('route endpoints present matching projected port circles '+record['stem']+'/'+edge['id'],all(any(p['x']==coord[0]and abs(p['y']-coord[1])<.051 or abs(p['x']-coord[0])<.051 and abs(p['y']-coord[1])<.051 for n in scene['nodes']if n['id']==node for p in n['ports']if edge['id']in p['canonicalEdgeIds'])for node,coord in [(edge['sourceId'],points(edge['path'])[0]),(edge['targetId'],points(edge['path'])[-1])]))
   if edge['label']:
    geometry=actual_geometry(scene,edge);warning=any(d.get('edgeId')==edge['id']and d.get('code')in ['layout-edge-label-blocked','layout-edge-label-association']for d in scene['diagnostics']);geometry.update({'case':record['stem'],'edgeId':edge['id'],'explicitWarning':warning});geometries.append(geometry)
    check('nominal association safe or explicit warning '+record['stem']+'/'+edge['id'],geometry['safe']or warning)
    if not geometry['safe']and not warning:unsafe_without_warning.append(geometry)
  parent={child:node for node in svg.iter()for child in node}
  svg_guides=[g for g in svg.iter()if g.get('data-caption-guide-id')];scene_guides=scene.get('captionGuides',[])
  check('guide inventory+metadata '+record['stem'],{g.get('data-caption-guide-id')for g in svg_guides}=={g['id']for g in scene_guides}and meta.get('presentationDecorations',[])==[{k:g[k]for k in ['id','kind','sceneEdgeId','path']}for g in scene_guides])
  for guide in svg_guides:
   ancestors=[];at=guide
   while at in parent:at=parent[at];ancestors.append(at)
   owner=guide.get('data-caption-for-edge');check('unarrowedinert unique owner '+record['stem']+'/'+guide.get('data-caption-guide-id'),sum(e['id']==owner for e in scene['edges'])==1 and not any(k.startswith('marker')for n in [guide,*ancestors]for k in n.attrib)and guide.get('pointer-events')=='none')
 budgets=load(HERE/args.tag/'budget-records.json')
 for obj in budgets:
  label_edges=[e for e in obj['input']['edges']if e['label']];placements=dict(obj['placements'])
  check('honestboundedfallback '+obj['input']['name'],obj['unchanged']and not obj['guides']and all(placements[e['id']]=={'x':e['labelX'],'y':e['labelY']}and any(d.get('edgeId')==e['id']and d.get('code')in ['layout-edge-label-blocked','layout-edge-label-association']for d in obj['diagnostics'])for e in label_edges))
 a=load(HERE/args.tag/'default-dy14-paper-180-whole.scene.json');b=load(HERE/args.tag/'default-dy15-paper-180-whole.scene.json')
 ea=next(e for e in a['edges']if e['id']=='edge:44');eb=next(e for e in b['edges']if e['id']=='edge:44');pa,pb=points(ea['path']),points(eb['path'])
 length=lambda p:sum(abs(q[0]-r[0])+abs(q[1]-r[1])for q,r in zip(p,p[1:]))
 threshold={'fromEncoderYDelta':14,'toEncoderYDelta':15,'sourceEndpointBefore':pa[0],'sourceEndpointAfter':pb[0],'targetEndpointBefore':pa[-1],'targetEndpointAfter':pb[-1],'pathBefore':ea['path'],'pathAfter':eb['path'],'lengthBefore':length(pa),'lengthAfter':length(pb),'sourceEndpointDisplacement':math.dist(pa[0],pb[0]),'targetEndpointDisplacement':math.dist(pa[-1],pb[-1]),'canonicalBindingsEqual':all(ea[k]==eb[k]for k in ['source','target','tensorId','role','canonicalEdgeIds']),'status':'existing-display-port-policy-discontinuity-remains','labelBefore':ea['label'],'labelAfter':eb['label']}
 report={'schema':'archcanvas-caption-stability-independent-oracle/1','tag':args.tag,'createdUtc':datetime.now(timezone.utc).isoformat(),'passed':sum(c['passed']for c in checks),'total':len(checks),'checks':checks,'failedChecks':[c for c in checks if not c['passed']],
         'sourceModels':1,'detachedLabelMoveInputs':45,'scenes':360,'labelFailures':label_failures,'unsafeCaptionWithoutWarning':unsafe_without_warning,'captionGeometries':geometries,'thresholdPortDiscontinuity':threshold,
         'scopes':['whole','root-detail'],'presets':['paper','monochrome'],'physicalWidthCases':[85,180],'budgetCases':7,
         'scope':'Literal static geometry/metadata/document/history oracle over one Transformer. No helper imports, source/runtime model execution, browser input, font measurement, physical publication, full visual quality or performance approval.'}
 (args.output/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'tag':args.tag,'passed':report['passed'],'total':report['total'],'labelFailures':len(label_failures),'unsafeWithoutWarning':len(unsafe_without_warning),'threshold':threshold}))
 raise SystemExit(0 if report['passed']==report['total']else 1)
if __name__=='__main__':main()
