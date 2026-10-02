from __future__ import annotations

import ast
import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass, fields, is_dataclass
from enum import Enum
from pathlib import Path
from typing import Any

import libcst as cst
from libcst.metadata import (
    ByteSpanPositionProvider,
    CodeRange,
    CodeSpan,
    FullRepoManager,
    FullyQualifiedNameProvider,
    MetadataWrapper,
    ParentNodeProvider,
    PositionProvider,
    QualifiedName,
    QualifiedNameProvider,
    Scope,
    ScopeProvider,
)

from archcanvas_core.models import SourceSpan
from archcanvas_core.source_v2 import SourceAnchor, SourceCorpus


def module_name_from_logical_path(logical_path: str) -> str:
    path = Path(logical_path)
    parts = list(path.with_suffix("").parts)
    if parts and parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts) or "__init__"


def _semantic_fingerprint(syntax: cst.CSTNode) -> str:
    payload = json.dumps(
        _semantic_cst_payload(syntax),
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


_TRIVIA_TYPES = (
    cst.Comment,
    cst.EmptyLine,
    cst.Newline,
    cst.ParenthesizedWhitespace,
    cst.SimpleWhitespace,
    cst.TrailingWhitespace,
)


def _semantic_cst_payload(value: Any) -> Any:
    """Return a formatting/comment-free structural payload for a CST subtree."""

    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, _TRIVIA_TYPES):
        return None
    if isinstance(value, (cst.LeftParen, cst.RightParen)):
        return None
    if isinstance(value, (tuple, list)):
        return [item for child in value if (item := _semantic_cst_payload(child)) is not None]
    if is_dataclass(value) and isinstance(value, cst.CSTNode):
        result: dict[str, Any] = {"node": type(value).__name__}
        for field in fields(value):
            child = _semantic_cst_payload(getattr(value, field.name))
            if child not in (None, [], {}):
                result[field.name] = child
        return result
    return repr(value)


@dataclass(frozen=True)
class ParsedSourceUnit:
    logical_path: str
    blob_digest: str
    module_name: str
    package_name: str | None
    module: cst.Module
    wrapper: MetadataWrapper
    positions: Mapping[cst.CSTNode, CodeRange]
    byte_spans: Mapping[cst.CSTNode, CodeSpan]
    parents: Mapping[cst.CSTNode, cst.CSTNode]
    scopes: Mapping[cst.CSTNode, Scope]
    qualified_names: Mapping[cst.CSTNode, set[QualifiedName]]
    fully_qualified_names: Mapping[cst.CSTNode, set[QualifiedName]]

    def find_node_for_ast(self, node: ast.AST) -> cst.CSTNode:
        line = getattr(node, "lineno", None)
        column = getattr(node, "col_offset", None)
        end_line = getattr(node, "end_lineno", None)
        candidates = [
            item
            for item, position in self.positions.items()
            if position.start.line == line and position.start.column == column
        ]
        kind_map: dict[type[ast.AST], tuple[type[cst.CSTNode], ...]] = {
            ast.ClassDef: (cst.ClassDef,),
            ast.FunctionDef: (cst.FunctionDef,),
            ast.AsyncFunctionDef: (cst.FunctionDef,),
            ast.Assign: (cst.Assign,),
            ast.AnnAssign: (cst.AnnAssign,),
            ast.BinOp: (cst.BinaryOperation,),
            ast.Call: (cst.Call,),
            ast.Return: (cst.Return,),
            ast.Name: (cst.Name,),
            ast.Attribute: (cst.Attribute,),
        }
        expected = next(
            (types for ast_type, types in kind_map.items() if isinstance(node, ast_type)),
            (),
        )
        typed = [item for item in candidates if not expected or isinstance(item, expected)]
        if typed:
            candidates = typed
        if end_line is not None:
            exact = [item for item in candidates if self.positions[item].end.line == end_line]
            if exact:
                candidates = exact
        if not candidates:
            raise ValueError(
                f"no CST node matches {type(node).__name__} at {self.logical_path}:{line}:{column}"
            )
        return min(
            candidates,
            key=lambda item: (
                self.byte_spans[item].length,
                type(item).__name__,
            ),
        )

    def source_anchor(
        self,
        node: ast.AST | cst.CSTNode,
        *,
        qualified_symbol: str,
        semantic_role: str,
    ) -> SourceAnchor:
        cst_node = self.find_node_for_ast(node) if isinstance(node, ast.AST) else node
        position = self.positions[cst_node]
        byte_span = self.byte_spans[cst_node]
        parent = self.parents.get(cst_node)
        parent_fingerprint: str | None = None
        if parent is not None:
            parent_fingerprint = _semantic_fingerprint(parent)
        return SourceAnchor(
            logical_path=self.logical_path,
            blob_digest=self.blob_digest,
            byte_start=byte_span.start,
            byte_length=byte_span.length,
            line_span=SourceSpan(
                start_line=position.start.line,
                end_line=position.end.line,
                start_column=position.start.column,
                end_column=position.end.column,
            ),
            qualified_symbol=qualified_symbol,
            cst_node_kind=type(cst_node).__name__,
            semantic_role=semantic_role,
            subtree_fingerprint=_semantic_fingerprint(cst_node),
            parent_fingerprint=parent_fingerprint,
        )


@dataclass(frozen=True)
class ParsedRepository:
    root: Path
    units: dict[str, ParsedSourceUnit]

    def by_module_name(self, module_name: str) -> ParsedSourceUnit | None:
        return next((item for item in self.units.values() if item.module_name == module_name), None)


def parse_frozen_corpus(corpus: SourceCorpus, snapshot_root: Path) -> ParsedRepository:
    root = snapshot_root.resolve()
    paths = [
        item.logical_path
        for item in corpus.files
        if item.file_kind in {"python", "stub"}
    ]
    providers = {
        PositionProvider,
        ByteSpanPositionProvider,
        ParentNodeProvider,
        ScopeProvider,
        QualifiedNameProvider,
        FullyQualifiedNameProvider,
    }
    manager_paths = [str(root / path) for path in paths]
    manager = FullRepoManager(root, manager_paths, providers, use_pyproject_toml=False)
    manager.resolve_cache()
    source_by_path = {item.logical_path: item for item in corpus.files}
    units: dict[str, ParsedSourceUnit] = {}
    for path in sorted(paths):
        wrapper = manager.get_metadata_wrapper_for_path(str(root / path))
        module_name = module_name_from_logical_path(path)
        package_name = module_name.rpartition(".")[0] or None
        units[path] = ParsedSourceUnit(
            logical_path=path,
            blob_digest=source_by_path[path].sha256,
            module_name=module_name,
            package_name=package_name,
            module=wrapper.module,
            wrapper=wrapper,
            positions=wrapper.resolve(PositionProvider),
            byte_spans=wrapper.resolve(ByteSpanPositionProvider),
            parents=wrapper.resolve(ParentNodeProvider),
            scopes=wrapper.resolve(ScopeProvider),
            qualified_names=wrapper.resolve(QualifiedNameProvider),
            fully_qualified_names=wrapper.resolve(FullyQualifiedNameProvider),
        )
    return ParsedRepository(root=root, units=units)
