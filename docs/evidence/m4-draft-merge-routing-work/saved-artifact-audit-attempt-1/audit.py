"""Independent saved-file / public-SVG / Python-AST readback; never imports a model."""
from pathlib import Path
from itertools import combinations
import ast
import hashlib
import json
import re
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
RAW = ROOT / "docs/evidence/m4-draft-merge-routing-work/browser-attempt-2"
STORE = ROOT / ".archcanvas/m4-authoring-preview-20261006-attempt-1"
SOURCE = RAW / "generated-source.py"
SAVED = STORE / "drafts/draft-7c9ff26a-8ab1-4d90-8bb7-a65e26728a7f.json"
STEMS = ["merge-complete-fit", "node-right-16", "node-left-16", "node-up-16",
         "node-down-16", "node-base-restored", "pan-right-40", "pan-left-40",
         "pan-up-40", "pan-down-40", "merge-reopened"]


def binding(path):
    data = path.read_bytes()
    return {"path": str(path.relative_to(ROOT)), "bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest()}


manifest = json.loads((RAW / "manifest.json").read_text())
raw_before = [binding(ROOT / item["path"]) for item in manifest["records"]]
assert raw_before == manifest["records"], "Frozen raw manifest mismatch"
paths = [SAVED, SOURCE, RAW / "manifest.json", RAW / "generated.dom.txt",
         RAW / "merge-reopened.ax.txt"]
paths += [RAW / f"{stem}.public.json" for stem in STEMS]
paths += [ROOT / name for name in ["src/archcanvas_cli/server.py", "src/archcanvas_cli/drafts.py",
                                 "src/archcanvas_authoring/draft.py"]]
managed = sorted((STORE / "projects").glob("*/source/model.py"))
paths += managed
inputs = [binding(path) for path in paths]
snapshots = []
for index, path in enumerate(paths):
    destination = OUT / "inputs" / f"{index:02d}-{path.name}"
    destination.parent.mkdir(exist_ok=True)
    destination.write_bytes(path.read_bytes())
    snapshots.append({"original": binding(path), "snapshot": binding(destination)})

envelope = json.loads(SAVED.read_text())
draft = envelope["draft"]
nodes = {node["id"]: node for node in draft["nodes"]}
edges = {edge["id"]: edge for edge in draft["edges"]}
assert len(nodes) == len(edges) == 5
assert draft["title"] == "M4 · 合并路由复核"
assert draft["mode"] == "authored-draft"
assert envelope["revision"] == 1 and draft["revision"] == 33


def translated(value):
    match = re.fullmatch(r"translate\(([-+\d.eE]+) ([-+\d.eE]+)\)", value)
    assert match, value
    return tuple(map(float, match.groups()))


def parse_path(value):
    tokens = re.findall(r"[A-Za-z]|[-+]?(?:\d*\.\d+|\d+)(?:[eE][-+]?\d+)?", value)
    assert tokens[0] == "M", value
    points = [(float(tokens[1]), float(tokens[2]))]
    index = 3
    while index < len(tokens):
        command, number = tokens[index], float(tokens[index + 1])
        assert command in {"H", "V"}
        previous = points[-1]
        point = (number, previous[1]) if command == "H" else (previous[0], number)
        assert point != previous, "Zero segment"
        points.append(point)
        index += 2
    return points


def intersection(a, b):
    (ax, ay), (bx, by) = a
    (cx, cy), (dx, dy) = b
    ah, bh = ay == by, cy == dy
    if ah and bh:
        low, high = max(min(ax, bx), min(cx, dx)), min(max(ax, bx), max(cx, dx))
        return ay == cy and low <= high
    if not ah and not bh:
        low, high = max(min(ay, by), min(cy, dy)), min(max(ay, by), max(cy, dy))
        return ax == cx and low <= high
    if not ah:
        return intersection(b, a)
    return min(ax, bx) <= cx <= max(ax, bx) and min(cy, dy) <= ay <= max(cy, dy)


def interior(segment, box):
    (ax, ay), (bx, by) = segment
    x, y, width, height = box
    if ay == by:
        return y < ay < y + height and max(min(ax, bx), x) < min(max(ax, bx), x + width)
    return x < ax < x + width and max(min(ay, by), y) < min(max(ay, by), y + height)


ns = "{http://www.w3.org/2000/svg}"
geometry = []
publics = {}
for stem in STEMS:
    public = publics[stem] = json.loads((RAW / f"{stem}.public.json").read_text())
    assert {n["id"] for n in public["nodes"]} == set(nodes)
    assert {e["id"] for e in public["edges"]} == set(edges)
    svg = ET.fromstring(public["svg"])
    boxes, ports, paths_here = {}, {}, {}
    for group in svg.iter(ns + "g"):
        identity = group.get("data-draft-node")
        if identity:
            x, y = translated(group.get("transform"))
            rect = group.find(ns + "rect")
            boxes[identity] = (x, y, float(rect.get("width")), float(rect.get("height")))
            for port in group.findall(ns + "g"):
                circle = port.find(ns + "circle")
                ports[identity, port.get("data-draft-port")] = (x + float(circle.get("cx")), y + float(circle.get("cy")))
        identity = group.get("data-draft-edge")
        if identity:
            values = [path.get("d") for path in group.findall(ns + "path")]
            assert len(values) == 2 and len(set(values)) == 1
            paths_here[identity] = values[0]
    assert paths_here == {e["id"]: e["path"] for e in public["edges"]}
    segments = {}
    for identity, value in paths_here.items():
        points = parse_path(value)
        edge = edges[identity]
        for endpoint, point in [("source", points[0]), ("target", points[-1])]:
            expected = ports[edge[endpoint]["nodeId"], edge[endpoint]["portId"]]
            assert point == expected, (stem, identity, endpoint, point, expected)
        segments[identity] = list(zip(points, points[1:]))
        assert not any(interior(segment, box) for segment in segments[identity] for box in boxes.values()), (stem, identity, "card interior")
    other_producer_conflicts, same_producer_contacts = [], []
    for first, second in combinations(paths_here, 2):
        contacts = sum(intersection(a, b) for a in segments[first] for b in segments[second])
        if contacts:
            same = edges[first]["source"] == edges[second]["source"]
            item = {"edges": [first, second], "segmentContacts": contacts}
            (same_producer_contacts if same else other_producer_conflicts).append(item)
    assert not other_producer_conflicts, (stem, other_producer_conflicts)
    positions = {n["id"]: translated(n["transform"]) for n in public["nodes"]}
    saved_positions = {identity: (node["position"]["x"], node["position"]["y"]) for identity, node in nodes.items()}
    add = next(identity for identity, node in nodes.items() if node["kind"] == "Add")
    expected_positions = dict(saved_positions)
    vector = {"node-right-16": (16, 0), "node-left-16": (-16, 0), "node-up-16": (0, -16), "node-down-16": (0, 16)}.get(stem, (0, 0))
    expected_positions[add] = tuple(a + b for a, b in zip(saved_positions[add], vector))
    assert positions == expected_positions, stem
    assert all(n["label"] == nodes[n["id"]]["label"] for n in public["nodes"])
    geometry.append({"capture": stem, "nodes": 5, "edges": 5, "exactEndpoints": 10,
                     "orthogonalNonzeroSegments": sum(map(len, segments.values())), "cardInteriorPenetrations": 0,
                     "distinctProducerConflicts": other_producer_conflicts, "permittedSameSourcePortContacts": same_producer_contacts,
                     "positionsMatchSavedPlusExpectedAddMove": True, "camera": public["camera"]})

for stem, vector in [("pan-right-40", (40, 0)), ("pan-left-40", (-40, 0)), ("pan-up-40", (0, -40)), ("pan-down-40", (0, 40))]:
    assert publics[stem]["edges"] == publics["node-base-restored"]["edges"]
    def camera(value):
        return list(map(float, re.findall(r"[-+]?(?:\d*\.\d+|\d+)(?:[eE][-+]?\d+)?", value)))
    baseline, moved = camera(publics["node-base-restored"]["camera"]), camera(publics[stem]["camera"])
    assert abs(moved[0] - baseline[0] - vector[0]) < 1e-10
    assert abs(moved[1] - baseline[1] - vector[1]) < 1e-10 and moved[2] == baseline[2]

source = SOURCE.read_text()
dom = (RAW / "generated.dom.txt").read_text()
generic = next(line.partition('- generic: ')[2] for line in dom.splitlines() if line.startswith('  - generic: "\\"\\"\\"Fresh'))
assert json.loads(generic) == " ".join(source.split()), "Generated modal/source whitespace-normalized mismatch"
tree = ast.parse(source)
clazz = next(item for item in tree.body if isinstance(item, ast.ClassDef))
forward = next(item for item in clazz.body if isinstance(item, ast.FunctionDef) and item.name == "forward")
names = {identity: "node_" + hashlib.sha256(identity.encode()).hexdigest()[:16] for identity in nodes}
incoming = {(edge["target"]["nodeId"], edge["target"]["portId"]): edge["source"]["nodeId"] for edge in edges.values()}
inputs_nodes = [node for node in draft["nodes"] if node["kind"] == "Input"]
assert [arg.arg for arg in forward.args.args] == ["self"] + [names[node["id"]] for node in inputs_nodes]
assert all(node["parameters"] == {"shape": [1, 16], "dtype": "float32"} for node in inputs_nodes)
assignments = {statement.targets[0].id: statement.value for statement in forward.body if isinstance(statement, ast.Assign)}
add = next(node for node in draft["nodes"] if node["kind"] == "Add")
concat = next(node for node in draft["nodes"] if node["kind"] == "Concat")
output = next(node for node in draft["nodes"] if node["kind"] == "Output")
add_expr = assignments[names[add["id"]]]
assert isinstance(add_expr, ast.BinOp) and isinstance(add_expr.op, ast.Add)
assert add_expr.left.id == names[incoming[add["id"], "left"]]
assert add_expr.right.id == names[incoming[add["id"], "right"]]
cat_expr = assignments[names[concat["id"]]]
assert isinstance(cat_expr, ast.Call) and isinstance(cat_expr.func, ast.Attribute)
assert cat_expr.func.value.id == "torch" and cat_expr.func.attr == "cat"
assert len(cat_expr.args) == 1 and isinstance(cat_expr.args[0], ast.Tuple)
assert [item.id for item in cat_expr.args[0].elts] == [names[incoming[concat["id"], "a"]], names[incoming[concat["id"], "b"]]]
assert len(cat_expr.keywords) == 1 and cat_expr.keywords[0].arg == "dim" and cat_expr.keywords[0].value.value == concat["parameters"]["dim"] == 1
returned = forward.body[-1]
assert isinstance(returned, ast.Return) and isinstance(returned.value, ast.Dict)
assert [key.value for key in returned.value.keys] == [output["id"]]
assert [value.id for value in returned.value.values] == [names[incoming[output["id"], "input"]]]
assert len(assignments) == 2 and len(forward.body) == 3
assert not any(path.read_bytes() == SOURCE.read_bytes() for path in managed)
assert inputs == [binding(path) for path in paths], "An input changed during audit"
assert raw_before == [binding(ROOT / item["path"]) for item in manifest["records"]], "Raw evidence changed during audit"

report = {"protocol": "archcanvas-saved-merge-artifact-audit/1", "role": "independent AI readback; zero human participants",
          "scope": "Saved authored draft identity, frozen public SVG geometry, and static source AST/text correspondence only",
          "inputs": inputs, "snapshots": snapshots, "frozenRawRecordsUnchanged": 60,
          "savedDraft": {"id": draft["id"], "draftRevision": draft["revision"], "storageRevision": envelope["revision"],
                         "title": draft["title"], "nodes": 5, "edges": 5, "publicReopenPositionsAndIdentitiesMatch": True},
          "publicGeometry": geometry,
          "staticSource": {"bytes": len(SOURCE.read_bytes()), "browserModalWhitespaceNormalizedMatch": True,
                           "astPortBindingsMatchSavedDraft": True, "declaredInputs": [{"shape": [1, 16], "dtype": "float32"}] * 2,
                           "declaredAddShape": [1, 16], "declaredConcatDim": 1, "declaredOutputShape": [1, 32],
                           "managedSourceMatchesInCurrentClone": 0, "managedProjectSourcesInspected": len(managed)},
          "limits": ["No model imported, executed, generated again, or dependency installed.",
                     "No browser interaction, hidden state, fetch, service state mutation or prototype access.",
                     "SVG geometry is public DOM evidence; it does not correct known stale or clipped raster frames.",
                     "Same exact source-port contacts are permitted; no globally minimum-bend or aesthetic optimum claim.",
                     "Source was shown by a generated modal but no matching managed model exists in this clone.",
                     "Tensor shapes are static declarations; no numerical or runtime correctness claim.",
                     "No human novice, physical-publication, or presented-performance certification."], "verdict": "bounded pass"}
(OUT / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
print(json.dumps({"verdict": report["verdict"], "inputs": len(inputs), "geometryCases": len(geometry),
                  "report": binding(OUT / "report.json")}, ensure_ascii=False))
