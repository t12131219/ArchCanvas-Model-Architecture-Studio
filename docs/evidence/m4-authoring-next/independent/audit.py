#!/usr/bin/env python3
"""Run independent hand-calculated graph/AST/IR checks and oracle counterexamples."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import shutil
import sys

from casebook import POSITIVE_CASES, rejection_cases
from oracle import assert_generated, exact

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "src"))
from archcanvas_authoring import DraftError, generate_model, validate_draft
from archcanvas_python import analyze_source

OUT = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_changed(receipt, transformation):
    """Re-analyze changed source and repair identity maps as data only.

    Changing an operator AST can change its canonical occurrence ID. Bind the
    changed source's actual call line/kind to the old occurrence before handing
    it to the oracle, so a dim/order mutation is not rejected merely because an
    old fingerprint became stale. No authoring generator/verifier is called.
    """
    result = deepcopy(receipt)
    source = transformation(result["source"])
    assert source != result["source"]
    old_nodes = {n["id"]: n for n in result["architecture"]["nodes"]}
    architecture = analyze_source(source, result["entry"])
    new_nodes = {n["id"]: n for n in architecture["nodes"]}
    for identity, binding in result["nodeBindings"].items():
        old = old_nodes[binding]
        if binding in new_nodes:
            replacement = new_nodes[binding]
        else:
            replacements = [n for n in architecture["nodes"] if n["kind"] == old["kind"] and
                            n.get("source", {}).get("line") == old.get("source", {}).get("line")]
            assert len(replacements) == 1
            replacement = replacements[0]
        result["nodeBindings"][identity] = replacement["id"]
        for port_name, old_port_id in result["portBindings"][identity].items():
            old_port = next(p for p in old["ports"] if p["id"] == old_port_id)
            matching = [p for p in replacement["ports"] if p["name"] == old_port["name"] and p["direction"] == old_port["direction"]]
            assert len(matching) == 1
            result["portBindings"][identity][port_name] = matching[0]["id"]
    result["source"], result["architecture"] = source, architecture
    return result


def controls(positive):
    items = []
    mlp, cnn, embed, residual, concat = positive[:5]

    def source(name, base, transform):
        items.append((name, base["case"], source_changed(base["receipt"], transform)))

    def data(name, base, transform):
        value = deepcopy(base["receipt"])
        transform(value)
        items.append((name, base["case"], value))

    source("constructor-width", mlp, lambda text: text.replace("in_features=4, out_features=8", "in_features=4, out_features=7"))
    source("constructor-bias", mlp, lambda text: text.replace("bias=False", "bias=True", 1))
    source("constructor-probability", mlp, lambda text: text.replace("p=0.25", "p=0.75"))
    source("constructor-dtype", mlp, lambda text: text.replace("dtype=torch.float32", "dtype=torch.float64", 1))
    source("conv-spatial-parameter", cnn, lambda text: text.replace("stride=[2, 2]", "stride=[1, 1]", 1))
    source("concat-axis", concat, lambda text: text.replace("dim=1", "dim=0"))
    concat_inputs = [p["name"] for n in concat["receipt"]["architecture"]["nodes"] if n["kind"] == "Input" for p in n["ports"]]
    first, second = concat_inputs
    source("concat-ordered-bindings", concat, lambda text: text.replace(f"({first}, {second})", f"({second}, {first})"))
    add = next(n for n in residual["receipt"]["architecture"]["nodes"] if n["kind"] == "Add")
    left, right = add["source"]["expression"].split(" + ")
    source("residual-ordered-bindings", residual, lambda text: text.replace(left + " + " + right, right + " + " + left))
    data("source-side-effect", mlp, lambda value: value.update(source=value["source"] + "\nopen('untouched.txt', 'w').write('forbidden')\n"))
    data("source-hidden-import", mlp, lambda value: value.update(source=value["source"].replace("import torch", "import os\nimport torch", 1)))
    data("source-hidden-constructor", mlp, lambda value: value.update(source=value["source"].replace("        super().__init__()", "        super().__init__()\n        self.extra = nn.Identity()", 1)))
    linear_binding = mlp["receipt"]["nodeBindings"]["first"]
    data("extra-canonical-port", mlp, lambda value: next(n for n in value["architecture"]["nodes"] if n["id"] == linear_binding)["ports"].append({"id": linear_binding + ":in:extra", "name": "extra", "direction": "in", "role": "data", "ordinal": 1}))
    data("wrong-canonical-parameter", mlp, lambda value: next(n for n in value["architecture"]["nodes"] if n["id"] == linear_binding)["parameters"].update(bias=0))
    data("double-draft-binding", mlp, lambda value: value["nodeBindings"].update(last=value["nodeBindings"]["first"]))
    data("wrong-typed-tensor-shape", mlp, lambda value: value["tensors"]["last"].update(shape=[2, 8]))
    data("same-name-foreign-port", residual, lambda value: value["portBindings"]["projection"].update(input=value["portBindings"]["add"]["left"]))
    data("duplicate-canonical-edge", residual, lambda value: value["architecture"]["edges"].append(deepcopy(value["architecture"]["edges"][-1])))
    data("fanout-tensor-split", residual, lambda value: value["architecture"]["edges"][0].update(tensorId="fabricated-other-tensor"))
    data("different-producer-tensor-merge", residual, lambda value: value["architecture"]["edges"][-1].update(tensorId=value["architecture"]["edges"][0]["tensorId"]))
    data("omitted-node", mlp, lambda value: value["architecture"]["nodes"].pop(-2))
    data("fake-output-slot", mlp, lambda value: next(n for n in value["architecture"]["nodes"] if n["kind"] == "Output").update(outputPath=[{"kind": "key", "key": "wrong"}]))
    return items


def main():
    source_paths = [ROOT / "src/archcanvas_authoring/draft.py", ROOT / "src/archcanvas_authoring/__init__.py", ROOT / "src/archcanvas_python/frontend.py"]
    before = {str(path.relative_to(ROOT)): sha(path) for path in source_paths}
    snapshot_id = hashlib.sha256(json.dumps(before, sort_keys=True).encode()).hexdigest()[:16]
    snapshot = OUT / "oracle-source-snapshots" / snapshot_id
    for path in source_paths:
        destination = snapshot / path.relative_to(ROOT)
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists():
            assert sha(destination) == sha(path), "immutable source snapshot changed"
        else:
            shutil.copyfile(path, destination)
    positives, positive_receipts = [], []
    for case in POSITIVE_CASES:
        original = json.dumps(case["draft"], sort_keys=True, allow_nan=False)
        validated = validate_draft(case["draft"])
        assert validated["complete"] is True and validated["issues"] == []
        expected = {identity: {"shape": shape, "dtype": dtype} for identity, (shape, dtype) in case["outputs"].items()}
        exact(validated["tensors"], expected, "declared tensor contracts")
        receipt = generate_model(case["draft"])
        fresh = analyze_source(receipt["source"], receipt["entry"])
        checks = assert_generated(case, receipt, fresh)
        assert json.dumps(case["draft"], sort_keys=True, allow_nan=False) == original
        source_path = OUT / (case["name"] + ".generated.py.txt")
        receipt_path = OUT / (case["name"] + ".receipt.json")
        source_path.write_text(receipt["source"])
        receipt_path.write_text(json.dumps(receipt, ensure_ascii=False, allow_nan=False, indent=2) + "\n")
        positives.append({"name": case["name"], "passed": True, "checks": checks,
                          "sourcePath": str(source_path.relative_to(ROOT)), "sourceSha256": sha(source_path),
                          "receiptPath": str(receipt_path.relative_to(ROOT)), "receiptSha256": sha(receipt_path)})
        positive_receipts.append({"case": case, "receipt": receipt})
    negatives = []
    for case in rejection_cases():
        original = json.dumps(case["draft"], sort_keys=True)
        try:
            (validate_draft if case["rejectAt"] == "validation" else generate_model)(case["draft"])
        except DraftError as error:
            negatives.append({"name": case["name"], "rejectAt": case["rejectAt"], "rejected": True, "error": str(error)})
        else:
            raise AssertionError("Invalid draft accepted: " + case["name"])
        assert json.dumps(case["draft"], sort_keys=True) == original, "negative input mutated"
    oracle_controls = []
    for name, case, receipt in controls(positive_receipts):
        control_directory = OUT / "oracle-counterexamples"
        control_directory.mkdir(exist_ok=True)
        source_path = control_directory / (name + ".py.txt")
        receipt_path = control_directory / (name + ".json")
        source_path.write_text(receipt["source"])
        receipt_path.write_text(json.dumps(receipt, ensure_ascii=False, allow_nan=False, indent=2) + "\n")
        try:
            # Fresh-source equality was checked for positives. Omitting it here
            # deliberately tests the substantive AST/binding oracle itself.
            assert_generated(case, receipt)
        except (AssertionError, KeyError, ValueError) as error:
            oracle_controls.append({"name": name, "rejected": True, "error": str(error),
                                    "changedSourcePath": str(source_path.relative_to(ROOT)), "changedSourceSha256": sha(source_path),
                                    "changedReceiptPath": str(receipt_path.relative_to(ROOT)), "changedReceiptSha256": sha(receipt_path)})
        else:
            raise AssertionError("Oracle accepted deliberate corruption: " + name)
    after = {str(path.relative_to(ROOT)): sha(path) for path in source_paths}
    assert before == after, "audited core changed during check"
    result = {"schemaVersion": 1, "scope": "Independent hand-calculated concrete drafts, narrow nonexecuting Python AST inspection and exact static IR/ports/producer oracle; no runtime, browser, human or publication acceptance",
              "runtimeExecuted": False, "browserOperations": False, "sourceHashes": before,
              "sourceSnapshotPath": str(snapshot.relative_to(ROOT)),
              "liveHashesMatchAtEnd": True, "positiveCases": positives, "negativeCases": negatives,
              "oracleCounterexamples": oracle_controls,
              "summary": {"positive": len(positives), "draftRejected": len(negatives), "oracleRejected": len(oracle_controls), "failed": 0},
              "oracleFiles": [{"path": str(path.relative_to(ROOT)), "sha256": sha(path)} for path in (OUT / "casebook.py", OUT / "oracle.py", OUT / "audit.py")],
              "limitations": ["Concrete expected tensor shapes are declared static facts, never sampled execution.",
                              "The AST inspector intentionally accepts only this generator's narrow declaration subset; a new valid source syntax requires an independent contract update.",
                              "Source-bound document persistence, draft CAS and HTTP session boundaries are checked separately.",
                              "The catalog's full combinatorial shape space, symbolic dimensions, arbitrary PyTorch calls, in-place operations and MHA/LSTM authoring are not certified."]}
    (OUT / "audit.json").write_text(json.dumps(result, ensure_ascii=False, allow_nan=False, indent=2) + "\n")
    print(json.dumps(result["summary"]))


if __name__ == "__main__":
    main()
