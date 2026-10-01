from __future__ import annotations

import fnmatch
import hashlib
import io
import tokenize
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from archcanvas_core.source_v2 import (
    ExcludedSource,
    ProjectManifest,
    SourceBlobRef,
    SourceCorpus,
    SourceRootSpec,
    compute_source_corpus_digest,
)
from archcanvas_engine.source_blob_store import SourceBlobStore


class CorpusCaptureError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class _Candidate:
    logical_path: str
    physical_path: Path
    root: SourceRootSpec
    file_kind: str


def _matches(path: str, patterns: list[str]) -> bool:
    candidate = PurePosixPath(path)
    return any(candidate.match(pattern) or fnmatch.fnmatchcase(path, pattern) for pattern in patterns)


def _logical_path(root: SourceRootSpec, path: Path, source_root: Path) -> str:
    relative = path.relative_to(source_root).as_posix()
    return f"{root.logical_prefix}/{relative}" if root.logical_prefix else relative


def _kind_for(path: Path, *, config: bool = False) -> str:
    if config:
        return "project-metadata" if path.name == "pyproject.toml" else "config"
    return "stub" if path.suffix == ".pyi" else "python"


def _stable_read(path: Path, attempts: int = 3) -> bytes:
    for _ in range(attempts):
        before = path.stat(follow_symlinks=False)
        payload = path.read_bytes()
        after = path.stat(follow_symlinks=False)
        before_key = (before.st_ino, before.st_size, before.st_mtime_ns)
        after_key = (after.st_ino, after.st_size, after.st_mtime_ns)
        if before_key == after_key and len(payload) == after.st_size:
            return payload
    raise CorpusCaptureError(
        "SOURCE_CAPTURE_UNSTABLE", f"source changed repeatedly during capture: {path.name}"
    )


def _source_encoding(payload: bytes, file_kind: str) -> str:
    try:
        if file_kind in {"python", "stub"}:
            encoding, _ = tokenize.detect_encoding(io.BytesIO(payload).readline)
        else:
            encoding = "utf-8"
        payload.decode(encoding)
    except (LookupError, SyntaxError, UnicodeDecodeError) as error:
        raise CorpusCaptureError("SOURCE_DECODE_ERROR", "source encoding is invalid") from error
    return encoding.lower()


def _discover_candidates(
    project_root: Path,
    manifest: ProjectManifest,
) -> tuple[list[_Candidate], list[ExcludedSource]]:
    candidates: dict[str, _Candidate] = {}
    excluded: list[ExcludedSource] = []
    for root_spec in sorted(
        manifest.source_roots,
        key=lambda item: (item.precedence, item.logical_prefix, item.relative_path),
    ):
        unresolved_root = project_root / root_spec.relative_path
        if unresolved_root.is_symlink():
            raise CorpusCaptureError(
                "SOURCE_ROOT_SYMLINK",
                f"source root cannot be a symbolic link: {root_spec.relative_path}",
            )
        source_root = unresolved_root.resolve()
        if not source_root.is_relative_to(project_root) or not source_root.is_dir():
            raise CorpusCaptureError(
                "SOURCE_ROOT_INVALID", f"source root is unavailable or escapes project: {root_spec.relative_path}"
            )
        for path in sorted(source_root.rglob("*")):
            logical_path = _logical_path(root_spec, path, source_root)
            if path.is_symlink():
                excluded.append(ExcludedSource(logical_path=logical_path, reason="symlink"))
                continue
            if not path.is_file():
                continue
            if _matches(logical_path, manifest.exclude_globs):
                excluded.append(
                    ExcludedSource(logical_path=logical_path, reason="excluded-pattern")
                )
                continue
            if not _matches(logical_path, manifest.include_globs):
                continue
            if path.suffix not in {".py", ".pyi"}:
                excluded.append(
                    ExcludedSource(logical_path=logical_path, reason="unsupported-kind")
                )
                continue
            candidate = _Candidate(
                logical_path=logical_path,
                physical_path=path,
                root=root_spec,
                file_kind=_kind_for(path),
            )
            if logical_path in candidates:
                excluded.append(
                    ExcludedSource(
                        logical_path=logical_path,
                        reason="shadowed",
                        detail=str(path.relative_to(project_root)),
                    )
                )
                continue
            candidates[logical_path] = candidate

    for config_path in manifest.config_paths:
        path = project_root.joinpath(*config_path.split("/"))
        if path.is_symlink():
            excluded.append(ExcludedSource(logical_path=config_path, reason="symlink"))
            continue
        resolved = path.resolve()
        if not resolved.is_relative_to(project_root):
            excluded.append(ExcludedSource(logical_path=config_path, reason="path-escape"))
            continue
        if resolved.is_file() and config_path not in candidates:
            candidates[config_path] = _Candidate(
                logical_path=config_path,
                physical_path=resolved,
                root=manifest.source_roots[0],
                file_kind=_kind_for(resolved, config=True),
            )
    return sorted(candidates.values(), key=lambda item: item.logical_path), excluded


def capture_source_corpus(
    project_root: Path,
    manifest: ProjectManifest,
    blob_store: SourceBlobStore,
    *,
    vcs_revision: str | None = None,
) -> SourceCorpus:
    root = project_root.resolve()
    if not root.is_dir():
        raise CorpusCaptureError("PROJECT_ROOT_INVALID", "project root is not a directory")
    candidates, excluded = _discover_candidates(root, manifest)
    files: list[SourceBlobRef] = []
    total_bytes = 0
    budget = manifest.discovery_budget
    for candidate in candidates:
        if len(files) >= budget.max_files:
            excluded.append(
                ExcludedSource(logical_path=candidate.logical_path, reason="budget-exhausted")
            )
            continue
        try:
            stat = candidate.physical_path.stat(follow_symlinks=False)
        except OSError as error:
            raise CorpusCaptureError(
                "SOURCE_CAPTURE_UNAVAILABLE",
                f"source became unavailable during capture: {candidate.logical_path}",
            ) from error
        if stat.st_size > budget.max_file_bytes:
            excluded.append(
                ExcludedSource(logical_path=candidate.logical_path, reason="file-too-large")
            )
            continue
        if total_bytes + stat.st_size > budget.max_total_bytes:
            excluded.append(
                ExcludedSource(logical_path=candidate.logical_path, reason="budget-exhausted")
            )
            continue
        try:
            payload = _stable_read(candidate.physical_path)
            encoding = _source_encoding(payload, candidate.file_kind)
        except OSError as error:
            raise CorpusCaptureError(
                "SOURCE_CAPTURE_UNAVAILABLE",
                f"source became unavailable during capture: {candidate.logical_path}",
            ) from error
        except CorpusCaptureError as error:
            if error.code != "SOURCE_DECODE_ERROR":
                raise
            excluded.append(
                ExcludedSource(logical_path=candidate.logical_path, reason="decode-error")
            )
            continue
        if len(payload) > budget.max_file_bytes:
            excluded.append(
                ExcludedSource(logical_path=candidate.logical_path, reason="file-too-large")
            )
            continue
        if total_bytes + len(payload) > budget.max_total_bytes:
            excluded.append(
                ExcludedSource(logical_path=candidate.logical_path, reason="budget-exhausted")
            )
            continue
        digest = hashlib.sha256(payload).hexdigest()
        blob_ref = blob_store.put(payload)
        files.append(
            SourceBlobRef(
                logical_path=candidate.logical_path,
                sha256=digest,
                blob_ref=blob_ref,
                size=len(payload),
                encoding=encoding,
                file_kind=candidate.file_kind,
            )
        )
        total_bytes += len(payload)
    if not files:
        raise CorpusCaptureError("SOURCE_CORPUS_EMPTY", "no source files were captured")
    excluded = sorted(excluded, key=lambda item: (item.logical_path, item.reason, item.detail or ""))
    digest = compute_source_corpus_digest(
        files=files,
        source_roots=manifest.source_roots,
        excluded=excluded,
    )
    return SourceCorpus(
        corpus_id=f"corpus:{digest[:24]}",
        source_corpus_digest=digest,
        vcs_revision=vcs_revision,
        files=files,
        source_roots=manifest.source_roots,
        excluded=excluded,
    )
