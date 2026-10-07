"""Copy source-bound BG observations, checking every byte against the archive.

This capture never executes product code. Outputs are created exclusively.
"""
import hashlib
import json
from pathlib import Path
from urllib.parse import unquote

project = Path(__file__).resolve().parents[3]
archive = project / "docs/evidence/before-m4-ancestor-corridors"
manifest_bytes = (archive / "manifest.json").read_bytes()
manifest = json.loads(manifest_bytes)
sealed = {item["path"]: item for item in manifest["bindings"]}
target = Path(__file__).parent / "baseline"
target.mkdir(exist_ok=False)
bindings = []

def copy(source_path, output_path):
    source_path = unquote(source_path)
    binding = sealed[source_path]
    raw = (project / binding["archivePath"]).read_bytes()
    assert len(raw) == binding["bytes"]
    assert hashlib.sha256(raw).hexdigest() == binding["sha256"]
    output = target / output_path
    with output.open("xb") as stream:
        stream.write(raw)
    row = {"path": str(output.relative_to(project)), "bytes": len(raw),
           "sha256": hashlib.sha256(raw).hexdigest(), "archivedSource": binding}
    bindings.append(row)
    return row

capture_path = "docs/evidence/m4-repeat-outline-work/oracle/after.json"
capture = json.loads((project / sealed[capture_path]["archivePath"]).read_text())
copy(capture_path, "archived-capture.json")
records = []
copied_inputs = {}
for original in capture["records"]:
    case = original["caseId"]
    key = case + ("--detail" if original.get("detailNodeId") else "")
    if case not in copied_inputs:
        copied_inputs[case] = copy(original["inputPath"], case + ".canvas.json")
    assert copied_inputs[case]["sha256"] == original["inputSha256"]
    scene = copy("docs/evidence/m4-repeat-outline-work/oracle/" + original["scenePath"], key + ".scene.json")
    svg = copy("docs/evidence/m4-repeat-outline-work/oracle/" + original["svgPath"], key + ".svg")
    assert svg["sha256"] == original["svgSha256"]
    records.append({"key": key, "caseId": case, "detailNodeId": original.get("detailNodeId"),
                    "input": copied_inputs[case], "scene": scene, "svg": svg})
result = {"schemaVersion": 1, "scope": "independent archive byte copies; no product execution",
          "archiveManifest": {"path": str((archive / "manifest.json").relative_to(project)),
                              "sha256": hashlib.sha256(manifest_bytes).hexdigest()},
          "records": records, "bindings": bindings}
with (target / "capture.json").open("x") as stream:
    json.dump(result, stream, ensure_ascii=False, indent=2)
    stream.write("\n")
print(json.dumps({"records": len(records), "bindings": len(bindings)}))
