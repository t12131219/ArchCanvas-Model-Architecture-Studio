"""Candidate-first planning for the restricted Stage 8 LayerNorm splice."""

from __future__ import annotations

from difflib import unified_diff

import libcst as cst

from archcanvas_core.graph_delta import GraphDeltaValidator, architecture_diff
from archcanvas_core.models.architecture import ArchitectureIR
from archcanvas_core.models.patch import InsertLayerNormPatch, PatchSet
from archcanvas_core.models.source_identity import SourceIdentityDocument

from ..analyzers import Analyzer
from ..transforms.insert_layer_norm import apply_insert_layer_norm
from .set_parameter import CandidateTransaction, TransactionRejected, _assert_semantics


def _two_hunk_diff(before: bytes, after: bytes, relative_file: str) -> str:
    try:
        before_lines = before.decode("utf-8").splitlines(keepends=True)
        after_lines = after.decode("utf-8").splitlines(keepends=True)
    except UnicodeDecodeError as error:
        raise TransactionRejected("SOURCE_NOT_UTF8", relative_file) from error
    diff = "".join(
        unified_diff(before_lines, after_lines, fromfile=f"a/{relative_file}", tofile=f"b/{relative_file}")
    )
    if sum(line.startswith("@@ ") for line in diff.splitlines()) != 2:
        raise TransactionRejected("TEXTUAL_HUNK_CARDINALITY", "insert_layer_norm requires exactly two diff hunks")
    return diff


def plan_insert_layer_norm(
    raw_source: bytes,
    patch_set: PatchSet,
    source: SourceIdentityDocument,
    ir: ArchitectureIR,
    *,
    analyzer: Analyzer,
) -> CandidateTransaction:
    if len(patch_set.patches) != 1 or not isinstance(patch_set.patches[0], InsertLayerNormPatch):
        raise TransactionRejected("PATCH_OPERATION_MISMATCH", "expected one insert_layer_norm patch")
    if patch_set.project_id != source.project_id or patch_set.project_id != ir.project_id:
        raise TransactionRejected("PROJECT_ID_MISMATCH", patch_set.project_id)
    _assert_semantics(ir, source, "BEFORE")
    patch = patch_set.patches[0]
    try:
        source_node = ir.node(patch.source_node_id)
        target_node = ir.node(patch.target_node_id)
        constructor = next(anchor for anchor in source.anchors if anchor.anchor_id == patch.constructor_anchor_id)
        forward = next(anchor for anchor in source.anchors if anchor.anchor_id == patch.forward_anchor_id)
    except StopIteration as error:
        raise TransactionRejected("PATCH_TARGET_NOT_FOUND", str(error)) from error
    if patch_set.base_source_revision != source.file_revisions.get(constructor.relative_file):
        raise TransactionRejected("PATCH_SOURCE_REVISION_MISMATCH", constructor.relative_file)
    if constructor.anchor_id not in target_node.source_anchor_ids:
        raise TransactionRejected("INSERT_CONSTRUCTOR_TARGET_MISMATCH", target_node.node_id)
    if not any(
        edge.source_node_id == source_node.node_id
        and edge.target_node_id == target_node.node_id
        and any(evidence.anchor_id == forward.anchor_id for evidence in edge.evidence)
        for edge in ir.edges
    ):
        raise TransactionRejected("INSERT_FORWARD_EDGE_MISMATCH", forward.anchor_id)
    if any(node.display_name == patch.attribute_name for node in ir.nodes):
        raise TransactionRejected("INSERT_ATTRIBUTE_ALREADY_EXISTS", patch.attribute_name)
    try:
        transformed = apply_insert_layer_norm(
            raw_source, patch, constructor, forward, patch_set.base_source_revision
        )
    except Exception as error:
        if hasattr(error, "code") and hasattr(error, "message"):
            raise TransactionRejected(error.code, error.message) from error
        raise
    diff = _two_hunk_diff(raw_source, transformed.output_bytes, constructor.relative_file)
    try:
        cst.parse_module(transformed.output_bytes.decode("utf-8"))
    except (UnicodeDecodeError, cst.ParserSyntaxError) as error:
        raise TransactionRejected("CANDIDATE_SYNTAX_INVALID", str(error)) from error
    after_source, after_ir = analyzer(transformed.output_bytes)
    _assert_semantics(after_ir, after_source, "AFTER")
    observed = architecture_diff(ir, after_ir)
    validation = GraphDeltaValidator().validate(patch.expected_delta, observed)
    if validation.blocking:
        raise TransactionRejected("GRAPH_DELTA_BLOCKING", validation.model_dump_json())
    return CandidateTransaction(
        before_bytes=raw_source,
        candidate_bytes=transformed.output_bytes,
        diff=diff,
        before_source=source,
        before_ir=ir,
        after_source=after_source,
        after_ir=after_ir,
        observed_delta=observed,
        validation=validation,
    )
