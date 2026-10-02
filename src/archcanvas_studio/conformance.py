from __future__ import annotations

from archcanvas_core.digest_protocol import domain_digest
from archcanvas_core.models import (
    ArchitectureIR,
    Diagnostic,
    PublicationHierarchy,
    RoundTripConformanceReport,
    SourceTransaction,
    TransactionState,
)
from archcanvas_patterns import exact_ir_digest

SOURCE_VIEW_NORMALIZATION_DOMAIN = "archcanvas:source-view-normalization-rule:v1"
SOURCE_VIEW_CLOSURE_DOMAIN = "archcanvas:source-view-canonical-closure:v1"
INTENT_NORMALIZATION_DOMAIN = "archcanvas:intent-source-normalization-rule:v1"
GRAPH_DELTA_DOMAIN = "archcanvas:graph-delta:v1"


def _source_view_normalization_digest() -> str:
    return domain_digest(
        SOURCE_VIEW_NORMALIZATION_DOMAIN,
        {
            "version": "source-view-v1",
            "ignored": ["view-node-identifiers", "geometry", "camera", "visual-style"],
            "preserved": [
                "canonical-node-closure",
                "canonical-edge-closure",
                "canonical-tensor-closure",
                "canonical-port-closure",
                "hierarchy-containment",
            ],
        },
    )


def build_source_view_report(
    architecture: ArchitectureIR,
    hierarchy: PublicationHierarchy,
    source_digest: str,
) -> RoundTripConformanceReport:
    expected = {
        "architecture_id": architecture.architecture_id,
        "nodes": sorted(item.node_id for item in architecture.nodes),
        "edges": sorted(item.edge_id for item in architecture.edges),
        "tensors": sorted(item.tensor_id for item in architecture.tensors),
        "ports": sorted(
            port.port_id
            for node in architecture.nodes
            for port in [*node.input_ports, *node.output_ports]
        ),
    }
    observed = {
        "architecture_id": hierarchy.architecture_id,
        "nodes": sorted(hierarchy.canonical_node_ids),
        "edges": sorted(hierarchy.canonical_edge_ids),
        "tensors": sorted(hierarchy.canonical_tensor_ids),
        "ports": sorted(hierarchy.canonical_port_ids),
    }
    expected_digest = domain_digest(SOURCE_VIEW_CLOSURE_DOMAIN, expected)
    observed_digest = domain_digest(SOURCE_VIEW_CLOSURE_DOMAIN, observed)
    exact = expected_digest == observed_digest
    diagnostics = (
        []
        if exact
        else [
            Diagnostic(
                code="SOURCE_VIEW_CONFORMANCE_FAILED",
                severity="blocking",
                message="Publication hierarchy does not preserve the Exact IR canonical closure.",
                target_ids=[architecture.architecture_id],
            )
        ]
    )
    ir_digest = exact_ir_digest(architecture)
    return RoundTripConformanceReport(
        report_id=f"round-trip:source-view.{ir_digest[:24]}",
        path="source-view",
        base_source_digest=source_digest,
        result_source_digest=source_digest,
        base_exact_ir_digest=ir_digest,
        result_exact_ir_digest=ir_digest,
        normalization_rule_digest=_source_view_normalization_digest(),
        expected_delta_digest=expected_digest,
        observed_delta_digest=observed_digest,
        semantic_isomorphism="exact" if exact else "failed",
        source_writes=[],
        diagnostics=diagnostics,
    )


def build_intent_source_report(
    transaction: SourceTransaction,
) -> RoundTripConformanceReport:
    if transaction.result_exact_ir_digest is None:
        raise ValueError("verified transaction has no result Exact IR digest")
    expected_digest = domain_digest(
        GRAPH_DELTA_DOMAIN,
        transaction.expected_delta.model_dump(mode="json"),
    )
    observed_digest = (
        domain_digest(
            GRAPH_DELTA_DOMAIN,
            transaction.observed_delta.model_dump(mode="json"),
        )
        if transaction.observed_delta is not None
        else None
    )
    exact = expected_digest == observed_digest and transaction.state in {
        TransactionState.REVIEW_READY,
        TransactionState.COMMITTED,
        TransactionState.DISCARDED,
    }
    normalization_digest = domain_digest(
        INTENT_NORMALIZATION_DOMAIN,
        {
            "version": "intent-source-v1",
            "ignored": ["source-formatting", "transaction-temporary-paths"],
            "preserved": [
                "graph-delta",
                "named-ports",
                "shape-delta",
                "sharing-delta",
                "evidence-anchor-delta",
            ],
        },
    )
    diagnostics = list(transaction.diagnostics)
    if not exact and not any(item.code == "INTENT_SOURCE_CONFORMANCE_FAILED" for item in diagnostics):
        diagnostics.append(
            Diagnostic(
                code="INTENT_SOURCE_CONFORMANCE_FAILED",
                severity="blocking",
                message="Expected and observed transaction Graph Delta are not identical.",
                target_ids=[transaction.transaction_id],
            )
        )
    return RoundTripConformanceReport(
        report_id=f"round-trip:intent.{transaction.transaction_id.removeprefix('transaction:')}",
        path="intent-source",
        base_source_digest=transaction.base_source_corpus_digest,
        result_source_digest=transaction.result_source_corpus_digest,
        base_exact_ir_digest=transaction.base_exact_ir_digest,
        result_exact_ir_digest=transaction.result_exact_ir_digest,
        normalization_rule_digest=normalization_digest,
        expected_delta_digest=expected_digest,
        observed_delta_digest=observed_digest,
        semantic_isomorphism="exact" if exact else "failed",
        source_writes=(
            sorted(item.path for item in transaction.file_changes)
            if transaction.state is TransactionState.COMMITTED
            else []
        ),
        diagnostics=diagnostics,
    )
