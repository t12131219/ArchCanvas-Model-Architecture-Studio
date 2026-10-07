"""Handwritten expectations from the formal MLP and Residual CNN sources.

No analyzer or model import is used to create these facts. Small helpers expand
the two explicitly authored residual blocks, not an analyzer-produced snapshot.
Relations name both endpoints and the original producer; container adapters
retain the producer's tensor rather than manufacturing a boundary tensor.
"""


def unary_ports():
    return (("input", "in", "data", 0), ("output", "out", "data", 0))


def node(kind, category, evidence, parent, ports, parameters=None, *, source_path="model.py",
         expression=None, instance=None, repeat=None):
    return {
        "kind": kind, "category": category, "evidence": evidence, "parent": parent,
        "ports": ports, "parameters": parameters or {}, "sourcePath": source_path,
        "expression": expression, "instance": instance, "repeat": repeat,
    }


MLP_NODES = {
    "input.features": node("Input", "input", "source", "root", (("features", "out", "data", 0),)),
    "root": node("Module", "container", "source", None, (("features", "in", "data", 0),),
                 {"input_dim": 16, "hidden_dim": 32, "output_dim": 4}, instance="root"),
    "network": node("Module", "container", "source", "root",
                    (("input", "in", "data", 0), ("result", "in", "data", 1)),
                    expression="self.network(features)", instance="network",
                    repeat={"count": 4, "sharing": "independent"}),
    "network.0": node("Linear", "linear", "contract", "network", unary_ports(),
                      {"in_features": 16, "out_features": 32},
                      expression="self.network(features)", instance="network.0"),
    "network.1": node("GELU", "activation", "contract", "network", unary_ports(),
                      expression="self.network(features)", instance="network.1"),
    "network.2": node("Dropout", "regularization", "contract", "network", unary_ports(),
                      {"p": 0.1}, expression="self.network(features)", instance="network.2"),
    "network.3": node("Linear", "linear", "contract", "network", unary_ports(),
                      {"in_features": 32, "out_features": 4},
                      expression="self.network(features)", instance="network.3"),
    "output": node("Output", "output", "source", "root", (("value", "in", "data", 0),)),
}

# (producer node, producer port, consumer node, consumer port, edge role).
MLP_RELATIONS = (
    ("input.features", "features", "root", "features", "data"),
    ("input.features", "features", "network", "input", "data"),
    ("input.features", "features", "network.0", "input", "data"),
    ("network.0", "output", "network.1", "input", "data"),
    ("network.1", "output", "network.2", "input", "data"),
    ("network.2", "output", "network.3", "input", "data"),
    ("network.3", "output", "network", "result", "data"),
    ("network.3", "output", "output", "value", "data"),
)

MLP_CHILDREN = {
    "root": ("input.features", "network", "output"),
    "network": ("network.0", "network.1", "network.2", "network.3"),
}

CNN_NODES = {
    "input.image": node("Input", "input", "source", "root", (("image", "out", "data", 0),)),
    "root": node("Module", "container", "source", None, (("image", "in", "data", 0),),
                 {"channels": 16, "classes": 10}, instance="root"),
    "stem": node("Conv2d", "convolution", "contract", "root", unary_ports(),
                 {"in_channels": 3, "out_channels": 16, "kernel_size": 3, "padding": 1},
                 expression="self.stem(image)", instance="stem"),
    "repeat.blocks": node("Repeat", "container", "source", "root", (),
                          repeat={"count": 2, "sharing": "independent"}),
}

CNN_CHILDREN = {
    "root": ("input.image", "stem", "repeat.blocks", "pool", "flatten", "classifier", "output"),
    "repeat.blocks": ("blocks.0", "blocks.1"),
}
CNN_RELATIONS = [
    ("input.image", "image", "root", "image", "data"),
    ("input.image", "image", "stem", "input", "data"),
]

for block_index, producer in ((0, "stem"), (1, "blocks.0.activation@2")):
    block = "blocks." + str(block_index)
    CNN_NODES[block] = node("Module", "container", "source", "repeat.blocks", (("x", "in", "data", 0),),
                           {"channels": 16}, expression="block(x)", instance=block)
    members = (
        ("conv1", "Conv2d", "convolution", {"in_channels": 16, "out_channels": 16, "kernel_size": 3, "padding": 1}, "self.conv1(x)"),
        ("norm1", "BatchNorm2d", "norm", {"num_features": 16}, "self.norm1(self.conv1(x))"),
        ("activation", "ReLU", "activation", {}, "self.activation(self.norm1(self.conv1(x)))"),
        ("conv2", "Conv2d", "convolution", {"in_channels": 16, "out_channels": 16, "kernel_size": 3, "padding": 1}, "self.conv2(x)"),
        ("norm2", "BatchNorm2d", "norm", {"num_features": 16}, "self.norm2(self.conv2(x))"),
    )
    for member, kind, category, parameters, expression in members:
        name = block + "." + member
        CNN_NODES[name] = node(kind, category, "contract", block, unary_ports(), parameters,
                               source_path="blocks.py", expression=expression, instance=name)
    CNN_NODES[block + ".add"] = node("Add", "residual", "source", block,
                                     (("left", "in", "data", 0), ("right", "in", "residual", 1),
                                      ("output", "out", "data", 0)),
                                     source_path="blocks.py", expression="x + residual")
    CNN_NODES[block + ".activation@2"] = node("ReLU", "activation", "contract", block, unary_ports(),
                                              source_path="blocks.py", expression="self.activation(x + residual)",
                                              instance=block + ".activation")
    CNN_CHILDREN[block] = tuple(block + "." + member for member in
                                ("conv1", "norm1", "activation", "conv2", "norm2", "add", "activation@2"))
    CNN_RELATIONS.extend((
        (producer, "output", block, "x", "data"),
        (producer, "output", block + ".conv1", "input", "data"),
        (block + ".conv1", "output", block + ".norm1", "input", "data"),
        (block + ".norm1", "output", block + ".activation", "input", "data"),
        (block + ".activation", "output", block + ".conv2", "input", "data"),
        (block + ".conv2", "output", block + ".norm2", "input", "data"),
        (block + ".norm2", "output", block + ".add", "left", "data"),
        (producer, "output", block + ".add", "right", "residual"),
        (block + ".add", "output", block + ".activation@2", "input", "data"),
    ))

CNN_NODES.update({
    "pool": node("AdaptiveAvgPool2d", "pooling", "contract", "root", unary_ports(),
                 {"output_size": 1}, expression="self.pool(x)", instance="pool"),
    "flatten": node("Flatten", "operator", "contract", "root", unary_ports(),
                    {"start_dim": 1}, expression="self.flatten(self.pool(x))", instance="flatten"),
    "classifier": node("Linear", "linear", "contract", "root", unary_ports(),
                       {"in_features": 16, "out_features": 10},
                       expression="self.classifier(x)", instance="classifier"),
    "output": node("Output", "output", "source", "root", (("value", "in", "data", 0),)),
})
CNN_RELATIONS.extend((
    ("blocks.1.activation@2", "output", "pool", "input", "data"),
    ("pool", "output", "flatten", "input", "data"),
    ("flatten", "output", "classifier", "input", "data"),
    ("classifier", "output", "output", "value", "data"),
))

BASE_MODELS = {
    "MLP": {"fixture": "mlp", "entry": "model:MLP", "sources": ("model.py",),
            "nodes": MLP_NODES, "relations": MLP_RELATIONS, "children": MLP_CHILDREN,
            "tensorCount": 5, "callCount": 6, "instanceCount": 6},
    "ResidualCNN": {"fixture": "residual_cnn", "entry": "model:ResidualCNN",
                    "sources": ("blocks.py", "model.py"), "nodes": CNN_NODES,
                    "relations": tuple(CNN_RELATIONS), "children": CNN_CHILDREN,
                    "tensorCount": 19, "callCount": 19, "instanceCount": 17},
}
