import json,re
from pathlib import Path
EPS=.051

def points(path):
 x=y=0;out=[]
 for c,a,b in re.findall(r'([MHV])\s*(-?[\d.]+)(?:\s+(-?[\d.]+))?',path):
  if c=='M':x=float(a);y=float(b)
  elif c=='H':x=float(a)
  else:y=float(a)
  if not out or abs(x-out[-1][0])>=EPS or abs(y-out[-1][1])>=EPS:out.append((x,y))
 return out

def segs(path):return [(a,b)for a,b in zip(points(path),points(path)[1:])]
def metric(a,b):
 cross=set(); contacts=set(); overlap=0
 for p,q in segs(a):
  for r,s in segs(b):
   av=abs(p[0]-q[0])<EPS;bv=abs(r[0]-s[0])<EPS
   if av==bv:
    if abs((p[0] if av else p[1])-(r[0] if av else r[1]))>=EPS:continue
    i=1 if av else 0; low=max(min(p[i],q[i]),min(r[i],s[i]));high=min(max(p[i],q[i]),max(r[i],s[i]))
    if high>low+EPS:overlap+=high-low
    elif high>=low-EPS:contacts.add((round((p[0] if av else low),2),round((low if av else p[1]),2)))
   else:
    v,w,h,k=(p,q,r,s) if av else (r,s,p,q);x,y=v[0],h[1]
    if x>=min(h[0],k[0])-EPS and x<=max(h[0],k[0])+EPS and y>=min(v[1],w[1])-EPS and y<=max(v[1],w[1])+EPS:
      strict=x>min(h[0],k[0])+EPS and x<max(h[0],k[0])-EPS and y>min(v[1],w[1])+EPS and y<max(v[1],w[1])-EPS
      (cross if strict else contacts).add((round(x,2),round(y,2)))
 return {'crossings':cross,'contacts':contacts,'overlap':round(overlap,5)}

before=Path('../routing-audit');after=Path('.')
changes=[];violations=[]
for bf in before.glob('*-level*-*.scene.json'):
 af=after/bf.name
 if not af.exists(): continue
 bs=json.load(open(bf));as_=json.load(open(af));be={e['id']:e for e in bs['edges']};ae={e['id']:e for e in as_['edges']}
 ids=sorted(set(be)&set(ae))
 for i,x in enumerate(ids):
  for y in ids[i+1:]:
   bm=metric(be[x]['path'],be[y]['path']);am=metric(ae[x]['path'],ae[y]['path'])
   # A newly introduced point contact or geometric overlap/crossing is a hard regression.
   for key in ('crossings','contacts'):
    added=am[key]-bm[key]
    if added: violations.append({'case':bf.stem,'pair':[x,y],'metric':key,'added':sorted(added)})
   if am['overlap']>bm['overlap']+EPS: violations.append({'case':bf.stem,'pair':[x,y],'metric':'overlap','before':bm['overlap'],'after':am['overlap']})
   if bm!=am: changes.append({'case':bf.stem,'pair':[x,y],'before':{k:(sorted(v) if isinstance(v,set) else v)for k,v in bm.items()},'after':{k:(sorted(v) if isinstance(v,set) else v)for k,v in am.items()}})
json.dump({'scenePairComparisons':len(changes),'violations':violations,'changes':changes},open('pair-comparison.json','w'),indent=2)
print('comparisons with geometry changes',len(changes),'violations',len(violations))
for x in violations[:20]:print(x)
for x in changes[:12]:print(x)
