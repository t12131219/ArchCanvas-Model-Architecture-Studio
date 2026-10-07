"""Seed isolated visual-only browser documents from frozen formal inputs."""
import hashlib
import json
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(root / "src"))
from archcanvas_cli.server import DocumentStore

store_dir = root / ".archcanvas/m4-ancestor-corridor-session/documents"
assert not store_dir.exists(), "Do not replace a live session"
store = DocumentStore(store_dir)
records = []
for case in ["transformer-level3-paper-180", "mlp-level0-paper-180", "residual_cnn-level0-paper-180"]:
    path = root / "docs/evidence/browser-visual-matrix-chs-current/captures" / case / "canvas.json"
    data = path.read_bytes()
    document = json.loads(data)
    saved = store.put(document["id"], document, 0)
    assert saved["document"] == document
    records.append({"case": case, "inputPath": str(path.relative_to(root)), "inputBytes": len(data),
        "inputSha256": hashlib.sha256(data).hexdigest(), "documentId": document["id"],
        "storageRevision": saved["revision"], "documentRevision": document["revision"],
        "storedPath": str(store.path(document["id"]).relative_to(root)),
        "storedSha256": hashlib.sha256(store.path(document["id"]).read_bytes()).hexdigest()})
report = {"scope": "Visual-only isolated test service inputs; static source-backed formal documents, no model execution", "records": records}
out = Path(__file__).parent / "session-inputs.json"
with out.open("x") as stream:
    json.dump(report, stream, ensure_ascii=False, indent=2)
    stream.write("\n")
print(json.dumps({"documents": len(records), "output": str(out.relative_to(root))}))
