#!/usr/bin/env python3
"""Check actual SVG geometry/style, frozen Git source, notebook cells and model facts."""
from __future__ import annotations
import argparse,ast,copy,hashlib,importlib,json,math,re,struct,zipfile
from pathlib import Path
import xml.etree.ElementTree as ET
from layout import validate
from models import KEYS as MODELS,VIEWS,BATCHES,selected
HERE=Path(__file__).resolve().parent
NUMBER=r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?"

def sha(data):
    return hashlib.sha256(data).hexdigest()


def read_json(path):
    if not path.is_file() or not path.stat().st_size:
        raise ValueError("missing/empty file: " + str(path))
    return json.loads(path.read_text(encoding="utf-8"))


def require(condition, message):
    if not condition:
        raise ValueError(message)


def close(a, b):
    if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
        return len(a) == len(b) and all(close(x, y) for x, y in zip(a, b))
    try:
        return math.isfinite(float(a)) and math.isfinite(float(b)) and abs(float(a) - float(b)) <= 1e-6
    except (TypeError, ValueError):
        return a == b


def numeric(value):
    return float(str(value).removesuffix("px"))


def path_points(data):
    tokens = re.findall(r"[A-Za-z]|" + NUMBER, data)
    remainder = re.sub(r"[A-Za-z]|" + NUMBER, "", data)
    require(not remainder.strip(" ,\t\r\n"), "unparsed SVG path content")
    require(len(tokens) >= 6 and len(tokens) % 3 == 0, "expected SVG M/L polyline")
    points = []
    for i in range(0, len(tokens), 3):
        require(tokens[i] == ("M" if i == 0 else "L"), "unsupported SVG path command")
        points.append([float(tokens[i + 1]), float(tokens[i + 2])])
    return points


def ast_symbols(source, filename):
    tree = ast.parse(source, filename=filename)
    tree.lineno = 1
    tree.end_lineno = len(source.splitlines())
    result = {'__module__': tree}
    def visit(body, prefix=""):
        for node in body:
            if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                name = prefix + node.name
                result[name] = node
                if isinstance(node, ast.ClassDef):
                    visit(node.body, name + ".")
    visit(tree.body)
    return result


def source_checks(folder,evidence,ir,manifest_path=None,source_root=None):
    manifest=read_json(Path(manifest_path or HERE/'source_manifest.json'))
    acquired_root=Path(source_root or HERE/'sources')
    slug=evidence['source_project'];project=manifest[slug]
    require(evidence['repository']==project['repository'] and evidence['commit']==project['commit'],'repository/commit mismatch')
    hashes={p:r['sha256'] for p,r in project['files'].items()}
    hashes.update({p:r['sha256'] for p,r in project.get('derived',{}).items()})
    expected_snapshot=sha(json.dumps(dict(repository=project['repository'],commit=project['commit'],files=hashes),sort_keys=True).encode())
    require(evidence['source_snapshot_sha256']==expected_snapshot,'source snapshot mismatch')
    projects={slug:project}
    if evidence.get('source_projects'):
        require(slug in evidence['source_projects'],'primary source project missing from joint evidence')
        for key,origin in evidence['source_projects'].items():
            p=manifest[key];projects[key]=p
            hashes={path:r['sha256'] for path,r in p['files'].items()}
            hashes.update({path:r['sha256'] for path,r in p.get('derived',{}).items()})
            expected=dict(repository=p['repository'],commit=p['commit'],snapshot=sha(json.dumps(dict(repository=p['repository'],commit=p['commit'],files=hashes),sort_keys=True).encode()))
            require(origin==expected,'joint source provenance mismatch: '+key)
        require(ir['source'].get('projects')==evidence['source_projects'],'IR joint source provenance differs')
    parsed={};source_lines={};notebooks={}
    for member,record in evidence['files'].items():
        path=Path(member)
        require(not path.is_absolute() and '..' not in path.parts and path.parts[0] in projects,'unsafe source path')
        data=(folder/'sources'/path).read_bytes()
        key=path.parts[0];p=projects[key]
        inner=path.relative_to(key).as_posix()
        pinned=p.get('derived',{}).get(inner) or p['files'][inner]
        if len(projects)>1:require(record.get('repository')==p['repository'] and record.get('commit')==p['commit'] and record.get('source_project')==key,'file provenance mismatch: '+member)
        require(sha(data)==record['sha256']==pinned['sha256'],'frozen source hash differs: '+member)
        require(data==(acquired_root/path).read_bytes(),'exported source differs from acquired copy: '+member)
        source=data.decode('utf-8-sig');source_lines[member]=source.splitlines()
        require(len(source_lines[member])==record['lines'],'source line count differs')
        if member.endswith('.py'):parsed[member]=ast_symbols(source,member)
        if member.endswith('.ipynb'):notebooks[member]=json.loads(source)
    for member,origin in evidence.get('notebook_origins',{}).items():
        notebook=notebooks[origin['original']]
        for row in origin['line_map']:
            cell=notebook['cells'][row['cell_index']]
            require(cell['cell_type']=='code','derived line points to non-code notebook cell')
            source=cell['source'];source=''.join(source) if isinstance(source,list) else source
            raw=source.splitlines()[row['cell_line']-1]
            actual=source_lines[member][row['derived_line']-1]
            require(actual==raw or actual=='# NOTEBOOK_MAGIC '+raw,'derived Python line differs from original cell')
            if actual!=raw:require(bool(re.match(r'^\s*(?:%{1,2}[A-Za-z_]\w*\b|![A-Za-z_])',raw)),'ordinary Python was wrongly removed as notebook magic')
    seen=set()
    for reference,span in evidence['symbols'].items():
        member,symbol=reference.split('::',1);node=parsed.get(member,{}).get(symbol)
        require(node is not None,'AST symbol missing: '+reference)
        require([node.lineno,node.end_lineno]==[span['start'],span['end']],'AST range mismatch')
        require('\n'.join(source_lines[member][node.lineno-1:node.end_lineno])==span['snippet'],'AST snippet mismatch')
        require(span['evidence_id'] not in seen,'duplicate evidence ID');seen.add(span['evidence_id'])
        origin=evidence.get('notebook_origins',{}).get(member)
        require(span.get('original_notebook')==(origin['original'] if origin else None),'AST span original notebook mismatch: '+reference)
        if origin:
            cells=sorted({m['cell_index'] for m in origin['line_map'] if span['start']<=m['derived_line']<=span['end']})
            require(cells==span['notebook_cells'],'AST span notebook cell mismatch')
    nodes={n['id']:n for n in ir['nodes']}
    require(len(nodes)==len(ir['nodes']) and nodes,'duplicate/empty IR nodes')
    for node in nodes.values():
        require(node.get('source') and all(s in evidence['symbols'] for s in node['source']),'node source missing')
        require(node['source_evidence']==[evidence['symbols'][s]['evidence_id'] for s in node['source']],'IR evidence differs')
        require(node['parent'] is None or node['parent'] in nodes,'unknown IR parent')
    require(len({e['id'] for e in ir['edges']})==len(ir['edges']),'duplicate IR edges')
    for edge in ir['edges']:
        for end in ('src','dst'):
            require(edge[end] in nodes and edge[end+'_port'] in nodes[edge[end]]['ports'],'unknown semantic endpoint/port')
    return dict(files=len(evidence['files']),symbols=len(evidence['symbols']),nodes=len(nodes),edges=len(ir['edges']),
                original_notebooks=len(notebooks),repository=evidence['repository'],commit=evidence['commit'])


def model_facts(key,ir):
    nodes={n['id']:n for n in ir['nodes']};edges=ir['edges'];profile=ir['profile'];checked=[]
    def check(condition,label):require(condition,key+': '+label);checked.append(label)
    def has(src,dst,role=None):return any(e['src']==src and e['dst']==dst and (not role or e['role']==role) for e in edges)
    def parameter(n):return n.get('param_identity',n.get('parameter',n.get('parameter_scope')))
    if key=='lenet':
        check(profile['input_size']==[32,32] and profile['activation']=='Tanh','32x32 Tanh profile')
        check(nodes['lenet.fc1']['parameter']=='classifier.0' and '400' in nodes['lenet.fc1']['label'],'400-feature classifier')
        check(has('lenet.returns','lenet.logits','fork') and has('lenet.returns','lenet.softmax','fork'),'same logits tensor forks, not tuple dispatch')
    elif key=='resnet':
        check(profile['stage_blocks']==[2,2,2,2] and profile['avgpool_called'] is False,'MNIST BasicBlock path without called AvgPool')
        for stage in (2,3,4):
            prefix=f'resnet.stage{stage}.downsample'
            check(has(prefix+'.paths',prefix+'.main','fork') and has(prefix+'.paths',prefix+'.shortcut','fork'),'same x supplies main and projected shortcut '+str(stage))
            check(nodes[prefix+'.proj_conv']['parameter'].endswith('.downsample.0') and nodes[prefix+'.proj_bn']['parameter'].endswith('.downsample.1'),'projected Conv and BN '+str(stage))
            check(has(prefix+'.add',prefix+'.relu2'),'Add precedes final ReLU '+str(stage))
    elif key=='densenet':
        check(profile['depth']==100 and profile['growthRate']==12 and profile['layers_per_block']==16,'BC100 growth/repeat profile')
        for block in (1,2,3):
            prefix=f'dense_b{block}'
            check(has(prefix+'_input',prefix+'_cat','dense_concat') and nodes[prefix+'_cat']['kind']=='concat','retained channels concatenate '+str(block))
            check(nodes[prefix]['repeat']['independent_parameters'] and nodes[prefix]['repeat']['count']==16,'16 distinct parameter instances '+str(block))
        check('342' in nodes['dense_fc']['label'] and 'LogSoftmax' in nodes['dense_log_softmax']['label'],'342 features and log-probability output')
    elif key=='unet':
        check(profile['init_features']==32 and profile['in_channels']==3 and profile['out_channels']==1,'default feature/input/output widths')
        for stage in range(1,5):
            check(has(f'unet_enc{stage}',f'unet_dec{stage}_cat','skip_concat'),'pre-pool encoder output reaches decoder Concat '+str(stage))
            check(parameter(nodes[f'unet_dec{stage}_upconv'])==f'upconv{stage}','learned transposed convolution '+str(stage))
        check('Sigmoid' in nodes['unet_sigmoid']['label'],'binary pixel sigmoid, not Softmax')
    elif key=='vae':
        check(parameter(nodes['vae.mu'])!=parameter(nodes['vae.logvar']),'independent mean and log-variance heads')
        check(nodes['vae.std']['expression']=='torch.exp(z_log_var / 2.)','std equals exp(logvar/2)')
        check(has('vae.epsilon','vae.noise_product','random_sample') and nodes['vae.epsilon']['origin']=='internal_random_source','noise is internal sampling, not a user feature')
        check(nodes['vae.return']['output_tuple']==['mu','logvar','encoded','decoded'],'four returned tensor fields')
        check(has('vae.mu','vae.return','retained_value') and has('vae.z','vae.return','retained_value'),'posterior statistics/z retained in forward return')
    elif key=='lstm':
        check(nodes['lstm.core']['opaque_runtime_boundary'] and nodes['lstm.core']['temporal_parameter_sharing'],'library boundary and weights shared across time')
        check(has('lstm.lengths','lstm.pack','sequence_length'),'external valid lengths drive packing')
        check(has('lstm.select_hidden','lstm.squeeze') and has('lstm.fc','lstm.flatten'),'hidden squeeze, then flattened logits')
        check(nodes['lstm.sigmoid']['parent']=='lstm.caller' and nodes['lstm.sigmoid']['boundary']=='caller','sigmoid belongs to caller, not model forward')
    elif key=='alexnet':
        check(profile['input_size']==[64,64] and profile['conv_groups']==[1,2,2,2,2],'64x64 caller and grouped Conv2-5')
        check([nodes[f'alex.conv_stage{i}.conv']['groups'] for i in range(1,6)]==[1,2,2,2,2],'groups are attributes of five real convolutions')
        check(nodes['alex.conv_stage5.pool']['shape']=='[B,256,1,1]' and nodes['alex.adaptive_pool']['shape']=='[B,256,6,6]' and nodes['alex.flatten']['shape']=='[B,9216]','1x1 features adaptively pooled to 6x6 and 9216 values')
        check(nodes['alex.unused_softmax']['returned'] is False and has('alex.classifier','alex.unused_softmax','computed_unused'),'Softmax computed from logits and not returned')
        check(not any(e['src']=='alex.unused_softmax' for e in edges),'unused probabilities have no return dependency')
    elif key=='mobilenetv2':
        check('torchvision-v0.9.0' in ir['source'].get('projects',{}),'notebook and exact torchvision implementation have separate provenance')
        check(profile['total_inverted_residual_blocks']==17 and profile['num_classes_after_replacement']==10,'17 blocks and replaced 10-class head')
        check([nodes[f'mobile.stage{i}']['feature_indices'] for i in range(1,8)]==[[1],[2,3],[4,5,6],[7,8,9,10],[11,12,13],[14,15,16],[17]],'independent source Sequential feature indices 1..17')
        blocks=[n for n in nodes.values() if 'use_res_connect' in n]
        check(sum(len(n['feature_indices']) for n in blocks)==17 and sum(len(n['feature_indices']) for n in blocks if n['use_res_connect'])==10,'10 conditional identity additions across 17 independent blocks')
        check('mobile.stage1.first.expand' not in nodes and nodes['mobile.stage1.first.depthwise.conv']['groups']==32,'ratio1 omits expansion and depthwise uses 32 groups')
        check(nodes['mobile.stage2.first.depthwise.conv']['groups']==96 and nodes['mobile.stage2.repeat']['use_res_connect'] and has('mobile.stage2.repeat','mobile.stage2.repeat.add','residual'),'ratio6 hidden96 and equal-channel repeat has residual')
        check(not nodes['mobile.stage5.first']['use_res_connect'] and not nodes['mobile.stage7.first']['use_res_connect'],'stride1 channel changes still omit skip')
        check(parameter(nodes['mobile.last.conv'])=='features.18.0' and parameter(nodes['mobile.fc'])=='classifier.1','source final convolution and replaced classifier identities')
        check(not any(n['kind']=='softmax' for n in nodes.values()),'forward returns logits without Softmax')
    elif key=='nin':
        check(sum(n['kind']=='conv' for n in nodes.values())==9 and sum(n['kind']=='activation' for n in nodes.values())==9,'nine Conv-ReLU pairs including class projection')
        check('MaxPool' in nodes['nin.pool1']['label'] and 'Average' in nodes['nin.pool2']['label'] and '8x8' in nodes['nin.pool3']['label'],'MaxPool then AvgPool and fixed final pool8')
        check(parameter(nodes['nin.mlpconv3.conv3'])=='classifier.20' and has('nin.mlpconv3.conv3','nin.mlpconv3.relu3'),'hard-coded 10-channel projection retains following ReLU')
        check(has('nin.returns','nin.logits','fork') and has('nin.returns','nin.softmax','fork'),'same logits produce two returned fields')
        check(not any(n['kind']=='linear' for n in nodes.values()),'class maps and average pooling replace a Linear head')
    elif key=='textcnn':
        check(profile['filter_widths']==[3,4,5] and profile['embedding_dim']==200 and profile['pooled_features']==384,'three widths and 384 pooled channels')
        for k,i in ((3,0),(4,1),(5,2)):
            p=f'textcnn.k{k}'
            check(parameter(nodes[p+'.conv'])==f'convolutions.{i}' and has('textcnn.lengths',p+'.count','sequence_length'),'independent convolution and external lengths for width '+str(k))
            check(nodes[p+'.valid_count']['suppress_input_boundary'] and nodes[p+'.count']['input_relation']['producer']=='textcnn.lengths','valid window count only consumes external lengths '+str(k))
            incoming=[e for e in edges if e['dst']==p+'.count']
            check(len(incoming)==1 and incoming[0]['src']=='textcnn.lengths','no feature-shape or tuple input to lengths arithmetic '+str(k))
            check(nodes[p+'.operands']['semantic_mode']=='operand_bundle' and nodes[p+'.mask_operands']['semantic_mode']=='operand_bundle','logical operands are not source tuples '+str(k))
            check(has(p+'.relu',p+'.positions','shape_dependency') and has(p+'.masked_fill',p+'.amax'),'positions depend on feature shape; masked values precede maximum '+str(k))
        check(profile['valid_windows']=='max(lengths-k+1,1)' and profile['mask_fill']=='torch.finfo(features.dtype).min','short reviews retain one window and fill with finite dtype minimum')
        check(has('textcnn.branches','textcnn.k3','fork') and nodes['textcnn.concat']['shape']=='[B,384]' and profile['forward_softmax'] is False,'same embedded input branches, explicit concat, logits-only return')
    elif key=='convae':
        check(sum(n['kind']=='conv2d' for n in nodes.values())==4,'four independently parameterized ordinary convolutions')
        check(all(nodes[f'convae.resize{i}']['mode']=='nearest' and not nodes[f'convae.resize{i}']['learnable'] for i in (1,2)),'two nearest interpolations with no learned weights')
        check(nodes['convae.conv3']['shape']=='[B,4,14,14]' and has('convae.conv4','convae.act4'),'actual conv3 channels and final LeakyReLU')
        check(has('convae.returns','convae.logits','fork') and has('convae.returns','convae.sigmoid','fork'),'activated logits and Sigmoid probabilities both returned')
        check(not any(n['kind'] in ('conv_transpose2d','max_unpool2d') for n in nodes.values()),'no invented learned upsampling or index unpool')
    elif key=='dcgan':
        check(profile['no_unified_forward'] and nodes['dcgan.root']['no_unified_forward'],'two explicit entries rather than invented DCGAN.forward')
        check(nodes['dcgan.discriminator']['global_receiver']=='model' and profile['source_discriminator_uses_self'] is False,'source global model discriminator receiver retained')
        check(profile['gradient_detach'] is False and has('dcgan.generator','dcgan.fake') and has('dcgan.fake','dcgan.discriminator'),'selected caller G-to-D scoring path has no detach')
        check(sum(n['kind']=='conv_transpose2d' for n in nodes.values())==5 and sum(n['kind']=='conv2d' for n in nodes.values())==5 and sum(n['kind']=='batch_norm2d' for n in nodes.values())==7,'five G and five D convolutions with seven BatchNorms')
        check([nodes[f'dcgan.d{i}.conv']['bias'] for i in range(1,6)]==[True,False,False,False,True],'discriminator first/last bias placement')
        check(nodes['dcgan.score']['shape']=='[B,1,1,1]' and not profile['real_image_call_in_main_graph'],'method score dimensions and separate real-image call')
    elif key in BATCHES.get('batch3',[])+BATCHES.get('batch4',[])+BATCHES.get('cell_examples',[]):
        checked=importlib.import_module('adapters.'+key).validate_ir(ir)
        require(isinstance(checked,list) and checked and all(isinstance(label,str) and label for label in checked),'empty/invalid reviewed semantic checks: '+key)
    else:raise ValueError('No reviewed semantic checks for model: '+key)
    return checked


def exported_view(svg_path, layout, evidence, ir, png=False):
    require(svg_path.is_file() and svg_path.stat().st_size > 0, "missing/empty SVG: " + str(svg_path))
    svg = ET.parse(svg_path).getroot()
    canvas = [numeric(svg.get(k, "nan")) for k in ("width", "height")]
    require(close(canvas, layout.get("canvas", [])), "SVG canvas differs from layout")
    require(close([float(x) for x in svg.get("viewBox", "").split()], [0, 0, *canvas]), "SVG viewBox differs from canvas")
    binding_element=next((e for e in svg if e.tag.rsplit('}',1)[-1]=='metadata' and e.get('id')=='source-binding'),None)
    require(binding_element is not None,'SVG source-binding metadata missing')
    binding=json.loads(binding_element.text)
    require(binding.get('model')==ir['model'] and binding.get('source_snapshot_sha256')==evidence['source_snapshot_sha256'] and binding.get('commit')==evidence['commit'], 'SVG source snapshot/model binding differs')
    require(binding.get('semantic_ir_sha256')==sha(json.dumps(ir,sort_keys=True).encode()),'SVG IR digest differs')
    require(binding.get('source_projects')==evidence.get('source_projects'),'SVG joint source binding differs')
    style_element=next((e for e in svg if e.tag.rsplit('}',1)[-1]=='metadata' and e.get('id')=='diagram-style'),None)
    require(style_element is not None and json.loads(style_element.text)==layout['visual_style'],'SVG style metadata differs from layout')
    actual_boxes, actual_routes, markers = {}, {}, {}
    def visit(element, in_defs=False):
        tag = element.tag.rsplit("}", 1)[-1]
        in_defs = in_defs or tag == "defs"
        if tag == "marker":
            require(element.get("markerUnits") == "userSpaceOnUse", "marker size depends on stroke width")
            require(element.get("id") not in markers, "duplicate SVG marker ID")
            size = [numeric(element.get(k, "nan")) for k in ("markerWidth", "markerHeight")]
            require(all(math.isfinite(v) and v > 0 for v in size), "invalid fixed marker dimensions")
            markers[element.get("id")] = size
        identity = element.get("data-node-id")
        if identity:
            require(identity not in actual_boxes, "duplicate SVG node ID: " + identity)
            rects = [c for c in element if c.tag.rsplit("}", 1)[-1] == "rect"]
            require(len(rects) == 1, "node does not contain exactly one rectangle: " + identity)
            rect = rects[0]
            title = " ".join(c.text or "" for c in element if c.tag.rsplit("}", 1)[-1] == "title")
            actual_boxes[identity] = dict(bbox=[numeric(rect.get(k, "nan")) for k in ("x", "y", "width", "height")], radius=numeric(rect.get("rx", 0)), title=title,
                                          fill=rect.get('fill'),stroke=rect.get('stroke'),stroke_width=numeric(rect.get('stroke-width',0)),
                                          role=element.get('data-visual-role'))
        if tag == "path" and not in_defs:
            identity = element.get("data-route-id")
            require(identity and identity not in actual_routes, "missing/duplicate actual SVG route ID")
            marker = element.get("marker-end")
            actual_routes[identity] = dict(points=path_points(element.get("d", "")), arrow=bool(marker), marker=marker)
        for child in element:
            visit(child, in_defs)
    visit(svg)
    require(markers, "SVG has no fixed-size arrow marker")
    boxes = {b["id"]: b for b in layout.get("boxes", [])}
    routes = {r["id"]: r for r in layout.get("routes", [])}
    require(boxes and len(boxes) == len(layout["boxes"]), "empty/duplicate layout boxes")
    require(routes and len(routes) == len(layout["routes"]), "empty/duplicate layout routes")
    require(set(actual_boxes) == set(boxes), "actual SVG rectangles and layout boxes differ")
    require(set(actual_routes) == set(routes), "actual SVG paths and layout routes differ")
    ir_nodes = {n["id"]: n for n in ir["nodes"]}
    scene = copy.deepcopy(layout)
    for box in scene["boxes"]:
        identity = box["id"]
        require(identity in ir_nodes, "SVG node missing from IR: " + identity)
        actual = actual_boxes[identity]
        require(close(box["bbox"], actual["bbox"]) and close(box.get("radius", 0), actual["radius"]), "SVG rectangle geometry differs: " + identity)
        require(box.get("source") == ir_nodes[identity].get("source"), "visible source binding differs from IR: " + identity)
        style=box['style']
        require(actual['fill']==style['fill'] and actual['stroke']==style['stroke'] and close(actual['stroke_width'],style['stroke_width']) and actual['role']==style['role'],'actual SVG visual role/color/border differs: '+identity)
        for reference in box.get("source", []):
            span = evidence["symbols"][reference]
            require(f'{span["path"]}:{span["start"]} {span["symbol"]}' in actual["title"], "SVG source title missing: " + identity)
        box["bbox"], box["radius"] = actual["bbox"], actual["radius"]
        x, y, w, h = actual["bbox"]
        ports = dict(in_=[x + w/2, y + h], out=[x + w/2, y], left=[x, y + h/2], right=[x + w, y + h/2])
        ports["in"] = ports.pop("in_")
        for name, point in ports.items():
            require(close(layout.get("ports", {}).get(identity, {}).get(name, []), point), "port does not match actual rectangle: " + identity + ":" + name)
        for name,point in layout.get('ports',{}).get(identity,{}).items():
            if '.aux' not in name:continue
            side=name.split('.',1)[0]
            require(re.fullmatch(r'(left|right|in|out)\.aux[0-9]+',name) and len(point)==2,
                    'invalid auxiliary side port: '+identity+':'+name)
            if side in ('left','right'):
                safe=close(point[0],x if side=='left' else x+w) and y+16<=point[1]<=y+h-16
            else:
                safe=close(point[1],y+h if side=='in' else y) and x+16<=point[0]<=x+w-16
            require(safe,'auxiliary port is not safely on the actual rectangle: '+identity+':'+name)
        scene["ports"][identity].update(ports)
    for route in scene["routes"]:
        actual = actual_routes[route["id"]]
        require(close(route["points"], actual["points"]) and bool(route.get("arrow")) == actual["arrow"], "SVG route geometry/arrow differs: " + route["id"])
        if actual["arrow"]:
            match = re.fullmatch(r"url\(#([^)]*)\)", actual["marker"])
            require(match and match[1] in markers, "route references missing arrow marker")
        route["points"], route["arrow"] = actual["points"], actual["arrow"]
        if route.get("semantic_src"):
            require(any(all(edge.get(k) == route.get("semantic_" + k) for k in ("src", "dst", "src_port", "dst_port")) and edge.get("role") == route.get("role") for edge in ir["edges"]), "rendered side route has no matching semantic edge")
        if route.get('operand_binding'):
            b=route['operand_binding'];scope=ir_nodes[b['scope']]
            require(scope['semantic_mode']=='operand_bundle' and scope['child_inputs'][b['child']]=={k:v for k,v in b.items() if k not in ('scope','child')},'rendered operand projection differs from typed IR')
            role='shape_dependency' if b['role']=='shape' else 'value_operand'
            require(any(e['src']==b['producer'] and e['src_port']==b.get('src_port','out') and e['dst']==b['child'] and e['role']==role for e in ir['edges']),'operand projection has no real producer in semantic IR')
    geometry = validate(scene)
    require(geometry.get("passed"), "geometry: " + "; ".join(geometry.get("errors", [])[:12]))
    if png:
        png_path = svg_path.with_suffix(".png")
        require(png_path.is_file(), "missing PNG: " + str(png_path))
        header = png_path.read_bytes()[:24]
        require(len(header) == 24 and header[:8] == b"\x89PNG\r\n\x1a\n" and header[12:16] == b"IHDR", "invalid PNG header")
        require(close(list(struct.unpack(">II", header[16:24])), canvas), "PNG dimensions differ from SVG")
    return dict(rectangles=len(boxes), actual_paths=len(routes), marker_sizes=markers,
                export_consistency="independent SVG/XML + source/IR comparison",
                geometry=dict(reused_validator="layout.validate", input="actual SVG rectangles and polylines", checks=geometry.get("checks", [])))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("generated", type=Path, help="generated root containing the selected model folders")
    parser.add_argument("--png", action="store_true", help="also require matching PNG dimensions")
    parser.add_argument('--batch',choices=['all']+list(BATCHES),default='all')
    parser.add_argument('--model',choices=['all']+MODELS,default='all')
    args = parser.parse_args()
    root = args.generated.resolve()
    require(root.is_dir(), "generated root does not exist: " + str(root))
    try:keys=selected(args.batch,args.model)
    except ValueError as exc:parser.error(str(exc))
    report = dict(passed=True, models={}, views_checked=0, expected_views=len(keys)*len(VIEWS), png_checked=args.png,
                  limitations=["Static reviewed model facts, not execution or numeric equivalence.",
                               "Export consistency checks are independent; geometry rules reuse layout.validate.",
                               "Text metrics and appearance still require visual inspection."])
    marker_sizes = []
    for key in keys:
        result = dict(passed=True, views={})
        report["models"][key] = result
        folder = root / key
        try:
            evidence, ir = read_json(folder / "source_evidence.json"), read_json(folder / "semantic_ir.json")
            require(ir.get("model") == key, "IR model identity mismatch")
            result["sources"] = source_checks(folder, evidence, ir)
            result["model_facts"] = model_facts(key, ir)
            digest = sha(json.dumps(ir, sort_keys=True).encode())
            result["semantic_ir_sha256"] = digest
            expected = {f"figure{i}_{view}.svg" for i, view in enumerate(VIEWS, 1)}
            require({p.name for p in folder.glob("figure*.svg")} == expected, "expected exactly three model SVG views")
            saved_checks = read_json(folder / "layout_checks.json")
            require(isinstance(saved_checks, list) and len(saved_checks) == len(VIEWS), "expected three layout check records")
            for view in VIEWS:
                check = next((c for c in saved_checks if c.get("view") == view), None)
                require(check and check.get("semantic_ir_sha256") == digest, "saved check IR digest differs: " + view)
            for i, view in enumerate(VIEWS, 1):
                try:
                    layout = read_json(folder / f"layout_{view}.json")
                    require(layout.get("semantic_ir_sha256") == digest, "view IR digest differs")
                    details = exported_view(folder / f"figure{i}_{view}.svg", layout, evidence, ir, args.png)
                    result["views"][view] = dict(passed=True, **details)
                    marker_sizes.extend(details["marker_sizes"].values())
                    report["views_checked"] += 1
                except (ValueError, KeyError, TypeError, OSError, ET.ParseError, struct.error) as exc:
                    result["passed"] = False
                    result["views"][view] = dict(passed=False, error=str(exc))
        except (ValueError, KeyError, TypeError, OSError, SyntaxError, zipfile.BadZipFile) as exc:
            result["passed"] = False
            result["error"] = str(exc)
        report["passed"] = report["passed"] and result["passed"]
        print(key + ": " + ("PASS" if result["passed"] else "FAIL") + (" — " + result["error"] if result.get("error") else ""))
        for view, value in result["views"].items():
            if not value["passed"]:
                print("  " + view + ": " + value["error"])
    if report["views_checked"] != report["expected_views"]:
        report["passed"] = False
        report["view_count_error"] = f"Not all {report['expected_views']} selected views passed inspection."
    if marker_sizes and any(not close(size, marker_sizes[0]) for size in marker_sizes):
        report["passed"] = False
        report["marker_error"] = "Arrow marker sizes differ across views."
    suffix='' if args.batch=='all' and args.model=='all' else '_'+(args.model if args.model!='all' else args.batch)
    destination = root / ('export_checks'+suffix+'.json')
    destination.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(str(destination))
    raise SystemExit(0 if report["passed"] else 1)


if __name__=="__main__":main()
