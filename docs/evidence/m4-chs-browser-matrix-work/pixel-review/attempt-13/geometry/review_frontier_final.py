"""Final declaration comparison only; no causal/operation-history certification."""
from pathlib import Path
import hashlib,json,re,xml.etree.ElementTree as ET
OUT=Path(__file__).resolve().parent
BASE=OUT.parents[2]
CASE=BASE/'raw/residual_cnn-level0-paper-180-edited-recapture1'
def bind(p):
 b=p.read_bytes();return {'path':str(p.resolve()),'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}
prepaths=[OUT/'residual-cnn-edited-recapture1-preparse-bindings.json',OUT/'residual-cnn-frontier-preparse-bindings.json']
prestart=[bind(p) for p in prepaths]
expected=[x for p in prepaths for x in json.loads(p.read_text())['inputBindingsStart']]
start=[bind(Path(x['path'])) for x in expected];assert start==expected
saved=json.loads((CASE/'saved-envelope.json').read_text())['document']
raw_svg=ET.parse(CASE/'browser-scene.svg').getroot()
root_id='call:instance:model.ResidualCNN'
def scene(root):
 groups={n.attrib['data-node-id']:n for n in root.iter() if n.attrib.get('data-canonical-id')}
 rects={k:next(c for c in v if c.tag.endswith('rect') and 'stroke-width' in c.attrib).attrib for k,v in groups.items()}
 backplate=[c.attrib for v in groups.values() for c in v if c.tag.endswith('rect') and 'opacity' in c.attrib]
 return {'svgRoot':root.attrib,'visibleCanonicalIds':sorted(groups),'frontRects':rects,'backplates':backplate,'expandControls':[x.attrib['data-expand-id'] for x in root.iter() if 'data-expand-id' in x.attrib],'collapseControls':[x.attrib['data-collapse-id'] for x in root.iter() if 'data-collapse-id' in x.attrib]}
final_scene=scene(raw_svg)
journals=[]
for p in sorted((BASE/'edited-journal').glob('residual_cnn-frontier-*.json')):
 j=json.loads(p.read_text());s=ET.fromstring(j['svg']);dom=p.with_suffix('.dom.txt').read_text()
 journals.append({'file':str(p.resolve()),'documentBinding':j['documentBinding'],'expandedIds':j['expandedIds'],'hiddenExpandedIds':[n for n in j['expandedIds'] if n not in scene(s)['visibleCanonicalIds']],'onlyRootExpanded':j['expandedIds']==[root_id],'footerDeclaration':j['footer'],'dialogCountDeclaration':j['dialogCount'],'rootCollapseControlInDom':'Collapse ResidualCNN' in dom,'blocksExpandControlInDom':'Expand blocks' in dom,'matchesFinalSceneStructure':scene(s)==final_scene,'embeddedSvgXmlSerializationEqualToExport':ET.tostring(s)==ET.tostring(raw_svg),'limit':'Named journal and footer declarations are compared only, not independent operation/reopen/save proof.'})
blocks=final_scene['frontRects']['repeat:instance:model.ResidualCNN.blocks'];pool=final_scene['frontRects']['call:instance:model.ResidualCNN.pool']
annotation=next(x for x in raw_svg.iter() if 'data-annotation-id' in x.attrib)
annotation_rect=next(c for c in annotation if c.tag.endswith('rect')).attrib
r={'scope':'Fresh CNN final hidden-frontier declarations/journal supplement; source only','caseId':CASE.name,'preparseBindingFilesStart':prestart,'inputBindingsStart':start,'savedExpandedIds':saved['expandedIds'],'savedOnlyRootExpanded':saved['expandedIds']==[root_id],'savedHiddenExpandedIds':[x for x in saved['expandedIds'] if x not in final_scene['visibleCanonicalIds']],'finalScene':final_scene,'journals':journals,'nominalGapDeclarations':{'blocksBottom':float(blocks['y'])+float(blocks['height']),'poolTop':float(pool['y']),'blocksToPoolGapSceneUnits':float(pool['y'])-float(blocks['y'])-float(blocks['height']),'annotationTop':float(annotation_rect['y']),'viewBox':raw_svg.attrib['viewBox'],'limit':'Fresh case has 38-unit blocks/pool gap; excluded original case 1614-unit gap is not reused. Large note y/viewBox remain factual; no layout causality or pixel acceptability claim.'},'limits':['No image opened, runtime/history/save acquisition or raster synchronization certification.','Architecture/source declaration consistency does not establish runtime semantic fidelity.','Old excluded case reports and raw originals remain preserved.']}
r['inputBindingsEnd']=[bind(Path(x['path'])) for x in expected];r['inputsUnchanged']=r['inputBindingsStart']==r['inputBindingsEnd'];r['preparseBindingFilesEnd']=[bind(p) for p in prepaths];r['preparseBindingsUnchanged']=prestart==r['preparseBindingFilesEnd']
p=OUT/'residual-cnn-fresh-frontier-final-review.json';assert not p.exists();p.write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'report':bind(p),'inputsUnchanged':r['inputsUnchanged'],'journalCount':len(journals),'allOnlyRootExpanded':all(x['onlyRootExpanded'] for x in journals),'allSceneStructureEqual':all(x['matchesFinalSceneStructure'] for x in journals),'gap':r['nominalGapDeclarations']},ensure_ascii=False,indent=2))
