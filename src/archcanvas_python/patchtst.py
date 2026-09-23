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
    "models/PatchTST.py",
    "layers/PatchTST_backbone.py",
    "layers/PatchTST_layers.py",
    "layers/RevIN.py",
)


def _config_path(project: Path, config_path: Path | None) -> str | None:
    if config_path is None:
        return None
    resolved = config_path.resolve()
    return resolved.relative_to(project).as_posix() if resolved.is_relative_to(project) else str(resolved)


def _assert_source_contract(documents: dict[str, Any]) -> dict[str, ast.FunctionDef]:
    model = documents["models/PatchTST.py"]
    backbone = documents["layers/PatchTST_backbone.py"]
    methods = {
        "model_init": model.method("Model", "__init__"),
        "model_forward": require_calls(
            model,
            "Model",
            "forward",
            {"self.decomp_module", "self.model_res", "self.model_trend", "x.permute"},
        ),
        "backbone_init": backbone.method("PatchTST_backbone", "__init__"),
        "backbone_forward": require_calls(
            backbone,
            "PatchTST_backbone",
            "forward",
            {"z.unfold", "self.backbone", "self.head"},
        ),
        "encoder_init": backbone.method("TSTiEncoder", "__init__"),
        "encoder_forward": require_calls(
            backbone,
            "TSTiEncoder",
            "forward",
            {"self.W_P", "torch.reshape", "self.encoder"},
        ),
        "head_init": backbone.method("Flatten_Head", "__init__"),
        "head_forward": backbone.method("Flatten_Head", "forward"),
        "stack_forward": backbone.method("TSTEncoder", "forward"),
    }
    text = {name: ast.unparse(method) for name, method in methods.items()}
    init_arguments = methods["model_init"].args.args
    init_defaults = [None] * (len(init_arguments) - len(methods["model_init"].args.defaults)) + list(
        methods["model_init"].args.defaults
    )
    init_default_by_name = {
        argument.arg: default for argument, default in zip(init_arguments, init_defaults, strict=True)
    }
    norm_default = init_default_by_name.get("norm")
    required = {
        "decomposition dual backbones": all(
            fragment in text["model_init"]
            for fragment in ("self.model_res = PatchTST_backbone", "self.model_trend = PatchTST_backbone")
        ),
        "decomposition merge": "x = res + trend" in text["model_forward"],
        "optional RevIN": "if self.revin" in text["backbone_forward"]
        and "'norm'" in text["backbone_forward"]
        and "'denorm'" in text["backbone_forward"],
        "conditional end padding": "if self.padding_patch == 'end'" in text["backbone_forward"],
        "patch unfold": "z.unfold(dimension=-1, size=self.patch_len, step=self.stride)"
        in text["backbone_forward"],
        "patch projection": "self.W_P = nn.Linear(patch_len, d_model)" in text["encoder_init"],
        "channel independent reshape": "x.shape[0] * x.shape[1]" in text["encoder_forward"],
        "position encoding": "self.W_pos = positional_encoding" in text["encoder_init"]
        and "u + self.W_pos" in text["encoder_forward"],
        "flatten head": "nn.Flatten(start_dim=-2)" in text["head_init"]
        and "nn.Linear(nf, target_window)" in text["head_init"],
        "residual attention": "if self.res_attention" in text["stack_forward"],
        "BatchNorm default": isinstance(norm_default, ast.Constant)
        and norm_default.value == "BatchNorm",
    }
    missing = [name for name, present in required.items() if not present]
    if missing:
        raise AnalysisError(
            "PATCHTST_SOURCE_CONTRACT",
            f"PatchTST source is missing required facts: {', '.join(missing)}",
        )
    return methods


def analyze_patchtst(
    project: Path,
    entrypoint: str,
    task: str,
    execution_mode: str,
    config: dict[str, Any],
    config_bytes: bytes,
    config_path: Path | None,
) -> AnalysisBundle:
    if entrypoint != "models.PatchTST:Model":
        raise AnalysisError(
            "PATCHTST_ENTRYPOINT",
            "PatchTST profile requires entrypoint models.PatchTST:Model",
        )
    documents = load_sources(project, SOURCE_PATHS, "patchtst")
    methods = _assert_source_contract(documents)
    provenance = json.loads((project / "provenance.json").read_text(encoding="utf-8"))
    required_config = {
        "seq_len",
        "pred_len",
        "e_layers",
        "d_model",
        "patch_len",
        "stride",
        "padding_patch",
        "revin",
        "decomposition",
        "individual",
        "res_attention",
        "norm",
    }
    missing = sorted(required_config - config.keys())
    if missing:
        raise AnalysisError("PATCHTST_CONFIG_INVALID", f"missing config values: {', '.join(missing)}")

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
        "model_init": ("models/PatchTST.py", "Model.__init__"),
        "model_forward": ("models/PatchTST.py", "Model.forward"),
        "backbone_init": ("layers/PatchTST_backbone.py", "PatchTST_backbone.__init__"),
        "backbone_forward": ("layers/PatchTST_backbone.py", "PatchTST_backbone.forward"),
        "encoder_init": ("layers/PatchTST_backbone.py", "TSTiEncoder.__init__"),
        "encoder_forward": ("layers/PatchTST_backbone.py", "TSTiEncoder.forward"),
        "head_init": ("layers/PatchTST_backbone.py", "Flatten_Head.__init__"),
        "head_forward": ("layers/PatchTST_backbone.py", "Flatten_Head.forward"),
        "stack_forward": ("layers/PatchTST_backbone.py", "TSTEncoder.forward"),
    }
    source_evidence: dict[str, str] = {}
    for name, (path, symbol) in locations.items():
        method = methods[name]
        evidence_id = f"evidence:patchtst.{name.replace('_', '-')}"
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
                claim=f"{symbol} provides the selected PatchTST path",
                confidence=Confidence.EXACT,
                execution_predicate=predicate,
            )
        )

    decomposition = bool(config["decomposition"])
    revin = bool(config["revin"])
    end_padding = config["padding_patch"] == "end"
    individual = bool(config["individual"])
    residual_attention = bool(config["res_attention"])
    patch_count = (int(config["seq_len"]) - int(config["patch_len"])) // int(config["stride"]) + 1
    if end_padding:
        patch_count += 1
    graph = ProfileGraphBuilder("patchtst", predicate)
    graph.node(
        "node:patchtst",
        "PatchTST",
        [source_evidence["model_init"]],
        kind=NodeKind.MODULE_CONTAINER,
        parent_id=None,
        architecture_profile="patchtst",
        default_norm=config["norm"],
    )
    graph.node(
        "node:input.x",
        "Input series",
        [source_evidence["model_forward"]],
        kind=NodeKind.INPUT_OUTPUT,
        io="input",
    )

    def add_lane(lane: str, source: str, source_role: str) -> str:
        current = source
        prefix = f"node:{lane}"
        if revin:
            graph.node(
                f"{prefix}.revin_norm",
                f"{lane.title()} RevIN normalize",
                [source_evidence["backbone_forward"], config_evidence["revin"]],
                config_predicate="revin == true",
            )
            graph.connect(current, source_role, f"{prefix}.revin_norm", "[B,C,L]", [source_evidence["backbone_forward"]])
            current = f"{prefix}.revin_norm"
        if end_padding:
            graph.node(
                f"{prefix}.end_padding",
                f"{lane.title()} end padding",
                [source_evidence["backbone_init"], config_evidence["padding_patch"]],
                config_predicate="padding_patch == 'end'",
            )
            graph.connect(current, f"{lane}.normalized", f"{prefix}.end_padding", "[B,C,L]", [source_evidence["backbone_forward"]])
            current = f"{prefix}.end_padding"
        graph.node(
            f"{prefix}.unfold",
            f"{lane.title()} patch unfold",
            [source_evidence["backbone_forward"], config_evidence["patch_len"], config_evidence["stride"]],
            operation="unfold",
            patch_count=patch_count,
        )
        graph.connect(current, f"{lane}.padded", f"{prefix}.unfold", "[B,C,L]", [source_evidence["backbone_forward"]])
        graph.node(
            f"{prefix}.patch_projection",
            f"{lane.title()} patch projection P to D",
            [source_evidence["encoder_init"], config_evidence["patch_len"], config_evidence["d_model"]],
            in_axis="P",
            out_axis="D",
        )
        graph.connect(f"{prefix}.unfold", f"{lane}.patches", f"{prefix}.patch_projection", "[B,C,Np,P]", [source_evidence["encoder_forward"]])
        graph.node(
            f"{prefix}.channel_reshape",
            f"{lane.title()} channel-independent reshape",
            [source_evidence["encoder_forward"]],
            transform="[B,C,Np,D] -> [BC,Np,D]",
        )
        graph.connect(f"{prefix}.patch_projection", f"{lane}.projected_patches", f"{prefix}.channel_reshape", "[B,C,Np,D]", [source_evidence["encoder_forward"]])
        graph.node(
            f"{prefix}.position",
            f"{lane.title()} positional encoding",
            [source_evidence["encoder_init"]],
            kind=NodeKind.STATE,
            learnable=True,
        )
        graph.node(
            f"{prefix}.position_add",
            f"{lane.title()} add positional encoding",
            [source_evidence["encoder_forward"]],
            kind=NodeKind.MERGE_EVENT,
        )
        graph.connect(f"{prefix}.channel_reshape", f"{lane}.channel_independent", f"{prefix}.position_add", "[BC,Np,D]", [source_evidence["encoder_forward"]])
        graph.connect(f"{prefix}.position", f"{lane}.position", f"{prefix}.position_add", "[Np,D]", [source_evidence["encoder_init"]])
        graph.node(
            f"{prefix}.encoder",
            f"{lane.title()} encoder stack",
            [source_evidence["stack_forward"], config_evidence["res_attention"], config_evidence["norm"]],
            residual_attention=residual_attention,
            norm=config["norm"],
        )
        graph.connect(f"{prefix}.position_add", f"{lane}.tokens", f"{prefix}.encoder", "[BC,Np,D]", [source_evidence["stack_forward"]])
        graph.node(
            f"{prefix}.restore_channels",
            f"{lane.title()} restore channels",
            [source_evidence["encoder_forward"]],
            transform="[BC,Np,D] -> [B,C,D,Np]",
        )
        graph.connect(f"{prefix}.encoder", f"{lane}.encoded_tokens", f"{prefix}.restore_channels", "[BC,Np,D]", [source_evidence["encoder_forward"]])
        graph.node(
            f"{prefix}.flatten",
            f"{lane.title()} flatten D times Np",
            [source_evidence["head_init"], source_evidence["head_forward"]],
            transform="[B,C,D,Np] -> [B,C,D*Np]",
        )
        graph.connect(f"{prefix}.restore_channels", f"{lane}.encoded_patches", f"{prefix}.flatten", "[B,C,D,Np]", [source_evidence["head_forward"]])
        graph.node(
            f"{prefix}.head_linear",
            f"{lane.title()} forecast Linear",
            [source_evidence["head_init"], config_evidence["pred_len"], config_evidence["individual"]],
            in_axis="D*Np",
            out_axis="S",
            individual=individual,
        )
        graph.connect(f"{prefix}.flatten", f"{lane}.flattened", f"{prefix}.head_linear", "[B,C,D*Np]", [source_evidence["head_forward"]])
        current = f"{prefix}.head_linear"
        if revin:
            graph.node(
                f"{prefix}.revin_denorm",
                f"{lane.title()} RevIN denormalize",
                [source_evidence["backbone_forward"], config_evidence["revin"]],
                config_predicate="revin == true",
            )
            graph.connect(current, f"{lane}.normalized_forecast", f"{prefix}.revin_denorm", "[B,C,S]", [source_evidence["backbone_forward"]])
            current = f"{prefix}.revin_denorm"
        return current

    if decomposition:
        graph.node(
            "node:decomposition",
            "Series decomposition",
            [source_evidence["model_forward"], config_evidence["decomposition"]],
            config_predicate="decomposition == true",
        )
        graph.connect("node:input.x", "series", "node:decomposition", "[B,L,C]", [source_evidence["model_forward"]])
        residual = add_lane("residual", "node:decomposition", "residual_input")
        trend = add_lane("trend", "node:decomposition", "trend_input")
        graph.node(
            "node:decomposition_add",
            "Residual plus trend forecast",
            [source_evidence["model_forward"]],
            kind=NodeKind.MERGE_EVENT,
        )
        graph.connect(residual, "residual_forecast", "node:decomposition_add", "[B,C,S]", [source_evidence["model_forward"]])
        graph.connect(trend, "trend_forecast", "node:decomposition_add", "[B,C,S]", [source_evidence["model_forward"]])
        current = "node:decomposition_add"
    else:
        graph.node(
            "node:input_permute",
            "Input channel-first permute",
            [source_evidence["model_forward"]],
            transform="[B,L,C] -> [B,C,L]",
        )
        graph.connect("node:input.x", "series", "node:input_permute", "[B,L,C]", [source_evidence["model_forward"]])
        current = add_lane("main", "node:input_permute", "channel_first")
    graph.node(
        "node:output_permute",
        "Forecast channel-last permute",
        [source_evidence["model_forward"]],
        transform="[B,C,S] -> [B,S,C]",
    )
    graph.connect(current, "channel_first_forecast", "node:output_permute", "[B,C,S]", [source_evidence["model_forward"]])
    graph.node(
        "node:output.forecast",
        "Forecast",
        [source_evidence["model_forward"]],
        kind=NodeKind.INPUT_OUTPUT,
        io="output",
    )
    graph.connect("node:output_permute", "forecast", "node:output.forecast", "[B,S,C]", [source_evidence["model_forward"]])
    nodes, tensors, edges, fanouts = graph.build()

    lanes = ["residual", "trend"] if decomposition else ["main"]
    repeats = [
        Repeat(
            repeat_id=f"repeat:{lane}.encoder-layers",
            kind=RepeatKind.STACK,
            member_node_ids=[f"node:{lane}.encoder"],
            count=int(config["e_layers"]),
            parameter_identity="independent-layer-parameters",
            evidence_ids=[source_evidence["stack_forward"], config_evidence["e_layers"]],
        )
        for lane in lanes
    ]
    predicate_values = {
        "decomposition": decomposition,
        "revin": revin,
        "padding_patch": config["padding_patch"],
        "individual": individual,
        "res_attention": residual_attention,
        "norm": config["norm"],
    }
    predicates = [
        ConfigPredicate(
            predicate_id=f"predicate:{key.replace('_', '-')}",
            expression=(f"{key} == 'end'" if key == "padding_patch" else f"{key} == configured"),
            resolved_value=value,
            affected_ids=[
                node.node_id
                for node in nodes
                if node.attributes.get("config_predicate", "").startswith(key)
                or (key == "individual" and node.node_id.endswith("head_linear"))
                or (key == "res_attention" and node.node_id.endswith("encoder"))
                or (key == "norm" and node.node_id.endswith("encoder"))
            ],
            evidence_ids=[config_evidence[key]],
        )
        for key, value in predicate_values.items()
    ]
    architecture = ArchitectureIR(
        architecture_id=f"architecture:{sha256(snapshot_seed + b':patchtst')[:16]}",
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
            discrepancy_id="discrepancy:patchtst.head",
            subject="Forecast head",
            reference_claim="The head may be summarized as D to pred_len.",
            source_finding="The source flattens D times patch count before Linear(pred_len).",
            resolution="include-source-behavior",
            evidence_ids=[source_evidence["head_init"], source_evidence["head_forward"]],
        ),
        DiscrepancyRecord(
            discrepancy_id="discrepancy:patchtst.norm",
            subject="Encoder normalization",
            reference_claim="The encoder norm may be assumed to be LayerNorm.",
            source_finding="The selected constructor default is BatchNorm.",
            resolution="include-source-behavior",
            evidence_ids=[source_evidence["model_init"], config_evidence["norm"]],
        ),
        DiscrepancyRecord(
            discrepancy_id="discrepancy:patchtst.predicates",
            subject="Optional PatchTST paths",
            reference_claim="Decomposition, padding, individual head, and residual attention may appear unconditional.",
            source_finding="Each behavior is selected by a constructor or config predicate.",
            resolution="mark-conditional",
            evidence_ids=[source_evidence["model_init"], source_evidence["backbone_init"]],
        ),
        DiscrepancyRecord(
            discrepancy_id="discrepancy:patchtst.decomposition",
            subject="Decomposition topology",
            reference_claim="Decomposition can be drawn as annotation around one backbone.",
            source_finding="decomposition=true executes independent residual and trend backbones then adds outputs.",
            resolution="include-source-behavior",
            evidence_ids=[source_evidence["model_forward"], config_evidence["decomposition"]],
        ),
    ]
    return AnalysisBundle(snapshot, evidence, architecture, discrepancies)
