"""Finite independent readback of saved bytes, XML and native trial geometry.

No product imports, input dispatch, model execution or performance certification.
"""
import copy
import hashlib
import json
import math
import re
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
STAGE = Path(__file__).resolve().parent
BROWSER = STAGE / "browser"
OUT = STAGE / "root-readback-attempt-1"
OUT.mkdir(exist_ok=False)
checks = []


def check(name, condition, detail=None):
    checks.append({"name": name, "passed": bool(condition), "detail": detail})


def read(path):
    return json.loads(path.read_text())


def binding(path):
    raw = path.read_bytes()
    return {"path": str(path.relative_to(ROOT)), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


saved_path = next((STAGE / "runtime-workspace/documents").glob("canvas*.json"))
saved_bytes = saved_path.read_bytes()
(OUT / "saved-rev10-envelope.json").write_bytes(saved_bytes)
saved = json.loads(saved_bytes)
candidate_path = ROOT / "docs/evidence/m4-readable-grid-next-work/candidate.canvas.json"
scene_path = ROOT / "docs/evidence/m4-readable-grid-next-work/candidate.scene.json"
candidate, scene = read(candidate_path), read(scene_path)
native_path = BROWSER / "07-native-300-four-toggle.complete.json"
native, dom = read(native_path), read(BROWSER / "09-final-rev10-public-dom.json")
final = saved["document"]
check("saved exact source/IR architecture", candidate["architecture"] == final["architecture"])
check("saved Canvas10/storage2", final["revision"] == 10 and saved["revision"] == 2)
adjusted = copy.deepcopy(final)
adjusted["revision"] = candidate["revision"]
adjusted["pinnedObjects"] = candidate["pinnedObjects"]
check("saved only revision and one input pin differ", adjusted == candidate)
pin = "input:model.DenseStress300:features"
check("one unrelated pin", list(final["pinnedObjects"]) == [pin])
check("full SVG read length", len((BROWSER / "09-final-rev10-complete.svg").read_text()) == dom["svgLength"] == 861749)
svg = ET.fromstring((BROWSER / "09-final-rev10-complete.svg").read_bytes())
ns = "{http://www.w3.org/2000/svg}"
metadata = json.loads(svg.find(ns + "metadata").text)
check("public XML current identity", svg.attrib["data-document-id"] == final["id"] and int(svg.attrib["data-revision"]) == 10)
check("XML canonical source facts exact", metadata["sourceFacts"] == scene["sourceFacts"])
check("XML source digest", metadata["sourceDigest"] == final["architecture"]["sourceDigest"])
check("XML IR digest", metadata["irDigest"] == final["architecture"]["irDigest"])
nodes = [g for g in svg.iter(ns + "g") if "data-canonical-id" in g.attrib]
node_by_id = {g.attrib["data-node-id"]: g for g in nodes}
check("304 actual node groups, no duplicates", len(nodes) == len(node_by_id) == 304)
check("scene node identities exact", set(node_by_id) == {n["id"] for n in scene["nodes"]})
for n in scene["nodes"]:
    body = next((r for r in node_by_id[n["id"]].findall(ns + "rect") if "stroke-width" in r.attrib), None)
    check("unchanged body " + n["id"], body is not None and all(float(body.attrib[k]) == n[k] for k in ("x", "y", "width", "height")))
leaves = [n for n in dom["nodes"] if re.fullmatch(r"(?:Linear|ReLU) \d+", n["label"] or "")]
check("300 uniquely source-bound leaves", len(leaves) == len({n["id"] for n in leaves}) == 300)
check("304 bodies within actual canvas rect", len(dom["nodes"]) == 304 and all(n["inside"] for n in dom["nodes"]))
check("actual clamped viewport4096x2700/DPR1", dom["window"] == {"width": 4096, "height": 2700, "dpr": 1})
scale = float(re.search(r"scale\(([^)]+)", dom["paper"]).group(1))
nominal_titles = [float(n["texts"][0]["fontSize"].removesuffix("px")) * scale for n in leaves]
small_text = [float(t["fontSize"].removesuffix("px")) * scale for n in leaves for t in n["texts"]]
check("positive actual glyph rectangles", all(t["rect"]["width"] > 0 and t["rect"]["height"] > 0 for n in leaves for t in n["texts"]))
check("all native trial denominator retained", len(native["trials"]) == 4)
check("native start304/inputpin", len(native["bindingAtStart"]["visibleIds"]) == 304 and native["bindingAtStart"]["pinnedIds"] == [pin])
durations = []
for i, trial in enumerate(native["trials"]):
    before, after = trial["before"], trial["after"]
    check(f"trial{i} exact revision", [before["revision"], after["revision"]] == [6+i, 7+i])
    check(f"trial{i} trusted bounded network operation", trial["trusted"] and trial["targetId"] == "call:instance:model.DenseStress300.network" and trial["operation"] == ("collapse" if i % 2 == 0 else "expand"))
    check(f"trial{i} source/document exact", all(before[k] == after[k] == native["bindingAtStart"][k] for k in ("documentId", "sourceDigest", "irDigest")))
    check(f"trial{i} actual frontier", [len(before["visibleIds"]), len(after["visibleIds"])] == ([304, 4] if i % 2 == 0 else [4, 304]))
    check(f"trial{i} no sample error", trial["error"] is None and trial["bindingValid"] and trial["targetChanged"])
    check(f"trial{i} unrelated pin measured unchanged", len(trial["pins"]) == 1 and trial["pins"][0]["measured"] and trial["pins"][0]["canvasDisplacementPx"] == 0)
    check(f"trial{i} anchor<=8CSSpx", trial["anchorScreenDisplacementPx"] <= 8)
    check(f"trial{i} raw returned arrangements", all(before["anchors"][node]["canvas"] == after["anchors"][node]["canvas"] for node in set(before["anchors"]) & set(after["anchors"])))
    durations.append(trial["nativeInputToNextPaintMs"])
check("four timing durations280/504/248/520", durations == [280, 504, 248, 520])
check("native p95 independently sorted", sorted(durations)[math.ceil(.95 * len(durations))-1] == native["summary"]["nativeInputToNextPaintP95Ms"] == 520)
check("all reexpanded anchors restore", native["trials"][1]["after"]["anchors"] == native["trials"][3]["after"]["anchors"])
validator = ROOT / "scripts/validate_native_performance.mjs"
result = subprocess.run(["node", str(validator), str(native_path)], capture_output=True, text=True)
(OUT / "validator.stdout").write_text(result.stdout)
(OUT / "validator.stderr").write_text(result.stderr)
check("official native receipt validator exit0", result.returncode == 0)
limitations = [
    "520ms is a four-toggle matched subset, not complete continuous input or page INP; numeric target is not passed.",
    "rAF58.5809/s is a whole-window callback cadence, not presented FPS.",
    "No resolved font/hardware/power lock, A/Bx3, medium or human certification.",
    "300 leaf bodies are fully inside, title nominal9.926px/subtitle7.635px; readable-object gate remains unapproved.",
    "Public DOM01/02 used907 mixed node/port groups; they cannot be quoted as907 objects.03/final canonical groups304.",
    "Embedded SVG strings in01/02/03/06 capped200011 chars; only09 full861749 SVG is XML authority.",
    "07 first raw attempt was capped200000 and invalid JSON; full receipt read in13 chunks from same textarea.",
    "Requested4800 width was clamped4096; screenshot clip04 returned top-left900x450, not requested viewport region; offline05 crop is explicit.",
    "Viewport reset after sampling; no calibration to physical publication size or stable all-pixel freshness.",
    "Script/asset filename matches frozen resize build, but HTTP asset byte readback not performed.",
]
report = {"schema": "archcanvas-large-native-finite-readback/1", "checks": checks,
          "passed": sum(c["passed"] for c in checks), "total": len(checks),
          "nominalLeafTitleMinCSSpx": min(nominal_titles), "nominalLeafTextMinCSSpx": min(small_text),
          "actualGlyphTitleMinRectHeight": min(n["texts"][0]["rect"]["height"] for n in leaves),
          "nativeSummary": native["summary"], "elapsedMs": native["elapsedMs"],
          "callbackCadencePerSecond": native["frames"]["fps"], "limitations": limitations,
          "humanParticipants": 0, "presentedFPSCertified": False, "performanceGatePassed": False,
          "readable300Certified": False, "M4": "partial"}
(OUT / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
inputs = [candidate_path, scene_path, native_path, validator, BROWSER / "09-final-rev10-complete.svg", BROWSER / "09-final-rev10-public-dom.json", OUT / "saved-rev10-envelope.json"]
manifest = {"schema": "archcanvas-finite-readback-seal/1", "inputs": [binding(p) for p in inputs],
            "outputs": [binding(p) for p in sorted(OUT.iterdir()) if p.is_file()] + [binding(Path(__file__).resolve())]}
(OUT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
print(json.dumps({"passed": report["passed"], "total": report["total"], "failed": [c["name"] for c in checks if not c["passed"]], "limitations": limitations}, ensure_ascii=False, indent=2))
raise SystemExit(0 if all(c["passed"] for c in checks) else 1)
