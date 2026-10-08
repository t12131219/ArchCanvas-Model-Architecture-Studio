"""Recover source class/output boundaries from an independent AST replay.

This records each actual static invocation's returned Ref slots. It avoids
guessing a class or multi-output port from labels and descendant port names.
"""
from __future__ import annotations

import ast
import hashlib
from pathlib import Path
import tempfile

from archcanvas_python.frontend import Analyzer, Corpus, output_bindings
from .custom_modules import _scope_bindings
from .draft import DraftError


def _retained_constructor_names(spec):
    """A keyword-call boundary needs direct ordinary Python signatures.

    Unsupported classes may still be displayed by the static frontend, but
    they cannot certify a retained executable call boundary for generation.
    """
    cls = spec.definition
    if cls.decorator_list or cls.keywords or _scope_bindings(spec.unit.tree.body).count(cls.name) != 1:
        return None
    bindings = _scope_bindings(cls.body)
    methods = {}
    for name in ("__init__", "forward"):
        candidates = [item for item in cls.body if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and item.name == name]
        if len(candidates) != bindings.count(name) or len(candidates) > 1:
            return None
        if not candidates:
            continue
        method = candidates[0]
        args = method.args
        if (isinstance(method, ast.AsyncFunctionDef) or method.decorator_list or args.posonlyargs
                or args.vararg or args.kwarg or not args.args or args.args[0].arg != "self"):
            return None
        methods[name] = method
    if "forward" not in methods:
        return None
    initializer = methods.get("__init__")
    if initializer is None:
        if len(cls.bases) != 1 or spec.unit.resolve(cls.bases[0]) != "torch.nn.Module":
            return None
        return []
    return [item.arg for item in initializer.args.args[1:]] + [item.arg for item in initializer.args.kwonlyargs]


class _BoundaryAnalyzer(Analyzer):
    def __init__(self, corpus):
        super().__init__(corpus)
        self.boundaries = {}

    def invoke(self, spec, args, keywords, parent, call_unit, call_source, label=None):
        key = f"call:{spec.identity}"
        occurrence = self.counters.get(key, 0)
        identity = key if occurrence == 0 else f"{key}@{occurrence + 1}"
        result = super().invoke(spec, args, keywords, parent, call_unit, call_source, label)
        if spec.definition:
            constructor_names = _retained_constructor_names(spec)
            if constructor_names is None:
                return result
            self.boundaries[identity] = {"module": spec.unit.module, "class": spec.definition.name,
                                         "constructorNames": constructor_names,
                                         "outputs": [{"source": {"nodeId": value.node, "portId": value.port}, "path": path}
                                                     for value, path in output_bindings(result)]}
        return result


def source_module_contracts(architecture):
    from .source_import import _analyze_sources
    original = _analyze_sources(architecture)
    with tempfile.TemporaryDirectory(prefix="archcanvas-source-boundaries-") as temporary:
        root = Path(temporary)
        for item in original["sources"]:
            try:
                compile(item["content"], item["path"], "exec", dont_inherit=True)
            except SyntaxError as exc:
                raise DraftError(f"保留源码 {item['path']}:{exc.lineno} 无法作为 Python 模块编译：{exc.msg}") from exc
            path = root / item["path"]; path.parent.mkdir(parents=True, exist_ok=True)
            raw = item["content"].encode("utf-8")
            if hashlib.sha256(raw).hexdigest() != item["digest"]:
                raw = b"\xef\xbb\xbf" + raw
            path.write_bytes(raw)
        module, name = original["entry"].split(":")
        analyzer = _BoundaryAnalyzer(Corpus(root))
        replayed = analyzer.analyze(module, name)
        if replayed != original:
            raise DraftError("源码模块边界的独立重放与原始事实不一致。")
        return analyzer.boundaries
