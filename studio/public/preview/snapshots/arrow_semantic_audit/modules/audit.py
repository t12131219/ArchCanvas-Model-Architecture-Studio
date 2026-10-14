#!/usr/bin/env python3
"""Read-only, independent source/IR/layout/SVG endpoint audit of all module views.

No drawing-engine helper is imported, and no upstream model is imported/run.
The source of truth is pinned evidence + typed IR boundary contracts; ranks and
physical port names never determine a computation's producer or consumer.
"""
from __future__ import annotations
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
GUIDE = HERE.parents[1] / 'module_programmatic_guide'
VIEWS = ['overview', 'modules', 'detailed']


def sha(data):
    return hashlib.sha256(data).hexdigest()


def endpoint(value):
    return tuple(value.rsplit(':', 1)) if value else None


def same(a, b):
    return len(a) == len(b) and all(abs(x-y) < 1e-5 for x, y in zip(a, b))


def edge_key(e):
    return e['src'], e['src_port'], e['dst'], e['dst_port'], e['role']


def interface_targets(nodes, edges, identity, port, direction):
    raw=nodes[identity].get('port_bindings',{}).get(port)
    if raw is not None:
        values=raw if isinstance(raw,list) else [raw]
        if all(v.get('direction',direction)==direction for v in values):
            return [(v['node'],v['port']) for v in values]
    if direction=='src':
        aliases=[(e['src'],e['src_port']) for e in edges if e['dst']==identity and e['dst_port']==port
                 and (e['role'] in ('tuple_collection','operand_collection') or e['role']=='boundary' and port=='out')]
        if port=='out' and nodes[identity].get('mode')=='parallel':
            aliases=[(e['src'],e['src_port']) for e in edges if e['dst']==identity and
                     e['role'] in ('tuple_collection','operand_collection')]
        if port=='shape' and not aliases:
            aliases=[(n,'shape') for n,p in interface_targets(nodes,edges,identity,'out',direction)]
        return aliases
    return [(e['dst'],e['dst_port']) for e in edges if e['src']==identity and e['src_port']==port and e['role']=='boundary' and port=='in']


def full_targets(nodes,edges,identity,port,direction,seen=()):
    pair=(identity,port)
    if pair in seen:return []
    targets=interface_targets(nodes,edges,identity,port,direction)
    if not targets:return [pair]
    return [leaf for n,p in targets for leaf in full_targets(nodes,edges,n,p,direction,seen+(pair,))]


def resolve(nodes, edges, boxes, identity, port, direction, seen=()):
    """Resolve exact semantic boundary aliases until a visible computation.

    A folded scope is a legal opaque summary. An expanded scope is transparent
    only through a declared alias / boundary; a graph rank is not a boundary.
    Retained source :in traces the incoming producer, never the transformed out.
    """
    marker=(identity, port, direction)
    if marker in seen:
        return [], 'cyclic boundary contract'
    seen=seen+(marker,)
    node=nodes[identity]
    if direction=='src' and port=='in':
        upstream=[e for e in edges if e['dst']==identity and e['dst_port']=='in'
                  and e['role'] not in ('tuple_collection','operand_collection')]
        if len(upstream)==1:
            e=upstream[0]
            return resolve(nodes,edges,boxes,e['src'],e['src_port'],'src',seen)
    if identity not in boxes:
        parent=node.get('parent')
        while parent not in boxes and parent:
            parent=nodes[parent].get('parent')
        if not parent:return [], 'no visible source scope'
        pair=(identity,port)
        exported=[name for name in nodes[parent].get('port_bindings',{})
                  if pair in full_targets(nodes,edges,parent,name,direction)]
        preferred=[name for name in exported if name not in ('in','out')]
        if preferred:exported=preferred
        if len(exported)==1:field=exported[0]
        elif pair in full_targets(nodes,edges,parent,'out' if direction=='src' else 'in',direction):
            boundary=full_targets(nodes,edges,parent,'out' if direction=='src' else 'in',direction)
            field=('out' if direction=='src' else 'in') if len(boundary)==1 else identity+':'+port
        else:field=identity+':'+port
        return [(parent,field)], 'folded endpoint projection'
    if not boxes[identity]['expanded']:
        raw=node.get('port_bindings',{}).get(port)
        declared=raw if isinstance(raw,list) else [raw] if raw else []
        if direction=='src' and declared and all(b.get('direction')=='src' for b in declared):
            values=[]
            for binding in declared:
                targets,reason=resolve(nodes,edges,boxes,binding['node'],binding['port'],'src',seen)
                values.extend(targets)
            return values,'explicit returned/retained leaf field alias'
        return [(identity,port)], 'visible opaque/leaf endpoint'
    aliases=node.get('port_bindings', {})
    if port in aliases:
        bindings=aliases[port]
        if isinstance(bindings,dict): bindings=[bindings]
        values=[]
        for binding in bindings:
            targets,reason=resolve(nodes,edges,boxes,binding['node'],binding['port'],direction,seen)
            if not targets:return [],reason
            values.extend(targets)
        return values,'explicit source interface'
    targets=interface_targets(nodes,edges,identity,port,direction)
    if targets:
        values=[]
        for n,p in targets:
            resolved,reason=resolve(nodes,edges,boxes,n,p,direction,seen)
            if not resolved:return [],reason
            values.extend(resolved)
        return values,'typed IR interface'
    if node.get('mode')=='parallel':
        return [(identity,port)], 'declared fork/collection scope'
    return [], 'expanded scope has no declared interface for '+port


def continuation(layout, point, scope, direction):
    """An alias attached to a scope border must have a real visible continuation.

    Only declared boundary/collection routes qualify. A neighboring endpoint
    or an unrelated crossing is not proof of a connected computation path.
    """
    matches=[]
    for r in layout['routes']:
        if r['role'] not in ('boundary','shape_dependency','tuple_collection','operand_collection'):
            continue
        if direction=='src' and r.get('dst') and endpoint(r['dst'])[0]==scope and same(r['points'][-1],point):
            matches.append(r['id'])
        if direction=='dst' and r.get('src') and endpoint(r['src'])[0]==scope and same(r['points'][0],point):
            matches.append(r['id'])
    return matches


def audit_folder(folder):
    ir=json.loads((folder/'semantic_ir.json').read_text())
    evidence=json.loads((folder/'source_evidence.json').read_text())
    nodes={n['id']:n for n in ir['nodes']}
    ir_edges={edge_key(e):e for e in ir['edges']}
    source_errors=[]
    for name,record in evidence['files'].items():
        path=folder/'sources'/name
        if not path.is_file() or sha(path.read_bytes())!=record['sha256']:
            source_errors.append(name)
    for n in nodes.values():
        expected=[evidence['symbols'][name]['evidence_id'] for name in n['source']]
        if n['source_evidence']!=expected:source_errors.append(n['id']+' evidence references')
    results=[]
    for number,view in enumerate(VIEWS,1):
        path=folder/f'figure{number}_{view}.svg'
        layout=json.loads((folder/f'layout_{view}.json').read_text())
        boxes={b['id']:b for b in layout['boxes']}
        svg=ET.fromstring(path.read_text())
        svg_nodes={g.get('data-node-id'):g for g in svg.iter() if g.get('data-node-id')}
        svg_routes={p.get('data-route-id'):p for p in svg.iter() if p.get('data-route-id')}
        problems=[];traces=[]
        def issue(kind,detail,route=None):
            problems.append({'kind':kind,'detail':detail,**({'route':route} if route else {})})
        logical_hash=sha(json.dumps(ir,sort_keys=True).encode())
        if layout.get('semantic_ir_sha256')!=logical_hash:
            issue('layout IR binding mismatch','Layout does not bind to the actual typed IR')
        binding=next((e for e in svg.iter() if e.get('id')=='source-binding'),None)
        svg_binding=json.loads(binding.text) if binding is not None else {}
        if svg_binding.get('semantic_ir_sha256')!=logical_hash or svg_binding.get('source_snapshot_sha256')!=evidence['source_snapshot_sha256'] or svg_binding.get('view')!=number-1:
            issue('SVG source/IR binding mismatch','Actual SVG metadata does not bind to source, IR and view')
        if set(svg_nodes)!=set(boxes):issue('SVG node coverage','Actual SVG identities differ from layout rectangles')
        for identity,box in boxes.items():
            rect=next((e for e in svg_nodes.get(identity,[]) if e.tag.endswith('rect')),None)
            if rect is None or not same([float(rect.get(k)) for k in ('x','y','width','height')],box['bbox']):
                issue('SVG rectangle mismatch',identity)
        if set(svg_routes)!={r['id'] for r in layout['routes']}:
            issue('SVG route coverage','Actual SVG paths differ from layout routes')
        for route in layout['routes']:
            rid=route['id'];actual=svg_routes.get(rid)
            coords=[float(v) for v in re.findall(r'-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?',actual.get('d',''))] if actual is not None else []
            points=[coords[i:i+2] for i in range(0,len(coords),2)]
            if len(points)!=len(route['points']) or any(not same(a,b) for a,b in zip(points,route['points'])):
                issue('SVG path mismatch','Actual path coordinates differ from recorded polyline',rid)
            if actual is not None and bool(actual.get('marker-end'))!=route['arrow']:
                issue('SVG arrow mismatch','Actual marker differs from route direction',rid)
            for direction,pos in [('src',0),('dst',-1)]:
                if not route.get(direction):continue
                identity,physical_port=endpoint(route[direction])
                point=layout['ports'].get(identity,{}).get(physical_port)
                if point is None or not same(point,route['points'][pos]):
                    issue('actual endpoint mismatch',direction+' '+route[direction],rid)
                x,y,w,h=boxes[identity]['bbox'];px,py=route['points'][pos]
                if not ((abs(px-x)<1e-5 or abs(px-x-w)<1e-5) and y-1e-5<=py<=y+h+1e-5 or
                        (abs(py-y)<1e-5 or abs(py-y-h)<1e-5) and x-1e-5<=px<=x+w+1e-5):
                    issue('endpoint not on actual SVG glyph',direction+' '+route[direction],rid)
            if not route.get('semantic_src'):
                # Automatic serial/parallel paths are checked against their
                # exact physical identities and the IR's typed boundary roles.
                if route.get('src') and route.get('dst'):
                    src,sp=endpoint(route['src']);dst,dp=endpoint(route['dst'])
                    sp=sp.split('.')[0];dp=dp.split('.')[0]
                    candidates=[e for e in ir['edges'] if e['src']==src and e['dst']==dst and e['role']==route['role']]
                    if not candidates and route['role'] not in ('residual','retained_input'):
                        issue('implicit route lacks IR dependency',src+' -> '+dst+' '+route['role'],rid)
                    if candidates and not any(e['src_port']==sp and (e['dst_port']==dp or e['dst_port']=='side' and dp in ('left','right')) for e in candidates):
                        issue('implicit route uses wrong typed boundary port',src+':'+sp+' -> '+dst+':'+dp,rid)
                continue
            semantic=(route['semantic_src'],route['semantic_src_port'],route['semantic_dst'],route['semantic_dst_port'],route['role'])
            if semantic not in ir_edges:issue('route missing typed IR edge',str(semantic),rid)
            contract=route.get('endpoint_binding')
            if contract:
                svg_contract=json.loads(actual.get('data-endpoint-binding','{}')) if actual is not None else {}
                if svg_contract!=contract:
                    issue('SVG endpoint binding mismatch','Actual path binding differs from the layout receipt',rid)
                canonical=contract.get('canonical',{})
                if tuple(canonical.get(k) for k in ('src','src_port','dst','dst_port','role'))!=semantic or contract.get('edge_id')!=ir_edges.get(semantic,{}).get('id'):
                    issue('wrong canonical binding','Route receipt is not bound to this typed IR edge',rid)
                if contract.get('rendered_src')!=route['src'] or contract.get('rendered_dst')!=route['dst']:
                    issue('binding differs from actual endpoints','Physical endpoint identity differs from binding',rid)
            ends={}
            for direction,pos in [('src',0),('dst',-1)]:
                logical=route['semantic_'+direction];port=route['semantic_'+direction+'_port']
                if direction=='src' and port=='out' and route['semantic_dst_port']=='in' and nodes[route['semantic_dst']].get('input_selector'):
                    port=nodes[route['semantic_dst']]['input_selector']
                if direction=='src' and route['role']=='dispatch' and boxes.get(logical,{}).get('expanded'):
                    entering=[e for e in ir['edges'] if e['dst']==logical and e['dst_port']=='in' and e['role'] not in ('tuple_collection','operand_collection')]
                    if len(entering)==1:logical=entering[0]['src']
                expected,reason=resolve(nodes,ir['edges'],boxes,logical,port,direction)
                physical=endpoint(route[direction]);visible=physical[0]
                links=[]
                if boxes[visible]['expanded']:
                    links=continuation(layout,route['points'][pos],visible,direction)
                okay=bool(expected) and (visible in {t[0] for t in expected} or bool(links))
                if boxes[visible]['expanded'] and not links:
                    okay=False
                if not okay:
                    issue('wrong or unbound visible endpoint',f'{direction} {logical}:{port} -> {route[direction]}; expected {expected}; {reason}',rid)
                if contract:
                    reported=contract['source' if direction=='src' else 'destination']
                    if reported.get('projection')=='exposed-interface' and boxes[visible]['expanded']:
                        issue('expanded interface has no actual computation endpoint',direction+' '+route[direction],rid)
                    observed=(reported['node'],reported['port'])
                    admissible=expected
                    # A tuple/list edge feeds the consumer's separate operand
                    # slots; it does not become a sum or merge at a border.
                    if direction=='dst' and port=='in':
                        source_targets,_=resolve(nodes,ir['edges'],boxes,route['semantic_src'],route['semantic_src_port'],'src')
                        if len(source_targets)>1:
                            admissible=expected+[(n,f'operand[{i}]') for n,p in expected for i in range(len(source_targets))]
                    if observed not in admissible or reported['node']!=visible:
                        issue('wrong typed field at actual glyph',f'{direction} receipt {observed}, independently expected {admissible}, actual glyph {visible}',rid)
                    field=layout.get('port_fields',{}).get(visible,{}).get(physical[1],{}).get('field')
                    if field!=reported['port']:
                        issue('physical slot loses typed field',f'{direction} {route[direction]} stores {field}, receipt denotes {reported["port"]}',rid)
                refs=[{'symbol':s,'path':evidence['symbols'][s]['path'],'start':evidence['symbols'][s]['start'],'end':evidence['symbols'][s]['end']} for s in nodes[logical]['source']]
                ends[direction]={'IR':[logical,port],'expected_visible':expected,'actual_layout':route[direction],
                    'actual_SVG_coordinate':route['points'][pos],'boundary_continuation':links,'source':refs,'reason':reason,'passed':okay}
            traces.append({'route':rid,'role':route['role'],'endpoints':ends})
        if 'endpoint_projections' in layout:
            projections=layout['endpoint_projections']
            if {p['edge'] for p in projections}!={e['id'] for e in ir['edges']}:
                issue('IR disposition coverage','Some typed IR dependencies have no rendered/folded/alias disposition')
            rendered={r['id']:r for r in layout['routes']}
            for p in projections:
                if p['status'] in ('rendered','same-visible-dependency') and p.get('route') not in rendered:
                    issue('disposition references missing SVG path',p['edge'])
        results.append({'module':ir['model'],'view':view,'passed':not problems and not source_errors,
                        'node_count':len(boxes),'route_count':len(layout['routes']),'typed_route_count':len(traces),
                        'source_errors':source_errors,'problems':problems,'traces':traces,
                        'artifacts':{'SVG':str(path),'SVG_sha256':sha(path.read_bytes()),'IR_sha256':sha((folder/'semantic_ir.json').read_bytes()),
                                     'layout_sha256':sha((folder/f'layout_{view}.json').read_bytes())}})
    return results


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--generated',type=Path,default=GUIDE/'generated')
    parser.add_argument('--report',type=Path,default=HERE/'endpoint_audit.json')
    args=parser.parse_args()
    results=[row for folder in sorted(args.generated.iterdir()) if (folder/'semantic_ir.json').is_file()
             for row in audit_folder(folder)]
    issues=Counter(p['kind'] for row in results for p in row['problems'])
    report={'passed':all(r['passed'] for r in results),'module_count':len(results)//3,'view_count':len(results),
            'visible_nodes':sum(r['node_count'] for r in results),'routes':sum(r['route_count'] for r in results),
            'explicit_typed_routes':sum(r['typed_route_count'] for r in results),
            'issue_counts':dict(issues),'model_executed':False,
            'method':'Independent fixed source hash + AST span references + IR boundary alias traversal + actual SVG XML coordinates; no drawing-engine functions imported.',
            'limits':['Named leaf operand identities are checked through typed metadata/contracts; pixels alone do not encode a tensor name.',
                      'Anonymous fork/collection bus fragments are checked for SVG fidelity; selected tuple identities require source-declared scope semantics.'],
            'views':results}
    args.report.parent.mkdir(parents=True,exist_ok=True)
    args.report.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    lines=['# 模块箭头语义独立审计','',f'范围：{report["module_count"]} 个模块 × 3 视图，共 {len(results)} 个 SVG。',
           f'核对 {report["visible_nodes"]} 个实际图框、{report["routes"]} 条 SVG 路径、{report["explicit_typed_routes"]} 条显式类型依赖。',
           '',report['method'],'','## 当前结果','',f'通过：{report["passed"]}。错误分类：`{dict(issues)}`。',
           '', '## 待修复的实际端点','', '| 模块 | 视图 | 路径 | 实际端点与期望 |','|---|---|---|---|']
    for row in results:
        for problem in row['problems']:
            if problem['kind']=='wrong or unbound visible endpoint':
                lines.append(f'| {row["module"]} | {row["view"]} | {problem.get("route","")} | {problem["detail"]} |')
    lines+=['','JSON 保留每条显式箭头的源码符号/行号、IR 端口、期望可见节点、实际布局端口和 SVG 坐标。',
            '折叠容器可作为不透明摘要；展开容器必须有真实边界续线或显式接口绑定。布局 rank 不能充当数据依赖。',
            '本检查没有执行模型；叶子命名端口的值身份仍依赖可审查的源码适配合同，不能仅由 SVG 像素证明。','']
    args.report.with_suffix('.md').write_text('\n'.join(lines))
    print(json.dumps({k:v for k,v in report.items() if k!='views'},ensure_ascii=False,indent=2))


if __name__=='__main__':main()
