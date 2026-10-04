"""Registered symbolic-shape unary input rebinding and exact Name-token lowering.

Expectation is frozen from the original architecture and inspected lexical
scope, never from lowered source. The byte transform independently reparses
the original Name argument and proves it is the only AST semantic change.
"""

from __future__ import annotations

import ast
import copy
import io
import tokenize
from pathlib import Path
from typing import Any

from .lowering import LoweringError, semantic_facts


REBIND_TRANSFORM = {"id": "pytorch-symbolic-unary-rebind", "version": 1, "profile": "symbolic-rebind-static", "engine": "stdlib-ast-tokenize-byte-splice", "operators": ["Identity", "Dropout", "ReLU", "GELU"], "scope": "entry-straightline-forward", "contract": "same-base-shape-and-dtype-preserving-chain"}


def expected_rebind(before: dict[str, Any], root: Path, entry: str, node_id: str, port_id: str, producer_node: str, producer_port: str) -> tuple[dict[str, Any], list[str], dict[str, Any]]:
    # This inspector parses ORIGINAL source scope and framework contracts. It
    # does not lower code and has no access to the transaction's staged tree.
    from archcanvas_python.rebind import inspect_rebind

    evidence = inspect_rebind(root, entry, node_id, architecture=before)
    if not evidence.get("supported"):
        raise LoweringError("Unsupported RebindInput: " + "; ".join(evidence.get("blockers", ["No lexical and shape/type proof is available."])))
    if evidence.get("sourceDigest") != before["sourceDigest"] or evidence.get("irDigest") != before["irDigest"]:
        raise LoweringError("Rebind scope evidence does not match the original source/IR binding.")
    target = evidence["target"]
    if target["nodeId"] != node_id or target["portId"] != port_id:
        raise LoweringError("Rebind target must identify the exact registered unary input port.")
    candidates = [item for item in evidence["candidates"] if item["binding"]["nodeId"] == producer_node and item["binding"]["portId"] == producer_port]
    if len(candidates) != 1:
        raise LoweringError("Rebind producer must be one unique in-scope, dominating, contract-compatible candidate.")
    candidate = candidates[0]
    current = target["currentBinding"]
    next_binding = candidate["binding"]
    if current == next_binding:
        raise LoweringError("The requested producer is already bound to the target input; there is no source change to review.")
    contract = candidate["contract"]
    base = target.get("baseTensorId")
    if contract.get("runtimeVerified") is not False or not base or contract.get("baseTensorId") != base or contract.get("shape") != {"kind": "symbol", "identity": f"shape:{base}"} or contract.get("dtype") != {"kind": "symbol", "identity": f"dtype:{base}"}:
        raise LoweringError("A proven symbolic shape/dtype contract is required; unknown is not compatible.")
    expected = semantic_facts(before)
    edges = [edge for edge in expected["edges"] if edge["target"] == {"nodeId": node_id, "portId": port_id}]
    if len(edges) != 1 or edges[0]["source"] != {"nodeId": current["nodeId"], "portId": current["portId"]} or edges[0]["tensorId"] != current["tensorId"]:
        raise LoweringError("The inspected lexical slot does not match one exact original graph binding.")
    edges[0]["source"] = {"nodeId": next_binding["nodeId"], "portId": next_binding["portId"]}
    edges[0]["tensorId"] = next_binding["tensorId"]
    slot = copy.deepcopy(target["slot"])
    if slot.get("variable") == candidate["variable"]:
        raise LoweringError("The requested Name token is already the current source argument.")
    affected = [node_id]
    # Existing output tensor IDs identify calls and remain stable. Every
    # downstream consumer is still exposed in review as behavioral impact.
    frontier = [node_id]
    while frontier:
        current_node = frontier.pop()
        for edge in before["edges"]:
            dependent = edge["target"]["nodeId"]
            if edge["source"]["nodeId"] == current_node and dependent not in affected:
                affected.append(dependent)
                frontier.append(dependent)
    intent = {"kind": "RebindInput", "nodeId": node_id, "portId": port_id, "before": {**copy.deepcopy(current), "variable": slot["variable"]}, "after": {**copy.deepcopy(next_binding), "variable": candidate["variable"]}, "scope": "single_call", "origin": slot, "contract": copy.deepcopy(contract)}
    return expected, affected, intent


def rewrite_name(raw: bytes, origin: dict[str, Any], before_name: str, after_name: str) -> bytes:
    if not after_name.isidentifier() or after_name == before_name:
        raise LoweringError("A distinct proven Python variable name is required.")
    bom = b"\xef\xbb\xbf" if raw.startswith(b"\xef\xbb\xbf") else b""
    content = raw[len(bom):].decode("utf-8")
    tree = ast.parse(content)
    key = tuple(origin.get(field) for field in ("line", "column", "endLine", "endColumn"))
    atoms = [node for node in ast.walk(tree) if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load) and (node.lineno, node.col_offset, node.end_lineno, node.end_col_offset) == key]
    if len(atoms) != 1 or atoms[0].id != before_name or origin.get("variable") != before_name or origin.get("expression") != before_name:
        raise LoweringError("The frozen input Name anchor is no longer unique or does not match the original lexical argument.")
    atom = atoms[0]
    parents = {child: parent for parent in ast.walk(tree) for child in ast.iter_child_nodes(parent)}
    call = parents.get(atom)
    if not isinstance(call, ast.Call) or call.args != [atom] or call.keywords or not isinstance(call.func, ast.Attribute) or not isinstance(call.func.value, ast.Name) or call.func.value.id != "self":
        raise LoweringError("Only a direct self-module call with one positional Name input is registered.")
    statement = parents.get(call)
    if not (isinstance(statement, ast.Assign) and statement.value is call and len(statement.targets) == 1 and isinstance(statement.targets[0], ast.Name)) and not (isinstance(statement, ast.Return) and statement.value is call):
        raise LoweringError("The rebind call must be a direct straight-line assignment or final return.")
    function = parents.get(statement)
    if not isinstance(function, ast.FunctionDef) or function.name != "forward" or function.decorator_list:
        raise LoweringError("The input call is not a directly authored undecorated forward statement.")
    lines = content.splitlines(keepends=True)
    if atom.lineno != atom.end_lineno:
        raise LoweringError("A single Name token is required.")
    offset = sum(len(line.encode("utf-8")) for line in lines[:atom.lineno - 1]) + len(bom)
    start, end = offset + atom.col_offset, offset + atom.end_col_offset
    token_text = raw[start:end].decode("utf-8")
    tokens = [token for token in tokenize.generate_tokens(io.StringIO(token_text).readline) if token.type not in (tokenize.ENDMARKER, tokenize.NEWLINE)]
    if len(tokens) != 1 or tokens[0].type != tokenize.NAME or tokens[0].string != before_name:
        raise LoweringError("The AST anchor is not exactly the original Name token.")
    changed = raw[:start] + after_name.encode("utf-8") + raw[end:]
    expected_tree = copy.deepcopy(tree)
    expected_atom = next(node for node in ast.walk(expected_tree) if isinstance(node, ast.Name) and (node.lineno, node.col_offset, node.end_lineno, node.end_col_offset) == key)
    expected_atom.id = after_name
    if ast.dump(expected_tree, include_attributes=False) != ast.dump(ast.parse(changed[len(bom):].decode("utf-8")), include_attributes=False):
        raise LoweringError("The staged AST changes more than the intended input Name.")
    return changed
