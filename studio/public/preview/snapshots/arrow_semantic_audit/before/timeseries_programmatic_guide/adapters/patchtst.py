"""Explicit, source-grounded adapter for the supervised PatchTST forecast path."""
from spec import chain, op, parallel, ref


BASE = "PatchTST/PatchTST_supervised/"
MODEL = BASE + "models/PatchTST.py"
BACK = BASE + "layers/PatchTST_backbone.py"
LAYERS = BASE + "layers/PatchTST_layers.py"
REVIN = BASE + "layers/RevIN.py"


def build():
    def r(symbol):
        return ref(BACK, symbol)

    extra_edges = []

    def encoder_layer(i, expand):
        prefix = "patch_layer%d" % i
        attention = chain(
            prefix + "_attention", "Self-attention", [
                parallel(prefix + "_qkv", "Q / K / V projections", [
                    op(prefix + "_q", "Linear Q + split", "linear", r("_MultiheadAttention.forward"),
                       "(BC,h,P,d)", ["D -> h*d; d=D/h"], param_identity="encoder.layers.%d.W_Q" % (i - 1)),
                    op(prefix + "_k", "Linear K + split", "linear", r("_MultiheadAttention.forward"),
                       "(BC,h,d,P)", ["Transpose K for QK"], param_identity="encoder.layers.%d.W_K" % (i - 1)),
                    op(prefix + "_v", "Linear V + split", "linear", r("_MultiheadAttention.forward"),
                       "(BC,h,P,d)", ["Independent value operand"], param_identity="encoder.layers.%d.W_V" % (i - 1)),
                ], r("_MultiheadAttention.forward"), "tuple(Q,K,V)", expand=2),
                chain(prefix + "_sdpa", "Scaled dot-product attention", [
                    parallel(prefix + "_sdpa_operands", "Attention weights and values", [
                        chain(prefix + "_weights", "QK -> attention weights", [
                            op(prefix + "_raw_scores", "QK / sqrt(d) + prev", "attention", r("_ScaledDotProductAttention.forward"),
                               "S%d:(BC,h,P,P)" % i,
                               ["Layer 1: prev=None" if i == 1 else "Layer 2: prev=S1", "No causal or padding mask"],
                               score_output=True, pre_softmax=True,
                               param_identity="encoder.layers.%d.sdp_attn.scale (fixed)" % (i - 1)),
                            op(prefix + "_softmax", "Softmax over key patches", "activation", r("_ScaledDotProductAttention.forward"),
                               "A:(BC,h,P,P)", ["dim=-1; normalize each query"]),
                            op(prefix + "_attention_dropout", "Attention dropout", "control", r("_ScaledDotProductAttention.forward"),
                               "A:(BC,h,P,P)", ["p=0.0 in selected profile"]),
                        ], r("_ScaledDotProductAttention.forward"), "A:(BC,h,P,P)",
                            expand=2, input_selector="Q,K"),
                        op(prefix + "_value_bypass", "V: independent value operand", "tensor", r("_ScaledDotProductAttention.forward"),
                           "V:(BC,h,P,d)", ["Bypass QK, scaling and Softmax"], input_selector="V"),
                    ], r("_ScaledDotProductAttention.forward"), "tuple(A,V)", expand=2, dispatch=True),
                    op(prefix + "_weighted_values", "A @ V", "attention", r("_ScaledDotProductAttention.forward"),
                       "Z:(BC,h,P,d)", ["Weights and V are separate operands"]),
                ], r("_ScaledDotProductAttention.forward"), "Z:(BC,h,P,d)",
                    ["Raw scores leave before Softmax"], expand=2),
                op(prefix + "_merge", "Merge + output projection", "linear", r("_MultiheadAttention.forward"),
                   "(BC,P,D)", ["Concat heads; Linear(h*d -> D)", "Output projection dropout"],
                   param_identity="encoder.layers.%d.to_out" % (i - 1)),
            ], [r("_MultiheadAttention.forward"), r("_ScaledDotProductAttention.forward")],
            "(BC,P,D)", expand=2)
        ffn = chain(prefix + "_ffn", "Position-wise FFN", [
            op(prefix + "_ff1", "Linear D -> F", "linear", r("TSTEncoderLayer.__init__"),
               "(BC,P,F)", param_identity="encoder.layers.%d.ff.0" % (i - 1)),
            op(prefix + "_gelu", "GELU", "activation", ref(LAYERS, "get_activation_fn"), "(BC,P,F)"),
            op(prefix + "_ffdrop", "Dropout", "control", r("TSTEncoderLayer.__init__"),
               "(BC,P,F)", ["p=0.05; identity at evaluation"]),
            op(prefix + "_ff2", "Linear F -> D", "linear", r("TSTEncoderLayer.__init__"),
               "(BC,P,D)", param_identity="encoder.layers.%d.ff.3" % (i - 1)),
        ], r("TSTEncoderLayer.__init__"), "(BC,P,D)", expand=2)
        layer = chain(prefix, "Encoder layer %d" % i, [
            chain(prefix + "_attn_res", "Attention + residual", [
                attention,
                op(prefix + "_attndrop", "Residual dropout", "control", r("TSTEncoderLayer.forward"),
                   "(BC,P,D)", ["p=0.05"]),
                op(prefix + "_attnadd", "Add input", "mixing", r("TSTEncoderLayer.forward"), "(BC,P,D)"),
            ], r("TSTEncoderLayer.forward"), "(BC,P,D)", expand=2, residual=True),
            op(prefix + "_bn1", "Post BatchNorm", "norm", [r("TSTEncoderLayer.__init__"), r("TSTEncoderLayer.forward")],
               "(BC,P,D)", ["Transpose -> BatchNorm1d(D) -> back", "Statistics over BC and P"],
               param_identity="encoder.layers.%d.norm_attn" % (i - 1)),
            chain(prefix + "_ffn_res", "FFN + residual", [
                ffn,
                op(prefix + "_ffnoutdrop", "Residual dropout", "control", r("TSTEncoderLayer.forward"),
                   "(BC,P,D)", ["p=0.05"]),
                op(prefix + "_ffnadd", "Add input", "mixing", r("TSTEncoderLayer.forward"), "(BC,P,D)"),
            ], r("TSTEncoderLayer.forward"), "(BC,P,D)", expand=2, residual=True),
            op(prefix + "_bn2", "Post BatchNorm", "norm", [r("TSTEncoderLayer.__init__"), r("TSTEncoderLayer.forward")],
               "(BC,P,D)", ["Post-norm; pre_norm=False"],
               param_identity="encoder.layers.%d.norm_ffn" % (i - 1)),
        ], [r("TSTEncoderLayer.forward"), r("TSTEncoder.__init__")], "(BC,P,D)",
            ["Independent parameters by layer", "Shared encoder across variables"], expand=expand,
            param_identity="encoder.layers.%d" % (i - 1))
        return layer

    # The second layer remains in the IR but is folded in the three views.
    # Its score endpoint projects to its visible layer boundary.
    encoder = chain("patch_encoder", "Channel-independent encoder", [
        encoder_layer(1, 2), encoder_layer(2, 3),
    ], [r("TSTiEncoder.forward"), r("TSTEncoder.forward")], "(BC,P,D)",
        ["N=2 independent layers", "Same weights for all C variables", "Pre-softmax scores propagate between layers"], expand=1)
    extra_edges.append(dict(src="patch_layer1_raw_scores", dst="patch_layer2_raw_scores",
                            role="scores", label="S1: pre-softmax scores",
                            src_port="scores", dst_port="side"))

    tree = chain("patchtst", "PatchTST supervised forecast", [
        op("patch_input", "Input time series", "input", ref(MODEL, "Model.forward"), "(B,L,C)"),
        op("patch_to_channels", "Permute to channels", "tensor", ref(MODEL, "Model.forward"), "(B,C,L)",
           ["Model interface is time-major"]),
        op("patch_revin_norm", "RevIN normalize", "norm", [r("PatchTST_backbone.forward"), ref(REVIN, "RevIN._normalize")],
           "(B,C,L)", ["Per-sample, per-variable mean / stdev", "affine=False; stats retained for denorm"]),
        chain("patch_patching", "End padding + patching", [
            op("patch_pad", "Repeat endpoint s times", "tensor", r("PatchTST_backbone.__init__"),
               "(B,C,L+s)", ["ReplicationPad1d((0,s))"]),
            op("patch_unfold", "Unfold temporal patches", "tensor", r("PatchTST_backbone.forward"),
               "(B,C,P,p)", ["P=floor((L-p)/s)+2", "p=16, s=8, P=12"]),
            op("patch_permute_patch", "Permute for backbone", "tensor", r("PatchTST_backbone.forward"), "(B,C,p,P)"),
        ], [r("PatchTST_backbone.__init__"), r("PatchTST_backbone.forward")], "(B,C,p,P)", expand=2),
        chain("patch_embedding", "Patch embedding + position", [
            op("patch_projection", "Patch Linear p -> D", "embedding", [r("TSTiEncoder.__init__"), r("TSTiEncoder.forward")],
               "(B,C,P,D)", ["Permute back to (B,C,P,p)", "One W_P shared across C and P"], param_identity="backbone.W_P"),
            op("patch_fold_channels", "Fold B and C", "tensor", r("TSTiEncoder.forward"), "(BC,P,D)",
               ["Variables become independent batch items"]),
            op("patch_position", "Add learnable position", "embedding", [r("TSTiEncoder.forward"), ref(LAYERS, "positional_encoding")],
               "(BC,P,D)", ["W_pos:(P,D), pe='zeros'", "Uniform initialization, not zero values"], param_identity="backbone.W_pos"),
            op("patch_embedding_dropout", "Embedding dropout", "control", r("TSTiEncoder.forward"), "(BC,P,D)", ["p=0.05"]),
        ], [r("TSTiEncoder.__init__"), r("TSTiEncoder.forward")], "(BC,P,D)", expand=2),
        encoder,
        op("patch_restore_channels", "Restore channels + permute", "tensor", r("TSTiEncoder.forward"),
           "(B,C,D,P)", ["Reshape (BC,P,D) -> (B,C,P,D)", "Then permute to (B,C,D,P)"]),
        chain("patch_head", "Shared flatten forecast head", [
            op("patch_flatten", "Flatten D and P", "tensor", r("Flatten_Head.forward"), "(B,C,D*P)"),
            op("patch_head_linear", "Linear D*P -> H", "linear", [r("Flatten_Head.__init__"), r("Flatten_Head.forward")],
               "(B,C,H)", ["individual=False: one shared head", "D*P=6144; H=96"], param_identity="head.linear"),
            op("patch_head_dropout", "Head dropout", "control", r("Flatten_Head.forward"), "(B,C,H)", ["p=0.0 in selected profile"]),
        ], [r("Flatten_Head.__init__"), r("Flatten_Head.forward")], "(B,C,H)", expand=2),
        op("patch_revin_denorm", "RevIN denormalize", "norm", [r("PatchTST_backbone.forward"), ref(REVIN, "RevIN._denormalize")],
           "(B,C,H)", ["Reuse input mean / stdev", "Internal permute to (B,H,C), then back"]),
        op("patch_to_time", "Permute to forecast", "tensor", ref(MODEL, "Model.forward"), "(B,H,C)"),
        op("patch_output", "Forecast", "output", ref(MODEL, "Model.forward"), "(B,H,C)"),
    ], ref(MODEL, "Model.forward"), "(B,L,C) -> (B,H,C)", expand=0)
    extra_edges.append(dict(src="patch_revin_norm", dst="patch_revin_denorm", role="normalization",
                            label="Input mean / stdev", src_port="stats", dst_port="side"))
    return dict(
        key="patchtst", name="PatchTST", archive="PatchTST.zip", entry=ref(MODEL, "Model"),
        profile=dict(path="supervised forecast; no decomposition", profile_source=BASE + "run_longExp.py:31-70",
                     seq_len=96, pred_len=96, enc_in=7, patch_len=16, stride=8, padding_patch="end", patch_count=12,
                     d_model=512, d_ff=2048, n_heads=8, e_layers=2, dropout=0.05,
                     head_dropout=0.0, fc_dropout=0.05, revin=True, affine=False, subtract_last=False,
                     decomposition=False, individual=False, norm="BatchNorm", act="gelu", pre_norm=False,
                     res_attention=True, pe="zeros", learn_pe=True, pretrain_head=False, head_type="flatten",
                     attn_dropout=0.0, attn_mask=None, key_padding_mask=None,
                     symbolic_shapes=True, model_executed=False),
        tree=tree, extra_edges=extra_edges,
        facts=[
            "The selected entry is PatchTST_supervised.models.PatchTST.Model, not the self-supervised implementation.",
            "Default run_longExp forecast profile: L=96,H=96,C=7,p=16,s=8,P=12,D=512,F=2048,h=8,N=2.",
            "Channel independence folds C into batch; W_P, W_pos, encoder and the individual=False head are shared across variables.",
            "Encoder layers are distinct ModuleList instances; repeated appearance does not mean shared layer weights.",
            "Default post normalization is BatchNorm1d(D), whose statistics aggregate the folded BC batch and P patches.",
            "res_attention=True passes pre-softmax attention scores to the next layer; it is separate from feature residual additions.",
            "RevIN normalizes each sample/variable and restores the saved input statistics after the forecast head.",
            "The adapter is explicit static source interpretation and does not import or execute the model.",
        ],
        corrections=[
            "Reference image shows (B,C,L) input and (B,C,H) output; Model.forward actually exposes (B,L,C) and (B,H,C).",
            "Flatten head projects D*P to H, not D to H; channel restoration yields (B,C,D,P), not (B,C,D).",
            "Default Add & Norm uses BatchNorm, not LayerNorm, and the default path is post-norm.",
            "End replication padding, RevIN normalization/denormalization and residual attention scores were missing from the reference image.",
            "P is determined by patch_len, stride and padding; stride=8 differs from patch_len=16 in the selected profile.",
            "The name pe='zeros' denotes a learnable (P,D) matrix initialized uniformly, not an all-zero fixed encoding.",
        ],
        symbols={
            MODEL: ["Model", "Model.__init__", "Model.forward"],
            BACK: ["PatchTST_backbone", "PatchTST_backbone.__init__", "PatchTST_backbone.forward", "Flatten_Head.__init__", "Flatten_Head.forward",
                   "TSTiEncoder.__init__", "TSTiEncoder.forward", "TSTEncoder.__init__", "TSTEncoder.forward", "TSTEncoderLayer.__init__", "TSTEncoderLayer.forward",
                   "_MultiheadAttention.__init__", "_MultiheadAttention.forward", "_ScaledDotProductAttention.__init__", "_ScaledDotProductAttention.forward"],
            LAYERS: ["get_activation_fn", "positional_encoding", "series_decomp.forward"],
            REVIN: ["RevIN", "RevIN.forward", "RevIN._get_statistics", "RevIN._normalize", "RevIN._denormalize"],
        },
        legend=["B batch", "L input steps", "H forecast steps", "C variables", "p patch length", "s stride",
                "P patch count", "D model width", "F FFN width", "h attention heads", "d=D/h", "BC=B*C", "N=2 encoder layers"],
    )
