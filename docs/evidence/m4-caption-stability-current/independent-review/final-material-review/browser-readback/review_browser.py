"""Literal final browser capture/SVG and actual export receipt readback.

No browser input, product import, model execution or pixel visual approval.
"""
from __future__ import annotations
from datetime import datetime,timezone
import copy,hashlib,json,math,re
from pathlib import Path
import xml.etree.ElementTree as ET
from urllib.parse import urlparse
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[4];STAGE=ROOT/'docs/evidence/m4-caption-stability-current';BROWSER=STAGE/'browser';EXPORT=STAGE/'actual-export-readback';NS='{http://www.w3.org/2000/svg}'
OUT=HERE/'browser-readback'
def load(path):return json.loads(path.read_bytes())
def binding(path):
 raw=path.read_bytes();return {'path':str(path.relative_to(ROOT)),'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}
def close(a,b,tolerance=.003):return abs(a-b)<=tolerance
def paper(style):
 m=re.fullmatch(r'width: ([-\d.]+)px; height: ([-\d.]+)px; transform: translate\(([-\d.]+)px, ([-\d.]+)px\) scale\(([-\d.]+)\);',style);assert m,style
 return dict(zip(['width','height','tx','ty','scale'],map(float,m.groups())))
def scene_signature(svg,drop_revision=False):
 root=ET.fromstring(svg);root.attrib.pop('data-revision',None)if drop_revision else None
 metadata=root.find(NS+'metadata');value=json.loads(metadata.text)
 if drop_revision:value.pop('revision',None)
 metadata.text=json.dumps(value,sort_keys=True);return ET.tostring(root)
def encoder_front(root):
 group=next(n for n in root.iter()if n.get('data-node-id')=='repeat:instance:model.Transformer.encoder'and not n.get('data-port-id'))
 rects=[n for n in group if n.tag==NS+'rect'];rect=next(n for n in rects if n.get('stroke-width')=='1.5');return {key:float(rect.get(key))for key in ['x','y','width','height']}
def nodes_except_encoder(root):
 return [ET.tostring(n)for n in root.iter()if n.tag==NS+'g'and n.get('data-node-id')and not n.get('data-port-id')and n.get('data-node-id')!='repeat:instance:model.Transformer.encoder']
def main():
 assert not OUT.exists();OUT.mkdir();checks=[];materials=set();captures={}
 def check(name,value):checks.append({'name':name,'passed':bool(value)})
 def keep(path):materials.add(path);return path
 receipt=load(keep(STAGE/'checks-final-attempt-2/receipt.json'));js=next(r for r in receipt['build']if r['path'].endswith('.js'));css=next(r for r in receipt['build']if r['path'].endswith('.css'))
 for index in range(12,35):
  candidates=list(BROWSER.glob(f'{index:02}-*.json'));assert len(candidates)==1;c=load(keep(candidates[0]));stem=candidates[0].stem;svg_path=keep(BROWSER/(stem+'.svg'));svg=svg_path.read_text();root=ET.fromstring(svg);meta=json.loads(root.find(NS+'metadata').text);c['parsedMetadata']=json.loads(c['metadata']);c['root']=root;c['paperNumbers']=paper(c['paper']);captures[index]=c
  check('capturedSVG exact json '+stem,c['svg']==svg)
  check('same current filename assets '+stem,[Path(urlparse(url).path).name for url in c['scripts']]==[Path(js['path']).name]and[Path(urlparse(url).path).name for url in c['styles']]==[Path(css['path']).name])
  check('json SVG exact identity facts metadata '+stem,c['parsedMetadata']==meta and meta['documentId']==root.get('data-document-id')and str(meta['revision'])==root.get('data-revision'))
  check('paper size matches world viewBox '+stem,all(close(a,b)for a,b in zip([c['paperNumbers']['width'],c['paperNumbers']['height']],[float(x)for x in root.get('viewBox').split()][2:])))
  edges={n.get('data-edge-id'):n for n in root.iter()if n.get('data-edge-id')};rendered={e['sceneEdgeId']:e for e in meta['renderedBindings']}
  check('SVG rendered edge inventory literal metadata '+stem,edges.keys()==rendered.keys())
  for edge_id,edge in rendered.items():
   if edge['role']!='memory':continue
   texts=[n.text for n in edges[edge_id].iter(NS+'text')];check('memory visible literal '+stem+'/'+edge_id,'memory'in texts and any(t['edgeId']==edge_id and t['text']=='memory'for t in c['texts']))
  guides=[n for n in root.iter()if n.get('data-caption-guide-id')]
  check('SVG/json guides exact ownery '+stem,{g.get('data-caption-guide-id')for g in guides}=={dict(g['attributes'])['data-caption-guide-id']for g in c['guides']}and all(g.get('pointer-events')=='none'and not any(k.startswith('marker')for k in g.attrib)and g.get('data-caption-for-edge')in edges for g in guides))
 def equal_view(a,b,label):
  check(label+' paper/window/viewport/cards/texts/guides equal',all(captures[a][key]==captures[b][key]for key in ['paper','viewport','window','cards','texts','guides']))
  check(label+' metadata SVG equal',captures[a]['parsedMetadata']==captures[b]['parsedMetadata']and captures[a]['svg']==captures[b]['svg'])
 equal_view(13,14,'reload final Transformer');equal_view(14,17,'model return Transformer');equal_view(16,18,'model return MLP');equal_view(33,34,'saved reopened baseline')
 def camera_delta(a,b,dx,dy,label):
  first=captures[a];second=captures[b];p=first['paperNumbers'];q=second['paperNumbers'];check(label+' paper translation',close(q['tx']-p['tx'],dx)and close(q['ty']-p['ty'],dy)and close(p['scale'],q['scale'])and first['viewport']==second['viewport'])
  check(label+' model SVG facts invariant',first['svg']==second['svg']and first['parsedMetadata']==second['parsedMetadata'])
  oldcards={x['id']:x['rect']for x in first['cards']};newcards={x['id']:x['rect']for x in second['cards']};check(label+' card CSS translation',oldcards.keys()==newcards.keys()and all(close(newcards[k]['x']-v['x'],dx)and close(newcards[k]['y']-v['y'],dy)and close(newcards[k]['width'],v['width'])and close(newcards[k]['height'],v['height'])for k,v in oldcards.items()))
 camera_delta(12,13,32,16,'pan+32+16');camera_delta(17,19,-32,0,'camera left32');camera_delta(19,20,32,0,'camera right32');camera_delta(20,21,0,-32,'camera up32');camera_delta(21,22,0,32,'camera down32')
 check('MLP zoom scale actually changed and SVG facts retained',captures[15]['paperNumbers']['scale']!=captures[16]['paperNumbers']['scale']and captures[15]['svg']==captures[16]['svg'])
 check('explicit fit changes transform with same SVG and document facts',captures[22]['paper']!=captures[23]['paper']and captures[22]['svg']==captures[23]['svg'])
 baseline=captures[24];baseline_rect=encoder_front(baseline['root']);base_meta=baseline['parsedMetadata'];moves=[]
 for applied,undo,dx,dy in [(25,26,0,24),(27,28,0,-24),(29,30,-24,0),(31,32,24,0)]:
  current=captures[applied];restored=captures[undo];rect=encoder_front(current['root']);move={'capture':applied,'undoCapture':undo,'dxWorld':dx,'dyWorld':dy,'paperBefore':baseline['paperNumbers'],'paperAfter':current['paperNumbers']};moves.append(move)
  check('node actual worlddelta '+str(applied),close(rect['x']-baseline_rect['x'],dx)and close(rect['y']-baseline_rect['y'],dy)and rect['width']==baseline_rect['width']and rect['height']==baseline_rect['height'])
  check('node move paper camera same '+str(applied),all(close(current['paperNumbers'][key],baseline['paperNumbers'][key])for key in ['tx','ty','scale'])and current['viewport']==baseline['viewport'])
  check('node move unrelated card nodes unchanged '+str(applied),nodes_except_encoder(current['root'])==nodes_except_encoder(baseline['root']))
  check('node actual facts binding invariant '+str(applied),all(current['parsedMetadata'][key]==base_meta[key]for key in ['documentId','sourceDigest','irDigest','sourceFacts','renderedBindings']))
  check('node undo exact geometry aside revision '+str(undo),scene_signature(restored['svg'],True)==scene_signature(baseline['svg'],True)and restored['cards']==baseline['cards']and restored['paper']==baseline['paper'])
 check('node move/undo revisions23through31',base_meta['revision']==23 and[captures[i]['parsedMetadata']['revision']for i in range(25,33)]==list(range(24,32)))
 saved=load(keep(EXPORT/'saved-rev31-envelope.json'));source=load(keep(ROOT/'docs/evidence/m4-caption-stability-current/independent-review/source-envelope.json'))['document'];document=saved['document']
 check('saved31 metadata final exact facts',saved['revision']==document['revision']==31 and captures[34]['parsedMetadata']['revision']==31 and captures[34]['parsedMetadata']['documentId']==document['id']and captures[34]['parsedMetadata']['sourceDigest']==document['sourceBindingDigest']and captures[34]['parsedMetadata']['irDigest']==document['architecture']['irDigest'])
 changed=[k for k in source if source[k]!=document[k]];layout_changed=[k for k in source['layout']if source['layout'][k]!=document['layout'][k]]
 check('saved20to31 only revision and known root+4+4 layout',changed==['revision','layout']and layout_changed==['call:instance:model.Transformer']and document['layout'][layout_changed[0]]=={'x':54,'y':96}and source['layout'][layout_changed[0]]=={'x':50,'y':92})
 identities=load(keep(EXPORT/'ui-export-identities.json'));exports=[]
 for name,index,extension,scope in [('wholePdf',35,'pdf','whole'),('wholeSvg',36,'svg','whole'),('detailSvg',37,'svg','detail')]:
  directory=EXPORT/name;artifact=keep(directory/f'figure.{extension}');receipt_path=keep(directory/f'figure.{extension}.receipt.json');r=load(receipt_path);export_document=load(keep(directory/'document.json'));ui=load(keep(next(BROWSER.glob(f'{index:02}-*.json'))));identity=identities[name];output=binding(artifact)
  check('actual export output receipt digest '+name,output['bytes']==r['bytes']and output['sha256']==r['outputDigest'])
  check('actual export input document exact saved31 '+name,export_document==document)
  check('actual export UIidentity links exact '+name,all(f'/api/exports/{identity}/'in item['href']for item in ui['links'])and all(Path(urlparse(url).path).name==Path(js['path']).name for url in ui['scripts']))
  check('actual export receipt identity/canonical digests '+name,r['documentId']==document['id']and r['revision']==31 and r['sourceDigest']==document['sourceBindingDigest']and r['irDigest']==document['architecture']['irDigest']and r['format']==extension and r['widthMm']==180 and r['geometryVerified'])
  check('formal publisher provenance '+name,r['publicationOrigin']==str(ROOT/'src/archcanvas_publication/exporter.py'))
  if extension=='svg':
   root=ET.fromstring(artifact.read_bytes());meta=json.loads(root.find(NS+'metadata').text);check('export SVG exact receipt geometry/source '+name,meta['documentId']==r['documentId']and meta['revision']==31 and meta['sourceDigest']==r['sourceDigest']and meta['irDigest']==r['irDigest']and[float(x)for x in root.get('viewBox').split()]==r['viewBox'])
   check('export memory literal exists '+name,any(n.text=='memory'for n in root.iter(NS+'text')))
  else:check('PDF bytes literal page dimension exists '+name,artifact.read_bytes().startswith(b'%PDF-')and b'/MediaBox [ 0 0 510.23622 590.416186 ]'in artifact.read_bytes())
  exports.append({'name':name,'identity':identity,'format':extension,'scope':scope,'receipt':binding(receipt_path),'output':output,'sourceDocumentRevision':31,'sourceDocumentExact':True,'reportedPhysicalPreflight':r['physicalPreflight']})
 report={'schema':'archcanvas-independent-final-browser-data-review/1','createdUtc':datetime.now(timezone.utc).isoformat(),'passed':sum(c['passed']for c in checks),'total':len(checks),'checks':checks,'failedChecks':[c for c in checks if not c['passed']],'dataCaptures':23,'captureIndices':[12,34],'cameraRestorePairs':[[13,14],[14,17],[16,18],[33,34]],'cardinalCameraDirections':4,'cameraCardinalDistanceCssPx':32,'cardinalNodeDirections':4,'nodeDistanceWorld':24,'nodeUndoCases':4,'actualExports':exports,'nodeMovement':moves,'savedRevision':31,'savedDeltaFrom20':{'revision':11,'rootLayoutDxWorld':4,'rootLayoutDyWorld':4},'assetFilename':Path(js['path']).name,'assetDigestFromCurrentAndFrozenReceipt':js['sha256'],'servedBytesHashVerified':False,'crossViewport':'pending separate literal captures; not inferred from same-window restore','scope':'Read-only JSON/SVG/data capture and export byte receipts. Does not operate browser or claim independent pixel quality, native event ordering, FPS, physical publication readability, global route optimality, human review or model execution. Asset filenames match current/frozen build; served HTTP bytes not independently fetched. Root browser actions/pixel observations are separate. M4 partial/humans0.'}
 (OUT/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');materials.update([OUT/'report.json',Path(__file__).resolve()]);rows=[binding(p)for p in sorted(materials)];path=OUT/'manifest.json';path.write_text(json.dumps({'schema':'archcanvas-independent-final-browser-data-manifest/1','files':rows,'scope':report['scope']},ensure_ascii=False,indent=2)+'\n');print(json.dumps({'passed':report['passed'],'total':report['total'],'rows':len(rows),'manifestSHA256':binding(path)['sha256']}));raise SystemExit(0 if report['passed']==report['total']else 1)
if __name__=='__main__':main()
