"""Reviewed standalone channel_shuffle function, not a ShuffleNet model."""
from module_adapters.support import chain, op, parallel, graph, ref, finish

SOURCE = "torchvision-v0.9.0-modules/torchvision/models/shufflenetv2.py"
GROUPS, CHANNELS, HEIGHT, WIDTH = 2, 24, 8, 8
CHANNELS_PER_GROUP = CHANNELS // GROUPS
PERMUTATION = [(i % GROUPS) * CHANNELS_PER_GROUP + i // GROUPS for i in range(CHANNELS)]


def build():
    source = ref(SOURCE,"channel_shuffle")
    axis_swap = chain("shuffle.axis_swap", "Transpose\n+ contiguous", [
        op("shuffle.transpose", "Transpose axes 1 and 2", "transpose", source,
           "[B,12,2,8,8]", width=330, learnable=False, dims=[1,2],
           expression="torch.transpose(x,1,2)", source_operation="torch.transpose",
           storage_effect="strided view; channels_per_group and groups axes exchanged"),
        op("shuffle.contiguous", "Contiguous memory layout", "contiguous", source,
           "[B,12,2,8,8]", width=330, learnable=False,
           expression="x.contiguous()", source_operation="Tensor.contiguous",
           storage_effect="materialize contiguous order when required; values and shape preserved"),
    ], source, "2 x 12 -> 12 x 2 axes",
        ["Two literal operations; contiguous prepares final view"], expand=2,
        learnable=False)
    module = chain("shuffle.module", "Shuffle\ngroups=2", [
        op("shuffle.group_view", "View C as groups x C/G", "view", source,
           "[B,2,12,8,8]", width=330, learnable=False,
           expression="x.view(batchsize,groups,channels_per_group,height,width)",
           source_operation="Tensor.view", groups=2, channels_per_group=12,
           target_shape=["B",2,12,8,8], axis_meaning=["batch","groups","channels_per_group","height","width"]),
        axis_swap,
        op("shuffle.flatten_view", "View group axes as channels", "view", source,
           "[B,24,8,8]", width=330, learnable=False,
           expression="x.view(batchsize,-1,height,width)", source_operation="Tensor.view",
           target_shape=["B",-1,8,8], inferred_channels=24, flattened_axes=[1,2]),
    ], source, "[B,24,8,8] -> [B,24,8,8]",
        ["Function only; tensor permutation without learned parameters"], expand=1,
        learnable=False, groups=2, channels_per_group=12,
        instance_identity="channel_shuffle_call_1", source_function="channel_shuffle")
    tree = chain("shuffle.root", "Channel shuffle", [
        op("shuffle.input", "Input x / contiguous", "input", source, "[B,24,8,8]",
           width=330, learnable=False, origin="declared_module_profile", contiguous=True),
        module,
        op("shuffle.output", "Shuffled output", "output", source, "[B,24,8,8]",
           width=330, learnable=False),
    ], source, "Function module", expand=0)
    return finish(dict(
        key="channel_shuffle", name="Channel shuffle / tensor permutation", doc="ChannelShuffle.md",
        source_project="torchvision-v0.9.0-modules", entry=source,
        module_scope="channel_shuffle function only",
        profile=dict(task="module channel permutation", groups=GROUPS, num_channels=CHANNELS,
                     channels_per_group=CHANNELS_PER_GROUP,
                     input_shape=["B",CHANNELS,HEIGHT,WIDTH], output_shape=["B",CHANNELS,HEIGHT,WIDTH],
                     grouped_shape=["B",2,12,8,8], transposed_shape=["B",12,2,8,8],
                     input_contiguity="contiguous declared input; first view must be compatible",
                     mode="mode-independent function; not executed", learned_parameter_count=0,
                     permutation_output_to_input=PERMUTATION,
                     permutation_origin="static derivation from view/transpose/view; not an additional source operator",
                     shape_origin="declared representative module input, not runtime observation",
                     symbolic_shapes=True),
        profile_label="Function / groups=2 / C=24 / H=W=8 / no learned parameters",
        tree=tree,
        visual_roles={"shuffle.root":"root","shuffle.input":"input","shuffle.module":"encoder",
                      "shuffle.axis_swap":"inner","shuffle.group_view":"tensor",
                      "shuffle.transpose":"tensor","shuffle.contiguous":"control",
                      "shuffle.flatten_view":"tensor","shuffle.output":"output"},
        fill_width=["shuffle.module","shuffle.axis_swap","shuffle.group_view",
                    "shuffle.flatten_view","shuffle.transpose","shuffle.contiguous"],
        color_legend=[("input","Input"),("tensor","View / Transpose"),
                      ("control","Contiguous"),("output","Output")],
        facts=[
            "This artifact contains one channel_shuffle(x,groups) call and excludes ShuffleNetV2/InvertedResidual convolutions and branch splitting.",
            "The declared example uses contiguous[B,24,8,8] input,groups2,channels_per_group=24//2=12; C must be divisible by groups.",
            "The function reads x.size() metadata and computes channels_per_group; these are configuration/shape arithmetic, not new learned feature nodes.",
            "The literal tensor operation order is view(B,2,12,8,8),transpose(1,2),contiguous(),view(B,-1,8,8).",
            "Transpose swaps group and within-group axes to[B,12,2,8,8]; it does not swap height/width or mix pixels.",
            "contiguous preserves logical values and shape and provides the storage order required by the following view.",
            "Output has the same[B,24,8,8] shape; output channel o reads input(o%2)*12+o//2 at the same spatial coordinate.",
            "The static permutation is0,12,1,13,...,11,23; this explanatory mapping is not a separate gather/index_select call in the source.",
            "All operations are nonparameterized; train/eval mode does not change this function's transformation.",
        ],
        corrections=[
            "Do not draw grouped/depthwise convolutions, branch concat, BatchNorm or a classifier around this isolated function.",
            "The final shape matches the input, but channel values are reordered; equal shapes do not mean an identity operation.",
            "Keep contiguous between transpose and final view; transpose alone generally leaves a noncontiguous tensor.",
            "groups2 reshapes24 channels into2x12 before swapping to12x2; it is not a12-group example.",
            "A channel-index mapping is a static explanation; the source contains no explicit permutation matrix or gather operator.",
        ],
        symbols={SOURCE:["channel_shuffle"]}, config_files=[SOURCE],
        legend=["B batch; [B,C,H,W]; declared C=24,H=W=8; groups=2",
                "Blue = tensor axes; gray = contiguous materialization",
                "Channel order after shuffle: 0,12,1,13,...,11,23 (derived explanation)",
                "No learned parameters; spatial coordinates and output shape are preserved"],
    ))


def validate_ir(ir):
    nodes = {node["id"]:node for node in ir["nodes"]}
    profile, edges, checks = ir["profile"], ir["edges"], []
    def check(condition, label):
        if not condition:raise ValueError("ChannelShuffle: " + label)
        checks.append(label)
    def has(a,b,role="tensor"):
        return any(e["src"]==a and e["dst"]==b and e["role"]==role for e in edges)
    check(ir.get("artifact_scope")==profile.get("artifact_scope")=="module"
          and profile["model_executed"] is False, "explicit nonexecuted function/module scope")
    check(profile["groups"]==2 and profile["num_channels"]==24 and profile["channels_per_group"]==12
          and profile["input_shape"]==profile["output_shape"]==["B",24,8,8],
          "declared two-group24-channel8x8 input/output")
    check(has("shuffle.input","shuffle.module") and has("shuffle.module","shuffle.output")
          and all(nodes[n]["parent"]=="shuffle.root" for n in ["shuffle.input","shuffle.module","shuffle.output"]),
          "root input -> single function -> output")
    first,transpose,contiguous,last = [nodes[n] for n in
        ["shuffle.group_view","shuffle.transpose","shuffle.contiguous","shuffle.flatten_view"]]
    check(first["kind"]=="view" and first["groups"]==2 and first["channels_per_group"]==12
          and first["target_shape"]==["B",2,12,8,8] and first["shape"]=="[B,2,12,8,8]",
          "first view splits channel axis into group and within-group axes")
    check(transpose["kind"]=="transpose" and transpose["dims"]==[1,2]
          and transpose["shape"]=="[B,12,2,8,8]", "transpose1,2 exchanges group axes only")
    check(contiguous["kind"]=="contiguous" and contiguous["shape"]==transpose["shape"]
          and contiguous["source_operation"]=="Tensor.contiguous",
          "contiguous materialization preserves transposed logical shape")
    check(last["kind"]=="view" and last["target_shape"]==["B",-1,8,8]
          and last["inferred_channels"]==24 and last["flattened_axes"]==[1,2]
          and last["shape"]=="[B,24,8,8]", "last view flattens swapped group axes to24 channels")
    check(has("shuffle.module","shuffle.group_view","boundary")
          and has("shuffle.group_view","shuffle.axis_swap")
          and has("shuffle.axis_swap","shuffle.transpose","boundary")
          and has("shuffle.transpose","shuffle.contiguous")
          and has("shuffle.contiguous","shuffle.axis_swap","boundary")
          and has("shuffle.axis_swap","shuffle.flatten_view")
          and has("shuffle.flatten_view","shuffle.module","boundary"),
          "exact view -> transpose -> contiguous -> view tensor flow")
    check(profile["grouped_shape"]==["B",2,12,8,8]
          and profile["transposed_shape"]==["B",12,2,8,8]
          and profile["permutation_output_to_input"]==PERMUTATION
          and sorted(profile["permutation_output_to_input"])==list(range(24)),
          "derived output-to-input channel map is a24-channel bijection")
    check(set(nodes)=={"shuffle.root","shuffle.input","shuffle.module","shuffle.group_view",
                      "shuffle.axis_swap","shuffle.transpose","shuffle.contiguous",
                      "shuffle.flatten_view","shuffle.output"},
          "function scope contains no surrounding ShuffleNet operations or invented gather")
    check(profile["learned_parameter_count"]==0
          and all(n.get("learnable",False) is False and not n.get("parameter") for n in nodes.values()),
          "all nodes are nonparameterized; no learned weight identities")
    check(nodes["shuffle.input"]["contiguous"] is True
          and profile["input_contiguity"].startswith("contiguous"), "declared input satisfies first view storage assumption")
    return checks
