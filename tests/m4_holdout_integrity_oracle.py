"""Source-authored complete holdout inventories, independent of analyzer output.

The authored constructor/call expressions below come from the six formal fixture
entries. Public atomic port contracts follow their PyTorch API; container ports
are explicit adapters, not new tensor producers. Relationships from the earlier
handwritten oracle are retained, while this oracle additionally freezes every
declared port, parameter, instance, hierarchy member and return slot.
"""

from m4_holdout_oracle import EXPECTED_VIT_RELATIONS, FAMILY_EXPECTATIONS


def ports(*inputs, outputs=("output",)):
    return tuple((name, "in", "data", index) for index, name in enumerate(inputs)) + tuple(
        (name, "out", "data", index) for index, name in enumerate(outputs))


def authored(kind, category, evidence, parent, declared_ports, parameters=None,
             *, member=None, expression=None, repeat=None, output_path=None):
    return {"kind": kind, "category": category, "evidence": evidence,
            "parent": parent, "ports": declared_ports, "parameters": parameters or {},
            "member": member, "expression": expression, "repeat": repeat,
            "outputPath": output_path}


def module(parent, inputs, member, parameters=None, expression=None, repeat=None):
    return authored("Module", "container", "source", parent, ports(*inputs, outputs=()),
                    parameters, member=member, expression=expression, repeat=repeat)


def atomic(kind, category, parent, member, parameters=None, expression=None,
           *, inputs=("input",), outputs=("output",), evidence="contract"):
    return authored(kind, category, evidence, parent, ports(*inputs, outputs=outputs),
                    parameters, member=member, expression=expression)


def input_node(name):
    return authored("Input", "input", "source", "root", ports(outputs=(name,)))


def output_node(path=()):
    return authored("Output", "output", "source", "root", ports("value", outputs=()),
                    output_path=list(path))


VIT_NODES = {
    "image": input_node("image"),
    "root": module(None, ("image",), "root", {"dim": 16, "heads": 4, "classes": 10}),
    "patch": atomic("Conv2d", "convolution", "root", "patch_projection",
                    {"in_channels": 3, "out_channels": 16, "kernel_size": 4, "stride": 4},
                    "self.patch_projection(image)"),
    "flatten": authored("Flatten", "operator", "contract", "root", ports("input"),
                        {"start_dim": 2, "end_dim": -1}, expression="tokens.flatten(2)"),
    "transpose": authored("Transpose", "operator", "contract", "root", ports("input"),
                          {"dim0": 1, "dim1": 2}, expression="tokens.flatten(2).transpose(1, 2)"),
    "block": module("root", ("tokens",), "block", {"dim": 16, "heads": 4}, "self.block(tokens)"),
    "norm": atomic("LayerNorm", "norm", "block", "block.norm", {"normalized_shape": 16}, "self.norm(tokens)"),
    "attention": atomic("MultiheadAttention", "attention", "block", "block.attention",
                        {"embed_dim": 16, "num_heads": 4, "batch_first": True},
                        "self.attention(normalized, normalized, normalized, need_weights=False)",
                        inputs=("query", "key", "value"), outputs=("output", "weights")),
    "attention_residual": authored("Add", "residual", "source", "block",
                                   (("left", "in", "residual", 0), ("right", "in", "data", 1),
                                    ("output", "out", "data", 0)), expression="tokens + attended"),
    "mlp": module("block", ("input", "result"), "block.mlp", expression="self.mlp(tokens)",
                  repeat={"count": 3, "sharing": "independent"}),
    "expand": atomic("Linear", "linear", "mlp", "block.mlp.0", {"in_features": 16, "out_features": 32}, "self.mlp(tokens)"),
    "gelu": atomic("GELU", "activation", "mlp", "block.mlp.1", expression="self.mlp(tokens)"),
    "project": atomic("Linear", "linear", "mlp", "block.mlp.2", {"in_features": 32, "out_features": 16}, "self.mlp(tokens)"),
    "mlp_residual": authored("Add", "residual", "source", "block",
                             (("left", "in", "residual", 0), ("right", "in", "data", 1),
                              ("output", "out", "data", 0)), expression="tokens + self.mlp(tokens)"),
    "pool": authored("Mean", "operator", "contract", "root", ports("input"), {"dim": 1, "keepdim": False}, expression="tokens.mean(dim=1)"),
    "classifier": atomic("Linear", "linear", "root", "classifier", {"in_features": 16, "out_features": 10}, "self.classifier(pooled)"),
    "output": output_node(),
}
VIT_CHILDREN = {
    "root": ("image", "patch", "flatten", "transpose", "block", "pool", "classifier", "output"),
    "block": ("norm", "attention", "attention_residual", "mlp", "mlp_residual"),
    "mlp": ("expand", "gelu", "project"),
}

OPAQUE_NODES = {
    "tokens": input_node("tokens"),
    "root": module(None, ("tokens",), "root", {"channels": 16}),
    "mixer": module("root", ("tokens",), "mixer", {"channels": 16}, "self.mixer(tokens)"),
    "mixer.mixer": atomic("LocalResponseNorm", "opaque", "mixer", "mixer.mixer",
                          {"size": 3, "alpha": 0.0001},
                          "self.mixer(tokens)", inputs=("arg0",), evidence="opaque"),
    "output": output_node(),
}
OPAQUE_RELATIONS = (
    ("tokens", "tokens", "root", "tokens", "data"),
    ("tokens", "tokens", "mixer", "tokens", "data"),
    ("tokens", "tokens", "mixer.mixer", "arg0", "data"),
    ("mixer.mixer", "output", "output", "value", "data"),
)

TEMPORAL_NODES = {
    "input.series": input_node("series"),
    "root": module(None, ("series",), "root"),
    "recurrent": atomic("LSTM", "recurrent", "root", "recurrent",
                        {"input_size": 6, "hidden_size": 8, "num_layers": 2, "batch_first": True},
                        "self.recurrent(series)", outputs=("output", "h_n", "c_n")),
    "projection": atomic("Linear", "linear", "root", "projection", {"in_features": 8, "out_features": 3}, "self.projection(sequence)"),
    "projection@2": atomic("Linear", "linear", "root", "projection", {"in_features": 8, "out_features": 3}, "self.shared_projection(sequence)"),
}
for output_name, output_path in FAMILY_EXPECTATIONS["TemporalForecaster"]["outputPaths"].items():
    TEMPORAL_NODES[output_name] = output_node(output_path)

SEGMENTATION_NODES = {
    "input.image": input_node("image"),
    "root": module(None, ("image",), "root"),
    "stem": atomic("Conv2d", "convolution", "root", "stem", {"in_channels": 3, "out_channels": 8, "kernel_size": 3, "padding": 1}, "self.stem(image)"),
    "repeat.refinement": authored("Repeat", "container", "source", "root", (), repeat={"count": 2, "sharing": "independent"}),
    "downsample": atomic("MaxPool2d", "pooling", "root", "downsample", {"kernel_size": 2}, "self.downsample(skip)"),
    "bottleneck": atomic("Conv2d", "convolution", "root", "bottleneck", {"in_channels": 8, "out_channels": 16, "kernel_size": 3, "padding": 1}, "self.bottleneck(self.downsample(skip))"),
    "upsample": atomic("ConvTranspose2d", "convolution", "root", "upsample", {"in_channels": 16, "out_channels": 8, "kernel_size": 2, "stride": 2}, "self.upsample(coarse)"),
    "Concat": authored("Concat", "operator", "contract", "root", ports("arg0", "arg0.1"), expression="torch.cat((skip, restored), dim=1)"),
    "head": atomic("Conv2d", "convolution", "root", "head", {"in_channels": 16, "out_channels": 2, "kernel_size": 1}, "self.head(merged)"),
    "output0": output_node(),
}
SEGMENTATION_CHILDREN = {
    "root": ("input.image", "stem", "repeat.refinement", "downsample", "bottleneck", "upsample", "Concat", "head", "output0"),
    "repeat.refinement": ("refinement.0", "refinement.1"),
}
for index in range(2):
    block = "refinement." + str(index)
    SEGMENTATION_NODES[block] = module("repeat.refinement", ("image",), block, {"channels": 8}, "block(skip)")
    SEGMENTATION_NODES[block + ".conv"] = atomic("Conv2d", "convolution", block, block + ".conv", {"in_channels": 8, "out_channels": 8, "kernel_size": 3, "padding": 1}, "self.conv(image)")
    SEGMENTATION_NODES[block + ".activation"] = atomic("ReLU", "activation", block, block + ".activation", expression="self.activation(self.conv(image))")
    SEGMENTATION_CHILDREN[block] = (block + ".conv", block + ".activation")

GRAPH_NODES = {
    "input.nodes": input_node("nodes"),
    "input.edge_index": input_node("edge_index"),
    "root": module(None, ("nodes", "edge_index"), "root"),
    "project": atomic("Linear", "linear", "root", "project", {"in_features": 4, "out_features": 4}, "self.project(nodes)"),
    "message": atomic("GraphAttentionKernel", "opaque", "root", "message", expression="self.message(features, edge_index)", inputs=("arg0", "arg1"), evidence="opaque"),
    "ConditionalRegion": authored("ConditionalRegion", "opaque", "opaque", "root", ports("features", "messages"), expression="if features.sum() > 0:\n            messages = self.activation(messages)"),
    "output0": output_node(),
}

SSM_NODES = {
    "input.sequence": input_node("sequence"),
    "root": module(None, ("sequence",), "root"),
    "scan": atomic("StateSpaceScan", "opaque", "root", "scan", expression="self.scan(sequence)", inputs=("arg0",), evidence="opaque"),
    "DynamicLoop": authored("DynamicLoop", "opaque", "opaque", "root", ports("sequence", "state"), expression="for index in range(sequence.shape[1]):\n            state = self.projection(state)"),
    "output0": output_node(),
}


def case(entry, fixture, nodes, relations, children, tensors, calls, instances, warnings):
    return {"entry": "model:" + entry, "fixture": fixture, "nodes": nodes,
            "relations": tuple(relations), "children": children, "tensorCount": tensors,
            "callCount": calls, "instanceCount": instances, "warnings": tuple(warnings)}


HOLDOUTS = {
    "PatchVisionEncoder": case("PatchVisionEncoder", "holdout_vit", VIT_NODES, EXPECTED_VIT_RELATIONS,
                                VIT_CHILDREN, 13, 10, 10, ()),
    "UnsupportedVision": case("UnsupportedVision", "holdout_catalog_boundaries", OPAQUE_NODES, OPAQUE_RELATIONS,
                               {"root": ("tokens", "mixer", "output"), "mixer": ("mixer.mixer",)},
                               2, 3, 3, ("Unknown constructor torch.nn.LocalResponseNorm",)),
    "TemporalForecaster": case("TemporalForecaster", "holdout_families", TEMPORAL_NODES,
                                FAMILY_EXPECTATIONS["TemporalForecaster"]["relations"],
                                {"root": ("input.series", "recurrent", "projection", "projection@2",
                                          "output0", "output1", "output2", "output3")}, 6, 4, 3, ()),
    "SkipSegmentation": case("SkipSegmentation", "holdout_families", SEGMENTATION_NODES,
                              FAMILY_EXPECTATIONS["SkipSegmentation"]["relations"], SEGMENTATION_CHILDREN,
                              11, 12, 12, ()),
    "GraphForecast": case("GraphForecast", "holdout_families", GRAPH_NODES,
                           FAMILY_EXPECTATIONS["GraphForecast"]["relations"],
                           {"root": ("input.edge_index", "input.nodes", "project", "message",
                                     "ConditionalRegion", "output0")}, 5, 3, 3,
                           ("Unknown constructor model.GraphAttentionKernel", "Unsupported control/state region ConditionalRegion")),
    "DynamicStateSpace": case("DynamicStateSpace", "holdout_families", SSM_NODES,
                               FAMILY_EXPECTATIONS["DynamicStateSpace"]["relations"],
                               {"root": ("input.sequence", "scan", "DynamicLoop", "output0")}, 3, 2, 2,
                               ("Unknown constructor model.StateSpaceScan", "Unsupported control/state region DynamicLoop")),
}
