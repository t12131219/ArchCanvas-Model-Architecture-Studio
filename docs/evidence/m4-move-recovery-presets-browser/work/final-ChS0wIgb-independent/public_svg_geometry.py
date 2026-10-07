"""Independent audit of captured public SVG; does not import product code."""
import hashlib
import re
import xml.etree.ElementTree as ET


def children(element, tag):
    return [child for child in element if child.tag.split("}")[-1] == tag]


def path_points(path):
    tokens = re.findall(r"[A-Za-z]|-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?", path)
    index, point, points = 0, None, []
    while index < len(tokens):
        command = tokens[index]
        index += 1
        if command in ("M", "L"):
            point = float(tokens[index]), float(tokens[index + 1])
            index += 2
        elif command == "H":
            point = float(tokens[index]), point[1]
            index += 1
        elif command == "V":
            point = point[0], float(tokens[index])
            index += 1
        else:
            raise ValueError("Unsupported captured path command: " + command)
        points.append(point)
    return points


def crosses_open_rectangle(start, end, rect):
    left, top, right, bottom = rect
    if start[0] == end[0]:
        return (left < start[0] < right and
                max(min(start[1], end[1]), top) < min(max(start[1], end[1]), bottom))
    if start[1] == end[1]:
        return (top < start[1] < bottom and
                max(min(start[0], end[0]), left) < min(max(start[0], end[0]), right))
    raise ValueError("Non-orthogonal captured route segment")


def audit_svg(source):
    root = ET.fromstring(source)
    draft = any("data-draft-node" in node.attrib for node in root.iter())
    nodes, ports, routes = [], [], []
    for element in root.iter():
        attributes = element.attrib
        is_node = ("data-draft-node" in attributes or
                   ("data-node-id" in attributes and attributes.get("role") == "button"))
        if is_node:
            rect = children(element, "rect")[0]
            if draft:
                x, y = map(float, re.findall(r"-?\d+(?:\.\d+)?", attributes["transform"])[:2])
            else:
                x, y = float(rect.get("x")), float(rect.get("y"))
            node_id = attributes.get("data-draft-node", attributes.get("data-node-id"))
            nodes.append({"id": node_id,
                          "label": attributes.get("aria-label", "".join(element.itertext())),
                          "rect": [x, y, x + float(rect.get("width")), y + float(rect.get("height"))],
                          "container": not draft and rect.get("rx") == "12"})
            if draft:
                for port in element.iter():
                    if "data-draft-port" not in port.attrib:
                        continue
                    circle = children(port, "circle")[0]
                    ports.append({"node": node_id, "name": port.get("data-draft-port"),
                                  "kind": "out" if "out" in port.get("class", "").split() else "in",
                                  "point": [x + float(circle.get("cx")), y + float(circle.get("cy"))]})
        if not draft and "data-port-id" in attributes:
            circle = children(element, "circle")[0]
            ports.append({"node": element.get("data-node-id"), "name": element.get("data-port-id"),
                          "kind": "out" if ":out:" in element.get("data-port-id") else "in",
                          "point": [float(circle.get("cx")), float(circle.get("cy"))]})
    edge_attribute = "data-draft-edge" if draft else "data-edge-id"
    for element in root.iter():
        if edge_attribute not in element.attrib:
            continue
        paths = children(element, "path")
        visible_paths = [path for path in paths if path.get("stroke") != "transparent"]
        path = visible_paths[0]
        points = path_points(path.get("d"))
        start, end = list(points[0]), list(points[-1])
        crossings = []
        for a, b in zip(points, points[1:]):
            for node in nodes:
                if not node["container"] and crosses_open_rectangle(a, b, node["rect"]):
                    crossings.append({"node": node["id"], "segment": [list(a), list(b)]})
        routes.append({"id": element.get(edge_attribute), "path": path.get("d"),
                       "allGroupPathDIdentical": len({p.get("d") for p in paths}) == 1,
                       "points": [list(point) for point in points],
                       "startOutputPorts": [port for port in ports if port["kind"] == "out" and port["point"] == start],
                       "endInputPorts": [port for port in ports if port["kind"] == "in" and port["point"] == end],
                       "markerEnd": path.get("marker-end"), "cardInteriorCrossings": crossings})
    scale = None
    for element in root.iter():
        match = re.search(r"scale\(([^)]+)\)", element.get("transform", ""))
        if match:
            scale = float(match.group(1))
            break
    return {"publicSvgBytesUtf8": len(source.encode()), "publicSvgSha256": hashlib.sha256(source.encode()).hexdigest(),
            "rootAttributes": root.attrib, "draft": draft, "scale": scale, "nodes": nodes, "ports": ports,
            "routes": routes, "nodeCount": len(nodes), "containerCount": sum(n["container"] for n in nodes),
            "visibleCardCount": sum(not n["container"] for n in nodes), "portCount": len(ports), "routeCount": len(routes),
            "allRouteEndpointsHaveMatchingOutputInputPorts": all(r["startOutputPorts"] and r["endInputPorts"] for r in routes),
            "routeCardInteriorCrossingCount": sum(len(r["cardInteriorCrossings"]) for r in routes),
            "sourceGeometryOnly": True, "allRasterEndpointContactCertified": False}
