#!/usr/bin/env python3
"""Read-only independent candidate review of the BTw memory caption."""
from pathlib import Path
import hashlib
import importlib.util
import json
import math

ROOT = Path(__file__).resolve().parents[5]
OUT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('independent_geometry', OUT.parent/'inspect_geometry.py')
geometry = importlib.util.module_from_spec(spec)
spec.loader.exec_module(geometry)

def binding(path):
    raw=path.read_bytes()
    return {'path':str(path.relative_to(ROOT)),'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}

def box(point):
    return (point[0]-2,point[1]-11,point[0]+56,point[1]+5)

def rectangle_distance(rect, points):
    l,t,r,b=rect
    values=[]
    for a,c in geometry.segments(points):
        sl,sr=sorted((a[0],c[0]));st,sb=sorted((a[1],c[1]))
        dx=max(l-sr,sl-r,0);dy=max(t-sb,st-b,0)
        values.append(math.hypot(dx,dy))
    return min(values)

def conflicts(rect,scene,edge):
    l,t,r,b=rect
    bodies=[]
    for node in scene['nodes']:
        rectangles=[(node['x'],node['y'],node['x']+node['width'],node['y']+node['headerHeight'])] if node['expanded'] else geometry.rects(node)
        if any(min(r,u)>max(l,x) and min(b,v)>max(t,y) for x,y,u,v in rectangles):bodies.append(node['id'])
    routes=[]
    for other in scene['edges']:
        if other['id']!=edge['id'] and any(geometry.hit_segment(segment,rect) for segment in geometry.segments(geometry.parse(other['path']))):routes.append(other['id'])
    return bodies,routes

def main():
    receipt_path=ROOT/'docs/evidence/m4-performance-next-current/checks-final-attempt-2/receipt.json'
    receipt=json.loads(receipt_path.read_text());entries=receipt['inputs']+receipt['build']
    assert all(binding(ROOT/r['path'])['sha256']==r['sha256']for r in entries)
    scene_path=OUT.parent/'fresh-source-core/transformer-level0-paper-180.scene.json'
    current_path=OUT.parent/'label-after/overview.scene.json'
    scene=json.loads(scene_path.read_text());current=json.loads(current_path.read_text())
    old=next(e for e in scene['edges']if e.get('label')=='memory')
    fixed=next(e for e in current['edges']if e['id']==old['id'])
    origin=(old['labelX'],old['labelY']);owned=geometry.parse(old['path']);route_y=owned[0][1]
    offsets=list(range(-64,65,8))
    candidates={(round(origin[0]+dx,2),round(origin[1]+dy,2))for dx in offsets for dy in offsets}
    center=((owned[0][0]+owned[-1][0])/2,(owned[0][1]+owned[-1][1])/2)
    candidates.update([(center[0]-27,center[1]-7),(center[0]-27,center[1]+17)])
    records=[]
    for point in sorted(candidates):
        rect=box(point);bodies,routes=conflicts(rect,scene,old)
        records.append({'point':point,'nominalRect':rect,'bodyConflicts':bodies,'otherRouteConflicts':routes,
                        'clear':not bodies and not routes,'originalAnchorDistance':math.dist(origin,point),
                        'baselineVerticalDistanceFromOwnRoute':abs(point[1]-route_y),'nominalBodyDistanceFromOwnRoute':rectangle_distance(rect,owned)})
    clear=[r for r in records if r['clear']]
    baseline_rank=sorted(clear,key=lambda r:(r['baselineVerticalDistanceFromOwnRoute'],r['originalAnchorDistance'],r['point']))
    body_rank=sorted(clear,key=lambda r:(r['nominalBodyDistanceFromOwnRoute'],r['originalAnchorDistance'],r['point']))
    chosen=next(r for r in records if tuple(r['point'])==(fixed['labelX'],fixed['labelY']))
    nearest=baseline_rank[0]
    assert chosen['point']==(280.5,388.1)
    assert nearest['point']==(280.5,492.1)
    assert nearest['baselineVerticalDistanceFromOwnRoute']==48 and chosen['baselineVerticalDistanceFromOwnRoute']==56
    assert len(clear)==24
    report={'schema':'archcanvas-readonly-caption-association-candidates/1','humanParticipants':0,'modelExecuted':False,
      'productModified':False,'currentBuild':'index-BTw7OHsD.js','currentSourceAndBuildBindingsChecked':len(entries),
      'receiptBinding':binding(receipt_path),'sceneBinding':binding(scene_path),'currentLabelBinding':binding(current_path),
      'browserInputs':[binding(ROOT/('docs/evidence/m4-performance-next-current/final-browser/'+name))for name in ['04-transformer-local-100-settled.jpg','04-transformer-local-100-settled.json','memory-local-100.json']],
      'fontEnvelope':'Independent 6×9 nominal width plus 2px each side, ascent11/descent5; not resolved-font metrics.',
      'origin':origin,'ownedPath':old['path'],'ownedRouteY':route_y,'candidates':len(records),'clearCandidates':len(clear),
      'current':chosen,'nearestBaselineCandidate':nearest,'nearestBodyCandidate':body_rank[0],'records':records,
      'geometricLowerBound':{'repeatRight':281,'targetLeft':316,'gapWidth':35,'nominalCaptionWidth':58,
          'nearestLowerBaseline':490,'minimumLowerBaselineDistance':45.9,'maximumUpperBaselineAboveMaskRoute':392,
          'minimumUpperBaselineDistance':52.1,'scope':'Within the current 64-unit x search rectangle all caption envelopes intersect one endpoint card while vertically beside y444.1. Below both cards requires nominal top≥479, hence baseline≥490; above cards and the y397 mask routes requires nominal bottom≤397, hence baseline≤392. Strict positive clearance raises these limiting thresholds.'},
      'recommendation':'Ranking by owned-route proximity selects the lower candidate but improves baseline distance by only 8 units and still leaves an unlinked caption 48 units away. Do not claim this alone resolves association. Prefer an explicit association-distance diagnostic or a separately implemented leader/precise-font contract over changing only tie-break ranking.',
      'limitations':['No new screenshot was taken; root BTw settled screenshot personally inspected read-only.','Candidate enumeration reproduces the current helper candidate domain independently; it is not a global search.','A nominal clear candidate is not current-browser glyph certification.','Old frozen 172-file review and source code were not changed.']}
    (OUT/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'candidates':len(records),'clear':len(clear),'current':chosen['point'],'closest':nearest['point'],'baselineDistances':[chosen['baselineVerticalDistanceFromOwnRoute'],nearest['baselineVerticalDistanceFromOwnRoute']],'bodyDistances':[chosen['nominalBodyDistanceFromOwnRoute'],body_rank[0]['nominalBodyDistanceFromOwnRoute']]}))

if __name__=='__main__':main()
