"""Recursive preview source adapter, independent of the prototype checkout.

The user requested the Summary_Merge preview implementation be migrated into
Studio. This package preserves its wire format and conservative AST behavior;
it never replaces the source authoring or semantic transaction implementation.
Migration validation lives in tests/test_preview_backend.py.
"""

from pathlib import Path
import tempfile

from .analyze import AdapterError, MAX_BYTES, MAX_DEPTH, MAX_EDGES, MAX_FILES, MAX_NODES, analyze, files_checked

__all__ = ["AdapterError", "analyze", "analyze_for_authoring", "capabilities"]


def analyze_for_authoring(files: dict[str, str], entry: str | None) -> dict:
    """Bind preview source to the existing authoring Architecture contract.

    Supplied files are validated before creating a disposable source directory.
    The formal analyzer reads it as text; no import or model execution occurs.
    The resulting Architecture can enter the existing managed-copy workflow.
    """
    from archcanvas_python import analyze_project

    checked = files_checked(files)
    resolved_entry = analyze(checked, entry)["entry"]
    with tempfile.TemporaryDirectory(prefix="archcanvas-preview-source-") as temporary:
        root = Path(temporary).resolve()
        for logical, text in checked.items():
            path = root / logical
            if not path.resolve().is_relative_to(root):
                raise AdapterError('源码路径越过临时解析目录。')
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        return analyze_project(root, resolved_entry)


def capabilities() -> dict:
    return {
        "schema": "summary-source-adapter/1",
        "irSchema": "summary-source-ir/1",
        "analyze": "/api/preview/analyze",
        "authoringArchitecture": "/api/preview/edit-source",
        "exports": "/api/preview/exports",
        "legacyAnalyze": "/api/source-adapter/analyze",
        "managedProject": "/api/projects/{projectId}/preview",
        "modelExecuted": False,
        "analysis": "static-source-dependencies",
        "limits": {"files": MAX_FILES, "sourceBytes": MAX_BYTES, "nodes": MAX_NODES, "edges": MAX_EDGES, "depth": MAX_DEPTH},
        "package": str(Path(__file__).resolve().parent),
        "sourceMigration": {
            "reason": "User-requested replacement of the Studio preview with Summary_Merge technology",
            "source": "prototype/Summary_Merge/source_adapter",
            "analyzerSha256": "4203423099ebe24d81a0d512e932d26ae3b172f8d7dce8f1d155c17fa4978650",
            "registrySha256": "5e5a34d04886f1a0450428a0715abc3dc4a14caa3ff1d9669e7948f245f1dbb3",
        },
    }
