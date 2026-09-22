"""Source-backed semantic signatures used by the Publication pattern registry.

This module deliberately does not create Architecture nodes.  It records a narrowly
defined source signature, with anchors, for a local module that is already present in
the Exact IR.  The Publication compiler consumes the resulting IR metadata only; it
never re-opens project source files.
"""

from __future__ import annotations

import ast
from collections.abc import Mapping
from dataclasses import dataclass, field
from hashlib import sha256

from archcanvas_core.models.source_identity import (
    AnchorKind,
    AnchorLocator,
    SourceAnchor,
    SourcePosition,
    SourceSpan,
)


@dataclass(frozen=True)
class SemanticPatternEvidence:
    """A complete static signature for one local module class."""

    pattern_id: str
    class_name: str
    source_anchor_ids: list[str]
    markers: dict[str, str]
    member_class_names: tuple[str, ...] = ()
    component_files: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class SemanticSourceFile:
    """A source file already approved by the project adapter for pattern evidence."""

    relative_file: str
    raw_source: bytes
    revision: str


def _digest(value: str) -> str:
    return "sha256:" + sha256(value.encode("utf-8")).hexdigest()


def _dotted(node: ast.expr) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = _dotted(node.value)
        return f"{parent}.{node.attr}" if parent else None
    return None


def _call_name(node: ast.Call) -> str:
    return _dotted(node.func) or "<dynamic>"


def _call_terminal(node: ast.Call) -> str:
    """Return the callable's final attribute even when its receiver is a call chain."""

    return node.func.attr if isinstance(node.func, ast.Attribute) else _call_name(node)


def _call_anchor(
    node: ast.AST,
    *,
    relative_file: str,
    class_name: str,
    method_name: str,
    marker: str,
    pattern_id: str,
    raw_text: str,
    revision: str,
) -> SourceAnchor:
    line = node.lineno
    column = node.col_offset
    end_line = node.end_lineno
    end_column = node.end_col_offset
    text_lines = raw_text.splitlines(keepends=True)
    if line == end_line:
        content = text_lines[line - 1][column:end_column]
    else:
        content = "".join(
            [text_lines[line - 1][column:], *text_lines[line:end_line - 1], text_lines[end_line - 1][:end_column]]
        )
    anchor_id = f"anchor:pattern.{class_name.lower()}.{method_name}.{marker}.{line}.{column}"
    return SourceAnchor(
        anchor_id=anchor_id,
        relative_file=relative_file,
        symbol_path=f"{class_name}.{method_name}",
        semantic_path=f"pattern.{pattern_id}.{class_name.lower()}.{marker}",
        kind=AnchorKind.EXPRESSION,
        cst_node_type=type(node).__name__,
        span=SourceSpan(
            start=SourcePosition(line=line, column=column),
            end=SourcePosition(line=end_line, column=end_column),
        ),
        locator=AnchorLocator(
            class_name=class_name,
            function_name=method_name,
            assignment_target=None,
            callee_text=None,
            qualified_callee=None,
            argument_name=None,
            occurrence=0,
        ),
        structural_fingerprint=_digest(f"{pattern_id}:{marker}:{type(node).__name__}"),
        content_fingerprint=_digest(content),
        file_revision=revision,
    )


def _methods(node: ast.ClassDef) -> dict[str, ast.FunctionDef]:
    return {item.name: item for item in node.body if isinstance(item, ast.FunctionDef)}


def _has_module_base(node: ast.ClassDef) -> bool:
    return any(_dotted(base) in {"nn.Module", "torch.nn.Module", "Module"} for base in node.bases)


def _contains_fft_top_k(function: ast.FunctionDef) -> tuple[ast.Call, ast.Call] | None:
    rfft = next(
        (
            call
            for call in ast.walk(function)
            if isinstance(call, ast.Call) and _call_name(call).endswith("fft.rfft")
        ),
        None,
    )
    top_k = next(
        (
            call
            for call in ast.walk(function)
            if isinstance(call, ast.Call) and _call_name(call).endswith("topk")
        ),
        None,
    )
    return (rfft, top_k) if rfft is not None and top_k is not None else None


def _is_range_over_self_k(node: ast.For) -> bool:
    return (
        isinstance(node.iter, ast.Call)
        and _call_name(node.iter) == "range"
        and len(node.iter.args) == 1
        and _dotted(node.iter.args[0]) == "self.k"
    )


def _is_residual_to_input(node: ast.BinOp, input_name: str) -> bool:
    if not isinstance(node.op, ast.Add):
        return False
    names = {_dotted(node.left), _dotted(node.right)}
    return input_name in names and len(names - {input_name}) == 1


def _spectral_period_inception_signature(
    class_node: ast.ClassDef, functions: dict[str, ast.FunctionDef]
) -> dict[str, ast.AST] | None:
    methods = _methods(class_node)
    init, forward = methods.get("__init__"), methods.get("forward")
    if init is None or forward is None:
        return None
    input_names = [argument.arg for argument in forward.args.args if argument.arg != "self"]
    if not input_names:
        return None
    fft_helpers = {
        name: signature
        for name, function in functions.items()
        if (signature := _contains_fft_top_k(function)) is not None
    }
    helper_call = next(
        (
            call
            for call in ast.walk(forward)
            if isinstance(call, ast.Call) and isinstance(call.func, ast.Name) and call.func.id in fft_helpers
        ),
        None,
    )
    if helper_call is None:
        return None
    helper_name = helper_call.func.id
    rfft, top_k = fft_helpers[helper_name]
    period_loop = next(
        (item for item in ast.walk(forward) if isinstance(item, ast.For) and _is_range_over_self_k(item)),
        None,
    )
    if period_loop is None:
        return None
    reshape_calls = [
        call for call in ast.walk(period_loop) if isinstance(call, ast.Call) and _call_terminal(call) == "reshape"
    ]
    permute_calls = [
        call for call in ast.walk(period_loop) if isinstance(call, ast.Call) and _call_terminal(call) == "permute"
    ]
    conv_call = next(
        (
            call
            for call in ast.walk(period_loop)
            if isinstance(call, ast.Call) and _dotted(call.func) == "self.conv"
        ),
        None,
    )
    softmax = next(
        (
            call
            for call in ast.walk(forward)
            if isinstance(call, ast.Call) and _call_name(call).endswith("softmax")
        ),
        None,
    )
    weighted_sum = next(
        (
            call
            for call in ast.walk(forward)
            if isinstance(call, ast.Call) and _call_name(call).endswith("sum")
        ),
        None,
    )
    residual = next(
        (
            node
            for node in ast.walk(forward)
            if isinstance(node, ast.BinOp) and _is_residual_to_input(node, input_names[0])
        ),
        None,
    )
    sequential = next(
        (
            call
            for call in ast.walk(init)
            if isinstance(call, ast.Call)
            and _call_name(call).endswith("Sequential")
            and len(call.args) == 3
            and _call_name(call.args[1]) in {"nn.GELU", "torch.nn.GELU", "GELU"}
            and "Inception" in _call_name(call.args[0])
            and "Inception" in _call_name(call.args[2])
        ),
        None,
    )
    if not (
        len(reshape_calls) >= 2
        and len(permute_calls) >= 2
        and conv_call is not None
        and softmax is not None
        and weighted_sum is not None
        and residual is not None
        and sequential is not None
    ):
        return None
    return {
        "fft": rfft,
        "top_k": top_k,
        "period_loop": period_loop,
        "reshape_1d_to_2d": reshape_calls[0],
        "inception": sequential,
        "reshape_2d_to_1d": reshape_calls[-1],
        "adaptive_aggregation": weighted_sum,
        "residual": residual,
    }


def _transformer_encoder_signature(class_node: ast.ClassDef) -> dict[str, ast.AST] | None:
    """Recognize the source-level encoder repeat contract, not merely its class name."""

    methods = _methods(class_node)
    init, forward = methods.get("__init__"), methods.get("forward")
    if init is None or forward is None:
        return None
    layer_list = next(
        (
            call
            for call in ast.walk(init)
            if isinstance(call, ast.Call)
            and _call_name(call).endswith("ModuleList")
            and call.args
            and isinstance(call.args[0], ast.ListComp)
            and isinstance(call.args[0].elt, ast.Call)
            and _call_name(call.args[0].elt).endswith("TransformerEncoderLayer")
        ),
        None,
    )
    repeat_loop = next(
        (
            item
            for item in ast.walk(forward)
            if isinstance(item, ast.For)
            and isinstance(item.target, ast.Name)
            and isinstance(item.iter, ast.Attribute)
            and (_dotted(item.iter) or "").startswith("self.")
        ),
        None,
    )
    norm_call = next(
        (
            call
            for call in ast.walk(forward)
            if isinstance(call, ast.Call)
            and isinstance(call.func, ast.Attribute)
            and _dotted(call.func) == "self.norm"
        ),
        None,
    )
    head_call = next(
        (
            call
            for call in ast.walk(forward)
            if isinstance(call, ast.Call)
            and isinstance(call.func, ast.Attribute)
            and _dotted(call.func) == "self.head"
        ),
        None,
    )
    if layer_list is None or repeat_loop is None or norm_call is None or head_call is None:
        return None
    return {
        "layer_construction": layer_list,
        "repeat_loop": repeat_loop,
        "layer_norm": norm_call,
        "forecast_head": head_call,
    }


def collect_semantic_pattern_evidence(
    raw_source: bytes,
    *,
    relative_file: str,
    revision: str,
) -> tuple[list[SemanticPatternEvidence], list[SourceAnchor]]:
    """Collect complete, generic structural signatures without importing or executing source."""

    text = raw_source.decode("utf-8")
    module = ast.parse(text)
    functions = {item.name: item for item in module.body if isinstance(item, ast.FunctionDef)}
    evidence: list[SemanticPatternEvidence] = []
    anchors: list[SourceAnchor] = []
    for class_node in module.body:
        if not isinstance(class_node, ast.ClassDef) or not _has_module_base(class_node):
            continue
        pattern_id = "spectral_period_inception_block_v1"
        signature = _spectral_period_inception_signature(class_node, functions)
        if signature is None:
            pattern_id = "encoder_attention_stack_v1"
            signature = _transformer_encoder_signature(class_node)
        if signature is None:
            continue
        marker_anchors = [
            _call_anchor(
                node,
                relative_file=relative_file,
                class_name=class_node.name,
                method_name=(
                    "__init__"
                    if marker in {"inception", "layer_construction"}
                    else "forward"
                ),
                marker=marker,
                pattern_id=pattern_id,
                raw_text=text,
                revision=revision,
            )
            for marker, node in signature.items()
        ]
        anchors.extend(marker_anchors)
        evidence.append(
            SemanticPatternEvidence(
                pattern_id=pattern_id,
                class_name=class_node.name,
                source_anchor_ids=[anchor.anchor_id for anchor in marker_anchors],
                markers={marker: anchor.anchor_id for marker, anchor in zip(signature, marker_anchors)},
            )
        )
    return evidence, anchors


def _ordered_nodes(node: ast.AST, node_type: type[ast.AST]) -> list[ast.AST]:
    return sorted(
        (item for item in ast.walk(node) if isinstance(item, node_type)),
        key=lambda item: (item.lineno, item.col_offset),
    )


def _self_assignment(function: ast.FunctionDef, attribute: str) -> ast.Assign | None:
    return next(
        (
            item
            for item in _ordered_nodes(function, ast.Assign)
            if any(
                isinstance(target, ast.Attribute)
                and isinstance(target.value, ast.Name)
                and target.value.id == "self"
                and target.attr == attribute
                for target in item.targets
            )
        ),
        None,
    )


def _assignment_call(function: ast.FunctionDef, attribute: str) -> ast.Call | None:
    assignment = _self_assignment(function, attribute)
    return assignment.value if assignment is not None and isinstance(assignment.value, ast.Call) else None


def _assignment_calls(function: ast.FunctionDef, attribute: str) -> list[ast.Call]:
    return [
        assignment.value
        for assignment in _ordered_nodes(function, ast.Assign)
        if any(
            isinstance(target, ast.Attribute)
            and isinstance(target.value, ast.Name)
            and target.value.id == "self"
            and target.attr == attribute
            for target in assignment.targets
        )
        and isinstance(assignment.value, ast.Call)
    ]


def _list_comprehension(call: ast.Call, constructor_name: str) -> ast.ListComp | None:
    return next(
        (
            argument
            for argument in call.args
            if isinstance(argument, ast.ListComp)
            and isinstance(argument.elt, ast.Call)
            and _call_name(argument.elt) == constructor_name
            and argument.generators
        ),
        None,
    )


def _keyword_call(call: ast.Call, name: str) -> ast.Call | None:
    return next(
        (keyword.value for keyword in call.keywords if keyword.arg == name and isinstance(keyword.value, ast.Call)),
        None,
    )


def _self_calls(function: ast.FunctionDef, attribute: str) -> list[ast.Call]:
    return [
        item
        for item in _ordered_nodes(function, ast.Call)
        if _dotted(item.func) == f"self.{attribute}"
    ]


def _for_over_self_attribute(function: ast.FunctionDef, attribute: str) -> ast.For | None:
    for item in _ordered_nodes(function, ast.For):
        if _dotted(item.iter) != f"self.{attribute}":
            continue
        if isinstance(item.target, ast.Name) and any(
            isinstance(call.func, ast.Name) and call.func.id == item.target.id
            for call in _ordered_nodes(item, ast.Call)
        ):
            return item
    return None


def _residuals(function: ast.FunctionDef) -> list[ast.BinOp]:
    return [
        item
        for item in _ordered_nodes(function, ast.BinOp)
        if isinstance(item.op, ast.Add)
    ]


def _find_class(source: SemanticSourceFile, name: str) -> ast.ClassDef | None:
    module = ast.parse(source.raw_source.decode("utf-8"))
    return next(
        (item for item in module.body if isinstance(item, ast.ClassDef) and item.name == name),
        None,
    )


def _container_signature(
    class_node: ast.ClassDef, *, layer_attribute: str, has_projection: bool
) -> dict[str, tuple[str, ast.AST]] | None:
    methods = _methods(class_node)
    init, forward = methods.get("__init__"), methods.get("forward")
    if init is None or forward is None:
        return None
    module_list = _assignment_call(init, layer_attribute)
    repeat_loop = _for_over_self_attribute(forward, layer_attribute)
    layer_norm_attributes = {
        target.attr
        for assignment in _ordered_nodes(init, ast.Assign)
        if isinstance(assignment.value, ast.Call)
        and _call_name(assignment.value).endswith("LayerNorm")
        for target in assignment.targets
        if isinstance(target, ast.Attribute)
        and isinstance(target.value, ast.Name)
        and target.value.id == "self"
    }
    norm_call = next(
        (
            call
            for call in _ordered_nodes(forward, ast.Call)
            if (_dotted(call.func) or "").removeprefix("self.") in layer_norm_attributes
        ),
        None,
    )
    if norm_call is None:
        retained_attributes = {
            target.attr
            for assignment in _ordered_nodes(init, ast.Assign)
            if isinstance(assignment.value, ast.Name)
            for target in assignment.targets
            if isinstance(target, ast.Attribute)
            and isinstance(target.value, ast.Name)
            and target.value.id == "self"
        }
        norm_call = next(
            (
                call
                for call in _ordered_nodes(forward, ast.Call)
                if (_dotted(call.func) or "").removeprefix("self.") in retained_attributes
            ),
            None,
        )
    if (
        module_list is None
        or not _call_name(module_list).endswith("ModuleList")
        or repeat_loop is None
        or norm_call is None
    ):
        return None
    result = {
        "module_list": ("__init__", module_list),
        "repeat_loop": ("forward", repeat_loop),
        "norm_call": ("forward", norm_call),
    }
    if has_projection:
        projection_call = next(
            (
                call
                for call in _ordered_nodes(forward, ast.Call)
                if _dotted(call.func) not in {f"self.{layer_attribute}", _dotted(norm_call.func)}
                and (_dotted(call.func) or "").startswith("self.")
            ),
            None,
        )
        if projection_call is None:
            return None
        result["projection_call"] = ("forward", projection_call)
    return result


def _encoder_layer_signature(
    class_node: ast.ClassDef,
) -> dict[str, tuple[str, ast.AST]] | None:
    methods = _methods(class_node)
    init, forward = methods.get("__init__"), methods.get("forward")
    if init is None or forward is None:
        return None
    norm_init = [
        call
        for call in _ordered_nodes(init, ast.Call)
        if _call_name(call).endswith("LayerNorm")
    ]
    norm_attributes = {
        target.attr
        for assignment in _ordered_nodes(init, ast.Assign)
        if isinstance(assignment.value, ast.Call)
        and _call_name(assignment.value).endswith("LayerNorm")
        for target in assignment.targets
        if isinstance(target, ast.Attribute)
        and isinstance(target.value, ast.Name)
        and target.value.id == "self"
    }
    norm_calls = [
        call
        for call in _ordered_nodes(forward, ast.Call)
        if (_dotted(call.func) or "").removeprefix("self.") in norm_attributes
    ]
    non_norm_calls = [
        call
        for call in _ordered_nodes(forward, ast.Call)
        if (_dotted(call.func) or "").startswith("self.") and call not in norm_calls
    ]
    attention = next(iter(non_norm_calls), None)
    norm1 = norm_calls[0] if norm_calls else None
    norm2 = norm_calls[-1] if norm_calls else None
    residuals = _residuals(forward)
    if (
        len(norm_init) < 2
        or attention is None
        or norm1 is None
        or norm2 is None
        or len(residuals) < 2
        or not (attention.lineno < residuals[0].lineno <= norm1.lineno < residuals[-1].lineno <= norm2.lineno)
    ):
        return None
    return {
        "attention": ("forward", attention),
        "attention_residual": ("forward", residuals[0]),
        "norm1": ("forward", norm1),
        "feed_forward_residual": ("forward", residuals[-1]),
        "norm2": ("forward", norm2),
    }


def _decoder_layer_signature(
    class_node: ast.ClassDef,
) -> dict[str, tuple[str, ast.AST]] | None:
    methods = _methods(class_node)
    init, forward = methods.get("__init__"), methods.get("forward")
    if init is None or forward is None:
        return None
    norm_init = [
        call
        for call in _ordered_nodes(init, ast.Call)
        if _call_name(call).endswith("LayerNorm")
    ]
    norm_attributes = {
        target.attr
        for assignment in _ordered_nodes(init, ast.Assign)
        if isinstance(assignment.value, ast.Call)
        and _call_name(assignment.value).endswith("LayerNorm")
        for target in assignment.targets
        if isinstance(target, ast.Attribute)
        and isinstance(target.value, ast.Name)
        and target.value.id == "self"
    }
    norm_calls = [
        call
        for call in _ordered_nodes(forward, ast.Call)
        if (_dotted(call.func) or "").removeprefix("self.") in norm_attributes
    ]
    non_norm_calls = [
        call
        for call in _ordered_nodes(forward, ast.Call)
        if (_dotted(call.func) or "").startswith("self.") and call not in norm_calls
    ]
    norm1 = norm_calls[0] if norm_calls else None
    norm2 = norm_calls[1] if len(norm_calls) > 1 else None
    norm3 = norm_calls[-1] if norm_calls else None
    self_attention = next(
        (call for call in non_norm_calls if norm1 is not None and call.lineno < norm1.lineno),
        None,
    )
    cross_attention = next(
        (
            call
            for call in non_norm_calls
            if norm1 is not None and norm2 is not None and norm1.lineno < call.lineno < norm2.lineno
        ),
        None,
    )
    residuals = _residuals(forward)
    if (
        len(norm_init) < 3
        or self_attention is None
        or cross_attention is None
        or norm1 is None
        or norm2 is None
        or norm3 is None
        or len(residuals) < 3
        or not (
            self_attention.lineno < norm1.lineno < cross_attention.lineno
            < norm2.lineno < residuals[-1].lineno <= norm3.lineno
        )
    ):
        return None
    return {
        "self_attention": ("forward", self_attention),
        "norm1": ("forward", norm1),
        "cross_attention": ("forward", cross_attention),
        "norm2": ("forward", norm2),
        "feed_forward_residual": ("forward", residuals[-1]),
        "norm3": ("forward", norm3),
    }


def _root_transformer_signature(
    class_node: ast.ClassDef, aliases: Mapping[str, str]
) -> dict[str, tuple[str, str, dict[str, tuple[str, ast.AST]]]] | None:
    """Recognize a two-stack encoder/decoder assembly from imports, never their names."""

    methods = _methods(class_node)
    init, forward = methods.get("__init__"), methods.get("forward")
    if init is None or forward is None:
        return None
    imported_by_alias = {alias: class_name for class_name, alias in aliases.items()}
    candidates: list[tuple[str, str, str, ast.Call, ast.ListComp, ast.Call, ast.Call | None]] = []
    for assignment in _ordered_nodes(init, ast.Assign):
        if not isinstance(assignment.value, ast.Call):
            continue
        attribute = next(
            (
                target.attr
                for target in assignment.targets
                if isinstance(target, ast.Attribute)
                and isinstance(target.value, ast.Name)
                and target.value.id == "self"
            ),
            None,
        )
        container_class = imported_by_alias.get(_call_name(assignment.value))
        if attribute is None or container_class is None:
            continue
        for argument in assignment.value.args:
            if not (
                isinstance(argument, ast.ListComp)
                and isinstance(argument.elt, ast.Call)
                and argument.generators
            ):
                continue
            layer_class = imported_by_alias.get(_call_name(argument.elt))
            layer_norm = next(
                (
                    keyword.value
                    for keyword in assignment.value.keywords
                    if isinstance(keyword.value, ast.Call)
                    and _call_name(keyword.value).endswith("LayerNorm")
                ),
                None,
            )
            head = next(
                (
                    keyword.value
                    for keyword in assignment.value.keywords
                    if isinstance(keyword.value, ast.Call)
                    and _call_name(keyword.value).endswith("Linear")
                ),
                None,
            )
            if layer_class is not None and layer_norm is not None:
                candidates.append(
                    (attribute, container_class, layer_class, assignment.value, argument, layer_norm, head)
                )
    decoder_candidate = next((candidate for candidate in candidates if candidate[-1] is not None), None)
    if decoder_candidate is None:
        return None
    encoder_candidate = next((candidate for candidate in candidates if candidate is not decoder_candidate), None)
    if encoder_candidate is None:
        return None
    helper = next(
        (
            method
            for name, method in methods.items()
            if name not in {"__init__", "forward"}
            and _self_calls(method, encoder_candidate[0])
            and _self_calls(method, decoder_candidate[0])
            and _self_calls(forward, name)
        ),
        None,
    )
    if helper is None:
        return None
    dispatch = next(iter(_self_calls(forward, helper.name)), None)
    encoder_call = next(iter(_self_calls(helper, encoder_candidate[0])), None)
    decoder_call = next(iter(_self_calls(helper, decoder_candidate[0])), None)
    if dispatch is None or encoder_call is None or decoder_call is None:
        return None

    def markers(
        candidate: tuple[str, str, str, ast.Call, ast.ListComp, ast.Call, ast.Call | None],
        call: ast.Call,
        *,
        include_head: bool,
    ) -> dict[str, tuple[str, ast.AST]]:
        _, _, _, construction, repeat, norm, head = candidate
        result = {
            "root_construction": ("__init__", construction),
            "root_layer_repeat": ("__init__", repeat),
            "root_norm": ("__init__", norm),
            "task_call": (helper.name, call),
            "task_dispatch": ("forward", dispatch),
        }
        if include_head and head is not None:
            result["output_head"] = ("__init__", head)
        return result

    return {
        "encoder": (encoder_candidate[1], encoder_candidate[2], markers(encoder_candidate, encoder_call, include_head=False)),
        "decoder": (decoder_candidate[1], decoder_candidate[2], markers(decoder_candidate, decoder_call, include_head=True)),
    }


def _cross_file_evidence(
    *,
    pattern_id: str,
    root_class_name: str,
    member_class_name: str,
    markers: Mapping[str, tuple[SemanticSourceFile, str, str, ast.AST]],
) -> tuple[SemanticPatternEvidence, list[SourceAnchor]]:
    marker_anchors = [
        _call_anchor(
            node,
            relative_file=source.relative_file,
            class_name=class_name,
            method_name=method_name,
            marker=marker,
            pattern_id=pattern_id,
            raw_text=source.raw_source.decode("utf-8"),
            revision=source.revision,
        )
        for marker, (source, class_name, method_name, node) in markers.items()
    ]
    return (
        SemanticPatternEvidence(
            pattern_id=pattern_id,
            class_name=root_class_name,
            source_anchor_ids=[anchor.anchor_id for anchor in marker_anchors],
            markers={marker: anchor.anchor_id for marker, anchor in zip(markers, marker_anchors)},
            member_class_names=(member_class_name,),
            component_files={
                class_name: source.relative_file
                for source, class_name, _, _ in markers.values()
            },
        ),
        marker_anchors,
    )


def collect_cross_file_transformer_evidence(
    root_source: SemanticSourceFile,
    *,
    root_class_name: str,
    imported_sources: Mapping[str, SemanticSourceFile],
    imported_aliases: Mapping[str, str],
) -> tuple[list[SemanticPatternEvidence], list[SourceAnchor]]:
    """Prove cross-file encoder/decoder stacks across direct local imports.

    This deliberately requires the root constructor/call path, the container loop and the
    implementation of each layer.  It records evidence only; it never flattens imported
    topology into the entrypoint IR.
    """

    root_class = _find_class(root_source, root_class_name)
    if root_class is None or not _has_module_base(root_class):
        return [], []
    root_signature = _root_transformer_signature(root_class, imported_aliases)
    if root_signature is None:
        return [], []
    encoder_class_name, encoder_layer_name, encoder_root_markers = root_signature["encoder"]
    decoder_class_name, decoder_layer_name, decoder_root_markers = root_signature["decoder"]
    encoder_source = imported_sources.get(encoder_class_name)
    decoder_source = imported_sources.get(decoder_class_name)
    encoder_layer_source = imported_sources.get(encoder_layer_name)
    decoder_layer_source = imported_sources.get(decoder_layer_name)
    if any(source is None for source in (encoder_source, decoder_source, encoder_layer_source, decoder_layer_source)):
        return [], []
    assert encoder_source is not None and decoder_source is not None
    assert encoder_layer_source is not None and decoder_layer_source is not None
    encoder_container = _find_class(encoder_source, encoder_class_name)
    decoder_container = _find_class(decoder_source, decoder_class_name)
    encoder_layer = _find_class(encoder_layer_source, encoder_layer_name)
    decoder_layer = _find_class(decoder_layer_source, decoder_layer_name)
    if any(item is None for item in (encoder_container, decoder_container, encoder_layer, decoder_layer)):
        return [], []
    assert encoder_container is not None and decoder_container is not None
    assert encoder_layer is not None and decoder_layer is not None
    encoder_layer_attribute = next(
        (target.attr for assignment in _ordered_nodes(_methods(encoder_container)["__init__"], ast.Assign)
         if isinstance(assignment.value, ast.Call) and _call_name(assignment.value).endswith("ModuleList")
         for target in assignment.targets if isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name) and target.value.id == "self"),
        None,
    )
    decoder_layer_attribute = next(
        (target.attr for assignment in _ordered_nodes(_methods(decoder_container)["__init__"], ast.Assign)
         if isinstance(assignment.value, ast.Call) and _call_name(assignment.value).endswith("ModuleList")
         for target in assignment.targets if isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name) and target.value.id == "self"),
        None,
    )
    if encoder_layer_attribute is None or decoder_layer_attribute is None:
        return [], []
    encoder_container_signature = _container_signature(
        encoder_container, layer_attribute=encoder_layer_attribute, has_projection=False
    )
    decoder_container_signature = _container_signature(
        decoder_container, layer_attribute=decoder_layer_attribute, has_projection=True
    )
    encoder_layer_signature = _encoder_layer_signature(encoder_layer)
    decoder_layer_signature = _decoder_layer_signature(decoder_layer)
    evidence: list[SemanticPatternEvidence] = []
    anchors: list[SourceAnchor] = []
    if encoder_container_signature is not None and encoder_layer_signature is not None:
        markers = {
            **{
                f"root_encoder_{name}": (root_source, root_class_name, method, node)
                for name, (method, node) in encoder_root_markers.items()
            },
            **{
                f"encoder_{name}": (encoder_source, encoder_class_name, method, node)
                for name, (method, node) in encoder_container_signature.items()
            },
            **{
                f"encoder_layer_{name}": (encoder_layer_source, encoder_layer_name, method, node)
                for name, (method, node) in encoder_layer_signature.items()
            },
        }
        item, item_anchors = _cross_file_evidence(
            pattern_id="encoder_attention_stack_v1",
            root_class_name=root_class_name,
            member_class_name=encoder_class_name,
            markers=markers,
        )
        evidence.append(item)
        anchors.extend(item_anchors)
    if decoder_container_signature is not None and decoder_layer_signature is not None:
        markers = {
            **{
                f"root_decoder_{name}": (root_source, root_class_name, method, node)
                for name, (method, node) in decoder_root_markers.items()
            },
            **{
                f"decoder_{name}": (decoder_source, decoder_class_name, method, node)
                for name, (method, node) in decoder_container_signature.items()
            },
            **{
                f"decoder_layer_{name}": (decoder_layer_source, decoder_layer_name, method, node)
                for name, (method, node) in decoder_layer_signature.items()
            },
        }
        item, item_anchors = _cross_file_evidence(
            pattern_id="decoder_cross_attention_stack_v1",
            root_class_name=root_class_name,
            member_class_name=decoder_class_name,
            markers=markers,
        )
        evidence.append(item)
        anchors.extend(item_anchors)
    return evidence, anchors


def _root_imported_attachments(
    class_node: ast.ClassDef, aliases: Mapping[str, str]
) -> list[tuple[str, str, ast.Call, ast.Call]]:
    """Return root fields wired to a directly imported local module by structure only."""

    methods = _methods(class_node)
    init, forward = methods.get("__init__"), methods.get("forward")
    if init is None or forward is None:
        return []
    imported_by_alias = {alias: class_name for class_name, alias in aliases.items()}
    attachments: list[tuple[str, str, ast.Call, ast.Call]] = []
    for assignment in _ordered_nodes(init, ast.Assign):
        if not isinstance(assignment.value, ast.Call):
            continue
        attribute = next(
            (
                target.attr
                for target in assignment.targets
                if isinstance(target, ast.Attribute)
                and isinstance(target.value, ast.Name)
                and target.value.id == "self"
            ),
            None,
        )
        class_name = imported_by_alias.get(_call_name(assignment.value))
        call = next(iter(_self_calls(forward, attribute)), None) if attribute is not None else None
        if attribute is not None and class_name is not None and call is not None:
            attachments.append((attribute, class_name, assignment.value, call))
    return attachments


def _sparse_router_signature(
    class_node: ast.ClassDef,
) -> dict[str, tuple[str, ast.AST]] | None:
    methods = _methods(class_node)
    init = methods.get("__init__")
    forward = methods.get("forward")
    if init is None or forward is None:
        return None
    experts_assignment = next(
        (
            assignment
            for assignment in _ordered_nodes(init, ast.Assign)
            if isinstance(assignment.value, ast.Call)
            and _call_name(assignment.value).endswith("ModuleList")
            and any(isinstance(argument, ast.ListComp) for argument in assignment.value.args)
        ),
        None,
    )
    experts = experts_assignment.value if experts_assignment is not None else None
    expert_attribute = next(
        (
            target.attr
            for target in experts_assignment.targets
            if isinstance(target, ast.Attribute)
            and isinstance(target.value, ast.Name)
            and target.value.id == "self"
        ),
        None,
    ) if experts_assignment is not None else None
    expert_constructor = next(
        (
            argument.elt
            for argument in experts.args
            if isinstance(argument, ast.ListComp) and isinstance(argument.elt, ast.Call)
        ),
        None,
    ) if experts is not None else None
    gating_candidates = [
        method
        for name, method in methods.items()
        if name not in {"__init__", "forward"}
        and any(_call_terminal(call) == "topk" for call in _ordered_nodes(method, ast.Call))
    ]
    gating = next(
        (
            method
            for method in gating_candidates
            if any(_call_name(call).endswith("softmax") for call in _ordered_nodes(method, ast.Call))
            and _self_calls(forward, method.name)
        ),
        None,
    )
    softmax = next(
        (call for call in _ordered_nodes(gating, ast.Call) if _call_name(call).endswith("softmax")),
        None,
    ) if gating is not None else None
    top_k = next(
        (call for call in _ordered_nodes(gating, ast.Call) if _call_terminal(call) == "topk"),
        None,
    ) if gating is not None else None
    gating_call = next(iter(_self_calls(forward, gating.name)), None) if gating is not None else None
    dispatcher_assignment = next(
        (
            assignment
            for assignment in _ordered_nodes(forward, ast.Assign)
            if isinstance(assignment.value, ast.Call) and isinstance(assignment.targets[0], ast.Name)
        ),
        None,
    )
    dispatcher = dispatcher_assignment.value if dispatcher_assignment is not None else None
    dispatcher_name = dispatcher_assignment.targets[0].id if dispatcher_assignment is not None else None
    dispatch = next(
        (
            call
            for call in _ordered_nodes(forward, ast.Call)
            if _dotted(call.func) == f"{dispatcher_name}.dispatch"
        ),
        None,
    ) if dispatcher_name is not None else None
    combine = next(
        (
            call
            for call in _ordered_nodes(forward, ast.Call)
            if _dotted(call.func) == f"{dispatcher_name}.combine"
        ),
        None,
    ) if dispatcher_name is not None else None
    expert_loop = next(
        (
            item
            for item in _ordered_nodes(forward, ast.ListComp)
            if isinstance(item.elt, ast.Call)
            and isinstance(item.elt.func, ast.Subscript)
            and _dotted(item.elt.func.value) == f"self.{expert_attribute}"
        ),
        None,
    ) if expert_attribute is not None else None
    if (
        experts is None
        or not _call_name(experts).endswith("ModuleList")
        or expert_constructor is None
        or softmax is None
        or top_k is None
        or gating_call is None
        or dispatcher is None
        or dispatch is None
        or expert_loop is None
        or combine is None
    ):
        return None
    return {
        "experts": ("__init__", experts),
        "softmax": (gating.name, softmax),
        "top_k": (gating.name, top_k),
        "gating_call": ("forward", gating_call),
        "dispatcher": ("forward", dispatcher),
        "dispatch": ("forward", dispatch),
        "expert_loop": ("forward", expert_loop),
        "combine": ("forward", combine),
        "expert_constructor": ("__init__", expert_constructor),
    }


def _frequency_mask_signature(
    class_node: ast.ClassDef,
) -> dict[str, tuple[str, ast.AST]] | None:
    methods = _methods(class_node)
    forward = methods.get("forward")
    if forward is None:
        return None
    distance = next(
        (
            method
            for method in methods.values()
            if any(_call_name(call).endswith("fft.rfft") for call in _ordered_nodes(method, ast.Call))
            and sum(_call_name(call).endswith("einsum") for call in _ordered_nodes(method, ast.Call)) >= 2
        ),
        None,
    )
    sampler = next(
        (
            method
            for method in methods.values()
            if any(_call_name(call).endswith("gumbel_softmax") for call in _ordered_nodes(method, ast.Call))
        ),
        None,
    )
    if distance is None or sampler is None:
        return None
    rfft = next(
        (call for call in _ordered_nodes(distance, ast.Call) if _call_name(call).endswith("fft.rfft")),
        None,
    )
    pairwise_difference = next(
        (item for item in _ordered_nodes(distance, ast.BinOp) if isinstance(item.op, ast.Sub)),
        None,
    )
    einsums = [
        call for call in _ordered_nodes(distance, ast.Call) if _call_name(call).endswith("einsum")
    ]
    gumbel = next(
        (call for call in _ordered_nodes(sampler, ast.Call) if _call_name(call).endswith("gumbel_softmax")),
        None,
    )
    probability = next(iter(_self_calls(forward, distance.name)), None)
    sample = next(iter(_self_calls(forward, sampler.name)), None)
    if (
        rfft is None
        or pairwise_difference is None
        or len(einsums) < 2
        or gumbel is None
        or probability is None
        or sample is None
    ):
        return None
    return {
        "rfft": (distance.name, rfft),
        "pairwise_difference": (distance.name, pairwise_difference),
        "learned_metric": (distance.name, einsums[0]),
        "probability": ("forward", probability),
        "gumbel_sample": (sampler.name, gumbel),
        "forward_sample": ("forward", sample),
    }


def _series_decomposition_signature(
    class_node: ast.ClassDef,
) -> dict[str, tuple[str, ast.AST]] | None:
    methods = _methods(class_node)
    init = methods.get("__init__")
    if init is None:
        return None
    assignments = [
        (target.attr, assignment.value)
        for assignment in _ordered_nodes(init, ast.Assign)
        if isinstance(assignment.value, ast.Call)
        for target in assignment.targets
        if isinstance(target, ast.Attribute)
        and isinstance(target.value, ast.Name)
        and target.value.id == "self"
    ]
    decomposition_pair = next(
        ((attribute, call) for attribute, call in assignments if not _call_name(call).endswith("Linear")),
        None,
    )
    linear_pairs = [(attribute, call) for attribute, call in assignments if _call_name(call).endswith("Linear")]
    if decomposition_pair is None or len(linear_pairs) < 2:
        return None
    decomposition_attribute, decomposition = decomposition_pair
    (seasonal_attribute, seasonal), (trend_attribute, trend) = linear_pairs[:2]
    encoder = next(
        (
            method
            for name, method in methods.items()
            if name != "__init__"
            and _self_calls(method, decomposition_attribute)
            and _self_calls(method, seasonal_attribute)
            and _self_calls(method, trend_attribute)
        ),
        None,
    )
    if encoder is None:
        return None
    decomposition_call = next(iter(_self_calls(encoder, decomposition_attribute)), None)
    seasonal_call = next(iter(_self_calls(encoder, seasonal_attribute)), None)
    trend_call = next(iter(_self_calls(encoder, trend_attribute)), None)
    call_targets = {
        target.id
        for assignment in _ordered_nodes(encoder, ast.Assign)
        if isinstance(assignment.value, ast.Call)
        and _dotted(assignment.value.func) in {f"self.{seasonal_attribute}", f"self.{trend_attribute}"}
        for target in assignment.targets
        if isinstance(target, ast.Name)
    }
    fused = next(
        (
            item
            for item in _ordered_nodes(encoder, ast.BinOp)
            if isinstance(item.op, ast.Add)
            and {_dotted(item.left), _dotted(item.right)} <= call_targets
            and len({_dotted(item.left), _dotted(item.right)}) == 2
        ),
        None,
    )
    if (
        decomposition is None
        or seasonal is None
        or trend is None
        or decomposition_call is None
        or seasonal_call is None
        or trend_call is None
        or fused is None
    ):
        return None
    return {
        "decomposition": ("__init__", decomposition),
        "seasonal_linear": ("__init__", seasonal),
        "trend_linear": ("__init__", trend),
        "decomposition_call": (encoder.name, decomposition_call),
        "seasonal_call": (encoder.name, seasonal_call),
        "trend_call": (encoder.name, trend_call),
        "fuse": (encoder.name, fused),
    }


def _moving_average_signature(
    class_node: ast.ClassDef,
) -> dict[str, tuple[str, ast.AST]] | None:
    methods = _methods(class_node)
    init, forward = methods.get("__init__"), methods.get("forward")
    if init is None or forward is None:
        return None
    moving_average_pair = next(
        (
            (target.attr, assignment.value)
            for assignment in _ordered_nodes(init, ast.Assign)
            if isinstance(assignment.value, ast.Call)
            for target in assignment.targets
            if isinstance(target, ast.Attribute)
            and isinstance(target.value, ast.Name)
            and target.value.id == "self"
        ),
        None,
    )
    if moving_average_pair is None:
        return None
    moving_average_attribute, moving_average = moving_average_pair
    moving_average_call = next(iter(_self_calls(forward, moving_average_attribute)), None)
    residual = next(
        (item for item in _ordered_nodes(forward, ast.BinOp) if isinstance(item.op, ast.Sub)),
        None,
    )
    if (
        moving_average is None
        or moving_average_call is None
        or residual is None
    ):
        return None
    return {
        "moving_average": ("__init__", moving_average),
        "moving_average_call": ("forward", moving_average_call),
        "seasonal_residual": ("forward", residual),
    }


def collect_cross_file_multibranch_evidence(
    root_source: SemanticSourceFile,
    *,
    root_class_name: str,
    imported_sources: Mapping[str, SemanticSourceFile],
    imported_aliases: Mapping[str, str],
) -> tuple[list[SemanticPatternEvidence], list[SourceAnchor]]:
    """Collect independent, fail-closed multi-branch signatures from local imports."""

    root_class = _find_class(root_source, root_class_name)
    if root_class is None or not _has_module_base(root_class):
        return [], []
    attachments = _root_imported_attachments(root_class, imported_aliases)
    if not attachments:
        return [], []
    evidence: list[SemanticPatternEvidence] = []
    anchors: list[SourceAnchor] = []
    imported_by_alias = {alias: class_name for class_name, alias in imported_aliases.items()}
    router_context: tuple[SemanticSourceFile, str, ast.Call, ast.Call, dict[str, tuple[str, ast.AST]]] | None = None
    for attribute, member_class_name, root_construction, root_call in attachments:
        source = imported_sources.get(member_class_name)
        member_class = _find_class(source, member_class_name) if source is not None else None
        if source is None or member_class is None:
            continue
        root_markers = {
            "root_construction": (root_source, root_class_name, "__init__", root_construction),
            "root_call": (root_source, root_class_name, "forward", root_call),
        }
        router_signature = _sparse_router_signature(member_class)
        if router_signature is not None:
            markers = {
                **{f"router_{name}": value for name, value in root_markers.items()},
                **{
                    f"router_{name}": (source, member_class_name, method, node)
                    for name, (method, node) in router_signature.items()
                },
            }
            item, item_anchors = _cross_file_evidence(
                pattern_id="topk_expert_router_v1",
                root_class_name=root_class_name,
                member_class_name=member_class_name,
                markers=markers,
            )
            evidence.append(item)
            anchors.extend(item_anchors)
            router_context = (source, member_class_name, root_construction, root_call, router_signature)
        mask_signature = _frequency_mask_signature(member_class)
        if mask_signature is not None:
            markers = {
                **{f"mask_{name}": value for name, value in root_markers.items()},
                **{
                    f"mask_{name}": (source, member_class_name, method, node)
                    for name, (method, node) in mask_signature.items()
                },
            }
            item, item_anchors = _cross_file_evidence(
                pattern_id="frequency_gumbel_mask_v1",
                root_class_name=root_class_name,
                member_class_name=member_class_name,
                markers=markers,
            )
            evidence.append(item)
            anchors.extend(item_anchors)
        root_methods = _methods(root_class)
        init = root_methods.get("__init__")
        if init is None or not isinstance(root_construction, ast.Call):
            continue
        layer_repeat = next(
            (
                argument
                for argument in root_construction.args
                if isinstance(argument, ast.ListComp)
                and isinstance(argument.elt, ast.Call)
            ),
            None,
        )
        layer_name = _call_name(layer_repeat.elt) if layer_repeat is not None else None
        layer_source = imported_sources.get(layer_name) if layer_name is not None else None
        layer = _find_class(layer_source, layer_name) if layer_source is not None and layer_name is not None else None
        layer_attribute = next(
            (
                target.attr
                for assignment in _ordered_nodes(_methods(member_class).get("__init__", init), ast.Assign)
                if isinstance(assignment.value, ast.Call) and _call_name(assignment.value).endswith("ModuleList")
                for target in assignment.targets
                if isinstance(target, ast.Attribute)
                and isinstance(target.value, ast.Name)
                and target.value.id == "self"
            ),
            None,
        )
        norm = next(
            (
                keyword.value
                for keyword in root_construction.keywords
                if isinstance(keyword.value, ast.Call) and _call_name(keyword.value).endswith("LayerNorm")
            ),
            None,
        )
        head_assignment = next(
            (
                assignment.value
                for assignment in _ordered_nodes(init, ast.Assign)
                if isinstance(assignment.value, ast.Call) and _call_name(assignment.value).endswith("Sequential")
            ),
            None,
        )
        head_call = next(
            (call for call in _ordered_nodes(root_methods["forward"], ast.Call) if _dotted(call.func) and _dotted(call.func).startswith("self.") and call is not root_call),
            None,
        )
        container_signature = (
            _container_signature(member_class, layer_attribute=layer_attribute, has_projection=False)
            if layer_attribute is not None else None
        )
        layer_signature = _encoder_layer_signature(layer) if layer is not None else None
        if (
            layer_repeat is not None and norm is not None and head_assignment is not None and head_call is not None
            and root_call.keywords and container_signature is not None and layer_signature is not None
            and layer_source is not None and layer_name is not None
        ):
            markers = {
                "channel_root_construction": (root_source, root_class_name, "__init__", root_construction),
                "channel_root_layer_repeat": (root_source, root_class_name, "__init__", layer_repeat),
                "channel_root_norm": (root_source, root_class_name, "__init__", norm),
                "channel_root_masked_call": (root_source, root_class_name, "forward", root_call),
                "channel_root_head": (root_source, root_class_name, "__init__", head_assignment),
                "channel_root_head_call": (root_source, root_class_name, "forward", head_call),
                **{
                    f"channel_encoder_{name}": (source, member_class_name, method, node)
                    for name, (method, node) in container_signature.items()
                },
                **{
                    f"channel_layer_{name}": (layer_source, layer_name, method, node)
                    for name, (method, node) in layer_signature.items()
                },
            }
            item, item_anchors = _cross_file_evidence(
                pattern_id="masked_attention_stack_v1",
                root_class_name=root_class_name,
                member_class_name=member_class_name,
                markers=markers,
            )
            evidence.append(item)
            anchors.extend(item_anchors)
    if router_context is not None:
        cluster_source, cluster_name, root_construction, root_call, cluster_signature = router_context
        expert_call = cluster_signature["expert_constructor"][1]
        extractor_name = (
            imported_by_alias.get(_call_name(expert_call)) if isinstance(expert_call, ast.Call) else None
        )
        extractor_source = imported_sources.get(extractor_name) if extractor_name is not None else None
        extractor = _find_class(extractor_source, extractor_name) if extractor_source is not None and extractor_name is not None else None
        extractor_signature = _series_decomposition_signature(extractor) if extractor is not None else None
        decomposition_call = extractor_signature["decomposition"][1] if extractor_signature is not None else None
        decomposition_name = (
            imported_by_alias.get(_call_name(decomposition_call))
            if isinstance(decomposition_call, ast.Call)
            else None
        )
        decomposition_source = imported_sources.get(decomposition_name) if decomposition_name is not None else None
        decomposition = _find_class(decomposition_source, decomposition_name) if decomposition_source is not None and decomposition_name is not None else None
        decomposition_signature = _moving_average_signature(decomposition) if decomposition is not None else None
        if (
            extractor_signature is not None
            and decomposition_signature is not None
            and extractor_source is not None
            and decomposition_source is not None
            and extractor_name is not None
            and decomposition_name is not None
        ):
            markers = {
                "series_root_root_construction": (root_source, root_class_name, "__init__", root_construction),
                "series_root_root_call": (root_source, root_class_name, "forward", root_call),
                **{
                    f"series_cluster_{name}": (cluster_source, cluster_name, method, node)
                    for name, (method, node) in {
                        key: cluster_signature[key] for key in ("experts", "expert_loop")
                    }.items()
                },
                **{
                    f"series_extractor_{name}": (extractor_source, extractor_name, method, node)
                    for name, (method, node) in extractor_signature.items()
                },
                **{
                    f"series_decomposition_{name}": (decomposition_source, decomposition_name, method, node)
                    for name, (method, node) in decomposition_signature.items()
                },
            }
            item, item_anchors = _cross_file_evidence(
                pattern_id="decomposition_linear_fusion_v1",
                root_class_name=root_class_name,
                member_class_name=cluster_name,
                markers=markers,
            )
            evidence.append(item)
            anchors.extend(item_anchors)
    return evidence, anchors
