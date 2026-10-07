"""Independent final native artifact readback. No product code is imported.

Expected geometry comes from the pre-change literal contract and frozen
formal L0/L2 DOM/Scene/document, not a current buildScene invocation.
"""
import copy
import datetime
import hashlib
import json
import pathlib
import re
import sys
import traceback
import xml.etree.ElementTree as ET

ROOT = pathlib.Path(__file__).resolve().parents[5]
WORK = ROOT / 'docs/evidence/m4-collapse-continuity-work'
OUT = pathlib.Path(__file__).resolve().parent
BROWSER = WORK / 'browser-current-attempt-2'
CORE = WORK / 'core-current-attempt-2'
BASE = ROOT / 'docs/evidence/m4-monochrome-role-work/acceptance/baseline/cnn12'
POOL = 'call:instance:model.ResidualCNN.pool'
REPEAT = 'repeat:instance:model.ResidualCNN.blocks'
NS = '{http://www.w3.org/2000/svg}'
bindings = {}
results = {}


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def read(path):
    path = pathlib.Path(path)
    if not path.is_absolute():
        path = ROOT / path
    path = path.resolve()
    raw = path.read_bytes()
    key = str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path)
    binding = {'path': key, 'bytes': len(raw), 'sha256': digest(raw)}
    if key in bindings:
        assert bindings[key] == binding, f'Input changed during readback: {key}'
    bindings[key] = binding
    return raw


def load(path):
    return json.loads(read(path))


def verify_binding(binding):
    raw = read(binding['path'])
    assert len(raw) == binding['bytes']
    assert digest(raw) == binding['sha256'], binding['path']


def tree(value, remove_revision=False, normalize_mm=None):
    root = ET.fromstring(value) if isinstance(value, (str, bytes)) else copy.deepcopy(value)
    if remove_revision:
        root.attrib.pop('data-revision', None)
        meta = root.find(NS + 'metadata')
        facts = json.loads(meta.text)
        facts.pop('revision', None)
        meta.text = json.dumps(facts)
    if normalize_mm:
        root.set('width', normalize_mm.get('width'))
        root.set('height', normalize_mm.get('height'))

    def canonical(node):
        text = node.text or ''
        if node.tag == NS + 'metadata':
            text = json.loads(text)
        elif not text.strip():
            text = ''
        return [node.tag, dict(sorted(node.attrib.items())), text, [canonical(c) for c in node]]
    return canonical(root)


def metadata(svg):
    return json.loads(ET.fromstring(svg).find(NS + 'metadata').text)


def dimensions(svg, expected_bounds=None):
    r = ET.fromstring(svg)
    vb = [float(v) for v in r.get('viewBox').split()]
    if expected_bounds is not None:
        assert vb == [expected_bounds[k] for k in ['x', 'y', 'width', 'height']]
    m = metadata(svg)
    height = m['widthMm'] * vb[3] / vb[2]
    assert abs(float(r.get('width').removesuffix('mm')) - m['widthMm']) <= .011
    assert abs(float(r.get('height').removesuffix('mm')) - height) <= .011
    assert abs(m['heightMm'] - height) <= 1e-10
    return {'widthMm': m['widthMm'], 'heightMm': height, 'viewBox': vb}


def matrix(text):
    assert re.fullmatch(r'matrix\([-\d.eE+, ]+\)', text)
    values = [float(v) for v in text[7:-1].split(',')]
    assert values[0] == values[3] and values[1] == values[2] == 0
    return values


def node_groups(svg):
    return {e.get('data-canonical-id'): e for e in ET.fromstring(svg).iter()
            if e.get('data-canonical-id') is not None}


def port_groups(svg):
    return {e.get('data-port-id'): e for e in ET.fromstring(svg).iter()
            if e.get('data-port-id') is not None}


def edge_groups(svg):
    return {e.get('data-edge-id'): e for e in ET.fromstring(svg).iter()
            if e.get('data-edge-id') is not None}


def geometry(svg, scene):
    groups = node_groups(svg)
    answer = {}
    assert set(groups) == {n['id'] for n in scene['nodes']}
    for n in scene['nodes']:
        # Repeat's main body follows the two translucent stacked outline rects.
        rects = [c for c in groups[n['id']] if c.tag == NS + 'rect']
        main = next(c for c in rects if float(c.get('x')) == n['x'] and
                    float(c.get('y')) == n['y'])
        answer[n['id']] = {k: float(main.get(k)) for k in ['x', 'y', 'width', 'height']}
        assert answer[n['id']] == {k: n[k] for k in answer[n['id']]}
    return answer


def path_points(text):
    tokens = re.findall(r'[A-Za-z]|[-+]?(?:\d*\.\d+|\d+)(?:[eE][-+]?\d+)?', text)
    assert ''.join(tokens) == re.sub(r'[\s,]', '', text), text
    points = []
    i = 0
    x = y = None
    while i < len(tokens):
        command = tokens[i]
        i += 1
        if command in ['M', 'L']:
            x, y = float(tokens[i]), float(tokens[i + 1])
            i += 2
        elif command == 'H':
            x = float(tokens[i]); i += 1
        elif command == 'V':
            y = float(tokens[i]); i += 1
        else:
            raise AssertionError(f'Unsupported actual path command {command}')
        points.append([x, y])
    return points


def endpoints(svg, scene, delta=(0, 0)):
    groups = edge_groups(svg)
    ports = port_groups(svg)
    assert set(groups) == {e['id'] for e in scene['edges']}
    count = 0
    for edge in scene['edges']:
        g = groups[edge['id']]
        assert g.get('data-tensor-id') == edge['tensorId']
        paths = [c for c in g if c.tag == NS + 'path']
        assert len(paths) == 1
        points = path_points(paths[0].get('d'))
        expected = []
        for which, direction in [('source', 'out'), ('target', 'in')]:
            node = next(n for n in scene['nodes'] if n['id'] == edge[which + 'Id'])
            port = next(p for p in node['ports'] if p['direction'] == direction and
                        edge['id'] in p['canonicalEdgeIds'])
            circles = [c for c in ports[port['id']] if c.tag == NS + 'circle']
            assert len(circles) == 2 and [float(c.get('r')) for c in circles] == [8, 2.6]
            dx, dy = delta if node['id'] == POOL else (0, 0)
            frozen_endpoint = path_points(edge['path'])[0 if which == 'source' else -1]
            assert all(abs(frozen_endpoint[i] - port[k]) <= .0500000001 for i, k in enumerate(['x', 'y']))
            expected.append([frozen_endpoint[0] + dx, frozen_endpoint[1] + dy])
            expected_circle = [round(port['x'] + dx, 2), round(port['y'] + dy, 2)]
            for circle in circles:
                assert [float(circle.get('cx')), float(circle.get('cy'))] == expected_circle
        assert points[0] == expected[0] and points[-1] == expected[1], edge['id']
        count += 1
    return count


def translate_back(group, delta):
    dx, dy = delta

    def visit(node):
        for k in ['x', 'cx']:
            if k in node.attrib:
                node.set(k, format(float(node.get(k)) - dx, 'g'))
        for k in ['y', 'cy']:
            if k in node.attrib:
                node.set(k, format(float(node.get(k)) - dy, 'g'))
        transform = node.get('transform')
        if transform:
            match = re.fullmatch(r'translate\(([-\d.]+) ([-\d.]+)\)', transform)
            assert match, transform
            node.set('transform', f'translate({float(match[1]) - dx:g} {float(match[2]) - dy:g})')
            # Glyph descendants are local to this translated group.
            return
        for child in node:
            visit(child)
    visit(group)


def normalize_ancestor(root, frozen_svg, scene, delta):
    root_id = 'call:instance:model.ResidualCNN'
    nodes = scene['nodes']
    frozen_root = node_groups(frozen_svg)[root_id]
    old = next(n for n in nodes if n['id'] == root_id)
    right = max(n['x'] + (delta[0] if n['id'] == POOL else 0) + n['width']
                for n in nodes if n['id'] != root_id)
    expected_width = right + 30 - old['x']
    width_delta = expected_width - old['width']
    assert width_delta == max(0, delta[0])
    expected = copy.deepcopy(frozen_root)
    body = next(c for c in expected if c.tag == NS + 'rect')
    body.set('width', format(expected_width, 'g'))
    divider = next(c for c in expected if c.tag == NS + 'path')
    assert divider.get('d') == 'M 51 134 H 303'
    divider.set('d', f'M 51 134 H {303 + width_delta:g}')
    control = next(c for c in expected if c.get('data-expand-id') == root_id)
    rect = control.find(NS + 'rect')
    rect.set('x', format(275 + width_delta, 'g'))
    path = control.find(NS + 'path')
    assert path.get('d') == 'M 280 112 h 8'
    path.set('d', f'M {280 + width_delta:g} 112 h 8')
    actual = next(e for e in root.iter() if e.get('data-canonical-id') == root_id)
    assert tree(actual) == tree(expected), 'ancestor containment/header/control differs from child-bounds formula'
    parent = next(p for p in root.iter() if actual in list(p))
    index = list(parent).index(actual)
    parent.remove(actual)
    parent.insert(index, copy.deepcopy(frozen_root))
    return {'nodeId': root_id, 'anchor': [old['x'], old['y']], 'oldWidth': old['width'],
            'actualExpectedWidth': expected_width, 'formula': 'max visible child right + 30 padding - root x'}


def audit():
    read(__file__)
    contract = load(WORK / 'acceptance/browser-contract-attempt-1.json')
    for directory in [BROWSER, CORE]:
        for p in sorted(directory.rglob('*')):
            if p.is_file(): read(p)
    olddeep = load(WORK / 'acceptance/before/actual-cnn-deep-rev12.json')
    oldbad = load(WORK / 'acceptance/before/actual-cnn-collapsed-rev14.json')
    base_scene = load(BASE / 'cnn-level0-paper-180/core-after-union/scene.json')
    deep_scene = load(BASE / 'cnn-level2-paper-180/core-after-union/scene.json')
    base_svg = read(BASE / 'cnn-level0-paper-180/core-after-union/interactive.svg')
    deep_svg = read(BASE / 'cnn-level2-paper-180/core-after-union/interactive.svg')
    base_publication = read(BASE / 'cnn-level0-paper-180/core-after-union/publication.svg')
    basemeta, deepmeta = metadata(base_svg), metadata(deep_svg)
    core_receipt = load(CORE / 'receipt.json')
    assert core_receipt['protocol'] == 'archcanvas-monochrome-current-observation/1'
    assert core_receipt['inputsBefore'] == core_receipt['inputsAfter']
    assert core_receipt['inputSetAndBytesUnchanged'] is True
    assert core_receipt['modelsExecuted'] is False
    assert core_receipt['dependenciesInstalled'] is False
    for binding in core_receipt['inputsBefore']:
        verify_binding(binding)
    for record in core_receipt['records']:
        verify_binding(record['input'])
        for binding in record['files']: verify_binding(binding)
    assert len(core_receipt['records']) == 1
    assert core_receipt['records'][0]['caseId'] == 'cnn-compact-paper180'
    for binding in core_receipt['currentRendererBuildBindings']: verify_binding(binding)
    results['currentCoreReceipt'] = {'path': str((CORE / 'receipt.json').relative_to(ROOT)),
        'sha256': digest(read(CORE / 'receipt.json')), 'bindingsVerified': True,
        'expectedFromCurrentCore': False}

    declarations = {
        'reopened-compact-rev22': (22, (0, 0), False),
        'expanded-deep-rev23': (23, (0, 0), True),
        'compact-rev24-before': (24, (0, 0), False),
        'compact-rev24-after': (24, (0, 0), False),
        'movement-start-rev24': (24, (0, 0), False),
        'move-right-rev25-before': (25, (40, 0), False),
        'move-right-rev25-after': (25, (40, 0), False),
        'move-left-rev26-before': (26, (0, 0), False),
        'move-left-rev26-after': (26, (0, 0), False),
        'move-up-rev27-before': (27, (0, -40), False),
        'move-up-rev27-after': (27, (0, -40), False),
        'move-down-rev28-before': (28, (0, 0), False),
        'move-down-rev28-after': (28, (0, 0), False),
        'undo-up-rev29': (29, (0, -40), False),
        'redo-down-rev30': (30, (0, 0), False),
        'native-reopened-rev30': (30, (0, 0), False),
        'final-fit-rev30-before': (30, (0, 0), False),
        'final-fit-rev30-after': (30, (0, 0), False),
    }
    observations, path_changes = {}, []
    for name, (revision, delta, expanded) in declarations.items():
        obs = load(BROWSER / (name + '.json'))
        observations[name] = obs
        scene, frozen_svg = (deep_scene, deep_svg) if expanded else (base_scene, base_svg)
        frozen_meta = deepmeta if expanded else basemeta
        ds = obs['dataset']
        assert ds['committedRevision'] == str(revision) and ds['sceneKind'] == 'committed'
        expected_expanded = contract['rawExpandedMemory'] + ([REPEAT] if expanded else [])
        assert json.loads(ds['expandedIds']) == expected_expanded
        assert json.loads(ds['pinnedIds']) == []
        assert obs['scripts'] == ['http://127.0.0.1:40875/assets/index-BKbgeBjI.js']
        assert obs['styles'] == ['http://127.0.0.1:40875/assets/index-B6WbMowt.css']
        assert obs['url'].startswith('http://127.0.0.1:40875/')
        current_meta = metadata(obs['svg'])
        assert obs['metadata'] == current_meta
        expected_meta = copy.deepcopy(frozen_meta)
        expected_meta['revision'] = revision
        assert current_meta == expected_meta, name
        assert ds['committedRevision'] == str(ET.fromstring(obs['svg']).get('data-revision'))
        dimensions(obs['svg'], scene['bounds'])
        matrix(obs['camera'])
        if delta == (0, 0):
            assert tree(obs['svg'], True) == tree(frozen_svg, True), name
            geometry(obs['svg'], scene)
        else:
            normalized = ET.fromstring(obs['svg'])
            frozen_edges = edge_groups(base_svg)
            changes = []
            ancestor = normalize_ancestor(normalized, base_svg, base_scene, delta)
            for group in normalized.iter():
                if group.get('data-canonical-id') == POOL or (
                    group.get('data-port-id') is not None and group.get('data-node-id') == POOL):
                    translate_back(group, delta)
                edge_id = group.get('data-edge-id')
                if edge_id:
                    a = next(c for c in group if c.tag == NS + 'path')
                    b = next(c for c in frozen_edges[edge_id] if c.tag == NS + 'path')
                    if a.get('d') != b.get('d'):
                        assert edge_id in ['edge:20', 'edge:21'], f'unrelated edge changed: {edge_id}'
                        changes.append({'edgeId': edge_id, 'frozenPath': b.get('d'), 'actualPath': a.get('d'),
                                        'points': path_points(a.get('d'))})
                    a.set('d', b.get('d'))
            assert tree(normalized, True) == tree(base_svg, True), name
            path_changes.append({'observation': name, 'changedIncidentPaths': changes, 'ancestorContainment': ancestor})
            pg = node_groups(obs['svg'])[POOL]
            main = next(c for c in pg if c.tag == NS + 'rect')
            assert [float(main.get('x')), float(main.get('y'))] == [80 + delta[0], 454 + delta[1]]
        endpoints(obs['svg'], scene, delta)
    results['nativeObservations'] = {'count': len(declarations), 'allSourceFactsAndBindingsExact': True,
        'fullUnaffectedXmlExact': True, 'ancestorWidthFromFrozenChildrenPlusDeclaredMove': True, 'currentSameModeChecks': True,
        'endpointSerialization': 'Actual path endpoints must equal immutable frozen path endpoints plus the declared pool delta exactly; frozen path endpoints must be within 0.0500000001 world units of their frozen exact ports (mixed one/two decimal path serializers). Actual port circles equal round2 frozen ports plus declared delta. Full unaffected XML remains exact.',
        'endpointCount': sum(len(deep_scene['edges']) if expanded else len(base_scene['edges'])
                             for _, _, expanded in declarations.values()), 'changedIncidentPaths': path_changes}

    brackets = []
    for name in ['compact-rev24', 'move-right-rev25', 'move-left-rev26', 'move-up-rev27',
                 'move-down-rev28', 'final-fit-rev30']:
        before, after = observations[name + '-before'], observations[name + '-after']
        assert set(before) == set(after)
        for key in before:
            if key != 'capturedAt': assert before[key] == after[key], (name, key)
        assert datetime.datetime.fromisoformat(before['capturedAt'].replace('Z', '+00:00')) <= \
               datetime.datetime.fromisoformat(after['capturedAt'].replace('Z', '+00:00'))
        image = read(BROWSER / (name + '.jpg'))
        assert image[:2] == b'\xff\xd8' and image[-2:] == b'\xff\xd9'
        brackets.append({'name': name, 'exactStateBeforeAfter': True, 'sha256': digest(image),
                         'pixelsReviewedByThisScript': False})
    results['screenshotBrackets'] = brackets

    assert observations['expanded-deep-rev23']['camera'] == observations['compact-rev24-after']['camera']
    # Same repeat body x/y at the exact camera implies collapse screen anchor continuity.
    repeat_before = next(n for n in deep_scene['nodes'] if n['id'] == REPEAT)
    assert [repeat_before['x'], repeat_before['y']] == [80, 354]
    for name in ['movement-start-rev24', 'move-right-rev25-after', 'move-left-rev26-after',
                 'move-up-rev27-after', 'move-down-rev28-after', 'undo-up-rev29', 'redo-down-rev30']:
        assert matrix(observations[name]['camera']) == [1, 0, 0, 1, 255.589, -164]
    results['gestures'] = {
        'collectorDeclaration': 'Native pool screen (670,435)->(710,435), reverse; (670,435)->(670,395), reverse; undo and redo. Zoom 1, screen delta equals world delta.',
        'revisions': [24, 25, 26, 27, 28, 29, 30],
        'worldPoolPositions': [[80,454], [120,454], [80,454], [80,414], [80,454], [80,414], [80,454]],
        'cameraStableDuringMoves': True, 'collapseCameraAndRepeatAnchorExact': True,
        'expandScreenAnchorCertified': False,
        'expandAnchorLimit': 'No matching immediately-before-expand camera checkpoint; initial reopen and expanded checkpoint include a camera change.'}
    assert contract['compactOutlineGap'] == 31
    assert contract['compactPoolTop'] - contract['compactRepeatOutlineBottom'] == 31
    results['compactGeometry'] = {'allEightWorldPositions': contract['compactWorld'],
        'repeatFullOutlineBottom': 423, 'poolTop': 454, 'gap': 31,
        'historicalBadPoolTop': 2030, 'historicalGap': 1607, 'poolDelta': -1576,
        'upMovePoolTop': 414, 'upMoveOutlineGap': -9,
        'upMoveOverlapAndRouteBlock': 'Actual deliberately chosen position; collector observed warning, pixels reviewed separately. Do not certify aesthetics.'}

    case = BROWSER / 'cnn-compact-paper180'
    document, envelope = load(case / 'document.json'), load(case / 'saved-envelope.json')
    assert envelope == load(BROWSER / 'native-saved-rev30-envelope.json')
    assert document == envelope['document'] and document['revision'] == 30
    assert envelope['revision'] == 10  # Service storage generation, distinct from Canvas revision.
    expected_doc = copy.deepcopy(oldbad)
    expected_doc['revision'] = 30
    expected_doc['layout'].update(contract['compactLocal'])
    compact_key = 'visible-frontier/1:' + json.dumps(['call:instance:model.ResidualCNN'], separators=(',', ':'))
    deep_ids = sorted(olddeep['expandedIds'])
    deep_key = 'visible-frontier/1:' + json.dumps(deep_ids, separators=(',', ':'))
    expected_doc['layoutByFrontier'][compact_key] = copy.deepcopy(contract['compactLocal'])
    expected_doc['layoutByFrontier'][deep_key] = copy.deepcopy(olddeep['layout'])
    assert document == expected_doc, 'complete final Canvas differs from declared literal/frozen contract'
    assert document['architecture'] == olddeep['architecture']
    hidden = set(olddeep['layout']) - set(contract['compactLocal'])
    assert {k: document['layout'][k] for k in hidden} == {k: olddeep['layout'][k] for k in hidden}
    for key, value in oldbad['layoutByFrontier'].items(): assert document['layoutByFrontier'][key] == value
    results['completeSavedCanvas'] = {'exact': True, 'expectedSource': 'Frozen actual badrev14 plus compact literal local positions, revision30 and declared effective-frontier JSON cache entries. Deep JSON entry equals frozen full rev12 layout.',
        'canvasRevision': 30, 'storageRevision': 10, 'legacyEntriesPreserved': len(oldbad['layoutByFrontier']),
        'hiddenLocalPositionsPreserved': len(hidden), 'rawExpansionMemoryPreserved': True}

    scene, export_scene = load(CORE / 'cnn-compact-paper180/scene.json'), load(CORE / 'cnn-compact-paper180/export.scene.json')
    expected_scene = copy.deepcopy(base_scene)
    expected_scene['revision'] = 30
    assert scene == expected_scene, 'complete Scene against frozen L0'
    assert export_scene == scene
    actual_canonical = [i for e in scene['edges'] for i in e['canonicalEdgeIds']] + scene['hiddenEdges']
    assert len(actual_canonical) == len(set(actual_canonical))
    assert sorted(actual_canonical) == sorted(e['id'] for e in document['architecture']['edges'])
    pub, interactive = read(CORE / 'cnn-compact-paper180/publication.svg'), read(CORE / 'cnn-compact-paper180/interactive.svg')
    assert tree(interactive, True) == tree(base_svg, True)
    assert tree(pub, True) == tree(base_publication, True)
    for name in ['native-reopened-rev30', 'final-fit-rev30-before', 'final-fit-rev30-after']:
        assert tree(observations[name]['svg']) == tree(interactive)

    binding = load(case / 'export-binding.json')
    links = binding['links']
    uuid = '1367fc7fa1034519b3de845b083c566a'
    assert len(links) == 3
    assert sum(l['href'] == f'/api/exports/{uuid}/figure.svg' for l in links) == 2
    assert sum(l['href'] == f'/api/exports/{uuid}/receipt' for l in links) == 1
    copies = load(case / 'artifact-copy-receipt.json')
    assert copies['actualUiBinding'] == binding and copies['modelsExecuted'] is False
    assert sorted(pathlib.Path(r['copy']).name for r in copies['records']) == \
        ['document.json', 'figure.svg', 'figure.svg.receipt.json', 'saved-envelope.json']
    for row in copies['records']:
        source, copied = read(row['source']), read(row['copy'])
        assert source == copied and len(copied) == row['bytes'] and digest(copied) == row['sha256']
        if '/exports/' in row['source']:
            assert pathlib.Path(row['source']).parent.name == uuid
    actual, receipt = read(case / 'figure.svg'), load(case / 'figure.svg.receipt.json')
    for key in ['svgDigest', 'outputDigest']: assert receipt[key] == digest(actual)
    for key in ['inputSvgDigest', 'sceneSvgDigest']: assert receipt[key] == digest(pub)
    assert receipt['bytes'] == len(actual) and receipt['format'] == 'svg'
    assert receipt['geometryVerified'] is True and receipt['documentId'] == document['id']
    assert receipt['revision'] == 30
    assert receipt['sourceDigest'] == document['architecture']['sourceDigest']
    assert receipt['irDigest'] == document['architecture']['irDigest']
    assert receipt['publicationOrigin'] == str(ROOT / 'src/archcanvas_publication/exporter.py')
    read(receipt['publicationOrigin'])
    assert read(receipt['path']) == actual
    size = dimensions(actual, scene['bounds'])
    assert receipt['viewBox'] == size['viewBox'] and receipt['widthMm'] == size['widthMm']
    assert abs(receipt['heightMm'] - size['heightMm']) <= 1e-10
    assert tree(actual, normalize_mm=ET.fromstring(pub).attrib) == tree(pub)
    results['actualExport'] = {'uuid': uuid, 'completeSameModeXmlExact': True,
        'rootMmSerializationOnlyException': 'Actual exporter 5 decimal mm versus core 2 decimal mm; both independently satisfy the physical formula.',
        'dimensions': size, 'sourceAndCopyBytesExact': True,
        'fonts': receipt['fonts'], 'physicalPublicationCertified': False}


error = None
try:
    audit()
except Exception as exc:
    error = {'name': type(exc).__name__, 'message': str(exc), 'traceback': traceback.format_exc()}
before = sorted(bindings.values(), key=lambda b: b['path'])
after = []
for b in before:
    p = pathlib.Path(b['path'])
    if not p.is_absolute(): p = ROOT / p
    raw = p.read_bytes()
    after.append({'path': b['path'], 'bytes': len(raw), 'sha256': digest(raw)})
exact = before == after
report = {'protocol': 'archcanvas-collapse-independent-final-native-readback/1',
    'finishedAt': datetime.datetime.now(datetime.timezone.utc).isoformat(),
    'status': 'bounded-pass' if error is None and exact else 'failed',
    'results': results, 'error': error, 'inputsBefore': before, 'inputsAfter': after,
    'auditInputBytesUnchanged': exact, 'expectedFromCurrentProduct': False,
    'modelsExecuted': False, 'dependenciesInstalled': False, 'humans': 0,
    'M4': 'partial', 'M5': 'not started',
    'limits': ['Collector-declared native chain, checkpoint-bound rather than OS-synchronized trace.',
        'One CNN compact/deep frontier; no arbitrary model/malformed JSON/multiple-root/root-collapse certification.',
        'No nonempty pins/held-pointer cancellation/numerical model execution/performance/font or human approval.',
        'No script pixel judgment; deliberate upward overlap and route detour remain observations.',
        'Full XML is compared within the same render mode; publication controls/count-label positions may differ from interactive mode.']}
with (OUT / 'report.json').open('x') as f:
    json.dump(report, f, ensure_ascii=False, indent=2)
    f.write('\n')
print(json.dumps({'status': report['status'], 'results': list(results), 'bindings': len(before),
                  'inputBytesUnchanged': exact, 'error': error}, ensure_ascii=False))
if report['status'] != 'bounded-pass': sys.exit(1)
