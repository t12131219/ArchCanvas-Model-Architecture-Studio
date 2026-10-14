"""Source-reviewed ResNet18 MNIST adapter with explicit projected shortcuts."""
from spec import chain, op, parallel, ref


SOURCE = "deeplearning-models/pytorch_ipynb/cnn/cnn-resnet18-mnist.py"


def _identity_block(prefix, scope, channels, size, count=1, expand=2):
    init = ref(SOURCE, "BasicBlock.__init__")
    forward = ref(SOURCE, "BasicBlock.forward")
    make_layer = ref(SOURCE, "ResNet._make_layer")
    shape = "[B,%d,%d,%d]" % (channels, size, size)
    residual = chain(prefix + ".residual", "Two convolutions + identity", [
        op(prefix + ".conv1", "Conv2d 3x3", "conv2d", [ref(SOURCE, "conv3x3"), init, forward],
           shape, ["stride=1; padding=1; bias=False"], parameter=scope + ".conv1"),
        op(prefix + ".bn1", "BatchNorm2d", "batch_norm2d", [init, forward], shape,
           ["eval: saved running statistics; affine=True"], parameter=scope + ".bn1"),
        op(prefix + ".relu1", "ReLU", "relu", forward, shape, ["inplace=True"]),
        op(prefix + ".conv2", "Conv2d 3x3", "conv2d", [ref(SOURCE, "conv3x3"), init, forward],
           shape, ["stride=1; padding=1; bias=False"], parameter=scope + ".conv2"),
        op(prefix + ".bn2", "BatchNorm2d", "batch_norm2d", [init, forward], shape,
           parameter=scope + ".bn2"),
        op(prefix + ".add", "Add identity", "add", forward, shape,
           ["out += original block input; identity has no parameters"]),
    ], forward, shape, expand=expand, residual=True)
    return chain(prefix, "Identity block" + (" x %d" % count if count > 1 else ""), [
        residual,
        op(prefix + ".relu2", "ReLU after Add", "relu", forward, shape, ["same self.relu module; no trainable parameters"]),
    ], [make_layer, init, forward], shape,
       ["two Conv / BN pairs; Add before final ReLU", "representative template; each instance owns separate Conv / BN weights"],
       expand=expand, parameter_scope=scope,
       repeat=dict(count=count, index="i", independent_parameters=True))


def _projection_block(prefix, scope, in_channels, out_channels, in_size, out_size):
    init = ref(SOURCE, "BasicBlock.__init__")
    forward = ref(SOURCE, "BasicBlock.forward")
    make_layer = ref(SOURCE, "ResNet._make_layer")
    shape = "[B,%d,%d,%d]" % (out_channels, out_size, out_size)
    main = chain(prefix + ".main", "Main convolution path", [
        op(prefix + ".conv1", "Conv2d 3x3 / stride 2", "conv2d",
           [ref(SOURCE, "conv3x3"), init, forward], shape,
           ["%d -> %d channels; padding=1; bias=False" % (in_channels, out_channels)],
           parameter=scope + ".conv1"),
        op(prefix + ".bn1", "BatchNorm2d", "batch_norm2d", [init, forward], shape,
           ["eval: running statistics"], parameter=scope + ".bn1"),
        op(prefix + ".relu1", "ReLU", "relu", forward, shape),
        op(prefix + ".conv2", "Conv2d 3x3 / stride 1", "conv2d",
           [ref(SOURCE, "conv3x3"), init, forward], shape,
           ["padding=1; bias=False"], parameter=scope + ".conv2"),
        op(prefix + ".bn2", "BatchNorm2d", "batch_norm2d", [init, forward], shape,
           parameter=scope + ".bn2"),
    ], [init, forward], shape, expand=2)
    shortcut = chain(prefix + ".shortcut", "Projection shortcut", [
        op(prefix + ".proj_conv", "Conv2d 1x1 / stride 2", "conv2d", [make_layer, forward], shape,
           ["%d -> %d channels; padding=0; bias=False" % (in_channels, out_channels)],
           parameter=scope + ".downsample.0"),
        op(prefix + ".proj_bn", "BatchNorm2d", "batch_norm2d", [make_layer, forward], shape,
           parameter=scope + ".downsample.1"),
    ], [make_layer, forward], shape, expand=2)
    paths = parallel(prefix + ".paths", "Main / projected shortcut", [main, shortcut],
                     [make_layer, forward], "(main, shortcut)",
                     ["both paths consume the same block input", "matching output shapes before arithmetic Add"],
                     expand=2, dispatch=False)
    return chain(prefix, "Downsampling block", [
        paths,
        op(prefix + ".add", "Add two paths", "add", forward, shape,
           ["main + downsample(x); fork/join above is not the arithmetic sum"]),
        op(prefix + ".relu2", "ReLU after Add", "relu", forward, shape),
    ], [make_layer, init, forward], shape,
       ["input [B,%d,%d,%d]" % (in_channels, in_size, in_size),
        "first block only; both paths reduce resolution with stride 2"],
       expand=2, parameter_scope=scope)


def _folded_identity(prefix, scope, channels, size):
    return op(prefix, "Identity block x 1", "residual_block",
              [ref(SOURCE, "ResNet._make_layer"), ref(SOURCE, "BasicBlock.__init__"), ref(SOURCE, "BasicBlock.forward")],
              "[B,%d,%d,%d]" % (channels, size, size),
              ["Conv3x3 -> BN -> ReLU -> Conv3x3 -> BN -> Add identity -> ReLU",
               "stride=1; no projection; same structure as expanded identity template",
               "separate conv1 / bn1 / conv2 / bn2 parameters at " + scope],
              parameter_scope=scope, repeat=dict(count=1, independent_parameters=True),
              parameter_members=[scope + ".conv1", scope + ".bn1", scope + ".conv2", scope + ".bn2"])


def build():
    init = ref(SOURCE, "ResNet.__init__")
    forward = ref(SOURCE, "ResNet.forward")
    stem = chain("resnet.stem", "Convolutional stem", [
        op("resnet.stem.conv", "Conv2d 1 -> 64", "conv2d", [init, forward],
           "[B,64,14,14]", ["kernel=7; stride=2; padding=3; bias=False"], parameter="conv1"),
        op("resnet.stem.bn", "BatchNorm2d", "batch_norm2d", [init, forward],
           "[B,64,14,14]", ["eval: running statistics"], parameter="bn1"),
        op("resnet.stem.relu", "ReLU", "relu", forward, "[B,64,14,14]"),
        op("resnet.stem.pool", "MaxPool2d", "max_pool2d", [init, forward],
           "[B,64,7,7]", ["kernel=3; stride=2; padding=1"]),
    ], [init, forward], "[B,64,7,7]", expand=1)
    stages = [chain("resnet.stage1", "Stage 1 · 64 channels", [
        _identity_block("resnet.stage1.identity", "layer1.{i}", 64, 7, count=2),
    ], [init, ref(SOURCE, "ResNet._make_layer"), forward], "[B,64,7,7]",
       ["2 independent BasicBlock instances: layer1.0 / layer1.1"], expand=1)]
    for stage, cin, cout, size_in, size_out in [(2, 64, 128, 7, 4), (3, 128, 256, 4, 2), (4, 256, 512, 2, 1)]:
        prefix = "resnet.stage%d" % stage
        scope = "layer%d" % stage
        stages.append(chain(prefix, "Stage %d · %d channels" % (stage, cout), [
            _projection_block(prefix + ".downsample", scope + ".0", cin, cout, size_in, size_out),
            _folded_identity(prefix + ".identity", scope + ".1", cout, size_out),
        ], [init, ref(SOURCE, "ResNet._make_layer"), forward],
            "[B,%d,%d,%d]" % (cout, size_out, size_out),
            ["first block: stride 2 and projected shortcut", "second block: stride 1 with identity shortcut"], expand=1))
    head = chain("resnet.head", "Classification head", [
        op("resnet.flatten", "Flatten", "tensor", forward,
           "[B,512]", ["x.view(x.size(0), -1); final MNIST spatial size is 1x1", "AvgPool2d exists in __init__, but its forward call is commented out"]),
        op("resnet.fc", "Linear 512 -> 10", "linear", [init, forward],
           "[B,10]", parameter="fc"),
        parallel("resnet.returns", "Return logits / probabilities", [
            op("resnet.logits", "Logits", "identity", forward, "[B,10]", ["raw fc output; consumed by cross_entropy"]),
            op("resnet.softmax", "Softmax", "softmax", forward, "[B,10]", ["F.softmax(logits, dim=1); returned as probas"]),
        ], forward, "(logits, probas)", ["same logits tensor to both branches"],
           expand=2, dispatch=False),
    ], [init, forward], "2 x [B,10]", expand=1)
    tree = chain("resnet.model", "ResNet18 · MNIST", [
        op("resnet.input", "MNIST image", "input", forward,
           "[B,1,28,28]", ["grayscale=True; native MNIST resolution"]),
        stem, *stages, head,
        op("resnet.output", "Forward return tuple", "output", forward,
           "2 x [B,10]", ["return logits, probas"]),
    ], [ref(SOURCE, "resnet18"), ref(SOURCE, "ResNet")], "2 x [B,10]", expand=0)
    roles = {}
    def visit(node):
        kind = node["kind"]
        roles[node["id"]] = dict(conv2d="conv", batch_norm2d="norm", relu="activation",
                                  max_pool2d="pool", add="norm", tensor="tensor", linear="linear",
                                  identity="tensor", softmax="softmax", input="input", output="output",
                                  residual_block="conv").get(kind, "group")
        for child in node.get("items", []):
            visit(child)
    visit(tree)
    roles.update({"resnet.model": "root", "resnet.stem": "conv", "resnet.head": "ffn"})
    roles.update({"resnet.stage%d" % i: "encoder" for i in range(1, 5)})
    for i in range(2, 5):
        roles["resnet.stage%d.downsample" % i] = "conv"
        roles["resnet.stage%d.downsample.main" % i] = "inner"
        roles["resnet.stage%d.downsample.shortcut" % i] = "inner"
    return dict(
        key="resnet", name="ResNet18", source_project="deeplearning-models",
        entry=ref(SOURCE, "ResNet"),
        profile=dict(task="MNIST classification", mode="eval", input_channels=1, input_size=[28, 28],
                     grayscale=True, num_classes=10, block="BasicBlock", block_expansion=1,
                     stage_blocks=[2, 2, 2, 2], stage_channels=[64, 128, 256, 512],
                     stage_spatial=[7, 4, 2, 1], stem_kernel=7, stem_stride=2,
                     avgpool_called=False, output="(logits, probas)",
                     config_source=SOURCE + " notebook cells 10, 15, 16"),
        profile_label="MNIST · 28x28 grayscale · [2,2,2,2] BasicBlocks · eval",
        tree=tree, aux_inputs=[], extra_edges=[], visual_roles=roles,
        fill_width=["resnet.stem", "resnet.stage1", "resnet.stage2", "resnet.stage3", "resnet.stage4", "resnet.head"],
        facts=[
            "resnet18 constructs ResNet(BasicBlock, [2,2,2,2], NUM_CLASSES=10, GRAYSCALE=True); the factory actually reads these module globals.",
            "Input [B,1,28,28] passes through 7x7 stride2 convolution to 14x14, then 3x3 stride2 MaxPool to 7x7.",
            "Stage spatial sizes are 7,4,2,1 with channels 64,128,256,512; stride2 occurs only in the first block of stages 2-4.",
            "A BasicBlock applies Conv-BN-ReLU-Conv-BN, adds the shortcut, then applies a second ReLU. It is not a pre-activation block.",
            "Stages 2-4 use independent 1x1 stride2 Conv + BN shortcuts in their first block; parallel path collection precedes a separate arithmetic Add.",
            "Each stage contains two independent parameter sets; the repeated identity template in stage1 denotes layer1.0 and layer1.1, not tied weights.",
            "AvgPool2d(7) is constructed but not called by forward; after stage4 MNIST is already 1x1, so flatten yields 512 values.",
            "BatchNorm2d is retained in the eval graph and uses running statistics; Softmax is called inside forward, which returns both logits and probas.",
        ],
        corrections=[
            "No model-specific reference PNG was supplied for this notebook; the diagram follows the reviewed code and shared Transformer visual theme.",
            "Do not copy an ImageNet ResNet diagram's 224x224 input or global average-pool path into this MNIST implementation.",
            "The 1x1 projection shortcuts are parameterized computations, not identity bypasses, and must be drawn before Add.",
            "Final ReLU follows residual addition; BatchNorm follows both convolutions, including the second convolution before Add.",
            "An attribute appearing in __init__ is not sufficient evidence for an executed operator: the unused avgpool is recorded in notes, not as a forward node.",
        ],
        symbols={SOURCE: ["conv3x3", "BasicBlock", "BasicBlock.__init__", "BasicBlock.forward",
                          "ResNet", "ResNet.__init__", "ResNet._make_layer", "ResNet.forward", "resnet18", "compute_accuracy"]},
        legend=["B: batch; image tensors use [B,C,H,W]", "blue Conv / yellow BN or Add / purple Linear / green Softmax",
                "input pink / return purple / ReLU gray",
                "repeat template = repeated structure with independent parameters; no tied block weights",
                "parallel branches consume the same x; only the explicit Add sums them; all chains flow bottom to top"],
        config_files=[SOURCE],
    )
