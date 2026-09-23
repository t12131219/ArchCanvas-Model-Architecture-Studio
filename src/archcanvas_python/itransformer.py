from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any

from archcanvas_core.models import (
    ArchitectureIR,
    Confidence,
    ConfigPredicate,
    DiscrepancyRecord,
    EvidenceKind,
    EvidenceRecord,
    NodeKind,
    Repeat,
    RepeatKind,
    SourceFile,
    SourceSnapshot,
    SourceSpan,
)

from .analyzer import ANALYZER_VERSION, AnalysisBundle, AnalysisError
from .profile_graph import ProfileGraphBuilder, load_sources, require_calls, sha256

SOURCE_PATHS = (
    "model/iTransformer.py",
    "layers/Embed.py",
    "layers/Transformer_EncDec.py",
)


def _config_path(project: Path, config_path: Path | None) -> str | None:
    if config_path is None:
        return None
    resolved = config_path.resolve()
    return resolved.relative_to(project).as_posix() if resolved.is_relative_to(project) else str(resolved)


def _assert_source_contract(documents: dict[str, Any]) -> dict[str, ast.FunctionDef]:
    model = documents["model/iTransformer.py"]
    embed = documents["layers/Embed.py"]
    encoder = documents["layers/Transformer_EncDec.py"]
    methods = {
        "forecast": require_calls(
            model,
            "Model",
            "forecast",
            {"self.enc_embedding", "self.encoder", "self.projector"},
        ),
        "embedding": require_calls(
            embed,
            "DataEmbedding_inverted",
            "forward",
            {"x.permute", "self.value_embedding", "self.dropout"},
        ),
        "encoder": require_calls(encoder, "Encoder", "forward", set()),
        "init": model.method("Model", "__init__"),
    }
    use_norm_tests = [
        node
        for node in ast.walk(methods["forecast"])
        if isinstance(node, ast.If) and ast.unparse(node.test) == "self.use_norm"
    ]
    forecast_source = ast.unparse(methods["forecast"])
    embedding_source = ast.unparse(methods["embedding"])
    init_source = ast.unparse(methods["init"])
    encoder_source = ast.unparse(methods["encoder"])
    required_fragments = {
        "normalization and denormalization": len(use_norm_tests) >= 2,
        "project then output permute": "self.projector(enc_out).permute(0, 2, 1)" in forecast_source,
        "covariate trimming": "[:, :, :N]" in forecast_source,
        "internal input permute": "x = x.permute(0, 2, 1)" in embedding_source,
        "covariate token concat": "torch.cat([x, x_mark.permute(0, 2, 1)], 1)" in embedding_source,
        "encoder construction": "self.encoder = Encoder" in init_source,
        "encoder layer iteration": "for attn_layer in self.attn_layers" in encoder_source,
        "encoder-only construction": "self.decoder =" not in init_source,
    }
    missing = [name for name, present in required_fragments.items() if not present]
    if missing:
        raise AnalysisError(
            "ITRANSFORMER_SOURCE_CONTRACT",
            f"iTransformer source is missing required facts: {', '.join(missing)}",
        )
    return methods


def analyze_itransformer(
    project: Path,
    entrypoint: str,
    task: str,
    execution_mode: str,
    config: dict[str, Any],
    config_bytes: bytes,
    config_path: Path | None,
) -> AnalysisBundle:
    if entrypoint != "model.iTransformer:Model":
        raise AnalysisError(
            "ITRANSFORMER_ENTRYPOINT",
            "iTransformer profile requires entrypoint model.iTransformer:Model",
        )
    documents = load_sources(project, SOURCE_PATHS, "itransformer")
    methods = _assert_source_contract(documents)
    try:
        provenance = json.loads((project / "provenance.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise AnalysisError("ITRANSFORMER_PROVENANCE_INVALID", str(error)) from error

    config_digest = sha256(config_bytes)
    predicate = f"task={task} && mode={execution_mode}"
    revision = provenance["upstream_revision"]
    source_digest = sha256("".join(documents[path].digest for path in SOURCE_PATHS).encode())
    snapshot_seed = f"{source_digest}:{config_digest}:{entrypoint}:{task}:{execution_mode}".encode()
    resolved_config_path = _config_path(project, config_path)
    snapshot = SourceSnapshot(
        snapshot_id=f"snapshot:{sha256(snapshot_seed)[:16]}",
        project_root=str(project),
        revision=revision,
        entrypoint=entrypoint,
        task=task,
        execution_mode=execution_mode,
        framework="pytorch",
        adapter_version=ANALYZER_VERSION,
        config_digest=config_digest,
        config_path=resolved_config_path,
        resolved_config=config,
        source_files=[
            SourceFile(path=path, sha256=documents[path].digest) for path in SOURCE_PATHS
        ],
    )

    evidence: list[EvidenceRecord] = []
    config_evidence: dict[str, str] = {}
    for key in sorted(config):
        evidence_id = f"evidence:config.{key.lower().replace('_', '-')}"
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

    source_evidence: dict[str, str] = {}
    locations = {
        "forecast": ("model/iTransformer.py", "Model.forecast"),
        "init": ("model/iTransformer.py", "Model.__init__"),
        "embedding": ("layers/Embed.py", "DataEmbedding_inverted.forward"),
        "encoder": ("layers/Transformer_EncDec.py", "Encoder.forward"),
    }
    for name, (path, symbol) in locations.items():
        method = methods[name]
        evidence_id = f"evidence:itransformer.{name}"
        source_evidence[name] = evidence_id
        evidence.append(
            EvidenceRecord(
                evidence_id=evidence_id,
                kind=EvidenceKind.SOURCE,
                path=path,
                symbol=symbol,
                span=SourceSpan(
                    start_line=method.lineno,
                    end_line=getattr(method, "end_lineno", method.lineno),
                ),
                file_sha256=documents[path].digest,
                revision=revision,
                claim=f"{symbol} provides the selected iTransformer architecture path",
                confidence=Confidence.EXACT,
                execution_predicate=predicate,
            )
        )

    required_config = {
        "seq_len",
        "pred_len",
        "d_model",
        "e_layers",
        "use_norm",
        "use_covariates",
    }
    missing_config = sorted(required_config - config.keys())
    if missing_config:
        raise AnalysisError(
            "ITRANSFORMER_CONFIG_INVALID",
            f"missing required config values: {', '.join(missing_config)}",
        )
    use_norm = bool(config["use_norm"])
    use_covariates = bool(config["use_covariates"])
    graph = ProfileGraphBuilder("itransformer", predicate)
    graph.node(
        "node:itransformer",
        "iTransformer",
        [source_evidence["init"]],
        kind=NodeKind.MODULE_CONTAINER,
        parent_id=None,
        architecture_profile="itransformer",
        encoder_only=True,
    )
    graph.node(
        "node:input.x_enc",
        "Observed series",
        [source_evidence["forecast"]],
        kind=NodeKind.INPUT_OUTPUT,
        io="input",
    )
    graph.node(
        "node:input.x_mark_enc",
        "Covariate marks",
        [source_evidence["forecast"]],
        kind=NodeKind.INPUT_OUTPUT,
        io="input",
    )
    current = "node:input.x_enc"
    if use_norm:
        graph.node(
            "node:normalize",
            "Optional normalization",
            [source_evidence["forecast"], config_evidence["use_norm"]],
            config_predicate="use_norm == true",
            steps=["mean", "center", "variance", "stdev", "scale"],
        )
        graph.connect(current, "observed", "node:normalize", "[B,L,N]", [source_evidence["forecast"]])
        current = "node:normalize"
    graph.node(
        "node:embedding.permute",
        "Internal variable-token permute",
        [source_evidence["embedding"]],
        internal_axis_transform=True,
        external_learnable_module=False,
        transform="[B,L,N] -> [B,N,L]",
    )
    graph.connect(current, "normalized_series", "node:embedding.permute", "[B,L,N]", [source_evidence["embedding"]])
    current = "node:embedding.permute"
    token_shape = "[B,N,L]"
    if use_covariates:
        graph.node(
            "node:covariate.permute",
            "Covariate token permute",
            [source_evidence["embedding"]],
            internal_axis_transform=True,
        )
        graph.node(
            "node:covariate.concat",
            "Append covariate tokens",
            [source_evidence["embedding"], config_evidence["use_covariates"]],
            kind=NodeKind.MERGE_EVENT,
            config_predicate="use_covariates == true",
        )
        graph.connect(
            "node:input.x_mark_enc",
            "covariates",
            "node:covariate.permute",
            "[B,L,M]",
            [source_evidence["embedding"]],
        )
        graph.connect(current, "variable_tokens", "node:covariate.concat", token_shape, [source_evidence["embedding"]])
        graph.connect(
            "node:covariate.permute",
            "covariate_tokens",
            "node:covariate.concat",
            "[B,M,L]",
            [source_evidence["embedding"]],
        )
        current = "node:covariate.concat"
        token_shape = "[B,N+M,L]"
    graph.node(
        "node:embedding.projection",
        "Variable-token projection L to D",
        [source_evidence["embedding"], config_evidence["seq_len"], config_evidence["d_model"]],
        in_axis="L",
        out_axis="D",
        op_type="nn.Linear",
    )
    graph.connect(current, "tokens", "node:embedding.projection", token_shape, [source_evidence["embedding"]])
    graph.node(
        "node:encoder.stack",
        "Encoder-only stack",
        [source_evidence["encoder"], config_evidence["e_layers"]],
        encoder_only=True,
    )
    graph.connect(
        "node:embedding.projection",
        "embedded_tokens",
        "node:encoder.stack",
        "[B,N+M,D]" if use_covariates else "[B,N,D]",
        [source_evidence["encoder"]],
    )
    graph.node(
        "node:forecast.projector",
        "Forecast projection D to pred_len",
        [source_evidence["forecast"], config_evidence["pred_len"]],
        in_axis="D",
        out_axis="S",
        op_type="nn.Linear",
    )
    graph.connect(
        "node:encoder.stack",
        "encoded_tokens",
        "node:forecast.projector",
        "[B,N+M,D]" if use_covariates else "[B,N,D]",
        [source_evidence["forecast"]],
    )
    graph.node(
        "node:forecast.permute",
        "Forecast output permute",
        [source_evidence["forecast"]],
        transform="[B,N,S] -> [B,S,N]",
    )
    graph.connect(
        "node:forecast.projector",
        "token_forecast",
        "node:forecast.permute",
        "[B,N+M,S]" if use_covariates else "[B,N,S]",
        [source_evidence["forecast"]],
    )
    current = "node:forecast.permute"
    if use_covariates:
        graph.node(
            "node:forecast.trim_covariates",
            "Trim covariate tokens",
            [source_evidence["forecast"], config_evidence["use_covariates"]],
            config_predicate="use_covariates == true",
            slice=":N",
        )
        graph.connect(current, "forecast_with_covariates", "node:forecast.trim_covariates", "[B,S,N+M]", [source_evidence["forecast"]])
        current = "node:forecast.trim_covariates"
    if use_norm:
        graph.node(
            "node:denormalize",
            "Optional denormalization",
            [source_evidence["forecast"], config_evidence["use_norm"]],
            config_predicate="use_norm == true",
            steps=["restore_stdev", "restore_mean"],
        )
        graph.connect(current, "normalized_forecast", "node:denormalize", "[B,S,N]", [source_evidence["forecast"]])
        current = "node:denormalize"
    graph.node(
        "node:output.forecast",
        "Forecast",
        [source_evidence["forecast"]],
        kind=NodeKind.INPUT_OUTPUT,
        io="output",
    )
    graph.connect(current, "forecast", "node:output.forecast", "[B,S,N]", [source_evidence["forecast"]])
    nodes, tensors, edges, fanouts = graph.build()

    repeats = [
        Repeat(
            repeat_id="repeat:encoder.layers",
            kind=RepeatKind.STACK,
            member_node_ids=["node:encoder.stack"],
            count=int(config["e_layers"]),
            parameter_identity="independent-layer-parameters",
            evidence_ids=[source_evidence["init"], config_evidence["e_layers"]],
        )
    ]
    predicates = [
        ConfigPredicate(
            predicate_id="predicate:use_norm",
            expression="use_norm == true",
            resolved_value=use_norm,
            affected_ids=(
                ["node:normalize", "node:denormalize"] if use_norm else []
            ),
            evidence_ids=[config_evidence["use_norm"], source_evidence["forecast"]],
        ),
        ConfigPredicate(
            predicate_id="predicate:use_covariates",
            expression="use_covariates == true",
            resolved_value=use_covariates,
            affected_ids=(
                ["node:covariate.permute", "node:covariate.concat", "node:forecast.trim_covariates"]
                if use_covariates
                else []
            ),
            evidence_ids=[config_evidence["use_covariates"], source_evidence["embedding"]],
        ),
    ]
    architecture = ArchitectureIR(
        architecture_id=f"architecture:{sha256(snapshot_seed + b':itransformer')[:16]}",
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
    discrepancies = [
        DiscrepancyRecord(
            discrepancy_id="discrepancy:itransformer.internal-permute",
            subject="DataEmbedding_inverted axis transform",
            reference_claim="The input permutation can appear as an external embedding block.",
            source_finding="The permutation is an internal non-learnable operation in DataEmbedding_inverted.forward.",
            resolution="include-source-behavior",
            evidence_ids=[source_evidence["embedding"]],
        ),
        DiscrepancyRecord(
            discrepancy_id="discrepancy:itransformer.normalization",
            subject="Normalization path",
            reference_claim="Normalization may be shown as unconditional.",
            source_finding="Normalization and denormalization are both guarded by use_norm.",
            resolution="mark-conditional",
            evidence_ids=[source_evidence["forecast"], config_evidence["use_norm"]],
        ),
        DiscrepancyRecord(
            discrepancy_id="discrepancy:itransformer.covariates",
            subject="Covariate tokens",
            reference_claim="All encoder tokens may be shown as forecast variables.",
            source_finding="Optional covariates are appended as tokens and trimmed from forecast output.",
            resolution="mark-conditional",
            evidence_ids=[source_evidence["embedding"], source_evidence["forecast"]],
        ),
    ]
    return AnalysisBundle(snapshot, evidence, architecture, discrepancies)
