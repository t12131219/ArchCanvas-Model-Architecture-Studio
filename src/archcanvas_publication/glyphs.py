from __future__ import annotations

from dataclasses import dataclass

from archcanvas_core.models import NodeKind, PublicationNode


@dataclass(frozen=True)
class GlyphStyle:
    glyph: str
    fill: str
    stroke: str


_GLYPH_STYLES = {
    "container": GlyphStyle("container", "#edf6ff", "#3b6f98"),
    "operator": GlyphStyle("operator", "#eef2f7", "#4b6075"),
    "tensor": GlyphStyle("tensor", "#e7f5ff", "#1971c2"),
    "merge": GlyphStyle("merge", "#fff3bf", "#8d6b00"),
    "io": GlyphStyle("io", "#f3f0ff", "#7048a8"),
    "state": GlyphStyle("state", "#e6fcf5", "#087f5b"),
    "opaque": GlyphStyle("opaque", "#f1f3f5", "#59636e"),
    "projection": GlyphStyle("projection", "#fff4e6", "#d9480f"),
    "activation": GlyphStyle("activation", "#fff9db", "#9c6f00"),
    "normalization": GlyphStyle("normalization", "#e6fcf5", "#087f5b"),
    "attention": GlyphStyle("attention", "#fff0f0", "#c92a2a"),
    "transform": GlyphStyle("transform", "#f3f0ff", "#7048a8"),
    "condition": GlyphStyle("condition", "#f3f0ff", "#7048a8"),
    "repeat": GlyphStyle("repeat", "#edf6ff", "#356f9f"),
}


def _annotation_glyph(node: PublicationNode) -> str | None:
    glyphs = {
        str(annotation.get("glyph"))
        for annotation in node.attributes.get("semantic_annotations", [])
        if isinstance(annotation, dict)
        and annotation.get("glyph") in _GLYPH_STYLES
    }
    return next(iter(glyphs)) if len(glyphs) == 1 else None


def resolve_node_glyph(node: PublicationNode, fully_expanded: bool) -> GlyphStyle:
    """Resolve a visual glyph from formal node facts and validated annotations."""
    source_kind = str(node.attributes.get("source_kind", node.kind.value))
    lowered = " ".join(
        str(value)
        for value in (
            node.semantic_name,
            source_kind,
            node.attributes.get("op_type", ""),
            node.attributes.get("source_expression", ""),
            node.attributes.get("transform", ""),
            " ".join(str(part) for part in node.attributes.get("path", [])),
        )
    ).lower()

    if node.parent_view_node_id is None and node.kind is NodeKind.MODULE_CONTAINER:
        return GlyphStyle("container", "#f7f9fc", "#52606d")
    if node.kind is NodeKind.OPAQUE_COMPOSITE or "opaque" in lowered:
        return _GLYPH_STYLES["opaque"]
    if node.kind is NodeKind.MERGE_EVENT:
        return _GLYPH_STYLES["merge"]
    if node.kind is NodeKind.TENSOR_VALUE:
        return _GLYPH_STYLES["tensor"]
    if node.kind is NodeKind.CONDITION_CONTROL:
        return _GLYPH_STYLES["condition"]
    if node.kind is NodeKind.REPEAT or node.attributes.get("repeat_id"):
        return _GLYPH_STYLES["repeat"]
    if node.kind is NodeKind.STATE:
        return _GLYPH_STYLES["state"]
    if node.kind is NodeKind.INPUT_OUTPUT or node.attributes.get("io"):
        return _GLYPH_STYLES["io"]
    if node.kind is NodeKind.MODULE_CONTAINER or node.collapsed:
        if "decoder" in lowered:
            return GlyphStyle("container", "#fff0f6", "#a61e4d")
        if "encoder" in lowered:
            return GlyphStyle("container", "#e7f5ff", "#1971c2")
        if "ffn" in lowered or "feed" in lowered:
            return GlyphStyle("container", "#e7f5ff", "#2b6f8a")
        if "output" in lowered:
            return GlyphStyle("container", "#ebfbee", "#2b8a3e")
        if "input" in lowered:
            return GlyphStyle("container", "#fff0f6", "#a61e4d")
        return _GLYPH_STYLES["container"]

    if any(word in lowered for word in ("layernorm", "batchnorm", "groupnorm", " rmsnorm", " norm")):
        return _GLYPH_STYLES["normalization"]
    if any(word in lowered for word in ("gelu", "relu", "silu", "sigmoid", "softmax", "activation")):
        return _GLYPH_STYLES["activation"]
    if any(
        word in lowered
        for word in ("reshape", ".view", "transpose", "permute", "flatten", "split heads", "unfold")
    ):
        return _GLYPH_STYLES["transform"]
    if any(word in lowered for word in ("attention", "matmul", "correlation", "state space", "selective scan")):
        return _GLYPH_STYLES["attention"]
    if any(word in lowered for word in ("linear", "projection", "_proj", "conv")):
        return _GLYPH_STYLES["projection"]
    annotation_glyph = _annotation_glyph(node)
    if annotation_glyph is not None:
        return _GLYPH_STYLES[annotation_glyph]
    if any(word in lowered for word in ("decomp", "head", "forecast", "output")):
        return GlyphStyle("operator", "#ebfbee", "#2b8a3e")
    if any(word in lowered for word in ("norm", "residual", "add", "merge", "concat")):
        return GlyphStyle("operator", "#fff9db", "#9c6f00")
    if any(word in lowered for word in ("attention", "correlation", "mix", "fft")):
        return GlyphStyle("operator", "#fff0f0", "#c92a2a")
    if any(word in lowered for word in ("embed", "projection", "linear", "conv")):
        return GlyphStyle("operator", "#fff4e6", "#d9480f")
    if fully_expanded:
        return GlyphStyle("operator", "#e7f5ff", "#1864ab")
    return _GLYPH_STYLES["operator"]
