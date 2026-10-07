"""Literal final route deltas, bodies, peer contacts, self contacts and normals.

No product imports. Coordinate changes remain enumerated; stripping display
port coordinates from a semantic comparison never silently approves geometry.
"""
from __future__ import annotations
from argparse import ArgumentParser
from datetime import datetime,timezone
import hashlib,json,math,sys
from pathlib import Path
sys.dont_write_bytecode=True
from audit_matrix import load,points,body_boxes,enters,on,pair_contacts,self_contacts,semantic_projection,EPS
HERE=Path(__file__).resolve().parent

def length(route):return sum(abs(a[0]-b[0])+abs(a[1]-b[1])for a,b in zip(route,route[1:]))
def port_key(p):return json.dumps({k:v for k,v in p.items()if k not in ['id','x','y']},sort_keys=True)
def intervals_subset(new,old):
 for axis,fixed,lo,hi in new:
  spans=sorted((a,b)for direction,where,a,b in old if direction==axis and abs(where-fixed)<EPS and b>=lo and a<=hi)
  reach=lo
  for a,b in spans:
   if a>reach+EPS:break
   reach=max(reach,b)
  if reach<hi-EPS:return False
 return True
def normals(scene,edge):
 route=points(edge['path']);result=[]
 for end,node_id,position,near in [('source',edge['sourceId'],route[0],route[1]),('target',edge['targetId'],route[-1],route[-2])]:
  node=next(n for n in scene['nodes']if n['id']==node_id)
  candidates=[p for p in node['ports']if set(edge['canonicalEdgeIds']).issubset(p['canonicalEdgeIds'])and math.dist((p['x'],p['y']),position)<.075]
  if len(candidates)!=1:
   result.append({'end':end,'issue':'unresolved-public-port','candidates':len(candidates)});continue
  port=candidates[0];side='right'if port['id'].endswith(':right')else'left'if port['id'].endswith(':left')else'bottom'if end=='source'else'top'
  expected={'right':(1,0),'left':(-1,0),'bottom':(0,1),'top':(0,-1)}[side]
  outside=(near[0]-position[0],near[1]-position[1])
  if not(abs(outside[1 if expected[0]else 0])<EPS and outside[0 if expected[0]else 1]*expected[0 if expected[0]else 1]>EPS):result.append({'end':end,'side':side,'issue':'endpoint-not-outward-normal','port':position,'neighbor':near})
 return result
def shared_endpoint_contact(scene,a,b,p):
 ar=points(a['path']);br=points(b['path'])
 return any(na==nb and math.dist(p,pa)<EPS and math.dist(p,pb)<EPS for na,pa in [(a['sourceId'],ar[0]),(a['targetId'],ar[-1])]for nb,pb in [(b['sourceId'],br[0]),(b['targetId'],br[-1])])
def common_binding(a,b):
 return a['source']==b['source']and a['tensorId']==b['tensorId']and a['role']==b['role']and all(a[k]==b[k]for k in ['stroke','width','dashed'])
def reversals(route):
 result=[]
 for a,b,c in zip(route,route[1:],route[2:]):
  first=(b[0]-a[0],b[1]-a[1]);second=(c[0]-b[0],c[1]-b[1])
  if first[0]*second[0]+first[1]*second[1]<-EPS:result.append([a,b,c])
 return result

def main():
 p=ArgumentParser();p.add_argument('--suite',choices=['matrix','port-gap','side-gap'],required=True);p.add_argument('--tag',choices=['before','label-only','after'],required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 assert not a.output.exists();a.output.mkdir(parents=True)
 prefix=''if a.suite=='matrix'else'gap-'if a.suite=='port-gap'else'side-gap-'
 capture=load(HERE/f'{prefix}{a.tag}/capture.json');prior=load(HERE/f'{prefix}before/capture.json');old={r['stem']:r for r in prior['sceneRecords']}
 checks=[];changes=[];port_changes=[];peer_changes=[];memory_normals=[];unwarned=[]
 def check(name,value):checks.append({'name':name,'passed':bool(value)})
 for record in capture['sceneRecords']:
  case=record['stem'];scene=load(HERE/record['sceneBinding']['path']);was=load(HERE/old[case]['sceneBinding']['path']);edge_map={e['id']:e for e in scene['edges']};was_map={e['id']:e for e in was['edges']}
  check('semantic facts canonical bindings exact '+case,semantic_projection(scene)==semantic_projection(was))
  for node,oldnode in zip(scene['nodes'],was['nodes']):
   oldports={port_key(p):p for p in oldnode['ports']};newports={port_key(p):p for p in node['ports']}
   check('canonical port inventory exact '+case+'/'+node['id'],oldports.keys()==newports.keys())
   for key,port in newports.items():
    previous=oldports[key]
    if all(port[k]==previous[k]for k in ['id','x','y']):continue
    port_changes.append({'case':case,'nodeId':node['id'],'canonicalEdgeIds':port['canonicalEdgeIds'],'before':{k:previous[k]for k in ['id','x','y']},'after':{k:port[k]for k in ['id','x','y']}})
  for e in scene['edges']:
   path=points(e['path']);oldedge=was_map[e['id']];oldpath=points(oldedge['path']);warnings=[d for d in scene['diagnostics']if d.get('edgeId')==e['id']];blocked=any(d.get('code')=='layout-route-blocked'for d in warnings)
   if e['role']=='memory':
    issues=normals(scene,e)
    if issues:memory_normals.append({'case':case,'edgeId':e['id'],'issues':issues,'blockedWarning':blocked,'path':e['path']})
    check('memory endpoint normals valid or blocked '+case+'/'+e['id'],not issues or blocked)
   if e['path']==oldedge['path']:continue
   oldself,oldoverlap=self_contacts(oldpath);newself,newoverlap=self_contacts(path);oldreverse=reversals(oldpath);newreverse=reversals(path)
   bodies=sorted({identity for identity,b in body_boxes(scene)for segment in zip(path,path[1:])if enters(segment,b)})
   oldbodies=sorted({identity for identity,b in body_boxes(was)for segment in zip(oldpath,oldpath[1:])if enters(segment,b)})
   new_body=set(bodies)-set(oldbodies)
   check('changed route new body penetration explicitly blocked '+case+'/'+e['id'],not new_body or blocked)
   no_new_self=not(newself-oldself)and intervals_subset(newoverlap,oldoverlap)and all(r in oldreverse for r in newreverse)
   check('changed route no new self contact overlap reverse '+case+'/'+e['id'],no_new_self or blocked)
   if (new_body or not no_new_self)and not blocked:unwarned.append({'case':case,'edgeId':e['id'],'newBody':sorted(new_body),'newSelf':sorted(newself-oldself),'newOverlap':newoverlap,'newReversals':newreverse})
   changes.append({'case':case,'edgeId':e['id'],'role':e['role'],'beforePath':oldedge['path'],'afterPath':e['path'],'beforeLength':length(oldpath),'afterLength':length(path),'beforeBends':len(oldpath)-2,'afterBends':len(path)-2,'endpointsBefore':[oldpath[0],oldpath[-1]],'endpointsAfter':[path[0],path[-1]],'bodyIntrusionsBefore':oldbodies,'bodyIntrusionsAfter':bodies,'newBodyIntrusions':sorted(new_body),'newSelfContacts':sorted(newself-oldself),'selfOverlapsBefore':oldoverlap,'selfOverlapsAfter':newoverlap,'newReversals':newreverse,'blockedWarning':blocked,'warnings':warnings})
  ids=list(edge_map)
  for i,identity in enumerate(ids):
   first=edge_map[identity];first_old=was_map[identity]
   for other_id in ids[i+1:]:
    second=edge_map[other_id];second_old=was_map[other_id]
    if first['path']==first_old['path']and second['path']==second_old['path']:continue
    oldcontact,oldoverlap=pair_contacts(points(first_old['path']),points(second_old['path']));newcontact,newoverlap=pair_contacts(points(first['path']),points(second['path']))
    added=newcontact-oldcontact
    extra=[pos for pos in sorted(added)if not shared_endpoint_contact(scene,first,second,pos)]
    trunk=common_binding(first,second);extra_overlap=not intervals_subset(newoverlap,oldoverlap)
    blocked=any(d.get('edgeId')in [identity,other_id]and d.get('code')=='layout-route-blocked'for d in scene['diagnostics'])
    if added or extra_overlap:peer_changes.append({'case':case,'edgeIds':[identity,other_id],'newContacts':sorted(added),'newNonEndpointContacts':extra,'overlapsBefore':oldoverlap,'overlapsAfter':newoverlap,'extraOverlap':extra_overlap,'commonCanonicalSourceTensorStyle':trunk,'blockedWarning':blocked})
    check('changed pair no new unrelated peer contact '+case+'/'+identity+'/'+other_id,trunk or(not extra and not extra_overlap)or blocked)
 report={'schema':'archcanvas-literal-route-delta-review/1','tag':a.tag,'suite':a.suite,'createdUtc':datetime.now(timezone.utc).isoformat(),'passed':sum(c['passed']for c in checks),'total':len(checks),'checks':checks,'failedChecks':[c for c in checks if not c['passed']],'changedRoutes':changes,'changedDisplayPorts':port_changes,'changedPeerContacts':peer_changes,'memoryNormalIssues':memory_normals,'unwarnedBodyOrSelfFailures':unwarned,'sourceModels':1,'scenes':len(capture['sceneRecords']),
 'scope':'One source-backed Transformer, finite detached inputs. Exact changed path and display-circle inventory; literal nominal body, centreline peer/self contacts and port normals. A blocked diagnostic reports a limitation, never proves aesthetic quality. Existing failures preserved. No product geometry helper imports, browser input, model execution, font, physical publication, global minimum route or performance approval.'}
 (a.output/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'tag':a.tag,'suite':a.suite,'passed':report['passed'],'total':report['total'],'changedRoutes':len(changes),'changedPorts':len(port_changes),'peerChanges':len(peer_changes),'memoryNormalIssues':len(memory_normals),'unwarnedBodySelfFailures':len(unwarned)}));raise SystemExit(0 if report['passed']==report['total']else 1)
if __name__=='__main__':main()
