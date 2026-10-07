"""Read-only source/evidence audit. Standard library only; no product imports."""
from pathlib import Path
import ast
import hashlib
import json
import re
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
OLD = 'docs/evidence/m4-authoring-interaction-work/'
NEW = 'docs/evidence/m4-draft-merge-routing-work/browser-attempt-2/'
inputs = [
    'AGENTS.md', 'skills/archcanvas/SKILL.md',
    'src/archcanvas_authoring/draft.py',
    'studio/src/AuthoringStudio.tsx', 'studio/src/AuthoringStudio.css',
    'studio/src/authoring.ts', 'studio/src/authoringPresets.ts',
    'studio/src/draftPortPresentation.ts', 'studio/src/api.ts',
    OLD + 'browser-final-manifest-attempt-1.json',
    OLD + 'actual-artifacts-attempt-1/manifest.json',
]
inputs += [OLD + 'browser-attempt-1/' + name for name in [
    'blank-four-before-connections.dom.txt', 'blank-four-before-connections.public.json',
    'label-first-pending.public.json', 'label-first-connected.public.json',
    'circle-drag-second-connected.public.json', 'keyboard-third-pending.public.json',
    'keyboard-third-connected.public.json', 'duplicate-rejected.public.json',
    'undo-third.public.json', 'redo-third.public.json',
    'vertical-save-settled.public.json', 'vertical-final-reopened-after.public.json',
    'arrange-horizontal.public.json', 'arrange-undone-vertical.public.json',
    'vertical-generated.dom.txt', 'vertical-generated-source-visible.py',
    'vertical-100-canceled-v2.public.json',
    'mlp-saved-settled.public.json', 'mlp-generated.dom.txt', 'mlp-generated-source-visible.py',
    'cnn-drag-before-empty.public.json', 'cnn-preset-native-drag-fit-after.public.json',
    'cnn-saved-settled.public.json', 'cnn-generated.dom.txt', 'cnn-generated-source-visible.py',
    'residual-saved-settled.public.json',
    'vertical-four-connected.jpg', 'cnn-preset-native-drag-fit.jpg',
]]
inputs += [OLD + 'actual-artifacts-attempt-1/' + name for name in [
    'vertical-draft-envelope.json', 'vertical-model.py',
    'mlp-draft-envelope.json', 'cnn-draft-envelope.json', 'residual-draft-envelope.json',
]]
inputs += [NEW + name for name in [
    'manifest.json', 'merge-complete-fit.public.json', 'generated-source.py',
    'merge-clear-after-generation.jpg', 'merge-clear-after-generation.ax.txt',
]]

def binding(path, data=None):
    data = (ROOT / path).read_bytes() if data is None else data
    return {'path': path, 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}

# New directory is intentionally one-shot: do not silently overwrite a receipt.
assert not (OUT / 'receipt.json').exists(), 'Use a fresh audit attempt.'
snapshots = {}
records = []
for path in inputs:
    data = (ROOT / path).read_bytes()
    snapshots[path] = data
    copy = OUT / 'inputs' / path
    copy.parent.mkdir(parents=True, exist_ok=True)
    copy.write_bytes(data)
    records.append({**binding(path, data), 'snapshot': str(copy.relative_to(ROOT))})

def read(path):
    return snapshots[path].decode()

def public(name):
    return json.loads(read(OLD + 'browser-attempt-1/' + name + '.public.json'))

checks = []
def check(name, passed, facts):
    checks.append({'check': name, 'passed': bool(passed), 'facts': facts})

tree = ast.parse(read('src/archcanvas_authoring/draft.py'))
catalog = next(n.value for n in tree.body if isinstance(n, ast.Assign)
               and any(isinstance(t, ast.Name) and t.id == '_CATALOG' for t in n.targets))
kinds = [ast.literal_eval(call.args[0]) for call in catalog.elts]
categories = [ast.literal_eval(call.args[1]) for call in catalog.elts]
expected = ['Input', 'Output', 'Linear', 'ReLU', 'GELU', 'SiLU', 'Identity', 'Dropout', 'Flatten',
            'Conv2d', 'MaxPool2d', 'AdaptiveAvgPool2d', 'BatchNorm2d', 'LayerNorm', 'Embedding', 'Add', 'Concat']
dom = read(OLD + 'browser-attempt-1/blank-four-before-connections.dom.txt')
visible = re.findall(r'^  - button "添加 ([^\"]+)":', dom, re.M)
visible_kinds = [kind for kind in visible if kind in expected]
check('catalog-and-visible-library', kinds == expected and visible_kinds == expected and len(set(categories)) == 11,
      {'catalogKinds': kinds, 'visibleBasicKinds': visible_kinds, 'categories': sorted(set(categories)),
       'visibleStartingGraphs': [s for s in visible if s not in expected]})

presets = read('studio/src/authoringPresets.ts')
preset_counts = []
for identity, next_identity, nodes, edges in [('mlp', 'cnn', 5, 4), ('cnn', 'residual-mlp', 8, 7), ('residual-mlp', None, 6, 6)]:
    start = presets.index("{ id: '" + identity + "'")
    end = presets.index("{ id: '" + next_identity + "'", start) if next_identity else presets.index('\n];', start)
    chunk = presets[start:end]
    item = {'id': identity, 'nodes': len(re.findall(r'\{ key:', chunk)), 'edges': len(re.findall(r'\{ source:', chunk))}
    preset_counts.append(item)
check('three-transparent-presets', [(i['nodes'], i['edges']) for i in preset_counts] == [(5,4),(8,7),(6,6)], preset_counts)

chain_names = ['blank-four-before-connections', 'label-first-connected', 'circle-drag-second-connected',
               'keyboard-third-connected', 'duplicate-rejected', 'undo-third', 'redo-third',
               'vertical-save-settled', 'vertical-final-reopened-after']
chain_counts = [{'observation': n, 'nodes': len(public(n)['nodes']), 'edges': len(public(n)['edges'])} for n in chain_names]
check('bounded-empty-chain-lifecycle-counts', all(i['nodes'] == 4 for i in chain_counts)
      and [i['edges'] for i in chain_counts] == [0,1,2,3,3,2,3,3,3], chain_counts)

envelopes = {}
for label, name, nc, ec in [('vertical','vertical',4,3),('mlp','mlp',5,4),('cnn','cnn',8,7),('residual','residual',6,6)]:
    path = OLD + 'actual-artifacts-attempt-1/' + name + '-draft-envelope.json'
    envelope = json.loads(read(path)); d = envelope['draft']; envelopes[label] = d
    check('saved-' + label + '-graph', len(d['nodes']) == nc and len(d['edges']) == ec,
          {'source': path, 'storageRevision': envelope['revision'], 'draftRevision': d['revision'],
           'kinds': [n['kind'] for n in d['nodes']], 'nodes': nc, 'edges': ec})

chain = envelopes['vertical']; nodes = chain['nodes']; byid = {n['id']: n for n in nodes}
expected_edges = [(nodes[i]['id'], 'output', nodes[i+1]['id'], 'input') for i in range(3)]
actual_edges = [(e['source']['nodeId'],e['source']['portId'],e['target']['nodeId'],e['target']['portId']) for e in chain['edges']]
check('saved-chain-declared-facts', actual_edges == expected_edges
      and [n['kind'] for n in nodes] == ['Input','Linear','GELU','Output']
      and nodes[0]['parameters'] == {'shape':[1,16],'dtype':'float32'}
      and nodes[1]['parameters']['in_features'] == 16 and nodes[1]['parameters']['out_features'] == 8,
      {'bindings': actual_edges, 'declaredShapes': [[1,16],[1,8],[1,8],[1,8]], 'modelExecution': 'not_run'})
check('visible-source-equals-managed-source', snapshots[OLD + 'browser-attempt-1/vertical-generated-source-visible.py']
      == snapshots[OLD + 'actual-artifacts-attempt-1/vertical-model.py'], {'byteEquality': True})

preset_obs = [{'name':n,'nodes':len(public(n)['nodes']),'edges':len(public(n)['edges'])} for n in
              ['cnn-drag-before-empty','cnn-preset-native-drag-fit-after','cnn-saved-settled','mlp-saved-settled','residual-saved-settled']]
check('bounded-preset-public-counts', [(i['nodes'],i['edges']) for i in preset_obs] == [(0,0),(8,7),(8,7),(5,4),(6,6)], preset_obs)

visible_sources = {}
for name in ['vertical', 'mlp', 'cnn']:
    source = read(OLD + 'browser-attempt-1/' + name + '-generated-source-visible.py')
    ast.parse(source)  # Parsing only; no code import or execution.
    visible_sources[name] = {'syntacticallyValid': True, 'bytes': len(source.encode())}
check('generated-source-parses-only', True, visible_sources)

ui = read('studio/src/AuthoringStudio.tsx')
check('implemented-click-drop-and-visual-instructions', all(token in ui for token in [
    "onClick={() => add(module)}", "application/x-archcanvas-module", "onDrop={event =>",
    "application/x-archcanvas-preset", "onClick={() => addPreset(preset)}", "每一步都在图上完成"]),
    {'scope':'source interface only, not all-module native gesture testing'})

merge = json.loads(read(NEW + 'merge-complete-fit.public.json'))
check('current-bounded-merge-public-counts', len(merge['nodes']) == 5 and len(merge['edges']) == 5,
      {'nodes':len(merge['nodes']), 'edges':len(merge['edges']), 'zoom':merge['zoom'],
       'fanoutPath':merge['edges'][3]['path'], 'minimumBendGuarantee':False})

# Validate only selected raw observations against manifests; the full raw manifests
# are bound, but unselected records do not receive semantic or visual review here.
raw_records = {}
for path in [OLD + 'browser-final-manifest-attempt-1.json', NEW + 'manifest.json']:
    for item in json.loads(read(path))['records']:
        raw_records[item['path']] = item
selected_raw = [r for r in records if r['path'] in raw_records]
check('selected-raw-manifest-bindings', all((r['bytes'],r['sha256']) == (raw_records[r['path']]['bytes'],raw_records[r['path']]['sha256']) for r in selected_raw),
      {'selectedRawFiles':len(selected_raw), 'allRawSemanticsReviewed':False})

unchanged = [path for path in inputs if binding(path) != binding(path, snapshots[path])]
copy_failures = [r['snapshot'] for r in records if (ROOT / r['snapshot']).read_bytes() != snapshots[r['path']]]
check('exact-source-and-snapshot-readback', not unchanged and not copy_failures,
      {'inputs':len(inputs), 'changedInputs':unchanged, 'failedCopies':copy_failures})

receipt = {
    'protocol':'archcanvas-novice-palette-readonly-ai-review/1',
    'createdAt':datetime.now(timezone.utc).isoformat(),
    'reviewer':'independent AI subagent novice_palette_review',
    'humanParticipants':0, 'm4Status':'partial', 'modelsExecuted':False, 'dependenciesInstalled':False,
    'sharedBrowserOperated':False, 'productFilesWritten':False,
    'scope':'Current source plus selected frozen evidence; old ye7sAyyI native trials and current BSA5RjBV merge frame are distinct scopes.',
    'personallyViewedImages':[OLD+'browser-attempt-1/vertical-four-connected.jpg',OLD+'browser-attempt-1/cnn-preset-native-drag-fit.jpg',NEW+'merge-clear-after-generation.jpg'],
    'externalDLPlaygroundReviewed':False,
    'limitations':[
        'AI is not human novice acceptance.', 'No per-module native generation or click/drag matrix.',
        'Residual preset was saved but not generated in the cited native trial.',
        'Current merge generated source was not opened as a new managed figure in this round.',
        'Small port labels and long CNN/merge return routes remain visible.',
        'No global aesthetics, minimum-bend, publication or runtime certification.',
    ],
    'observerFailures':['Initial reviewer search used absent archcanvas_runtime/ directory; corrected to src/archcanvas_authoring/draft.py.',
                        'Initial reviewer tried absent mlp-generated.public.json; corrected to frozen visible DOM/source, without creating replacement evidence.'],
    'inputBindings':records,
    'checks':checks, 'passed':all(c['passed'] for c in checks),
    'outputs':[binding(str((OUT/'README.md').relative_to(ROOT))), binding(str(Path(__file__).resolve().relative_to(ROOT)))],
}
(OUT / 'receipt.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2)+'\n')
print(json.dumps({'receipt':str((OUT/'receipt.json').relative_to(ROOT)), 'checks':len(checks),
                  'passed':receipt['passed'],'inputBindings':len(records),
                  'failed':[c for c in checks if not c['passed']]},ensure_ascii=False))
