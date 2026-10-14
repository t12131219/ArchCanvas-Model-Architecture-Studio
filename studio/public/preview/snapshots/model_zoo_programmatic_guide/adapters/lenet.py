"""Reviewed LeNet5 MNIST adapter; the upstream notebook is never executed."""
from spec import chain, op, parallel, ref


SOURCE = "deeplearning-models/pytorch_ipynb/cnn/cnn-lenet5-mnist.py"


def build():
    init = ref(SOURCE, "LeNet5.__init__")
    forward = ref(SOURCE, "LeNet5.forward")
    features = chain("lenet.features", "Convolutional features", [
        chain("lenet.conv_stage1", "Conv / Tanh / Pool · 1", [
            op("lenet.conv1", "Conv2d 1 -> 6", "conv2d", [init, forward],
               "[B,6,28,28]", ["kernel=5; stride=1; padding=0; bias=True"],
               parameter="features.0"),
            op("lenet.tanh1", "Tanh", "tanh", [init, forward], "[B,6,28,28]"),
            op("lenet.pool1", "MaxPool2d", "max_pool2d", [init, forward],
               "[B,6,14,14]", ["kernel=2; default stride=2"]),
        ], [init, forward], "[B,6,14,14]", ["logical group: features.0 / .1 / .2"], expand=2),
        chain("lenet.conv_stage2", "Conv / Tanh / Pool · 2", [
            op("lenet.conv2", "Conv2d 6 -> 16", "conv2d", [init, forward],
               "[B,16,10,10]", ["kernel=5; stride=1; padding=0; bias=True"],
               parameter="features.3"),
            op("lenet.tanh2", "Tanh", "tanh", [init, forward], "[B,16,10,10]"),
            op("lenet.pool2", "MaxPool2d", "max_pool2d", [init, forward],
               "[B,16,5,5]", ["kernel=2; default stride=2"]),
        ], [init, forward], "[B,16,5,5]", ["logical group: features.3 / .4 / .5"], expand=2),
    ], [init, forward], "[B,16,5,5]", expand=1)
    classifier = chain("lenet.classifier", "Fully connected classifier", [
        chain("lenet.hidden1", "Linear / Tanh · 1", [
            op("lenet.fc1", "Linear 400 -> 120", "linear", [init, forward],
               "[B,120]", ["16 * 5 * 5 = 400"], parameter="classifier.0"),
            op("lenet.tanh3", "Tanh", "tanh", [init, forward], "[B,120]"),
        ], [init, forward], "[B,120]", ["logical group: classifier.0 / .1"], expand=2),
        chain("lenet.hidden2", "Linear / Tanh · 2", [
            op("lenet.fc2", "Linear 120 -> 84", "linear", [init, forward],
               "[B,84]", parameter="classifier.2"),
            op("lenet.tanh4", "Tanh", "tanh", [init, forward], "[B,84]"),
        ], [init, forward], "[B,84]", ["logical group: classifier.2 / .3"], expand=2),
        op("lenet.fc3", "Linear 84 -> 10", "linear", [init, forward],
           "[B,10]", ["raw class logits; no activation here"], parameter="classifier.4"),
    ], [init, forward], "logits: [B,10]", expand=1)
    returns = parallel("lenet.returns", "Return logits / probabilities", [
        op("lenet.logits", "Logits", "identity", forward,
           "[B,10]", ["return original classifier output; used by cross_entropy"]),
        op("lenet.softmax", "Softmax", "softmax", forward,
           "[B,10]", ["F.softmax(logits, dim=1); returned as probas"]),
    ], forward, "(logits, probas)", ["same logits tensor to both branches"],
       expand=1, dispatch=False)
    tree = chain("lenet.model", "LeNet5 · MNIST", [
        op("lenet.input", "MNIST image", "input", forward,
           "[B,1,32,32]", ["caller resizes original MNIST 28x28 to 32x32", "grayscale=True"]),
        features,
        op("lenet.flatten", "Flatten features", "tensor", forward,
           "[B,400]", ["torch.flatten(x, 1); preserve batch axis"]),
        classifier,
        returns,
        op("lenet.output", "Forward return tuple", "output", forward,
           "2 x [B,10]", ["return logits, probas; Softmax belongs to forward"]),
    ], ref(SOURCE, "LeNet5"), "2 x [B,10]", expand=0)
    roles = {
        "lenet.model": "root", "lenet.features": "conv", "lenet.classifier": "ffn",
        "lenet.returns": "group", "lenet.input": "input", "lenet.output": "output",
        "lenet.flatten": "tensor", "lenet.logits": "tensor", "lenet.softmax": "softmax",
        "lenet.conv_stage1": "conv", "lenet.conv_stage2": "conv",
        "lenet.hidden1": "ffn", "lenet.hidden2": "ffn",
    }
    roles.update({"lenet." + name: "conv" for name in ("conv1", "conv2")})
    roles.update({"lenet." + name: "pool" for name in ("pool1", "pool2")})
    roles.update({"lenet." + name: "linear" for name in ("fc1", "fc2", "fc3")})
    roles.update({"lenet.tanh" + str(i): "activation" for i in range(1, 5)})
    return dict(
        key="lenet", name="LeNet5", source_project="deeplearning-models",
        entry=ref(SOURCE, "LeNet5"),
        profile=dict(task="MNIST classification", mode="eval", input_channels=1,
                     input_size=[32, 32], num_classes=10, grayscale=True,
                     conv_channels=[6, 16], conv_kernel=5, pooling="MaxPool2d(2)",
                     activation="Tanh", classifier=[400, 120, 84, 10],
                     output="(logits, probas)", config_source=SOURCE + " notebook cells 8, 10, 13"),
        profile_label="MNIST · 32x32 grayscale · Tanh / MaxPool · eval",
        tree=tree, aux_inputs=[], extra_edges=[], visual_roles=roles,
        fill_width=["lenet.features", "lenet.flatten", "lenet.classifier", "lenet.returns",
                    "lenet.conv_stage1", "lenet.conv_stage2", "lenet.hidden1", "lenet.hidden2"],
        facts=[
            "The caller resizes MNIST to 32x32 and constructs LeNet5(NUM_CLASSES, GRAYSCALE), with NUM_CLASSES=10 and GRAYSCALE=True.",
            "Both convolutions have kernel 5, stride 1, padding 0; spatial sizes are 32 -> 28 -> 14 -> 10 -> 5.",
            "This source uses Tanh and MaxPool2d, not ReLU or the average subsampling in the original LeNet-5 paper.",
            "The classifier receives 16*5*5=400 flattened features, then applies Linear 400->120->84->10 with two Tanh operations.",
            "forward computes Softmax(dim=1) and returns both raw logits and probabilities; cross_entropy consumes the logits branch.",
            "All five parameterized layers have separate parameter identities. Equal colors denote operator families, never weight sharing.",
        ],
        corrections=[
            "No supplied model-specific reference PNG exists for this source; the layout is constructed from the reviewed implementation.",
            "Do not substitute the paper's average pooling, C5 convolution, or partial connection scheme for this simpler nn.Sequential implementation.",
            "The model input is 32x32 after caller-side resizing, not native 28x28 MNIST; drawing 28x28 would invalidate the fixed 400-feature classifier.",
            "Softmax is a real forward operator in this notebook and the logits branch is retained; it is not merely explanatory decoration.",
        ],
        symbols={SOURCE: ["LeNet5", "LeNet5.__init__", "LeNet5.forward", "compute_accuracy"]},
        legend=["B: batch; image tensors use [B,C,H,W]", "Conv blue / pool pale green / Linear purple / Softmax green",
                "input pink / return purple / Tanh gray",
                "same color = same operator family; different parameter paths = separate weights",
                "both return branches are computed from the same logits; all main chains flow bottom to top"],
        config_files=[SOURCE],
    )
