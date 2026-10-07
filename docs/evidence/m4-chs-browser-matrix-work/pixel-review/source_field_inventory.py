"""Read-only source-field inventory for explicitly selected evidence cases.

This helper does not view images, infer pixel observations, accept the product,
operate a browser, import product code, or assert screenshot synchronization.
"""
from pathlib import Path
import hashlib
import json
import sys
import xml.etree.ElementTree as ET

from PIL import Image


def binding(path):
    content = path.read_bytes()
    return {
        "path": str(path.resolve()),
        "bytes": len(content),
        "sha256": hashlib.sha256(content).hexdigest(),
    }


def inventory(base, cases):
    bindings, records = [], []
    for case in cases:
        directory = base / "raw" / case
        bindings.extend(binding(path) for path in sorted(directory.iterdir()) if path.is_file())
        observation_file = (
            "dom-observation-correct-variant.json"
            if (directory / "dom-observation-correct-variant.json").is_file()
            else "dom-observation.json"
        )
        observation = json.loads((directory / observation_file).read_text())
        svg = ET.fromstring((directory / "browser-scene.svg").read_text())
        metadata = json.loads(svg.find("{http://www.w3.org/2000/svg}metadata").text)
        envelope = json.loads((directory / "saved-envelope.json").read_text())
        record = {
            "directoryCase": case,
            "observationFile": observation_file,
            "observation": observation,
            "svgRoot": svg.attrib,
            "svgMetadata": {key: metadata[key] for key in (
                "documentId", "revision", "sourceDigest", "irDigest", "widthMm", "heightMm"
            )},
            "visibleNodeLabels": [node.attrib["aria-label"] for node in svg.iter()
                                  if "data-node-id" in node.attrib and "aria-label" in node.attrib],
            "edgeRoles": {role: sum(edge["role"] == role for edge in metadata["renderedBindings"])
                          for role in sorted({edge["role"] for edge in metadata["renderedBindings"]})},
            "envelopeTopRevision": envelope["revision"],
            "canvasDocument": {key: envelope["document"][key] for key in (
                "id", "revision", "pageSpec", "expandedIds"
            )},
            "decodedImages": {},
            "fullDOM": {},
        }
        for name in ("primer.jpg", "screenshot.jpg"):
            with Image.open(directory / name) as image:
                record["decodedImages"][name] = {
                    "format": image.format, "size": list(image.size), "mode": image.mode
                }
        for name in ("before.dom.txt", "after.dom.txt", "export-complete.dom.txt", "post-close.dom.txt"):
            if not (directory / name).is_file():
                continue
            dom = (directory / name).read_text()
            record["fullDOM"][name] = {
                "hasDialog": "- dialog" in dom or "dialog " in dom,
                "revisionLines": [line.strip() for line in dom.splitlines() if "rev " in line],
                "pageLines": [line.strip() for line in dom.splitlines()
                              if "mm" in line or "PAPER " in line or "MONO" in line or " pt" in line],
                "savedLines": [line.strip() for line in dom.splitlines()
                               if "已保存" in line or "画布已保存" in line or "Failed" in line],
                "exportLinks": [line.strip() for line in dom.splitlines() if "/api/exports/" in line],
            }
        record["beforeAfterEqual"] = (
            (directory / "before.dom.txt").read_bytes() == (directory / "after.dom.txt").read_bytes()
        )
        records.append(record)
    return {"scope": "Explicitly selected cases; discovery precedes binding, image views are separately recorded.",
            "inputBindings": bindings, "cases": records}


if __name__ == "__main__":
    output = Path(sys.argv[1])
    base = Path(__file__).resolve().parents[1]
    record = inventory(base, sys.argv[2:])
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        raise SystemExit("Refusing to overwrite an existing inventory")
    output.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n")
    for case in record["cases"]:
        observation = case["observation"]
        print(json.dumps({
            "case": case["directoryCase"],
            "observation": {key: observation[key] for key in (
                "dialogCount", "pageSpec", "expandedIds", "documentBinding", "camera"
            )},
            "svgRoot": case["svgRoot"],
            "nodeCount": len(case["visibleNodeLabels"]),
            "edgeRoles": case["edgeRoles"],
            "envelopeTopRevision": case["envelopeTopRevision"],
            "preflight": case["fullDOM"].get("export-complete.dom.txt", {}).get("pageLines"),
        }, ensure_ascii=False))
    print(json.dumps({"inputCount": len(record["inputBindings"]), "output": binding(output)}, ensure_ascii=False))
