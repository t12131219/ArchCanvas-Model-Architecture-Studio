from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Literal

from archcanvas_core.builtin_registry import BuiltinModuleRegistry
from archcanvas_core.models import Diagnostic, DraftGraphDocument, DraftNode
from archcanvas_core.module_contract import ModuleDefinition

Dimension = int | str | None


@dataclass(frozen=True)
class Shape:
    dimensions: tuple[Dimension, ...]
    layout: str = "any"
    dtype: str | None = None


@dataclass(frozen=True)
class ValueState:
    status: Literal["known", "unknown", "blocked"]
    shape: Shape | None = None
    reason: str | None = None
    diagnostic_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class Cost:
    parameter_count: str | None = None
    flops: str | None = None
    assumptions: tuple[str, ...] = ()


@dataclass(frozen=True)
class DraftAnalysis:
    node_shapes: dict[str, dict[str, ValueState]]
    node_costs: dict[str, Cost]
    diagnostics: list[Diagnostic]
    graph_cost: Cost


@dataclass
class _RuleResult:
    outputs: dict[str, ValueState]
    diagnostics: list[Diagnostic] = field(default_factory=list)
    cost: Cost = field(default_factory=Cost)


def _diagnostic(code: str, message: str, node_id: str, *targets: str) -> Diagnostic:
    return Diagnostic(
        code=code,
        severity="blocking",
        message=message,
        target_ids=[node_id, *targets],
    )


def _warning(code: str, message: str, node_id: str) -> Diagnostic:
    return Diagnostic(code=code, severity="warning", message=message, target_ids=[node_id])


def _known(shape: Shape) -> ValueState:
    return ValueState(status="known", shape=shape)


def _unknown(reason: str) -> ValueState:
    return ValueState(status="unknown", reason=reason)


def _blocked(diagnostics: list[Diagnostic]) -> ValueState:
    return ValueState(
        status="blocked",
        diagnostic_ids=tuple(
            f"diagnostic:{item.code.lower()}:{':'.join(item.target_ids)}"
            for item in diagnostics
        ),
    )


def _outputs(definition: ModuleDefinition) -> list[str]:
    return [item.port_id for item in definition.ports if item.direction == "output"]


def _forward(definition: ModuleDefinition, value: ValueState) -> _RuleResult:
    return _RuleResult(outputs={name: value for name in _outputs(definition)})


def _integer(node: DraftNode, name: str, default: int | None = None) -> int | None:
    value = node.parameters.get(name, default)
    return value if isinstance(value, int) and not isinstance(value, bool) and value > 0 else None


def _pair(value: object, default: int | None = None, *, allow_zero: bool = False) -> tuple[int, int] | None:
    if value is None:
        return (default, default) if default is not None else None
    minimum = 0 if allow_zero else 1
    if isinstance(value, int) and not isinstance(value, bool) and value >= minimum:
        return value, value
    if (
        isinstance(value, (list, tuple))
        and len(value) == 2
        and all(
            isinstance(item, int) and not isinstance(item, bool) and item >= minimum
            for item in value
        )
    ):
        return int(value[0]), int(value[1])
    return None


def _shape_parameter(value: object) -> Shape | None:
    values = value if isinstance(value, (list, tuple)) else [value]
    if not values:
        return None
    dimensions: list[Dimension] = []
    for item in values:
        if isinstance(item, int) and not isinstance(item, bool) and item > 0:
            dimensions.append(item)
        elif isinstance(item, str) and item.strip():
            dimensions.append(item.strip())
        else:
            return None
    return Shape(tuple(dimensions))


def _text(value: Dimension) -> str:
    return "?" if value is None else str(value)


def _product(values: tuple[Dimension, ...]) -> str | None:
    return None if any(item is None for item in values) else "*".join(map(_text, values)) or "1"


def _conv_dimension(value: Dimension, kernel: int, stride: int, padding: int, dilation: int) -> Dimension:
    if isinstance(value, int):
        return math.floor((value + 2 * padding - dilation * (kernel - 1) - 1) / stride + 1)
    return f"floor(({_text(value)}+{2 * padding}-{dilation}*({kernel}-1)-1)/{stride}+1)"


def _input(node: DraftNode, definition: ModuleDefinition) -> _RuleResult:
    shape = _shape_parameter(node.parameters.get("shape"))
    if shape is None:
        errors = [_diagnostic("INPUT_SHAPE_REQUIRED", "Tensor Input requires a non-empty valid shape parameter.", node.node_id)]
        return _RuleResult({name: _blocked(errors) for name in _outputs(definition)}, errors)
    return _RuleResult({"output": _known(shape)})


def _identity(definition: ModuleDefinition, inputs: dict[str, list[ValueState]]) -> _RuleResult:
    return _forward(definition, (inputs.get("input") or [_unknown("input is unavailable")])[0])


def _linear(node: DraftNode, definition: ModuleDefinition, inputs: dict[str, list[ValueState]]) -> _RuleResult:
    value = (inputs.get("input") or [_unknown("Linear input is unavailable")])[0]
    if value.status != "known" or value.shape is None:
        return _forward(definition, value)
    in_features = _integer(node, "in_features")
    out_features = _integer(node, "out_features")
    errors: list[Diagnostic] = []
    if not value.shape.dimensions:
        errors.append(_diagnostic("LINEAR_RANK_INVALID", "Linear input must have at least one dimension.", node.node_id))
    elif in_features and isinstance(value.shape.dimensions[-1], int) and value.shape.dimensions[-1] != in_features:
        errors.append(_diagnostic("LINEAR_FEATURE_MISMATCH", f"Linear expects {in_features} input features but receives {value.shape.dimensions[-1]}.", node.node_id))
    if not in_features or not out_features:
        errors.append(_diagnostic("LINEAR_PARAMETER_INVALID", "Linear features must be positive integers.", node.node_id))
    if errors or out_features is None:
        return _RuleResult({"output": _blocked(errors)}, errors)
    output = Shape((*value.shape.dimensions[:-1], out_features), value.shape.layout, value.shape.dtype)
    elements = _product(output.dimensions)
    return _RuleResult(
        {"output": _known(output)},
        cost=Cost(
            parameter_count=(str(in_features * out_features + (0 if node.parameters.get("bias") is False else out_features)) if in_features else None),
            flops=(f"{elements}*{2 * in_features}" if elements and in_features else None),
            assumptions=("multiply-add counted as two FLOPs",),
        ),
    )


def _conv2d(node: DraftNode, inputs: dict[str, list[ValueState]]) -> _RuleResult:
    value = (inputs.get("input") or [_unknown("Conv2d input is unavailable")])[0]
    if value.status != "known" or value.shape is None:
        return _RuleResult({"output": value})
    shape = value.shape
    in_channels = _integer(node, "in_channels")
    out_channels = _integer(node, "out_channels")
    groups = _integer(node, "groups", 1)
    kernel = _pair(node.parameters.get("kernel_size"))
    stride = _pair(node.parameters.get("stride"), 1)
    padding = _pair(node.parameters.get("padding"), 0, allow_zero=True)
    dilation = _pair(node.parameters.get("dilation"), 1)
    errors: list[Diagnostic] = []
    if len(shape.dimensions) != 4:
        errors.append(_diagnostic("CONV2D_RANK_MISMATCH", "Conv2d input must have rank 4.", node.node_id))
    elif in_channels and isinstance(shape.dimensions[1], int) and shape.dimensions[1] != in_channels:
        errors.append(_diagnostic("CONV2D_CHANNEL_MISMATCH", f"Conv2d expects {in_channels} channels but receives {shape.dimensions[1]}.", node.node_id))
    if not all((in_channels, out_channels, groups, kernel, stride, padding, dilation)):
        errors.append(_diagnostic("CONV2D_PARAMETER_INVALID", "Conv2d parameters are incomplete or invalid.", node.node_id))
    elif in_channels % groups or out_channels % groups:
        errors.append(_diagnostic("CONV2D_GROUP_MISMATCH", "Conv2d groups must divide input and output channels.", node.node_id))
    if errors or None in (out_channels, groups, kernel, stride, padding, dilation) or len(shape.dimensions) != 4:
        return _RuleResult({"output": _blocked(errors)}, errors)
    assert out_channels and groups and kernel and stride and padding and dilation
    output = Shape(
        (
            shape.dimensions[0],
            out_channels,
            _conv_dimension(shape.dimensions[2], kernel[0], stride[0], padding[0], dilation[0]),
            _conv_dimension(shape.dimensions[3], kernel[1], stride[1], padding[1], dilation[1]),
        ),
        "NCHW",
        shape.dtype,
    )
    if any(isinstance(item, int) and item <= 0 for item in output.dimensions[2:]):
        errors = [
            _diagnostic(
                "CONV2D_OUTPUT_INVALID",
                "Conv2d parameters produce a non-positive spatial dimension.",
                node.node_id,
            )
        ]
        return _RuleResult({"output": _blocked(errors)}, errors)
    count = out_channels * ((in_channels or 1) // groups) * kernel[0] * kernel[1]
    if node.parameters.get("bias") is not False:
        count += out_channels
    return _RuleResult(
        {"output": _known(output)},
        cost=Cost(
            parameter_count=str(count),
            flops=f"{_product(output.dimensions)}*{((in_channels or 1) // groups) * kernel[0] * kernel[1] * 2}",
            assumptions=("multiply-add counted as two FLOPs",),
        ),
    )


def _broadcast_dimension(left: Dimension, right: Dimension) -> Dimension | Literal[False]:
    if left == right:
        return left
    if left == 1:
        return right
    if right == 1:
        return left
    if left is None or right is None:
        return None
    if isinstance(left, str) or isinstance(right, str):
        return f"broadcast({_text(left)},{_text(right)})"
    return False


def _broadcast(node: DraftNode, definition: ModuleDefinition, inputs: dict[str, list[ValueState]]) -> _RuleResult:
    values = inputs.get("operands", [])
    unavailable = next((item for item in values if item.status != "known"), None)
    if unavailable:
        return _forward(definition, unavailable)
    shapes = [item.shape for item in values if item.shape is not None]
    if not shapes:
        return _forward(definition, _unknown("Add operands are unavailable"))
    result = list(shapes[0].dimensions)
    for shape in shapes[1:]:
        rank = max(len(result), len(shape.dimensions))
        left = [1] * (rank - len(result)) + result
        right = [1] * (rank - len(shape.dimensions)) + list(shape.dimensions)
        merged = [_broadcast_dimension(a, b) for a, b in zip(left, right, strict=True)]
        if any(item is False for item in merged):
            errors = [_diagnostic("BROADCAST_SHAPE_MISMATCH", "Add operands are not broadcast compatible.", node.node_id)]
            return _RuleResult({"output": _blocked(errors)}, errors)
        result = [None if item is False else item for item in merged]
    output = Shape(tuple(result), shapes[0].layout, shapes[0].dtype)
    elements = _product(output.dimensions)
    return _RuleResult(
        {"output": _known(output)},
        cost=Cost(flops=f"{elements}*{max(1, len(shapes) - 1)}" if elements else None),
    )


def _reshape(node: DraftNode, definition: ModuleDefinition, inputs: dict[str, list[ValueState]]) -> _RuleResult:
    value = (inputs.get("input") or [_unknown("Reshape input is unavailable")])[0]
    if value.status != "known" or value.shape is None:
        return _forward(definition, value)
    raw = node.parameters.get("shape")
    raw_values = list(raw) if isinstance(raw, (list, tuple)) else [raw]
    inferred = [index for index, item in enumerate(raw_values) if item == -1]
    invalid = not raw_values or len(inferred) > 1 or any(
        not (
            isinstance(item, int)
            and not isinstance(item, bool)
            and (item == -1 or item > 0)
            or isinstance(item, str)
            and bool(item.strip())
        )
        for item in raw_values
    )
    if invalid:
        errors = [_diagnostic("RESHAPE_TARGET_INVALID", "Reshape requires non-zero dimensions and at most one inferred -1 dimension.", node.node_id)]
        return _RuleResult({"output": _blocked(errors)}, errors)
    dimensions: list[Dimension] = [None if item == -1 else item.strip() if isinstance(item, str) else item for item in raw_values]
    if inferred:
        source_product = _product(value.shape.dimensions)
        known_product = _product(tuple(item for index, item in enumerate(dimensions) if index != inferred[0]))
        if source_product and known_product:
            dimensions[inferred[0]] = f"({source_product})/({known_product})"
    elif all(isinstance(item, int) for item in value.shape.dimensions + tuple(dimensions)):
        source_count = math.prod(value.shape.dimensions)  # type: ignore[arg-type]
        target_count = math.prod(dimensions)  # type: ignore[arg-type]
        if source_count != target_count:
            errors = [_diagnostic("RESHAPE_ELEMENT_MISMATCH", "Reshape changes the number of tensor elements.", node.node_id)]
            return _RuleResult({"output": _blocked(errors)}, errors)
    return _RuleResult({"output": _known(Shape(tuple(dimensions), "any", value.shape.dtype))})


def _pool2d(node: DraftNode, definition: ModuleDefinition, inputs: dict[str, list[ValueState]]) -> _RuleResult:
    value = (inputs.get("input") or [_unknown("MaxPool2d input is unavailable")])[0]
    if value.status != "known" or value.shape is None:
        return _forward(definition, value)
    kernel = _pair(node.parameters.get("kernel_size"))
    stride = kernel if node.parameters.get("stride") is None else _pair(node.parameters.get("stride"))
    padding = _pair(node.parameters.get("padding"), 0, allow_zero=True)
    errors: list[Diagnostic] = []
    if len(value.shape.dimensions) != 4:
        errors.append(_diagnostic("POOL2D_RANK_MISMATCH", "MaxPool2d input must have rank 4.", node.node_id))
    if not kernel or not stride or not padding:
        errors.append(_diagnostic("POOL2D_PARAMETER_INVALID", "MaxPool2d parameters are incomplete or invalid.", node.node_id))
    if errors or len(value.shape.dimensions) != 4 or not kernel or not stride or not padding:
        return _RuleResult({"output": _blocked(errors)}, errors)
    shape = value.shape
    output = Shape(
        (
            shape.dimensions[0],
            shape.dimensions[1],
            _conv_dimension(shape.dimensions[2], kernel[0], stride[0], padding[0], 1),
            _conv_dimension(shape.dimensions[3], kernel[1], stride[1], padding[1], 1),
        ),
        "NCHW",
        shape.dtype,
    )
    elements = _product(output.dimensions)
    return _RuleResult(
        {"output": _known(output)},
        cost=Cost(
            flops=f"{elements}*{kernel[0] * kernel[1]}" if elements else None,
            assumptions=("one comparison per pooling element",),
        ),
    )


def _embedding(node: DraftNode, definition: ModuleDefinition, inputs: dict[str, list[ValueState]]) -> _RuleResult:
    value = (inputs.get("input") or [_unknown("Embedding input is unavailable")])[0]
    if value.status != "known" or value.shape is None:
        return _forward(definition, value)
    count = _integer(node, "num_embeddings")
    width = _integer(node, "embedding_dim")
    if not count or not width:
        errors = [_diagnostic("EMBEDDING_PARAMETER_INVALID", "Embedding dimensions must be positive integers.", node.node_id)]
        return _RuleResult({"output": _blocked(errors)}, errors)
    return _RuleResult(
        {"output": _known(Shape((*value.shape.dimensions, width), value.shape.layout, value.shape.dtype))},
        cost=Cost(parameter_count=str(count * width), assumptions=("embedding lookup has no arithmetic FLOP estimate",)),
    )


def _layernorm(node: DraftNode, definition: ModuleDefinition, inputs: dict[str, list[ValueState]]) -> _RuleResult:
    value = (inputs.get("input") or [_unknown("LayerNorm input is unavailable")])[0]
    if value.status != "known" or value.shape is None:
        return _forward(definition, value)
    normalized = _shape_parameter(node.parameters.get("normalized_shape"))
    errors: list[Diagnostic] = []
    if normalized is None or len(normalized.dimensions) > len(value.shape.dimensions):
        errors.append(_diagnostic("LAYERNORM_SHAPE_INVALID", "LayerNorm normalized_shape must match an input suffix.", node.node_id))
    elif any(
        isinstance(left, int) and isinstance(right, int) and left != right
        for left, right in zip(
            value.shape.dimensions[-len(normalized.dimensions) :],
            normalized.dimensions,
            strict=True,
        )
    ):
        errors.append(_diagnostic("LAYERNORM_SHAPE_MISMATCH", "LayerNorm normalized_shape does not match the input suffix.", node.node_id))
    if errors or normalized is None:
        return _RuleResult({"output": _blocked(errors)}, errors)
    normalized_count = _product(normalized.dimensions)
    output_count = _product(value.shape.dimensions)
    return _RuleResult(
        {"output": value},
        cost=Cost(
            parameter_count=(None if node.parameters.get("elementwise_affine") is False or not normalized_count else f"{normalized_count}*2"),
            flops=f"{output_count}*5" if output_count else None,
            assumptions=("LayerNorm estimated as five elementwise operations",),
        ),
    )


def _mha(node: DraftNode, definition: ModuleDefinition, inputs: dict[str, list[ValueState]]) -> _RuleResult:
    values = [(inputs.get(name) or [_unknown(f"{name} input is unavailable")])[0] for name in ("query", "key", "value")]
    unavailable = next((item for item in values if item.status != "known" or item.shape is None), None)
    if unavailable:
        return _forward(definition, unavailable)
    shapes = [item.shape for item in values if item.shape is not None]
    embed = _integer(node, "embed_dim")
    heads = _integer(node, "num_heads")
    errors: list[Diagnostic] = []
    if any(len(shape.dimensions) != 3 for shape in shapes):
        errors.append(_diagnostic("MHA_RANK_MISMATCH", "MultiheadAttention query, key, and value must have rank 3.", node.node_id))
    if not embed or not heads or embed % heads:
        errors.append(_diagnostic("MHA_PARAMETER_INVALID", "MultiheadAttention embed_dim must be divisible by num_heads.", node.node_id))
    if embed and any(isinstance(shape.dimensions[-1], int) and shape.dimensions[-1] != embed for shape in shapes):
        errors.append(_diagnostic("MHA_EMBED_MISMATCH", f"MultiheadAttention expects embedding width {embed}.", node.node_id))
    batch_index = 0 if node.parameters.get("batch_first") is True else 1
    sequence_index = 1 if node.parameters.get("batch_first") is True else 0
    if len(shapes) == 3 and all(len(shape.dimensions) == 3 for shape in shapes):
        if not (shapes[0].dimensions[batch_index] == shapes[1].dimensions[batch_index] == shapes[2].dimensions[batch_index]):
            errors.append(_diagnostic("MHA_BATCH_MISMATCH", "MultiheadAttention batch dimensions must match.", node.node_id))
        if shapes[1].dimensions[sequence_index] != shapes[2].dimensions[sequence_index]:
            errors.append(_diagnostic("MHA_KEY_VALUE_LENGTH_MISMATCH", "MultiheadAttention key and value sequence lengths must match.", node.node_id))
    if errors or not embed or len(shapes) != 3 or any(len(shape.dimensions) != 3 for shape in shapes):
        state = _blocked(errors)
        return _RuleResult({name: state for name in _outputs(definition)}, errors)
    batch = shapes[0].dimensions[batch_index]
    query_length = shapes[0].dimensions[sequence_index]
    key_length = shapes[1].dimensions[sequence_index]
    weights = Shape((batch, query_length, key_length), "any", shapes[0].dtype)
    return _RuleResult(
        {"context": _known(shapes[0]), "weights": _known(weights)},
        cost=Cost(
            parameter_count=str(4 * embed * embed + 4 * embed),
            flops=f"{_text(batch)}*({_text(query_length)}+{_text(key_length)})*{4 * embed * embed}+{_text(batch)}*{_text(query_length)}*{_text(key_length)}*{4 * embed}",
            assumptions=("dense QKV/output projections and attention matmuls included",),
        ),
    )


def _lstm(node: DraftNode, definition: ModuleDefinition, inputs: dict[str, list[ValueState]]) -> _RuleResult:
    value = (inputs.get("input") or [_unknown("LSTM input is unavailable")])[0]
    if value.status != "known" or value.shape is None:
        return _forward(definition, value)
    input_size = _integer(node, "input_size")
    hidden_size = _integer(node, "hidden_size")
    layers = _integer(node, "num_layers", 1)
    directions = 2 if node.parameters.get("bidirectional") is True else 1
    errors: list[Diagnostic] = []
    if len(value.shape.dimensions) != 3:
        errors.append(_diagnostic("LSTM_RANK_MISMATCH", "LSTM input must have rank 3.", node.node_id))
    if input_size and value.shape.dimensions and isinstance(value.shape.dimensions[-1], int) and value.shape.dimensions[-1] != input_size:
        errors.append(_diagnostic("LSTM_INPUT_SIZE_MISMATCH", f"LSTM expects input_size {input_size}.", node.node_id))
    if not input_size or not hidden_size or not layers:
        errors.append(_diagnostic("LSTM_PARAMETER_INVALID", "LSTM sizes must be positive integers.", node.node_id))
    if errors or not input_size or not hidden_size or not layers or len(value.shape.dimensions) != 3:
        state = _blocked(errors)
        return _RuleResult({name: state for name in _outputs(definition)}, errors)
    batch_index = 0 if node.parameters.get("batch_first") is True else 1
    sequence_index = 1 if node.parameters.get("batch_first") is True else 0
    batch = value.shape.dimensions[batch_index]
    sequence = Shape((*value.shape.dimensions[:-1], hidden_size * directions), "sequence", value.shape.dtype)
    state_shape = Shape((layers * directions, batch, hidden_size), "sequence", value.shape.dtype)
    parameters = sum(
        directions * 4 * hidden_size * ((input_size if layer == 0 else hidden_size * directions) + hidden_size + 2)
        for layer in range(layers)
    )
    return _RuleResult(
        {"sequence": _known(sequence), "hn": _known(state_shape), "cn": _known(state_shape)},
        cost=Cost(
            parameter_count=str(parameters),
            flops=f"{_text(batch)}*{_text(value.shape.dimensions[sequence_index])}*{parameters * 2}",
            assumptions=("LSTM gate multiply-adds estimated from recurrent parameter matrices",),
        ),
    )


def _run_rule(node: DraftNode, definition: ModuleDefinition, inputs: dict[str, list[ValueState]]) -> _RuleResult:
    rule = definition.shape_rule_id
    if rule == "shape.input.v1":
        return _input(node, definition)
    if rule == "shape.conv2d.v1":
        return _conv2d(node, inputs)
    if rule == "shape.linear.v1":
        return _linear(node, definition, inputs)
    if rule == "shape.broadcast.v1":
        return _broadcast(node, definition, inputs)
    if rule == "shape.reshape.v1":
        return _reshape(node, definition, inputs)
    if rule == "shape.pool2d.v1":
        return _pool2d(node, definition, inputs)
    if rule == "shape.embedding.v1":
        return _embedding(node, definition, inputs)
    if rule == "shape.multihead-attention.v1":
        return _mha(node, definition, inputs)
    if rule == "shape.lstm.v1":
        return _lstm(node, definition, inputs)
    if rule == "shape.identity.v1":
        return _layernorm(node, definition, inputs) if definition.definition_id == "pytorch.nn.layernorm" else _identity(definition, inputs)
    warning = _warning("SHAPE_RULE_UNAVAILABLE", f"Shape rule {rule or 'none'} is unavailable in the server analyzer.", node.node_id)
    return _RuleResult({name: _unknown(warning.message) for name in _outputs(definition)}, [warning])


def analyze_draft_graph(
    graph: DraftGraphDocument,
    registry: BuiltinModuleRegistry,
) -> DraftAnalysis:
    nodes = {node.node_id: node for node in graph.nodes}
    ports = {
        port.port_id: (node, port)
        for node in graph.nodes
        for port in node.ports
    }
    incoming: dict[str, list[Any]] = {}
    adjacency: dict[str, set[str]] = {node_id: set() for node_id in nodes}
    indegree = dict.fromkeys(nodes, 0)
    for edge in sorted(graph.edges, key=lambda item: item.edge_id):
        source = ports.get(edge.source_port_id)
        target = ports.get(edge.target_port_id)
        if target is not None:
            incoming.setdefault(edge.target_port_id, []).append(edge)
        if source is not None and target is not None and source[0].node_id != target[0].node_id:
            source_id = source[0].node_id
            target_id = target[0].node_id
            if target_id not in adjacency[source_id]:
                adjacency[source_id].add(target_id)
                indegree[target_id] += 1

    ready = sorted(node_id for node_id, count in indegree.items() if count == 0)
    shapes: dict[str, dict[str, ValueState]] = {}
    costs: dict[str, Cost] = {}
    diagnostics: list[Diagnostic] = []
    while ready:
        node_id = ready.pop(0)
        node = nodes[node_id]
        if node.definition_ref is None:
            error = _diagnostic("DEFINITION_REF_MISSING", "Draft node has no exact module definition.", node_id)
            diagnostics.append(error)
            shapes[node_id] = {}
            costs[node_id] = Cost()
        else:
            definition = registry.resolve_ref(
                node.definition_ref.definition_id,
                node.definition_ref.version,
                node.definition_ref.digest,
            )
            if definition is None:
                error = _diagnostic("DEFINITION_REF_STALE", "Draft node module definition is unavailable or stale.", node_id)
                diagnostics.append(error)
                shapes[node_id] = {}
                costs[node_id] = Cost()
            else:
                inputs: dict[str, list[ValueState]] = {}
                for port in (item for item in node.ports if item.direction == "input"):
                    contract_id = port.definition_port_id or port.name
                    edges = sorted(
                        incoming.get(port.port_id, []),
                        key=lambda item: (
                            item.target_ordinal if item.target_ordinal is not None else 2**63,
                            item.edge_id,
                        ),
                    )
                    values: list[ValueState] = []
                    for edge in edges:
                        source = ports.get(edge.source_port_id)
                        if source is None:
                            values.append(_unknown("canonical upstream shape is unavailable in the draft analyzer"))
                            continue
                        source_node, source_port = source
                        source_contract = source_port.definition_port_id or source_port.name
                        values.append(
                            shapes.get(source_node.node_id, {}).get(
                                source_contract,
                                _unknown("upstream output has not been analyzed"),
                            )
                        )
                    inputs[contract_id] = values
                contract_errors: list[Diagnostic] = []
                for port in (item for item in node.ports if item.direction == "input"):
                    contract_id = port.definition_port_id or port.name
                    for value in inputs.get(contract_id, []):
                        if value.status != "known" or value.shape is None:
                            continue
                        if port.tensor_ranks and len(value.shape.dimensions) not in port.tensor_ranks:
                            contract_errors.append(
                                _diagnostic(
                                    "PORT_TENSOR_RANK_INVALID",
                                    f"{port.name} rejects rank {len(value.shape.dimensions)}.",
                                    node_id,
                                    port.port_id,
                                )
                            )
                        if (
                            port.tensor_layouts
                            and value.shape.layout != "any"
                            and "any" not in port.tensor_layouts
                            and value.shape.layout not in port.tensor_layouts
                        ):
                            contract_errors.append(
                                _diagnostic(
                                    "PORT_TENSOR_LAYOUT_INVALID",
                                    f"{port.name} rejects {value.shape.layout} layout.",
                                    node_id,
                                    port.port_id,
                                )
                            )
                result = (
                    _RuleResult(
                        {
                            name: _blocked(contract_errors)
                            for name in _outputs(definition)
                        },
                        contract_errors,
                    )
                    if contract_errors
                    else _run_rule(node, definition, inputs)
                )
                shapes[node_id] = result.outputs
                costs[node_id] = result.cost
                diagnostics.extend(result.diagnostics)
        for target_id in sorted(adjacency[node_id]):
            indegree[target_id] -= 1
            if indegree[target_id] == 0:
                ready.append(target_id)
        ready.sort()

    parameter_terms = [item.parameter_count for item in costs.values() if item.parameter_count]
    flop_terms = [item.flops for item in costs.values() if item.flops]
    assumptions = tuple(dict.fromkeys(value for item in costs.values() for value in item.assumptions))
    return DraftAnalysis(
        node_shapes=shapes,
        node_costs=costs,
        diagnostics=sorted(diagnostics, key=lambda item: (item.code, item.target_ids)),
        graph_cost=Cost(
            parameter_count="+".join(parameter_terms) or None,
            flops="+".join(flop_terms) or None,
            assumptions=assumptions,
        ),
    )
