"""Source-backed semantic signatures used by the Publication pattern registry.

This module deliberately does not create Architecture nodes.  It records a narrowly
defined source signature, with anchors, for a local module that is already present in
the Exact IR.  The Publication compiler consumes the resulting IR metadata only; it
never re-opens project source files.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
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
        structural_fingerprint=_digest(f"timesnet_v1:{marker}:{type(node).__name__}"),
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


def _timesnet_signature(
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
        pattern_id = "timesnet_v1"
        signature = _timesnet_signature(class_node, functions)
        if signature is None:
            pattern_id = "transformer_encoder_layer_v1"
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
