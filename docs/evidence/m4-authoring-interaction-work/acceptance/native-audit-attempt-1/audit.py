"""Read previously recorded native observations; do not drive the product/browser."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import ast
import re
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[5]
OUT = Path(__file__).resolve().parent
BROWSER = ROOT / 'docs/evidence/m4-authoring-interaction-work/browser-attempt-1'
CONTRACT = ROOT / 'docs/evidence/m4-authoring-interaction-work/acceptance/flow-contract.json'
PRIOR_MANAGED_PUBLIC = ROOT / 'docs/evidence/m4-collapse-continuity-work/authoring-browser-attempt-1/managed-figure-after.json'
PRIOR_MANAGED_SAVED = ROOT / 'docs/evidence/m4-collapse-continuity-work/authoring-browser-attempt-1/managed-saved-envelope.json'
EPSILON = 0.0001
# The parent identified this capture-closure failure before raw freeze. Preserve its
# exact null fields and audit intact SVG geometry; do not promote these hits to success.
KNOWN_INCOMPLETE_OBSERVER_FILES = {
    'node-left16-supplement-settled.public.json', 'node-left16-supplement-undone.public.json',
    'pan-cancel-settled.public.json', 'pan-down-retry40.public.json',
    'vertical-100-current.public.json', 'vertical-100-pending-after.public.json',
    'vertical-100-pending-before.public.json', 'vertical-final-reopened-after.public.json',
    'vertical-final-reopened-before.public.json', 'vertical-fit-after-pan.public.json',
    'vertical-saved-final.public.json',
}


def binding(path):
    data = path.read_bytes()
    return {'path': str(path.relative_to(ROOT)), 'bytes': len(data),
            'sha256': hashlib.sha256(data).hexdigest()}


def close(a, b):
    return len(a) == len(b) and all(abs(x-y) < EPSILON for x, y in zip(a, b))


def translation(value):
    match = re.fullmatch(r'translate\(([-\d.eE+]+)[, ]+([-\d.eE+]+)\)', value)
    if not match:
        raise ValueError('Unrecognized node translation: ' + value)
    return tuple(map(float, match.groups()))


def route_points(value):
    # Independent parser for the public absolute M/L/H/V route contract.
    tokens = re.findall(r'[MLHV]|[-+]?(?:\d+\.?\d*|\.\d+)(?:e[-+]?\d+)?', value, re.I)
    result = []
    index = 0
    x = y = 0
    while index < len(tokens):
        op = tokens[index]
        index += 1
        if op in ('M', 'L'):
            x, y = float(tokens[index]), float(tokens[index+1])
            index += 2
        elif op == 'H':
            x = float(tokens[index])
            index += 1
        elif op == 'V':
            y = float(tokens[index])
            index += 1
        else:
            raise ValueError('Unrecognized path command: ' + value)
        result.append((x, y))
    return result


def penetrates(a, b, box):
    x, y, width, height = box
    if a[0] == b[0]:
        return x + EPSILON < a[0] < x + width - EPSILON and max(min(a[1], b[1]), y + EPSILON) < min(max(a[1], b[1]), y + height - EPSILON)
    if a[1] == b[1]:
        return y + EPSILON < a[1] < y + height - EPSILON and max(min(a[0], b[0]), x + EPSILON) < min(max(a[0], b[0]), x + width - EPSILON)
    return False


def strict_crossing(a, b, c, d):
    if a[0] == b[0] and c[1] == d[1] and min(c[0],d[0]) < a[0] < max(c[0],d[0]) and min(a[1],b[1]) < c[1] < max(a[1],b[1]):
        return (a[0], c[1])
    if a[1] == b[1] and c[0] == d[0] and min(a[0],b[0]) < c[0] < max(a[0],b[0]) and min(c[1],d[1]) < a[1] < max(c[1],d[1]):
        return (c[0], a[1])
    return None


def extract(path):
    public = json.loads(path.read_text())
    svg = ET.fromstring(public['svg'])
    nodes, ports, edges, pending = [], [], [], []
    for node in svg.iter():
        if 'data-draft-node' not in node.attrib:
            continue
        node_id = node.attrib['data-draft-node']
        position = translation(node.attrib['transform'])
        card = next(child for child in node if child.tag.endswith('rect'))
        width, height = float(card.attrib['width']), float(card.attrib['height'])
        nodes.append({'id': node_id, 'position': position, 'width': width, 'height': height,
                      'box': (*position, width, height)})
        for group in node.iter():
            if 'data-draft-port' not in group.attrib:
                continue
            dot = next(child for child in group if child.attrib.get('class') == 'draft-port-dot')
            direction = 'out' if 'out' in group.attrib.get('class', '').split() else 'in'
            ports.append({'node': node_id, 'port': group.attrib['data-draft-port'], 'direction': direction,
                          'flow': group.attrib.get('data-draft-port-flow'),
                          'coordinate': (position[0] + float(dot.attrib['cx']), position[1] + float(dot.attrib['cy'])),
                          'pressed': group.attrib.get('aria-pressed')})
    for element in svg.iter():
        if 'data-draft-edge' in element.attrib:
            visible = list(element)[1]
            points = route_points(visible.attrib['d'])
            source = [port for port in ports if port['direction'] == 'out' and close(points[0], port['coordinate'])]
            target = [port for port in ports if port['direction'] == 'in' and close(points[-1], port['coordinate'])]
            segments = list(zip(points, points[1:]))
            crossings = [{'node': node['id'], 'segment': index, 'a': a, 'b': b}
                         for index, (a, b) in enumerate(segments) for node in nodes if penetrates(a, b, node['box'])]
            edges.append({'id': element.attrib['data-draft-edge'], 'path': visible.attrib['d'], 'points': points,
                          'sourceCandidates': source, 'targetCandidates': target,
                          'orthogonal': all(a[0] == b[0] or a[1] == b[1] for a, b in segments),
                          'bodyPenetrations': crossings, 'bends': max(0, len(points)-2)})
        if element.tag.endswith('path') and element.attrib.get('stroke-dasharray') == '6 4':
            pending.append({'path': element.attrib['d'], 'points': route_points(element.attrib['d'])})
    public_centers = []
    for port in public.get('ports', []):
        for name, center in port.get('centers', {}).items():
            hit = center.get('hit')
            coordinate = tuple(center['xy']) if 'xy' in center else (center['x'], center['y'])
            viewport = public['view']
            within = viewport['x'] <= coordinate[0] < viewport['x'] + viewport['width'] and viewport['y'] <= coordinate[1] < viewport['y'] + viewport['height']
            public_centers.append({'node': port['node'], 'port': port['port'], 'part': name,
                                   'center': coordinate, 'withinViewport': within, 'hit': hit,
                                   'matches': bool(port['node'] and hit and hit.get('node') == port['node'] and hit.get('port') == port['port'])})
    active = [port for port in ports if port['pressed'] == 'true']
    crossings = []
    for i, first in enumerate(edges):
        for second in edges[i+1:]:
            if len(first['sourceCandidates']) != 1 or len(second['sourceCandidates']) != 1:
                continue
            first_producer = (first['sourceCandidates'][0]['node'], first['sourceCandidates'][0]['port'])
            second_producer = (second['sourceCandidates'][0]['node'], second['sourceCandidates'][0]['port'])
            if first_producer == second_producer:
                continue
            for a,b in zip(first['points'],first['points'][1:]):
                for c,d in zip(second['points'],second['points'][1:]):
                    point = strict_crossing(a,b,c,d)
                    if point is not None:
                        crossings.append({'firstEdge': first['id'], 'secondEdge': second['id'], 'point': point,
                                          'firstProducer': first_producer, 'secondProducer': second_producer})
    return {'name': path.stem.replace('.public', ''), 'binding': binding(path),
            'capturedAt': public.get('capturedAt'), 'flow': public.get('flow'),
            'camera': public.get('camera'), 'footer': public.get('footer'),
            'nodes': nodes, 'ports': ports, 'edges': edges, 'pending': pending,
            'active': active, 'publicCenterObservations': public_centers,
            'differentProducerStrictCrossings': crossings,
            'knownIncompleteObserver': path.name in KNOWN_INCOMPLETE_OBSERVER_FILES,
            'missingDerivedPortNodeCount': sum(not port.get('node') for port in public['ports']),
            'missingDerivedRoutePathCount': sum(not edge.get('path') for edge in public['edges']),
            'pendingStartMatchesActiveCircle': all(any(close(item['points'][0], port['coordinate']) for port in active) for item in pending),
            'pathEndpointPairCount': len(edges), 'sourceTargetPortPairsExact': all(len(edge['sourceCandidates']) == len(edge['targetCandidates']) == 1 for edge in edges),
            'routesOrthogonal': all(edge['orthogonal'] for edge in edges),
            'publicAndSvgNodeIdentitiesExact': [node['id'] for node in nodes] == [node['id'] for node in public['nodes']],
            'publicAndSvgEdgePathsExact': [{'id': edge['id'], 'path': edge['path']} for edge in edges] == public['edges']}


def camera(value):
    match = re.fullmatch(r'translate\(([-\d.eE+]+)[, ]+([-\d.eE+]+)\) scale\(([-\d.eE+]+)\)', value)
    if not match:
        raise ValueError('Unrecognized camera: ' + value)
    return tuple(map(float, match.groups()))


inputs = sorted(path for path in BROWSER.iterdir() if path.is_file())
inputs += [CONTRACT, PRIOR_MANAGED_PUBLIC, PRIOR_MANAGED_SAVED, Path(__file__)]
FINAL_BROWSER_MANIFEST = ROOT / 'docs/evidence/m4-authoring-interaction-work/browser-final-manifest-attempt-1.json'
if FINAL_BROWSER_MANIFEST.exists():
    inputs.append(FINAL_BROWSER_MANIFEST)
ARTIFACTS = ROOT / 'docs/evidence/m4-authoring-interaction-work/actual-artifacts-attempt-1'
ARTIFACT_MANIFEST = ARTIFACTS / 'manifest.json'
artifact_manifest = json.loads(ARTIFACT_MANIFEST.read_text())
artifact_inputs = {path for path in ARTIFACTS.rglob('*') if path.is_file()}
for copy in artifact_manifest['copies']:
    artifact_inputs.add(ROOT / copy['source']['path'])
for asset in artifact_manifest['assets']:
    artifact_inputs.add(ROOT / asset['disk']['path'])
inputs += sorted(artifact_inputs)
before = [binding(path) for path in inputs]
observations = [extract(path) for path in sorted(BROWSER.glob('*.public.json')) if 'flow' in json.loads(path.read_text())]
by_name = {item['name']: item for item in observations}
contract = json.loads(CONTRACT.read_text())
literal_routes = contract['literalFrozenVerticalChain']['requiredRoutes']
checks = {}
native_specific = {}
browser_manifest = json.loads(FINAL_BROWSER_MANIFEST.read_text())
browser_readback = [{'recorded': item, 'current': binding(ROOT / item['path']),
                     'matches': item == binding(ROOT / item['path'])} for item in browser_manifest['records']]
checks['raw165FilesBoundAndClosed'] = browser_manifest['rawClosed'] and len(browser_readback) == 165 and all(item['matches'] for item in browser_readback)
artifact_readback = []
for copy in artifact_manifest['copies']:
    current_source = binding(ROOT / copy['source']['path'])
    current_copy = binding(ROOT / copy['copy']['path'])
    artifact_readback.append({'recorded': copy, 'source': current_source, 'copy': current_copy,
        'matches': current_source == copy['source'] and current_copy == copy['copy'] and current_source['sha256'] == current_copy['sha256'] and current_source['bytes'] == current_copy['bytes']})
checks['actual11CopiesExactAgainstSourceAndManifest'] = len(artifact_readback) == 11 and all(item['matches'] for item in artifact_readback)
asset_readback = []
for asset in artifact_manifest['assets']:
    received = binding(ROOT / asset['received']['path'])
    disk = binding(ROOT / asset['disk']['path'])
    asset_readback.append({'recorded': asset, 'received': received, 'disk': disk,
        'matches': asset['status'] == 200 and received == asset['received'] and disk == asset['disk'] and received['sha256'] == disk['sha256'] and received['bytes'] == disk['bytes']})
checks['actualHttp2AssetsMatchCurrentBuildBytes'] = len(asset_readback) == 2 and all(item['matches'] for item in asset_readback)
native_specific['frozenRawAndActualArtifacts'] = {'browserManifest': binding(FINAL_BROWSER_MANIFEST),
    'browserReadback': browser_readback, 'artifactManifest': binding(ARTIFACT_MANIFEST),
    'copyReadback': artifact_readback, 'httpAssetReadback': asset_readback,
    'limits': 'Received HTTP bytes confirm server response against built disk assets, not the browser cache. Actions in the root manifest are retrospective declarations rather than synchronous OS telemetry.'}
for name in ['keyboard-third-connected', 'redo-third', 'vertical-save-settled', 'vertical-reopened', 'arrange-undone-vertical', 'vertical-saved-final', 'vertical-final-reopened-after', 'node-left16-supplement-undone', 'vertical-100-canceled-v2']:
    if name in by_name:
        observed = by_name[name]
        checks[name + ':literalThreeStraightRoutes'] = [edge['points'] for edge in observed['edges']] == [list(map(tuple, route)) for route in literal_routes]
complete_observations = [item for item in observations if not item['knownIncompleteObserver']]
incomplete_observations = [item for item in observations if item['knownIncompleteObserver']]
checks['completeRecorderPublicRoutesMatchSvg'] = all(item['publicAndSvgEdgePathsExact'] for item in complete_observations)
checks['unexpectedIncompleteRecorderCountZero'] = all(not item['missingDerivedPortNodeCount'] and not item['missingDerivedRoutePathCount'] for item in complete_observations)
checks['publicNodeIdentitiesMatchSvg'] = all(item['publicAndSvgNodeIdentitiesExact'] for item in observations)
checks['allRouteEndpointPairsExact'] = all(item['sourceTargetPortPairsExact'] for item in observations)
checks['allCommittedRoutesOrthogonal'] = all(item['routesOrthogonal'] for item in observations)
checks['allRecordedCommittedRoutesAvoidCardInteriors'] = all(not edge['bodyPenetrations'] for item in observations for edge in item['edges'])
checks['pendingStartsAtActivePublicCircle'] = all(item['pendingStartMatchesActiveCircle'] for item in observations)
if 'blank-four-before-connections' in by_name:
    blank = by_name['blank-four-before-connections']
    checks['blankFourNodesNoEdgesAllSidePorts'] = len(blank['nodes']) == 4 and not blank['edges'] and all(port['flow'] == 'horizontal' for port in blank['ports'])
if 'label-first-connected' in by_name:
    first = by_name['label-first-connected']
    vertical_ids = {node['id'] for node in first['nodes'][:2]}
    checks['firstConnectionOnlyConnectedPairSwitchesVertical'] = len(first['edges']) == 1 and all(port['flow'] == ('vertical' if port['node'] in vertical_ids else 'horizontal') for port in first['ports'])
if all(name in by_name for name in ['keyboard-third-connected', 'duplicate-rejected', 'undo-third', 'redo-third']):
    full = by_name['keyboard-third-connected']['edges']
    duplicate = by_name['duplicate-rejected']
    undo = by_name['undo-third']['edges']
    redo = by_name['redo-third']['edges']
    checks['duplicateRejectedCommittedEdgesUnchanged'] = duplicate['edges'] == full and '该输入已有连接' in duplicate['footer']
    checks['undoRemovesOnlyThirdConnection'] = len(undo) == 2 and undo == full[:2]
    checks['redoRestoresThirdConnectionExactly'] = redo == full
if 'arrange-horizontal' in by_name:
    horizontal = by_name['arrange-horizontal']
    expected_horizontal = [[(226, 136), (298, 136)], [(474, 136), (546, 136)], [(722, 136), (794, 136)]]
    checks['explicitArrangeHorizontalThreeLiteralStraightRoutes'] = [edge['points'] for edge in horizontal['edges']] == expected_horizontal
    checks['explicitArrangeOnlyExpectedNodePositions'] = [node['position'] for node in horizontal['nodes']] == [(50, 70), (298, 70), (546, 70), (794, 70)]
if all(name in by_name for name in ['pan-start', 'pan-right40', 'pan-left40', 'pan-up40', 'pan-down-retry40']):
    names = ['pan-start', 'pan-right40', 'pan-left40', 'pan-up40', 'pan-down-retry40']
    values = [camera(by_name[name]['camera']) for name in names]
    expected_delta = [(40, 0, 0), (-40, 0, 0), (0, -40, 0), (0, 40, 0)]
    deltas = [tuple(b-a for a, b in zip(values[index], values[index+1])) for index in range(4)]
    checks['fourPanCameraDeltasExact'] = all(close(actual, expected) for actual, expected in zip(deltas, expected_delta))
    checks['fourPanModelGeometryUnchanged'] = all(by_name[name]['edges'] == by_name[names[0]]['edges'] and by_name[name]['nodes'] == by_name[names[0]]['nodes'] for name in names)
    native_specific['fourPan'] = {'observations': names, 'cameras': values, 'deltas': deltas, 'expectedDeltas': expected_delta}
if all(name in by_name for name in ['linear-selected', 'node-right16', 'node-up16', 'node-down16']):
    selected = by_name['linear-selected']
    target = selected['nodes'][1]['id']
    base = selected['nodes'][1]['position']
    moves = []
    for name in ['node-left16', 'node-right16', 'node-up16', 'node-down16']:
        if name in by_name:
            pos = next(node['position'] for node in by_name[name]['nodes'] if node['id'] == target)
            moves.append({'observation': name, 'position': pos, 'deltaFromSelected': tuple(b-a for a,b in zip(base,pos))})
    native_specific['nodeDirectionInitialAttempt'] = {'target': target, 'selectedPosition': base, 'observations': moves,
        'note': 'Filename alone is not a success oracle. Initial right66/224 to left50/224 supports -16 x as an adjacent action, while up50/208 to down50/224 supports +16 y. A supplement from a named base checks left50→34 and its undo separately.'}
    names = ['linear-selected', 'node-right16', 'node-left16', 'node-up16', 'node-down16']
    if all(name in by_name for name in names):
        positions = [next(node['position'] for node in by_name[name]['nodes'] if node['id'] == target) for name in names]
        deltas = [tuple(b-a for a,b in zip(positions[index],positions[index+1])) for index in range(4)]
        checks['adjacentFourKeyboardNodeDirectionsExact'] = deltas == [(16,0),(-16,0),(0,-16),(0,16)]
        native_specific['nodeDirectionInitialAttempt']['adjacentDeltas'] = deltas
        checks['otherNodesUnchangedDuringFourKeyboardMoves'] = all([node for node in by_name[name]['nodes'] if node['id'] != target] == [node for node in selected['nodes'] if node['id'] != target] for name in names)
    if all(name in by_name for name in ['node-left16-supplement-settled', 'node-left16-supplement-undone']):
        moved = by_name['node-left16-supplement-settled']
        undone = by_name['node-left16-supplement-undone']
        moved_position = next(node['position'] for node in moved['nodes'] if node['id'] == target)
        undone_position = next(node['position'] for node in undone['nodes'] if node['id'] == target)
        checks['leftSupplementMoves16AndUndoRestoresPosition'] = moved_position == (34,224) and undone_position == (50,224)
        checks['leftSupplementOtherNodeGeometryUnchanged'] = [node for node in moved['nodes'] if node['id'] != target] == [node for node in undone['nodes'] if node['id'] != target]
        native_specific['leftSupplement'] = {'moved': moved_position, 'undone': undone_position,
            'limits': 'Supplement center recorder has missing hit.node fields; SVG geometry still preserves public endpoint identity and those center records remain mismatches.'}
center_observations = [center for item in observations for center in item['publicCenterObservations']]
valid_visible_centers = [center for item in complete_observations for center in item['publicCenterObservations'] if center['withinViewport']]
checks['completeRecorderVisibleCentersResolveExactEndpointIdentity'] = all(center['matches'] for center in valid_visible_centers)
if 'vertical-100-canceled-v2' in by_name:
    canceled = by_name['vertical-100-canceled-v2']
    checks['escapeCancelsActiveAndPendingWithoutCommittedEdgeLoss'] = not canceled['active'] and not canceled['pending'] and len(canceled['edges']) == 3
    checks['native100PercentCamera'] = camera(canceled['camera']) == (30,30,1)
merge_final_names = [name for name in by_name if name.startswith('merge-') and any(word in name for word in ['complete', 'output-connected', 'saved', 'reopened'])]
merge_names = ['merge-add-left-connected', 'merge-add-right-connected', 'merge-concat-a-connected', 'merge-concat-b-fanout-connected']
if all(name in by_name for name in merge_names):
    initial = by_name[merge_names[0]]
    # Parent's authored intent, recorded before final merge audit: A/B→Add left/right,
    # Add→Concat a, A→Concat b fanout, Concat→Output. Node order is established by the
    # blank/pending snapshot and stable label identity, not chosen to match path output.
    a, b, add, concat, out = [node['id'] for node in initial['nodes']]
    expected = [((a,'output'),(add,'left')), ((b,'output'),(add,'right')),
                ((add,'output'),(concat,'a')), ((a,'output'),(concat,'b')),
                ((concat,'output'),(out,'input'))]
    witness_names = merge_names + merge_final_names
    bindings = []
    for name in witness_names:
        item = by_name[name]
        observed = [((edge['sourceCandidates'][0]['node'],edge['sourceCandidates'][0]['port']),
                     (edge['targetCandidates'][0]['node'],edge['targetCandidates'][0]['port']))
                    for edge in item['edges'] if len(edge['sourceCandidates']) == len(edge['targetCandidates']) == 1]
        bindings.append({'name': name, 'observedBindings': observed,
                         'matchesExpectedPrefix': observed == expected[:len(observed)]})
    checks['mergeNativeNamedPortBindingsMatchAuthoredIntent'] = all(item['matchesExpectedPrefix'] for item in bindings)
    checks['mergeNativeAllNodePositionsFixed'] = all(by_name[name]['nodes'] == initial['nodes'] for name in witness_names)
    native_specific['mergeNamedPorts'] = {'nodeIdentities': {'inputA': a, 'inputB': b, 'Add': add, 'Concat': concat, 'Output': out},
        'expectedBindings': expected, 'observed': bindings,
        'limits': 'This native arrangement is horizontal. Top-edge ordered Add/Concat merge projections are covered by the independent pure fixtures, not a native vertical-merge claim.'}
managed_path = BROWSER / 'managed-reopened.public.json'
if managed_path.exists():
    current_managed = json.loads(managed_path.read_text())
    prior_managed = json.loads(PRIOR_MANAGED_PUBLIC.read_text())
    saved_managed = json.loads(PRIOR_MANAGED_SAVED.read_text())['document']
    svg = ET.fromstring(current_managed['svg'])
    output_id = 'output:model.AuthoredModel:0'
    output_group = next(element for element in svg.iter() if element.attrib.get('data-node-id') == output_id and element.attrib.get('role') == 'button')
    texts = [''.join(element.itertext()) for element in output_group.iter() if element.tag.endswith('text')]
    expected_output = next(node for node in saved_managed['architecture']['nodes'] if node['id'] == output_id)
    fact = next(item for item in current_managed['metadata']['sourceFacts'] if item['id'] == output_id)
    checks['managedCanonicalMetadataExactAgainstPriorNative'] = current_managed['metadata'] == prior_managed['metadata']
    checks['managedAliasedCaptionReadable'] = texts == [saved_managed['displayAliases'][output_id], 'model output']
    checks['managedOutputPathAndSourceEvidenceExact'] = fact['outputPath'] == expected_output['outputPath'] and fact['source'] == expected_output['source'] and fact['sourceLabel'] == expected_output['label']
    native_specific['managedOutputCaption'] = {'currentNative': binding(managed_path), 'priorNative': binding(PRIOR_MANAGED_PUBLIC),
        'savedCanvas': binding(PRIOR_MANAGED_SAVED), 'renderedTexts': texts, 'outputSourceFact': fact,
        'unchangedCanonicalMetadata': current_managed['metadata'] == prior_managed['metadata'],
        'limits': 'This checks the existing aliased authored Output. Unaliased user return keys are covered by the separate independent caption test receipt.'}
saved_vertical = json.loads((ARTIFACTS / 'vertical-draft-envelope.json').read_text())['draft']
saved_merge = json.loads((ARTIFACTS / 'merge-draft-envelope.json').read_text())['draft']
def native_matches_saved(item, draft):
    expected_nodes = [(node['id'], (node['position']['x'], node['position']['y'])) for node in draft['nodes']]
    observed_nodes = [(node['id'], node['position']) for node in item['nodes']]
    expected_edges = [(edge['id'],(edge['source']['nodeId'],edge['source']['portId']),(edge['target']['nodeId'],edge['target']['portId'])) for edge in draft['edges']]
    observed_edges = [(edge['id'],(edge['sourceCandidates'][0]['node'],edge['sourceCandidates'][0]['port']),(edge['targetCandidates'][0]['node'],edge['targetCandidates'][0]['port'])) for edge in item['edges'] if len(edge['sourceCandidates']) == len(edge['targetCandidates']) == 1]
    return expected_nodes == observed_nodes and expected_edges == observed_edges
checks['actualVerticalSavedFourNodeFactsMatchFrozenIntendedChain'] = [(node['kind'],node['parameters'],node['position']) for node in saved_vertical['nodes']] == [
    ('Input',{'shape':[1,16],'dtype':'float32'},{'x':50,'y':70}),
    ('Linear',{'in_features':16,'out_features':8,'bias':True},{'x':50,'y':224}),
    ('GELU',{'approximate':'none'},{'x':50,'y':378}), ('Output',{}, {'x':50,'y':532})]
checks['actualVerticalSavedMatchesNativeReopenedIdsAndBindings'] = native_matches_saved(by_name['vertical-reopened'], saved_vertical)
checks['actualMergeSavedMatchesNativeCompleteIdsAndBindings'] = all(native_matches_saved(by_name[name],saved_merge) for name in merge_final_names)
model_path = ARTIFACTS / 'vertical-model.py'
model_ast = ast.parse(model_path.read_text())
klass = next(node for node in model_ast.body if isinstance(node,ast.ClassDef))
initialization = next(node for node in klass.body if isinstance(node,ast.FunctionDef) and node.name == '__init__')
forward = next(node for node in klass.body if isinstance(node,ast.FunctionDef) and node.name == 'forward')
module_assignments = [node for node in initialization.body if isinstance(node,ast.Assign)]
def constructor(node):
    call = node.value
    kwargs = {keyword.arg: ast.literal_eval(keyword.value) if isinstance(keyword.value,(ast.Constant,ast.List,ast.Tuple)) else ast.unparse(keyword.value) for keyword in call.keywords}
    return ast.unparse(call.func), kwargs
constructors = [constructor(node) for node in module_assignments]
checks['actualGeneratedSourceHasLiteralLinearAndGeluDeclarations'] = constructors == [('nn.Linear',{'in_features':16,'out_features':8,'bias':True,'dtype':'torch.float32'}),('nn.GELU',{'approximate':'none'})]
linear_name = module_assignments[0].targets[0].attr
gelu_name = module_assignments[1].targets[0].attr
input_name = forward.args.args[1].arg
call1,call2,returned = forward.body
checks['actualGeneratedSourceForwardPreservesIntendedSingleChain'] = isinstance(call1,ast.Assign) and isinstance(call2,ast.Assign) and isinstance(returned,ast.Return) and ast.unparse(call1.value) == 'self.'+linear_name+'('+input_name+')' and ast.unparse(call2.value) == 'self.'+gelu_name+'('+linear_name+')' and isinstance(returned.value,ast.Dict) and len(returned.value.values) == 1 and ast.unparse(returned.value.values[0]) == gelu_name
native_specific['actualSavedDraftsAndStaticSource'] = {'verticalSaved': binding(ARTIFACTS / 'vertical-draft-envelope.json'),
    'mergeSaved': binding(ARTIFACTS / 'merge-draft-envelope.json'), 'modelSource': binding(model_path),
    'constructors': constructors, 'sourceInspectedWithAstOnly': True, 'modelExecuted': False}
after = [binding(path) for path in inputs]
checks['inputsUnchangedDuringAudit'] = before == after
crossing_observations = [{'name': item['name'], **crossing} for item in observations for crossing in item['differentProducerStrictCrossings']]
report = {'protocol': 'archcanvas-authored-flow-independent-native-audit/1',
          'reviewedAt': datetime.now(timezone.utc).isoformat(), 'checks': checks, 'pass': all(checks.values()),
          'inputsBefore': before, 'inputsAfter': after, 'observations': observations,
          'knownObserverFailureObservations': [{'name': item['name'], 'binding': item['binding'],
             'missingDerivedPortNodeCount': item['missingDerivedPortNodeCount'], 'missingDerivedRoutePathCount': item['missingDerivedRoutePathCount'],
             'publicAndSvgEdgePathsExact': item['publicAndSvgEdgePathsExact'],
             'hitIdentitySuccessCount': sum(center['matches'] for center in item['publicCenterObservations']),
             'intactSvgEndpointPairsExact': item['sourceTargetPortPairsExact']} for item in incomplete_observations],
          'specificChecks': native_specific,
          'aestheticFindings': {'differentProducerStrictCrossingObservations': crossing_observations,
              'strictCrossingFree': not crossing_observations,
              'scope': 'Scoped endpoint/history/projection checks may pass while this separate aesthetic requirement remains incomplete. Distinct producer crossing at (614,220) in the hand-built Add/Concat network remains a current uncorrected problem.'},
          'counts': {'authoringSnapshots': len(observations), 'endpointPairs': sum(item['pathEndpointPairCount'] for item in observations),
                     'publicCenterObservations': len(center_observations), 'publicCenterIdentityMatches': sum(item['matches'] for item in center_observations),
                     'completeVisiblePublicCenters': len(valid_visible_centers), 'completeVisibleIdentityMatches': sum(item['matches'] for item in valid_visible_centers),
                     'knownObserverFailureSnapshots': len(incomplete_observations),
                     'cardInteriorPenetrations': sum(len(edge['bodyPenetrations']) for item in observations for edge in item['edges']),
                     'differentProducerStrictCrossingObservations': len(crossing_observations)},
          'limits': ['Snapshot geometry and elementFromPoint records alone do not establish every UI event. Action provenance needs the parent native receipt.',
                     'Eleven explicitly identified capture-closure failures preserve intact SVG but null derived endpoint/path fields. They are listed as observer failures and contribute zero successful hit identities.',
                     'Center identity observations include covered/offscreen positions; every mismatch is retained and not silently converted to successful clicks.',
                     'Initial direction deltas are evaluated relative to adjacent predecessor snapshots; the left supplement separately records a base50→34 move and undo50.',
                     'Long arbitrary labels, dense arbitrary graphs, native cancellation under every busy/pan state, physical publication sizes/fonts and true human usability are not certified.'],
          'productEditedByAuditor': False, 'browserDrivenByAuditor': False, 'testsOrBuildRun': False,
          'modelsExecuted': False, 'humanParticipants': 0, 'M4': 'partial', 'M5': 'not-started'}
target = OUT / 'report.json'
with target.open('x') as stream:
    json.dump(report, stream, ensure_ascii=False, indent=2)
    stream.write('\n')
print(json.dumps({'report': binding(target), 'checks': checks, 'counts': report['counts']}, ensure_ascii=False))
