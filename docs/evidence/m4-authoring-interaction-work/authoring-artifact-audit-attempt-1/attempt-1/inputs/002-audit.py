"""Independent bounded artifact reader. Stdlib only; never imports product/models."""
from __future__ import annotations

import argparse
import ast
from collections import Counter
import copy
import hashlib
import json
from pathlib import Path
import shutil
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[4]
BASE = Path(__file__).resolve().parent
NS = {"s": "http://www.w3.org/2000/svg"}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def normalized(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()


def binding(path):
    data = path.read_bytes()
    return {"path": str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path), "bytes": len(data), "sha256": sha(data)}


def dotted(node):
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return f"{dotted(node.value)}.{node.attr}"
    raise AssertionError(f"unexpected non-symbol AST {type(node).__name__}")


def parameter_value(node):
    # This recognizes explicit AST forms, never eval/exec or model imports.
    if isinstance(node, ast.Constant):
        return node.value
    return {"symbol": dotted(node)}


def xml(svg):
    tree = ET.fromstring(svg)
    return tree, json.loads(tree.find("s:metadata", NS).text)


def source_fact(node, architecture):
    fact = {"id": node["id"], "sourceLabel": node["label"], "kind": node["kind"], "category": node["category"], "evidence": node["evidence"]}
    for key in ["callId", "repeat", "outputPath", "source"]:
        if key in node:
            fact[key] = node[key]
    if node.get("instanceId"):
        fact["instanceId"] = node["instanceId"]
        fact["callCount"] = len({n["callId"] for n in architecture["nodes"] if n.get("instanceId") == node["instanceId"] and n.get("callId")})
    return fact


def draft_chain(draft):
    assert draft["schemaVersion"] == 1 and draft["mode"] == "authored-draft"
    assert len(draft["nodes"]) == 4 and len(draft["edges"]) == 3
    assert len({n["id"] for n in draft["nodes"]}) == 4
    assert len({e["id"] for e in draft["edges"]}) == 3
    by_kind = {n["kind"]: n for n in draft["nodes"]}
    assert set(by_kind) == {"Input", "Linear", "GELU", "Output"}
    ordered = [by_kind[k] for k in ["Input", "Linear", "GELU", "Output"]]
    assert [n["label"] for n in ordered] == ["输入", "全连接", "GELU 激活", "输出"]
    assert ordered[0]["parameters"] == {"shape": [1, 16], "dtype": "float32"}
    assert ordered[1]["parameters"] == {"in_features": 16, "out_features": 8, "bias": True}
    assert ordered[2]["parameters"] == {"approximate": "none"}
    assert ordered[3]["parameters"] == {}
    expected_edges = Counter((ordered[i]["id"], "output", ordered[i + 1]["id"], "input") for i in range(3))
    assert Counter((e["source"]["nodeId"], e["source"]["portId"], e["target"]["nodeId"], e["target"]["portId"]) for e in draft["edges"]) == expected_edges
    assert [(n["position"]["x"], n["position"]["y"]) for n in ordered] == [(50, 70), (50, 224), (50, 378), (50, 532)]
    # Handwritten shape contract: Linear replaces last dimension 16 with 8;
    # the elementwise GELU preserves it. These are static declarations only.
    shapes = [[1, 16], [1, 8], [1, 8], [1, 8]]
    return ordered, {"nodeCount": 4, "edgeCount": 3, "typedPortsExact": True, "orderedKinds": [n["kind"] for n in ordered], "declaredShapes": shapes, "declaredDtype": "float32", "runtimeObserved": False}


def ast_model(source, output_id):
    tree = ast.parse(source)
    assert len(tree.body) == 4 and isinstance(tree.body[0], ast.Expr)
    assert isinstance(tree.body[0].value, ast.Constant) and tree.body[0].value.value == "Fresh ArchCanvas authored model; static declarations are not runtime verification."
    imports = [n for n in tree.body if isinstance(n, (ast.Import, ast.ImportFrom))]
    assert [(type(n).__name__, getattr(n, "module", None), [(a.name, a.asname) for a in n.names]) for n in imports] == [
        ("Import", None, [("torch", None)]), ("ImportFrom", "torch", [("nn", None)])]
    classes = [n for n in tree.body if isinstance(n, ast.ClassDef)]
    assert len(classes) == 1 and classes[0].name == "AuthoredModel"
    cls = classes[0]
    assert not cls.decorator_list and not cls.keywords
    assert [dotted(n) for n in cls.bases] == ["nn.Module"]
    methods = {n.name: n for n in cls.body if isinstance(n, ast.FunctionDef)}
    assert set(methods) == {"__init__", "forward"}
    init, forward = methods["__init__"], methods["forward"]
    assert not init.decorator_list and not forward.decorator_list
    assert len(cls.body) == 2 and [arg.arg for arg in init.args.args] == ["self"]
    assert len(init.body) == 3 and len(forward.body) == 3
    super_call = init.body[0]
    assert isinstance(super_call, ast.Expr) and isinstance(super_call.value, ast.Call)
    assert ast.get_source_segment(source, super_call) == "super().__init__()"
    constructors = []
    for statement in init.body[1:]:
        assert isinstance(statement, ast.Assign) and len(statement.targets) == 1
        target = dotted(statement.targets[0]); call = statement.value
        assert target.startswith("self.") and isinstance(call, ast.Call) and not call.args
        assert all(k.arg is not None for k in call.keywords)
        parameters = {k.arg: parameter_value(k.value) for k in call.keywords}
        constructors.append({"target": target.removeprefix("self."), "kind": dotted(call.func), "parameters": parameters, "ast": call})
    assert [(n["kind"], n["parameters"]) for n in constructors] == [
        ("nn.Linear", {"in_features": 16, "out_features": 8, "bias": True, "dtype": {"symbol": "torch.float32"}}),
        ("nn.GELU", {"approximate": "none"}),
    ]
    args = [arg.arg for arg in forward.args.args]
    assert len(args) == 2 and args[0] == "self"
    assert not forward.args.defaults and not forward.args.vararg and not forward.args.kwarg and not forward.args.kwonlyargs
    calls = []
    producer = args[1]
    for statement, constructor in zip(forward.body[:2], constructors):
        assert isinstance(statement, ast.Assign) and len(statement.targets) == 1
        assert isinstance(statement.targets[0], ast.Name) and isinstance(statement.value, ast.Call)
        call = statement.value
        assert dotted(call.func) == f"self.{constructor['target']}" and not call.keywords and len(call.args) == 1
        assert isinstance(call.args[0], ast.Name) and call.args[0].id == producer
        assert statement.targets[0].id == constructor["target"]
        calls.append({"target": statement.targets[0].id, "input": producer, "expression": ast.get_source_segment(source, call), "ast": call})
        producer = statement.targets[0].id
    returned = forward.body[2]
    assert isinstance(returned, ast.Return) and isinstance(returned.value, ast.Dict)
    assert len(returned.value.keys) == 1 and isinstance(returned.value.keys[0], ast.Constant) and returned.value.keys[0].value == output_id
    assert isinstance(returned.value.values[0], ast.Name) and returned.value.values[0].id == producer
    return {"class": cls, "forward": forward, "constructors": constructors, "calls": calls, "input": args[1], "outputKey": output_id, "returnProducer": producer}


def check_architecture(architecture, document, source, draft_nodes, model):
    assert len(architecture["nodes"]) == 5 and len(architecture["edges"]) == 4
    assert Counter(n["kind"] for n in architecture["nodes"]) == Counter(["Input", "Module", "Linear", "GELU", "Output"])
    assert architecture["entry"] == "model:AuthoredModel"
    assert architecture["sources"] == [{"path": "model.py", "content": source, "digest": sha(source.encode())}]
    source_corpus = [{"path": "model.py", "digest": sha(source.encode())}]
    assert architecture["sourceDigest"] == sha(normalized(source_corpus))
    semantic_nodes = []
    for node in architecture["nodes"]:
        item = {k: v for k, v in node.items() if k not in ["source", "parameterOrigins"]}
        if "parameterOrigins" in node:
            item["parameterOrigins"] = {k: {f: origin[f] for f in ["kind", "expression", "path"]} for k, origin in node["parameterOrigins"].items()}
        semantic_nodes.append(item)
    assert architecture["irDigest"] == sha(normalized({"entry": "model:AuthoredModel", "nodes": semantic_nodes, "edges": architecture["edges"]}))
    nodes = {n["kind"]: n for n in architecture["nodes"]}
    # Generation uses its declared deterministic symbol encoding. This checks
    # wire identity separately from the handwritten producer/parameter oracle.
    symbols = ["node_" + sha(n["id"].encode())[:16] for n in draft_nodes]
    assert model["input"] == symbols[0]
    assert [c["target"] for c in model["constructors"]] == symbols[1:3]
    assert nodes["Input"]["label"] == model["input"]
    assert nodes["Output"]["outputPath"] == [{"kind": "key", "key": model["outputKey"]}]
    root = nodes["Module"]
    assert not root.get("parentId") and set(root["children"]) == {n["id"] for n in architecture["nodes"] if n is not root}
    assert all(n.get("parentId") == root["id"] for n in architecture["nodes"] if n is not root)
    for kind, constructor, call in zip(["Linear", "GELU"], model["constructors"], model["calls"]):
        node = nodes[kind]
        assert node["id"].endswith("." + constructor["target"])
        assert node["evidence"] == "contract"
        expected = constructor["parameters"].copy()
        if kind == "Linear":
            expected["dtype"] = {"expression": "torch.float32", "origin": "unknown"}
        assert node["parameters"] == expected
        assert set(node["parameterOrigins"]) == set(expected)
        for keyword in constructor["ast"].keywords:
            value = keyword.value; origin = node["parameterOrigins"][keyword.arg]
            assert origin["path"] == "model.py"
            assert origin["line"] == value.lineno and origin["endLine"] == value.end_lineno
            assert origin["column"] == value.col_offset and origin["endColumn"] == value.end_col_offset
            assert origin["expression"] == ast.get_source_segment(source, value)
            assert origin["kind"] == ("literal" if isinstance(value, ast.Constant) else "unknown")
            line = source.splitlines()[value.lineno - 1].encode()
            assert line[origin["column"]:origin["endColumn"]].decode() == origin["expression"]
        assert node["source"]["expression"] == call["expression"]
    for node in architecture["nodes"]:
        expected_ast = model["class"] if node["kind"] == "Module" else model["forward"] if node["kind"] in ["Input", "Output"] else next(c["ast"] for c in model["calls"] if node["id"].endswith("." + c["target"]))
        assert node["source"] == {"path": "model.py", "line": expected_ast.lineno, "endLine": expected_ast.end_lineno, "expression": ast.get_source_segment(source, expected_ast)}
    # Canonical ports are checked independently from labels and routing.
    port_map = {n["id"]: {p["id"]: p for p in n["ports"]} for n in architecture["nodes"]}
    for edge in architecture["edges"]:
        assert port_map[edge["source"]["nodeId"]][edge["source"]["portId"]]["direction"] == "out"
        assert port_map[edge["target"]["nodeId"]][edge["target"]["portId"]]["direction"] == "in"
        assert edge["role"] == "data"
    chain = [nodes[k]["id"] for k in ["Input", "Linear", "GELU", "Output"]]
    expected_pairs = Counter(zip(chain, chain[1:]))
    actual_pairs = Counter((e["source"]["nodeId"], e["target"]["nodeId"]) for e in architecture["edges"] if e["target"]["nodeId"] != root["id"])
    assert actual_pairs == expected_pairs
    adapters = [e for e in architecture["edges"] if e["target"]["nodeId"] == root["id"]]
    assert len(adapters) == 1 and adapters[0]["source"]["nodeId"] == chain[0]
    assert document["architecture"] == architecture
    assert document["sourceBindingDigest"] == architecture["sourceDigest"]
    assert document["revision"] == 0 and document["expandedIds"] == [root["id"]]
    aliases = {nodes[k]["id"]: d["label"] for k, d in zip(["Input", "Linear", "GELU", "Output"], draft_nodes)}
    assert document["displayAliases"] == aliases
    assert document["title"] == "M4 · 端口与纵向链"
    return nodes, {"canonicalNodes": 5, "canonicalEdges": 4, "sourceSha256": sha(source.encode()), "sourceDigest": architecture["sourceDigest"], "irDigest": architecture["irDigest"], "parameterUtf8SpansExact": True, "astSemanticsExact": True, "sourceAndIRDigestNormalizationExact": True}


def check_public_svg(raw, document, architecture, nodes):
    values = raw.get("svgs") or [raw.get("svg")]
    candidates = []
    for value in values:
        if value:
            tree, meta = xml(value)
            if meta.get("documentId") == document["id"]:
                candidates.append((tree, meta, value))
    assert len(candidates) == 1
    tree, meta, value = candidates[0]
    assert tree.get("data-document-id") == document["id"] and tree.get("data-revision") == "0"
    assert tree.get("aria-label") == document["title"]
    assert meta["documentId"] == document["id"] and meta["revision"] == 0
    assert meta["sourceDigest"] == architecture["sourceDigest"] and meta["irDigest"] == architecture["irDigest"]
    assert meta["sourceFactScope"] == "whole-source-architecture"
    assert meta["sourceFacts"] == [source_fact(n, architecture) for n in architecture["nodes"]]
    groups = tree.findall('.//s:g[@data-canonical-id]', NS)
    assert len(groups) == 5
    assert {g.get("data-canonical-id") for g in groups} == {n["id"] for n in architecture["nodes"]}
    assert {n["canonicalNodeId"] for n in meta["renderedNodes"]} == {n["id"] for n in architecture["nodes"]}
    edge_by_id = {e["id"]: e for e in architecture["edges"]}
    assert len(meta["renderedBindings"]) == 3
    for binding in meta["renderedBindings"]:
        assert len(binding["canonicalEdgeIds"]) == 1
        edge = edge_by_id[binding["canonicalEdgeIds"][0]]
        assert {k: binding[k] for k in ["source", "target", "tensorId", "role"]} == {k: edge[k] for k in ["source", "target", "tensorId", "role"]}
        assert edge["target"]["nodeId"] != nodes["Module"]["id"]
    output_group = next(g for g in groups if g.get("data-canonical-id") == nodes["Output"]["id"])
    output_text = ["".join(t.itertext()) for t in output_group.findall('s:text', NS)]
    assert output_text == ["输出", "model output"]
    real_key = nodes["Output"]["outputPath"][0]["key"]
    assert f'return["{real_key}"]' in output_group.find('s:title', NS).text
    assert not any(real_key in "".join(t.itertext()) for t in tree.findall('.//s:text', NS))
    assert any("index-ye7sAyyI.js" in script for script in raw["scripts"])
    return {"documentId": document["id"], "svgSha256": sha(value.encode()), "renderedNodes": 5, "renderedBindings": 3, "outputVisibleTexts": output_text, "completeOutputPathInTitleAndMetadata": True, "metadataFactsExact": True}, value


def publication_artifacts(svg_path, receipt_path, document_path, state):
    svg_bytes = svg_path.read_bytes(); tree, meta = xml(svg_bytes.decode())
    receipt = json.loads(receipt_path.read_text())
    exported_document = json.loads(document_path.read_text())
    assert exported_document == state["document"]
    assert len(svg_bytes) == receipt["bytes"]
    assert sha(svg_bytes) == receipt["outputDigest"] == receipt["svgDigest"]
    assert receipt["documentId"] == state["document"]["id"] and receipt["revision"] == 0
    assert receipt["sourceDigest"] == state["architecture"]["sourceDigest"] and receipt["irDigest"] == state["architecture"]["irDigest"]
    assert receipt["sceneSvgDigest"] == receipt["inputSvgDigest"]
    public_tree, public_meta = xml(state["lastPublicSvg"])
    assert meta == public_meta
    viewbox = [float(value) for value in tree.get("viewBox").split()]
    assert viewbox == [0, 0, 595, 650] == receipt["viewBox"]
    assert float(tree.get("width").removesuffix("mm")) == 180 == receipt["widthMm"]
    exact_height = 180 * 650 / 595
    assert abs(float(tree.get("height").removesuffix("mm")) - exact_height) < 1e-10
    assert abs(receipt["heightMm"] - exact_height) < 1e-10
    assert meta["widthMm"] == 180 and abs(meta["heightMm"] - exact_height) < 1e-10
    # Compare complete node/edge object XML, removing only explicit interaction
    # attributes/expand controls. Publication ports differ by declared mode.
    def node_object(group):
        group = copy.deepcopy(group)
        group.attrib.pop("tabindex", None); group.attrib.pop("role", None)
        for child in list(group):
            if "data-expand-id" in child.attrib:
                group.remove(child)
        return ET.canonicalize(ET.tostring(group, encoding="unicode"))
    public_nodes = {g.get("data-canonical-id"): node_object(g) for g in public_tree.findall('.//s:g[@data-canonical-id]', NS)}
    export_nodes = {g.get("data-canonical-id"): node_object(g) for g in tree.findall('.//s:g[@data-canonical-id]', NS)}
    assert export_nodes == public_nodes and len(export_nodes) == 5
    def objects(attribute):
        return {g.get(attribute): ET.canonicalize(ET.tostring(g, encoding="unicode")) for g in tree.findall(f'.//s:g[@{attribute}]', NS)}, {g.get(attribute): ET.canonicalize(ET.tostring(g, encoding="unicode")) for g in public_tree.findall(f'.//s:g[@{attribute}]', NS)}
    for attribute in ["data-edge-id", "data-legend-id", "data-edge-legend-id", "data-annotation-id"]:
        exported, public = objects(attribute)
        assert exported == public
    assert len(tree.findall('.//s:g[@data-edge-id]', NS)) == 3
    assert not tree.findall('.//s:g[@data-expand-id]', NS)
    for group in tree.findall('.//s:g[@data-canonical-id]', NS):
        assert "tabindex" not in group.attrib and "role" not in group.attrib
    assert not tree.findall('.//s:script', NS)
    assert not tree.findall('.//s:image', NS)
    return {"outputBytes": len(svg_bytes), "outputSha256": sha(svg_bytes), "exportedDocumentExact": True, "publicAndExportNodeEdgeLegendAnnotationObjectsExact": True, "publicAndExportWholeSourceMetadataExact": True, "rootPhysicalDimensionsIndependentlyMeasured": [180, exact_height], "rendererInputDigestCrossBoundOnly": receipt["inputSvgDigest"], "rendererInputBytesIndependentlyRecovered": False, "runtimeOrHumanOrPublicationReadabilityCertified": False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--spec", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    spec = json.loads(args.spec.read_text())
    paths = {key: ROOT / relative for key, relative in spec["paths"].items()}
    manifest = json.loads(paths["manifest"].read_text())
    manifest_inputs = [ROOT / item[role]["path"] for item in manifest["copies"] for role in ["source", "copy"]]
    all_inputs = list(dict.fromkeys([args.spec.resolve(), BASE / "contract.json", Path(__file__).resolve(), *paths.values(), *manifest_inputs]))
    before = [binding(p) for p in all_inputs]
    args.out.mkdir(parents=True, exist_ok=False)
    copies = args.out / "inputs"; copies.mkdir()
    for index, path in enumerate(all_inputs):
        shutil.copyfile(path, copies / f"{index:03d}-{path.name}")
    results = []
    def case(name, function):
        try:
            detail = function()
            results.append({"name": name, "passed": True, "detail": detail})
            return detail
        except Exception as error:
            results.append({"name": name, "passed": False, "error": f"{type(error).__name__}: {error}"})
            return None
    state = {}
    def freeze():
        assert binding(paths["manifest"])["sha256"] == "fc17d40749597423e0e74771cf4c3a45dd5cd4a921fc7513eea670e69e0347a3"
        for item in manifest["copies"]:
            for role in ["source", "copy"]:
                declared = item[role]; actual = binding(ROOT / declared["path"])
                assert actual["bytes"] == declared["bytes"] and actual["sha256"] == declared["sha256"]
            assert (ROOT / item["source"]["path"]).read_bytes() == (ROOT / item["copy"]["path"]).read_bytes()
        return {"rootFrozenFilesVerified": len(manifest["copies"]), "actualCopiesExact": True, "otherPresetSemanticsReviewed": False, "HTTPAssetAndBrowserCacheReviewed": False}
    case("root frozen artifact bindings", freeze)
    def draft():
        envelope = json.loads(paths["draft"].read_text()); d = envelope["draft"]
        ordered, detail = draft_chain(d); state["draft"] = d; state["ordered"] = ordered
        reopened = json.loads(paths["draftPublic"].read_text())
        assert reopened["title"] == d["title"]
        assert [n["id"] for n in reopened["nodes"]] == [n["id"] for n in ordered]
        assert {e["id"] for e in reopened["edges"]} == {e["id"] for e in d["edges"]}
        assert [n["transform"] for n in reopened["nodes"]] == ["translate(50 70)", "translate(50 224)", "translate(50 378)", "translate(50 532)"]
        detail.update({"storageRevision": envelope["revision"], "draftRevision": d["revision"], "publicReopenedIdentitiesAndPositionsExact": True})
        return detail
    case("actual saved typed draft and reopened public state", draft)
    def generated():
        source = paths["source"].read_text(); visible = paths["visibleSource"].read_text()
        assert source == visible
        model = ast_model(source, state["ordered"][3]["id"])
        state.update({"source": source, "model": model})
        return {"sourceSha256": sha(source.encode()), "visibleAndActualSourceExact": True, "inputSymbol": model["input"], "constructorKinds": [c["kind"] for c in model["constructors"]], "forwardInputDependencies": [c["input"] for c in model["calls"]], "outputKey": model["outputKey"], "returnProducer": model["returnProducer"], "modelImportedOrExecuted": False}
    case("actual generated Python AST and visible source", generated)
    def project():
        project = json.loads(paths["project"].read_text())
        assert project == {"id": "1ae6944134fc42e48acc0e7484341642", "entry": "model:AuthoredModel", "scope": "managed-copy"}
        envelope = json.loads(paths["document"].read_text()); document = envelope["document"]
        architecture = document["architecture"]
        nodes, detail = check_architecture(architecture, document, state["source"], state["ordered"], state["model"])
        state.update({"architecture": architecture, "document": document, "nodes": nodes})
        detail.update({"projectId": project["id"], "storageRevision": envelope["revision"], "documentRevision": document["revision"], "documentId": document["id"]})
        return detail
    case("registered source architecture, canonical ports, digests and saved alias document", project)
    def public():
        records = []; first_svg = None
        for name in ["publicBefore", "publicSaved", "publicReopened", "publicFinalBefore", "publicAfter"]:
            raw = json.loads(paths[name].read_text())
            detail, svg = check_public_svg(raw, state["document"], state["architecture"], state["nodes"])
            if first_svg is None:
                first_svg = svg
            assert ET.canonicalize(first_svg) == ET.canonicalize(svg)
            if "metadata" in raw:
                assert raw["metadata"] == xml(svg)[1]
            records.append({"name": name, "capturedAt": raw["capturedAt"], "detail": detail})
        state["lastPublicSvg"] = svg
        return {"records": records, "allFivePublicSvgExactCanonicalXml": True, "oldManagedReopenedNotBorrowed": True}
    case("actual browser Output captions, full source metadata and saved public SVG continuity", public)
    case("actual publication SVG, exported document and receipt physical/hash bindings", lambda: publication_artifacts(paths["exportSvg"], paths["exportReceipt"], paths["exportDocument"], state))
    after = [binding(p) for p in all_inputs]
    report = {"version": 1, "scope": "independent stdlib static four-node authored artifact audit", "results": results, "passedCases": sum(r["passed"] for r in results), "allCases": len(results), "allCasesPassed": all(r["passed"] for r in results), "inputBindingsBefore": before, "inputBindingsAfter": after, "inputsUnchanged": before == after, "allInputCopiesExact": all((copies / f"{i:03d}-{p.name}").read_bytes() == p.read_bytes() for i,p in enumerate(all_inputs)), "humanParticipantsCertified": 0, "runtimeTensorVerified": False, "allCatalogModulesCertified": False, "publicationSizeCertified": False, "M4CompleteCertified": False}
    (args.out / "receipt.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"receipt": binding(args.out / "receipt.json"), "passedCases": report["passedCases"], "allCases": report["allCases"], "inputsUnchanged": report["inputsUnchanged"]}))
    raise SystemExit(0 if report["allCasesPassed"] and report["inputsUnchanged"] and report["allInputCopiesExact"] else 2)


if __name__ == "__main__":
    main()
