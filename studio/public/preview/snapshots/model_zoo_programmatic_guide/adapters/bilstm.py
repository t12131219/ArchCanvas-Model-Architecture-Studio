"""Reviewed two-layer bidirectional AGNews LSTM with explicit last-layer slices."""
from spec import chain, op, parallel, ref

SOURCE = "deeplearning-models-batch3/pytorch_ipynb/rnn/rnn_bi_multilayer_lstm_own_csv_agnews.py"


def build():
    init, forward = ref(SOURCE,"RNN.__init__"), ref(SOURCE,"RNN.forward")
    accuracy, predict = ref(SOURCE,"compute_accuracy"), ref(SOURCE,"predict_class")
    parameters = ["rnn." + base + "_l" + str(layer) + suffix
                  for layer in range(2) for suffix in ("", "_reverse")
                  for base in ("weight_ih", "weight_hh", "bias_ih", "bias_hh")]
    def dropout(node_id, shape):
        return op(node_id,"Dropout .5 (eval off)", "control", [init,forward],shape,
                  ["same self.dropout instance, distinct call site; identity in this eval profile",
                   "training calls sample fresh masks; Dropout has no learned parameters"],
                  module_identity="dropout", instance_identity="self.dropout",
                  p=0.5, active=False, learnable=False, runtime_dependency="torch.nn.Dropout")
    embedding = chain("bilstm.embedding", "Token embedding / dropout", [
        op("bilstm.lookup", "Embedding V -> 128", "embedding", [init,forward], "[T,B,128]",
           ["padding_idx=PAD_IDX; default random Embedding, not a copied GloVe matrix"],
           parameter="embedding.weight", padding_idx="TEXT.vocab.stoi[TEXT.pad_token]",
           pretrained_vectors_copied=False),
        dropout("bilstm.embed_dropout", "[T,B,128]"),
    ], [init,forward], "[T,B,128]", expand=2)
    packing = chain("bilstm.packing", "Pack valid time steps", [
        op("bilstm.pack", "pack_padded_sequence", "tensor", forward, "PackedSequence",
           ["external text_length; sorted descending by content length within each batch",
            "source leaves batch_first and enforce_sorted at API defaults"],
           batch_first=False, enforce_sorted="default True",
           runtime_dependency="torch.nn.utils.rnn.pack_padded_sequence"),
    ], forward, "PackedSequence", expand=2)
    recurrent = chain("bilstm.recurrent", "Two-layer bidirectional LSTM", [
        op("bilstm.core", "nn.LSTM 128 -> 256 / 2 layers / 2 directions", "recurrent", [init,forward],
           "(packed_output,(h_n,c_n))",
           ["four layer/direction parameter families; shared across time within each family",
            "dropout=.5 between recurrent layers during train; inactive in eval"],
           parameter_scope="rnn", parameters=parameters, runtime_dependency="torch.nn.LSTM",
           opaque_runtime_boundary=True, num_layers=2, bidirectional=True, bias=True,
           batch_first=False, dropout=0.5, recurrent_dropout_active=False,
           initial_state="PyTorch default zeros", temporal_parameter_sharing=True,
           layer_direction_parameter_sharing=False,
           output_tuple=["packed_output",["hidden","cell"]], hidden_shape="[4,B,256]",
           parameter_shapes={"layer0_weight_ih":[1024,128], "layer1_weight_ih":[1024,512],
                             "weight_hh":[1024,256], "bias":[1024]}),
        op("bilstm.select_hidden", "Select hidden h_n", "tensor", forward, "[4,B,256]",
           ["packed_output and cell are unused; no pad_packed_sequence call"], input_selector="hidden"),
    ], [init,forward], "h_n: [4,B,256]", expand=2, parameter_scope="rnn")
    slices = parallel("bilstm.last_layer", "Last-layer directional states", [
        op("bilstm.forward_state", "Forward state: hidden[-2]", "tensor", forward, "[B,256]",
           ["last recurrent layer, forward direction; layer-direction index 2"],
           expression="hidden[-2,:,:]", layer_index=1, direction="forward", hidden_index=2),
        op("bilstm.reverse_state", "Reverse state: hidden[-1]", "tensor", forward, "[B,256]",
           ["last recurrent layer, reverse direction; layer-direction index 3"],
           expression="hidden[-1,:,:]", layer_index=1, direction="reverse", hidden_index=3),
    ], forward, "two operands [B,256]", expand=2,
        semantic_mode="operand_bundle", literal_tuple=True,
        child_inputs={"bilstm.forward_state":dict(role="value",producer="bilstm.select_hidden",src_port="out"),
                      "bilstm.reverse_state":dict(role="value",producer="bilstm.select_hidden",src_port="out")},
        operand_order=["bilstm.forward_state","bilstm.reverse_state"])
    aggregation = chain("bilstm.aggregation", "Last-layer Concat", [
        slices,
        op("bilstm.concat", "Concat forward / reverse", "concat", forward, "[B,512]",
           ["torch.cat((hidden[-2,:,:],hidden[-1,:,:]),dim=1); forward then reverse"],
           dim=1, operand_order=["bilstm.forward_state","bilstm.reverse_state"]),
        dropout("bilstm.hidden_dropout", "[B,512]"),
    ], forward, "[B,512]", expand=1)
    classifier = chain("bilstm.classifier", "Two linear layers / logits", [
        op("bilstm.fc1", "Linear 512 -> 64", "linear", [init,forward], "[B,64]",
           ["source expression hidden_dim*num_layers: 256*2=512 for this fixed profile",
            "the selected hidden concatenation width is hidden_dim*2 directions"],
           parameter="fc1", in_features=512, out_features=64,
           source_in_features_expression="hidden_dim * num_layers"),
        dropout("bilstm.head_dropout", "[B,64]"),
        op("bilstm.fc2", "Linear 64 -> 4", "linear", [init,forward], "logits: [B,4]",
           ["returned directly; no intervening activation after fc1"],
           parameter="fc2", in_features=64, out_features=4),
    ], [init,forward], "logits: [B,4]", expand=2)
    model_forward = chain("bilstm.forward", "RNN.forward: AGNews classifier", [
        embedding,packing,recurrent,aggregation,classifier,
    ], forward, "logits: [B,4]", expand=1)
    caller = chain("bilstm.caller", "Caller: per-batch class decisions", [
        op("bilstm.argmax", "max(logits, dim=1): indices", "control", accuracy, "labels: [B]",
           ["torch.max returns values and indices; only indices become predicted labels",
            "accuracy accumulation and final percentage are outside the diagram"],
           boundary="caller", expression="torch.max(logits, 1)[1]", dim=1),
    ], accuracy, "class labels: [B]", expand=1)
    tree = chain("bilstm.root", "BiLSTM: AGNews", [
        op("bilstm.input", "Padded content token IDs", "input", [forward,accuracy], "text: [T,B]"),
        model_forward,caller,
    ], [forward,accuracy], "per-batch labels: [B]", expand=0)
    lengths = op("bilstm.lengths", "External sequence lengths", "input", [forward,accuracy],
                 "text_length: [B]", ["batch_data.content[1]; participates only in packing"],
                 origin="caller_batch_data.content[1]", learnable=False)
    return dict(
        key="bilstm", name="BiLSTM (2-layer AGNews classifier)", source_project="deeplearning-models-batch3",
        entry=forward,
        profile=dict(task="AGNews 4-class text classification", mode="eval",
                     selected_caller="compute_accuracy: per-batch prediction segment",
                     vocabulary_size="V=len(TEXT.vocab)", vocabulary_max_size_setting=5000,
                     embedding_dim=128, hidden_dim=256, output_dim=4,
                     num_layers=2, bidirectional=True, batch_first=False, bias=True,
                     recurrent_dropout=0.5, external_dropout=0.5, external_dropout_calls=3,
                     recurrent_dropout_active=False, external_dropout_active=False,
                     batch_size_setting=128, enforce_sorted="default True",
                     last_layer_hidden_indices=[2,3], concatenation_width=512,
                     classifier_widths=[512,64,4], classifier_first_width_source="hidden_dim * num_layers",
                     return_value="[B,4] logits", caller_output="torch.max(logits,1) indices",
                     training_loss="cross_entropy outside forward",
                     vocabulary_vector_reference="glove.6B.100d, not copied into Embedding",
                     pretrained_embedding=False, recurrent_internals="opaque PyTorch nn.LSTM library boundary"),
        profile_label="AGNews / 2 layers / bidirectional H256 / concat512 / dropout.5 / eval",
        tree=tree, aux_inputs=[lengths],
        extra_edges=[dict(src="bilstm.lengths",dst="bilstm.pack",role="sequence_length",
                          label="valid lengths",src_port="out",dst_port="lengths")],
        visual_roles={"bilstm.root":"root","bilstm.forward":"encoder","bilstm.embedding":"embedding",
                      "bilstm.packing":"inner","bilstm.recurrent":"recurrent","bilstm.core":"recurrent",
                      "bilstm.aggregation":"ffn","bilstm.last_layer":"inner","bilstm.concat":"concat",
                      "bilstm.classifier":"ffn","bilstm.caller":"control","bilstm.fc2":"output",
                      "bilstm.input":"input","bilstm.lengths":"input"},
        fill_width=["bilstm.forward","bilstm.embedding","bilstm.packing","bilstm.recurrent",
                    "bilstm.aggregation","bilstm.classifier","bilstm.caller"],
        facts=[
            "The fixed constructor uses Embedding(V,128,padding_idx=PAD_IDX), LSTM(128,256,num_layers=2,bidirectional=True,dropout=.5).",
            "The selected caller sets eval; all three self.dropout calls and recurrent inter-layer dropout are inactive identities in this profile.",
            "Training recurrent dropout operates between two LSTM layers, not on h_n as a separate source-defined gate.",
            "The three external dropout call sites reuse one weightless module; training draws fresh masks rather than sharing one mask.",
            "Packing is sequence-first with default enforce_sorted=True; BucketIterator sorts within batch by content length.",
            "h_n and c_n have [4,B,256]; forward selects only last-layer forward hidden[-2] and reverse hidden[-1], in that order.",
            "The 512-wide concat does not combine all four hidden states, time outputs, or cell states.",
            "fc1 is constructed from hidden_dim*num_layers, which equals512 only for this selected2-layer profile; the concat width depends on2 directions.",
            "Linear512->64, self.dropout, Linear64->4 contain no ReLU/other activation between the Linear layers; forward returns raw logits.",
            "compute_accuracy selects max(logits,1) indices without Softmax; predict_class separately applies Softmax and is not the chosen caller.",
            "build_vocab references GloVe100-dimensional vectors, but the source never copies them to the128-dimensional Embedding.",
            "Layer and direction families have independent parameters; each family reuses its weights across valid time steps.",
            "The notebook has no gate implementation; nn.LSTM remains an opaque external library boundary. Models and old torchtext code are never executed.",
        ],
        corrections=[
            "Do not draw a generic single-layer LSTM or replace hidden[-2]/[-1] with all-layer flattening or last time output.",
            "Do not add hidden/cell summation, attention, mean pooling, or the commented-out pad_packed_sequence call.",
            "Do not rename the actual fc1 expression to a generic direction formula; explain why it works for this fixed profile only.",
            "Do not invent ReLU between fc1 and fc2 or put the predict_class Softmax into model.forward or compute_accuracy.",
            "Do not label Embedding as pretrained GloVe or a100-dimensional projection based only on build_vocab vectors metadata.",
            "Two directions describe the opaque LSTM runtime, not two separately constructed notebook nn.LSTM modules or extracted gate graphs.",
        ],
        symbols={SOURCE:["RNN","RNN.__init__","RNN.forward","compute_accuracy","predict_class"]},
        config_files=[SOURCE],
        legend=["T: padded time axis; B: batch; V: actual vocabulary; H=256 per direction; h_n=[4,B,H]",
                "orange: recurrent library boundary / yellow: ordered directional concat / purple: Linear",
                "last layer forward and reverse run as parallel operands; they are concatenated, not added",
                "one Dropout instance / three call sites / no learned weights; eval identity; caller max outside forward"],
    )


def validate_ir(ir):
    """Check hidden-direction selection, parameter families and real caller boundaries."""
    nodes={n["id"]:n for n in ir["nodes"]};p=ir["profile"];edges=ir["edges"];checks=[]
    def check(condition,label):
        if not condition: raise ValueError("bilstm: "+label)
        checks.append(label)
    def has(a,b,role):
        return any(e["src"]==a and e["dst"]==b and e["role"]==role for e in edges)
    check({"bilstm.core","bilstm.select_hidden","bilstm.forward_state","bilstm.reverse_state",
           "bilstm.last_layer","bilstm.concat","bilstm.embed_dropout","bilstm.hidden_dropout",
           "bilstm.head_dropout","bilstm.fc1","bilstm.fc2","bilstm.lookup","bilstm.pack",
           "bilstm.lengths","bilstm.argmax"} <= nodes.keys(), "required source-grounded operators")
    check(p["mode"]=="eval" and p["embedding_dim"]==128 and p["hidden_dim"]==256 and p["output_dim"]==4
          and p["num_layers"]==2 and p["bidirectional"] is True,
          "selected eval AGNews 128/256/4 profile")
    core=nodes["bilstm.core"]
    check(core["runtime_dependency"]=="torch.nn.LSTM" and core["opaque_runtime_boundary"] is True
          and core["num_layers"]==2 and core["bidirectional"] is True and core["hidden_shape"]=="[4,B,256]",
          "two-layer bidirectional library boundary and hidden shape")
    expected=["rnn."+base+"_l"+str(layer)+suffix for layer in range(2) for suffix in ("","_reverse")
              for base in ("weight_ih","weight_hh","bias_ih","bias_hh")]
    check(core["parameters"]==expected and core["layer_direction_parameter_sharing"] is False
          and core["temporal_parameter_sharing"] is True,"16 independent layer/direction tensors reused across time")
    check(core["output_tuple"]==["packed_output",["hidden","cell"]]
          and nodes["bilstm.select_hidden"]["input_selector"]=="hidden","hidden chosen without cell or packed output")
    f,r=nodes["bilstm.forward_state"],nodes["bilstm.reverse_state"]
    check(f["expression"]=="hidden[-2,:,:]" and r["expression"]=="hidden[-1,:,:]"
          and (f["layer_index"],r["layer_index"],f["hidden_index"],r["hidden_index"])==(1,1,2,3),
          "only last-layer forward/reverse hidden slices")
    bundle=nodes["bilstm.last_layer"];order=["bilstm.forward_state","bilstm.reverse_state"]
    check(bundle["semantic_mode"]=="operand_bundle" and bundle["operand_order"]==order
          and all(bundle["child_inputs"][n]==dict(role="value",producer="bilstm.select_hidden",src_port="out") for n in order)
          and all(has("bilstm.select_hidden",n,"value_operand") for n in order),
          "typed same-hidden operands without tuple dispatch or state summation")
    check(nodes["bilstm.concat"]["dim"]==1 and nodes["bilstm.concat"]["operand_order"]==order
          and nodes["bilstm.concat"]["shape"]=="[B,512]","ordered forward/reverse feature concatenation")
    drops=[nodes[n] for n in ("bilstm.embed_dropout","bilstm.hidden_dropout","bilstm.head_dropout")]
    check(all(n["p"]==0.5 and n["active"] is False and n["instance_identity"]=="self.dropout" and n["learnable"] is False for n in drops)
          and core["dropout"]==0.5 and core["recurrent_dropout_active"] is False,
          "three shared-instance dropout call sites plus inactive eval inter-layer dropout")
    check(nodes["bilstm.fc1"]["source_in_features_expression"]=="hidden_dim * num_layers"
          and nodes["bilstm.fc1"]["in_features"]==512 and nodes["bilstm.fc1"]["out_features"]==64
          and nodes["bilstm.fc2"]["in_features"]==64 and nodes["bilstm.fc2"]["out_features"]==4,
          "actual fixed512->64->4 Linear head and source expression")
    check(nodes["bilstm.lookup"]["pretrained_vectors_copied"] is False
          and nodes["bilstm.lookup"]["padding_idx"]=="TEXT.vocab.stoi[TEXT.pad_token]",
          "padding-aware128-dimensional embedding without copied GloVe")
    check(nodes["bilstm.pack"]["batch_first"] is False and nodes["bilstm.pack"]["enforce_sorted"]=="default True"
          and has("bilstm.lengths","bilstm.pack","sequence_length"),"external lengths and default sorted sequence-first packing")
    check(nodes["bilstm.argmax"]["parent"]=="bilstm.caller" and nodes["bilstm.argmax"]["boundary"]=="caller"
          and nodes["bilstm.argmax"]["expression"]=="torch.max(logits, 1)[1]"
          and not any(n["kind"]=="activation" or "softmax" in n["id"] for n in nodes.values()),
          "raw logits and external max with no invented head activation or Softmax")
    return checks
