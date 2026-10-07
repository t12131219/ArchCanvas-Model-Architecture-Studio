"""Independent read-only audit of completed CUA public-DOM/SVG observations.

No product imports, browser automation, source analysis/execution or image/DOM
synchronization inference. The caller selects a completed capture inventory.
"""
from __future__ import annotations
import argparse
from collections import Counter
import hashlib
import json
import re
from pathlib import Path
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
CAPTURES = HERE.parent / 'browser/continuation'
NAMESPACE = '{http://www.w3.org/2000/svg}'
EPS = 1e-5

def binding(path):
    raw = path.read_bytes()
    return {'path': str(path.relative_to(ROOT)), 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}

def compact(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'))

def tree_value(node):
    return [node.tag, sorted(node.attrib.items()), (node.text or '').strip(), [tree_value(child) for child in node]]

def info(svg):
    root = ET.fromstring(svg)
    metadata = json.loads(root.find(NAMESPACE + 'metadata').text)
    nodes = {g.get('data-node-id'): g for g in root.iter() if g.get('data-canonical-id')}
    edges = {g.get('data-edge-id'): g for g in root.iter() if g.get('data-edge-id')}
    guides = {g.get('data-caption-guide-id'): g for g in root.iter() if g.get('data-caption-guide-id')}
    ports = {g.get('data-port-id'): g for g in root.iter() if g.get('data-port-id')}
    front = {}
    for identity, node in nodes.items():
        rectangles = [g for g in node if g.tag == NAMESPACE + 'rect' and 'stroke-width' in g.attrib]
        assert len(rectangles) == 1, identity
        front[identity] = {k: float(rectangles[0].get(k)) for k in ['x', 'y', 'width', 'height']}
    geometry = []
    for child in root:
        if child.tag == NAMESPACE + 'metadata':
            continue
        geometry.append(tree_value(child))
    return {'root': root, 'metadata': metadata, 'nodes': nodes, 'front': front,
            'edges': edges, 'guides': guides, 'ports': ports, 'geometry': compact(geometry)}

def transform(value):
    match = re.fullmatch(r'width: ([\d.]+)px; height: ([\d.]+)px; transform: translate\(([-\d.]+)px, ([-\d.]+)px\) scale\(([-\d.]+)\);', value)
    assert match, value
    return dict(zip(['width', 'height', 'x', 'y', 'scale'], map(float, match.groups())))

def point_on_route(point, route):
    tokens = list(re.finditer(r'([MHVL])\s*([-+\d.eE]+)(?:[ ,]+([-+\d.eE]+))?', route))
    pts = []
    at = 0
    for token in tokens:
        assert not route[at:token.start()].strip()
        at = token.end()
        cmd, first, second = token.groups()
        first = float(first)
        p = (first, float(second)) if cmd in ['M', 'L'] else (first, pts[-1][1]) if cmd == 'H' else (pts[-1][0], first)
        pts.append(p)
    assert not route[at:].strip() and len(pts) >= 2
    return any(min(a[0], b[0])-EPS <= point[0] <= max(a[0], b[0])+EPS and
               min(a[1], b[1])-EPS <= point[1] <= max(a[1], b[1])+EPS and
               (abs(a[0]-b[0]) < EPS and abs(point[0]-a[0]) < EPS or abs(a[1]-b[1]) < EPS and abs(point[1]-a[1]) < EPS)
               for a, b in zip(pts, pts[1:]))

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--through', required=True, type=int, help='Last completed numbered capture; later captures remain outside this audit.')
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    assert args.through >= 14
    assert not args.output.exists(), 'Never overwrite an earlier audit attempt.'
    args.output.mkdir(parents=True)
    checks = []
    def check(name, condition):
        checks.append({'name': name, 'passed': bool(condition)})
        assert condition, name
    paths = [p for p in sorted(CAPTURES.glob('*.json')) if re.match(r'^\d\d-', p.stem) and 4 <= int(p.name[:2]) <= args.through]
    before = {p: binding(p) for p in CAPTURES.rglob('*') if p.is_file()}
    package = ROOT / '.archcanvas/m4-research-trial-caption-route-current'
    architecture = json.loads((package / 'baseline/architecture.json').read_bytes())
    baseline_manifest = json.loads((package / 'manifest.json').read_bytes())
    architecture_row = next(row for row in baseline_manifest['baseline']['files'] if row['path'] == 'baseline/architecture.json')
    raw_arch = (package / 'baseline/architecture.json').read_bytes()
    check('frozen architecture exact package binding', len(raw_arch) == architecture_row['bytes'] and hashlib.sha256(raw_arch).hexdigest() == architecture_row['sha256'])
    check('frozen fixture source bytes still match both formal source files', all((package / 'baseline/source' / name).read_bytes() == (ROOT / 'fixtures/transformer' / name).read_bytes() for name in ['model.py', 'blocks.py']))
    facts = []
    calls_by_instance = Counter(n['instanceId'] for n in architecture['nodes'] if 'instanceId' in n)
    for node in architecture['nodes']:
        fact = {'id': node['id'], 'sourceLabel': node['label'], 'kind': node['kind'], 'category': node['category'], 'evidence': node['evidence']}
        for key in ['instanceId', 'callCount', 'callId', 'repeat', 'source', 'outputPath']:
            if key in node:
                fact[key] = node[key]
        if 'instanceId' in node:
            fact['callCount'] = calls_by_instance[node['instanceId']]
        facts.append(fact)
    canonical = {e['id']: e for e in architecture['edges']}
    observed = {}
    reports = []
    for path in paths:
        data = json.loads(path.read_bytes())
        svg_path = path.with_suffix('.svg')
        check(path.stem + ' separate SVG exact public observation bytes', svg_path.read_text() == data['svg'])
        parsed = info(data['svg'])
        meta = parsed['metadata']
        check(path.stem + ' metadata exact JSON and document/source/IR identity', meta == json.loads(data['metadata']) and
              meta['documentId'] == baseline_manifest['baseline']['documentId'] and meta['sourceDigest'] == architecture['sourceDigest'] and meta['irDigest'] == architecture['irDigest'] and meta['sourceFactScope'] == 'whole-source-architecture')
        check(path.stem + ' all49 independent architecture facts', meta['sourceFacts'] == facts and len(facts) == 49)
        check(path.stem + ' exact metadata SVG document and revision', parsed['root'].get('data-document-id') == meta['documentId'] and int(parsed['root'].get('data-revision')) == meta['revision'])
        bindings = meta['renderedBindings']
        check(path.stem + ' rendered SVG edge identity inventory equals metadata', len(parsed['edges']) == len(bindings) and set(parsed['edges']) == {b['sceneEdgeId'] for b in bindings})
        for edge in bindings:
            main = canonical[edge['sceneEdgeId']]
            check(path.stem + ' edge source/target/tensor/role ' + edge['sceneEdgeId'], all(edge[k] == main[k] for k in ['source', 'target', 'tensorId', 'role']) and
                  edge['canonicalEdgeIds'] and all(identity in canonical for identity in edge['canonicalEdgeIds']) and parsed['edges'][edge['sceneEdgeId']].get('data-tensor-id') == edge['tensorId'])
        check(path.stem + ' node identity inventory equals metadata', set(parsed['nodes']) == {n['sceneNodeId'] for n in meta['renderedNodes']} and all(n['canonicalNodeId'] in {f['id'] for f in facts} for n in meta['renderedNodes']))
        decorations = meta.get('presentationDecorations', [])
        check(path.stem + ' guide decoration identities exact and outside tensor binding ids', set(parsed['guides']) == {g['id'] for g in decorations} and not set(parsed['guides']).intersection(parsed['edges']))
        for identity, guide in parsed['guides'].items():
            owner = guide.get('data-caption-for-edge')
            paths_with_arrows = [g for g in parsed['edges'][owner] if g.tag == NAMESPACE+'path' and 'marker-end' in g.attrib]
            check(path.stem + ' unarrowed guide unique owned edge ' + identity, len(paths_with_arrows) == 1 and owner in parsed['edges'] and
                  not any(k.startswith('marker') for k in guide.attrib) and not any(k.startswith('marker') for ancestor in parsed['root'].iter() if guide in list(ancestor) for k in ancestor.attrib) and
                  guide.get('pointer-events') == 'none' and sum(g['id'] == identity and g['sceneEdgeId'] == owner and g['path'] == guide.get('d') for g in decorations) == 1)
            match = re.match(r'M\s*([-+\d.eE]+)\s+([-+\d.eE]+)', guide.get('d'))
            check(path.stem + ' guide actually starts on its sole owned canonical route ' + identity, match is not None and point_on_route(tuple(map(float, match.groups())), paths_with_arrows[0].get('d')))
        observed[path.stem] = {'data': data, **parsed}
        reports.append({'capture': path.stem, 'metadataRevision': meta['revision'], 'nodeCount': len(parsed['nodes']), 'edgeCount': len(parsed['edges']),
                        'sourceFactCount': len(facts), 'guides': [{'id': i, 'owner': g.get('data-caption-for-edge'), 'path': g.get('d')} for i, g in parsed['guides'].items()],
                        'camera': transform(data['paper']), 'svgBinding': binding(svg_path), 'jsonBinding': binding(path)})
    base = observed['04-divs-100-settled']
    camera_names = ['04-divs-100-settled', '05-camera-right', '06-camera-down', '07-camera-left', '08-camera-up-restored']
    expected = [(32,0), (0,32), (-32,0), (0,-32)]
    camera_steps = []
    for a, b, delta in zip(camera_names, camera_names[1:], expected):
        left, right = observed[a], observed[b]
        ca, cb = transform(left['data']['paper']), transform(right['data']['paper'])
        check(b + ' exact discrete32px camera delta', abs(cb['x']-ca['x']-delta[0]) < EPS and abs(cb['y']-ca['y']-delta[1]) < EPS and cb['scale'] == ca['scale'] == 1)
        check(b + ' entire SVG geometry and metadata unchanged', left['geometry'] == right['geometry'] and left['metadata'] == right['metadata'])
        before_cards = {n['id']: n['rect'] for n in left['data']['cards']}
        after_cards = {n['id']: n['rect'] for n in right['data']['cards']}
        check(b + ' all public card rects translate rigidly with camera', set(before_cards) == set(after_cards) and all(abs(after_cards[i]['x']-r['x']-delta[0]) < EPS and abs(after_cards[i]['y']-r['y']-delta[1]) < EPS and abs(after_cards[i]['width']-r['width']) < EPS and abs(after_cards[i]['height']-r['height']) < EPS for i,r in before_cards.items()))
        camera_steps.append({'from': a, 'to': b, 'deltaPx': list(delta), 'nodeBodies': len(before_cards), 'revision': right['metadata']['revision']})
    check('camera returns exactly to baseline transform', observed[camera_names[-1]]['data']['paper'] == base['data']['paper'])
    move_series = []
    for direction, delta in [('right',(32,0)),('down',(0,32)),('left',(-32,0)),('up',(0,-32))]:
        move_key = next((k for k in observed if k.endswith('node-'+direction)), None)
        undo_key = next((k for k in observed if k.endswith(direction+'-undo')), None)
        redo_key = next((k for k in observed if k.endswith(direction+'-redo')), None)
        if not move_key:
            continue
        check(direction + ' completed move/undo/redo captures exist', undo_key is not None and redo_key is not None)
        moved, undone, redone = observed[move_key], observed[undo_key], observed[redo_key]
        changed = [i for i in moved['front'] if moved['front'][i] != base['front'][i]]
        check(direction + ' exactly one front card moves', len(changed) == 1 and set(moved['front']) == set(base['front']))
        identity = changed[0]
        before_card, after_card = base['front'][identity], moved['front'][identity]
        check(direction + ' actual world32node movement in required direction', abs(after_card['x']-before_card['x']-delta[0]) < EPS and abs(after_card['y']-before_card['y']-delta[1]) < EPS and before_card['width'] == after_card['width'] and before_card['height'] == after_card['height'])
        check(direction + ' camera unchanged by node operation', all(o['data']['paper'] == base['data']['paper'] for o in [moved,undone,redone]))
        check(direction + ' complete undo baseline and redo edited scene geometry match', undone['geometry'] == base['geometry'] and redone['geometry'] == moved['geometry'])
        immutable = ['documentId','sourceDigest','irDigest','sourceFacts','renderedNodes','renderedBindings']
        check(direction + ' metadata facts and canonical binding preserved', all(o['metadata'][k] == base['metadata'][k] for o in [moved,undone,redone] for k in immutable))
        check(direction + ' actual revisions advance through undo and redo', moved['metadata']['revision'] < undone['metadata']['revision'] < redone['metadata']['revision'])
        move_series.append({'direction': direction,'nodeId':identity,'deltaWorld':list(delta),'captures':[move_key,undo_key,redo_key],
                            'revisions':[o['metadata']['revision'] for o in [moved,undone,redone]],'undoWholeSceneRestored':True,'redoWholeSceneRestored':True})
    additional = {}
    if '22-encoder-down-association' in observed:
        moved = observed['22-encoder-down-association']
        restored = observed['23-encoder-undo-restored']
        repeat_id = 'repeat:instance:model.Transformer.encoder'
        check('22 encoder actual24world vertical move', abs(moved['front'][repeat_id]['y']-base['front'][repeat_id]['y']-24) < EPS and moved['front'][repeat_id]['x'] == base['front'][repeat_id]['x'])
        check('22 canonical memory edge remains while derived label and guide are absent', 'edge:44' in moved['edges'] and not any(g.tag == NAMESPACE+'text' and ''.join(g.itertext()).strip() == 'memory' for g in moved['edges']['edge:44']) and not moved['guides'])
        check('22 exact source facts and canonical binding unchanged', all(moved['metadata'][k] == base['metadata'][k] for k in ['sourceDigest','irDigest','sourceFacts','renderedBindings']))
        check('23 undo restores full baseline scene and memory guide', restored['geometry'] == base['geometry'] and restored['guides'].keys() == base['guides'].keys())
        additional['memoryLabelDiscontinuity'] = {'capture':'22-encoder-down-association','encoderDeltaY':24,'memoryEdgePreserved':True,'memoryLabelPresent':False,'guidePresent':False,'undoRestoresBaseline':True,
            'status':'verified-current-product-experience-gap','causeAssessment':'Root/caption agent separately investigates the existing abs(sourceBox.y-targetBox.y)<15 label policy; this observer does not infer causality from absence alone.',
            'labelStabilityPassed':False}
    if '25-reopened' in observed:
        restored = observed['23-encoder-undo-restored']
        saved, reopened = observed['24-saved-restored'], observed['25-reopened']
        check('24 save keeps exact baseline18 source/geometry', saved['geometry'] == restored['geometry'] and saved['metadata'] == restored['metadata'] and saved['metadata']['revision'] == 18)
        check('25 reopen exactly restores saved18 scene geometry and metadata', reopened['geometry'] == saved['geometry'] and reopened['metadata'] == saved['metadata'])
        additional['saveReopen'] = {'captures':['24-saved-restored','25-reopened'],'revision':18,'wholeSceneEqual':True,'metadataEqual':True,
            'cameraBefore':transform(saved['data']['paper']),'cameraAfter':transform(reopened['data']['paper']),'cameraPreserved':saved['data']['paper'] == reopened['data']['paper']}
    envelope_before = HERE.parent/'browser/pre-ui/saved-transformer-envelope.json'
    envelope_after = HERE.parent/'browser/pre-ui/saved-transformer-after-envelope.json'
    if envelope_after.exists():
        old_envelope, new_envelope = [json.loads(p.read_bytes()) for p in [envelope_before,envelope_after]]
        check('actual stored before/after document inventory identical', set(old_envelope['document']) == set(new_envelope['document']))
        changed = [k for k in old_envelope['document'] if old_envelope['document'][k] != new_envelope['document'][k]]
        check('actual stored restored document changes only visual revision', changed == ['revision'] and old_envelope['document']['revision'] == 0 and new_envelope['document']['revision'] == 18)
        check('actual saved storage counter1to2 separate from visual18', old_envelope['revision'] == 1 and new_envelope['revision'] == 2)
        check('actual stored architecture/sourceIR identical to frozen baseline', new_envelope['document']['architecture'] == old_envelope['document']['architecture'] == architecture and new_envelope['document']['sourceBindingDigest'] == architecture['sourceDigest'])
        check('actual saved document exactly matches reopened documentId and visual revision', new_envelope['document']['id'] == observed['25-reopened']['metadata']['documentId'] and new_envelope['document']['revision'] == observed['25-reopened']['metadata']['revision'])
        additional['storedDocument'] = {'before':binding(envelope_before),'after':binding(envelope_after),'changedDocumentFields':changed,
            'beforeVisualRevision':0,'afterVisualRevision':18,'beforeStorageRevision':1,'afterStorageRevision':2,'sourceArchitectureEqual':True,
            'persistedHistoryFieldPresent': 'history' in new_envelope['document'],'note':'Stored document has no history field; browser undo/redo is separately proved by captures, not persisted-history evidence.'}
    check('all captured input bytes unchanged by read-only audit', before == {p: binding(p) for p in CAPTURES.rglob('*') if p.is_file()})
    report = {'schema':'archcanvas-public-dom-svg-browser-independent/1','status':'passed-observation-relations', 'passed':len(checks),'total':len(checks),'checks':checks,
              'captures':reports, 'cameraSteps':camera_steps,'nodeMoves':move_series,'additionalObservations':additional,'inputs':[v for v in before.values()],
              'boundaries':{'automatedReadOnly':True,'productImports':False,'nativeInputSynthesized':False,'modelExecuted':False,'humanParticipants':0,'performanceCertified':False,'imagesInspectedByThisScript':False,
                           'screenshotAndDomSynchronizedByFilename':False,'continuousDraggingProved':False},
              'limitations':['Same-name screenshots and DOM may represent different painted instants; this script does not certify pixel synchronization.',
                             'Discrete32px camera/node snapshots are not continuous gesture latency, native input denominator, actual presented FPS or 300 objects visible proof.',
                             'Full scene geometry excludes only SVG metadata and root revision; public source/IR digests and facts are independently compared with frozen static architecture, not runtime execution.']}
    (args.output/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(compact({'passed':len(checks),'total':len(checks),'captures':len(reports),'cameraDirections':len(camera_steps),'nodeDirections':len(move_series)}))

if __name__ == '__main__':
    main()
