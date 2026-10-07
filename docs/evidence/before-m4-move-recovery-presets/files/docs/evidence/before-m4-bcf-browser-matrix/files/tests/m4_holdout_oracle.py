"""Handwritten M4 holdout expectations.

The oracle describes the source-level facts of the independent vision fixture;
it does not import or execute the fixture and does not derive expectations from
the analyzer implementation.
"""

EXPECTED_VIT_CONTRACT_COUNTS = {
    "Conv2d": 1,
    "LayerNorm": 1,
    "MultiheadAttention": 1,
    "Linear": 3,
    "GELU": 1,
    "Flatten": 1,
    "Transpose": 1,
    "Mean": 1,
    "Add": 2,
    "Module": 3,
    "Input": 1,
    "Output": 1,
}

# Containers retain their input/result bindings without inventing a new tensor.
# Full relationships are frozen here rather than copied from an IR snapshot.
EXPECTED_VIT_RELATIONS = {
    ("image", "image", "root", "image", "data"),
    ("image", "image", "patch", "input", "data"),
    ("patch", "output", "flatten", "input", "data"),
    ("flatten", "output", "transpose", "input", "data"),
    ("transpose", "output", "block", "tokens", "data"),
    ("transpose", "output", "norm", "input", "data"),
    ("norm", "output", "attention", "query", "data"),
    ("norm", "output", "attention", "key", "data"),
    ("norm", "output", "attention", "value", "data"),
    ("transpose", "output", "attention_residual", "left", "residual"),
    ("attention", "output", "attention_residual", "right", "data"),
    ("attention_residual", "output", "mlp", "input", "data"),
    ("attention_residual", "output", "expand", "input", "data"),
    ("expand", "output", "gelu", "input", "data"),
    ("gelu", "output", "project", "input", "data"),
    ("project", "output", "mlp", "result", "data"),
    ("attention_residual", "output", "mlp_residual", "left", "residual"),
    ("project", "output", "mlp_residual", "right", "data"),
    ("mlp_residual", "output", "pool", "input", "data"),
    ("pool", "output", "classifier", "input", "data"),
    ("classifier", "output", "output", "value", "data"),
}

EXPECTED_VIT_PARAMETERS = {
    "patch_projection": {
        "kind": "Conv2d",
        "parameters": {"in_channels": 3, "out_channels": 16, "kernel_size": 4, "stride": 4},
    },
    "attention": {
        "kind": "MultiheadAttention",
        "parameters": {"embed_dim": 16, "num_heads": 4, "batch_first": True},
    },
    "classifier": {
        "kind": "Linear",
        "parameters": {"in_features": 16, "out_features": 10},
    },
}

EXPECTED_OPAQUE = {
    "entry": "model:UnsupportedVision",
    "kind": "Conv1d",
    "category": "opaque",
    "evidence": "opaque",
    "warning_fragment": "Unknown constructor torch.nn.Conv1d",
}


# Each map enumerates every expected node and every source/port relationship.
# Keys are names from the fixture's authored module members and unique operations.
FAMILY_EXPECTATIONS = {
    "TemporalForecaster": {
        "outputPaths": {
            "output0": [{"kind": "key", "key": "forecast"}, {"kind": "index", "index": 0}],
            "output1": [{"kind": "key", "key": "forecast"}, {"kind": "index", "index": 1}],
            "output2": [{"kind": "key", "key": "state"}, {"kind": "key", "key": "hidden"}],
            "output3": [{"kind": "key", "key": "state"}, {"kind": "key", "key": "cell"}],
        },
        "nodes": {
            "input.series": ("Input", "input", "source"),
            "root": ("Module", "container", "source"),
            "recurrent": ("LSTM", "recurrent", "contract"),
            "projection": ("Linear", "linear", "contract"),
            "projection@2": ("Linear", "linear", "contract"),
            "output0": ("Output", "output", "source"),
            "output1": ("Output", "output", "source"),
            "output2": ("Output", "output", "source"),
            "output3": ("Output", "output", "source"),
        },
        "relations": {
            ("input.series", "series", "root", "series", "data"),
            ("input.series", "series", "recurrent", "input", "data"),
            ("recurrent", "output", "projection", "input", "data"),
            ("recurrent", "output", "projection@2", "input", "data"),
            ("projection", "output", "output0", "value", "data"),
            ("projection@2", "output", "output1", "value", "data"),
            ("recurrent", "h_n", "output2", "value", "data"),
            ("recurrent", "c_n", "output3", "value", "data"),
        },
        "parameters": {
            "recurrent": {"input_size": 6, "hidden_size": 8, "num_layers": 2, "batch_first": True},
            "projection": {"in_features": 8, "out_features": 3},
            "projection@2": {"in_features": 8, "out_features": 3},
        },
        "warnings": [],
    },
    "SkipSegmentation": {
        "nodes": {
            "input.image": ("Input", "input", "source"),
            "root": ("Module", "container", "source"),
            "stem": ("Conv2d", "convolution", "contract"),
            "repeat.refinement": ("Repeat", "container", "source"),
            "refinement.0": ("Module", "container", "source"),
            "refinement.0.conv": ("Conv2d", "convolution", "contract"),
            "refinement.0.activation": ("ReLU", "activation", "contract"),
            "refinement.1": ("Module", "container", "source"),
            "refinement.1.conv": ("Conv2d", "convolution", "contract"),
            "refinement.1.activation": ("ReLU", "activation", "contract"),
            "downsample": ("MaxPool2d", "pooling", "contract"),
            "bottleneck": ("Conv2d", "convolution", "contract"),
            "upsample": ("ConvTranspose2d", "opaque", "opaque"),
            "Concat": ("Concat", "operator", "contract"),
            "head": ("Conv2d", "convolution", "contract"),
            "output0": ("Output", "output", "source"),
        },
        "relations": {
            ("input.image", "image", "root", "image", "data"),
            ("input.image", "image", "stem", "input", "data"),
            ("stem", "output", "refinement.0", "image", "data"),
            ("stem", "output", "refinement.0.conv", "input", "data"),
            ("refinement.0.conv", "output", "refinement.0.activation", "input", "data"),
            ("refinement.0.activation", "output", "refinement.1", "image", "data"),
            ("refinement.0.activation", "output", "refinement.1.conv", "input", "data"),
            ("refinement.1.conv", "output", "refinement.1.activation", "input", "data"),
            ("refinement.1.activation", "output", "downsample", "input", "data"),
            ("downsample", "output", "bottleneck", "input", "data"),
            ("bottleneck", "output", "upsample", "arg0", "data"),
            ("refinement.1.activation", "output", "Concat", "arg0", "data"),
            ("upsample", "output", "Concat", "arg0.1", "data"),
            ("Concat", "output", "head", "input", "data"),
            ("head", "output", "output0", "value", "data"),
        },
        "parameters": {
            "stem": {"in_channels": 3, "out_channels": 8, "kernel_size": 3, "padding": 1},
            "downsample": {"kernel_size": 2},
            "bottleneck": {"in_channels": 8, "out_channels": 16, "kernel_size": 3, "padding": 1},
            "head": {"in_channels": 16, "out_channels": 2, "kernel_size": 1},
        },
        "warnings": ["Unknown constructor torch.nn.ConvTranspose2d"],
    },
    "GraphForecast": {
        "nodes": {
            "input.nodes": ("Input", "input", "source"),
            "input.edge_index": ("Input", "input", "source"),
            "root": ("Module", "container", "source"),
            "project": ("Linear", "linear", "contract"),
            "message": ("GraphAttentionKernel", "opaque", "opaque"),
            "ConditionalRegion": ("ConditionalRegion", "opaque", "opaque"),
            "output0": ("Output", "output", "source"),
        },
        "relations": {
            ("input.nodes", "nodes", "root", "nodes", "data"),
            ("input.edge_index", "edge_index", "root", "edge_index", "data"),
            ("input.nodes", "nodes", "project", "input", "data"),
            ("project", "output", "message", "arg0", "data"),
            ("input.edge_index", "edge_index", "message", "arg1", "data"),
            ("project", "output", "ConditionalRegion", "features", "data"),
            ("message", "output", "ConditionalRegion", "messages", "data"),
            ("ConditionalRegion", "output", "output0", "value", "data"),
        },
        "parameters": {"project": {"in_features": 4, "out_features": 4}},
        "warnings": ["Unknown constructor model.GraphAttentionKernel", "Unsupported control/state region ConditionalRegion"],
    },
    "DynamicStateSpace": {
        "nodes": {
            "input.sequence": ("Input", "input", "source"),
            "root": ("Module", "container", "source"),
            "scan": ("StateSpaceScan", "opaque", "opaque"),
            "DynamicLoop": ("DynamicLoop", "opaque", "opaque"),
            "output0": ("Output", "output", "source"),
        },
        "relations": {
            ("input.sequence", "sequence", "root", "sequence", "data"),
            ("input.sequence", "sequence", "scan", "arg0", "data"),
            ("input.sequence", "sequence", "DynamicLoop", "sequence", "data"),
            ("scan", "output", "DynamicLoop", "state", "data"),
            ("DynamicLoop", "output", "output0", "value", "data"),
        },
        "parameters": {},
        "warnings": ["Unknown constructor model.StateSpaceScan", "Unsupported control/state region DynamicLoop"],
    },
}
