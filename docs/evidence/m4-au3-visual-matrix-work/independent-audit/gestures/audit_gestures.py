"""Read-only gesture snapshots audit; does not execute renderer/model/browser."""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import hashlib
import json
import math
import re
import traceback
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[5]
OUT = Path(__file__).resolve().parent
WORK = OUT.parent.parent
NS = '{http://www.w3.org/2000/svg}'
cache = {}


def read(path):
    path = Path(path).absolute()
    raw = path.read_bytes()
    assert path not in cache or cache[path] == raw, f'Input changed: {path}'
    cache[path] = raw
    return raw


def load(path):
    return json.loads(read(path))


def bind(path, raw):
    return {'path': str(path.relative_to(ROOT)), 'bytes': len(raw),
            'sha256': hashlib.sha256(raw).hexdigest()}


def normalized_svg(value):
    # Change only root/document revision scalar representations.
    return re.sub(r'("revision":)\d+', r'\g<1>REV',
                  re.sub(r'data-revision="\d+"', 'data-revision="REV"', value))


def snapshot(path):
    value = load(path)
    root = ET.fromstring(value['svg'])
    assert root.tag == NS + 'svg'
    metadata = json.loads(root.find(NS + 'metadata').text)
    assert {key: val for key, val in metadata.items() if key != 'heightMm'} == {
        key: val for key, val in value['metadata'].items() if key != 'heightMm'}
    assert abs(metadata['heightMm'] - value['metadata']['heightMm']) <= 1e-10
    bodies = {}
    for element in root.iter():
        if element.get('data-canonical-id') is not None:
            identity = element.get('data-node-id')
            rectangles = [child for child in element if child.tag == NS + 'rect']
            assert rectangles
            rectangle = rectangles[-1]
            bodies[identity] = {key: float(rectangle.get(key)) for key in ('x','y','width','height')}
    nodes = {node['id']: node for node in value['nodes']}
    assert set(nodes) == set(bodies)
    for identity, body in bodies.items():
        assert {key: nodes[identity][key] for key in body} == body
    value['_metadata'] = metadata
    value['_bodies'] = bodies
    return value


def audit(fixture):
    directory = WORK / 'gestures' / fixture
    architecture = load(ROOT / 'docs/evidence/visual-golds-au3-matrix' / (fixture + '.architecture.json'))
    by_id = {node['id']: node for node in architecture['nodes']}
    input_paths = sorted(directory.glob('*-input.json'))
    assert len(input_paths) == 4
    expected_directions = {'left','right','up','down'}
    seen, trials = set(), []
    for path in input_paths:
        input_record = load(path)
        direction = input_record['direction']
        assert direction in expected_directions and direction not in seen
        seen.add(direction)
        prefix = path.stem.removesuffix('-input')
        before = snapshot(directory / (input_record['fromStep'] + '.json'))
        move_path = directory / (prefix + '-move.json')
        if not move_path.exists():
            move_path = directory / (prefix + '.json')
        after = snapshot(move_path)
        if direction == 'left' and (directory / '02-left-undo.json').exists():
            undo_path, redo_path = directory / '02-left-undo.json', directory / '03-left-redo.json'
        else:
            undo_path, redo_path = directory / (prefix + '-undo.json'), directory / (prefix + '-redo.json')
        undo, redo = snapshot(undo_path), snapshot(redo_path)
        target = input_record['nodeId']
        assert target in before['_bodies']
        ancestors = set()
        current = by_id[target]
        while current.get('parentId'):
            ancestors.add(current['parentId'])
            current = by_id[current['parentId']]
        for value in (after, undo, redo):
            assert value['camera'] == before['camera']
            assert value['expandedIds'] == before['expandedIds']
            assert {key: val for key,val in value['_metadata'].items() if key not in ('revision','heightMm')} == {
                key: val for key,val in before['_metadata'].items() if key not in ('revision','heightMm')}
            assert set(value['_bodies']) == set(before['_bodies'])
        assert before['_metadata']['sourceDigest'] == architecture['sourceDigest']
        assert before['_metadata']['irDigest'] == architecture['irDigest']
        assert after['_metadata']['revision'] == before['_metadata']['revision'] + 1
        assert undo['_metadata']['revision'] == after['_metadata']['revision'] + 1
        assert redo['_metadata']['revision'] == undo['_metadata']['revision'] + 1
        matrix = re.fullmatch(r'matrix\(([^)]+)\)', before['camera'])
        assert matrix
        camera_values = [float(v.strip()) for v in matrix.group(1).split(',')]
        assert len(camera_values) == 6 and camera_values[0] == camera_values[3] and camera_values[1] == camera_values[2] == 0
        zoom = camera_values[0]
        requested = input_record['screenDelta']
        expected_delta = [math.floor(delta / zoom / 4 + .5) * 4 for delta in requested]
        actual_delta = [after['_bodies'][target][key] - before['_bodies'][target][key] for key in ('x','y')]
        assert actual_delta == expected_delta, (direction, expected_delta, actual_delta)
        screen = next(node['screen'] for node in before['nodes'] if node['id'] == target)
        start = input_record['from']
        assert screen['x'] < start[0] < screen['x'] + screen['width']
        assert screen['y'] < start[1] < screen['y'] + screen['height']
        if 'to' in input_record:
            assert [input_record['to'][i] - start[i] for i in range(2)] == requested
        unrelated_changes = [identity for identity, body in before['_bodies'].items()
                             if identity not in ancestors | {target} and body != after['_bodies'][identity]]
        assert unrelated_changes == []
        ancestor_changes = [{'id':identity,'before':before['_bodies'][identity], 'after':after['_bodies'][identity]}
                            for identity in sorted(ancestors) if before['_bodies'][identity] != after['_bodies'][identity]]
        assert normalized_svg(before['svg']) == normalized_svg(undo['svg'])
        assert normalized_svg(after['svg']) == normalized_svg(redo['svg'])
        assert input_record['atomicNativeDrag'] is True and input_record['activeHeldCancelTested'] is False
        trials.append({'direction':direction,'nodeId':target,'screenDeltaReported':requested,
                       'observedZoomRoundedCss':zoom,'worldDeltaExpected':expected_delta,'worldDeltaActual':actual_delta,
                       'unrelatedBodyChanges':unrelated_changes,'ancestorFrameChanges':ancestor_changes,
                       'fullSvgUndoExactExceptRevision':True,'fullSvgRedoExactExceptRevision':True,
                       'cameraSourceIrFrontierCanonicalBindingUnchanged':True,
                       'beforeRevision':before['_metadata']['revision'],'moveRevision':after['_metadata']['revision'],
                       'undoRevision':undo['_metadata']['revision'],'redoRevision':redo['_metadata']['revision']})
    assert seen == expected_directions
    # Bind actual DOM and image artifacts too, without adding pixel review claims.
    for path in sorted(directory.iterdir()):
        if path.is_file() and path.suffix in ('.json','.txt','.jpg','.png'):
            read(path)
    return {'fixture':fixture,'directions':trials,'gesturesChecked':4,'humanParticipants':0,
            'nativeEventsRecordedByIndependentObserver':False,'activeHeldCancelTested':False,
            'timingOrPresentedFpsCertified':False,'savedReopenCertified':False,
            'scope':'Root-reported actual atomic input instructions matched public final geometry/history snapshots; no event-timing/native-provenance or product-model execution.'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--fixture', required=True, choices=('residual_cnn','mlp','transformer'))
    parser.add_argument('--label', required=True)
    args = parser.parse_args()
    destination = OUT / args.label
    assert not destination.exists() and '/' not in args.label
    started = datetime.now(timezone.utc).isoformat()
    source = read(Path(__file__))
    result = {'protocol':'archcanvas-au3-independent-gesture-audit/1','startedAt':started,
              'testsRun':False,'modelsRun':False,'buildRun':False,'browserOperated':False,
              'auditorSource':bind(Path(__file__).absolute(),source)}
    try:
        result['gestureAudit'] = audit(args.fixture)
        result['status'] = 'passed-with-stated-scope'
    except Exception as error:
        result['status']='audit-failed';result['error']=str(error);result['traceback']=traceback.format_exc()
    before = [bind(path,raw) for path,raw in sorted(cache.items())]
    after = [bind(path,path.read_bytes()) for path in sorted(cache)]
    result.update({'inputsBefore':before,'inputsAfter':after,'inputsUnchanged':before==after,
                   'finishedAt':datetime.now(timezone.utc).isoformat()})
    if before != after: result['status']='audit-failed-input-changed'
    destination.mkdir()
    (destination/'auditor-source.py').open('xb').write(source)
    raw=(json.dumps(result,ensure_ascii=False,indent=2)+'\n').encode()
    (destination/'report.json').open('xb').write(raw)
    print(json.dumps({'report':bind(destination/'report.json',raw),'status':result['status'],
                      'inputs':len(cache),'unchanged':before==after,'error':result.get('error')},ensure_ascii=False))
    return 0 if result['status']=='passed-with-stated-scope' else 1


if __name__ == '__main__':
    raise SystemExit(main())
