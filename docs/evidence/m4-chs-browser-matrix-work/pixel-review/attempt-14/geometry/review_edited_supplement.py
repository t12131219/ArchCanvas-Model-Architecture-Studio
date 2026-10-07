"""Edited declaration supplement only, read already-bound new cases/reports."""
from pathlib import Path
import hashlib,json,itertools,xml.etree.ElementTree as ET
OUT=Path(__file__).resolve().parent
BASE=OUT.parents[2]
paths=[BASE/'pixel-review/attempt-12/geometry/mlp-level1-paper-180-edited-source-geometry.json',BASE/'pixel-review/attempt-13/geometry/residual_cnn-level0-paper-180-edited-recapture1-source-geometry.json',OUT/'transformer-level0-paper-180-edited-source-geometry.json',OUT/'transformer-level0-paper-180-edited-annotation-baseline-review.json',OUT/'transformer-edited-preparse-bindings.json']
def bind(p):
 b=p.read_bytes();return {'path':str(p.resolve()),'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}
report_start=[bind(p) for p in paths]
raw_expected=json.loads(paths[-1].read_text())['inputBindingsStart'];raw_start=[bind(Path(x['path'])) for x in raw_expected];assert raw_start==raw_expected
case=BASE/'raw/transformer-level0-paper-180-edited';svg=ET.parse(case/'browser-scene.svg').getroot();saved=json.loads((case/'saved-envelope.json').read_text())['document']
notes=[]
for group in svg.iter():
 if 'data-annotation-id' not in group.attrib:continue
 a=next(x for x in saved['annotations'] if x['id']==group.attrib['data-annotation-id']);text=next(x for x in group if x.tag.endswith('text'));rect=next(x for x in group if x.tag.endswith('rect'))
 y=float(text.attrib['y']);lines=[]
 for t in text:
  if not t.tag.endswith('tspan'):continue
  y+=float(t.attrib.get('dy',0));lines.append({'text':''.join(t.itertext()),'x':float(t.attrib.get('x',text.attrib['x'])),'y':y})
 joined=' '.join(x['text'] for x in lines);concat=''.join(text.itertext());x0,y0,w,h=[float(rect.attrib[k]) for k in ['x','y','width','height']]
 notes.append({'id':a['id'],'savedExactText':a['text'],'publicTspanLines':lines,'rawItertextConcatenation':concat,'rawConcatenationEqualsSaved':concat==a['text'],'linesJoinedWithSingleSpace':joined,'lineJoinEqualsSaved':joined==a['text'],'allLineAnchorsInsideNominalRect':all(x0<=p['x']<=x0+w and y0<=p['y']<=y0+h for p in lines),'rawDomContainsConcatenatedLineToken':{p.name:concat in p.read_text() for p in sorted(case.glob('*.dom.txt'))},'interpretation':'Wrapping produces separate tspans. Raw itertext and DOM serialization concatenate their text without a delimiter; line-join with one space matches the saved sentence. This is a textual representation comparison, no proof of rendered glyph loss, clipping or readability.'})
def intersect(a,b,c,d):
 ah,ch=a[1]==b[1],c[1]==d[1]
 if ah==ch:
  if (a[1]!=c[1] if ah else a[0]!=c[0]):return None
  dim=0 if ah else 1;lo=max(min(a[dim],b[dim]),min(c[dim],d[dim]));hi=min(max(a[dim],b[dim]),max(c[dim],d[dim]))
  return None if lo>hi else {'type':'overlap' if lo<hi else 'touch','interval':[lo,hi]}
 h0,h1,v0,v1=(a,b,c,d) if ah else (c,d,a,b);p=[v0[0],h0[1]]
 return {'type':'cross-or-touch','point':p} if min(h0[0],h1[0])<=p[0]<=max(h0[0],h1[0]) and min(v0[1],v1[1])<=p[1]<=max(v0[1],v1[1]) else None
checks=[]
for p in paths[:3]:
 r=json.loads(p.read_text());rects={n['id']:n['mainRect'] for n in r['visibleNodes']};used={e['publicPort']['id']:e['publicPort'] for route in r['routes'] for e in route['endpoints'].values()};off=[]
 for port in used.values():
  rect=rects[port['sceneNodeId']];x,y=port['point'];x0,y0,w,h=[rect[k] for k in ['x','y','width','height']];on=((x==x0 or x==x0+w) and y0<=y<=y0+h) or ((y==y0 or y==y0+h) and x0<=x<=x0+w)
  if not on:off.append(port)
 self_hits=[]
 for route in r['routes']:
  segs=[(i,a,b) for i,(a,b) in enumerate(zip(route['points'],route['points'][1:])) if a!=b]
  for (i,a,b),(j,c,d) in itertools.combinations(segs,2):
   if j==i+1:continue
   hit=intersect(a,b,c,d)
   if hit:self_hits.append({'edgeId':route['id'],'segmentA':i,'segmentB':j,**hit})
 checks.append({'caseId':r['caseId'],'uniqueEndpointUsedPublicPorts':len(used),'offNominalFrontPerimeter':off,'nonadjacentSelfRouteSegmentContacts':self_hits})
r={'scope':'Append-only Transformer wrapped-note clarification and 3 edited route/port supplement; no baseline re-audit or pixels','inputReportBindingsStart':report_start,'rawTransformerBindingsStart':raw_start,'transformerNoteLineClarification':notes,'editedPortSelfRouteChecks':checks,'limits':['The original annotation report rawTextMatchesSaved=false remains correct for delimiter-free concat; this supplement records why single-space line join succeeds.','Port centers on nominal card perimeter and no self-route contacts do not prove clean inter-route rendering.','No images opened, glyph/font/stroke/marker extents, runtime/history/performance or human acceptance certified.']}
r['rawTransformerBindingsEnd']=[bind(Path(x['path'])) for x in raw_expected];r['rawTransformerInputsUnchanged']=raw_start==r['rawTransformerBindingsEnd'];r['inputReportBindingsEnd']=[bind(p) for p in paths];r['reportsUnchanged']=report_start==r['inputReportBindingsEnd'];p=OUT/'edited-note-lines-port-selfroute-supplement.json';assert not p.exists();p.write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'report':bind(p),'rawInputsUnchanged':r['rawTransformerInputsUnchanged'],'reportsUnchanged':r['reportsUnchanged'],'notes':notes,'checks':checks},ensure_ascii=False,indent=2))
