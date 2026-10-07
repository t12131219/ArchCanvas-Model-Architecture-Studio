"""Independent hash/JSON/XML/PDF oracle; no production Python imports or model execution."""
from pathlib import Path
from datetime import datetime, timezone
from collections import Counter
import hashlib
import json
import math
import re
import subprocess
import xml.etree.ElementTree as ET

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[4]
STAGE = OUT.parents[1]
EXPORTS = OUT.parent
NS = '{http://www.w3.org/2000/svg}'
rows = []

def read(p):
    return json.loads(p.read_text())

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def stable_sha(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()

def add(name, condition, detail=None):
    rows.append({'relation': name, 'passed': bool(condition), **({'detail': detail} if detail is not None else {})})

def near(a, b, bound=1e-10):
    return math.isclose(a, b, rel_tol=0, abs_tol=bound)

def xml_value(tree, omit_root_height=False):
    attrs = dict(tree.attrib)
    if omit_root_height:
        attrs.pop('height', None)
    return [tree.tag, sorted(attrs.items()), tree.text or '', [xml_value(child) for child in tree]]

def points(d):
    # This independent parser rejects other syntax rather than guessing it.
    tokens = re.findall(r'[A-Za-z]|[-+]?(?:\d*\.\d+|\d+)(?:[Ee][-+]?\d+)?', d)
    result = []
    i = 0
    x = y = 0.0
    while i < len(tokens):
        op = tokens[i]
        i += 1
        if op in ('M', 'L'):
            x, y = float(tokens[i]), float(tokens[i+1]); i += 2
        elif op == 'H':
            x = float(tokens[i]); i += 1
        elif op == 'V':
            y = float(tokens[i]); i += 1
        else:
            raise ValueError('Unrecognized independent route command: ' + op)
        result.append((x, y))
    if len(result) < 2:
        raise ValueError('A rendered binding needs at least two points')
    return result

frozen = read(OUT / 'input-manifest.json')['files']
for i, row in enumerate(frozen):
    file = ROOT / row['path']
    add(f'frozen-input:{i}', file.stat().st_size == row['bytes'] and sha(file) == row['sha256'], row['path'])
add('frozen-input:nonempty-unique-denominator', len(frozen) > 140 and len({r['path'] for r in frozen}) == len(frozen), len(frozen))
checks = read(STAGE / 'checks-final-attempt-2/receipt.json')
for group in ['inputs', 'build', 'publicationInputs']:
    source_rows = checks[group]
    add('checks-current:' + group, bool(source_rows) and all((ROOT/r['path']).stat().st_size == r['bytes'] and sha(ROOT/r['path']) == r['sha256'] for r in source_rows), len(source_rows))
add('checks-current:expected-asset', any(r['path'] == 'studio/dist/assets/index-_KAUBMcR.js' and r['sha256'] == 'be212a3c88c284158fe7c66e133a15f75c655f7f22096e63dc30f443c818dbd2' for r in checks['build']))
capture = read(OUT / 'capture-receipt.json')
add('capture:read-only-and-nonempty', capture['frozenInputCount'] == len(frozen) and capture['inputDocumentMutated'] is False and capture['frozenInputMutated'] is False and capture['modelExecuted'] is False)

saved = read(STAGE / 'saved-readback/saved-rev39-envelope.json')
old = read(ROOT / 'docs/evidence/m4-caption-stability-current/actual-export-readback/saved-rev31-envelope.json')
doc = saved['document']
arch = doc['architecture']
nodes = {n['id']: n for n in arch['nodes']}
edges = {e['id']: e for e in arch['edges']}
add('saved:visual39-storage6-old31-storage5', doc['revision'] == 39 and saved['revision'] == 6 and old['document']['revision'] == 31 and old['revision'] == 5)
new_without_rev = {k:v for k,v in doc.items() if k != 'revision'}
old_without_rev = {k:v for k,v in old['document'].items() if k != 'revision'}
add('saved:only-document-revision-changed-from31', new_without_rev == old_without_rev,
    {'old': 31, 'new': 39, 'comparisonExcludes': ['document.revision'], 'layoutExact': doc['layout'] == old['document']['layout']})
add('saved:canonical-denominator-unique49-71', len(nodes) == len(arch['nodes']) == 49 and len(edges) == len(arch['edges']) == 71)
add('saved:source-binding-digest', doc['sourceBindingDigest'] == arch['sourceDigest'])
for source in arch['sources']:
    fixture = ROOT / 'fixtures/transformer' / source['path']
    add('source:embedded-content-digest:' + source['path'], hashlib.sha256(source['content'].encode()).hexdigest() == source['digest'])
    add('source:actual-fixture-exact:' + source['path'], fixture.read_text() == source['content'] and sha(fixture) == source['digest'])
source_input = [{k:v for k,v in source.items() if k != 'content'} for source in arch['sources']]
add('source:independent-corpus-digest', bool(source_input) and stable_sha(source_input) == arch['sourceDigest'])
semantic_nodes = []
for n in arch['nodes']:
    semantic = {k:v for k,v in n.items() if k not in ('source', 'parameterOrigins')}
    if 'parameterOrigins' in n:
        semantic['parameterOrigins'] = {name: {k:origin[k] for k in ('kind', 'expression', 'path')} for name, origin in n['parameterOrigins'].items()}
    semantic_nodes.append(semantic)
add('ir:independent-semantic-digest', stable_sha({'entry':arch['entry'], 'nodes':semantic_nodes, 'edges':arch['edges']}) == arch['irDigest'])
for e in arch['edges']:
    source = e['source']; target = e['target']
    out_ports = {p['id'] for p in nodes[source['nodeId']]['ports'] if p['direction'] == 'out'}
    in_ports = {p['id'] for p in nodes[target['nodeId']]['ports'] if p['direction'] == 'in'}
    add('canonical:port-binding:' + e['id'], source['portId'] in out_ports and target['portId'] in in_ports)

identities = read(EXPORTS / 'ui-export-identities.json')
receipts = {}
for label, ext, ui_sample in [('wholePdf','pdf','40-export-ui-complete.dom.txt'), ('wholeSvg','svg','41-svg-export-complete.dom.txt')]:
    folder = EXPORTS / label
    artifact = folder / ('figure.' + ext)
    receipt_path = folder / ('figure.' + ext + '.receipt.json')
    r = read(receipt_path); receipts[label] = r
    actual_doc = read(folder / 'document.json')
    # Direct JSON comparisons with exactly two known artifacts; never an empty all().
    add(label + ':actual-document-equals-saved39', actual_doc == doc, {'documentTopLevelKeys': len(actual_doc), 'canonicalNodes': len(actual_doc['architecture']['nodes']), 'canonicalEdges': len(actual_doc['architecture']['edges'])})
    add(label + ':receipt-document-source-ir', r['documentId'] == doc['id'] and r['revision'] == 39 and r['sourceDigest'] == arch['sourceDigest'] and r['irDigest'] == arch['irDigest'])
    add(label + ':receipt-artifact-bytes', r['outputDigest'] == sha(artifact) and r['bytes'] == artifact.stat().st_size)
    original = Path(r['path'])
    add(label + ':service-artifact-copy-exact', original.read_bytes() == artifact.read_bytes())
    add(label + ':service-receipt-copy-exact', original.with_name(original.name+'.receipt.json').read_bytes() == receipt_path.read_bytes())
    add(label + ':service-document-copy-exact', (original.parent/'document.json').read_bytes() == (folder/'document.json').read_bytes())
    add(label + ':ui-link-id-format-revision', original.parent.name == identities['exports'][label] and ('/api/exports/'+original.parent.name+'/figure.'+ext) in (STAGE/'browser'/ui_sample).read_text() and '视觉版本 39' in (STAGE/'browser'/ui_sample).read_text())
    add(label + ':formal-publication-origin', r['publicationOrigin'] == str(ROOT/'src/archcanvas_publication/exporter.py'))
    add(label + ':whole180mm', r['format'] == ext and r['widthMm'] == 180 and r['exportScope'] == {'kind':'document'})
    add(label + ':identity-inventory6-exact', len(identities['files']) == 6 and all((ROOT/row['path']).stat().st_size == row['bytes'] and sha(ROOT/row['path']) == row['sha256'] for row in identities['files']))

tree = ET.parse(EXPORTS/'wholeSvg/figure.svg').getroot()
raw = ET.parse(OUT/'whole.raw.svg').getroot()
scene = read(OUT/'whole.scene.json')
metadata = json.loads(tree.find(NS+'metadata').text)
r = receipts['wholeSvg']
viewbox = [float(v) for v in tree.get('viewBox').split()]
add('svg:root-document-revision', tree.get('data-document-id') == doc['id'] and tree.get('data-revision') == '39' and tree.get('aria-label') == doc['title'])
add('svg:metadata-identities', metadata['documentId'] == doc['id'] and metadata['revision'] == 39 and metadata['sourceDigest'] == arch['sourceDigest'] and metadata['irDigest'] == arch['irDigest'] and metadata['renderer'] == r['renderer'])
add('svg:raw-scene-digest', r['inputSvgDigest'] == r['sceneSvgDigest'] == sha(OUT/'whole.raw.svg'))
add('svg:normalized-digest', r['outputDigest'] == r['svgDigest'] == sha(EXPORTS/'wholeSvg/figure.svg'))
add('svg:complete-xml-except-root-height-normalization', xml_value(tree, True) == xml_value(raw, True))
add('svg:metadata-exact-observation', metadata == json.loads(raw.find(NS+'metadata').text))
add('svg:viewbox-scene-and-receipt', viewbox == r['viewBox'] == [scene['bounds'][k] for k in ('x','y','width','height')])
height = 180*viewbox[3]/viewbox[2]
add('svg:independent-physical-size-aspect', tree.get('width') == '180mm' and near(r['heightMm'],height) and near(metadata['heightMm'],height) and near(float(tree.get('height').removesuffix('mm')),height,5.1e-6))
facts = metadata['sourceFacts']
add('metadata:all49-source-facts-unique', len(facts) == len({f['id'] for f in facts}) == len(nodes) == 49 and {f['id'] for f in facts} == set(nodes) and metadata['sourceFactScope'] == 'whole-source-architecture')
for f in facts:
    c = nodes[f['id']]
    count = len({n['callId'] for n in arch['nodes'] if n.get('instanceId') == c.get('instanceId') and n.get('callId')}) if c.get('instanceId') else None
    add('metadata:source-fact:' + f['id'], f['sourceLabel'] == c['label'] and all(f.get(k) == c.get(k) for k in ('kind','category','evidence','source','instanceId','callId','repeat','outputPath')) and f.get('callCount') == count)
xml_nodes = {n.get('data-node-id'):n for n in tree.iter() if n.get('data-canonical-id')}
scene_nodes = {n['id']:n for n in scene['nodes']}
rendered_nodes = metadata['renderedNodes']
add('metadata:rendered-node-frontier12', len(xml_nodes) == len(scene_nodes) == len(rendered_nodes) == 12 and set(xml_nodes) == set(scene_nodes) == {n['sceneNodeId'] for n in rendered_nodes})
for n in scene['nodes']:
    canonical_id = n.get('canonicalNodeId',n['id'])
    add('svg:visible-node:' + n['id'], canonical_id in nodes and xml_nodes[n['id']].get('data-canonical-id') == canonical_id and xml_nodes[n['id']].get('aria-label') == n['label'] and n['sourceFact']['id'] == canonical_id)
xml_edges = {n.get('data-edge-id'):n for n in tree.iter() if n.get('data-edge-id')}
scene_edges = {e['id']:e for e in scene['edges']}
bindings = metadata['renderedBindings']
add('metadata:rendered-bindings-unique12', len(xml_edges) == len(scene_edges) == len(bindings) == len({b['sceneEdgeId'] for b in bindings}) == 12 and set(xml_edges) == set(scene_edges) == {b['sceneEdgeId'] for b in bindings})
ports = {p['id']:p for n in scene['nodes'] for p in n['ports']}
xml_ports = {n.get('data-port-id'):n for n in tree.iter() if n.get('data-port-id')}
add('svg:port-frontier-exact', len(ports)>0 and set(xml_ports) == set(ports),len(ports))
for pid,p in ports.items():
    expected = [edges[eid]['source' if p['direction']=='out' else 'target'] for eid in p['canonicalEdgeIds']]
    add('svg:display-port:' + pid, bool(expected) and expected == p['canonicalBindings'] and near(float(xml_ports[pid].get('cx')),p['x'],.0051) and near(float(xml_ports[pid].get('cy')),p['y'],.0051))
represented = []
for b in bindings:
    e = scene_edges[b['sceneEdgeId']]
    ids = b['canonicalEdgeIds']; represented.extend(ids)
    add('metadata:canonical-projected-binding:' + e['id'], bool(ids) and all(edges[i]['source']==b['source'] and edges[i]['role']==b['role'] and edges[i]['tensorId']==b['tensorId'] for i in ids) and edges[ids[0]]['target']==b['target'] and all(e.get(k)==b.get(k) for k in ('canonicalEdgeIds','source','target','tensorId','role')))
    xml = xml_edges[e['id']]; route = xml.find(NS+'path'); texts = xml.findall(NS+'text')
    add('svg:route-caption-style:' + e['id'], route.get('d') == e['path'] and route.get('stroke') == e['stroke'] and near(float(route.get('stroke-width')),e['width']) and xml.get('data-tensor-id')==e['tensorId'] and route.get('marker-end','').startswith('url(#archcanvas-arrow-') and (len(texts)==1 and texts[0].text==e['label'] and near(float(texts[0].get('x')),e['labelX'],.0051) and near(float(texts[0].get('y')),e['labelY'],.0051) if e['label'] else len(texts)==0))
    pp = points(e['path']); ends=[]
    for direction,nodeid,endpoint,point in [('out',e['sourceId'],e['source'],pp[0]),('in',e['targetId'],e['target'],pp[-1])]:
        candidates=[p for p in scene_nodes[nodeid]['ports'] if p['direction']==direction and endpoint in p['canonicalBindings'] and ids[0] in p['canonicalEdgeIds']]
        ends.append(bool(candidates) and min(max(abs(point[0]-p['x']),abs(point[1]-p['y'])) for p in candidates)<=.050000001)
    add('svg:orthogonal-port-endpoints:' + e['id'], all(ends) and all(near(a[0],b[0]) or near(a[1],b[1]) for a,b in zip(pp,pp[1:])))
add('metadata:full71-edge-partition', len(represented)==len(set(represented))==25 and len(scene['hiddenEdges'])==len(set(scene['hiddenEdges']))==46 and not set(represented)&set(scene['hiddenEdges']) and set(represented)|set(scene['hiddenEdges']) == set(edges),{'represented':len(represented),'hidden':len(scene['hiddenEdges'])})
guides=[n for n in tree.iter() if n.get('data-caption-guide-id')]
decorations=metadata.get('presentationDecorations',[])
add('svg:caption-guide-nonsemantic-unique', len(guides)==len(decorations)==len(scene['captionGuides'])==1 and guides[0].get('data-caption-guide-id')==decorations[0]['id']==scene['captionGuides'][0]['id'] and guides[0].get('data-caption-for-edge')==decorations[0]['sceneEdgeId']==scene['captionGuides'][0]['sceneEdgeId']=='edge:44' and guides[0].get('d')==decorations[0]['path']==scene['captionGuides'][0]['path'] and decorations[0]['id'] not in edges and decorations[0]['id'] not in scene_edges)
add('svg:caption-guide-inert-unarrowed', len(guides)==1 and not any(k.startswith('marker-') for k in guides[0].attrib) and guides[0].get('pointer-events')=='none' and guides[0].get('data-edge-id') is None and guides[0].get('data-tensor-id') is None and scene_edges['edge:44']['label']=='memory')
text_sizes=[float(t.get('font-size')) for t in tree.iter(NS+'text') if t.get('font-size')]
min_pt=min(text_sizes)*180/viewbox[2]/25.4*72
node_label_pt=13*180/viewbox[2]/25.4*72
min_line_pt=min(e['width'] for e in scene['edges'])*180/viewbox[2]/25.4*72
add('physical:independent-minimum-nominal-text', bool(text_sizes) and near(min_pt,r['physicalPreflight']['minTextPt']),{'fontSizeDenominator':len(text_sizes),'minimumPt':min_pt})
add('physical:node-label-and-main-line', near(node_label_pt,r['physicalPreflight']['nodeLabelPt']) and near(min_line_pt,r['physicalPreflight']['minMainLinePt']))

pdf_file=EXPORTS/'wholePdf/figure.pdf'; pdf=pdf_file.read_bytes(); pr=receipts['wholePdf']
result=subprocess.run(['/usr/bin/pdfinfo',str(pdf_file)],capture_output=True,text=True,check=False)
(OUT/'pdfinfo.stdout.txt').write_text(result.stdout);(OUT/'pdfinfo.stderr.txt').write_text(result.stderr)
add('pdf:independent-parser-success',result.returncode==0)
add('pdf:single-page-header-eof', pdf.startswith(b'%PDF-1.5') and pdf.rstrip().endswith(b'%%EOF') and re.search(r'^Pages:\s+1$',result.stdout,re.M) is not None)
boxes=re.findall(rb'/MediaBox\s*\[([^\]]+)\]',pdf)
add('pdf:single-explicit-page-box',len(boxes)==1)
values=[float(v) for v in boxes[0].split()];size_pt=[values[2]-values[0],values[3]-values[1]]
add('pdf:independent-physical-page',len(values)==4 and all(near(a,b,1e-5) for a,b in zip(size_pt,[180/25.4*72,height/25.4*72])) and size_pt==pr['pageSizePt'],size_pt)
add('pdf:same-scene-and-preflight-as-svg',all(pr[k]==r[k] for k in ('inputSvgDigest','svgDigest','sceneSvgDigest','viewBox','widthMm','heightMm','documentId','revision','sourceDigest','irDigest','physicalPreflight')))
add('pdf:formal-python-converter-origins',pr['pythonExecutable']==str(ROOT/'.venv/bin/python') and pr['converterOrigin']==str(ROOT/'.venv/lib/python3.11/site-packages/cairosvg/__init__.py') and pr['converter']=='CairoSVG')

failed=[row for row in rows if not row['passed']]
report={'schema':'archcanvas-viewport-actual-export-independent/1','createdUtc':datetime.now(timezone.utc).isoformat(),'relationships':len(rows),'passed':len(rows)-len(failed),'failed':len(failed),'failures':failed,
    'summary':{'actualArtifactCount':2,'actualSavedDocumentExactCount':sum(row['passed'] for row in rows if row['relation'].endswith(':actual-document-equals-saved39')),'savedCanvasRevision':39,'savedStorageRevision':6,'oldCanvasRevision':31,'oldStorageRevision':5,'canonicalNodes':len(nodes),'canonicalEdges':len(edges),'renderedNodes':len(scene_nodes),'renderedBindings':len(scene_edges),'visibleCanonicalEdges':len(represented),'hiddenCanonicalEdges':len(scene['hiddenEdges']),'physicalWidthMm':180,'physicalHeightMm':height,'minimumNominalTextPt':min_pt,'pdfPagePt':size_pt,'checkedCurrentSourceTestConfig':len(checks['inputs']),'checkedCurrentDist':len(checks['build']),'checkedPublicationInputs':len(checks['publicationInputs']),'frozenInputs':len(frozen)},
    'limits':['Data/hash/XML/PDF relationships only; no physical human review or global routing aesthetic certification.','Source/IR digest computation checks declared canonical content against the current formal digest contract; no model was executed.','Production scene is an observation, independently compared to XML, canonical bindings, saved document and receipts.','No actual 85 mm artifact, per-font physical quality, glyph shaping or PDF font embedding certification is added.','UI DOM files identify the actual export links; this audit does not independently fetch served JS bytes or review screenshots.','The existing dy14 to dy15 display-port jump is not repaired or approved by these exports.'],
    'relations':rows}
(OUT/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items() if k not in ('relations','limits')},ensure_ascii=False))
raise SystemExit(bool(failed))
