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
    return document.model_copy(
        update={
            "visual_patches": [*document.visual_patches, patch],
            "redo_patches": [],
        }
    )


def undo_visual_patch(document: CanvasDocument) -> CanvasDocument:
    """Move the latest visual patch to the redo stack."""
    if not document.visual_patches:
        return document
    patch = document.visual_patches[-1]
    return document.model_copy(
        update={
            "visual_patches": document.visual_patches[:-1],
            "redo_patches": [patch, *document.redo_patches],
        }
    )


def redo_visual_patch(document: CanvasDocument) -> CanvasDocument:
    """Restore the next visual patch without changing the source binding."""
    if not document.redo_patches:
        return document
    patch = document.redo_patches[0]
    return document.model_copy(
        update={
            "visual_patches": [*document.visual_patches, patch],
            "redo_patches": document.redo_patches[1:],
        }
    )


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

    repeat_ids = {repeat.repeat_id for repeat in ir.repeats}
    if len(repeat_ids) != len(ir.repeats):
        diagnostics.append(_diagnostic("DUPLICATE_REPEAT_ID", "Repeat identifiers must be unique"))
    for repeat in ir.repeats:
        if any(member_id not in nodes for member_id in repeat.member_node_ids):
            diagnostics.append(
                _diagnostic(
                    "REPEAT_MEMBER_MISSING",
                    f"Repeat {repeat.repeat_id} references a missing member",
                    repeat.repeat_id,
                )
            )
        if not repeat.evidence_ids:
            diagnostics.append(
                _diagnostic(
                    "REPEAT_WITHOUT_EVIDENCE",
                    f"Repeat {repeat.repeat_id} has no evidence",
                    repeat.repeat_id,
                )
            )

    predicate_ids = {predicate.predicate_id for predicate in ir.config_predicates}
    if len(predicate_ids) != len(ir.config_predicates):
        diagnostics.append(
            _diagnostic("DUPLICATE_PREDICATE_ID", "Config predicate identifiers must be unique")
        )
    for predicate in ir.config_predicates:
        if any(target_id not in nodes for target_id in predicate.affected_ids):
            diagnostics.append(
                _diagnostic(
                    "PREDICATE_TARGET_MISSING",
                    f"Config predicate {predicate.predicate_id} has a missing target",
                    predicate.predicate_id,
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
        | {evidence_id for repeat in ir.repeats for evidence_id in repeat.evidence_ids}
        | {
            evidence_id
            for predicate in ir.config_predicates
            for evidence_id in predicate.evidence_ids
        }
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


def _autoformer_diagnostics(ir: ArchitectureIR) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    nodes = {node.node_id: node for node in ir.nodes}
    incoming: dict[str, set[str]] = defaultdict(set)
    for edge in ir.edges:
        incoming[edge.consumer_id].add(edge.producer_id)

    required = {
        "node:enc_embedding",
        "node:dec_embedding",
        "node:encoder.q_projection",
        "node:encoder.k_projection",
        "node:encoder.v_projection",
        "node:encoder.q_fft",
        "node:encoder.k_fft",
        "node:encoder.spectral_product",
        "node:encoder.irfft",
        "node:encoder.top_k",
        "node:encoder.delay_aggregate",
        "node:encoder.decomp1",
        "node:encoder.decomp2",
        "node:decoder.self_q_projection",
        "node:decoder.self_k_projection",
        "node:decoder.self_v_projection",
        "node:decoder.cross_q_projection",
        "node:decoder.cross_k_projection",
        "node:decoder.cross_v_projection",
        "node:decoder.decomp1",
        "node:decoder.decomp2",
        "node:decoder.decomp3",
        "node:decoder.trend_residual_sum",
        "node:decoder.trend_accumulate",
        "node:final_add",
        "node:output.forecast",
    }
    for node_id in sorted(required - nodes.keys()):
        diagnostics.append(
            _diagnostic(
                "AUTOFORMER_NODE_MISSING",
                f"Autoformer source contract requires {node_id}",
            )
        )
    if diagnostics:
        return diagnostics

    for embedding_id in ("node:enc_embedding", "node:dec_embedding"):
        if nodes[embedding_id].attributes.get("position_embedding_used") is not False:
            diagnostics.append(
                _diagnostic(
                    "AUTOFORMER_POSITION_EMBEDDING_INVALID",
                    f"{embedding_id} must use DataEmbedding_wo_pos without a position term",
                    embedding_id,
                )
            )

    def require_inputs(target: str, expected: set[str], code: str) -> None:
        if not expected <= incoming[target]:
            diagnostics.append(
                _diagnostic(
                    code,
                    f"{target} must consume {', '.join(sorted(expected))}",
                    target,
                )
            )

    require_inputs(
        "node:encoder.spectral_product",
        {"node:encoder.q_fft", "node:encoder.k_fft"},
        "AUTOFORMER_FFT_CORRELATION_INVALID",
    )
    require_inputs(
        "node:encoder.irfft",
        {"node:encoder.spectral_product"},
        "AUTOFORMER_FFT_CORRELATION_INVALID",
    )
    require_inputs(
        "node:encoder.delay_aggregate",
        {"node:encoder.top_k", "node:encoder.v_projection", "node:encoder.irfft"},
        "AUTOFORMER_DELAY_AGGREGATION_INVALID",
    )
    require_inputs(
        "node:encoder.decomp1",
        {"node:encoder.residual1"},
        "AUTOFORMER_ENCODER_DECOMPOSITION_INVALID",
    )
    require_inputs(
        "node:encoder.decomp2",
        {"node:encoder.residual2"},
        "AUTOFORMER_ENCODER_DECOMPOSITION_INVALID",
    )

    memory_edges = [
        edge
        for edge in ir.edges
        if edge.edge_type.value == "memory" and edge.producer_id == "node:encoder.decomp2"
    ]
    if {edge.consumer_id for edge in memory_edges} != {
        "node:decoder.cross_k_projection",
        "node:decoder.cross_v_projection",
    }:
        diagnostics.append(
            _diagnostic(
                "AUTOFORMER_CROSS_MEMORY_INVALID",
                "Decoder cross K/V must both come from encoder memory",
            )
        )
    require_inputs(
        "node:decoder.cross_q_projection",
        {"node:decoder.decomp1"},
        "AUTOFORMER_CROSS_QUERY_INVALID",
    )

    require_inputs(
        "node:decoder.trend_residual_sum",
        {"node:decoder.decomp1", "node:decoder.decomp2", "node:decoder.decomp3"},
        "AUTOFORMER_TREND_SUM_INVALID",
    )
    require_inputs(
        "node:decoder.trend_accumulate",
        {"node:trend_seed", "node:decoder.trend_projection"},
        "AUTOFORMER_TREND_ACCUMULATION_INVALID",
    )
    require_inputs(
        "node:final_add",
        {"node:decoder.seasonal_projection", "node:decoder.trend_accumulate"},
        "AUTOFORMER_FINAL_MERGE_INVALID",
    )

    condition_edges = [edge for edge in ir.edges if edge.edge_type.value == "condition"]
    if condition_edges:
        diagnostics.append(
            _diagnostic(
                "AUTOFORMER_MASK_SEMANTICS_INVALID",
                "This source revision does not consume masks inside AutoCorrelation",
                *(edge.edge_id for edge in condition_edges),
            )
        )

    output_tensor = next((tensor for tensor in ir.tensors if tensor.role == "forecast"), None)
    if output_tensor is None or output_tensor.symbolic_shape != "[B,P,C]":
        diagnostics.append(
            _diagnostic(
                "AUTOFORMER_OUTPUT_SHAPE_INVALID",
                "Autoformer forecast must have symbolic shape [B,P,C]",
            )
        )
    repeat_by_id = {repeat.repeat_id: repeat for repeat in ir.repeats}
    for repeat_id in ("repeat:encoder.layers", "repeat:decoder.layers"):
        if repeat_id not in repeat_by_id:
            diagnostics.append(
                _diagnostic(
                    "AUTOFORMER_REPEAT_MISSING",
                    f"Autoformer requires {repeat_id}",
                )
            )
    return diagnostics


def _itransformer_diagnostics(ir: ArchitectureIR) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    nodes = {node.node_id: node for node in ir.nodes}
    incoming: dict[str, set[str]] = defaultdict(set)
    for edge in ir.edges:
        incoming[edge.consumer_id].add(edge.producer_id)
    predicates = {predicate.predicate_id: predicate for predicate in ir.config_predicates}
    required = {
        "node:input.x_enc",
        "node:embedding.permute",
        "node:embedding.projection",
        "node:encoder.stack",
        "node:forecast.projector",
        "node:forecast.permute",
        "node:output.forecast",
    }
    for node_id in sorted(required - nodes.keys()):
        diagnostics.append(
            _diagnostic(
                "ITRANSFORMER_NODE_MISSING",
                f"iTransformer source contract requires {node_id}",
            )
        )
    for predicate_id in ("predicate:use_norm", "predicate:use_covariates"):
        if predicate_id not in predicates:
            diagnostics.append(
                _diagnostic(
                    "ITRANSFORMER_PREDICATE_MISSING",
                    f"iTransformer requires {predicate_id}",
                )
            )
    if diagnostics:
        return diagnostics

    permute = nodes["node:embedding.permute"]
    if (
        permute.attributes.get("internal_axis_transform") is not True
        or permute.attributes.get("external_learnable_module") is not False
        or permute.attributes.get("transform") != "[B,L,N] -> [B,N,L]"
    ):
        diagnostics.append(
            _diagnostic(
                "ITRANSFORMER_INTERNAL_PERMUTE_INVALID",
                "DataEmbedding_inverted permute must remain an internal non-learnable axis transform",
                permute.node_id,
            )
        )
    projection = nodes["node:embedding.projection"]
    if projection.attributes.get("in_axis") != "L" or projection.attributes.get("out_axis") != "D":
        diagnostics.append(
            _diagnostic(
                "ITRANSFORMER_TOKEN_PROJECTION_INVALID",
                "The inverted embedding must project temporal axis L to model depth D",
                projection.node_id,
            )
        )
    forecast_projection = nodes["node:forecast.projector"]
    if (
        forecast_projection.attributes.get("in_axis") != "D"
        or forecast_projection.attributes.get("out_axis") != "S"
    ):
        diagnostics.append(
            _diagnostic(
                "ITRANSFORMER_FORECAST_PROJECTION_INVALID",
                "The forecast projector must map D to prediction length S",
                forecast_projection.node_id,
            )
        )
    if any("decoder" in node.node_id or "decoder" in node.semantic_name.lower() for node in ir.nodes):
        diagnostics.append(
            _diagnostic(
                "ITRANSFORMER_ENCODER_ONLY_INVALID",
                "iTransformer must remain encoder-only",
            )
        )

    def require_input(target: str, source: str, code: str) -> None:
        if source not in incoming[target]:
            diagnostics.append(
                _diagnostic(code, f"{target} must consume {source}", target)
            )

    require_input(
        "node:embedding.projection",
        "node:covariate.concat"
        if predicates["predicate:use_covariates"].resolved_value
        else "node:embedding.permute",
        "ITRANSFORMER_TOKEN_FLOW_INVALID",
    )
    require_input(
        "node:encoder.stack",
        "node:embedding.projection",
        "ITRANSFORMER_ENCODER_FLOW_INVALID",
    )
    require_input(
        "node:forecast.projector",
        "node:encoder.stack",
        "ITRANSFORMER_FORECAST_FLOW_INVALID",
    )
    require_input(
        "node:forecast.permute",
        "node:forecast.projector",
        "ITRANSFORMER_OUTPUT_PERMUTE_INVALID",
    )

    use_covariates = bool(predicates["predicate:use_covariates"].resolved_value)
    covariate_nodes = {
        "node:covariate.permute",
        "node:covariate.concat",
        "node:forecast.trim_covariates",
    }
    if use_covariates:
        missing = covariate_nodes - nodes.keys()
        if missing:
            diagnostics.append(
                _diagnostic(
                    "ITRANSFORMER_COVARIATE_PATH_INVALID",
                    f"Active covariate path is missing {sorted(missing)}",
                )
            )
        elif "node:forecast.permute" not in incoming["node:forecast.trim_covariates"]:
            diagnostics.append(
                _diagnostic(
                    "ITRANSFORMER_COVARIATE_TRIM_INVALID",
                    "Forecast covariate tokens must be trimmed after output permutation",
                    "node:forecast.trim_covariates",
                )
            )
    elif covariate_nodes & nodes.keys():
        diagnostics.append(
            _diagnostic(
                "ITRANSFORMER_COVARIATE_PREDICATE_INVALID",
                "Inactive covariate config must not produce an active covariate path",
            )
        )

    use_norm = bool(predicates["predicate:use_norm"].resolved_value)
    norm_nodes = {"node:normalize", "node:denormalize"}
    if use_norm and not norm_nodes <= nodes.keys():
        diagnostics.append(
            _diagnostic(
                "ITRANSFORMER_NORMALIZATION_PATH_INVALID",
                "use_norm requires both normalization and denormalization",
            )
        )
    if not use_norm and norm_nodes & nodes.keys():
        diagnostics.append(
            _diagnostic(
                "ITRANSFORMER_NORMALIZATION_PREDICATE_INVALID",
                "Inactive use_norm must not produce an active normalization path",
            )
        )
    output_tensor = next((tensor for tensor in ir.tensors if tensor.role == "forecast"), None)
    if output_tensor is None or output_tensor.symbolic_shape != "[B,S,N]":
        diagnostics.append(
            _diagnostic(
                "ITRANSFORMER_OUTPUT_SHAPE_INVALID",
                "iTransformer forecast must have symbolic shape [B,S,N]",
            )
        )
    if not any(repeat.repeat_id == "repeat:encoder.layers" for repeat in ir.repeats):
        diagnostics.append(
            _diagnostic(
                "ITRANSFORMER_REPEAT_MISSING",
                "iTransformer requires its encoder layer repeat",
            )
        )
    return diagnostics


def _patchtst_diagnostics(ir: ArchitectureIR) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    nodes = {node.node_id: node for node in ir.nodes}
    incoming: dict[str, set[str]] = defaultdict(set)
    for edge in ir.edges:
        incoming[edge.consumer_id].add(edge.producer_id)
    predicates = {predicate.predicate_id: predicate for predicate in ir.config_predicates}
    required_predicates = {
        "predicate:decomposition",
        "predicate:revin",
        "predicate:padding-patch",
        "predicate:individual",
        "predicate:res-attention",
        "predicate:norm",
    }
    for predicate_id in sorted(required_predicates - predicates.keys()):
        diagnostics.append(
            _diagnostic(
                "PATCHTST_PREDICATE_MISSING",
                f"PatchTST requires {predicate_id}",
            )
        )
    required = {"node:input.x", "node:output_permute", "node:output.forecast"}
    for node_id in sorted(required - nodes.keys()):
        diagnostics.append(
            _diagnostic("PATCHTST_NODE_MISSING", f"PatchTST requires {node_id}")
        )
    if diagnostics:
        return diagnostics

    decomposition = bool(predicates["predicate:decomposition"].resolved_value)
    revin = bool(predicates["predicate:revin"].resolved_value)
    end_padding = predicates["predicate:padding-patch"].resolved_value == "end"
    residual_attention = bool(predicates["predicate:res-attention"].resolved_value)
    norm = predicates["predicate:norm"].resolved_value
    lanes = ["residual", "trend"] if decomposition else ["main"]

    def require_input(target: str, source: str, code: str) -> None:
        if target not in incoming or source not in incoming[target]:
            diagnostics.append(_diagnostic(code, f"{target} must consume {source}", target))

    if decomposition:
        for node_id in ("node:decomposition", "node:decomposition_add"):
            if node_id not in nodes:
                diagnostics.append(
                    _diagnostic(
                        "PATCHTST_DECOMPOSITION_PATH_INVALID",
                        f"decomposition=true requires {node_id}",
                    )
                )
    elif "node:decomposition" in nodes or "node:decomposition_add" in nodes:
        diagnostics.append(
            _diagnostic(
                "PATCHTST_DECOMPOSITION_PREDICATE_INVALID",
                "decomposition=false must use a single backbone",
            )
        )

    for lane in lanes:
        prefix = f"node:{lane}"
        lane_required = {
            f"{prefix}.unfold",
            f"{prefix}.patch_projection",
            f"{prefix}.channel_reshape",
            f"{prefix}.position",
            f"{prefix}.position_add",
            f"{prefix}.encoder",
            f"{prefix}.restore_channels",
            f"{prefix}.flatten",
            f"{prefix}.head_linear",
        }
        for node_id in sorted(lane_required - nodes.keys()):
            diagnostics.append(
                _diagnostic("PATCHTST_LANE_NODE_MISSING", f"{lane} lane requires {node_id}")
            )
        if lane_required - nodes.keys():
            continue
        patch_projection = nodes[f"{prefix}.patch_projection"]
        if (
            patch_projection.attributes.get("in_axis") != "P"
            or patch_projection.attributes.get("out_axis") != "D"
        ):
            diagnostics.append(
                _diagnostic(
                    "PATCHTST_PATCH_PROJECTION_INVALID",
                    "Patch projection must map patch length P to model depth D",
                    patch_projection.node_id,
                )
            )
        reshape = nodes[f"{prefix}.channel_reshape"]
        if reshape.attributes.get("transform") != "[B,C,Np,D] -> [BC,Np,D]":
            diagnostics.append(
                _diagnostic(
                    "PATCHTST_CHANNEL_INDEPENDENCE_INVALID",
                    "PatchTST must fold batch and channel before its shared encoder",
                    reshape.node_id,
                )
            )
        flatten = nodes[f"{prefix}.flatten"]
        head = nodes[f"{prefix}.head_linear"]
        if flatten.attributes.get("transform") != "[B,C,D,Np] -> [B,C,D*Np]":
            diagnostics.append(
                _diagnostic(
                    "PATCHTST_HEAD_FLATTEN_INVALID",
                    "PatchTST head must flatten D times Np",
                    flatten.node_id,
                )
            )
        if head.attributes.get("in_axis") != "D*Np" or head.attributes.get("out_axis") != "S":
            diagnostics.append(
                _diagnostic(
                    "PATCHTST_HEAD_LINEAR_INVALID",
                    "PatchTST head Linear must map D*Np to prediction length S",
                    head.node_id,
                )
            )
        encoder = nodes[f"{prefix}.encoder"]
        if encoder.attributes.get("residual_attention") is not residual_attention:
            diagnostics.append(
                _diagnostic(
                    "PATCHTST_RESIDUAL_ATTENTION_INVALID",
                    "Encoder residual attention must follow its resolved predicate",
                    encoder.node_id,
                )
            )
        if encoder.attributes.get("norm") != norm:
            diagnostics.append(
                _diagnostic(
                    "PATCHTST_NORM_INVALID",
                    "Encoder norm must match the resolved constructor value",
                    encoder.node_id,
                )
            )
        require_input(
            f"{prefix}.patch_projection",
            f"{prefix}.unfold",
            "PATCHTST_PATCH_FLOW_INVALID",
        )
        require_input(
            f"{prefix}.channel_reshape",
            f"{prefix}.patch_projection",
            "PATCHTST_CHANNEL_FLOW_INVALID",
        )
        require_input(
            f"{prefix}.position_add",
            f"{prefix}.position",
            "PATCHTST_POSITION_ENCODING_INVALID",
        )
        require_input(
            f"{prefix}.position_add",
            f"{prefix}.channel_reshape",
            "PATCHTST_POSITION_ENCODING_INVALID",
        )
        require_input(
            f"{prefix}.head_linear",
            f"{prefix}.flatten",
            "PATCHTST_HEAD_FLOW_INVALID",
        )
        revin_nodes = {f"{prefix}.revin_norm", f"{prefix}.revin_denorm"}
        if revin and not revin_nodes <= nodes.keys():
            diagnostics.append(
                _diagnostic(
                    "PATCHTST_REVIN_PATH_INVALID",
                    f"{lane} lane requires RevIN norm and denorm",
                )
            )
        if not revin and revin_nodes & nodes.keys():
            diagnostics.append(
                _diagnostic(
                    "PATCHTST_REVIN_PREDICATE_INVALID",
                    f"{lane} lane has an inactive RevIN path",
                )
            )
        padding_node = f"{prefix}.end_padding"
        if end_padding != (padding_node in nodes):
            diagnostics.append(
                _diagnostic(
                    "PATCHTST_PADDING_PREDICATE_INVALID",
                    f"{lane} end padding must follow padding_patch",
                )
            )
        if not any(repeat.repeat_id == f"repeat:{lane}.encoder-layers" for repeat in ir.repeats):
            diagnostics.append(
                _diagnostic(
                    "PATCHTST_REPEAT_MISSING",
                    f"{lane} encoder layer repeat is missing",
                )
            )

    if decomposition and "node:decomposition_add" in nodes:
        for lane in lanes:
            producer = (
                f"node:{lane}.revin_denorm" if revin else f"node:{lane}.head_linear"
            )
            require_input(
                "node:decomposition_add",
                producer,
                "PATCHTST_DECOMPOSITION_MERGE_INVALID",
            )
    output_tensor = next((tensor for tensor in ir.tensors if tensor.role == "forecast"), None)
    if output_tensor is None or output_tensor.symbolic_shape != "[B,S,C]":
        diagnostics.append(
            _diagnostic(
                "PATCHTST_OUTPUT_SHAPE_INVALID",
                "PatchTST forecast must have symbolic shape [B,S,C]",
            )
        )
    return diagnostics


def _timemixer_diagnostics(ir: ArchitectureIR) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    nodes = {node.node_id: node for node in ir.nodes}
    incoming: dict[str, set[str]] = defaultdict(set)
    for edge in ir.edges:
        incoming[edge.consumer_id].add(edge.producer_id)
    predicates = {predicate.predicate_id: predicate for predicate in ir.config_predicates}
    required_predicates = {
        "predicate:down-sampling-layers",
        "predicate:down-sampling-method",
        "predicate:channel-independence",
        "predicate:decomp-method",
        "predicate:use-norm",
    }
    for predicate_id in sorted(required_predicates - predicates.keys()):
        diagnostics.append(
            _diagnostic(
                "TIMEMIXER_PREDICATE_MISSING",
                f"TimeMixer requires {predicate_id}",
            )
        )
    required = {
        "node:input.x_enc",
        "node:season.bottom_up",
        "node:trend.top_down",
        "node:forecast.stack",
        "node:forecast.sum",
        "node:denormalize",
        "node:output.forecast",
    }
    for node_id in sorted(required - nodes.keys()):
        diagnostics.append(
            _diagnostic("TIMEMIXER_NODE_MISSING", f"TimeMixer requires {node_id}")
        )
    if diagnostics:
        return diagnostics

    scale_count = int(predicates["predicate:down-sampling-layers"].resolved_value) + 1
    channel_independent = (
        int(predicates["predicate:channel-independence"].resolved_value) == 1
    )
    decomp_method = predicates["predicate:decomp-method"].resolved_value
    season = nodes["node:season.bottom_up"]
    trend = nodes["node:trend.top_down"]
    if season.attributes.get("direction") != "high-resolution-to-low-resolution":
        diagnostics.append(
            _diagnostic(
                "TIMEMIXER_SEASON_DIRECTION_INVALID",
                "Seasonal mixing must proceed from high to low resolution",
                season.node_id,
            )
        )
    if trend.attributes.get("direction") != "low-resolution-to-high-resolution":
        diagnostics.append(
            _diagnostic(
                "TIMEMIXER_TREND_DIRECTION_INVALID",
                "Trend mixing must proceed from low to high resolution",
                trend.node_id,
            )
        )
    if any(
        "conv" in node.semantic_name.lower()
        and any(label in node.semantic_name.lower() for label in ("short", "mid", "long"))
        for node in ir.nodes
    ):
        diagnostics.append(
            _diagnostic(
                "TIMEMIXER_FICTIONAL_BRANCH_INVALID",
                "The selected source has no short/mid/long Conv mixer branches",
            )
        )

    def require_input(target: str, source: str, code: str) -> None:
        if target not in incoming or source not in incoming[target]:
            diagnostics.append(_diagnostic(code, f"{target} must consume {source}", target))

    for scale in range(scale_count):
        prefix = f"node:scale.{scale}"
        required_scale = {
            f"{prefix}.normalize",
            f"{prefix}.embedding",
            f"{prefix}.decomposition",
            f"{prefix}.mix_add",
            f"{prefix}.predictor",
            f"{prefix}.projection",
        }
        if channel_independent:
            required_scale.add(f"{prefix}.channel_reshape")
            required_scale.add(f"{prefix}.mark_repeat")
            required_scale.add(f"{prefix}.restore_forecast")
        for node_id in sorted(required_scale - nodes.keys()):
            diagnostics.append(
                _diagnostic(
                    "TIMEMIXER_SCALE_NODE_MISSING",
                    f"Scale {scale} requires {node_id}",
                )
            )
        if required_scale - nodes.keys():
            continue
        embedding = nodes[f"{prefix}.embedding"]
        if embedding.attributes.get("position_embedding_used") is not False:
            diagnostics.append(
                _diagnostic(
                    "TIMEMIXER_POSITION_EMBEDDING_INVALID",
                    "TimeMixer must use DataEmbedding_wo_pos",
                    embedding.node_id,
                )
            )
        decomposition = nodes[f"{prefix}.decomposition"]
        if decomposition.attributes.get("method") != decomp_method:
            diagnostics.append(
                _diagnostic(
                    "TIMEMIXER_DECOMPOSITION_INVALID",
                    "Every scale decomposition must follow decomp_method",
                    decomposition.node_id,
                )
            )
        require_input(
            "node:season.bottom_up",
            f"{prefix}.decomposition",
            "TIMEMIXER_SEASON_INPUT_INVALID",
        )
        require_input(
            "node:trend.top_down",
            f"{prefix}.decomposition",
            "TIMEMIXER_TREND_INPUT_INVALID",
        )
        require_input(
            f"{prefix}.mix_add",
            "node:season.bottom_up",
            "TIMEMIXER_SCALE_MERGE_INVALID",
        )
        require_input(
            f"{prefix}.mix_add",
            "node:trend.top_down",
            "TIMEMIXER_SCALE_MERGE_INVALID",
        )
        require_input(
            f"{prefix}.predictor",
            f"{prefix}.mix_add",
            "TIMEMIXER_PREDICTOR_INVALID",
        )
        require_input(
            f"{prefix}.projection",
            f"{prefix}.predictor",
            "TIMEMIXER_PROJECTION_INVALID",
        )
        forecast_source = f"{prefix}.projection"
        if channel_independent:
            require_input(
                f"{prefix}.embedding",
                f"{prefix}.mark_repeat",
                "TIMEMIXER_TEMPORAL_FEATURE_REPEAT_INVALID",
            )
            require_input(
                f"{prefix}.restore_forecast",
                f"{prefix}.projection",
                "TIMEMIXER_CHANNEL_RESTORE_INVALID",
            )
            forecast_source = f"{prefix}.restore_forecast"
        require_input(
            "node:forecast.stack",
            forecast_source,
            "TIMEMIXER_SCALE_FORECAST_MISSING",
        )
    for scale in range(1, scale_count):
        if f"node:scale.{scale}.downsample" not in nodes:
            diagnostics.append(
                _diagnostic(
                    "TIMEMIXER_DOWNSAMPLING_INVALID",
                    f"Scale {scale} downsampling node is missing",
                )
            )
    require_input(
        "node:forecast.sum",
        "node:forecast.stack",
        "TIMEMIXER_FORECAST_REDUCTION_INVALID",
    )
    require_input(
        "node:denormalize",
        "node:forecast.sum",
        "TIMEMIXER_DENORMALIZATION_INVALID",
    )
    if not any(repeat.repeat_id == "repeat:pdm-blocks" for repeat in ir.repeats):
        diagnostics.append(
            _diagnostic("TIMEMIXER_PDM_REPEAT_MISSING", "PDM block repeat is missing")
        )
    if not any(
        repeat.repeat_id == "repeat:scales" and repeat.count == scale_count
        for repeat in ir.repeats
    ):
        diagnostics.append(
            _diagnostic(
                "TIMEMIXER_SCALE_REPEAT_INVALID",
                "Scale repeat count must match the downsampling list",
            )
        )
    output_tensor = next((tensor for tensor in ir.tensors if tensor.role == "forecast"), None)
    if output_tensor is None or output_tensor.symbolic_shape != "[B,S,C]":
        diagnostics.append(
            _diagnostic(
                "TIMEMIXER_OUTPUT_SHAPE_INVALID",
                "TimeMixer forecast must have symbolic shape [B,S,C]",
            )
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

    is_transformer = any(
        node.attributes.get("architecture_profile") == "transformer-l3" for node in ir.nodes
    )
    transformer = _transformer_l3_diagnostics(ir) if is_transformer else []
    is_autoformer = any(
        node.attributes.get("architecture_profile") == "autoformer" for node in ir.nodes
    )
    autoformer = _autoformer_diagnostics(ir) if is_autoformer else []
    is_itransformer = any(
        node.attributes.get("architecture_profile") == "itransformer" for node in ir.nodes
    )
    itransformer = _itransformer_diagnostics(ir) if is_itransformer else []
    is_patchtst = any(
        node.attributes.get("architecture_profile") == "patchtst" for node in ir.nodes
    )
    patchtst = _patchtst_diagnostics(ir) if is_patchtst else []
    is_timemixer = any(
        node.attributes.get("architecture_profile") == "timemixer" for node in ir.nodes
    )
    timemixer = _timemixer_diagnostics(ir) if is_timemixer else []
    diagnostics = [
        *structural,
        *evidence_diagnostics,
        *transformer,
        *autoformer,
        *itransformer,
        *patchtst,
        *timemixer,
    ]
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
    if is_autoformer:
        gates.append(
            GateResult(
                gate="B-autoformer",
                status="failed" if autoformer else "passed",
                message=(
                    f"{len(autoformer)} Autoformer source contract issue(s)."
                    if autoformer
                    else "Embedding, AutoCorrelation, decomposition, trend/season, and mask semantics are source-backed."
                ),
            )
        )
    if is_itransformer:
        gates.append(
            GateResult(
                gate="B-itransformer",
                status="failed" if itransformer else "passed",
                message=(
                    f"{len(itransformer)} iTransformer source contract issue(s)."
                    if itransformer
                    else "Inverted tokens, encoder-only flow, predicates, covariate trimming, and forecast shape are source-backed."
                ),
            )
        )
    if is_patchtst:
        gates.append(
            GateResult(
                gate="B-patchtst",
                status="failed" if patchtst else "passed",
                message=(
                    f"{len(patchtst)} PatchTST source contract issue(s)."
                    if patchtst
                    else "Patching, channel independence, positional encoding, predicates, true head, and decomposition are source-backed."
                ),
            )
        )
    if is_timemixer:
        gates.append(
            GateResult(
                gate="B-timemixer",
                status="failed" if timemixer else "passed",
                message=(
                    f"{len(timemixer)} TimeMixer source contract issue(s)."
                    if timemixer
                    else "Multiscale normalization, decomposition, bidirectional mixing, per-scale forecasts, and reduction are source-backed."
                ),
            )
        )
    gates.append(
        GateResult(
            gate="C-publication-compilation",
            status="skipped",
            message="Run render or validate --quality publication to execute publication gates.",
        )
    )
    return gates, diagnostics
