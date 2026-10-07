"""Narrow, independently declared configuration and activation transforms."""
from __future__ import annotations

import ast
import copy
import io
import math
import tokenize
from pathlib import Path
from typing import Any

from archcanvas_python.frontend import Analyzer, Corpus, Spec
from archcanvas_python.rebind import _module_effect_blocker, _span

from .lowering import LoweringError, TRANSFORM, anchor_key, semantic_facts


CONFIG_TRANSFORM = {"id": "pytorch-top-level-float-configuration", "version": 1, "profile": "parameter-static", "engine": "stdlib-ast-tokenize-byte-splice", "parameters": copy.deepcopy(TRANSFORM["parameters"]), "scope": "unique-module-constant-all-probability-readers"}
ACTIVATION_TRANSFORM = {"id": "pytorch-default-activation-replacement", "version": 1, "profile": "parameter-static", "engine": "stdlib-ast-tokenize-byte-splice", "operators": ["ReLU", "GELU"], "scope": "exact-no-argument-constructor-all-instances"}
ACTIVATION_VERIFIED_TRANSFORM = {**ACTIVATION_TRANSFORM, "id": "pytorch-verified-activation-replacement", "profile": "structural-verified"}


def _specifications(root: Path, entry: str):
    corpus = Corpus(root); corpus.load(entry.split(":", 1)[0])
    definition = corpus.definition(entry.replace(":", "."))
    if not definition or not corpus.framework_is_unshadowed():
        raise LoweringError("The entry and external PyTorch symbols are not independently resolved.")
    effect = _module_effect_blocker(corpus)
    if effect:
        raise LoweringError(effect)
    unit, cls = definition
    call = ast.copy_location(ast.Call(func=ast.Name(id=cls.name), args=[], keywords=[]), cls)
    spec = Analyzer(corpus).construct(call, unit, {}, {}, f"instance:{unit.module}.{cls.name}")
    result = []; seen = set()
    def visit(value):
        if not isinstance(value, Spec) or id(value) in seen:
            return
        seen.add(id(value)); result.append(value)
        for child in list(value.attributes.values()) + value.items:
            visit(child)
    visit(spec)
    return corpus, result


def _call_key(spec):
    return spec.unit.path, getattr(spec.source, "lineno", None), getattr(spec.source, "col_offset", None), getattr(spec.source, "end_lineno", None), getattr(spec.source, "end_col_offset", None)


def inspect_configuration_origin(root: Path, entry: str, node_id: str, parameter: str, architecture: dict[str, Any]) -> dict[str, Any]:
    result = {"schemaVersion": 1, "supported": False, "sourceDigest": architecture["sourceDigest"], "irDigest": architecture["irDigest"], "target": None, "affectedNodeIds": [], "blockers": []}
    try:
        target = next((node for node in architecture["nodes"] if node["id"] == node_id), None)
        if target is None or target.get("evidence") != "contract" or CONFIG_TRANSFORM["parameters"].get(target["kind"]) != parameter:
            raise LoweringError("Only registered Dropout.p and MultiheadAttention.dropout configuration readers are supported.")
        corpus, specs = _specifications(root, entry)
        if {unit.path: unit.raw_digest for unit in corpus.units.values()} != {source["path"]: source["digest"] for source in architecture["sources"]}:
            raise LoweringError("Configuration evidence does not match the frozen complete source corpus.")
        selected = [spec for spec in specs if spec.identity == target.get("instanceId")]
        if len(selected) != 1:
            raise LoweringError("The selected module has no unique authored construction identity.")
        spec = selected[0]
        origin = spec.parameter_origins.get(parameter, {})
        arguments = [node for node in ast.walk(spec.source) if isinstance(node, ast.Name) and (node.lineno, node.col_offset, node.end_lineno, node.end_col_offset) == tuple(origin.get(key) for key in ("line", "column", "endLine", "endColumn"))]
        if len(arguments) != 1:
            raise LoweringError("Configuration editing requires one directly authored Name argument.")
        name = arguments[0].id
        definitions = [statement for statement in spec.unit.tree.body if isinstance(statement, ast.Assign) and len(statement.targets) == 1 and isinstance(statement.targets[0], ast.Name) and statement.targets[0].id == name and isinstance(statement.value, ast.Constant) and type(statement.value.value) is float]
        stores = [node for node in ast.walk(spec.unit.tree) if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store) and node.id == name]
        if len(definitions) != 1 or len(stores) != 1:
            raise LoweringError("Configuration must have one unique module-top-level float literal and no shadowing/reassignment.")
        definition = definitions[0]
        if not math.isfinite(definition.value.value) or not 0 <= definition.value.value <= 1:
            raise LoweringError("The original configuration must be a valid finite probability in [0, 1].")
        parents = {child: parent for parent in ast.walk(spec.unit.tree) for child in ast.iter_child_nodes(parent)}
        reader_anchors = set()
        for atom in [node for node in ast.walk(spec.unit.tree) if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load) and node.id == name]:
            call = parents.get(atom)
            parameter_name = None
            if isinstance(call, ast.keyword):
                parameter_name = call.arg; call = parents.get(call)
            if not isinstance(call, ast.Call):
                raise LoweringError("Configuration has a derived or unregistered read; its complete impact cannot be proven.")
            qualified = spec.unit.resolve(call.func)
            kind = qualified.rsplit(".", 1)[-1]
            expected_parameter = CONFIG_TRANSFORM["parameters"].get(kind)
            if qualified != f"torch.nn.{kind}" or expected_parameter is None:
                raise LoweringError("Configuration has a reader outside registered probability constructors.")
            if parameter_name is None:
                index = 0 if kind == "Dropout" else 2
                if len(call.args) <= index or call.args[index] is not atom:
                    raise LoweringError("Configuration is not the registered positional probability argument.")
                parameter_name = expected_parameter
            if parameter_name != expected_parameter or any(isinstance(arg, ast.Starred) for arg in call.args) or any(keyword.arg is None for keyword in call.keywords):
                raise LoweringError("Configuration reader has unknown/unpacked argument binding.")
            probability_index = 0 if kind == "Dropout" else 2
            named = [keyword for keyword in call.keywords if keyword.arg == expected_parameter]
            if len(named) > 1 or (named and len(call.args) > probability_index):
                raise LoweringError("Configuration probability is duplicated across constructor argument bindings.")
            function = parents.get(call)
            while function is not None and not isinstance(function, ast.FunctionDef):
                function = parents.get(function)
            if function is None or function.name != "__init__" or any(arg.arg == name for arg in function.args.args + function.args.kwonlyargs):
                raise LoweringError("Configuration Name is not an unshadowed initializer reference to the module constant.")
            shadowed = dict.fromkeys([arg.arg for arg in function.args.args + function.args.kwonlyargs] + [node.id for node in ast.walk(function) if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store)])
            if spec.unit.resolve(call.func, shadowed) != qualified:
                raise LoweringError("Configuration framework constructor symbol is locally shadowed.")
            reader_anchors.add((spec.unit.path, call.lineno, call.col_offset, call.end_lineno, call.end_col_offset))
        readers = [item for item in specs if _call_key(item) in reader_anchors]
        if {item_key for item_key in reader_anchors} != {_call_key(item) for item in readers}:
            raise LoweringError("Some configuration reader lies outside the analyzed instance corpus; hidden consumers cannot be omitted.")
        instances = {reader.identity for reader in readers}
        affected = [node["id"] for node in architecture["nodes"] if node.get("instanceId") in instances]
        if not affected or type(target["parameters"].get(parameter)) is not float or target["parameters"][parameter] != definition.value.value:
            raise LoweringError("The selected effective parameter does not equal the unique frozen configuration literal.")
        result.update(supported=True, target={"nodeId": node_id, "parameter": parameter, "name": name, "before": definition.value.value, "origin": _span(spec.unit, definition.value) | {"kind": "configuration_literal", "configurationName": name}}, affectedNodeIds=affected)
        return result
    except LoweringError as exc:
        result["blockers"].append(str(exc)); return result


def expected_config(before, root, entry, node_id, parameter, value):
    if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 1:
        raise LoweringError("Configuration probability must be finite and in [0, 1].")
    evidence = inspect_configuration_origin(root, entry, node_id, parameter, before)
    if not evidence["supported"]:
        raise LoweringError("Unsupported configuration: " + "; ".join(evidence["blockers"]))
    target = evidence["target"]
    if target["before"] == value:
        raise LoweringError("The configuration already equals the requested probability.")
    expected = semantic_facts(before)
    corpus, specs = _specifications(root, entry)
    if {unit.path: unit.raw_digest for unit in corpus.units.values()} != {source["path"]: source["digest"] for source in before["sources"]}:
        raise LoweringError("Configuration scope changed after original evidence was frozen.")
    owners = {spec.identity for spec in specs if spec.definition and spec.unit.path == target["origin"]["path"]}
    for node in expected["nodes"]:
        if node["id"] in evidence["affectedNodeIds"]:
            probability = CONFIG_TRANSFORM["parameters"][node["kind"]]
            if node["parameters"].get(probability) != target["before"]:
                raise LoweringError("A shared configuration reader has inconsistent original effective value.")
            # Nodes may share the parameter dict by object identity; assign a
            # copy to every node rather than treating an earlier update as old.
            node["parameters"] = {**node["parameters"], probability: float(value)}
        if node.get("instanceId") in owners and target["name"] in node["parameters"]:
            node["parameters"] = {**node["parameters"], target["name"]: float(value)}
    intent = {"kind": "UpdateConfiguration", "nodeId": node_id, "parameter": parameter, "before": target["before"], "after": float(value), "configurationName": target["name"], "scope": "all_configuration_readers", "origin": target["origin"]}
    return expected, evidence["affectedNodeIds"], intent


def expected_activation(before, root, entry, node_id, activation, input_spec=None):
    if activation not in ("ReLU", "GELU"):
        raise LoweringError("Only default ReLU and GELU activation replacements are registered.")
    target = next((node for node in before["nodes"] if node["id"] == node_id), None)
    if not target or target["kind"] not in ("ReLU", "GELU") or target.get("evidence") != "contract":
        raise LoweringError("The target is not a registered activation invocation.")
    if target["kind"] == activation:
        raise LoweringError("The requested activation is already constructed.")
    corpus, specs = _specifications(root, entry)
    if {unit.path: unit.raw_digest for unit in corpus.units.values()} != {source["path"]: source["digest"] for source in before["sources"]}:
        raise LoweringError("Activation evidence does not match the frozen complete source corpus.")
    selected = [spec for spec in specs if spec.identity == target.get("instanceId")]
    if len(selected) != 1:
        raise LoweringError("The activation construction identity is ambiguous.")
    selected = selected[0]; call = selected.source
    if not isinstance(call, ast.Call) or call.args or call.keywords or not isinstance(call.func, ast.Attribute) or selected.unit.resolve(call.func) != f"torch.nn.{target['kind']}":
        raise LoweringError("Only direct no-argument external nn.ReLU()/nn.GELU() constructors are registered.")
    instances = {spec.identity for spec in specs if _call_key(spec) == _call_key(selected)}
    affected = [node["id"] for node in before["nodes"] if node.get("instanceId") in instances]
    expected = semantic_facts(before)
    for node in expected["nodes"]:
        if node["id"] not in affected:
            continue
        if node["kind"] != target["kind"] or node["parameters"]:
            raise LoweringError("Shared activation readers have unsupported argument or kind facts.")
        node["kind"] = activation
        suffix = node["instanceId"].rsplit(".", 1)[-1]
        if suffix.isdigit():
            node["label"] = f"{activation} {int(suffix) + 1}"
    end_column = call.func.end_col_offset
    origin = _span(selected.unit, call.func) | {"column": end_column - len(target["kind"]), "expression": target["kind"], "activation": target["kind"], "constructor": _span(selected.unit, call)}
    intent = {"kind": "ReplaceActivation", "nodeId": node_id, "before": target["kind"], "after": activation, "scope": "all_constructor_instances", "origin": origin, "contract": {"basis": "public floating-tensor shape/dtype preserving default activations", "condition": "Both activations require a supported floating input tensor; no concrete shape, dtype or numerical equivalence is claimed by the static profile.", "runtimeVerified": False}}
    if input_spec is not None:
        from archcanvas_python.structural_rebind import inspect_structural_rebind
        if len(affected) != 1:
            raise LoweringError("Structural activation verification currently requires one root-authored invocation.")
        input_port = next(port["id"] for port in target["ports"] if port["direction"] == "in")
        evidence = inspect_structural_rebind(root, entry, node_id, input_port, input_spec, before)
        if not evidence["supported"]:
            raise LoweringError("Unsupported verified activation scope: " + "; ".join(evidence["blockers"]))
        runtime_expected = {"calls": copy.deepcopy(evidence["runtimeCalls"]), "outputs": copy.deepcopy(evidence["outputContracts"]), "state": copy.deepcopy(evidence["stateContracts"]), "stateSharing": copy.deepcopy(evidence["stateSharingContract"])}
        next(call for call in runtime_expected["calls"] if call["nodeId"] == node_id)["kind"] = activation
        intent.update(validationProfile="structural-verified", inputSpec=evidence["inputSpec"], inputSpecDigest=evidence["inputSpecDigest"], expectedRuntimeContract=runtime_expected)
    return expected, affected, intent


def rewrite_registered_atom(raw: bytes, origin: dict[str, Any], before_value: Any, after_value: Any, kind: str):
    bom = b"\xef\xbb\xbf" if raw.startswith(b"\xef\xbb\xbf") else b""
    content = raw[len(bom):].decode("utf-8"); tree = ast.parse(content)
    lines = content.splitlines(keepends=True)
    if origin["line"] != origin["endLine"]:
        raise LoweringError("Registered atom must occupy one exact token.")
    offset = len(bom) + sum(len(line.encode()) for line in lines[:origin["line"] - 1])
    start, end = offset + origin["column"], offset + origin["endColumn"]
    text = raw[start:end].decode("utf-8")
    tokens = [token for token in tokenize.generate_tokens(io.StringIO(text).readline) if token.type not in (tokenize.ENDMARKER, tokenize.NEWLINE)]
    expected_tree = copy.deepcopy(tree)
    if kind == "configuration":
        key = tuple(origin[field] for field in ("line", "column", "endLine", "endColumn"))
        atoms = [node for node in ast.walk(expected_tree) if isinstance(node, ast.Constant) and (node.lineno, node.col_offset, node.end_lineno, node.end_col_offset) == key]
        if len(atoms) != 1 or type(atoms[0].value) is not float or atoms[0].value != before_value or len(tokens) != 1 or tokens[0].type != tokenize.NUMBER:
            raise LoweringError("The configuration literal token does not match its frozen origin/value.")
        statement = next((item for item in expected_tree.body if isinstance(item, ast.Assign) and item.value is atoms[0] and len(item.targets) == 1 and isinstance(item.targets[0], ast.Name) and item.targets[0].id == origin["configurationName"]), None)
        if statement is None:
            raise LoweringError("The float token is not the registered top-level configuration assignment.")
        atoms[0].value = float(after_value); replacement = repr(float(after_value)).encode("ascii")
    else:
        constructor = origin["constructor"]
        calls = [node for node in ast.walk(expected_tree) if isinstance(node, ast.Call) and (node.lineno, node.col_offset, node.end_lineno, node.end_col_offset) == tuple(constructor[field] for field in ("line", "column", "endLine", "endColumn"))]
        if len(calls) != 1 or calls[0].args or calls[0].keywords or not isinstance(calls[0].func, ast.Attribute) or calls[0].func.attr != before_value or len(tokens) != 1 or tokens[0].type != tokenize.NAME or text != before_value:
            raise LoweringError("The default activation constructor token does not match its frozen origin.")
        calls[0].func.attr = after_value; replacement = after_value.encode("ascii")
    changed = raw[:start] + replacement + raw[end:]
    if ast.dump(expected_tree, include_attributes=False) != ast.dump(ast.parse(changed[len(bom):].decode("utf-8")), include_attributes=False):
        raise LoweringError("The registered atom splice changes more than the declared configuration/activation atom.")
    return changed
