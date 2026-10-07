"""Audit four actual browser-saved drafts and visible generated source texts.

No generated source or torch is imported/executed. Saved model text is parsed
with stdlib AST and the formal static frontend. No browser mutation occurs.
"""
from __future__ import annotations

import argparse
import ast
from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
WORK = ROOT / "docs/evidence/m4-move-recovery-presets-work"
BROWSER = ROOT / "docs/evidence/m4-move-recovery-presets-browser"
sys.path.insert(0, str(ROOT / "src"))
from archcanvas_authoring import validate_draft  # noqa: E402
from archcanvas_python import analyze_source  # noqa: E402
import archcanvas_authoring.draft as backend  # noqa: E402
import archcanvas_python.frontend as frontend  # noqa: E402


def module_from_file(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


oracle = module_from_file("browser_handwritten_ast_oracle", WORK / "preset-independent/audit.py")
ir_oracle = module_from_file("browser_source_ir_oracle", WORK / "preset-independent/audit-ir.py")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def visible_ax_source(ax_path, source):
    required = " ".join(source.split())
    values = []
    for line in ax_path.read_text().splitlines():
        if "- generic: " not in line:
            continue
        text = line.split("- generic: ", 1)[1]
        if text.startswith('"'):
            values.append(json.loads(text))
    matching = [value for value in values if " ".join(value.split()) == required]
    oracle.require(len(matching) == 1, "Captured source does not exactly match the whitespace-normalized actual AX modal text")
    return {"status": "passed", "basis": "One exact whitespace-normalized AX generic source string; source formatting is separately preserved in the .py.txt artifact."}


def final_public_draft(public, draft):
    svg = ET.fromstring(public["draftSvg"])
    actual_nodes = {element.attrib["data-draft-node"]: element for element in svg.iter() if "data-draft-node" in element.attrib}
    oracle.require(set(actual_nodes) == {node["id"] for node in draft["nodes"]}, "Public SVG node IDs differ from actual saved draft")
    port_points = {}
    for node in draft["nodes"]:
        element = actual_nodes[node["id"]]
        point = re.fullmatch(r"translate\((-?[\d.]+) (-?[\d.]+)\)", element.attrib["transform"])
        oracle.require(point is not None and [float(point[1]), float(point[2])] == [node["position"]["x"], node["position"]["y"]], "Public SVG position differs from saved node")
        text_values = [child.text for child in element if child.tag.endswith("text")]
        oracle.require(text_values == [node["label"], node["kind"]], "Public node label/type differs from saved node")
        ports = [child for child in element if "data-draft-port" in child.attrib]
        expected_ports = ["output"] if node["kind"] == "Input" else ["input"] if node["kind"] == "Output" else ["input", "output"]
        oracle.require([port.attrib["data-draft-port"] for port in ports] == expected_ports, "Public SVG port inventory differs")
        for port in ports:
            circles = [child for child in port if child.tag.endswith("circle")]
            oracle.require(len(circles) == 2 and float(circles[0].attrib["cx"]) == float(circles[1].attrib["cx"]) and float(circles[0].attrib["cy"]) == float(circles[1].attrib["cy"]), "Public SVG hit/visible port circles differ")
            port_points[node["id"], port.attrib["data-draft-port"]] = (node["position"]["x"] + float(circles[1].attrib["cx"]), node["position"]["y"] + float(circles[1].attrib["cy"]))
    actual_edges = {element.attrib["data-draft-edge"]: element for element in svg.iter() if "data-draft-edge" in element.attrib}
    oracle.require(set(actual_edges) == {edge["id"] for edge in draft["edges"]}, "Public SVG edge IDs differ from saved draft")
    for edge in draft["edges"]:
        paths = [child for child in actual_edges[edge["id"]] if child.tag.endswith("path")]
        oracle.require(len(paths) == 2 and paths[0].attrib["d"] == paths[1].attrib["d"], "Public edge visible/hit geometry differs")
        tokens = re.findall(r"[MHV]|-?\d+(?:\.\d+)?", paths[1].attrib["d"])
        oracle.require(" ".join(tokens) == paths[1].attrib["d"] and tokens[0] == "M", "Unsupported or malformed orthogonal public edge")
        x, y = float(tokens[1]), float(tokens[2])
        start = x, y
        index = 3
        while index < len(tokens):
            command, value = tokens[index], float(tokens[index + 1])
            oracle.require(command in {"H", "V"}, "Nonorthogonal edge segment")
            if command == "H":
                x = value
            else:
                y = value
            index += 2
        expected_start = port_points[edge["source"]["nodeId"], edge["source"]["portId"]]
        expected_end = port_points[edge["target"]["nodeId"], edge["target"]["portId"]]
        oracle.require(start == expected_start and (x, y) == expected_end, "Public edge endpoints differ from saved canonical ports")
    node0 = draft["nodes"][0]
    offsets = [(node["position"]["x"] - node0["position"]["x"], node["position"]["y"] - node0["position"]["y"]) for node in draft["nodes"]]
    oracle.require(offsets == [(0, 0), (224, 0), (448, 0), (672, 0), (0, 180), (224, 180), (448, 180), (672, 180)], "Final CNN default relative coordinates differ from the expected two forward rows")
    camera = [element.attrib["transform"] for element in svg if element.tag.endswith("g") and "transform" in element.attrib]
    return {"status": "passed", "nodes": len(actual_nodes), "edges": len(actual_edges), "canonicalEndpoints": 2 * len(actual_edges), "relativeCoordinates": offsets, "publicCameraTransform": camera, "scripts": public["scripts"], "scope": "Actual public SVG IDs/types/labels/positions/ports and orthogonal exact endpoints, plus two-row CNN relative coordinates; no pixel beauty or publication-size claim."}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output = args.output.resolve()
    args.output.mkdir(parents=True, exist_ok=False)
    original_contract = WORK / "preset-independent/expected-contracts.json"
    contracts = deepcopy(json.loads(original_contract.read_text())["presets"])
    contracts["mlp-batch2"] = deepcopy(contracts["mlp"])
    contracts["mlp-batch2"]["nodes"][0]["parameters"]["shape"] = [2, 16]
    for node in contracts["mlp-batch2"]["nodes"]:
        node["shape"][0] = 2
    session = BROWSER / "session-2"
    final = BROWSER / "final-ChS0wIgb"
    cases = [
        ("browser-mlp-batch2", "mlp-batch2", session / "draft-stores/mlp-envelope.json", session / "mlp-generated-source.py.txt", session / "mlp-generated-actual.after.dom.txt"),
        ("browser-cnn-original-row", "cnn", session / "draft-stores/cnn-envelope.json", session / "cnn-generated-source.py.txt", session / "cnn-generated.after.dom.txt"),
        ("browser-residual", "residual-mlp", session / "draft-stores/residual-envelope.json", session / "residual-generated-source.py.txt", session / "residual-generated.after.dom.txt"),
        ("browser-cnn-compact-final", "cnn", final / "compact-cnn-envelope.json", final / "compact-cnn-source.py.txt", final / "compact-cnn-generated-final.public.json"),
    ]
    input_paths = [original_contract, WORK / "preset-independent/audit.py", WORK / "preset-independent/audit-ir.py", WORK / "preset-independent/evidence-manifest.json", WORK / "browser-source-audit/check.py", WORK / "browser-source-audit/report.json", session / "draft-stores/copy-receipts.json", Path(backend.__file__), Path(frontend.__file__), Path(__file__)]
    for _, _, envelope_path, source_path, ui_path in cases:
        input_paths.extend([envelope_path, source_path, ui_path])
    input_paths = list(dict.fromkeys(path.resolve() for path in input_paths))
    before = {str(path.relative_to(ROOT)): digest(path) for path in input_paths}
    oracle.require("torch" not in sys.modules, "Static audit unexpectedly imported torch")
    oracle.require(Path(backend.__file__).resolve().is_relative_to(ROOT / "src") and Path(frontend.__file__).resolve().is_relative_to(ROOT / "src"), "Formal package provenance is not isolated")
    rows = []
    try:
        for name, preset, envelope_path, source_path, ui_path in cases:
            envelope = json.loads(envelope_path.read_text())
            draft, source = envelope["draft"], source_path.read_text()
            original = deepcopy(draft)
            nodes, edges, shapes, _ = oracle.graph_contract(draft, [preset], contracts)
            checked = validate_draft(draft, require_complete=True)
            oracle.require(checked["complete"] and not checked["issues"] and checked["tensors"] == shapes, "Backend declared tensor validation differs from handwritten per-node arithmetic")
            ast_result = oracle.source_ast_contract(source, nodes, edges)
            actual_ir = analyze_source(source, "model:AuthoredModel")
            ir_result = ir_oracle.check_ir({"source": source, "architecture": actual_ir}, nodes, edges, ast_result)
            controls = oracle.negative_ast_controls(source, nodes, edges)
            if name == "browser-cnn-compact-final":
                public = json.loads(ui_path.read_text())
                oracle.require(len(public["dialog"]) == 1 and source in public["dialog"][0], "Final modal public string does not contain exact captured source bytes")
                visibility = {"status": "passed", "basis": "Captured .py.txt is exact substring of the sole public generated-source modal dialog."}
                geometry = final_public_draft(public, draft)
            else:
                visibility = visible_ax_source(ui_path, source)
                geometry = None
            oracle.require(draft == original and "torch" not in sys.modules, "Static validation/analysis mutated input or imported torch")
            result = {"case": name, "status": "passed", "draftId": draft["id"], "draftRevision": draft["revision"], "storageRevision": envelope["revision"], "nodes": len(nodes), "edges": len(edges), "handwrittenDeclaredTensors": shapes, "ast": ast_result, "staticIR": ir_result, "sourceVisibleEvidence": visibility, "publicGeometry": geometry, "negativeControls": controls, "modelExecution": "not_run"}
            rows.append(result)
            oracle.write_new(args.output / f"{name}-audit.json", result)
            oracle.write_new(args.output / f"{name}-validation.json", checked)
            oracle.write_new(args.output / f"{name}-actual-source-ir.json", actual_ir)
        previous_manifest = json.loads((WORK / "preset-independent/evidence-manifest.json").read_text())
        for binding in previous_manifest["bindings"]:
            path = ROOT / binding["path"]
            oracle.require(path.stat().st_size == binding["bytes"] and digest(path) == binding["sha256"], "Prior 106-file oracle evidence changed")
        oracle.require(before == {str(path.relative_to(ROOT)): digest(path) for path in input_paths}, "Input/source evidence changed while auditing")
        oracle.write_new(args.output / "audit-summary.json", {"status": "passed", "scope": "Four actual browser-saved drafts and visible source artifacts, hand-calculated shapes, full AST and independently recovered actual static IR ports; final compact CNN public SVG geometry", "modelExecution": "not_run", "torchImported": False, "cases": [{key: value for key, value in row.items() if key not in {"negativeControls", "handwrittenDeclaredTensors", "ast", "staticIR"}} for row in rows], "totals": {"cases": len(rows), "draftNodes": sum(row["nodes"] for row in rows), "draftEdges": sum(row["edges"] for row in rows), "negativeASTControls": sum(len(row["negativeControls"]) for row in rows), "irNodes": sum(row["staticIR"]["irNodes"] for row in rows), "irEdges": sum(row["staticIR"]["irEdges"] for row in rows), "exactPorts": sum(row["staticIR"]["exactPorts"] for row in rows)}, "priorOracle": {"filesVerifiedUnchanged": len(previous_manifest["bindings"]), "manifestSha256": digest(WORK / "preset-independent/evidence-manifest.json"), "oldProductBindingsRemainHistorical": True}, "inputBindings": before, "rootPriorCheckScopeReview": {"path": str((WORK / "browser-source-audit/check.py").relative_to(ROOT)), "cases": 3, "validScope": "Uses the handwritten full DAG/parameters and source AST oracle; emits its own hand-calculated shapes and 22 negative controls.", "supplementalEvidenceAddedHere": "Actual formal validate_draft tensors and static source frontend IR endpoint/role/fan-out reconciliation; original 3 modal AX strings and final exact dialog-source substring; fourth compact CNN and saved/public SVG identity/position/endpoint checks; all input bytes locked before/after."}, "limitations": ["The original root three-case check remains three cases and is not relabeled as four or as numerical validation.", "Input shapes/dtypes are static declarations. Generated source has no encoded batch-shape signature; the actual saved input declaration and shape propagation prove the batch-2 metadata.", "No model execution, numeric output, native input event performance, current live browser synchronization, pixel beauty, publication-size readability, or human research acceptance is certified.", "The final public script basename is observed UI state; full bundle/source binding belongs to the root final-build seal."]})
    except BaseException as error:
        oracle.write_new(args.output / "FAILED.json", {"type": type(error).__name__, "message": str(error), "completedCases": [row["case"] for row in rows], "inputBindingsBefore": before})
        raise
    print(json.dumps({"status": "passed", "cases": len(rows), "nodes": sum(row["nodes"] for row in rows), "edges": sum(row["edges"] for row in rows), "modelExecution": "not_run", "priorOracleFilesUnchanged": len(previous_manifest["bindings"])}))


if __name__ == "__main__":
    main()
