"""AI novice contract audit; never import or execute a generated model."""
from pathlib import Path
from copy import deepcopy
from unittest.mock import patch
import ast
import hashlib
import json
import sys

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))
from archcanvas_authoring import DraftError, generate_model, module_catalog, validate_draft
from archcanvas_cli.drafts import DraftStore

EXPECTED_KINDS = ["Input", "Output", "Linear", "ReLU", "GELU", "SiLU", "Identity", "Dropout", "Flatten", "Conv2d", "MaxPool2d", "AdaptiveAvgPool2d", "BatchNorm2d", "LayerNorm", "Embedding", "Add", "Concat"]
# Handwritten compatible declarations and output expectations, independent of
# product shape-inference code and constructor defaults.
EXPECTED_SHAPES = {
    "Input": ([1, 16], "float32", [1, 16]), "Output": ([1, 16], "float32", [1, 16]),
    "Linear": ([1, 16], "float32", [1, 32]), "ReLU": ([1, 16], "float32", [1, 16]),
    "GELU": ([1, 16], "float32", [1, 16]), "SiLU": ([1, 16], "float32", [1, 16]),
    "Identity": ([1, 16], "float32", [1, 16]), "Dropout": ([1, 16], "float32", [1, 16]),
    "Flatten": ([1, 2, 3], "float32", [1, 6]), "Conv2d": ([1, 3, 8, 8], "float32", [1, 16, 6, 6]),
    "MaxPool2d": ([1, 3, 8, 8], "float32", [1, 3, 4, 4]), "AdaptiveAvgPool2d": ([1, 3, 8, 8], "float32", [1, 3, 1, 1]),
    "BatchNorm2d": ([2, 16, 4, 4], "float32", [2, 16, 4, 4]), "LayerNorm": ([1, 16], "float32", [1, 16]),
    "Embedding": ([1, 8], "int64", [1, 8, 16]), "Add": ([1, 16], "float32", [1, 16]),
    "Concat": ([1, 16], "float32", [1, 32]),
}
INPUTS = ["AGENTS.md", "docs/m4-routing-components-v1.md", "src/archcanvas_authoring/draft.py", "src/archcanvas_cli/drafts.py", "studio/src/AuthoringStudio.tsx", "studio/src/AuthoringStudio.css", "studio/src/authoring.ts", "studio/src/authoringPresets.ts", "studio/src/draftParameterHelp.ts", "studio/src/draftValidation.ts", "studio/src/authoringFeedback.ts", "studio/src/App.tsx", "studio/src/api.ts", "studio/dist/index.html"]
INPUTS += [str(path.relative_to(ROOT)) for path in sorted((ROOT / "studio/dist/assets").glob("*")) if path.is_file()]
def binding(path):
    p = ROOT / path
    data = p.read_bytes()
    return {"path": path, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
before = [binding(path) for path in INPUTS]
catalog = module_catalog()
assert [module["kind"] for module in catalog["modules"]] == EXPECTED_KINDS
assert sum(len(module["parameters"]) for module in catalog["modules"]) == 34
by_kind = {module["kind"]: module for module in catalog["modules"]}
def node(kind, identity, parameters=None, y=70):
    return {"id": identity, "kind": kind, "label": kind, "parameters": {**deepcopy(by_kind[kind]["defaults"]), **(parameters or {})}, "position": {"x": 50 if identity.startswith("in") else 300 if identity == "layer" else 550, "y": y}}
def graph(kind):
    shape, dtype, _ = EXPECTED_SHAPES[kind]
    draft = {"schemaVersion": 1, "mode": "authored-draft", "id": "draft-ab123", "title": "AI static contract check", "revision": 0, "nodes": [node("Input", "in", {"shape": shape, "dtype": dtype})], "edges": []}
    def edge(source, target, port="input"):
        draft["edges"].append({"id": f"e{len(draft['edges'])}", "source": {"nodeId": source, "portId": "output"}, "target": {"nodeId": target, "portId": port}})
    if kind in ("Input", "Output"):
        draft["nodes"].append(node("Output", "out")); edge("in", "out")
    else:
        draft["nodes"].extend([node(kind, "layer"), node("Output", "out")])
        if kind in ("Add", "Concat"):
            draft["nodes"].append(node("Input", "in2", {"shape": shape, "dtype": dtype}, 240))
            edge("in", "layer", "left" if kind == "Add" else "a")
            edge("in2", "layer", "right" if kind == "Add" else "b")
        else:
            edge("in", "layer")
        edge("layer", "out")
    return draft

positive = []
artifacts = HERE / "artifacts"
artifacts.mkdir(exist_ok=True)
with patch("builtins.exec", side_effect=AssertionError("generated model execution forbidden")), patch("builtins.eval", side_effect=AssertionError("evaluation forbidden")):
    for kind in EXPECTED_KINDS:
        draft = graph(kind)
        generated = generate_model(draft)
        expected_dtype = "float32" if kind == "Embedding" else EXPECTED_SHAPES[kind][1]
        assert generated["tensors"]["out"] == {"shape": EXPECTED_SHAPES[kind][2], "dtype": expected_dtype}
        assert generated["verification"]["status"] == "passed"
        assert generated["verification"]["modelExecution"] == "not_run"
        module_types = [item.func.attr for item in ast.walk(ast.parse(generated["source"])) if isinstance(item, ast.Call) and isinstance(item.func, ast.Attribute) and isinstance(item.func.value, ast.Name) and item.func.value.id == "nn"]
        assert module_types == ([] if kind in ("Input", "Output", "Add", "Concat") else [kind])
        name = artifacts / f"{kind}.json"
        name.write_text(json.dumps({"draft": draft, "generatedSource": generated["source"], "output": generated["tensors"]["out"], "verification": generated["verification"]}, ensure_ascii=False, indent=2) + "\n")
        positive.append({"kind": kind, "nodes": len(draft["nodes"]), "connections": len(draft["edges"]), "output": generated["tensors"]["out"], "sourceConstructorKinds": module_types, "artifact": str(name.relative_to(ROOT))})

negative = []
def rejects(name, draft, expected_code, expected_target=None, generation=False):
    bytes_before = json.dumps(draft, sort_keys=True)
    try:
        (generate_model if generation else validate_draft)(draft)
    except DraftError as error:
        assert expected_code in [item["code"] for item in error.diagnostics], (name, error.diagnostics)
        if expected_target:
            assert any(all(item.get(key) == value for key, value in expected_target.items()) for item in error.diagnostics)
        assert bytes_before == json.dumps(draft, sort_keys=True)
        negative.append({"case": name, "diagnostics": error.diagnostics, "draftPreserved": True})
    else:
        raise AssertionError(f"{name} incorrectly accepted")

mismatch = graph("Linear"); mismatch["nodes"][1]["parameters"]["in_features"] = 8
rejects("Linear upstream last dimension 16 versus input feature 8", mismatch, "linear_input_features_mismatch", {"nodeId": "layer", "parameter": "in_features", "portId": "input"})
conv = graph("Conv2d"); conv["nodes"][0]["parameters"]["shape"] = [1, 16]
rejects("default Input shape cannot feed Conv2d", conv, "input_rank_mismatch", {"nodeId": "layer", "portId": "input"})
embed = graph("Embedding"); embed["nodes"][0]["parameters"]["dtype"] = "float32"
rejects("default float32 Input cannot feed Embedding", embed, "input_dtype_mismatch", {"nodeId": "layer", "portId": "input"})
add = graph("Add"); add["nodes"][-1]["parameters"]["shape"] = [1, 1]
rejects("Add does not broadcast", add, "add_input_shape_mismatch", {"nodeId": "layer"})
for kind in ["Sigmoid", "Tanh", "Softmax", "Conv1d", "AvgPool2d", "BatchNorm1d", "MultiheadAttention", "LSTM", "GRU", "Reshape", "Transpose"]:
    draft = graph("Linear"); draft["nodes"][1]["kind"] = kind; draft["nodes"][1]["parameters"] = {}
    rejects(f"unsupported {kind}", draft, "unsupported_module", {"nodeId": "layer"})
incomplete = graph("Linear"); incomplete["edges"] = []
partial = validate_draft(incomplete)
assert not partial["complete"] and {"unbound-input", "unused-node"} <= {item["code"] for item in partial["issues"]}
rejects("unbound graph cannot generate source", incomplete, "unbound-input", generation=True)
store = DraftStore(artifacts / "saved-drafts")
saved = store.put(incomplete["id"], incomplete, 0)
assert store.get(incomplete["id"]) == saved
try:
    store.put(mismatch["id"], mismatch, 1)
except DraftError as error:
    assert error.diagnostics[0]["code"] == "linear_input_features_mismatch"
    negative.append({"case": "saving contradictory shape is refused", "diagnostics": error.diagnostics, "savedPartialDraftPreserved": store.get(incomplete["id"]) == saved})
else:
    raise AssertionError("contradictory shape unexpectedly saved")

after = [binding(path) for path in INPUTS]
assert before == after, "product bytes changed while this audit ran"
report = {"schema": "archcanvas-ai-novice-static-contract-audit/1", "reviewer": "/root/novice_authoring_review", "reviewerKind": "AI-simulation", "humanParticipantsAdded": 0, "modelsExecuted": False, "sharedBrowserOperated": False, "productFilesWritten": False, "inventory": {"count": len(catalog["modules"]), "parameterCount": 34, "categories": sorted({m["category"] for m in catalog["modules"]}), "catalog": catalog}, "positiveStaticCases": positive, "negativeStaticCases": negative, "incompleteDraftPersistence": {"saveReopenExact": True, "complete": partial["complete"], "issues": partial["issues"]}, "inputBindingsBeforeAndAfterExact": before, "limits": ["Controlled static graphs, not 17 native UI user tasks.", "Generated source was parsed, never imported or executed.", "No current browser pixels or human usability measured by this script."]}
(HERE / "contract-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
print(json.dumps({"positiveStaticCases": len(positive), "negativeStaticCases": len(negative), "inputBindingsExact": len(before), "humanParticipantsAdded": 0, "modelsExecuted": False}, ensure_ascii=False))
