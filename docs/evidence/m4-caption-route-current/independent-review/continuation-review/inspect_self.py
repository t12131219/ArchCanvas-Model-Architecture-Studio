#!/usr/bin/env python3
import json,sys
from pathlib import Path
BASE=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(BASE))
from inspect_geometry import points,segments,pair,introduced

def selfGeometry(poly):
 contacts=set();crossings=set();overlaps={};lines=segments(poly)
 for i,first in enumerate(lines):
  for second in lines[i+2:]:
   hit=pair(list(first),list(second));contacts.update(hit['contacts']);crossings.update(hit['crossings'])
   for axis,ranges in hit['overlaps'].items():overlaps.setdefault(axis,[]).extend(ranges)
 for axis,ranges in list(overlaps.items()):
  union=[]
  for lo,hi in sorted(ranges):
   if union and lo<=union[-1][1]+1e-7:union[-1][1]=max(hi,union[-1][1])
   else:union.append([lo,hi])
  overlaps[axis]=union
 return {'contacts':contacts,'crossings':crossings,'overlaps':overlaps}

def summary(geo):return {'contactPoints':sorted(geo['contacts']),'properCrossings':sorted(geo['crossings']),'overlapIntervals':[{'axis':axis,'intervals':vals} for axis,vals in geo['overlaps'].items()]}

def main():
 tag=sys.argv[1];out=BASE/tag;records=[]
 capture=json.loads((out/'capture.json').read_text())
 for row in capture['records']:
  stem=row['stem'];a=json.loads((out/(stem+'.old.scene.json')).read_text());b=json.loads((out/(stem+'.new.scene.json')).read_text());old={e['id']:e for e in a['edges']}
  for e in b['edges']:
   if e['path']==old[e['id']]['path']:continue
   first=selfGeometry(points(old[e['id']]['path']));second=selfGeometry(points(e['path']));records.append({'case':stem,'edge':e['id'],'before':summary(first),'after':summary(second),'introduced':introduced(second,first)})
 router=json.loads((out/'router-adversarial.json').read_text())
 for row in router['records']:
  for i,(a,b) in enumerate(zip(row['old'],row['next'])):
   if a['path']==b['path']:continue
   first=selfGeometry(points(a['path']));second=selfGeometry(points(b['path']));records.append({'case':row['name'],'edge':i,'before':summary(first),'after':summary(second),'introduced':introduced(second,first)})
 counter=json.loads((out/'self-counterexample.json').read_text());counterResults=[]
 for row in counter['records']:
  first=selfGeometry(points(row['old'][0]['path']));second=selfGeometry(points(row['next'][0]['path']));counterResults.append({'case':row['name'],'before':summary(first),'after':summary(second),'beforePath':row['old'][0]['path'],'afterPath':row['next'][0]['path'],'immutable':row['immutable'],'deterministic':row['deterministic']})
 failures=[{'case':r['case'],'edge':r['edge'],**f} for r in records for f in r['introduced']]
 unsafeCounterAfter=[r for r in counterResults if r['after']['contactPoints'] or r['after']['overlapIntervals']]
 report={'schema':'archcanvas-independent-nonadjacent-self-geometry/1','tag':tag,'changedRouteOccurrences':len(records),'failures':failures,'counterexampleCases':counterResults,'unsafeCounterexampleAfter':unsafeCounterAfter,'records':records,'limits':['Finite matrix and adversarial cases; no universal safety proof','Nonadjacent segments exclude ordinary bend joints','No source execution, physical approval or timing proof']}
 (out/'self-geometry-report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({'changedRouteOccurrences':len(records),'introducedFailures':len(failures),'counterexampleCases':len(counterResults),'unsafeCounterexampleAfter':len(unsafeCounterAfter)}))
if __name__=='__main__':main()
