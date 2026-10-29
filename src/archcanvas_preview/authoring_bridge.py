"""Bounded static Summary source-module compilation; never executes user code."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import threading

from .analyze import AdapterError, MAX_EDGES, MAX_NODES

MAX_SOURCE_BYTES = 120_000
MAX_RESULT_BYTES = 16_000_000
_COMPILATION = threading.BoundedSemaphore(1)


def _request(source, entry, constructor):
    if not isinstance(source, str) or not source.strip() or len(source.encode("utf-8")) > MAX_SOURCE_BYTES:
        raise AdapterError("Summary 模块源码必须为非空文本，且不超过 120 KB。")
    if not isinstance(entry, str) or len(entry) > 240 or not entry.isidentifier():
        raise AdapterError("Summary 模块入口必须是源码中的类名或函数名。")
    if constructor is None:
        constructor = {}
    if not isinstance(constructor, dict) or any(not isinstance(key, str) or not key.isidentifier() for key in constructor):
        raise AdapterError("Summary 模块构造参数必须是名称到 JSON 值的对象。")
    try:
        text = json.dumps(constructor, ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError, RecursionError) as error:
        raise AdapterError("构造参数必须是有限 JSON 值。") from error
    if len(text.encode("utf-8")) > 16_000:
        raise AdapterError("构造参数超过 16 KB。")
    return {"source": source, "entry": entry, "constructor": constructor}


def inspect_source(source):
    payload = _request(source, "_inspect", {})
    return _run_task({**payload, "task": "inspect"})


def generate_python(document):
    if not isinstance(document, dict) or len(json.dumps(document, ensure_ascii=False, allow_nan=False).encode()) > MAX_RESULT_BYTES:
        raise AdapterError("Python 生成文档无效或超过 16 MB。")
    return _run_task({"task": "generate", "document": document})


def _run_task(payload):
    if not _COMPILATION.acquire(blocking=False):
        raise AdapterError("正在进行另一个 Summary 静态分析，请完成后重试。")
    try:
        return _compile_module(payload)
    finally:
        _COMPILATION.release()


def compile_source_module(source, entry, constructor=None):
    payload = _request(source, entry, constructor)
    if not _COMPILATION.acquire(blocking=False):
        raise AdapterError("正在解析另一个 Summary 源码模块，请完成后重试。")
    try:
        return _compile_module(payload)
    finally:
        _COMPILATION.release()


def _compile_module(payload):
    bootstrap = "import sys;sys.path.insert(0,sys.argv[1]);from archcanvas_preview.authoring_bridge import _module_worker;_module_worker()"
    command = [sys.executable, "-I", "-S", "-B", "-c", bootstrap, str(Path(__file__).resolve().parents[1])]
    # A file output bounds parent memory as well as the worker's output. The
    # worker's RLIMIT_FSIZE guards writes; the parent independently checks size.
    with tempfile.TemporaryFile() as output:
        try:
            result = subprocess.run(command, input=json.dumps(payload, ensure_ascii=False).encode("utf-8"), stdout=output,
                                    stderr=subprocess.DEVNULL, timeout=15, check=False)
        except subprocess.TimeoutExpired as error:
            raise AdapterError("Summary 模块静态解析超过 15 秒预算；当前编辑稿保留。") from error
        if result.returncode or output.tell() > MAX_RESULT_BYTES:
            raise AdapterError("Summary 模块静态解析失败或超过资源预算；当前编辑稿保留。")
        output.seek(0)
        try:
            response = json.load(output)
        except (ValueError, UnicodeDecodeError) as error:
            raise AdapterError("Summary 模块解析没有返回有效结果。") from error
    if response.get("error"):
        raise AdapterError(response["error"])
    if payload.get("task"):
        return response["result"]
    module = response["module"]
    if module.get("schema") != "semantic-module/1" or module.get("source") != payload["source"] or module.get("entry") != payload["entry"] or module.get("constructor") != payload["constructor"]:
        raise AdapterError("Summary 模块解析结果与请求来源不一致。")
    return module


def _module_worker():
    try:
        import resource
        resource.setrlimit(resource.RLIMIT_CPU, (8, 8))
        resource.setrlimit(resource.RLIMIT_AS, (512 * 1024 * 1024,) * 2)
        resource.setrlimit(resource.RLIMIT_FSIZE, (MAX_RESULT_BYTES,) * 2)
        resource.setrlimit(resource.RLIMIT_NOFILE, (48, 48))
        from archcanvas_summary_semantic.authoring import compile_module
        from archcanvas_summary_semantic.schema import validate_ir
        payload = json.load(sys.stdin)
        if payload.get("task") == "inspect":
            from archcanvas_summary_semantic.source_inventory import inspect_source
            result = inspect_source(_request(payload["source"], "_inspect", {})["source"])
            sys.stdout.write(json.dumps({"result": result}, ensure_ascii=False, allow_nan=False))
            return
        if payload.get("task") == "generate":
            from archcanvas_summary_semantic.python_export import generate_python
            result = generate_python(payload["document"])
            sys.stdout.write(json.dumps({"result": result}, ensure_ascii=False, allow_nan=False))
            return
        module = compile_module(**_request(**payload))
        ir = module["ir"]
        if len(ir["nodes"]) > MAX_NODES or len(ir["edges"]) > MAX_EDGES:
            raise ValueError("模块超过当前 480 节点 / 3600 依赖预算。")
        check = validate_ir(ir)
        if not check["ok"]:
            raise ValueError("模块未通过 Summary 原生语义校验。")
        module["analysis"]["boundary"] = {
            "mode": "isolated-static-ast", "modelExecuted": False, "sourceTransactionBinding": False,
            "wallSeconds": 15, "cpuSeconds": 8, "addressSpaceBytes": 512 * 1024 * 1024,
            "resultBytes": MAX_RESULT_BYTES,
        }
        response = {"module": module}
    except Exception as error:
        response = {"error": str(error)[:2000]}
    sys.stdout.write(json.dumps(response, ensure_ascii=False, allow_nan=False))
