"""A formatting-preserving, one-token lowering independent of its delta oracle.

Registered contract v1: exact external PyTorch Dropout.p and
MultiheadAttention.dropout, explicitly written as an AST floating-point Constant.
Only UTF-8/UTF-8-BOM files are supported. AST UTF-8 byte columns plus tokenize
identify one NUMBER token; all other bytes, comments, newlines and BOM survive.
Names, expressions, omitted defaults and integer tokens have no lowering.
"""

from __future__ import annotations

import ast
import copy
import io
import math
import tokenize
from typing import Any

from archcanvas_python.frontend import Corpus, digest


TRANSFORM = {"id": "pytorch-explicit-dropout-float", "version": 1, "profile": "parameter-static", "engine": "stdlib-ast-tokenize-byte-splice", "parameters": {"Dropout": "p", "MultiheadAttention": "dropout"}}


class LoweringError(ValueError):
    pass


def anchor_key(origin: dict[str, Any]) -> tuple[Any, ...]:
    return tuple(origin.get(key) for key in ("path", "line", "column", "endLine", "endColumn"))


def semantic_facts(architecture: dict[str, Any]) -> dict[str, Any]:
    """Full declared facts, retaining origins while allowing evidence offsets to move."""
    result = copy.deepcopy({key: architecture[key] for key in ("schemaVersion", "id", "label", "entry", "nodes", "edges")})
    for node in result["nodes"]:
        node.pop("source", None)
        if "parameterOrigins" in node:
            # Literal spelling changes are the necessary evidence delta. Names
            # and derived expressions remain meaningful semantic source facts.
            node["parameterOrigins"] = {name: {key: value for key, value in origin.items() if key in ("kind", "path") or (key == "expression" and origin["kind"] != "literal")} for name, origin in node["parameterOrigins"].items()}
    return result


def expected_delta(before: dict[str, Any], node_id: str, parameter: str, value: float) -> tuple[dict[str, Any], list[str], dict[str, Any]]:
    """Freeze expectation from original facts and intent before any source mutation."""
    if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 1:
        raise LoweringError("Dropout probability must be a finite number in [0, 1].")
    value = float(value)
    selected = next((node for node in before["nodes"] if node["id"] == node_id), None)
    if not selected:
        raise LoweringError("The selected node is absent from the source-bound architecture.")
    if TRANSFORM["parameters"].get(selected["kind"]) != parameter or selected.get("evidence") != "contract" or not selected.get("instanceId"):
        raise LoweringError("Unsupported parameter: only explicit PyTorch Dropout.p and MultiheadAttention.dropout constructors are registered.")
    origin = selected.get("parameterOrigins", {}).get(parameter)
    if not origin or origin["kind"] != "literal" or type(selected["parameters"].get(parameter)) is not float:
        raise LoweringError("Unsupported parameter origin: an explicit float literal is required; constructor arguments, config references, derived expressions and omitted defaults need a separately proven source rule.")
    if selected["parameters"][parameter] == value:
        raise LoweringError("The requested value equals the current source parameter; there is no source change to review.")
    affected = [node["id"] for node in before["nodes"] if anchor_key(node.get("parameterOrigins", {}).get(parameter, {})) == anchor_key(origin) and node.get("kind") == selected["kind"]]
    if not affected:
        raise LoweringError("The literal has no proven affected calls.")
    if any(node["parameters"][parameter] != selected["parameters"][parameter] for node in before["nodes"] if node["id"] in affected):
        raise LoweringError("The shared origin has inconsistent original parameter facts.")
    expected = semantic_facts(before)
    for node in expected["nodes"]:
        if node["id"] in affected:
            node["parameters"][parameter] = value
    return expected, affected, {"nodeId": node_id, "parameter": parameter, "before": selected["parameters"][parameter], "after": value, "scope": "source_origin", "origin": copy.deepcopy(origin)}


def rewrite_literal(raw: bytes, origin: dict[str, Any], kind: str, parameter: str, before_value: float, value: float, corpus: Corpus) -> bytes:
    """Re-locate the original AST argument; never search by literal value or class name."""
    bom = b"\xef\xbb\xbf" if raw.startswith(b"\xef\xbb\xbf") else b""
    content = raw[len(bom):].decode("utf-8")
    tree = ast.parse(content)
    candidates = [node for node in ast.walk(tree) if isinstance(node, ast.Constant) and (node.lineno, node.col_offset, node.end_lineno, node.end_col_offset) == (origin["line"], origin["column"], origin["endLine"], origin["endColumn"])]
    if len(candidates) != 1 or type(candidates[0].value) is not float or candidates[0].value != before_value:
        raise LoweringError("The frozen float AST argument is no longer unique or does not match the original value.")
    atom = candidates[0]
    parents = {child: parent for parent in ast.walk(tree) for child in ast.iter_child_nodes(parent)}
    call = parents.get(atom)
    if isinstance(call, ast.keyword):
        if call.arg != parameter:
            raise LoweringError("The anchor is not the named constructor argument.")
        call = parents.get(call)
    elif not isinstance(call, ast.Call) or call.args.index(atom) != (0 if kind == "Dropout" else 2):
        raise LoweringError("The anchor is not the registered positional constructor argument.")
    if not isinstance(call, ast.Call):
        raise LoweringError("A direct constructor argument is required.")
    unit = next((item for item in corpus.units.values() if item.path == origin["path"]), None)
    if not unit:
        raise LoweringError("The argument source is outside the frozen corpus.")
    ancestor = parents.get(call)
    while ancestor is not None and not isinstance(ancestor, ast.FunctionDef):
        ancestor = parents.get(ancestor)
    if ancestor is None or ancestor.name != "__init__":
        raise LoweringError("Only directly authored Module initializer arguments are registered.")
    shadowed = {arg.arg: None for arg in ancestor.args.args + ancestor.args.kwonlyargs}
    for item in ast.walk(ancestor):
        if isinstance(item, ast.Name) and isinstance(item.ctx, ast.Store):
            shadowed[item.id] = None
    if unit.resolve(call.func, shadowed) != f"torch.nn.{kind}" or not corpus.framework_is_unshadowed():
        raise LoweringError("The constructor's external PyTorch symbol is not independently proven.")
    # A keyword can collide with a positional binding; Python permits this
    # syntax but construction would fail, so it cannot enter the registered gate.
    position = 0 if kind == "Dropout" else 2
    bound = [keyword for keyword in call.keywords if keyword.arg == parameter]
    if any(isinstance(arg, ast.Starred) for arg in call.args) or any(keyword.arg is None for keyword in call.keywords) or len(bound) > 1 or (bound and len(call.args) > position):
        raise LoweringError("Unpacked or duplicated constructor parameters are unsupported.")
    lines = content.splitlines(keepends=True)
    if atom.lineno != atom.end_lineno:
        raise LoweringError("A single NUMBER token is required.")
    start = sum(len(line.encode("utf-8")) for line in lines[:atom.lineno - 1]) + atom.col_offset + len(bom)
    end = sum(len(line.encode("utf-8")) for line in lines[:atom.end_lineno - 1]) + atom.end_col_offset + len(bom)
    token_text = raw[start:end].decode("utf-8")
    tokens = [token for token in tokenize.generate_tokens(io.StringIO(token_text).readline) if token.type not in (tokenize.ENDMARKER, tokenize.NEWLINE)]
    if len(tokens) != 1 or tokens[0].type != tokenize.NUMBER or tokens[0].string != token_text:
        raise LoweringError("The AST span is not exactly one numeric token.")
    replacement = repr(float(value)).encode("ascii")
    changed = raw[:start] + replacement + raw[end:]
    after_tree = ast.parse(changed[len(bom):].decode("utf-8"))
    expected_tree = copy.deepcopy(tree)
    expected_atom = next(node for node in ast.walk(expected_tree) if isinstance(node, ast.Constant) and (node.lineno, node.col_offset, node.end_lineno, node.end_col_offset) == (atom.lineno, atom.col_offset, atom.end_lineno, atom.end_col_offset))
    expected_atom.value = float(value)
    if ast.dump(expected_tree, include_attributes=False) != ast.dump(after_tree, include_attributes=False):
        raise LoweringError("The staged AST changes more than the intended argument.")
    return changed


def facts_digest(architecture: dict[str, Any]) -> str:
    return digest(semantic_facts(architecture))
