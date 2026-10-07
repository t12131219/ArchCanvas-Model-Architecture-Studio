from pathlib import Path
import hashlib,json,sys,xml.etree.ElementTree as E
root=Path.cwd();sys.path.insert(0,str(root/'src'))
from archcanvas_publication import export_svg,capabilities
out=root/'docs/evidence/m4-caption-route-current/export-integration-repair';source=(out/'current-publication-input.svg').read_text();tree=E.fromstring(source);metadata=json.loads(next(n.text for n in tree.iter() if n.tag.endswith('metadata')));guide=next(n for n in tree.iter() if n.attrib.get('data-caption-guide-id'));records=[]
for width in [85,180]:
 for format in ['svg','pdf','png']:
  result=export_svg(source,format,width,150);file=out/f'current-{width}.{format}';file.write_bytes(result['data']);(out/f'current-{width}.{format}.receipt.json').write_text(json.dumps(result['receipt'],indent=2)+'\n')
  row={'path':str(file.relative_to(root)),'widthMm':width,'format':format,'bytes':len(result['data']),'sha256':hashlib.sha256(result['data']).hexdigest(),'receipt':result['receipt']}
  if format=='svg':
   actual=E.fromstring(result['data']);after=json.loads(next(n.text for n in actual.iter() if n.tag.endswith('metadata')));g=next(n for n in actual.iter() if n.attrib.get('data-caption-guide-id'));row.update(guideAttributesExact=g.attrib==guide.attrib,sourceFactsExact=after['sourceFacts']==metadata['sourceFacts'],canonicalBindingsExact=after['renderedBindings']==metadata['renderedBindings'],presentationDecorationsExact=after['presentationDecorations']==metadata['presentationDecorations'])
  records.append(row)
(out/'exports-report.json').write_text(json.dumps({'schema':'archcanvas-caption-publication-output/1','pythonExecutable':sys.executable,'capabilities':capabilities(),'inputSha256':hashlib.sha256(source.encode()).hexdigest(),'records':records,'limits':['Actual formal converter bytes, not browser UI success','No pixel/physical approval or font embedding guarantee','No model executed']},indent=2)+'\n')
print(json.dumps({'exports':len(records),'svgRelationsExact':all(r.get('guideAttributesExact',True) and r.get('sourceFactsExact',True) and r.get('canonicalBindingsExact',True) and r.get('presentationDecorationsExact',True) for r in records),'formats':sorted({r['format'] for r in records})}))
