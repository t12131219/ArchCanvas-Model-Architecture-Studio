"""Explicit frozen-source editing, separate from graphical tensor lowering.

A selected source card locates a Python file, never a filesystem write target.
The complete independently analyzed file is the edit unit: this supports
rebuilding branches and unknown modules without interpreting inspection arrows
as executable tensor relations. All edits produce a new isolated corpus.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
import tempfile

from archcanvas_python import analyze_project, AnalysisError
from .draft import DraftError, _diagnostic, _digest, generate_model
from .source_preservation import _raw


def _fail(technical, message, region_id=None):
    raise DraftError(technical, diagnostics=[_diagnostic(
        "source-region-edit", message, technical, nodeId=region_id)])


def _prepared(draft, region_id):
    if not isinstance(draft, dict) or not isinstance(draft.get("sourceProvenance"), dict):
        _fail("Explicit source editing requires a source-derived draft.", "当前草稿没有原始源码；请先打开源码模型。")
    if type(region_id) is not str or not region_id or len(region_id) > 4096:
        _fail("The selected source region identity is invalid.", "请选择具有源码位置的模块。")
    # This independently reconciles the original frozen bytes and incorporates
    # every supported pending graph/parameter edit. Unsupported pending edits
    # must not silently disappear behind a pristine source file editor.
    try:
        generated = generate_model(draft)
    except DraftError as exc:
        _fail(f"Pending draft edits cannot be preserved before source editing: {exc}",
              "当前草稿有尚不能生成的改动；请先恢复相应源码区域或撤销这些改动，再编辑源码。", region_id)
    architecture = generated["architecture"]
    original = draft["sourceProvenance"]["architecture"]
    refs = draft["sourceProvenance"].get("nodeRefs", {})
    canonical = refs.get(region_id, {}).get("nodeId", region_id)
    old_fact = next((node for node in original["nodes"] if node["id"] == canonical), None)
    bindings = {**generated.get("nodeBindings", {}), **generated.get("containerBindings", {})}
    bound = bindings.get(region_id)
    if bound is None:
        aliases = {bindings[key] for key, value in refs.items() if value.get("nodeId") == canonical and key in bindings}
        if len(aliases) == 1:
            bound = next(iter(aliases))
    fact = next((node for node in architecture["nodes"] if node["id"] == (bound or canonical)), None)
    if old_fact is None or fact is None:
        _fail("The selected source region has no retained independently generated identity.",
              "所选模块的源码位置已改变或已删除；请恢复区域或打开新的预览后重试。", region_id)
    source = fact.get("source", {})
    path = source.get("path")
    selected = next((item for item in architecture["sources"] if item["path"] == path), None)
    if selected is None:
        _fail("The selected source region has no frozen Python file.", "该模块没有可编辑的 Python 源码位置。", region_id)
    binding = {"schema": "archcanvas-source-file-edit/1", "draftDigest": generated["draftDigest"],
               "regionId": region_id, "canonicalId": fact["id"], "path": path,
               "sourceDigest": architecture["sourceDigest"], "irDigest": architecture["irDigest"],
               "fileDigest": selected["digest"], "entry": architecture["entry"]}
    return generated, fact, selected, _digest(binding)


def prepare_source_region(draft, region_id):
    generated, fact, selected, baseline = _prepared(draft, region_id)
    source = fact.get("source", {})
    return {"regionId": region_id, "canonicalId": fact["id"], "path": selected["path"],
            "source": selected["content"], "baselineDigest": baseline,
            "startLine": source.get("line", 1), "endLine": source.get("endLine", source.get("line", 1)),
            "entry": generated["entry"], "baseSourceDigest": generated["architecture"]["sourceDigest"],
            "baseIrDigest": generated["architecture"]["irDigest"],
            "verification": {"scope": "independently-reanalyzed-source-file", "modelExecution": "not_run",
                             "pendingEdits": "included", "editUnit": "complete-python-file"}}


def apply_source_region(draft, region_id, baseline_digest, replacement):
    generated, fact, selected, baseline = _prepared(draft, region_id)
    if type(baseline_digest) is not str or baseline_digest != baseline:
        _fail("The source file edit baseline changed; prepare a fresh source editing session.",
              "源码编辑的基线已变化；当前编辑未写入，请重新打开源码并核对。", region_id)
    if type(replacement) is not str or not replacement.strip():
        _fail("Replacement source must be nonempty Python text.", "请提供完整且非空的 Python 源码。", region_id)
    previous_raw = _raw(selected)
    raw = replacement.encode("utf-8")
    # Preserve a BOM present in the original file. Text editors generally strip
    # it; retaining it here keeps unchanged file bytes stable on an empty edit.
    if previous_raw.startswith(b"\xef\xbb\xbf") and not raw.startswith(b"\xef\xbb\xbf"):
        raw = b"\xef\xbb\xbf" + raw
    architecture = generated["architecture"]
    written = {item["path"]: _raw(item) for item in architecture["sources"]}
    written[selected["path"]] = raw
    if len(written) > 80 or sum(map(len, written.values())) > 2_000_000:
        _fail("The explicit source edit exceeds the standard frozen corpus budget.", "源码总量超过 80 文件或 2 MB 的分析预算。", region_id)
    try:
        compile(raw, selected["path"], "exec", dont_inherit=True)
    except (SyntaxError, UnicodeError, ValueError) as exc:
        _fail(f"Replacement Python source is invalid: {exc}", f"Python 语法检查失败：{exc}", region_id)
    try:
        with tempfile.TemporaryDirectory(prefix="archcanvas-source-file-edit-") as temporary:
            root = Path(temporary)
            for path, data in written.items():
                logical = Path(path)
                if logical.is_absolute() or ".." in logical.parts or "\\" in path or logical.suffix != ".py":
                    _fail("Frozen source paths must remain relative Python files.", "源码文件位置不合法。", region_id)
                target = root / logical
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)
            actual = analyze_project(root, generated["entry"])
    except AnalysisError as exc:
        _fail(f"Independent analysis rejected the replacement source: {exc}", f"新源码无法重新分析：{exc}", region_id)
    actual_sources = {item["path"]: item for item in actual["sources"]}
    if set(actual_sources) != set(written) or any(actual_sources[path]["digest"] != hashlib.sha256(data).hexdigest()
                                               for path, data in written.items()):
        _fail("Independent source analysis did not retain the exact edited corpus.", "新源码的独立分析与编辑内容不一致。", region_id)
    return {"architecture": actual, "source": next(item["content"] for item in actual["sources"] if item["path"] == selected["path"]),
            "entry": actual["entry"],
            "sourceEdit": {"path": selected["path"], "beforeDigest": selected["digest"],
                           "afterDigest": actual_sources[selected["path"]]["digest"], "baselineDigest": baseline,
                           "selectedRegionId": region_id, "selectedCanonicalId": fact["id"]},
            "verification": {"status": "passed", "scope": "explicit-source-file-reanalysis", "modelExecution": "not_run",
                             "inputDraftDigest": generated["draftDigest"], "pendingEdits": "included",
                             "originalProjectWritten": False, "tensorLowering": False,
                             "unchangedFiles": sorted(path for path in written if path != selected["path"]),
                             "limitations": ["Source syntax was compiled and independently analyzed without importing or executing the model.",
                                             "Inspection relations do not establish runtime tensor flow, shapes, or numerical correctness.",
                                             "The edited corpus opens as a fresh source document; the original draft and history remain separate."]}}
