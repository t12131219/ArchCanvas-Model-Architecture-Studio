"""Reviewed packed LSTM IMDB adapter, with an explicit PyTorch library boundary."""
from spec import chain, op, ref


SOURCE = "deeplearning-models/pytorch_ipynb/rnn/rnn_lstm_packed_imdb.py"


def build():
    init = ref(SOURCE, "RNN.__init__")
    forward = ref(SOURCE, "RNN.forward")
    accuracy = ref(SOURCE, "compute_binary_accuracy")
    predict = ref(SOURCE, "predict_sentiment")

    embedding = chain("lstm.embedding", "Token embedding", [
        op("lstm.lookup", "Embedding V -> 128", "embedding", [init, forward],
           "[T,B,128]", ["integer token IDs select rows of one shared vocabulary matrix",
                         "V=len(TEXT.vocab), not exactly the max_size setting"],
           parameter="embedding.weight", runtime_dependency="torch.nn.Embedding"),
    ], [init, forward], "[T,B,128]", expand=2, parameter_scope="embedding")

    packing = chain("lstm.packing", "Pack valid time steps", [
        op("lstm.pack", "pack_padded_sequence", "tensor", forward,
           "PackedSequence; data [sum(lengths),128]",
           ["sequence-first embedded input and external text_length",
            "source does not pass batch_first or enforce_sorted arguments",
            "BucketIterator(sort_within_batch=True) supplies the expected ordering"],
           runtime_dependency="torch.nn.utils.rnn.pack_padded_sequence",
           batch_first=False, enforce_sorted="default True"),
    ], forward, "PackedSequence", expand=2)

    recurrent = chain("lstm.recurrent", "Single-layer LSTM", [
        op("lstm.core", "nn.LSTM 128 -> 256", "recurrent", [init, forward],
           "(packed_output, (h_n,c_n))",
           ["PyTorch library module; gate implementation is not present in this notebook",
            "one layer, unidirectional, no supplied initial state",
            "one parameter set is reused across valid time steps"],
           parameter_scope="rnn",
           parameters=["rnn.weight_ih_l0", "rnn.weight_hh_l0",
                       "rnn.bias_ih_l0", "rnn.bias_hh_l0"],
           runtime_dependency="torch.nn.LSTM", opaque_runtime_boundary=True,
           num_layers=1, bidirectional=False, initial_state="PyTorch default zeros",
           output_tuple=["packed_output", ["hidden", "cell"]],
           temporal_parameter_sharing=True),
        op("lstm.select_hidden", "Select hidden h_n", "tensor", forward,
           "[1,B,256]",
           ["assignment unpacks packed_output, (hidden, cell)",
            "only hidden is used by the classifier; packed_output and cell are unused"],
           input_selector="hidden"),
        op("lstm.squeeze", "Squeeze layer axis 0", "tensor", forward,
           "[B,256]", ["hidden.squeeze(0); no time averaging or sequence unpacking"]),
    ], [init, forward], "[B,256]", expand=2,
       parameter_scope="rnn", temporal_parameter_sharing=True)

    classifier = chain("lstm.classifier", "Binary logit head", [
        op("lstm.fc", "Linear 256 -> 1", "linear", [init, forward],
           "[B,1]", ["self.fc"], parameter="fc"),
        op("lstm.flatten", "view(-1)", "tensor", forward,
           "logits: [B]", ["this tensor is the complete RNN.forward result"]),
    ], [init, forward], "logits: [B]", expand=2, parameter_scope="fc")

    model_forward = chain("lstm.forward", "RNN.forward: packed LSTM classifier", [
        embedding, packing, recurrent, classifier,
    ], forward, "logits: [B]",
       ["Sigmoid is not called inside this model forward"], expand=1)

    caller = chain("lstm.caller", "Caller: binary accuracy decision", [
        op("lstm.sigmoid", "Sigmoid", "activation", accuracy,
           "p(positive): [B]", ["compute_binary_accuracy calls sigmoid on returned logits"],
           boundary="caller", expression="torch.sigmoid(logits)"),
        op("lstm.threshold", "Threshold p > 0.5", "control", accuracy,
           "predicted labels: [B]", ["comparison then .long(); caller-only evaluation"],
           boundary="caller", expression="(torch.sigmoid(logits) > 0.5).long()"),
    ], accuracy, "binary labels: [B]", expand=1)

    tree = chain("lstm.root", "Packed LSTM: IMDB sentiment", [
        op("lstm.input", "Padded token IDs", "input", [forward, accuracy],
           "text: [T,B]", ["batch_data.text is (text, text_lengths)",
                          "sequence-first; variable valid lengths per example"]),
        model_forward,
        caller,
    ], [forward, accuracy], "binary labels: [B]", expand=0)
    lengths = op("lstm.lengths", "External sequence lengths", "input", [forward, accuracy],
                 "text_length: [B]", ["provided alongside text by torchtext Field(include_lengths=True)",
                                      "used by pack_padded_sequence; not a learned feature"],
                 origin="caller_batch_data.text[1]", learnable=False)

    return dict(
        key="lstm", name="LSTM (packed IMDB classifier)", source_project="deeplearning-models",
        entry=forward,
        profile=dict(task="IMDB binary sentiment classification", mode="batch evaluation",
                     vocabulary_size="V=len(TEXT.vocab)", vocabulary_max_size_setting=20000,
                     embedding_dim=128, hidden_dim=256, output_dim=1,
                     num_layers=1, bidirectional=False, batch_first=False,
                     default_bias=True, default_dropout=0, batch_size_setting=128,
                     input_layout="[T,B]", lengths_layout="[B]",
                     output_layout="[B] logits from RNN.forward",
                     packing="sorted within batch, pack_padded_sequence",
                     caller_output="sigmoid probabilities, then threshold p>0.5 labels",
                     training_loss="binary_cross_entropy_with_logits outside forward",
                     lstm_internals="opaque PyTorch library implementation"),
        profile_label="IMDB / embedding 128 / hidden 256 / one direction / packed sequences",
        tree=tree, aux_inputs=[lengths],
        extra_edges=[dict(src="lstm.lengths", dst="lstm.pack", role="sequence_length",
                          label="valid lengths", src_port="out", dst_port="lengths")],
        visual_roles={"lstm.root": "root", "lstm.forward": "encoder",
                      "lstm.embedding": "embedding", "lstm.packing": "inner",
                      "lstm.recurrent": "recurrent", "lstm.core": "recurrent",
                      "lstm.classifier": "ffn", "lstm.caller": "control",
                      "lstm.sigmoid": "softmax", "lstm.threshold": "control",
                      "lstm.input": "input", "lstm.lengths": "input", "lstm.flatten": "output"},
        fill_width=["lstm.forward", "lstm.embedding", "lstm.packing",
                    "lstm.recurrent", "lstm.classifier", "lstm.caller"],
        facts=[
            "The notebook constructor is nn.Embedding(input_dim,128), nn.LSTM(128,256), nn.Linear(256,1).",
            "The recurrent module is one-layer, unidirectional, sequence-first by the PyTorch API defaults used here.",
            "input_dim is len(TEXT.vocab); max_size=20000 is a vocabulary construction limit, not an exact embedding row count.",
            "pack_padded_sequence consumes embedded tokens and their external valid lengths.",
            "BucketIterator(sort_within_batch=True) provides sorted minibatches for default packing behavior.",
            "Only hidden.squeeze(0) feeds fc; packed_output and cell are not used by this classifier.",
            "RNN.forward returns flattened logits; sigmoid and threshold belong to compute_binary_accuracy.",
            "predict_sentiment also applies sigmoid externally, but its tokenization/single-sentence path is not the selected batch diagram.",
            "binary_cross_entropy_with_logits is in the training loop, outside model forward; it must not be preceded by a model sigmoid.",
            "Gate equations and the nn.LSTM implementation are external library behavior, not notebook-defined source nodes.",
            "Within one nn.LSTM instance recurrent weights are reused across time; it is not a fresh Linear per token.",
        ],
        corrections=[
            "A generic LSTM figure cannot replace the actual pack_padded_sequence call with a dense padded sequence or averaging head.",
            "The head consumes the final hidden state; this source does not unpack/concatenate all time outputs.",
            "No bidirectional, stacked LSTM, attention, or dropout module is added to this selected constructor.",
            "The common four-gate textbook drawing is not presented as extracted notebook code; the nn.LSTM boundary remains explicit.",
            "Sigmoid is shown above the model boundary as caller evaluation; model.forward returns logits.",
            "The vocabulary row count remains V rather than asserting max_size is exactly the realized len(TEXT.vocab).",
        ],
        symbols={SOURCE: ["RNN", "RNN.__init__", "RNN.forward",
                          "compute_binary_accuracy", "predict_sentiment"]},
        legend=["T: padded sequence length; B: batch; V: realized vocabulary; E=128; H=256",
                "external inputs pink / forward logits purple / caller threshold gray / Sigmoid green",
                "lengths enter packing through a side port; recurrent weights are shared across time",
                "nn.LSTM is an opaque runtime boundary; caller Sigmoid / threshold are outside forward"],
        config_files=[SOURCE],
    )
