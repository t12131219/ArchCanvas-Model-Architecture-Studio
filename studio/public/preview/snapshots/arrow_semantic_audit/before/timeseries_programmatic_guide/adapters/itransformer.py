"""Explicit source-grounded adapter for the supplied iTransformer archive.

The source model is inspected as text/AST by the generator, never imported.
This adapter represents one ETTh1 forecasting profile, not all repository models.
"""
from spec import chain, op, parallel, ref


MODEL = "iTransformer/model/iTransformer.py"
EMBED = "iTransformer/layers/Embed.py"
ATTN = "iTransformer/layers/SelfAttention_Family.py"
ENC = "iTransformer/layers/Transformer_EncDec.py"


def _attention(prefix, parameter_scope):
    a = ref(ATTN, "AttentionLayer.forward")
    ai = ref(ATTN, "AttentionLayer.__init__")
    full = ref(ATTN, "FullAttention.forward")

    def projection(suffix, label, attr):
        return chain(prefix + "." + suffix, label, [
            op(prefix + "." + suffix + ".linear", "Linear " + label, "linear",
               [ai, a], "[B,T,D]", ["D -> H*d; independent weight"],
               parameter=parameter_scope + "." + attr),
            op(prefix + "." + suffix + ".heads", "Split heads", "tensor", a,
               "[B,T,H,d]", ["view; d=D/H=32"]),
        ], [ai, a], "[B,T,H,d]", expand=2)

    # A and V are separate operands. V must never pass through Softmax.
    weights = chain(prefix + ".weights", "QK -> weights", [
        parallel(prefix + ".qk", "Q / K projections", [
            projection("q", "Q", "query_projection"),
            projection("k", "K", "key_projection"),
        ], [ai, a], "(Q,K)", expand=2),
        op(prefix + ".scores", "QK contraction", "attention", full,
           "[B,H,T,T]", ["einsum blhe,bshe -> bhls"]),
        op(prefix + ".scale", "Scale scores", "attention", full,
           "[B,H,T,T]", ["1 / sqrt(d); no causal mask"]),
        op(prefix + ".softmax", "Softmax", "activation", full,
           "[B,H,T,T]", ["over key tokens"]),
        op(prefix + ".attn_drop", "Attention dropout", "control", full,
           "[B,H,T,T]", ["p=0.1; train only"]),
    ], full, "A: [B,H,T,T]", expand=2)
    return chain(prefix, "Full self-attention", [
        parallel(prefix + ".operands", "Weights / values", [
            weights, projection("v", "V", "value_projection"),
        ], [a, full], "(A,V)", expand=2),
        op(prefix + ".av", "A times V", "attention", full,
           "[B,T,H,d]", ["einsum bhls,bshd -> blhd"]),
        op(prefix + ".merge", "Merge heads", "tensor", a,
           "[B,T,D]", ["contiguous + view"]),
        op(prefix + ".out", "Output projection", "linear", [ai, a],
           "[B,T,D]", ["Linear H*d -> D"], parameter=parameter_scope + ".out_projection"),
    ], [ref(MODEL, "Model.__init__"), a, full], "[B,T,D]",
       ["H=8; mask_flag=False", "attention across variable / time tokens"], expand=2)


def _layer(number, expand):
    prefix = "it.enc" + str(number)
    scope = "encoder.attn_layers." + str(number - 1)
    src = ref(ENC, "EncoderLayer.forward")
    init = ref(ENC, "EncoderLayer.__init__")
    attn_res = chain(prefix + ".attention_residual", "Attention + residual", [
        _attention(prefix + ".attention", scope + ".attention"),
        op(prefix + ".attention_dropout", "Output dropout", "control", src,
           "[B,T,D]", ["p=0.1"]),
        op(prefix + ".add1", "Add residual", "mixing", src,
           "[B,T,D]", ["x + dropout(attention(x))"]),
    ], src, "[B,T,D]", expand=1, residual=True)
    ffn = chain(prefix + ".ffn", "Pointwise FFN", [
        op(prefix + ".ffn_transpose_in", "Transpose", "tensor", src,
           "[B,D,T]", ["swap token / feature axes"]),
        op(prefix + ".conv1", "Conv1d D -> F", "linear", [init, src],
           "[B,F,T]", ["kernel=1; tokenwise"], parameter=scope + ".conv1"),
        op(prefix + ".gelu", "GELU", "activation", [init, src],
           "[B,F,T]", ["activation=gelu"]),
        op(prefix + ".ffn_dropout1", "Dropout", "control", src,
           "[B,F,T]", ["p=0.1"]),
        op(prefix + ".conv2", "Conv1d F -> D", "linear", [init, src],
           "[B,D,T]", ["kernel=1; tokenwise"], parameter=scope + ".conv2"),
        op(prefix + ".ffn_transpose_out", "Transpose", "tensor", src,
           "[B,T,D]", ["restore token-first axes"]),
        op(prefix + ".ffn_dropout2", "Dropout", "control", src,
           "[B,T,D]", ["p=0.1"]),
    ], [init, src], "[B,T,D]", ["D=256; F=256"], expand=2)
    ffn_res = chain(prefix + ".ffn_residual", "FFN + residual", [
        ffn,
        op(prefix + ".add2", "Add residual", "mixing", src,
           "[B,T,D]", ["norm1 state + FFN state"]),
    ], src, "[B,T,D]", expand=1, residual=True)
    return chain(prefix, "Encoder layer " + str(number), [
        attn_res,
        op(prefix + ".norm1", "LayerNorm 1", "norm", [init, src],
           "[B,T,D]", ["post-attention; over D"], parameter=scope + ".norm1"),
        ffn_res,
        op(prefix + ".norm2", "LayerNorm 2", "norm", [init, src],
           "[B,T,D]", ["post-FFN; over D"], parameter=scope + ".norm2"),
    ], [ref(MODEL, "Model.__init__"), src], "[B,T,D]",
       ["same structure; independent layer parameters"], expand=expand,
       parameter_scope=scope)


def build():
    forecast = ref(MODEL, "Model.forecast")
    emb = ref(EMBED, "DataEmbedding_inverted.forward")
    emb_init = ref(EMBED, "DataEmbedding_inverted.__init__")
    embedding = chain("it.embedding", "Inverted embedding", [
        op("it.invert", "Invert axes", "tensor", emb,
           "[B,N,L]", ["permute(0,2,1); one variate = one token"]),
        op("it.concat", "Append time tokens", "mixing", emb,
           "[B,T,L]", ["concat along token axis; T=N+C", "selected: C=4; None -> C=0"]),
        op("it.embed_linear", "Temporal projection", "linear", [emb_init, emb],
           "[B,T,D]", ["Linear L=96 -> D=256; shared across tokens"],
           parameter="enc_embedding.value_embedding"),
        op("it.embed_dropout", "Embedding dropout", "control", emb,
           "[B,T,D]", ["p=0.1; no positional embedding"]),
    ], [emb_init, emb, forecast], "[B,T,D]", ["time axis becomes features"], expand=1)
    encoder = chain("it.encoder", "Encoder x 2", [
        _layer(1, 1),
        _layer(2, 3),
        op("it.encoder_norm", "Final LayerNorm", "norm",
           [ref(MODEL, "Model.__init__"), ref(ENC, "Encoder.forward")],
           "[B,T,D]", ["after both encoder layers"], parameter="encoder.norm"),
    ], [ref(MODEL, "Model.__init__"), ref(ENC, "Encoder.forward")],
       "[B,T,D]", ["layer 2 folded in all views", "layers have independent weights"], expand=1)
    head = chain("it.head", "Forecast projection", [
        op("it.project", "Linear D -> P", "linear",
           [ref(MODEL, "Model.__init__"), forecast], "[B,T,P]",
           ["P=96; same head across tokens"], parameter="projector"),
        op("it.restore", "Restore time axis", "tensor", forecast,
           "[B,P,T]", ["permute(0,2,1); after projection"]),
        op("it.select", "Keep N variates", "control", forecast,
           "[B,P,N]", ["[:, :, :N]; discard time-token forecasts"]),
    ], forecast, "[B,P,N]", expand=1)
    tree = chain("it.model", "iTransformer", [
        op("it.input", "Input time series", "input", forecast,
           "[B,L,N]", ["L=96; N=7"]),
        op("it.normalize", "Series normalize", "norm", forecast,
           "[B,L,N]", ["per-variate mean over L; mean.detach()", "std=sqrt(var(unbiased=False)+1e-5)", "(x-mean)/std; use_norm=True"]),
        embedding,
        encoder,
        head,
        op("it.denormalize", "Restore series scale", "norm", forecast,
           "[B,P,N]", ["forecast * saved_std + saved_mean"]),
        op("it.output", "Forecast", "output", ref(MODEL, "Model.forward"),
           "[B,96,7]", ["last P steps; output_attention=False"]),
    ], ref(MODEL, "Model"), "[B,P,N]", expand=0)
    return dict(
        key="itransformer", name="iTransformer", archive="iTransformer.zip",
        entry=ref(MODEL, "Model"),
        profile=dict(task="ETTh1 multivariate forecasting", seq_len=96, pred_len=96,
                     n_vars=7, covariates=4, tokens=11, d_model=256, d_ff=256,
                     n_heads=8, e_layers=2, dropout=0.1, activation="gelu",
                     use_norm=True, output_attention=False, embed="timeF", freq="h",
                     config_source="iTransformer/scripts/multivariate_forecasting/ETT/iTransformer_ETTh1.sh:5-22 + run.py defaults"),
        tree=tree,
        aux_inputs=[chain("it.marks", "Time covariates", [
            op("it.marks_input", "Time features", "input", forecast,
               "[B,L,C]", ["selected C=4; external x_mark_enc"]),
            op("it.marks_invert", "Invert time features", "tensor", emb,
               "[B,C,L]", ["permute(0,2,1)"]),
        ], [forecast, emb], "[B,C,L]", ["optional; absent when x_mark_enc=None"], expand=2)],
        extra_edges=[
            dict(src="it.marks", dst="it.concat", role="covariate",
                 label="time tokens", src_port="out", dst_port="side"),
            dict(src="it.normalize", dst="it.denormalize", role="statistics",
                 label="mean / std", src_port="out", dst_port="side"),
        ],
        facts=[
            "One variate is one token; attention is over T=N+C tokens, not L time steps.",
            "Inverted embedding uses Linear(seq_len,d_model), with no positional embedding.",
            "Optional x_mark_enc is appended as additional tokens before the same Linear.",
            "FullAttention(False) and attn_mask=None mean no causal mask in this forecast path.",
            "Encoder FFN is two kernel=1 Conv1d operations; GELU comes from selected CLI defaults.",
            "Both encoder layers have independent parameters; final Encoder LayerNorm is additional.",
            "Projection precedes output permutation; covariate forecasts are then discarded.",
            "Input series statistics are reused for output denormalization; this is distinct from dataset scaling.",
            "x_dec and x_mark_dec are accepted by forecast but unused in this model.",
        ],
        corrections=[
            "Reference figure reverses output permute/projector order; code projects D->P before permute.",
            "Reference figure omits covariate tokens, their output slicing, and series denormalization.",
            "Reference figure omits the encoder's final LayerNorm after the repeated layers.",
            "FFN labels now identify actual Conv1d(kernel=1) modules instead of only equivalent Linear operations.",
            "Attention internals now flow bottom-to-top; Q/K generate A while V reaches A*V independently.",
        ],
        symbols={
            MODEL: ["Model", "Model.__init__", "Model.forecast", "Model.forward"],
            EMBED: ["DataEmbedding_inverted", "DataEmbedding_inverted.__init__", "DataEmbedding_inverted.forward"],
            ATTN: ["AttentionLayer", "AttentionLayer.__init__", "AttentionLayer.forward", "FullAttention", "FullAttention.__init__", "FullAttention.forward"],
            ENC: ["EncoderLayer", "EncoderLayer.__init__", "EncoderLayer.forward", "Encoder", "Encoder.__init__", "Encoder.forward"],
            "iTransformer/data_provider/data_factory.py": ["data_provider"],
            "iTransformer/data_provider/data_loader.py": ["Dataset_ETT_hour.__read_data__"],
            "iTransformer/utils/timefeatures.py": ["time_features_from_frequency_str"],
        },
        legend=["B: batch; L: input time; P: forecast time; N: original variates",
                "C: time covariates; T=N+C; D: model width; F: FFN width; H: heads",
                "same color = same operator family, not shared parameters",
                "dashed side route = saved statistics; side input = time tokens"],
    )
