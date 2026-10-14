"""Reviewed CIFAR-10 Network in Network path; notebook code is never run."""
from spec import chain, op, parallel, ref

SOURCE = "deeplearning-models-batch2/pytorch_ipynb/cnn/nin-cifar10.py"


def build():
    init = ref(SOURCE, "NiN.__init__")
    forward = ref(SOURCE, "NiN.forward")
    roles, fill = {"nin.root": "root"}, []

    def mlpconv(i, channels, kernels, indices, spatial):
        p = "nin.mlpconv%d" % i
        items = []
        for j, (cin, cout, kernel, index) in enumerate(zip(channels, channels[1:], kernels, indices), 1):
            conv_id, relu_id = p + ".conv%d" % j, p + ".relu%d" % j
            pad = kernel // 2 if kernel > 1 else 0
            items.extend([
                op(conv_id, "Conv %dx%d: %d -> %d" % (kernel, kernel, cin, cout), "conv", [init, forward],
                   "[B,%d,%d,%d]" % (cout, spatial, spatial),
                   ["stride=1; padding=%d; default bias=True" % pad,
                    "One kernel is shared over spatial locations, not over different layers"],
                   parameter="classifier.%d" % index),
                op(relu_id, "ReLU", "activation", [init, forward],
                   "[B,%d,%d,%d]" % (cout, spatial, spatial), ["inplace=True"]),
            ])
            roles[conv_id], roles[relu_id] = "conv", "activation"
        roles[p] = "conv"; fill.append(p)
        return chain(p, "mlpconv %d / spatial + 1x1 stack" % i, items, [init, forward],
                     "[B,%d,%d,%d]" % (channels[-1], spatial, spatial),
                     ["Logical diagram group within one nn.Sequential", "Three independent Conv-ReLU pairs"], expand=2)

    stage1 = chain("nin.stage1", "Feature stage 1", [
        mlpconv(1, [3, 192, 160, 96], [5, 1, 1], [0, 2, 4], 32),
        op("nin.pool1", "MaxPool 3x3 / 2", "pool", [init, forward], "[B,96,16,16]",
           ["padding=1; classifier.6"]),
        op("nin.dropout1", "Dropout p=0.5", "control", [init, forward], "[B,96,16,16]",
           ["classifier.7; inactive only when caller selects eval"], parameter_scope="classifier.7", dropout=0.5),
    ], [init, forward], "[B,96,16,16]", expand=1)
    stage2 = chain("nin.stage2", "Feature stage 2", [
        mlpconv(2, [96, 192, 192, 192], [5, 1, 1], [8, 10, 12], 16),
        op("nin.pool2", "Average pool 3x3 / 2", "pool", [init, forward], "[B,192,8,8]",
           ["padding=1; classifier.14; default count_include_pad=True"]),
        op("nin.dropout2", "Dropout p=0.5", "control", [init, forward], "[B,192,8,8]",
           ["classifier.15; follows caller train/eval state"], parameter_scope="classifier.15", dropout=0.5),
    ], [init, forward], "[B,192,8,8]", expand=1)
    stage3 = chain("nin.stage3", "Class feature maps + global pool", [
        mlpconv(3, [192, 192, 192, 10], [3, 1, 1], [16, 18, 20], 8),
        op("nin.pool3", "Average pool 8x8 / 1", "pool", [init, forward], "[B,10,1,1]",
           ["classifier.22; fixed kernel=8, padding=0", "Global on the selected 8x8 feature maps; not AdaptiveAvgPool"]),
    ], [init, forward], "[B,10,1,1]", expand=1)
    returns = parallel("nin.returns", "Return logits / probabilities", [
        op("nin.logits", "Retain logits", "tensor", forward, "[B,10]",
           ["Mean of nonnegative class feature maps; no learned Linear head"]),
        op("nin.softmax", "Softmax over classes", "softmax", forward, "[B,10]",
           ["torch.softmax(logits,dim=1)"]),
    ], forward, "(logits, probas)", ["Same logits fan out; tuple collection, not summation"], expand=1)
    tree = chain("nin.root", "NiN / CIFAR-10", [
        op("nin.input", "CIFAR-10 image", "input", forward, "[B,3,32,32]",
           ["Dataset ToTensor converts pixels to [0,1] outside forward"]),
        stage1, stage2, stage3,
        op("nin.view", "View pooled maps as logits", "tensor", forward, "[B,10]",
           ["x.view(x.size(0),self.num_classes); batch axis preserved"]),
        returns,
        op("nin.output", "Forward return tuple", "output", forward, "2 x [B,10]",
           ["return logits,probas; cross_entropy uses logits"]),
    ], ref(SOURCE, "NiN"), "[B,3,32,32] -> (logits,probas)", expand=0)
    roles.update({"nin.stage1": "encoder", "nin.stage2": "encoder", "nin.stage3": "ffn",
                  "nin.input": "input", "nin.output": "output", "nin.view": "tensor",
                  "nin.pool1": "pool", "nin.pool2": "pool", "nin.pool3": "pool",
                  "nin.dropout1": "control", "nin.dropout2": "control",
                  "nin.returns": "group", "nin.logits": "tensor", "nin.softmax": "softmax"})
    fill.extend(["nin.stage1", "nin.stage2", "nin.stage3", "nin.view", "nin.returns"])
    return dict(
        key="nin", name="NiN (Network in Network)", source_project="deeplearning-models-batch2",
        entry=ref(SOURCE, "NiN"),
        profile=dict(task="CIFAR10 classification", input_channels=3, image_size=32, num_classes=10,
                     batch_size_setting=256, mlpconv_channels=[[3,192,160,96],[96,192,192,192],[192,192,192,10]],
                     kernels=[[5,1,1],[5,1,1],[3,1,1]], spatial_sizes=[32,16,8,1], dropout=0.5,
                     mode="forward structure; Dropout follows caller train/eval state",
                     final_pool="fixed AvgPool2d(8,stride=1)", output_tuple=["logits","probas"],
                     symbolic_shapes=True, model_executed=False),
        profile_label="CIFAR-10 / 3 mlpconv stages / 10 class maps / fixed pool 8",
        tree=tree, aux_inputs=[], extra_edges=[], visual_roles=roles, fill_width=fill,
        facts=[
            "NiN.classifier is one nn.Sequential; three mlpconv/stage containers are logical source-grounded drawing groups.",
            "The nine independent Conv2d channel changes are 3->192->160->96->192->192->192->192->192->10.",
            "Each stage uses one spatial Conv followed by two 1x1 Conv; ReLU follows all nine convolutions, including the final class convolution.",
            "The first reduction uses MaxPool2d(3,2,1); the second uses AvgPool2d(3,2,1); each is followed by Dropout(0.5).",
            "Final class maps have 10 hard-coded channels; fixed AvgPool2d(8,1,0) globally averages selected 8x8 maps.",
            "forward preserves batch while viewing pooled maps, computes Softmax(dim=1), and returns both logits and probabilities.",
            "The num_classes argument controls only the final view; the last Conv2d is hard-coded to 10 channels.",
            "compute_accuracy does not call model.eval in this notebook; graph records Dropout and does not imply validation disables it.",
            "Convolution weights are shared across spatial positions, while all nine classifier layer instances own separate parameters.",
        ],
        corrections=[
            "No supplied NiN reference PNG exists; this is a new layout grounded in the selected notebook rather than a generic paper diagram.",
            "Do not replace the second AvgPool by MaxPool, or the fixed final pool by AdaptiveAvgPool.",
            "Retain the final ReLU after Conv1x1(192,10); the logits are not produced by a separate Linear layer.",
            "Draw two return fields: raw logits and the forward Softmax result.",
            "Do not silently treat num_classes as controlling final Conv channels, or infer eval mode from the accuracy-function name.",
        ],
        symbols={SOURCE: ["NiN", "NiN.__init__", "NiN.forward", "compute_accuracy"]},
        config_files=[SOURCE],
        legend=["B batch; image layout [B,C,H,W]", "mlpconv = spatial Conv + two point-wise Conv, each with ReLU",
                "32 -> 16 -> 8 -> 1 spatial resolution", "Same glyph type is not shared layer parameters",
                "Dropout is active in train mode; forward returns (logits,probas)"],
    )
