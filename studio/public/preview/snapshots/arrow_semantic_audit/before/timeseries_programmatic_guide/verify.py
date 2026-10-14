#!/usr/bin/env python3
"""Independently inspect exported SVG/source records; never import model code.

Usage: python3 verify.py generated [--png]
The export-consistency checks are independent of the drawing code. Geometry is
also checked by layout.validate, after replacing records with parsed SVG data.
"""
from __future__ import annotations

import argparse
import ast
import copy
import hashlib
import json
import math
from pathlib import Path
import re
import struct
import xml.etree.ElementTree as ET
import zipfile

from layout import validate


MODELS = ("autoformer", "itransformer", "patchtst", "timemixer")
VIEWS = ("overview", "modules", "detailed")
HERE = Path(__file__).resolve().parent
NUMBER = r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def read_json(path):
    if not path.is_file() or not path.stat().st_size:
        raise ValueError("missing/empty file: " + str(path))
    return json.loads(path.read_text(encoding="utf-8"))


def require(condition, message):
    if not condition:
        raise ValueError(message)


def close(a, b):
    if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
        return len(a) == len(b) and all(close(x, y) for x, y in zip(a, b))
    try:
        return math.isfinite(float(a)) and math.isfinite(float(b)) and abs(float(a) - float(b)) <= 1e-6
    except (TypeError, ValueError):
        return a == b


def numeric(value):
    return float(str(value).removesuffix("px"))


def path_points(data):
    tokens = re.findall(r"[A-Za-z]|" + NUMBER, data)
    remainder = re.sub(r"[A-Za-z]|" + NUMBER, "", data)
    require(not remainder.strip(" ,\t\r\n"), "unparsed SVG path content")
    require(len(tokens) >= 6 and len(tokens) % 3 == 0, "expected SVG M/L polyline")
    points = []
    for i in range(0, len(tokens), 3):
        require(tokens[i] == ("M" if i == 0 else "L"), "unsupported SVG path command")
        points.append([float(tokens[i + 1]), float(tokens[i + 2])])
    return points


def ast_symbols(source, filename):
    result = {}
    def visit(body, prefix=""):
        for node in body:
            if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                name = prefix + node.name
                result[name] = node
                if isinstance(node, ast.ClassDef):
                    visit(node.body, name + ".")
    visit(ast.parse(source, filename=filename).body)
    return result


def source_checks(folder, evidence, ir):
    files, symbols = evidence.get("files", {}), evidence.get("symbols", {})
    require(files and symbols, "empty source evidence")
    parsed, lines_by_path = {}, {}
    archive_path = HERE.parent / evidence.get("archive", "__missing_archive__")
    pinned_path = HERE / "reviewed_archives.json"
    pinned = read_json(pinned_path) if pinned_path.exists() else {}
    if evidence.get("archive") in pinned:
        require(evidence.get("archive_sha256") == pinned[evidence["archive"]], "archive hash differs from reviewed archive")
    archive = zipfile.ZipFile(archive_path) if archive_path.is_file() else None
    try:
        if archive:
            require(sha(archive_path.read_bytes()) == evidence.get("archive_sha256"), "local archive hash differs from evidence")
        for member, record in files.items():
            relative = Path(member)
            require(not relative.is_absolute() and ".." not in relative.parts, "unsafe source path: " + member)
            path = folder / "sources" / relative
            require(path.is_file() and path.stat().st_size > 0, "missing/empty exported source: " + member)
            data = path.read_bytes()
            require(sha(data) == record.get("sha256"), "source SHA mismatch: " + member)
            if archive:
                require(data == archive.read(member), "source differs from reviewed archive member: " + member)
            source = data.decode("utf-8-sig")
            lines_by_path[member] = source.splitlines()
            require(len(lines_by_path[member]) == record.get("lines"), "source line count mismatch: " + member)
            if member.endswith(".py"):
                parsed[member] = ast_symbols(source, member)
        evidence_ids = set()
        for reference, span in symbols.items():
            member, symbol = reference.split("::", 1)
            require(span.get("path") == member and span.get("symbol") == symbol, "evidence reference mismatch: " + reference)
            node = parsed.get(member, {}).get(symbol)
            require(node is not None, "AST symbol missing: " + reference)
            require((node.lineno, node.end_lineno) == (span.get("start"), span.get("end")), "AST span mismatch: " + reference)
            snippet = "\n".join(lines_by_path[member][node.lineno - 1:node.end_lineno])
            require(snippet == span.get("snippet"), "AST snippet mismatch: " + reference)
            eid = span.get("evidence_id")
            require(eid and eid not in evidence_ids, "missing/duplicate evidence ID")
            evidence_ids.add(eid)
        nodes = {n["id"]: n for n in ir.get("nodes", [])}
        require(nodes and len(nodes) == len(ir["nodes"]), "empty/duplicate IR nodes")
        for node in nodes.values():
            refs = node.get("source", [])
            require(refs and all(r in symbols for r in refs), "unbound node source: " + node["id"])
            require(node.get("source_evidence") == [symbols[r]["evidence_id"] for r in refs], "node evidence ID mismatch: " + node["id"])
            require(node.get("parent") is None or node["parent"] in nodes, "unknown IR parent: " + node["id"])
        edges = ir.get("edges", [])
        require(edges and len({e["id"] for e in edges}) == len(edges), "empty/duplicate IR edges")
        for edge in edges:
            for end in ("src", "dst"):
                require(edge.get(end) in nodes, "unknown IR edge endpoint")
                require(edge.get(end + "_port") in nodes[edge[end]].get("ports", []), "unregistered IR edge port")
        return dict(files=len(files), symbols=len(symbols), nodes=len(nodes), edges=len(edges),
                    compared_to_local_archive=archive is not None)
    finally:
        if archive:
            archive.close()


def parameter(node):
    return node.get("param_identity", node.get("parameter", node.get("parameter_scope")))


def model_facts(key, ir):
    nodes = {n["id"]: n for n in ir["nodes"]}
    edges = ir["edges"]
    def has(src, dst, role=None):
        return any(e.get("src") == src and e.get("dst") == dst and (role is None or e.get("role") == role) for e in edges)
    def distinct(*ids):
        values = [parameter(nodes.get(i, {})) for i in ids]
        return all(values) and len(set(values)) == len(values)
    profile = ir.get("profile", {})
    checked = []
    def check(condition, label):
        require(condition, key + ": " + label)
        checked.append(label)
    if key == "autoformer":
        check(has("af_memory", "af_dec_cross", "memory"), "encoder memory supplies cross AutoCorrelation")
        decomps = [n for n in nodes.values() if n.get("retained_input")]
        check(len(decomps) >= 5, "encoder/decoder decomposition retains original input")
        check(all(any(e["src"] == n["id"] and e.get("role") == "retained_input" and e.get("src_port") == "in" for e in edges) for n in decomps), "retained decomposition inputs have explicit edges")
    elif key == "patchtst":
        check(has("patch_layer1_raw_scores", "patch_layer2_raw_scores", "scores"), "layer 1 raw scores feed layer 2 before Softmax")
        check(all(nodes.get(f"patch_layer{i}_raw_scores", {}).get("pre_softmax") is True and
                  has(f"patch_layer{i}_raw_scores", f"patch_layer{i}_softmax") for i in (1, 2)),
              "both score endpoints precede Softmax")
        check(all(has(f"patch_layer{i}_value_bypass", f"patch_layer{i}_sdpa_operands", "tuple_collection") and
                  has(f"patch_layer{i}_sdpa_operands", f"patch_layer{i}_weighted_values") for i in (1, 2)),
              "V bypasses weight computation and joins at A@V")
        head = nodes.get("patch_head_linear", {})
        head_text = " ".join([head.get("label", ""), *head.get("detail", [])]).replace(" ", "")
        check("D*P->H" in head_text, "flatten head projects D*P to H")
        check(profile.get("norm", "").lower() == "batchnorm" and profile.get("pre_norm") is False, "selected default is post BatchNorm")
        check(all("BatchNorm" in nodes.get(f"patch_layer1_bn{i}", {}).get("label", "") for i in (1, 2)), "both first-layer normalization sites are BatchNorm")
        check(distinct("patch_layer1", "patch_layer2"), "encoder layers have independent parameter identities")
    elif key == "itransformer":
        check(has("it.project", "it.restore") and has("it.restore", "it.select"), "projection precedes restore and variate selection")
        check(has("it.normalize", "it.denormalize", "statistics"), "input statistics feed denormalization")
        check(distinct("it.enc1", "it.enc2"), "encoder layers have independent parameter identities")
    elif key == "timemixer":
        predictors = [n for n in nodes.values() if n.get("parent") == "tm.fmm"]
        check(len(predictors) == 4 and {n["id"] for n in predictors} == {f"tm.predict{i}" for i in range(4)}, "four scale-specific predictors")
        check(all(has(n["id"], "tm.fmm", "tuple_collection") for n in predictors) and has("tm.fmm", "tm.forecast_sum"), "four forecasts collect then sum")
        check("sum" in nodes.get("tm.forecast_sum", {}).get("label", "").lower(), "forecast fusion is sum")
        stat_edges = [e for e in edges if e.get("dst") == "tm.denorm" and e.get("role") == "statistics"]
        check(len(stat_edges) == 1 and stat_edges[0].get("src") == "tm.norm0", "only scale 0 statistics restore forecast scale")
        check(distinct("tm.pdm1", "tm.pdm2"), "two PDM blocks have independent parameters")
    return checked


def exported_view(svg_path, layout, evidence, ir, png=False):
    require(svg_path.is_file() and svg_path.stat().st_size > 0, "missing/empty SVG: " + str(svg_path))
    svg = ET.parse(svg_path).getroot()
    canvas = [numeric(svg.get(k, "nan")) for k in ("width", "height")]
    require(close(canvas, layout.get("canvas", [])), "SVG canvas differs from layout")
    require(close([float(x) for x in svg.get("viewBox", "").split()], [0, 0, *canvas]), "SVG viewBox differs from canvas")
    binding_element=next((e for e in svg if e.tag.rsplit('}',1)[-1]=='metadata' and e.get('id')=='source-binding'),None)
    require(binding_element is not None,'SVG source-binding metadata missing')
    binding=json.loads(binding_element.text)
    require(binding.get('model')==ir['model'] and binding.get('source_archive_sha256')==evidence['archive_sha256'], 'SVG source archive/model binding differs')
    require(binding.get('semantic_ir_sha256')==sha(json.dumps(ir,sort_keys=True).encode()),'SVG IR digest differs')
    actual_boxes, actual_routes, markers = {}, {}, {}
    def visit(element, in_defs=False):
        tag = element.tag.rsplit("}", 1)[-1]
        in_defs = in_defs or tag == "defs"
        if tag == "marker":
            require(element.get("markerUnits") == "userSpaceOnUse", "marker size depends on stroke width")
            require(element.get("id") not in markers, "duplicate SVG marker ID")
            size = [numeric(element.get(k, "nan")) for k in ("markerWidth", "markerHeight")]
            require(all(math.isfinite(v) and v > 0 for v in size), "invalid fixed marker dimensions")
            markers[element.get("id")] = size
        identity = element.get("data-node-id")
        if identity:
            require(identity not in actual_boxes, "duplicate SVG node ID: " + identity)
            rects = [c for c in element if c.tag.rsplit("}", 1)[-1] == "rect"]
            require(len(rects) == 1, "node does not contain exactly one rectangle: " + identity)
            rect = rects[0]
            title = " ".join(c.text or "" for c in element if c.tag.rsplit("}", 1)[-1] == "title")
            actual_boxes[identity] = dict(bbox=[numeric(rect.get(k, "nan")) for k in ("x", "y", "width", "height")], radius=numeric(rect.get("rx", 0)), title=title)
        if tag == "path" and not in_defs:
            identity = element.get("data-route-id")
            require(identity and identity not in actual_routes, "missing/duplicate actual SVG route ID")
            marker = element.get("marker-end")
            actual_routes[identity] = dict(points=path_points(element.get("d", "")), arrow=bool(marker), marker=marker)
        for child in element:
            visit(child, in_defs)
    visit(svg)
    require(markers, "SVG has no fixed-size arrow marker")
    boxes = {b["id"]: b for b in layout.get("boxes", [])}
    routes = {r["id"]: r for r in layout.get("routes", [])}
    require(boxes and len(boxes) == len(layout["boxes"]), "empty/duplicate layout boxes")
    require(routes and len(routes) == len(layout["routes"]), "empty/duplicate layout routes")
    require(set(actual_boxes) == set(boxes), "actual SVG rectangles and layout boxes differ")
    require(set(actual_routes) == set(routes), "actual SVG paths and layout routes differ")
    ir_nodes = {n["id"]: n for n in ir["nodes"]}
    scene = copy.deepcopy(layout)
    for box in scene["boxes"]:
        identity = box["id"]
        require(identity in ir_nodes, "SVG node missing from IR: " + identity)
        actual = actual_boxes[identity]
        require(close(box["bbox"], actual["bbox"]) and close(box.get("radius", 0), actual["radius"]), "SVG rectangle geometry differs: " + identity)
        require(box.get("source") == ir_nodes[identity].get("source"), "visible source binding differs from IR: " + identity)
        for reference in box.get("source", []):
            span = evidence["symbols"][reference]
            require(f'{span["path"]}:{span["start"]} {span["symbol"]}' in actual["title"], "SVG source title missing: " + identity)
        box["bbox"], box["radius"] = actual["bbox"], actual["radius"]
        x, y, w, h = actual["bbox"]
        ports = dict(in_=[x + w/2, y + h], out=[x + w/2, y], left=[x, y + h/2], right=[x + w, y + h/2])
        ports["in"] = ports.pop("in_")
        for name, point in ports.items():
            require(close(layout.get("ports", {}).get(identity, {}).get(name, []), point), "port does not match actual rectangle: " + identity + ":" + name)
        scene["ports"][identity].update(ports)
    for route in scene["routes"]:
        actual = actual_routes[route["id"]]
        require(close(route["points"], actual["points"]) and bool(route.get("arrow")) == actual["arrow"], "SVG route geometry/arrow differs: " + route["id"])
        if actual["arrow"]:
            match = re.fullmatch(r"url\(#([^)]*)\)", actual["marker"])
            require(match and match[1] in markers, "route references missing arrow marker")
        route["points"], route["arrow"] = actual["points"], actual["arrow"]
        if route.get("semantic_src"):
            require(any(all(edge.get(k) == route.get("semantic_" + k) for k in ("src", "dst", "src_port", "dst_port")) and edge.get("role") == route.get("role") for edge in ir["edges"]), "rendered side route has no matching semantic edge")
    geometry = validate(scene)
    require(geometry.get("passed"), "geometry: " + "; ".join(geometry.get("errors", [])[:12]))
    if png:
        png_path = svg_path.with_suffix(".png")
        require(png_path.is_file(), "missing PNG: " + str(png_path))
        header = png_path.read_bytes()[:24]
        require(len(header) == 24 and header[:8] == b"\x89PNG\r\n\x1a\n" and header[12:16] == b"IHDR", "invalid PNG header")
        require(close(list(struct.unpack(">II", header[16:24])), canvas), "PNG dimensions differ from SVG")
    return dict(rectangles=len(boxes), actual_paths=len(routes), marker_sizes=markers,
                export_consistency="independent SVG/XML + source/IR comparison",
                geometry=dict(reused_validator="layout.validate", input="actual SVG rectangles and polylines", checks=geometry.get("checks", [])))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("generated", type=Path, help="generated root with all four model folders")
    parser.add_argument("--png", action="store_true", help="also require matching PNG dimensions")
    args = parser.parse_args()
    root = args.generated.resolve()
    require(root.is_dir(), "generated root does not exist: " + str(root))
    report = dict(passed=True, models={}, views_checked=0, expected_views=12, png_checked=args.png,
                  limitations=["Static reviewed model facts, not execution or numeric equivalence.",
                               "Export consistency checks are independent; geometry rules reuse layout.validate.",
                               "Text metrics and appearance still require visual inspection."])
    marker_sizes = []
    for key in MODELS:
        result = dict(passed=True, views={})
        report["models"][key] = result
        folder = root / key
        try:
            evidence, ir = read_json(folder / "source_evidence.json"), read_json(folder / "semantic_ir.json")
            require(ir.get("model") == key, "IR model identity mismatch")
            result["sources"] = source_checks(folder, evidence, ir)
            result["model_facts"] = model_facts(key, ir)
            digest = sha(json.dumps(ir, sort_keys=True).encode())
            result["semantic_ir_sha256"] = digest
            expected = {f"figure{i}_{view}.svg" for i, view in enumerate(VIEWS, 1)}
            require({p.name for p in folder.glob("figure*.svg")} == expected, "expected exactly three model SVG views")
            saved_checks = read_json(folder / "layout_checks.json")
            require(isinstance(saved_checks, list) and len(saved_checks) == len(VIEWS), "expected three layout check records")
            for view in VIEWS:
                check = next((c for c in saved_checks if c.get("view") == view), None)
                require(check and check.get("semantic_ir_sha256") == digest, "saved check IR digest differs: " + view)
            for i, view in enumerate(VIEWS, 1):
                try:
                    layout = read_json(folder / f"layout_{view}.json")
                    require(layout.get("semantic_ir_sha256") == digest, "view IR digest differs")
                    details = exported_view(folder / f"figure{i}_{view}.svg", layout, evidence, ir, args.png)
                    result["views"][view] = dict(passed=True, **details)
                    marker_sizes.extend(details["marker_sizes"].values())
                    report["views_checked"] += 1
                except (ValueError, KeyError, TypeError, OSError, ET.ParseError, struct.error) as exc:
                    result["passed"] = False
                    result["views"][view] = dict(passed=False, error=str(exc))
        except (ValueError, KeyError, TypeError, OSError, SyntaxError, zipfile.BadZipFile) as exc:
            result["passed"] = False
            result["error"] = str(exc)
        report["passed"] = report["passed"] and result["passed"]
        print(key + ": " + ("PASS" if result["passed"] else "FAIL") + (" — " + result["error"] if result.get("error") else ""))
        for view, value in result["views"].items():
            if not value["passed"]:
                print("  " + view + ": " + value["error"])
    if report["views_checked"] != report["expected_views"]:
        report["passed"] = False
        report["view_count_error"] = "Not all 12 exported views passed independent inspection."
    if marker_sizes and any(not close(size, marker_sizes[0]) for size in marker_sizes):
        report["passed"] = False
        report["marker_error"] = "Arrow marker sizes differ across views."
    destination = root / "export_checks.json"
    destination.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(str(destination))
    raise SystemExit(0 if report["passed"] else 1)


if __name__ == "__main__":
    main()
