#!/usr/bin/env python3
import json, sys
from pathlib import Path
from inspect_geometry import geometry, points, penetrates, rect, TOL

here=Path(__file__).resolve().parent; tag=sys.argv[1] if len(sys.argv)>1 else 'attempt-2'; out=here/tag
caption=json.loads((out/'caption-adversarial.json').read_text()); capResults=[]
for case in caption['cases']:
    result=geometry(case['scene']);result.update(name=case['name'],immutable=case['immutable'],deterministic=case['deterministic']);capResults.append(result)
router=json.loads((out/'router-adversarial.json').read_text()); routeResults=[]
for case in router['records']:
    scene={'bounds':{'x':-10000,'y':-10000,'width':100000,'height':100000},'nodes':case['nodes'],'annotations':[],'diagnostics':[],
           'edges':[{'id':str(i),'path':r['path'],'label':''} for i,r in enumerate(case['next'])]}
    old=dict(scene,edges=[{'id':str(i),'path':r['path'],'label':''} for i,r in enumerate(case['old'])])
    result=geometry(scene,old);result.update(name=case['name'],immutable=case['immutable'],deterministic=case['deterministic'])
    # Conservative output contract for pre-capped cases, compared to the prior
    # router's already obstacle-validated result rather than raw preferred path.
    if case['name'].startswith('over-') and case['old']!=case['next']:
        result['failures'].append({'kind':'precap-output-changed'})
    # Six-unit clearance is checked independently on newly shortened routes
    # and unrelated card/header obstacles; endpoint cards remain exempt only
    # for endpoint escapes. Existing generic/family behavior is not recertified.
    for i,(new,old) in enumerate(zip(case['next'],case['old'])):
        if new['path']==old['path']: continue
        poly=points(new['path']); req=case['requests'][i]
        ancestorIds=set()
        nodeMap={n['id']:n for n in case['nodes']}
        for endpoint in [req['sourceId'],req['targetId']]:
            at=nodeMap[endpoint].get('parentId')
            while at: ancestorIds.add(at);at=nodeMap[at].get('parentId')
        for n in case['nodes']:
            if n['id'] in [req['sourceId'],req['targetId']]:
                if len(poly)>3 and penetrates(poly[1:-1],rect(n,6)): result['failures'].append({'kind':'middle-endpoint-clearance','edge':i,'body':n['id']})
                continue
            if n['id'] in ancestorIds:
                n=dict(n,height=n['headerHeight'])
            variants=[n]+([dict(n,x=n['x']+s,y=n['y']+s) for s in [3.5,7]] if n.get('repeat') and not n['expanded'] else [])
            for variant in variants:
                if penetrates(poly,rect(variant,6)): result['failures'].append({'kind':'unrelated-clearance','edge':i,'body':n['id']})
    routeResults.append(result)
results=capResults+routeResults; failed=[{'case':r['name'],**f} for r in results for f in r['failures']]
report={'schema':'archcanvas-independent-caption-route-adversarial/1','tag':tag,'captionCases':len(capResults),'routerCases':len(routeResults),
        'immutable':all(r['immutable'] for r in results),'deterministic':all(r['deterministic'] for r in results),
        'failures':failed,'captionResults':capResults,'routerResults':routeResults,'humanParticipants':0}
(out/'adversarial-report.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({'tag':tag,'captionCases':len(capResults),'routerCases':len(routeResults),'immutable':report['immutable'],'deterministic':report['deterministic'],'failureCount':len(failed),'firstFailures':failed[:15]}))
