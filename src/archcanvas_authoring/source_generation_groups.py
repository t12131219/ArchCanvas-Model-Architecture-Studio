"""Strict nested source generation for source and authored grouped drafts.

The generator emits a fresh module hierarchy and then independently analyses the
fresh bytes.  Grouping is semantic ownership: tensor values are carried by
canonical node/port pairs and are never recovered from display order.
"""
from __future__ import annotations

import ast
from copy import deepcopy
import hashlib
import re
import tempfile
from pathlib import Path

from archcanvas_python import analyze_project

from .catalog import BY_KIND, FUNCTIONAL
from .draft import DraftError, _digest, _name, validate_draft


def _symbol(identity: str, prefix: str = "node_") -> str:
    return prefix + hashlib.sha256(identity.encode()).hexdigest()[:12]


def _safe_class(identity: str) -> str:
    return "GraphGroup_" + re.sub(r"[^A-Za-z0-9_]", "_", identity)[:35] + "_" + hashlib.sha256(identity.encode()).hexdigest()[:8]


def generate_grouped_source(draft: dict) -> dict:
    refs = draft.get("sourceProvenance", {}).get("nodeRefs", {}) if isinstance(draft.get("sourceProvenance"), dict) else {}
    original = deepcopy(draft)
    if refs:
        from .source_import import validate_source_draft
        validated = validate_source_draft(draft, require_complete=True)
    else:
        grouped = {n["id"] for n in draft.get("nodes", []) if n.get("presentation", {}).get("group")}
        semantic = deepcopy(draft)
        semantic["nodes"] = [{k: deepcopy(v) for k, v in n.items() if k != "presentation"} for n in draft.get("nodes", []) if n["id"] not in grouped]
        validated = validate_draft(semantic, require_complete=True)
    nodes = {n["id"]: n for n in original["nodes"]}
    edges = list(original["edges"])
    groups = {n["id"] for n in original["nodes"] if n.get("presentation", {}).get("group")}
    parents = {n["id"]: n.get("presentation", {}).get("parentId") for n in original["nodes"]}

    def kind(node):
        result = refs.get(node["id"], {}).get("kind", node["kind"])
        if result in BY_KIND or result in {"Module", "Repeat", "Sequential"}:
            return result
        raise DraftError(f"分组生成器不接受未注册模块 {node['kind']}；请先展开未知源码边界。")

    def group_parent(identity):
        parent, seen = parents.get(identity), set()
        while parent is not None:
            if parent in seen:
                raise DraftError("分组层级形成环路。")
            seen.add(parent)
            if parent in groups:
                return parent
            parent = parents.get(parent)
        return None

    roots = {g for g in groups if parents.get(g) is None}
    # A complete imported model root already owns its Input/Output cards.
    # Emit that root as AuthoredModel itself instead of introducing a redundant
    # inner group whose Input/Output peers would overlap the original frame.
    # Ordinary authored groups and source regions whose I/O lives outside the
    # region remain real nested modules.
    source_facts = {n["id"]: n for n in original.get("sourceProvenance", {}).get("architecture", {}).get("nodes", [])}
    def contained_by(identity, ancestor):
        seen = set()
        while identity is not None and identity not in seen:
            if identity == ancestor:
                return True
            seen.add(identity); identity = parents.get(identity)
        return False
    source_io = [n["id"] for n in original["nodes"] if refs.get(n["id"], {}).get("kind") in {"Input", "Output"}]
    virtual_roots = {g for g in roots if refs.get(g, {}).get("kind") == "Module"
                     and source_facts.get(refs[g].get("nodeId"), {}).get("parentId") is None
                     and source_io and all(contained_by(identity, g) for identity in source_io)}

    def owner(identity):
        parent = group_parent(identity)
        return None if parent in virtual_roots else parent

    children: dict[str | None, list[str]] = {}
    for identity in nodes:
        if identity not in virtual_roots:
            children.setdefault(owner(identity), []).append(identity)

    def is_inside(identity, group):
        if identity == group:
            return True
        parent, seen = parents.get(identity), set()
        while parent is not None:
            if parent in seen:
                raise DraftError("分组层级形成环路。")
            seen.add(parent)
            if parent == group:
                return True
            parent = parents.get(parent)
        return False

    modules = {m["kind"]: m for m in original.get("sourceProvenance", {}).get("modules", [])}

    def spec(node):
        return modules.get(node["kind"]) or BY_KIND.get(kind(node))

    def ports(node, direction):
        return [p for p in (spec(node) or {}).get("ports", []) if p["direction"] == direction]

    facts = {n["id"]: n for n in original.get("sourceProvenance", {}).get("architecture", {}).get("nodes", [])}

    def semantic_names(node, port):
        if not refs:
            return [port.get("name", port["id"])]
        names = []
        for binding in refs[node["id"]].get("portBindings", {}).get(port["id"], []):
            fact = facts.get(binding.get("nodeId"), {})
            names.extend(p.get("name", p["id"]) for p in fact.get("ports", []) if p["id"] == binding.get("portId"))
        return names or [port.get("name", port["id"])]

    def tensor_key(endpoint):
        node = nodes[endpoint["nodeId"]]
        port = next((p for p in ports(node, "out") if p["id"] == endpoint["portId"]), None)
        names = semantic_names(node, port) if port else [endpoint["portId"]]
        if len(set(names)) != 1:
            raise DraftError("输出代理混合不同canonical张量，无法生成。")
        return (endpoint["nodeId"], next(iter(names)))

    def crossing_edges(group, incoming):
        """Return every boundary edge, including projected duplicate targets."""
        result = []
        for edge in edges:
            source, target = edge["source"]["nodeId"], edge["target"]["nodeId"]
            crossing = (is_inside(target, group) and not is_inside(source, group)) if incoming else (is_inside(source, group) and not is_inside(target, group))
            if crossing:
                result.append(edge)
        return result

    def boundary(group, incoming):
        """Return one formal slot per source port for a group boundary."""
        result, seen = [], set()
        for edge in crossing_edges(group, incoming):
            key = tensor_key(edge["source"])
            if key not in seen:
                seen.add(key); result.append(edge)
        return result

    def result_edges(group):
        """Edges whose producer tensor must cross a group call boundary."""
        result = boundary(group, False)
        seen = {tensor_key(e["source"]) for e in result}
        for edge in edges:
            if kind(nodes[edge["target"]["nodeId"]]) == "Output" and is_inside(edge["target"]["nodeId"], group) and is_inside(edge["source"]["nodeId"], group):
                key = tensor_key(edge["source"])
                if key not in seen:
                    seen.add(key); result.append(edge)
        return result

    def projected_dependencies(scope):
        members = set(children.get(scope, [])); result = []
        def direct(identity):
            current = identity
            while current not in members:
                parent = parents.get(current)
                if parent is None:
                    return None
                current = parent
            return current
        for edge in edges:
            source, target = direct(edge["source"]["nodeId"]), direct(edge["target"]["nodeId"])
            if source is not None and target is not None and source != target:
                result.append((source, target))
        return result

    class_names = {g: _safe_class(g) for g in groups}
    class_defs, emitted = [], set()

    def constructor(node):
        module_kind = kind(node)
        if module_kind not in BY_KIND:
            raise DraftError(f"源码模块 {module_kind} 必须展开后才能生成。")
        params = node.get("parameters", {})
        return f"nn.{module_kind}({', '.join(f'{key}={value!r}' for key, value in params.items())})"

    def emit_scope(scope, class_name):
        if scope in emitted:
            return
        emitted.add(scope)
        members = children.get(scope, [])
        for child in members:
            if child in groups:
                emit_scope(child, class_names[child])

        incoming = [] if scope is None else boundary(scope, True)
        outgoing = [] if scope is None else boundary(scope, False)
        exported = []
        if scope is not None:
            for edge in edges:
                if kind(nodes[edge["target"]["nodeId"]]) == "Output" and is_inside(edge["target"]["nodeId"], scope) and is_inside(edge["source"]["nodeId"], scope):
                    key = tensor_key(edge["source"])
                    if key not in [(e["source"]["nodeId"], e["source"]["portId"]) for e in outgoing + exported]:
                        exported.append(edge)
        input_keys = []
        for edge in incoming:
            key = tensor_key(edge["source"])
            if key not in input_keys:
                input_keys.append(key)
        input_names = {key: f"arg_{index}" for index, key in enumerate(input_keys)}
        root_inputs = [identity for identity, node in nodes.items() if kind(node) == "Input"] if scope is None else [identity for identity in nodes if kind(nodes[identity]) == "Input" and is_inside(identity, scope) and owner(identity) == scope]
        formal_names = {identity: _name(identity) for identity in root_inputs if scope is None or scope in roots}
        arguments = list(formal_names.values()) + ([] if scope is None else [input_names[key] for key in input_keys])
        values: dict[tuple[str, str], str] = {}
        for identity, name in formal_names.items():
            for port in ports(nodes[identity], "out"):
                values[identity, port["id"]] = name
                values[tensor_key({"nodeId": identity, "portId": port["id"]})] = name
        # A single formal source slot can feed several projected target ports
        # inside the group.  Boundary slot deduplication must not discard those
        # target bindings, otherwise a source view with both a container edge
        # and its descendant edge silently drops the descendant input.
        if scope is not None:
            for edge in crossing_edges(scope, True):
                values[edge["target"]["nodeId"], edge["target"]["portId"]] = input_names[tensor_key(edge["source"])]
                values[tensor_key(edge["source"])] = input_names[tensor_key(edge["source"])]

        init = ["        super().__init__()"]
        constructed: dict[str, str] = {}
        for identity in members:
            node, module_kind = nodes[identity], kind(nodes[identity])
            if identity in groups:
                init.append(f"        self.{_symbol(identity)} = {class_names[identity]}()")
            elif module_kind not in ("Input", "Output") and module_kind not in FUNCTIONAL:
                shared_key = refs.get(identity, {}).get("instanceId", identity)
                if shared_key not in constructed:
                    constructed[shared_key] = _symbol(identity)
                    init.append(f"        self.{_symbol(identity)} = {constructor(node)}")

        pending, order = set(members), []
        dependencies = projected_dependencies(scope)
        while pending:
            ready = sorted(identity for identity in pending if all(target != identity or source not in pending for source, target in dependencies))
            if not ready:
                raise DraftError("分组作用域连接存在环路或未投影的依赖。")
            pending.difference_update(ready); order.extend(ready)

        body = []
        for identity in order:
            node, module_kind = nodes[identity], kind(nodes[identity])
            if module_kind in ("Input", "Output"):
                continue
            for edge in edges:
                if edge["target"]["nodeId"] == identity:
                    source_key = tensor_key(edge["source"])
                    if source_key in values:
                        values[identity, edge["target"]["portId"]] = values[source_key]
            target = _symbol(identity)
            if identity in groups:
                input_keys_for_group = []
                for edge in boundary(identity, True):
                    key = tensor_key(edge["source"])
                    if key not in input_keys_for_group:
                        input_keys_for_group.append(key)
                if identity in roots and refs.get(identity, {}).get("kind") == "Module":
                    enclosed_inputs = [tensor_key({"nodeId": input_id, "portId": ports(nodes[input_id], "out")[0]["id"]}) for input_id in root_inputs if is_inside(input_id, identity)]
                    if enclosed_inputs:
                        input_keys_for_group = enclosed_inputs + input_keys_for_group
                try:
                    call_arguments = [values[key] for key in input_keys_for_group]
                except KeyError as exc:
                    raise DraftError(f"分组输入张量未在父scope生成: group={identity}, missing={exc.args[0]}, available={list(values)}") from exc
                expression = f"self.{_symbol(identity)}({', '.join(call_arguments)})"
                body.append(f"        {target} = {expression}")
                output_keys = []
                for edge in result_edges(identity):
                    key = tensor_key(edge["source"])
                    if key not in output_keys:
                        output_keys.append(key)
                for index, key in enumerate(output_keys):
                    values[key] = target if len(output_keys) == 1 else f"{target}[{index}]"
                continue

            def value_for(name):
                for port in ports(node, "in"):
                    if name in semantic_names(node, port) and (identity, port["id"]) in values:
                        return values[identity, port["id"]]
                raise DraftError(f"{node['label']}.{name} 缺少精确输入张量；ports={[(p.get('name'), p.get('id')) for p in ports(node, 'in')]}; values={list(values)}")

            if module_kind in FUNCTIONAL:
                params = node.get("parameters", {})
                if module_kind in ("Add", "Subtract", "Multiply", "Divide", "MatMul"):
                    op = {"Add": "+", "Subtract": "-", "Multiply": "*", "Divide": "/", "MatMul": "@"}[module_kind]
                    expression = f"{value_for('left')} {op} {value_for('right')}"
                elif module_kind == "Concat":
                    expression = f"torch.cat(({value_for('a')}, {value_for('b')}), dim={params['dim']})"
                elif module_kind in ("Reshape", "Permute", "Unflatten"):
                    parameter = {"Reshape": "shape", "Permute": "dims", "Unflatten": "unflattened_size"}[module_kind]
                    expression = f"{value_for('input')}.{module_kind.lower()}({tuple(params[parameter])!r})"
                elif module_kind == "Transpose":
                    expression = f"{value_for('input')}.transpose({params['dim0']}, {params['dim1']})"
                elif module_kind in ("Unsqueeze", "Squeeze"):
                    expression = f"{value_for('input')}.{module_kind.lower()}({params['dim']})"
                elif module_kind in ("Mean", "Sum"):
                    expression = f"{value_for('input')}.{module_kind.lower()}(dim={params['dim']}, keepdim={params['keepdim']!r})"
                else:
                    raise DraftError(f"未支持函数 {module_kind}")
                body.append(f"        {target} = {expression}")
                values[identity, ports(node, "out")[0]["id"]] = target
                values[tensor_key({"nodeId": identity, "portId": ports(node, "out")[0]["id"]})] = target
                continue

            shared_key = refs.get(identity, {}).get("instanceId", identity)
            reference = f"self.{constructed.get(shared_key, _symbol(identity))}"
            arguments_for_call = []
            for port in ports(node, "in"):
                if (identity, port["id"]) not in values:
                    continue
                for semantic_name in semantic_names(node, port):
                    arguments_for_call.append((semantic_name, values[identity, port["id"]]))
            if module_kind == "MultiheadAttention":
                keyword_args = [f"{name}={value}" for name, value in arguments_for_call if name in {"query", "key", "value", "attn_mask"}]
                need_weights = any("weights" in semantic_names(node, port) for port in ports(node, "out"))
                expression = f"{reference}({', '.join(keyword_args)}, need_weights={need_weights!r})"
            else:
                expression = f"{reference}({', '.join(value for _, value in arguments_for_call)})"
            output_names = [name for port in ports(node, "out") for name in semantic_names(node, port)]
            if module_kind == "LSTM":
                body.append(f"        {target}, ({target}_h_n, {target}_c_n) = {expression}")
            elif module_kind in ("RNN", "GRU"):
                body.append(f"        {target}, {target}_h_n = {expression}")
            elif module_kind == "MultiheadAttention":
                body.append(f"        {target}, {target}_weights = {expression}")
            else:
                body.append(f"        {target} = {expression}")
            for port in ports(node, "out"):
                for name in semantic_names(node, port):
                    values[identity, port["id"]] = target + {"h_n": "_h_n", "c_n": "_c_n", "weights": "_weights"}.get(name, "")
                    values[tensor_key({"nodeId": identity, "portId": port["id"]})] = values[identity, port["id"]]

        if scope is None:
            returns = []
            for node in nodes.values():
                if kind(node) != "Output":
                    continue
                edge = next((edge for edge in edges if edge["target"]["nodeId"] == node["id"]), None)
                if edge is None or tensor_key(edge["source"]) not in values:
                    raise DraftError("根输出没有精确 producer。")
                returns.append(f"{node['id']!r}: {values[tensor_key(edge['source'])]}")
            name, return_text = "AuthoredModel", "{" + ", ".join(returns) + "}"
        else:
            result_values = []
            seen = set()
            for edge in outgoing + exported:
                key = tensor_key(edge["source"])
                if key not in seen:
                    seen.add(key); result_values.append(values[key])
            name = class_name
            return_text = ("(" + ", ".join(result_values) + ("," if len(result_values) == 1 else "") + ")") if len(result_values) > 1 else (result_values[0] if result_values else "None")
        class_defs.append("\n".join([f"class {name}(nn.Module):", "    def __init__(self):", *init, "", f"    def forward(self, {', '.join(arguments)}):", *body, f"        return {return_text}", ""]))

    for group in groups:
        if group not in virtual_roots:
            emit_scope(group, class_names[group])
    emit_scope(None, "AuthoredModel")
    source = "\n".join(['"""Fresh grouped ArchCanvas source; static graph only."""', "import torch", "from torch import nn", "", *class_defs])
    try:
        ast.parse(source)
    except SyntaxError as exc:
        raise DraftError(f"Grouped source syntax is invalid: {exc}") from exc
    with tempfile.TemporaryDirectory(prefix="archcanvas-grouped-source-") as temporary:
        root = Path(temporary); (root / "archcanvas_grouped.py").write_text(source, encoding="utf-8")
        architecture = analyze_project(root, "archcanvas_grouped:AuthoredModel")

    node_bindings, container_bindings = {}, {}
    instance_occurrences: dict[str, int] = {}
    functional_occurrences: dict[tuple[str, str | None], int] = {}
    def constructor_symbol(identity):
        key = refs.get(identity, {}).get("instanceId", identity)
        same_scope = [item["id"] for item in original["nodes"] if refs.get(item["id"], {}).get("instanceId", item["id"]) == key and owner(item["id"]) == owner(identity)]
        return _symbol(same_scope[0] if same_scope else identity)
    def instance_path(identity):
        """Analyzer instance path, including Sequential repeat indices."""
        # A group is represented by the attribute on its owning class.  For a
        # leaf node start at its parent, otherwise the group would be repeated
        # in paths such as AuthoredModel.node_group.node_leaf.
        chain, current = [], identity if identity in groups else parents.get(identity)
        while current is not None:
            parent = parents.get(current)
            if current in groups and current not in virtual_roots:
                chain.append(current)
            current = parent
        chain.reverse()
        segments = []
        for index, group in enumerate(chain):
            segments.append(_symbol(group))
        if identity not in groups:
            segments.append(constructor_symbol(identity))
        return "instance:archcanvas_grouped.AuthoredModel" + "".join("." + item for item in segments)
    for node in original["nodes"]:
        module_kind = kind(node)
        if module_kind == "Output":
            matches = [item for item in architecture["nodes"] if item.get("kind") == "Output" and item.get("outputPath") == [{"kind": "key", "key": node["id"]}]]
        elif module_kind == "Input":
            matches = [item for item in architecture["nodes"] if item.get("kind") == "Input" and item.get("label") == _name(node["id"])]
        elif module_kind in FUNCTIONAL:
            parent_identity = owner(node["id"])
            parent_arch = ({**node_bindings, **container_bindings}.get(parent_identity) if parent_identity else "call:instance:archcanvas_grouped.AuthoredModel")
            key = (module_kind, parent_arch)
            candidates = [item for item in architecture["nodes"] if item.get("kind") == module_kind and item.get("parentId") == parent_arch]
            occurrence = functional_occurrences.get(key, 0); functional_occurrences[key] = occurrence + 1
            matches = [candidates[occurrence]] if occurrence < len(candidates) else []
        else:
            if node["id"] in virtual_roots:
                matches = [item for item in architecture["nodes"] if item.get("id") == "call:instance:archcanvas_grouped.AuthoredModel"]
            else:
                expected = instance_path(node["id"])
                matches = [item for item in architecture["nodes"] if item.get("instanceId") == expected]
                # A shared module may be invoked more than once.  The
                # instance path identifies ownership; the preserved source
                # expression identifies the exact call occurrence.
                occurrence = instance_occurrences.get(expected, 0)
                instance_occurrences[expected] = occurrence + 1
                if len(matches) > 1:
                    matches = [matches[occurrence]] if occurrence < len(matches) else []
        if len(matches) != 1:
            raise DraftError(f"生成源丢失精确节点绑定: {node['id']} expected={locals().get('expected')} candidates={[item.get('instanceId') for item in architecture['nodes'] if item.get('kind') not in ('Input','Output')][:12]}")
        (container_bindings if node["id"] in groups else node_bindings)[node["id"]] = matches[0]["id"]
    all_bindings = {**node_bindings, **container_bindings}
    edge_bindings = {}
    edge_port_bindings = {}
    adjacency = {}
    for item in architecture["edges"]:
        adjacency.setdefault(item["source"]["nodeId"], []).append(item)
    for edge in edges:
        source_id, target_id = all_bindings.get(edge["source"]["nodeId"]), all_bindings.get(edge["target"]["nodeId"])
        matches = [item["id"] for item in architecture["edges"] if item["source"]["nodeId"] == source_id and item["target"]["nodeId"] == target_id]
        if not matches:
            # A leaf relation crossing one or more real group boundaries is
            # represented by the exact projected path through those containers.
            queue = [(source_id, [])]; visited = {source_id}; path = None
            while queue:
                current, current_path = queue.pop(0)
                if current == target_id:
                    path = current_path; break
                for item in adjacency.get(current, []):
                    nxt = item["target"]["nodeId"]
                    if nxt not in visited:
                        visited.add(nxt); queue.append((nxt, current_path + [item["id"]]))
            if path is None:
                raise DraftError(f"生成源丢失精确连线绑定: {edge['id']}")
            matches = path
        edge_bindings[edge["id"]] = matches
        edge_port_bindings[edge["id"]] = {"source": deepcopy(edge["source"]), "target": deepcopy(edge["target"]), "architectureEdges": list(matches), "projected": len(matches) > 1}
    return {"draft": original, "draftDigest": validated["draftDigest"], "entry": "archcanvas_grouped:AuthoredModel", "source": source, "architecture": architecture, "nodeBindings": node_bindings, "containerBindings": container_bindings, "edgeBindings": edge_bindings, "portBindings": edge_port_bindings, "verification": {"status": "passed", "scope": "real-grouped-source-and-static-ir", "modelExecution": "not_run", "limitations": ["Declared tensors are static contracts; source is never executed.", "Unknown source-linked modules must be expanded or replaced with a registered atom before generation."]}}
