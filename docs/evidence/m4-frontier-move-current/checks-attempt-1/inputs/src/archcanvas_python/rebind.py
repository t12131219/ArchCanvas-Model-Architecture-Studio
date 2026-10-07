"""Source-bound evidence for the first, strictly bounded RebindInput contract.

The result is a sidecar, not an ArchitectureIR mutation. Compatibility means
conditional symbolic shape/dtype preservation from one forward input; it does
not mean a model was executed or that arbitrary input shapes/dtypes are valid.
"""

from __future__ import annotations

import ast
import copy
from pathlib import Path
from typing import Any

from .frontend import Corpus, UNKNOWN, analyze_project, literal

PRESERVING = {"Identity", "Dropout", "ReLU", "GELU"}
REBINDSCOPE = {
    "version": 1,
    "targetKinds": sorted(PRESERVING),
    "inputSyntax": "one positional Name in directly authored self.module(Name)",
    "scope": "entry-root straight-line forward only",
    "producerSyntax": "forward parameter or uniquely assigned preceding registered unary call",
    "compatibility": "conditional same-base symbolic shape/dtype preservation",
    "inplace": False,
    "runtimeVerified": False,
    "unsupported": ["keyword inputs", "different base tensors", "reassignment", "control flow", "nested calls", "unknown calls", "mutation", "inherited or shared authored scopes", "unresolved imports or constructors"],
}


class RebindEvidenceError(ValueError):
    """The requested rebind is outside the independently checked static subset."""


def _span(unit, node: ast.AST) -> dict[str, Any]:
    return {"path": unit.path, "line": node.lineno, "column": node.col_offset, "endLine": node.end_lineno, "endColumn": node.end_col_offset, "expression": unit.expression(node), "fileDigest": unit.raw_digest}


def _binding(edge: dict[str, Any]) -> dict[str, str]:
    return {**edge["source"], "tensorId": edge["tensorId"]}


def _unary(expression: ast.AST) -> tuple[str, ast.Name] | None:
    if not isinstance(expression, ast.Call) or len(expression.args) != 1 or expression.keywords or not isinstance(expression.args[0], ast.Name):
        return None
    function = expression.func
    if not isinstance(function, ast.Attribute) or not isinstance(function.value, ast.Name) or function.value.id != "self":
        return None
    return function.attr, expression.args[0]


def _module_effect_blocker(corpus: Corpus) -> str | None:
    """Reject frozen import-time Python that could invalidate public symbols.

    The first slice has no effect analysis for factories or monkeypatching. It
    cannot certify a framework contract while ignoring a known source mutation.
    """
    for unit in corpus.units.values():
        constants = {}
        for statement in unit.tree.body:
            if isinstance(statement, (ast.Import, ast.ImportFrom)):
                if any(alias.name == "*" for alias in statement.names):
                    return f"Wildcard import at {unit.path}:{statement.lineno} is outside the bounded framework provenance contract."
                resolved = [unit.imports.get(alias.asname or alias.name.split(".")[0], "") for alias in statement.names]
                for imported in resolved:
                    if imported == "torch" or imported.startswith("torch.nn"):
                        continue
                    if not any(imported == name or imported.startswith(name + ".") for name in corpus.units):
                        return f"Unresolved external import at {unit.path}:{statement.lineno} has no bounded initialization-effects contract."
                continue
            if isinstance(statement, ast.Expr) and isinstance(statement.value, ast.Constant):
                continue
            if isinstance(statement, ast.Assign) and len(statement.targets) == 1 and isinstance(statement.targets[0], ast.Name):
                value = literal(statement.value, constants)
                if value is not UNKNOWN:
                    constants[statement.targets[0].id] = value
                    continue
            if isinstance(statement, ast.ClassDef) and not statement.decorator_list and not statement.keywords and all(isinstance(base, (ast.Name, ast.Attribute)) for base in statement.bases):
                if statement.bases and (len(statement.bases) != 1 or unit.resolve(statement.bases[0]) != "torch.nn.Module"):
                    return f"Class creation through a local or unresolved base at {unit.path}:{statement.lineno} may execute inheritance hooks; only no-base classes or a single external nn.Module base have a bounded initialization-effects contract."
                for member in statement.body:
                    if isinstance(member, ast.Expr) and isinstance(member.value, ast.Constant):
                        continue
                    if not isinstance(member, ast.FunctionDef) or member.decorator_list:
                        return f"Executable class-scope mutation or decorator at {unit.path}:{member.lineno} cannot prove external framework symbols."
                    defaults = member.args.defaults + [item for item in member.args.kw_defaults if item is not None]
                    if any(literal(default, constants) is UNKNOWN for default in defaults):
                        return f"Dynamic method default at {unit.path}:{member.lineno} has unresolved import-time effects."
                    annotations = [argument.annotation for argument in member.args.posonlyargs + member.args.args + member.args.kwonlyargs if argument.annotation is not None]
                    if member.returns is not None:
                        annotations.append(member.returns)
                    if any(any(isinstance(node, ast.Call) for node in ast.walk(annotation)) for annotation in annotations):
                        return f"Executable method annotation at {unit.path}:{member.lineno} has unresolved import-time effects."
                continue
            return f"Import-time call or framework mutation at {unit.path}:{statement.lineno} is outside the bounded external-constructor provenance contract."
    return None


def inspect_rebind(root: str | Path, entry: str, node_id: str, architecture: dict[str, Any] | None = None) -> dict[str, Any]:
    """Return compatible names/bindings and their precise source input slot.

    An optional frozen architecture must match fresh analysis completely. A
    client-supplied graph, label or source snippet can never certify a binding.
    No user import, initializer, decorator, forward or expression is executed.
    """
    observed = analyze_project(root, entry)
    result: dict[str, Any] = {"schemaVersion": 1, "status": "unsupported", "supported": False, "sourceDigest": observed["sourceDigest"], "irDigest": observed["irDigest"], "scope": copy.deepcopy(REBINDSCOPE), "target": None, "candidates": [], "excludedCandidates": [], "blockers": []}

    def reject(message: str):
        result["blockers"].append(message)
        return result

    if architecture is not None and architecture != observed:
        return reject("Frozen architecture does not match the current complete source-bound analysis.")
    target = next((node for node in observed["nodes"] if node["id"] == node_id), None)
    if target is None:
        return reject("Target node is absent from the current architecture.")
    if target.get("kind") not in PRESERVING or target.get("evidence") != "contract":
        return reject("Target must be an exact registered Identity, Dropout, ReLU or GELU framework call.")
    roots = [node for node in observed["nodes"] if not node.get("parentId")]
    if len(roots) != 1 or target.get("parentId") != roots[0]["id"]:
        return reject("Only calls directly inside the entry-root forward are supported; shared or nested authored scopes require an impact rule.")
    model = roots[0]
    corpus = Corpus(Path(root))
    module, _, classname = entry.partition(":")
    corpus.load(module)
    definition = corpus.definition(f"{module}.{classname}")
    if not definition or not corpus.framework_is_unshadowed():
        return reject("The entry and external PyTorch symbols are not independently resolved in the frozen project.")
    frozen_sources = {source["path"]: source["digest"] for source in observed["sources"]}
    evidence_sources = {value.path: value.raw_digest for value in corpus.units.values()}
    if frozen_sources != evidence_sources:
        return reject("The complete source corpus changed between architecture analysis and connection-evidence freezing.")
    effect_blocker = _module_effect_blocker(corpus)
    if effect_blocker:
        return reject(effect_blocker)
    unit, cls = definition
    if cls.decorator_list or cls.keywords or len(cls.bases) != 1 or unit.resolve(cls.bases[0]) != "torch.nn.Module":
        return reject("Only a directly authored, undecorated Module class with a single external nn.Module base is supported.")
    methods = [item for item in cls.body if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))]
    if any(not isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and not (isinstance(item, ast.Expr) and isinstance(item.value, ast.Constant)) for item in cls.body):
        return reject("Class-level attributes, nested classes and descriptor overrides are outside the registered connection contract.")
    if any(item.name not in ("__init__", "forward") or item.decorator_list or isinstance(item, ast.AsyncFunctionDef) for item in methods):
        return reject("Custom call/attribute methods, decorators and asynchronous methods are outside the registered connection contract.")
    initializers = [item for item in methods if item.name == "__init__"]
    forwards = [item for item in methods if item.name == "forward"]
    if len(initializers) != 1 or len(forwards) != 1:
        return reject("A unique directly authored initializer and forward are required.")
    initializer, forward = initializers[0], forwards[0]
    if not initializer.args.args or initializer.args.args[0].arg != "self" or not forward.args.args or forward.args.args[0].arg != "self":
        return reject("Both directly authored methods must use the unshadowed self receiver.")
    if initializer.args.vararg or initializer.args.kwarg or forward.args.vararg or forward.args.kwarg or forward.args.posonlyargs:
        return reject("Variadic and positional-only signatures are outside the registered connection contract.")
    # Independently resolve module constructors and reject mutable or ambiguous
    # symbols rather than accepting a convenient-looking IR kind alone.
    init_names = {argument.arg for argument in initializer.args.args + initializer.args.kwonlyargs}
    initializer_stores = {item.id for item in ast.walk(initializer) if isinstance(item, ast.Name) and isinstance(item.ctx, ast.Store)}
    if "self" in initializer_stores or "super" in init_names | initializer_stores:
        return reject("The self receiver and super initializer cannot be shadowed or reassigned.")
    shadowed = dict.fromkeys(init_names | initializer_stores)
    constants = dict(unit.constants)
    parameters = initializer.args.args[1:]
    if initializer.args.defaults:
        for argument, default in zip(parameters[-len(initializer.args.defaults):], initializer.args.defaults):
            constants[argument.arg] = literal(default, constants)
    for argument, default in zip(initializer.args.kwonlyargs, initializer.args.kw_defaults):
        constants[argument.arg] = literal(default, constants) if default else UNKNOWN
    attributes: dict[str, dict[str, Any]] = {}
    for statement in initializer.body:
        if isinstance(statement, ast.Expr) and isinstance(statement.value, ast.Constant):
            continue
        if isinstance(statement, ast.Expr) and isinstance(statement.value, ast.Call):
            call = statement.value
            if isinstance(call.func, ast.Attribute) and call.func.attr == "__init__" and isinstance(call.func.value, ast.Call) and isinstance(call.func.value.func, ast.Name) and call.func.value.func.id == "super" and not call.args and not call.keywords and not call.func.value.args and not call.func.value.keywords:
                continue
            return reject("Initializer contains a call outside direct registered module construction.")
        if not isinstance(statement, ast.Assign) or len(statement.targets) != 1:
            return reject("Initializer has unsupported control, unpacking, mutation or construction syntax.")
        location = statement.targets[0]
        if isinstance(location, ast.Name):
            constant = literal(statement.value, constants)
            if constant is UNKNOWN:
                return reject("Initializer local values must be frozen literal expressions; dynamic factories are unsupported.")
            constants[location.id] = constant
            continue
        if not isinstance(location, ast.Attribute) or not isinstance(location.value, ast.Name) or location.value.id != "self" or location.attr in attributes:
            return reject("Module attributes must have unique direct initializer assignments; aliases or reassignment are unsupported.")
        call = statement.value
        if not isinstance(call, ast.Call):
            return reject("Module aliases and non-call constructor values are unsupported.")
        qualified = unit.resolve(call.func, shadowed)
        kind = qualified.rsplit(".", 1)[-1]
        if qualified != f"torch.nn.{kind}" or kind not in PRESERVING:
            return reject("Every module in this first connection scope must have an exact registered preserving constructor.")
        if any(isinstance(arg, ast.Starred) for arg in call.args) or any(keyword.arg is None for keyword in call.keywords):
            return reject("Unpacked constructor arguments are unsupported.")
        names = [keyword.arg for keyword in call.keywords]
        if len(names) != len(set(names)):
            return reject("Duplicated constructor keyword arguments are unsupported.")
        values = [literal(arg, constants) for arg in call.args] + [literal(keyword.value, constants) for keyword in call.keywords]
        if any(value is UNKNOWN for value in values):
            return reject("Constructor arguments must be frozen literals in this connection scope.")
        positional_names = {"Identity": [], "Dropout": ["p", "inplace"], "ReLU": ["inplace"], "GELU": ["approximate"]}[kind]
        if len(call.args) > len(positional_names) or any(name not in positional_names for name in names):
            return reject("Constructor arguments do not match the registered preserving signature.")
        bound = dict(zip(positional_names, [literal(arg, constants) for arg in call.args]))
        if any(name in bound for name in names):
            return reject("A constructor argument is bound both positionally and by keyword.")
        bound.update({keyword.arg: literal(keyword.value, constants) for keyword in call.keywords})
        if kind in ("Dropout", "ReLU") and bound.get("inplace", False) is not False:
            return reject("In-place or unresolved mutation is forbidden in a RebindInput scope.")
        if kind == "Dropout" and (type(bound.get("p", 0.5)) not in (int, float) or not 0 <= bound.get("p", 0.5) <= 1):
            return reject("Dropout probability is not valid under its public preserving contract.")
        if kind == "GELU" and bound.get("approximate", "none") not in ("none", "tanh"):
            return reject("GELU approximate argument is outside its public contract.")
        attributes[location.attr] = {"kind": kind, "span": _span(unit, call)}
    arguments = forward.args.args[1:] + forward.args.kwonlyargs
    names = [argument.arg for argument in arguments]
    stored: dict[str, int] = dict.fromkeys(names, 1)
    for item in ast.walk(forward):
        if isinstance(item, ast.Name) and isinstance(item.ctx, ast.Store):
            if item.id == "self":
                return reject("The forward self receiver cannot be reassigned.")
            stored[item.id] = stored.get(item.id, 0) + 1
    if any(count != 1 for count in stored.values()):
        return reject("Forward parameters and local producer names cannot be reassigned anywhere in the function.")
    # Build a complete sequence first. Unsupported statements anywhere in this
    # function block the contract, even if a tempting target precedes them.
    operations = []
    returned = False
    for index, statement in enumerate(forward.body):
        if isinstance(statement, ast.Expr) and isinstance(statement.value, ast.Constant) and not returned:
            continue
        if returned:
            return reject("Statements following return are outside the unique straight-line scope.")
        if isinstance(statement, ast.Assign) and len(statement.targets) == 1 and isinstance(statement.targets[0], ast.Name):
            output_name = statement.targets[0].id
            expression = statement.value
        elif isinstance(statement, ast.Return):
            returned = True
            output_name = None
            expression = statement.value
            if isinstance(expression, ast.Name):
                operations.append({"index": index, "returnName": expression.id})
                continue
        else:
            return reject("Forward must contain only direct unary assignments and a single return; control flow, mutations and unknown calls are unsupported.")
        call_info = _unary(expression)
        if call_info is None:
            return reject("Forward inputs must be single positional local names in self.module(Name); keywords, expressions and nested calls are unsupported.")
        attribute, argument = call_info
        if attribute not in attributes:
            return reject("Forward call does not resolve to a uniquely constructed preserving module attribute.")
        matches = [node for node in observed["nodes"] if node.get("parentId") == model["id"] and node.get("source", {}).get("path") == unit.path and node["source"].get("line") == expression.lineno and node["source"].get("endLine") == expression.end_lineno and node["source"].get("expression") == unit.expression(expression)]
        if len(matches) != 1:
            return reject("An authored call anchor maps ambiguously to canonical invocations; a unique impact mapping is required.")
        call_node = matches[0]
        if call_node["kind"] != attributes[attribute]["kind"] or call_node.get("evidence") != "contract":
            return reject("Authored constructor evidence and canonical call facts disagree.")
        operations.append({"index": index, "call": expression, "argument": argument, "attribute": attribute, "outputName": output_name, "node": call_node})
    if not returned:
        return reject("A uniquely authored return is required for this connection contract.")
    selected_operations = [operation for operation in operations if operation.get("node", {}).get("id") == node_id]
    if len(selected_operations) != 1:
        return reject("The target is not a unique directly authored unary operation in the entry scope.")
    chosen = selected_operations[0]
    values: dict[str, dict[str, Any]] = {}
    for argument in arguments:
        incoming = [edge for edge in observed["edges"] if edge["target"]["nodeId"] == model["id"] and any(port["id"] == edge["target"]["portId"] and port["name"] == argument.arg and port["direction"] == "in" for port in model["ports"])]
        if len(incoming) != 1:
            return reject("A forward parameter does not have one uniquely bound canonical input tensor.")
        binding = _binding(incoming[0])
        values[argument.arg] = {"variable": argument.arg, "binding": binding, "definition": _span(unit, argument), "baseTensorId": binding["tensorId"], "chain": []}
    candidates_at_target = None
    for operation in operations:
        if "returnName" in operation:
            if operation["returnName"] not in values:
                return reject("Return references a name without a supported dominating definition.")
            continue
        argument = operation["argument"]
        previous = values.get(argument.id)
        if previous is None:
            return reject("A producer name has no supported dominating definition in this forward scope.")
        node = operation["node"]
        incoming = [edge for edge in observed["edges"] if edge["target"]["nodeId"] == node["id"]]
        if len(incoming) != 1 or _binding(incoming[0]) != previous["binding"]:
            return reject("Canonical producer/consumer binding disagrees with independently interpreted local source names.")
        input_ports = [port for port in node["ports"] if port["direction"] == "in" and port["name"] == "input" and port["id"] == incoming[0]["target"]["portId"]]
        if len(input_ports) != 1:
            return reject("The target port is outside the single registered unary input contract.")
        if node["id"] == node_id:
            candidates_at_target = copy.deepcopy(values)
            slot = _span(unit, argument) | {"variable": argument.id}
            result["target"] = {"nodeId": node_id, "portId": incoming[0]["target"]["portId"], "slot": slot, "currentBinding": _binding(incoming[0]), "call": _span(unit, operation["call"]), "baseTensorId": previous["baseTensorId"]}
        output_name = operation["outputName"]
        if output_name:
            outputs = [port for port in node["ports"] if port["direction"] == "out" and port["name"] == "output"]
            tensors = {edge["tensorId"] for edge in observed["edges"] if edge["source"]["nodeId"] == node["id"] and edge["source"]["portId"] == outputs[0]["id"]} if len(outputs) == 1 else set()
            if len(outputs) != 1 or len(tensors) > 1:
                return reject("A unary producer output does not have one canonical tensor identity.")
            # Unused authored outputs still have canonical output ports. The
            # frontend's fixed output identity rule supplies their tensor ID;
            # no producer call or architecture node is invented for the view.
            binding = {"nodeId": node["id"], "portId": outputs[0]["id"], "tensorId": next(iter(tensors), f"tensor:{node['id']}:output")}
            values[output_name] = {"variable": output_name, "binding": binding, "definition": _span(unit, operation["call"]), "baseTensorId": previous["baseTensorId"], "chain": previous["chain"] + [{"nodeId": node["id"], "kind": node["kind"], "contract": f"torch.nn.{node['kind']}", "source": _span(unit, operation["call"])}]}
    base = result["target"]["baseTensorId"]
    for value in (candidates_at_target or {}).values():
        if value["baseTensorId"] != base:
            result["excludedCandidates"].append({"variable": value["variable"], "reason": "A different forward-input origin has no proven symbolic shape/dtype compatibility."})
            continue
        contract = {"baseTensorId": base, "shape": {"kind": "symbol", "identity": f"shape:{base}"}, "dtype": {"kind": "symbol", "identity": f"dtype:{base}"}, "basis": "registered same-origin shape/dtype preservation", "runtimeVerified": False, "conditional": True, "condition": "The input is a tensor accepted by every registered operation on both source chains; concrete dimensions and dtype are unknown.", "chain": value["chain"]}
        result["candidates"].append({key: copy.deepcopy(value[key]) for key in ("variable", "binding", "definition")} | {"contract": contract})
    result["status"], result["supported"] = "supported", True
    return result
