"""Independent XML and receipt bindings; production only captures scene inputs."""
from pathlib import Path
import json,hashlib,re,sys,xml.etree.ElementTree as E
root=Path.cwd();out=root/'docs/evidence/m4-caption-route-current/browser-export-final';browser=root/'docs/evidence/m4-caption-route-current/browser/continuation';rows=[]
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def meta(tree):return json.loads(next(n.text for n in tree.iter() if n.tag.endswith('metadata')))
def doc(path):
 j=json.loads(path.read_text());return j.get('document',j)
def add(name,value,detail=None):rows.append({'relation':name,'passed':bool(value),'detail':detail})
identifiers=['ea42cd05c8a344348ed5751da24276ec','a0a6f9b4d5b74acfa9c9b032175c14ca','a6a82fd6101e451ab7e09caec69e035b'];documents=[];exports=[]
for identifier in identifiers:
 base=out/'exports'/identifier;artifact=next(p for p in base.glob('figure.*') if not p.name.endswith('.json'));receipt=json.loads((base/(artifact.name+'.receipt.json')).read_text());document=doc(base/'document.json');documents.append(document)
 add(identifier+':output-bytes-and-digest',receipt['bytes']==artifact.stat().st_size and receipt['outputDigest']==digest(artifact))
 add(identifier+':document-revision',receipt['documentId']==document['id'] and receipt['revision']==document['revision']==20)
 add(identifier+':source-ir-digests',receipt['sourceDigest']==document['architecture']['sourceDigest'] and receipt['irDigest']==document['architecture']['irDigest'])
 add(identifier+':formal-publication-origin',receipt['publicationOrigin']==str(root/'src/archcanvas_publication/exporter.py'))
 add(identifier+':width-180',receipt['widthMm']==180)
 if artifact.suffix=='.svg':
  label='whole' if identifier==identifiers[0] else 'detail';raw=out/(label+'.raw.svg');scene=json.loads((out/(label+'.scene.json')).read_text());tree=E.fromstring(artifact.read_bytes());metadata=meta(tree);rawmeta=meta(E.fromstring(raw.read_bytes()));guides=[n for n in tree.iter() if n.attrib.get('data-caption-guide-id')];edges={n.attrib['data-edge-id']:n for n in tree.iter() if n.attrib.get('data-edge-id')};canonical={e['id']:e for e in document['architecture']['edges']}
  add(label+':input-raw-scene-digest',receipt['inputSvgDigest']==receipt['sceneSvgDigest']==digest(raw))
  add(label+':svg-digest',receipt['svgDigest']==digest(artifact))
  add(label+':metadata-exact',metadata==rawmeta)
  add(label+':facts-scene-exact',metadata['sourceFacts']==scene['sourceFacts'])
  add(label+':binding-count',len(metadata['renderedBindings'])==len(edges)==len(scene['edges'])==12)
  add(label+':facts-count',len(metadata['sourceFacts'])==49)
  archNodes={n['id']:n for n in document['architecture']['nodes']}
  for fact in metadata['sourceFacts']:
   n=archNodes[fact['id']];add(label+':fact-'+fact['id'],all(fact.get(k)==n.get(k) for k in ['kind','category','evidence','source']) and fact['sourceLabel']==n['label'])
  for binding in metadata['renderedBindings']:
   ids=binding['canonicalEdgeIds'];sources=[canonical[i]['source'] for i in ids];roles=[canonical[i]['role'] for i in ids];tensors=[canonical[i]['tensorId'] for i in ids]
   add(label+':canonical-'+binding['sceneEdgeId'],bool(ids) and all(s==binding['source'] for s in sources) and all(role==binding['role'] for role in roles) and all(t==binding['tensorId'] for t in tensors) and canonical[ids[0]]['target']==binding['target'])
  decorations=metadata.get('presentationDecorations',[]);add(label+':one-guide-and-decoration',len(guides)==len(decorations)==1)
  for guide in guides:
   owner=guide.get('data-caption-for-edge');gid=guide.get('data-caption-guide-id');dec=next(d for d in decorations if d['id']==gid)
   add(label+':guide-presentation-only',owner in edges and gid not in edges and all(b['sceneEdgeId']!=gid for b in metadata['renderedBindings']) and dec['kind']=='caption-guide' and dec['sceneEdgeId']==owner and dec['path']==guide.get('d'))
   add(label+':guide-unarrowed-inert',not any(n.startswith('marker-') for n in guide.attrib) and not any(n in guide.attrib for n in ['data-edge-id','data-tensor-id']) and guide.get('pointer-events')=='none' and guide.get('fill')=='none' and guide.get('stroke-width')=='0.8')
  exports.append({'id':identifier,'format':'svg','artifact':str(artifact.relative_to(root)),'receipt':receipt,'guideAttributes':[g.attrib for g in guides]})
 else:
  size=re.search(rb'/MediaBox\s*\[([^\]]+)\]',artifact.read_bytes());values=[float(s) for s in size.group(1).split()];actual=[values[2]-values[0],values[3]-values[1]]
  add('pdf:physical-page-box',abs(actual[0]-180/25.4*72)<.01 and abs(actual[1]-receipt['heightMm']/25.4*72)<.01)
  other=json.loads((out/'exports'/identifiers[1]/'figure.svg.receipt.json').read_text());add('pdf:detail-input-exact',receipt['inputSvgDigest']==other['inputSvgDigest'] and receipt['svgDigest']==other['svgDigest'] and receipt['exportScope']==other['exportScope'])
  add('pdf:formal-python-converter',receipt['pythonExecutable']==str(root/'.venv/bin/python') and '.venv/' in receipt['converterOrigin'])
  exports.append({'id':identifier,'format':'pdf','artifact':str(artifact.relative_to(root)),'receipt':receipt,'actualPageSizePt':actual})
add('three-documents-identical',documents[0]==documents[1]==documents[2])
final=doc(root/'docs/evidence/m4-caption-route-current/browser/pre-ui/saved-transformer-final-envelope.json');add('export-documents-match-final-saved',documents[0]==final)
original=doc(root/'docs/evidence/m4-caption-route-current/browser/pre-ui/saved-transformer-envelope.json');add('saved-layout-model-and-presentations-preserved',dict(final,revision=0)==original)
for name,identifier,format in [('33-whole-svg-success',identifiers[0],'SVG'),('35-detail-svg-success',identifiers[1],'SVG'),('36-detail-pdf-success',identifiers[2],'PDF')]:
 capture=json.loads((browser/(name+'.json')).read_text());links=json.loads((browser/(name.split('-')[0]+'-export-links.json')).read_text());add(name+':actual-ui-success',f'文件已生成 · {format}' in capture['bodyText'] and 'ApiError' not in capture['bodyText']);add(name+':actual-link-id',any(identifier in row['href'] for row in links));add(name+':current-build',any('index-Divs1MJA.js' in s for s in capture['scripts']))
checks=json.loads((root/'docs/evidence/m4-caption-route-current/checks-final-attempt-4/receipt.json').read_text());bindings=checks['inputs']+checks['build']+checks['publicationInputs'];add('checks4-current-inputs-exact',all(digest(root/r['path'])==r['sha256'] and (root/r['path']).stat().st_size==r['bytes'] for r in bindings));add('checks4-commands-success',all(r['exitCode']==0 for r in checks['checks']))
mono=json.loads((browser/'31-monochrome-settled.json').read_text());m=meta(E.fromstring((browser/'31-monochrome-settled.svg').read_bytes()));add('mono-guide-gray-present',len(mono['guides'])==1 and dict(mono['guides'][0]['attributes'])['stroke']=='#56616b' and len(m['presentationDecorations'])==1);add('mono-30-31-identical-screenshot-bytes',digest(browser/'30-monochrome.jpg')==digest(browser/'31-monochrome-settled.jpg'))
first=json.loads((browser/'03-divs-100-first.json').read_text());settled=json.loads((browser/'04-divs-100-settled.json').read_text());add('zoom-first-and-settled-dom100', 'scale(1)' in first['paper'] and 'scale(1)' in settled['paper'])
finalCapture=json.loads((browser/'39-final-100-settled.json').read_text());finalMeta=meta(E.fromstring((browser/'39-final-100-settled.svg').read_bytes()));add('final39-doc-rev20',finalMeta['documentId']==final['id'] and finalMeta['revision']==20);add('final39-memory-guide-present',len(finalCapture['guides'])==1 and len(finalMeta['presentationDecorations'])==1 and 'scale(1)' in finalCapture['paper']);add('final39-same-sourcefacts-and-bindings',finalMeta['sourceFacts']==meta(E.fromstring((out/'whole.raw.svg').read_bytes()))['sourceFacts'] and finalMeta['renderedBindings']==meta(E.fromstring((out/'whole.raw.svg').read_bytes()))['renderedBindings'])
report={'schema':'archcanvas-final-browser-export-independent-audit/1','relations':rows,'relationCount':len(rows),'failedRelations':[r for r in rows if not r['passed']],'exports':exports,'checksCurrentBindings':len(bindings),'physicalAdvice':{'whole180MinTextPt':exports[0]['receipt']['physicalPreflight']['minTextPt'],'detail180MinTextPt':exports[1]['receipt']['physicalPreflight']['minTextPt'],'whole85MinTextPt':exports[0]['receipt']['physicalPreflight']['minTextPt']*85/180,'notApproval':True},'manualPixelObservations':{'personallyViewed':['30-monochrome.jpg','31-monochrome-settled.jpg','31-monochrome-settled-caption-crop.png','32-color-restored.jpg','03-divs-100-first.jpg','04-divs-100-settled.jpg','whole-svg-review.png','detail-svg-review.png','detail-pdf.png','39-final-100-settled.jpg'],'monoGuide':'Visible thin unarrowed vertical guide joins the memory tensor centerline to the separate memory caption; at68% it is faint but discernible in the original and enlarged pixel crop.','firstFrameMismatch':'03 screenshot displays68% and overview pixels while its DOM paper already says scale(1);04 settled screenshot displays100% and larger pixels. No mismatch found between30/31, whose screenshot bytes are identical.','exports':'Whole/detail SVG rasterizations and actual PDF Poppler rendering show the memory guide and caption. No clipped memory text or guide was observed in this finite reviewed region; broad visual approval is not established.'},'limits':['AI independent review, human participants0','Font glyph masks, family fidelity, PDF embedding and physical publication approval not certified','Source models never executed','No native/presented-performance proof','Nominal DOM geometry and finite pixels do not prove general gestures','Bundled Poppler GLIBC_2.38 failure retained; system Poppler succeeded']}
(out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({'relations':len(rows),'failures':report['failedRelations'],'currentBindings':len(bindings),'docsIdentical':documents[0]==documents[1]==documents[2]}))
