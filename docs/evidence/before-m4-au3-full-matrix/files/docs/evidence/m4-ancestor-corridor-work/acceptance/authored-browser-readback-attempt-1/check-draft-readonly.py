"""Read-only authored draft geometry/storage audit. Does not import model code."""
import hashlib
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path

root = Path(__file__).resolve().parents[5]
out = Path(__file__).parent
browser = root / 'docs/evidence/m4-ancestor-corridor-work/browser-final-attempt-1'
store = root / '.archcanvas/m4-ancestor-corridor-session/drafts/draft-859cef62-6bbe-45c6-a166-b5f519d7e600.json'

def binding(path):
    raw = path.read_bytes()
    return {'path': str(path.relative_to(root)), 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}

inputs = [store] + sorted(browser.glob('from-zero-*')) + [browser / 'final-public.json', root / 'studio/dist/assets/index-au3IB_0Q.js', root / 'studio/dist/assets/index-B6WbMowt.css']
before = [binding(path) for path in inputs]
envelope = json.loads(store.read_text())
draft = envelope['draft']
assert envelope['revision'] == 1 and draft['revision'] == 16
assert draft['schemaVersion'] == 1 and draft['mode'] == 'authored-draft'
assert draft['id'] == 'draft-859cef62-6bbe-45c6-a166-b5f519d7e600'
assert len(draft['nodes']) == 4 and len(draft['edges']) == 3
assert [node['kind'] for node in draft['nodes']] == ['Input', 'Linear', 'ReLU', 'Output']
assert [node['position'] for node in draft['nodes']] == [{'x': 50, 'y': 70}, {'x': 298, 'y': 70}, {'x': 546, 'y': 70}, {'x': 794, 'y': 70}]
assert draft['nodes'][0]['parameters'] == {'shape': [1, 16], 'dtype': 'float32'}
assert draft['nodes'][1]['parameters'] == {'in_features': 16, 'out_features': 32, 'bias': True}
assert draft['nodes'][2]['parameters'] == {} and draft['nodes'][3]['parameters'] == {}
for index, edge in enumerate(draft['edges']):
    assert edge['source'] == {'nodeId': draft['nodes'][index]['id'], 'portId': 'output'}
    assert edge['target'] == {'nodeId': draft['nodes'][index + 1]['id'], 'portId': 'input'}

# Independent complete path tokenizer. Zero collinear legs are allowed in draft
# display but every coordinate is finite and every segment is orthogonal.
def parse(path):
    token = r'[MLHV]|[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?'
    assert not re.sub(token + r'|[\s,]', '', path)
    values = re.findall(token, path)
    points = []
    index = 0
    x = y = 0
    while index < len(values):
        cmd = values[index]; index += 1
        assert cmd in ['M', 'L', 'H', 'V']
        assert (cmd == 'M') == (not points)
        if cmd in ['M', 'L']:
            x, y = float(values[index]), float(values[index + 1]); index += 2
        elif cmd == 'H':
            x = float(values[index]); index += 1
        else:
            y = float(values[index]); index += 1
        assert abs(x) < 1e7 and abs(y) < 1e7
        assert not points or points[-1][0] == x or points[-1][1] == y
        points.append([x, y])
    assert len(points) >= 2
    return points

records = []
for name in ['from-zero-complete.svg', 'from-zero-arranged.svg', 'from-zero-reopened.svg']:
    path = browser / name
    tree = ET.parse(path).getroot()
    nodes = [e for e in tree.iter('g') if e.get('data-draft-node')]
    edges = [e for e in tree.iter('g') if e.get('data-draft-edge')]
    expected_edges = 1 if name == 'from-zero-complete.svg' else 3
    assert len(nodes) == 4 and len(edges) == expected_edges
    assert [node.get('data-draft-node') for node in nodes] == [node['id'] for node in draft['nodes']]
    assert [edge.get('data-draft-edge') for edge in edges] == [edge['id'] for edge in draft['edges'][:expected_edges]]
    circles = {}
    positions = []
    for index, node in enumerate(nodes):
        match = re.fullmatch(r'translate\(([-\d.]+) ([-\d.]+)\)', node.get('transform', ''))
        assert match
        x, y = map(float, match.groups()); positions.append({'x': x, 'y': y})
        body = node.find('rect'); assert body is not None and body.get('width') == '176' and body.get('height') == '100'
        label = next(child.text for child in node if child.tag == 'text' and child.get('class') == 'draft-node-title')
        kind = next(child.text for child in node if child.tag == 'text' and child.get('class') == 'draft-node-kind')
        assert label == draft['nodes'][index]['label'] and kind == draft['nodes'][index]['kind']
        for port in node:
            if not port.get('data-draft-port'):
                continue
            assert port.get('data-node') == node.get('data-draft-node') and port.get('role') == 'button'
            actual = [circle for circle in port if circle.tag == 'circle' and circle.get('r') == '5']
            assert len(actual) == 1
            visible = actual[0]
            circles[(node.get('data-draft-node'), port.get('data-draft-port'))] = [x + float(visible.get('cx')), y + float(visible.get('cy'))]
    routes = []
    for index, edge in enumerate(edges):
        pair = [child for child in edge if child.tag == 'path']
        assert len(pair) == 2 and pair[0].get('d') == pair[1].get('d')
        points = parse(pair[1].get('d'))
        binding_edge = draft['edges'][index]
        assert points[0] == circles[(binding_edge['source']['nodeId'], binding_edge['source']['portId'])]
        assert points[-1] == circles[(binding_edge['target']['nodeId'], binding_edge['target']['portId'])]
        routes.append({'edgeId': edge.get('data-draft-edge'), 'path': pair[1].get('d'), 'points': points, 'sourceCircle': points[0], 'targetCircle': points[-1]})
    if expected_edges == 3:
        assert positions == [node['position'] for node in draft['nodes']]
        assert all(all(point[1] == 136 for point in row['points']) for row in routes)
    records.append({'raw': binding(path), 'draftNodes': len(nodes), 'draftEdges': len(edges), 'positions': positions, 'routes': routes,
                    'successForCompleteGraph': expected_edges == 3, 'rapidBatchCause': 'undetermined' if expected_edges == 1 else None})
assert (browser / 'from-zero-arranged.svg').read_bytes() == (browser / 'from-zero-reopened.svg').read_bytes()
status = {}
for name in ['from-zero-complete.dom.txt', 'from-zero-two-edges.dom.txt', 'from-zero-three-edges.dom.txt', 'from-zero-arranged.dom.txt', 'from-zero-saved.dom.txt', 'from-zero-reopened.dom.txt', 'from-zero-generation-review.dom.txt', 'from-zero-generated-saved.dom.txt']:
    text = (browser / name).read_text()
    status[name] = {'raw': binding(browser / name), 'draftCounts': re.findall(r'(\d+)\s+模块\s+(\d+)\s+连接', text), 'status': re.findall(r'- status: ([^\n]+)', text), 'contentInfoTail': text[-450:]}
assert status['from-zero-complete.dom.txt']['draftCounts'] == [('4', '1')]
assert status['from-zero-two-edges.dom.txt']['draftCounts'] == [('4', '2')]
assert status['from-zero-three-edges.dom.txt']['draftCounts'] == [('4', '3')]
assert '模型草稿已保存' in (browser / 'from-zero-saved.dom.txt').read_text()
assert '已重开保存的模型草稿' in (browser / 'from-zero-generation-review.dom.txt').read_text()
assert '模型已生成并静态核对' in (browser / 'from-zero-generation-review.dom.txt').read_text()
assert '画布已保存到正式工程' in (browser / 'from-zero-generated-saved.dom.txt').read_text()
final = json.loads((browser / 'final-public.json').read_text())
assert final['scripts'] == ['/assets/index-au3IB_0Q.js'] and final['styles'] == ['/assets/index-B6WbMowt.css']
assert final['url'] == 'http://127.0.0.1:8987/'
assert binding(root / 'studio/dist/assets/index-au3IB_0Q.js')['sha256'] == 'dca15460bc9ed8def5ff80c9da5dfcf16bb49f7a230986e0ffeef1a6b0e7548b'
assert binding(root / 'studio/dist/assets/index-B6WbMowt.css')['sha256'] == '172a09a8c147e53c3bef426cf76b59b8cc4893e891eb6e920aa7b25a0bb024e0'
after = [binding(path) for path in inputs]
assert before == after
report = {'schemaVersion': 1, 'scope': 'Read-only authored draft storage/XML geometry/status readback; no model/browser/test run', 'sourceBeforeAfterExact': True,
          'inputBindingsBefore': before, 'inputBindingsAfter': after, 'storedDraft': binding(store), 'storageRevision': envelope['revision'], 'draftRevision': draft['revision'],
          'declarations': {'input': draft['nodes'][0]['parameters'], 'linear': draft['nodes'][1]['parameters'], 'inferredByDeclaredRulesOnlyOutputShape': [1, 32], 'runtimeVerified': False},
          'draftNodeIds': [node['id'] for node in draft['nodes']], 'draftEdgeIds': [edge['id'] for edge in draft['edges']], 'rawStates': records, 'domStates': status,
          'arrangedAndReopenedSvgBytesExact': True, 'currentAuAndB6AssetsExact': True,
          'limitations': ['First rapid-batch 4/1 state is incomplete; cause remains undetermined.', 'Reopened SVG is exact persisted graph; its immediate DOM snapshot reports a transient checking/disabled state. Later generation-review DOM says draft reopened and statically checked.',
                         'Input shape/dtype and output shape derived from declared Linear rules are declarations, not runtime inference.', 'OuterHTML getAttribute null was a capture tool misuse, not product failure.',
                         'Draft save/reopen/generated working-copy success does not establish imported Canvas alias editing or its persistence.', 'No execution, dependency install, new test suite, matrix or human visual review.']}
with (out / 'draft-readback.json').open('x') as stream:
    json.dump(report, stream, ensure_ascii=False, indent=2); stream.write('\n')
print(json.dumps({'storedDraft': '4 nodes / 3 edges', 'rapidIncomplete': '4 nodes / 1 edge', 'arrangedReopenedSvgExact': True, 'bindingsExact': True}))
