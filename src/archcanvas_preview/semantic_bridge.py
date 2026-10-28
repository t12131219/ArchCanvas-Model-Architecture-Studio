"""Bridge Summary_Merge semantic IR into the portable recursive preview bundle.

The Summary semantic adapter is deliberately kept as a separate package.  This
module only performs bounded file staging, static AST analysis, path remapping,
and a lossless presentation projection.  It never imports or executes supplied
model code.  The complete ``archcanvas-source-semantic/2`` document is retained
under ``ir.semantic_ir`` so Studio panels can inspect contracts, motifs,
coverage, and opaque boundaries while the browser consumes its stable
``summary-source-ir/1`` projection.
"""
from __future__ import annotations

import copy
import ast
import hashlib
import json
import tempfile
from pathlib import Path
from typing import Any

from archcanvas_summary_semantic import analyze as summary_analyze
from archcanvas_summary_semantic.schema import seal, validate_ir
from archcanvas_summary_semantic.contracts import recognize_contracts

from .analyze import AdapterError, canonical, files_checked, sha


MAX_SEMANTIC_NODES = 480
MAX_SEMANTIC_EDGES = 3600


def _remap(value: Any, root: str) -> Any:
    """Remove ephemeral staging paths, including paths embedded in identities.

    Keep the native semantic schema unchanged (notably end_line/end_column).
    Camel-case spans belong only to the portable presentation evidence map.
    """
    if isinstance(value, list):
        return [_remap(item, root) for item in value]
    if isinstance(value, dict):
        return {_remap(key, root): _remap(item, root) for key, item in value.items()}
    if isinstance(value, str):
        return "." if value == root else value.replace(root + "/", "")
    return value


def _entry_for_summary(entry: str | None, files: dict[str, str]) -> tuple[str, str]:
    if entry is not None and (not isinstance(entry, str) or not entry.strip()):
        raise AdapterError("模型入口必须是非空字符串。")
    matches = []
    for path, text in sorted(files.items()):
        try:
            tree = ast.parse(text, filename=path)
        except (SyntaxError, RecursionError) as exc:
            raise AdapterError(f"{path}: Python 语法无法解析: {exc}") from exc
        module = path[:-3].replace("/", ".")
        module = "" if module == "__init__" else module.removesuffix(".__init__")
        for node in tree.body:
            if not isinstance(node, ast.ClassDef):
                continue
            key = module + ":" + node.name
            if entry in (key, node.name) or (entry is None and any(
                    isinstance(method, ast.FunctionDef) and method.name in {"forward", "__call__"} for method in node.body)):
                matches.append((path, key))
    if len(matches) != 1:
        raise AdapterError("请指定唯一模型入口 module:Class。候选：" + ", ".join(key for _, key in matches))
    return matches[0]


def _source_expression(files: dict[str, str], span: dict[str, Any]) -> str:
    text = files.get(span.get("file", ""), "")
    lines = text.split("\n")
    first = max(0, int(span.get("line", 1)) - 1)
    last = max(first, int(span.get("end_line", span.get("endLine", span.get("line", 1)))) - 1)
    column = int(span.get("column", 0))
    end_column = int(span.get("end_column", span.get("endColumn", column)))
    encoded = [line.encode("utf-8") for line in lines[first : last + 1]]
    if not encoded:
        return ""
    chunks = [encoded[0][column:]]
    if last > first:
        chunks = [encoded[0][column:]] + encoded[1:-1] + [encoded[-1][:end_column]]
    else:
        chunks = [encoded[0][column:end_column]]
    return b"\n".join(chunks).decode("utf-8", errors="replace")


def _evidence_map(semantic: dict[str, Any], files: dict[str, str]) -> tuple[dict[str, dict[str, Any]], dict[str, list[str]]]:
    evidence: dict[str, dict[str, Any]] = {}
    node_evidence: dict[str, list[str]] = {}
    for node in semantic.get("nodes", []):
        refs: list[str] = []
        for span in node.get("source", []):
            data = {
                "file": span["file"],
                "line": span["line"],
                "endLine": span.get("endLine", span.get("end_line", span.get("line"))),
                "column": span.get("column", 0),
                "endColumn": span.get("endColumn", span.get("end_column", span.get("column", 0))),
                "expression": _source_expression(files, span),
            }
            key = "e-" + hashlib.sha256(canonical(data).encode("utf-8")).hexdigest()[:16]
            evidence[key] = data
            refs.append(key)
        if refs:
            node_evidence[node["id"]] = refs
    return evidence, node_evidence


def _presentation_kind(node: dict[str, Any]) -> str:
    kind = node.get("kind")
    if kind == "compute":
        # The Summary renderer has dedicated binary glyphs for these operators.
        operator = str(node.get("operator") or "compute")
        return "multiply" if operator == "mult" else operator
    if kind == "interface":
        return {"output": "output", "input": "input"}.get(node.get("role"), "interface")
    if kind == "composite":
        return "group"
    return str(kind or "opaque")


def _to_bundle(semantic: dict[str, Any], files: dict[str, str], entry: str, config: dict) -> dict[str, Any]:
    if semantic.get("schema") != "archcanvas-source-semantic/2":
        raise AdapterError("Summary 语义适配器返回了不支持的 schema。")
    validation = validate_ir(semantic)
    if not validation["ok"]:
        errors = "; ".join(validation["errors"][:3])
        raise AdapterError("Summary 语义 IR 校验失败：" + errors)
    if len(semantic.get("nodes", [])) > MAX_SEMANTIC_NODES:
        raise AdapterError(f"Summary 语义节点超过 {MAX_SEMANTIC_NODES} 个。")
    if len(semantic.get("edges", [])) > MAX_SEMANTIC_EDGES:
        raise AdapterError(f"Summary 语义边超过 {MAX_SEMANTIC_EDGES} 条。")

    evidence, node_evidence = _evidence_map(semantic, files)
    nodes: list[dict[str, Any]] = []
    for raw in semantic["nodes"]:
        refs = node_evidence.get(raw["id"], [])
        if not refs:
            raise AdapterError("Summary 语义节点缺少可定位的源码证据：" + raw["id"])
        node = {
            "id": raw["id"],
            "parent": raw.get("parent"),
            "kind": _presentation_kind(raw),
            "label": raw.get("label", raw["id"]),
            "source_evidence": refs,
            "expression": evidence[refs[0]]["expression"],
            "sourceKind": "SummarySemantic",
            "semantic_kind": raw.get("kind"),
            "evidence_status": raw.get("evidence_status", "opaque"),
            "semantic": copy.deepcopy(raw),
        }
        if raw.get("module_path") is not None:
            node["instance"] = entry + ("." + raw["module_path"] if raw["module_path"] else "")
        if raw.get("kind") == "composite":
            node["sourceStructure"] = True
        if raw.get("constructor") is not None:
            node["sourceParameters"] = {"constructor": copy.deepcopy(raw["constructor"])}
        nodes.append(node)

    by_id = {node["id"]: node for node in nodes}
    edges: list[dict[str, Any]] = []
    for index, raw in enumerate(semantic.get("edges", []), 1):
        refs = node_evidence.get(raw["target"], node_evidence.get(raw["source"], []))
        target_port = str(raw.get("target_port", "in"))
        source_port = str(raw.get("source_port", "out"))
        role = "shape_dependency" if by_id[raw["source"]]["kind"] == "shape" else "source_dependency"
        edges.append({
            "id": str(raw.get("id") or f"edge-{index}"),
            "source": raw["source"], "target": raw["target"],
            "sourcePort": source_port, "targetPort": target_port,
            "wire": raw["source"] + ":" + source_port, "role": role,
            "source_evidence": refs,
            "semantic": copy.deepcopy(raw),
        })

    manifest = [{"path": path, "sha256": sha(text), "text": text} for path, text in sorted(files.items())]
    source_digest = sha(canonical([{key: value for key, value in item.items() if key != "text"} for item in manifest]))
    portable_entry = entry if isinstance(entry, str) and entry else str(semantic.get("entry", {}).get("class", "Model"))
    projected_ir: dict[str, Any] = {
        "schema": "summary-source-ir/1",
        "entry": portable_entry,
        "nodes": nodes,
        "edges": edges,
        # Keep the portable wire contract stable; the richer semantic layer is
        # identified separately so older browser validators remain valid.
        "analysis": "static-source-dependencies",
        "semanticAnalysis": "summary-static-source-semantic",
        "modelExecuted": False,
        "shapePolicy": "Summary semantic adapter does not infer tensor dimensions without runtime evidence",
        "semanticSchema": semantic["schema"],
        "semantic_ir": semantic,
        "canonicalSemanticIR": canonical({key: value for key, value in semantic.items() if key != "ir_digest"}),
    }
    serial = canonical(projected_ir)
    diagnostics = [dict(item, message=item.get("message") or item.get("reason") or item.get("kind", "未解析边界"))
                   for item in [*semantic.get("diagnostics", []), *semantic.get("coverage_blockers", [])]]
    diagnostics.extend({"node": node["id"], "message": node.get("reason", "opaque 源码边界")}
                       for node in semantic["nodes"] if node["kind"] == "opaque")
    normalized_entry = semantic.get("entry", entry or "Model")
    title = normalized_entry.get("class", str(normalized_entry).split(":")[-1]) if isinstance(normalized_entry, dict) else str(normalized_entry).split(":")[-1]
    return {
        "schema": "summary-source-adapter/1",
        "id": "source-" + sha(title + source_digest + serial)[:16],
        "title": title,
        "entry": projected_ir["entry"],
        "files": manifest,
        "sourceSha256": source_digest,
        "ir": projected_ir,
        "canonicalIR": serial,
        "irSha256": sha(serial),
        "evidence": evidence,
        "diagnostics": diagnostics,
        "config": copy.deepcopy(config),
        "semanticMode": "summary",
        "adapterVersion": 1,
        "semantic": {
            "schema": semantic["schema"],
            "irDigest": semantic.get("ir_digest"),
            "coverage": copy.deepcopy(semantic.get("coverage")),
            "motifs": copy.deepcopy(semantic.get("motifs", [])),
            "semanticContracts": copy.deepcopy(semantic.get("semantic_contracts", [])),
            "runtime": copy.deepcopy(semantic.get("runtime", {})),
            "modelExecuted": False,
        },
    }


def analyze_summary(files: dict[str, str], entry: str | None, config: dict[str, Any] | None = None) -> dict[str, Any]:
    checked = files_checked(files)
    if config is not None and not isinstance(config, dict):
        raise AdapterError("构造参数必须是 JSON 对象。")
    config = {} if config is None else copy.deepcopy(config)
    try:
        json.dumps(config, allow_nan=False)
    except (TypeError, ValueError, RecursionError) as exc:
        raise AdapterError("构造参数必须是有限的 JSON 字面量。") from exc
    source_file, entry_name = _entry_for_summary(entry, checked)
    with tempfile.TemporaryDirectory(prefix="archcanvas-summary-semantic-") as temporary:
        root = Path(temporary).resolve()
        for logical, text in checked.items():
            path = root / logical
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        source_path = root / source_file
        try:
            semantic = summary_analyze(source_path, entry_name, constructor=config, project_root=root,
                                       max_nodes=MAX_SEMANTIC_NODES, max_edges=MAX_SEMANTIC_EDGES, max_depth=10)
        except (OSError, ValueError, KeyError, TypeError, RecursionError) as exc:
            raise AdapterError("Summary 静态语义分析失败：" + str(exc)) from exc
        semantic = _remap(semantic, str(root))
        # Staging paths are intentionally replaced by logical source paths so
        # browser evidence can navigate the submitted corpus.  Re-seal after
        # this deterministic transport rewrite.
        # Certificates bind the graph including source identities. Re-derive
        # them after relocation rather than just replacing their basis hash.
        semantic.pop("semantic_contracts", None)
        semantic.pop("semantic_contract_basis", None)
        recognize_contracts(semantic)
        semantic = seal(semantic)
        return _to_bundle(semantic, checked, entry_name, config)
