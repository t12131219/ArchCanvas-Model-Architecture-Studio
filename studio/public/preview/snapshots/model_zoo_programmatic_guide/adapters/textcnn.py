"""Reviewed modern IMDb TextCNN with valid-window masking; no model execution."""
from spec import chain, op, parallel, ref

SOURCE = "deeplearning-models-batch2/pytorch_ipynb/cnn-nlp/cnn_imdb.py"


def build():
    init = ref(SOURCE, "TextCNN.__init__")
    forward = ref(SOURCE, "TextCNN.forward")
    config = ref(SOURCE, "Config")
    loaders = ref(SOURCE, "make_loaders")
    roles, fill, edges = {}, [], []

    def branch(width, index):
        p = "textcnn.k%d" % width
        positions = 512 - width + 1
        validity = chain(p + ".validity", "Build valid-window mask", [
            parallel(p + ".mask_operands", "Allowed count / positions", [
                chain(p + ".valid_count", "Count retained windows", [
                    op(p + ".count", "lengths - k + 1", "control", forward, "[B]",
                       ["k=%d; independent lengths operand enters side port" % width],
                       input_relation=dict(role="external",producer="textcnn.lengths",src_port="out"),
                       input_ports=["lengths"]),
                    op(p + ".clamp", "Clamp count to at least 1", "control", forward, "valid_windows: [B]",
                       [".clamp(min=1)", "A short review retains its first zero-padded convolution window"]),
                ], forward, "valid_windows: [B]", expand=2,
                    input_relation=dict(role="external",producer="textcnn.lengths",src_port="out"),
                    suppress_input_boundary=True),
                op(p + ".positions", "arange feature positions", "tensor", forward, "positions: [%d]" % positions,
                   ["torch.arange(features.shape[-1],device=features.device)", "Runtime S=L-k+1; only shape, not feature values"],
                   input_relation=dict(role="shape",producer=p + ".relu",src_port="shape")),
            ], forward, "count + position operands", expand=2,
                semantic_mode="operand_bundle", literal_tuple=False,
                child_inputs={
                    p + ".valid_count":dict(role="external",producer="textcnn.lengths",src_port="out"),
                    p + ".positions":dict(role="shape",producer=p + ".relu",src_port="shape"),
                }),
            op(p + ".mask", "positions >= valid_windows", "control", forward, "mask: [B,%d]" % positions,
               ["positions[None,:] >= valid_windows[:,None]", "True excludes a window; lengths never become learned features"]),
        ], forward, "mask: [B,%d]" % positions, expand=2,
            input_relation=dict(role="shape",producer=p + ".relu",src_port="shape"),
            boundary_input_role="shape")
        operands = parallel(p + ".operands", "Retained features / length mask", [
            op(p + ".features_operand", "Retain ReLU features", "tensor", forward,
               "[B,128,%d]" % positions,
               input_relation=dict(role="value",producer=p + ".relu",src_port="out")),
            validity,
        ], forward, "features + mask operands",
            ["Logical operation-argument group; source does not create a (features,mask) tuple",
             "features retains ReLU values; mask only reads ReLU shape and external lengths"],
            expand=2, semantic_mode="operand_bundle",literal_tuple=False,
            child_inputs={
                p + ".features_operand":dict(role="value",producer=p + ".relu",src_port="out"),
                p + ".validity":dict(role="shape",producer=p + ".relu",src_port="shape"),
            })
        result = chain(p, "Conv branch / width k=%d" % width, [
            op(p + ".conv", "Conv1d 200 -> 128 / k=%d" % width, "conv", [init,forward],
               "[B,128,%d]" % positions,
               ["stride=1; padding=0; dilation=1; default bias=True", "One separate ModuleList convolution per width"],
               parameter="convolutions.%d" % index),
            op(p + ".relu", "ReLU", "activation", forward, "[B,128,%d]" % positions),
            operands,
            op(p + ".masked_fill", "Fill excluded windows with dtype min", "control", forward,
               "[B,128,%d]" % positions,
               ["features.masked_fill(mask[:,None,:],torch.finfo(features.dtype).min)",
                "Same mask broadcasts across all 128 filters; finite minimum, not -infinity"]),
            op(p + ".amax", "amax over valid positions", "pool", forward, "[B,128]",
               ["features.amax(dim=-1); one feature per convolution filter"]),
        ], [init,forward], "[B,128]", ["S=L-k+1; selected example L=512"], expand=2,
            parameter_scope="convolutions.%d" % index)
        edges.append(dict(src="textcnn.lengths",dst=p + ".count",role="sequence_length",
                          label="lengths for k=%d" % width,src_port="out",dst_port="lengths"))
        roles.update({p:"conv",p+".conv":"conv",p+".relu":"activation",p+".operands":"inner",
                      p+".features_operand":"tensor",p+".validity":"group",p+".mask_operands":"inner",
                      p+".valid_count":"group",p+".count":"control",p+".clamp":"control",
                      p+".positions":"tensor",p+".mask":"control",p+".masked_fill":"control",p+".amax":"pool"})
        return result

    embedding = chain("textcnn.embedding", "Embedding + channel-first layout", [
        op("textcnn.lookup", "Embedding V -> 200", "embedding", [init,forward], "[B,L,200]",
           ["padding_idx=0; vocabulary matrix initialized uniform[-0.25,0.25]", "Padding row explicitly zeroed in __init__"],
           parameter="embedding.weight"),
        op("textcnn.transpose", "Transpose axes 1 and 2", "tensor", forward, "[B,200,L]",
           ["Conv1d interprets embedding width as channels"]),
    ], [init,forward], "[B,200,512]", expand=1)
    branches = parallel("textcnn.branches", "Three independent convolution widths", [branch(3,0),branch(4,1),branch(5,2)],
                        [init,forward], "3 tensors [B,128]",
                        ["Each branch receives the same embedded sequence", "Separate Conv weights; tuple/list collection is not summation"],expand=1)
    classifier = chain("textcnn.head", "Concatenated feature classifier", [
        op("textcnn.concat", "Concat pooled branch features", "concat", forward, "[B,384]",
           ["torch.cat(pooled,dim=1); ordered widths 3,4,5", "3*128=384; not temporal concat"]),
        op("textcnn.dropout", "Dropout p=0.5", "control", [init,forward], "[B,384]",
           ["Disabled in selected evaluate/model.eval path"], dropout=0.5),
        op("textcnn.classifier", "Linear 384 -> 2", "linear", [init,forward], "logits: [B,2]",
           ["class order: negative=0, positive=1; no Softmax in forward"],parameter="classifier"),
    ], [init,forward], "logits: [B,2]",expand=1)
    tree = chain("textcnn.root", "TextCNN / IMDb valid-window pooling", [
        op("textcnn.input", "Right-padded token IDs", "input", [forward,loaders], "[B,512]",
           ["Caller truncates to max_length=512; padding index 0", "Empty tokenization is replaced by [unk], so lengths>=1"]),
        embedding,branches,classifier,
        op("textcnn.output", "Two-class logits", "output", forward, "[B,2]",
           ["evaluate argmax and cross_entropy are caller operations"]),
    ], ref(SOURCE,"TextCNN"), "(token_ids,lengths) -> logits [B,2]",expand=0)
    lengths = op("textcnn.lengths","External valid lengths","input",[forward,loaders],"lengths: [B]",
                 ["1 <= lengths <= 512 on selected make_loaders path", "Counts real tokens after truncation, excluding right padding"],
                 origin="caller TensorDataset(ids,lengths,labels)",learnable=False)
    roles.update({"textcnn.root":"root","textcnn.embedding":"embedding","textcnn.lookup":"embedding",
                  "textcnn.transpose":"tensor","textcnn.branches":"encoder","textcnn.head":"ffn",
                  "textcnn.concat":"concat","textcnn.dropout":"control","textcnn.classifier":"linear",
                  "textcnn.input":"input","textcnn.output":"output","textcnn.lengths":"input"})
    fill.extend(["textcnn.embedding","textcnn.branches","textcnn.head"])
    return dict(
        key="textcnn",name="TextCNN (IMDb length-masked)",source_project="deeplearning-models-batch2",
        entry=ref(SOURCE,"TextCNN"),
        profile=dict(task="IMDb sentiment classification",mode="evaluation (Dropout disabled)",
                     vocabulary_size="V=len(vocabulary)",vocabulary_max_size=30000,min_frequency=2,
                     max_length=512,embedding_dim=200,filter_widths=[3,4,5],filters_per_width=128,
                     feature_positions=[510,509,508],pooled_features=384,dropout=0.5,output_classes=2,
                     batch_size_setting=128,input_layout="[B,L]",lengths_layout="[B]",padding_idx=0,
                     valid_windows="max(lengths-k+1,1)",mask_fill="torch.finfo(features.dtype).min",
                     caller_autocast="bfloat16 CUDA evaluation; runtime not executed",forward_softmax=False,
                     symbolic_shapes=True,model_executed=False),
        profile_label="IMDb / E=200 / widths 3,4,5 / 128 filters each / L=512 / eval",
        tree=tree,aux_inputs=[lengths],extra_edges=edges,visual_roles=roles,fill_width=fill,
        view_overrides={"2":{"textcnn.k4.operands":3,"textcnn.k5.operands":3}},
        facts=[
            "Config defaults are embedding_dim=200,filter_widths=(3,4,5),filters_per_width=128,max_length=512,dropout=0.5.",
            "The realized embedding row count is len(vocabulary); 30000 is an upper limit including pad/unk, not a guaranteed exact size.",
            "One shared embedding supplies three independently parameterized Conv1d branches, all with no padding and stride=1.",
            "For L=512, convolution output positions are 510,509,508; each branch maps 200 embedding channels to 128 filters.",
            "After ReLU, valid_windows=(lengths-k+1).clamp(min=1); positions>=valid_windows marks excluded windows.",
            "Internal parallel argument groups are logical operand bundles, not literal source tuples or tuple-field dispatch.",
            "Typed child bindings give count only the external lengths input, positions only ReLU.shape, and masked_fill the retained ReLU values plus mask.",
            "Very short reviews retain their first zero-padded window rather than excluding every window.",
            "Excluded features are filled with the finite minimum of their actual floating dtype, then amax over positions yields [B,128].",
            "Pooled features concatenate in widths 3,4,5 order to [B,384], pass Dropout(0.5), then Linear(384,2).",
            "forward returns raw two-class logits only; evaluate applies argmax and cross_entropy outside model forward.",
            "Lengths are an explicit caller input used by each branch mask; they are not learned embedding or a packed recurrent input.",
            "Convolution kernels share weights across positions within each branch; different widths have distinct parameter instances.",
        ],
        corrections=[
            "This frozen notebook is a newer length-masked implementation, not the older torchtext/TextCNN tutorial structure.",
            "Use Conv1d with batch-first token IDs followed by transpose, not a made-up Conv2d image or sequence-first input.",
            "Draw masking before maximum reduction; including every padded convolution window changes this source's semantics.",
            "Preserve clamp(min=1) for short reviews and torch.finfo(dtype).min; neither all-invalid output nor -infinity is the literal source.",
            "Draw explicit channel Concat after three branch reductions; branches are not summed and do not share convolution weights.",
            "Do not add a forward Softmax, positional encoding, attention, LSTM packing or pretrained embeddings.",
        ],
        symbols={SOURCE:["Config","TextCNN","TextCNN.__init__","TextCNN.forward","make_loaders","tokenize","check_model","evaluate"]},
        config_files=[SOURCE],
        legend=["B batch; L=512 padded tokens; E=200 embedding width; V realized vocabulary",
                "k in {3,4,5}; S=L-k+1; F=128 convolution filters", "Masks use external lengths; each branch retains at least one window",
                "Three [B,F] results concatenate to [B,3F]; same glyph is not shared branch weights"],
    )
