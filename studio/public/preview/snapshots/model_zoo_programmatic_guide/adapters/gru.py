"""Reviewed packed GRU IMDb adapter; PyTorch recurrence stays a library boundary."""
from spec import chain, op, ref

SOURCE = "deeplearning-models-batch3/pytorch_ipynb/rnn/rnn_gru_packed_imdb.py"


def build():
    init, forward = ref(SOURCE, "RNN.__init__"), ref(SOURCE, "RNN.forward")
    accuracy, predict = ref(SOURCE, "compute_binary_accuracy"), ref(SOURCE, "predict_sentiment")
    embedding = chain("gru.embedding", "Token embedding", [
        op("gru.lookup", "Embedding V -> 128", "embedding", [init, forward], "[T,B,128]",
           ["V=len(TEXT.vocab); no pretrained initialization or padding_idx is passed"],
           parameter="embedding.weight", padding_idx=None, runtime_dependency="torch.nn.Embedding"),
    ], [init, forward], "[T,B,128]", expand=2)
    packing = chain("gru.packing", "Pack valid time steps", [
        op("gru.pack", "pack_padded_sequence", "tensor", forward, "PackedSequence",
           ["embedded values + external valid lengths; sorted within batch",
            "batch_first and enforce_sorted are omitted, so API defaults apply"],
           runtime_dependency="torch.nn.utils.rnn.pack_padded_sequence",
           batch_first=False, enforce_sorted="default True"),
    ], forward, "PackedSequence", expand=2)
    recurrent = chain("gru.recurrent", "Single-layer GRU", [
        op("gru.core", "nn.GRU 128 -> 256", "recurrent", [init, forward], "(packed_output,h_n)",
           ["one layer / one direction; no initial state supplied",
            "gate kernels are not defined in this notebook"],
           parameter_scope="rnn", parameters=["rnn.weight_ih_l0", "rnn.weight_hh_l0",
                                                "rnn.bias_ih_l0", "rnn.bias_hh_l0"],
           runtime_dependency="torch.nn.GRU", opaque_runtime_boundary=True,
           num_layers=1, bidirectional=False, bias=True, dropout=0,
           initial_state="PyTorch default zeros", output_tuple=["packed_output", "hidden"],
           temporal_parameter_sharing=True),
        op("gru.select_hidden", "Select hidden h_n", "tensor", forward, "[1,B,256]",
           ["packed_output is unused; GRU returns no cell state"], input_selector="hidden"),
        op("gru.squeeze", "Squeeze layer axis 0", "tensor", forward, "[B,256]",
           ["hidden.squeeze(0); no mean pooling or unpacking"], expression="hidden.squeeze(0)"),
    ], [init, forward], "[B,256]", expand=2, parameter_scope="rnn")
    classifier = chain("gru.classifier", "Binary logit head", [
        op("gru.fc", "Linear 256 -> 1", "linear", [init, forward], "[B,1]", parameter="fc"),
        op("gru.flatten", "view(-1)", "tensor", forward, "logits: [B]",
           ["complete RNN.forward return; no internal Sigmoid"], expression="view(-1)"),
    ], [init, forward], "logits: [B]", expand=2)
    model_forward = chain("gru.forward", "RNN.forward: packed GRU classifier", [
        embedding, packing, recurrent, classifier,
    ], forward, "logits: [B]", expand=1)
    caller = chain("gru.caller", "Caller: per-batch binary decisions", [
        op("gru.sigmoid", "Sigmoid", "activation", accuracy, "p(positive): [B]",
           boundary="caller", expression="torch.sigmoid(logits)"),
        op("gru.threshold", "Threshold p > 0.5", "control", accuracy, "labels: [B]",
           ["accuracy accumulation and final percentage are outside the diagram"],
           boundary="caller", expression="(torch.sigmoid(logits) > 0.5).long()"),
    ], accuracy, "binary labels: [B]", expand=1)
    tree = chain("gru.root", "Packed GRU: IMDb sentiment", [
        op("gru.input", "Padded token IDs", "input", [forward, accuracy], "text: [T,B]"),
        model_forward, caller,
    ], [forward, accuracy], "per-batch labels: [B]", expand=0)
    lengths = op("gru.lengths", "External sequence lengths", "input", [forward, accuracy],
                 "text_length: [B]", ["Field(include_lengths=True); used by packing, not a learned feature"],
                 origin="caller_batch_data.text[1]", learnable=False)
    return dict(
        key="gru", name="GRU (packed IMDb classifier)", source_project="deeplearning-models-batch3",
        entry=forward,
        profile=dict(task="IMDb binary sentiment classification", mode="eval",
                     selected_caller="compute_binary_accuracy: per-batch prediction segment",
                     embedding_dim=128, hidden_dim=256, output_dim=1,
                     vocabulary_size="V=len(TEXT.vocab)", vocabulary_max_size_setting=20000,
                     num_layers=1, bidirectional=False, batch_first=False,
                     bias=True, recurrent_dropout=0, external_dropout_calls=0,
                     batch_size_setting=128, enforce_sorted="default True",
                     return_value="[B] logits", caller_output="[B] labels after sigmoid > 0.5",
                     training_loss="binary_cross_entropy_with_logits outside forward",
                     recurrent_internals="opaque PyTorch nn.GRU library boundary"),
        profile_label="IMDb / embedding128 / hidden256 / one direction / packed / eval",
        tree=tree, aux_inputs=[lengths],
        extra_edges=[dict(src="gru.lengths", dst="gru.pack", role="sequence_length",
                          label="valid lengths", src_port="out", dst_port="lengths")],
        visual_roles={"gru.root":"root", "gru.forward":"encoder", "gru.embedding":"embedding",
                      "gru.packing":"inner", "gru.recurrent":"recurrent", "gru.core":"recurrent",
                      "gru.classifier":"ffn", "gru.caller":"control", "gru.sigmoid":"softmax",
                      "gru.flatten":"output", "gru.input":"input", "gru.lengths":"input"},
        fill_width=["gru.forward", "gru.embedding", "gru.packing", "gru.recurrent", "gru.classifier", "gru.caller"],
        facts=[
            "The selected constructor is Embedding(V,128), GRU(128,256), Linear(256,1); V is len(TEXT.vocab).",
            "The API defaults used by the source are one layer, unidirectional, sequence-first, bias=True and dropout=0.",
            "Field(include_lengths=True) and BucketIterator(sort_within_batch=True) supply valid lengths and sorted batches.",
            "pack_padded_sequence omits batch_first and enforce_sorted arguments; do not silently change their defaults.",
            "GRU returns (packed_output,hidden), without an LSTM cell; only hidden.squeeze(0) enters the classifier.",
            "RNN.forward returns fc(...).view(-1), a [B] logit vector; the caller applies sigmoid and threshold.",
            "The diagram ends at per-batch predictions inside compute_binary_accuracy, not the function's accumulated accuracy percentage.",
            "Training uses binary_cross_entropy_with_logits outside forward; predict_sentiment is a separate single-sentence caller.",
            "The same recurrent instance reuses weights across time; gate implementation is external PyTorch code, not notebook AST.",
            "Old torchtext/spaCy and length-device compatibility are not tested: source and model are never executed.",
        ],
        corrections=[
            "Do not substitute an LSTM tuple or add a cell state, bidirectional branch, stacked layer, or dropout.",
            "Do not replace packing/final hidden with dense padding, last padded output, mean pooling, or pad_packed_sequence.",
            "Do not put Sigmoid inside RNN.forward or claim vocabulary_max_size is the realized embedding row count.",
            "Reset/update gates are not source-extracted operators; the real nn.GRU runtime boundary remains explicit.",
        ],
        symbols={SOURCE:["RNN", "RNN.__init__", "RNN.forward", "compute_binary_accuracy", "predict_sentiment"]},
        config_files=[SOURCE],
        legend=["T: padded time axis; B: batch; V: realized vocabulary; E=128; H=256",
                "lengths enter packing through a side port; recurrent weights are reused across time",
                "nn.GRU is a library boundary; model returns logits; caller Sigmoid / threshold are outside",
                "eval batch profile; displayed labels are intermediate decisions, not final aggregate accuracy"],
    )


def validate_ir(ir):
    """Reject model-specific errors beyond source hash/AST and geometric checks."""
    nodes = {n["id"]: n for n in ir["nodes"]}
    edges, p, checks = ir["edges"], ir["profile"], []
    def check(condition, label):
        if not condition: raise ValueError("gru: " + label)
        checks.append(label)
    def has(a, b, role):
        return any(e["src"]==a and e["dst"]==b and e["role"]==role for e in edges)
    check({"gru.core","gru.select_hidden","gru.pack","gru.squeeze","gru.fc","gru.flatten",
           "gru.sigmoid","gru.threshold","gru.lengths"} <= nodes.keys(), "required source-grounded operators")
    check(p["mode"]=="eval" and p["embedding_dim"]==128 and p["hidden_dim"]==256 and p["output_dim"]==1
          and p["num_layers"]==1 and p["bidirectional"] is False,
          "selected eval 128/256/1 configuration")
    core=nodes["gru.core"]
    check(core["runtime_dependency"]=="torch.nn.GRU" and core["opaque_runtime_boundary"] is True,
          "actual GRU library boundary")
    check(core["num_layers"]==1 and core["bidirectional"] is False and core["dropout"]==0,
          "single layer / direction without recurrent dropout")
    check(core["parameters"]==["rnn.weight_ih_l0","rnn.weight_hh_l0","rnn.bias_ih_l0","rnn.bias_hh_l0"]
          and core["temporal_parameter_sharing"] is True, "one recurrent parameter family reused across time")
    check(core["output_tuple"]==["packed_output","hidden"] and nodes["gru.select_hidden"]["input_selector"]=="hidden",
          "GRU hidden selected without cell state")
    check(nodes["gru.pack"]["batch_first"] is False and nodes["gru.pack"]["enforce_sorted"]=="default True"
          and has("gru.lengths","gru.pack","sequence_length"), "external lengths and default sorted sequence-first packing")
    check(nodes["gru.squeeze"]["expression"]=="hidden.squeeze(0)" and nodes["gru.fc"]["parameter"]=="fc"
          and nodes["gru.flatten"]["expression"]=="view(-1)", "final hidden to flattened binary logits")
    check(nodes["gru.sigmoid"]["boundary"]=="caller" and nodes["gru.threshold"]["boundary"]=="caller"
          and nodes["gru.sigmoid"]["parent"]=="gru.caller" and nodes["gru.threshold"]["parent"]=="gru.caller"
          and nodes["gru.threshold"]["expression"]=="(torch.sigmoid(logits) > 0.5).long()",
          "Sigmoid and strict 0.5 threshold remain outside forward")
    check(not any(n.get("kind")=="dropout" or "cell" in n["id"] for n in nodes.values()),
          "no invented dropout or cell nodes")
    return checks
