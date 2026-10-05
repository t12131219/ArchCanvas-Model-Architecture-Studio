"""Parse actual public DOM SVG with Python's standard XML parser; no product imports."""
from pathlib import Path
import argparse
import hashlib
import json
import re
import xml.etree.ElementTree as ET

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
NS = '{http://www.w3.org/2000/svg}'

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def parse(dom_path, canvas_path, standalone=False):
    dom = {'svg': dom_path.read_text()} if standalone else json.loads(dom_path.read_text())
    stored = json.loads(canvas_path.read_text())
    document = stored.get('document', stored)
    svg = ET.fromstring(dom['svg'])
    metadata = json.loads(svg.find(NS + 'metadata').text)
    architecture = document['architecture']
    canonical = {node['id']: node for node in architecture['nodes']}
    expanded = set(document['expandedIds'])
    all_groups = list(svg.iter())
    node_groups = {group.get('data-node-id'): group for group in all_groups if group.get('data-node-id') and not group.get('data-port-id')}
    port_groups = [group for group in all_groups if group.get('data-port-id')]
    edge_groups = {group.get('data-edge-id'): group for group in all_groups if group.get('data-edge-id')}
    bindings = metadata['renderedBindings']
    assert len(node_groups) == len(metadata['renderedNodes'])
    assert set(edge_groups) == {binding['sceneEdgeId'] for binding in bindings}
    assert metadata['documentId'] == document['id']
    assert metadata['revision'] == document['revision']
    assert metadata['sourceDigest'] == architecture['sourceDigest'] == document['sourceBindingDigest']
    assert metadata['irDigest'] == architecture['irDigest']
    assert sorted(node_groups) == sorted(node['sceneNodeId'] for node in metadata['renderedNodes'])

    def representative(node_id):
        while node_id not in node_groups:
            node_id = canonical[node_id]['parentId']
        return node_id

    nodes = []
    for node_id, group in node_groups.items():
        # The main visible body is the direct rect with its declared stroke width;
        # decorative repeat shadows and nested glyph/button rects are not bodies.
        bodies = [child for child in group if child.tag == NS + 'rect' and child.get('stroke-width')]
        assert len(bodies) == 1
        rect = bodies[0]
        x, y, width, height = (float(rect.get(key)) for key in ('x', 'y', 'width', 'height'))
        original = canonical[node_id]
        node = dict(id=node_id, x=x, y=y, width=width, height=height, localX=0, localY=0,
                    label=group.get('aria-label'), subtitle='', kind=original['kind'], category=original['category'],
                    fill=rect.get('fill'), stroke=rect.get('stroke'), glyph='module', expanded=node_id in expanded,
                    expandable=bool(original['children']), pinned=node_id in document['pinnedObjects'], evidence=original['evidence'], ports=[])
        if original.get('parentId'):
            node['parentId'] = original['parentId']
        dividers = [child for child in group if child.tag == NS + 'path' and child.get('opacity') == '.28']
        assert len(dividers) == int(node_id in expanded)
        # The public SVG grammar places its separator 4 units above the padded
        # header boundary. Parse its actual y coordinate independently; no font,
        # router or product geometry helper computes the region.
        node['headerHeight'] = float(re.fullmatch(r'M\s+[-\d.]+\s+([-\d.]+)\s+H\s+[-\d.]+', dividers[0].get('d'))[1]) - y + 4 if dividers else height
        nodes.append(node)
    by_node = {node['id']: node for node in nodes}
    for group in port_groups:
        if group.tag == NS + 'circle':
            circle = group
        else:
            circles = [child for child in group if child.tag == NS + 'circle']
            assert circles
            circle = circles[0]
        port_id, owner = group.get('data-port-id'), group.get('data-node-id')
        matches = []
        for binding in bindings:
            for endpoint, direction in [('source', 'out'), ('target', 'in')]:
                canonical_binding = binding[endpoint]
                expected_id = f"{canonical_binding['nodeId']}:{canonical_binding['portId']}:{binding['role']}"
                if owner == representative(canonical_binding['nodeId']) and port_id == expected_id:
                    matches.append((binding, canonical_binding, direction))
        assert matches, (owner, port_id)
        assert len({direction for _, _, direction in matches}) == 1
        binding, endpoint, direction = matches[0]
        canonical_port = next(port for port in canonical[endpoint['nodeId']]['ports'] if port['id'] == endpoint['portId'])
        edge_ids = list(dict.fromkeys(edge for binding, _, _ in matches for edge in binding['canonicalEdgeIds']))
        canonical_bindings = []
        for _, endpoint_value, _ in matches:
            if endpoint_value not in canonical_bindings:
                canonical_bindings.append(endpoint_value)
        by_node[owner]['ports'].append(dict(id=port_id, canonicalNodeId=endpoint['nodeId'], canonicalPortId=endpoint['portId'],
            canonicalBindings=canonical_bindings, canonicalEdgeIds=edge_ids, direction=direction, role=canonical_port['role'],
            name=canonical_port['name'], x=float(circle.get('cx')), y=float(circle.get('cy')), proxy=owner != endpoint['nodeId']))
    edges = []
    for binding in bindings:
        group = edge_groups[binding['sceneEdgeId']]
        path = next(child for child in group if child.tag == NS + 'path')
        assert group.get('data-tensor-id') == binding['tensorId']
        labels = [child for child in group if child.tag == NS + 'text']
        assert len(labels) <= 1
        edges.append(dict(id=binding['sceneEdgeId'], sourceId=representative(binding['source']['nodeId']), targetId=representative(binding['target']['nodeId']),
            source=binding['source'], target=binding['target'], canonicalEdgeIds=binding['canonicalEdgeIds'], tensorId=binding['tensorId'], role=binding['role'],
            path=path.get('d'), stroke=path.get('stroke'), width=float(path.get('stroke-width')), dashed=bool(path.get('stroke-dasharray')),
            label=''.join(labels[0].itertext()) if labels else '', labelX=float(labels[0].get('x')) if labels else 0, labelY=float(labels[0].get('y')) if labels else 0))
    bx, by, bw, bh = map(float, svg.get('viewBox').split())
    represented = {edge_id for binding in bindings for edge_id in binding['canonicalEdgeIds']}
    scene = dict(version='1.0', documentId=metadata['documentId'], revision=metadata['revision'], title=svg.get('aria-label'),
        bounds=dict(x=bx, y=by, width=bw, height=bh), nodes=nodes, edges=edges, hiddenEdges=[edge['id'] for edge in architecture['edges'] if edge['id'] not in represented],
        legend=[], annotations=[], pageSpec=document['pageSpec'], sourceDigest=metadata['sourceDigest'], irDigest=metadata['irDigest'], sourceFacts=metadata['sourceFacts'], diagnostics=[])
    return scene, dict(metadata=metadata, nodeXml={node_id: ET.tostring(group, encoding='unicode') for node_id, group in node_groups.items()},
        portXml={group.get('data-port-id'): ET.tostring(group, encoding='unicode') for group in port_groups},
        canonicalDocument=document, storageRevision=stored.get('revision'), scripts=dom.get('scripts'), links=dom.get('links'))

def main():
    parser = argparse.ArgumentParser()
    for key in ['before_dom', 'after_dom', 'before_canvas', 'after_canvas']:
        parser.add_argument('--' + key.replace('_', '-'), required=True, type=Path)
    args = parser.parse_args()
    paths = vars(args)
    before, b = parse(args.before_dom, args.before_canvas)
    after, a = parse(args.after_dom, args.after_canvas)
    assert b['canonicalDocument'] == a['canonicalDocument'], 'actual saved CanvasDocument changed'
    assert b['storageRevision'] == a['storageRevision'], 'storage CAS revision changed'
    assert b['nodeXml'] == a['nodeXml'], 'visible owner body/text/controls changed'
    assert b['portXml'] == a['portXml'], 'visible port glyphs/positions changed'
    assert b['metadata']['sourceFacts'] == a['metadata']['sourceFacts']
    assert b['metadata']['renderedNodes'] == a['metadata']['renderedNodes']
    assert b['metadata']['renderedBindings'] == a['metadata']['renderedBindings']
    for name, data in [('browser-before.scene.json', before), ('browser-after.scene.json', after), ('browser-xml-binding.json', dict(
        scope='Actual read-only DOM SVG and actual CAS store. XML parser never imports product or model. Header covers SVG divider plus documented 4-unit padded band. This is a browser engineering representative, not full matrix/human/performance certification.',
        inputs={key: dict(path=str(path.resolve().relative_to(ROOT)), sha256=digest(path)) for key, path in paths.items()},
        checks=['saved document exact', 'storage revision exact', 'visible node XML exact', 'visible port XML exact', 'sourceFacts exact', 'renderedNodes exact', 'renderedBindings exact'],
        beforeScripts=b['scripts'], afterScripts=a['scripts'], beforeNodeCount=len(before['nodes']), beforeEdgeCount=len(before['edges']), beforePortCount=sum(len(node['ports']) for node in before['nodes'])))]:
        target = OUT / name
        assert not target.exists(), f'Refusing overwrite: {target}'
        target.write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n')
    print(json.dumps(dict(nodes=len(before['nodes']), edges=len(before['edges']), ports=sum(len(node['ports']) for node in before['nodes']), savedDocumentUnchanged=True)))

if __name__ == '__main__':
    main()
