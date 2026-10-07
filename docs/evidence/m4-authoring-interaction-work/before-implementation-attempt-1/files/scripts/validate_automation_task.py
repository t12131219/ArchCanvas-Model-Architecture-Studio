#!/usr/bin/env python3
"""Read-only independent field/geometry audit of the predeclared UI task.

No product imports, renderer invocation, raw rewriting, or research certification.
Missing evidence stays unknown. Only an explicit --output report is written.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import re
from datetime import datetime
from pathlib import Path
import xml.etree.ElementTree as ET


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(value):
    return digest(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode())


def index(items, key="id"):
    result = {item[key]: item for item in items}
    if len(result) != len(items):
        raise ValueError(f"Duplicate {key}")
    return result


def number(value):
    return type(value) in (int, float) and math.isfinite(value)


def close(a, b, tolerance=1e-6):
    return number(a) and number(b) and abs(a - b) <= tolerance


def shifted(rect, dx, dy):
    result = copy.deepcopy(rect)
    result["x"] += dx
    result["y"] += dy
    return result


def same_rect(a, b):
    return all(close(a.get(k), b.get(k)) for k in ("x", "y", "width", "height"))


def camera(snapshot):
    # Read the exposed pre-input style; do not infer camera from output geometry.
    style = snapshot["cameraStyle"]
    match = re.search(r"translate\(\s*([-+.\deE]+)px\s*,\s*([-+.\deE]+)px\s*\)\s*scale\(\s*([-+.\deE]+)\s*\)", style)
    if not match:
        raise ValueError("Unsupported or missing exposed camera transform")
    x, y, zoom = map(float, match.groups())
    if not all(number(v) for v in (x, y, zoom)) or zoom <= 0:
        raise ValueError("Invalid camera scalars")
    return {"x": x, "y": y, "zoom": zoom}


def intersects(rect, viewport):
    return (rect["x"] + rect["width"] > viewport["x"] and rect["x"] < viewport["x"] + viewport["width"]
            and rect["y"] + rect["height"] > viewport["y"] and rect["y"] < viewport["y"] + viewport["height"])


def endpoints(path):
    """Endpoints of the declared absolute M/V/H orthogonal edge path only."""
    tokens = re.findall(r"[A-Za-z]|[-+]?(?:\d*\.\d+|\d+)(?:[eE][-+]?\d+)?", path)
    if not tokens or tokens[0] != "M":
        raise ValueError("Unsupported edge path")
    x, y = float(tokens[1]), float(tokens[2])
    start, pos = (x, y), 3
    while pos < len(tokens):
        command = tokens[pos]
        if command not in ("H", "V") or pos + 1 >= len(tokens):
            raise ValueError("Only absolute M/H/V paths are audited")
        value = float(tokens[pos + 1])
        if command == "H":
            x = value
        else:
            y = value
        pos += 2
    return start, (x, y)


class Audit:
    def __init__(self):
        self.checks = []
        self.inputs = []
        self.observations = {}

    def check(self, name, condition, detail=None):
        self.checks.append({"name": name, "status": "pass" if condition else "fail", "detail": detail})

    def unknown(self, name, detail):
        self.checks.append({"name": name, "status": "unknown", "detail": detail})

    def read(self, path, label, json_file=True):
        if path is None:
            self.unknown(label, "No evidence path supplied.")
            return None
        path = Path(path)
        if not path.is_file():
            self.unknown(label, f"Evidence file absent: {path}")
            return None
        raw = path.read_bytes()
        self.inputs.append({"label": label, "path": str(path.resolve()), "sha256": digest(raw), "bytes": len(raw)})
        return json.loads(raw) if json_file else raw

    def guard(self, label, callback):
        try:
            return callback()
        except (ValueError, TypeError, KeyError, IndexError, StopIteration, ET.ParseError) as error:
            self.check(label + ".structure", False, str(error))
            return None

    def report(self):
        counts = {status: sum(c["status"] == status for c in self.checks) for status in ("pass", "fail", "unknown")}
        return {"schemaVersion": 1, "protocol": "archcanvas-independent-automation-task-audit/1",
                "status": "failed" if counts["fail"] else "verified-with-evidence-gaps" if counts["unknown"] else "verified",
                "humanSuccessCertified": False, "researchGate": "not_run", "counts": counts,
                "inputFiles": self.inputs, "checks": self.checks, "observations": self.observations,
                "auditor": {"path": str(Path(__file__).resolve()), "sha256": digest(Path(__file__).read_bytes()),
                    "runtimeDependencies": "Python standard library; no product imports/rendering"},
                "limitations": ["This verifies supplied recorded fields, not their capture time or authenticity.",
                    "DOM geometry does not establish presented paint, smoothness, or readable 85 mm text.",
                    "PDF header/hash/receipt/input matching is not independent PDF content certification.",
                    "Automation is excluded from the real researcher success denominator."]}


def binding_checks(audit, label, snapshot, plan, baseline):
    metadata = snapshot["metadata"]
    basis = plan["expectedBasis"]
    for key in ("documentId", "sourceDigest", "irDigest"):
        audit.check(label + "." + key, metadata[key] == basis[key])
    audit.check(label + ".documentAttribute", snapshot["documentId"] == metadata["documentId"])
    audit.check(label + ".revisionAttribute", snapshot["revision"] == metadata["revision"])
    nodes = index(snapshot["nodes"])
    baseline_nodes = index(baseline["architecture"]["nodes"])
    audit.check(label + ".canonicalNodes", all(n["id"] == n["canonicalId"] and n["id"] in baseline_nodes for n in nodes.values()))
    rendered = index(metadata["renderedNodes"], "sceneNodeId")
    audit.check(label + ".renderedNodeMapping", set(rendered) == set(nodes) and all(rendered[k]["canonicalNodeId"] == nodes[k]["canonicalId"] for k in nodes))
    edges = index(snapshot["edges"])
    bindings = index(metadata["renderedBindings"], "sceneEdgeId")
    canonical_edges = index(baseline["architecture"]["edges"])
    audit.check(label + ".edgeMapping", set(edges) == set(bindings))
    for identity, binding in bindings.items():
        originals = [canonical_edges[k] for k in binding["canonicalEdgeIds"]]
        # Projected bindings may collapse multiple edges; exact unchanged scene
        # metadata is compared separately. Check canonical membership/tensor/role.
        audit.check(label + ".canonicalBinding." + identity,
                    bool(originals) and all(e["tensorId"] == binding["tensorId"] and e["role"] == binding["role"] for e in originals)
                    and edges[identity]["tensorId"] == binding["tensorId"])
    expected = {k: v for k, v in plan["edgeBindingOracle"].items() if k not in ("id", "selectionRequirement")}
    actual = bindings[plan["edgeBindingOracle"]["id"]]
    audit.check(label + ".predeclaredEdge18Binding", all(actual[k] == v for k, v in expected.items()) and actual["canonicalEdgeIds"] == ["edge:18"])


def intended_dom(audit, label, snapshot, plan):
    fields = plan["expectedSavedFields"]
    nodes = index(snapshot["nodes"])
    encoder = nodes[plan["canonicalTargets"]["encoder"]]
    audit.check(label + ".alias", encoder["label"] == next(iter(fields["displayAliases"].values())))
    audit.check(label + ".monochromeBody", encoder["body"]["fill"] == "#ffffff")
    edge = index(snapshot["edges"])["edge:18"]
    audit.check(label + ".edgeStyle", edge["width"] == 2 and edge["dashed"] == "5 4" and edge["stroke"] == "#56616b")
    legend = index(snapshot["legend"])["legend:residual"]
    audit.check(label + ".legendLabel", legend["text"] == fields["legendItemById"]["label"])
    annotations = snapshot["annotations"]
    expected = fields["newAnnotation"]
    audit.check(label + ".annotationCount", len(annotations) == expected["count"])
    audit.check(label + ".annotationFields", len(annotations) == 1 and re.fullmatch(expected["idRegex"], annotations[0]["id"]) is not None
                and annotations[0]["text"] == expected["text"] and annotations[0]["width"] == expected["width"])
    audit.check(label + ".frontierContains", set(fields["expandedIdsContains"]).issubset(snapshot["expandedIds"]))
    audit.check(label + ".pinContains", set(fields["pinnedObjectsContains"]).issubset(snapshot["pinnedIds"]))
    audit.check(label + ".physicalWidth", snapshot["metadata"]["widthMm"] == fields["pageSpec"]["widthMm"])


def compare_dom(audit, label, before, actual, plan, dx=0, dy=0, screen=True):
    target = plan["canonicalTargets"]["movedNode"]
    expected_nodes, actual_nodes = index(before["nodes"]), index(actual["nodes"])
    audit.check(label + ".allNodeIdentities", set(expected_nodes) == set(actual_nodes))
    for identity in sorted(set(expected_nodes) & set(actual_nodes)):
        expected = copy.deepcopy(expected_nodes[identity])
        if identity == target:
            expected["body"] = shifted(expected["body"], dx, dy)
            zoom = camera(before)["zoom"]
            expected["screen"] = shifted(expected["screen"], dx * zoom, dy * zoom)
        got = actual_nodes[identity]
        audit.check(label + ".node." + identity,
                    same_rect(expected["body"], got["body"]) and all(expected[k] == got[k] for k in ("canonicalId", "label"))
                    and all(expected["body"][k] == got["body"][k] for k in ("fill", "stroke")),
                    {"expected": expected["body"], "actual": got["body"]})
        audit.check(label + ".nodeOrigin." + identity, close(expected["body"]["x"], got["body"]["x"]) and close(expected["body"]["y"], got["body"]["y"]))
        if screen:
            audit.check(label + ".recordedScreenRect." + identity, same_rect(expected["screen"], got["screen"]), {"expected": expected["screen"], "actual": got["screen"]})
    for key in ("expandedIds", "pinnedIds", "annotations", "legend", "viewBox"):
        audit.check(label + ".stable." + key, before[key] == actual[key])
    if screen:
        audit.check(label + ".camera", camera(before) == camera(actual))
        audit.check(label + ".viewport", before["viewport"] == actual["viewport"], {"expected": before["viewport"], "actual": actual["viewport"]})
        audit.check(label + ".paperStyle", before["cameraStyle"] == actual["cameraStyle"])
    else:
        audit.unknown(label + ".cameraContinuity", "Reload may fit camera. Only canvas geometry is compared; this is not persistence of camera.")
    for key in ("sourceDigest", "irDigest", "documentId", "sourceFacts", "sourceFactScope", "renderedNodes", "renderedBindings", "widthMm", "heightMm"):
        audit.check(label + ".stableMetadata." + key, before["metadata"][key] == actual["metadata"][key])
    edges, got_edges = index(before["edges"]), index(actual["edges"])
    bindings = index(before["metadata"]["renderedBindings"], "sceneEdgeId")
    audit.check(label + ".edgeIdentities", set(edges) == set(got_edges))
    for identity in sorted(set(edges) & set(got_edges)):
        expected, got = edges[identity], got_edges[identity]
        audit.check(label + ".edgeFields." + identity, {k: v for k, v in expected.items() if k != "path"} == {k: v for k, v in got.items() if k != "path"})
        b = bindings[identity]
        incident = b["source"]["nodeId"] == target or b["target"]["nodeId"] == target
        if not incident or (dx == 0 and dy == 0):
            audit.check(label + ".edgePath." + identity, expected["path"] == got["path"], {"expected": expected["path"], "actual": got["path"]})
        else:
            first, last = endpoints(expected["path"])
            got_first, got_last = endpoints(got["path"])
            if b["source"]["nodeId"] == target:
                first = (first[0] + dx, first[1] + dy)
            if b["target"]["nodeId"] == target:
                last = (last[0] + dx, last[1] + dy)
            audit.check(label + ".incidentEndpoints." + identity, all(close(a, b) for a, b in zip(first + last, got_first + got_last)))


def saved_checks(audit, label, envelope, dom, plan, baseline):
    document = envelope["document"]
    fields, basis = plan["expectedSavedFields"], plan["expectedBasis"]
    audit.check(label + ".storageEnvelope", type(envelope["revision"]) is int and envelope["revision"] >= 0)
    audit.check(label + ".sourceArchitectureExact", document["architecture"] == baseline["architecture"])
    audit.check(label + ".documentSourceIdentity", document["id"] == basis["documentId"] and document["sourceBindingDigest"] == basis["sourceDigest"])
    for key in ("displayAliases", "nodeStyleOverrides", "edgeStyleOverrides", "pageSpec"):
        expected = copy.deepcopy(baseline[key])
        for k, value in fields[key].items():
            if isinstance(value, dict):
                expected[k] = {**expected.get(k, {}), **value}
            else:
                expected[k] = value
        audit.check(label + ".intended." + key, document[key] == expected)
    expected_legend = copy.deepcopy(baseline["legendItems"])
    for item in expected_legend:
        if item["id"] == fields["legendItemById"]["id"]:
            item["label"] = fields["legendItemById"]["label"]
    audit.check(label + ".legendExact", document["legendItems"] == expected_legend)
    annotations = document["annotations"]
    expected = fields["newAnnotation"]
    audit.check(label + ".annotationIntended", len(annotations) == 1 and re.fullmatch(expected["idRegex"], annotations[0]["id"]) is not None
                and annotations[0]["text"] == expected["text"] and annotations[0]["width"] == expected["width"])
    audit.check(label + ".pinSet", set(document["pinnedObjects"]) == set(baseline["pinnedObjects"]) | set(fields["pinnedObjectsContains"]))
    if dom is not None:
        audit.check(label + ".domRevision", document["revision"] == dom["revision"])
        audit.check(label + ".domFrontier", document["expandedIds"] == dom["expandedIds"])
        audit.check(label + ".domPins", document["pinnedObjects"] == dom["pinnedIds"])
        dom_annotations = [{k: a[k] for k in ("id", "text", "x", "y", "width")} for a in dom["annotations"]]
        audit.check(label + ".domAnnotationExact", annotations == dom_annotations)
        by_id = index(document["architecture"]["nodes"])
        rendered = index(dom["nodes"])
        for identity, node in rendered.items():
            parent_id = by_id[identity].get("parentId")
            parent = rendered.get(parent_id)
            # Canvas local coordinates are relative to the rendered canonical
            # parent origin. This uses recorded hierarchy and rectangles only.
            x = node["body"]["x"] - (parent["body"]["x"] if parent else 0)
            y = node["body"]["y"] - (parent["body"]["y"] if parent else 0)
            position = document["layout"][identity]
            audit.check(label + ".savedLocalGeometry." + identity, close(position["x"], x) and close(position["y"], y),
                        {"expectedFromRecordedDom": {"x": x, "y": y}, "saved": position})
    return document


def native_checks(audit, raw, before, after, plan):
    target = plan["canonicalTargets"]["movedNode"]
    trials = [t for t in raw["trials"] if t["spec"]["operation"] == "drag" and t["spec"]["targetIds"] == [target]]
    audit.check("native.uniquePlannedDrag", len(trials) == 1)
    if len(trials) != 1:
        return
    trial = trials[0]
    events = [e for e in raw["events"] if e["trialId"] == trial["id"]]
    down = next((e for e in events if e["id"] == trial["firstEventId"]), None)
    audit.check("native.targetDown", bool(down) and down["trusted"] and down["type"] == "pointerdown" and down["button"] == 0
                and down["target"]["nodeId"] == target and down["target"]["kind"] == "node")
    if not down:
        return
    ups = [e for e in events if e["type"] == "pointerup" and e["pointerId"] == down["pointerId"] and e["eventAt"] >= down["eventAt"]]
    audit.check("native.uniquePointerUp", len(ups) == 1)
    if len(ups) != 1:
        return
    up = ups[0]
    moves = [e for e in events if e["type"] == "pointermove" and e["pointerId"] == down["pointerId"] and down["eventAt"] <= e["eventAt"] <= up["eventAt"]]
    audit.check("native.trustedContinuousGesture", up["trusted"] and len(moves) > 0 and all(e["trusted"] for e in moves)
                and not any(e["type"] == "pointercancel" for e in events))
    delta = plan["moveOracle"]["desiredScreenDeltaCssPixels"]
    audit.check("native.predeclaredScreenDelta", close(up["x"] - down["x"], delta["x"]) and close(up["y"] - down["y"], delta["y"]),
                {"observed": {"x": up["x"] - down["x"], "y": up["y"] - down["y"]}, "predeclared": delta})
    for name, dom in (("before", before), ("after", after)):
        recorded = trial[name]
        audit.check("native." + name + ".snapshotBinding", recorded["documentId"] == dom["documentId"] and recorded["revision"] == dom["revision"]
                    and recorded["sourceDigest"] == dom["metadata"]["sourceDigest"] and recorded["irDigest"] == dom["metadata"]["irDigest"])
        audit.check("native." + name + ".targetGeometry", same_rect(recorded["objects"][target]["canvas"], index(dom["nodes"])[target]["body"]))


def svg_snapshot(raw):
    root = ET.fromstring(raw)
    name = lambda e: e.tag.split("}")[-1]
    metadata = json.loads(next(e for e in root if name(e) == "metadata").text)
    result = {"metadata": metadata, "nodes": [], "edges": [], "annotations": [], "legend": []}
    for group in root.iter():
        attr = group.attrib
        if "data-canonical-id" in attr:
            body = next(e for e in group if name(e) == "rect" and "stroke-width" in e.attrib)
            result["nodes"].append({"id": attr["data-node-id"], "canonicalId": attr["data-canonical-id"], "label": attr["aria-label"],
                                    "body": {**{k: float(body.attrib[k]) for k in ("x", "y", "width", "height")},
                                             **{k: body.attrib[k] for k in ("fill", "stroke")}}})
        if "data-edge-id" in attr:
            path = next(e for e in group if name(e) == "path")
            result["edges"].append({"id": attr["data-edge-id"], "tensorId": attr["data-tensor-id"], "path": path.attrib["d"],
                                    "stroke": path.attrib["stroke"], "width": float(path.attrib["stroke-width"]), "dashed": path.attrib.get("stroke-dasharray")})
        if "data-annotation-id" in attr:
            body = next(e for e in group if name(e) == "rect")
            lines = [e.text or "" for e in group.iter() if name(e) == "tspan"]
            result["annotations"].append({"id": attr["data-annotation-id"], "text": " ".join(lines),
                                          **{k: float(body.attrib[k]) for k in ("x", "y", "width", "height")}})
        if "data-legend-id" in attr:
            text = next(e for e in group if name(e) == "text")
            body = next(e for e in group if name(e) == "rect")
            result["legend"].append({"id": attr["data-legend-id"], "text": "".join(text.itertext())})
            if attr["data-legend-id"] == "legend:residual":
                result["residualColor"] = body.attrib["fill"]
                result["residualAddGlyph"] = any(name(e) == "circle" and e.attrib.get("r") == "8" for e in group.iter()) and any(name(e) == "path" and e.attrib.get("d") == "M-4 0H4M0-4V4" for e in group.iter())
    result["documentId"] = root.attrib["data-document-id"]
    result["revision"] = int(root.attrib["data-revision"])
    result["viewBox"] = root.attrib["viewBox"]
    return root, result


def export_checks(audit, directory, saved, final_dom, plan, baseline):
    directory = Path(directory)
    label = "export." + directory.name
    document = audit.read(directory / "document.json", label + ".input")
    if document is None:
        return
    audit.check(label + ".exactFinalCanvasInput", document == saved, {"inputCanonicalSha256": canonical(document), "savedCanonicalSha256": canonical(saved)})
    receipts = list(directory.glob("figure.*.receipt.json"))
    audit.check(label + ".uniqueReceipt", len(receipts) == 1)
    if len(receipts) != 1:
        return
    receipt = audit.read(receipts[0], label + ".receipt")
    fmt = receipt["format"]
    audit.check(label + ".supportedFormat", fmt in ("svg", "pdf"))
    raw = audit.read(directory / ("figure." + fmt), label + ".figure", False)
    if raw is None:
        return
    audit.check(label + ".outputBytes", receipt["outputDigest"] == digest(raw) and receipt["bytes"] == len(raw))
    for key in ("documentId", "sourceDigest", "irDigest"):
        audit.check(label + ".receipt." + key, receipt[key] == plan["expectedBasis"][key])
    audit.check(label + ".receipt.revision", receipt["revision"] == saved["revision"])
    audit.check(label + ".receipt.widthMm", receipt["widthMm"] == 85)
    audit.check(label + ".receipt.documentScope", receipt["exportScope"]["kind"] == "document")
    if fmt == "pdf":
        audit.check(label + ".pdfSignature", raw.startswith(b"%PDF-"))
        audit.unknown(label + ".independentPdfContent", "No independent PDF reconversion/content oracle; receipt and bytes only.")
        return fmt
    root, svg = svg_snapshot(raw)
    binding_checks(audit, label + ".svg", svg, plan, baseline)
    actual_nodes, expected_nodes = index(svg["nodes"]), index(final_dom["nodes"])
    audit.check(label + ".svg.allFinalNodes", actual_nodes == {k: {field: value for field, value in n.items() if field != "screen"} for k, n in expected_nodes.items()})
    for key in ("edges", "annotations", "legend", "viewBox"):
        audit.check(label + ".svg.final." + key, svg[key] == final_dom[key])
    for key in ("renderedNodes", "renderedBindings", "sourceFacts", "sourceFactScope"):
        audit.check(label + ".svg.finalMetadata." + key, svg["metadata"][key] == final_dom["metadata"][key])
    width = float(root.attrib["width"].removesuffix("mm"))
    height = float(root.attrib["height"].removesuffix("mm"))
    viewbox = list(map(float, root.attrib["viewBox"].split()))
    audit.check(label + ".svg.physicalDimensions", root.attrib["width"].endswith("mm") and root.attrib["height"].endswith("mm") and width == 85 and height > 0
                and len(viewbox) == 4 and abs(height - width * viewbox[3] / viewbox[2]) <= .011)
    audit.check(label + ".svg.residualMonoGlyph", svg.get("residualColor") == "#ffffff" and svg.get("residualAddGlyph") is True)
    audit.check(label + ".svg.publicationControls", not any("data-expand-id" in e.attrib or e.attrib.get("role") == "button" or e.attrib.get("tabindex") is not None for e in root.iter()))
    font_sizes = [float(e.attrib["font-size"]) for e in root.iter() if e.tag.split("}")[-1] == "text" and "font-size" in e.attrib]
    min_text_pt = min(font_sizes) * width / viewbox[2] * 72 / 25.4
    annotation_overlaps = {
        a["id"]: [n["id"] for n in svg["nodes"] if n["id"] not in final_dom["expandedIds"] and intersects(a, n["body"])]
        for a in svg["annotations"]}
    audit.observations[label + ".publication"] = {"widthMm": width, "heightMm": height,
        "minimumExplicitTextFontSizeCanvasUnits": min(font_sizes), "minimumTextPointSizeAtDeclaredWidth": min_text_pt,
        "annotationLeafBodyOverlaps": annotation_overlaps, "readabilityCertified": False}
    audit.unknown(label + ".visualReadability", "Inspect actual opened export screenshot at intended size; field/XML equality cannot establish aesthetics or text readability.")
    return fmt


def study_checks(audit, study, saved, plan):
    audit.check("study.automationOnly", study["participantKind"] == "automation")
    audit.check("study.protocol", study["protocol"] == "archcanvas-m4-research-task/1" and study["schemaVersion"] == 1)
    checkpoints = study["checkpoints"]
    audit.check("study.fiveSelfReportedCheckpoints", [c["task"] for c in checkpoints] == [1, 2, 3, 4, 5]
                and all(c["selfReportedComplete"] is True for c in checkpoints) and study["outcome"] == "completed")
    audit.check("study.finalRevision", int(checkpoints[-1]["observation"]["visualRevision"]) == saved["revision"])
    for checkpoint in checkpoints:
        observation = checkpoint["observation"]
        audit.check("study.binding.task" + str(checkpoint["task"]), all(observation[k] == plan["expectedBasis"][k] for k in ("documentId", "sourceDigest", "irDigest")))
    elapsed = (datetime.fromisoformat(study["finishedAt"].replace("Z", "+00:00"))
               - datetime.fromisoformat(study["startedAt"].replace("Z", "+00:00"))).total_seconds() * 1000
    audit.check("study.elapsedClockConsistency", abs(elapsed - checkpoints[-1]["elapsedMs"]) <= 2)
    audit.check("study.finalCurrentExportLinks", bool(checkpoints[-1]["observation"]["exportLinks"]))
    audit.observations["study"] = {"participantKind": study["participantKind"], "participantCode": study["participantCode"],
        "selfReportedCheckpointCount": len(checkpoints), "elapsedMs": checkpoints[-1]["elapsedMs"],
        "environment": study["environment"], "durationIsInputLatency": False, "includedInResearcherDenominator": False,
        "checkpoint2Revision": checkpoints[1]["observation"]["visualRevision"],
        "checkpoint2ExpandedNodes": checkpoints[1]["observation"]["expandedNodes"],
        "checkpoint5CurrentExportLinks": checkpoints[-1]["observation"]["exportLinks"]}
    audit.unknown("study.checkpoint2EnhancedFields", "Checkpoint2 precedes later FFN/edge enhancements. Recorder did not capture field values; final edge style cannot be assigned to checkpoint2.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", required=True, type=Path)
    parser.add_argument("--baseline", required=True, type=Path)
    for name in ("before", "after", "undo", "redo", "reopened", "saved-before-reload", "saved-after-reload", "raw-input", "color-dom", "study", "final-environment"):
        parser.add_argument("--" + name, type=Path)
    parser.add_argument("--export-dir", action="append", type=Path, default=[])
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    protected_inputs = [args.plan, args.baseline, *[getattr(args, name.replace("-", "_")) for name in
        ("before", "after", "undo", "redo", "reopened", "saved-before-reload", "saved-after-reload", "raw-input", "color-dom", "study", "final-environment")]]
    protected_inputs += [p for directory in args.export_dir if directory.is_dir() for p in directory.iterdir()]
    if args.output.resolve() in {p.resolve() for p in protected_inputs if p is not None}:
        parser.error("--output must not replace any supplied input evidence")
    audit = Audit()
    plan = audit.read(args.plan, "predeclaredPlan")
    baseline = audit.read(args.baseline, "frozenBaseline")
    doms = {name: audit.read(getattr(args, name), name + "DOM") for name in ("before", "after", "undo", "redo", "reopened")}
    if plan is not None and baseline is not None:
        audit.check("plan.notAnObservedOutcome", plan["status"] == "predeclared-intent-and-baseline-oracle-not-observed-outcome")
        audit.check("plan.baselineIdentity", baseline["id"] == plan["expectedBasis"]["documentId"] and all(baseline["architecture"][k] == plan["expectedBasis"][k] for k in ("sourceDigest", "irDigest")))
        for label, dom in doms.items():
            if dom is not None:
                audit.guard(label, lambda label=label, dom=dom: (binding_checks(audit, label, dom, plan, baseline), intended_dom(audit, label, dom, plan)))
        before = doms["before"]
        if before is not None:
            def movement():
                zoom = camera(before)["zoom"]
                delta = plan["moveOracle"]["desiredScreenDeltaCssPixels"]
                # Math.round for declared positive displacement, independent of output.
                dx, dy = [4 * math.floor(delta[k] / zoom / 4 + .5) for k in ("x", "y")]
                audit.check("move.exactPreInputZoom", zoom == 1, {"camera": camera(before), "predeclaredCanvasDelta": {"x": dx, "y": dy}})
                for label, displacement in (("after", (dx, dy)), ("undo", (0, 0)), ("redo", (dx, dy))):
                    if doms[label] is not None:
                        audit.guard(label + ".comparison", lambda label=label, displacement=displacement: compare_dom(audit, label, before, doms[label], plan, *displacement))
                for earlier, later in (("before", "after"), ("after", "undo"), ("undo", "redo")):
                    if doms[earlier] is not None and doms[later] is not None:
                        audit.check(later + ".revisionStep", doms[later]["revision"] == doms[earlier]["revision"] + 1)
                pin = index(before["nodes"])[plan["canonicalTargets"]["protectedPin"]]
                audit.check("pin.beforeCanvasPresent", all(number(pin["body"][k]) for k in ("x", "y", "width", "height")))
                if not intersects(pin["screen"], before["viewport"]):
                    audit.unknown("pin.screenCoverage", "Protected pin is offscreen in pre-input DOM. Recorded screen rect arithmetic is not observed visible pin coverage.")
            audit.guard("movement", movement)
        if doms["redo"] is not None and doms["reopened"] is not None:
            audit.guard("reload.comparison", lambda: compare_dom(audit, "reload", doms["redo"], doms["reopened"], plan, screen=False))
            audit.check("reload.visualRevision", doms["redo"]["revision"] == doms["reopened"]["revision"])
        if doms["after"] is not None and doms["redo"] is not None:
            audit.guard("redoAfterExactCanvas", lambda: compare_dom(audit, "redoAfterExactCanvas", doms["after"], doms["redo"], plan, screen=False))
        audit.unknown("annotation.initialPosition", "SVG viewBox immediately before Add annotation was not captured. Later x/y cannot prove the predeclared initial placement rule.")
        audit.unknown("history.hiddenSavedFields", "DOM snapshots cannot prove hidden saved overrides/layoutByFrontier were restored by undo/redo without per-phase document snapshots.")
        color = audit.read(args.color_dom, "colorDOM")
        if color is not None:
            fields = plan["expectedSavedFields"]
            audit.check("color.actualAliasAndFill", color["documentId"] == plan["expectedBasis"]["documentId"] and color["fill"] == next(iter(fields["nodeStyleOverrides"].values()))["fill"]
                        and color["label"] == next(iter(fields["displayAliases"].values())) and color["legend"] == fields["legendItemById"]["label"])
            audit.check("color.annotationIdentity", doms["before"] is not None and color["annotation"] == [{k: a[k] for k in ("id", "text")} for a in doms["before"]["annotations"]])
        saved_documents = {}
        for name, dom_name in (("saved_before_reload", "redo"), ("saved_after_reload", "reopened")):
            value = audit.read(getattr(args, name), name)
            if value is not None:
                result = audit.guard(name, lambda name=name, value=value, dom_name=dom_name: saved_checks(audit, name, value, doms[dom_name], plan, baseline))
                if result is not None:
                    saved_documents[name] = result
        if len(saved_documents) == 2:
            audit.check("save.reloadExactAllCanvasFields", saved_documents["saved_before_reload"] == saved_documents["saved_after_reload"])
        raw = audit.read(args.raw_input, "rawNativeInput")
        if raw is None:
            audit.unknown("native.trustedSamePointerDownMovesUp", "No attached native observer raw. CUA action history plus DOM displacement does not establish this native predicate.")
        if raw is not None and doms["before"] is not None and doms["after"] is not None:
            audit.guard("native", lambda: native_checks(audit, raw, doms["before"], doms["after"], plan))
        formats = []
        saved = saved_documents.get("saved_after_reload")
        study = audit.read(args.study, "studyPublicRecord")
        if saved is not None and study is not None:
            audit.guard("study", lambda: study_checks(audit, study, saved, plan))
        environment = audit.read(args.final_environment, "finalEnvironmentDom")
        if environment is not None:
            audit.observations["finalBrowserEnvironment"] = environment
            audit.unknown("environment.fixedHardwareFontViewportCertification", "Study and later DOM browser dimensions differ; no fixed hardware/font/host certification is supplied.")
        audit.observations["domChain"] = {name: {"revision": dom["revision"], "cameraStyle": dom["cameraStyle"], "viewport": dom["viewport"],
            "nodes": len(dom["nodes"]), "edges": len(dom["edges"])} for name, dom in doms.items() if dom is not None}
        if args.export_dir and saved is not None and doms["reopened"] is not None:
            for directory in args.export_dir:
                result = audit.guard("export." + directory.name, lambda directory=directory: export_checks(audit, directory, saved, doms["reopened"], plan, baseline))
                formats.append(result)
            audit.check("export.svgAndPdfCoverage", set(formats) == {"svg", "pdf"})
        else:
            audit.unknown("export.coverage", "Requires both actual export directories, saved-after-reload envelope and reopened DOM.")
    report = audit.report()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({"status": report["status"], "counts": report["counts"], "report": str(args.output.resolve())}, ensure_ascii=False))
    return 1 if report["counts"]["fail"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
