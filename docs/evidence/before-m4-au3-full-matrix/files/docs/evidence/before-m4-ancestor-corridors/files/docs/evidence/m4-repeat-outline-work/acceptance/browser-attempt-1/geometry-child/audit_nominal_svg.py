"""Independent, read-only audit of literal public SVG geometry; no product imports."""
from __future__ import annotations

import hashlib
import json
import math
import re
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[6]
RAW = PROJECT / 'docs/evidence/m4-repeat-outline-work/browser/attempt-1'
OUT = Path(__file__).resolve().parent
NS = {'s': 'http://www.w3.org/2000/svg'}
TAG = '{http://www.w3.org/2000/svg}'
TOL = .051
EPS = 1e-8
CASES = ['transformer-l0', 'cnn-l0', 'mlp-l0', 'transformer-encoder-detail']
MOVES = ['before', 'right', 'left', 'up', 'down', 'right-undo', 'left-undo', 'up-undo', 'down-undo', 'down-redo', 'saved', 'reopened']


def binding(path):
    data = path.read_bytes()
    return {'path': str(path.relative_to(PROJECT)), 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}


def new_json(name, value):
    with (OUT / name).open('x') as f:
        json.dump(value, f, ensure_ascii=False, indent=2)
        f.write('\n')


def points(d):
    """Reject non-orthogonal commands, relative commands, and unparsed characters."""
    tokens = re.findall(r'[MHVL]|[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?', d)
    remaining = re.sub(r'[MHVL]|[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?|[\s,]+', '', d)
    if remaining or not tokens or tokens[0] != 'M':
        raise ValueError(f'Unsupported orthogonal path: {d}')
    result, command, i = [], None, 0
    while i < len(tokens):
        if tokens[i] in ('M', 'H', 'V', 'L'):
            command = tokens[i]
            i += 1
        elif command is None:
            raise ValueError('No command')
        count = 2 if command in ('M', 'L') else 1
        if i + count > len(tokens) or any(t in ('M', 'H', 'V', 'L') for t in tokens[i:i+count]):
            raise ValueError('Incomplete path command')
        values = list(map(float, tokens[i:i+count]))
        i += count
        if command in ('M', 'L'):
            point = tuple(values)
            if command == 'M' and result:
                raise ValueError('Multiple subpaths')
            command = 'L'
        else:
            if not result:
                raise ValueError('Missing start')
            point = (values[0], result[-1][1]) if command == 'H' else (result[-1][0], values[0])
        if not all(math.isfinite(v) for v in point):
            raise ValueError('Non-finite path')
        if result and abs(point[0]-result[-1][0]) > EPS and abs(point[1]-result[-1][1]) > EPS:
            raise ValueError('Diagonal path')
        result.append(point)
    if len(result) < 2:
        raise ValueError('Missing route segment')
    return result


def rectangle(e):
    x, y, w, h = (float(e.get(k, '0')) for k in ('x', 'y', 'width', 'height'))
    if w <= 0 or h <= 0:
        raise ValueError('Nonpositive public rectangle')
    return [x, y, w, h]


def penetration(a, b, r):
    """Length of an orthogonal segment inside the OPEN, unrounded rectangle."""
    x, y, w, h = r
    if abs(a[0]-b[0]) <= EPS:
        if not x+EPS < a[0] < x+w-EPS:
            return 0.
        return max(0., min(max(a[1], b[1]), y+h)-max(min(a[1], b[1]), y))
    if abs(a[1]-b[1]) <= EPS:
        if not y+EPS < a[1] < y+h-EPS:
            return 0.
        return max(0., min(max(a[0], b[0]), x+w)-max(min(a[0], b[0]), x))
    raise ValueError('Nonorthogonal segment')


def ray_boundary(rects, p, side):
    axis = 0 if side in ('top', 'bottom') else 1
    tangent = p[axis]
    eligible = [r for r in rects if r[axis]-TOL <= tangent <= r[axis]+r[axis+2]+TOL]
    if not eligible:
        return None
    if side == 'top': return [p[0], min(r[1] for r in eligible)]
    if side == 'bottom': return [p[0], max(r[1]+r[3] for r in eligible)]
    if side == 'left': return [min(r[0] for r in eligible), p[1]]
    if side == 'right': return [max(r[0]+r[2] for r in eligible), p[1]]
    raise ValueError(side)


NORMAL = {'top': (0, -1), 'bottom': (0, 1), 'left': (-1, 0), 'right': (1, 0)}


def load_svg(path):
    if path.suffix == '.json':
        raw = json.loads(path.read_text())
        return raw['svg'], raw
    return path.read_text(), None


def audit(path):
    svg, capture = load_svg(path)
    root = ET.fromstring(svg)
    metadata = json.loads(root.find('s:metadata', NS).text)
    nodes, ports, routes = {}, {}, {}
    rendered = {n['sceneNodeId']: n for n in metadata['renderedNodes']}
    for e in root.iter():
        node_id = e.get('data-node-id')
        if e.tag == TAG+'g' and e.get('data-canonical-id'):
            direct = e.findall('s:rect', NS)
            rects = [rectangle(r) for r in direct]
            if not rects:
                raise ValueError('Node without public direct rectangle')
            headers = [p for p in e.findall('s:path', NS) if p.get('opacity') == '.28']
            if len(headers) > 1:
                raise ValueError('Multiple expanded headers')
            expanded = bool(headers)
            if expanded and len(rects) != 1:
                raise ValueError('Expanded node with ambiguous body')
            header = None
            if headers:
                hp = points(headers[0].get('d'))
                if len(hp) != 2 or hp[0][1] != hp[1][1]:
                    raise ValueError('Ambiguous header separator')
                header = rects[0][:]
                header[3] = hp[0][1]-header[1]
            stack = len(rects) == 3
            front = rects[-1] if stack else rects[0]
            shape_valid = not stack or all(
                max(abs(a-b) for a,b in zip(r, [front[0]+off,front[1]+off,front[2],front[3]])) <= EPS
                for r,off in zip(rects,[7,3.5,0]))
            title = e.find('s:title', NS).text
            nodes[node_id] = {'canonicalNodeId': e.get('data-canonical-id'), 'kind': title.split(' · ')[1],
                              'boundary': rendered[node_id]['boundary'], 'expanded': expanded,
                              'rectangles': rects, 'front': front, 'header': header,
                              'stack': stack, 'stackOffsetsValid': shape_valid}
        port_id = e.get('data-port-id')
        if port_id:
            circles = e.findall('s:circle', NS) if e.tag == TAG+'g' else [e]
            centers = [(float(c.get('cx')), float(c.get('cy'))) for c in circles]
            if not centers or any(p != centers[0] for p in centers):
                raise ValueError('Port circle centers differ')
            if port_id in ports:
                raise ValueError('Duplicate semantic port identity')
            ports[port_id] = {'nodeId': node_id, 'point': list(centers[0]), 'radii': [float(c.get('r')) for c in circles]}
        if e.tag == TAG+'g' and e.get('data-edge-id'):
            paths = e.findall('s:path', NS)
            if len(paths) != 1:
                raise ValueError('Edge without unique public path')
            routes[e.get('data-edge-id')] = {'points': points(paths[0].get('d')), 'd': paths[0].get('d'),
                                            'title': e.find('s:title', NS).text, 'pathAttrs': paths[0].attrib}
    bindings = {b['sceneEdgeId']: b for b in metadata['renderedBindings']}
    violations, endpoint_records, hits = [], [], []
    if set(bindings) != set(routes):
        violations.append({'type': 'edge-binding-set-mismatch', 'bindings': sorted(bindings), 'routes': sorted(routes)})
    if set(nodes) != set(rendered):
        violations.append({'type': 'rendered-node-set-mismatch'})
    for node_id, n in nodes.items():
        if not n['stackOffsetsValid']:
            violations.append({'type': 'stack-offset-mismatch', 'nodeId': node_id})
    for edge_id, route in routes.items():
        b = bindings[edge_id]
        pp = route['points']
        owners = {}
        for endpoint, index in [('source',0),('target',-1)]:
            canonical = b[endpoint]
            prefix = f"{canonical['nodeId']}:{canonical['portId']}:{b['role']}"
            candidates = []
            for pid, p in ports.items():
                standard = pid == prefix or pid in [prefix+':'+side for side in NORMAL]
                n = nodes[p['nodeId']]
                boundary = (n['boundary'] and n['canonicalNodeId'] == canonical['nodeId']
                            and pid == p['nodeId']+':'+canonical['portId'])
                if standard or boundary:
                    candidates.append((pid, p, 'canonical-node-port-role-side' if standard else 'canonical-boundary-node-port-and-endpoint'))
            close = [(pid,p,rule) for pid,p,rule in candidates if max(abs(p['point'][a]-pp[index][a]) for a in (0,1)) <= TOL]
            if len(close) != 1:
                violations.append({'type': 'endpoint-public-port-resolution', 'edgeId': edge_id, 'endpoint': endpoint,
                                   'routePoint': pp[index], 'candidates': [c[0] for c in candidates], 'close': [c[0] for c in close]})
                continue
            pid,p,rule = close[0]
            owner = nodes[p['nodeId']]
            owners[endpoint] = p['nodeId']
            suffix = pid[len(prefix):] if rule == 'canonical-node-port-role-side' else ''
            side = suffix[1:] if suffix else ('bottom' if endpoint == 'source' else 'top')
            expected = ray_boundary(owner['rectangles'], p['point'], side)
            boundary_error = None if expected is None else max(abs(p['point'][a]-expected[a]) for a in (0,1))
            nonzero = [(a,z) for a,z in zip(pp,pp[1:]) if max(abs(a[k]-z[k]) for k in (0,1)) > EPS]
            a,z = nonzero[0] if endpoint == 'source' else nonzero[-1]
            vec = [z[k]-a[k] for k in (0,1)]
            if endpoint == 'target': vec = [-v for v in vec]
            length = sum(abs(v) for v in vec)
            unit = [v/length for v in vec]
            normal_valid = all(abs(unit[k]-NORMAL[side][k]) <= EPS for k in (0,1))
            record = {'edgeId': edge_id, 'endpoint': endpoint, 'canonicalEndpoint': canonical, 'role': b['role'],
                      'portId': pid, 'ownerSceneNodeId': p['nodeId'], 'resolutionRule': rule,
                      'routePoint': pp[index], 'publicPortPoint': p['point'],
                      'routePortError': max(abs(p['point'][a]-pp[index][a]) for a in (0,1)),
                      'side': side, 'expectedNominalRayBoundary': expected, 'portBoundaryError': boundary_error,
                      'outwardEndpointSegment': vec, 'normalValid': normal_valid,
                      'ownerStack': owner['stack'], 'ownerKind': owner['kind']}
            endpoint_records.append(record)
            if boundary_error is None or boundary_error > TOL:
                violations.append({'type': 'port-ray-union-boundary', **record})
            if not normal_valid:
                violations.append({'type': 'endpoint-segment-normal', **record})
        for segment_index,(a,z) in enumerate(zip(pp,pp[1:])):
            for node_id,n in nodes.items():
                obstacles = [('header', 0, n['header'])] if n['expanded'] else [('card',i,r) for i,r in enumerate(n['rectangles'])]
                for kind,rect_index,rect in obstacles:
                    length = penetration(a,z,rect)
                    if length <= EPS:
                        continue
                    own = node_id in owners.values()
                    hits.append({'edgeId': edge_id, 'segmentIndex': segment_index, 'segment': [a,z],
                                 'nodeId': node_id, 'obstacleKind': kind, 'rectangleIndex': rect_index,
                                 'rectangle': rect, 'interiorLength': length, 'owner': own,
                                 'stack': n['stack'], 'nodeKind': n['kind'],
                                 'backplate': n['stack'] and rect_index < 2})
    dom_path = path.with_suffix('.dom.txt') if capture else None
    dom = dom_path.read_text() if dom_path and dom_path.exists() else ''
    diagnostics = [line.strip() for line in dom.splitlines() if '布局提示' in line or '连线缺少畅通路径' in line]
    stack_hits = [h for h in hits if h['stack']]
    pair = lambda hs: len({(h['edgeId'],h['nodeId']) for h in hs})
    counts = {'nodes': len(nodes), 'expandedGroups': sum(n['expanded'] for n in nodes.values()),
              'collapsedStacks': sum(n['stack'] for n in nodes.values()),
              'collapsedRepeatStacks': sum(n['stack'] and n['kind']=='Repeat' for n in nodes.values()),
              'publicPorts': len(ports), 'routes': len(routes), 'routeEndpoints': 2*len(routes),
              'resolvedEndpoints': len(endpoint_records),
              'stackOwnedEndpoints': sum(e['ownerStack'] for e in endpoint_records),
              'repeatStackOwnedEndpoints': sum(e['ownerStack'] and e['ownerKind']=='Repeat' for e in endpoint_records),
              'endpointViolations': len(violations), 'bodyRectangleInteriors': len([h for h in hits if h['obstacleKind']=='card']),
              'bodyEdgeNodePairs': pair([h for h in hits if h['obstacleKind']=='card']),
              'headerRectangleInteriors': len([h for h in hits if h['obstacleKind']=='header']),
              'headerEdgeNodePairs': pair([h for h in hits if h['obstacleKind']=='header']),
              'stackRectangleInteriors': len(stack_hits), 'stackEdgeNodePairs': pair(stack_hits),
              'backplateRectangleInteriors': len([h for h in stack_hits if h['backplate']]),
              'ownStackRectangleInteriors': len([h for h in stack_hits if h['owner']]),
              'ownBackplateRectangleInteriors': len([h for h in stack_hits if h['owner'] and h['backplate']])}
    return {'input': str(path.relative_to(PROJECT)), 'revision': metadata['revision'], 'viewBox': root.get('viewBox'),
            'counts': counts, 'violations': violations, 'interiorHits': hits, 'endpointRecords': endpoint_records,
            'nodes': nodes, 'ports': ports, 'routes': routes, 'visibleDomDiagnostics': diagnostics,
            'hollowExpandedGroupRule': 'Only direct header rectangles obstruct routes; body interiors hold descendants. No source/target owner rectangle or stack exemptions.'}


def controls():
    front = [0,0,20,10]
    stack = [[7,7,20,10],[3.5,3.5,20,10],front]
    checks = {
        'strict_diagonal_rejected': False,
        'strict_relative_rejected': False,
        'zero_length_segment_zero_interior': penetration((10,0),(10,0),front)==0,
        'boundary_segment_zero_interior': penetration((0,0),(20,0),front)==0,
        'body_crossing_detected': penetration((-1,5),(21,5),front)==20,
        'own_backplate_crossing_detected': penetration((10,10),(10,20),stack[0])==7,
        'bottom_front_only_ray': ray_boundary(stack,(1,10),'bottom')==[1,10],
        'bottom_half_plate_ray': ray_boundary(stack,(5,13.5),'bottom')==[5,13.5],
        'bottom_full_plate_ray': ray_boundary(stack,(10,17),'bottom')==[10,17],
        'right_front_only_ray': ray_boundary(stack,(20,1),'right')==[20,1],
        'right_half_plate_ray': ray_boundary(stack,(23.5,5),'right')==[23.5,5],
        'right_full_plate_ray': ray_boundary(stack,(27,10),'right')==[27,10],
        'envelope_empty_corner_not_rect_hit': not any(penetration((0,15),(2,15),r)>0 for r in stack),
    }
    for key,d in [('strict_diagonal_rejected','M 0 0 L 2 3'),('strict_relative_rejected','M 0 0 v 3')]:
        try: points(d)
        except ValueError: checks[key]=True
    if not all(checks.values()): raise AssertionError(checks)
    return checks


def main():
    inputs = [RAW/c/f for c in CASES for f in ['browser-scene.svg','figure.svg']]
    inputs += [RAW/'transformer-encoder-detail'/'preview.svg']
    inputs += [RAW/'transformer-moves'/f'{m}.json' for m in MOVES]
    bound = inputs + [RAW/'transformer-moves'/f'{m}.dom.txt' for m in MOVES]
    before = [binding(p) for p in bound]
    new_json('inputs-before.json', before)
    audits = [audit(p) for p in inputs]
    after = [binding(p) for p in bound]
    new_json('inputs-after.json', after)
    if before != after: raise AssertionError('Inputs changed during audit')
    report = {'schema': 'independent-nominal-svg-geometry-review/1.0', 'tolerance': TOL,
              'productImports': False, 'inputHashesUnchanged': True, 'inputCount': len(bound),
              'controlChecks': controls(), 'artifactsAudited': len(audits), 'audits': audits,
              'aggregateCounts': dict(Counter({k:sum(a['counts'][k] for a in audits) for k in audits[0]['counts']})),
              'limitations': ['Nominal axis-aligned rectangle interiors and ray union boundaries only; rounded corners, glyphs, stroke/arrowhead footprint, raster antialiasing, and screenshot visibility are outside this audit.',
                              'Four representative model cases and a Transformer movement journal are not the full browser matrix and do not constitute human acceptance.',
                              'Explicit DOM routing diagnostics are preserved as observations and never exempt a route from geometry checks.',
                              'Boundary port IDs omit role; boundary endpoints require canonical node and port identity plus a unique public circle within endpoint tolerance.',
                              'Expanded group body interiors intentionally contain child nodes/routes; their literal public header separators define obstructing header rectangles.']}
    new_json('report.json', report)
    lines = ['# Independent nominal SVG geometry review', '',
             f"{len(audits)} literal SVG artifacts; {len(bound)} input hashes unchanged. No product geometry/router imports.", '',
             '| Input | Routes | Endpoints | Endpoint violations | Stack hits | Body hits | Header hits |',
             '| --- | ---: | ---: | ---: | ---: | ---: | ---: |']
    for a in audits:
        c=a['counts']; name=a['input'].replace(str(RAW.relative_to(PROJECT))+'/', '')
        lines.append(f"| {name} | {c['routes']} | {c['resolvedEndpoints']} | {c['endpointViolations']} | {c['stackRectangleInteriors']} | {c['bodyRectangleInteriors']} | {c['headerRectangleInteriors']} |")
    lines += ['', 'All intersections remain in report.json. Reported warning text never excuses a geometric hit.', '',
              'This review covers unrounded nominal rectangles and route centerlines only. It does not establish stroke, arrowhead, glyph or raster clearance; four representative cases are not a full matrix or human acceptance.']
    with (OUT/'report.md').open('x') as f: f.write('\n'.join(lines)+'\n')
    print(json.dumps({'aggregate': report['aggregateCounts'], 'rows': [{'input':a['input'],'counts':a['counts'],'hits':a['interiorHits'],'violations':a['violations']} for a in audits], 'report':binding(OUT/'report.json')},ensure_ascii=False,indent=2))


if __name__ == '__main__':
    main()
