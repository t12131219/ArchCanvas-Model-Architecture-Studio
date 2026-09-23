from __future__ import annotations

from collections import Counter, defaultdict, deque

from .models import (
    ArchitectureIR,
    CanvasDocument,
    Diagnostic,
    EvidenceKind,
    EvidenceRecord,
    GateResult,
    NodeKind,
    SourceSnapshot,
    VisualPatch,
)


def apply_visual_patch(document: CanvasDocument, patch: VisualPatch) -> CanvasDocument:
    """Append visual history without changing the source binding."""
    return document.model_copy(update={"visual_patches": [*document.visual_patches, patch]})


def _diagnostic(code: str, message: str, *target_ids: str) -> Diagnostic:
    return Diagnostic(
        code=code,
        severity="blocking",
        message=message,
        target_ids=list(target_ids),
    )


def _structural_diagnostics(ir: ArchitectureIR) -> list[Diagnostic]:
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
        for duplicate in sorted(key for key, count in Counter(values).items() if count > 1):
            diagnostics.append(
                _diagnostic(
                    f"DUPLICATE_{label}_ID",
                    f"Duplicate {label.lower()} identifier: {duplicate}",
                    duplicate,
                )
            )

    all_port_ids = [
        port.port_id for node in ir.nodes for port in node.input_ports + node.output_ports
    ]
    for duplicate in sorted(key for key, count in Counter(all_port_ids).items() if count > 1):
        diagnostics.append(
            _diagnostic("DUPLICATE_PORT_ID", f"Duplicate port identifier: {duplicate}", duplicate)
        )

    for node in ir.nodes:
        if node.parent_id and node.parent_id not in nodes:
            diagnostics.append(
                _diagnostic(
                    "MISSING_PARENT",
                    f"Node {node.node_id} references missing parent {node.parent_id}",
                    node.node_id,
                )
            )
        for child_id in node.children:
            if child_id not in nodes or nodes[child_id].parent_id != node.node_id:
                diagnostics.append(
                    _diagnostic(
                        "CHILD_PARENT_MISMATCH",
                        f"Container {node.node_id} has an invalid child {child_id}",
                        node.node_id,
                    )
                )
        if node.confidence.value not in {"unresolved", "reference-only"} and not node.evidence_ids:
            diagnostics.append(
                _diagnostic(
                    "NODE_WITHOUT_EVIDENCE",
                    f"Executable node {node.node_id} has no evidence",
                    node.node_id,
                )
            )

    edges_by_tensor: dict[str, list] = defaultdict(list)
    adjacency: dict[str, set[str]] = defaultdict(set)
    for edge in ir.edges:
        edges_by_tensor[edge.tensor_id].append(edge)
        if edge.producer_id not in nodes or edge.consumer_id not in nodes:
            diagnostics.append(
                _diagnostic(
                    "EDGE_ENDPOINT_MISSING",
                    f"Edge {edge.edge_id} references a missing node",
                    edge.edge_id,
                )
            )
        else:
            adjacency[edge.producer_id].add(edge.consumer_id)
        tensor = tensors.get(edge.tensor_id)
        if tensor is None:
            diagnostics.append(
                _diagnostic(
                    "EDGE_TENSOR_MISSING",
                    f"Edge {edge.edge_id} references missing tensor {edge.tensor_id}",
                    edge.edge_id,
                )
            )
        elif tensor.producer_id != edge.producer_id or tensor.producer_port != edge.producer_port:
            diagnostics.append(
                _diagnostic(
                    "EDGE_TENSOR_PRODUCER_MISMATCH",
                    f"Edge {edge.edge_id} disagrees with tensor {edge.tensor_id} producer",
                    edge.edge_id,
                    edge.tensor_id,
                )
            )
        for port_id, expected_node, expected_direction in (
            (edge.producer_port, edge.producer_id, "output"),
            (edge.consumer_port, edge.consumer_id, "input"),
        ):
            if ports.get(port_id) != (expected_node, expected_direction):
                diagnostics.append(
                    _diagnostic(
                        "EDGE_PORT_INVALID",
                        f"Edge {edge.edge_id} has invalid {expected_direction} port {port_id}",
                        edge.edge_id,
                    )
                )
        if not edge.evidence_ids:
            diagnostics.append(
                _diagnostic(
                    "EDGE_WITHOUT_EVIDENCE",
                    f"Edge {edge.edge_id} has no evidence",
                    edge.edge_id,
                )
            )

    for tensor in ir.tensors:
        actual_consumers = {edge.consumer_id for edge in edges_by_tensor[tensor.tensor_id]}
        if actual_consumers != set(tensor.consumer_ids):
            diagnostics.append(
                _diagnostic(
                    "TENSOR_CONSUMER_MISMATCH",
                    f"Tensor {tensor.tensor_id} consumer ledger disagrees with its edges",
                    tensor.tensor_id,
                )
            )
        if not tensor.evidence_ids:
            diagnostics.append(
                _diagnostic(
                    "TENSOR_WITHOUT_EVIDENCE",
                    f"Tensor {tensor.tensor_id} has no evidence",
                    tensor.tensor_id,
                )
            )

    fanout_ids = [relation.relation_id for relation in ir.fanouts]
    for duplicate in sorted(key for key, count in Counter(fanout_ids).items() if count > 1):
        diagnostics.append(
            _diagnostic(
                "DUPLICATE_FANOUT_ID",
                f"Duplicate fan-out relation identifier: {duplicate}",
                duplicate,
            )
        )
    fanouts_by_tensor = {relation.tensor_id: relation for relation in ir.fanouts}
    for tensor in ir.tensors:
        if len(tensor.consumer_ids) > 1:
            relation = fanouts_by_tensor.get(tensor.tensor_id)
            if (
                relation is None
                or relation.producer_id != tensor.producer_id
                or set(relation.consumer_ids) != set(tensor.consumer_ids)
            ):
                diagnostics.append(
                    _diagnostic(
                        "FANOUT_RELATION_MISMATCH",
                        f"Tensor {tensor.tensor_id} requires an exact fan-out relation",
                        tensor.tensor_id,
                    )
                )
    for relation in ir.fanouts:
        tensor = tensors.get(relation.tensor_id)
        if tensor is None or len(tensor.consumer_ids) < 2:
            diagnostics.append(
                _diagnostic(
                    "FANOUT_RELATION_INVALID",
                    f"Fan-out relation {relation.relation_id} has no multi-consumer tensor",
                    relation.relation_id,
                )
            )

    for node in ir.nodes:
        if node.kind is NodeKind.MERGE_EVENT:
            incoming = sum(1 for edge in ir.edges if edge.consumer_id == node.node_id)
            if incoming < 2:
                diagnostics.append(
                    _diagnostic(
                        "MERGE_ARITY_INVALID",
                        f"Merge node {node.node_id} has fewer than two inputs",
                        node.node_id,
                    )
                )

    input_nodes = [
        node.node_id
        for node in ir.nodes
        if node.kind is NodeKind.INPUT_OUTPUT and node.attributes.get("io") == "input"
    ]
    output_nodes = [
        node.node_id
        for node in ir.nodes
        if node.kind is NodeKind.INPUT_OUTPUT and node.attributes.get("io") == "output"
    ]
    if not input_nodes or not output_nodes:
        diagnostics.append(
            _diagnostic(
                "INPUT_OUTPUT_INCOMPLETE",
                "Architecture requires at least one input and one output node",
            )
        )
    else:
        reachable = set(input_nodes)
        queue = deque(input_nodes)
        while queue:
            current = queue.popleft()
            for target in adjacency[current] - reachable:
                reachable.add(target)
                queue.append(target)
        for output_id in output_nodes:
            if output_id not in reachable:
                diagnostics.append(
                    _diagnostic(
                        "OUTPUT_NOT_REACHABLE",
                        f"No authored data path reaches {output_id}",
                        output_id,
                    )
                )
    return diagnostics


def _evidence_diagnostics(
    ir: ArchitectureIR,
    evidence: list[EvidenceRecord],
    snapshot: SourceSnapshot,
) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    by_id = {record.evidence_id: record for record in evidence}
    source_hashes = {source.path: source.sha256 for source in snapshot.source_files}
    referenced = (
        {evidence_id for node in ir.nodes for evidence_id in node.evidence_ids}
        | {evidence_id for tensor in ir.tensors for evidence_id in tensor.evidence_ids}
        | {evidence_id for edge in ir.edges for evidence_id in edge.evidence_ids}
        | {evidence_id for relation in ir.fanouts for evidence_id in relation.evidence_ids}
        | {
            evidence_id
            for node in ir.nodes
            for parameter in node.parameters
            for evidence_id in parameter.evidence_ids
        }
    )
    for evidence_id in sorted(referenced - by_id.keys()):
        diagnostics.append(
            _diagnostic(
                "EVIDENCE_RECORD_MISSING",
                f"Referenced evidence record does not exist: {evidence_id}",
                evidence_id,
            )
        )
    for record in evidence:
        if record.kind is EvidenceKind.SOURCE:
            expected_hash = source_hashes.get(record.path or "")
            if expected_hash is None or record.file_sha256 != expected_hash:
                diagnostics.append(
                    _diagnostic(
                        "EVIDENCE_SOURCE_STALE",
                        f"Evidence {record.evidence_id} does not match the source snapshot",
                        record.evidence_id,
                    )
                )
        if (
            record.kind is EvidenceKind.CONFIG
            and record.revision != f"content:{snapshot.config_digest}"
        ):
            diagnostics.append(
                _diagnostic(
                    "EVIDENCE_CONFIG_STALE",
                    f"Config evidence {record.evidence_id} does not match the config snapshot",
                    record.evidence_id,
                )
            )
    return diagnostics


def _transformer_l3_diagnostics(ir: ArchitectureIR) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    by_symbol = {
        node.attributes.get("assigned_symbol"): node
        for node in ir.nodes
        if node.attributes.get("assigned_symbol")
    }
    incoming: dict[str, list] = defaultdict(list)
    for edge in ir.edges:
        incoming[edge.consumer_id].append(edge)

    required_symbols = {
        "enc_q",
        "enc_k",
        "enc_v",
        "enc_q_split",
        "enc_k_split",
        "enc_v_split",
        "enc_k_t",
        "enc_scores_raw",
        "enc_scores",
        "enc_weights",
        "enc_context_heads",
        "enc_concat",
        "enc_attention",
        "enc_residual",
        "memory",
        "dec_q",
        "dec_k",
        "dec_v",
        "dec_q_split",
        "dec_k_split",
        "dec_v_split",
        "dec_k_t",
        "dec_scores_raw",
        "dec_scores",
        "masked_scores",
        "dec_weights",
        "dec_context_heads",
        "dec_concat",
        "dec_attention",
        "dec_residual",
        "decoder_hidden",
        "cross_q",
        "cross_k",
        "cross_v",
        "cross_q_split",
        "cross_k_split",
        "cross_v_split",
        "cross_k_t",
        "cross_scores_raw",
        "cross_scores",
        "cross_weights",
        "cross_context_heads",
        "cross_concat",
        "cross_attention",
        "cross_residual",
        "cross_hidden",
        "transformed",
        "output_residual",
        "output_hidden",
        "logits",
    }
    for symbol in sorted(required_symbols - by_symbol.keys()):
        diagnostics.append(
            _diagnostic(
                "TRANSFORMER_L3_NODE_MISSING",
                f"Transformer L3 requires source-backed symbol {symbol}",
            )
        )
    if diagnostics:
        return diagnostics

    def producers(symbol: str) -> set[str]:
        return {edge.producer_id for edge in incoming[by_symbol[symbol].node_id]}

    input_by_symbol = {
        node.attributes.get("assigned_symbol"): node
        for node in ir.nodes
        if node.attributes.get("io") == "input"
    }
    src = input_by_symbol.get("src")
    tgt = input_by_symbol.get("tgt")
    mask = input_by_symbol.get("target_mask")
    if not src or not tgt or not mask:
        diagnostics.append(
            _diagnostic(
                "TRANSFORMER_INPUTS_INVALID",
                "Transformer L3 requires src, tgt, and target_mask inputs",
            )
        )
        return diagnostics

    for symbol in ("enc_q", "enc_k", "enc_v"):
        if src.node_id not in producers(symbol):
            diagnostics.append(
                _diagnostic(
                    "TRANSFORMER_ENCODER_QKV_NOT_PARALLEL",
                    f"{symbol} must be projected directly from src",
                    by_symbol[symbol].node_id,
                )
            )
    for symbol in ("dec_q", "dec_k", "dec_v"):
        if tgt.node_id not in producers(symbol):
            diagnostics.append(
                _diagnostic(
                    "TRANSFORMER_DECODER_QKV_NOT_PARALLEL",
                    f"{symbol} must be projected directly from tgt",
                    by_symbol[symbol].node_id,
                )
            )

    def require_producers(symbol: str, expected_symbols: set[str], code: str) -> None:
        expected_ids = {by_symbol[name].node_id for name in expected_symbols}
        if not expected_ids <= producers(symbol):
            diagnostics.append(
                _diagnostic(
                    code,
                    f"{symbol} must consume {', '.join(sorted(expected_symbols))}",
                    by_symbol[symbol].node_id,
                )
            )

    for lane in ("enc", "dec", "cross"):
        for role in ("q", "k", "v"):
            require_producers(
                f"{lane}_{role}_split",
                {f"{lane}_{role}"},
                "TRANSFORMER_HEAD_SPLIT_INVALID",
            )
        require_producers(
            f"{lane}_k_t",
            {f"{lane}_k_split"},
            "TRANSFORMER_KEY_TRANSPOSE_INVALID",
        )
        require_producers(
            f"{lane}_scores_raw",
            {f"{lane}_q_split", f"{lane}_k_t"},
            "TRANSFORMER_QK_SCORE_INVALID",
        )
        require_producers(
            f"{lane}_scores",
            {f"{lane}_scores_raw"},
            "TRANSFORMER_SCORE_SCALE_INVALID",
        )
        weights_source = "masked_scores" if lane == "dec" else f"{lane}_scores"
        require_producers(
            f"{lane}_weights",
            {weights_source},
            "TRANSFORMER_SOFTMAX_ORDER_INVALID",
        )
        require_producers(
            f"{lane}_context_heads",
            {f"{lane}_weights", f"{lane}_v_split"},
            "TRANSFORMER_WEIGHTED_VALUE_INVALID",
        )
        require_producers(
            f"{lane}_concat",
            {f"{lane}_context_heads"},
            "TRANSFORMER_HEAD_CONCAT_INVALID",
        )
    require_producers(
        "masked_scores",
        {"dec_scores"},
        "TRANSFORMER_MASK_ORDER_INVALID",
    )

    memory_node = by_symbol["memory"].node_id
    decoder_hidden_node = by_symbol["decoder_hidden"].node_id
    if decoder_hidden_node not in producers("cross_q"):
        diagnostics.append(
            _diagnostic(
                "TRANSFORMER_CROSS_Q_SOURCE_INVALID",
                "Cross-attention Q must come from decoder hidden state",
                by_symbol["cross_q"].node_id,
            )
        )
    for symbol in ("cross_k", "cross_v"):
        if memory_node not in producers(symbol):
            diagnostics.append(
                _diagnostic(
                    "TRANSFORMER_MEMORY_SOURCE_INVALID",
                    f"{symbol} must come from encoder memory",
                    by_symbol[symbol].node_id,
                )
            )

    mask_edges = [
        edge
        for edge in incoming[by_symbol["masked_scores"].node_id]
        if edge.producer_id == mask.node_id and edge.edge_type.value == "condition"
    ]
    if not mask_edges:
        diagnostics.append(
            _diagnostic(
                "TRANSFORMER_MASK_PATH_INVALID",
                "Target mask must enter masked scores through a condition edge",
                by_symbol["masked_scores"].node_id,
            )
        )

    for residual, source_symbol, branch_symbol, norm_symbol in (
        ("enc_residual", "src", "enc_attention", "memory"),
        ("dec_residual", "tgt", "dec_attention", "decoder_hidden"),
        ("cross_residual", "decoder_hidden", "cross_attention", "cross_hidden"),
        ("output_residual", "cross_hidden", "transformed", "output_hidden"),
    ):
        node = by_symbol[residual]
        if node.kind is not NodeKind.MERGE_EVENT:
            diagnostics.append(
                _diagnostic(
                    "TRANSFORMER_RESIDUAL_NOT_MERGE",
                    f"{residual} must be an explicit merge event",
                    node.node_id,
                )
            )
            continue
        source_node = input_by_symbol.get(source_symbol) or by_symbol.get(source_symbol)
        expected = {source_node.node_id, by_symbol[branch_symbol].node_id} if source_node else set()
        if not expected <= producers(residual) or node.node_id not in producers(norm_symbol):
            diagnostics.append(
                _diagnostic(
                    "TRANSFORMER_POST_NORM_ORDER_INVALID",
                    f"{residual} must merge both branches before {norm_symbol}",
                    node.node_id,
                )
            )

    tensors = {tensor.role: tensor for tensor in ir.tensors}
    expected_shapes = {
        "enc_q_split": "[B,H,S,Dh]",
        "dec_q_split": "[B,H,T,Dh]",
        "cross_q_split": "[B,H,T,Dh]",
        "cross_k_split": "[B,H,S,Dh]",
        "cross_v_split": "[B,H,S,Dh]",
        "logits": "[B,T,V]",
    }
    for role, shape in expected_shapes.items():
        tensor = tensors.get(role)
        if tensor is None or tensor.symbolic_shape != shape:
            targets = [tensor.tensor_id] if tensor else []
            diagnostics.append(
                _diagnostic(
                    "TRANSFORMER_SHAPE_INVALID",
                    f"{role} must have symbolic shape {shape}",
                    *targets,
                )
            )

    output_nodes = [node for node in ir.nodes if node.attributes.get("io") == "output"]
    if not output_nodes or by_symbol["logits"].node_id not in {
        edge.producer_id for edge in incoming[output_nodes[0].node_id]
    }:
        diagnostics.append(
            _diagnostic(
                "TRANSFORMER_OUTPUT_NOT_LOGITS",
                "Selected forward path must return logits directly",
            )
        )
    require_producers(
        "logits",
        {"output_hidden"},
        "TRANSFORMER_GENERATOR_INPUT_INVALID",
    )
    return diagnostics


def validate_architecture(
    ir: ArchitectureIR,
    evidence: list[EvidenceRecord] | None = None,
    snapshot: SourceSnapshot | None = None,
) -> tuple[list[GateResult], list[Diagnostic]]:
    structural = _structural_diagnostics(ir)
    evidence_diagnostics: list[Diagnostic] = []
    if evidence is not None and snapshot is not None:
        evidence_diagnostics = _evidence_diagnostics(ir, evidence, snapshot)

    is_transformer = ir.entrypoint.rsplit(":", 1)[-1].lower() == "transformer"
    transformer = _transformer_l3_diagnostics(ir) if is_transformer else []
    diagnostics = [*structural, *evidence_diagnostics, *transformer]
    gates = [
        GateResult(
            gate="A-source-identity",
            status=(
                "skipped"
                if evidence is None or snapshot is None
                else "failed"
                if evidence_diagnostics
                else "passed"
            ),
            message=(
                "Source snapshot and evidence ledger were not supplied."
                if evidence is None or snapshot is None
                else f"{len(evidence_diagnostics)} source identity issue(s)."
                if evidence_diagnostics
                else "Every referenced evidence record matches the frozen source/config snapshot."
            ),
        ),
        GateResult(
            gate="B-semantic-closure",
            status="failed" if structural else "passed",
            message=(
                f"{len(structural)} blocking semantic issue(s)."
                if structural
                else "Endpoints, ports, tensors, containment, evidence references, and reachability close."
            ),
        ),
    ]
    if is_transformer:
        gates.append(
            GateResult(
                gate="B-transformer-l3",
                status="failed" if transformer else "passed",
                message=(
                    f"{len(transformer)} Transformer L3 contract issue(s)."
                    if transformer
                    else "Q/K/V, mask, memory, residual order, shapes, and logits are source-backed."
                ),
            )
        )
    gates.append(
        GateResult(
            gate="C-publication-compilation",
            status="skipped",
            message="Publication compiler is not part of Stage 1.",
        )
    )
    return gates, diagnostics
