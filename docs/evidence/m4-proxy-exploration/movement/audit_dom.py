"""Read-only audit of captured public DOM; never calls the app or model."""
import hashlib
import json
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
NS = '{http://www.w3.org/2000/svg}'
TARGET = 'call:instance:model.Transformer.source_embedding'


def read(name):
    data = json.loads((OUT / f'{name}.json').read_text())
    svg = ET.fromstring(data['svg'])
    nodes = {e.get('data-node-id'): ET.tostring(e, encoding='unicode')
             for e in svg.iter() if e.get('data-node-id') and e.get('role') == 'button'}
    edges = {e.get('data-edge-id'): ET.tostring(e, encoding='unicode')
             for e in svg.iter() if e.get('data-edge-id')}
    ports = {e.get('data-port-id'): ET.tostring(e, encoding='unicode')
             for e in svg.iter() if e.get('data-port-id')}
    metadata = json.loads(svg.find(f'{NS}metadata').text)
    target = next(e for e in svg.iter() if e.get('data-node-id') == TARGET and e.get('role') == 'button')
    rect = target.find(f'{NS}rect')
    return data, {'nodes': nodes, 'edges': edges, 'ports': ports}, metadata, {k: float(rect.get(k)) for k in ('x', 'y', 'width', 'height')}


baseline_data, baseline, baseline_metadata, baseline_rect = read('selected')
checks = []
for move, undo in [('node-up', 'node-up-undo'), ('node-down', 'node-down-undo'),
                   ('node-left', 'node-left-undo'), ('node-right', 'node-right-undo')]:
    _, geometry, metadata, rect = read(move)
    _, undone, undo_metadata, undone_rect = read(undo)
    checks.append({'move': move, 'deltaWorld': {k: rect[k] - baseline_rect[k] for k in ('x', 'y')},
                   'changedEdges': [k for k in geometry['edges'] if geometry['edges'][k] != baseline['edges'].get(k)],
                   'nodeIdsPreserved': geometry['nodes'].keys() == baseline['nodes'].keys(),
                   'edgeIdsPreserved': geometry['edges'].keys() == baseline['edges'].keys(),
                   'portIdsPreserved': geometry['ports'].keys() == baseline['ports'].keys(),
                   'sourceAndIRUnchanged': all(metadata[k] == baseline_metadata[k] for k in ('sourceDigest', 'irDigest', 'sourceFacts')),
                   'undoGeometryExact': undone == baseline,
                   'undoTargetExact': undone_rect == baseline_rect,
                   'revisions': [metadata['revision'], undo_metadata['revision']]})

pan_and_zoom = []
for name in ['pan-up', 'pan-down', 'pan-left', 'pan-right', 'zoom-small', 'zoom-100', 'zoom-large', 'zoom-refit']:
    data, geometry, metadata, _ = read(name)
    pan_and_zoom.append({'name': name, 'sceneGeometryExact': geometry == baseline,
                         'revision': metadata['revision'], 'paper': data['paper'], 'paperStyle': data['paperStyle']})

_, up, _, _ = read('node-up')
_, redo, _, _ = read('node-up-redo')
fits = []
for name in ['fit-overview', 'expanded-fit', 'fit-after-focus100']:
    data, geometry, metadata, _ = read(name)
    paper, canvas = data['paper'], data['canvas']
    fits.append({'name': name, 'viewport': data['viewport'], 'paper': paper, 'canvas': canvas,
                 'entirePaperInsideViewport': paper['x'] >= canvas['x'] and paper['y'] >= canvas['y'] and paper['right'] <= canvas['right'] and paper['bottom'] <= canvas['bottom'],
                 'nodeCount': len(geometry['nodes']), 'edgeCount': len(geometry['edges']), 'portCount': len(geometry['ports']),
                 'revision': metadata['revision']})

bindings = []
for rel in ['studio/src/App.tsx', 'studio/src/styles.css', 'studio/src/cameraProjection.ts',
            'studio/src/core/orthogonalRouter.ts', 'studio/src/core/scene.ts', 'studio/src/core/exportScene.ts',
            'fixtures/transformer/model.py', 'src/archcanvas_cli/server.py']:
    path = ROOT / rel
    if path.exists():
        bindings.append({'path': rel, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'bytes': path.stat().st_size})
for path in sorted((ROOT / 'studio/dist/assets').glob('*')):
    bindings.append({'path': str(path.relative_to(ROOT)), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'bytes': path.stat().st_size})

result = {'role': 'AI exploratory tester; not a human acceptance participant', 'actualViewport': baseline_data['viewport'],
          'baselineTarget': baseline_rect, 'moves': checks, 'upRedoGeometryExact': redo == up,
          'cameraOnlyOperations': pan_and_zoom, 'fitChecks': fits, 'sourceBuildBindings': bindings,
          'limits': ['One Transformer sample; four representative directions, not all objects or gesture sizes.',
                     'Up/right manual moves created and retained overlap warnings; these are not tidy outcomes.',
                     'Public DOM geometry checks do not certify publication aesthetics or human usability.',
                     'No current-build full visual matrix or native FPS acceptance is claimed.']}
(OUT / 'dom-audit.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({'moves': checks, 'redo': result['upRedoGeometryExact'], 'cameraExact': all(x['sceneGeometryExact'] for x in pan_and_zoom), 'fitChecks': fits}, ensure_ascii=False, indent=2))
