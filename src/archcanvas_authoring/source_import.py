"""Source-to-draft bridge. Source facts are immutable provenance, draft edits are a copy.

No user's module is imported or executed. A current source frontier is retained as
editable source-linked regions. Hidden hierarchy and exact canonical relations
remain in the provenance, including repeats, shared instances and opaque facts.
"""
from __future__ import annotations

import ast
from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path
import tempfile
import uuid

from archcanvas_python import analyze_project
from .draft import DraftError, _digest, _identity, _keys, _text, _parameter, _diagnostic, _visual, _port_layouts

SOURCE_VERIFICATION = "source-preserved-graph; no model execution"
MAX_SOURCE_NODES, MAX_SOURCE_EDGES = 1200, 3600


def _provenance_digest(value):
    """Bind JSON number values across Python and browser serialization.

    JSON.stringify emits 0 for 0.0. Preserve all actual values, source bytes,
    and IR bindings while treating these identical JSON numbers alike.
    """
    def numbers(item):
        if type(item) is float and math.isfinite(item) and item.is_integer():
            return int(item)
        if isinstance(item, list):
            return [numbers(child) for child in item]
        if isinstance(item, dict):
            return {key: numbers(child) for key, child in item.items()}
        return item
    return _digest(numbers(value))


def _safe_json(value, depth=0):
    if depth > 32:
        raise DraftError("Source provenance exceeds its nesting budget.")
    if value is None or type(value) in (str, bool, int):
        return
    if type(value) is float and math.isfinite(value):
        return
    if isinstance(value, list):
        for child in value:
            _safe_json(child, depth + 1)
        return
    if isinstance(value, dict) and all(type(key) is str for key in value):
        for child in value.values():
            _safe_json(child, depth + 1)
        return
    raise DraftError("Source provenance requires finite JSON data.")


def _analyze_sources(architecture):
    """Reconcile actual source bytes without trusting a client-built IR."""
    sources = architecture.get("sources")
    if not isinstance(sources, list) or not 1 <= len(sources) <= 80:
        raise DraftError("Source import requires the complete original source corpus.")
    with tempfile.TemporaryDirectory(prefix="archcanvas-source-draft-") as temporary:
        root, paths, total = Path(temporary), set(), 0
        for item in sources:
            _keys(item, {"path", "content", "digest"}, "Source provenance file")
            logical = item["path"]
            if type(logical) is not str or Path(logical).is_absolute() or ".." in Path(logical).parts or "\\" in logical or Path(logical).suffix != ".py" or logical in paths:
                raise DraftError("Source paths must be unique relative Python files.")
            if type(item["content"]) is not str:
                raise DraftError("Source content must be text.")
            raw = item["content"].encode("utf-8")
            if hashlib.sha256(raw).hexdigest() != item["digest"]:
                raw = b"\xef\xbb\xbf" + raw
            if hashlib.sha256(raw).hexdigest() != item["digest"]:
                raise DraftError("Source bytes do not match the bound digest.")
            total += len(raw)
            if total > 2_000_000:
                raise DraftError("Source corpus exceeds the 2 MB import budget.")
            path = root / logical
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
            paths.add(logical)
        actual = analyze_project(root, architecture["entry"])
    if actual != architecture:
        raise DraftError("Source import IR differs from independent source analysis.")
    return actual


def _identifier(prefix, original):
    return prefix + hashlib.sha256(original.encode()).hexdigest()[:24]


def _position(raw):
    _keys(raw, {"x", "y"}, "Source draft position")
    if any(type(v) not in (int, float) or not math.isfinite(v) or abs(v) > 1_000_000 for v in raw.values()):
        raise DraftError("Source draft position must be finite world coordinates.")
    return deepcopy(raw)


def _primitive(value):
    return type(value) in (str, bool, int, float) or isinstance(value, list) and all(type(v) is int for v in value)


def _field_from_source(name, value, catalog_fields):
    field = deepcopy(catalog_fields.get(name))
    if field:
        field["default"] = deepcopy(value)
        return field
    kind = "boolean" if type(value) is bool else "integer" if type(value) is int else "number" if type(value) is float else "integer-array" if isinstance(value, list) else "choice"
    return {"name": name, "type": kind, "default": deepcopy(value), **({"options": [value]} if kind == "choice" else {})}


def import_source_draft(document: dict, scene: dict) -> dict:
    """Keep every visible source object and all hidden facts; create a fresh id."""
    from .draft import module_catalog
    if not isinstance(document, dict) or not isinstance(scene, dict):
        raise DraftError("Source import requires the current CanvasDocument and Scene.")
    architecture = _analyze_sources(document.get("architecture", {}))
    if document.get("sourceBindingDigest") != architecture["sourceDigest"] or scene.get("documentId") != document.get("id") or scene.get("revision") != document.get("revision") or scene.get("sourceDigest") != architecture["sourceDigest"] or scene.get("irDigest") != architecture["irDigest"]:
        raise DraftError("Source view is stale; import the current document and scene together.")
    raw_nodes, raw_edges = scene.get("nodes"), scene.get("edges")
    if not isinstance(raw_nodes, list) or len(raw_nodes) > MAX_SOURCE_NODES or not isinstance(raw_edges, list) or len(raw_edges) > MAX_SOURCE_EDGES:
        raise DraftError("Source view exceeds the 1200-object/3600-connection import budget.")
    facts = {n["id"]: n for n in architecture["nodes"]}
    canonical_edges = {e["id"]: e for e in architecture["edges"]}
    catalog = {module["kind"]: module for module in module_catalog()["modules"]}
    scene_bindings = {node["id"]: _identifier("s_", node["id"]) for node in raw_nodes}
    if len(scene_bindings) != len(raw_nodes):
        raise DraftError("Source scene has duplicate object identities.")
    nodes, modules, refs = [], [], {}
    port_maps = {}
    for raw in raw_nodes:
        canonical = raw.get("canonicalNodeId", raw["id"])
        if canonical not in facts:
            raise DraftError("Source view contains an object without a canonical source fact.")
        fact, identity = facts[canonical], scene_bindings[raw["id"]]
        kind = "Source_" + identity[2:]
        fields = {field["name"]: field for field in catalog.get(fact["kind"], {}).get("parameters", [])}
        # Literals from source are retained; absent constructors, shapes and
        # opaque expressions are never fabricated from the palette defaults.
        params = {name: deepcopy(value) for name, value in fact.get("parameters", {}).items() if _primitive(value)}
        for name, value in list(params.items()):
            field = fields.get(name)
            if field and field["type"] == "integer-array" and type(value) is int:
                params[name] = [value] * field.get("length", 1)
        ports, port_bindings = [], {}
        for index, port in enumerate(raw.get("ports", [])):
            port_id = _identifier("p_", port["id"])
            if port["direction"] not in ("in", "out"):
                raise DraftError("Source view port has an invalid direction.")
            bindings = port.get("canonicalBindings", [{"nodeId": port.get("canonicalNodeId", canonical), "portId": port.get("canonicalPortId", port["id"])}])
            if any(binding.get("nodeId") not in facts or not any(p["id"] == binding.get("portId") for p in facts[binding["nodeId"]]["ports"]) for binding in bindings):
                raise DraftError("Source proxy port does not preserve exact canonical bindings.")
            ports.append({"id": port_id, "name": port["name"], "direction": port["direction"], "type": "tensor"})
            port_maps[raw["id"], port["id"]] = port_id
            port_bindings[port_id] = deepcopy(bindings)
        module = {"kind": kind, "label": fact["kind"], "category": "source", "description": "Source module; original hierarchy, repetition, shared instances and unresolved facts are retained in provenance.", "defaults": deepcopy(params),
                  "parameters": [_field_from_source(name, value, fields) for name, value in params.items()], "ports": ports}
        modules.append(module)
        group = bool(raw.get("expanded") and fact.get("children"))
        presentation = {"width": raw["width"], "height": raw["height"], "fill": raw.get("fill", "#ffffff"), "stroke": raw.get("stroke", "#355247"), "group": group,
                        "ports": {port_maps[raw["id"], p["id"]]: {"x": p["x"] - raw["x"], "y": p["y"] - raw["y"]} for p in raw.get("ports", [])}}
        if raw.get("parentId") in scene_bindings:
            presentation["parentId"] = scene_bindings[raw["parentId"]]
        nodes.append({"id": identity, "kind": kind, "label": raw["label"][:120] or fact["kind"], "parameters": params, "position": _position({"x": raw["x"], "y": raw["y"]}), "presentation": presentation})
        manual_ports = {port_maps[raw["id"], p["id"]]: deepcopy(document.get("portLayoutOverrides", {}).get(p.get("layoutKey"))) for p in raw.get("ports", []) if p.get("layoutKey") in document.get("portLayoutOverrides", {})}
        if manual_ports:
            nodes[-1]["portLayouts"] = manual_ports
        refs[identity] = {"nodeId": canonical, "sceneNodeId": raw["id"], "kind": fact["kind"], "category": fact["category"], "evidence": fact["evidence"], "portBindings": port_bindings,
                          "originalParameters": deepcopy(params), "group": group, **({"instanceId": fact["instanceId"]} if "instanceId" in fact else {}), **({"repeat": deepcopy(fact["repeat"])} if "repeat" in fact else {})}
    edges = []
    for raw in raw_edges:
        if raw.get("sourceId") not in scene_bindings or raw.get("targetId") not in scene_bindings or any(edge not in canonical_edges for edge in raw.get("canonicalEdgeIds", [])):
            raise DraftError("Source view relation is missing its exact canonical edge provenance.")
        source_key = raw["sourceId"], raw["source"]["portId"]
        target_key = raw["targetId"], raw["target"]["portId"]
        # Scene endpoints use projected ports, whose ids sometimes differ from
        # the retained canonical endpoint. Resolve by its canonical relation.
        def endpoint(key, direction):
            if key in port_maps:
                return {"nodeId": scene_bindings[key[0]], "portId": port_maps[key]}
            choices = [p for p in next(n for n in raw_nodes if n["id"] == key[0])["ports"] if p["direction"] == direction and any(b["portId"] == key[1] for b in p.get("canonicalBindings", [])) and set(raw["canonicalEdgeIds"]) & set(p.get("canonicalEdgeIds", []))]
            if len(choices) != 1:
                raise DraftError("Source relation must identify one exact projected port.")
            return {"nodeId": scene_bindings[key[0]], "portId": port_maps[key[0], choices[0]["id"]]}
        edges.append({"id": _identifier("e_", raw["id"]), "source": endpoint(source_key, "out"), "target": endpoint(target_key, "in")})
    provenance = {"schemaVersion": 1, "documentId": document["id"], "visualRevision": document["revision"], "sourceDigest": architecture["sourceDigest"], "irDigest": architecture["irDigest"],
                  "architecture": architecture, "canvas": deepcopy(document), "modules": modules, "nodeRefs": refs, "edgeRefs": {_identifier("e_", e["id"]): deepcopy(e["canonicalEdgeIds"]) for e in raw_edges}, "originalGraph": {"nodes": deepcopy(nodes), "edges": deepcopy(edges)}}
    provenance["digest"] = _provenance_digest(provenance)
    draft = {"schemaVersion": 1, "mode": "authored-draft", "id": "draft-" + str(uuid.uuid4()), "title": (document["title"][:108] + " · 编辑副本"), "revision": 0, "nodes": nodes, "edges": edges, "sourceProvenance": provenance}
    validate_source_draft(draft)
    return {"draft": draft, "sceneNodeBindings": scene_bindings, "sourceNodeBindings": {raw.get("canonicalNodeId", raw["id"]): scene_bindings[raw["id"]] for raw in raw_nodes}, "provenanceDigest": provenance["digest"], "verification": SOURCE_VERIFICATION}


def _retain_view_frontier(draft: dict, view: dict) -> dict:
    """Keep the compact source view separate from the editable composition."""
    source, before = draft["sourceProvenance"], view["sourceProvenance"]
    if any(source.get(key) != before.get(key) for key in ("documentId", "visualRevision", "sourceDigest", "irDigest")):
        raise DraftError("Editing and view frontiers must belong to the same source document revision.")
    source["viewCanvas"] = deepcopy(before["canvas"])
    source["viewGraph"] = deepcopy(before["originalGraph"])
    source["digest"] = _provenance_digest({key: value for key, value in source.items() if key != "digest"})
    validate_source_draft(draft)
    return draft


def import_editable_source_draft(document: dict, scene: dict, editing_document: dict, editing_scene: dict) -> dict:
    view = import_source_draft(document, scene)
    imported = import_source_draft(editing_document, editing_scene)
    imported["draft"]["id"] = view["draft"]["id"]
    _retain_view_frontier(imported["draft"], view["draft"])
    imported["provenanceDigest"] = imported["draft"]["sourceProvenance"]["digest"]
    return imported


def validate_source_draft(draft: dict, *, require_complete=False) -> dict:
    from .draft import module_catalog
    _keys(draft, {"schemaVersion", "mode", "id", "title", "revision", "nodes", "edges", "sourceProvenance"} | ({"sourceCache"} if "sourceCache" in draft else set()) | ({"customModules"} if "customModules" in draft else set()) | ({"allowUnusedNodes"} if "allowUnusedNodes" in draft else set()), "Source-derived draft")
    from .custom_modules import validate_custom_definitions, custom_spec
    custom = validate_custom_definitions(draft.get("customModules", []))
    if "allowUnusedNodes" in draft and type(draft["allowUnusedNodes"]) is not bool:
        raise DraftError("allowUnusedNodes must be boolean.")
    if "sourceCache" in draft:
        _keys(draft["sourceCache"], {"nodes", "edges", "removedNodeIds", "removedCanonicalEdgeIds"}, "Source edit cache")
        _safe_json(draft["sourceCache"])
        if len(draft["sourceCache"]["nodes"]) > MAX_SOURCE_NODES or len(draft["sourceCache"]["edges"]) > MAX_SOURCE_EDGES:
            raise DraftError("Source edit cache exceeds its persistence budget.")
    if draft["schemaVersion"] != 1 or draft["mode"] != "authored-draft":
        raise DraftError("Invalid source-derived draft schema.")
    _identity(draft["id"], "Draft id"); _text(draft["title"], "Draft title")
    if type(draft["revision"]) is not int or not 0 <= draft["revision"] <= 2**53 - 1:
        raise DraftError("Invalid source-derived revision.")
    provenance = draft["sourceProvenance"]
    _safe_json(provenance)
    # Existing Python-only receipts remain readable without rewriting history.
    body = {k: v for k, v in provenance.items() if k != "digest"} if isinstance(provenance, dict) else {}
    if not isinstance(provenance, dict) or provenance.get("schemaVersion") != 1 or provenance.get("digest") not in (_provenance_digest(body), _digest(body)):
        raise DraftError("Source provenance digest changed; source facts cannot be edited in the draft.")
    architecture = provenance.get("architecture", {})
    if provenance.get("sourceDigest") != architecture.get("sourceDigest") or provenance.get("irDigest") != architecture.get("irDigest"):
        raise DraftError("Source provenance lost its original source/IR binding.")
    if not isinstance(draft["nodes"], list) or len(draft["nodes"]) > MAX_SOURCE_NODES or not isinstance(draft["edges"], list) or len(draft["edges"]) > MAX_SOURCE_EDGES:
        raise DraftError("Source-derived draft exceeds its node/connection budget.")
    specs = {item["kind"]: item for item in module_catalog()["modules"] + provenance["modules"] + [custom_spec(item) for item in custom]}
    nodes, incoming, outgoing, issues = {}, {}, {}, []
    for node in draft["nodes"]:
        _keys(node, {"id", "kind", "label", "parameters", "position"} | ({"presentation"} if "presentation" in node else set()) | ({"visual"} if "visual" in node else set()) | ({"portLayouts"} if "portLayouts" in node else set()), "Source draft node")
        identity = _identity(node["id"], "Node id")
        if identity in nodes or node["kind"] not in specs:
            raise DraftError("Duplicate or unregistered source-draft node.")
        _text(node["label"], "Node label"); _position(node["position"])
        spec = specs[node["kind"]]
        if set(node["parameters"]) != set(spec["defaults"]):
            raise DraftError("Source node parameters must retain all declared fields.")
        for field in spec["parameters"]:
            _parameter(node["parameters"][field["name"]], field, node["label"], identity)
        if "presentation" in node:
            style = node["presentation"]
            if not isinstance(style, dict) or any(type(style.get(d)) not in (int, float) or not math.isfinite(style[d]) or not 10 <= style[d] <= 1_000_000 for d in ("width", "height")):
                raise DraftError("Imported object dimensions must be finite.")
            _safe_json(style)
        if "visual" in node:
            _visual(node["visual"], identity)
        if "portLayouts" in node:
            _port_layouts(node["portLayouts"], {p["id"] for p in spec["ports"]})
        nodes[identity] = node; incoming[identity] = []; outgoing[identity] = []
    bound, identities = {}, set()
    for edge in draft["edges"]:
        _keys(edge, {"id", "source", "target"}, "Source draft edge")
        identity = _identity(edge["id"], "Edge id")
        if identity in identities:
            raise DraftError("Duplicate source-draft connection.")
        identities.add(identity)
        for end, direction in ((edge["source"], "out"), (edge["target"], "in")):
            _keys(end, {"nodeId", "portId"}, "Source draft endpoint")
            if end["nodeId"] not in nodes or not any(p["id"] == end["portId"] and p["direction"] == direction for p in specs[nodes[end["nodeId"]]["kind"]]["ports"]):
                raise DraftError("Source draft edge must bind exact declared ports.")
        target = (edge["target"]["nodeId"], edge["target"]["portId"])
        if target in bound:
            raise DraftError("Source draft input already has a producer.")
        bound[target] = edge; incoming[target[0]].append(edge); outgoing[edge["source"]["nodeId"]].append(edge)
    degree = {identity: len(incoming[identity]) for identity in nodes}; waiting = [identity for identity in nodes if degree[identity] == 0]; order = []
    while waiting:
        identity = waiting.pop(0); order.append(identity)
        for edge in outgoing[identity]:
            target = edge["target"]["nodeId"]; degree[target] -= 1
            if degree[target] == 0: waiting.append(target)
    if len(order) != len(nodes):
        raise DraftError("Source-derived edits form a cycle; retain an acyclic forward graph.")
    for node in nodes.values():
        ref = provenance["nodeRefs"].get(node["id"])
        if ref and ref["group"]: continue
        for port in specs[node["kind"]]["ports"]:
            if port["direction"] == "in" and (node["id"], port["id"]) not in bound:
                issues.append(_diagnostic("unbound-input", "输入端口尚未连接；可继续编辑源码副本。", "Connect the declared input port.", nodeId=node["id"], portId=port["id"]))
    if require_complete and issues:
        raise DraftError("Source draft is incomplete.", diagnostics=issues)
    return {"draft": deepcopy(draft), "draftDigest": _digest(draft), "complete": not issues, "issues": issues, "tensors": {}, "order": order, "verification": SOURCE_VERIFICATION}


def _source_class(fact, facts, sources):
    """Find a custom source class from its actual descendant forward spans."""
    descendants, pending = [], list(fact.get("children", []))
    while pending:
        child = facts[pending.pop()]; descendants.append(child); pending.extend(child.get("children", []))
    matches = set()
    for item in sources:
        tree = ast.parse(item["content"])
        for cls in tree.body:
            if not isinstance(cls, ast.ClassDef): continue
            init = next((member for member in cls.body if isinstance(member, ast.FunctionDef) and member.name == "__init__"), None)
            names = {arg.arg for arg in init.args.args[1:]} if init else set()
            if not set(fact.get("parameters", {})) <= names: continue
            if any(child.get("source", {}).get("path") == item["path"] and cls.lineno <= child["source"]["line"] <= cls.end_lineno for child in descendants):
                matches.add((item["path"].removesuffix(".py").replace("/", "."), cls.name))
    if len(matches) != 1:
        raise DraftError("Custom source region has no unique class construction evidence; expand it or replace the region.")
    return next(iter(matches))


def _functional_expression(kind, params, args):
    values = [value for _, value in args]
    if kind in ("Add", "Subtract", "Multiply", "Divide", "MatMul"):
        if len(values) != 2: raise DraftError("Binary operation requires exactly two inputs.")
        return values[0] + {"Add": " + ", "Subtract": " - ", "Multiply": " * ", "Divide": " / ", "MatMul": " @ "}[kind] + values[1]
    if kind == "Concat": return f"torch.cat(({', '.join(values)}), dim={params['dim']})"
    value = values[0]
    if kind == "Reshape": return f"{value}.reshape({tuple(params['shape'])!r})"
    if kind == "Transpose": return f"{value}.transpose({params['dim0']}, {params['dim1']})"
    if kind == "Permute": return f"{value}.permute({tuple(params['dims'])!r})"
    if kind in ("Unsqueeze", "Squeeze"): return f"{value}.{kind.lower()}({params['dim']})"
    if kind in ("Mean", "Sum"): return f"{value}.{kind.lower()}(dim={params['dim']}, keepdim={params['keepdim']!r})"
    raise DraftError("Functional source expression has no registered constructor.")



def _materialize_collapsed_frontier(draft: dict) -> tuple[dict, dict[str, str]]:
    """Materialize a hidden source frontier from its canonical IR facts.

    A collapsed root card deliberately has no visible input/output ports or
    displayed edges. Generation still needs the complete graph, so construct
    an ephemeral canonical frontier and rebase the complete edit cache onto it.
    Every source node/port/edge
    comes from ``sourceProvenance.architecture``; display labels are never used
    to infer topology.  The returned id map maps canonical ids to the
    generated draft ids so that bindings can be projected back to the visible
    draft after generation.
    """
    provenance = draft.get("sourceProvenance")
    architecture = provenance.get("architecture") if isinstance(provenance, dict) else None
    if not isinstance(architecture, dict) or not isinstance(architecture.get("nodes"), list) or not isinstance(architecture.get("edges"), list):
        raise DraftError("Collapsed source frontier has no complete canonical architecture provenance.")
    document_id = provenance.get("documentId")
    revision = provenance.get("visualRevision")
    if not isinstance(document_id, str) or type(revision) is not int:
        raise DraftError("Collapsed source frontier provenance is missing its bound document revision.")
    # Reuse the trusted source corpus from provenance.  import_source_draft
    # independently re-analyzes these bytes before accepting the synthetic
    # scene, preserving the same source/IR digest contract as a visible import.
    scene_nodes, index = [], {}
    for ordinal, fact in enumerate(architecture["nodes"]):
        identity = fact.get("id")
        if not isinstance(identity, str) or identity in index:
            raise DraftError("Canonical source architecture contains duplicate node identities.")
        index[identity] = ordinal
        ports = []
        for port_index, port in enumerate(fact.get("ports", [])):
            # Coordinates are only a temporary bridge for source import.  The
            # generated source never relies on them; canonical id/binding data
            # carries the semantic attachment exactly.
            ports.append({"id": port["id"], "name": port["name"], "direction": port["direction"],
                          "x": 32 if port["direction"] == "in" else 144, "y": 24 + port_index * 18,
                          "canonicalNodeId": identity, "canonicalPortId": port["id"],
                          "canonicalBindings": [{"nodeId": identity, "portId": port["id"]}]})
        scene_nodes.append({"id": identity, "canonicalNodeId": identity,
                            "label": str(fact.get("label", fact.get("kind", "source")))[:120],
                            "x": (ordinal % 12) * 220, "y": (ordinal // 12) * 140,
                            "width": 194 if fact.get("children") else 176,
                            "height": 100 if fact.get("children") else 80,
                            "expanded": bool(fact.get("children")),
                            "parentId": fact.get("parentId"), "ports": ports})
    scene_edges = []
    for edge in architecture["edges"]:
        source, target = edge.get("source", {}), edge.get("target", {})
        if source.get("nodeId") not in index or target.get("nodeId") not in index:
            raise DraftError("Canonical source edge refers to a missing node.")
        # The renderer's fully expanded frontier omits plumbing edges attached
        # directly to container cards.  Child/leaf bindings remain exact and
        # still let the grouped generator derive each real group boundary.
        source_fact = architecture["nodes"][index[source["nodeId"]]]
        target_fact = architecture["nodes"][index[target["nodeId"]]]
        if source_fact.get("children") or target_fact.get("children"):
            continue
        scene_edges.append({"id": edge["id"], "sourceId": source["nodeId"], "targetId": target["nodeId"],
                            "source": {"portId": source["portId"]}, "target": {"portId": target["portId"]},
                            "canonicalEdgeIds": [edge["id"]]})
    scene = {"documentId": document_id, "revision": revision,
             "sourceDigest": architecture.get("sourceDigest"), "irDigest": architecture.get("irDigest"),
             "nodes": scene_nodes, "edges": scene_edges}
    source_document = {"schemaVersion": 1, "id": document_id, "title": provenance.get("canvas", {}).get("title", draft.get("title", "模型")),
                       "revision": revision, "sourceBindingDigest": architecture.get("sourceDigest"),
                       "architecture": architecture}
    # Rebase, rather than importing a pristine graph and overlaying only the
    # visible card, so cached parameters, removals, rewires and ordinary user
    # nodes survive exactly as they do when the user explicitly expands.
    materialized = rebase_source_frontier(draft, source_document, scene)["draft"]
    by_canonical = {ref["nodeId"]: identity for identity, ref in materialized["sourceProvenance"]["nodeRefs"].items()}
    return materialized, by_canonical


def _project_materialized_result(result: dict, original: dict, by_canonical: dict[str, str]) -> dict:
    """Expose bindings only for cards retained in the collapsed draft."""
    refs = original.get("sourceProvenance", {}).get("nodeRefs", {})
    visible_by_materialized = {}
    for node in original["nodes"]:
        identity = node["id"]
        ref = refs.get(identity)
        canonical = ref.get("nodeId") if isinstance(ref, dict) else None
        visible_by_materialized[by_canonical.get(canonical, identity)] = identity
    for field in ("nodeBindings", "containerBindings"):
        result[field] = {visible_by_materialized[key]: value for key, value in result.get(field, {}).items() if key in visible_by_materialized}
    # A displayed proxy edge can represent several canonical leaf edges. Its
    # ID changes on expansion, so project the independently verified paths
    # back through source identities instead of dropping its port/style map.
    materialized = result["draft"]
    canonical_edges = {}
    for identity, canonical_ids in materialized["sourceProvenance"]["edgeRefs"].items():
        for canonical in canonical_ids:
            canonical_edges.setdefault(canonical, set()).add(identity)
    original_edges = {edge["id"]: edge for edge in original["sourceProvenance"]["originalGraph"]["edges"]}
    edge_bindings, port_bindings = {}, {}
    for edge in original["edges"]:
        identity = edge["id"]
        candidates = {identity} if identity in result.get("edgeBindings", {}) else set()
        if original_edges.get(identity) == edge:
            for canonical in original["sourceProvenance"]["edgeRefs"].get(identity, []):
                candidates.update(canonical_edges.get(canonical, set()))
        else:
            # A rewire/fan-out rebased through a collapsed proxy has derived
            # IDs, bound to the original edit ID and its exact new endpoints.
            for item in materialized["edges"]:
                derived = _identifier("r_", json.dumps([identity, item["source"], item["target"]], sort_keys=True))
                if item["id"] == derived:
                    candidates.add(item["id"])
        paths = sorted({generated for key in candidates for generated in result.get("edgeBindings", {}).get(key, [])})
        if not paths:
            # Retained custom boundaries can expose a valid multi-slot edge
            # whose analyzer identity is intentionally hidden behind the
            # adapter. Keep the relation unresolved for style projection; the
            # grouped generator has already independently checked its ports.
            if result.get("verification", {}).get("retainedSourceModules") or result.get("verification", {}).get("customBoundaryBindings") or result.get("entry", "").startswith("archcanvas_composed:"):
                edge_bindings[identity] = []
                port_bindings[identity] = {"source": deepcopy(edge["source"]), "target": deepcopy(edge["target"]),
                                           "architectureEdges": [], "projected": True}
                continue
            raise DraftError("Materialized source lost a visible connection binding.")
        edge_bindings[identity] = paths
        port_bindings[identity] = {"source": deepcopy(edge["source"]), "target": deepcopy(edge["target"]),
                                   "architectureEdges": paths, "projected": True}
    result["edgeBindings"], result["portBindings"] = edge_bindings, port_bindings
    result["draft"] = deepcopy(original)
    result["draftDigest"] = _digest(original)
    verification = dict(result.get("verification", {}))
    verification.update({"scope": "source-preserved-collapsed-frontier-materialized-from-canonical-facts",
                         "sourceProvenanceDigest": original["sourceProvenance"]["digest"],
                         "modelExecution": "not_run"})
    result["verification"] = verification
    return result


def generate_source_draft(draft: dict) -> dict:
    """Generate an independently analyzed source copy with exact graph bindings.

    A source frontier with a real presentation group is emitted through the
    grouped generator. This dispatch is deliberately based on persisted group
    metadata, never on a display label or a guessed source hierarchy.

    Constructors come from explicit original source facts. Each shared instance
    is constructed once; role-decorated view ports retain their canonical tensor
    identity rather than becoming invented tuple outputs.
    """
    # Validate the actual edited draft before inspecting or materializing its
    # source provenance. Invalid digests, disconnected ordinary nodes, and
    # malformed relations must never disappear behind a pristine source import.
    validated = validate_source_draft(draft, require_complete=True)
    provenance = draft["sourceProvenance"]
    refs = provenance["nodeRefs"]
    canonical_nodes = provenance["architecture"]["nodes"]
    if any(node.get('sourceStructure') for node in canonical_nodes):
        raise DraftError(
            'Source inspection is expandable but has no verified tensor lowering; preserve presentation edits on the original canvas.',
            diagnostics=[_diagnostic('unsupported-source-structure',
                                    '源码分支可以展开查看；尚未确定实际路径和张量连接。展示修改可以保存到原画布，结构生成需要真实配置和受支持的解析规则。',
                                    'Keep visual edits on the source canvas; provide configuration evidence before semantic generation.')],
        )
    canonical_facts = {node["id"]: node for node in canonical_nodes}
    visible_kinds = {refs.get(node["id"], {}).get("kind", node["kind"]) for node in draft["nodes"]}
    canonical_kinds = {node["kind"] for node in canonical_nodes}
    hidden_groups = any(
        canonical_facts.get(refs.get(node["id"], {}).get("nodeId"), {}).get("children")
        and not node.get("presentation", {}).get("group")
        for node in draft["nodes"]
    )
    custom_composition = bool(draft.get("customModules"))
    retained_custom_source = any(item.get("path", "").startswith("archcanvas_custom_")
                                for item in provenance.get("architecture", {}).get("sources", []))
    # Partial frontiers (e.g. expanded Transformer with collapsed encoder and
    # decoder) need the same canonical materialization as a collapsed root.
    # The browser must not expand and route every intermediate scene merely
    # to generate source. Validate the edited frontier above before restoring
    # hidden facts, and rebase its cache so additions/deletions stay effective.
    materialize = hidden_groups and {"Input", "Output"} <= canonical_kinds and not retained_custom_source
    grouped = custom_composition or any(node.get("presentation", {}).get("group") for node in draft["nodes"])
    if materialize or grouped:
        # Group constructors have no independent lowering contract. Refuse
        # parameter edits explicitly instead of silently dropping them while
        # rebuilding a group from its canonical child graph.
        candidates = {node["id"]: node for node in draft.get("sourceCache", {}).get("nodes", [])}
        candidates.update({node["id"]: node for node in draft["nodes"]})
        for identity, node in candidates.items():
            ref = refs.get(identity)
            fact = canonical_facts.get(ref.get("nodeId")) if isinstance(ref, dict) else None
            if fact and fact.get("children") and node["parameters"] != ref.get("originalParameters"):
                raise DraftError(
                    "Source group constructor edits cannot be generated independently; edit its expanded child modules instead.",
                    diagnostics=[_diagnostic("unsupported-group-parameters", "源码分组的构造参数尚无独立生成规则；请展开后编辑子模块参数。", "Expand this source group and edit child module parameters.", nodeId=identity)],
                )
    if materialize:
        from .source_generation_groups import generate_grouped_source
        materialized, canonical_ids = _materialize_collapsed_frontier(draft)
        materialized_refs = materialized["sourceProvenance"]["nodeRefs"]
        kinds = {materialized_refs.get(node["id"], {}).get("kind", node["kind"]) for node in materialized["nodes"]}
        if not {"Input", "Output"} <= kinds:
            raise DraftError(
                "Source draft needs retained or declared inputs and outputs; deleted source endpoints are not restored.",
                diagnostics=[_diagnostic("missing-source-io", "当前草稿缺少输入或输出；已删除的源码端点不会自动恢复。", "Add or restore the intended Input and Output nodes.")],
            )
        return _project_materialized_result(generate_grouped_source(materialized), draft, canonical_ids)
    if grouped:
        from .source_generation_groups import generate_grouped_source
        if not {"Input", "Output"} <= visible_kinds:
            raise DraftError(
                "A source-derived model needs retained or declared inputs and outputs.",
                diagnostics=[_diagnostic("missing-source-io", "当前草稿缺少输入或输出；请添加或恢复所需端点。", "Add or restore the intended Input and Output nodes.")],
            )
        return generate_grouped_source(draft)
    from .draft import module_catalog, _name
    from .catalog import FUNCTIONAL
    original = _analyze_sources(provenance["architecture"])
    catalog = {item["kind"]: item for item in module_catalog()["modules"]}
    specs = {**catalog, **{item["kind"]: item for item in provenance["modules"]}}
    facts, nodes = {item["id"]: item for item in original["nodes"]}, {item["id"]: item for item in draft["nodes"]}
    producers = {(e["target"]["nodeId"], e["target"]["portId"]): e["source"] for e in draft["edges"]}
    refs, symbols, input_ids, output_ids = provenance["nodeRefs"], {}, [], []
    init, forward, constructors, imports, expressions = [], [], {}, set(), {}
    def ref_kind(node): return refs.get(node["id"], {}).get("kind", node["kind"])
    def value(end):
        if (end["nodeId"], end["portId"]) not in symbols:
            raise DraftError("This expanded boundary has no proven tensor producer; retain the source region or replace it explicitly.")
        return symbols[end["nodeId"], end["portId"]]
    def inputs(node): return [(p, value(producers[node["id"], p["id"]])) for p in specs[node["kind"]]["ports"] if p["direction"] == "in"]
    def constructor(fact, params):
        kind = fact["kind"]
        if any(not _primitive(v) for v in fact["parameters"].values()):
            raise DraftError("Original constructor contains unresolved values; replace this source region explicitly before generating.")
        if kind == "Module":
            children = [facts[id] for id in fact["children"]]
            if fact.get("repeat") and fact["repeat"]["count"] == len(children) and children and all(child["kind"] in catalog for child in children):
                return "nn.Sequential(" + ", ".join(constructor(child, child["parameters"]) for child in children) + ")"
            module, cls = _source_class(fact, facts, original["sources"])
            imports.add(f"from {module} import {cls}")
            return f"{cls}({', '.join(f'{k}={v!r}' for k,v in params.items())})"
        if kind not in catalog: raise DraftError("Source operator has no explicit constructor; retain it in the draft or replace it with a registered module.")
        return f"nn.{kind}({', '.join(f'{k}={v!r}' for k,v in params.items())})"
    def names_for_port(ref, port):
        bindings = ref["portBindings"][port["id"]]
        return {(b["nodeId"], next(p["name"] for p in facts[b["nodeId"]]["ports"] if p["id"] == b["portId"])) for b in bindings}
    for identity in validated["order"]:
        node, ref = nodes[identity], refs.get(identity)
        spec, kind = specs[node["kind"]], ref_kind(node)
        outputs = [p for p in spec["ports"] if p["direction"] == "out"]
        symbol = _name(identity)
        if ref and ref["group"]: continue
        if kind == "Input":
            input_ids.append(identity)
            for port in outputs: symbols[identity, port["id"]] = symbol
            continue
        args = inputs(node)
        if kind == "Output":
            if len(args) != 1: raise DraftError("A retained output needs exactly one producer.")
            output_ids.append((identity, args[0][1])); continue
        if kind in FUNCTIONAL:
            expression = _functional_expression(kind, node["parameters"], args)
        elif kind == "Repeat" and ref:
            fact = facts[ref["nodeId"]]
            children = [facts[id] for id in fact["children"]]
            if not children or not args: raise DraftError("Repeated source region has no explicit module children.")
            first, *rest = args
            direct = {child["id"] for child in children}
            other = []
            for port, argument in rest:
                names = {name for node_id, name in names_for_port(ref, port) if node_id in direct}
                if len(names) == 1: other.append((next(iter(names)), argument))
                elif argument != first[1]: raise DraftError("Repeated residual boundary was rewired independently; expand the region to generate the changed structure.")
            key = fact["id"]
            reference = "self." + symbol
            init.append(f"        {reference} = nn.ModuleList([{', '.join(constructor(child, child['parameters']) for child in children)}])")
            forward.append(f"        {symbol} = {first[1]}")
            forward.append(f"        for source_layer in {reference}:")
            forward.append(f"            {symbol} = source_layer({symbol}{', ' if other else ''}{', '.join(f'{name}={arg}' for name,arg in other)})")
            expression = None
        elif ref:
            fact = facts[ref["nodeId"]]
            key = ref.get("instanceId", ref["nodeId"])
            params = node["parameters"]
            previous = constructors.get(key)
            if previous and previous[0] != params:
                raise DraftError("Shared module calls have conflicting constructor edits; edit all shared calls consistently.")
            if not previous:
                reference = "self." + symbol
                init.append(f"        {reference} = {constructor(fact, params)}")
                constructors[key] = (params, reference)
            reference = constructors[key][1]
            if kind == "MultiheadAttention":
                keywords = {}
                for port, argument in args:
                    for _, name in names_for_port(ref, port): keywords[name] = argument
                if not {"query", "key", "value"} <= set(keywords): raise DraftError("Attention requires its exact Q/K/V source bindings.")
                expression = reference + "(" + ", ".join(f"{name}={arg}" for name, arg in keywords.items()) + ", need_weights=False)"
            elif kind == "Module":
                keywords = {}
                for port, argument in args:
                    names = {name for node_id, name in names_for_port(ref, port) if node_id == ref["nodeId"]}
                    if names: keywords.update({name: argument for name in names})
                    elif argument not in keywords.values() and argument != args[0][1]: raise DraftError("Collapsed module boundary was edited internally; expand it before generating.")
                expression = reference + "(" + (next(iter(keywords.values())) if len(keywords) == 1 else ", ".join(f"{name}={arg}" for name,arg in keywords.items())) + ")"
            else: expression = reference + "(" + ", ".join(argument for _, argument in args) + ")"
        else:
            reference = "self." + symbol
            init.append(f"        {reference} = nn.{kind}({', '.join(f'{k}={v!r}' for k,v in node['parameters'].items())})")
            expression = reference + "(" + ", ".join(argument for _, argument in args) + ")"
        if expression is not None:
            expressions[identity] = expression
            if kind == "MultiheadAttention":
                forward.append(f"        {symbol}, {symbol}_weights = {expression}")
            elif kind in ("LSTM", "GRU", "RNN"):
                tail = f"({symbol}_h_n, {symbol}_c_n)" if kind == "LSTM" else f"{symbol}_h_n"
                forward.append(f"        {symbol}, {tail} = {expression}")
            else: forward.append(f"        {symbol} = {expression}")
        for port in outputs:
            if ref:
                names = {name for _, name in names_for_port(ref, port)}
                if len(names) != 1: raise DraftError("Projected output combines distinct canonical values; expand the source region.")
                name = next(iter(names))
            else: name = port["id"]
            symbols[identity, port["id"]] = symbol + ("_" + name if name in {"weights", "h_n", "c_n"} else "")
    if not input_ids or not output_ids: raise DraftError("A source-derived model needs retained or declared inputs and outputs.")
    lines = ['"""ArchCanvas source-derived editing copy. No runtime equivalence is asserted."""', "import torch", "from torch import nn", *sorted(imports), "", "", "class AuthoredModel(nn.Module):", "    def __init__(self):", "        super().__init__()", *init, "", f"    def forward(self, {', '.join(_name(id) for id in input_ids)}):", *forward, "        return {" + ", ".join(f"{key!r}: {val}" for key, val in output_ids) + "}", ""]
    source = "\n".join(lines); ast.parse(source)
    filename = "archcanvas_authored.py"
    if any(s["path"] == filename for s in original["sources"]): raise DraftError("Generated filename collides with preserved source; choose a new source project.")
    with tempfile.TemporaryDirectory(prefix="archcanvas-generated-source-") as temporary:
        root = Path(temporary)
        for item in original["sources"]:
            path = root / item["path"]; path.parent.mkdir(parents=True, exist_ok=True); path.write_text(item["content"], encoding="utf-8")
        (root / filename).write_text(source, encoding="utf-8")
        architecture = analyze_project(root, "archcanvas_authored:AuthoredModel")
    bindings = {}
    for node in draft["nodes"]:
        id = node["id"]; kind = ref_kind(node)
        if node.get("presentation", {}).get("group"): continue
        if kind == "Input": matches = [n for n in architecture["nodes"] if n["kind"] == "Input" and n["label"] == _name(id)]
        elif kind == "Output": matches = [n for n in architecture["nodes"] if n["kind"] == "Output" and n.get("outputPath") == [{"kind": "key", "key": id}]]
        elif kind == "Repeat": matches = [n for n in architecture["nodes"] if n["id"] == "repeat:instance:archcanvas_authored.AuthoredModel." + _name(id)]
        elif kind in FUNCTIONAL: matches = [n for n in architecture["nodes"] if n.get("source", {}).get("expression") == expressions.get(id)]
        else:
            reference = constructors.get(refs.get(id, {}).get("instanceId", refs.get(id, {}).get("nodeId", id)), (None, "self." + _name(id)))[1]
            matches = [n for n in architecture["nodes"] if n.get("instanceId") == "instance:archcanvas_authored.AuthoredModel." + reference.removeprefix("self.") and n.get("source", {}).get("expression") == expressions.get(id)]
        if len(matches) != 1: raise DraftError("Generated source lost an exact operation binding; source copy generation refused.")
        bindings[id] = matches[0]["id"]
    if len(set(bindings.values())) != len(bindings): raise DraftError("Generated source aliases distinct draft operations.")
    # Bind each retained draft edge to the exact generated tensor edge(s).
    # Root-to-wrapper edges are intentionally excluded; they are generated
    # container plumbing, while this map covers user-editable graph relations.
    edge_bindings = {}
    for edge in draft["edges"]:
        source_id, target_id = bindings.get(edge["source"]["nodeId"]), bindings.get(edge["target"]["nodeId"])
        matches = [item["id"] for item in architecture["edges"] if item["source"]["nodeId"] == source_id and item["target"]["nodeId"] == target_id]
        if not matches and edge["source"]["nodeId"] in bindings and edge["target"]["nodeId"] in bindings:
            # A collapsed proxy may materialize one canonical relation through
            # a generated group loop; retain an explicit empty binding rather
            # than guessing from labels or tensor text.
            edge_bindings[edge["id"]] = []
        else: edge_bindings[edge["id"]] = matches
    return {"draft": deepcopy(draft), "draftDigest": validated["draftDigest"], "entry": "archcanvas_authored:AuthoredModel", "source": source, "architecture": architecture, "nodeBindings": bindings, "containerBindings": {}, "edgeBindings": edge_bindings, "portBindings": {}, "tensors": {},
            "verification": {"status": "passed", "scope": "source-corpus-preservation-and-exact-static-operation-bindings", "modelExecution": "not_run", "sourceProvenanceDigest": provenance["digest"], "limitations": ["Original source corpus is preserved in a new managed copy; shared modules retain one construction.", "Shapes and numerical equivalence are unverified; no model is executed.", "Unknown expressions require explicit replacement before executable source generation."]}}


def rebase_source_frontier(draft: dict, document: dict, scene: dict) -> dict:
    """Reproject a source hierarchy while retaining edits and hidden descendants.

    Newly revealed internals come only from the independently analyzed corpus.
    Changed external bindings expand through their exact canonical proxy ports.
    A hidden edit cache is part of the saved draft, not a discarded UI snapshot.
    """
    validate_source_draft(draft)
    imported = import_source_draft(document, scene)
    fresh, old = imported["draft"], draft["sourceProvenance"]
    provenance = fresh["sourceProvenance"]
    if provenance["sourceDigest"] != old["sourceDigest"] or provenance["irDigest"] != old["irDigest"]:
        raise DraftError("Source hierarchy rebase cannot replace the frozen source corpus.")
    previous = draft.get("sourceCache", {"nodes": [], "edges": [], "removedNodeIds": [], "removedCanonicalEdgeIds": []})
    cached_nodes = {node["id"]: deepcopy(node) for node in previous["nodes"]}
    cached_nodes.update({node["id"]: deepcopy(node) for node in draft["nodes"]})
    current_nodes = {node["id"]: node for node in draft["nodes"]}
    original_nodes = {node["id"]: node for node in old["originalGraph"]["nodes"]}
    removed_nodes = set(previous["removedNodeIds"]) | (set(original_nodes) - set(current_nodes))
    current_edges = {edge["id"]: edge for edge in draft["edges"]}
    original_edges = {edge["id"]: edge for edge in old["originalGraph"]["edges"]}
    changed_edges = {edge["id"]: deepcopy(edge) for edge in previous["edges"]}
    live_ids = set(current_nodes)
    # Removing a user-created connection while its endpoints are visible removes
    # its cached counterpart as well; hidden connections survive a collapse.
    changed_edges = {id: edge for id, edge in changed_edges.items() if id in current_edges or not {edge["source"]["nodeId"], edge["target"]["nodeId"]} <= live_ids}
    removed_edges = set(previous["removedCanonicalEdgeIds"])
    for id, edge in original_edges.items():
        if current_edges.get(id) != edge: removed_edges.update(old["edgeRefs"].get(id, []))
    for id, edge in current_edges.items():
        if original_edges.get(id) != edge: changed_edges[id] = deepcopy(edge)
    # Metadata for formerly visible nodes stays available for exact port mapping.
    refs = deepcopy(old["nodeRefs"])
    for identity, ref in provenance["nodeRefs"].items():
        prior = refs.get(identity, {})
        refs[identity] = {**deepcopy(ref), "portBindings": {**deepcopy(prior.get("portBindings", {})), **deepcopy(ref["portBindings"])}}
    modules = {module["kind"]: module for module in old["modules"] + provenance["modules"]}
    source_facts = {node["id"]: node for node in provenance["architecture"]["nodes"]}
    removed_canonical = {refs[id]["nodeId"] for id in removed_nodes if id in refs}
    def removed_descendant(id):
        canonical = refs.get(id, {}).get("nodeId")
        while canonical:
            if canonical in removed_canonical: return True
            canonical = source_facts.get(canonical, {}).get("parentId")
        return False
    nodes = []
    for node in fresh["nodes"]:
        if node["id"] in removed_nodes or removed_descendant(node["id"]): continue
        previous_node = cached_nodes.get(node["id"])
        if previous_node:
            node["label"], node["parameters"], node["position"] = deepcopy(previous_node["label"]), deepcopy(previous_node["parameters"]), deepcopy(previous_node["position"])
            node["presentation"]["fill"], node["presentation"]["stroke"] = previous_node.get("presentation", node["presentation"])["fill"], previous_node.get("presentation", node["presentation"])["stroke"]
            if "visual" in previous_node:
                node["visual"] = deepcopy(previous_node["visual"])
            if "portLayouts" in previous_node:
                # Scene port IDs include projection/side information and may
                # change between frontiers. Retain offsets through canonical
                # bindings rather than attaching obsolete IDs to the new spec.
                current_ref = provenance["nodeRefs"][node["id"]]
                previous_ref = refs[node["id"]]
                current_ports = modules[node["kind"]]["ports"]
                previous_spec = next((m for m in old["modules"] if m["kind"] == previous_node["kind"]), {})
                previous_ports = {p["id"]: p for p in previous_spec.get("ports", [])}
                layouts = {}
                for port_id, layout in previous_node["portLayouts"].items():
                    if any(p["id"] == port_id for p in current_ports):
                        layouts[port_id] = deepcopy(layout)
                        continue
                    pairs = {(p["nodeId"], p["portId"]) for p in previous_ref["portBindings"].get(port_id, [])}
                    candidates = [p for p in current_ports if pairs & {
                        (b["nodeId"], b["portId"]) for b in current_ref["portBindings"].get(p["id"], [])}]
                    previous_port = previous_ports.get(port_id)
                    if previous_port:
                        candidates = [p for p in candidates if p["direction"] == previous_port["direction"]]
                        named = [p for p in candidates if p["name"] == previous_port["name"]]
                        if named:
                            candidates = named
                    for port in candidates:
                        layouts[port["id"]] = deepcopy(layout)
                if layouts:
                    node["portLayouts"] = layouts
        nodes.append(node)
    visible = {node["id"] for node in nodes}
    for node in draft["nodes"]:
        if node["id"] not in refs and node["id"] not in visible:
            nodes.append(deepcopy(node)); visible.add(node["id"])
    edges = [edge for edge in fresh["edges"] if edge["source"]["nodeId"] in visible and edge["target"]["nodeId"] in visible and not set(provenance["edgeRefs"].get(edge["id"], [])) & removed_edges]
    def mapped_end(end, direction):
        if end["nodeId"] in visible:
            current = next((item for item in nodes if item["id"] == end["nodeId"]), None)
            if current and end["nodeId"] not in refs:
                return [deepcopy(end)]  # Registered ordinary node, already validated.
            current_spec = modules.get(current.get("kind")) if current else None
            if current_spec and any(port["id"] == end["portId"] and port["direction"] == direction for port in current_spec.get("ports", [])):
                return [deepcopy(end)]
        ref = refs.get(end["nodeId"])
        if not ref: return []
        bindings = ref["portBindings"].get(end["portId"], [])
        pairs = {(b["nodeId"], b["portId"]) for b in bindings}
        candidates = []
        for node in nodes:
            current_ref = provenance["nodeRefs"].get(node["id"])
            if not current_ref or node.get("presentation", {}).get("group"): continue
            spec = modules[node["kind"]]
            for port in spec["ports"]:
                if port["direction"] == direction and pairs & {(b["nodeId"], b["portId"]) for b in current_ref["portBindings"].get(port["id"], [])}:
                    candidates.append({"nodeId": node["id"], "portId": port["id"]})
        return candidates
    for edge in changed_edges.values():
        sources, targets = mapped_end(edge["source"], "out"), mapped_end(edge["target"], "in")
        if not sources or not targets: continue  # Hidden internal edit remains cached.
        for source in sources:
            for target in targets:
                if source["nodeId"] == target["nodeId"]: continue
                identity = edge["id"] if len(sources) * len(targets) == 1 else _identifier("r_", json.dumps([edge["id"], source, target], sort_keys=True))
                # Role-projected source ports can be aliases of one tensor. For
                # a target, select the original role where possible; never add
                # multiple producers silently.
                if any(item["target"] == target for item in edges):
                    edges = [item for item in edges if item["target"] != target]
                edges.append({"id": identity, "source": source, "target": target})
    provenance["nodeRefs"], provenance["modules"] = refs, list(modules.values())
    for key in ("viewCanvas", "viewGraph"):
        if key in old:
            provenance[key] = deepcopy(old[key])
    provenance["digest"] = _provenance_digest({key: value for key, value in provenance.items() if key != "digest"})
    fresh.update({"id": draft["id"], "title": draft["title"], "revision": draft["revision"], "nodes": nodes, "edges": edges,
                  "sourceCache": {"nodes": list(cached_nodes.values()), "edges": list(changed_edges.values()), "removedNodeIds": sorted(removed_nodes), "removedCanonicalEdgeIds": sorted(removed_edges)}})
    if "customModules" in draft:
        fresh["customModules"] = deepcopy(draft["customModules"])
    validate_source_draft(fresh)
    return {**imported, "draft": fresh, "provenanceDigest": provenance["digest"]}
