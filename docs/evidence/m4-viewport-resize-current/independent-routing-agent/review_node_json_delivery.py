"""Finite native-gesture DOM/SVG readback, not browser paint certification."""
from pathlib import Path
import copy, datetime, hashlib, json, re, xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[4]
STAGE=ROOT/'docs/evidence/m4-viewport-resize-current'
OUT=STAGE/'independent-routing-agent/browser-node-readback-attempt-4'
if OUT.exists(): raise SystemExit('Append-only: output exists')
OUT.mkdir()
paths=sorted(p for p in (STAGE/'browser').glob('*.json') if p.name.split('-')[0].isdigit() and 27<=int(p.name.split('-')[0])<=36)
checks=[];rows=[];samples=[];data={};ns={'s':'http://www.w3.org/2000/svg'}
def bind(p):
 b=p.read_bytes();return {'path':p.relative_to(ROOT).as_posix(),'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}
def check(name,passed,**details):checks.append({'name':name,'passed':bool(passed),**details})
def near(a,b):return abs(a-b)<=1e-6
for p in paths:
 x=json.loads(p.read_text());number=int(p.name.split('-')[0]);rows.append(bind(p));metadata=json.loads(x['metadata']);svg=ET.fromstring(x['svg']);embedded=json.loads(svg.find('s:metadata',ns).text)
 check(p.name+' public/embedded metadata exact',metadata==embedded)
 nodes={};ports={};edge_paths={}
 for g in svg.findall('.//s:g',ns):
  if 'data-node-id' in g.attrib and 'data-canonical-id' in g.attrib:
   # A container may have repeat backing/header rects before its body. The
   # first rect still tracks its stable24world displacement; all rects enter
   # the exact undo comparison independently below.
   rects=[dict(r.attrib) for r in g.findall('s:rect',ns)];nodes[g.attrib['data-node-id']]=rects
  if 'data-port-id' in g.attrib:
   c=g.find('s:circle',ns);ports[g.attrib['data-port-id']]={'x':float(c.attrib['cx']),'y':float(c.attrib['cy'])}
  if 'data-edge-id' in g.attrib:
   route=g.find('s:path',ns);text=g.find('s:text',ns);edge_paths[g.attrib['data-edge-id']]={'path':route.attrib.get('d'),'label':text.text if text is not None else None}
 prepaper=x['paper'];post=x['afterScreenshot'];paper=re.search(r'translate\(([-.\d]+)px, ([-.\d]+)px\) scale\(([-.\d]+)\)',prepaper);camera=tuple(map(float,paper.groups()))
 check(p.name+' current geometry stable across screenshot capture fields',all(x[k]==post[k] for k in ['paper','viewport','footer']) and x['publicDomStableAcrossScreenshot'] is True)
 check(p.name+' camera mapping unchanged(-14,-49.5,1)',camera==(-14,-49.5,1))
 check(p.name+' default memory caption present in public SVG',edge_paths['edge:44']['label']=='memory')
 check(p.name+' SVG/metadata revision exact',str(metadata['revision'])==svg.attrib['data-revision'])
 record={'file':p.name,'revision':metadata['revision'],'encoderBackingRect':nodes['repeat:instance:model.Transformer.encoder'][0],
         'memory':edge_paths['edge:44'],'portCount':len(ports),'camera':camera,'publicDomStableAcrossScreenshot':True}
 samples.append(record);data[number]={'raw':x,'meta':metadata,'svg':svg,'nodes':nodes,'ports':ports,'paths':edge_paths}
 image=p.with_suffix('.jpg')
 if image.exists():rows.append(bind(image))
base=data[27]
for n,actual in data.items():
 check(str(n)+' canonical source facts unchanged',actual['meta']['sourceFacts']==base['meta']['sourceFacts'] and actual['meta']['sourceDigest']==base['meta']['sourceDigest'] and actual['meta']['irDigest']==base['meta']['irDigest'])
 check(str(n)+' canonical rendered bindings unchanged',actual['meta']['renderedBindings']==base['meta']['renderedBindings'])
 check(str(n)+' rendered identity list unchanged',actual['meta']['renderedNodes']==base['meta']['renderedNodes'])
 normalize_ports=lambda ports:{re.sub(r':memory:(?:left|right)$',':memory',pid) for pid in ports}
 check(str(n)+' canonical display port keys preserved excluding known orientation suffix',normalize_ports(actual['ports'])==normalize_ports(base['ports']))
for n,dx,dy in [(28,0,24),(30,0,-24),(32,-24,0),(34,24,0)]:
 actual=data[n];r=actual['nodes']['repeat:instance:model.Transformer.encoder'][0];b=base['nodes']['repeat:instance:model.Transformer.encoder'][0]
 check(str(n)+' one native24world direction',near(float(r['x'])-float(b['x']),dx) and near(float(r['y'])-float(b['y']),dy))
 check(str(n)+' unrelated node rects exact',all(actual['nodes'][node]==rects for node,rects in base['nodes'].items() if node!='repeat:instance:model.Transformer.encoder'))
 check(str(n)+' revision is one edit after preceding undo',actual['meta']['revision']==31+(n-27))
 # Orthogonal SVG route endpoints are drawn against the current visible
 # port coordinates. Parse only the actual M/H/V form; curve routing is not
 # silently flattened into an assumed endpoint.
 route=actual['paths']['edge:44']['path'];tokens=re.findall(r'[MHV]|[-+]?\d+(?:\.\d+)?',route);pos=0;x=y=None;start=None
 while pos<len(tokens):
  c=tokens[pos];pos+=1
  if c=='M':x=float(tokens[pos]);y=float(tokens[pos+1]);pos+=2;start=(x,y)
  elif c=='H':x=float(tokens[pos]);pos+=1
  elif c=='V':y=float(tokens[pos]);pos+=1
  else:raise ValueError('Unsupported current route: '+route)
 source=[pt for pid,pt in actual['ports'].items() if pid.startswith('call:instance:model.Transformer.encoder.1.feedforward_norm:') and ':memory' in pid]
 target=[pt for pid,pt in actual['ports'].items() if pid.startswith('call:instance:model.Transformer.decoder:') and ':in:memory:memory' in pid]
 check(str(n)+' memory start at current emitted port',len(source)==1 and near(start[0],source[0]['x']) and near(start[1],source[0]['y']))
 check(str(n)+' memory end at current emitted port',len(target)==1 and near(x,target[0]['x']) and near(y,target[0]['y']))
for n in [29,31,33,35,36]:
 actual=data[n]
 check(str(n)+' undo/saved restores all visible node rects exact',actual['nodes']==base['nodes'])
 check(str(n)+' undo/saved restores all visible ports exact',actual['ports']==base['ports'])
 check(str(n)+' undo/saved restores all route paths and labels exact',actual['paths']==base['paths'])
 # Normalize only revision in root and embedded metadata; preserve every
 # other element, attribute, text and presentation byte for the tree oracle.
 tree=copy.deepcopy(actual['svg']);tree.attrib['data-revision']='31';m=json.loads(tree.find('s:metadata',ns).text);m['revision']=31;tree.find('s:metadata',ns).text=json.dumps(m,separators=(',',':'),ensure_ascii=False)
 b=copy.deepcopy(base['svg']);m=json.loads(b.find('s:metadata',ns).text);b.find('s:metadata',ns).text=json.dumps(m,separators=(',',':'),ensure_ascii=False)
 check(str(n)+' undo/saved whole SVG tree exact except revision',ET.tostring(tree)==ET.tostring(b))
saved=STAGE/'saved-readback/saved-rev39-envelope.json';envelope=json.loads(saved.read_text());rows.append(bind(saved));doc=envelope['document'];seed_path=STAGE/'before-change/inputs/docs/evidence/m4-caption-stability-current/checks-final-attempt-2/receipt.json'
# Runtime seed is a separate artifact: prove storage/version and onlyrevision
# document difference against the currently immutable runtime seed receipt's
# named source envelope, when root supplies the source archive.
check('saved envelope distinguishes storage6 from canvas39',envelope['revision']==6 and doc['revision']==39)
check('saved document/source/IR identities match publicDOM39',doc['id']==data[36]['meta']['documentId'] and doc['sourceBindingDigest']==data[36]['meta']['sourceDigest'] and doc['architecture']['irDigest']==data[36]['meta']['irDigest'])
check('saved actual memory binding canonical44/55/56 unchanged',data[36]['meta']['renderedBindings']==base['meta']['renderedBindings'])
seed_receipt=STAGE/'runtime-seed-receipt.json';seed=json.loads(seed_receipt.read_text());rows.append(bind(seed_receipt));source_path=ROOT/seed['source'];source_envelope=json.loads(source_path.read_text());rows.append(bind(source_path))
check('seed31 envelope hash exact against seed receipt',bind(source_path)['sha256']==seed['sha256'])
newdoc=copy.deepcopy(doc);newdoc['revision']=31
check('saved39 only canvas revision changes against byte-bound31 document',newdoc==source_envelope['document'])
reopen_records=[]
for number in [37,38,42,43]:
 p=next((STAGE/'browser').glob(str(number)+'*.json'));raw=json.loads(p.read_text());rows.append(bind(p));image=p.with_suffix('.jpg');rows.append(bind(image));m=json.loads(raw['metadata']);svg=ET.fromstring(raw['svg'])
 check(str(number)+' revision39 same canonical facts and rendered bindings',m['revision']==39 and m['sourceFacts']==data[36]['meta']['sourceFacts'] and m['renderedBindings']==data[36]['meta']['renderedBindings'])
 check(str(number)+' same saved39 sceneSVG exact',raw['svg']==data[36]['raw']['svg'])
 observed_stability=all(raw[k]==raw['afterScreenshot'][k] for k in ['paper','viewport','footer'])
 check(str(number)+' recorded pre/post publicDOM stability flag accurate',observed_stability==raw['publicDomStableAcrossScreenshot'])
 coords=[]
 for sample in [raw,raw['afterScreenshot']]:
  t=re.search(r'translate\(([-.\d]+)px, ([-.\d]+)px\) scale\(([-.\d]+)\)',sample['paper']);px,py,z=map(float,t.groups());size=sample['viewport'];coords.append({'translation':{'x':px,'y':py},'zoom':z,'center':{'x':(size['width']/2-px)/z,'y':(size['height']/2-py)/z}})
 if number in [37,38]:check(str(number)+' stable reopen eventually restores350405',near(coords[1]['center']['x'],350) and near(coords[1]['center']['y'],405) and coords[1]['zoom']==1)
 if number in [42,43]:
  # Derive fit directly from saved SVG dimensions and public viewport size.
  vb=list(map(float,svg.attrib['viewBox'].split()));width,height=vb[2:];v=raw['viewport'];expected=min((v['width']-96)/width,(v['height']-92)/height,1.2);left=v['width']/2-width*expected/2;top=v['height']/2-height*expected/2
  check(str(number)+' explicit fit matches independent bounds equation withinCSSrounding',abs(coords[0]['zoom']-expected)<=5e-7 and abs(coords[0]['translation']['x']-left)<=.001 and abs(coords[0]['translation']['y']-top)<=.001)
  check(str(number)+' explicit fit preserves whole paper margins',coords[0]['translation']['x']>=47.99 and coords[0]['translation']['y']>=45.99 and v['width']-coords[0]['translation']['x']-width*coords[0]['zoom']>=47.99 and v['height']-coords[0]['translation']['y']-height*coords[0]['zoom']>=45.99)
 reopen_records.append({'sampleNumber':number,'file':p.name,'pre':coords[0],'post':coords[1],'publicDomStableAcrossScreenshot':observed_stability})
check('all bounded input bytes unchanged during readback',rows==[bind(ROOT/r['path']) for r in rows])
report={'schema':'archcanvas-independent-browser-node-four-directions-readback/1','createdUtc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'passed':sum(x['passed'] for x in checks),'total':len(checks),'checks':checks,'samples':samples,'priorAudit':{'path':'browser-node-readback-final/report.json','passed':132,'total':134,'reason':'The initial oracle expected exact display port IDs during vertical moves. Their memory:left/right suffix correctly reflects changing display orientation; canonical identities remain exact. The exact display-ID changes are kept below.'},'reopenAndFinalFit':reopen_records,'initialReopenFailure':{'file':'37-saved-reopen-initial.json','status':'initial-publicDOM-still-default90percent','firstPaintCertified':False,'pre':reopen_records[0]['pre'],'post':reopen_records[0]['post']},'displayPortOrientationChanges':[{'file':next(x['file'] for x in samples if x['revision']==data[n]['meta']['revision']),'sampleNumber':n,'removed':sorted(set(base['ports'])-set(data[n]['ports'])),'added':sorted(set(data[n]['ports'])-set(base['ports']))} for n in [28,30]],'rootPixelObservations':[
 {'file':'28-node-down.jpg','status':'root-observed-stale-raster','screenshotFooterRevision':31,'publicDOMRevision':32},
 {'file':'30-node-up.jpg','status':'root-observed-stale-raster','screenshotFooterRevision':33,'publicDOMRevision':34},
 {'file':'42-final-fit-default.jpg','status':'root-observed-stale-raster','screenshotZoomPercent':100,'publicDOMZoomPercent':53.5802},
 {'file':'43-final-fit-settled.jpg','status':'root-finite-pixel-review','visible':'54percent full figure and legend','firstPaintCertified':False}],
 'limitations':['Root supplied the finite raster observations; this auditor has not independently viewed screenshots.','Stable pre/post public DOM fields do not prove compositor or raster freshness. Four-direction pixel/first-paint success is not certified. Capture43 is root-reviewed finite settled pixel evidence, not proof all prior pixels are fresh.','This proves finite XML/JSON geometry and identities, port attachment, persistent default captions and whole-scene undo normalization only.','Vertical memory paths still detour and display endpoint orientation switches; canonical binding correctness is not route aesthetics acceptance.','No React mounting, browser input, model execution, actual publication or human usability gate is certified.']}
p=OUT/'report.json';p.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');rows.append(bind(p));rows.append(bind(Path(__file__).resolve()));rows.append(bind(STAGE/'independent-routing-agent/browser-node-readback-final/report.json'));rows.append(bind(STAGE/'independent-routing-agent/browser-node-readback-final/manifest.json'));rows.append(bind(STAGE/'independent-routing-agent/browser-node-readback-attempt-2/report.json'));rows.append(bind(STAGE/'independent-routing-agent/browser-node-readback-attempt-2/manifest.json'));rows.append(bind(STAGE/'independent-routing-agent/browser-node-readback-attempt-3/report.json'));rows.append(bind(STAGE/'independent-routing-agent/browser-node-readback-attempt-3/manifest.json'));p=OUT/'manifest.json';p.write_text(json.dumps({'schema':'archcanvas-independent-node-readback-manifest/1','rows':rows},indent=2)+'\n');print(json.dumps({'passed':report['passed'],'total':report['total'],'manifestRows':len(rows),'manifestSha256':hashlib.sha256(p.read_bytes()).hexdigest()}))
