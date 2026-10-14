"""Reviewed grouped AlexNet CIFAR-10 notebook, including computed unused Softmax."""
from spec import chain, op, ref


SOURCE = "deeplearning-models-batch2/pytorch_ipynb/cnn/cnn-alexnet-cifar10-grouped.py"


def build():
    init = ref(SOURCE, "AlexNet.__init__")
    forward = ref(SOURCE, "AlexNet.forward")
    roles = {}

    def conv_stage(number, cin, cout, kernel, stride, padding, groups, size, conv_index, relu_index,
                   pool_index=None, pool_size=None):
        prefix = "alex.conv_stage" + str(number)
        shape = "[B,%d,%d,%d]" % (cout, size, size)
        items = [
            op(prefix + ".conv", "Conv2d %d -> %d" % (cin, cout), "conv2d", [init, forward], shape,
               ["kernel=%d; stride=%d; padding=%d; groups=%d" % (kernel, stride, padding, groups),
                "bias=True; grouped channels stay inside this single Conv2d"],
               parameter="features.%d" % conv_index, groups=groups),
            op(prefix + ".relu", "ReLU", "relu", [init, forward], shape, ["inplace=True"]),
        ]
        if pool_index is not None:
            shape = "[B,%d,%d,%d]" % (cout, pool_size, pool_size)
            items.append(op(prefix + ".pool", "MaxPool2d 3x3 / 2", "max_pool2d", [init, forward],
                            shape, ["padding=0; ceil_mode=False; features.%d" % pool_index]))
            roles[prefix + ".pool"] = "pool"
        roles.update({prefix: "conv", prefix + ".conv": "conv", prefix + ".relu": "activation"})
        return chain(prefix, "Conv stage %d%s" % (number, " · groups=2" if groups == 2 else ""),
                     items, [init, forward], shape,
                     ["logical grouping of contiguous features Sequential items", "ReLU is features.%d" % relu_index],
                     expand=2)

    features = chain("alex.features", "Conv features · 5 stages", [
        conv_stage(1, 3, 64, 11, 4, 2, 1, 15, 0, 1, 2, 7),
        conv_stage(2, 64, 192, 5, 1, 2, 2, 7, 3, 4, 5, 3),
        conv_stage(3, 192, 384, 3, 1, 1, 2, 3, 6, 7),
        conv_stage(4, 384, 256, 3, 1, 1, 2, 3, 8, 9),
        conv_stage(5, 256, 256, 3, 1, 1, 2, 3, 10, 11, 12, 1),
    ], [init, forward], "[B,256,1,1]", ["conv2 through conv5 use groups=2"], expand=1)
    def hidden(number, fin, fout, linear_index, dropout_index, relu_index):
        p = "alex.hidden" + str(number)
        roles.update({p: "ffn", p + ".dropout": "control", p + ".linear": "linear",
                      p + ".relu": "activation"})
        return chain(p, "Hidden classifier %d" % number, [
            op(p + ".dropout", "Dropout 0.5", "dropout", [init, forward], "[B,%d]" % fin,
               ["classifier.%d; identity in selected eval mode" % dropout_index,
                "train mode randomly zeroes activations and rescales survivors"]),
            op(p + ".linear", "Linear %d -> %d" % (fin, fout), "linear", [init, forward],
               "[B,%d]" % fout, parameter="classifier.%d" % linear_index),
            op(p + ".relu", "ReLU", "relu", [init, forward], "[B,%d]" % fout,
               ["inplace=True; classifier.%d" % relu_index]),
        ], [init, forward], "[B,%d]" % fout, expand=2)
    classifier = chain("alex.classifier", "Classifier head", [
        hidden(1, 9216, 4096, 1, 0, 2),
        hidden(2, 4096, 4096, 4, 3, 5),
        op("alex.fc3", "Linear 4096 -> 10", "linear", [init, forward],
           "logits: [B,10]", parameter="classifier.6"),
    ], [init, forward], "logits: [B,10]", expand=1)
    tree = chain("alex.model", "Grouped AlexNet · CIFAR-10", [
        op("alex.input", "CIFAR-10 image", "input", forward, "[B,3,64,64]",
           ["caller Resize70 then Crop64; original CIFAR-10 is 32x32"]),
        features,
        op("alex.adaptive_pool", "AdaptiveAvgPool2d 6x6", "adaptive_avg_pool2d", [init, forward],
           "[B,256,6,6]", ["actual input here is 1x1; adaptive bins produce 6x6", "this is not a fixed pooling kernel"]),
        op("alex.flatten", "Flatten spatial features", "tensor", forward, "[B,9216]",
           ["x.view(x.size(0),256*6*6); preserve batch axis"]),
        classifier,
        op("alex.output", "Returned logits", "output", forward, "[B,10]",
           ["return logits only; probabilities are computed but not returned"]),
    ], ref(SOURCE, "AlexNet"), "logits: [B,10]", expand=0)
    unused_softmax = op("alex.unused_softmax", "Computed Softmax · unused", "softmax", forward,
                        "probas: [B,10]", ["F.softmax(logits,dim=1) is executed", "local probas is unused; no edge to forward return"],
                        origin="internal_derived_unused", returned=False, output_ports=["out"])
    roles.update({"alex.model": "root", "alex.input": "input", "alex.features": "encoder",
                  "alex.adaptive_pool": "pool", "alex.flatten": "tensor", "alex.classifier": "ffn",
                  "alex.fc3": "linear", "alex.output": "output", "alex.unused_softmax": "softmax"})
    return dict(
        key="alexnet", name="AlexNet (grouped CIFAR-10)", source_project="deeplearning-models-batch2",
        entry=ref(SOURCE, "AlexNet"),
        profile=dict(task="CIFAR-10 classification", mode="eval", input_channels=3, input_size=[64, 64],
                     num_classes=10, conv_channels=[64, 192, 384, 256, 256], conv_groups=[1, 2, 2, 2, 2],
                     conv_kernel=[11, 5, 3, 3, 3], conv_stride=[4, 1, 1, 1, 1],
                     adaptive_pool_output=[6, 6], feature_spatial_output=[1, 1],
                     classifier=[9216, 4096, 4096, 10], dropout=0.5,
                     output="logits only", computed_unused="Softmax(logits,dim=1)",
                     config_source=SOURCE + " notebook cells 13, 17, 20, 21"),
        profile_label="CIFAR-10 · Crop64 · Conv2-5 groups=2 · eval · logits only",
        tree=tree, aux_inputs=[unused_softmax],
        extra_edges=[dict(src="alex.classifier", dst="alex.unused_softmax", role="computed_unused",
                          label="logits · no return use", src_port="out", dst_port="in")],
        visual_roles=roles,
        fill_width=["alex.features", "alex.adaptive_pool", "alex.flatten", "alex.classifier"] +
                   ["alex.conv_stage%d" % i for i in range(1, 6)] + ["alex.hidden1", "alex.hidden2"],
        facts=[
            "The notebook resizes CIFAR-10 to 70x70 then crops to 64x64; the model receives [B,3,64,64].",
            "Only the first convolution has groups=1; convolutions 2-5 have groups=2 within individual Conv2d modules.",
            "The feature path spatial sizes are 64->15->7->3->1; no local response normalization exists in this implementation.",
            "AdaptiveAvgPool2d((6,6)) consumes the actual 1x1 feature and produces 6x6, then view yields 256*6*6=9216 features.",
            "The classifier uses Dropout0.5->Linear9216->4096->ReLU->Dropout0.5->Linear4096->4096->ReLU->Linear4096->10.",
            "Dropout is retained as a source operator but is an identity in the selected eval profile.",
            "forward computes local probas=Softmax(logits,dim=1) but returns only logits; the side node has no return dependency.",
            "Eight parameterized Conv/Linear modules have distinct parameter paths; groups=2 does not create two Python-level modules or branches.",
        ],
        corrections=[
            "Use the notebook's 64x64 crop rather than ImageNet 224x224 input; do not assume final convolutional maps are 6x6.",
            "Do not add paper-era LRN, two-GPU split modules, or an explicit concatenation for the grouped Conv2d implementations.",
            "Do not change the computed unused Softmax into a returned probability tuple; this source returns logits alone.",
            "Keep AdaptiveAvgPool2d and its actual output target rather than silently replacing it with global average pooling.",
        ],
        symbols={SOURCE: ["AlexNet", "AlexNet.__init__", "AlexNet.forward"]}, config_files=[SOURCE],
        legend=["B batch; image layout [B,C,H,W]", "input pink / Conv blue / Linear and return purple / ReLU gray / Softmax green",
                "groups=2 stays inside each Conv2d; same color is not weight sharing",
                "side Softmax is computed and unused; only logits reach the forward return"],
    )
