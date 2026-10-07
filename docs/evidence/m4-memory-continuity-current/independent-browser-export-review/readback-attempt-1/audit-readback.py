"""Bounded independent stdlib audit; reads captured DOM and actual exports only."""
from __future__ import annotations
import copy
import hashlib
import json
import math
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET
import zlib
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[4]
STAGE = ROOT / 'docs/evidence/m4-memory-continuity-current'
OWNER = Path(__file__).resolve().parent
EXPECT = OWNER / 'expectations-attempt-1'
OUT = OWNER / (sys.argv[1] if len(sys.argv) > 1 else 'readback-attempt-1')
if OUT.exists():
    raise SystemExit('Do not overwrite evidence')
OUT.mkdir()
NS = '{http://www.w3.org/2000/svg}'
relations = []

def load(path):
    return json.loads(Path(path).read_text())

def bind(path):
    p = Path(path)
    if not p.is_absolute():
        p = ROOT / p
    data = p.read_bytes()
    return {'path': str(p.relative_to(ROOT)), 'bytes': len(data),
            'sha256': hashlib.sha256(data).hexdigest()}

def check(name, ok, detail=None):
    row = {'relation': name, 'passed': bool(ok)}
    if detail is not None:
        row['detail'] = detail
    relations.append(row)

def canonical(e):
    return (e.tag, sorted(e.attrib.items()), e.text or '', e.tail or '',
            [canonical(c) for c in e])

def metadata(tree):
    return json.loads(tree.find(NS + 'metadata').text)

def groups(tree, attribute, canonical_only=False):
    return {e.get(attribute): e for e in tree.iter(NS+'g')
            if e.get(attribute) and (not canonical_only or e.get('data-canonical-id'))}

def source_facts(architecture):
    # Independently project the documented facts from the captured architecture;
    # do not import the renderer, exporter or their metadata helpers.
    calls = {}
    for node in architecture['nodes']:
        if node.get('instanceId') and node.get('callId'):
            calls.setdefault(node['instanceId'], set()).add(node['callId'])
    result = []
    for node in architecture['nodes']:
        fact = {key: node[key] for key in ['id','kind','category','evidence']}
        fact['sourceLabel'] = node['label']
        for key in ['instanceId','callId','repeat','outputPath']:
            if key in node:
                fact[key] = node[key]
        if node.get('instanceId'):
            fact['callCount'] = len(calls.get(node['instanceId'], set()))
        if 'source' in node:
            fact['source'] = {k:node['source'][k] for k in ['path','line','endLine','expression']
                              if k in node['source']}
        result.append(fact)
    return result

def no_revision(tree):
    tree = copy.deepcopy(tree)
    tree.attrib.pop('data-revision', None)
    m = metadata(tree)
    m.pop('revision', None)
    tree.find(NS+'metadata').text = json.dumps(m, sort_keys=True, separators=(',',':'))
    return canonical(tree)

capture = load(EXPECT/'capture.json')
saved = load(STAGE/'actual-export-work/saved-rev47-envelope.json')
doc = saved['document']
architecture = doc['architecture']
facts = source_facts(architecture)
arch_nodes = {n['id']:n for n in architecture['nodes']}
arch_edges = {e['id']:e for e in architecture['edges']}
root_observation = load(STAGE/'root-observation.json')
checks = load(STAGE/'checks-final-attempt-2/receipt.json')
copy_receipt = load(STAGE/'actual-export-work/copy-receipt.json')

input_paths = {str(Path(b['path'])) for b in capture['inputBindings']}
input_paths.update(str(p.relative_to(ROOT)) for p in EXPECT.iterdir() if p.is_file())
input_paths.update(str(p.relative_to(ROOT)) for p in (STAGE/'browser').iterdir() if p.is_file())
input_paths.update(['docs/evidence/m4-memory-continuity-current/root-observation.json',
                    'docs/evidence/m4-memory-continuity-current/checks-final-attempt-2/receipt.json',
                    str(Path(__file__).resolve().relative_to(ROOT))])
for b in checks['build']:
    input_paths.add(b['path'])
    input_paths.add(b['snapshot'])
input_bindings = [bind(p) for p in sorted(input_paths)]

for b in capture['inputBindings']:
    check('expectations-input-current:'+b['path'], bind(b['path']) == b)
for key in ['inputAfter']:
    check('expectations-input-before-after', capture[key] == capture['inputBindings'])
check('expectations-records-unchanged',capture['inputsUnchanged'])
for b in copy_receipt['files']:
    check('actual-copy-binding:'+b['path'],bind(b['path']) == b)
for b in checks['build']:
    expected = {k:b[k] for k in ['path','bytes','sha256']}
    check('local-current-build:'+b['path'],bind(b['path']) == expected)
    snapshot = bind(b['snapshot'])
    check('frozen-build-copy:'+b['path'],snapshot['sha256'] == b['sha256'] and snapshot['bytes'] == b['bytes'])
check('formal-check-exits',all(c['exitCode']==0 for c in checks['checks']))
check('saved-canvas-storage-identity',doc['revision']==47 and saved['revision']==7)
check('root-final-capture-and-staleness-preserved',
      len(root_observation['personallyViewedImages'])==5 and
      any(x['path'].startswith('browser/16-') and 'still shows export modal' in x['observations'] for x in root_observation['personallyViewedImages']) and
      any(x['path'].startswith('browser/17-') and 'no modal' in x['observations'] for x in root_observation['personallyViewedImages']))

rows = capture['rows'] + [{
    'number':17,'expectedRevision':47,'displacement':[0,0],
    'browserBinding':bind(STAGE/'browser/17-post-dialog-settled47.json'),
    'interactiveSvgBinding':next(r['interactiveSvgBinding'] for r in capture['rows'] if r['number']==16),
    'sceneBinding':next(r['sceneBinding'] for r in capture['rows'] if r['number']==16),
    'expectationReuse':'Same actual saved47 and same committed public whole scene; 17 is separately bound, no new reconstruction.'
}]
baseline = ET.fromstring(load(STAGE/'browser/01-finalbuild-rev39-baseline.json')['before']['svg'])
baseline_nodes = groups(baseline,'data-node-id',True)
browser_results = []
expected_revisions = {1:39,2:40,3:41,4:42,5:43,6:44,7:45,8:46,9:47,10:47,11:47,12:47,13:47,14:47,16:47,17:47}
node_id = 'repeat:instance:model.Transformer.encoder'
for row in rows:
    num = row['number']
    raw = load(ROOT/row['browserBinding']['path'])
    public = ET.fromstring(raw['before']['svg'])
    expected = ET.parse(ROOT/row['interactiveSvgBinding']['path']).getroot()
    scene = load(ROOT/row['sceneBinding']['path'])
    prefix = f'browser{num:02d}'
    check(prefix+':complete-public-XML',canonical(public)==canonical(expected))
    pm,em = metadata(public),metadata(expected)
    for k in em:
        check(prefix+':metadata:'+k,pm.get(k)==em[k])
    check(prefix+':revision-chain',pm['revision']==expected_revisions[num] and
          public.get('data-revision')==str(expected_revisions[num]) and
          dict(raw['before']['sceneAttrs'])['data-committed-revision']==str(expected_revisions[num]) and
          raw['after']['rev']==str(expected_revisions[num]))
    check(prefix+':committed-scene',dict(raw['before']['sceneAttrs'])['data-scene-kind']=='committed')
    check(prefix+':script-identity',raw['before']['scripts']==['http://127.0.0.1:42938/assets/index-CU5JhnoS.js'])
    check(prefix+':public-svg-length',len(raw['before']['svg'])==raw['before']['svgLength'])
    check(prefix+':sourcefact-inventory',pm['sourceFacts']==facts and len(facts)==49)
    for fact in pm['sourceFacts']:
        check(prefix+':source-fact:'+fact['id'],fact==next(f for f in facts if f['id']==fact['id']))
    for attr,only in [('data-node-id',True),('data-edge-id',False),('data-port-id',False)]:
        pg,eg = groups(public,attr,only),groups(expected,attr,only)
        check(prefix+':inventory:'+attr,set(pg)==set(eg))
        for id_,g in pg.items():
            check(prefix+':object:'+attr+':'+id_,id_ in eg and canonical(g)==canonical(eg[id_]))
    for binding in pm['renderedBindings']:
        check(prefix+':canonical-primary:'+binding['sceneEdgeId'],
              {k:binding[k] for k in ['source','target','tensorId','role']} ==
              {k:arch_edges[binding['sceneEdgeId']][k] for k in ['source','target','tensorId','role']})
        check(prefix+':canonical-members:'+binding['sceneEdgeId'],
              all(id_ in arch_edges for id_ in binding['canonicalEdgeIds']))
    for rendered in pm['renderedNodes']:
        check(prefix+':canonical-node:'+rendered['sceneNodeId'],rendered['canonicalNodeId'] in arch_nodes)
    # All direct body rectangles, including Repeat rear layers, obey the literal
    # world displacement. Other body rectangles remain equal to baseline.
    nodes = groups(public,'data-node-id',True)
    dx,dy = row['displacement']
    for id_,g in nodes.items():
        old_rects = list(baseline_nodes[id_].findall(NS+'rect'))
        new_rects = list(g.findall(NS+'rect'))
        delta = [dx,dy] if id_==node_id else [0,0]
        check(prefix+':body-literal-position:'+id_,len(old_rects)==len(new_rects) and
              all(abs(float(n.get('x'))-float(o.get('x'))-delta[0])<1e-9 and
                  abs(float(n.get('y'))-float(o.get('y'))-delta[1])<1e-9 and
                  all(n.get(k)==o.get(k) for k in ['width','height','rx','fill','stroke'])
                  for n,o in zip(new_rects,old_rects)))
    if num in [3,5,7,9,10,11,12,13,14,16,17]:
        check(prefix+':restored-full-scene-minus-revision',no_revision(public)==no_revision(baseline))
    memory = next(e for e in scene['edges'] if e['id']=='edge:44')
    expected_path = {2:'M 285 464.1 H 302.5 V 448.1 H 320',4:'M 285 432.1 H 302.5 V 448.1 H 320',
                     6:'M 261 448.1 H 320',8:'M 309 448.1 H 320'}.get(num,'M 285 448.1 H 320')
    check(prefix+':literal-memory-path',memory['path']==expected_path)
    browser_results.append({'number':num,'revision':pm['revision'],'nodes':len(pm['renderedNodes']),
                            'edges':len(pm['renderedBindings']),'sourceFacts':len(pm['sourceFacts']),
                            'memoryPath':memory['path'],'publicXmlExact':canonical(public)==canonical(expected)})

initial = load(STAGE/'browser/12-reopen-initial47.json')
settled = load(STAGE/'browser/13-reopen-settled47.json')
check('camera-initial-default-preserved','translate(35px, 35px) scale(0.9)' in initial['before']['paper'])
check('camera-settled-after12-and13',initial['after']['paper']==settled['before']['paper'] and
      'translate(98.7778px, 46px) scale(0.677778)' in settled['before']['paper'])
check('camera-first-paint-not-certified',root_observation['reopen']['firstPaintContinuityCertified'] is False)
check('camera-final17-same-settled',load(STAGE/'browser/17-post-dialog-settled47.json')['before']['paper']==settled['before']['paper'])
check('save-ui-recorded', '保存' in load(STAGE/'browser/10-save47.json')['before']['footer'] and
      'rev 47' in load(STAGE/'browser/11-settled-save47.json')['before']['footer'])
ui = load(STAGE/'browser/15-actual180pdf-ui.json')
pdf_id = root_observation['actualWhole180mmExportIds']['pdf']
svg_id = root_observation['actualWhole180mmExportIds']['svg']
check('pdf-ui-actual-links',ui['links']==[f'http://127.0.0.1:42938/api/exports/{pdf_id}/figure.pdf',
                                       f'http://127.0.0.1:42938/api/exports/{pdf_id}/receipt'])
for literal in ['视觉版本 47','180 × 208.3 mm','9.48 pt','6.56 pt','1.09 pt','193 × 223.3 mm']:
    check('pdf-ui-preflight:'+literal,literal in ui['dialogs'][0])

pub = ET.parse(EXPECT/'saved47.publication.svg').getroot()
pub_meta = metadata(pub)
actual_svg_path = STAGE/'actual-export-work'/svg_id/'figure.svg'
actual_svg = ET.parse(actual_svg_path).getroot()
compare_pub = copy.deepcopy(pub)
compare_actual = copy.deepcopy(actual_svg)
for key in ['width','height']:
    compare_pub.attrib.pop(key)
    compare_actual.attrib.pop(key)
check('actual-svg-complete-XML-except-normalized-physical-root',canonical(compare_pub)==canonical(compare_actual))
check('actual-svg-complete-metadata',metadata(actual_svg)==pub_meta)
check('actual-svg-sourcefact-inventory',metadata(actual_svg)['sourceFacts']==facts)
export_results=[]
for format_,id_ in [('svg',svg_id),('pdf',pdf_id)]:
    export_dir = STAGE/'actual-export-work'/id_
    receipt = load(export_dir/f'figure.{format_}.receipt.json')
    artifact_binding = bind(export_dir/f'figure.{format_}')
    check(format_+':actual-document-exact-saved47',load(export_dir/'document.json')==doc)
    check(format_+':actual-output-hash-and-bytes',artifact_binding['sha256']==receipt['outputDigest'] and artifact_binding['bytes']==receipt['bytes'])
    check(format_+':normalized-svg-hash',receipt['svgDigest']==bind(actual_svg_path)['sha256'])
    for k in ['documentId','revision','sourceDigest','irDigest','renderer']:
        check(format_+':receipt-identity:'+k,receipt[k]==pub_meta[k])
    check(format_+':current-scene-SVG-digest',receipt['sceneSvgDigest']==receipt['inputSvgDigest']==bind(EXPECT/'saved47.publication.svg')['sha256'])
    check(format_+':formal-publication-origin',receipt['publicationOrigin']==str(ROOT/'src/archcanvas_publication/exporter.py'))
    check(format_+':physical-page-ratio',receipt['widthMm']==180 and
          math.isclose(receipt['heightMm'],180*810/700,abs_tol=1e-10) and receipt['viewBox']==[0,0,700,810])
    for k in ['widthMm','heightMm','minTextPt','nodeLabelPt','minMainLinePt','suggestedWidthFor7Pt','suggestedHeightFor7Pt','exampleTargetPt','claim']:
        check(format_+':preflight:'+k,receipt['physicalPreflight'][k]==capture['preflight'][k])
    check(format_+':font-limits-preserved',receipt['fonts']['embeddingGuaranteed'] is False)
    export_results.append({'format':format_,'exportId':id_,'documentExact':load(export_dir/'document.json')==doc,
                           'canvasRevision':receipt['revision'],'storageRevision':saved['revision'],
                           'bytes':artifact_binding['bytes'],'outputDigest':artifact_binding['sha256'],
                           'widthMm':receipt['widthMm'],'heightMm':receipt['heightMm']})

# Physical attributes use declared eight significant decimal digits, rather
# than the renderer's rounded two-decimal root height. Other XML is exact.
for attr,expected_mm in [('width',180),('height',180*810/700)]:
    actual_mm = float(actual_svg.get(attr).removesuffix('mm'))
    check('actual-svg-physical-root:'+attr,actual_svg.get(attr).endswith('mm') and
          abs(actual_mm-expected_mm)<=5e-6,
          {'actualMm':actual_mm,'expectedMm':expected_mm,'serializationToleranceMm':5e-6})

pdf_bytes=(STAGE/'actual-export-work'/pdf_id/'figure.pdf').read_bytes()
pdf_receipt=load(STAGE/'actual-export-work'/pdf_id/'figure.pdf.receipt.json')
boxes=re.findall(rb'/MediaBox\s*\[\s*([-+0-9.]+)\s+([-+0-9.]+)\s+([-+0-9.]+)\s+([-+0-9.]+)\s*\]',pdf_bytes)
box=[float(x) for x in boxes[0]] if boxes else []
check('pdf-pagebox-one-page',len(boxes)==1 and box[:2]==[0,0])
check('pdf-pagebox-receipt',box[2:]==pdf_receipt['pageSizePt'])
check('pdf-pagebox-independent-mm',len(box)==4 and abs(box[2]-180/25.4*72)<=1e-6 and abs(box[3]-(180*810/700)/25.4*72)<=1e-6)
check('pdf-formal-converter-path',pdf_receipt['pythonExecutable']==str(ROOT/'.venv/bin/python') and
      pdf_receipt['converterOrigin']==str(ROOT/'.venv/lib/python3.11/site-packages/cairosvg/__init__.py'))

def simplify(points):
    out=[]
    for p in points:
        if out and p==out[-1]:
            continue
        if len(out)>=2:
            a,b=out[-2:]
            cross=(b[0]-a[0])*(p[1]-b[1])-(b[1]-a[1])*(p[0]-b[0])
            dot=(b[0]-a[0])*(p[0]-b[0])+(b[1]-a[1])*(p[1]-b[1])
            if abs(cross)<1e-8 and dot>=0:
                out.pop()
        out.append(p)
    return out

def svg_polyline(path):
    tokens=re.findall(r'[MLHVmlhv]|[-+]?(?:\d*\.\d+|\d+)(?:[eE][-+]?\d+)?',path)
    points=[]; i=0; x=y=0
    while i<len(tokens):
        command=tokens[i];i+=1
        if command in ['M','L']:
            x,y=float(tokens[i]),float(tokens[i+1]);i+=2
        elif command=='H':
            x=float(tokens[i]);i+=1
        elif command=='V':
            y=float(tokens[i]);i+=1
        else:
            raise ValueError('Unsupported captured centreline command: '+command)
        points.append([x,y])
    return simplify(points)

streams=[]
for match in re.finditer(rb'stream\r?\n(.*?)\r?\nendstream',pdf_bytes,re.S):
    try:
        streams.append(zlib.decompress(match[1]))
    except zlib.error:
        pass
drawings=[s.decode('latin1') for s in streams if b'1 0 0 -1 0 590.416186 cm' in s]
check('pdf-drawingstream-one',len(drawings)==1)
pattern=r'[-+0-9.]+\s+[-+0-9.]+\s+m\s+(?:[-+0-9.]+\s+[-+0-9.]+\s+l\s+)+S'
pdf_polylines=[]
for stream in drawings:
    for match in re.finditer(pattern,stream):
        pairs=re.findall(r'([-+0-9.]+)\s+([-+0-9.]+)\s+[ml]',match[0])
        pdf_polylines.append(simplify([[float(x),float(y)] for x,y in pairs]))
scale=180/25.4*72/700
pub_scene=load(EXPECT/'saved47.publication.scene.json')
pdf_route_results=[]
for edge in pub_scene['edges']:
    expected=[[x*scale,y*scale] for x,y in svg_polyline(edge['path'])]
    candidates=[]
    for index,poly in enumerate(pdf_polylines):
        if len(poly)==len(expected):
            error=max(abs(a-b) for p,q in zip(poly,expected) for a,b in zip(p,q))
            if error<=0.0045:
                candidates.append({'pdfPolylineIndex':index,'maxCoordinateErrorPt':error,'points':poly})
    check('pdf-centreline:'+edge['id'],len(candidates)==1,{'matches':len(candidates),'tolerancePt':0.0045})
    pdf_route_results.append({'id':edge['id'],'svgPath':edge['path'],'expectedPointPolyline':expected,
                              'matches':candidates})
check('pdf-centrelines-complete',len(pdf_route_results)==12 and all(len(r['matches'])==1 for r in pdf_route_results))
check('pdf-centrelines-distinct',len({r['matches'][0]['pdfPolylineIndex'] for r in pdf_route_results if r['matches']})==12)

input_after=[bind(b['path']) for b in input_bindings]
check('audit-inputs-before-after',input_after==input_bindings)
passed=sum(r['passed'] for r in relations)
failures=[r for r in relations if not r['passed']]
report={'schema':'archcanvas-independent-browser-export-readback/1',
        'createdUtc':datetime.now(timezone.utc).isoformat(),
        'pythonExecutable':sys.executable,'cases':19,'browserPublicSvgCases':16,'browserRecordCases':17,
        'actualArtifactCases':2,'relations':len(relations),'passed':passed,'failed':len(failures),
        'inputBindings':input_bindings,'inputAfter':input_after,'inputsUnchanged':input_after==input_bindings,
        'browserResults':browser_results,'exports':export_results,'pdfRoutes':pdf_route_results,
        'relationResults':relations,'failures':failures,
        'scope':'Bounded stdlib XML/JSON/hash/physical-root/PDF-pagebox/12-PDF-centreline consistency against separately reconstructed current-core expectations and actual saved47. No browser mutation and no actual export regeneration.',
        'limits':[
            'Public SVG comparison checks all captured XML, facts, object bodies/ports/styles/titles and canonical metadata. Intermediate hidden whole documents are reconstructed expectations, not captured browser documents.',
            'Capture17 reuses captured saved47/current whole-scene expectation from16; it is independently input-bound. Captures02/04/10 have root-observed stale raster footer/status;16 has root-observed stale modal. This auditor did not view pixels. Root separately viewed17 without modal; no all-frame freshness certification.',
            'Initial reopen12 publicDOM has default camera35,35/0.9; after12 and13/17 settle98.7778,46/0.677778. First-paint continuity is not certified.',
            'Native four-direction node moves are finite Encoder moves and undo. Global aesthetics, mask congestion, narrow-gap transitions and expanded-memory continuity remain open.',
            'PDF audit reads one pagebox and twelve centreline paths with0.0045pt tolerance for Cairo1/256pt quantization/decimal serialization. It does not independently certify PDF text shaping, font resolution/embedding or full semantic metadata.',
            'Actual export documents2/2exact saved Canvas47/storage7 and receipts are bound. SVG full metadata is checked independently from captured architecture; this is preservation evidence, not a new AST/source truth analysis.',
            'Script URL identity plus exact local dist/check snapshot binds currentbuild; response/served asset bytes are unverified.',
            '180mm min nominal text6.56018pt requires actual physical/font/line review; UI recommends193mm as adjustable7pt starting measurement. Physical publication, readability and glyph shaping are not accepted.',
            'No human participants added, no model execution/source writeback, no presented FPS/performance approval. M4partial; M5not_started.'
        ],'humanParticipants':0,'M4':'partial','M5':'not_started'}
(OUT/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'cases':report['cases'],'publicSvgCases':16,'relations':len(relations),'passed':passed,
                  'failed':len(failures),'inputs':len(input_bindings),'inputsUnchanged':report['inputsUnchanged'],
                  'failures':failures},ensure_ascii=False))
raise SystemExit(0 if not failures else 1)
