"""Notebook-selected MobileNetV2 backed by the exact torchvision v0.9.0 implementation."""
from spec import chain, op, ref


CALLER = "deeplearning-models-batch2/pytorch_ipynb/cnn/cnn-mobilenet-v2-cifar10.py"
MODEL = "torchvision-v0.9.0/torchvision/models/mobilenetv2.py"
SETTINGS = [[1, 16, 1, 1], [6, 24, 2, 2], [6, 32, 3, 2],
            [6, 64, 4, 2], [6, 96, 3, 1], [6, 160, 3, 2], [6, 320, 1, 1]]


def build():
    init = ref(MODEL, "MobileNetV2.__init__")
    forward = ref(MODEL, "MobileNetV2._forward_impl")
    block_init = ref(MODEL, "InvertedResidual.__init__")
    block_forward = ref(MODEL, "InvertedResidual.forward")
    cba = ref(MODEL, "ConvBNActivation.__init__")
    roles, fill = {}, []

    def conv_bn_relu(prefix, label, cin, cout, kernel, stride, groups, size, scope, expand=2):
        shape = "[B,%d,%d,%d]" % (cout, size, size)
        owner = block_init if ".conv." in scope else init
        roles.update({prefix: "conv", prefix + ".conv": "conv", prefix + ".bn": "norm",
                      prefix + ".relu6": "activation"})
        return chain(prefix, label, [
            op(prefix + ".conv", "Conv2d %dx%d" % (kernel, kernel), "conv2d", [cba, owner], shape,
               ["%d -> %d channels; stride=%d; groups=%d" % (cin, cout, stride, groups),
                "padding=%d; bias=False" % ((kernel - 1) // 2)],
               parameter=scope + ".0", groups=groups),
            op(prefix + ".bn", "BatchNorm2d", "batch_norm2d", cba, shape,
               ["selected eval: running statistics; affine=True"], parameter=scope + ".1"),
            op(prefix + ".relu6", "ReLU6", "relu6", cba, shape, ["inplace=True; clips at 6"]),
        ], [cba, owner], shape, expand=expand)

    def expanded_block(prefix, cin, cout, stride, t, input_size, output_size, feature_index,
                       count=1, indices=None):
        hidden = cin * t
        scope = "features.%d.conv" % feature_index if count == 1 else "features.{j}.conv"
        items = []
        if t != 1:
            items.append(conv_bn_relu(prefix + ".expand", "Pointwise expansion", cin, hidden,
                                      1, 1, 1, input_size, scope + ".0"))
        depth_index = 1 if t != 1 else 0
        proj_index = depth_index + 1
        items.append(conv_bn_relu(prefix + ".depthwise", "Depthwise spatial convolution", hidden, hidden,
                                  3, stride, hidden, output_size, scope + ".%d" % depth_index))
        shape = "[B,%d,%d,%d]" % (cout, output_size, output_size)
        items.extend([
            op(prefix + ".project", "Linear bottleneck Conv1x1", "conv2d", block_init, shape,
               ["%d -> %d channels; stride=1; bias=False" % (hidden, cout),
                "linear means no following ReLU6, not nn.Linear"], parameter=scope + ".%d" % proj_index),
            op(prefix + ".project_bn", "BatchNorm2d", "batch_norm2d", block_init, shape,
               ["no activation after this BN"], parameter=scope + ".%d" % (proj_index + 1)),
        ])
        residual = stride == 1 and cin == cout
        if residual:
            items.append(op(prefix + ".add", "Add identity shortcut", "add", block_forward, shape,
                            ["return x + self.conv(x); no activation after Add"]))
            roles[prefix + ".add"] = "norm"
        roles.update({prefix: "conv", prefix + ".project": "linear", prefix + ".project_bn": "norm"})
        fill.append(prefix)
        kw = dict(residual=residual, parameter_scope=scope,
                  expand_ratio=t, hidden_channels=hidden, stride=stride,
                  use_res_connect=residual, feature_indices=indices or [feature_index])
        if count > 1:
            kw["repeat"] = dict(count=count, index="j", independent_parameters=True,
                                 instance_indices=indices, template=prefix)
        return chain(prefix, ("Identity IR block" + (" x %d" % count if count > 1 else "") if residual else "IR block · no skip"),
                     items, [block_init, block_forward, init], shape,
                     ["t=%d; hidden=%d; input channels=%d" % (t, hidden, cin),
                      "identity only when stride=1 and input channels=output channels",
                      "separate weights for each feature index"], expand=2, **kw)

    def folded_block(prefix, cin, cout, stride, t, output_size, feature_indices, residual):
        idx = feature_indices[0]
        scope = "features.%d.conv" % idx if len(feature_indices) == 1 else "features.{j}.conv"
        hidden = cin * t
        members = ([scope + ".0.0", scope + ".0.1"] if t != 1 else [])
        depth_index = 1 if t != 1 else 0
        members += [scope + ".%d.0" % depth_index, scope + ".%d.1" % depth_index,
                    scope + ".%d" % (depth_index + 1), scope + ".%d" % (depth_index + 2)]
        roles[prefix] = "conv"
        return op(prefix, "Identity IR block x %d" % len(feature_indices) if residual else "First IR block · no skip",
                  "inverted_residual", [block_init, block_forward, init],
                  "[B,%d,%d,%d]" % (cout, output_size, output_size),
                  ["%d -> %d channels; t=%d; hidden=%d; stride=%d" % (cin, cout, t, hidden, stride),
                   "Expand1x1-BN-ReLU6 -> depthwise3x3-BN-ReLU6 -> project1x1-BN" if t != 1 else
                   "No expansion: depthwise3x3-BN-ReLU6 -> project1x1-BN",
                   "then Add input; no post-Add activation" if residual else "no identity Add; shape/channel change",
                   "feature indices: " + ",".join(map(str, feature_indices)) + "; separate weights"],
                  parameter_scope=scope, parameter_members=members, feature_indices=feature_indices,
                  expand_ratio=t, hidden_channels=hidden, stride=stride, use_res_connect=residual,
                  repeat=dict(count=len(feature_indices), index="j", independent_parameters=True,
                              instance_indices=feature_indices))

    stem = conv_bn_relu("mobile.stem", "Stem Conv / BN / ReLU6", 3, 32, 3, 2, 1, 32, "features.0", expand=1)
    stages = []
    cin, input_size, index = 32, 32, 1
    for stage, (t, cout, n, stride) in enumerate(SETTINGS, 1):
        prefix = "mobile.stage%d" % stage
        output_size = (input_size + stride - 1) // stride
        first = expanded_block(prefix + ".first", cin, cout, stride, t, input_size, output_size, index) if stage <= 2 else \
                folded_block(prefix + ".first", cin, cout, stride, t, output_size, [index], False)
        items = [first]
        if n > 1:
            indices = list(range(index + 1, index + n))
            items.append(expanded_block(prefix + ".repeat", cout, cout, 1, t, output_size, output_size,
                                        indices[0], count=len(indices), indices=indices) if stage == 2 else
                         folded_block(prefix + ".repeat", cout, cout, 1, t, output_size, indices, True))
        stages.append(chain(prefix, "Stage %d · c=%d / n=%d" % (stage, cout, n),
                            items, [init, block_init, block_forward],
                            "[B,%d,%d,%d]" % (cout, output_size, output_size),
                            ["t=%d; first stride=%d; later blocks use stride 1" % (t, stride),
                             "logical stage from the source settings table; features is one Sequential"],
                            expand=1, feature_indices=list(range(index, index + n))))
        roles[prefix] = "encoder"; fill.append(prefix)
        cin, input_size, index = cout, output_size, index + n
    last = conv_bn_relu("mobile.last", "Final pointwise features", 320, 1280, 1, 1, 1, 2, "features.18", expand=1)
    head = chain("mobile.head", "CIFAR-10 classifier", [
        op("mobile.pool", "Adaptive average pool 1x1", "adaptive_avg_pool2d", forward,
           "[B,1280,1,1]", ["nn.functional.adaptive_avg_pool2d(x,(1,1))"]),
        op("mobile.reshape", "Reshape preserving batch", "tensor", forward,
           "[B,1280]", ["reshape(x.shape[0],-1); safe when B=1; not all-axis squeeze"]),
        op("mobile.dropout", "Dropout 0.2", "dropout", [init, forward],
           "[B,1280]", ["classifier.0; identity in selected eval mode"]),
        op("mobile.fc", "Replaced Linear 1280 -> 10", "linear", [init, forward],
           "logits: [B,10]", ["notebook replaces classifier[-1] after torch.hub.load", "replacement weight initialization follows nn.Linear default"],
           parameter="classifier.1", configuration_source=CALLER),
    ], [init, forward], "logits: [B,10]", expand=1)
    tree = chain("mobile.model", "MobileNetV2 · CIFAR-10", [
        op("mobile.input", "CIFAR-10 image", "input", forward, "[B,3,64,64]",
           ["caller Resize70 then Crop64; Normalize(mean=std=0.5)"]),
        stem, *stages, last, head,
        op("mobile.output", "Returned logits", "output", [forward, ref(MODEL, "MobileNetV2.forward")],
           "[B,10]", ["model forward has no Softmax"]),
    ], [ref(MODEL, "mobilenet_v2"), ref(MODEL, "MobileNetV2")], "logits: [B,10]", expand=0)
    roles.update({"mobile.model": "root", "mobile.input": "input", "mobile.output": "output",
                  "mobile.head": "ffn", "mobile.pool": "pool", "mobile.reshape": "tensor",
                  "mobile.dropout": "control", "mobile.fc": "linear"})
    return dict(
        key="mobilenetv2", name="MobileNetV2 (CIFAR-10)", source_project="deeplearning-models-batch2",
        source_projects=["torchvision-v0.9.0"], entry=ref(MODEL, "MobileNetV2"),
        profile=dict(task="CIFAR-10 classification", mode="eval", input_channels=3, input_size=[64, 64],
                     constructor="torch.hub.load('pytorch/vision:v0.9.0','mobilenet_v2',pretrained=False)",
                     pretrained=False, torchvision_ref="v0.9.0", width_mult=1.0, round_nearest=8,
                     inverted_residual_setting=SETTINGS, stage_channels=[16, 24, 32, 64, 96, 160, 320],
                     stage_spatial=[32, 16, 8, 4, 4, 2, 2], total_inverted_residual_blocks=17,
                     last_channel=1280, num_classes_after_replacement=10, dropout=0.2,
                     output="logits", symbolic_shapes=True, model_executed=False,
                     config_source=CALLER + " notebook cells 9, 12, 14"),
        profile_label="CIFAR-10 · Crop64 · torchvision v0.9.0 · width=1 · replaced 10-class head · eval",
        tree=tree, aux_inputs=[], extra_edges=[], visual_roles=roles,
        fill_width=fill + ["mobile.stem", "mobile.last", "mobile.head"],
        facts=[
            "The notebook pins torch.hub to pytorch/vision:v0.9.0, pretrained=False; its actual implementation is independently frozen as source.",
            "The caller crops resized CIFAR-10 to 64x64 and replaces classifier[-1] with Linear(1280,10).",
            "Default width_mult=1 and round_nearest=8 preserve the seven [t,c,n,s] settings and 17 independently constructed InvertedResidual blocks.",
            "The stem maps 3->32 with stride2; stage channels are 16,24,32,64,96,160,320 and spatial sizes are 32,16,8,4,4,2,2.",
            "Expansion uses hidden_dim=round(inp*t); t=1 stage1 omits expansion completely and depthwise-convolves 32 channels before projecting to16.",
            "Depthwise Conv2d uses groups=hidden_dim; the subsequent pointwise bottleneck is Conv2d+BN without ReLU6.",
            "Identity Add executes only when stride=1 and inp==oup. There are 10 identity additions, no learned projection shortcuts and no post-Add activation.",
            "Final Conv1x1 maps320->1280, then adaptive average pooling and batch-preserving reshape feed Dropout0.2 and the replaced Linear1280->10.",
            "Dropout is an eval identity; BatchNorm still uses running statistics; forward returns logits without Softmax.",
            "Later blocks are folded operator summaries with real feature indices and parameter members; representative t1, t6/no-skip and t6/identity blocks expand.",
        ],
        corrections=[
            "Do not infer architecture solely from the notebook's torch.hub call; bind the exact torchvision v0.9.0 source implementation.",
            "Do not copy the original ImageNet 1000-class head or 224x224 shapes into this 64x64 CIFAR-10 replacement-head profile.",
            "Depthwise grouping is an attribute of a single Conv2d, not hundreds of separately instantiated branches.",
            "Do not add a projection shortcut to changed-channel or stride2 blocks; this implementation simply omits the identity Add.",
            "The linear bottleneck is a pointwise Conv2d without activation, not an nn.Linear layer or a ReLU6 block.",
            "Do not insert Softmax in model.forward or use squeeze that removes the B=1 batch dimension.",
        ],
        symbols={MODEL: ["_make_divisible", "ConvBNActivation", "ConvBNActivation.__init__",
                         "InvertedResidual", "InvertedResidual.__init__", "InvertedResidual.forward",
                         "MobileNetV2", "MobileNetV2.__init__", "MobileNetV2._forward_impl", "MobileNetV2.forward", "mobilenet_v2"]},
        config_files=[CALLER],
        legend=["B batch; image layout [B,C,H,W]; t expansion / c output channels / n repeats / s first stride",
                "IR block: InvertedResidual; no skip for channel-changing first blocks",
                "blue Conv / yellow BN or Add / purple linear bottleneck and head / gray ReLU6",
                "repeat templates retain distinct feature indices; same operator color is not shared weights",
                "residual only for equal-channel stride1 blocks; groups=hidden dimension is depthwise convolution"],
    )
