"""Reviewed torchvision v0.9.0 InceptionA module, not an Inception-v3 model."""
from module_adapters.support import chain, op, parallel, graph, ref, finish

SOURCE = "torchvision-v0.9.0-modules/torchvision/models/inception.py"
# Names are real attributes of one InceptionA instance, in source list order.
BRANCHES = [
    ("1x1", [("branch1x1", 192, 64, 1, 0)]),
    ("5x5", [("branch5x5_1", 192, 48, 1, 0),
             ("branch5x5_2", 48, 64, 5, 2)]),
    ("3x3dbl", [("branch3x3dbl_1", 192, 64, 1, 0),
                ("branch3x3dbl_2", 64, 96, 3, 1),
                ("branch3x3dbl_3", 96, 96, 3, 1)]),
    ("pool", [("branch_pool", 192, 32, 1, 0)]),
]
WIDTHS = [64, 64, 96, 32]


def build():
    init = ref(SOURCE, "InceptionA.__init__")
    paths = ref(SOURCE, "InceptionA._forward")
    forward = ref(SOURCE, "InceptionA.forward")
    basic_init = ref(SOURCE, "BasicConv2d.__init__")
    basic_forward = ref(SOURCE, "BasicConv2d.forward")
    roles = {"inca.root": "root", "inca.input": "input",
             "inca.module": "encoder", "inca.branches": "inner",
             "inca.concat": "concat", "inca.output": "output"}

    def basic(attribute, cin, cout, kernel, padding):
        prefix = "inca." + attribute
        evidence = [init, paths, basic_init, basic_forward]
        shape = "[B,%d,35,35]" % cout
        roles.update({prefix: "conv", prefix + ".conv": "conv",
                      prefix + ".bn": "norm", prefix + ".relu": "activation"})
        return chain(prefix, "BasicConv %dx%d" % (kernel, kernel), [
            op(prefix + ".conv", "Conv %d×%d / %d→%d" % (kernel, kernel, cin, cout),
               "conv", evidence, shape,
               ["stride=1; padding=%d; groups=1; bias=False" % padding],
               width=300, parameter=attribute + ".conv",
               instance_identity="inception_a." + attribute + ".conv", learnable=True,
               in_channels=cin, out_channels=cout, kernel_size=kernel, stride=1,
               padding=padding, dilation=1, groups=1, bias=False,
               source_operation="nn.Conv2d"),
            op(prefix + ".bn", "BatchNorm / eps=0.001", "batch_norm2d", evidence, shape,
               ["affine=True; momentum=0.1; running statistics follow caller train/eval"],
               width=300, parameter=attribute + ".bn",
               instance_identity="inception_a." + attribute + ".bn", learnable=True,
               num_features=cout, eps=0.001, momentum=0.1, affine=True,
               track_running_stats=True, source_operation="nn.BatchNorm2d"),
            op(prefix + ".relu", "ReLU / inplace=True", "relu", [paths, basic_forward], shape,
               width=300, learnable=False, inplace=True, source_operation="F.relu"),
        ], evidence, shape,
            ["One actual BasicConv2d attribute; Conv -> BatchNorm -> ReLU"],
            expand=2, width=300, parameter_scope=attribute,
            instance_identity="inception_a." + attribute,
            source_class="BasicConv2d", input_channels=cin, output_channels=cout)

    branch_nodes = []
    for index, (name, configs) in enumerate(BRANCHES):
        prefix = "inca.path_" + name
        children = []
        if name == "pool":
            children.append(op("inca.avgpool", "AvgPool 3x3 / stride=1", "pool", paths,
                               "[B,192,35,35]", width=300, learnable=False,
                               pool_type="average", kernel_size=3, stride=1, padding=1,
                               ceil_mode=False, count_include_pad=True,
                               source_operation="F.avg_pool2d"))
            roles["inca.avgpool"] = "pool"
        children.extend(basic(*config) for config in configs)
        roles[prefix] = "group"
        branch_nodes.append(chain(prefix, ["1x1 path", "1x1 -> 5x5 path",
                                         "1x1 -> 3x3 -> 3x3", "AvgPool -> 1x1 path"][index],
                                  children, [init, paths], "[B,%d,35,35]" % WIDTHS[index],
                                  ["Same x input; independent attribute parameters"],
                                  expand=1, collection_index=index,
                                  source_attributes=[config[0] for config in configs]))
    branches = parallel("inca.branches", "Four paths / ordered output list", branch_nodes,
                        [init, paths], "64 + 64 + 96 + 32 channels",
                        ["outputs is a Python list; collection is not tensor addition"],
                        expand=1, collection_type="list", literal_list=True,
                        literal_tuple=False, branch_order=[node["id"] for node in branch_nodes],
                        branch_channels=WIDTHS, input_dispatch=False)
    module = chain("inca.module", "InceptionA / four independent paths", [
        branches,
        op("inca.concat", "Concat / channel dim=1", "concat", forward,
           "[B,256,35,35]", ["torch.cat(outputs,1); ordered [1x1,5x5,3x3dbl,pool]"],
           width=330, learnable=False, dim=1, collection_type="list",
           ordered_inputs=[node["id"] for node in branch_nodes], branch_channels=WIDTHS,
           source_operation="torch.cat"),
    ], [init, paths, forward], "[B,192,35,35] -> [B,256,35,35]",
        ["Isolated InceptionA(192,pool_features=32,conv_block=None)"], expand=1,
        source_class="InceptionA", instance_identity="inception_a",
        input_channels=192, pool_features=32, output_channels=256,
        conv_block="BasicConv2d")
    tree = chain("inca.root", "InceptionA / module scope", [
        op("inca.input", "Module input x", "input", paths, "[B,192,35,35]",
           width=330, learnable=False, origin="declared_module_profile"),
        module,
        op("inca.output", "Module output", "output", forward, "[B,256,35,35]",
           width=330, learnable=False),
    ], ref(SOURCE, "InceptionA"), "One module; no backbone or classifier", expand=0)
    return finish(dict(
        key="inception_a", name="InceptionA / parallel convolution module", doc="InceptionA.md",
        source_project="torchvision-v0.9.0-modules", entry=ref(SOURCE, "InceptionA"),
        module_scope="InceptionA only",
        profile=dict(task="module feature transformation", input_shape=["B",192,35,35],
                     output_shape=["B",256,35,35], in_channels=192, pool_features=32,
                     conv_block="BasicConv2d (default)", conv_block_argument=None,
                     branch_channels=WIDTHS, concat_dim=1, basic_conv_count=7,
                     batch_norm_eps=0.001, mode="caller train/eval; not executed",
                     shape_origin="declared representative module input, not runtime observation",
                     constructor="InceptionA(192,pool_features=32)",
                     constructor_matches="Inception3.Mixed_5b; surrounding model is excluded",
                     symbolic_shapes=True),
        profile_label="Module / C=192 / pool_features=32 / H=W=35 / output C=256",
        tree=tree, visual_roles=roles, fill_width=["inca.module", "inca.concat"],
        color_legend=[("input","Input"),("conv","Conv"),("norm","BN / Concat"),
                      ("pool","AvgPool"),("activation","ReLU"),("output","Output")],
        facts=[
            "This artifact contains one InceptionA instance; no Inception-v3 stem, reductions, Aux head, or classifier is inferred.",
            "Constructor dimensions match Inception3.Mixed_5b, while 35x35 is a declared representative input rather than an observed tensor.",
            "All four branches read the same x and keep its 35x35 spatial resolution using stride1 and exact padding.",
            "The source list order is branch1x1,branch5x5,branch3x3dbl,branch_pool, with widths64,64,96,32.",
            "The seven separate BasicConv2d attributes each apply Conv2d(bias=False),BatchNorm2d(eps=.001),F.relu(inplace=True).",
            "BatchNorm defaults are affine=True,momentum=.1,track_running_stats=True; behavior follows the caller mode.",
            "The pool branch applies F.avg_pool2d(x,3,stride=1,padding=1), then BasicConv2d(192,32,1).",
            "InceptionA._forward returns a list; InceptionA.forward applies torch.cat(outputs,1), giving64+64+96+32=256 channels.",
            "Shared-engine tuple_collection edges denote ordered field collection; collection_type=list explicitly preserves the literal source list.",
            "Each attribute owns distinct Conv and BN parameters; equal colors or matching kernel sizes do not imply weight sharing.",
        ],
        corrections=[
            "Use the literal5x5 convolution in this version; do not replace it with two3x3 convolutions from a different Inception variant.",
            "The fourth path starts with average pooling, not MaxPool or an identity shortcut.",
            "The branch join is Concat along channel dim1, not Add; its output is256 channels, not192 or288.",
            "ReLU belongs after BN inside all seven BasicConv2d instances; there is no extra ReLU after Concat.",
            "The figure is a module example, not a complete Inception-v3 diagram or an executed model profile.",
        ],
        symbols={SOURCE:["InceptionA","InceptionA.__init__","InceptionA._forward",
                         "InceptionA.forward","BasicConv2d","BasicConv2d.__init__",
                         "BasicConv2d.forward","Inception3.__init__"]},
        config_files=[SOURCE],
        legend=["B batch; [B,C,H,W]; declared H=W=35", "Same x supplies four independent branches",
                "Blue Conv; yellow BN/Concat; green AvgPool; gray ReLU",
                "Branch list order: 1x1 / 5x5 / double3x3 / pool",
                "Colors express operation roles; parameters are separate attribute instances"],
    ))


def validate_ir(ir):
    nodes = {node["id"]:node for node in ir["nodes"]}
    profile, edges, checks = ir["profile"], ir["edges"], []
    def check(condition, label):
        if not condition: raise ValueError("InceptionA: " + label)
        checks.append(label)
    def has(a, b, role="tensor", sp=None, dp=None):
        return any(e["src"]==a and e["dst"]==b and e["role"]==role
                   and (sp is None or e["src_port"]==sp)
                   and (dp is None or e["dst_port"]==dp) for e in edges)
    check(ir.get("artifact_scope")==profile.get("artifact_scope")=="module"
          and profile["model_executed"] is False, "explicit nonexecuted module scope")
    check(profile["input_shape"]==["B",192,35,35] and profile["output_shape"]==["B",256,35,35]
          and profile["in_channels"]==192 and profile["pool_features"]==32
          and profile["conv_block_argument"] is None, "selected192/32/35 default BasicConv configuration")
    check(has("inca.input","inca.module") and has("inca.module","inca.output")
          and all(nodes[n]["parent"]=="inca.root" for n in ["inca.input","inca.module","inca.output"]),
          "root contains input -> isolated module -> output")
    order = ["inca.path_"+name for name,_ in BRANCHES]
    branch = nodes["inca.branches"]
    check(branch["mode"]=="parallel" and branch["collection_type"]=="list"
          and branch["literal_list"] is True and branch["literal_tuple"] is False
          and branch["branch_order"]==order and branch["branch_channels"]==WIDTHS,
          "literal ordered four-field list, no Add or tuple dispatch")
    for index, (name, configs) in enumerate(BRANCHES):
        path = "inca.path_"+name
        check(nodes[path]["collection_index"]==index
              and nodes[path]["source_attributes"]==[c[0] for c in configs]
              and has("inca.branches",path,"fork","in","in")
              and has(path,"inca.branches","tuple_collection","out",f"item[{index}]"),
              name+" branch receives same x and preserves ordered collection slot")
        basic_ids=["inca."+c[0] for c in configs]
        if name=="pool":basic_ids.insert(0,"inca.avgpool")
        check(has(path,basic_ids[0],"boundary","in","in")
              and all(has(a,b) for a,b in zip(basic_ids,basic_ids[1:]))
              and has(basic_ids[-1],path,"boundary","out","out"), name+" exact operation order")
        for attribute, cin, cout, kernel, padding in configs:
            prefix="inca."+attribute
            c,b,r=nodes[prefix+".conv"],nodes[prefix+".bn"],nodes[prefix+".relu"]
            check(nodes[prefix]["source_class"]=="BasicConv2d"
                  and [c["in_channels"],c["out_channels"],c["kernel_size"],c["padding"]]==[cin,cout,kernel,padding]
                  and c["stride"]==c["dilation"]==c["groups"]==1 and c["bias"] is False,
                  attribute+" exact Conv channels/kernel/padding/no-bias")
            check(c["parameter"]==attribute+".conv" and b["parameter"]==attribute+".bn"
                  and c["instance_identity"]=="inception_a."+attribute+".conv"
                  and b["instance_identity"]=="inception_a."+attribute+".bn",
                  attribute+" distinct scoped parameter identities")
            check(b["kind"]=="batch_norm2d" and b["num_features"]==cout and b["eps"]==0.001
                  and b["momentum"]==0.1 and b["affine"] is True and b["track_running_stats"] is True
                  and r["kind"]=="relu" and r["inplace"] is True,
                  attribute+" BN eps/defaults then inplace ReLU")
            check(has(prefix,prefix+".conv","boundary","in","in")
                  and has(prefix+".conv",prefix+".bn") and has(prefix+".bn",prefix+".relu")
                  and has(prefix+".relu",prefix,"boundary","out","out"), attribute+" Conv -> BN -> ReLU")
            check(all(n["shape"]==f"[B,{cout},35,35]" for n in [c,b,r]), attribute+" preserved spatial shape")
    pool=nodes["inca.avgpool"]; cat=nodes["inca.concat"]
    check(pool["pool_type"]=="average" and [pool["kernel_size"],pool["stride"],pool["padding"]]==[3,1,1]
          and pool["ceil_mode"] is False and pool["count_include_pad"] is True,
          "literal average-pool3/1/1 functional defaults")
    check(cat["kind"]=="concat" and cat["dim"]==1 and cat["ordered_inputs"]==order
          and cat["branch_channels"]==WIDTHS and cat["shape"]=="[B,256,35,35]"
          and has("inca.branches","inca.concat") and has("inca.concat","inca.module","boundary","out","out"),
          "list -> channel Concat256 -> module output")
    learned=[n for n in nodes.values() if n.get("learnable") is True]
    check(len(learned)==14 and len({n["parameter"] for n in learned})==14
          and sum(n["kind"]=="conv" for n in nodes.values())==7
          and sum(n["kind"]=="batch_norm2d" for n in nodes.values())==7,
          "seven Conv/BN pairs; fourteen separate learned parameter owners")
    check(not any(n["kind"] in ("add","linear","softmax","max_pool2d") for n in nodes.values())
          and not any(e["role"] in ("residual","dispatch") for e in edges),
          "no invented residual, classifier, MaxPool or input dispatch")
    return checks
