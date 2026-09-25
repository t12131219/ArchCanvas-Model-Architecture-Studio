from __future__ import annotations

import ast
from collections import defaultdict
from pathlib import Path
from typing import Any

from archcanvas_core.models import (
    ArchitectureIR,
    EvidenceRecord,
    PublicationHierarchy,
    SourceSnapshot,
)

PROJECTIONS = ("module", "source")


def _span(node: ast.AST) -> dict[str, int] | None:
    start = getattr(node, "lineno", None)
    end = getattr(node, "end_lineno", start)
    if not isinstance(start, int) or not isinstance(end, int):
        return None
    return {
        "start_line": start,
        "end_line": end,
        "start_column": int(getattr(node, "col_offset", 0)),
        "end_column": int(getattr(node, "end_col_offset", 0)),
    }


def _source_evidence(
    evidence: list[EvidenceRecord],
) -> tuple[dict[str, set[str]], dict[tuple[str, str], set[str]]]:
    by_path_line: dict[str, set[str]] = defaultdict(set)
    by_symbol: dict[tuple[str, str], set[str]] = defaultdict(set)
    for record in evidence:
        if record.kind.value != "source" or not record.path or not record.span:
            continue
        by_path_line[f"{record.path}:{record.span.start_line}"].add(record.evidence_id)
        by_symbol[(record.path, record.symbol or "")].add(record.evidence_id)
    return by_path_line, by_symbol


def _canonical_by_evidence(
    architecture: ArchitectureIR,
) -> dict[str, set[str]]:
    result: dict[str, set[str]] = defaultdict(set)
    for node in architecture.nodes:
        for evidence_id in node.evidence_ids:
            result[evidence_id].add(node.node_id)
    for tensor in architecture.tensors:
        for evidence_id in tensor.evidence_ids:
            result[evidence_id].add(tensor.tensor_id)
    for edge in architecture.edges:
        for evidence_id in edge.evidence_ids:
            result[evidence_id].add(edge.edge_id)
    return result


def _row(
    row_id: str,
    parent_id: str | None,
    kind: str,
    label: str,
    *,
    depth: int,
    relation: str,
    canonical_ids: set[str] | list[str] = (),
    evidence_ids: set[str] | list[str] = (),
    path: str | None = None,
    span: dict[str, int] | None = None,
    reference: bool = False,
    secondary_label: str | None = None,
    binding_status: str = "unbound",
) -> dict[str, Any]:
    return {
        "id": row_id,
        "parent_id": parent_id,
        "kind": kind,
        "label": label,
        "depth": depth,
        "relation": relation,
        "canonical_ids": sorted(set(canonical_ids)),
        "evidence_ids": sorted(set(evidence_ids)),
        "path": path,
        "span": span,
        "reference": reference,
        "secondary_label": secondary_label,
        "binding_status": binding_status,
        "child_count": 0,
        "sibling_index": 1,
        "sibling_count": 1,
    }


def _call_binding(
    child: ast.Call,
    candidate_ids: set[str],
    architecture: ArchitectureIR,
) -> tuple[set[str], str]:
    candidate_nodes = [
        node for node in architecture.nodes if node.node_id in candidate_ids
    ]
    if not candidate_nodes:
        return set(), "unbound"

    expression = ast.unparse(child)
    callee = ast.unparse(child.func)
    matchers = (
        lambda node: node.attributes.get("source_expression") == expression,
        lambda node: node.attributes.get("module_path") == callee,
        lambda node: node.attributes.get("op_type") == callee,
    )
    for matches in (
        [node.node_id for node in candidate_nodes if matcher(node)]
        for matcher in matchers
    ):
        if matches:
            return set(matches), "exact" if len(matches) == 1 else "ambiguous"
    return {node.node_id for node in candidate_nodes}, "ambiguous"


def _binding_parts(
    node: ast.Assign | ast.AnnAssign | ast.AugAssign | ast.NamedExpr,
) -> tuple[list[str], ast.AST]:
    if isinstance(node, ast.Assign):
        targets = [ast.unparse(target) for target in node.targets]
        return targets, node.value
    target = ast.unparse(node.target)
    return [target], node.value


def _statement_binding(
    child: ast.Assign | ast.AnnAssign | ast.AugAssign | ast.NamedExpr,
    candidate_ids: set[str],
    architecture: ArchitectureIR,
) -> tuple[set[str], str]:
    targets, value = _binding_parts(child)
    target_names = {*targets, *(target.rsplit(".", 1)[-1] for target in targets)}
    expression = ast.unparse(value)
    candidate_nodes = [
        node for node in architecture.nodes if node.node_id in candidate_ids
    ]
    if not candidate_nodes:
        return set(), "unbound"

    def target_matches(node: Any) -> bool:
        return (
            node.attributes.get("assigned_symbol") in target_names
            or node.attributes.get("module_path") in target_names
        )

    matchers = (
        lambda node: target_matches(node)
        and node.attributes.get("source_expression") == expression,
        lambda node: node.attributes.get("source_expression") == expression,
        target_matches,
    )
    for matches in (
        [node.node_id for node in candidate_nodes if matcher(node)]
        for matcher in matchers
    ):
        if matches:
            return set(matches), "exact" if len(matches) == 1 else "ambiguous"
    candidate_node_ids = {node.node_id for node in candidate_nodes}
    return (
        candidate_node_ids,
        "exact" if len(candidate_node_ids) == 1 else "ambiguous",
    )


def _return_binding(
    candidate_ids: set[str], architecture: ArchitectureIR
) -> tuple[set[str], str]:
    candidate_nodes = [
        node for node in architecture.nodes if node.node_id in candidate_ids
    ]
    output_nodes = [
        node.node_id
        for node in candidate_nodes
        if node.attributes.get("io") == "output"
    ]
    matches = output_nodes or [node.node_id for node in candidate_nodes]
    if not matches:
        return set(), "unbound"
    return set(matches), "exact" if len(matches) == 1 else "ambiguous"


def _module_projection(
    architecture: ArchitectureIR,
    hierarchy: PublicationHierarchy,
) -> list[dict[str, Any]]:
    children: dict[str, list[str]] = defaultdict(list)
    by_id = {node.hierarchy_node_id: node for node in hierarchy.nodes}
    for node in hierarchy.nodes:
        if node.parent_hierarchy_node_id is not None:
            children[node.parent_hierarchy_node_id].append(node.hierarchy_node_id)

    descendants: dict[str, list[str]] = {}
    hierarchy_order = {
        node.hierarchy_node_id: index for index, node in enumerate(hierarchy.nodes)
    }

    def semantic_order(node_id: str) -> tuple[int, int]:
        name = by_id[node_id].semantic_name.lower()
        stage = next(
            (
                rank
                for rank, tokens in enumerate(
                    (
                        ("input", "source", "covariate"),
                        ("decomp", "seasonal", "trend", "state"),
                        ("encoder", "backbone"),
                        ("decoder",),
                        ("ffn", "feed", "mlp"),
                        ("output", "forecast", "prediction", "head"),
                    )
                )
                if any(token in name for token in tokens)
            ),
            6,
        )
        return stage, hierarchy_order[node_id]

    for members in children.values():
        members.sort(key=semantic_order)

    def canonical_descendants(node_id: str) -> list[str]:
        if node_id not in descendants:
            node = by_id[node_id]
            descendants[node_id] = list(
                dict.fromkeys(
                    [
                        *node.canonical_node_ids,
                        *[
                            canonical_id
                            for child_id in children.get(node_id, [])
                            for canonical_id in canonical_descendants(child_id)
                        ],
                    ]
                )
            )
        return descendants[node_id]

    rows: list[dict[str, Any]] = []

    def append_preorder(node_id: str) -> None:
        node = by_id[node_id]
        canonical_ids = canonical_descendants(node.hierarchy_node_id)
        rows.append(
            _row(
                node.hierarchy_node_id,
                node.parent_hierarchy_node_id,
                "module" if children.get(node.hierarchy_node_id) else "operator",
                node.semantic_name,
                depth=node.depth,
                relation="module-containment",
                canonical_ids=canonical_ids,
                evidence_ids=node.evidence_ids,
                path=str(node.attributes.get("source_node_id") or "") or None,
                secondary_label=(
                    f"包含 {len(canonical_ids)} 个执行对象"
                    if children.get(node.hierarchy_node_id)
                    else str(node.attributes.get("source_node_id") or "") or None
                ),
            )
        )
        for child_id in children.get(node_id, []):
            append_preorder(child_id)

    append_preorder(hierarchy.root_node_id)
    return rows


def _qualified_name(node: ast.AST, parents: list[str]) -> str:
    name = getattr(node, "name", "")
    return ".".join([*parents, name]) if name else ".".join(parents)


def _source_projection(
    architecture: ArchitectureIR,
    snapshot: SourceSnapshot,
    evidence: list[EvidenceRecord],
) -> list[dict[str, Any]]:
    by_path_line, by_symbol = _source_evidence(evidence)
    canonical_by_evidence = _canonical_by_evidence(architecture)
    rows: list[dict[str, Any]] = [
        _row(
            "source:root",
            None,
            "repository",
            Path(snapshot.project_root).name or snapshot.project_root,
            depth=0,
            relation="source-containment",
        )
    ]
    directory_ids: dict[tuple[str, ...], str] = {(): "source:root"}
    for source in sorted(snapshot.source_files, key=lambda item: item.path):
        path = Path(source.path)
        parts = path.parts
        parent_id = "source:root"
        for index, part in enumerate(parts[:-1], 1):
            key = parts[:index]
            directory_id = directory_ids.get(key)
            if directory_id is None:
                directory_id = f"source:dir:{'/'.join(key)}"
                directory_ids[key] = directory_id
                rows.append(
                    _row(
                        directory_id,
                        parent_id,
                        "directory",
                        part,
                        depth=index,
                        relation="source-containment",
                        path="/".join(key),
                    )
                )
            parent_id = directory_id
        file_id = f"source:file:{source.path}"
        rows.append(
            _row(
                file_id,
                parent_id,
                "file",
                parts[-1],
                depth=len(parts),
                relation="source-containment",
                path=source.path,
                secondary_label=source.path,
            )
        )
        source_path = source.path
        file_path = Path(snapshot.project_root) / source_path
        try:
            tree = ast.parse(file_path.read_text(encoding="utf-8"), filename=source_path)
        except (OSError, SyntaxError, UnicodeDecodeError):
            continue

        def visit(
            node: ast.AST,
            owner_id: str,
            owner_depth: int,
            parents: list[str],
            current_path: str = source.path,
        ) -> None:
            for child in ast.iter_child_nodes(node):
                if isinstance(child, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                    qualified = _qualified_name(child, parents)
                    child_id = f"source:def:{current_path}:{child.lineno}:{qualified}"
                    evidence_ids = set(by_symbol.get((current_path, qualified), set()))
                    line_evidence = by_path_line.get(f"{current_path}:{child.lineno}", set())
                    evidence_ids.update(line_evidence)
                    canonical_ids = {
                        canonical
                        for evidence_id in evidence_ids
                        for canonical in canonical_by_evidence.get(evidence_id, set())
                    }
                    rows.append(
                        _row(
                            child_id,
                            owner_id,
                            "class" if isinstance(child, ast.ClassDef) else "function",
                            child.name,
                            depth=owner_depth + 1,
                            relation="source-containment",
                            canonical_ids=canonical_ids,
                            evidence_ids=evidence_ids,
                            path=current_path,
                            span=_span(child),
                            secondary_label=(
                                f"{current_path}:{child.lineno}:"
                                f"{getattr(child, 'col_offset', 0) + 1}"
                            ),
                        )
                    )
                    visit(child, child_id, owner_depth + 1, [*parents, child.name])
                    continue
                if isinstance(child, (ast.If, ast.For, ast.AsyncFor, ast.While, ast.With, ast.AsyncWith)):
                    line = getattr(child, "lineno", 0)
                    scope_name = {
                        ast.If: "if",
                        ast.For: "for",
                        ast.AsyncFor: "async for",
                        ast.While: "while",
                        ast.With: "with",
                        ast.AsyncWith: "async with",
                    }[type(child)]
                    scope_id = (
                        f"source:scope:{current_path}:{line}:"
                        f"{getattr(child, 'col_offset', 0)}:{scope_name}"
                    )
                    evidence_ids = by_path_line.get(f"{current_path}:{line}", set())
                    rows.append(
                        _row(
                            scope_id,
                            owner_id,
                            "control-scope",
                            f"{scope_name} scope",
                            depth=owner_depth + 1,
                            relation="source-containment",
                            evidence_ids=evidence_ids,
                            path=current_path,
                            span=_span(child),
                            secondary_label=(
                                f"{current_path}:{line}:"
                                f"{getattr(child, 'col_offset', 0) + 1}"
                            ),
                        )
                    )
                    visit(child, scope_id, owner_depth + 1, parents)
                    continue
                if isinstance(child, (ast.Assign, ast.AnnAssign, ast.AugAssign, ast.NamedExpr)):
                    line = getattr(child, "lineno", 0)
                    column = getattr(child, "col_offset", 0)
                    evidence_ids = by_path_line.get(f"{current_path}:{line}", set())
                    candidate_ids = {
                        canonical
                        for evidence_id in evidence_ids
                        for canonical in canonical_by_evidence.get(evidence_id, set())
                    }
                    targets, _ = _binding_parts(child)
                    canonical_ids, binding_status = _statement_binding(
                        child, candidate_ids, architecture
                    )
                    binding_id = (
                        f"source:binding:{current_path}:{line}:{column}:"
                        f"{getattr(child, 'end_lineno', line)}:"
                        f"{getattr(child, 'end_col_offset', column)}"
                    )
                    rows.append(
                        _row(
                            binding_id,
                            owner_id,
                            "binding",
                            ", ".join(targets),
                            depth=owner_depth + 1,
                            relation="assignment",
                            canonical_ids=canonical_ids,
                            evidence_ids=evidence_ids,
                            path=current_path,
                            span=_span(child),
                            secondary_label=f"{current_path}:{line}:{column + 1}",
                            binding_status=binding_status,
                        )
                    )
                    visit(child, binding_id, owner_depth + 1, parents)
                    continue
                if isinstance(child, ast.Return):
                    line = getattr(child, "lineno", 0)
                    column = getattr(child, "col_offset", 0)
                    evidence_ids = by_path_line.get(f"{current_path}:{line}", set())
                    candidate_ids = {
                        canonical
                        for evidence_id in evidence_ids
                        for canonical in canonical_by_evidence.get(evidence_id, set())
                    }
                    canonical_ids, binding_status = _return_binding(
                        candidate_ids, architecture
                    )
                    return_id = (
                        f"source:return:{current_path}:{line}:{column}:"
                        f"{getattr(child, 'end_lineno', line)}:"
                        f"{getattr(child, 'end_col_offset', column)}"
                    )
                    value_label = ast.unparse(child.value) if child.value is not None else ""
                    rows.append(
                        _row(
                            return_id,
                            owner_id,
                            "return",
                            f"return {value_label}".rstrip(),
                            depth=owner_depth + 1,
                            relation="return",
                            canonical_ids=canonical_ids,
                            evidence_ids=evidence_ids,
                            path=current_path,
                            span=_span(child),
                            secondary_label=f"{current_path}:{line}:{column + 1}",
                            binding_status=binding_status,
                        )
                    )
                    visit(child, return_id, owner_depth + 1, parents)
                    continue
                elif isinstance(child, ast.Call):
                    line = getattr(child, "lineno", 0)
                    evidence_ids = by_path_line.get(f"{current_path}:{line}", set())
                    candidate_ids = {
                        canonical
                        for evidence_id in evidence_ids
                        for canonical in canonical_by_evidence.get(evidence_id, set())
                    }
                    callee = ast.unparse(child.func)
                    canonical_ids, binding_status = _call_binding(
                        child, candidate_ids, architecture
                    )
                    call_id = (
                        f"source:call:{current_path}:{line}:"
                        f"{getattr(child, 'col_offset', 0)}:"
                        f"{getattr(child, 'end_lineno', line)}:"
                        f"{getattr(child, 'end_col_offset', 0)}"
                    )
                    rows.append(
                        _row(
                            call_id,
                            owner_id,
                            "callsite",
                            f"call {callee}",
                            depth=owner_depth + 1,
                            relation="invocation",
                            canonical_ids=canonical_ids,
                            evidence_ids=evidence_ids,
                            path=current_path,
                            span=_span(child),
                            reference=True,
                            secondary_label=(
                                f"{current_path}:{line}:"
                                f"{getattr(child, 'col_offset', 0) + 1}"
                            ),
                            binding_status=binding_status,
                        )
                    )
                    visit(child, call_id, owner_depth + 1, parents)
                    mapped_nodes = {
                        canonical_id
                        for canonical_id in canonical_ids
                        if canonical_id.startswith("node:")
                    }
                    for tensor in architecture.tensors:
                        if tensor.producer_id in mapped_nodes:
                            rows.append(
                                _row(
                                    f"source:output:{call_id}:{tensor.tensor_id}",
                                    call_id,
                                    "tensor",
                                    tensor.role,
                                    depth=owner_depth + 2,
                                    relation="producer-output",
                                    canonical_ids=[tensor.tensor_id, tensor.producer_id],
                                    evidence_ids=tensor.evidence_ids,
                                    path=current_path,
                                    secondary_label=tensor.symbolic_shape,
                                )
                            )
                        consumers = sorted(set(tensor.consumer_ids).intersection(mapped_nodes))
                        for consumer_id in consumers:
                            rows.append(
                                _row(
                                    f"source:input:{call_id}:{tensor.tensor_id}:{consumer_id}",
                                    call_id,
                                    "tensor-reference",
                                    f"input {tensor.role}",
                                    depth=owner_depth + 2,
                                    relation="consumer-reference",
                                    canonical_ids=[tensor.tensor_id, consumer_id],
                                    evidence_ids=tensor.evidence_ids,
                                    path=current_path,
                                    reference=True,
                                    secondary_label=tensor.symbolic_shape,
                                )
                            )
                    continue
                visit(child, owner_id, owner_depth, parents)

        visit(tree, file_id, len(parts), [])
    return rows


def build_navigation_projections(
    architecture: ArchitectureIR,
    snapshot: SourceSnapshot,
    evidence: list[EvidenceRecord],
    hierarchy: PublicationHierarchy,
) -> dict[str, Any]:
    module_rows = _module_projection(architecture, hierarchy)
    source_rows = _source_projection(architecture, snapshot, evidence)
    for rows in (module_rows, source_rows):
        child_counts: dict[str, int] = defaultdict(int)
        children: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in rows:
            if row["parent_id"] is not None:
                child_counts[row["parent_id"]] += 1
                children[row["parent_id"]].append(row)
        for row in rows:
            row["child_count"] = child_counts[row["id"]]
        for siblings in children.values():
            sibling_count = len(siblings)
            for index, row in enumerate(siblings, 1):
                row["sibling_index"] = index
                row["sibling_count"] = sibling_count
    return {
        "active_projection": "module",
        "projections": {
            "module": {
                "projection_id": "module",
                "label": "模块关系",
                "description": "Exact IR 与语义标注的包含关系",
                "nodes": module_rows,
            },
            "source": {
                "projection_id": "source",
                "label": "源码关系",
                "description": "文件 / 作用域 / 语句 / 表达式逐级包含；引用关系来自 Exact IR",
                "nodes": source_rows,
            },
        },
    }
