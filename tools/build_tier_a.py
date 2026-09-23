"""Build read-only, source-checked Tier A diagram contracts from bundled archives.

No archived code is imported or executed. A missing/changed source expression blocks
generation instead of silently turning a reference-image element into a fact.
"""

from __future__ import annotations

import hashlib
import itertools
import json
from pathlib import Path
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[2]
ASSETS = ROOT / "Constraint relationship of architecture diagram"
OUTPUT = Path(__file__).resolve().parents[1] / "desktop/public/tier-a"
FIXTURES = Path(__file__).resolve().parents[1] / "fixtures/tier_a_v1"


def item(
    key: str,
    label: str,
    file: str,
    snippet: str,
    *,
    parent: str | None = None,
    lane: str = "main",
    role: str = "module",
    shape: str = "",
    level: int = 1,
    repeat: str = "",
    occurrence: int | None = None,
) -> dict:
    return {
        "id": key,
        "label": label,
        "file": file,
        "snippet": snippet,
        "parent": parent,
        "lane": lane,
        "role": role,
        "shape": shape,
        "level": level,
        "repeat": repeat,
        "_occurrence": occurrence,
    }


def chain(*keys: str, kind: str = "main") -> list[dict]:
    return [{"source": a, "target": b, "kind": kind} for a, b in itertools.pairwise(keys)]


T = "pytorch_transformer_original/transformer.py"
A = "Autoformer-main/models/Autoformer.py"
AE = "Autoformer-main/layers/Autoformer_EncDec.py"
AC = "Autoformer-main/layers/AutoCorrelation.py"
I = "iTransformer/model/iTransformer.py"
IE = "iTransformer/layers/Embed.py"
IL = "iTransformer/layers/Transformer_EncDec.py"
P = "PatchTST/PatchTST_supervised/models/PatchTST.py"
PB = "PatchTST/PatchTST_supervised/layers/PatchTST_backbone.py"
M = "TimeMixer-main/models/TimeMixer.py"


def transformer():
    nodes = [
        item("src", "Source tokens", T, "src: [B, S]", lane="encoder", role="input", shape="[B,S]"),
        item(
            "src_embed",
            "Input embedding",
            T,
            "self.src_embedding(src)",
            lane="encoder",
            role="embedding",
            shape="[B,S,D]",
        ),
        item(
            "src_pos",
            "Sinusoidal position",
            T,
            "self.position(self.src_embedding(src))",
            lane="encoder",
            role="embedding",
        ),
        item(
            "encoder",
            "Encoder layers",
            T,
            "self.layers = clones(layer, num_layers)",
            lane="encoder",
            role="repeat",
            repeat="2 x",
            occurrence=0,
        ),
        item(
            "enc_layer_in",
            "Layer input",
            T,
            "query=x,",
            parent="encoder",
            lane="encoder",
            role="data",
            level=2,
            shape="[B,S,128]",
            occurrence=0,
        ),
        item(
            "enc_attn",
            "Self-attention",
            T,
            "self.self_attn = MultiHeadAttention",
            parent="encoder",
            lane="encoder",
            role="attention",
            level=2,
            occurrence=0,
        ),
        item(
            "enc_add1",
            "Add + LayerNorm",
            T,
            "x = self.norm1(x + self.dropout1(attn_out))",
            parent="encoder",
            lane="encoder",
            role="merge",
            level=2,
        ),
        item(
            "enc_ffn",
            "Feed forward",
            T,
            "self.ffn = PositionwiseFeedForward",
            parent="encoder",
            lane="encoder",
            role="ffn",
            level=2,
            occurrence=0,
        ),
        item(
            "enc_add2",
            "Add + LayerNorm",
            T,
            "x = self.norm2(x + self.dropout2(ffn_out))",
            parent="encoder",
            lane="encoder",
            role="merge",
            level=2,
        ),
        item(
            "memory",
            "Encoder memory",
            T,
            "memory = self.encode(src, src_key_padding_mask)",
            lane="encoder",
            role="data",
            shape="[B,S,D]",
        ),
        item(
            "tgt",
            "Target prefix tokens",
            T,
            "tgt: [B, T]",
            lane="decoder",
            role="input",
            shape="[B,T]",
        ),
        item(
            "tgt_embed",
            "Output embedding",
            T,
            "self.tgt_embedding(tgt)",
            lane="decoder",
            role="embedding",
            shape="[B,T,D]",
        ),
        item(
            "tgt_pos",
            "Sinusoidal position",
            T,
            "self.position(self.tgt_embedding(tgt))",
            lane="decoder",
            role="embedding",
        ),
        item(
            "decoder",
            "Decoder layers",
            T,
            "self.layers = clones(layer, num_layers)",
            lane="decoder",
            role="repeat",
            repeat="2 x",
            occurrence=1,
        ),
        item(
            "dec_layer_in",
            "Layer input",
            T,
            "query=x,",
            parent="decoder",
            lane="decoder",
            role="data",
            level=2,
            shape="[B,T,128]",
            occurrence=1,
        ),
        item(
            "dec_self",
            "Masked self-attention",
            T,
            "self_attn_out = self.self_attn(",
            parent="decoder",
            lane="decoder",
            role="attention",
            level=2,
        ),
        item(
            "dec_add1",
            "Add + LayerNorm",
            T,
            "x = self.norm1(x + self.dropout1(self_attn_out))",
            parent="decoder",
            lane="decoder",
            role="merge",
            level=2,
        ),
        item(
            "dec_cross",
            "Cross-attention",
            T,
            "cross_attn_out = self.cross_attn(",
            parent="decoder",
            lane="decoder",
            role="attention",
            level=2,
        ),
        item(
            "dec_add2",
            "Add + LayerNorm",
            T,
            "x = self.norm2(x + self.dropout2(cross_attn_out))",
            parent="decoder",
            lane="decoder",
            role="merge",
            level=2,
        ),
        item(
            "dec_ffn",
            "Feed forward",
            T,
            "ffn_out = self.ffn(x)",
            parent="decoder",
            lane="decoder",
            role="ffn",
            level=2,
            occurrence=1,
        ),
        item(
            "dec_add3",
            "Add + LayerNorm",
            T,
            "x = self.norm3(x + self.dropout3(ffn_out))",
            parent="decoder",
            lane="decoder",
            role="merge",
            level=2,
        ),
        item(
            "head",
            "Vocabulary linear",
            T,
            "return self.generator(decoder_out)",
            lane="decoder",
            role="head",
            shape="[B,T,V]",
        ),
        item(
            "logits",
            "Output logits",
            T,
            "logits: [B, T, tgt_vocab_size]",
            lane="decoder",
            role="output",
            shape="[B,T,V]",
        ),
    ]
    edges = chain("src", "src_embed", "src_pos", "encoder", "memory") + chain(
        "tgt", "tgt_embed", "tgt_pos", "decoder", "head", "logits"
    )
    edges += chain("enc_layer_in", "enc_attn", "enc_add1", "enc_ffn", "enc_add2")
    edges += chain(
        "dec_layer_in", "dec_self", "dec_add1", "dec_cross", "dec_add2", "dec_ffn", "dec_add3"
    )
    edges += [
        {
            "source": "memory",
            "target": "c_k",
            "kind": "memory",
            "source_port": "memory_out",
            "target_port": "K_in",
        },
        {
            "source": "memory",
            "target": "c_v",
            "kind": "memory",
            "source_port": "memory_out",
            "target_port": "V_in",
        },
        {
            "source": "dec_add1",
            "target": "c_q",
            "kind": "main",
            "source_port": "hidden_out",
            "target_port": "Q_in",
        },
    ]
    for prefix, parent, snippet in [
        ("e", "enc_attn", "self.w_q(query)"),
        ("s", "dec_self", "self.w_q(query)"),
        ("c", "dec_cross", "self.w_q(query)"),
    ]:
        lane = "encoder" if prefix == "e" else "decoder"
        for role, expression in [
            ("Q", "self.w_q(query)"),
            ("K", "self.w_k(key)"),
            ("V", "self.w_v(value)"),
        ]:
            nodes.append(
                item(
                    f"{prefix}_{role.lower()}",
                    f"{role} projection",
                    T,
                    expression,
                    parent=parent,
                    lane=lane,
                    role="projection",
                    level=3,
                    shape=f"[B,H,{'S' if prefix == 'e' or (prefix == 'c' and role != 'Q') else 'T'},16]",
                )
            )
        detail_steps = [
            ("score", "Q x K transpose", "torch.matmul(q, k.transpose(-2, -1))", 4),
            ("scale", "Scale 1/sqrt(Dh)", "/ math.sqrt(d_k)", 4),
            *(
                [
                    ("mask", "Causal mask", "attn_mask=tgt_mask", 4),
                    (
                        "apply_mask",
                        "Apply causal mask",
                        'scores = scores.masked_fill(attn_mask, float("-inf"))',
                        4,
                    ),
                ]
                if prefix == "s"
                else []
            ),
            ("softmax", "Softmax weights", "torch.softmax(scores, dim=-1)", 4),
            ("weighted", "Weights x V", "torch.matmul(attention_weights, v)", 4),
            ("combine", "Combine heads", "self._combine_heads(x)", 3),
            ("out", "W^O output", "self.w_o(x)", 3),
        ]
        for key, label, expression, level in detail_steps:
            nodes.append(
                item(
                    f"{prefix}_{key}",
                    label,
                    T,
                    expression,
                    parent=parent,
                    lane=lane,
                    role="condition"
                    if key in {"mask", "apply_mask"}
                    else "attention"
                    if key in {"score", "softmax", "weighted"}
                    else "projection",
                    level=level,
                    shape=(
                        f"[B,8,{'S' if prefix == 'e' else 'T'},"
                        f"{'S' if prefix in {'e', 'c'} else 'T'}]"
                        if key in {"score", "scale", "softmax", "apply_mask"}
                        else "[T,T]"
                        if key == "mask"
                        else f"[B,8,{'S' if prefix == 'e' else 'T'},16]"
                        if key == "weighted"
                        else f"[B,{'S' if prefix == 'e' else 'T'},128]"
                    ),
                )
            )
        edges += chain(
            f"{prefix}_q",
            f"{prefix}_score",
            f"{prefix}_scale",
            *(["s_apply_mask"] if prefix == "s" else []),
            f"{prefix}_softmax",
            f"{prefix}_weighted",
            f"{prefix}_combine",
            f"{prefix}_out",
        )
        edges += [
            {
                "source": f"{prefix}_k",
                "target": f"{prefix}_score",
                "kind": "main",
                "target_port": "K_in",
            },
            {
                "source": f"{prefix}_v",
                "target": f"{prefix}_weighted",
                "kind": "main",
                "target_port": "V_in",
            },
        ]
        if prefix in {"e", "s"}:
            source = "enc_layer_in" if prefix == "e" else "dec_layer_in"
            edges += [
                {"source": source, "target": f"{prefix}_{role}", "kind": "main"}
                for role in ("q", "k", "v")
            ]
    edges.append(
        {
            "source": "s_mask",
            "target": "s_apply_mask",
            "kind": "condition",
            "target_port": "condition_in",
        }
    )
    for prefix, parent in [("ef", "enc_ffn"), ("df", "dec_ffn")]:
        lane = "encoder" if prefix == "ef" else "decoder"
        for key, label, snippet in [
            ("linear1", "Linear D -> F", "self.linear1(x)"),
            ("relu", "ReLU", "self.activation(self.linear1(x))"),
            ("linear2", "Linear F -> D", "self.linear2(self.dropout("),
        ]:
            nodes.append(
                item(
                    f"{prefix}_{key}",
                    label,
                    T,
                    snippet,
                    parent=parent,
                    lane=lane,
                    role="ffn",
                    level=3,
                    shape=f"[B,{'S' if prefix == 'ef' else 'T'},{512 if key == 'linear1' else 128}]"
                    if key != "relu"
                    else "",
                )
            )
        edges += chain(f"{prefix}_linear1", f"{prefix}_relu", f"{prefix}_linear2")
    for key, source, target, snippet in [
        ("er1", "enc_layer_in", "enc_add1", "x = self.norm1(x + self.dropout1(attn_out))"),
        ("er2", "enc_add1", "enc_add2", "x = self.norm2(x + self.dropout2(ffn_out))"),
        ("dr1", "dec_layer_in", "dec_add1", "x = self.norm1(x + self.dropout1(self_attn_out))"),
        ("dr2", "dec_add1", "dec_add2", "x = self.norm2(x + self.dropout2(cross_attn_out))"),
        ("dr3", "dec_add2", "dec_add3", "x = self.norm3(x + self.dropout3(ffn_out))"),
    ]:
        edges.append(
            {
                "source": source,
                "target": target,
                "kind": "residual",
                "evidence_file": T,
                "evidence_snippet": snippet,
                "source_port": "skip_out",
                "target_port": "skip_in",
            }
        )
    return nodes, edges


def autoformer():
    nodes = [
        item(
            "input",
            "Input series",
            A,
            "seasonal_init, trend_init = self.decomp(x_enc)",
            role="input",
            shape="[B,L,N]",
        ),
        item(
            "decomp",
            "Series decomposition",
            A,
            "seasonal_init, trend_init = self.decomp(x_enc)",
            role="decomposition",
        ),
        item(
            "enc_embed",
            "Value + temporal embedding",
            A,
            "enc_out = self.enc_embedding(x_enc, x_mark_enc)",
            lane="encoder",
            role="embedding",
        ),
        item(
            "encoder",
            "Encoder AutoCorrelation",
            A,
            "for l in range(configs.e_layers)",
            lane="encoder",
            role="repeat",
            repeat="2 x",
        ),
        item(
            "enc_corr",
            "AutoCorrelation + residual",
            AE,
            "self.attention(",
            parent="encoder",
            lane="encoder",
            level=2,
            role="attention",
        ),
        item(
            "enc_decomp1",
            "Progressive decomposition",
            AE,
            "self.decomp1(",
            parent="encoder",
            lane="encoder",
            level=2,
            role="decomposition",
            occurrence=0,
        ),
        item(
            "enc_ffn",
            "Conv1d feed forward",
            AE,
            "self.conv1(",
            parent="encoder",
            lane="encoder",
            level=2,
            role="ffn",
            occurrence=0,
        ),
        item(
            "enc_decomp2",
            "Progressive decomposition",
            AE,
            "self.decomp2(",
            parent="encoder",
            lane="encoder",
            level=2,
            role="decomposition",
            occurrence=0,
        ),
        item(
            "memory",
            "Encoder memory",
            A,
            "enc_out, attns = self.encoder(enc_out",
            lane="encoder",
            role="data",
        ),
        item(
            "dec_init",
            "Seasonal + trend initialization",
            A,
            "seasonal_init = torch.cat(",
            lane="decoder",
            role="decomposition",
        ),
        item(
            "dec_embed",
            "Value + temporal embedding",
            A,
            "dec_out = self.dec_embedding(seasonal_init",
            lane="decoder",
            role="embedding",
        ),
        item(
            "decoder",
            "Decoder AutoCorrelation",
            A,
            "for l in range(configs.d_layers)",
            lane="decoder",
            role="repeat",
            repeat="1 x",
        ),
        item(
            "self_corr",
            "Self AutoCorrelation",
            AE,
            "self.self_attention(",
            parent="decoder",
            lane="decoder",
            level=2,
            role="attention",
        ),
        item(
            "dec_decomp1",
            "Progressive decomposition",
            AE,
            "self.decomp1(",
            parent="decoder",
            lane="decoder",
            level=2,
            role="decomposition",
            occurrence=1,
        ),
        item(
            "cross_corr",
            "Cross AutoCorrelation",
            AE,
            "self.cross_attention(",
            parent="decoder",
            lane="decoder",
            level=2,
            role="attention",
        ),
        item(
            "dec_decomp2",
            "Progressive decomposition",
            AE,
            "self.decomp2(",
            parent="decoder",
            lane="decoder",
            level=2,
            role="decomposition",
            occurrence=1,
        ),
        item(
            "dec_ffn",
            "Conv1d feed forward",
            AE,
            "self.conv1(",
            parent="decoder",
            lane="decoder",
            level=2,
            role="ffn",
            occurrence=1,
        ),
        item(
            "dec_decomp3",
            "Progressive decomposition",
            AE,
            "self.decomp3(x + y)",
            parent="decoder",
            lane="decoder",
            level=2,
            role="decomposition",
        ),
        item(
            "trend",
            "Accumulate residual trend",
            AE,
            "trend = trend + residual_trend",
            parent="decoder",
            lane="decoder",
            level=2,
            role="decomposition",
        ),
        item(
            "result",
            "Seasonal + trend",
            A,
            "dec_out = trend_part + seasonal_part",
            lane="decoder",
            role="merge",
        ),
        item(
            "output",
            "Forecast",
            A,
            "return dec_out[:, -self.pred_len:, :]  # [B, L, D]",
            lane="decoder",
            role="output",
            shape="[B,H,N]",
        ),
    ]
    edges = chain("input", "decomp", "enc_embed", "encoder", "memory") + chain(
        "decomp", "dec_init", "dec_embed", "decoder", "result", "output"
    )
    edges += chain("enc_corr", "enc_decomp1", "enc_ffn", "enc_decomp2") + chain(
        "self_corr", "dec_decomp1", "cross_corr", "dec_decomp2", "dec_ffn", "dec_decomp3", "trend"
    )
    for prefix, parent, lane in [
        ("e", "enc_corr", "encoder"),
        ("d", "self_corr", "decoder"),
        ("c", "cross_corr", "decoder"),
    ]:
        for key, label, snippet, shape in [
            ("q", "Q projection", "queries = self.query_projection(queries).view(", "[B,Lq,8,64]"),
            ("k", "K projection", "keys = self.key_projection(keys).view(", "[B,Lk,8,64]"),
            ("v", "V projection", "values = self.value_projection(values).view(", "[B,Lv,8,64]"),
        ]:
            nodes.append(
                item(
                    f"{prefix}_{key}",
                    label,
                    AC,
                    snippet,
                    parent=parent,
                    lane=lane,
                    role="projection",
                    level=3,
                    shape=shape,
                )
            )
        for key, label, snippet in [
            ("fft", "FFT correlation", "q_fft = torch.fft.rfft("),
            ("delay", "Top-k delays", "weights, delay = torch.topk(mean_value, top_k, dim=-1)"),
            ("aggregate", "Time-delay aggregation", "self.time_delay_agg_inference("),
        ]:
            nodes.append(
                item(
                    f"{prefix}_{key}",
                    label,
                    AC,
                    snippet,
                    parent=parent,
                    lane=lane,
                    role="attention",
                    level=4,
                )
            )
        edges += chain(f"{prefix}_q", f"{prefix}_fft", f"{prefix}_delay", f"{prefix}_aggregate")
        edges += [
            {"source": f"{prefix}_k", "target": f"{prefix}_fft", "kind": "main", "target_port": "K_in"},
            {"source": f"{prefix}_v", "target": f"{prefix}_aggregate", "kind": "main", "target_port": "V_in"},
        ]
    edges += [
        {
            "source": "memory",
            "target": "c_k",
            "kind": "memory",
            "source_port": "memory_out",
            "target_port": "K_in",
        },
        {
            "source": "memory",
            "target": "c_v",
            "kind": "memory",
            "source_port": "memory_out",
            "target_port": "V_in",
        },
    ]
    return nodes, edges


def itransformer():
    nodes = [
        item(
            "input", "Input time series", I, "_, _, N = x_enc.shape", role="input", shape="[B,L,N]"
        ),
        item(
            "norm",
            "Series normalization",
            I,
            "if self.use_norm:",
            role="normalization",
            occurrence=0,
        ),
        item(
            "invert",
            "Invert time / variable axes",
            IE,
            "x.permute(0, 2, 1)",
            role="transform",
            shape="[B,N,L]",
            occurrence=1,
        ),
        item(
            "embed",
            "Variable-token projection",
            IE,
            "self.value_embedding(x)",
            role="embedding",
            shape="[B,N,D]",
            occurrence=1,
        ),
        item(
            "encoder",
            "Variable-token encoder",
            I,
            "for l in range(configs.e_layers)",
            role="repeat",
            repeat="2 x",
        ),
        item(
            "attention",
            "Self-attention over variables",
            IL,
            "self.attention(",
            parent="encoder",
            level=2,
            role="attention",
        ),
        item(
            "add1",
            "Residual + LayerNorm",
            IL,
            "self.norm1(",
            parent="encoder",
            level=2,
            role="merge",
            occurrence=0,
        ),
        item(
            "ffn",
            "1x1 Conv feed forward",
            IL,
            "self.conv1(",
            parent="encoder",
            level=2,
            role="ffn",
            occurrence=0,
        ),
        item(
            "add2",
            "Residual + LayerNorm",
            IL,
            "self.norm2(",
            parent="encoder",
            level=2,
            role="merge",
            occurrence=0,
        ),
        item(
            "project",
            "Project D -> horizon",
            I,
            "self.projector(enc_out).permute(0, 2, 1)",
            role="head",
            shape="[B,N,H]",
        ),
        item(
            "restore",
            "Restore forecast axes",
            I,
            ".permute(0, 2, 1)[:, :, :N]",
            role="transform",
            shape="[B,H,N]",
        ),
        item("denorm", "De-normalization", I, "dec_out = dec_out * (stdev", role="normalization"),
        item(
            "output",
            "Forecast",
            I,
            "return dec_out[:, -self.pred_len:, :]  # [B, L, D]",
            role="output",
            shape="[B,H,N]",
        ),
    ]
    edges = chain(
        "input", "norm", "invert", "embed", "encoder", "project", "restore", "denorm", "output"
    ) + chain("attention", "add1", "ffn", "add2")
    for key, label, file, snippet in [
        (
            "q",
            "Q projection",
            "iTransformer/layers/SelfAttention_Family.py",
            "queries = self.query_projection(queries).view(",
        ),
        (
            "k",
            "K projection",
            "iTransformer/layers/SelfAttention_Family.py",
            "keys = self.key_projection(keys).view(",
        ),
        (
            "v",
            "V projection",
            "iTransformer/layers/SelfAttention_Family.py",
            "values = self.value_projection(values).view(",
        ),
        (
            "score",
            "Variable attention scores",
            "iTransformer/layers/SelfAttention_Family.py",
            'scores = torch.einsum("blhe,bshe->bhls", queries, keys)',
        ),
        (
            "softmax",
            "Softmax weights",
            "iTransformer/layers/SelfAttention_Family.py",
            "A = self.dropout(torch.softmax(scale * scores, dim=-1))",
        ),
        (
            "context",
            "Weighted values",
            "iTransformer/layers/SelfAttention_Family.py",
            'V = torch.einsum("bhls,bshd->blhd", A, values)',
        ),
    ]:
        nodes.append(
            item(
                key,
                label,
                file,
                snippet,
                parent="attention",
                role="attention",
                level=3 if key in {"q", "k", "v"} else 4,
                shape="[B,N,8,64]"
                if key in {"q", "k", "v"}
                else "[B,8,N,N]"
                if key in {"score", "softmax"}
                else "[B,N,8,64]",
            )
        )
    edges += chain("q", "score", "softmax", "context")
    edges += [
        {"source": "k", "target": "score", "kind": "main", "target_port": "K_in"},
        {"source": "v", "target": "context", "kind": "main", "target_port": "V_in"},
    ]
    for key, label, snippet in [
        ("conv1", "1x1 Conv D -> F", "self.conv1(y.transpose(-1, 1))"),
        ("gelu", "GELU", "self.activation(self.conv1("),
        ("conv2", "1x1 Conv F -> D", "self.conv2(y).transpose(-1, 1)"),
    ]:
        nodes.append(item(key, label, IL, snippet, parent="ffn", role="ffn", level=3, occurrence=0))
    edges += chain("conv1", "gelu", "conv2")
    return nodes, edges


def patchtst():
    nodes = [
        item(
            "input", "Input time series", P, "def forward(self, x):", role="input", shape="[B,L,C]"
        ),
        item(
            "channel",
            "Channel-first axes",
            P,
            "x = x.permute(0,2,1)",
            role="transform",
            shape="[B,C,L]",
            occurrence=2,
        ),
        item(
            "revin", "RevIN normalization", PB, "self.revin_layer(z, 'norm')", role="normalization"
        ),
        item(
            "patch",
            "Unfold / patching",
            PB,
            ".unfold(dimension=-1",
            role="embedding",
            shape="[B,C,Np,P]",
        ),
        item(
            "embed", "Per-patch projection", PB, "self.W_P(", role="embedding", shape="[B,C,Np,D]"
        ),
        item(
            "position",
            "Learned position encoding",
            PB,
            "self.dropout(u + self.W_pos)",
            role="embedding",
        ),
        item(
            "encoder",
            "Channel-independent encoder",
            PB,
            "self.encoder(",
            role="repeat",
            repeat="3 x",
        ),
        item(
            "attention",
            "Multi-head self-attention",
            PB,
            "self.self_attn(",
            parent="encoder",
            role="attention",
            level=2,
            occurrence=0,
        ),
        item(
            "norm1",
            "Residual + BatchNorm",
            PB,
            "self.norm_attn(",
            parent="encoder",
            role="merge",
            level=2,
            occurrence=1,
        ),
        item("ffn", "GELU feed forward", PB, "self.ff(", parent="encoder", role="ffn", level=2),
        item(
            "norm2",
            "Residual + BatchNorm",
            PB,
            "self.norm_ffn(",
            parent="encoder",
            role="merge",
            level=2,
            occurrence=1,
        ),
        item(
            "flatten",
            "Flatten D x Np",
            PB,
            "x = self.flatten(x)",
            role="transform",
            shape="[B,C,D*Np]",
        ),
        item(
            "head", "Forecast linear head", PB, "x = self.linear(x)", role="head", shape="[B,C,H]"
        ),
        item(
            "denorm",
            "RevIN denormalization",
            PB,
            "self.revin_layer(z, 'denorm')",
            role="normalization",
        ),
        item("output", "Forecast", P, "return x", role="output", shape="[B,H,C]"),
    ]
    edges = chain(
        "input",
        "channel",
        "revin",
        "patch",
        "embed",
        "position",
        "encoder",
        "flatten",
        "head",
        "denorm",
        "output",
    ) + chain("attention", "norm1", "ffn", "norm2")
    for key, label, snippet, level, role in [
        ("q", "Q projection + split", "q_s = self.W_Q(Q).view(", 3, "projection"),
        ("k", "K projection + split", "k_s = self.W_K(K).view(", 3, "projection"),
        ("v", "V projection + split", "v_s = self.W_V(V).view(", 3, "projection"),
        (
            "scores",
            "Scaled QK scores",
            "attn_scores = torch.matmul(q, k) * self.scale",
            4,
            "attention",
        ),
        ("prev", "Previous-layer score residual", "attn_scores = attn_scores + prev", 4, "merge"),
        (
            "softmax",
            "Softmax weights",
            "attn_weights = F.softmax(attn_scores, dim=-1)",
            4,
            "attention",
        ),
        ("weighted", "Weights x V", "output = torch.matmul(attn_weights, v)", 4, "attention"),
        (
            "combine",
            "Combine heads",
            "output = output.transpose(1, 2).contiguous().view(",
            3,
            "transform",
        ),
        ("out", "Output projection", "output = self.to_out(output)", 3, "projection"),
    ]:
        nodes.append(
            item(
                key,
                label,
                PB,
                snippet,
                parent="attention",
                role=role,
                level=level,
                shape="[B*C,16,Np,8]"
                if key in {"q", "k", "v", "weighted"}
                else "[B*C,16,Np,Np]"
                if key in {"scores", "prev", "softmax"}
                else "[B*C,Np,128]",
            )
        )
    edges += chain("q", "scores", "prev", "softmax", "weighted", "combine", "out")
    edges += [
        {"source": "k", "target": "scores", "kind": "main", "target_port": "K_in"},
        {"source": "v", "target": "weighted", "kind": "main", "target_port": "V_in"},
    ]
    for key, label, snippet in [
        ("ffn_in", "Linear D -> F", "nn.Linear(d_model, d_ff, bias=bias)"),
        ("ffn_gelu", "GELU", "get_activation_fn(activation)"),
        ("ffn_out", "Linear F -> D", "nn.Linear(d_ff, d_model, bias=bias)"),
    ]:
        nodes.append(item(key, label, PB, snippet, parent="ffn", role="ffn", level=3))
    edges += chain("ffn_in", "ffn_gelu", "ffn_out")
    return nodes, edges


def timemixer():
    nodes = [
        item(
            "input",
            "Input time series",
            M,
            "def forecast(self, x_enc",
            role="input",
            shape="[B,L,N]",
        ),
        item(
            "pyramid",
            "Average-pool scale pyramid",
            M,
            "__multi_scale_process_inputs(x_enc",
            role="decomposition",
            shape="[96,48,24,12] x N",
            occurrence=0,
        ),
        item(
            "normalize",
            "Per-scale normalization",
            M,
            "self.normalize_layers[i](x, 'norm')",
            role="normalization",
            occurrence=1,
        ),
        item(
            "embedding",
            "Per-scale value + temporal embedding",
            M,
            "enc_out = self.enc_embedding(x, None)",
            role="embedding",
            occurrence=0,
        ),
        item(
            "blocks",
            "Past-decomposable mixing",
            M,
            "for _ in range(configs.e_layers)",
            role="repeat",
            repeat="2 x",
        ),
        item(
            "decomp",
            "Per-scale moving-average decomposition",
            M,
            "season, trend = self.decompsition(x)",
            parent="blocks",
            role="decomposition",
            level=2,
        ),
        item(
            "season",
            "Seasonal bottom-up mixing",
            M,
            "self.mixing_multi_scale_season(season_list)",
            parent="blocks",
            role="decomposition",
            level=2,
        ),
        item(
            "trend",
            "Trend top-down mixing",
            M,
            "self.mixing_multi_scale_trend(trend_list)",
            parent="blocks",
            role="decomposition",
            level=2,
        ),
        item(
            "merge",
            "Season + trend / residual",
            M,
            "out = out_season + out_trend",
            parent="blocks",
            role="merge",
            level=2,
        ),
        item(
            "predict",
            "Per-scale prediction",
            M,
            "self.predict_layers[i]",
            role="head",
            occurrence=1,
        ),
        item(
            "aggregate",
            "Sum scale forecasts",
            M,
            "torch.stack(dec_out_list, dim=-1).sum(-1)",
            role="merge",
            shape="[B,H,N]",
        ),
        item(
            "denorm",
            "De-normalization",
            M,
            "self.normalize_layers[0](dec_out, 'denorm')",
            role="normalization",
            occurrence=0,
        ),
        item(
            "output", "Forecast", M, "return dec_out", role="output", shape="[B,H,N]", occurrence=1
        ),
    ]
    edges = chain(
        "input",
        "pyramid",
        "normalize",
        "embedding",
        "blocks",
        "predict",
        "aggregate",
        "denorm",
        "output",
    )
    edges += [
        {"source": "decomp", "target": "season", "kind": "main"},
        {"source": "decomp", "target": "trend", "kind": "main"},
        {"source": "season", "target": "merge", "kind": "main"},
        {"source": "trend", "target": "merge", "kind": "main"},
    ]
    for key, label, snippet, parent, level in [
        (
            "moving_avg",
            "Moving average",
            "self.decompsition = series_decomp(configs.moving_avg)",
            "decomp",
            3,
        ),
        (
            "season_low",
            "Linear high -> low",
            "out_low_res = self.down_sampling_layers[i](out_high)",
            "season",
            3,
        ),
        ("season_add", "Low-scale residual add", "out_low = out_low + out_low_res", "season", 4),
        (
            "trend_high",
            "Linear low -> high",
            "out_high_res = self.up_sampling_layers[i](out_low)",
            "trend",
            3,
        ),
        ("trend_add", "High-scale residual add", "out_high = out_high + out_high_res", "trend", 4),
    ]:
        nodes.append(
            item(
                key,
                label,
                M,
                snippet,
                parent=parent,
                role="merge" if key.endswith("add") else "decomposition",
                level=level,
            )
        )
    edges += chain("season_low", "season_add") + chain("trend_high", "trend_add")
    return nodes, edges


MODELS = {
    "transformer": (
        "pytorch_transformer_original.zip",
        "transformer.py:Transformer.forward",
        "translation / teacher forcing",
        {
            "src_vocab_size": 100,
            "tgt_vocab_size": 120,
            "d_model": 128,
            "num_heads": 8,
            "num_encoder_layers": 2,
            "num_decoder_layers": 2,
            "d_ff": 512,
            "dropout": 0.1,
            "tie_tgt_embedding_and_generator": False,
            "src_len": 7,
            "tgt_len": 5,
            "causal_mask": True,
        },
        transformer,
    ),
    "autoformer": (
        "Autoformer-main.zip",
        "models/Autoformer.py:Model.forward",
        "long-term forecast",
        {
            "seq_len": 96,
            "label_len": 48,
            "pred_len": 96,
            "enc_in": 7,
            "dec_in": 7,
            "c_out": 7,
            "d_model": 512,
            "n_heads": 8,
            "d_ff": 2048,
            "e_layers": 2,
            "d_layers": 1,
            "moving_avg": 25,
            "factor": 3,
            "embed": "timeF",
            "freq": "h",
            "activation": "gelu",
            "dropout": 0.05,
            "output_attention": False,
            "execution_mode": "eval",
        },
        autoformer,
    ),
    "itransformer": (
        "iTransformer.zip",
        "model/iTransformer.py:Model.forecast",
        "long_term_forecast",
        {
            "seq_len": 96,
            "pred_len": 96,
            "enc_in": 7,
            "d_model": 512,
            "n_heads": 8,
            "d_ff": 2048,
            "e_layers": 2,
            "factor": 1,
            "embed": "timeF",
            "freq": "h",
            "activation": "gelu",
            "dropout": 0.1,
            "use_norm": True,
            "output_attention": False,
            "class_strategy": "projection",
            "x_mark_enc": None,
        },
        itransformer,
    ),
    "patchtst": (
        "PatchTST.zip",
        "PatchTST_supervised/models/PatchTST.py:Model.forward",
        "long-term forecast",
        {
            "seq_len": 336,
            "pred_len": 96,
            "enc_in": 7,
            "e_layers": 3,
            "n_heads": 16,
            "d_model": 128,
            "d_ff": 256,
            "dropout": 0.2,
            "fc_dropout": 0.2,
            "head_dropout": 0,
            "individual": False,
            "patch_len": 16,
            "stride": 8,
            "padding_patch": "end",
            "revin": True,
            "affine": False,
            "subtract_last": False,
            "decomposition": False,
            "kernel_size": 25,
            "norm": "BatchNorm",
            "act": "gelu",
            "res_attention": True,
            "pre_norm": False,
            "pe": "zeros",
            "learn_pe": True,
        },
        patchtst,
    ),
    "timemixer": (
        "TimeMixer-main.zip",
        "models/TimeMixer.py:Model.forecast",
        "long_term_forecast",
        {
            "seq_len": 96,
            "label_len": 48,
            "pred_len": 96,
            "enc_in": 7,
            "c_out": 7,
            "d_model": 16,
            "d_ff": 32,
            "e_layers": 2,
            "down_sampling_layers": 3,
            "down_sampling_window": 2,
            "down_sampling_method": "avg",
            "decomp_method": "moving_avg",
            "moving_avg": 25,
            "channel_independence": 0,
            "use_norm": 1,
            "use_future_temporal_feature": False,
            "embed": "timeF",
            "freq": "h",
            "dropout": 0.1,
            "x_mark_enc": None,
        },
        timemixer,
    ),
}


DISCREPANCIES = {
    "transformer": [
        ("图1/2/3.png", "Softmax probabilities", "forward returns logits; no output Softmax node"),
        ("图1.png", "N x 6", "example.py selects two independent encoder/decoder layers"),
    ],
    "autoformer": [
        ("Autoformer.png", "Positional Encoding", "DataEmbedding_wo_pos omits position"),
        (
            "Autoformer.png",
            "Add & Norm in each layer",
            "progressive decomposition follows residuals; stack-level my_Layernorm",
        ),
    ],
    "itransformer": [
        (
            "Itransformer.png",
            "Permute before embedding",
            "permutation is inside DataEmbedding_inverted",
        ),
        ("Itransformer.png", "optional normalization", "selected use_norm=True"),
    ],
    "patchtst": [
        ("PatchTST.png", "Linear D -> pred_len", "flatten D*Np before head projection"),
        ("PatchTST.png", "LayerNorm", "selected norm is BatchNorm"),
        ("PatchTST.png", "decomposition", "selected decomposition=False"),
    ],
    "timemixer": [
        (
            "TimeMixer.png",
            "three parallel Conv mixers",
            "source has bottom-up seasonal and top-down trend linear scale mixing",
        ),
        ("TimeMixer.png", "positional embedding", "source uses DataEmbedding_wo_pos"),
    ],
}


def build_model(name: str) -> dict:
    archive_name, entrypoint, task, config, factory = MODELS[name]
    archive = ASSETS / archive_name
    nodes, edges = factory()
    data: dict[str, list[str]] = {}
    with ZipFile(archive) as bundle:
        for node in nodes:
            path = node.pop("file")
            snippet = node.pop("snippet")
            occurrence = node.pop("_occurrence")
            if path not in data:
                data[path] = bundle.read(path).decode("utf-8-sig").splitlines()
            matches = [i + 1 for i, line in enumerate(data[path]) if snippet in line]
            if (
                not matches
                or (occurrence is None and len(matches) != 1)
                or (occurrence is not None and occurrence >= len(matches))
            ):
                raise ValueError(
                    f"{name}:{node['id']} ambiguous/missing source proof {path}: {snippet!r} matches={matches}"
                )
            node["evidence"] = {
                "file": path,
                "line": matches[occurrence or 0],
                "expression": snippet,
                "file_sha256": hashlib.sha256(bundle.read(path)).hexdigest(),
                "grade": "E1",
            }
        for edge in edges:
            if "evidence_snippet" in edge:
                path = edge.pop("evidence_file")
                snippet = edge.pop("evidence_snippet")
                matches = [i + 1 for i, line in enumerate(data[path]) if snippet in line]
                if not matches:
                    raise ValueError(f"{name}: missing edge proof {path}: {snippet!r}")
                edge["evidence"] = {
                    "file": path,
                    "line": matches[0],
                    "expression": snippet,
                    "grade": "E1",
                    "basis": "direct_residual_expression",
                }
            else:
                target_evidence = next(n["evidence"] for n in nodes if n["id"] == edge["target"])
                edge["evidence"] = {
                    **target_evidence,
                    "grade": "E3",
                    "basis": "target_call_site; route_requires_human_review",
                }
    ids = [node["id"] for node in nodes]
    if len(set(ids)) != len(ids):
        raise ValueError(f"{name}: duplicate canonical node")
    by_id = {node["id"]: node for node in nodes}
    for node in nodes:
        if node["parent"] and (
            node["parent"] not in by_id or node["level"] <= by_id[node["parent"]]["level"]
        ):
            raise ValueError(f"{name}: invalid containment: {node['id']}")
    for index, edge in enumerate(edges):
        if edge["source"] not in by_id or edge["target"] not in by_id:
            raise ValueError(f"{name}: dangling edge: {edge}")
        edge["id"] = f"{name}.edge.{index:03d}"
        edge.setdefault("source_port", "out")
        edge.setdefault("target_port", "in")
    return {
        "model": name,
        "archive": archive_name,
        "archive_sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
        "entrypoint": entrypoint,
        "task_branch": task,
        "config": config,
        "selection_status": "implementation_selected_pending_human_review",
        "nodes": nodes,
        "edges": edges,
        "discrepancies": [
            {
                "reference": r,
                "reference_sha256": {
                    image: hashlib.sha256((ASSETS / image).read_bytes()).hexdigest()
                    for image in (["图1.png", "图2.png", "图3.png"] if r == "图1/2/3.png" else [r])
                },
                "element": e,
                "resolution": d,
                "status": "review_pending",
            }
            for r, e, d in DISCREPANCIES[name]
        ],
    }


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    for name in MODELS:
        result = build_model(name)
        target = FIXTURES / name
        target.mkdir(parents=True, exist_ok=True)

        def write(path: Path, value: object) -> None:
            path.write_text(
                json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )

        write(OUTPUT / f"{name}.json", result)
        write(
            target / "approved-config-snapshot.json",
            {
                "archive": result["archive"],
                "archive_sha256": result["archive_sha256"],
                "entrypoint": result["entrypoint"],
                "task_branch": result["task_branch"],
                "config": result["config"],
                "approval_status": result["selection_status"],
            },
        )
        write(
            target / "source-identity.json",
            {
                "archive": result["archive"],
                "sha256": result["archive_sha256"],
                "files": {
                    node["evidence"]["file"]: node["evidence"]["file_sha256"]
                    for node in result["nodes"]
                },
            },
        )
        write(
            target / "module-ledger.json",
            [
                {key: value for key, value in node.items() if key != "evidence"}
                for node in result["nodes"]
            ],
        )
        write(
            target / "tensor-ledger.json",
            [
                {
                    "producer": node["id"],
                    "shape": node["shape"],
                    "dtype": "unresolved",
                    "consumer_ids": [
                        edge["target"] for edge in result["edges"] if edge["source"] == node["id"]
                    ],
                    "evidence": node["evidence"],
                }
                for node in result["nodes"]
                if node["shape"]
            ],
        )
        write(target / "edge-ledger.json", result["edges"])
        write(
            target / "evidence-ledger.json",
            {
                "nodes": {node["id"]: node["evidence"] for node in result["nodes"]},
                "edges": {edge["id"]: edge["evidence"] for edge in result["edges"]},
            },
        )
        write(target / "reference-discrepancy-ledger.json", result["discrepancies"])
        write(
            target / "capability-report.json",
            {
                "status": "implementation_sample_pending_review",
                "source_executed": False,
                "runtime_shapes_validated": False,
                "human_review_completed": False,
                "direct_full": "available_for_source_mapped_sample_only",
            },
        )
        print(f"{name}: {len(result['nodes'])} nodes / {len(result['edges'])} edges")


if __name__ == "__main__":
    main()
