#!/usr/bin/env python3
"""Apply the separately tested saved-SVG oracle to frozen CPU rerenders."""
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from audit_geometry import ROOT, inspect, primitive_counterexamples


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


manifest_path = HERE / "cpu-scenes.json"
manifest = json.loads(manifest_path.read_text())
cases = []
for item in manifest["cases"]:
    svg = ROOT / item["svgPath"]
    canvas = ROOT / item["inputCanvasPath"]
    assert digest(svg) == item["svgSha256"]
    assert digest(canvas) == item["inputCanvasSha256"]
    cases.append(inspect(svg, json.loads(canvas.read_text()), item["caseId"]))

totals = {"cases": len(cases),
          "endpointDefects": sum(len(case["endpointDefects"]) for case in cases),
          "unrelatedBodyPenetrations": sum(len(case["unrelatedBodyPenetrations"]) for case in cases),
          "unrelatedBodyOverlaps": sum(len(case["unrelatedBodyOverlaps"]) for case in cases),
          "properCrossingsAcrossDifferentTensors": sum(len(case["properCrossingsAcrossDifferentTensors"]) for case in cases)}
output = {"schemaVersion": 1,
          "scope": "Independent saved-SVG geometry observations of 39 final frozen CPU rerenders; these are historical canvas inputs, not new browser captures or inherited browser coverage",
          "humanAcceptanceCertified": False, "browserCoverageInherited": False,
          "primitiveCounterexamples": primitive_counterexamples(),
          "cpuManifestPath": str(manifest_path.relative_to(ROOT)), "cpuManifestSha256": digest(manifest_path),
          "geometryOraclePath": str((HERE.parent / "audit_geometry.py").relative_to(ROOT)), "geometryOracleSha256": digest(HERE.parent / "audit_geometry.py"),
          "totals": totals, "cases": cases,
          "limitations": ["Unrelated bodies use a 2-unit interior inset, and endpoint dots use 0.15-unit tolerance.",
                          "This oracle excludes ancestor interiors and own endpoint bodies; the separate routing-independent oracle checks endpoint bodies and expanded headers.",
                          "Different-tensor edge crossings are observations; this fix does not optimize crossing count or separate shared corridors.",
                          "No browser display timing, physical typography, presented frames, human tasks, or publication acceptance is established."]}
(HERE / "independent-geometry.json").write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n")
print(json.dumps(totals, indent=2))
