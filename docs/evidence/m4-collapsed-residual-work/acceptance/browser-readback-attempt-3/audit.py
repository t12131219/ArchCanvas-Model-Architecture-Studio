"""Independent 12-case data readback. Run only after root's completion signal.

Does not import or execute product/core/model code. Current core outputs are
observations supplied separately by root, never the source of expected geometry.
Every report is create-only; failed attempts retain all inputs and findings.
"""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import hashlib
import json
import math
import re
import traceback
from urllib.parse import urlsplit

from geometry import parse_svg, assert_scene_svg, assert_endpoints, intrusions, stats, pair, points

ROOT = Path(__file__).resolve().parents[5]
OUT = Path(__file__).resolve().parent
WORK = OUT.parent.parent
BROWSER = WORK / 'browser-after-union'
CORE = WORK / 'core-after-union'
GOLDS = ROOT / 'docs/evidence/visual-golds-au3-matrix'
NS = '{http://www.w3.org/2000/svg}'
BUILD_IDENTITY = json.loads((OUT / 'expected-final-build.json').read_bytes())
JS = BUILD_IDENTITY['js']['path']
CSS = 'studio/dist/assets/index-B6WbMowt.css'
JS_SHA = BUILD_IDENTITY['js']['sha256']
CSS_SHA = '172a09a8c147e53c3bef426cf76b59b8cc4893e891eb6e920aa7b25a0bb024e0'
CACHE = {}
CHECKS = []
HEIGHT_ROUNDTRIPS = []


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def read(path):
    path = Path(path).absolute()
    if not path.is_file() or path.is_symlink():
        raise ValueError(f'Missing or symlink input: {path}')
    raw = path.read_bytes()
    if path in CACHE and CACHE[path] != raw:
        raise ValueError(f'Input changed during read: {path}')
    CACHE[path] = raw
    return raw


def load(path):
    return json.loads(read(path))


def binding(path, raw=None):
    path = Path(path).absolute()
    body = read(path) if raw is None else raw
    return {'path': str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path),
            'bytes': len(body), 'sha256': sha(body)}


def verify(record):
    path = Path(record['path'])
    if not path.is_absolute():
        path = ROOT / path
    actual = binding(path)
    assert actual['bytes'] == record['bytes'] and actual['sha256'] == record['sha256'], record
    return path


def exact(a, b, message):
    assert a == b, message
    CHECKS.append(message)


def keys_diff(a, b):
    return {key: {'before': a.get(key), 'after': b.get(key)}
            for key in sorted(a.keys() | b.keys()) if a.get(key) != b.get(key)}


def without(value, keys):
    return {key: item for key, item in value.items() if key not in keys}


def svg_tree(raw, root_mm=False):
    root, metadata = parse_svg(raw)
    def visit(node, at_root=False):
        attrs = dict(node.attrib)
        if at_root and root_mm:
            # The actual publisher rewrites only root mm numeric formatting.
            # Both values are separately checked against complete Scene bounds.
            for key in ('width', 'height'):
                value = attrs[key]
                assert value.endswith('mm')
                attrs[key] = float(value[:-2])
        text = node.text or ''
        if node.tag == NS + 'metadata':
            text = json.loads(text)
        return {'tag': node.tag, 'attributes': attrs, 'text': text,
                'children': [visit(child) for child in node]}
    return visit(root, True)


def publisher_equal(publication, actual):
    expected = svg_tree(publication, root_mm=True)
    exported = svg_tree(actual, root_mm=True)
    for key in ('width', 'height'):
        assert math.isclose(expected['attributes'][key], exported['attributes'][key], abs_tol=.011), key
    # Numeric physical size differences have just been checked; this affects
    # root width/height comparison only, never revision/metadata/layout/routes.
    for key in ('width', 'height'):
        exported['attributes'][key] = expected['attributes'][key]
    exact(exported, expected, 'Actual publication SVG matches current core complete XML aside from independently checked root mm serialization')


def dimensions(scene, svg):
    root, metadata = parse_svg(svg)
    b = scene['bounds']
    expected_box = [b[key] for key in ('x', 'y', 'width', 'height')]
    box = [float(number) for number in root.attrib['viewBox'].split()]
    assert len(box) == 4 and all(math.isclose(a, b, abs_tol=.011) for a, b in zip(box, expected_box))
    assert math.isclose(float(root.attrib['width'][:-2]), scene['pageSpec']['widthMm'], abs_tol=.011)
    height = scene['pageSpec']['widthMm'] * b['height'] / b['width']
    assert math.isclose(float(root.attrib['height'][:-2]), height, abs_tol=.011)
    assert math.isclose(metadata['heightMm'], height, abs_tol=1e-8)
    exact(metadata['widthMm'], scene['pageSpec']['widthMm'], 'SVG width metadata binds Canvas page')
    return {'viewBox': box, 'widthMm': scene['pageSpec']['widthMm'], 'heightMm': height}


def architecture(document):
    nodes = {node['id']: node for node in document['architecture']['nodes']}
    assert len(nodes) == len(document['architecture']['nodes'])
    sources = document['architecture']['sources']
    rows = []
    for item in sources:
        file = ROOT / 'fixtures/residual_cnn' / item['path']
        source = read(file)
        assert sha(source) == item['digest'] == sha(item['content'].encode())
        rows.append(binding(file))
    return nodes, rows


def ancestor_chain(nodes, identity):
    result, seen = [], set()
    while identity in nodes and nodes[identity].get('parentId'):
        identity = nodes[identity]['parentId']
        assert identity not in seen, 'Canonical parent cycle'
        seen.add(identity)
        result.append(identity)
    return result


def residual_facts(scene, document, level, changed_ids):
    canonical, _ = architecture(document)
    visible = {node['id']: node for node in scene['nodes']}
    rows = []
    for edge in scene['edges']:
        if edge['role'] != 'residual':
            continue
        owner = visible[edge['targetId']]
        real = canonical[edge['target']['nodeId']]
        assert real['kind'] == 'Add' and edge['target']['portId'].endswith(':in:right')
        hidden = real['id'] != owner['id']
        chain = ancestor_chain(canonical, real['id'])
        if hidden:
            assert owner['expandable'] and not owner['expanded'] and owner['id'] in chain
            assert real['id'] not in visible
        else:
            assert real['id'] in visible and level == 2
        if edge['id'] in changed_ids:
            assert hidden and points(edge['path'])[-1][1] > points(edge['path'])[0][1]
        rows.append({'id': edge['id'], 'canonicalTarget': edge['target'], 'canonicalSource': edge['source'],
                     'displayTarget': owner['id'], 'realTargetKind': real['kind'],
                     'targetHidden': hidden, 'ancestorChain': chain,
                     'displayOwnerExpanded': owner['expanded'], 'stats': stats(edge['path'])})
    assert len(rows) == (1 if level == 0 else 2)
    if level == 0:
        residual = next(edge for edge in scene['edges'] if edge['id'] == 'edge:9')
        data = next(edge for edge in scene['edges'] if edge['id'] == 'edge:2')
        assert residual['tensorId'] == data['tensorId'] and residual['role'] != data['role']
        assert residual['canonicalEdgeIds'] == ['edge:9'] and data['canonicalEdgeIds'] == ['edge:2', 'edge:3']
        assert points(residual['path'])[0][0] != points(data['path'])[0][0]
    return rows


def refinement(before, scene, document, level):
    # No cloned/rewritten baseline, no temporal revision normalization.
    # Old/current revision is separately recorded. All other complete Scene
    # protected fields are compared directly to the same frontier/style/width.
    exact(set(scene), set(before), 'Current Scene field set equals matched historical Scene')
    for key in scene:
        if key not in ('revision', 'edges'):
            exact(scene[key], before[key], f'Matched historical protected Scene field exact: {key}')
    exact([without(edge, ('path', 'labelX', 'labelY')) for edge in scene['edges']],
          [without(edge, ('path', 'labelX', 'labelY')) for edge in before['edges']],
          'Canonical branches, bindings, tensor, role, style and identities exact')
    changed = [edge['id'] for edge, old in zip(scene['edges'], before['edges']) if edge['path'] != old['path']]
    exact(changed, ['edge:9'] if level == 0 else ['edge:18'] if level == 1 else [],
          'Only independently identified collapsed residual route changes')
    routes = []
    for old, edge in zip(before['edges'], scene['edges']):
        old_stats, current_stats = stats(old['path']), stats(edge['path'])
        if edge['id'] in changed:
            assert math.isclose(old_stats['length'], 271.4 if level == 0 else 235.4, abs_tol=1e-8)
            assert old_stats['bends'] == 4 and current_stats == {'length': 38, 'bends': 0}
        else:
            exact(edge, old, f'Unchanged full route/label/style record: {edge["id"]}')
        routes.append({'id': edge['id'], 'before': old_stats, 'after': current_stats,
                      'pathChanged': edge['id'] in changed})
    old_hits, new_hits = intrusions(before), intrusions(scene)
    assert set(new_hits).issubset(old_hits), f'New body/header/backplate intrusion {set(new_hits)-set(old_hits)}'
    pairs = []
    for index, edge in enumerate(scene['edges']):
        for other_index in range(index + 1, len(scene['edges'])):
            other = scene['edges'][other_index]
            old = pair(before['edges'][index]['path'], before['edges'][other_index]['path'])
            current = pair(edge['path'], other['path'])
            assert len(current['crossings']) <= len(old['crossings']), (edge['id'], other['id'], 'crossings')
            assert current['overlapLength'] <= old['overlapLength'] + 1e-7, (edge['id'], other['id'], 'overlap')
            pairs.append({'first': edge['id'], 'second': other['id'],
                          'sameTensor': edge['tensorId'] == other['tensorId'],
                          'roles': [edge['role'], other['role']], 'before': old, 'after': current})
    return {'oldRevision': before['revision'], 'currentRevision': scene['revision'],
            'revisionModifiedOrNormalized': False, 'changedEdges': changed,
            'routes': routes, 'intrusionsBefore': old_hits, 'intrusionsAfter': new_hits,
            'pairLocal': pairs, 'residualFacts': residual_facts(scene, document, level, changed)}


def export_files(directory, scene, publication, expected_document, expected_uuid=None):
    doc = load(directory / 'document.json')
    exact(doc, expected_document, 'Actual exporter Canvas equals saved/current Canvas including revision')
    raw = read(directory / 'figure.svg')
    receipt = load(directory / 'figure.svg.receipt.json')
    assert receipt['format'] == 'svg' and receipt['geometryVerified'] is True
    assert receipt['bytes'] == len(raw)
    for key in ('outputDigest', 'svgDigest'):
        exact(receipt[key], sha(raw), f'Actual SVG bytes bind receipt {key}')
    for key in ('inputSvgDigest', 'sceneSvgDigest'):
        exact(receipt[key], sha(publication), f'Exporter receipt binds current publication input {key}')
    for key, value in [('documentId', doc['id']), ('revision', doc['revision']),
                       ('sourceDigest', doc['architecture']['sourceDigest']), ('irDigest', doc['architecture']['irDigest'])]:
        exact(receipt[key], value, f'Export receipt binds Canvas {key}')
    assert Path(receipt['publicationOrigin']) == ROOT / 'src/archcanvas_publication/exporter.py'
    read(receipt['publicationOrigin'])
    assert_scene_svg(scene, raw)
    size = dimensions(scene, raw)
    assert receipt['widthMm'] == size['widthMm'] and math.isclose(receipt['heightMm'], size['heightMm'], abs_tol=1e-8)
    exact(receipt['viewBox'], size['viewBox'], 'Actual publication receipt viewBox exact')
    publisher_equal(publication, raw)
    source_path = Path(receipt['path'])
    assert source_path.parent.parent == ROOT / '.archcanvas/m4-collapsed-residual-session/exports'
    if expected_uuid is not None:
        exact(source_path.parent.name, expected_uuid, 'Export UUID binds actual source directory')
    exact(read(source_path), raw, 'Copied actual SVG bytes equal session source SVG')
    exact(read(source_path.parent / 'document.json'), read(directory / 'document.json'), 'Copied actual exporter document bytes equal session source document')
    if source_path.parent != directory:
        exact(read(source_path.parent / 'figure.svg.receipt.json'), read(directory / 'figure.svg.receipt.json'), 'Copied actual exporter receipt bytes equal session source receipt')
    return {'svg': binding(directory / 'figure.svg'), 'document': binding(directory / 'document.json'),
            'receipt': binding(directory / 'figure.svg.receipt.json'), 'sourceDirectory': str(source_path.parent),
            'dimensions': size, 'fonts': receipt['fonts'], 'uuid': source_path.parent.name}


def public_observation(path, document, scene, interactive):
    observation = load(path)
    assert observation['kind'] == 'committed'
    for key, value in [('revision', document['revision']), ('expandedIds', document['expandedIds'])]:
        exact(observation[key], value, f'Public committed observation binds {key}')
    exact(observation['pinnedIds'], document['pinnedObjects'], 'Public pins bind Canvas')
    exact(observation['edges'], [{'id': edge['id'], 'path': edge['path']} for edge in scene['edges']], 'Public path collection binds every core route')
    raw = observation['svg'].encode()
    _, metadata = parse_svg(raw)
    exact(without(observation['metadata'], ('heightMm',)), without(metadata, ('heightMm',)),
          'Public observation complete metadata is exact except independently checked heightMm roundtrip')
    assert set(observation['metadata']) == set(metadata), 'No metadata field hidden by height check'
    public_height, svg_height = observation['metadata']['heightMm'], metadata['heightMm']
    root_svg, _ = parse_svg(raw)
    viewbox = [float(item) for item in root_svg.attrib['viewBox'].split()]
    assert len(viewbox) == 4 and viewbox[2] > 0
    independently_expected = metadata['widthMm'] * viewbox[3] / viewbox[2]
    # Explicitly scoped to this JSON number only. Complete raw SVG XML,
    # all other metadata and actual Scene/Canvas revisions remain exact.
    assert all(isinstance(value, (int, float)) and math.isfinite(value)
               for value in (public_height, svg_height, independently_expected))
    delta = abs(public_height - svg_height)
    assert delta <= 1e-10 and abs(public_height - independently_expected) <= 1e-10 and abs(svg_height - independently_expected) <= 1e-10
    if delta:
        HEIGHT_ROUNDTRIPS.append({'observation': str(path.relative_to(ROOT)),
                                 'observationHeightMm': public_height, 'actualSvgHeightMm': svg_height,
                                 'independentViewBoxHeightMm': independently_expected,
                                 'absoluteDifferenceMm': delta, 'maximumAllowedDifferenceMm': 1e-10,
                                 'allOtherMetadataExact': True, 'actualSvgXmlModified': False})
    exact(svg_tree(raw), svg_tree(interactive), 'Actual browser interactive XML matches complete current core interactive XML')
    assert_scene_svg(scene, raw)
    dimensions(scene, raw)
    urls = [urlsplit(url).path for url in observation['assetUrls']]
    exact(urls, ['/assets/' + Path(JS).name, '/assets/' + Path(CSS).name], 'Actual public observation names current JS/CSS')
    assert observation['viewport'] == {'height': 720, 'width': 1280}
    assert isinstance(observation['capturedAt'], str) and 'T' in observation['capturedAt']
    return observation


def case_check(plan, root_capture):
    original_id = plan['caseId']
    case_id = original_id.replace('residual_cnn-', 'cnn-', 1)
    level = plan['frontier']
    directory = BROWSER / case_id
    current = load(directory / 'document.json')
    envelope = load(directory / 'saved-envelope.json')
    exact(envelope['document'], current, 'Stored envelope readback equals actual exported Canvas')
    assert isinstance(envelope['revision'], int) and envelope['revision'] > 0
    prior = load(GOLDS / (original_id + '.canvas.json'))
    exact(set(current), set(prior), 'Current Canvas field set equals exact matching historical Canvas')
    canvas_differences = keys_diff(prior, current)
    assert set(canvas_differences).issubset({'revision'}), canvas_differences
    for key in current:
        if key != 'revision':
            exact(current[key], prior[key], f'Whole matched Canvas field exact without normalization: {key}')
    assert isinstance(current['revision'], int) and current['revision'] >= 0
    exact(current['expandedIds'], plan['expandedIds'], 'Authored frontier explicitly matches plan')
    exact(current['pageSpec'], {'widthMm': plan['widthMm'], 'background': '#ffffff', 'preset': plan['preset']}, 'Page/preset explicitly matches case')
    canonical, source_files = architecture(current)
    reference = load(GOLDS / 'residual_cnn-level0-paper-180.canvas.json')
    common_differences = keys_diff(reference, current)
    assert set(common_differences).issubset({'revision', 'pageSpec', 'expandedIds', 'layout', 'layoutByFrontier'})
    # These differences are reported completely, never used to rewrite data.
    # Layout/appearance/source still require exact same-frontier matched gold.
    for key in ('architecture', 'displayAliases', 'nodeStyleOverrides', 'edgeStyleOverrides',
                'legendItems', 'annotations', 'pinnedObjects', 'sourceBindingDigest'):
        exact(current[key], reference[key], f'Common source/appearance/pins protected field exact: {key}')
    core_record = next(row for row in root_capture['records'] if row['caseId'] == case_id)
    exact(core_record['input'], binding(directory / 'document.json'), 'Core case observer directly binds this actual browser Canvas file')
    verify(core_record['input'])
    exact(sorted(row['path'] for row in core_record['files']),
          sorted(str((CORE / case_id / name).relative_to(ROOT)) for name in
                 ('scene.json', 'export.scene.json', 'publication.svg', 'interactive.svg')),
          'Core case observer binds all four correct case output paths')
    for file in core_record['files']:
        verify(file)
    core_dir = CORE / case_id
    scene = load(core_dir / 'scene.json')
    exported = load(core_dir / 'export.scene.json')
    exact(scene, exported, 'Full Canvas and full export complete Scene exact')
    exact(scene['documentId'], current['id'], 'Current core Scene Canvas identity exact')
    exact(scene['revision'], current['revision'], 'Current core Scene actual Canvas revision exact')
    exact(scene['pageSpec'], current['pageSpec'], 'Current core Scene actual page exact')
    assert len(scene['nodes']) == plan['expectedRenderedNodes']
    publication = read(core_dir / 'publication.svg')
    interactive = read(core_dir / 'interactive.svg')
    assert_scene_svg(scene, publication)
    assert_scene_svg(scene, interactive)
    endpoint_facts = assert_endpoints(scene, current)
    old_scene = load(GOLDS / (original_id + '.scene.json'))
    refine = refinement(old_scene, scene, current, level)
    before = public_observation(directory / 'fit-before.json', current, scene, interactive)
    after = public_observation(directory / 'fit-after.json', current, scene, interactive)
    assert datetime.fromisoformat(before['capturedAt'].replace('Z', '+00:00')) <= datetime.fromisoformat(after['capturedAt'].replace('Z', '+00:00'))
    exact(without(before, ('capturedAt',)), without(after, ('capturedAt',)), 'Fit screenshot is bracketed by identical public state and camera')
    fit_image = binding(directory / 'fit.jpg')
    assert read(directory / 'fit.jpg').startswith(b'\xff\xd8'), 'Actual fit capture is JPEG'
    local = None
    if plan['localScreenshotRequired'] or (directory / 'local.jpg').exists():
        local_before = public_observation(directory / 'local-before.json', current, scene, interactive)
        local_after = public_observation(directory / 'local-after.json', current, scene, interactive)
        assert datetime.fromisoformat(local_before['capturedAt'].replace('Z', '+00:00')) <= datetime.fromisoformat(local_after['capturedAt'].replace('Z', '+00:00'))
        exact(without(local_before, ('capturedAt',)), without(local_after, ('capturedAt',)), 'Local screenshot is bracketed by identical public state and camera')
        exact(without(local_before, ('capturedAt', 'paperTransform', 'zoom')),
              without(before, ('capturedAt', 'paperTransform', 'zoom')), 'Local view differs only in time and camera')
        assert read(directory / 'local.jpg').startswith(b'\xff\xd8')
        local = {'image': binding(directory / 'local.jpg'), 'zoom': local_before['zoom'],
                 'paperTransform': local_before['paperTransform']}
    export_binding = load(directory / 'export-binding.json')
    exact(export_binding['caseId'], case_id, 'Actual exporter binding case identity exact')
    exact(export_binding['revision'], current['revision'], 'Exporter action visual revision exact')
    exact(export_binding['storageRevision'], envelope['revision'], 'Exporter action storage revision exact')
    assert export_binding['href'] == '/api/exports/' + export_binding['uuid'] + '/figure.svg'
    assert Path(export_binding['sourceDirectory']) == ROOT / '.archcanvas/m4-collapsed-residual-session/exports' / export_binding['uuid']
    actual_export = export_files(directory, scene, publication, current, export_binding['uuid'])
    reopened = None
    if case_id == 'cnn-level0-paper-180':
        reopened_public = public_observation(directory / 'reopen-public.json', current, scene, interactive)
        exact(without(reopened_public, ('capturedAt', 'paperTransform', 'zoom')),
              without(before, ('capturedAt', 'paperTransform', 'zoom')), 'Post-reload current document and complete public geometry exact')
        action = load(directory / 'reopen-export.json')
        exact(action['originalHref'], export_binding['href'], 'Post-reload exporter action identifies the original export href')
        exact(action['cacheReused'], action['href'] == action['originalHref'], 'Post-reload cache provenance agrees with actual UUID identity')
        match = re.fullmatch(r'/api/exports/([0-9a-f]{32})/figure.svg', action['href'])
        assert match
        source_dir = ROOT / '.archcanvas/m4-collapsed-residual-session/exports' / match[1]
        reopened = export_files(source_dir, scene, publication, current, match[1])
        exact(read(source_dir / 'figure.svg'), read(directory / 'figure.svg'), 'Actual post-reload export complete bytes equal original actual export')
        reopened['publicObservation'] = binding(directory / 'reopen-public.json')
        reopened['action'] = binding(directory / 'reopen-export.json')
        reopened['storageRevisionReadback'] = envelope['revision']
        reopened['storageRevisionAfterReloadIndependentlyObserved'] = False
    # Across page/style variants of one frontier, geometry/layout/state remains
    # unchanged. The exact same-case gold comparison above protects appearance.
    cross_variant = []
    for other_id in sorted(path.name for path in BROWSER.iterdir() if path.is_dir()
                           and path.name.startswith(f'cnn-level{level}-') and path.name != case_id):
        other = load(BROWSER / other_id / 'document.json')
        exact(without(other, ('revision', 'pageSpec')), without(current, ('revision', 'pageSpec')),
              'Within one authored frontier, variants differ only in actual revision/page')
        cross_variant.append({'otherCaseId': other_id, 'actualDifferingFields': keys_diff(current, other)})
    return {'caseId': case_id, 'planCaseId': original_id, 'visualRevision': current['revision'],
            'storageRevision': envelope['revision'], 'matchedOldCanvasRevision': prior['revision'],
            'matchedCanvasDifferences': canvas_differences,
            'explicitCommonReferenceDifferences': common_differences,
            'baselineModifiedOrNormalized': False, 'expectedExpandedIds': plan['expandedIds'],
            'withinFrontierVariantDifferences': cross_variant,
            'expectedPageSpec': current['pageSpec'], 'sourceFiles': source_files,
            'nodeCount': len(scene['nodes']), 'edgeCount': len(scene['edges']),
            'fit': {'image': fit_image, 'zoom': before['zoom'], 'paperTransform': before['paperTransform']},
            'local': local, 'actualExport': actual_export, 'reopenedExport': reopened,
            'buildBindingScope': 'Public asset URLs name exact local dist JS/CSS hashes; network response bodies are not independently hashed by this helper.',
            'canonicalEndpointFacts': endpoint_facts, 'refinement': refine,
            'pixelAssessmentByThisHelper': False, 'humanAcceptanceCertified': False}


def current_bindings(paths):
    return [binding(path) for path in sorted(paths)]


def formal_check(name):
    directory = WORK / 'checks' / name
    receipt = load(directory / 'receipt.json')
    exact(receipt['exitCode'], 0, f'Root formal check exit0: {name}')
    exact(receipt['sourceBeforeAfterExact'], True, f'Root formal check before/after source exact: {name}')
    exact(receipt['inputsBefore'], receipt['inputsAfter'], f'Root formal check original input lists exact: {name}')
    for row in receipt['inputsAfter'] + receipt.get('infrastructure', []) + receipt.get('logs', []) + receipt.get('builtFiles', []):
        verify(row)
    assert read(directory / 'stderr.txt') == b''
    counts = None
    if name != BUILD_IDENTITY['buildCheck']:
        stdout = read(directory / 'stdout.txt').decode()
        counts = {key: int(re.search(r'^ℹ ' + key + r' (\d+)$', stdout, re.M)[1]) for key in ('tests', 'pass', 'fail')}
        expected = BUILD_IDENTITY['targetTestCount'] if name == BUILD_IDENTITY['targetCheck'] else BUILD_IDENTITY['suiteTestCount']
        exact(counts, {'tests': expected, 'pass': expected, 'fail': 0}, f'Root formal test actual stdout count: {name}')
    return {'name': name, 'receipt': binding(directory / 'receipt.json'),
            'exitCode': receipt['exitCode'], 'sourceBeforeAfterExact': receipt['sourceBeforeAfterExact'],
            'counts': counts, 'historicalCheckReceiptsSubstitutedOrNormalized': False}


def core_runner():
    directory = WORK / 'core-observation-run-attempt-2'
    receipt = load(directory / 'receipt.json')
    exact(receipt['exitCode'], 0, 'Root current core observation runner exit0')
    exact(receipt['sourceBeforeAfterExact'], True, 'Root current core observation runner source before/after exact')
    exact(receipt['inputsBefore'], receipt['inputsAfter'], 'Root current core observation original input lists exact')
    for row in receipt['inputsAfter'] + receipt['infrastructure'] + receipt['logs'] + receipt['outputs']:
        verify(row)
    argv = receipt['argv']
    assert argv[0] == '/home/fzg/.nvm/versions/node/v24.19.0/bin/node'
    assert '--experimental-strip-types' in argv and argv[-1].endswith('m4-collapsed-residual-work/observe_core.ts')
    assert Path(receipt['cwd']) == ROOT
    assert read(directory / 'stderr.txt') == b''
    return {'receipt': binding(directory / 'receipt.json'), 'argv': argv,
            'exitCode': receipt['exitCode'], 'sourceBeforeAfterExact': receipt['sourceBeforeAfterExact'],
            'scope': 'Observed formal core run; independent expected geometry is supplied separately by this reviewer.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--complete-signal', required=True, choices=['root-confirmed-12-cases-complete'])
    parser.add_argument('--report', default='report.json')
    args = parser.parse_args()
    assert re.fullmatch(r'[a-zA-Z0-9._-]+\.json', args.report)
    target = OUT / args.report
    if target.exists():
        raise ValueError('Refusing to overwrite an existing report')
    started = datetime.now(timezone.utc).isoformat()
    paths = set()
    for directory in (BROWSER, CORE, WORK / 'checks', OUT.parent / 'baseline'):
        paths.update(path for path in directory.rglob('*') if path.is_file())
    paths.update(path for path in (WORK / 'core-observation-run-attempt-2').rglob('*') if path.is_file())
    paths.update(path for path in (ROOT / 'studio/src').rglob('*') if path.is_file())
    paths.update(path for path in (ROOT / 'fixtures/residual_cnn').rglob('*') if path.is_file())
    paths.update([ROOT / JS, ROOT / CSS, ROOT / 'studio/dist/index.html', WORK / 'observe_core.ts',
                  WORK / 'run_core_observation.py',
                  OUT / 'audit.py', OUT / 'geometry.py', OUT / 'README.md',
                  OUT / 'expected-final-build.json',
                  OUT / 'preexecution-freeze.json',
                  WORK / 'visual-plan/plan.json', OUT.parent / 'acceptance-contract.json',
                  ROOT / '.archcanvas/browser-visual-matrix-au3/spec.json'])
    before = current_bindings(paths)
    result = {'protocol': 'archcanvas-collapsed-residual-browser-independent-readback/1',
              'startedAt': started, 'completionSignal': args.complete_signal,
              'scope': 'Twelve actual CNN browser cases and core/export/save observations; independent geometry and exact source binding. No browser interaction or product/model execution.',
              'cases': [], 'verdict': 'incomplete', 'inputsBefore': before,
              'productCodeExecutedByReviewer': False, 'testsRunByReviewer': False,
              'buildRunByReviewer': False, 'browserOperatedByReviewer': False,
              'modelsRunByReviewer': False, 'baselineRewrittenOrNormalized': False,
              'pixelAcceptanceCertified': False, 'humanAcceptanceCertified': False,
              'limits': ['JPEG bindings and bracketed DOM are checked, not pixel aesthetics by this data helper.',
                         'No actual physical85/180mm, resolved font, PDF/PNG or embedding certification.',
                         'No full39case matrix, drag/history/performance/novice/model equivalence certification.',
                         'Stored envelope snapshot is checked. Post-reload visible complete geometry and actual export are checked; a new post-reload envelope snapshot is not invented.']}
    try:
        prepared = load(OUT / 'preexecution-freeze.json')
        for row in prepared['helperSources'] + prepared['oldAttempt1Files'] + prepared['oldBrowserInputs'] + prepared['previousFailedAttemptFiles']:
            verify(row)
        result['retainedFailedAttempt'] = {'files': prepared['previousFailedAttemptFiles'],
                                         'failureKeptExact': True,
                                         'repairScope': 'Observation metadata heightMm JSON roundtrip only, checked independently; no SVG/data revision or baseline normalization.'}
        result['oldInputsPreserved'] = {'attempt1HelperExecuted': False,
                                       'attempt1FileCount': len(prepared['oldAttempt1Files']),
                                       'oldBrowserFileCount': len(prepared['oldBrowserInputs']),
                                       'scope': 'Nine incomplete prior-build cases remain exact historical evidence; no acceptance inherited.'}
        prior_union_manifest = load(WORK / 'before-overlap-union-repair/manifest.json')
        exact(sha(read(WORK / 'before-overlap-union-repair/manifest.json')),
              '5626fff004f90571682600fd341e9dfcfb9d179fdaa79dd461026a3c4edef9ca',
              'Explicit before-overlap-union archive identity')
        for row in prior_union_manifest['files']:
            verify({'path': row['copy'], 'bytes': row['bytes'], 'sha256': row['sha256']})
        for row in BUILD_IDENTITY['formalReceiptBindings']:
            verify(row)
        exact(BUILD_IDENTITY['targetTestCount'], 24, 'Explicit amended independent target count')
        exact(BUILD_IDENTITY['suiteTestCount'], 203, 'Explicit amended full suite count')
        exact(sha(read(ROOT / JS)), JS_SHA, 'Exact new JS build hash')
        exact(sha(read(ROOT / CSS)), CSS_SHA, 'Unchanged CSS build hash')
        result['formalChecks'] = [formal_check(name) for name in
                                 (BUILD_IDENTITY['targetCheck'], BUILD_IDENTITY['suiteCheck'], BUILD_IDENTITY['buildCheck'])]
        result['coreObservationRunner'] = core_runner()
        plan = load(WORK / 'visual-plan/plan.json')
        exact(plan['newCaseCount'], 12, 'Independent planned case count')
        expected = sorted(item['caseId'].replace('residual_cnn-', 'cnn-', 1) for item in plan['newCases'])
        actual = sorted(path.name for path in BROWSER.iterdir() if path.is_dir() and re.fullmatch(r'cnn-level[012]-(paper|monochrome)-(85|180)', path.name))
        exact(actual, expected, 'Exactly all twelve required case directories exist')
        archive_manifest = load(ROOT / 'docs/evidence/before-m4-collapsed-residual/manifest.json')
        verify(archive_manifest['priorSeal'])
        exact(archive_manifest['priorSeal']['sha256'],
              '360685f78ecc6d29875854a00ba9d8be19d1b2212483382aff78144dc4cc8225',
              'Historical au3 seal identity remains explicit')
        historical_seal = load(ROOT / archive_manifest['priorSeal']['path'])
        old_bindings = {row['path']: row for row in historical_seal['bindings']}
        old_inputs = []
        for item in plan['newCases']:
            for suffix in ('.canvas.json', '.scene.json'):
                old_path = GOLDS / (item['caseId'] + suffix)
                row = old_bindings[str(old_path.relative_to(ROOT))]
                verify(row)
                old_inputs.append(row)
        spec_binding = old_bindings['.archcanvas/browser-visual-matrix-au3/spec.json']
        verify(spec_binding)
        result['historicalExpectedInputs'] = {'seal': archive_manifest['priorSeal'],
                                             'caseCanvasAndSceneBindings': old_inputs,
                                             'matrixSpec': spec_binding,
                                             'oldSealOtherBindingsRevalidatedHere': False}
        captured = load(CORE / 'receipt.json')
        exact(captured['inputsBefore'], captured['inputsAfter'], 'Root core observer input bytes unchanged')
        assert captured['inputBytesUnchanged'] is True
        exact(sorted(row['caseId'] for row in captured['records']), expected, 'Root current core observes all twelve exact browser documents')
        for binding_row in captured['inputsBefore']:
            verify(binding_row)
        for item in plan['newCases']:
            result['cases'].append(case_check(item, captured))
        result['verdict'] = 'pass-bounded-artifact-canonical-geometry-export-save-readback'
    except Exception as failure:
        result['verdict'] = 'fail-retained'
        result['failure'] = {'type': type(failure).__name__, 'message': str(failure),
                             'traceback': traceback.format_exc()}
    # Preserve the first bytes of every adaptive read and compare them directly
    # with final disk bytes. No cache assertion can prevent a failure receipt.
    all_first = [binding(path, CACHE[path]) for path in sorted(CACHE)]
    after, unreadable = [], []
    for path in sorted(CACHE):
        try:
            if path.is_symlink() or not path.is_file():
                raise ValueError('Missing/symlink at final read')
            after.append(binding(path, path.read_bytes()))
        except Exception as error:
            unreadable.append({'path': str(path), 'error': str(error)})
    before_map = {row['path']: row for row in all_first}
    changed = [row['path'] for row in after if row != before_map[row['path']]]
    result['allInputFirstReadBindings'] = all_first
    result['inputsAfter'] = after
    initially_bound = {row['path'] for row in before}
    result['inputsAddedByAdaptiveRead'] = [row for row in all_first if row['path'] not in initially_bound]
    result['allInputsReadTwiceExact'] = not changed and not unreadable
    result['changedInputs'] = changed
    result['unreadableInputsAtFinalRead'] = unreadable
    result['completedAt'] = datetime.now(timezone.utc).isoformat()
    result['checks'] = CHECKS
    result['heightMmJsonRoundtripExceptions'] = HEIGHT_ROUNDTRIPS
    result['heightMmJsonRoundtripExceptionScope'] = 'Only observation metadata.heightMm vs its own exact SVG metadata; absolute<=1e-10 and independent SVG viewBox formula. All other metadata and complete actual/current core XML exact.'
    result['checkCount'] = len(CHECKS)
    if changed or unreadable:
        result['verdict'] = 'fail-input-mutation-retained'
    with target.open('x') as output:
        json.dump(result, output, ensure_ascii=False, indent=2, allow_nan=False)
        output.write('\n')
    body = target.read_bytes()
    print(json.dumps({'report': {'path': str(target.relative_to(ROOT)), 'bytes': len(body), 'sha256': sha(body)},
                      'caseCount': len(result['cases']), 'verdict': result['verdict'],
                      'inputsReadTwice': len(after), 'inputsExact': not changed and not unreadable}, ensure_ascii=False))
    return 0 if result['verdict'].startswith('pass-') else 1


if __name__ == '__main__':
    raise SystemExit(main())
