"""Independent data-only geometry and actual SVG checks for the 12 CNN cases.

This module does not import the product, execute models, or derive expected
routes from a renderer. Callers supply independently bound Scene/Canvas data.
No revision, page, style, or canonical-binding normalization occurs here.
"""

from __future__ import annotations

import json
import math
import re
import xml.etree.ElementTree as ET
from typing import Any

EPSILON = 1e-7
# Scene route coordinates have one decimal place; port coordinates retain
# fractions. SVG card/port coordinates have two decimal places.
ENDPOINT_TOLERANCE = 0.06
SVG_COORDINATE_TOLERANCE = 0.011
SVG_NS = "http://www.w3.org/2000/svg"
Point = tuple[float, float]
Segment = tuple[Point, Point]
NUMBER = re.compile(r"[-+]?(?:\d*\.\d+|\d+\.?\d*)(?:[eE][-+]?\d+)?")
TOKEN = re.compile(r"[A-Za-z]|[-+]?(?:\d*\.\d+|\d+\.?\d*)(?:[eE][-+]?\d+)?")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _finite(value: Any, label: str) -> float:
    _require(isinstance(value, (int, float)) and not isinstance(value, bool),
             f"{label}: expected number")
    result = float(value)
    _require(math.isfinite(result), f"{label}: nonfinite number")
    return result


def _xml_number(value: str | None, label: str) -> float:
    _require(isinstance(value, str) and bool(NUMBER.fullmatch(value)),
             f"{label}: missing/invalid complete numeric attribute")
    result = float(value)
    _require(math.isfinite(result), f"{label}: nonfinite number")
    return result


def _near(first: float, second: float, tolerance: float = EPSILON) -> bool:
    return abs(first - second) <= tolerance


def _same_point(first: Point, second: Point,
                tolerance: float = EPSILON) -> bool:
    return _near(first[0], second[0], tolerance) and _near(first[1], second[1], tolerance)


def _render_number(value: float) -> float:
    """The explicit two-decimal SVG attribute serialization contract."""
    return math.floor(float(value) * 100 + 0.5) / 100


def _coordinate_text(value: float) -> str:
    return str(int(value)) if value.is_integer() else repr(value)


def _unique(items: list[dict], key: str, label: str) -> dict[str, dict]:
    result: dict[str, dict] = {}
    for item in items:
        identity = item.get(key)
        _require(isinstance(identity, str) and bool(identity), f"{label}: missing identity")
        _require(identity not in result, f"{label}: duplicate {identity}")
        result[identity] = item
    return result


def points(path: str) -> list[Point]:
    """Parse the complete single-subpath absolute M/L/H/V route vocabulary.

    Every command has its required numeric operands. Implicit commands,
    punctuation, relative commands, ignored text, and extra subpaths fail.
    """
    _require(isinstance(path, str), "route is not text")
    tokens: list[str] = []
    cursor = 0
    for match in TOKEN.finditer(path):
        _require(not path[cursor:match.start()].strip(), "unparsed route bytes")
        tokens.append(match.group())
        cursor = match.end()
    _require(not path[cursor:].strip(), "unparsed route bytes")
    result: list[Point] = []
    cursor = 0
    while cursor < len(tokens):
        command = tokens[cursor]
        cursor += 1
        _require(command in ("M", "L", "H", "V"),
                 f"unsupported route/subpath {command}")
        _require((command == "M" and not result) or
                 (command != "M" and bool(result)),
                 f"unsupported route/subpath {command}")
        count = 2 if command in ("M", "L") else 1
        _require(cursor + count <= len(tokens), "nonfinite/partial route")
        operands = tokens[cursor:cursor + count]
        _require(all(NUMBER.fullmatch(value) for value in operands),
                 "nonfinite/partial route")
        values = [float(value) for value in operands]
        _require(all(math.isfinite(value) for value in values), "nonfinite/partial route")
        cursor += count
        if command in ("M", "L"):
            point = (values[0], values[1])
        elif command == "H":
            point = (values[0], result[-1][1])
        else:
            point = (result[-1][0], values[0])
        _require(not result or point[0] == result[-1][0] or point[1] == result[-1][1],
                 "diagonal route")
        result.append(point)
    _require(len(result) >= 2, "missing route")
    return result


def segments(path: str) -> list[Segment]:
    """Drop zero-length steps and merge forward collinear subdivisions."""
    vertices: list[Point] = []
    for point in points(path):
        if vertices and _same_point(vertices[-1], point):
            continue
        while len(vertices) > 1:
            first, last = vertices[-2:]
            vertical = (first[0] == last[0] == point[0] and
                        (last[1] - first[1]) * (point[1] - last[1]) >= 0)
            horizontal = (first[1] == last[1] == point[1] and
                          (last[0] - first[0]) * (point[0] - last[0]) >= 0)
            if not (vertical or horizontal):
                break
            vertices.pop()
        vertices.append(point)
    return list(zip(vertices, vertices[1:]))


def stats(path: str) -> dict:
    route = segments(path)
    axes = ["v" if first[0] == last[0] else "h" for first, last in route]
    return {
        "length": sum(abs(first[0] - last[0]) + abs(first[1] - last[1])
                      for first, last in route),
        "bends": sum(first != last for first, last in zip(axes, axes[1:])),
    }


def pair(first: str, second: str) -> dict:
    """Count whole-polyline interior perpendicular contacts and union overlap.

    Whole-edge starts/ends are attachments. Actual bend vertices and split
    vertices are interior contacts. No exemption uses tensor, role, or style.
    Positive collinear overlaps are unioned per supporting line, so redundant
    subdivisions or repeated traversal cannot inflate or conceal that length.
    """
    first_points, second_points = points(first), points(second)
    endpoints = [first_points[0], first_points[-1], second_points[0], second_points[-1]]
    contacts: list[Point] = []
    intervals: list[dict] = []
    for a0, a1 in segments(first):
        av = a0[0] == a1[0]
        for b0, b1 in segments(second):
            bv = b0[0] == b1[0]
            if av != bv:
                v0, v1, h0, h1 = (a0, a1, b0, b1) if av else (b0, b1, a0, a1)
                contact = (v0[0], h0[1])
                if (min(h0[0], h1[0]) - EPSILON <= contact[0] <= max(h0[0], h1[0]) + EPSILON and
                    min(v0[1], v1[1]) - EPSILON <= contact[1] <= max(v0[1], v1[1]) + EPSILON and
                    not any(_same_point(contact, endpoint) for endpoint in endpoints) and
                    not any(_same_point(contact, prior) for prior in contacts)):
                    contacts.append(contact)
                continue
            coordinate_a, coordinate_b = (a0[0], b0[0]) if av else (a0[1], b0[1])
            if not _near(coordinate_a, coordinate_b):
                continue
            a_values = (a0[1], a1[1]) if av else (a0[0], a1[0])
            b_values = (b0[1], b1[1]) if bv else (b0[0], b1[0])
            low, high = max(min(a_values), min(b_values)), min(max(a_values), max(b_values))
            if high <= low + EPSILON:
                continue
            group = next((item for item in intervals
                          if item["vertical"] == av and _near(item["coordinate"], coordinate_a)), None)
            if group is None:
                group = {"vertical": av, "coordinate": coordinate_a, "values": []}
                intervals.append(group)
            group["values"].append((low, high))
    overlap = 0.0
    for group in intervals:
        values = sorted(group["values"])
        low, high = values[0]
        for next_low, next_high in values[1:]:
            if next_low <= high + EPSILON:
                high = max(high, next_high)
            else:
                overlap += high - low
                low, high = next_low, next_high
        overlap += high - low
    return {
        "crossings": sorted(f"{_coordinate_text(x)}/{_coordinate_text(y)}" for x, y in contacts),
        "overlapLength": overlap,
    }


def _rectangle(value: dict, label: str) -> dict:
    result = {key: _finite(value.get(key), f"{label}.{key}")
              for key in ("x", "y", "width", "height")}
    _require(result["width"] >= 0 and result["height"] >= 0, f"{label}: negative rectangle")
    return result


def body_rectangles(node: dict) -> list[dict]:
    front = _rectangle(node, f"node {node.get('id')}")
    result = [front]
    if node.get("repeat") and not node.get("expanded"):
        result.extend({**front, "x": front["x"] + offset, "y": front["y"] + offset}
                      for offset in (3.5, 7))
    return result


def penetrates(path: str, rectangle: dict) -> bool:
    """Conservative nominal rectangle interiors; merely touching is allowed."""
    rect = _rectangle(rectangle, "obstacle")
    for first, last in segments(path):
        if first[0] == last[0]:
            if (rect["x"] + EPSILON < first[0] < rect["x"] + rect["width"] - EPSILON and
                max(min(first[1], last[1]), rect["y"] + EPSILON) <
                min(max(first[1], last[1]), rect["y"] + rect["height"] - EPSILON)):
                return True
        elif (rect["y"] + EPSILON < first[1] < rect["y"] + rect["height"] - EPSILON and
              max(min(first[0], last[0]), rect["x"] + EPSILON) <
              min(max(first[0], last[0]), rect["x"] + rect["width"] - EPSILON)):
            return True
    return False


def _ancestors(identity: str, nodes: dict[str, dict]) -> list[str]:
    result: list[str] = []
    seen = {identity}
    _require(identity in nodes, f"missing ancestry node {identity}")
    current = nodes[identity].get("parentId")
    while current is not None:
        _require(current not in seen, f"cyclic ancestry {identity}")
        _require(current in nodes, f"missing ancestry parent {current}")
        seen.add(current)
        result.append(current)
        current = nodes[current].get("parentId")
    return result


def intrusions(scene: dict) -> list[str]:
    nodes = _unique(scene["nodes"], "id", "scene nodes")
    _unique(scene["edges"], "id", "scene edges")
    hits: list[str] = []
    for edge in scene["edges"]:
        ancestors = set(_ancestors(edge["sourceId"], nodes) + _ancestors(edge["targetId"], nodes))
        for node in scene["nodes"]:
            if node["id"] in ancestors and node["id"] not in (edge["sourceId"], edge["targetId"]):
                if node["expanded"]:
                    header = {**_rectangle(node, node["id"]),
                              "height": _finite(node["headerHeight"], "headerHeight")}
                    if penetrates(edge["path"], header):
                        hits.append(f"{edge['id']}|{node['id']}|header")
            else:
                for index, rect in enumerate(body_rectangles(node)):
                    if penetrates(edge["path"], rect):
                        hits.append(f"{edge['id']}|{node['id']}|" +
                                    (f"backplate{index}" if index else "body"))
    return sorted(hits)


def _canonical_port(binding: dict, canonical_nodes: dict[str, dict], direction: str) -> dict:
    _require(set(binding) == {"nodeId", "portId"}, "canonical endpoint fields changed")
    node = canonical_nodes.get(binding["nodeId"])
    _require(node is not None, f"canonical endpoint node missing {binding['nodeId']}")
    ports = _unique(node["ports"], "id", f"canonical ports {node['id']}")
    port = ports.get(binding["portId"])
    _require(port is not None, f"canonical endpoint port missing {binding['portId']}")
    _require(port["direction"] == direction, f"canonical port direction {binding['portId']}")
    return port


def assert_endpoints(scene: dict, document: dict) -> list[dict]:
    """Bind actual route endpoints to projected ports and the canonical graph.

    canonicalBindings retains ordered duplicates from canonicalEdgeIds. A
    source port can have canonical role=data for a residual edge. proxy is
    about the representative canonicalNodeId, not all grouped bindings.
    """
    _require(scene["documentId"] == document["id"], "Scene/Canvas document identity")
    _require(scene["revision"] == document["revision"], "Scene/Canvas revision")
    architecture = document["architecture"]
    _require(scene["sourceDigest"] == architecture["sourceDigest"] == document["sourceBindingDigest"],
             "Scene/Canvas source digest")
    _require(scene["irDigest"] == architecture["irDigest"], "Scene/Canvas IR digest")
    _require(scene["pageSpec"] == document["pageSpec"], "Scene/Canvas page spec")
    canonical_nodes = _unique(architecture["nodes"], "id", "canonical nodes")
    canonical_edges = _unique(architecture["edges"], "id", "canonical edges")
    nodes = _unique(scene["nodes"], "id", "scene nodes")
    _unique(scene["edges"], "id", "scene edges")
    all_ports: dict[str, tuple[dict, dict]] = {}
    for node in scene["nodes"]:
        canonical_id = node.get("canonicalNodeId", node["id"])
        _require(canonical_id in canonical_nodes, f"Scene node absent from canonical graph {node['id']}")
        for port in node["ports"]:
            _require(port["id"] not in all_ports, f"duplicate Scene port {port['id']}")
            all_ports[port["id"]] = (node, port)
            direction = port["direction"]
            _require(direction in ("in", "out"), f"Scene port direction {port['id']}")
            side = "source" if direction == "out" else "target"
            ids = port["canonicalEdgeIds"]
            _require(bool(ids) and len(ids) == len(set(ids)), f"port canonical edge ids {port['id']}")
            _require(all(identity in canonical_edges for identity in ids),
                     f"unknown port canonical edge {port['id']}")
            expected_bindings = [canonical_edges[identity][side] for identity in ids]
            _require(port["canonicalBindings"] == expected_bindings,
                     f"ordered canonicalBindings {port['id']}")
            first = expected_bindings[0]
            _require(port["canonicalNodeId"] == first["nodeId"] and
                     port["canonicalPortId"] == first["portId"],
                     f"representative canonical port {port['id']}")
            expected_port = _canonical_port(first, canonical_nodes, direction)
            _require(port["name"] == expected_port["name"] and port["role"] == expected_port["role"],
                     f"original canonical port name/role {port['id']}")
            _require(port["proxy"] == (first["nodeId"] != canonical_id),
                     f"representative proxy flag {port['id']}")
            for binding in expected_bindings:
                _canonical_port(binding, canonical_nodes, direction)
                _require(binding["nodeId"] == canonical_id or
                         canonical_id in _ancestors(binding["nodeId"], canonical_nodes),
                         f"canonical endpoint outside projected owner {port['id']}")
            _finite(port["x"], f"port {port['id']}.x")
            _finite(port["y"], f"port {port['id']}.y")
    records: list[dict] = []
    covered_ports: set[str] = set()
    canonical_coverage: set[str] = set()
    for edge in scene["edges"]:
        ids = edge["canonicalEdgeIds"]
        _require(bool(ids) and len(ids) == len(set(ids)), f"edge canonical ids {edge['id']}")
        _require(all(identity in canonical_edges for identity in ids), f"unknown canonical edge {edge['id']}")
        _require(not canonical_coverage.intersection(ids), f"duplicate canonical branch coverage {edge['id']}")
        canonical_coverage.update(ids)
        first = canonical_edges[ids[0]]
        _require(edge["source"] == first["source"] and edge["target"] == first["target"],
                 f"representative canonical edge endpoints {edge['id']}")
        _require(all(canonical_edges[identity]["tensorId"] == edge["tensorId"] and
                     canonical_edges[identity]["role"] == edge["role"] for identity in ids),
                 f"canonical tensor/role grouping {edge['id']}")
        route = points(edge["path"])
        for owner_id, direction, location in ((edge["sourceId"], "out", route[0]),
                                              (edge["targetId"], "in", route[-1])):
            owner = nodes.get(owner_id)
            _require(owner is not None, f"missing projected owner {edge['id']} {direction}")
            ports = [port for port in owner["ports"] if port["direction"] == direction and
                     all(identity in port["canonicalEdgeIds"] for identity in ids) and
                     _same_point((port["x"], port["y"]), location, ENDPOINT_TOLERANCE)]
            _require(len(ports) == 1, f"detached/ambiguous {edge['id']} {direction}")
            port = ports[0]
            covered_ports.add(port["id"])
            records.append({"edgeId": edge["id"], "direction": direction,
                            "ownerId": owner_id, "portId": port["id"],
                            "canonicalEdgeIds": list(ids),
                            "canonicalBindings": list(port["canonicalBindings"]),
                            "proxy": port["proxy"], "point": list(location),
                            "portPoint": [port["x"], port["y"]]})
    _require(covered_ports == set(all_ports), "uncovered/orphan projected port")
    return records


def _tag(element: ET.Element) -> str:
    _require(isinstance(element.tag, str) and element.tag.startswith(f"{{{SVG_NS}}}"),
             "actual SVG foreign/non-element namespace")
    return element.tag[len(SVG_NS) + 2:]


def parse_svg(raw: str | bytes) -> tuple[ET.Element, dict]:
    if isinstance(raw, bytes):
        try:
            raw = raw.decode("utf-8", errors="strict")
        except UnicodeDecodeError as error:
            raise AssertionError(f"actual SVG invalid UTF-8: {error}") from error
    _require(isinstance(raw, str) and bool(raw), "actual SVG missing")
    _require(not re.search(r"<!\s*(?:DOCTYPE|ENTITY)", raw, flags=re.I),
             "actual SVG entity/doctype declaration")
    _require("<?" not in raw, "actual SVG processing instruction")
    try:
        root = ET.fromstring(raw)
    except (ET.ParseError, RecursionError) as error:
        raise AssertionError(f"actual SVG XML parse: {error}") from error
    _require(_tag(root) == "svg", "actual SVG root")
    vocabulary = {"svg", "metadata", "defs", "marker", "path", "rect", "g",
                  "text", "title", "tspan", "circle"}
    for element in root.iter():
        _require(_tag(element) in vocabulary, "actual SVG unsupported element")
        _require(not any(attribute.lower().startswith("on") or attribute in ("href", "style")
                         for attribute in element.attrib), "actual SVG executable/external attribute")
    metadata_elements = [element for element in root.iter() if _tag(element) == "metadata"]
    _require(len(metadata_elements) == 1 and metadata_elements[0] in list(root),
             "actual SVG unique direct metadata")
    _require(not list(metadata_elements[0]), "actual SVG metadata contains elements")
    try:
        metadata = json.loads(metadata_elements[0].text or "")
    except (ValueError, TypeError) as error:
        raise AssertionError(f"actual SVG metadata parse: {error}") from error
    _require(isinstance(metadata, dict), "actual SVG metadata object")
    return root, metadata


def _children(element: ET.Element, name: str) -> list[ET.Element]:
    return [child for child in element if _tag(child) == name]


def _element_map(elements: list[ET.Element], attribute: str, label: str) -> dict[str, ET.Element]:
    result: dict[str, ET.Element] = {}
    for element in elements:
        identity = element.get(attribute)
        _require(bool(identity) and identity not in result, f"{label} missing/duplicate {identity}")
        result[identity] = element
    return result


def _numeric_attrs(element: ET.Element, expected: dict, label: str,
                   tolerance: float = EPSILON) -> None:
    for key, value in expected.items():
        actual = _xml_number(element.get(key), f"{label}.{key}")
        _require(_near(actual, _render_number(value), tolerance), f"{label}.{key} detached/changed")


def assert_scene_svg(scene: dict, raw: str | bytes) -> dict:
    """Validate actual XML identities, paths, styles, rectangles and ports.

    Interactive controls and publication objects have separate explicit
    vocabularies. Geometry is checked against the supplied bound Scene; this
    function neither changes revisions nor erases differences from the XML.
    """
    root, metadata = parse_svg(raw)
    _unique(scene["nodes"], "id", "scene nodes")
    _unique(scene["edges"], "id", "scene edges")
    _unique([port for node in scene["nodes"] for port in node["ports"]], "id", "scene ports")
    all_elements = list(root.iter())
    expected_metadata = {
        "renderer": "archcanvas-svg/1.0", "documentId": scene["documentId"],
        "revision": scene["revision"], "sourceDigest": scene["sourceDigest"],
        "irDigest": scene["irDigest"], "widthMm": scene["pageSpec"]["widthMm"],
        "heightMm": scene["pageSpec"]["widthMm"] * scene["bounds"]["height"] / scene["bounds"]["width"],
        "sourceFactScope": "whole-source-architecture", "sourceFacts": scene["sourceFacts"],
        "renderedNodes": [{"sceneNodeId": node["id"],
                           "canonicalNodeId": node.get("canonicalNodeId", node["id"]),
                           "boundary": node.get("boundary", False)} for node in scene["nodes"]],
        "renderedBindings": [{"sceneEdgeId": edge["id"], "canonicalEdgeIds": edge["canonicalEdgeIds"],
                              "source": edge["source"], "target": edge["target"],
                              "tensorId": edge["tensorId"], "role": edge["role"]}
                             for edge in scene["edges"]],
    }
    if "exportScope" in scene:
        expected_metadata["exportScope"] = scene["exportScope"]
    _require(metadata == expected_metadata, "actual SVG complete metadata/canonical bindings")
    _require(root.get("data-document-id") == scene["documentId"] and
             root.get("data-revision") == str(scene["revision"]), "actual SVG root document/revision")
    _require(root.get("role") == "img" and root.get("aria-label") == scene["title"],
             "actual SVG root accessible identity")
    for key, expected in (("width", expected_metadata["widthMm"]),
                          ("height", expected_metadata["heightMm"])):
        value = root.get(key, "")
        _require(value.endswith("mm"), f"actual SVG root {key} units")
        actual = _xml_number(value[:-2], f"svg.{key}")
        # Interactive/core renderers round to two decimal places. The actual
        # publication exporter writes the derived physical size to eight
        # significant digits; neither rule alters metadata/world geometry.
        allowed = (_render_number(expected), float(format(expected, ".8g")))
        _require(any(_near(actual, candidate) for candidate in allowed),
                 f"actual SVG root {key} physical geometry/serialization")
    bounds_tokens = root.get("viewBox", "").split()
    _require(len(bounds_tokens) == 4, "actual SVG viewBox")
    for value, key in zip(bounds_tokens, ("x", "y", "width", "height")):
        _require(_near(_xml_number(value, "viewBox"), _render_number(scene["bounds"][key])),
                 f"actual SVG viewBox {key}")
    edge_groups = _element_map([element for element in all_elements if "data-edge-id" in element.attrib],
                               "data-edge-id", "SVG edge groups")
    _require(set(edge_groups) == {edge["id"] for edge in scene["edges"]}, "actual SVG edge set")
    colors = list(dict.fromkeys(edge["stroke"] for edge in scene["edges"]))
    markers = _element_map([element for element in all_elements if _tag(element) == "marker"],
                           "id", "SVG markers")
    _require(set(markers) == {f"archcanvas-arrow-{index}" for index in range(len(colors))},
             "actual SVG arrow marker set")
    for index, color in enumerate(colors):
        marker = markers[f"archcanvas-arrow-{index}"]
        _require(marker.attrib == {"id": f"archcanvas-arrow-{index}", "viewBox": "0 0 10 10",
                                   "refX": "8.5", "refY": "5", "markerWidth": "5.5",
                                   "markerHeight": "5.5", "orient": "auto-start-reverse"},
                 "actual SVG arrow definition")
        _require(len(marker) == 1 and _tag(marker[0]) == "path" and
                 marker[0].attrib == {"d": "M 1 1 L 9 5 L 1 9 Z", "fill": color},
                 "actual SVG arrowhead style")
    for edge in scene["edges"]:
        group = edge_groups[edge["id"]]
        _require(_tag(group) == "g" and group.attrib == {
            "data-edge-id": edge["id"], "data-tensor-id": edge["tensorId"]},
            f"actual SVG edge identity {edge['id']}")
        titles, paths, labels = _children(group, "title"), _children(group, "path"), _children(group, "text")
        _require(len(titles) == len(paths) == 1 and
                 titles[0].text == f"{edge['id']} · {edge['role']} · {edge['tensorId']}",
                 f"actual SVG edge title/path {edge['id']}")
        _require(len(group) == 2 + bool(edge["label"]), f"actual SVG extra edge object {edge['id']}")
        path = paths[0]
        expected_path = {"d": edge["path"], "stroke": edge["stroke"],
                         "marker-end": f"url(#archcanvas-arrow-{colors.index(edge['stroke'])})"}
        if edge["dashed"]:
            expected_path["stroke-dasharray"] = "5 4"
        _require(set(path.attrib) == set(expected_path) | {"stroke-width"} and
                 all(path.get(key) == value for key, value in expected_path.items()),
                 f"actual SVG route/style/arrow {edge['id']}")
        _numeric_attrs(path, {"stroke-width": edge["width"]}, edge["id"], EPSILON)
        points(path.get("d", ""))
        _require(len(labels) == bool(edge["label"]), f"actual SVG edge label presence {edge['id']}")
        if labels:
            label = labels[0]
            _require(label.text == edge["label"] and label.get("font-size") == "9" and
                     label.get("fill") == edge["stroke"] and label.get("stroke") == "none",
                     f"actual SVG edge label identity/style {edge['id']}")
            _numeric_attrs(label, {"x": edge["labelX"], "y": edge["labelY"]}, edge["id"])
    cards = _element_map([element for element in all_elements if "data-canonical-id" in element.attrib],
                         "data-node-id", "SVG cards")
    _require(set(cards) == {node["id"] for node in scene["nodes"]}, "actual SVG card set")
    interactive = any("tabindex" in element.attrib for element in cards.values())
    expand_elements = _element_map([element for element in all_elements if "data-expand-id" in element.attrib],
                                   "data-expand-id", "SVG expand controls")
    expected_controls = {node["id"] for node in scene["nodes"] if node["expandable"]} if interactive else set()
    _require(set(expand_elements) == expected_controls, "actual SVG expand-control set")
    for node in scene["nodes"]:
        group = cards[node["id"]]
        expected_attributes = {"data-node-id": node["id"],
                               "data-canonical-id": node.get("canonicalNodeId", node["id"]),
                               "aria-label": node["label"]}
        if interactive:
            expected_attributes.update({"tabindex": "0", "role": "button"})
        _require(_tag(group) == "g" and group.attrib == expected_attributes,
                 f"actual SVG card identity {node['id']}")
        titles = _children(group, "title")
        _require(len(titles) == 1 and (titles[0].text or "").startswith(
            f"{node['label']} · {node['kind']} · {node['evidence']}"), f"actual SVG node title {node['id']}")
        rectangles = _children(group, "rect")
        bodies = body_rectangles(node)
        # Actual SVG paints farthest and nearer plates before the front card.
        ordered = list(reversed(bodies[1:])) + [bodies[0]]
        _require(len(rectangles) == len(ordered), f"actual SVG body/backplate count {node['id']}")
        for index, (rect, expected) in enumerate(zip(rectangles, ordered)):
            front = index == len(ordered) - 1
            _numeric_attrs(rect, expected, f"{node['id']} rectangle {index}")
            expected_style = {"rx": "12" if node["expanded"] and front else "9",
                              "fill": node["fill"], "stroke": node["stroke"]}
            if front:
                expected_style["stroke-width"] = "1.3" if node["expanded"] else "1.5"
                if node["evidence"] == "opaque":
                    expected_style["stroke-dasharray"] = "5 3"
            else:
                expected_style["opacity"] = ".45" if index == 0 else ".7"
            _require(set(rect.attrib) == set(expected_style) | {"x", "y", "width", "height"} and
                     all(rect.get(key) == value for key, value in expected_style.items()),
                     f"actual SVG body/backplate style {node['id']}")
        separators = _children(group, "path")
        _require(len(separators) == bool(node["expanded"]), f"actual SVG header count {node['id']}")
        if separators:
            separator = separators[0]
            header_points = points(separator.get("d", ""))
            expected_header = [(node["x"] + 1, node["y"] + node["headerHeight"] - 4),
                               (node["x"] + node["width"] - 1, node["y"] + node["headerHeight"] - 4)]
            expected_header = [(_render_number(x), _render_number(y)) for x, y in expected_header]
            _require(len(header_points) == 2 and all(_same_point(a, b)
                     for a, b in zip(header_points, expected_header)) and
                     separator.get("stroke") == node["stroke"] and separator.get("opacity") == ".28",
                     f"actual SVG ancestor header {node['id']}")
        if interactive and node["expandable"]:
            control = expand_elements[node["id"]]
            _require(control in list(group) and control.get("role") == "button" and
                     control.get("aria-label") == ("Collapse " if node["expanded"] else "Expand ") + node["label"],
                     f"actual SVG expand control binding {node['id']}")
        if node["expanded"] and node.get("repeat"):
            badge_text = f"{node['repeat']['count']}× · {node['repeat']['sharing']}"
            badges = [element for element in _children(group, "text") if element.text == badge_text]
            _require(len(badges) == 1, f"actual SVG Repeat badge {node['id']}")
            _numeric_attrs(badges[0], {"x": node["x"] + node["width"] - (47 if interactive else 17),
                                       "y": node["y"] + 27}, f"Repeat badge {node['id']}")
    port_elements = _element_map([element for element in all_elements if "data-port-id" in element.attrib],
                                 "data-port-id", "SVG ports")
    expected_ports = {port["id"] for node in scene["nodes"] for port in node["ports"]}
    _require(set(port_elements) == expected_ports, "actual SVG port set")
    for node in scene["nodes"]:
        for port in node["ports"]:
            element = port_elements[port["id"]]
            _require(element.get("data-node-id") == node["id"], f"actual SVG port owner {port['id']}")
            suffix = " · projected boundary port" if port["proxy"] else (
                " · 拖向来源输出端口以创建改接提案" if interactive and port["direction"] == "in" else "")
            if interactive:
                _require(_tag(element) == "g" and element.attrib == {
                    "data-port-id": port["id"], "data-node-id": node["id"]},
                    f"actual SVG interactive port vocabulary {port['id']}")
                circles = _children(element, "circle")
                titles = _children(element, "title")
                _require(len(element) == 3 and len(circles) == 2 and len(titles) == 1,
                         f"actual SVG interactive port children {port['id']}")
                hitbox, circle = circles
                _require(set(hitbox.attrib) == {"cx", "cy", "r", "fill"} and
                         hitbox.get("r") == "8" and hitbox.get("fill") == "transparent",
                         f"actual SVG port hitbox {port['id']}")
                _numeric_attrs(hitbox, {"cx": port["x"], "cy": port["y"]}, port["id"])
                _require(set(circle.attrib) == {"cx", "cy", "r", "fill"}, f"actual SVG port circle attrs {port['id']}")
            else:
                _require(_tag(element) == "circle" and
                         set(element.attrib) == {"data-port-id", "data-node-id", "cx", "cy", "r", "fill"},
                         f"actual SVG publication port vocabulary {port['id']}")
                circle = element
                titles = _children(element, "title")
                _require(len(element) == 1 and len(titles) == 1, f"actual SVG port title count {port['id']}")
            _require(titles[0].text == port["name"] + suffix, f"actual SVG port name/proxy {port['id']}")
            _require(circle.get("r") == "2.6" and circle.get("fill") == node["stroke"],
                     f"actual SVG visible port style {port['id']}")
            _numeric_attrs(circle, {"cx": port["x"], "cy": port["y"]}, port["id"])
    legends = _element_map([element for element in all_elements if "data-legend-id" in element.attrib],
                           "data-legend-id", "SVG legend")
    annotations = _element_map([element for element in all_elements if "data-annotation-id" in element.attrib],
                               "data-annotation-id", "SVG annotations")
    _require(set(legends) == {item["id"] for item in scene["legend"]}, "actual SVG legend set")
    _require(set(annotations) == {item["id"] for item in scene["annotations"]}, "actual SVG annotation set")
    return {"interactive": interactive, "nodes": len(cards), "edges": len(edge_groups),
            "ports": len(port_elements), "markers": len(markers), "legend": len(legends),
            "annotations": len(annotations), "metadataExact": True,
            "canonicalBindingsExact": True, "actualPathStyleBodyPortVerified": True}


def assert_refinement(before: dict, after: dict, svg: str | None = None,
                      document: dict | None = None) -> dict:
    """Require explicit caller-bound equal Scene identity, preserving geometry.

    Only path/label coordinates can change. Pair protection compares every
    edge pair separately and never trades an increased pair for another pair.
    """
    _require(set(before) == set(after), "changed Scene top-level field set")
    for key in before:
        if key != "edges":
            _require(after[key] == before[key], f"changed protected Scene field {key}")
    _require(len(before["edges"]) == len(after["edges"]), "changed Scene edge count")
    changed = []
    for old, new in zip(before["edges"], after["edges"]):
        protected_old = {key: value for key, value in old.items() if key not in ("path", "labelX", "labelY")}
        protected_new = {key: value for key, value in new.items() if key not in ("path", "labelX", "labelY")}
        _require(protected_old == protected_new, "changed canonical branch/role/style/identity")
        points(new["path"])
        if new["path"] != old["path"]:
            changed.append({"edgeId": new["id"], "before": stats(old["path"]), "after": stats(new["path"])})
    old_hits, new_hits = intrusions(before), intrusions(after)
    _require(set(new_hits).issubset(old_hits), "new nominal body/backplate/ancestor-header intrusion")
    pair_records = []
    for index, first in enumerate(before["edges"]):
        for other in range(index + 1, len(before["edges"])):
            second = before["edges"][other]
            old_pair = pair(first["path"], second["path"])
            new_pair = pair(after["edges"][index]["path"], after["edges"][other]["path"])
            _require(len(new_pair["crossings"]) <= len(old_pair["crossings"]),
                     f"new protected crossing {first['id']}/{second['id']}")
            _require(new_pair["overlapLength"] <= old_pair["overlapLength"] + EPSILON,
                     f"new protected overlap {first['id']}/{second['id']}")
            pair_records.append({"edges": [first["id"], second["id"]],
                                 "before": old_pair, "after": new_pair})
    result = {"changedRoutes": changed, "beforeIntrusions": old_hits,
              "afterIntrusions": new_hits, "pairs": pair_records}
    if document is not None:
        result["endpoints"] = assert_endpoints(after, document)
    if svg is not None:
        result["svg"] = assert_scene_svg(after, svg)
    return result
