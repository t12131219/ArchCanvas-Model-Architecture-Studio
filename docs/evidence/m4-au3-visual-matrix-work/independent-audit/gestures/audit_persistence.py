"""Audit saved envelopes against public before/reopened SVGs without product execution."""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import hashlib
import json
import math
import traceback
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[5]
OUT = Path(__file__).resolve().parent
WORK = OUT.parent.parent
NS = '{http://www.w3.org/2000/svg}'
CACHE = {}


def read(path):
    path = Path(path).absolute()
    raw = path.read_bytes()
    assert path not in CACHE or CACHE[path] == raw, f'Input changed: {path}'
    CACHE[path] = raw
    return raw


def load(path):
    return json.loads(read(path))


def binding(path, raw):
    return {'path': str(path.relative_to(ROOT)), 'bytes': len(raw),
            'sha256': hashlib.sha256(raw).hexdigest()}


def snapshot(path):
    value = load(path)
    root = ET.fromstring(value['svg'])
    assert root.tag == NS + 'svg'
    metadata = json.loads(root.find(NS + 'metadata').text)
    assert {k: v for k, v in metadata.items() if k != 'heightMm'} == {
        k: v for k, v in value['metadata'].items() if k != 'heightMm'}
    delta = abs(metadata['heightMm'] - value['metadata']['heightMm'])
    assert all(math.isfinite(v) and v > 0 for v in (metadata['heightMm'], value['metadata']['heightMm']))
    assert delta <= 1e-10
    bodies = {}
    for element in root.iter():
        if element.get('data-canonical-id') is not None:
            rectangles = [child for child in element if child.tag == NS + 'rect']
            assert rectangles
            bodies[element.get('data-node-id')] = {
                key: float(rectangles[-1].get(key)) for key in ('x', 'y', 'width', 'height')}
    nodes = {node['id']: node for node in value['nodes']}
    assert set(nodes) == set(bodies)
    for identity, body in bodies.items():
        assert {key: nodes[identity][key] for key in body} == body
    assert root.get('data-document-id') == metadata['documentId']
    assert int(root.get('data-revision')) == metadata['revision']
    value['_svgMetadata'] = metadata
    value['_bodies'] = bodies
    value['_metadataHeightDelta'] = delta
    return value


def audit(fixture):
    directory = WORK / 'gestures' / fixture
    save_prefix, reopened_prefix, redo_name = (
        ('08', '09', '07-down-redo') if fixture == 'residual_cnn'
        else ('05', '06', '04-down-redo'))
    before = snapshot(directory / (save_prefix + '-save.json'))
    redo = snapshot(directory / (redo_name + '.json'))
    reopened = snapshot(directory / (reopened_prefix + '-reopened.json'))
    envelope = load(directory / (save_prefix + '-saved-envelope.json'))
    document = envelope['document']
    architecture = load(ROOT / 'docs/evidence/visual-golds-au3-matrix' / (fixture + '.architecture.json'))
    # Reuse previously independently checked static architecture; no model/renderer execution.
    assert document['architecture'] == architecture
    assert document['sourceBindingDigest'] == architecture['sourceDigest']
    assert type(envelope['revision']) is int and envelope['revision'] > 0
    assert document['revision'] == before['_svgMetadata']['revision'] == reopened['_svgMetadata']['revision']
    assert document['id'] == before['_svgMetadata']['documentId']
    assert before['svg'] == reopened['svg'] == redo['svg']
    assert before['metadata'] == reopened['metadata'] == redo['metadata']
    assert before['_bodies'] == reopened['_bodies'] == redo['_bodies']
    assert before['expandedIds'] == reopened['expandedIds'] == document['expandedIds']
    assert before['_svgMetadata']['sourceDigest'] == architecture['sourceDigest']
    assert before['_svgMetadata']['irDigest'] == architecture['irDigest']
    assert before['_svgMetadata']['widthMm'] == document['pageSpec']['widthMm']
    assert before['warnings'] == reopened['warnings'] == []
    assert 'camera' not in document and 'history' not in document
    by_id = {node['id']: node for node in architecture['nodes']}
    visible = set()
    def visit(identity):
        assert identity not in visible
        visible.add(identity)
        if identity in document['expandedIds']:
            for child in by_id[identity]['children']:
                assert by_id[child]['parentId'] == identity
                visit(child)
    for identity, node in by_id.items():
        if not node.get('parentId'):
            visit(identity)
    assert visible == set(before['_bodies'])
    positions = []
    for identity in sorted(visible):
        current, seen = identity, set()
        expected = {'x': 0, 'y': 0}
        while current:
            assert current not in seen
            seen.add(current)
            for key in expected:
                expected[key] += document['layout'][current][key]
            current = by_id[current].get('parentId')
        actual = {key: before['_bodies'][identity][key] for key in expected}
        assert actual == expected, (identity, expected, actual)
        positions.append({'id': identity, 'documentAncestorLocalSum': expected, 'publicSvgPosition': actual})
    saved_dom = read(directory / (save_prefix + '-save.dom.txt')).decode()
    reopened_dom = read(directory / (reopened_prefix + '-reopened.dom.txt')).decode()
    assert '- generic: 已保存' in reopened_dom and '已重开保存的画布' in reopened_dom
    assert '- button "撤销 Ctrl+Z" [disabled]:' in reopened_dom
    assert '- button "重做 Ctrl+Shift+Z" [disabled]:' in reopened_dom
    assert before['capturedAt'] < reopened['capturedAt']
    result = {'fixture': fixture, 'storageRevisionObserved': envelope['revision'],
              'visualRevision': document['revision'], 'sourceIrAndArchitectureExact': True,
              'lastRedoSavedAndReopenedFullSvgByteExact': True, 'metadataExactAcrossReopen': True,
              'savedDocumentLocalPositionsMatchPublicSvg': positions,
              'expandedVisibleMembershipExact': True, 'historyButtonsDisabledAfterReopen': True,
              'historyInternalStateIndependentlyInspected': False,
              'cameraBefore': before['camera'], 'cameraAfter': reopened['camera'],
              'cameraReopenFitChangeAllowed': True, 'cameraAndHistoryAbsentFromSavedDocument': True,
              'savedDomStatusAtCapture': '已保存' if '- generic: 已保存' in saved_dom else '保存请求仍在进行中',
              'reopenDomStatusObserved': '已保存 / 已重开保存的画布',
              'svgVsPublicMetadataHeightAbsDelta': [before['_metadataHeightDelta'], reopened['_metadataHeightDelta']],
              'pixelMatchingPerformed': False, 'humanParticipants': 0,
              'scope': 'Saved-envelope readback, ancestor-local position sums and full public SVG/metadata equality; successful reopen UI/history controls. No browser operation, storage backend execution or pixel/timing/native-event certification.'}
    if fixture == 'residual_cnn':
        failure = load(directory / 'reopen-first-read-failure.json')
        assert before['capturedAt'] < failure['recordedAt'] < reopened['capturedAt']
        assert failure['error'] == 'publication-scene svg null while page loading'
        result['preservedFirstReadFailure'] = failure
        result['initialLoadingReadCountedAsSuccess'] = False
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--fixture', required=True, choices=('residual_cnn', 'mlp', 'transformer'))
    parser.add_argument('--label', required=True)
    args = parser.parse_args()
    destination = OUT / args.label
    assert not destination.exists() and '/' not in args.label
    source = read(Path(__file__))
    result = {'protocol': 'archcanvas-au3-independent-persistence-audit/1',
              'startedAt': datetime.now(timezone.utc).isoformat(),
              'testsRun': False, 'modelsRun': False, 'buildRun': False, 'browserOperated': False,
              'auditorSource': binding(Path(__file__).absolute(), source)}
    try:
        result['persistenceAudit'] = audit(args.fixture)
        result['status'] = 'passed-with-stated-scope'
    except Exception as error:
        result['status'] = 'audit-failed'
        result['error'] = str(error)
        result['traceback'] = traceback.format_exc()
    before = [binding(path, raw) for path, raw in sorted(CACHE.items())]
    after = [binding(path, path.read_bytes()) for path in sorted(CACHE)]
    result.update({'inputsBefore': before, 'inputsAfter': after, 'inputsUnchanged': before == after,
                   'finishedAt': datetime.now(timezone.utc).isoformat()})
    if before != after:
        result['status'] = 'audit-failed-input-changed'
    destination.mkdir()
    (destination / 'auditor-source.py').open('xb').write(source)
    raw = (json.dumps(result, ensure_ascii=False, indent=2) + '\n').encode()
    (destination / 'report.json').open('xb').write(raw)
    print(json.dumps({'report': binding(destination / 'report.json', raw), 'status': result['status'],
                      'inputs': len(CACHE), 'unchanged': before == after, 'error': result.get('error')}, ensure_ascii=False))
    return 0 if result['status'] == 'passed-with-stated-scope' else 1


if __name__ == '__main__':
    raise SystemExit(main())
