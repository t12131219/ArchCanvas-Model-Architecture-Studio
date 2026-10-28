"""Local operand-structure analysis of declared assemblies; no Python execution."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile

from .analyze import AdapterError, MAX_NODES, MAX_EDGES
from .authoring_bridge import _COMPILATION, MAX_RESULT_BYTES

SCHEMA = "archcanvas-summary-local-assembly/1"
SCOPE = "local operand structure of the declared user assembly; not equivalence to original source or execution coverage"


def _request(ir):
    if not isinstance(ir, dict) or ir.get("schema") != "archcanvas-source-semantic/2" or not isinstance(ir.get("authoring"), dict) or ir["authoring"].get("edited") is not True:
        raise AdapterError("需要当前显式编辑的 Summary 组装稿。")
    if not isinstance(ir.get("runtime"), dict) or not isinstance(ir.get("coverage"), dict) or ir["runtime"].get("model_executed") is not False or ir["coverage"].get("scope") != "user-authored-assembly":
        raise AdapterError("局部复核仅接受未执行的组装声明。")
    nodes, edges = ir.get("nodes"), ir.get("edges")
    if not isinstance(nodes, list) or not isinstance(edges, list) or len(nodes) > MAX_NODES or len(edges) > MAX_EDGES:
        raise AdapterError("组装图超过 480 节点 / 3600 依赖预算。")
    try:
        text = json.dumps(ir, ensure_ascii=False, allow_nan=False)
        if len(text.encode("utf-8")) > MAX_RESULT_BYTES:
            raise ValueError("size")
        by = {node["id"]: node for node in nodes}
        if len(by) != len(nodes) or any(not isinstance(key, str) or not key or key.startswith("runtime:") or key == "runtime-observations" for key in by):
            raise ValueError("identity")
        for node in nodes:
            seen, at = set(), node
            while at.get("parent"):
                if at["id"] in seen or len(seen) >= 128:
                    raise ValueError("hierarchy")
                seen.add(at["id"])
                at = by[at["parent"]]
        ids = set()
        for edge in edges:
            if not isinstance(edge["id"], str) or edge["id"] in ids or edge["source"] not in by or edge["target"] not in by:
                raise ValueError("endpoint")
            ids.add(edge["id"])
    except (ValueError, TypeError, KeyError, AttributeError, RecursionError) as error:
        raise AdapterError("组装图包含无效身份、层级、端点或超出有限 JSON 预算。") from error
    return ir


def certify_declared_assembly(ir):
    payload = _request(ir)
    if not _COMPILATION.acquire(blocking=False):
        raise AdapterError("正在进行另一个 Summary 静态分析，请完成后重试。")
    try:
        bootstrap = "import sys;sys.path.insert(0,sys.argv[1]);from archcanvas_preview.assembly_bridge import _worker;_worker()"
        command = [sys.executable, "-I", "-S", "-B", "-c", bootstrap, str(Path(__file__).resolve().parents[1])]
        with tempfile.TemporaryFile() as output:
            try:
                result = subprocess.run(command, input=json.dumps(payload, ensure_ascii=False).encode("utf-8"), stdout=output,
                                        stderr=subprocess.DEVNULL, timeout=15, check=False)
            except subprocess.TimeoutExpired as error:
                raise AdapterError("局部结构复核超过 15 秒预算；当前稿件保留。") from error
            if result.returncode or output.tell() > MAX_RESULT_BYTES:
                raise AdapterError("局部结构复核失败或超出资源预算；当前稿件保留。")
            output.seek(0)
            try:
                response = json.load(output)
            except (ValueError, UnicodeError) as error:
                raise AdapterError("局部结构复核未返回有效结果。") from error
        if response.get("error"):
            raise AdapterError(response["error"])
        return response
    finally:
        _COMPILATION.release()


def _worker():
    try:
        import resource
        resource.setrlimit(resource.RLIMIT_CPU, (8, 8))
        resource.setrlimit(resource.RLIMIT_AS, (512 * 1024 * 1024,) * 2)
        resource.setrlimit(resource.RLIMIT_FSIZE, (MAX_RESULT_BYTES,) * 2)
        resource.setrlimit(resource.RLIMIT_NOFILE, (48, 48))
        from archcanvas_summary_semantic.authoring import certify_assembly
        payload = _request(json.load(sys.stdin))
        # Never reuse imported or stale certificates. Only the original
        # recognizer may produce contracts for this submitted declaration.
        payload["semantic_contracts"] = []
        payload.pop("semantic_contract_basis", None)
        payload["authoring"].pop("local_contracts_recomputed", None)
        ir = certify_assembly(payload)
        text = json.dumps(ir, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
        response = {"schema": SCHEMA, "irText": text, "resultSha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                    "analysis": {"scope": SCOPE, "contracts": len(ir.get("semantic_contracts", [])),
                                 "modelExecuted": False, "sourceTransactionBinding": False, "staticStructureOnly": True}}
    except Exception as error:
        response = {"error": str(error)[:2000]}
    sys.stdout.write(json.dumps(response, ensure_ascii=False, allow_nan=False))
