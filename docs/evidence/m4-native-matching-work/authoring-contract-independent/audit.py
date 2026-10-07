#!/usr/bin/env python3
"""Read-only authoring evidence audit, using authored topology and Python AST.

This does not import a product module, generate a model, operate a browser or
execute captured source. Images are hash-bound only; no pixel claim is made.
"""

from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
import argparse
import ast
import hashlib
import json
import math
from pathlib import Path
import re


PROJECT = Path(__file__).resolve().parents[4]
WORK = PROJECT / "docs/evidence/m4-native-matching-work"
RAW = WORK / "authoring-smoke"
ARTIFACTS = WORK / "authoring-artifacts"
LOG = []


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def binding(path):
    return {"path": str(path.relative_to(PROJECT)), "bytes": path.stat().st_size, "sha256": sha(path)}


def frame(name):
    return load(RAW / (name + ".public.json"))


def geometry(value):
    return {"nodes": value["nodes"], "edges": value["edges"]}


NUMBER = r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?"


def point(transform):
    match = re.fullmatch(r"translate\((" + NUMBER + r") (" + NUMBER + r")\)", transform)
    require(match is not None, "Unexpected public node transform")
    return tuple(float(value) for value in match.groups())


def camera(transform):
    match = re.fullmatch(r"translate\((" + NUMBER + r") (" + NUMBER + r")\) scale\((" + NUMBER + r")\)", transform)
    require(match is not None, "Unexpected public camera transform")
    return tuple(float(value) for value in match.groups())


def close(actual, expected, tolerance=1e-9):
    return len(actual) == len(expected) and all(math.isfinite(a) and abs(a - b) <= tolerance for a, b in zip(actual, expected))


def path_points(value):
    tokens = re.findall(r"[MHV]|" + NUMBER, value)
    require(" ".join(tokens) == " ".join(value.split()), "Unsupported public route syntax")
    result, index = [], 0
    while index < len(tokens):
        command = tokens[index]
        index += 1
        if command == "M":
            require(not result, "Multiple route moves")
            result.append((float(tokens[index]), float(tokens[index + 1])))
            index += 2
        elif command == "H":
            require(bool(result), "Route horizontal before move")
            result.append((float(tokens[index]), result[-1][1]))
            index += 1
        elif command == "V":
            require(bool(result), "Route vertical before move")
            result.append((result[-1][0], float(tokens[index])))
            index += 1
        else:
            raise AssertionError("Unsupported route command")
    require(len(result) >= 2 and all(math.isfinite(value) for pair in result for value in pair), "Invalid route coordinates")
    return result


def draft_contract(draft, kind):
    expected_kinds = ["Input", "Linear", "GELU", "Output"] if kind == "four" else ["Input", "Linear", "ReLU", "Linear", "Add", "Output"]
    expected_parameters = ([{"shape": [1, 16], "dtype": "float32"}, {"in_features": 16, "out_features": 32, "bias": True}, {"approximate": "none"}, {}]
                           if kind == "four" else [{"shape": [1, 16], "dtype": "float32"}, {"in_features": 16, "out_features": 32, "bias": True}, {},
                                                  {"in_features": 32, "out_features": 16, "bias": True}, {}, {}])
    expected_relations = ([(0, "output", 1, "input"), (1, "output", 2, "input"), (2, "output", 3, "input")]
                          if kind == "four" else [(0, "output", 1, "input"), (1, "output", 2, "input"), (2, "output", 3, "input"),
                                                 (3, "output", 4, "left"), (0, "output", 4, "right"), (4, "output", 5, "input")])
    require(draft["schemaVersion"] == 1 and draft["mode"] == "authored-draft", "Draft contract differs")
    require([node["kind"] for node in draft["nodes"]] == expected_kinds, kind + ": complete node inventory differs")
    require([node["parameters"] for node in draft["nodes"]] == expected_parameters, kind + ": parameter inventory differs")
    node_ids = [node["id"] for node in draft["nodes"]]
    require(len(set(node_ids)) == len(node_ids), kind + ": duplicate node identity")
    index = {identity: offset for offset, identity in enumerate(node_ids)}
    observed = [(index[edge["source"]["nodeId"]], edge["source"]["portId"], index[edge["target"]["nodeId"]], edge["target"]["portId"]) for edge in draft["edges"]]
    require(Counter(observed) == Counter(expected_relations), kind + ": complete port/producer graph differs")
    require(len({edge["id"] for edge in draft["edges"]}) == len(expected_relations), kind + ": duplicate edge identity")
    expected_positions = ([(50 + 248 * index, 70) for index in range(4)] if kind == "four" else [(72 + 248 * index, 172) for index in range(6)])
    require([(node["position"]["x"], node["position"]["y"]) for node in draft["nodes"]] == expected_positions, kind + ": saved positions differ")
    return expected_relations


def public_contract(public, draft):
    wanted = [{"id": node["id"], "kind": node["kind"], "label": node["label"],
               "transform": f'translate({node["position"]["x"]} {node["position"]["y"]})'} for node in draft["nodes"]]
    require(public["nodes"] == wanted, "Public node/label/position inventory differs from actual draft")
    require([edge["id"] for edge in public["edges"]] == [edge["id"] for edge in draft["edges"]], "Public/actual draft edge identities differ")
    check_endpoints(public, draft)


def check_endpoints(public, draft):
    nodes = {node["id"]: node for node in public["nodes"]}
    positions = {identity: point(node["transform"]) for identity, node in nodes.items()}
    routes = {edge["id"]: edge["path"] for edge in public["edges"]}
    for edge in draft["edges"]:
        source, target = edge["source"], edge["target"]
        sx, sy = positions[source["nodeId"]]
        tx, ty = positions[target["nodeId"]]
        # Authored public-port contract for these examples: card width 176;
        # unary/output center at y+66; Add left/right inputs at y+60/y+72.
        target_offset = {"left": 60, "right": 72}[target["portId"]] if nodes[target["nodeId"]]["kind"] == "Add" else 66
        points = path_points(routes[edge["id"]])
        require(points[0] == (sx + 176, sy + 66), "Route producer endpoint differs")
        require(points[-1] == (tx, ty + target_offset), "Route consumer/port endpoint differs")


def attribute(node, root, member):
    return isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id == root and node.attr == member


def constructor_keywords(call):
    require(not call.args and all(keyword.arg is not None for keyword in call.keywords), "Unexpected constructor args/unpack")
    result = {}
    for keyword in call.keywords:
        require(keyword.arg not in result, "Duplicate constructor keyword")
        result[keyword.arg] = "torch.float32" if attribute(keyword.value, "torch", "float32") else ast.literal_eval(keyword.value)
    return result


def ast_contract(source, draft, kind):
    tree = ast.parse(source)
    require(len(tree.body) == 4 and isinstance(tree.body[0], ast.Expr) and isinstance(tree.body[0].value, ast.Constant), "Source module inventory differs")
    require(isinstance(tree.body[1], ast.Import) and [(item.name, item.asname) for item in tree.body[1].names] == [("torch", None)], "Torch declaration differs")
    require(isinstance(tree.body[2], ast.ImportFrom) and tree.body[2].module == "torch" and tree.body[2].level == 0 and [(item.name, item.asname) for item in tree.body[2].names] == [("nn", None)], "nn declaration differs")
    model = tree.body[3]
    require(isinstance(model, ast.ClassDef) and model.name == "AuthoredModel" and not model.decorator_list and not model.keywords and len(model.bases) == 1 and attribute(model.bases[0], "nn", "Module"), "Authored class declaration differs")
    require([node.name for node in model.body if isinstance(node, ast.FunctionDef)] == ["__init__", "forward"] and len(model.body) == 2, "Complete method inventory differs")
    initializer, forward = model.body
    require(ast.unparse(initializer.body[0]) == "super().__init__()", "Initializer base call differs")
    expected_ops = ([('Linear', {'in_features': 16, 'out_features': 32, 'bias': True, 'dtype': 'torch.float32'}), ('GELU', {'approximate': 'none'})]
                    if kind == 'four' else [('Linear', {'in_features': 16, 'out_features': 32, 'bias': True, 'dtype': 'torch.float32'}),
                                           ('ReLU', {}), ('Linear', {'in_features': 32, 'out_features': 16, 'bias': True, 'dtype': 'torch.float32'})])
    require(len(initializer.body) == len(expected_ops) + 1, "Complete constructor inventory differs")
    symbols = []
    for statement, (operation, parameters) in zip(initializer.body[1:], expected_ops):
        require(isinstance(statement, ast.Assign) and len(statement.targets) == 1 and isinstance(statement.targets[0], ast.Attribute) and isinstance(statement.targets[0].value, ast.Name) and statement.targets[0].value.id == 'self', "Constructor target differs")
        require(isinstance(statement.value, ast.Call) and attribute(statement.value.func, 'nn', operation), "Constructor kind differs")
        require(constructor_keywords(statement.value) == parameters, "Constructor parameter/dtype differs")
        symbols.append(statement.targets[0].attr)
    require(len(set(symbols)) == len(symbols), "Constructor symbol identity collision")
    arguments = forward.args
    require(len(arguments.args) == 2 and arguments.args[0].arg == 'self' and not arguments.posonlyargs and not arguments.kwonlyargs and not arguments.defaults and arguments.vararg is None and arguments.kwarg is None, "Forward input contract differs")
    input_symbol = arguments.args[1].arg
    require(len(forward.body) == len(expected_ops) + (1 if kind == 'four' else 2), "Complete forward statement inventory differs")
    producer = input_symbol
    relations = []
    for index, symbol in enumerate(symbols):
        statement = forward.body[index]
        require(isinstance(statement, ast.Assign) and len(statement.targets) == 1 and isinstance(statement.targets[0], ast.Name) and statement.targets[0].id == symbol, "Forward output symbol differs")
        call = statement.value
        require(isinstance(call, ast.Call) and attribute(call.func, 'self', symbol) and not call.keywords and len(call.args) == 1 and isinstance(call.args[0], ast.Name) and call.args[0].id == producer, "Forward operation input/producer differs")
        relations.append([producer, symbol])
        producer = symbol
    if kind == 'residual':
        addition = forward.body[-2]
        require(isinstance(addition, ast.Assign) and len(addition.targets) == 1 and isinstance(addition.targets[0], ast.Name), "Add declaration differs")
        add = addition.value
        require(isinstance(add, ast.BinOp) and isinstance(add.op, ast.Add) and isinstance(add.left, ast.Name) and add.left.id == producer and isinstance(add.right, ast.Name) and add.right.id == input_symbol, "Residual left/right source producers differ")
        producer = addition.targets[0].id
        relations.extend([[symbols[-1], producer + ':left'], [input_symbol, producer + ':right']])
    returned = forward.body[-1]
    require(isinstance(returned, ast.Return) and isinstance(returned.value, ast.Dict) and len(returned.value.keys) == 1 and isinstance(returned.value.keys[0], ast.Constant) and returned.value.keys[0].value == draft['nodes'][-1]['id'] and isinstance(returned.value.values[0], ast.Name) and returned.value.values[0].id == producer, "Output key/producer differs")
    return {'operatorKinds': [operation for operation, _ in expected_ops], 'constructorParameters': [parameters for _, parameters in expected_ops],
            'inputSymbol': input_symbol, 'orderedProducerRelations': relations, 'outputKey': draft['nodes'][-1]['id'], 'outputProducer': producer,
            'sourceSha256': hashlib.sha256(source.encode('utf-8')).hexdigest(), 'parsedOnly': True}


def source_in_dom(name, source):
    values = []
    for line in (RAW / (name + '.dom.txt')).read_text(encoding='utf-8').splitlines():
        text = line.strip()
        if text.startswith('- generic: "'):
            try:
                values.append(json.loads(text.removeprefix('- generic: ')))
            except json.JSONDecodeError:
                pass
    require(' '.join(source.split()) in values, name + ': source generic differs from public source')


def run(output):
    require(not (output / 'report.json').exists(), 'Use a new output directory; old reports are not overwritten')
    started = datetime.now(timezone.utc).isoformat()
    manifest = load(RAW / 'manifest.json')
    receipt = load(RAW / 'receipt.json')
    artifact_manifest = load(ARTIFACTS / 'manifest.json')
    checks = load(WORK / 'checks-final/receipt.json')
    paths = [PROJECT / item['path'] for item in manifest['rawFiles']] + [RAW / 'manifest.json', ARTIFACTS / 'manifest.json', WORK / 'checks-final/receipt.json']
    paths += [PROJECT / item['copy'] for item in artifact_manifest['files']]
    paths += [PROJECT / item['path'] for item in checks['build']]
    paths += [PROJECT / 'studio/package.json', PROJECT / 'studio/package-lock.json']
    paths = sorted(set(paths))
    before = [binding(path) for path in paths]
    for item in manifest['rawFiles']:
        require(binding(PROJECT / item['path']) == item, 'Raw file manifest binding differs')
    require(manifest['frameCount'] == 43 and receipt['rawFileCount'] == 129 and len(receipt['frames']) == 43 and len(set(receipt['frames'])) == 43, 'Frame/receipt inventory differs')
    expected_raw = {str((RAW / (name + suffix)).relative_to(PROJECT)) for name in receipt['frames'] for suffix in ('.public.json', '.dom.txt', '.jpg')}
    require({item['path'] for item in manifest['rawFiles']} == expected_raw | {str((RAW / 'receipt.json').relative_to(PROJECT))}, 'Manifest is not 129 frame files plus receipt')
    live_artifacts = []
    for item in artifact_manifest['files']:
        path = PROJECT / item['copy']
        require(path.stat().st_size == item['bytes'] and sha(path) == item['sha256'], 'Artifact copy binding differs')
        original = Path(item['source'])
        live_artifacts.append({'source': str(original), 'exists': original.exists(), 'exactByteMatch': original.read_bytes() == path.read_bytes() if original.exists() else None})
        require(not original.exists() or original.read_bytes() == path.read_bytes(), 'Live authored artifact differs from snapshot')
    for item in checks['build']:
        require(binding(PROJECT / item['path']) == item, 'Current build digest differs')
    for name in ('studio/package.json', 'studio/package-lock.json'):
        expected = next(item for item in checks['inputs'] if item['path'] == name)
        require(binding(PROJECT / name) == expected, 'Current package binding differs')
    require(all(frame(name)['assets'] == ['/assets/index-D60-bDcz.js'] for name in receipt['frames']), 'Observed browser JS asset differs')
    LOG.append('PASS 43 frames / 129 raw files + one receipt binding; 4 actual artifacts; current build/package selected bindings')
    drafts = [load(PROJECT / item['copy']) for item in artifact_manifest['files'] if '/drafts/' in item['copy']]
    require(len(drafts) == 2 and all(value['revision'] == 1 for value in drafts), 'Saved draft envelope inventory differs')
    four = next(value['draft'] for value in drafts if len(value['draft']['nodes']) == 4)
    residual = next(value['draft'] for value in drafts if len(value['draft']['nodes']) == 6)
    require(four['revision'] == 8 and residual['revision'] == 17, 'Saved inner draft revisions differ')
    four_relations, residual_relations = draft_contract(four, 'four'), draft_contract(residual, 'residual')
    require(not frame('empty')['nodes'] and not frame('empty')['edges'], 'Blank starting capture is not empty')
    require([node['kind'] for node in frame('four-added')['nodes']] == ['Input', 'Linear', 'GELU', 'Output'] and not frame('four-added')['edges'], 'Added-node public inventory differs')
    for name in ('four-check-settled', 'four-saved', 'four-reopened', 'four-generated'):
        public_contract(frame(name), four)
    require(geometry(frame('four-saved')) == geometry(frame('four-reopened')), 'Blank saved/reopened public geometry differs')
    require(frame('four-saved')['camera'] == frame('four-reopened')['camera'], 'Blank camera changed on saved/reopen sample')
    require(frame('four-connected-checked')['status'] == '正在检查模型…', 'Intermediate checking state changed')
    require(frame('four-check-settled')['status'] == '静态检查通过；声明形状与连接相容，模型尚未执行。', 'Settled static-check result missing')
    four_source = frame('four-generated')['source']
    four_ast = ast_contract(four_source, four, 'four')
    source_in_dom('four-generated', four_source)
    source_path = next(PROJECT / item['copy'] for item in artifact_manifest['files'] if item['copy'].endswith('/source/model.py'))
    require(source_path.read_text(encoding='utf-8') == four_source, 'Actual managed source differs from public generated source')
    metadata_path = next(PROJECT / item['copy'] for item in artifact_manifest['files'] if item['copy'].endswith('/project.json'))
    metadata = load(metadata_path)
    require(metadata == {'id': metadata_path.parent.name, 'entry': 'model:AuthoredModel', 'scope': 'managed-copy'}, 'Managed project identity/entry/scope differs')
    managed_dom = (RAW / 'four-managed.dom.txt').read_text(encoding='utf-8')
    require('tree "模型层级"' in managed_dom and 'AuthoredModel' in managed_dom and '16 → 32' in managed_dom and 'GELU 激活' in managed_dom and '"5"\n  - generic: 事实对象\n  - generic: "4"\n  - generic: 端口关系' in managed_dom, 'Opened managed AX source facts missing')
    require('已打开草稿生成的新模型工作副本' in frame('four-managed')['status'], 'Managed open feedback missing')
    LOG.append('PASS blank chain: 4 nodes / 3 directed port relations, Input[1,16] float32 / Linear16→32 / GELU / Output; save/reopen geometry exact; actual managed source equals public generated source and hand AST')
    for name in ('residual-base', 'residual-checked', 'residual-node-restored', 'residual-saved', 'residual-reopened', 'residual-generated', 'residual-final-preview'):
        public_contract(frame(name), residual)
    require(geometry(frame('residual-saved')) == geometry(frame('residual-reopened')), 'Residual saved/reopened public geometry differs')
    residual_source = frame('residual-generated')['source']
    residual_ast = ast_contract(residual_source, residual, 'residual')
    source_in_dom('residual-generated', residual_source)
    LOG.append('PASS residual: 6 nodes / 6 directed port relations, Linear16→32 / ReLU / Linear32→16 / Add left=projection right=input / Output; save/reopen exact; public/AX generated source hand AST passes; managed residual not opened')
    baseline = frame('residual-base')
    add = next(node for node in baseline['nodes'] if node['kind'] == 'Add')
    add_id, add_position = add['id'], point(add['transform'])
    node_moves = []
    directions = {'left': (-16, 0), 'right': (16, 0), 'up': (0, -16), 'down': (0, 16)}
    incident = {edge['id'] for edge in residual['edges'] if add_id in (edge['source']['nodeId'], edge['target']['nodeId'])}
    base_paths = {edge['id']: edge['path'] for edge in baseline['edges']}
    for name, delta in directions.items():
        moved, undone, redone = (frame('residual-node-' + name + suffix) for suffix in ('', '-undo', '-redo'))
        for node, original in zip(moved['nodes'], baseline['nodes']):
            require(node.keys() == original.keys(), 'Moved node fields differ')
            if node['id'] == add_id:
                require({key: value for key, value in node.items() if key != 'transform'} == {key: value for key, value in original.items() if key != 'transform'}, 'Add identity/label/kind differs after move')
                require(point(node['transform']) == (add_position[0] + delta[0], add_position[1] + delta[1]), 'Four-direction Add delta differs')
            else:
                require(node == original, 'Unrelated node changed during Add move')
        check_endpoints(moved, residual)
        moved_paths = {edge['id']: edge['path'] for edge in moved['edges']}
        require(set(moved_paths) == set(base_paths) and all(moved_paths[identity] == path for identity, path in base_paths.items() if identity not in incident), 'Nonincident route changed during Add move')
        require(geometry(undone) == geometry(baseline) and geometry(redone) == geometry(moved), 'Undo/redo did not exactly restore captured public geometry')
        require(moved['camera'] == baseline['camera'] == undone['camera'] == redone['camera'], 'Node move altered camera')
        node_moves.append({'direction': name, 'inputKind': 'keyboard-per-bound-operation-receipt', 'expectedWorldDelta': list(delta), 'actualWorldPosition': list(point(next(node['transform'] for node in moved['nodes'] if node['id'] == add_id))), 'undoPublicGeometryExact': True, 'redoPublicGeometryExact': True, 'nonincidentRoutesExact': True, 'portEndpointsExact': True})
    require(geometry(frame('residual-node-restored')) == geometry(baseline), 'Final node-restored geometry differs')
    LOG.append('PASS Add four keyboard directions ±16 world; unrelated node geometry/nonincident routes stable; captured undo/redo/restored exact')
    base_camera = camera(frame('residual-camera-base')['camera'])
    camera_moves = []
    for name, delta in {'left': (-40, 0), 'right': (40, 0), 'up': (0, -40), 'down': (0, 40)}.items():
        moved = frame('residual-camera-' + name)
        returned_name = 'residual-camera-right-return-settled' if name == 'right' else 'residual-camera-' + name + '-return'
        returned = frame(returned_name)
        require(geometry(moved) == geometry(baseline) == geometry(returned), 'Camera pan mutated model public geometry')
        actual = camera(moved['camera'])
        require(close(actual, (base_camera[0] + delta[0], base_camera[1] + delta[1], base_camera[2])), 'Camera direction does not match 40 CSS-unit translation')
        require(close(camera(returned['camera']), base_camera), 'Settled camera return differs beyond 1e-9')
        camera_moves.append({'direction': name, 'inputKind': 'CUA-drag-per-bound-operation-receipt', 'expectedCssTranslation': list(delta), 'actualCamera': list(actual), 'returnedFrame': returned_name, 'returnTolerance': 1e-9, 'modelGeometryExact': True})
    camera_failures = []
    for name, residual_x in [('residual-camera-right-return', 30), ('residual-camera-right-return-recovered', 10)]:
        public = frame(name)
        require(geometry(public) == geometry(baseline), 'Incomplete camera return mutated model geometry')
        observed = camera(public['camera'])
        require(close(observed, (base_camera[0] + residual_x, base_camera[1], base_camera[2])), 'Retained incomplete return delta differs')
        camera_failures.append({'frame': name, 'observedResidualCssX': residual_x, 'observedCamera': list(observed), 'successfulReturn': False})
    require(not frame('residual-drag-attempt-no-change')['nodes'] and not frame('residual-drag-attempt-no-change')['edges'], 'Failed initial preset drag no longer shows empty draft')
    LOG.append('PASS camera four reported CUA-drag directions ±40 CSS translate; returns within1e-9 after explicit recovery; retained incomplete +30/+10 not recast as success')
    after = [binding(path) for path in paths]
    require(before == after, 'Input bytes changed across independent readback')
    report = {'schemaVersion': 1, 'startedAt': started, 'finishedAt': datetime.now(timezone.utc).isoformat(),
              'status': 'passed-bounded-contract-with-retained-operation-failures', 'scope': 'Read-only public DOM/draft/generated-AST contract audit for two current authoring browser flows; no pixel, native paint or human acceptance certification',
              'actorKind': receipt['actorKind'], 'humanParticipants': receipt['humanParticipants'], 'frames': 43, 'frameRawFiles': 129, 'manifestBindingsIncludingReceipt': 130,
              'blank': {'nodeCount': 4, 'edgeCount': 3, 'innerDraftRevision': four['revision'], 'storageRevision': 1, 'authoredRelationsByNodeIndex': four_relations, 'savedReopenedPublicGeometryExact': True, 'generatedAst': four_ast, 'actualManagedSourceEqualsPublicSource': True, 'managedMetadata': metadata, 'managedAXFacts': {'objects': 5, 'portRelations': 4}, 'managedGeometryCaptured': False},
              'residual': {'nodeCount': 6, 'edgeCount': 6, 'innerDraftRevision': residual['revision'], 'storageRevision': 1, 'authoredRelationsByNodeIndex': residual_relations, 'savedReopenedPublicGeometryExact': True, 'generatedAst': residual_ast, 'sourceOrigin': 'public generated source plus AX dialog only', 'managedOpened': False},
              'nodeMoves': node_moves, 'cameraMoves': camera_moves, 'retainedIncompleteCameraReturns': camera_failures,
              'liveSelectedArtifactReadback': live_artifacts, 'currentBuildBindings': checks['build'], 'rawBindingsStable': True, 'inputsBefore': before, 'inputsAfter': after,
              'notInspected': {'pixels': True, 'all17Kinds': True, 'publicationExport': True, 'nativeInputEventTrace': True, 'actualPaintOrFps': True, 'runtimeModel': True, 'humanTasks': True},
              'retainedReceiptFailures': receipt['failures'],
              'limitations': ['Images are hash-bound only; this agent did not open images and does not certify pixel/DOM synchrony, arrow beauty or final publication readability.',
                              'Node moves are keyboard samples; camera input mode is reported by the bound CUA operation receipt. Public transform deltas are measured; no raw trusted-pointer event trace, intermediate drag frames or native latency is certified.',
                              'Public captures expose node identity/kind/label/transform and route id/path only. Equality claims cover those fields, not a complete CanvasDocument, hidden model properties or general scene contracts.',
                              'Four-managed public nodes/edges are empty because that capture queried draft selectors; opened managed AX tree/status, actual metadata and source are verified without inventing managed geometry.',
                              'Residual generated source is public/AX only; no actual residual managed file/opened managed scene is claimed.',
                              'The intermediate checking frame, unsuccessful clipped-card drag and +30/+10 incomplete camera returns remain retained failures; final explicit recovery does not erase them.',
                              'AST source is parsed as data only. No product module or generated model is imported/executed; concrete runtime shape/numerical/forward/backward behavior remains unverified.',
                              'This is automation with zero humans; it cannot certify 17-kind complete workflows, performance, publication or M4 research acceptance.'],
              'auditScriptSha256': sha(Path(__file__).resolve())}
    output.mkdir(parents=True, exist_ok=True)
    (output / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    (output / 'audit.log').write_text('\n'.join(LOG) + '\n', encoding='utf-8')
    print(json.dumps({'status': report['status'], 'report': str(output / 'report.json'), 'inputBindings': len(before)}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path(__file__).resolve().parent)
    run(parser.parse_args().output.resolve())
