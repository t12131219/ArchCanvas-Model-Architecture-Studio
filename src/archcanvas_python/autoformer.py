from __future__ import annotations

import ast
import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from archcanvas_core.models import (
    ArchitectureEdge,
    ArchitectureIR,
    ArchitectureNode,
    Confidence,
    ConfigPredicate,
    DiscrepancyRecord,
    EdgeType,
    EvidenceKind,
    EvidenceRecord,
    FanoutRelation,
    NodeKind,
    Port,
    Repeat,
    RepeatKind,
    SourceFile,
    SourceSnapshot,
    SourceSpan,
    TensorValue,
)

from .analyzer import ANALYZER_VERSION, AnalysisBundle, AnalysisError

SOURCE_PATHS = (
    "models/Autoformer.py",
    "layers/Autoformer_EncDec.py",
    "layers/AutoCorrelation.py",
    "layers/Embed.py",
)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _identifier(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9._:-]+", "-", value.lower()).strip("-.")
    return normalized if normalized and normalized[0].isalpha() else f"id-{normalized or 'unknown'}"


def _call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = _call_name(node.value)
        return f"{prefix}.{node.attr}" if prefix else node.attr
    return "call"


@dataclass(frozen=True)
class _SourceDocument:
    path: str
    data: bytes
    digest: str
    tree: ast.Module

    def method(self, class_name: str, method_name: str) -> ast.FunctionDef:
        class_node = next(
            (
                node
                for node in self.tree.body
                if isinstance(node, ast.ClassDef) and node.name == class_name
            ),
            None,
        )
        if class_node is None:
            raise AnalysisError(
                "AUTOFORMER_SOURCE_CONTRACT",
                f"{self.path} is missing class {class_name}",
            )
        method = next(
            (
                node
                for node in class_node.body
                if isinstance(node, ast.FunctionDef) and node.name == method_name
            ),
            None,
        )
        if method is None:
            raise AnalysisError(
                "AUTOFORMER_SOURCE_CONTRACT",
                f"{self.path}:{class_name} is missing {method_name}",
            )
        return method


@dataclass
class _NodeSpec:
    node_id: str
    semantic_name: str
    kind: NodeKind
    parent_id: str | None
    evidence_ids: list[str]
    attributes: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class _Connection:
    producer_id: str
    role: str
    consumer_id: str
    edge_type: EdgeType
    shape: str
    evidence_ids: list[str]


def _shape_axes(shape: str) -> list[str]:
    names = {
        "B": "batch",
        "S": "source_length",
        "Ld": "decoder_length",
        "P": "prediction_length",
        "D": "model_depth",
        "C": "channel",
        "M": "time_feature",
        "H": "head",
        "Dh": "head_depth",
        "F": "frequency",
        "K": "top_k_delay",
    }
    if not shape.startswith("[") or not shape.endswith("]"):
        return []
    return [names.get(part.strip(), "unknown") for part in shape[1:-1].split(",")]


class _GraphBuilder:
    def __init__(self, predicate: str) -> None:
        self.predicate = predicate
        self.nodes: dict[str, _NodeSpec] = {}
        self.connections: list[_Connection] = []

    def node(
        self,
        node_id: str,
        semantic_name: str,
        evidence_ids: list[str],
        *,
        kind: NodeKind = NodeKind.OPERATOR,
        parent_id: str | None = "node:autoformer",
        **attributes: Any,
    ) -> str:
        self.nodes[node_id] = _NodeSpec(
            node_id=node_id,
            semantic_name=semantic_name,
            kind=kind,
            parent_id=parent_id,
            evidence_ids=evidence_ids,
            attributes=attributes,
        )
        return node_id

    def connect(
        self,
        producer_id: str,
        role: str,
        consumer_id: str,
        shape: str,
        evidence_ids: list[str],
        edge_type: EdgeType = EdgeType.MAIN,
    ) -> None:
        self.connections.append(
            _Connection(
                producer_id=producer_id,
                role=role,
                consumer_id=consumer_id,
                edge_type=edge_type,
                shape=shape,
                evidence_ids=evidence_ids,
            )
        )

    def build(
        self,
    ) -> tuple[
        list[ArchitectureNode],
        list[TensorValue],
        list[ArchitectureEdge],
        list[FanoutRelation],
    ]:
        input_ports: dict[str, list[Port]] = {node_id: [] for node_id in self.nodes}
        output_ports: dict[str, dict[str, Port]] = {node_id: {} for node_id in self.nodes}
        tensor_data: dict[str, dict[str, Any]] = {}
        edges: list[ArchitectureEdge] = []
        for index, connection in enumerate(self.connections):
            producer_key = connection.producer_id.removeprefix("node:")
            consumer_key = connection.consumer_id.removeprefix("node:")
            producer_port = output_ports[connection.producer_id].setdefault(
                connection.role,
                Port(
                    port_id=f"port:{producer_key}.{_identifier(connection.role)}",
                    name=connection.role,
                    direction="output",
                    role=connection.role,
                ),
            )
            consumer_port = Port(
                port_id=f"port:{consumer_key}.in{len(input_ports[connection.consumer_id])}",
                name=connection.role,
                direction="input",
                role=connection.role,
            )
            input_ports[connection.consumer_id].append(consumer_port)
            tensor_id = f"tensor:{_identifier(connection.role)}"
            current = tensor_data.get(tensor_id)
            if current and current["producer_id"] != connection.producer_id:
                raise AnalysisError(
                    "AUTOFORMER_TENSOR_IDENTITY",
                    f"tensor role {connection.role} has multiple producers",
                )
            if current is None:
                current = {
                    "producer_id": connection.producer_id,
                    "producer_port": producer_port.port_id,
                    "consumer_ids": [],
                    "shape": connection.shape,
                    "evidence_ids": [],
                }
                tensor_data[tensor_id] = current
            current["consumer_ids"].append(connection.consumer_id)
            current["evidence_ids"] = list(
                dict.fromkeys([*current["evidence_ids"], *connection.evidence_ids])
            )
            edges.append(
                ArchitectureEdge(
                    edge_id=f"edge:{producer_key}:{consumer_key}:{index}",
                    tensor_id=tensor_id,
                    producer_id=connection.producer_id,
                    producer_port=producer_port.port_id,
                    consumer_id=connection.consumer_id,
                    consumer_port=consumer_port.port_id,
                    role=connection.role,
                    edge_type=connection.edge_type,
                    symbolic_shape=connection.shape,
                    semantic_axes=_shape_axes(connection.shape),
                    evidence_ids=connection.evidence_ids,
                    confidence=Confidence.EXACT,
                    execution_predicate=self.predicate,
                )
            )

        children: dict[str, list[str]] = {node_id: [] for node_id in self.nodes}
        for spec in self.nodes.values():
            if spec.parent_id:
                children[spec.parent_id].append(spec.node_id)
        nodes = [
            ArchitectureNode(
                node_id=spec.node_id,
                kind=spec.kind,
                semantic_name=spec.semantic_name,
                source_symbol=spec.attributes.get("source_symbol"),
                parent_id=spec.parent_id,
                children=children[spec.node_id],
                input_ports=input_ports[spec.node_id],
                output_ports=list(output_ports[spec.node_id].values()),
                parameter_identity="independent-module-parameters"
                if spec.kind is NodeKind.OPERATOR
                else "not-applicable",
                execution_predicate=self.predicate,
                evidence_ids=spec.evidence_ids,
                confidence=Confidence.EXACT,
                attributes={
                    key: value for key, value in spec.attributes.items() if key != "source_symbol"
                },
            )
            for spec in self.nodes.values()
        ]
        tensors = [
            TensorValue(
                tensor_id=tensor_id,
                role=tensor_id.removeprefix("tensor:"),
                producer_id=data["producer_id"],
                producer_port=data["producer_port"],
                consumer_ids=data["consumer_ids"],
                symbolic_shape=data["shape"],
                semantic_axes=_shape_axes(data["shape"]),
                dtype="unknown",
                provenance="source+config",
                confidence=Confidence.EXACT,
                evidence_ids=data["evidence_ids"],
            )
            for tensor_id, data in tensor_data.items()
        ]
        fanouts = [
            FanoutRelation(
                relation_id=f"fanout:{tensor.tensor_id.removeprefix('tensor:')}",
                tensor_id=tensor.tensor_id,
                producer_id=tensor.producer_id,
                consumer_ids=tensor.consumer_ids,
                evidence_ids=tensor.evidence_ids,
            )
            for tensor in tensors
            if len(tensor.consumer_ids) > 1
        ]
        return nodes, tensors, edges, fanouts


def _load_sources(project: Path) -> dict[str, _SourceDocument]:
    provenance_path = project / "provenance.json"
    try:
        provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise AnalysisError("AUTOFORMER_PROVENANCE_INVALID", str(error)) from error
    expected = provenance.get("members", {})
    documents: dict[str, _SourceDocument] = {}
    for relative_path in SOURCE_PATHS:
        path = project / relative_path
        try:
            data = path.read_bytes()
            tree = ast.parse(data, filename=str(path))
        except (OSError, SyntaxError) as error:
            raise AnalysisError("AUTOFORMER_SOURCE_INVALID", str(error)) from error
        digest = _sha256(data)
        if expected.get(relative_path) != digest:
            raise AnalysisError(
                "AUTOFORMER_SOURCE_STALE",
                f"{relative_path} does not match provenance.json",
            )
        documents[relative_path] = _SourceDocument(relative_path, data, digest, tree)
    return documents


def _method_calls(method: ast.FunctionDef) -> set[str]:
    return {_call_name(node.func) for node in ast.walk(method) if isinstance(node, ast.Call)}


def _assert_calls(
    document: _SourceDocument,
    class_name: str,
    method_name: str,
    required: set[str],
) -> ast.FunctionDef:
    method = document.method(class_name, method_name)
    missing = required - _method_calls(method)
    if missing:
        raise AnalysisError(
            "AUTOFORMER_SOURCE_CONTRACT",
            f"{document.path}:{class_name}.{method_name} is missing calls {sorted(missing)}",
        )
    return method


def _assert_source_contract(documents: dict[str, _SourceDocument]) -> dict[str, ast.FunctionDef]:
    model = documents["models/Autoformer.py"]
    embed = documents["layers/Embed.py"]
    correlation = documents["layers/AutoCorrelation.py"]
    blocks = documents["layers/Autoformer_EncDec.py"]
    methods = {
        "model": _assert_calls(
            model,
            "Model",
            "forward",
            {
                "self.decomp",
                "self.enc_embedding",
                "self.encoder",
                "self.dec_embedding",
                "self.decoder",
            },
        ),
        "embedding": _assert_calls(
            embed,
            "DataEmbedding_wo_pos",
            "forward",
            {"self.value_embedding", "self.temporal_embedding", "self.dropout"},
        ),
        "correlation": _assert_calls(
            correlation,
            "AutoCorrelation",
            "forward",
            {"torch.fft.rfft", "torch.fft.irfft", "self.time_delay_agg_inference"},
        ),
        "delay": _assert_calls(
            correlation,
            "AutoCorrelation",
            "time_delay_agg_inference",
            {"torch.topk", "torch.softmax", "torch.gather"},
        ),
        "projection": _assert_calls(
            correlation,
            "AutoCorrelationLayer",
            "forward",
            {
                "self.query_projection",
                "self.key_projection",
                "self.value_projection",
                "self.inner_correlation",
                "self.out_projection",
            },
        ),
        "encoder": _assert_calls(
            blocks,
            "EncoderLayer",
            "forward",
            {"self.attention", "self.decomp1", "self.decomp2"},
        ),
        "decoder_layer": _assert_calls(
            blocks,
            "DecoderLayer",
            "forward",
            {
                "self.self_attention",
                "self.cross_attention",
                "self.decomp1",
                "self.decomp2",
                "self.decomp3",
                "self.projection",
            },
        ),
        "decoder": _assert_calls(blocks, "Decoder", "forward", set()),
    }
    embed_names = {
        node.attr for node in ast.walk(methods["embedding"]) if isinstance(node, ast.Attribute)
    }
    if "position_embedding" in embed_names:
        raise AnalysisError(
            "AUTOFORMER_POSITION_EMBEDDING_ACTIVE",
            "DataEmbedding_wo_pos.forward unexpectedly uses position_embedding",
        )
    correlation_loaded = {
        node.id for node in ast.walk(methods["correlation"]) if isinstance(node, ast.Name)
    }
    if "attn_mask" in correlation_loaded:
        raise AnalysisError(
            "AUTOFORMER_MASK_BEHAVIOR_CHANGED",
            "AutoCorrelation.forward now consumes attn_mask; update the profile",
        )
    decoder_decompositions = {
        node.attr
        for node in ast.walk(methods["decoder_layer"])
        if isinstance(node, ast.Attribute) and node.attr.startswith("decomp")
    }
    if decoder_decompositions != {"decomp1", "decomp2", "decomp3"}:
        raise AnalysisError(
            "AUTOFORMER_DECOMPOSITION_CHANGED",
            "DecoderLayer must contain exactly decomp1, decomp2, and decomp3",
        )
    return methods


def analyze_autoformer(
    project: Path,
    entrypoint: str,
    task: str,
    execution_mode: str,
    config: dict[str, Any],
    config_bytes: bytes,
    config_path: Path | None,
) -> AnalysisBundle:
    if entrypoint != "models.Autoformer:Model":
        raise AnalysisError(
            "AUTOFORMER_ENTRYPOINT_INVALID",
            "Autoformer profile requires entrypoint models.Autoformer:Model",
        )
    documents = _load_sources(project)
    methods = _assert_source_contract(documents)
    combined_digest = _sha256(
        "".join(document.digest for document in documents.values()).encode("ascii")
    )
    config_digest = _sha256(config_bytes)
    snapshot_seed = (
        f"{combined_digest}:{config_digest}:{entrypoint}:{task}:{execution_mode}".encode()
    )
    resolved_config_path = None
    if config_path:
        resolved = config_path.resolve()
        resolved_config_path = (
            resolved.relative_to(project).as_posix()
            if resolved.is_relative_to(project)
            else str(resolved)
        )
    snapshot = SourceSnapshot(
        snapshot_id=f"snapshot:{_sha256(snapshot_seed)[:16]}",
        project_root=str(project),
        revision=f"content:{combined_digest}",
        entrypoint=entrypoint,
        task=task,
        execution_mode=execution_mode,
        framework="pytorch",
        adapter_version=ANALYZER_VERSION,
        config_digest=config_digest,
        config_path=resolved_config_path,
        resolved_config=config,
        source_files=[
            SourceFile(path=document.path, sha256=document.digest)
            for document in documents.values()
        ],
    )
    predicate = f"task={task} && mode={execution_mode}"
    evidence: list[EvidenceRecord] = []
    config_evidence: dict[str, str] = {}
    for key in sorted(config):
        evidence_id = f"evidence:config.{_identifier(key)}"
        config_evidence[key] = evidence_id
        evidence.append(
            EvidenceRecord(
                evidence_id=evidence_id,
                kind=EvidenceKind.CONFIG,
                path=resolved_config_path,
                symbol=key,
                file_sha256=config_digest,
                revision=f"content:{config_digest}",
                claim=f"Resolved config provides {key}",
                confidence=Confidence.EXACT,
                execution_predicate=predicate,
            )
        )

    evidence_map: dict[str, str] = {}
    method_sources = {
        "model": "models/Autoformer.py",
        "embedding": "layers/Embed.py",
        "correlation": "layers/AutoCorrelation.py",
        "delay": "layers/AutoCorrelation.py",
        "projection": "layers/AutoCorrelation.py",
        "encoder": "layers/Autoformer_EncDec.py",
        "decoder_layer": "layers/Autoformer_EncDec.py",
        "decoder": "layers/Autoformer_EncDec.py",
    }
    for key, method in methods.items():
        document = documents[method_sources[key]]
        evidence_id = f"evidence:autoformer.{key}"
        evidence_map[key] = evidence_id
        evidence.append(
            EvidenceRecord(
                evidence_id=evidence_id,
                kind=EvidenceKind.SOURCE,
                path=document.path,
                symbol=f"{method.name}",
                span=SourceSpan(
                    start_line=method.lineno,
                    end_line=getattr(method, "end_lineno", method.lineno),
                ),
                file_sha256=document.digest,
                revision=snapshot.revision,
                claim=f"Autoformer source contract: {key}",
                confidence=Confidence.EXACT,
                execution_predicate=predicate,
            )
        )

    graph = _build_autoformer_graph(config, predicate, evidence_map)
    nodes, tensors, edges, fanouts = graph.build()
    repeats = [
        Repeat(
            repeat_id="repeat:encoder.layers",
            kind=RepeatKind.STACK,
            member_node_ids=["node:encoder.layer"],
            count=int(config["e_layers"]),
            parameter_identity="independent-per-layer",
            evidence_ids=[evidence_map["model"], config_evidence["e_layers"]],
        ),
        Repeat(
            repeat_id="repeat:decoder.layers",
            kind=RepeatKind.STACK,
            member_node_ids=["node:decoder.layer"],
            count=int(config["d_layers"]),
            parameter_identity="independent-per-layer",
            evidence_ids=[evidence_map["model"], config_evidence["d_layers"]],
        ),
    ]
    predicates = [
        ConfigPredicate(
            predicate_id="predicate:autoformer.output-attention",
            expression="output_attention == false",
            resolved_value=bool(config["output_attention"]),
            affected_ids=["node:output.forecast"],
            evidence_ids=[config_evidence["output_attention"], evidence_map["model"]],
        ),
        ConfigPredicate(
            predicate_id="predicate:autoformer.eval-delay-path",
            expression="execution_mode == eval",
            resolved_value=execution_mode == "eval",
            affected_ids=["node:encoder.delay_aggregate"],
            evidence_ids=[evidence_map["correlation"], evidence_map["delay"]],
        ),
    ]
    architecture = ArchitectureIR(
        architecture_id=f"architecture:{_sha256(snapshot_seed)[:16]}",
        source_snapshot_id=snapshot.snapshot_id,
        framework="pytorch",
        entrypoint=entrypoint,
        nodes=nodes,
        tensors=tensors,
        edges=edges,
        fanouts=fanouts,
        repeats=repeats,
        config_predicates=predicates,
    )
    discrepancies = _autoformer_discrepancies(evidence_map)
    return AnalysisBundle(
        snapshot=snapshot,
        evidence=evidence,
        architecture=architecture,
        discrepancies=discrepancies,
    )


def _build_autoformer_graph(
    config: dict[str, Any],
    predicate: str,
    ev: dict[str, str],
) -> _GraphBuilder:
    graph = _GraphBuilder(predicate)
    model_ev = [ev["model"]]
    embed_ev = [ev["model"], ev["embedding"]]
    encoder_ev = [ev["encoder"]]
    decoder_ev = [ev["decoder_layer"]]
    corr_ev = [ev["projection"], ev["correlation"], ev["delay"]]

    graph.node(
        "node:autoformer",
        "Autoformer",
        model_ev,
        kind=NodeKind.MODULE_CONTAINER,
        parent_id=None,
        source_symbol="Model",
        architecture_profile="autoformer",
    )
    for container_id, name, parent, evidence_ids in (
        ("node:encoder", "Encoder", "node:autoformer", encoder_ev),
        ("node:encoder.layer", "Encoder Layer", "node:encoder", encoder_ev),
        (
            "node:encoder.autocorrelation",
            "Encoder AutoCorrelation",
            "node:encoder.layer",
            corr_ev,
        ),
        ("node:decoder", "Decoder", "node:autoformer", decoder_ev),
        ("node:decoder.layer", "Decoder Layer", "node:decoder", decoder_ev),
        (
            "node:decoder.self_autocorrelation",
            "Decoder Self AutoCorrelation",
            "node:decoder.layer",
            corr_ev,
        ),
        (
            "node:decoder.cross_autocorrelation",
            "Decoder Cross AutoCorrelation",
            "node:decoder.layer",
            corr_ev,
        ),
    ):
        graph.node(
            container_id,
            name,
            evidence_ids,
            kind=NodeKind.MODULE_CONTAINER,
            parent_id=parent,
        )

    for name in (
        "x_enc",
        "x_mark_enc",
        "x_dec",
        "x_mark_dec",
        "enc_self_mask",
        "dec_self_mask",
        "dec_enc_mask",
    ):
        graph.node(
            f"node:input.{name}",
            name,
            model_ev,
            kind=NodeKind.INPUT_OUTPUT,
            io="input",
            assigned_symbol=name,
            unused=name.endswith("mask"),
        )

    def op(
        node_id: str,
        name: str,
        evidence_ids: list[str],
        parent: str = "node:autoformer",
        kind: NodeKind = NodeKind.OPERATOR,
        **attributes: Any,
    ) -> str:
        return graph.node(
            node_id,
            name,
            evidence_ids,
            kind=kind,
            parent_id=parent,
            assigned_symbol=node_id.removeprefix("node:").replace(".", "_"),
            **attributes,
        )

    mean = op("node:mean", "Prediction mean seed", model_ev)
    zeros = op("node:zeros", "Seasonal zero seed", model_ev)
    initial_decomp = op("node:initial_decomp", "Initial series decomposition", model_ev)
    trend_seed = op(
        "node:trend_seed", "Trend seed concat", model_ev, kind=NodeKind.MERGE_EVENT, merge="concat"
    )
    seasonal_seed = op(
        "node:seasonal_seed",
        "Seasonal seed concat",
        model_ev,
        kind=NodeKind.MERGE_EVENT,
        merge="concat",
    )
    enc_embedding = op(
        "node:enc_embedding",
        "DataEmbedding_wo_pos",
        embed_ev,
        embedding="value+temporal",
        position_embedding_used=False,
    )
    graph.connect("node:input.x_enc", "x_enc", mean, "[B,S,C]", model_ev)
    graph.connect("node:input.x_dec", "x_dec_shape", zeros, "[B,Ld,C]", model_ev)
    graph.connect("node:input.x_enc", "x_enc", initial_decomp, "[B,S,C]", model_ev)
    graph.connect(initial_decomp, "trend_base", trend_seed, "[B,S,C]", model_ev)
    graph.connect(mean, "mean_seed", trend_seed, "[B,P,C]", model_ev)
    graph.connect(initial_decomp, "seasonal_base", seasonal_seed, "[B,S,C]", model_ev)
    graph.connect(zeros, "zero_seed", seasonal_seed, "[B,P,C]", model_ev)
    graph.connect("node:input.x_enc", "x_enc", enc_embedding, "[B,S,C]", embed_ev)
    graph.connect("node:input.x_mark_enc", "x_mark_enc", enc_embedding, "[B,S,M]", embed_ev)

    enc_q = op("node:encoder.q_projection", "Q projection", corr_ev, "node:encoder.autocorrelation")
    enc_k = op("node:encoder.k_projection", "K projection", corr_ev, "node:encoder.autocorrelation")
    enc_v = op("node:encoder.v_projection", "V projection", corr_ev, "node:encoder.autocorrelation")
    for target, role in ((enc_q, "enc_q"), (enc_k, "enc_k"), (enc_v, "enc_v")):
        graph.connect(enc_embedding, "enc_embedding", target, "[B,S,D]", corr_ev)
    q_fft = op("node:encoder.q_fft", "RFFT(Q)", corr_ev, "node:encoder.autocorrelation")
    k_fft = op("node:encoder.k_fft", "RFFT(K)", corr_ev, "node:encoder.autocorrelation")
    spectral = op(
        "node:encoder.spectral_product",
        "Q_fft x conj(K_fft)",
        corr_ev,
        "node:encoder.autocorrelation",
        kind=NodeKind.MERGE_EVENT,
        merge="multiply",
    )
    irfft = op("node:encoder.irfft", "IRFFT correlation", corr_ev, "node:encoder.autocorrelation")
    top_k = op("node:encoder.top_k", "Top-k delays", corr_ev, "node:encoder.autocorrelation")
    delay = op(
        "node:encoder.delay_aggregate",
        "Time-delay aggregation",
        corr_ev,
        "node:encoder.autocorrelation",
        mode="inference",
    )
    enc_out = op(
        "node:encoder.out_projection",
        "Output projection",
        corr_ev,
        "node:encoder.autocorrelation",
    )
    graph.connect(enc_q, "enc_q_heads", q_fft, "[B,S,H,Dh]", corr_ev)
    graph.connect(enc_k, "enc_k_heads", k_fft, "[B,S,H,Dh]", corr_ev)
    graph.connect(q_fft, "q_frequency", spectral, "[B,H,Dh,F]", corr_ev)
    graph.connect(k_fft, "k_frequency", spectral, "[B,H,Dh,F]", corr_ev)
    graph.connect(spectral, "spectral_product", irfft, "[B,H,Dh,F]", corr_ev)
    graph.connect(irfft, "correlation", top_k, "[B,H,Dh,S]", corr_ev)
    graph.connect(top_k, "top_k_delays", delay, "[B,K]", corr_ev)
    graph.connect(enc_v, "enc_v_heads", delay, "[B,S,H,Dh]", corr_ev)
    graph.connect(irfft, "correlation", delay, "[B,H,Dh,S]", corr_ev)
    graph.connect(delay, "delay_aggregated", enc_out, "[B,S,H,Dh]", corr_ev)

    enc_residual = op(
        "node:encoder.residual1",
        "Attention residual Add",
        encoder_ev,
        "node:encoder.layer",
        kind=NodeKind.MERGE_EVENT,
        merge="add",
    )
    enc_decomp1 = op(
        "node:encoder.decomp1", "Progressive decomposition 1", encoder_ev, "node:encoder.layer"
    )
    enc_ffn = op("node:encoder.ffn", "Conv1d feature transform", encoder_ev, "node:encoder.layer")
    enc_residual2 = op(
        "node:encoder.residual2",
        "FFN residual Add",
        encoder_ev,
        "node:encoder.layer",
        kind=NodeKind.MERGE_EVENT,
        merge="add",
    )
    enc_decomp2 = op(
        "node:encoder.decomp2", "Progressive decomposition 2", encoder_ev, "node:encoder.layer"
    )
    graph.connect(enc_embedding, "enc_embedding", enc_residual, "[B,S,D]", encoder_ev)
    graph.connect(enc_out, "enc_correlation_out", enc_residual, "[B,S,D]", corr_ev)
    graph.connect(enc_residual, "enc_residual1", enc_decomp1, "[B,S,D]", encoder_ev)
    graph.connect(enc_decomp1, "enc_seasonal1", enc_ffn, "[B,S,D]", encoder_ev)
    graph.connect(enc_decomp1, "enc_seasonal1", enc_residual2, "[B,S,D]", encoder_ev)
    graph.connect(enc_ffn, "enc_ffn", enc_residual2, "[B,S,D]", encoder_ev)
    graph.connect(enc_residual2, "enc_residual2", enc_decomp2, "[B,S,D]", encoder_ev)

    dec_embedding = op(
        "node:dec_embedding",
        "DataEmbedding_wo_pos",
        embed_ev,
        embedding="value+temporal",
        position_embedding_used=False,
    )
    graph.connect(seasonal_seed, "seasonal_init", dec_embedding, "[B,Ld,C]", embed_ev)
    graph.connect("node:input.x_mark_dec", "x_mark_dec", dec_embedding, "[B,Ld,M]", embed_ev)

    self_q = op(
        "node:decoder.self_q_projection",
        "Self Q projection",
        corr_ev,
        "node:decoder.self_autocorrelation",
    )
    self_k = op(
        "node:decoder.self_k_projection",
        "Self K projection",
        corr_ev,
        "node:decoder.self_autocorrelation",
    )
    self_v = op(
        "node:decoder.self_v_projection",
        "Self V projection",
        corr_ev,
        "node:decoder.self_autocorrelation",
    )
    self_corr = op(
        "node:decoder.self_fft_delay",
        "Self FFT correlation + top-k delay aggregation",
        corr_ev,
        "node:decoder.self_autocorrelation",
    )
    for target in (self_q, self_k, self_v):
        graph.connect(dec_embedding, "dec_embedding", target, "[B,Ld,D]", corr_ev)
    graph.connect(self_q, "dec_self_q", self_corr, "[B,Ld,H,Dh]", corr_ev)
    graph.connect(self_k, "dec_self_k", self_corr, "[B,Ld,H,Dh]", corr_ev)
    graph.connect(self_v, "dec_self_v", self_corr, "[B,Ld,H,Dh]", corr_ev)
    self_residual = op(
        "node:decoder.self_residual",
        "Self correlation residual Add",
        decoder_ev,
        "node:decoder.layer",
        kind=NodeKind.MERGE_EVENT,
        merge="add",
    )
    dec_decomp1 = op(
        "node:decoder.decomp1", "Decoder decomposition 1", decoder_ev, "node:decoder.layer"
    )
    graph.connect(dec_embedding, "dec_embedding", self_residual, "[B,Ld,D]", decoder_ev)
    graph.connect(self_corr, "dec_self_correlation", self_residual, "[B,Ld,D]", corr_ev)
    graph.connect(self_residual, "dec_self_residual", dec_decomp1, "[B,Ld,D]", decoder_ev)

    cross_q = op(
        "node:decoder.cross_q_projection",
        "Cross Q projection",
        corr_ev,
        "node:decoder.cross_autocorrelation",
    )
    cross_k = op(
        "node:decoder.cross_k_projection",
        "Cross K projection",
        corr_ev,
        "node:decoder.cross_autocorrelation",
    )
    cross_v = op(
        "node:decoder.cross_v_projection",
        "Cross V projection",
        corr_ev,
        "node:decoder.cross_autocorrelation",
    )
    cross_corr = op(
        "node:decoder.cross_fft_delay",
        "Cross FFT correlation + top-k delay aggregation",
        corr_ev,
        "node:decoder.cross_autocorrelation",
    )
    graph.connect(dec_decomp1, "dec_seasonal1", cross_q, "[B,Ld,D]", corr_ev)
    graph.connect(enc_decomp2, "encoder_memory", cross_k, "[B,S,D]", corr_ev, EdgeType.MEMORY)
    graph.connect(enc_decomp2, "encoder_memory", cross_v, "[B,S,D]", corr_ev, EdgeType.MEMORY)
    graph.connect(cross_q, "dec_cross_q", cross_corr, "[B,Ld,H,Dh]", corr_ev)
    graph.connect(cross_k, "dec_cross_k", cross_corr, "[B,S,H,Dh]", corr_ev)
    graph.connect(cross_v, "dec_cross_v", cross_corr, "[B,S,H,Dh]", corr_ev)
    cross_residual = op(
        "node:decoder.cross_residual",
        "Cross correlation residual Add",
        decoder_ev,
        "node:decoder.layer",
        kind=NodeKind.MERGE_EVENT,
        merge="add",
    )
    dec_decomp2 = op(
        "node:decoder.decomp2", "Decoder decomposition 2", decoder_ev, "node:decoder.layer"
    )
    graph.connect(dec_decomp1, "dec_seasonal1", cross_residual, "[B,Ld,D]", decoder_ev)
    graph.connect(cross_corr, "dec_cross_correlation", cross_residual, "[B,Ld,D]", corr_ev)
    graph.connect(cross_residual, "dec_cross_residual", dec_decomp2, "[B,Ld,D]", decoder_ev)

    dec_ffn = op("node:decoder.ffn", "Conv1d feature transform", decoder_ev, "node:decoder.layer")
    dec_ffn_residual = op(
        "node:decoder.ffn_residual",
        "FFN residual Add",
        decoder_ev,
        "node:decoder.layer",
        kind=NodeKind.MERGE_EVENT,
        merge="add",
    )
    dec_decomp3 = op(
        "node:decoder.decomp3", "Decoder decomposition 3", decoder_ev, "node:decoder.layer"
    )
    graph.connect(dec_decomp2, "dec_seasonal2", dec_ffn, "[B,Ld,D]", decoder_ev)
    graph.connect(dec_decomp2, "dec_seasonal2", dec_ffn_residual, "[B,Ld,D]", decoder_ev)
    graph.connect(dec_ffn, "dec_ffn", dec_ffn_residual, "[B,Ld,D]", decoder_ev)
    graph.connect(dec_ffn_residual, "dec_ffn_residual", dec_decomp3, "[B,Ld,D]", decoder_ev)

    trend_sum = op(
        "node:decoder.trend_residual_sum",
        "Trend residual sum",
        decoder_ev,
        "node:decoder.layer",
        kind=NodeKind.MERGE_EVENT,
        merge="sum",
    )
    trend_projection = op(
        "node:decoder.trend_projection",
        "Trend projection",
        decoder_ev,
        "node:decoder.layer",
    )
    trend_accumulate = op(
        "node:decoder.trend_accumulate",
        "Trend accumulation",
        [ev["decoder"], ev["decoder_layer"]],
        "node:decoder",
        kind=NodeKind.MERGE_EVENT,
        merge="add",
    )
    seasonal_projection = op(
        "node:decoder.seasonal_projection",
        "Seasonal projection",
        [ev["decoder"]],
        "node:decoder",
    )
    graph.connect(dec_decomp1, "trend1", trend_sum, "[B,Ld,D]", decoder_ev)
    graph.connect(dec_decomp2, "trend2", trend_sum, "[B,Ld,D]", decoder_ev)
    graph.connect(dec_decomp3, "trend3", trend_sum, "[B,Ld,D]", decoder_ev)
    graph.connect(trend_sum, "trend_residual", trend_projection, "[B,Ld,D]", decoder_ev)
    graph.connect(trend_seed, "trend_init", trend_accumulate, "[B,Ld,C]", model_ev)
    graph.connect(trend_projection, "trend_delta", trend_accumulate, "[B,Ld,C]", decoder_ev)
    graph.connect(dec_decomp3, "seasonal_state", seasonal_projection, "[B,Ld,D]", decoder_ev)

    final_add = op(
        "node:final_add",
        "Seasonal + Trend",
        model_ev,
        kind=NodeKind.MERGE_EVENT,
        merge="add",
    )
    output_slice = op("node:prediction_slice", "Prediction horizon slice", model_ev)
    graph.node(
        "node:output.forecast",
        "Forecast output",
        model_ev,
        kind=NodeKind.INPUT_OUTPUT,
        io="output",
        assigned_symbol="forecast",
    )
    graph.connect(seasonal_projection, "seasonal_part", final_add, "[B,Ld,C]", model_ev)
    graph.connect(trend_accumulate, "trend_part", final_add, "[B,Ld,C]", model_ev)
    graph.connect(final_add, "seasonal_trend", output_slice, "[B,Ld,C]", model_ev)
    graph.connect(output_slice, "forecast", "node:output.forecast", "[B,P,C]", model_ev)
    return graph


def _autoformer_discrepancies(ev: dict[str, str]) -> list[DiscrepancyRecord]:
    return [
        DiscrepancyRecord(
            discrepancy_id="discrepancy:autoformer.position-embedding",
            subject="Positional encoding",
            reference_claim="Transformer-style diagrams may show an explicit positional encoding.",
            source_finding="DataEmbedding_wo_pos.forward adds value and temporal embeddings only.",
            resolution="exclude-from-executable-graph",
            evidence_ids=[ev["embedding"]],
        ),
        DiscrepancyRecord(
            discrepancy_id="discrepancy:autoformer.add-norm",
            subject="Residual normalization",
            reference_claim="A generic Transformer diagram may show Add & Norm blocks.",
            source_finding="EncoderLayer and DecoderLayer apply progressive decomposition after residual additions.",
            resolution="include-source-behavior",
            evidence_ids=[ev["encoder"], ev["decoder_layer"]],
        ),
        DiscrepancyRecord(
            discrepancy_id="discrepancy:autoformer.mask",
            subject="Attention masks",
            reference_claim="Mask arguments imply an active score mask.",
            source_finding="AutoCorrelation.forward accepts attn_mask but never reads it in this revision.",
            resolution="exclude-from-executable-graph",
            evidence_ids=[ev["correlation"]],
        ),
        DiscrepancyRecord(
            discrepancy_id="discrepancy:autoformer.dual-path",
            subject="Seasonal and trend paths",
            reference_claim="Trend and seasonal labels may be treated as explanatory annotations.",
            source_finding="Decoder returns separate seasonal and accumulated trend tensors that are explicitly added.",
            resolution="include-source-behavior",
            evidence_ids=[ev["decoder"], ev["model"]],
        ),
    ]
