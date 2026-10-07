"""Read-only reconstruction of public router candidate bounds, not an oracle."""
from pathlib import Path
import json
from explore_candidates import scene, points, pair, bodies

work = Path(__file__).resolve().parent
pressure = {}; overlap = {}
for edge in scene['edges']: pressure[edge['id']] = overlap[edge['id']] = 0
for i, a in enumerate(scene['edges']):
    for b in scene['edges'][i+1:]:
        if a['tensorId'] == b['tensorId']: continue
        metric = pair(points(a['path']), points(b['path']))
        for edge in [a,b]:
            pressure[edge['id']] += metric['crossingPoints'] + metric['overlapPairs']
            overlap[edge['id']] += metric['overlapLength']
order = sorted([e for e in scene['edges'] if pressure[e['id']]], key=lambda e:(-pressure[e['id']],-overlap[e['id']],scene['edges'].index(e)))
records=[]
for id, target in [('edge:44',468),('edge:58',520)]:
    edge=next(e for e in scene['edges'] if e['id']==id); anchors=[p[0] for p in points(edge['path'])]; values=set()
    for x in anchors:
        for d in [0,-8,8,-16,16]: values.add(round(x+d,2))
    for node in scene['nodes']:
        for left,top,right,bottom in bodies(node):
            for d in [6,14,22]: values.add(round(left-d,2));values.add(round(right+d,2))
    ranked=sorted(values,key=lambda x:(min(abs(x-a) for a in anchors),x))
    records.append({'edgeId':id,'pressureRank1Based':order.index(edge)+1,'pressure':pressure[id],'overlapPressure':overlap[id],
      'desiredExistingGeometryLane':target,'laneCandidateRank1Based':ranked.index(target)+1 if target in ranked else None,
      'lanePresentInFirst24':target in ranked[:24],'first24X':ranked[:24]})
report={'scope':'Router candidate-generation gap reconstruction; no live instrumentation or performance claim','conflictedRouteOrder':[e['id'] for e in order],'selectedRoutes':records,'maxRefinedRoutes':8,'maxAxisCoordinates':24}
(work/'router-candidate-gap.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report))
