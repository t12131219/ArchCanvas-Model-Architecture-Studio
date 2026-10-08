"""Portable source-defined modules, inspected and composed without execution.

The generated adapter names every tensor return slot and gives it a real
Identity output anchor. Those anchors keep passthrough/multi-output modules
traceable when the source hierarchy is collapsed; they are source operations,
not invented IR relations. User source is never imported into this process.
"""
from __future__ import annotations

import ast
from copy import deepcopy
from functools import lru_cache
import hashlib
import json
import math
import re
from pathlib import Path
import tempfile

from archcanvas_python import AnalysisError, analyze_project

MAX_CUSTOM_MODULES = 24
MAX_CUSTOM_SOURCE_BYTES = 128_000
MAX_CUSTOM_PORTS = 16
ADAPTER = "_ArchCanvasCustomModule"
PROBE = "_ArchCanvasCustomProbe"
PROBE_MODULE = "archcanvas_custom_probe"


def _error(message, code="custom_module_contract", **details):
    from .draft import DraftError
    raise DraftError(message, diagnostics=[{"code": code, "message": message,
                                           "technical": message, **details}])


def _json_value(value, depth=0):
    if depth > 8:
        _error("构造参数嵌套过深；请使用有限 JSON 字面量。")
    if value is None or type(value) in (str, bool, int):
        return
    if type(value) is float and math.isfinite(value):
        return
    if isinstance(value, list) and len(value) <= 64:
        for item in value:
            _json_value(item, depth + 1)
        return
    if isinstance(value, dict) and len(value) <= 64 and all(type(key) is str for key in value):
        for item in value.values():
            _json_value(item, depth + 1)
        return
    _error("构造参数仅接受有限 JSON 字面量；不能传入表达式或可执行对象。")


def _scope_bindings(statements):
    """Names that can replace a class or method in its containing namespace.

    Nested function/class bodies belong to another namespace, so their local
    variables must not be mistaken for rebinding the surrounding module.
    """
    bindings = []
    pending = list(statements)
    while pending:
        node = pending.pop()
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            bindings.append(node.name)
            continue
        if isinstance(node, ast.Lambda):
            continue
        if isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)):
            bindings.append(node.id)
        elif isinstance(node, ast.Import):
            bindings.extend(alias.asname or alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            bindings.extend(alias.asname or alias.name for alias in node.names)
        elif isinstance(node, (ast.MatchAs, ast.MatchStar)) and node.name:
            bindings.append(node.name)
        elif isinstance(node, ast.ExceptHandler) and node.name:
            bindings.append(node.name)
        pending.extend(ast.iter_child_nodes(node))
    return bindings


def _signature(method, context):
    if method.decorator_list:
        _error(f"{context} 的装饰器可能改变调用合同；当前仅支持直接编写的普通实例方法。")
    args = method.args
    if args.vararg or args.kwarg:
        _error(f"{context} 的 *args / **kwargs 无法确定端口或构造字段；请写出具名参数。")
    positional = list(args.posonlyargs) + list(args.args)
    if not positional or positional[0].arg != "self":
        _error(f"{context} 必须是直接编写且以 self 开始的实例方法。")
    names = positional[1:] + list(args.kwonlyargs)
    if len(set(arg.arg for arg in positional + list(args.kwonlyargs))) != len(positional) + len(args.kwonlyargs):
        _error(f"{context} 含有重复参数名；请为每个调用端口或构造字段使用唯一名称。")
    if len(names) > MAX_CUSTOM_PORTS or any(not arg.arg.isascii() or len(arg.arg) > 64 for arg in names):
        _error(f"{context} 最多允许 {MAX_CUSTOM_PORTS} 个 ASCII 具名参数。")
    defaults = dict(zip([arg.arg for arg in positional[-len(args.defaults):]], args.defaults)) if args.defaults else {}
    defaults.update({arg.arg: default for arg, default in zip(args.kwonlyargs, args.kw_defaults) if default is not None})
    return names, {arg.arg for arg in args.posonlyargs[1:]}, defaults


def _call_arguments(names, positional_only, values):
    return ", ".join(values[arg.arg] if arg.arg in positional_only else f"{arg.arg}={values[arg.arg]}" for arg in names)


def _access(expression, path):
    for segment in path:
        expression += f"[{segment['key']!r}]" if segment["kind"] == "key" else f"[{segment['index']}]"
    return expression


def custom_filename(definition):
    return f"archcanvas_custom_{definition['digest'][:24]}.py"


def custom_source(definition):
    """Original bytes plus a deterministic adapter; no symbol rewriting."""
    tree = ast.parse(definition["source"])
    identifiers = {item.id for item in ast.walk(tree) if isinstance(item, ast.Name)}
    identifiers.update(item.arg for item in ast.walk(tree) if isinstance(item, ast.arg))
    identifiers.update(item.name for item in ast.walk(tree) if isinstance(item, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)))
    identifiers.update((item.asname or item.name.split(".")[0]) for item in ast.walk(tree) if isinstance(item, ast.alias))
    nn_alias, suffix = "_archcanvas_nn", 1
    while nn_alias in identifiers:
        nn_alias = f"_archcanvas_nn_{suffix}"; suffix += 1
    cls = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == definition["entry"])
    init = next((node for node in cls.body if isinstance(node, ast.FunctionDef) and node.name == "__init__"), None)
    names, positional_only, _ = _signature(init, "__init__") if init else ([], set(), {})
    constructor = _call_arguments(names, positional_only, {key: repr(value) for key, value in definition["constructorValues"].items()})
    forward = next(node for node in cls.body if isinstance(node, ast.FunctionDef) and node.name == "forward")
    names, positional_only, _ = _signature(forward, "forward")
    arguments = _call_arguments(names, positional_only, {arg.arg: arg.arg for arg in names})
    lines = [definition["source"].rstrip(), "", "# Stable output anchors for ArchCanvas composition; no execution occurred.",
             f"from torch import nn as {nn_alias}", "", f"class {ADAPTER}({nn_alias}.Module):",
             "    def __init__(self):", "        super().__init__()",
             f"        self.inner = {definition['entry']}({constructor})"]
    for output in definition["outputs"]:
        lines.append(f"        self.{output['id']} = {nn_alias}.Identity()")
    lines += ["", f"    def forward(self, {', '.join(arg.arg for arg in names)}):",
              f"        result = self.inner({arguments})"]
    entries = [f"{output['id']!r}: self.{output['id']}({_access('result', output['path'])})" for output in definition["outputs"]]
    lines += ["        return {" + ", ".join(entries) + "}", ""]
    return "\n".join(lines)


def _probe_source(module, cls, constructor, inputs):
    arguments = ", ".join(arg["id"] for arg in inputs)
    calls = ", ".join(arg["id"] if arg.get("positionalOnly") else f"{arg['name']}={arg['id']}" for arg in inputs)
    return "\n".join(["from torch import nn", f"from {module} import {cls}", f"class {PROBE}(nn.Module):",
                     "    def __init__(self):", "        super().__init__()", f"        self.module = {cls}({constructor})",
                     f"    def forward(self, {arguments}):", f"        return self.module({calls})", ""])


def _analyze(source, filename, probe):
    try:
        with tempfile.TemporaryDirectory(prefix="archcanvas-custom-static-") as temporary:
            root = Path(temporary)
            (root / filename).write_text(source, encoding="utf-8")
            (root / f"{PROBE_MODULE}.py").write_text(probe, encoding="utf-8")
            return analyze_project(root, f"{PROBE_MODULE}:{PROBE}")
    except (AnalysisError, SyntaxError, ValueError) as exc:
        _error(f"自定义模块静态分析失败：{exc}", "custom_source_analysis")


@lru_cache(maxsize=64)
def _preview(encoded):
    request = json.loads(encoded)
    source, entry, label, values = request["source"], request["entry"], request["label"], request["constructorValues"]
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        _error(f"源码第 {exc.lineno} 行语法错误：{exc.msg}", "custom_source_syntax", line=exc.lineno)
    try:
        # Compile only to catch parser-valid but Python-invalid constructs
        # (duplicate arguments, top-level return, break, and similar cases).
        # Compilation produces bytecode metadata; it never imports or runs the
        # submitted source.
        compile(source, "<archcanvas-custom>", "exec", dont_inherit=True)
    except SyntaxError as exc:
        _error(f"源码第 {exc.lineno} 行不能作为 Python 模块编译：{exc.msg}", "custom_source_syntax", line=exc.lineno)
    if any((isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in {ADAPTER, PROBE})
           or (isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store) and node.id in {ADAPTER, PROBE})
           or (isinstance(node, ast.alias) and node.asname in {ADAPTER, PROBE}) for node in ast.walk(tree)):
        _error("源码使用了 ArchCanvas 保留的适配器类名；请重命名该类。")
    classes = [node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == entry]
    if len(classes) != 1 or _scope_bindings(tree.body).count(entry) != 1:
        _error("类名必须标识源码中唯一的顶层 nn.Module 类。")
    cls = classes[0]
    if cls.decorator_list or cls.keywords:
        _error("类装饰器或元类可能改变模块合同；当前静态预览不支持。")
    forward_methods = [node for node in cls.body
                       if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "forward"]
    if len(forward_methods) != 1 or isinstance(forward_methods[0], ast.AsyncFunctionDef):
        _error("自定义模块需要直接编写的 forward 方法；继承或异步 forward 尚不支持。")
    class_bindings = _scope_bindings(cls.body)
    if class_bindings.count("forward") != 1:
        _error("forward 在类体中被重新绑定；静态端口合同无法确定。")
    forward = forward_methods[0]
    args, positional_only, _ = _signature(forward, "forward")
    if forward.args.posonlyargs:
        _error("当前静态前端不支持 positional-only forward；请使用具名普通或 keyword-only 参数。")
    if not args:
        _error("自定义模块需要至少一个具名张量输入。")
    def input_identity(name):
        # Draft endpoint identities start with an alphanumeric character, and
        # input/output ids share one namespace. Keep ordinary names readable;
        # map private or output-like Python argument names deterministically.
        if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", name) and not re.fullmatch(r"output(?:_[0-9]+)?", name):
            return name
        return "input_" + hashlib.sha256(name.encode()).hexdigest()[:16]
    inputs = []
    used_input_ids = set()
    for arg in args:
        identity = input_identity(arg.arg)
        if identity in used_input_ids:
            base = identity
            suffix = 2
            while f"{base}_{suffix}" in used_input_ids:
                suffix += 1
            identity = f"{base}_{suffix}"
        used_input_ids.add(identity)
        inputs.append({"id": identity, "name": arg.arg, "positionalOnly": arg.arg in positional_only})
    init_methods = [node for node in cls.body
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "__init__"]
    if class_bindings.count("__init__") != len(init_methods) or len(init_methods) > 1 or (init_methods and isinstance(init_methods[0], ast.AsyncFunctionDef)):
        _error("自定义模块需要唯一且直接编写的普通 __init__；异步或重复构造函数尚不支持。")
    init = init_methods[0] if init_methods else None
    if not init:
        nn_module_names = {"torch.nn.Module"}
        for statement in tree.body:
            if isinstance(statement, ast.ImportFrom) and statement.module == "torch.nn":
                nn_module_names.update(alias.asname or alias.name for alias in statement.names if alias.name == "Module")
            elif isinstance(statement, ast.ImportFrom) and statement.module == "torch":
                nn_module_names.update(f"{alias.asname or alias.name}.Module" for alias in statement.names if alias.name == "nn")
            elif isinstance(statement, ast.Import):
                nn_module_names.update(f"{alias.asname or alias.name}.Module" for alias in statement.names if alias.name == "torch.nn" and alias.asname)
                nn_module_names.update(f"{alias.asname or alias.name}.nn.Module" for alias in statement.names if alias.name == "torch")
        if len(cls.bases) != 1 or ast.unparse(cls.bases[0]) not in nn_module_names:
            _error("继承的构造函数无法确定具名构造字段；请在该类中直接编写 __init__。")
    init_names, init_positional, defaults = _signature(init, "__init__") if init else ([], set(), {})
    if init and init.args.posonlyargs:
        _error("当前静态前端不支持 positional-only 构造参数；请使用具名参数。")
    allowed = {arg.arg for arg in init_names}
    if set(values) - allowed:
        _error("构造参数包含 __init__ 未声明的字段：" + ", ".join(sorted(set(values) - allowed)))
    normalized = deepcopy(values)
    for arg in init_names:
        if arg.arg not in normalized:
            if arg.arg not in defaults:
                _error(f"构造参数 {arg.arg} 为必填字段；请在构造参数 JSON 中提供值。")
            try:
                normalized[arg.arg] = ast.literal_eval(defaults[arg.arg])
            except (ValueError, TypeError):
                _error(f"构造参数 {arg.arg} 的默认值不是 JSON 字面量；请明确提供值。")
        _json_value(normalized[arg.arg])
    core = {"schemaVersion": 1, "source": source, "entry": entry, "label": label,
            "constructorValues": normalized}
    digest = hashlib.sha256(json.dumps(core, sort_keys=True, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode()).hexdigest()
    filename = f"archcanvas_custom_{digest[:24]}.py"
    module = filename.removesuffix(".py")
    constructor = _call_arguments(init_names, init_positional, {key: repr(value) for key, value in normalized.items()})
    raw = _analyze(source, filename, _probe_source(module, entry, constructor, inputs))
    root = next(node for node in raw["nodes"] if node.get("instanceId") == f"instance:{PROBE_MODULE}.{PROBE}.module")
    if root.get("category") == "opaque":
        _error("类未被静态证明为 nn.Module 或无法确定 forward 边界；请检查源码继承与构造。")
    output_nodes = [node for node in raw["nodes"] if node["kind"] == "Output"]
    if not output_nodes or len(output_nodes) > MAX_CUSTOM_PORTS:
        _error(f"无法确定有效的张量输出；需要 1–{MAX_CUSTOM_PORTS} 个静态可辨认的返回槽。")
    outputs = []
    for index, node in enumerate(output_nodes):
        path = deepcopy(node["outputPath"])
        name = _access("output", path)
        outputs.append({"id": "output" if len(output_nodes) == 1 else f"output_{index + 1}", "name": name, "path": path})
    definition = {**core, "kind": "Custom_" + digest[:24], "digest": digest,
                  "sourceDigest": hashlib.sha256(source.encode()).hexdigest(), "inputs": inputs, "outputs": outputs}
    adapted = _analyze(custom_source(definition), filename, _probe_source(module, ADAPTER, "", inputs))
    if len([node for node in adapted["nodes"] if node["kind"] == "Output"]) != len(outputs):
        _error("输出适配器未保留完整的静态返回合同。")
    opaque = [node["id"] for node in adapted["nodes"] if node.get("evidence") == "opaque"]
    return {"definition": definition, "module": custom_spec(definition), "architecture": adapted,
            "verification": {"status": "passed", "scope": "static-source-and-named-module-boundary",
                             "modelExecution": "not_run", "shapeInference": "unknown",
                             "opaqueNodeIds": opaque, "warnings": [item["message"] for item in adapted["diagnostics"] if item["level"] == "warning"]}}


def preview_custom_module(payload):
    if not isinstance(payload, dict) or set(payload) != {"source", "entry", "label", "constructorValues"}:
        _error("自定义源码预览需要 source、entry、label 和 constructorValues 四个字段。")
    source, entry, label, values = payload["source"], payload["entry"], payload["label"], payload["constructorValues"]
    if type(source) is not str or not source.strip() or len(source.encode()) > MAX_CUSTOM_SOURCE_BYTES:
        _error("源码必须是非空 UTF-8 文本，最多 128 KB。")
    if type(entry) is not str:
        _error("请填写源码中 nn.Module 的类名。")
    entry = entry.removeprefix("model:")
    if not entry.isidentifier() or not entry.isascii():
        _error("模块类名必须是有效的 ASCII Python 类名。")
    if type(label) is not str or not 1 <= len(label) <= 120 or any(ord(char) < 32 for char in label):
        _error("模块显示名称需要 1–120 个非控制字符。")
    if not isinstance(values, dict) or any(type(key) is not str for key in values):
        _error("构造参数需要 JSON 对象。")
    _json_value(values)
    encoded = json.dumps({"source": source, "entry": entry, "label": label, "constructorValues": values},
                         sort_keys=True, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
    return deepcopy(_preview(encoded))


def validate_custom_definitions(raw):
    if not isinstance(raw, list) or len(raw) > MAX_CUSTOM_MODULES:
        _error(f"每份草稿最多保存 {MAX_CUSTOM_MODULES} 个自定义模块定义。")
    definitions, kinds = [], set()
    for definition in raw:
        if not isinstance(definition, dict):
            _error("自定义模块定义必须是经过静态预览的对象。")
        preview = preview_custom_module({key: definition.get(key) for key in ("source", "entry", "label", "constructorValues")})
        if definition != preview["definition"]:
            _error("自定义模块源码、哈希或端口合同已变化；请重新静态预览，保留原草稿。", "custom_definition_mismatch")
        if definition["kind"] in kinds:
            _error("草稿存在重复的自定义模块定义。")
        kinds.add(definition["kind"]); definitions.append(deepcopy(definition))
    return definitions


def custom_spec(definition):
    return {"kind": definition["kind"], "label": definition["label"], "category": "custom",
            "description": "源码自定义模块；具名端口已静态检查，输出形状未知，模型未执行。",
            "defaults": {}, "parameters": [],
            "ports": [{"id": port["id"], "name": port["name"], "direction": direction, "type": "tensor"}
                      for direction, key in (("in", "inputs"), ("out", "outputs")) for port in definition[key]]}


def custom_output_expression(definition, port_id, expression):
    if not any(port["id"] == port_id for port in definition["outputs"]):
        _error("自定义模块输出端口不属于已验证的合同。")
    return f"{expression}[{port_id!r}]"
