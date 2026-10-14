"""Reviewed DenseNet-BC-100 CIFAR-10 path; model code is never imported."""
from spec import chain, op, ref

MODEL = "densenet.pytorch/densenet.py"
TRAIN = "densenet.pytorch/train.py"


def build():
    def r(symbol):
        return ref(MODEL, symbol)

    edges, roles, fill = [], {}, []

    def dense_block(i, channels, spatial):
        p = "dense_b%d" % i
        cj = "%d+12j" % channels
        items = [
            op(p + "_input", "Retain dense input x", "tensor", r("Bottleneck.forward"),
               "[B,Cj,%d,%d]" % (spatial, spatial),
               ["Cj=%s; j=0,...,15" % cj, "This x contains every preceding feature in this block"],
               output_ports=["out", "retained"]),
            op(p + "_bn1", "BatchNorm Cj", "norm",
               [r("Bottleneck.__init__"), r("Bottleneck.forward")],
               "[B,Cj,%d,%d]" % (spatial, spatial),
               param_identity="dense%d[j].bn1" % i),
            op(p + "_relu1", "ReLU", "activation", r("Bottleneck.forward"),
               "[B,Cj,%d,%d]" % (spatial, spatial)),
            op(p + "_conv1", "Conv 1x1: Cj -> 4k", "conv",
               [r("Bottleneck.__init__"), r("Bottleneck.forward")],
               "[B,48,%d,%d]" % (spatial, spatial),
               ["k=12; stride=1; bias=False"], param_identity="dense%d[j].conv1" % i),
            op(p + "_bn2", "BatchNorm 4k", "norm",
               [r("Bottleneck.__init__"), r("Bottleneck.forward")],
               "[B,48,%d,%d]" % (spatial, spatial), param_identity="dense%d[j].bn2" % i),
            op(p + "_relu2", "ReLU", "activation", r("Bottleneck.forward"),
               "[B,48,%d,%d]" % (spatial, spatial)),
            op(p + "_conv2", "Conv 3x3: 4k -> k", "conv",
               [r("Bottleneck.__init__"), r("Bottleneck.forward")],
               "[B,12,%d,%d]" % (spatial, spatial),
               ["padding=1; stride=1; bias=False"], param_identity="dense%d[j].conv2" % i),
            op(p + "_cat", "Concat x and new features", "concat", r("Bottleneck.forward"),
               "[B,Cj+12,%d,%d]" % (spatial, spatial),
               ["torch.cat((x,out),1); channel concatenation, not addition"],
               input_ports=["in", "side"]),
        ]
        representative = chain(p + "_layer", "Bottleneck template j=0...15", items,
            [r("Bottleneck.__init__"), r("Bottleneck.forward"), r("DenseNet._make_dense")],
            "Cj=%s; growth k=12" % cj,
            ["16 sequential layers; each owns distinct parameters", "Only one symbolic iteration is expanded"],
            expand=2, param_identity="dense%d[j]" % i,
            iteration_index="j", channel_input="%d+12*j" % channels,
            channel_output="%d+12*(j+1)" % channels)
        block = chain(p, "Dense block %d x 16" % i, [representative],
            [r("DenseNet._make_dense"), r("DenseNet.forward")],
            "[B,%d,%d,%d] -> [B,%d,%d,%d]" %
            (channels, spatial, spatial, channels + 16 * 12, spatial, spatial),
            ["Each layer appends k=12 channels; no feature summation"], expand=1,
            param_identity="dense%d" % i,
            repeat=dict(count=16, index="j", template=p + "_layer", independent_parameters=True))
        edges.append(dict(src=p + "_input", dst=p + "_cat", role="dense_concat",
                          label="x: retained channels", src_port="retained", dst_port="side"))
        roles[p] = "encoder"; roles[p + "_layer"] = "group"
        roles[p + "_cat"] = "concat"
        fill.extend([p, p + "_layer"])
        return block

    def transition(i, cin, cout, spatial):
        p = "dense_t%d" % i
        roles[p] = "group"; fill.append(p)
        return chain(p, "Transition %d: compression + pooling" % i, [
            op(p + "_bn", "BatchNorm", "norm", [r("Transition.__init__"), r("Transition.forward")],
               "[B,%d,%d,%d]" % (cin, spatial, spatial), param_identity="trans%d.bn1" % i),
            op(p + "_relu", "ReLU", "activation", r("Transition.forward"),
               "[B,%d,%d,%d]" % (cin, spatial, spatial)),
            op(p + "_conv", "Conv 1x1: %d -> %d" % (cin, cout), "conv",
               [r("Transition.__init__"), r("Transition.forward")],
               "[B,%d,%d,%d]" % (cout, spatial, spatial),
               ["floor(C*0.5); bias=False"], param_identity="trans%d.conv1" % i),
            op(p + "_pool", "Average pool 2x2 / 2", "pool", r("Transition.forward"),
               "[B,%d,%d,%d]" % (cout, spatial // 2, spatial // 2)),
        ], [r("Transition.__init__"), r("Transition.forward")],
            "[B,%d,%d,%d]" % (cout, spatial // 2, spatial // 2), expand=2,
            param_identity="trans%d" % i)

    head = chain("dense_head", "Final normalization + classifier", [
        op("dense_final_bn", "BatchNorm 342", "norm", [r("DenseNet.__init__"), r("DenseNet.forward")],
           "[B,342,8,8]", param_identity="bn1"),
        op("dense_final_relu", "ReLU", "activation", r("DenseNet.forward"), "[B,342,8,8]"),
        op("dense_global_pool", "Average pool 8x8", "pool", r("DenseNet.forward"), "[B,342,1,1]",
           ["Fixed kernel=8 in this CIFAR-10 path; not AdaptiveAvgPool"]),
        op("dense_squeeze", "Squeeze singleton axes", "tensor", r("DenseNet.forward"), "[B,342] for B>1",
           ["torch.squeeze removes every singleton axis", "At B=1 this legacy implementation produces [342]"]),
        op("dense_fc", "Linear 342 -> 10", "linear", [r("DenseNet.__init__"), r("DenseNet.forward")],
           "[B,10] for B>1", param_identity="fc"),
        op("dense_log_softmax", "LogSoftmax over classes", "softmax", r("DenseNet.forward"),
           "[B,10] log probabilities",
           ["Legacy F.log_softmax(fc(out)) call omits dim", "Class-axis interpretation assumes selected B>1 profile"]),
    ], r("DenseNet.forward"), "342 features -> 10 classes", expand=2)
    roles.update(densenet="root", dense_stem="conv", dense_head="ffn", dense_log_softmax="softmax")
    fill.extend(["dense_stem", "dense_head"])
    tree = chain("densenet", "DenseNet-BC-100 / CIFAR-10", [
        op("dense_input", "CIFAR-10 image", "input", ref(TRAIN, "main"), "[B,3,32,32]"),
        op("dense_stem", "Stem Conv 3x3: 3 -> 24", "conv", [r("DenseNet.__init__"), r("DenseNet.forward")],
           "[B,24,32,32]", ["padding=1; bias=False; no stem pooling"], param_identity="conv1"),
        dense_block(1, 24, 32), transition(1, 216, 108, 32),
        dense_block(2, 108, 16), transition(2, 300, 150, 16),
        dense_block(3, 150, 8), head,
        op("dense_output", "Class log probabilities", "output", r("DenseNet.forward"), "[B,10] for B>1"),
    ], r("DenseNet.forward"), "[B,3,32,32] -> [B,10]", expand=0)
    return dict(
        key="densenet", name="DenseNet-BC-100", source_project="densenet.pytorch", entry=r("DenseNet"),
        profile=dict(dataset="CIFAR10", growthRate=12, depth=100, reduction=0.5, bottleneck=True,
                     nClasses=10, layers_per_block=16, input_channels=3, image_size=32, batch_size=64,
                     mode="evaluation", shape_batch_assumption="B>1",
                     symbolic_shapes=True, model_executed=False),
        profile_label="CIFAR-10 / depth=100 / k=12 / theta=0.5 / B>1",
        tree=tree, aux_inputs=[], extra_edges=edges, visual_roles=roles, fill_width=fill,
        facts=[
            "train.main constructs DenseNet(growthRate=12,depth=100,reduction=0.5,bottleneck=True,nClasses=10).",
            "(100-4)//3//2 = 16 Bottleneck layers per dense block; 48 distinct bottleneck instances in total.",
            "Feature channels are 3->24->216->108->300->150->342->10; spatial sizes are 32->16->8->1.",
            "Every Bottleneck performs BN->ReLU->Conv1x1->BN->ReLU->Conv3x3->channel cat(x,out).",
            "Dense reuse means channel concatenation, not a residual Add; retained x bypasses both convolutions.",
            "Repeated blocks/layers have independently created parameters; a representative symbolic template is drawn.",
            "The source uses fixed avg_pool2d(kernel=8), torch.squeeze without axis, and legacy log_softmax without dim.",
            "The diagrams use a selected B>1 static profile; no claim of modern PyTorch runtime compatibility is made.",
        ],
        corrections=[
            "Use the repository's CIFAR-10 BC-100 variant, not an ImageNet DenseNet-121 stem or four dense stages.",
            "Draw explicit channel Concat and retained-input dependency; do not replace dense connections by Add.",
            "Transition pooling is average pooling and compression is floor(C*0.5).",
            "The returned output is log probability, not logits or ordinary Softmax probability.",
            "Preserve the actual fixed pooling and all-axis squeeze, including their input-size/batch-size limitation.",
        ],
        symbols={MODEL: ["Bottleneck", "Bottleneck.__init__", "Bottleneck.forward", "Transition", "Transition.__init__",
                         "Transition.forward", "DenseNet", "DenseNet.__init__", "DenseNet._make_dense", "DenseNet.forward"],
                 TRAIN: ["main"]},
        config_files=[TRAIN],
        legend=["B batch (selected B>1)", "C channels", "H,W spatial axes", "k=12 growth", "j=0...15 layer index",
                "Cj=block input channels+12j", "theta=0.5 compression", "Concat joins channels; no Add", "x16: distinct layer parameters"],
    )
