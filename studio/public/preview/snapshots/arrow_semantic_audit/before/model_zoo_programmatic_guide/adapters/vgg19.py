"""Reviewed VGG19-type CIFAR-10 notebook with a stale VGG16 class name."""
from spec import chain, op, parallel, ref


SOURCE = "deeplearning-models-batch4/pytorch_ipynb/cnn/cnn-vgg19.py"
DEPTHS = [2, 2, 4, 4, 4]
WIDTHS = [64, 128, 256, 512, 512]


def build():
    init = ref(SOURCE, "VGG16.__init__")
    forward = ref(SOURCE, "VGG16.forward")
    roles, fill, blocks = {}, [], []
    cin, side = 3, 32
    for i, (depth, cout) in enumerate(zip(DEPTHS, WIDTHS), 1):
        prefix = "v19.block%d" % i
        items = []
        for j in range(depth):
            idx = j * 2
            items.extend([
                op(prefix + ".conv%d" % (j + 1), "Conv2d %d -> %d" % (cin if j == 0 else cout, cout),
                   "conv2d", [init, forward], "[B,%d,%d,%d]" % (cout, side, side),
                   ["kernel=3; stride=1; padding=1; default bias=True"],
                   parameter="block_%d.%d" % (i, idx), kernel_size=3, stride=1, padding=1,
                   in_channels=cin if j == 0 else cout, out_channels=cout),
                op(prefix + ".relu%d" % (j + 1), "ReLU", "relu", [init, forward],
                   "[B,%d,%d,%d]" % (cout, side, side), ["default inplace=False"]),
            ])
            roles[prefix + ".conv%d" % (j + 1)] = "conv"
            roles[prefix + ".relu%d" % (j + 1)] = "activation"
        items.append(op(prefix + ".pool", "MaxPool2d 2x2 / 2", "max_pool2d", [init, forward],
                        "[B,%d,%d,%d]" % (cout, side // 2, side // 2),
                        ["block_%d.%d; no padding" % (i, depth * 2)], kernel_size=2, stride=2))
        roles[prefix] = "encoder"; roles[prefix + ".pool"] = "pool"; fill.append(prefix)
        blocks.append(chain(prefix, "Block %d · %d Conv/ReLU pairs" % (i, depth), items,
                            [init, forward], "[B,%d,%d,%d]" % (cout, side // 2, side // 2),
                            ["actual nn.Sequential block_%d; distinct weights" % i],
                            expand=2 if i in (1, 3) else 3, parameter_scope="block_%d" % i,
                            conv_count=depth))
        cin, side = cout, side // 2
    features = chain("v19.features", "Five convolutional blocks", blocks, [init, forward],
                     "[B,512,1,1]", ["16 independent Conv2d layers; 5 MaxPool steps"], expand=1)
    head_items = []
    for i, (fin, fout, idx) in enumerate([(512, 4096, 0), (4096, 4096, 2)], 1):
        p = "v19.hidden%d" % i
        head_items.append(chain(p, "Linear / ReLU · %d" % i, [
            op(p + ".linear", "Linear %d -> %d" % (fin, fout), "linear", [init, forward],
               "[B,%d]" % fout, parameter="classifier.%d" % idx),
            op(p + ".relu", "ReLU", "relu", [init, forward], "[B,%d]" % fout,
               ["inplace=True; no Dropout module in the source"]),
        ], [init, forward], "[B,%d]" % fout, expand=2))
        roles.update({p: "ffn", p + ".linear": "linear", p + ".relu": "activation"});fill.append(p)
    head_items.append(op("v19.fc3", "Linear 4096 -> 10", "linear", [init, forward],
                         "logits: [B,10]", parameter="classifier.4"))
    classifier = chain("v19.classifier", "Classifier head", head_items, [init, forward],
                       "logits: [B,10]", ["no Dropout and no BatchNorm in this implementation"], expand=1)
    returns = parallel("v19.returns", "Return logits / probabilities", [
        op("v19.logits", "Retain logits", "identity", forward, "[B,10]", ["raw classifier output"]),
        op("v19.softmax", "Softmax", "softmax", forward, "[B,10]", ["F.softmax(logits,dim=1)"]),
    ], forward, "(logits, probas)", ["same logits fan out to two actual return fields"], expand=1, dispatch=False)
    tree = chain("v19.root", "VGG19-type · CIFAR-10", [
        op("v19.input", "CIFAR-10 image", "input", forward, "[B,3,32,32]",
           ["actual Dataset is CIFAR10; nearby MNIST header is stale", "ToTensor in caller; no resizing"]),
        features,
        op("v19.flatten", "Flatten features", "tensor", forward, "[B,512]",
           ["x.view(-1,512); fixed 32x32 profile gives one row per example", "hard-coded view width512; no avgpool is constructed"],
           expression="x.view(-1, 512)", batch_preservation="only for the selected final1x1 profile"),
        classifier, returns,
        op("v19.output", "Forward return tuple", "output", forward, "2 x [B,10]",
           ["return logits, probas"]),
    ], ref(SOURCE, "VGG16"), "2 x [B,10]", expand=0)
    roles.update({"v19.root": "root", "v19.features": "encoder", "v19.input": "input",
                  "v19.flatten": "tensor", "v19.classifier": "ffn", "v19.fc3": "linear",
                  "v19.returns": "group", "v19.logits": "tensor", "v19.softmax": "softmax", "v19.output": "output"})
    return dict(
        key="vgg19", name="VGG19-type (source class VGG16)", source_project="deeplearning-models-batch4",
        entry=ref(SOURCE, "VGG16"),
        profile=dict(task="CIFAR-10 classification", mode="eval", input_channels=3, input_size=[32, 32],
                     num_classes=10, supplied_num_features=784, num_features_argument_used=False, source_class="VGG16", actual_convolution_depth=16,
                     flatten_expression="x.view(-1, 512)", weight_initialization="normal_(0, 0.05)",
                     block_conv_counts=DEPTHS, block_channels=WIDTHS, block_spatial=[16, 8, 4, 2, 1],
                     conv_bias=True, conv_kernel=3, conv_padding=1, classifier=[512, 4096, 4096, 10],
                     batch_size_setting=128, dropout_constructed=False, batchnorm_constructed=False,
                     avgpool_constructed=False, avgpool_called=False, output="(logits, probas)",
                     config_source=SOURCE + " notebook cells 8, 10, 12"),
        profile_label="CIFAR-10 32x32 · Conv[2,2,4,4,4] · source class=VGG16 · eval",
        tree=tree, aux_inputs=[], extra_edges=[], visual_roles=roles,
        fill_width=fill + ["v19.features", "v19.flatten", "v19.classifier", "v19.returns"],
        facts=[
            "The source class is still named VGG16, but16 Conv plus3 Linear with [2,2,4,4,4] blocks forms VGG19-type; keep the real class symbol.",
            "Flatten uses x.view(-1,512), not a batch-preserving expression: it keeps B only for the selected32x32 profile.",
            "Conv/Linear weights use normal_(0,0.05) and zero biases rather than the previous VGG16 notebook initialization.",
            "The actual dataset is CIFAR10 with ToTensor and no resize; the MNIST comment and num_features=784 do not define input shape.",
            "VGG16 accepts num_features but never uses it in __init__; selected input is3-channel32x32, and num_classes=10 controls the final Linear.",
            "Five actual Sequential blocks contain2,2,4,4,4 independent Conv-ReLU pairs and one MaxPool2d(2,2) each.",
            "All16 Conv2d layers use kernel3,stride1,padding1,bias=True; spatial sizes after pools are16,8,4,2,1.",
            "Flatten receives [B,512,1,1] and outputs512 values; classifier is Linear512->4096->4096->10 with two ReLUs.",
            "No Dropout, BatchNorm or adaptive avgpool is constructed in this notebook.",
            "Feature-block ReLUs use default inplace=False; classifier ReLUs are explicitly inplace=True.",
            "forward computes Softmax(dim=1) and returns logits and probabilities; loss uses logits outside forward.",
            "All16 convolution and3 Linear modules have distinct parameters; blocks1 and3 expand as representative2- and4-convolution structures.",
        ],
        corrections=[
            "Do not infer13 convolution layers from stale class name VGG16 or invent a VGG19 source class. Actual block depths are2,2,4,4,4.",
            "Retain x.view(-1,512): larger inputs can alter the effective batch row count; arbitrary input sizes are not supported by merely changing labels.",
            "Draw CIFAR-10 rather than the stale MNIST section label; unused num_features=784 is not a flatten width.",
            "Do not copy ImageNet224x224 shapes, a512*7*7 classifier input or an AdaptiveAvgPool7x7 into this implementation.",
            "Do not add standard VGG Dropout/AvgPool or introduce VGG-BN normalization absent from this implementation.",
            "Retain all16 convolution parameter identities even when same-family blocks are folded.",
            "Softmax is a real forward output here, not an unused local variable as in the grouped AlexNet notebook.",
        ],
        symbols={SOURCE: ["VGG16", "VGG16.__init__", "VGG16.forward", "compute_accuracy", "compute_epoch_loss"]},
        config_files=[SOURCE],
        legend=["B batch; [B,C,H,W]; 32 ->16 ->8 ->4 ->2 ->1 spatial sizes",
                "input pink / Conv blue / Linear and return purple / ReLU gray / pooling pale green / Softmax green",
                "blocks1/3 expand representative2/4 Conv patterns; all parameter identities remain in IR",
                "source class name is VGG16; equal colors do not share weights"],
    )


def validate_ir(ir):
    """Selected-profile semantic guards, independent of visual folding."""
    nodes={n["id"]:n for n in ir["nodes"]};edges=ir["edges"];p=ir["profile"];checked=[]
    def check(value,label):
        if not value:raise ValueError("vgg19: "+label)
        checked.append(label)
    def has(src,dst,role=None):
        return any(e["src"]==src and e["dst"]==dst and (role is None or e["role"]==role) for e in edges)
    check(p["input_size"]==[32,32] and p["input_channels"]==3 and p["task"]=="CIFAR-10 classification", "actual CIFAR10 input, not stale MNIST annotation")
    check(p["num_features_argument_used"] is False and p["supplied_num_features"]==784, "unused constructor num_features is not classifier width")
    check(p["source_class"]=="VGG16" and p["actual_convolution_depth"]==16, "real VGG16 symbol describes19-layer architecture")
    check(p["flatten_expression"]=="x.view(-1, 512)" and p["weight_initialization"]=="normal_(0, 0.05)", "source hardcoded flatten and initialization retained")
    check(p["block_conv_counts"]==DEPTHS and p["block_channels"]==WIDTHS, "five source blocks with16 Conv layers")
    convs=[n for n in nodes.values() if n["kind"]=="conv2d"]
    check(len(convs)==16 and len({n["parameter"] for n in convs})==16, "16 separately parameterized convolutions")
    for i,(depth,cout,side) in enumerate(zip(DEPTHS,WIDTHS,[16,8,4,2,1]),1):
        prefix="v19.block%d"%i
        check(nodes[prefix]["conv_count"]==depth and nodes[prefix]["shape"]=="[B,%d,%d,%d]"%(cout,side,side), "block%d depth and output shape"%i)
        check(has(prefix+".relu%d"%depth,prefix+".pool") and nodes[prefix+".pool"]["stride"]==2, "block%d final ReLU then MaxPool"%i)
    check(nodes["v19.flatten"]["shape"]=="[B,512]" and nodes["v19.flatten"]["expression"]=="x.view(-1, 512)" and nodes["v19.hidden1.linear"]["parameter"]=="classifier.0" and "512 -> 4096" in nodes["v19.hidden1.linear"]["label"], "512-value hardcoded flatten feeds classifier")
    check(not any(n["kind"] in ("dropout","batch_norm2d","adaptive_avg_pool2d") for n in nodes.values()) and not p["dropout_constructed"] and not p["avgpool_called"], "no invented Dropout/avgpool or BatchNorm")
    check(has("v19.returns","v19.logits","fork") and has("v19.returns","v19.softmax","fork"), "same logits fork to both returned fields")
    return checked
