"""Apply the bounded proposal policy to nine hash-bound historical frontiers."""
import json
from collections import Counter
from datetime import datetime, timezone
from evaluate_frozen_candidates import HERE, ROOT, binding, propose

out = HERE / "historical-frontier-proposal-attempt-1"
assert not out.exists(), "Evidence is append-only"
out.mkdir()
index_path = ROOT / "docs/evidence/m4-caption-route-current/self-route-review/source-frontier-measurement.json"
index = json.loads(index_path.read_text())
rows, inputs, frontiers = [], [binding(index_path)], []
for record in index["records"]:
    p = ROOT / record["sceneBinding"]["path"]
    actual = binding(p)
    expected = record["sceneBinding"]
    assert actual["bytes"] == expected["bytes"] and actual["sha256"] == expected["sha256"]
    inputs.append(actual)
    scene = json.loads(p.read_text())
    memories = [edge for edge in scene["edges"] if edge["role"] == "memory"]
    frontiers.append({"caseId": record["caseId"], "sceneBinding": actual,
                      "nodes": len(scene["nodes"]), "edges": len(scene["edges"]), "memories": len(memories)})
    for edge in memories:
        rows.append({"case": record["caseId"], "edgeId": edge["id"],
                     "sourceId": edge["sourceId"], "targetId": edge["targetId"], **propose(scene, edge)})
report = {"schema": "archcanvas-historical-frontier-proposal-analysis/1",
          "createdUtc": datetime.now(timezone.utc).isoformat(), "frontiers": frontiers,
          "sourceFrontierCount": len(frontiers), "routeOccurrences": sum(x["edges"] for x in frontiers),
          "memoryOccurrences": len(rows), "statusCounts": Counter(row["status"] for row in rows),
          "rows": rows, "inputBindings": inputs,
          "scope": "Historical nine source-backed frontiers of three models, not the current browser or current production scene capture. No model/product execution. Read-only geometric proposal analysis; expanded endpoint policy keeps historical deep routes unchanged. Current full frontier regeneration remains required before product acceptance."}
(out / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
print(json.dumps({k: report[k] for k in ["sourceFrontierCount", "routeOccurrences", "memoryOccurrences", "statusCounts"]}))
