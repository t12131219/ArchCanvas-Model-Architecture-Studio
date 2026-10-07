"""Read-only file verification of the restored preview; no model execution."""
from pathlib import Path
from datetime import datetime, timezone
from hashlib import sha256
from xml.etree import ElementTree as ET
import json

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent

def bind(path):
    path = Path(path)
    data = path.read_bytes()
    return {"path": str(path.relative_to(ROOT)), "bytes": len(data), "sha256": sha256(data).hexdigest()}

clone = json.loads((OUT / "clone-receipt.json").read_text())
clone_checks = []
for record in clone["records"]:
    original, copied = ROOT / record["source"], ROOT / record["copy"]
    original_bytes, copy_bytes = original.read_bytes(), copied.read_bytes()
    clone_checks.append({"source": record["source"], "copy": record["copy"],
                         "exact": original_bytes == copy_bytes and len(copy_bytes) == record["bytes"]
                         and sha256(copy_bytes).hexdigest() == record["sha256"]})

public = json.loads((OUT / "reload.public.json").read_text())
main = [s for s in public["svg"] if "data-document-id" in dict(s["attributes"])]
assert len(main) == 1
svg = ET.fromstring(main[0]["outerHTML"])
metadata = json.loads(svg.find("{http://www.w3.org/2000/svg}metadata").text)
document_id = metadata["documentId"]
document_path = ROOT / ".archcanvas/m4-authoring-preview-20261006-attempt-1/documents" / (document_id + ".json")
envelope = json.loads(document_path.read_text())
document = envelope["document"]
startup = json.loads((OUT / "service.stdout.log").read_text().splitlines()[0])
provenance = startup["capabilities"]["packageProvenance"]
checks = {
    "cloned57FilesStillExact": len(clone_checks) == 57 and all(c["exact"] for c in clone_checks),
    "newManagedIdReopened": document_id == "canvas-architecture-model.AuthoredModel-306378c82c52-704b0c13",
    "savedRevisionZeroReopened": metadata["revision"] == document["revision"] == 0,
    "sourceDigestMatchesSaved": metadata["sourceDigest"] == document["sourceBindingDigest"],
    "irDigestMatchesSaved": metadata["irDigest"] == document["architecture"]["irDigest"],
    "observedCurrentAssetURLs": public["scripts"] == ["/assets/index-ye7sAyyI.js"]
        and public["styles"] == ["/assets/index-C769d2rm.css"],
    "formalRuntimeOrigins": provenance["independent"] and provenance["projectRoot"] == str(ROOT)
        and all(Path(p).is_relative_to(ROOT / "src") for p in provenance["modules"].values()),
    "reopenedSavedNotice": "已重开工作副本及保存的画布" in public["footer"],
    "declaredOutputAliasSubtitle": "model output" in main[0]["outerHTML"],
}
assert all(checks.values()), checks
bindings = [bind(p) for p in sorted(OUT.iterdir()) if p.is_file() and p.name != "receipt.json"]
bindings += [bind(document_path), bind(ROOT / "studio/dist/assets/index-ye7sAyyI.js"),
             bind(ROOT / "studio/dist/assets/index-C769d2rm.css")]
receipt = {
    "createdAt": datetime.now(timezone.utc).isoformat(),
    "scope": "Preview restoration and read-only reopened UI. Outside the frozen acceptance trees.",
    "url": "http://127.0.0.1:40875/", "session": 50016,
    "previousSession": 78032, "previousExitCode": 143,
    "checks": checks, "cloneChecks": clone_checks, "bindings": bindings,
    "publicSVGMetadata": {k: metadata[k] for k in ("documentId", "revision", "sourceDigest", "irDigest", "widthMm", "heightMm")},
    "observations": [
        "Root personally viewed reload.jpg: clear managed four-node figure, 67% zoom, model output caption, no export modal.",
        "First native AX diff after reload said 90%; later public DOM and actual raster said 67%. The earlier AX is not treated as zoom equivalence.",
        "Asset URLs are read from the public DOM; local dist bytes are bound. This handoff does not certify browser cache memory or fresh HTTP asset-byte equality.",
        "New independent live store is used; original sealed saved artifacts are unmodified.",
    ],
    "serviceLiveness": "Startup log plus successful intentional browser reload; PTY session polled running before this receipt.",
    "modelsExecuted": False, "dependenciesInstalled": False,
    "humanParticipants": 0, "M4": "partial", "M5Started": False,
}
(OUT / "receipt.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n")
print(json.dumps({"checks": checks, "receipt": bind(OUT / "receipt.json")}, ensure_ascii=False))
