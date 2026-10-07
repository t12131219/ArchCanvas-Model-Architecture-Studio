"""Independent static JSON/XML and literal geometry preflight; no product imports."""
from pathlib import Path
from copy import deepcopy
import hashlib
import json
import math
import re
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[3]
WORK = HERE / 'workload'
NS = '{http://www.w3.org/2000/svg}'
ROOT = 'call:instance:model.DenseStress300'
NETWORK = 'call:instance:model.DenseStress300.network'
OUTPUT = 'output:model.DenseStress300:0'
PIN = 'input:model.DenseStress300:features'
COMPACT_KEY = 'visible-frontier/1:["call:instance:model.DenseStress300"]'
DEEP_KEY = 'visible-frontier/1:["call:instance:model.DenseStress300","call:instance:model.DenseStress300.network"]'
checks = []
def add(name, passed, detail=None):
    checks.append({'relation': name, 'passed': bool(passed), **({'detail': detail} if detail is not None else {})})
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def near(a, b, epsilon=1e-9): return abs(a - b) <= epsilon
def stable_sha(v): return hashlib.sha256(json.dumps(v, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()
def load(p): return json.loads(p.read_text())

original = load(WORK / 'unbroken-grid4.canvas.json')
docs = {n: load(WORK / (n + '.canvas.json')) for n in ['candidate', 'pinned', 'collapsed', 'reexpanded']}
scenes = {n: load(WORK / (n + '.scene.json')) for n in docs}
trees = {n: ET.parse(WORK / (n + '.svg')).getroot() for n in docs}
arch = original['architecture']; canonical = {n['id']: n for n in arch['nodes']}; edges = {e['id']: e for e in arch['edges']}
preparation = load(WORK / 'preparation-report.json')
add('finite20-preparation-input-bindings-exact', len(preparation['inputs']) == 20 and all((PROJECT / i['path']).stat().st_size == i['bytes'] and sha(PROJECT / i['path']) == i['sha256'] for i in preparation['inputs']))
add('new-input-is-exact-unbroken-grid4', original['revision'] == 4 and (WORK / 'unbroken-grid4.canvas.json').read_bytes() == (PROJECT / 'docs/evidence/m4-readable-grid-next-work/inputs/previous-workload/grid.canvas.json').read_bytes())
semantic_nodes = []
for n in arch['nodes']:
    item = {k: v for k, v in n.items() if k not in ['source', 'parameterOrigins']}
    if 'parameterOrigins' in n: item['parameterOrigins'] = {k: {q: o[q] for q in ['kind', 'expression', 'path']} for k, o in n['parameterOrigins'].items()}
    semantic_nodes.append(item)
source_inputs = [{k: v for k, v in s.items() if k != 'content'} for s in arch['sources']]
add('embedded-source-and-semantic-ir-digests-recomputed', all(hashlib.sha256(s['content'].encode()).hexdigest() == s['digest'] for s in arch['sources']) and stable_sha(source_inputs) == arch['sourceDigest'] and stable_sha({'entry': arch['entry'], 'nodes': semantic_nodes, 'edges': arch['edges']}) == arch['irDigest'])
add('actual-current-frontier-operation-exact', load(WORK / 'typed-current-move.json') == {'type': 'move', 'ids': [OUTPUT], 'dx': 0, 'dy': -28590, 'scope': 'current-frontier'})
expected = deepcopy(original); expected['revision'] = 5; expected['layout'][OUTPUT] = {'x': 30, 'y': 1664}; expected['layoutByFrontier'][DEEP_KEY] = deepcopy(expected['layout'])
add('complete-candidate-exact-independent-current-only-expected', docs['candidate'] == expected)
add('complete-original-compact-cache-remains-exact', docs['candidate']['layoutByFrontier'][COMPACT_KEY] == original['layoutByFrontier'][COMPACT_KEY])
expected_pin = deepcopy(expected); expected_pin['revision'] = 6; expected_pin['pinnedObjects'] = [PIN]
add('complete-typed-pin-only-expected', docs['pinned'] == expected_pin)
expected_compact = deepcopy(expected_pin); expected_compact['revision'] = 7; expected_compact['expandedIds'] = [ROOT]; expected_compact['layout'][OUTPUT] = {'x': 30, 'y': 262}
add('complete-collapse-exact-literal-compact-output-and-retained-hidden-locals', docs['collapsed'] == expected_compact)
expected_reexpanded = deepcopy(expected_pin); expected_reexpanded['revision'] = 8
add('complete-reexpanded-document-exact-except-revision', docs['reexpanded'] == expected_reexpanded)

def world(d, identity):
    x = y = 0; current = identity
    while current:
        p = d['layout'][current]; x += p['x']; y += p['y']; current = canonical[current].get('parentId')
    return x, y
def route_points(path):
    tokens = re.findall(r'[A-Za-z]|[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?', path)
    result = []; i = 0
    while i < len(tokens):
        command = tokens[i]; value = float(tokens[i + 1]); i += 2
        if command in ['M', 'L']: result.append((value, float(tokens[i]))); i += 1
        elif command == 'H': result.append((value, result[-1][1]))
        elif command == 'V': result.append((result[-1][0], value))
        else: raise ValueError('Unexpected path command: ' + command)
    return result

binding_counts = []; summaries = []
for name, d in docs.items():
    s = scenes[name]; xml = trees[name]; m = json.loads(xml.find(NS + 'metadata').text)
    nodes = {n['id']: n for n in s['nodes']}
    groups = {n.get('data-node-id'): n for n in xml.iter() if n.get('data-canonical-id')}
    visible = {ROOT, NETWORK, PIN, OUTPUT} if name == 'collapsed' else set(canonical)
    add(name + ':document-source-ir-and-public-svg-identity-exact', d['architecture'] == arch and d['sourceBindingDigest'] == arch['sourceDigest'] and xml.get('data-document-id') == d['id'] == m['documentId'] == s['documentId'] and int(xml.get('data-revision')) == d['revision'] == s['revision'] == m['revision'] and m['sourceDigest'] == arch['sourceDigest'] == s['sourceDigest'] and m['irDigest'] == arch['irDigest'] == s['irDigest'])
    facts = m['sourceFacts']; facts_ok = len(facts) == 304 and len({f['id'] for f in facts}) == 304 and {f['id'] for f in facts} == set(canonical) and s['sourceFacts'] == facts and m['sourceFactScope'] == 'whole-source-architecture'
    for f in facts:
        n = canonical[f['id']]; count = len({a['callId'] for a in arch['nodes'] if a.get('instanceId') == n.get('instanceId') and a.get('callId')}) if n.get('instanceId') else None
        facts_ok &= f['sourceLabel'] == n['label'] and all(f.get(k) == n.get(k) for k in ['kind', 'category', 'evidence', 'source', 'instanceId', 'callId', 'repeat', 'outputPath']) and f.get('callCount') == count
    add(name + ':all304-whole-source-facts-exact-even-when-collapsed', facts_ok)
    add(name + ':literal-visible-node-set-in-scene-and-svg', set(nodes) == set(groups) == visible and len(m['renderedNodes']) == len(visible) and {n['canonicalNodeId'] for n in m['renderedNodes']} == visible)
    bodies_ok = True; ports_ok = True; endpoints_ok = True
    for identity, n in nodes.items():
        g = groups[identity]; body = next(c for c in g if c.tag == NS + 'rect' and c.get('stroke-width') is not None)
        x, y = world(d, identity)
        bodies_ok &= near(n['x'], x) and near(n['y'], y) and near(n['localX'], d['layout'][identity]['x']) and near(n['localY'], d['layout'][identity]['y']) and g.get('data-canonical-id') == identity
        bodies_ok &= all(near(float(body.get(k)), n[k], .005001) for k in ['x', 'y', 'width', 'height'])
        for p in n['ports']:
            for binding in p['canonicalBindings']:
                ports_ok &= binding['nodeId'] in canonical and any(a['id'] == binding['portId'] for a in canonical[binding['nodeId']]['ports'])
            ports_ok &= all(e in edges for e in p['canonicalEdgeIds'])
            element = next(e for e in xml.iter() if e.get('data-port-id') == p['id']); circle = list(element)[-1]
            ports_ok &= near(float(circle.get('cx')), p['x'], .005001) and near(float(circle.get('cy')), p['y'], .005001)
    add(name + ':all-body-world-coordinates-independently-sum-locals-and-match-svg', bodies_ok)
    add(name + ':all-public-port-centres-and-canonical-port-references-faithful', ports_ok)
    represented = []; binding_ok = len(m['renderedBindings']) == len(s['edges'])
    for b in m['renderedBindings']:
        ids = b['canonicalEdgeIds']; represented.extend(ids)
        binding_ok &= bool(ids) and all(i in edges and edges[i]['source'] == b['source'] and edges[i]['role'] == b['role'] and edges[i]['tensorId'] == b['tensorId'] for i in ids) and edges[ids[0]]['target'] == b['target']
    expected_edges = {'edge:1', 'edge:2', 'edge:303'} if name == 'collapsed' else set(edges) - {'edge:0', 'edge:302'}
    binding_ok &= set(represented) == expected_edges and len(represented) == len(set(represented)) and set(s['hiddenEdges']) == set(edges) - expected_edges
    add(name + ':rendered-and-hidden-canonical-edge-partition-exact', binding_ok, {'renderedRoutes': len(s['edges']), 'representedCanonical': len(represented), 'hiddenCanonical': len(s['hiddenEdges']), 'fullCanonicalEdges': len(edges)})
    for edge in s['edges']:
        public = next(e for e in xml.iter() if e.get('data-edge-id') == edge['id']); public_path = next(c for c in public if c.tag == NS + 'path')
        pts = route_points(public_path.get('d'))
        def bound_ports(identity, direction, binding):
            return [p for p in nodes[identity]['ports'] if p['direction'] == direction and binding in p['canonicalBindings'] and all(i in p['canonicalEdgeIds'] for i in edge['canonicalEdgeIds'])]
        source_ports = bound_ports(edge['sourceId'], 'out', edge['source'])
        target_ports = bound_ports(edge['targetId'], 'in', edge['target'])
        if len(source_ports) != 1 or len(target_ports) != 1:
            endpoints_ok = False
            continue
        a, b = source_ports[0], target_ports[0]
        endpoints_ok &= public_path.get('d') == edge['path'] and near(pts[0][0], a['x'], .005001) and near(pts[0][1], a['y'], .005001) and near(pts[-1][0], b['x'], .005001) and near(pts[-1][1], b['y'], .005001)
    add(name + ':all-route-paths-and-public-port-endpoints-faithful', endpoints_ok)
    sibling_overlap = []
    vals = list(nodes.values())
    for i, a in enumerate(vals):
        for b in vals[i + 1:]:
            if a.get('parentId') == b.get('parentId') and min(a['x'] + a['width'], b['x'] + b['width']) > max(a['x'], b['x']) and min(a['y'] + a['height'], b['y'] + b['height']) > max(a['y'], b['y']): sibling_overlap.append([a['id'], b['id']])
    add(name + ':finite-sibling-body-nonoverlap', not sibling_overlap, {'overlaps': sibling_overlap})
    if name != 'collapsed':
        grid_ok = True
        for i in range(300):
            row = i // 20; column = 19 - i % 20 if row % 2 else i % 20
            n = nodes['call:instance:model.DenseStress300.network.' + str(i)]
            grid_ok &= (n['x'], n['y'], n['width'], n['height']) == (110 + column * 218, 316 + row * 92, 194, 62)
        add(name + ':300-leaf-grid-literal-coordinates-and-dimensions-exact', grid_ok)
    summaries.append({'state': name, 'revision': d['revision'], 'bodyCount': len(nodes), 'bounds': s['bounds'], 'output': {'x': nodes[OUTPUT]['x'], 'y': nodes[OUTPUT]['y']}, 'diagnostics': s['diagnostics']})

add('root-position-anchor-only-not-frame-size-invariance', all((scenes[n]['nodes'][0]['x'], scenes[n]['nodes'][0]['y']) == (50, 92) for n in docs))
add('network-operated-position-anchor-only-not-size-invariance', all((next(a for a in scenes[n]['nodes'] if a['id'] == NETWORK)['x'], next(a for a in scenes[n]['nodes'] if a['id'] == NETWORK)['y']) == (80, 254) for n in docs))
pin_bodies = [next(a for a in scenes[n]['nodes'] if a['id'] == PIN) for n in ['pinned', 'collapsed', 'reexpanded']]
add('unrelated-input-pin-body-world-exact-through-both-frontiers', all(docs[n]['pinnedObjects'] == [PIN] for n in ['pinned', 'collapsed', 'reexpanded']) and all((n['x'], n['y'], n['width'], n['height']) == (80, 154, 194, 62) for n in pin_bodies))
add('unpinned-output-legitimate-different-frontier-positions', all((next(a for a in scenes[n]['nodes'] if a['id'] == OUTPUT)['x'], next(a for a in scenes[n]['nodes'] if a['id'] == OUTPUT)['y']) == (80, 354 if n == 'collapsed' else 1756) for n in docs))
failures = [c for c in checks if not c['passed']]
report = {'schema': 'archcanvas-frontier-workload-independent-preflight/1', 'groupedRelations': len(checks), 'passedGroups': len(checks) - len(failures), 'failedGroups': len(failures), 'checks': checks, 'states': summaries,
    'limits': ['Static typed preparation and JSON/XML/literal body evidence only, no browser input or mounted Studio.', 'SVG numerical values are rounded to0.01; ports/endpoints compared within0.005001 world units.', 'World pin and root/network position anchors do not certify screen/camera continuity or frame-size invariance.', 'Collapsed output354 and expanded1756 are distinct legitimate unpinned placements, not zero common-body movement.', '300 bodies, nominal typography and no sibling body intersections do not certify readable text, occlusion, global route aesthetics, publication or presented performance.', 'Old malformed candidate,353/357 native report and old raw are retained unchanged; no migration.', 'No model execution, semantic writeback, new human participants or M4 completion.'],
    'modelExecuted': False, 'browserInputsAdded': 0, 'humanParticipantsAdded': 0, 'performanceGatePassed': False}
with (HERE / 'workload-readback-report.json').open('x') as f: json.dump(report, f, ensure_ascii=False, indent=2); f.write('\n')
print(json.dumps({'groups': len(checks), 'passed': len(checks) - len(failures), 'failed': failures, 'states': summaries}, ensure_ascii=False))
raise SystemExit(1 if failures else 0)
