from __future__ import annotations

from .digest_protocol import domain_digest
from .module_contract import (
    MODULE_REGISTRY_DIGEST_DOMAIN,
    ModuleDefinition,
    ModuleRegistryBundle,
    ParameterContract,
    PortContract,
    define_module,
    registry_bundle_payload,
)


def _input(
    port_id: str,
    *,
    required: bool = True,
    ranks: list[int] | None = None,
    layouts: list[str] | None = None,
) -> PortContract:
    return PortContract(
        port_id=port_id,
        direction="input",
        required=required,
        min_connections=1 if required else 0,
        max_connections=1,
        tensor_ranks=ranks or [],
        tensor_layouts=layouts or [],  # type: ignore[arg-type]
    )


def _output(
    port_id: str,
    *,
    ranks: list[int] | None = None,
    layouts: list[str] | None = None,
) -> PortContract:
    return PortContract(
        port_id=port_id,
        direction="output",
        min_connections=0,
        max_connections="many",
        tensor_ranks=ranks or [],
        tensor_layouts=layouts or [],  # type: ignore[arg-type]
    )


def _parameter(
    parameter_id: str,
    value_type: str,
    positional_index: int | None,
    *,
    required: bool = False,
    default: object = None,
    affects: list[str] | None = None,
) -> ParameterContract:
    return ParameterContract(
        parameter_id=parameter_id,
        value_type=value_type,  # type: ignore[arg-type]
        positional_index=positional_index,
        required=required,
        default=default,
        affects=affects or ["shape", "cost", "code", "visual"],  # type: ignore[arg-type]
    )


BUILTIN_MODULE_DEFINITIONS: list[ModuleDefinition] = [
    define_module(
        definition_id="archcanvas.input.tensor",
        version="1.0.0",
        semantic_kind="input",
        qualified_names=["archcanvas.input.Tensor"],
        ports=[_output("output")],
        parameters=[_parameter("shape", "shape", None, required=True)],
        glyph_id="io.input",
        shape_rule_id="shape.input.v1",
    ),
    define_module(
        definition_id="pytorch.nn.linear",
        version="1.0.0",
        semantic_kind="linear",
        qualified_names=["torch.nn.Linear", "torch.nn.modules.linear.Linear"],
        ports=[_input("input", ranks=[1, 2, 3, 4]), _output("output", ranks=[1, 2, 3, 4])],
        parameters=[
            _parameter("in_features", "integer", 0, required=True),
            _parameter("out_features", "integer", 1, required=True),
            _parameter("bias", "boolean", 2, default=True),
        ],
        glyph_id="linear",
        shape_rule_id="shape.linear.v1",
        cost_rule_id="cost.linear.v1",
        codegen_rule_id="codegen.pytorch.linear.v1",
    ),
    define_module(
        definition_id="pytorch.nn.conv2d",
        version="1.0.0",
        semantic_kind="convolution",
        qualified_names=["torch.nn.Conv2d", "torch.nn.modules.conv.Conv2d"],
        ports=[_input("input", ranks=[4], layouts=["NCHW"]), _output("output", ranks=[4], layouts=["NCHW"])],
        parameters=[
            _parameter("in_channels", "integer", 0, required=True),
            _parameter("out_channels", "integer", 1, required=True),
            _parameter("kernel_size", "shape", 2, required=True),
            _parameter("stride", "shape", 3, default=1),
            _parameter("padding", "shape", 4, default=0),
            _parameter("dilation", "shape", 5, default=1),
            _parameter("groups", "integer", 6, default=1),
            _parameter("bias", "boolean", 7, default=True),
        ],
        glyph_id="conv2d",
        detail_template_id="convolution",
        shape_rule_id="shape.conv2d.v1",
        cost_rule_id="cost.conv2d.v1",
        codegen_rule_id="codegen.pytorch.conv2d.v1",
    ),
    define_module(
        definition_id="pytorch.nn.maxpool2d",
        version="1.0.0",
        semantic_kind="pooling",
        qualified_names=["torch.nn.MaxPool2d", "torch.nn.modules.pooling.MaxPool2d"],
        ports=[_input("input", ranks=[4], layouts=["NCHW"]), _output("output", ranks=[4], layouts=["NCHW"])],
        parameters=[
            _parameter("kernel_size", "shape", 0, required=True),
            _parameter("stride", "shape", 1),
            _parameter("padding", "shape", 2, default=0),
        ],
        glyph_id="maxpool2d",
        detail_template_id="pooling",
        shape_rule_id="shape.pool2d.v1",
        cost_rule_id="cost.pool2d.v1",
        codegen_rule_id="codegen.pytorch.maxpool2d.v1",
    ),
    define_module(
        definition_id="pytorch.nn.relu",
        version="1.0.0",
        semantic_kind="activation",
        qualified_names=["torch.nn.ReLU", "torch.nn.modules.activation.ReLU", "torch.relu"],
        ports=[_input("input"), _output("output")],
        parameters=[_parameter("inplace", "boolean", 0, default=False)],
        glyph_id="relu",
        shape_rule_id="shape.identity.v1",
        cost_rule_id="cost.elementwise.v1",
        codegen_rule_id="codegen.pytorch.relu.v1",
    ),
    define_module(
        definition_id="pytorch.nn.gelu",
        version="1.0.0",
        semantic_kind="activation",
        qualified_names=["torch.nn.GELU", "torch.nn.modules.activation.GELU", "torch.nn.functional.gelu"],
        ports=[_input("input"), _output("output")],
        parameters=[_parameter("approximate", "string", 0, default="none")],
        glyph_id="gelu",
        shape_rule_id="shape.identity.v1",
        cost_rule_id="cost.elementwise.v1",
        codegen_rule_id="codegen.pytorch.gelu.v1",
    ),
    define_module(
        definition_id="pytorch.op.add",
        version="1.0.0",
        semantic_kind="add",
        qualified_names=["torch.add", "operator.add"],
        ports=[
            PortContract(
                port_id="operands",
                direction="input",
                min_connections=2,
                max_connections="many",
                ordering="unordered",
            ),
            _output("output"),
        ],
        glyph_id="add",
        shape_rule_id="shape.broadcast.v1",
        cost_rule_id="cost.elementwise.v1",
        codegen_rule_id="codegen.pytorch.add.v1",
    ),
    define_module(
        definition_id="pytorch.nn.layernorm",
        version="1.0.0",
        semantic_kind="normalization",
        qualified_names=["torch.nn.LayerNorm", "torch.nn.modules.normalization.LayerNorm"],
        ports=[_input("input"), _output("output")],
        parameters=[
            _parameter("normalized_shape", "shape", 0, required=True),
            _parameter("eps", "number", 1, default="1e-5"),
            _parameter("elementwise_affine", "boolean", 2, default=True),
        ],
        glyph_id="layernorm",
        detail_template_id="normalization",
        shape_rule_id="shape.identity.v1",
        cost_rule_id="cost.layernorm.v1",
        codegen_rule_id="codegen.pytorch.layernorm.v1",
    ),
    define_module(
        definition_id="pytorch.nn.dropout",
        version="1.0.0",
        semantic_kind="regularization",
        qualified_names=["torch.nn.Dropout", "torch.nn.modules.dropout.Dropout", "torch.nn.functional.dropout"],
        ports=[_input("input"), _output("output")],
        parameters=[
            _parameter("p", "number", 0, default="0.5"),
            _parameter("inplace", "boolean", 1, default=False),
        ],
        glyph_id="dropout",
        shape_rule_id="shape.identity.v1",
        codegen_rule_id="codegen.pytorch.dropout.v1",
    ),
    define_module(
        definition_id="pytorch.op.reshape",
        version="1.0.0",
        semantic_kind="shape-transform",
        qualified_names=["torch.reshape", "torch.Tensor.reshape", "torch.Tensor.view"],
        ports=[_input("input"), _output("output")],
        parameters=[_parameter("shape", "shape", 1, required=True)],
        glyph_id="reshape",
        shape_rule_id="shape.reshape.v1",
        codegen_rule_id="codegen.pytorch.reshape.v1",
    ),
    define_module(
        definition_id="pytorch.op.transpose",
        version="1.0.0",
        semantic_kind="shape-transform",
        qualified_names=["torch.transpose", "torch.Tensor.transpose", "torch.Tensor.permute"],
        ports=[_input("input"), _output("output")],
        glyph_id="transpose",
        shape_rule_id="shape.transpose.v1",
        codegen_rule_id="codegen.pytorch.transpose.v1",
    ),
    define_module(
        definition_id="pytorch.nn.embedding",
        version="1.0.0",
        semantic_kind="embedding",
        qualified_names=["torch.nn.Embedding", "torch.nn.modules.sparse.Embedding"],
        ports=[_input("input"), _output("output")],
        parameters=[
            _parameter("num_embeddings", "integer", 0, required=True),
            _parameter("embedding_dim", "integer", 1, required=True),
        ],
        glyph_id="embedding",
        detail_template_id="embedding",
        shape_rule_id="shape.embedding.v1",
        cost_rule_id="cost.embedding.v1",
        codegen_rule_id="codegen.pytorch.embedding.v1",
    ),
    define_module(
        definition_id="pytorch.nn.multiheadattention",
        version="1.0.0",
        semantic_kind="attention",
        qualified_names=["torch.nn.MultiheadAttention", "torch.nn.modules.activation.MultiheadAttention"],
        ports=[
            _input("query", ranks=[3], layouts=["sequence"]),
            _input("key", ranks=[3], layouts=["sequence"]),
            _input("value", ranks=[3], layouts=["sequence"]),
            _input("key_padding_mask", required=False),
            _input("attention_mask", required=False),
            _output("context", ranks=[3], layouts=["sequence"]),
            _output("weights", ranks=[3]),
        ],
        parameters=[
            _parameter("embed_dim", "integer", 0, required=True),
            _parameter("num_heads", "integer", 1, required=True),
            _parameter("dropout", "number", 2, default="0.0"),
            _parameter("batch_first", "boolean", None, default=False),
        ],
        glyph_id="multihead-attention",
        detail_template_id="attention",
        shape_rule_id="shape.multihead-attention.v1",
        cost_rule_id="cost.multihead-attention.v1",
        codegen_rule_id="codegen.pytorch.multihead-attention.v1",
    ),
    define_module(
        definition_id="pytorch.nn.lstm",
        version="1.0.0",
        semantic_kind="recurrent",
        qualified_names=["torch.nn.LSTM", "torch.nn.modules.rnn.LSTM"],
        ports=[
            _input("input", ranks=[3], layouts=["sequence"]),
            _input("initial_state", required=False),
            _output("sequence", ranks=[3], layouts=["sequence"]),
            _output("hn", ranks=[3], layouts=["sequence"]),
            _output("cn", ranks=[3], layouts=["sequence"]),
        ],
        parameters=[
            _parameter("input_size", "integer", 0, required=True),
            _parameter("hidden_size", "integer", 1, required=True),
            _parameter("num_layers", "integer", 2, default=1),
            _parameter("batch_first", "boolean", None, default=False),
            _parameter("bidirectional", "boolean", None, default=False),
        ],
        glyph_id="lstm",
        detail_template_id="recurrent",
        shape_rule_id="shape.lstm.v1",
        cost_rule_id="cost.lstm.v1",
        codegen_rule_id="codegen.pytorch.lstm.v1",
    ),
]


def builtin_registry_bundle() -> ModuleRegistryBundle:
    digest = domain_digest(
        MODULE_REGISTRY_DIGEST_DOMAIN,
        registry_bundle_payload(BUILTIN_MODULE_DEFINITIONS),
    )
    return ModuleRegistryBundle(
        bundle_id="registry:archcanvas-pytorch-v1",
        bundle_digest=digest,
        definitions=BUILTIN_MODULE_DEFINITIONS,
    )


class BuiltinModuleRegistry:
    def __init__(self, bundle: ModuleRegistryBundle | None = None) -> None:
        self.bundle = bundle or builtin_registry_bundle()
        self._by_qualified_name = {
            name: definition
            for definition in self.bundle.definitions
            for name in definition.qualified_names
        }
        self._by_ref = {
            (definition.definition_id, definition.version, definition.digest): definition
            for definition in self.bundle.definitions
        }

    def resolve_qualified_name(self, qualified_name: str) -> ModuleDefinition | None:
        return self._by_qualified_name.get(qualified_name)

    def resolve_ref(self, definition_id: str, version: str, digest: str) -> ModuleDefinition | None:
        return self._by_ref.get((definition_id, version, digest))
