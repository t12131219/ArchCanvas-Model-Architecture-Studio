from __future__ import annotations

from pathlib import Path

from archcanvas_publication import PublicationCompiler, StageLayout
from archcanvas_publication.patterns import PublicationPatternRegistry
from archcanvas_pytorch.static import PyTorchProjectStaticAdapter
from archcanvas_renderer import publication_preflight, render_svg

ROOT = Path(__file__).resolve().parents[2]


def _timesnet_exact():
    return PyTorchProjectStaticAdapter().analyze(
        ROOT / "fixtures" / "timesnet_pattern_v1" / "source",
        project_id="fixture:timesnet-pattern-v1",
        entrypoint="model.py:TimesNet",
        resolved_config={"e_layers": 2, "task_name": "long_term_forecast", "top_k": 2},
    )


def _transformer_exact():
    return PyTorchProjectStaticAdapter().analyze(
        ROOT / "fixtures" / "transformer_static_v1" / "source",
        project_id="fixture:transformer-pattern-v1",
        entrypoint="model.py:EncoderModel",
        resolved_config={"depth": 3},
    )


def test_timesnet_pattern_requires_and_carries_the_complete_source_signature() -> None:
    source, exact = _timesnet_exact()

    matches = PublicationPatternRegistry().match(exact)

    assert len(matches) == 1
    match = matches[0]
    assert match.pattern_id == "spectral_period_inception_block_v1"
    assert match.confidence.value == "confirmed"
    assert match.member_node_ids == ["node:timesnet.model"]
    assert match.resolved_parameters == {"e_layers": 2, "task_name": "long_term_forecast", "top_k": 2}
    assert len(match.source_anchor_ids) == 8
    assert set(match.source_anchor_ids) <= {anchor.anchor_id for anchor in source.anchors}
    assert set(match.source_anchor_ids) <= set(exact.node("node:timesnet.model").source_anchor_ids)


def test_timesnet_pattern_compiles_to_an_honest_repeat_group_and_schematic_only_preview() -> None:
    _, exact = _timesnet_exact()

    publication = PublicationCompiler().compile(exact)
    group = next(node for node in publication.nodes if node.node_id == "publication-node:spectral-period-blocks")
    scene = StageLayout().layout(publication)
    report = publication_preflight(publication, scene, render_svg(publication, scene))

    assert group.label == "Spectral Period Block"
    assert group.member_node_ids == ["node:timesnet.model"]
    assert publication.annotations[0].text == "Spectral period block repeated 2 times"
    assert [(miniature.miniature_id, miniature.disclosure.value) for miniature in publication.miniatures] == [
        ("miniature:input-flow-schematic", "illustrative"),
        ("miniature:spectral-period-schematic", "illustrative"),
        ("miniature:spectral-period-detail-inset", "evidence"),
    ]
    assert report.blocking is False


def test_timesnet_pattern_fails_closed_when_a_required_source_marker_is_missing() -> None:
    _, exact = _timesnet_exact()
    evidence = exact.metadata["publication_pattern_evidence"]
    assert isinstance(evidence, list)
    incomplete = [{**evidence[0], "markers": {"fft": "anchor:missing"}}]
    incomplete_exact = exact.model_copy(
        update={"metadata": {**exact.metadata, "publication_pattern_evidence": incomplete}}
    )

    assert PublicationPatternRegistry().match(incomplete_exact) == []
    assert all(
        node.label != "Spectral Period Block" for node in PublicationCompiler().compile(incomplete_exact).nodes
    )


def test_transformer_encoder_pattern_requires_repeat_norm_and_head_evidence() -> None:
    source, exact = _transformer_exact()

    matches = PublicationPatternRegistry().match(exact)

    assert len(matches) == 1
    match = matches[0]
    assert match.pattern_id == "encoder_attention_stack_v1"
    assert match.confidence.value == "confirmed"
    assert match.member_node_ids == ["node:encodermodel.layers"]
    assert set(match.source_anchor_ids) <= {anchor.anchor_id for anchor in source.anchors}
    assert set(match.source_anchor_ids) <= set(exact.node("node:encodermodel.layers").source_anchor_ids)
    assert match.detail_template == "encoder_attention_stack_detail_v1"


def test_transformer_encoder_pattern_fails_closed_without_forecast_head() -> None:
    _, exact = _transformer_exact()
    evidence = exact.metadata["publication_pattern_evidence"]
    assert isinstance(evidence, list)
    incomplete = [{**evidence[0], "markers": {"layer_construction": "anchor:missing"}}]
    incomplete_exact = exact.model_copy(
        update={"metadata": {**exact.metadata, "publication_pattern_evidence": incomplete}}
    )

    assert PublicationPatternRegistry().match(incomplete_exact) == []


def _write_cross_file_transformer(root: Path, *, include_cross_attention: bool = True) -> None:
    (root / "layers.py").write_text(
        """import torch.nn as nn

class EncoderLayer(nn.Module):
    def __init__(self):
        super().__init__()
        self.attention = nn.Identity()
        self.dropout = nn.Identity()
        self.norm1 = nn.LayerNorm(4)
        self.norm2 = nn.LayerNorm(4)
    def forward(self, x):
        new_x = self.attention(x)
        x = x + self.dropout(new_x)
        y = x = self.norm1(x)
        return self.norm2(x + y), None

class Encoder(nn.Module):
    def __init__(self, attn_layers, norm_layer=None):
        super().__init__()
        self.attn_layers = nn.ModuleList(attn_layers)
        self.norm = norm_layer
    def forward(self, x):
        for attn_layer in self.attn_layers:
            x, _ = attn_layer(x)
        return self.norm(x), None

class DecoderLayer(nn.Module):
    def __init__(self):
        super().__init__()
        self.self_attention = nn.Identity()
        self.cross_attention = nn.Identity()
        self.dropout = nn.Identity()
        self.norm1 = nn.LayerNorm(4)
        self.norm2 = nn.LayerNorm(4)
        self.norm3 = nn.LayerNorm(4)
    def forward(self, x, cross):
        x = x + self.dropout(self.self_attention(x))
        x = self.norm1(x)
        """
        + (
            "x = x + self.dropout(self.cross_attention(x, cross))\n"
            if include_cross_attention
            else "x = x\n"
        )
        + """        y = x = self.norm2(x)
        return self.norm3(x + y)

class Decoder(nn.Module):
    def __init__(self, layers, norm_layer=None, projection=None):
        super().__init__()
        self.layers = nn.ModuleList(layers)
        self.norm = norm_layer
        self.projection = projection
    def forward(self, x, cross):
        for layer in self.layers:
            x = layer(x, cross)
        x = self.norm(x)
        return self.projection(x)
""",
        encoding="utf-8",
    )
    (root / "model.py").write_text(
        """import torch.nn as nn
from layers import Decoder, DecoderLayer, Encoder, EncoderLayer

class Transformer(nn.Module):
    def __init__(self, configs):
        super().__init__()
        self.encoder = Encoder(
            [EncoderLayer() for _ in range(configs.e_layers)],
            norm_layer=nn.LayerNorm(4),
        )
        self.decoder = Decoder(
            [DecoderLayer() for _ in range(configs.d_layers)],
            norm_layer=nn.LayerNorm(4),
            projection=nn.Linear(4, 2),
        )
    def forecast(self, x, context):
        memory, _ = self.encoder(x)
        return self.decoder(x, memory)
    def forward(self, x, context):
        return self.forecast(x, context)
""",
        encoding="utf-8",
    )


def test_cross_file_transformer_patterns_require_root_containers_and_layer_order(tmp_path: Path) -> None:
    _write_cross_file_transformer(tmp_path)

    source, exact = PyTorchProjectStaticAdapter().analyze(
        tmp_path,
        project_id="fixture:cross-file-transformer-v1",
        entrypoint="model.py:Transformer",
        resolved_config={"task_name": "long_term_forecast", "e_layers": 2, "d_layers": 1, "n_heads": 2},
    )

    matches = PublicationPatternRegistry().match(exact)

    assert [(match.pattern_id, match.member_node_ids) for match in matches] == [
        ("encoder_attention_stack_v1", ["node:transformer.encoder"]),
        ("decoder_cross_attention_stack_v1", ["node:transformer.decoder"]),
    ]
    assert all(
        set(match.source_anchor_ids) <= {anchor.anchor_id for anchor in source.anchors}
        and set(match.source_anchor_ids) <= set(exact.node(match.member_node_ids[0]).source_anchor_ids)
        for match in matches
    )
    records = exact.metadata["publication_pattern_evidence"]
    assert isinstance(records, list)
    assert {record["pattern_id"] for record in records} == {
        "encoder_attention_stack_v1",
        "decoder_cross_attention_stack_v1",
    }
    assert all(record["component_files"] == {"Decoder": "layers.py", "DecoderLayer": "layers.py", "Transformer": "model.py"} or record["component_files"] == {"Encoder": "layers.py", "EncoderLayer": "layers.py", "Transformer": "model.py"} for record in records)
    publication = PublicationCompiler().compile(exact)
    scene = StageLayout().layout(publication)

    assert [
        (node.node_id, node.label, node.member_node_ids)
        for node in publication.nodes
        if node.kind.value == "repeat_group"
    ] == [
        ("publication-node:transformer-encoder", "Transformer Encoder", ["node:transformer.encoder"]),
        ("publication-node:transformer-decoder", "Transformer Decoder", ["node:transformer.decoder"]),
    ]
    assert [annotation.text for annotation in publication.annotations] == [
        "Repeated 2 times",
        "Repeated 1 times",
    ]
    assert publication_preflight(publication, scene, render_svg(publication, scene)).blocking is False


def test_cross_file_transformer_decoder_pattern_fails_closed_without_cross_attention(tmp_path: Path) -> None:
    _write_cross_file_transformer(tmp_path, include_cross_attention=False)

    _, exact = PyTorchProjectStaticAdapter().analyze(
        tmp_path,
        project_id="fixture:cross-file-transformer-negative-v1",
        entrypoint="model.py:Transformer",
        resolved_config={"task_name": "long_term_forecast", "e_layers": 2, "d_layers": 1},
    )

    assert [match.pattern_id for match in PublicationPatternRegistry().match(exact)] == [
        "encoder_attention_stack_v1"
    ]


def test_cross_file_attention_stacks_do_not_depend_on_transformer_symbol_names(tmp_path: Path) -> None:
    _write_cross_file_transformer(tmp_path)
    replacements = (
        ("EncoderLayer", "SourceAttentionCell"),
        ("DecoderLayer", "TargetAttentionCell"),
        ("Transformer", "SequenceAssembly"),
        ("Encoder", "SourceStack"),
        ("Decoder", "TargetStack"),
    )
    for source_path in tmp_path.glob("*.py"):
        source = source_path.read_text(encoding="utf-8")
        for old, new in replacements:
            source = source.replace(old, new)
        source_path.write_text(source, encoding="utf-8")

    _, exact = PyTorchProjectStaticAdapter().analyze(
        tmp_path,
        project_id="fixture:renamed-attention-stack-v1",
        entrypoint="model.py:SequenceAssembly",
        resolved_config={"e_layers": 2, "d_layers": 1},
    )

    assert [(match.pattern_id, match.member_node_ids) for match in PublicationPatternRegistry().match(exact)] == [
        ("encoder_attention_stack_v1", ["node:sequenceassembly.encoder"]),
        ("decoder_cross_attention_stack_v1", ["node:sequenceassembly.decoder"]),
    ]


def _write_duet_pattern_sources(
    root: Path,
    *,
    include_gumbel_sample: bool = True,
    include_series_fusion: bool = True,
) -> None:
    _write_cross_file_transformer(root)
    (root / "decomp.py").write_text(
        """import torch.nn as nn

class moving_avg(nn.Module):
    def forward(self, x):
        return x

class series_decomp(nn.Module):
    def __init__(self):
        super().__init__()
        self.moving_avg = moving_avg()
    def forward(self, x):
        moving_mean = self.moving_avg(x)
        residual = x - moving_mean
        return residual, moving_mean
""",
        encoding="utf-8",
    )
    (root / "linear.py").write_text(
        """import torch.nn as nn
from decomp import series_decomp

class Linear_extractor(nn.Module):
    def __init__(self):
        super().__init__()
        self.decompsition = series_decomp()
        self.Linear_Seasonal = nn.Linear(4, 4)
        self.Linear_Trend = nn.Linear(4, 4)
    def encoder(self, x):
        seasonal_init, trend_init = self.decompsition(x)
        seasonal_output = self.Linear_Seasonal(seasonal_init)
        trend_output = self.Linear_Trend(trend_init)
        """
        + ("return seasonal_output + trend_output\n" if include_series_fusion else "return seasonal_output\n")
        + """    def forward(self, x):
        return self.encoder(x)
""",
        encoding="utf-8",
    )
    (root / "router.py").write_text(
        """import torch.nn as nn
from linear import Linear_extractor as expert

class Linear_extractor_cluster(nn.Module):
    def __init__(self):
        super().__init__()
        self.num_experts = 2
        self.experts = nn.ModuleList([expert() for _ in range(self.num_experts)])
        self.gate = nn.Identity()
        self.noise = nn.Identity()
        self.softmax = nn.Softmax(1)
        self.revin = nn.Identity()
    def noisy_top_k_gating(self, x):
        logits = self.softmax(x)
        top_logits, top_indices = logits.topk(1, dim=1)
        return top_logits, top_indices
    def forward(self, x):
        gates, _ = self.noisy_top_k_gating(x)
        dispatcher = SparseDispatcher(self.num_experts, gates)
        expert_inputs = dispatcher.dispatch(x)
        expert_outputs = [self.experts[i](expert_inputs[i]) for i in range(self.num_experts)]
        return dispatcher.combine(expert_outputs), gates
""",
        encoding="utf-8",
    )
    (root / "mask.py").write_text(
        """import torch
import torch.nn as nn
from torch.nn.functional import gumbel_softmax

class Mahalanobis_mask(nn.Module):
    def calculate_prob_distance(self, x):
        xf = torch.fft.rfft(x, dim=-1)
        diff = xf.unsqueeze(2) - xf.unsqueeze(1)
        metric = torch.einsum("ij,bcj->bci", diff, diff)
        return torch.einsum("bci,bci->bc", metric, metric)
    def bernoulli_gumbel_rsample(self, probability):
        """
        + (
            "return gumbel_softmax(probability, hard=True)\n"
            if include_gumbel_sample
            else "return probability\n"
        )
        + """    def forward(self, x):
        probability = self.calculate_prob_distance(x)
        return self.bernoulli_gumbel_rsample(probability)
""",
        encoding="utf-8",
    )
    (root / "model.py").write_text(
        """import torch.nn as nn
from layers import Encoder, EncoderLayer
from mask import Mahalanobis_mask
from router import Linear_extractor_cluster

class DUETModel(nn.Module):
    def __init__(self, configs):
        super().__init__()
        self.cluster = Linear_extractor_cluster()
        self.mask_generator = Mahalanobis_mask()
        self.Channel_transformer = Encoder(
            [EncoderLayer() for _ in range(configs.e_layers)],
            norm_layer=nn.LayerNorm(4),
        )
        self.linear_head = nn.Sequential(nn.Linear(4, 2), nn.Dropout(0.0))
    def forward(self, input):
        temporal_feature, _ = self.cluster(input)
        channel_mask = self.mask_generator(input)
        channel_feature, _ = self.Channel_transformer(temporal_feature, attn_mask=channel_mask)
        output = self.linear_head(channel_feature)
        return self.cluster.revin(output, "denorm")
""",
        encoding="utf-8",
    )


def test_cross_file_duet_patterns_require_independent_router_mask_and_encoder_evidence(
    tmp_path: Path,
) -> None:
    _write_duet_pattern_sources(tmp_path)

    source, exact = PyTorchProjectStaticAdapter().analyze(
        tmp_path,
        project_id="fixture:duet-pattern-v1",
        entrypoint="model.py:DUETModel",
        resolved_config={"e_layers": 2, "k": 1, "num_experts": 2, "n_heads": 2},
    )

    matches = PublicationPatternRegistry().match(exact)

    assert [(match.pattern_id, match.member_node_ids) for match in matches] == [
        ("topk_expert_router_v1", ["node:duetmodel.cluster"]),
        ("frequency_gumbel_mask_v1", ["node:duetmodel.mask_generator"]),
        ("masked_attention_stack_v1", ["node:duetmodel.Channel_transformer"]),
        ("decomposition_linear_fusion_v1", ["node:duetmodel.cluster"]),
    ]
    assert all(
        set(match.source_anchor_ids) <= {anchor.anchor_id for anchor in source.anchors}
        and set(match.source_anchor_ids) <= set(exact.node(match.member_node_ids[0]).source_anchor_ids)
        for match in matches
    )
    publication = PublicationCompiler().compile(exact)
    scene = StageLayout().layout(publication)

    assert [
        (node.node_id, node.label, node.member_node_ids)
        for node in publication.nodes
        if node.node_id in {
            "publication-node:expert-temporal-pattern-module",
            "publication-node:frequency-channel-mask",
            "publication-node:masked-temporal-channel-fusion",
        }
    ] == [
        (
            "publication-node:expert-temporal-pattern-module",
            "Temporal Pattern Module",
            ["node:duetmodel.cluster"],
        ),
        (
            "publication-node:frequency-channel-mask",
            "Channel Mask Generator",
            ["node:duetmodel.mask_generator"],
        ),
        (
            "publication-node:masked-temporal-channel-fusion",
            "Temporal-Channel Fusion",
            ["node:duetmodel.Channel_transformer"],
        ),
    ]
    assert [annotation.text for annotation in publication.annotations] == [
        "2 experts; Top-1 routing",
        "Repeated 2 times",
    ]
    assert [(miniature.miniature_id, miniature.disclosure.value) for miniature in publication.miniatures] == [
        ("miniature:expert-router-schematic", "illustrative"),
        ("miniature:decomposition-linear-fusion-inset", "evidence"),
        ("miniature:frequency-mask-schematic", "illustrative"),
        ("miniature:masked-attention-stack-inset", "evidence"),
        ("miniature:input-flow-schematic", "illustrative"),
    ]
    assert publication_preflight(publication, scene, render_svg(publication, scene)).blocking is False


def test_cross_file_multibranch_patterns_do_not_depend_on_benchmark_symbol_names(
    tmp_path: Path,
) -> None:
    _write_duet_pattern_sources(tmp_path)
    replacements = (
        ("Linear_extractor_cluster", "ExpertRouter"),
        ("Linear_extractor", "SeasonalTrendProjector"),
        ("Mahalanobis_mask", "FrequencySelector"),
        ("Channel_transformer", "masked_stack"),
        ("EncoderLayer", "AttentionUnit"),
        ("DecoderLayer", "CrossAttentionUnit"),
        ("series_decomp", "TrendDecomposer"),
        ("moving_avg", "WindowAverager"),
        ("Encoder", "AttentionStack"),
        ("Decoder", "CrossAttentionStack"),
        ("DUETModel", "ForecastAssembly"),
        ("mask_generator", "selector"),
        ("linear_head", "prediction_head"),
        ("cluster", "router"),
    )
    for source_path in tmp_path.glob("*.py"):
        source = source_path.read_text(encoding="utf-8")
        for old, new in replacements:
            source = source.replace(old, new)
        source_path.write_text(source, encoding="utf-8")

    _, exact = PyTorchProjectStaticAdapter().analyze(
        tmp_path,
        project_id="fixture:renamed-multibranch-pattern-v1",
        entrypoint="model.py:ForecastAssembly",
        resolved_config={"e_layers": 2, "k": 1, "num_experts": 2},
    )

    assert [(match.pattern_id, match.member_node_ids) for match in PublicationPatternRegistry().match(exact)] == [
        ("topk_expert_router_v1", ["node:forecastassembly.router"]),
        ("frequency_gumbel_mask_v1", ["node:forecastassembly.selector"]),
        ("masked_attention_stack_v1", ["node:forecastassembly.masked_stack"]),
        ("decomposition_linear_fusion_v1", ["node:forecastassembly.router"]),
    ]


def test_cross_file_duet_frequency_pattern_fails_closed_without_gumbel_sampling(tmp_path: Path) -> None:
    _write_duet_pattern_sources(tmp_path, include_gumbel_sample=False)

    _, exact = PyTorchProjectStaticAdapter().analyze(
        tmp_path,
        project_id="fixture:duet-pattern-negative-v1",
        entrypoint="model.py:DUETModel",
        resolved_config={"e_layers": 2, "num_experts": 2},
    )

    assert [match.pattern_id for match in PublicationPatternRegistry().match(exact)] == [
        "topk_expert_router_v1",
        "masked_attention_stack_v1",
        "decomposition_linear_fusion_v1",
    ]


def test_cross_file_duet_series_pattern_fails_closed_without_seasonal_trend_fusion(
    tmp_path: Path,
) -> None:
    _write_duet_pattern_sources(tmp_path, include_series_fusion=False)

    _, exact = PyTorchProjectStaticAdapter().analyze(
        tmp_path,
        project_id="fixture:duet-series-negative-v1",
        entrypoint="model.py:DUETModel",
        resolved_config={"e_layers": 2, "num_experts": 2},
    )

    assert [match.pattern_id for match in PublicationPatternRegistry().match(exact)] == [
        "topk_expert_router_v1",
        "frequency_gumbel_mask_v1",
        "masked_attention_stack_v1",
    ]
