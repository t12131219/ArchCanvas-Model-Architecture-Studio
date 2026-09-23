"""Candidate-first planning for the inverse restricted LayerNorm splice."""

from __future__ import annotations

from difflib import unified_diff

import libcst as cst

from archcanvas_core.graph_delta import GraphDeltaValidator, architecture_diff
from archcanvas_core.models.architecture import (
    ArchitectureIR,
    Confidence,
    EdgeKind,
    EvidenceSource,
    NodeKind,
)
from archcanvas_core.models.patch import PatchSet, RemoveLayerNormPatch
from archcanvas_core.models.source_identity import SourceIdentityDocument

from ..analyzers import Analyzer
from ..transforms.remove_layer_norm import apply_remove_layer_norm
from .set_parameter import CandidateTransaction, TransactionRejected, _assert_semantics
from .structural_delta import require_exact_structural_delta


def plan_remove_layer_norm(raw_source: bytes, patch_set: PatchSet, source: SourceIdentityDocument, ir: ArchitectureIR, *, analyzer: Analyzer) -> CandidateTransaction:
    if len(patch_set.patches) != 1 or not isinstance(patch_set.patches[0], RemoveLayerNormPatch):
        raise TransactionRejected("PATCH_OPERATION_MISMATCH", "expected one remove_layer_norm patch")
    patch = patch_set.patches[0]
    if patch_set.project_id != source.project_id or patch_set.project_id != ir.project_id:
        raise TransactionRejected("PROJECT_ID_MISMATCH", patch_set.project_id)
    _assert_semantics(ir, source, "BEFORE")
    try:
        removed = ir.node(patch.removed_node_id)
        constructor = next(anchor for anchor in source.anchors if anchor.anchor_id == patch.constructor_anchor_id)
        forward = next(anchor for anchor in source.anchors if anchor.anchor_id == patch.forward_anchor_id)
    except StopIteration as error:
        raise TransactionRejected("PATCH_TARGET_NOT_FOUND", str(error)) from error
    if (
        removed.kind is not NodeKind.MODULE
        or removed.op_type not in {"torch.nn.LayerNorm", "nn.LayerNorm"}
        or constructor.anchor_id not in removed.source_anchor_ids
        or removed.display_name != patch.attribute_name
    ):
        raise TransactionRejected("REMOVE_CONSTRUCTOR_TARGET_MISMATCH", patch.removed_node_id)
    if patch_set.base_source_revision != source.file_revisions.get(constructor.relative_file):
        raise TransactionRejected("PATCH_SOURCE_REVISION_MISMATCH", constructor.relative_file)
    connected = [
        edge for edge in ir.edges
        if edge.source_node_id == removed.node_id or edge.target_node_id == removed.node_id
    ]
    incoming = [edge for edge in connected if edge.target_node_id == removed.node_id]
    outgoing = [edge for edge in connected if edge.source_node_id == removed.node_id]
    if (
        patch.source_node_id == patch.target_node_id
        or len(incoming) != 1
        or len(outgoing) != 1
        or incoming[0].source_node_id != patch.source_node_id
        or outgoing[0].target_node_id != patch.target_node_id
        or incoming[0].kind is not EdgeKind.DATA
        or outgoing[0].kind is not EdgeKind.DATA
    ):
        raise TransactionRejected("REMOVE_LINEAR_SPLICE_NOT_PROVEN", removed.node_id)
    if not any(
        evidence.anchor_id == forward.anchor_id
        and evidence.confidence is Confidence.CONFIRMED
        and evidence.source in {EvidenceSource.STATIC_AST, EvidenceSource.STATIC_CST}
        for evidence in incoming[0].evidence
    ):
        raise TransactionRejected("REMOVE_FORWARD_EDGE_MISMATCH", forward.anchor_id)
    if not any(
        evidence.anchor_id is not None
        and evidence.confidence is Confidence.CONFIRMED
        and evidence.source in {EvidenceSource.STATIC_AST, EvidenceSource.STATIC_CST}
        for evidence in outgoing[0].evidence
    ):
        raise TransactionRejected("REMOVE_TARGET_EDGE_UNPROVEN", outgoing[0].edge_id)
    try:
        output = apply_remove_layer_norm(raw_source, patch, constructor, forward, patch_set.base_source_revision)
        cst.parse_module(output.decode("utf-8"))
    except Exception as error:
        if hasattr(error, "code") and hasattr(error, "message"):
            raise TransactionRejected(error.code, error.message) from error
        raise TransactionRejected("CANDIDATE_SYNTAX_INVALID", str(error)) from error
    diff = "".join(unified_diff(raw_source.decode().splitlines(keepends=True), output.decode().splitlines(keepends=True), fromfile=f"a/{constructor.relative_file}", tofile=f"b/{constructor.relative_file}"))
    if sum(line.startswith("@@ ") for line in diff.splitlines()) != 2:
        raise TransactionRejected("TEXTUAL_HUNK_CARDINALITY", "remove_layer_norm requires exactly two diff hunks")
    after_source, after_ir = analyzer(output)
    _assert_semantics(after_ir, after_source, "AFTER")
    observed = architecture_diff(ir, after_ir)
    require_exact_structural_delta(
        patch.expected_delta, observed,
        removed_node_id=patch.removed_node_id, edge_additions=1, edge_removals=2,
    )
    validation = GraphDeltaValidator().validate(patch.expected_delta, observed)
    if validation.blocking:
        raise TransactionRejected("GRAPH_DELTA_BLOCKING", validation.model_dump_json())
    return CandidateTransaction(raw_source, output, diff, source, ir, after_source, after_ir, observed, validation)
