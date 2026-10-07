"""Append a gesture pixel review only after direct original-image inspection."""
from pathlib import Path
from datetime import datetime, timezone
from PIL import Image
import argparse, hashlib, json, re, xml.etree.ElementTree as E

PROJECT = Path(__file__).resolve().parents[5]
BASE = PROJECT / 'docs/evidence/m4-au3-visual-matrix-work'
OUT = BASE / 'pixel-audit/gestures'
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
p = argparse.ArgumentParser()
p.add_argument('fixture'); p.add_argument('step'); p.add_argument('--node-id',required=True)
p.add_argument('--origin',default='00-origin');p.add_argument('--input');p.add_argument('--edge-ids',required=True)
p.add_argument('--observations',required=True);p.add_argument('--route',required=True)
a=p.parse_args();raw=BASE/'gestures'/a.fixture
j=raw/(a.step+'.json');shot=raw/(a.step+'.jpg');o=raw/(a.origin+'.json')
d=json.loads(j.read_text());origin=json.loads(o.read_text());root=E.fromstring(d['svg'])
node=next(n for n in d['nodes'] if n['id']==a.node_id);onode=next(n for n in origin['nodes'] if n['id']==a.node_id)
m=re.fullmatch(r'matrix\(([^)]+)\)',d['camera']);matrix=[float(x.strip()) for x in m[1].split(',')]
assert matrix[1:3]==[0,0] and matrix[0]==matrix[3]
delta={k:node[k]-onode[k] for k in ['x','y','width','height']}
sdelta={k:node['screen'][k]-onode['screen'][k] for k in ['x','y','width','height']}
assert all(abs(sdelta[k]-delta[k]*matrix[0])<0.01 for k in delta)
others=[]
omap={n['id']:n for n in origin['nodes']}
for n in d['nodes']:
 if n['id']!=a.node_id:
  dif={k:(omap[n['id']][k],n[k]) for k in ['x','y','width','height'] if omap[n['id']][k]!=n[k]}
  if dif:others.append({'id':n['id'],'differences':dif})
edges=[]
for g in root.iter():
 if g.attrib.get('data-edge-id') in a.edge_ids.split(','):
  edges.append({'id':g.attrib['data-edge-id'],'tensorId':g.attrib.get('data-tensor-id'),'paths':[x.attrib for x in g.iter() if x.tag.endswith('path')]})
files=[shot,j,raw/(a.step+'.dom.txt'),o]
if a.input:files.append(raw/(a.input+'.json'))
with Image.open(shot) as im:fmt=im.format;size=list(im.size)
record={'schemaVersion':1,'auditProtocol':'archcanvas-ai-gesture-pixel-review/1','fixture':a.fixture,'step':a.step,'auditor':'AI subagent /root/au3_pixel_audit','reviewedAt':datetime.now(timezone.utc).isoformat(),'sourceFiles':[{'path':str(f),'sha256':sha(f),'bytes':f.stat().st_size} for f in files],'image':{'path':str(shot),'detectedFormat':fmt,'detectedMime':'image/jpeg','widthPx':size[0],'heightPx':size[1],'originalRetained':True},'publicState':{'documentId':d['metadata']['documentId'],'revision':d['metadata']['revision'],'camera':d['camera'],'expandedIds':d['expandedIds'],'warnings':d['warnings'],'selectedBody':node,'originBody':onode,'bodyWorldDeltaFromOrigin':delta,'screenDeltaFromOrigin':sdelta,'scaleMatchesRelativeScreenGeometryWithin0.01Px':True,'otherNodeGeometryDifferences':others,'relevantSavedSvgPaths':edges},'pixelObservations':json.loads(a.observations),'pixelBodyMatch':'visible-body-position-size-direction-and-inspector-coordinates-match-public-geometry-at-screen-resolution','routeAssessment':a.route,'scope':{'AIOnly':True,'realHumanParticipantsAdded':0,'personallyViewedOriginalScreenshot':True,'browserOperatedByAuditor':False,'gestureExecutionIndependentlyObservedLive':False,'undoRedoCertifiedByPixelReview':False,'physicalPublicationCertified':False,'fullDiagramVisible':False,'pathOptimalityCertified':False},'limitations':['Original local screenshot is deliberately zoomed/panned; offscreen nodes and full page clipping cannot be assessed from it.','Position correspondence is visual at screenshot resolution, with numeric relative geometry from saved public DOM; no exact raster contour extraction is claimed.','Static after-input screenshots do not prove every native pointer event, presented frame, held cancellation, persistence or undo/redo.','AI audit cannot count as real human research acceptance.']}
q=OUT/(a.fixture+'-'+a.step+'.review.json')
with q.open('x') as f:json.dump(record,f,ensure_ascii=False,indent=2);f.write('\n')
print(json.dumps({'path':str(q),'sha256':sha(q)},ensure_ascii=False))
