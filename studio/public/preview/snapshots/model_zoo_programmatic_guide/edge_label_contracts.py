"""Validate captions against their emitter's exact source route, never distance."""
def validate_edge_labels(document,layout):
    labels=layout.get('edge_labels',[])
    specs={a['id']:a for a in labels}
    if len(specs)!=len(labels):raise ValueError('duplicate edge caption')
    routes={r['id']:r for r in layout['routes']};seen=set()
    for element in document.iter():
        identity=element.get('data-edge-label-id')
        if not identity:continue
        if identity not in specs or identity in seen:raise ValueError('unregistered/duplicate SVG edge caption '+identity)
        seen.add(identity);label=specs[identity];route=routes.get(label['route'])
        if not route or element.get('data-follow-edge')!=route['id']:raise ValueError('SVG caption route differs '+identity)
        source={k:route[k] for k in ['endpoint_binding','semantic_src','semantic_dst','semantic_src_port','semantic_dst_port','semantic_trace'] if k in route}
        if not source or label['source_binding']!=source:raise ValueError('caption source binding differs '+identity)
        lines=list(element)
        text=' | '.join(''.join(line.itertext()) for line in lines) if lines else ''.join(element.itertext())
        if text!=label['text']:raise ValueError('caption content differs '+identity)
    if seen!=set(specs):raise ValueError('SVG edge caption coverage differs')
    return len(seen)
