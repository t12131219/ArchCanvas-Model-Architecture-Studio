from __future__ import annotations

import hashlib
import os
import shutil
from pathlib import Path

import pytest

from archcanvas_core.source_v2 import DiscoveryBudget
from archcanvas_engine.source_blob_store import SourceBlobStore
from archcanvas_python import capture_source_corpus, discover_project_manifest


def _project(root: Path) -> Path:
    project = root / "project"
    (project / "src" / "sample").mkdir(parents=True)
    (project / "src" / "sample" / "__init__.py").write_text("from .model import Model\n")
    (project / "src" / "sample" / "model.py").write_text(
        "class Model:\n    pass\n",
        encoding="utf-8",
    )
    (project / "pyproject.toml").write_text(
        "[tool.setuptools.packages.find]\nwhere = [\"src\"]\n",
        encoding="utf-8",
    )
    return project


def test_corpus_digest_does_not_depend_on_absolute_project_path(tmp_path: Path) -> None:
    first = _project(tmp_path / "first")
    second = tmp_path / "second" / "project"
    shutil.copytree(first, second)
    first_manifest = discover_project_manifest(first, "project:fixture")
    second_manifest = discover_project_manifest(second, "project:fixture")
    store = SourceBlobStore(tmp_path / "cas")

    first_corpus = capture_source_corpus(first, first_manifest, store)
    second_corpus = capture_source_corpus(second, second_manifest, store)

    assert first_corpus.source_corpus_digest == second_corpus.source_corpus_digest
    assert [item.logical_path for item in first_corpus.files] == [
        "pyproject.toml",
        "sample/__init__.py",
        "sample/model.py",
    ]


def test_new_import_candidate_changes_corpus_digest(tmp_path: Path) -> None:
    project = _project(tmp_path)
    manifest = discover_project_manifest(project, "project:fixture")
    store = SourceBlobStore(tmp_path / "cas")
    before = capture_source_corpus(project, manifest, store)

    (project / "src" / "sample" / "shadow.py").write_text("VALUE = 1\n", encoding="utf-8")
    after = capture_source_corpus(project, manifest, store)

    assert before.source_corpus_digest != after.source_corpus_digest


def test_blob_excerpt_survives_working_tree_change(tmp_path: Path) -> None:
    project = _project(tmp_path)
    manifest = discover_project_manifest(project, "project:fixture")
    store = SourceBlobStore(tmp_path / "cas")
    corpus = capture_source_corpus(project, manifest, store)
    source = next(item for item in corpus.files if item.logical_path == "sample/model.py")

    (project / "src" / "sample" / "model.py").write_text("CHANGED = True\n", encoding="utf-8")
    excerpt = store.source_excerpt(source, 1, 2, context=0)

    assert [line["text"] for line in excerpt["lines"]] == ["class Model:", "    pass"]
    assert excerpt["sha256"] == hashlib.sha256(b"class Model:\n    pass\n").hexdigest()


def test_symlink_is_recorded_but_never_captured(tmp_path: Path) -> None:
    project = _project(tmp_path)
    outside = tmp_path / "outside.py"
    outside.write_text("SECRET = True\n", encoding="utf-8")
    link = project / "src" / "sample" / "linked.py"
    try:
        os.symlink(outside, link)
    except OSError:
        pytest.skip("symbolic links are unavailable")
    manifest = discover_project_manifest(project, "project:fixture")

    corpus = capture_source_corpus(project, manifest, SourceBlobStore(tmp_path / "cas"))

    assert "sample/linked.py" not in {item.logical_path for item in corpus.files}
    assert any(
        item.logical_path == "sample/linked.py" and item.reason == "symlink"
        for item in corpus.excluded
    )


def test_budget_exclusions_are_part_of_corpus_identity(tmp_path: Path) -> None:
    project = _project(tmp_path)
    manifest = discover_project_manifest(
        project,
        "project:fixture",
        budget=DiscoveryBudget(max_files=1, max_total_bytes=10_000, max_file_bytes=10_000),
    )
    corpus = capture_source_corpus(project, manifest, SourceBlobStore(tmp_path / "cas"))

    assert len(corpus.files) == 1
    assert any(item.reason == "budget-exhausted" for item in corpus.excluded)


def test_materialized_snapshot_is_read_only(tmp_path: Path) -> None:
    project = _project(tmp_path)
    manifest = discover_project_manifest(project, "project:fixture")
    store = SourceBlobStore(tmp_path / "cas")
    corpus = capture_source_corpus(project, manifest, store)

    snapshot = store.materialize(corpus, tmp_path / "snapshot")

    target = snapshot / "sample" / "model.py"
    assert target.read_text(encoding="utf-8") == "class Model:\n    pass\n"
    assert target.stat().st_mode & 0o222 == 0
