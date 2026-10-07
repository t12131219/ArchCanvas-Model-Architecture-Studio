"""Read-only facts from captured public DOM; not a product route or hit oracle."""
from pathlib import Path
import hashlib
import itertools
import json
import re
import xml.etree.ElementTree as ET

FORMAL = Path(__file__).resolve().parents[4]
SOURCE = FORMAL / 'docs/evidence/m4-authoring-interaction-work/browser-attempt-1'
WORK = Path(__file__).resolve().parent

def binding(path):
    raw = path.read_bytes()
    return {'path': str(path.relative_to(FORMAL)), 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}

def points(path):
    tokens = re.findall(r'[MLHV]|[-+]?(?:\d*\.)?\d+(?:e[-+]?\d+)?', path, re.I)
    out = []; current = (0.0, 0.0); i = 0
    while i < len(tokens):
        command = tokens[i]; i += 1
        if command in ('M', 'L'):
            current = (float(tokens[i]), float(tokens[i + 1])); i += 2
        elif command == 'H':
            current = (float(tokens[i]), current[1]); i += 1
        elif command == 'V':
            current = (current[0], float(tokens[i])); i += 1
        else:
            raise ValueError(f'Unsupported actual path command: {command}')
        if not out or out[-1] != current:
            out.append(current)
    return out

def route_facts(edge):
    ps = points(edge['path']); segments = []
    for a, b in zip(ps, ps[1:]):
        orientation = 'H' if a[1] == b[1] else 'V' if a[0] == b[0] else 'diagonal'
        segments.append({'a': list(a), 'b': list(b), 'axis': orientation})
    bends = sum(a['axis'] != b['axis'] for a, b in zip(segments, segments[1:]))
    return {**edge, 'points': [list(p) for p in ps], 'segments': segments, 'visibleNonzeroBends': bends}

def pair_facts(routes):
    overlaps = []; crossings = []
    for a, b in itertools.combinations(routes, 2):
        for s in a['segments']:
            for t in b['segments']:
                if s['axis'] == t['axis'] == 'H' and s['a'][1] == t['a'][1]:
                    lo = max(min(s['a'][0], s['b'][0]), min(t['a'][0], t['b'][0])); hi = min(max(s['a'][0], s['b'][0]), max(t['a'][0], t['b'][0]))
                    if hi > lo: overlaps.append({'edges': [a['id'], b['id']], 'axis': 'H', 'lane': s['a'][1], 'lo': lo, 'hi': hi})
                if s['axis'] == t['axis'] == 'V' and s['a'][0] == t['a'][0]:
                    lo = max(min(s['a'][1], s['b'][1]), min(t['a'][1], t['b'][1])); hi = min(max(s['a'][1], s['b'][1]), max(t['a'][1], t['b'][1]))
                    if hi > lo: overlaps.append({'edges': [a['id'], b['id']], 'axis': 'V', 'lane': s['a'][0], 'lo': lo, 'hi': hi})
                if {s['axis'], t['axis']} == {'H', 'V'}:
                    h, v = (s, t) if s['axis'] == 'H' else (t, s)
                    x = v['a'][0]; y = h['a'][1]
                    if min(h['a'][0], h['b'][0]) < x < max(h['a'][0], h['b'][0]) and min(v['a'][1], v['b'][1]) < y < max(v['a'][1], v['b'][1]):
                        crossings.append({'edges': [a['id'], b['id']], 'point': [x, y]})
    return {'strictInteriorCrossings': crossings, 'positiveLengthSharedLanes': overlaps, 'notSemanticNecessityOrLegalityOracle': True}

def observe(name):
    path = SOURCE / f'{name}.public.json'; before = binding(path); data = json.loads(path.read_text())
    if 'svg' not in data:
        return {'case': name, 'inputBefore': before, 'inputAfter': binding(path), 'inputExact': before == binding(path),
                'camera': data.get('camera'), 'summary': data.get('summary'), 'footer': data.get('footer'),
                'routes': [], 'routePairs': {'strictInteriorCrossings': [], 'positiveLengthSharedLanes': []}, 'recordedDomHitSamples': [],
                'noSvgCaptured': True, 'geometryObserved': False, 'actualNativeOperationNotEstablishedByThisScript': True}
    xml = ET.fromstring(data['svg'])
    edges = data.get('edges')
    if edges is None:
        edges = []
        for group in xml.iter():
            if 'data-edge-id' in group.attrib:
                for child in group:
                    if child.tag.endswith('path') and child.attrib.get('stroke') != 'transparent':
                        edges.append({'id': group.attrib['data-edge-id'], 'path': child.attrib['d']}); break
    routes = [route_facts(edge) for edge in edges]
    hits = []
    for port in data.get('ports', []):
        for kind, center in port.get('centers', {}).items():
            got = center.get('hit', {}); view = data.get('view', {})
            inside = view.get('x', 0) <= center['x'] <= view.get('x', 0) + view.get('width', 0) and view.get('y', 0) <= center['y'] <= view.get('y', 0) + view.get('height', 0)
            hits.append({'node': port['node'], 'port': port['port'], 'sample': kind, 'center': {'x': center['x'], 'y': center['y']},
                         'observedHit': got, 'sameEndpoint': got.get('node') == port['node'] and got.get('port') == port['port'],
                         'insideViewport': inside, 'notNativeEvent': True})
    captions = []
    for group in xml.iter():
        if 'data-node-id' in group.attrib and group.tag.endswith('g'):
            captions.append({'id': group.attrib['data-node-id'], 'texts': [''.join(c.itertext()) for c in group if c.tag.endswith('text')]})
    return {'case': name, 'inputBefore': before, 'inputAfter': binding(path), 'inputExact': before == binding(path),
            'scripts': data.get('scripts'), 'flow': data.get('flow'), 'camera': data.get('camera'), 'summary': data.get('summary'), 'footer': data.get('footer'),
            'nodes': data.get('nodes'), 'captions': captions, 'routes': routes, 'routePairs': pair_facts(routes), 'recordedDomHitSamples': hits,
            'actualNativeOperationNotEstablishedByThisScript': True}

def run(names, output):
    observations = [observe(n) for n in names]
    with (WORK / output).open('x') as file:
        json.dump({'kind': 'independent-captured-public-geometry-and-dom-hit-facts', 'modelsExecuted': False, 'productImported': False, 'humanParticipant': False, 'observations': observations}, file, indent=2, ensure_ascii=False); file.write('\n')
    print(json.dumps([{'case': o['case'], 'routes': len(o['routes']), 'bends': [r['visibleNonzeroBends'] for r in o['routes']], 'crossings': len(o['routePairs']['strictInteriorCrossings']), 'sharedLanes': len(o['routePairs']['positiveLengthSharedLanes']), 'domSamples': len(o['recordedDomHitSamples']), 'hitMismatches': sum(not s['sameEndpoint'] for s in o['recordedDomHitSamples']), 'outsideViewport': sum(not s['insideViewport'] for s in o['recordedDomHitSamples'])} for o in observations], ensure_ascii=False))

if __name__ == '__main__':
    import sys
    run(sys.argv[2:], sys.argv[1])
