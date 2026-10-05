"""Independent archived service/source/export checker; never imports or executes a model."""
from pathlib import Path
from datetime import datetime, timezone
import ast
import copy
import hashlib
import json
import re
import xml.etree.ElementTree as ET

from check_v2 import ROOT, RAW, OUT, Rejected, need, close, tag, points, hit, cross, overlap

DRAFT = 'draft-e9f99d9c-da58-4407-8a1c-2fb44997741a'
PROJECT = '7bb8b017622f4479b71837138c74af0a'
DOCUMENT = 'canvas-architecture-model.AuthoredModel-b7070bac8587-6dcb37ea'
PDF_DIR = '6da4a5a321fb4100bd3900b1e5a0ffd9'
SVG_DIR = '7dd1ec51c9a84ca8a5c9bbb6fa220f02'
FILES = RAW / 'service-files'

def digest(value): return hashlib.sha256(value).hexdigest()
def read_json(path): return json.loads(path.read_bytes())
def syntax(node, expected): return ast.dump(node, include_attributes=False) == ast.dump(ast.parse(expected, mode='eval').body, include_attributes=False)

def inspect_source(draft_envelope, project, source, document_envelope, export_document):
    draft=draft_envelope['draft'];document=document_envelope['document'];architecture=document['architecture']
    need(draft_envelope['revision']==2 and draft['revision']==19,'recorded draft storage/history revisions changed')
    need(document_envelope['revision']==1 and document['revision']==0,'recorded canvas storage/document revisions changed')
    need(draft['id']==DRAFT and draft['mode']=='authored-draft' and draft['schemaVersion']==1,'draft identity/mode changed')
    need(project=={'id':PROJECT,'entry':'model:AuthoredModel','scope':'managed-copy'},'managed project identity changed')
    need(document==export_document,'stored canvas differs from export document')
    baseline=read_json(RAW/'saved-baseline.json')
    need([(n['id'],n['label'],n['kind'],(n['position']['x'],n['position']['y'])) for n in draft['nodes']]==
         [(n['id'],n['label'],kind,tuple(map(float,re.fullmatch(r'translate\(([^ ]+) ([^)]+)\)',n['transform']).groups()))) for n,kind in zip(baseline['positions'],['Input','Linear','ReLU','Output'])],'saved draft public node geometry differs')
    need(len(draft['edges'])==3 and [e['id'] for e in draft['edges']]==[e['id'] for e in baseline['edges']],'saved draft edge identities differ')
    for i,e in enumerate(draft['edges']):
        need(e['source']=={'nodeId':draft['nodes'][i]['id'],'portId':'output'} and e['target']=={'nodeId':draft['nodes'][i+1]['id'],'portId':'input'},'saved draft typed chain differs')
    need(draft['nodes'][0]['parameters']=={'shape':[1,16],'dtype':'float32'},'recorded input parameters changed')
    need(draft['nodes'][1]['parameters']=={'in_features':16,'out_features':48,'bias':True},'recorded Linear parameters changed')
    need(draft['nodes'][2]['parameters']==draft['nodes'][3]['parameters']=={},'recorded nonparameter modules changed')
    tree=ast.parse(source)
    need(len(tree.body)==4 and isinstance(tree.body[0],ast.Expr) and isinstance(tree.body[0].value,ast.Constant), 'unexpected generated top-level structure')
    need(isinstance(tree.body[1],ast.Import) and [a.name for a in tree.body[1].names]==['torch'],'generated import changed')
    need(isinstance(tree.body[2],ast.ImportFrom) and tree.body[2].module=='torch' and [a.name for a in tree.body[2].names]==['nn'],'generated nn import changed')
    cls=tree.body[3];need(isinstance(cls,ast.ClassDef) and cls.name=='AuthoredModel' and len(cls.bases)==1 and syntax(cls.bases[0],'nn.Module'),'generated class changed')
    need(len(cls.body)==2 and all(isinstance(f,ast.FunctionDef) for f in cls.body),'generated method structure changed')
    init,forward=cls.body;need(init.name=='__init__' and forward.name=='forward' and len(init.body)==3 and len(forward.body)==3,'generated method lengths changed')
    need(isinstance(init.body[0],ast.Expr) and syntax(init.body[0].value,'super().__init__()'),'generated initializer changed')
    attrs=[]
    for declaration,expected in zip(init.body[1:],['nn.Linear(in_features=16, out_features=48, bias=True, dtype=torch.float32)','nn.ReLU()']):
        need(isinstance(declaration,ast.Assign) and len(declaration.targets)==1 and isinstance(declaration.targets[0],ast.Attribute) and syntax(declaration.targets[0].value,'self'),'generated module assignment changed')
        need(syntax(declaration.value,expected),'generated module parameters differ from saved draft')
        attrs.append(declaration.targets[0].attr)
    need(attrs[0]!=attrs[1],'generated module aliases collide')
    need([a.arg for a in init.args.args]==['self'] and [a.arg for a in forward.args.args][0]=='self' and len(forward.args.args)==2,'generated forward inputs differ')
    input_name=forward.args.args[1].arg;previous=input_name
    for statement,attribute in zip(forward.body[:2],attrs):
        need(isinstance(statement,ast.Assign) and len(statement.targets)==1 and isinstance(statement.targets[0],ast.Name) and statement.targets[0].id==attribute,'generated data variable changed')
        need(syntax(statement.value,'self.'+attribute+'('+previous+')'),'generated chain data binding changed');previous=attribute
    result=forward.body[2];need(isinstance(result,ast.Return) and syntax(result.value,repr({draft['nodes'][3]['id']:None}).replace('None',previous)),'generated output binding changed')
    need(document['id']==DOCUMENT and document['title']==draft['title'],'document identity/title changed')
    need(architecture['entry']==project['entry'] and architecture['sourceDigest']==document['sourceBindingDigest'],'source binding digest disagreement')
    need(architecture['sources']==[{'path':'model.py','content':source,'digest':digest(source.encode())}],'architecture source bytes/digest changed')
    canonical=['input:model.AuthoredModel:'+input_name]+['call:instance:model.AuthoredModel.'+a for a in attrs]+['output:model.AuthoredModel:0']
    nodes={n['id']:n for n in architecture['nodes']};container='call:instance:model.AuthoredModel'
    need(set(nodes)==set(canonical+[container]),'canonical node identity set differs')
    need([nodes[n]['kind'] for n in canonical]==['Input','Linear','ReLU','Output'] and nodes[container]['kind']=='Module','canonical module kinds differ')
    need(document['displayAliases']=={n:draft['nodes'][i]['label'] for i,n in enumerate(canonical)},'saved display aliases differ')
    linear=nodes[canonical[1]]
    need(linear['parameters']=={'in_features':16,'out_features':48,'bias':True,'dtype':{'expression':'torch.float32','origin':'unknown'}},'architecture Linear parameters differ')
    need(nodes[canonical[3]]['outputPath']==[{'kind':'key','key':draft['nodes'][3]['id']}],'canonical output path differs')
    ports={};directions={canonical[0]:['out'],canonical[1]:['in','out'],canonical[2]:['in','out'],canonical[3]:['in'],container:['in']}
    for identity,node in nodes.items():
        need([p['direction'] for p in node['ports']]==directions[identity],'canonical port directions differ')
        for p in node['ports']:
            need(p['role']=='data' and p['id'] not in ports,'canonical port role/uniqueness differs');ports[p['id']]=(identity,p['direction'])
    need(len(architecture['edges'])==4,'canonical edge count differs')
    pairs=[(canonical[0],container)]+list(zip(canonical,canonical[1:]))
    for i,(edge,(source_id,target_id)) in enumerate(zip(architecture['edges'],pairs)):
        need(edge['id']=='edge:'+str(i) and edge['role']=='data' and edge['source']['nodeId']==source_id and edge['target']['nodeId']==target_id,'canonical edge binding differs')
        need(ports.get(edge['source']['portId'])==(source_id,'out') and ports.get(edge['target']['portId'])==(target_id,'in'),'canonical edge typed port differs')
    return {'draftId':draft['id'],'draftStorageRevision':draft_envelope['revision'],'draftHistoryRevision':draft['revision'],'documentStorageRevision':document_envelope['revision'],'canvasDocumentRevision':document['revision'],'parameters':draft['nodes'][1]['parameters'],'canonicalNodes':canonical,'sourceSha256':digest(source.encode()),'canonicalChainEdges':architecture['edges'][1:],'modelExecutionVerified':False,'sourceShapeClaim':'Input shape [1,16] is a draft declaration; no runtime shape inference is certified.'}

def inspect_publication(svg_bytes,document):
    xml=ET.fromstring(svg_bytes);architecture=document['architecture']
    metadata=json.loads(next(e.text for e in xml if tag(e)=='metadata'))
    physical=[float(xml.get(k).removesuffix('mm')) for k in ['width','height']]
    need(xml.get('viewBox')=='0 0 595 650' and physical[0]==180 and close(physical[1],metadata['heightMm'],.01),'publication physical XML dimensions differ')
    need(metadata['documentId']==document['id'] and metadata['revision']==document['revision'] and metadata['sourceDigest']==architecture['sourceDigest'] and metadata['irDigest']==architecture['irDigest'],'publication metadata binding differs')
    groups={e.get('data-canonical-id'):e for e in xml.iter() if e.get('data-canonical-id')}
    need(set(groups)=={n['id'] for n in architecture['nodes']},'publication actual canonical nodes differ')
    node_map={n['id']:n for n in architecture['nodes']};bodies={}
    for identity,group in groups.items():
        rect=next(e for e in group if tag(e)=='rect');bodies[identity]=tuple(float(rect.get(k)) for k in ['x','y','width','height'])
        need(group.get('data-node-id')==identity and group.get('aria-label')==document['displayAliases'].get(identity,node_map[identity]['label']),'publication actual canonical labels differ')
    port_map={}
    for e in xml.iter():
        if e.get('data-port-id'):
            owner=e.get('data-node-id');dot=e if tag(e)=='circle' else next(p for p in e if tag(p)=='circle' and p.get('fill')!='transparent')
            need(owner in node_map,'publication foreign port owner')
            declared=next((p for p in node_map[owner]['ports'] if e.get('data-port-id')==owner+':'+p['id']+':data'),None)
            need(declared is not None and (owner,declared['id']) not in port_map,'publication wrong/duplicate port')
            port_map[owner,declared['id']]=(float(dot.get('cx')),float(dot.get('cy')))
    expected_edges={e['id']:e for e in architecture['edges'][1:]}
    routes={};marker_ids={e.get('id') for e in xml.iter() if tag(e)=='marker'};endpoint_error=0
    for group in xml.iter():
        identity=group.get('data-edge-id')
        if not identity:continue
        need(identity in expected_edges and identity not in routes,'publication actual edge identities differ')
        edge=expected_edges[identity];paths=[e for e in group if tag(e)=='path' and e.get('marker-end')];need(len(paths)==1,'publication missing/duplicate arrow path')
        path=paths[0];marker=re.fullmatch(r'url\(#([^)]*)\)',path.get('marker-end'));need(marker and marker.group(1) in marker_ids,'publication detached arrow marker')
        polyline=points(path.get('d'));routes[identity]=polyline
        need(group.get('data-tensor-id')==edge['tensorId'],'publication tensor binding differs')
        for point,endpoint in [(polyline[0],edge['source']),(polyline[-1],edge['target'])]:
            need((endpoint['nodeId'],endpoint['portId']) in port_map,'publication missing bound port')
            port=port_map[endpoint['nodeId'],endpoint['portId']];error=max(abs(a-b) for a,b in zip(point,port));endpoint_error=max(endpoint_error,error)
            need(error<=.051,'publication detached endpoint')
        for a,b in zip(polyline,polyline[1:]):
            for owner,body in bodies.items():
                if node_map[owner]['kind']!='Module':need(not hit(a,b,body),'publication arrow penetrates leaf body')
        length=sum(abs(a[0]-b[0])+abs(a[1]-b[1]) for a,b in zip(polyline,polyline[1:]));need(close(length,abs(polyline[0][0]-polyline[-1][0])+abs(polyline[0][1]-polyline[-1][1])),'publication unnecessary detour')
    need(set(routes)==set(expected_edges),'publication missing visible chain edge')
    for i,e in enumerate(metadata['renderedBindings']):
        expected=architecture['edges'][i+1];need(e['sceneEdgeId']==expected['id'] and e['canonicalEdgeIds']==[expected['id']] and all(e[k]==expected[k] for k in ['source','target','tensorId','role']),'publication metadata typed binding differs')
    need(len(metadata['renderedBindings'])==3 and len(metadata['renderedNodes'])==5,'publication metadata counts differ')
    for i,e in enumerate(routes.values()):
        for f in list(routes.values())[i+1:]:
            for a,b in zip(e,e[1:]):
                for c,d in zip(f,f[1:]):need(cross(a,b,c,d) is None and overlap(a,b,c,d)<=.02,'publication arrow crossing/overlap')
    return {'metadata':metadata,'bodyRects':bodies,'routes':routes,'portCount':len(port_map),'physicalXmlRootMm':physical,'maxEndpointRoundingSvgUnits':endpoint_error,'bends':sum(len(p)-2 for p in routes.values()),'properCrossings':0,'collinearOverlaps':0,'leafBodyPenetrations':0,'publicationHumanReviewCertified':False}

def inspect_pdf(pdf_bytes,receipt):
    need(pdf_bytes.startswith(b'%PDF-') and pdf_bytes.rstrip().endswith(b'%%EOF'),'PDF envelope incomplete')
    need(digest(pdf_bytes)==receipt['outputDigest'] and len(pdf_bytes)==receipt['bytes'],'PDF output digest/length differs')
    media=re.findall(rb'/MediaBox\s*\[([^]]+)\]',pdf_bytes);need(len(media)==1,'PDF page count/media box differs')
    box=list(map(float,media[0].split()));need(len(box)==4 and box[:2]==[0,0],'PDF media box origin differs')
    dimensions=[v*25.4/72 for v in box[2:]]
    need(close(dimensions[0],180,.0001) and close(dimensions[1],receipt['heightMm'],.0001),'PDF physical size differs')
    return {'sha256':digest(pdf_bytes),'bytes':len(pdf_bytes),'mediaBoxPt':box,'measuredMm':dimensions,'fontNamesObserved':[v.decode() for v in re.findall(rb'/BaseFont\s*/([^\s/]+)',pdf_bytes)],'fontFidelityOrGlyphShapingCertified':False,'rasterOrVisualReviewCertified':False}

def run():
    manifest_path=RAW/'service-files-manifest.json';manifest=read_json(manifest_path);bindings={}
    for b in manifest['bindings']:
        need('approval-key' not in b['path'] and 'approval-key' not in b['archivePath'],'private signing key present in shareable archive')
        archived=ROOT/b['archivePath'];live=ROOT/b['path'];need(ROOT in archived.resolve().parents and ROOT in live.resolve().parents,'manifest path escapes project')
        raw=archived.read_bytes();need(raw==live.read_bytes() and len(raw)==b['bytes'] and digest(raw)==b['sha256'],'service artifact copy/digest mismatch')
        bindings[b['archivePath']]={'bytes':len(raw),'sha256':digest(raw)}
    draft=read_json(FILES/'drafts'/f'{DRAFT}.json');project=read_json(FILES/'projects'/PROJECT/'project.json')
    source=(FILES/'projects'/PROJECT/'source/model.py').read_text();document=read_json(FILES/'documents'/f'{DOCUMENT}.json')
    exported=read_json(FILES/'exports'/SVG_DIR/'document.json');need(exported==read_json(FILES/'exports'/PDF_DIR/'document.json'),'SVG/PDF export document mismatch')
    source_result=inspect_source(draft,project,source,document,exported)
    generated_dom=(RAW/'generated-review-dom.txt').read_text();need('nn.Linear(in_features=16, out_features=48, bias=True, dtype=torch.float32)' in generated_dom,'public generated review differs from saved source')
    saved=(RAW/'source-saved-svg.xml').read_bytes();reopened=(RAW/'source-reopened-svg.xml').read_bytes();need(saved==reopened,'reopened browser source SVG bytes differ')
    svg=(FILES/'exports'/SVG_DIR/'figure.svg').read_bytes();publication=inspect_publication(svg,exported);browser=inspect_publication(saved,exported)
    need({k:v for k,v in publication.items() if k!='physicalXmlRootMm'}=={k:v for k,v in browser.items() if k!='physicalXmlRootMm'},'browser/publication actual geometry or bindings differ')
    receipts={kind:read_json(FILES/'exports'/directory/f'figure.{kind}.receipt.json') for kind,directory in [('pdf',PDF_DIR),('svg',SVG_DIR)]}
    for kind,receipt in receipts.items():
        need(receipt['documentId']==exported['id'] and receipt['revision']==exported['revision'] and receipt['sourceDigest']==exported['architecture']['sourceDigest'] and receipt['irDigest']==exported['architecture']['irDigest'],'receipt source/document binding differs')
        need(receipt['svgDigest']==digest(svg) and receipt['widthMm']==180 and receipt['exportScope']=={'kind':'document'},'receipt SVG/width/scope differs')
    need(receipts['svg']['outputDigest']==digest(svg) and receipts['svg']['bytes']==len(svg),'SVG output digest/length differs')
    need(svg.startswith(b'<svg'),'export SVG encoding changed')
    pdf_bytes=(FILES/'exports'/PDF_DIR/'figure.pdf').read_bytes();pdf=inspect_pdf(pdf_bytes,receipts['pdf'])
    counters=[]
    def reject(name,callback):
        try:callback()
        except (Rejected,ValueError,IndexError,KeyError,ET.ParseError) as error:counters.append({'name':name,'rejected':True,'reason':str(error)})
        else:raise AssertionError('missed counterexample '+name)
    def case(name,index,mutate):
        values=copy.deepcopy([draft,project,source,document,exported]);mutate(values[index]);reject(name,lambda:inspect_source(*values))
    case('draft-store-revision-drift',0,lambda v:v.update(revision=1))
    case('draft-history-revision-drift',0,lambda v:v['draft'].update(revision=20))
    case('draft-parameter-drift',0,lambda v:v['draft']['nodes'][1]['parameters'].update(out_features=49))
    case('draft-port-binding-drift',0,lambda v:v['draft']['edges'][0]['target'].update(portId='output'))
    case('managed-project-identity-drift',1,lambda v:v.update(id='foreign'))
    reject('generated-source-parameter-drift',lambda:inspect_source(draft,project,source.replace('out_features=48','out_features=49'),document,exported))
    relu_attr=source_result['canonicalNodes'][2].rsplit('.',1)[1];linear_attr=source_result['canonicalNodes'][1].rsplit('.',1)[1];input_attr=source_result['canonicalNodes'][0].rsplit(':',1)[1]
    reject('generated-source-chain-drift',lambda:inspect_source(draft,project,source.replace('self.'+relu_attr+'('+linear_attr+')','self.'+relu_attr+'('+input_attr+')'),document,exported))
    reject('generated-source-output-key-drift',lambda:inspect_source(draft,project,source.replace(draft['draft']['nodes'][3]['id'],'foreign'),document,exported))
    def consistent_document_case(name,mutate):
        value=copy.deepcopy(document);mutate(value['document']);reject(name,lambda:inspect_source(draft,project,source,value,value['document']))
    consistent_document_case('coherent-architecture-source-drift',lambda v:v['architecture']['sources'][0].update(content='foreign'))
    consistent_document_case('coherent-architecture-parameter-drift',lambda v:next(n for n in v['architecture']['nodes'] if n['kind']=='Linear')['parameters'].update(out_features=49))
    consistent_document_case('coherent-canonical-port-role-drift',lambda v:v['architecture']['nodes'][0]['ports'][0].update(role='mask'))
    consistent_document_case('coherent-canonical-edge-port-drift',lambda v:v['architecture']['edges'][1]['target'].update(portId='foreign'))
    consistent_document_case('coherent-display-alias-drift',lambda v:v['displayAliases'].update({source_result['canonicalNodes'][1]:'foreign'}))
    damaged=ET.fromstring(svg);edge=next(g for g in damaged.iter() if g.get('data-edge-id')=='edge:1');next(p for p in edge if tag(p)=='path').set('d','M 177 216 V 235 H 178.6 V 240')
    reject('coherent-publication-endpoint-detachment',lambda:inspect_publication(ET.tostring(damaged),exported))
    damaged=ET.fromstring(svg);metadata=next(e for e in damaged if tag(e)=='metadata');value=json.loads(metadata.text);value['sourceDigest']='foreign';metadata.text=json.dumps(value)
    reject('publication-source-digest-drift',lambda:inspect_publication(ET.tostring(damaged),exported))
    receipt=copy.deepcopy(receipts['pdf']);receipt['outputDigest']='foreign';reject('PDF-receipt-output-drift',lambda:inspect_pdf(pdf_bytes,receipt))
    damaged_pdf=pdf_bytes.replace(b'510.23622',b'500.23622');receipt=copy.deepcopy(receipts['pdf']);receipt['outputDigest']=digest(damaged_pdf)
    reject('coherent-PDF-media-box-drift',lambda:inspect_pdf(damaged_pdf,receipt))
    result={'schemaVersion':1,'recordedAt':datetime.now(timezone.utc).isoformat(),'scope':'Independent static checks of actual native UI/API session artifacts copied from the isolated service. No model execution or hidden browser state.','checkerSha256':digest(Path(__file__).read_bytes()),'geometryCheckerSha256':digest((OUT/'check_v2.py').read_bytes()),'manifestSha256':digest(manifest_path.read_bytes()),'archiveBindings':bindings,'source':source_result,'publication':publication,'sourceBrowserPhysicalXmlRootMm':browser['physicalXmlRootMm'],'pdf':pdf,'sourceBrowserSavedReopenedByteEquality':True,'sourceBrowserSvgSha256':digest(saved),'counterexamples':counters,'limits':['Original draft storage revision 1 bytes were not preserved; its parameters are not independently certified.','Generation preview is public DOM, but the native HTTP generation response/receipt was not captured; no browser receipt or correspondence digest is certified.','Source/IR digest fields agree between recorded artifacts; only the individual source SHA-256 is independently recomputed here.','The model was parsed with stdlib AST only, never imported or executed. No training/inference validity claim.','PDF page size and byte binding pass; rendered glyph shaping, font fidelity and publication appearance require separate review.','The paper diagram has four genuine bends across two endpoint center offsets; these are shortest paths at the observed positions, not a universal aesthetic acceptance.'],'humanAcceptanceCertified':False,'publicationAcceptanceCertified':False,'browserPerformanceCertified':False}
    (OUT/'service-audit.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'artifacts':len(bindings),'staticChain':'Input → Linear(16,48) → ReLU → Output','draftStorageRevision':2,'draftHistoryRevision':19,'browserSourceByteEquality':True,'paperBends':publication['bends'],'counterexamples':len(counters),'pdfMeasuredMm':pdf['measuredMm']},ensure_ascii=False))

if __name__=='__main__':run()
