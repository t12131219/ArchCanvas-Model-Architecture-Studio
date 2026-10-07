"""Read handwritten fixture roles from nonexecuting generated static IR.

No generated Python is imported or executed. Product generation is an observed
output here, never the source of expected roles. This does not establish runtime
shapes, arbitrary Python correctness, aesthetics or human acceptance.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

import archcanvas_authoring.draft as product

ROOT = Path(__file__).resolve().parent
PROJECT = ROOT.parents[3]


def main() -> None:
    fixtures_path = ROOT / "source-role-handwritten-fixtures.json"
    frozen = fixtures_path.read_bytes()
    fixture_data = json.loads(frozen)
    inputs = ["src/archcanvas_authoring/draft.py", "src/archcanvas_python/frontend.py"]
    bindings = []
    for name in inputs:
        path = PROJECT / name
        if path.exists():
            content = path.read_bytes()
            bindings.append({"path": name, "bytes": len(content), "sha256": hashlib.sha256(content).hexdigest()})
    assert Path(product.__file__).resolve() == PROJECT / "src/archcanvas_authoring/draft.py"
    assert "torch" not in sys.modules, "model framework must not be imported for this static check"
    checks = []
    results = []

    def check(name: str, passed: bool) -> None:
        checks.append({"name": name, "passed": passed})
        assert passed, name

    output_dir = ROOT / "static-generated-readback"
    output_dir.mkdir(exist_ok=False)
    for case in fixture_data["fixtures"]:
        before = json.dumps(case["draft"], sort_keys=True)
        observed = product.generate_model(case["draft"])
        check(case["name"] + ": draft bytes preserved", before == json.dumps(case["draft"], sort_keys=True))
        check(case["name"] + ": framework remains unimported", "torch" not in sys.modules)
        architecture = observed["architecture"]
        bindings_by_id = observed["nodeBindings"]
        check(case["name"] + ": one source binding per handwritten node", len(set(bindings_by_id.values())) == len(case["draft"]["nodes"]))
        by_id = {node["id"]: node for node in architecture["nodes"]}
        fixture_results = []
        for edge in case["draft"]["edges"]:
            source_id = bindings_by_id[edge["source"]["nodeId"]]
            target_id = bindings_by_id[edge["target"]["nodeId"]]
            target_port = observed["portBindings"][edge["target"]["nodeId"]][edge["target"]["portId"]]
            found = [item for item in architecture["edges"] if item["source"]["nodeId"] == source_id
                     and item["target"]["nodeId"] == target_id and item["target"]["portId"] == target_port]
            check(case["name"] + ": exact target binding " + edge["id"], len(found) == 1)
            expected = case["expectedEdgeRoles"][edge["id"]]
            check(case["name"] + ": handwritten edge role " + edge["id"], found[0]["role"] == expected)
            matching_port = [item for item in by_id[target_id]["ports"] if item["id"] == target_port]
            check(case["name"] + ": target port role " + edge["id"], len(matching_port) == 1 and matching_port[0]["role"] == expected)
            fixture_results.append({"edgeId": edge["id"], "expected": expected, "observed": found[0]["role"],
                                    "sourceNodeId": source_id, "targetNodeId": target_id, "targetPortId": target_port})
        for node_id, expected in case["expectedAddCategories"].items():
            check(case["name"] + ": handwritten Add category " + node_id, by_id[bindings_by_id[node_id]]["category"] == expected)
        check(case["name"] + ": no extra generated residual edges",
              Counter(item["role"] for item in architecture["edges"])["residual"] == Counter(case["expectedEdgeRoles"].values())["residual"])
        (output_dir / (case["name"] + ".py")).write_text(observed["source"])
        (output_dir / (case["name"] + ".architecture.json")).write_text(json.dumps(architecture, ensure_ascii=False, indent=2) + "\n")
        results.append({"name": case["name"], "edges": fixture_results, "generatedSourceExecuted": False})
    check("frozen handwritten fixture bytes unchanged", fixtures_path.read_bytes() == frozen)
    result = {"createdUtc": datetime.now(timezone.utc).isoformat(), "status": "passed-bounded-static-source-roles",
              "fixtureSha256": hashlib.sha256(frozen).hexdigest(), "productOrigin": str(Path(product.__file__).resolve()),
              "inputBindings": bindings, "fixtures": results, "checks": checks,
              "passed": sum(item["passed"] for item in checks), "total": len(checks),
              "modelExecution": False, "frameworkImported": "torch" in sys.modules,
              "scope": "Seven hand-enumerated DAGs, exact source target-port edge role/category readback only; not runtime, pixels, beauty, physical publication or human acceptance."}
    (ROOT / "source-role-readback-report.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"status": result["status"], "fixtures": len(results), "passed": result["passed"], "total": len(checks), "modelExecution": False}))


if __name__ == "__main__":
    main()
