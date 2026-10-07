"""Independent corruptions of bound route facts; never edits supplied files."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import sys

sys.dont_write_bytecode = True
here = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("routing_case_adapter", here / "audit_cases.py")
adapter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(adapter)


def main():
    if len(sys.argv) != 3:
        raise ValueError("Usage: check_adapter_controls.py PARSED_SCENE_JSON ACTUAL_CANVAS_JSON")
    paths = [Path(value).resolve() for value in sys.argv[1:]]
    scene = json.loads(paths[0].read_text())
    payload = json.loads(paths[1].read_text())
    document = payload.get("document", payload)
    adapter.check_canonical_projection(scene, document)
    cases = [
        ("forged-tensor-cannot-reclassify-crossing-as-shared", lambda s: s["edges"][0].update(tensorId="forged-same-tensor")),
        ("forged-relation-role", lambda s: s["edges"][0].update(role="forged-role")),
        ("empty-canonical-group", lambda s: s["edges"][0].update(canonicalEdgeIds=[])),
        ("duplicate-edge-inside-group", lambda s: s["edges"][0]["canonicalEdgeIds"].append(s["edges"][0]["canonicalEdgeIds"][0])),
        ("canonical-edge-reused-between-routes", lambda s: s["edges"][1].update(canonicalEdgeIds=s["edges"][0]["canonicalEdgeIds"][:])),
        ("missing-canonical-edge", lambda s: s["edges"][0].update(canonicalEdgeIds=["forged-edge"])),
        ("wrong-projected-source-owner", lambda s: s["edges"][0].update(sourceId="forged-visible-owner")),
        ("forged-canonical-source-port", lambda s: s["edges"][0]["source"].update(portId="forged-port")),
    ]
    rows = []
    for name, corrupt in cases:
        changed = deepcopy(scene)
        corrupt(changed)
        reason = None
        try:
            adapter.check_canonical_projection(changed, document)
        except (ValueError, KeyError) as error:
            reason = f"{type(error).__name__}: {error}"
        if reason is None:
            raise AssertionError(f"Contamination unexpectedly accepted: {name}")
        rows.append({"name": name, "rejected": True, "reason": reason})
    print(json.dumps({"schema": "archcanvas-routing-adapter-controls/1", "inputs": [adapter.binding(path) for path in paths],
        "positiveProjectionAccepted": True, "negativeControls": len(rows), "rejected": len(rows), "rows": rows,
        "scope": "Deliberately contaminated in-memory source-bound geometric facts; no actual SVG/Canvas files or product edited.",
        "aestheticCertified": False, "humanCertified": False}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
