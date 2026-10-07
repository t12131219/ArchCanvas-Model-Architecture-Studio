"""Freeze the exact previous verification before changing its product inputs."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

root = Path(__file__).resolve().parents[4]
seal_rel = Path("docs/evidence/m4-repeat-outline-current-verification-sealed.json")
seal_bytes = (root / seal_rel).read_bytes()
assert hashlib.sha256(seal_bytes).hexdigest() == "21086a9a305544d303bb5505a81b19ff070f08bceb727a7d93bb871f0f17a96e"
seal = json.loads(seal_bytes)
assert len(seal["bindings"]) == 1896
target_rel = Path("docs/evidence/before-m4-ancestor-corridors")
target = root / target_rel
assert not target.exists(), "A prior archive must never be overwritten"
inputs = {item["path"]: item for item in seal["bindings"]}
inputs[str(seal_rel)] = {"path": str(seal_rel), "bytes": len(seal_bytes), "sha256": hashlib.sha256(seal_bytes).hexdigest()}
supplement = root / "docs/evidence/m4-repeat-outline-work/acceptance/final-seal-attempt-1"
for path in sorted(supplement.rglob("*")):
    if path.is_file():
        data = path.read_bytes()
        rel = str(path.relative_to(root))
        inputs[rel] = {"path": rel, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
for item in inputs.values():
    data = (root / item["path"]).read_bytes()
    assert len(data) == item["bytes"] and hashlib.sha256(data).hexdigest() == item["sha256"], item["path"]
records = []
for rel, item in sorted(inputs.items()):
    dest_rel = target_rel / "files" / rel
    dest = root / dest_rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    data = (root / rel).read_bytes()
    with dest.open("xb") as stream:
        stream.write(data)
    assert dest.read_bytes() == data
    records.append({**item, "archivePath": str(dest_rel)})
manifest = {"schemaVersion": 1, "createdAt": datetime.now(timezone.utc).isoformat(),
    "previousSeal": str(seal_rel), "previousSealSha256": hashlib.sha256(seal_bytes).hexdigest(),
    "sealedBindingsAndSeal": 1897, "supplementalFinalReadbackFiles": len(records) - 1897,
    "bindingCount": len(records), "bindings": records}
with (target / "manifest.json").open("x") as stream:
    json.dump(manifest, stream, ensure_ascii=False, indent=2)
    stream.write("\n")
print(json.dumps({"archived": len(records), "sealedInputs": 1897, "allExact": True,
    "manifest": str(target_rel / "manifest.json")}))
