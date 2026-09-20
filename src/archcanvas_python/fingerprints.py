from __future__ import annotations

from hashlib import sha256

import libcst as cst


def content_fingerprint(node: cst.CSTNode) -> str:
    return "sha256:" + sha256(cst.Module([]).code_for_node(node).encode("utf-8")).hexdigest()


class _LiteralRedactor(cst.CSTTransformer):
    def leave_Integer(self, original_node: cst.Integer, updated_node: cst.Integer) -> cst.Name:
        return cst.Name("__ARCHCANVAS_LITERAL__")

    def leave_Float(self, original_node: cst.Float, updated_node: cst.Float) -> cst.Name:
        return cst.Name("__ARCHCANVAS_LITERAL__")

    def leave_SimpleString(self, original_node: cst.SimpleString, updated_node: cst.SimpleString) -> cst.Name:
        return cst.Name("__ARCHCANVAS_LITERAL__")


def structural_fingerprint(node: cst.CSTNode) -> str:
    redacted = node.visit(_LiteralRedactor())
    return "sha256:" + sha256(cst.Module([]).code_for_node(redacted).encode("utf-8")).hexdigest()
