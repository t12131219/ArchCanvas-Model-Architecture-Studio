"""Reviewed static adapter for the supplied Autoformer archive, not model execution."""
from spec import op, chain, parallel, ref


MODEL = "Autoformer-main/models/Autoformer.py"
LAYERS = "Autoformer-main/layers/Autoformer_EncDec.py"
AC = "Autoformer-main/layers/AutoCorrelation.py"
EMBED = "Autoformer-main/layers/Embed.py"


def build():
    model = ref(MODEL, "Model.forward")
    ctor = ref(MODEL, "Model.__init__")

    def embedding(prefix, length):
        parameter_path = "enc_embedding" if prefix == "af_enc_embedding" else "dec_embedding"
        marks = "x_mark_enc" if prefix == "af_enc_embedding" else "x_mark_dec"
        return chain(prefix, "Embedding (no PE)", [
            parallel(prefix + "_terms", "Value + time features", [
                op(prefix + "_value", "Circular Conv1d", "embedding", ref(EMBED, "TokenEmbedding.forward"),
                   f"B,{length},D", ["kernel=3; C -> D"], input_selector="value",
                   param_identity=parameter_path + ".value_embedding.tokenConv"),
                op(prefix + "_time", "Time feature Linear", "embedding", ref(EMBED, "TimeFeatureEmbedding.forward"),
                   f"B,{length},D", ["hourly: 4 -> D"], input_selector=marks,
                   param_identity=parameter_path + ".temporal_embedding.embed"),
            ], ref(EMBED, "DataEmbedding_wo_pos.forward"), expand=2, dispatch=True),
            op(prefix + "_sum", "Add + dropout", "mixing", ref(EMBED, "DataEmbedding_wo_pos.forward"),
               f"B,{length},D", ["No positional term"]),
        ], [ctor, ref(EMBED, "DataEmbedding_wo_pos.forward")], f"B,{length},D", expand=2)

    def autocorrelation(prefix, length, cross=False):
        # Projected V takes a separate branch around the FFT on Q/K.
        parameter_path = {"af_enc_ac": "encoder.attn_layers[i].attention",
                          "af_dec_self": "decoder.layers[0].self_attention",
                          "af_dec_cross": "decoder.layers[0].cross_attention"}[prefix]
        return chain(prefix, "Cross AutoCorrelation" if cross else "AutoCorrelation", [
            op(prefix + "_qkv", "Q / K / V projections", "linear", ref(AC, "AutoCorrelationLayer.forward"),
               "Q: decoder; K,V: memory" if cross else "(Q,K,V)", ["Q=seasonal; K,V=memory" if cross else "Q,K,V from same state",
                            "3 distinct Linear weights; split heads"],
               main_input_operand="Q" if cross else "Q,K,V",
               auxiliary_input_operands={"memory_KV": ["K", "V"]} if cross else {},
               param_identity=parameter_path + ".{query_projection,key_projection,value_projection}"),
            parallel(prefix + "_operands", "Correlation and values", [
                chain(prefix + "_corr", "Q/K period discovery", [
                    op(prefix + "_align", "Align K to Q length", "tensor", ref(AC, "AutoCorrelation.forward"),
                       f"Lq={length}", ["Truncate or zero-pad K"]),
                    op(prefix + "_fft", "rFFT(Q) * conj(rFFT(K))", "attention", ref(AC, "AutoCorrelation.forward"),
                       "B,H,E,freq", ["FFT along time only"]),
                    op(prefix + "_irfft", "irFFT: lag correlation", "attention", ref(AC, "AutoCorrelation.forward"),
                       f"B,H,E,{length}"),
                ], ref(AC, "AutoCorrelation.forward"), expand=2,
                      detail=["Select Q,K from tuple"], input_selector="Q,K"),
                op(prefix + "_values", "V: align + bypass FFT", "tensor", ref(AC, "AutoCorrelation.forward"),
                   f"B,H,E,{length}", ["Independent aggregation operand"], input_selector="V"),
            ], ref(AC, "AutoCorrelation.forward"), expand=2, dispatch=True),
            op(prefix + "_delay", "Top-k delay aggregation", "attention", ref(AC, "AutoCorrelation.time_delay_agg_inference"),
               f"B,H,E,{length}", ["k=floor(factor * log(Lq))", "Per-sample delays; Softmax weights", "Gather shifted V; weighted sum"]),
            op(prefix + "_out", "Merge heads + Linear", "linear", ref(AC, "AutoCorrelationLayer.forward"),
               f"B,{length},D", param_identity=parameter_path + ".out_projection"),
        ], [ref(AC, "AutoCorrelationLayer.forward"), ref(AC, "AutoCorrelation.forward")],
            f"B,{length},D", ["Inference branch; no mask applied"], expand=2)

    def residual_ac(prefix, length, layer_symbol, cross=False):
        evidence = ref(LAYERS, layer_symbol)
        return chain(prefix + "_residual", "Cross + residual" if cross else "AutoCorr + residual", [
            autocorrelation(prefix, length, cross),
            op(prefix + "_dropout", "Dropout", "control", evidence, f"B,{length},D", ["Identity in eval mode"]),
            op(prefix + "_add", "Residual add", "mixing", evidence, f"B,{length},D",
               glyph_expression="x + self.dropout(new_x)" if layer_symbol=='EncoderLayer.forward' else
                   "x + self.dropout(self.cross_attention(x, cross, cross, attn_mask=cross_mask)[0])" if cross else
                   "x + self.dropout(self.self_attention(x, x, x, attn_mask=x_mask)[0])"),
        ], evidence, f"B,{length},D", expand=2, residual=True)

    def residual_ffn(prefix, length, layer_symbol):
        evidence = ref(LAYERS, layer_symbol)
        parameter_path = "encoder.attn_layers[i]" if prefix == "af_enc_ffn" else "decoder.layers[0]"
        return chain(prefix, "Pointwise FFN + residual", [
            op(prefix + "_conv1", "Conv1d: D -> F", "linear", evidence, f"B,F,{length}",
               ["kernel=1; bias=False"], param_identity=parameter_path + ".conv1"),
            op(prefix + "_act", "GELU + dropout", "activation", evidence, f"B,F,{length}"),
            op(prefix + "_conv2", "Conv1d: F -> D", "linear", evidence, f"B,{length},D",
               ["Transpose back; dropout"], param_identity=parameter_path + ".conv2"),
            op(prefix + "_add", "Residual add", "mixing", evidence, f"B,{length},D", glyph_expression="x + y"),
        ], evidence, f"B,{length},D", expand=2, residual=True)

    def decomp(prefix, label, length, caller):
        return chain(prefix, label, [
            op(prefix + "_mean", "Moving average", "decomposition", ref(LAYERS, "moving_avg.forward"),
               f"B,{length},D", ["Replicate endpoints; window=25"]),
            op(prefix + "_split", "Seasonal = x - mean", "decomposition", ref(LAYERS, "series_decomp.forward"),
               f"seasonal: B,{length},D", ["Original x retained in block", "Trend=mean; separate side output"]),
        ], [ref(LAYERS, caller), ref(LAYERS, "series_decomp.forward")],
            f"seasonal: B,{length},D", ["Trend is a separate output"], expand=2, retained_input=True,
            output_bindings={"trend": prefix + "_mean"})

    def seasonal_norm(prefix, length):
        parameter_path = "encoder.norm" if prefix == "af_memory" else "decoder.norm"
        return chain(prefix, "Seasonal LayerNorm", [
            op(prefix + "_ln", "LayerNorm over D", "norm", ref(LAYERS, "my_Layernorm.forward"), f"B,{length},D",
               param_identity=parameter_path + ".layernorm"),
            op(prefix + "_center", "Subtract time mean", "norm", ref(LAYERS, "my_Layernorm.forward"), f"B,{length},D"),
        ], ref(LAYERS, "my_Layernorm.forward"), f"B,{length},D", expand=2)

    encoder_layer = chain("af_enc_layer", "Encoder layer x N_e=2", [
        residual_ac("af_enc_ac", "L", "EncoderLayer.forward"),
        decomp("af_enc_decomp1", "Decomposition 1", "L", "EncoderLayer.forward"),
        residual_ffn("af_enc_ffn", "L", "EncoderLayer.forward"),
        decomp("af_enc_decomp2", "Decomposition 2", "L", "EncoderLayer.forward"),
    ], [ctor, ref(LAYERS, "EncoderLayer.forward")], "B,L,D",
       ["Two independently parameterized layers", "Encoder trends are discarded"], expand=1,
       flow_role="seasonal", repeat=dict(count=2, index="i", independent_parameters=True),
       param_identity="encoder.attn_layers[i]; i=0,1; no tied weights")

    decoder_layer = chain("af_dec_layer", "Decoder layer x N_d=1", [
        residual_ac("af_dec_self", "T", "DecoderLayer.forward"),
        decomp("af_dec_decomp1", "Decomposition 1", "T", "DecoderLayer.forward"),
        residual_ac("af_dec_cross", "T", "DecoderLayer.forward", cross=True),
        decomp("af_dec_decomp2", "Decomposition 2", "T", "DecoderLayer.forward"),
        residual_ffn("af_dec_ffn", "T", "DecoderLayer.forward"),
        decomp("af_dec_decomp3", "Decomposition 3", "T", "DecoderLayer.forward"),
        op("af_trend_update", "Trend update; carry seasonal", "mixing",
           [ref(LAYERS, "DecoderLayer.forward"), ref(LAYERS, "Decoder.forward")],
           "(seasonal[B,T,D], trend[B,T,C])",
           ["Sum trend1 + trend2 + trend3", "Circular Conv1d: D -> C, k=3", "trend += projected sum; seasonal bypass"],
           param_identity="decoder.layers[0].projection"),
    ], [ctor, ref(LAYERS, "DecoderLayer.forward"), ref(LAYERS, "Decoder.forward")],
       "(seasonal[B,T,D], trend[B,T,C])", ["Seasonal main lane; explicit trend side state"],
       expand=1, flow_role="seasonal", param_identity="decoder.layers[0]; self/cross use distinct weights")

    prepare = parallel("af_prepare", "Encoder + decoder preparation", [
        chain("af_encoder", "Encoder memory path", [
            embedding("af_enc_embedding", "L"), encoder_layer,
            seasonal_norm("af_memory", "L"),
        ], [model, ref(LAYERS, "Encoder.forward")], "memory: B,L,D", expand=1),
        chain("af_decoder_init", "Decoder initialization from x_enc", [
            op("af_init_decomp", "Decompose raw input", "decomposition",
               [model, ref(LAYERS, "series_decomp.forward")], "(seasonal[B,L,C], trend[B,L,C])",
               ["Moving average on raw channels"]),
            parallel("af_init_states", "Seasonal and trend seeds", [
                chain("af_seasonal_seed", "Seasonal seed + embedding", [
                    op("af_seasonal_init", "Last label + future zeros", "tensor", model, "B,T,C",
                       ["T=label_len+pred_len"]),
                    embedding("af_dec_embedding", "T"),
                ], model, "B,T,D", expand=1, input_selector="seasonal"),
                op("af_trend_init", "Last trend + input mean", "decomposition", model, "B,T,C",
                   ["Repeat raw x_enc mean for future"], input_selector="trend, mean(x_enc)"),
            ], model, "(seasonal[B,T,D], trend[B,T,C])", expand=1, dispatch=True),
        ], model, "(seasonal[B,T,D], trend[B,T,C])", expand=1),
    ], model, "(memory, seasonal, trend)",
       ["Both paths select the same raw x_enc", "x_mark_enc/dec enter their own embedding"], expand=1)

    tree = chain("af_model", "Autoformer forecasting", [
        op("af_input", "Input time series", "input", model, "x_enc: B,L,C",
           ["Time marks: B,L,4 and B,T,4", "x_dec values unused; only shape consulted"]),
        prepare,
        decoder_layer,
        parallel("af_final_parts", "Seasonal and trend outputs", [
            chain("af_seasonal_output", "Seasonal forecast", [
                seasonal_norm("af_dec_norm", "T"),
                op("af_seasonal_projection", "Linear: D -> C", "linear",
                   [ctor, ref(LAYERS, "Decoder.forward")], "B,T,C",
                   param_identity="decoder.projection"),
            ], ref(LAYERS, "Decoder.forward"), "B,T,C", expand=1, input_selector="seasonal"),
            op("af_trend_output", "Accumulated trend", "tensor", ref(LAYERS, "Decoder.forward"), "B,T,C",
               ["Select trend from state tuple"], input_selector="trend"),
        ], ref(LAYERS, "Decoder.forward"), "(seasonal[B,T,C], trend[B,T,C])", expand=1, dispatch=True),
        op("af_sum", "Seasonal + trend", "mixing", model, "B,T,C"),
        op("af_slice", "Keep last pred_len", "tensor", model, "B,P,C"),
        op("af_output", "Forecast", "output", model, "B,P,C"),
    ], model, "B,P,C", expand=0)

    return dict(
        key="autoformer", name="Autoformer", archive="Autoformer-main.zip",
        entry=MODEL + "::Model",
        profile={"task": "long-term forecasting", "mode": "eval / inference", "seq_len": 96,
                 "label_len": 48, "pred_len": 96, "enc_in": 7, "dec_in": 7, "c_out": 7,
                 "d_model": 512, "d_ff": 2048, "n_heads": 8, "e_layers": 2, "d_layers": 1,
                 "moving_avg": 25, "factor": 1, "activation": "gelu", "embed": "timeF",
                 "freq": "h", "dropout": 0.05, "output_attention": False,
                 "masks": "None; AutoCorrelation.forward ignores mask arguments"},
        tree=tree,
        aux_inputs=[
            op("af_x_mark_enc", "Encoder time marks", "input", model, "B,L,4",
               ["External x_mark_enc; hourly timeF"]),
            op("af_x_mark_dec", "Decoder time marks", "input", model, "B,T,4",
               ["External x_mark_dec; hourly timeF"]),
        ],
        extra_edges=[
            dict(src="af_x_mark_enc", dst="af_enc_embedding_time", role="covariate", label="x_mark_enc",
                 src_port="out", dst_port="side"),
            dict(src="af_x_mark_dec", dst="af_dec_embedding_time", role="covariate", label="x_mark_dec",
                 src_port="out", dst_port="side"),
            dict(src="af_memory", dst="af_dec_cross_qkv", role="memory", label="K,V = encoder memory",
                 src_port="out", dst_port="memory_KV"),
            dict(src="af_trend_init", dst="af_trend_update", role="trend", label="initial trend",
                 src_port="out", dst_port="initial_trend"),
            *[dict(src=f"af_dec_decomp{i}", dst="af_trend_update", role="trend", label=f"trend{i}",
                   src_port="trend", dst_port=f"trend{i}") for i in (1, 2, 3)],
        ],
        facts=[
            "Reviewed handwritten adapter; AST evidence does not automatically recover semantics.",
            "DataEmbedding_wo_pos sums a circular Conv1d value embedding and time feature embedding; no positional encoding.",
            "Encoder has two residual-plus-decomposition stages per layer; discarded trends never feed the decoder.",
            "Decoder uses self AutoCorrelation, cross AutoCorrelation, and FFN with three decomposition stages.",
            "Cross Q is decoder seasonal state; cross K/V are final normalized encoder memory.",
            "Decoder trend1/2/3 are summed, Conv1d-projected to C, and added to the carried raw-channel trend.",
            "Autocorrelation uses FFT lag correlation and delay-weighted V aggregation, not dot-product attention.",
            "Inference picks delays per sample; training uses batch-shared delay indices and a different aggregation method.",
            "mask_flag and attn_mask are accepted but not applied in the supplied AutoCorrelation.forward.",
            "Forecast is the final pred_len slice of seasonal projection plus accumulated trend.",
            "Repeated encoder layers are distinct modules with independent parameters; same color does not mean weight sharing.",
        ],
        corrections=[
            "Replace the reference image's ordinary Add & Norm blocks by residual + progressive series decomposition.",
            "Remove positional encoding: it is constructed in DataEmbedding_wo_pos but unused by forward.",
            "Replace Linear token embedding with kernel-3 circular Conv1d; preserve the distinct time-feature Linear.",
            "Remove causal-mask claims for decoder AutoCorrelation; the supplied implementation does not apply masks.",
            "Move raw-series decomposition to decoder initialization; encoder consumes raw x_enc through embedding.",
            "Draw encoder self correlation before its FFN, and decoder self -> cross -> FFN in actual source order.",
            "Show three decoder trend contributions and accumulation separately from the seasonal forecast projection.",
            "Replace a right-shifted x_dec value path by x_enc-derived seasonal/trend initialization.",
        ],
        symbols={MODEL: ["Model.__init__", "Model.forward"],
                 LAYERS: ["series_decomp.forward", "moving_avg.forward", "EncoderLayer.forward", "Encoder.forward",
                          "DecoderLayer.forward", "Decoder.forward", "my_Layernorm.forward"],
                 AC: ["AutoCorrelationLayer.__init__", "AutoCorrelationLayer.forward", "AutoCorrelation.forward",
                      "AutoCorrelation.time_delay_agg_inference", "AutoCorrelation.time_delay_agg_training"],
                 EMBED: ["DataEmbedding_wo_pos.__init__", "DataEmbedding_wo_pos.forward", "TokenEmbedding.forward",
                         "TimeFeatureEmbedding.forward"]},
        legend=["B=batch; L=input length; P=prediction length; T=label_len+P",
                "C=raw variables/output channels; D=d_model; F=d_ff; H=heads; E=D/H",
                "Parallel collects named operands/states; only explicit Add nodes perform summation",
                "Trend edges carry decomposition side outputs; memory edge binds cross K/V"],
    )
