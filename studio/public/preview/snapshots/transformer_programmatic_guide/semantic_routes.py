"""Source interfaces choose terminals; the measured drawing supplies wire geometry.

No source model is imported. The original polylines form a routing scaffold only;
they are replaced by source-traced leaf-to-leaf wires before SVG serialization.
Crossings do not create graph junctions unless a wire vertex actually meets a
segment. Visible tensor grids are value aliases, never extra Python operators.
"""
from __future__ import annotations
from collections import defaultdict
import heapq
import html
import json
import math
import re
import xml.etree.ElementTree as ET


def source_contracts(nodes, edges):
    index = {node['id']: node for node in nodes}
    for node in nodes:
        bindings = {}
        for edge in edges:
            if edge['kind'] != 'interface_binding':
                continue
            if edge['src'] == node['id'] and index[edge['dst']]['parent'] == node['id']:
                bindings.setdefault(edge['src_port'], []).append(
                    dict(node=edge['dst'], port=edge['dst_port']))
            if edge['dst'] == node['id'] and index[edge['src']]['parent'] == node['id']:
                bindings.setdefault(edge['dst_port'], []).append(
                    dict(node=edge['src'], port=edge['src_port']))
        if bindings:
            node['port_bindings'] = {port: values[0] if len(values) == 1 else values
                                     for port, values in bindings.items()}
    for side in ('enc', 'dec'):
        last = side + ('.norm2' if side == 'enc' else '.norm3')
        index[side + '.output']['port_bindings'] = {
            'out': dict(node=last, port='out')}
    index['logits']['port_bindings'] = {'out': dict(node='generator', port='out')}
    for identity in ('enc.self','dec.self','dec.cross'):
        cross=identity=='dec.cross'
        projection=dict(id=identity+'.projection_summary',kind='source_summary',parent=identity,
                        children=[],ports=['in','memory','q_out','k_out','v_out'],
                        source_evidence=['MultiHeadAttention.forward','MultiHeadAttention._split_heads'],
                        param_identity=None,summary_members=[identity+'.'+role for role in 'qkv']+[identity+'.split'],
                        member_ports={
                            **{ref(identity+'.'+role,'in'):('memory' if cross and role!='q' else 'in') for role in 'qkv'},
                            **{ref(identity+'.'+role,'out'):role+'_out' for role in 'qkv'},
                            **{ref(identity+'.split',role+'_in'):role+'_out' for role in 'qkv'},
                            **{ref(identity+'.split',role+'_out'):role+'_out' for role in 'qkv'}})
        output=dict(id=identity+'.output_summary',kind='source_summary',parent=identity,
                    children=[],ports=['in','out'],source_evidence=['MultiHeadAttention.forward','MultiHeadAttention._combine_heads'],
                    param_identity=None,summary_members=[identity+'.merge',identity+'.wo'],
                    member_ports={ref(identity+'.merge','in'):'in',ref(identity+'.merge','out'):'out',
                                  ref(identity+'.wo','in'):'out',ref(identity+'.wo','out'):'out'})
        nodes.extend((projection,output));index[identity]['children'].extend((projection['id'],output['id']))


def ref(identity, port):
    return identity + ':' + port


def canonical_terminals(ir, boxes, with_resolver=False):
    """Project source edges by declared interfaces, folding only named transparent ops."""
    nodes = {node['id']: node for node in ir['nodes']}
    incoming, outgoing = defaultdict(list), defaultdict(list)
    for edge in ir['edges']:
        incoming[edge['dst'], edge['dst_port']].append(edge)
        outgoing[edge['src'], edge['src_port']].append(edge)
    expanded = {node for node in nodes if any(
        child in boxes for child in nodes[node].get('children', []))}
    transparent = {'dropout', 'attn_dropout', 'nan_guard', 'stack_output', 'output'}
    summary_ports={member:(node['id'],port) for node in nodes.values() if node['id'] in boxes
                   for member,port in node.get('member_ports',{}).items()}

    def resolve(identity, port, side, trail=()):
        key = identity, port, side
        if key in trail:
            raise ValueError('cyclic source interface ' + repr(key))
        node = nodes[identity]
        if ref(identity,port) in summary_ports:
            target,terminal=summary_ports[ref(identity,port)]
            return [(target,terminal,[])]
        # A real visible leaf is authoritative. Output aliases for logits and
        # serial-stack results are source interfaces rather than a new operator.
        if identity in boxes and identity not in expanded:
            return [(identity, port, [])]
        parent=node.get('parent')
        while parent:
            if parent in boxes and parent not in expanded:
                return [(parent,'out' if side=='src' else 'in',[])]
            parent=nodes[parent].get('parent')
        through = (incoming.get((identity,port),[]) if side=='src'
                   else outgoing.get((identity,port),[]))
        through = [edge for edge in through if edge['kind']!='interface_binding']
        if through and ((side=='src' and port!='out' and not port.endswith('_out'))
                        or (side=='dst' and (port=='out' or port.endswith('_out')))):
            result=[]
            for edge in through:
                nid=edge['src' if side=='src' else 'dst'];p=edge['src_port' if side=='src' else 'dst_port']
                for target,terminal,trace in resolve(nid,p,side,trail+(key,)):
                    result.append((target,terminal,[edge['id']]+trace))
            return result
        bindings = node.get('port_bindings', {}).get(port)
        if bindings:
            bindings = bindings if isinstance(bindings, list) else [bindings]
            result = []
            for binding in bindings:
                for nid, terminal, trace in resolve(binding['node'], binding['port'], side, trail + (key,)):
                    bridge = [edge['id'] for edge in ir['edges']
                              if edge['kind'] == 'interface_binding'
                              and ((edge['src'], edge['src_port'], edge['dst'], edge['dst_port'])
                                   in ((identity, port, binding['node'], binding['port']),
                                       (binding['node'], binding['port'], identity, port)))]
                    result.append((nid, terminal, bridge + trace))
            return result
        if node['kind'] in transparent:
            candidates = (incoming.get((identity, 'in'), []) if side == 'src'
                          else outgoing.get((identity, 'out'), []))
            result = []
            for edge in candidates:
                nid = edge['src' if side == 'src' else 'dst']
                p = edge['src_port' if side == 'src' else 'dst_port']
                for target, terminal, trace in resolve(nid, p, side, trail + (key,)):
                    result.append((target, terminal, [edge['id']] + trace))
            if result:
                return result
        raise ValueError('unresolved source interface ' + repr(key))

    projected = {}
    for edge in ir['edges']:
        if edge['kind'] == 'interface_binding':
            continue
        for a, ap, atrace in resolve(edge['src'], edge['src_port'], 'src'):
            for b, bp, btrace in resolve(edge['dst'], edge['dst_port'], 'dst'):
                if a == b:
                    continue
                key = a, ap, b, bp
                if key not in projected:
                    projected[key] = dict(src=ref(a, ap), dst=ref(b, bp),
                                          semantic_edges=[], kind=edge['kind'])
                if edge['kind'] in ('memory','residual','explanatory'):
                    projected[key]['kind']=edge['kind']
                projected[key]['semantic_edges'] = sorted(set(
                    projected[key]['semantic_edges'] + [edge['id']] + atrace + btrace))
    result=list(projected.values())
    return (result,resolve) if with_resolver else result


def bind_scene(scene):
    """Replace scaffolding with canonical edges; route over the existing clear corridors."""
    # IDs for module-view summaries represent explicit source interface scopes.
    # Detailed operators retain their real semantic IDs. Summaries need actual
    # ports and source members rather than anonymous descriptive rectangles.
    boxes = {box['id']: box for box in scene.boxes}
    source_edges,resolve = canonical_terminals(scene.ir, boxes,True)
    raw = scene.routes
    scene.routing_scaffold_count = len(raw)
    points = set(tuple(p) for route in raw for p in route['points'])
    for ports in scene.ports.values():
        points.update(tuple(point) for point in ports.values())
    links = []
    for route in raw:
        for a, b in zip(route['points'], route['points'][1:]):
            links.append((tuple(a), tuple(b), None))
    for value in scene.tensor_views:
        x, y, w, h = value['bbox']
        if value['flow'] == 'up':
            a, b = (x + w/2, y+h), (x + w/2, y)
        elif value['flow'] == 'down':
            a, b = (x+w/2, y), (x+w/2, y+h)
        else:
            a, b = (x, y+h/2), (x+w, y+h/2)
        # Q/K/V linear-output arrows in compact use y+17, while tensor rows
        # occupy y+15. Their registered input is the actual wire endpoint.
        if value.get('input'): a = tuple(value['input'])
        if value.get('output'): b = tuple(value['output'])
        value['in'], value['out'] = a, b
        points.update((a,b));links.append((a,b,value['id']))
        scene.ports[value['id']] = {'in':a, 'out':b}
        owner=value['owner'].split(':')[0]
        scope=owner
        nodes={n['id']:n for n in scene.ir['nodes']}
        while scope:
            box=boxes.get(scope)
            if box and any(b.get('parent')==scope for b in boxes.values()):
                bx,by,bw,bh=box['bbox']
                if bx<=x and by<=y and x+w<=bx+bw and y+h<=by+bh:break
            scope=nodes.get(scope,{}).get('parent')
        scene.boxes.append(dict(id=value['id'], parent=scope, bbox=value['bbox'],
                                glyph='tensor_value_alias', canonical=value['owner']))
    adjacency = defaultdict(list)
    for a,b,alias in links:
        if alias:
            adjacency[a].append((b,math.dist(a,b),alias));adjacency[b].append((a,math.dist(a,b),alias))
            continue
        # Split at existing vertices/ports on this polyline, never at an
        # unregistered crossing between two independent wires.
        candidates = [p for p in points if on_segment(p,a,b)]
        candidates.sort(key=lambda p: math.dist(a,p))
        for p,q in zip(candidates,candidates[1:]):
            length = math.dist(p,q)
            if length:
                adjacency[p].append((q,length,alias));adjacency[q].append((p,length,alias))

    def path(start, end):
        start, end = tuple(start), tuple(end)
        heap=[(0,start)];distance={start:0};prev={}
        while heap:
            score,current=heapq.heappop(heap)
            if score != distance[current]:continue
            if current == end:break
            for target,length,alias in adjacency[current]:
                candidate=score+length
                if candidate < distance.get(target,float('inf')):
                    distance[target]=candidate;prev[target]=(current,alias)
                    heapq.heappush(heap,(candidate,target))
        if end not in distance:raise ValueError('no scaffold path '+repr((start,end)))
        vertices=[end];aliases=[];current=end
        while current != start:
            previous,alias=prev[current];aliases.append(alias);vertices.append(previous);current=previous
        return list(reversed(vertices)),list(reversed(aliases))

    # Remove old path items only. Glyphs, labels, established coordinates and
    # original filled marker definitions remain unchanged.
    scene.svg = [item for item in scene.svg if not item.startswith('<path data-route-id=')]
    scene.routes=[]
    for edge in source_edges:
        a,ap=edge['src'].split(':');b,bp=edge['dst'].split(':')
        start=scene.ports.get(a,{}).get(ap);end=scene.ports.get(b,{}).get(bp)
        if start is None or end is None:
            raise ValueError('missing canonical physical port '+str((edge,start,end)))
        try:vertices,aliases=path(start,end)
        except ValueError as exc:raise ValueError(str(exc)+" for "+repr(edge)) from exc
        # Cut transparent tensor-grid crossings into actual endpoint segments.
        # Both resulting segments still carry the same reviewed source edge.
        cuts=[]
        for i,alias in enumerate(aliases):
            if alias and (not cuts or cuts[-1][2] != alias):cuts.append((i,i+1,alias))
            elif alias:cuts[-1]=(cuts[-1][0],i+1,alias)
        cursor=0;physical_src=edge['src']
        for first,last,alias in cuts:
            if first>cursor:
                emit(scene,vertices[cursor:first+1],physical_src,alias+':in',edge)
            cursor=last;physical_src=alias+':out'
        if cursor<len(vertices)-1:
            emit(scene,vertices[cursor:],physical_src,edge['dst'],edge)
    disposition=[]
    for source_edge in scene.ir['edges']:
        projected=[dict(src=e['src'],dst=e['dst']) for e in source_edges if source_edge['id'] in e['semantic_edges']]
        if source_edge['kind']=='interface_binding':
            status='declared_source_interface_alias'
        elif projected:status='rendered_source_connection'
        else:
            starts=resolve(source_edge['src'],source_edge['src_port'],'src')
            ends=resolve(source_edge['dst'],source_edge['dst_port'],'dst')
            if not all(a==b for a,_,_ in starts for b,_,_ in ends):
                raise ValueError('source dependency silently omitted '+source_edge['id'])
            status='folded_inside_same_visible_source_scope'
        disposition.append(dict(edge=source_edge['id'],status=status,projected_connections=projected))
    scene.semantic_projection = dict(schema='transformer-source-terminals/1',
                                     edge_dispositions=disposition,
                                     scaffold_paths=len(raw), source_connections=len(source_edges),
                                     value_aliases=scene.tensor_views,
                                     mode='source IR selects glyph terminals; geometric network selects route',
                                     physical_routing=dict(schema='semantic-physical-ports/2',
                                         binding_authority='canonical source IR', geometry_authority='editable presentation',
                                         objective='short legal orthogonal routes with few bends',
                                         caption_policy='canonical source route selects caption identity; editable path anchors follow displayed geometry',
                                         border_policy='painted shaft and frame half-widths plus 2px air gap; corner gates and shared forks adapt within source scope',
                                         gate_policy='source-recorded straight ancestor exits follow their endpoint; gate side and hierarchy stay fixed',
                                         protected=['value-alias flow','branch stems','folded field slots','container side gates']))
    # Labels are presentation attachments, never extra model operators.
    # Their explicit owner resolves to a source node or the value alias's
    # canonical port; coordinate proximity does not establish ownership.
    aliases={v['id']:v for v in scene.tensor_views}
    for attachment in scene.attachments:
        owner=attachment['owner']
        source_owner=aliases[owner]['owner'] if owner in aliases else owner
        attachment['source_owner']=source_owner
        if attachment['kind']=='edge-label':
            candidates=[r for r in scene.routes if all(r.get(k)==v for k,v in attachment['edge_spec'].items())]
            if len(candidates)!=1:raise ValueError('Ambiguous source caption binding '+str(attachment))
            route=candidates[0]
            attachment.update(route=route['id'],canonical_src=route['canonical_src'],canonical_dst=route['canonical_dst'],semantic_edges=route['semantic_edges'])
            needle='data-follow-id="'+attachment['id']+'"'
            scene.svg=[line.replace(needle,needle+' data-follow-edge="'+html.escape(route['id'],quote=True)+'"') if needle in line else line for line in scene.svg]
        needle='data-follow-id="'+attachment['id']+'"' 
        scene.svg=[line.replace(needle,needle+' data-follow-source="'+html.escape(source_owner,quote=True)+'"') if needle in line else line for line in scene.svg]
    # A dot annotates a source tensor fork. It has route ownership rather
    # than belonging to the glyph emitted immediately before it in SVG.
    markers=[]
    for i,line in enumerate(scene.svg):
        if not line.startswith('<circle '):continue
        circle=ET.fromstring(line)
        if float(circle.get('r','99'))>6:continue
        p=(float(circle.get('cx')),float(circle.get('cy')))
        candidates=[r for r in scene.routes if any(on_segment(p,a,b) for a,b in zip(r['points'],r['points'][1:]))]
        sources={r['canonical_src'] for r in candidates}
        if len(sources)!=1:raise ValueError('junction dot has no unique source tensor '+str(p))
        rays=set()
        for r in candidates:
            for a,b in zip(r['points'],r['points'][1:]):
                if on_segment(p,a,b):
                    for q in (a,b):
                        if tuple(q)!=p:rays.add(('x' if q[0]!=p[0] else 'y',1 if sum(q)>sum(p) else -1))
        if len(candidates)<2 or len(rays)<3:raise ValueError('junction dot is not on a source fork '+str(p))
        identity='source-fork-'+str(len(markers)+1)
        marker=dict(id=identity,point=list(p),canonical_src=next(iter(sources)),routes=[r['id'] for r in candidates],
                    geometry='intersection of registered source routes',kind='tensor-fork')
        markers.append(marker)
        attrs={'data-junction-id':identity,'data-junction-source':marker['canonical_src'],'data-junction-routes':json.dumps(marker['routes'])}
        scene.svg[i]=line.replace('<circle','<circle'+''.join(' '+k+'="'+html.escape(v,quote=True)+'"' for k,v in attrs.items()),1)
    scene.semantic_projection['junction_markers']=markers


def on_segment(point,a,b):
    if a[0]==b[0]:return point[0]==a[0] and min(a[1],b[1])<=point[1]<=max(a[1],b[1])
    if a[1]==b[1]:return point[1]==a[1] and min(a[0],b[0])<=point[0]<=max(a[0],b[0])
    return False


def emit(scene,points,src,dst,edge):
    if len(points)<2:return
    identity = ('encoder-memory-to-cross' if edge['kind']=='memory'
                else 'binding-%03d'%(len(scene.routes)+1))
    if any(route['id']==identity for route in scene.routes):identity+='-%03d'%len(scene.routes)
    scene.line(points,src=src,dst=dst,dashed=edge['kind']=='explanatory',
               id=identity,width=2.8 if edge['kind']=='memory' else 2.2)
    scene.routes[-1].update(canonical_src=edge['src'],canonical_dst=edge['dst'],
                            semantic_edges=edge['semantic_edges'],semantic_kind=edge['kind'],
                            port_authority=dict(source=edge['src'],target=edge['dst'],geometry='presentation'))
    attributes={"data-src":src,"data-dst":dst,"data-canonical-src":edge['src'],
                "data-canonical-dst":edge['dst'],"data-semantic-edges":json.dumps(edge['semantic_edges'])}
    scene.svg[-1]=scene.svg[-1].replace(' d=', ''.join(' '+k+'="'+html.escape(v,quote=True)+'"' for k,v in attributes.items())+' d=',1)


def validate_semantics(layout,ir):
    """Validate complete projected-edge coverage and actual physical alias chains."""
    errors=[];nodes={n['id']:n for n in ir['nodes']};edges={e['id']:e for e in ir['edges']}
    aliases={v['id']:v for v in layout.get('semantic_projection',{}).get('value_aliases',[])}
    routing=layout.get('semantic_projection',{}).get('physical_routing',{})
    if routing.get('schema')!='semantic-physical-ports/2' or routing.get('binding_authority')!='canonical source IR' or routing.get('geometry_authority')!='editable presentation':
        errors.append('physical routing must preserve canonical source authority')
    if routing.get('caption_policy')!='canonical source route selects caption identity; editable path anchors follow displayed geometry':
        errors.append('caption routing must preserve source connection authority')
    if routing.get('border_policy')!='painted shaft and frame half-widths plus 2px air gap; corner gates and shared forks adapt within source scope':
        errors.append('painted frame clearance policy missing')
    for route in layout.get('routes',[]):
        if route.get('canonical_src') and route.get('port_authority')!=dict(source=route['canonical_src'],target=route['canonical_dst'],geometry='presentation'):
            errors.append('physical port authority differs from canonical field '+route['id'])
    routes={r['id']:r for r in layout.get('routes',[])}
    for marker in layout.get('semantic_projection',{}).get('junction_markers',[]):
        refs=[routes.get(identity) for identity in marker.get('routes',[])]
        if len(refs)<2 or any(r is None or r.get('canonical_src')!=marker.get('canonical_src') for r in refs):
            errors.append('junction source tensor or route ownership differs '+marker['id']);continue
        p=marker.get('point',[])
        if len(p)!=2 or not all(any(on_segment(p,a,b) for a,b in zip(r['points'],r['points'][1:])) for r in refs):
            errors.append('junction marker detached from source routes '+marker['id'])
    boxes={box['id']:box for box in layout['boxes']}
    attachments=layout.get('attachments',[])
    if len({a['id'] for a in attachments})!=len(attachments):errors.append('duplicate presentation attachment')
    for attachment in attachments:
        owner=attachment.get('owner');source_owner=aliases.get(owner,{}).get('owner',owner)
        if owner not in boxes:errors.append('presentation owner is not a visible glyph '+attachment['id'])
        if attachment.get('source_owner')!=source_owner:errors.append('presentation source ownership differs '+attachment['id'])
        if attachment.get('kind')=='edge-label':
            refs=[r for r in layout['routes'] if all(r.get(k)==v for k,v in attachment.get('edge_spec',{}).items())]
            if len(refs)!=1 or refs[0]['id']!=attachment.get('route') or any(attachment.get(k)!=refs[0].get(k) for k in ['canonical_src','canonical_dst','semantic_edges']):
                errors.append('source caption route identity differs '+attachment['id'])
        value=attachment.get('value_owner')
        if value:
            identity,_,port=value.partition(':')
            if identity not in nodes or port not in nodes[identity]['ports'] or identity!=owner:
                errors.append('value snapshot must follow its producing source operator '+attachment['id'])
    if nodes.get('dec.cross',{}).get('semantic_contract'):
        memory=aliases.get('enc.memory.value')
        if not memory or memory.get('owner')!='enc.output:out' or memory.get('flow')!='down':
            errors.append('Memory must visibly alias the final encoder output')
        for target in ['dec.cross.k:in','dec.cross.v:in'] if layout['view']=='detailed' else [None]:
            routes=[r for r in layout['routes'] if r.get('semantic_kind')=='memory' and (target is None or r.get('canonical_dst')==target)]
            if not any(r.get('dst')=='enc.memory.value:in' for r in routes) or not any(r.get('src')=='enc.memory.value:out' for r in routes):
                errors.append('memory connection bypasses its visible value alias '+str(target))
    for identity,box in boxes.items():
        # Containment comes from source hierarchy (or a value alias owner),
        # not from whichever rectangle happens to surround the glyph.
        owner=aliases.get(identity,{}).get('owner','').split(':')[0]
        parent=owner if owner else nodes.get(identity,{}).get('parent')
        while parent and (parent not in boxes or parent==identity or not any(b.get('parent')==parent for b in boxes.values())):
            parent=nodes.get(parent,{}).get('parent')
        if box.get('parent')!=parent:errors.append('visible source containment differs: '+identity)
    expected,resolve=canonical_terminals(ir,{k:v for k,v in boxes.items() if k not in aliases},True)
    expected={(e['src'],e['dst']):e for e in expected}
    dispositions=layout.get('semantic_projection',{}).get('edge_dispositions',[])
    if len(dispositions)!=len(edges) or {d['edge'] for d in dispositions}!=set(edges):
        errors.append('source-edge disposition coverage incomplete')
    for disposition in dispositions:
        eid=disposition['edge'];status=disposition['status']
        if eid not in edges:continue
        if status=='declared_source_interface_alias':
            if edges[eid]['kind']!='interface_binding':errors.append('real dependency mislabeled as interface '+eid)
        elif status=='rendered_source_connection':
            if not any(eid in e['semantic_edges'] for e in expected.values()):errors.append('unproven rendered disposition '+eid)
        elif status=='folded_inside_same_visible_source_scope':
            e=edges[eid]
            if not all(a==b for a,_,_ in resolve(e['src'],e['src_port'],'src') for b,_,_ in resolve(e['dst'],e['dst_port'],'dst')):
                errors.append('external dependency mislabeled as folded '+eid)
        else:errors.append('unknown source-edge disposition '+eid)
    groups=defaultdict(list)
    for route in layout['routes']:
        key=route.get('canonical_src'),route.get('canonical_dst')
        groups[key].append(route)
        canonical=expected.get(key)
        if canonical is None:
            errors.append('source projection does not permit endpoints: '+route['id'])
        elif set(route.get('semantic_edges',[]))!=set(canonical['semantic_edges']):
            errors.append('trace does not prove these endpoints: '+route['id'])
        if not route.get('semantic_edges'):
            errors.append('route lacks source trace: '+route['id'])
        if any(e not in edges for e in route.get('semantic_edges',[])):
            errors.append('unknown trace edge: '+route['id'])
        for side,point in (('src',route['points'][0]),('dst',route['points'][-1])):
            physical=route.get(side);canonical_ref=route.get('canonical_'+side)
            if not physical or not canonical_ref:
                errors.append('route lacks canonical endpoint: '+route['id']);continue
            identity,_,port=physical.partition(':')
            if identity not in boxes:errors.append('endpoint is not visible glyph: '+physical);continue
            registered=layout['ports'].get(identity,{}).get(port)
            if registered is None or math.dist(registered,point)>1e-6:
                errors.append('actual wire differs from source port: '+physical)
            x,y,w,h=boxes[identity]['bbox']
            if not ((abs(point[0]-x)<1e-6 or abs(point[0]-x-w)<1e-6) and y-1e-6<=point[1]<=y+h+1e-6
                    or (abs(point[1]-y)<1e-6 or abs(point[1]-y-h)<1e-6) and x-1e-6<=point[0]<=x+w+1e-6):
                errors.append('physical endpoint is not glyph perimeter: '+physical)
            if identity not in nodes and identity not in aliases:
                errors.append('endpoint lacks source identity: '+physical)
            name,_,terminal=canonical_ref.partition(':')
            if name not in nodes or terminal not in nodes[name]['ports']:
                errors.append('illegal canonical port: '+canonical_ref)
            if identity in aliases:
                owner=aliases[identity]['owner'];oname,_,op=owner.partition(':')
                try: origins={ref(n,p) for n,p,_ in resolve(oname,op,'src')}
                except (KeyError,ValueError):origins=set()
                if route.get('canonical_src') not in origins:
                    errors.append('value alias has wrong producer: '+physical)
            elif physical!=canonical_ref:
                errors.append('physical endpoint does not match canonical leaf: '+physical)
    for key,edge in expected.items():
        routes=groups.get(key,[])
        if not routes:
            errors.append('uncovered source connection: '+str(key));continue
        # Continue only via an alias of the same source value. Merely having an
        # unrelated valid edge ID, or a route to an outer frame, cannot pass.
        todo=[edge['src']];seen=set();used=set()
        while todo:
            endpoint=todo.pop()
            if endpoint in seen:continue
            seen.add(endpoint)
            for route in routes:
                if route['src']!=endpoint:continue
                used.add(route['id']);destination=route['dst'];seen.add(destination)
                aid,_,port=destination.partition(':')
                if aid in aliases and port=='in':todo.append(aid+':out')
        if edge['dst'] not in seen:
            errors.append('source connection has broken physical chain: '+str(key))
        if len(used)!=len(routes):
            errors.append('unreachable or duplicate physical branch: '+str(key))
    return errors
