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

SOURCE_PATHS = ("models/TimeMixer.py", "layers/Embed.py", "layers/StandardNorm.py")


def _config_path(project: Path, config_path: Path | None) -> str | None:
    if config_path is None:
        return None
    resolved = config_path.resolve()
    return resolved.relative_to(project).as_posix() if resolved.is_relative_to(project) else str(resolved)


def _assert_source_contract(documents: dict[str, Any]) -> dict[str, ast.FunctionDef]:
    model = documents["models/TimeMixer.py"]
    embed = documents["layers/Embed.py"]
    norm = documents["layers/StandardNorm.py"]
    methods = {
        "model_init": model.method("Model", "__init__"),
        "downsample": model.method("Model", "__multi_scale_process_inputs"),
        "forecast": require_calls(
            model,
            "Model",
            "forecast",
            {
                "self.__multi_scale_process_inputs",
                "self.pre_enc",
                "self.future_multi_mixing",
                "torch.stack",
            },
        ),
        "future": model.method("Model", "future_multi_mixing"),
        "pdm_init": model.method("PastDecomposableMixing", "__init__"),
        "pdm_forward": require_calls(
            model,
            "PastDecomposableMixing",
            "forward",
            {"self.decompsition", "self.mixing_multi_scale_season", "self.mixing_multi_scale_trend"},
        ),
        "season": model.method("MultiScaleSeasonMixing", "forward"),
        "trend": model.method("MultiScaleTrendMixing", "forward"),
        "dft": require_calls(
            model,
            "DFT_series_decomp",
            "forward",
            {"torch.fft.rfft", "torch.topk", "torch.fft.irfft"},
        ),
        "embedding": embed.method("DataEmbedding_wo_pos", "forward"),
        "normalize": norm.method("Normalize", "forward"),
    }
    text = {name: ast.unparse(method) for name, method in methods.items()}
    required = {
        "multiscale downsampling": "for i in range(self.configs.down_sampling_layers)"
        in text["downsample"],
        "per-scale normalization": "self.normalize_layers[i](x, 'norm')" in text["forecast"],
        "channel-independent reshape": "reshape(B * N, T, 1)" in text["forecast"],
        "embedding without position": "self.position_embedding" not in text["embedding"],
        "moving-average or DFT decomposition": "configs.decomp_method == 'moving_avg'"
        in text["pdm_init"]
        and "configs.decomp_method == 'dft_decomp'" in text["pdm_init"],
        "seasonal bottom-up mixing": "out_low = out_low + out_low_res" in text["season"],
        "trend top-down mixing": "out_high = out_high + out_high_res" in text["trend"],
        "per-scale prediction": "self.predict_layers[i]" in text["future"]
        and "self.projection_layer" in text["future"],
        "stack and sum": "torch.stack(dec_out_list, dim=-1).sum(-1)" in text["forecast"],
        "denormalization": "self.normalize_layers[0](dec_out, 'denorm')" in text["forecast"],
    }
    missing = [name for name, present in required.items() if not present]
    if missing:
        raise AnalysisError(
            "TIMEMIXER_SOURCE_CONTRACT",
            f"TimeMixer source is missing required facts: {', '.join(missing)}",
        )
    return methods


def analyze_timemixer(
    project: Path,
    entrypoint: str,
    task: str,
    execution_mode: str,
    config: dict[str, Any],
    config_bytes: bytes,
    config_path: Path | None,
) -> AnalysisBundle:
    if entrypoint != "models.TimeMixer:Model":
        raise AnalysisError(
            "TIMEMIXER_ENTRYPOINT",
            "TimeMixer profile requires entrypoint models.TimeMixer:Model",
        )
    documents = load_sources(project, SOURCE_PATHS, "timemixer")
    methods = _assert_source_contract(documents)
    provenance = json.loads((project / "provenance.json").read_text(encoding="utf-8"))
    required_config = {
        "seq_len",
        "pred_len",
        "e_layers",
        "down_sampling_layers",
        "down_sampling_window",
        "down_sampling_method",
        "channel_independence",
        "decomp_method",
        "use_norm",
    }
    missing = sorted(required_config - config.keys())
    if missing:
        raise AnalysisError("TIMEMIXER_CONFIG_INVALID", f"missing config values: {', '.join(missing)}")
    if config["decomp_method"] not in {"moving_avg", "dft_decomp"}:
        raise AnalysisError("TIMEMIXER_CONFIG_INVALID", "unsupported decomp_method")

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
        source_files=[SourceFile(path=path, sha256=documents[path].digest) for path in SOURCE_PATHS],
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
    locations = {
        "model_init": ("models/TimeMixer.py", "Model.__init__"),
        "downsample": ("models/TimeMixer.py", "Model.__multi_scale_process_inputs"),
        "forecast": ("models/TimeMixer.py", "Model.forecast"),
        "future": ("models/TimeMixer.py", "Model.future_multi_mixing"),
        "pdm_init": ("models/TimeMixer.py", "PastDecomposableMixing.__init__"),
        "pdm_forward": ("models/TimeMixer.py", "PastDecomposableMixing.forward"),
        "season": ("models/TimeMixer.py", "MultiScaleSeasonMixing.forward"),
        "trend": ("models/TimeMixer.py", "MultiScaleTrendMixing.forward"),
        "dft": ("models/TimeMixer.py", "DFT_series_decomp.forward"),
        "embedding": ("layers/Embed.py", "DataEmbedding_wo_pos.forward"),
        "normalize": ("layers/StandardNorm.py", "Normalize.forward"),
    }
    source_evidence: dict[str, str] = {}
    for name, (path, symbol) in locations.items():
        method = methods[name]
        evidence_id = f"evidence:timemixer.{name.replace('_', '-')}"
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
                claim=f"{symbol} provides the selected TimeMixer path",
                confidence=Confidence.EXACT,
                execution_predicate=predicate,
            )
        )

    scale_count = int(config["down_sampling_layers"]) + 1
    channel_independent = int(config["channel_independence"]) == 1
    graph = ProfileGraphBuilder("timemixer", predicate)
    graph.node(
        "node:timemixer",
        "TimeMixer",
        [source_evidence["model_init"]],
        kind=NodeKind.MODULE_CONTAINER,
        parent_id=None,
        architecture_profile="timemixer",
        fictional_conv_branches=False,
    )
    graph.node(
        "node:input.x_enc",
        "Input series",
        [source_evidence["forecast"]],
        kind=NodeKind.INPUT_OUTPUT,
        io="input",
    )
    graph.node(
        "node:input.x_mark_enc",
        "Temporal features",
        [source_evidence["forecast"]],
        kind=NodeKind.INPUT_OUTPUT,
        io="input",
    )

    scale_sources = ["node:input.x_enc"]
    mark_sources = ["node:input.x_mark_enc"]
    for scale in range(1, scale_count):
        graph.node(
            f"node:scale.{scale}.downsample",
            f"Downsample to scale {scale}",
            [source_evidence["downsample"], config_evidence["down_sampling_method"]],
            method=config["down_sampling_method"],
            scale_index=scale,
        )
        graph.connect(
            scale_sources[-1],
            f"scale{scale}.downsample_source",
            f"node:scale.{scale}.downsample",
            f"[B,L/{int(config['down_sampling_window']) ** (scale - 1)},N]",
            [source_evidence["downsample"]],
        )
        scale_sources.append(f"node:scale.{scale}.downsample")
        graph.node(
            f"node:scale.{scale}.mark_downsample",
            f"Temporal feature slice for scale {scale}",
            [source_evidence["downsample"]],
            scale_index=scale,
        )
        graph.connect(
            mark_sources[-1],
            f"scale{scale}.mark_source",
            f"node:scale.{scale}.mark_downsample",
            f"[B,L/{int(config['down_sampling_window']) ** (scale - 1)},M]",
            [source_evidence["downsample"]],
        )
        mark_sources.append(f"node:scale.{scale}.mark_downsample")

    decomposition_nodes: list[str] = []
    for scale, (series_source, mark_source) in enumerate(zip(scale_sources, mark_sources, strict=True)):
        prefix = f"node:scale.{scale}"
        length = "L" if scale == 0 else f"L/{int(config['down_sampling_window']) ** scale}"
        graph.node(
            f"{prefix}.normalize",
            f"Normalize scale {scale}",
            [source_evidence["normalize"], config_evidence["use_norm"]],
            scale_index=scale,
            use_norm=bool(config["use_norm"]),
        )
        graph.connect(series_source, f"scale{scale}.series", f"{prefix}.normalize", f"[B,{length},N]", [source_evidence["forecast"]])
        current = f"{prefix}.normalize"
        embedding_mark_source = mark_source
        if channel_independent:
            graph.node(
                f"{prefix}.channel_reshape",
                f"Channel-independent reshape scale {scale}",
                [source_evidence["forecast"], config_evidence["channel_independence"]],
                transform=f"[B,{length},N] -> [B*N,{length},1]",
                scale_index=scale,
            )
            graph.connect(current, f"scale{scale}.normalized", f"{prefix}.channel_reshape", f"[B,{length},N]", [source_evidence["forecast"]])
            current = f"{prefix}.channel_reshape"
            graph.node(
                f"{prefix}.mark_repeat",
                f"Repeat temporal features by channel scale {scale}",
                [source_evidence["forecast"]],
                transform=f"[B,{length},M] -> [B*N,{length},M]",
                scale_index=scale,
            )
            graph.connect(
                mark_source,
                f"scale{scale}.marks_unrepeated",
                f"{prefix}.mark_repeat",
                f"[B,{length},M]",
                [source_evidence["forecast"]],
            )
            embedding_mark_source = f"{prefix}.mark_repeat"
        graph.node(
            f"{prefix}.embedding",
            f"DataEmbedding_wo_pos scale {scale}",
            [source_evidence["embedding"]],
            position_embedding_used=False,
            scale_index=scale,
        )
        graph.connect(current, f"scale{scale}.values", f"{prefix}.embedding", f"[B*N,{length},1]" if channel_independent else f"[B,{length},N]", [source_evidence["embedding"]])
        graph.connect(
            embedding_mark_source,
            f"scale{scale}.marks",
            f"{prefix}.embedding",
            f"[B*N,{length},M]" if channel_independent else f"[B,{length},M]",
            [source_evidence["embedding"]],
        )
        graph.node(
            f"{prefix}.decomposition",
            f"{config['decomp_method']} decomposition scale {scale}",
            [source_evidence["pdm_init"], source_evidence["pdm_forward"], config_evidence["decomp_method"]],
            method=config["decomp_method"],
            scale_index=scale,
        )
        graph.connect(f"{prefix}.embedding", f"scale{scale}.embedded", f"{prefix}.decomposition", f"[B*N,{length},D]" if channel_independent else f"[B,{length},D]", [source_evidence["pdm_forward"]])
        decomposition_nodes.append(f"{prefix}.decomposition")

    graph.node(
        "node:season.bottom_up",
        "Seasonal bottom-up scale mixing",
        [source_evidence["season"]],
        direction="high-resolution-to-low-resolution",
        scale_count=scale_count,
    )
    graph.node(
        "node:trend.top_down",
        "Trend top-down scale mixing",
        [source_evidence["trend"]],
        direction="low-resolution-to-high-resolution",
        scale_count=scale_count,
    )
    for scale, decomposition_node in enumerate(decomposition_nodes):
        graph.connect(decomposition_node, f"scale{scale}.season", "node:season.bottom_up", "[B*,Li,D]", [source_evidence["season"]])
        graph.connect(decomposition_node, f"scale{scale}.trend", "node:trend.top_down", "[B*,Li,D]", [source_evidence["trend"]])

    forecasts: list[str] = []
    for scale in range(scale_count):
        prefix = f"node:scale.{scale}"
        graph.node(
            f"{prefix}.mix_add",
            f"Merge seasonal and trend scale {scale}",
            [source_evidence["pdm_forward"]],
            kind=NodeKind.MERGE_EVENT,
            scale_index=scale,
        )
        graph.connect("node:season.bottom_up", f"scale{scale}.mixed_season", f"{prefix}.mix_add", "[B*,Li,D]", [source_evidence["season"]])
        graph.connect("node:trend.top_down", f"scale{scale}.mixed_trend", f"{prefix}.mix_add", "[B*,Li,D]", [source_evidence["trend"]])
        graph.node(
            f"{prefix}.predictor",
            f"Temporal predictor scale {scale}",
            [source_evidence["future"]],
            scale_index=scale,
            out_axis="S",
        )
        graph.connect(f"{prefix}.mix_add", f"scale{scale}.mixed", f"{prefix}.predictor", "[B*,Li,D]", [source_evidence["future"]])
        graph.node(
            f"{prefix}.projection",
            f"Output projection scale {scale}",
            [source_evidence["future"]],
            scale_index=scale,
            restores_channels=channel_independent,
        )
        graph.connect(f"{prefix}.predictor", f"scale{scale}.predicted", f"{prefix}.projection", "[B*,S,D]", [source_evidence["future"]])
        forecast_node = f"{prefix}.projection"
        if channel_independent:
            graph.node(
                f"{prefix}.restore_forecast",
                f"Restore channel forecast scale {scale}",
                [source_evidence["future"]],
                transform="[B*N,S,1] -> [B,S,C]",
                scale_index=scale,
            )
            graph.connect(
                forecast_node,
                f"scale{scale}.channel_independent_forecast",
                f"{prefix}.restore_forecast",
                "[B*N,S,1]",
                [source_evidence["future"]],
            )
            forecast_node = f"{prefix}.restore_forecast"
        forecasts.append(forecast_node)

    graph.node(
        "node:forecast.stack",
        "Stack per-scale forecasts",
        [source_evidence["forecast"]],
        kind=NodeKind.MERGE_EVENT,
        scale_count=scale_count,
    )
    for scale, forecast in enumerate(forecasts):
        graph.connect(forecast, f"scale{scale}.forecast", "node:forecast.stack", "[B,S,C]", [source_evidence["forecast"]])
    graph.node(
        "node:forecast.sum",
        "Sum per-scale forecasts",
        [source_evidence["forecast"]],
        operation="reduce_sum",
        axis="scale",
    )
    graph.connect("node:forecast.stack", "stacked_forecasts", "node:forecast.sum", "[B,S,C,K]", [source_evidence["forecast"]])
    graph.node(
        "node:denormalize",
        "Denormalize forecast",
        [source_evidence["normalize"], source_evidence["forecast"]],
        source_scale=0,
    )
    graph.connect("node:forecast.sum", "summed_forecast", "node:denormalize", "[B,S,C]", [source_evidence["forecast"]])
    graph.node(
        "node:output.forecast",
        "Forecast",
        [source_evidence["forecast"]],
        kind=NodeKind.INPUT_OUTPUT,
        io="output",
    )
    graph.connect("node:denormalize", "forecast", "node:output.forecast", "[B,S,C]", [source_evidence["forecast"]])
    nodes, tensors, edges, fanouts = graph.build()
    repeats = [
        Repeat(
            repeat_id="repeat:pdm-blocks",
            kind=RepeatKind.STACK,
            member_node_ids=[
                *decomposition_nodes,
                "node:season.bottom_up",
                "node:trend.top_down",
            ],
            count=int(config["e_layers"]),
            parameter_identity="independent-block-parameters",
            evidence_ids=[source_evidence["model_init"], config_evidence["e_layers"]],
        ),
        Repeat(
            repeat_id="repeat:scales",
            kind=RepeatKind.SCALE,
            member_node_ids=[f"node:scale.{scale}.embedding" for scale in range(scale_count)],
            count=scale_count,
            parameter_identity="per-scale-modules",
            evidence_ids=[source_evidence["downsample"], config_evidence["down_sampling_layers"]],
        ),
    ]
    predicate_values = {
        "down_sampling_layers": int(config["down_sampling_layers"]),
        "down_sampling_method": config["down_sampling_method"],
        "channel_independence": int(config["channel_independence"]),
        "decomp_method": config["decomp_method"],
        "use_norm": int(config["use_norm"]),
    }
    predicates = [
        ConfigPredicate(
            predicate_id=f"predicate:{key.replace('_', '-')}",
            expression=f"{key} == configured",
            resolved_value=value,
            affected_ids=[
                node.node_id
                for node in nodes
                if (key == "down_sampling_layers" and "scale." in node.node_id)
                or (key == "down_sampling_method" and node.node_id.endswith("downsample"))
                or (key == "channel_independence" and "channel_reshape" in node.node_id)
                or (key == "decomp_method" and node.node_id.endswith("decomposition"))
                or (key == "use_norm" and node.node_id.endswith("normalize"))
            ],
            evidence_ids=[config_evidence[key]],
        )
        for key, value in predicate_values.items()
    ]
    architecture = ArchitectureIR(
        architecture_id=f"architecture:{sha256(snapshot_seed + b':timemixer')[:16]}",
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
            discrepancy_id="discrepancy:timemixer.fictional-branches",
            subject="Reference mixer branches",
            reference_claim="The core path contains short, mid, and long Conv mixer branches.",
            source_finding="The source builds a multiscale list and bidirectional season/trend mixing; those branches do not exist.",
            resolution="exclude-from-executable-graph",
            evidence_ids=[source_evidence["downsample"], source_evidence["pdm_forward"]],
        ),
        DiscrepancyRecord(
            discrepancy_id="discrepancy:timemixer.bidirectional-scales",
            subject="Multiscale mixing direction",
            reference_claim="Scale mixing can be summarized as one undirected mixer.",
            source_finding="Season moves high-to-low while trend moves low-to-high.",
            resolution="include-source-behavior",
            evidence_ids=[source_evidence["season"], source_evidence["trend"]],
        ),
        DiscrepancyRecord(
            discrepancy_id="discrepancy:timemixer.prediction-merge",
            subject="Forecast merge",
            reference_claim="Only the highest-resolution scale produces a forecast.",
            source_finding="Every scale has predictor/projection and outputs are stacked then summed.",
            resolution="include-source-behavior",
            evidence_ids=[source_evidence["future"], source_evidence["forecast"]],
        ),
    ]
    return AnalysisBundle(snapshot, evidence, architecture, discrepancies)
