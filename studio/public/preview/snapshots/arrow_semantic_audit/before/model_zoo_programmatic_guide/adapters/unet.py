"""Reviewed brain-segmentation U-Net; skip edges remain explicit in all views."""
from spec import chain, op, ref

MODEL = "brain-segmentation-pytorch/unet.py"
TRAIN = "brain-segmentation-pytorch/train.py"


def build():
    def r(symbol):
        return ref(MODEL, symbol)

    roles, fill, edges = {}, [], []

    def block(prefix, name, cin, cout, spatial, expand=2):
        items = []
        ordered_name = name.replace("encoder", "enc").replace("decoder", "dec")
        for j in (1, 2):
            inp = cin if j == 1 else cout
            items.extend([
                op(prefix + "_conv%d" % j, "Conv 3x3: %d -> %d" % (inp, cout), "conv", r("UNet._block"),
                   "[B,%d,%d,%d]" % (cout, spatial, spatial),
                   ["padding=1; stride=1; bias=False"], param_identity=name + "." + ordered_name + "conv%d" % j),
                op(prefix + "_bn%d" % j, "BatchNorm %d" % cout, "norm", r("UNet._block"),
                   "[B,%d,%d,%d]" % (cout, spatial, spatial),
                   param_identity=name + "." + ordered_name + "norm%d" % j),
                op(prefix + "_relu%d" % j, "ReLU", "activation", r("UNet._block"),
                   "[B,%d,%d,%d]" % (cout, spatial, spatial), ["inplace=True"]),
            ])
        roles[prefix] = "conv"; fill.append(prefix)
        return chain(prefix, "Double Conv + BN + ReLU", items, r("UNet._block"),
                     "[B,%d,%d,%d]" % (cout, spatial, spatial),
                     ["Two independently parameterized Conv-BN-ReLU sequences", "Same padding; no crop"],
                     expand=expand, param_identity=name)

    tree_items = [op("unet_input", "Input image / MRI channels", "input", r("UNet.forward"), "[B,3,256,256]")]
    for i in range(1, 5):
        cin = 3 if i == 1 else 32 * 2 ** (i - 2)
        cout, spatial = 32 * 2 ** (i - 1), 256 // 2 ** (i - 1)
        p = "unet_enc%d" % i
        # The skip leaves this block BEFORE its following MaxPool.
        enc = chain(p, "Encoder %d / retained skip" % i,
            [block(p + "_block", "encoder%d" % i, cin, cout, spatial, expand=2 if i == 1 else 3)],
            [r("UNet.__init__"), r("UNet.forward"), r("UNet._block")],
            "enc%d: [B,%d,%d,%d]" % (i, cout, spatial, spatial),
            ["Skip operand is the block output, before MaxPool"], expand=1,
            param_identity="encoder%d" % i, output_ports=["out", "skip"])
        tree_items.extend([enc,
            op("unet_pool%d" % i, "MaxPool %d: 2x2 / 2" % i, "pool",
               [r("UNet.__init__"), r("UNet.forward")],
               "[B,%d,%d,%d]" % (cout, spatial // 2, spatial // 2), ["No learned parameters"]),
        ])
        roles[p] = "encoder"; fill.extend([p, "unet_pool%d" % i])
    tree_items.append(chain("unet_bottleneck", "Bottleneck / lowest resolution",
        [block("unet_bottleneck_block", "bottleneck", 256, 512, 16, expand=2)],
        [r("UNet.__init__"), r("UNet.forward"), r("UNet._block")],
        "[B,512,16,16]", expand=1, param_identity="bottleneck"))
    roles["unet_bottleneck"] = "group"; fill.append("unet_bottleneck")
    for i in (4, 3, 2, 1):
        cout, spatial = 32 * 2 ** (i - 1), 256 // 2 ** (i - 1)
        p = "unet_dec%d" % i
        dec = chain(p, "Decoder %d / upsample + skip fusion" % i, [
            op(p + "_upconv", "ConvTranspose 2x2 / 2", "conv",
               [r("UNet.__init__"), r("UNet.forward")],
               "[B,%d,%d,%d]" % (cout, spatial, spatial),
               ["Learned transposed convolution: %d -> %d channels" % (cout * 2, cout)],
               param_identity="upconv%d" % i),
            op(p + "_cat", "Concat upsampled + encoder skip", "concat", r("UNet.forward"),
               "[B,%d,%d,%d]" % (cout * 2, spatial, spatial),
               ["torch.cat((dec%d,enc%d),dim=1)" % (i, i), "Two equally sized spatial operands; no crop"],
               input_ports=["in", "side"]),
            block(p + "_block", "decoder%d" % i, cout * 2, cout, spatial, expand=2 if i == 1 else 3),
        ], [r("UNet.__init__"), r("UNet.forward")], "[B,%d,%d,%d]" % (cout, spatial, spatial),
            ["Upsampling halves channels; concatenation doubles them before the double-conv block"],
            expand=1, param_identity="decoder%d" % i)
        tree_items.append(dec)
        edges.append(dict(src="unet_enc%d" % i, dst=p + "_cat", role="skip_concat",
                          label="enc%d: %d channels" % (i, cout), src_port="skip", dst_port="side"))
        roles[p] = "decoder"; roles[p + "_cat"] = "concat"; fill.append(p)
    tree_items.extend([
        chain("unet_head", "Pixel-wise segmentation head", [
            op("unet_head_conv", "Conv 1x1: 32 -> 1", "conv",
               [r("UNet.__init__"), r("UNet.forward")], "[B,1,256,256]",
               ["Default bias=True"], param_identity="conv"),
            op("unet_sigmoid", "Sigmoid per pixel", "activation", r("UNet.forward"), "[B,1,256,256]",
               ["Independent binary foreground probability; not class-axis Softmax"]),
        ], r("UNet.forward"), "[B,1,256,256]", expand=2),
        op("unet_output", "Foreground probability mask", "output", r("UNet.forward"), "[B,1,256,256]"),
    ])
    roles.update(unet="root", unet_head="ffn", unet_sigmoid="softmax")
    fill.append("unet_head")
    tree = chain("unet", "U-Net / brain segmentation", tree_items, r("UNet.forward"),
                 "[B,3,256,256] -> [B,1,256,256]", expand=0)
    return dict(
        key="unet", name="U-Net", source_project="brain-segmentation-pytorch", entry=r("UNet"),
        profile=dict(in_channels=3, out_channels=1, init_features=32, image_size=256, batch_size=16,
                     source_defaults="UNet.__init__ and train argparse image-size", mode="evaluation",
                     spatial_assumption="H and W divisible by 16", symbolic_shapes=True, model_executed=False),
        profile_label="3 input channels / 1 foreground mask / features=32 / 256x256",
        tree=tree, aux_inputs=[], extra_edges=edges, visual_roles=roles, fill_width=fill,
        facts=[
            "UNet constructor defaults are in_channels=3,out_channels=1,init_features=32; train image-size defaults to 256.",
            "Encoder widths are 32,64,128,256; the bottleneck width is 512. Four MaxPool2d(2,2) steps reduce 256 to 16.",
            "Every _block is Conv3x3->BatchNorm2d->ReLU->Conv3x3->BatchNorm2d->ReLU, with padding=1 and bias=False.",
            "Each decoder uses learned ConvTranspose2d(kernel=2,stride=2), channel cat with the matching pre-pool encoder output, then _block.",
            "Skip sources are enc1..enc4 outputs before pooling; they concatenate along channels and are never residual additions.",
            "UNet.forward returns torch.sigmoid(self.conv(dec1)); the default 1x1 output convolution maps 32 to 1.",
            "No resizing, interpolation or center-cropping appears in forward; the selected 256x256 input keeps cat spatial sizes compatible.",
            "Separate encoder/decoder _block calls instantiate distinct parameters; same glyph type does not imply parameter sharing.",
            "Three representative double-conv blocks expand in the detailed view; all nine blocks retain their six operations in semantic IR.",
        ],
        corrections=[
            "Follow this repository's BN-equipped same-padding U-Net, rather than the original paper's valid-convolution/crop variant.",
            "Draw ConvTranspose2d rather than interpolation or a generic upsample operator.",
            "Draw channel Concat rather than Add for all four long skip connections; route from the output before MaxPool.",
            "Use Sigmoid per pixel rather than Softmax; default output has a single foreground channel.",
            "Do not infer RGB semantics from in_channels=3: the selected repository targets MRI segmentation.",
        ],
        symbols={MODEL: ["UNet", "UNet.__init__", "UNet.forward", "UNet._block"],
                 TRAIN: ["main", "datasets"]},
        config_files=[TRAIN],
        legend=["B batch", "C channels", "H,W spatial axes", "Example H=W=256 (multiples of 16)",
                "Skip: pre-pool encoder output", "Concat joins channel operands; no Add", "Repeated glyphs have distinct parameter scopes"],
    )
