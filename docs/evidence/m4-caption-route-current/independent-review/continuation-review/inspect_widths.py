#!/usr/bin/env python3
"""Independent visible-segment rectangle oracle, not product geometry.

Axis-aligned SVG butt-cap segments form exact nominal stroke rectangles.
At joints this is a minimum occupied region: overlap here is conclusive,
absence is not resolved-font, antialias, marker, full miter, or pixel proof.
"""
import json, math, sys
from pathlib import Path
BASE=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(BASE))
from inspect_geometry import points,segments,caption,body_rects
TOL=1e-7

def strokes(path,width):
 if not math.isfinite(width) or width<0: raise ValueError('uncertifiable width')
 result=[];radius=width/2
 for a,b in segments(points(path)):
  if a[0]==b[0]:result.append((a[0]-radius,min(a[1],b[1]),a[0]+radius,max(a[1],b[1])))
  else:result.append((min(a[0],b[0]),a[1]-radius,max(a[0],b[0]),a[1]+radius))
 return result

def intersection(a,b):
 x=min(a[2],b[2])-max(a[0],b[0]);y=min(a[3],b[3])-max(a[1],b[1])
 if x<-TOL or y<-TOL:return None
 return {'kind':'visible-stroke-overlap' if x>TOL and y>TOL else 'visible-stroke-contact','intersectionWidth':x,'intersectionHeight':y}

def inspect(scene):
 findings=[];guides=scene.get('captionGuides',[])
 for g in guides:
  occupied=strokes(g['path'],g['width'])
  for edge in scene['edges']:
   if edge['id']==g['sceneEdgeId']:continue
   for first in occupied:
    for second in strokes(edge['path'],edge['width']):
     hit=intersection(first,second)
     if hit:findings.append({'guide':g['id'],'foreignEdge':edge['id'],'guideWidth':g['width'],'foreignWidth':edge['width'],**hit});break
  for other in guides:
   if other['id']<=g['id']:continue
   for first in occupied:
    for second in strokes(other['path'],other['width']):
     hit=intersection(first,second)
     if hit:findings.append({'guide':g['id'],'otherGuide':other['id'],**hit});break
  for edge in scene['edges']:
   if not edge.get('label') or edge['id']==g['sceneEdgeId']:continue
   for first in occupied:
    hit=intersection(first,caption(edge))
    if hit and hit['kind']=='visible-stroke-overlap':findings.append({'guide':g['id'],'foreignCaption':edge['id'],'kind':'stroke-nominal-caption-overlap','intersectionWidth':hit['intersectionWidth'],'intersectionHeight':hit['intersectionHeight']})
  for bid,box in body_rects(scene):
   for first in occupied:
    hit=intersection(first,box)
    if hit and hit['kind']=='visible-stroke-overlap':findings.append({'guide':g['id'],'body':bid,'kind':'stroke-body-interior-overlap','intersectionWidth':hit['intersectionWidth'],'intersectionHeight':hit['intersectionHeight']})
 return findings

def main():
 tag=sys.argv[1];out=BASE/tag
 records=[]
 cap=json.loads((out/'capture.json').read_text())
 for row in cap['records']:
  scene=json.loads((out/(row['stem']+'.new.scene.json')).read_text());records.append({'case':row['stem'],'guides':len(scene.get('captionGuides',[])),'findings':inspect(scene)})
 adversarial=json.loads((out/'caption-adversarial.json').read_text())
 for row in adversarial['cases']:records.append({'case':row['name'],'guides':len(row['scene'].get('captionGuides',[])),'findings':inspect(row['scene'])})
 foreignPath=out/'foreign-stroke-capture.json'
 foreign=json.loads(foreignPath.read_text()) if foreignPath.exists() else None
 if foreign:
  for row in foreign['cases']:records.append({'case':row['name'],'guides':len(row['scene'].get('captionGuides',[])),'findings':inspect(row['scene'])})
 report={'schema':'archcanvas-independent-stroke-rectangles/1','tag':tag,'records':records,'findings':[{'case':r['case'],**f} for r in records for f in r['findings']],
  'invalidWidthHonesty':None if foreign is None else all(r['honest'] and r['inputWidthPreserved'] for r in foreign['invalid']),
  'limits':['Nominal exact butt-cap segment rectangles; joins/markers/antialias/font glyphs not certified','No source model execution','No human or physical publication approval','No timing or presented FPS proof']}
 (out/'width-report.json').write_text(json.dumps(report,indent=2)+'\n')
 print(json.dumps({'cases':len(records),'guides':sum(r['guides'] for r in records),'findingCount':len(report['findings']),'firstFindings':report['findings'][:8]}))
if __name__=='__main__':main()
