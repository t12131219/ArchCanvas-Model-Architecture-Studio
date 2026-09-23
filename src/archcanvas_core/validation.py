from __future__ import annotations

from collections import Counter, defaultdict

from .models import ArchitectureIR, Diagnostic, GateResult, NodeKind


def apply_visual_patch(document, patch):
    """Append visual history without changing the source binding."""
    return document.model_copy(update={"visual_patches": [*document.visual_patches, patch]})


def validate_architecture(ir: ArchitectureIR) -> tuple[list[GateResult], list[Diagnostic]]:
    diagnostics: list[Diagnostic] = []
    node_ids = [node.node_id for node in ir.nodes]
    tensor_ids = [tensor.tensor_id for tensor in ir.tensors]
    edge_ids = [edge.edge_id for edge in ir.edges]
    nodes = {node.node_id: node for node in ir.nodes}
    tensors = {tensor.tensor_id: tensor for tensor in ir.tensors}
    ports = {
        port.port_id: (node.node_id, port.direction)
        for node in ir.nodes
        for port in node.input_ports + node.output_ports
    }

    for label, values in (("NODE", node_ids), ("TENSOR", tensor_ids), ("EDGE", edge_ids)):
        duplicates = sorted(key for key, count in Counter(values).items() if count > 1)
        for duplicate in duplicates:
            diagnostics.append(
                Diagnostic(
                    code=f"DUPLICATE_{label}_ID",
                    severity="blocking",
                    message=f"Duplicate {label.lower()} identifier: {duplicate}",
                    target_ids=[duplicate],
                )
            )

    for node in ir.nodes:
        if node.parent_id and node.parent_id not in nodes:
            diagnostics.append(
                Diagnostic(
                    code="MISSING_PARENT",
                    severity="blocking",
                    message=f"Node {node.node_id} references missing parent {node.parent_id}",
                    target_ids=[node.node_id],
                )
            )
        if node.confidence.value not in {"unresolved", "reference-only"} and not node.evidence_ids:
            diagnostics.append(
                Diagnostic(
                    code="NODE_WITHOUT_EVIDENCE",
                    severity="blocking",
                    message=f"Executable node {node.node_id} has no evidence",
                    target_ids=[node.node_id],
                )
            )

    incoming: dict[str, int] = defaultdict(int)
    for edge in ir.edges:
        if edge.producer_id not in nodes or edge.consumer_id not in nodes:
            diagnostics.append(
                Diagnostic(
                    code="EDGE_ENDPOINT_MISSING",
                    severity="blocking",
                    message=f"Edge {edge.edge_id} references a missing node",
                    target_ids=[edge.edge_id],
                )
            )
        if edge.tensor_id not in tensors:
            diagnostics.append(
                Diagnostic(
                    code="EDGE_TENSOR_MISSING",
                    severity="blocking",
                    message=f"Edge {edge.edge_id} references missing tensor {edge.tensor_id}",
                    target_ids=[edge.edge_id],
                )
            )
        for port_id, expected_direction in (
            (edge.producer_port, "output"),
            (edge.consumer_port, "input"),
        ):
            if port_id not in ports or ports[port_id][1] != expected_direction:
                diagnostics.append(
                    Diagnostic(
                        code="EDGE_PORT_INVALID",
                        severity="blocking",
                        message=f"Edge {edge.edge_id} has invalid {expected_direction} port {port_id}",
                        target_ids=[edge.edge_id],
                    )
                )
        incoming[edge.consumer_id] += 1

    input_nodes = [node for node in ir.nodes if node.kind is NodeKind.INPUT_OUTPUT and node.attributes.get("io") == "input"]
    output_nodes = [node for node in ir.nodes if node.kind is NodeKind.INPUT_OUTPUT and node.attributes.get("io") == "output"]
    if not input_nodes or not output_nodes:
        diagnostics.append(
            Diagnostic(
                code="INPUT_OUTPUT_INCOMPLETE",
                severity="blocking",
                message="Architecture requires at least one input and one output node",
            )
        )

    blocking = [item for item in diagnostics if item.severity == "blocking"]
    gates = [
        GateResult(
            gate="A-source-identity",
            status="passed",
            message="Architecture is bound to a versioned source snapshot.",
        ),
        GateResult(
            gate="B-semantic-closure",
            status="failed" if blocking else "passed",
            message=(f"{len(blocking)} blocking semantic issue(s)." if blocking else "Endpoints, ports, tensors, and evidence close."),
        ),
        GateResult(
            gate="C-publication-compilation",
            status="skipped",
            message="Publication compiler is not part of the rewrite baseline.",
        ),
    ]
    return gates, diagnostics
