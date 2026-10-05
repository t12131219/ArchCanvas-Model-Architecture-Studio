"""Hand-authored networks and concrete expected tensor contracts.

This module neither imports the backend nor derives expected values using its
registry/shape propagation. Tensor shapes below are worked examples, not product
snapshots. An adapter may package these exact nodes for the declared draft API.
"""
from copy import deepcopy


def node(identity, kind, parameters=None, label=None):
    return {"id": identity, "kind": kind, "label": label or identity,
            "parameters": parameters or {}, "position": {"x": 100, "y": 100}}


def edge(identity, source, target, source_port="output", target_port="input"):
    return {"id": identity, "source": {"nodeId": source, "portId": source_port},
            "target": {"nodeId": target, "portId": target_port}}


def draft(identity, nodes, edges):
    return {"schemaVersion": 1, "mode": "authored-draft", "id": identity,
            "title": "Independent " + identity, "revision": 0, "nodes": nodes, "edges": edges}


MLP = draft("independent-mlp", [
    node("x", "Input", {"shape": [2, 4], "dtype": "float32"}),
    node("first", "Linear", {"in_features": 4, "out_features": 8, "bias": False}, "投影"),
    node("relu", "ReLU"),
    node("gelu", "GELU", {"approximate": "tanh"}),
    node("silu", "SiLU"),
    node("identity", "Identity"),
    node("drop", "Dropout", {"p": 0.25}),
    node("last", "Linear", {"in_features": 8, "out_features": 3, "bias": True}, "投影"),
    node("out", "Output"),
], [edge("e1", "x", "first"), edge("e2", "first", "relu"), edge("e3", "relu", "gelu"),
    edge("e4", "gelu", "silu"), edge("e5", "silu", "identity"), edge("e6", "identity", "drop"),
    edge("e7", "drop", "last"), edge("e8", "last", "out")])

CNN = draft("independent-cnn", [
    node("image", "Input", {"shape": [2, 3, 8, 8], "dtype": "float32"}),
    node("conv", "Conv2d", {"in_channels": 3, "out_channels": 4, "kernel_size": [3, 3], "stride": [2, 2], "padding": [1, 1]}),
    node("bn", "BatchNorm2d", {"num_features": 4, "eps": 0.001, "momentum": 0.2}),
    node("pool", "MaxPool2d", {"kernel_size": [2, 2], "stride": [2, 2], "padding": [0, 0]}),
    node("avg", "AdaptiveAvgPool2d", {"output_size": [1, 1]}),
    node("flat", "Flatten", {"start_dim": 1, "end_dim": -1}),
    node("fc", "Linear", {"in_features": 4, "out_features": 5, "bias": True}),
    node("out", "Output"),
], [edge("e1", "image", "conv"), edge("e2", "conv", "bn"), edge("e3", "bn", "pool"),
    edge("e4", "pool", "avg"), edge("e5", "avg", "flat"), edge("e6", "flat", "fc"), edge("e7", "fc", "out")])

EMBED = draft("independent-embedding", [
    node("tokens", "Input", {"shape": [2, 3], "dtype": "int64"}),
    node("embedding", "Embedding", {"num_embeddings": 7, "embedding_dim": 4}),
    node("norm", "LayerNorm", {"normalized_shape": [4], "eps": 0.00001, "elementwise_affine": True}),
    node("flat", "Flatten", {"start_dim": 1, "end_dim": -1}),
    node("out", "Output"),
], [edge("e1", "tokens", "embedding"), edge("e2", "embedding", "norm"), edge("e3", "norm", "flat"), edge("e4", "flat", "out")])

RESIDUAL = draft("independent-residual", [
    node("x", "Input", {"shape": [2, 4], "dtype": "float32"}),
    node("projection", "Linear", {"in_features": 4, "out_features": 4, "bias": False}),
    node("add", "Add"), node("out", "Output"),
], [edge("branch", "x", "projection"), edge("left", "x", "add", target_port="left"),
    edge("right", "projection", "add", target_port="right"), edge("result", "add", "out")])

CONCAT = draft("independent-concat", [
    node("a", "Input", {"shape": [2, 3], "dtype": "float32"}),
    node("b", "Input", {"shape": [2, 5], "dtype": "float32"}),
    node("cat", "Concat", {"dim": -1}), node("out", "Output"),
], [edge("a-to-cat", "a", "cat", target_port="a"), edge("b-to-cat", "b", "cat", target_port="b"), edge("result", "cat", "out")])

POSITIVE_CASES = [
    {"name": "mlp-distinct-same-label-modules", "draft": MLP, "outputs": {
        "x": ([2, 4], "float32"), "first": ([2, 8], "float32"), "relu": ([2, 8], "float32"),
        "gelu": ([2, 8], "float32"), "silu": ([2, 8], "float32"), "identity": ([2, 8], "float32"),
        "drop": ([2, 8], "float32"), "last": ([2, 3], "float32"), "out": ([2, 3], "float32")}},
    {"name": "cnn-concrete-spatial-shapes", "draft": CNN, "outputs": {
        "image": ([2, 3, 8, 8], "float32"), "conv": ([2, 4, 4, 4], "float32"), "bn": ([2, 4, 4, 4], "float32"),
        "pool": ([2, 4, 2, 2], "float32"), "avg": ([2, 4, 1, 1], "float32"), "flat": ([2, 4], "float32"),
        "fc": ([2, 5], "float32"), "out": ([2, 5], "float32")}},
    {"name": "embedding-index-and-normalized-tail", "draft": EMBED, "outputs": {
        "tokens": ([2, 3], "int64"), "embedding": ([2, 3, 4], "float32"), "norm": ([2, 3, 4], "float32"),
        "flat": ([2, 12], "float32"), "out": ([2, 12], "float32")}},
    {"name": "residual-single-producer-fanout", "draft": RESIDUAL, "edgeRoles": {"left": "residual"}, "outputs": {
        "x": ([2, 4], "float32"), "projection": ([2, 4], "float32"), "add": ([2, 4], "float32"), "out": ([2, 4], "float32")}},
    {"name": "concat-negative-axis-ordered-inputs", "draft": CONCAT, "outputs": {
        "a": ([2, 3], "float32"), "b": ([2, 5], "float32"), "cat": ([2, 8], "float32"), "out": ([2, 8], "float32")}},
]

# Additional arithmetic branches are concrete, independently worked cases.
# 9x9 grouped/dilated k3,p2,s2 convolution gives 5x5; ceil pool k3,p1,s2
# gives 3x3. The original baseline case remains unchanged.
GROUPED = deepcopy(CNN)
GROUPED["id"] = "independent-grouped-ceil"
for item in GROUPED["nodes"]:
    if item["id"] == "image":
        item["parameters"]["shape"] = [2, 4, 9, 9]
    elif item["id"] == "conv":
        item["parameters"].update(in_channels=4, out_channels=6, groups=2, dilation=[2, 2], padding=[2, 2])
    elif item["id"] == "bn":
        item["parameters"]["num_features"] = 6
    elif item["id"] == "pool":
        item["parameters"].update(kernel_size=[3, 3], padding=[1, 1], ceil_mode=True)
    elif item["id"] == "fc":
        item["parameters"]["in_features"] = 6
POSITIVE_CASES.append({"name": "grouped-dilated-conv-and-ceil-pool", "draft": GROUPED, "outputs": {
    "image": ([2, 4, 9, 9], "float32"), "conv": ([2, 6, 5, 5], "float32"), "bn": ([2, 6, 5, 5], "float32"),
    "pool": ([2, 6, 3, 3], "float32"), "avg": ([2, 6, 1, 1], "float32"), "flat": ([2, 6], "float32"),
    "fc": ([2, 5], "float32"), "out": ([2, 5], "float32")}})

AXIS_ZERO = deepcopy(CONCAT)
AXIS_ZERO["id"] = "independent-axis-zero"
AXIS_ZERO["nodes"][1]["parameters"]["shape"] = [5, 3]
AXIS_ZERO["nodes"][2]["parameters"]["dim"] = 0
POSITIVE_CASES.append({"name": "concat-axis-zero-distinct-widths", "draft": AXIS_ZERO, "effectiveConcatDim": 0,
                      "outputs": {"a": ([2, 3], "float32"), "b": ([5, 3], "float32"), "cat": ([7, 3], "float32"), "out": ([7, 3], "float32")}})

REPEATED_ADD = deepcopy(RESIDUAL)
REPEATED_ADD["id"] = "independent-repeated-add"
REPEATED_ADD["nodes"].insert(-1, node("add2", "Add", label="同一表达式的另一个调用"))
REPEATED_ADD["nodes"].append(node("out2", "Output"))
REPEATED_ADD["edges"] += [edge("left2", "x", "add2", target_port="left"),
                           edge("right2", "projection", "add2", target_port="right"), edge("result2", "add2", "out2")]
POSITIVE_CASES.append({"name": "same-binary-expression-distinct-calls-and-outputs", "draft": REPEATED_ADD,
                      "edgeRoles": {"left": "residual", "left2": "residual"},
                      "outputs": {"x": ([2, 4], "float32"), "projection": ([2, 4], "float32"),
                                  "add": ([2, 4], "float32"), "add2": ([2, 4], "float32"),
                                  "out": ([2, 4], "float32"), "out2": ([2, 4], "float32")}})


def rejection_cases():
    """Each mutated field is an independently specified contract violation."""
    cases = []

    def changed(name, base, mutate, stage="validation"):
        value = deepcopy(base)
        mutate(value)
        cases.append({"name": name, "draft": value, "rejectAt": stage})

    def parameter(value, identity, key, replacement):
        next(n for n in value["nodes"] if n["id"] == identity)["parameters"][key] = replacement

    changed("source-mode-not-authoring", MLP, lambda d: d.update(mode="source-bound"))
    changed("unknown-envelope-field", MLP, lambda d: d.update(sourceRoot="/tmp/imported-source"))
    changed("duplicate-node-id", MLP, lambda d: d["nodes"].append(deepcopy(d["nodes"][1])))
    changed("duplicate-edge-id", MLP, lambda d: d["edges"].append(deepcopy(d["edges"][0])))
    changed("foreign-node-same-port-name", MLP, lambda d: d["edges"][0]["source"].update(nodeId="does-not-exist"))
    changed("undeclared-output-port", MLP, lambda d: d["edges"][0]["source"].update(portId="input"))
    changed("undeclared-input-port", MLP, lambda d: d["edges"][0]["target"].update(portId="output"))
    changed("second-input-producer", RESIDUAL, lambda d: d["edges"].append(edge("duplicate-input", "projection", "add", target_port="left")))
    changed("self-cycle", MLP, lambda d: d["edges"][1]["source"].update(nodeId="relu"))
    changed("two-node-cycle", MLP, lambda d: d["edges"][0]["source"].update(nodeId="relu"))
    changed("unknown-module-kind", MLP, lambda d: d["nodes"][1].update(kind="MultiheadAttention"))
    changed("unknown-parameter-key", MLP, lambda d: parameter(d, "first", "__code__", "danger"))
    changed("linear-negative-width", MLP, lambda d: parameter(d, "first", "in_features", -4))
    changed("linear-boolean-width", MLP, lambda d: parameter(d, "first", "in_features", True))
    changed("linear-fractional-width", MLP, lambda d: parameter(d, "first", "out_features", 3.5))
    changed("linear-incompatible-tail", MLP, lambda d: parameter(d, "last", "in_features", 7))
    changed("dropout-negative", MLP, lambda d: parameter(d, "drop", "p", -0.01))
    changed("dropout-over-one", MLP, lambda d: parameter(d, "drop", "p", 1.01))
    changed("dropout-boolean", MLP, lambda d: parameter(d, "drop", "p", True))
    changed("dropout-nan", MLP, lambda d: parameter(d, "drop", "p", float("nan")))
    changed("dropout-infinity", MLP, lambda d: parameter(d, "drop", "p", float("inf")))
    changed("gelu-unknown-approximation", MLP, lambda d: parameter(d, "gelu", "approximate", "relu"))
    changed("weighted-float64-input", MLP, lambda d: parameter(d, "x", "dtype", "float64"))
    changed("input-boolean-dimension", MLP, lambda d: parameter(d, "x", "shape", [2, True]))
    changed("input-negative-dimension", MLP, lambda d: parameter(d, "x", "shape", [2, -4]))
    changed("position-nonfinite", MLP, lambda d: d["nodes"][1]["position"].update(x=float("inf")))
    changed("conv-zero-kernel", CNN, lambda d: parameter(d, "conv", "kernel_size", [0, 0]))
    changed("conv-channel-mismatch", CNN, lambda d: parameter(d, "conv", "in_channels", 2))
    changed("pool-zero-stride", CNN, lambda d: parameter(d, "pool", "stride", [0, 0]))
    changed("batchnorm-channel-mismatch", CNN, lambda d: parameter(d, "bn", "num_features", 3))
    changed("layernorm-negative-epsilon", EMBED, lambda d: parameter(d, "norm", "eps", -1.0))
    changed("layernorm-wrong-tail", EMBED, lambda d: parameter(d, "norm", "normalized_shape", [3]))
    changed("embedding-float-indices", EMBED, lambda d: parameter(d, "tokens", "dtype", "float32"))
    changed("embedding-zero-vocabulary", EMBED, lambda d: parameter(d, "embedding", "num_embeddings", 0))
    changed("add-broadcast-unsupported", RESIDUAL, lambda d: parameter(d, "projection", "out_features", 1))
    changed("concat-nonaxis-shape-mismatch", CONCAT, lambda d: parameter(d, "b", "shape", [3, 5]))
    changed("concat-axis-out-of-range", CONCAT, lambda d: parameter(d, "cat", "dim", 2))
    changed("concat-boolean-axis", CONCAT, lambda d: parameter(d, "cat", "dim", False))
    changed("concat-dtype-mismatch", CONCAT, lambda d: parameter(d, "b", "dtype", "float64"))
    changed("conv-groups-not-dividing-channels", GROUPED, lambda d: parameter(d, "conv", "groups", 3))
    changed("pool-padding-exceeds-half-kernel", CNN, lambda d: parameter(d, "pool", "padding", [2, 2]))
    changed("conv-kernel-larger-than-padded-input", CNN, lambda d: parameter(d, "conv", "kernel_size", [20, 20]))
    changed("flatten-out-of-range-axis", EMBED, lambda d: parameter(d, "flat", "start_dim", 3))
    changed("batchnorm-training-singleton", CNN, lambda d: parameter(d, "image", "shape", [1, 3, 1, 1]))
    changed("input-elements-exceed-budget", MLP, lambda d: parameter(d, "x", "shape", [1000000, 1000000]))
    changed("unsafe-revision", MLP, lambda d: d.update(revision=2**53))
    changed("boolean-revision", MLP, lambda d: d.update(revision=True))
    changed("incomplete-input-slot", MLP, lambda d: d["edges"].pop(0), "generation")
    changed("unreachable-island", MLP, lambda d: d["nodes"].append(node("unused", "Identity")), "generation")
    changed("missing-output", MLP, lambda d: (d["nodes"].pop(), d["edges"].pop()), "generation")
    return cases
