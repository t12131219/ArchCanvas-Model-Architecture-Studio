from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]


def _sidecar_request(cache_root: Path, request: dict[str, Any]) -> dict[str, Any]:
    environment = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
    completed = subprocess.run(
        [sys.executable, "-m", "archcanvas_engine.stdio", "--cache-root", str(cache_root)],
        cwd=ROOT,
        env=environment,
        input=json.dumps(request) + "\n",
        capture_output=True,
        check=True,
        text=True,
    )
    assert completed.stderr == ""
    return json.loads(completed.stdout)


def _request(request_id: str, command: dict[str, Any]) -> dict[str, Any]:
    return {"schema_version": "1.0", "request_id": request_id, "command": command}


def test_jsonl_sidecar_restarts_with_persisted_analysis_and_canvas_document(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    source_path = project_root / "model.py"
    shutil.copyfile(ROOT / "fixtures" / "transformer_static_v1" / "source" / "model.py", source_path)
    source_before = source_path.read_bytes()
    cache_root = tmp_path / "engine-cache"

    opened = _sidecar_request(
        cache_root,
        _request(
            "engine-request:sidecar-open",
            {
                "operation": "open_project",
                "project_id": "project:sidecar-transformer",
                "approved_root": str(project_root),
                "entrypoint": "model.py:EncoderModel",
                "environment": {"python_executable": sys.executable, "environment_name": "TFB_py311"},
            },
        ),
    )
    assert opened["status"] == "succeeded"

    analyzed = _sidecar_request(
        cache_root,
        _request(
            "engine-request:sidecar-analyze",
            {"operation": "analyze_project", "project_id": "project:sidecar-transformer"},
        ),
    )
    analysis = analyzed["result"]
    assert analysis["kind"] == "analysis_completed"
    publication_nodes = analysis["publication"]["nodes"]
    document = {
        "schema_version": "1.0",
        "canvas_document_id": "canvas-document:sidecar-layout",
        "project_id": "project:sidecar-transformer",
        "publication_id": analysis["publication"]["publication_id"],
        "base_source_revision": analysis["manifest"]["source_revision"],
        "layout_mode": "manual",
        "viewport": {"x": 10.0, "y": -20.0, "zoom": 1.25},
        "nodes": [
            {
                "publication_node_id": node["node_id"],
                "x": float(index * 200),
                "y": 120.0,
                "width": 180.0,
                "height": 72.0,
                "style": {},
                "collapsed": node["collapsed"],
                "locked": False,
            }
            for index, node in enumerate(publication_nodes)
        ],
        "annotations": [],
    }
    saved = _sidecar_request(
        cache_root,
        _request(
            "engine-request:sidecar-save-canvas",
            {"operation": "save_canvas_document", "canvas_document": document},
        ),
    )
    assert saved["status"] == "succeeded", saved
    assert saved["result"]["kind"] == "canvas_document_saved"

    loaded = _sidecar_request(
        cache_root,
        _request(
            "engine-request:sidecar-load-analysis",
            {"operation": "load_analysis", "project_id": "project:sidecar-transformer"},
        ),
    )
    replayed = _sidecar_request(
        cache_root,
        _request(
            "engine-request:sidecar-replay-canvas",
            {"operation": "replay_canvas_documents", "project_id": "project:sidecar-transformer"},
        ),
    )

    assert loaded["result"]["kind"] == "analysis_loaded"
    assert loaded["result"]["architecture"]["ir_id"] == analysis["architecture"]["ir_id"]
    replayed_document = replayed["result"]["canvas_documents"][0]
    assert replayed_document["canvas_document_id"] == document["canvas_document_id"]
    assert replayed_document["viewport"] == document["viewport"]
    assert replayed_document["nodes"][2]["x"] == document["nodes"][2]["x"]
    assert replayed_document["nodes"][2]["collapsed"] == document["nodes"][2]["collapsed"]
    assert source_path.read_bytes() == source_before


def test_jsonl_sidecar_rejects_invalid_request_without_traceback(tmp_path: Path) -> None:
    response = _sidecar_request(tmp_path / "engine-cache", {"request_id": "engine-request:invalid"})

    assert response["status"] == "rejected"
    assert response["error"]["code"] == "INVALID_ENGINE_REQUEST"
