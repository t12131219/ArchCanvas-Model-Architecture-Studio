from __future__ import annotations

import hashlib
import os
import tempfile
from pathlib import Path

from archcanvas_core.source_v2 import SourceBlobRef, SourceCorpus


class SourceBlobStoreError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class SourceBlobStore:
    """Local content-addressed storage for immutable source bytes."""

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.blob_root = self.root / "sha256"
        self.blob_root.mkdir(parents=True, exist_ok=True)

    def _path_for_digest(self, digest: str) -> Path:
        if len(digest) != 64 or any(character not in "0123456789abcdef" for character in digest):
            raise SourceBlobStoreError("SOURCE_BLOB_REF_INVALID", "invalid sha256 blob reference")
        return self.blob_root / digest[:2] / digest

    def put(self, payload: bytes) -> str:
        digest = hashlib.sha256(payload).hexdigest()
        target = self._path_for_digest(digest)
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            self._verify_path(target, digest)
            return f"sha256:{digest}"

        temporary: Path | None = None
        try:
            with tempfile.NamedTemporaryFile("wb", dir=target.parent, delete=False) as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
                temporary = Path(handle.name)
            if hashlib.sha256(temporary.read_bytes()).hexdigest() != digest:
                raise SourceBlobStoreError(
                    "SOURCE_BLOB_WRITE_CORRUPT", "temporary source blob failed verification"
                )
            try:
                os.link(temporary, target)
            except FileExistsError:
                self._verify_path(target, digest)
            temporary.unlink(missing_ok=True)
            temporary = None
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
        return f"sha256:{digest}"

    def _verify_path(self, path: Path, digest: str) -> None:
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise SourceBlobStoreError(
                "SOURCE_BLOB_CORRUPT", f"source blob does not match sha256:{digest}"
            )

    def read(self, blob_ref: str) -> bytes:
        if not blob_ref.startswith("sha256:"):
            raise SourceBlobStoreError("SOURCE_BLOB_REF_INVALID", "unsupported blob reference")
        digest = blob_ref.removeprefix("sha256:")
        path = self._path_for_digest(digest)
        if not path.is_file():
            raise SourceBlobStoreError(
                "SOURCE_BLOB_MISSING", f"source blob is unavailable: {blob_ref}"
            )
        payload = path.read_bytes()
        if hashlib.sha256(payload).hexdigest() != digest:
            raise SourceBlobStoreError(
                "SOURCE_BLOB_CORRUPT", f"source blob does not match {blob_ref}"
            )
        return payload

    def source_excerpt(
        self,
        source: SourceBlobRef,
        start_line: int,
        end_line: int,
        *,
        context: int = 4,
    ) -> dict[str, object]:
        if start_line < 1 or end_line < start_line:
            raise ValueError("source excerpt line range is invalid")
        if not 0 <= context <= 12:
            raise ValueError("source excerpt context must be between 0 and 12")
        payload = self.read(source.blob_ref)
        if hashlib.sha256(payload).hexdigest() != source.sha256:
            raise SourceBlobStoreError(
                "SOURCE_BLOB_CORRUPT", "source manifest and blob content disagree"
            )
        lines = payload.decode(source.encoding).splitlines()
        excerpt_start = max(1, start_line - context)
        excerpt_end = min(len(lines), min(end_line, start_line + 79) + context)
        highlight_end = min(end_line, start_line + 79, len(lines))
        return {
            "path": source.logical_path,
            "sha256": source.sha256,
            "start_line": excerpt_start,
            "end_line": excerpt_end,
            "highlight_start_line": start_line,
            "highlight_end_line": highlight_end,
            "lines": [
                {"number": number, "text": lines[number - 1]}
                for number in range(excerpt_start, excerpt_end + 1)
            ],
        }

    def materialize(self, corpus: SourceCorpus, destination: Path) -> Path:
        destination = destination.resolve()
        if destination.exists() and any(destination.iterdir()):
            raise ValueError("snapshot destination must be empty")
        destination.mkdir(parents=True, exist_ok=True)
        for source in sorted(corpus.files, key=lambda item: item.logical_path):
            target = destination.joinpath(*source.logical_path.split("/"))
            if not target.resolve().is_relative_to(destination):
                raise ValueError("source path escapes the snapshot destination")
            target.parent.mkdir(parents=True, exist_ok=True)
            payload = self.read(source.blob_ref)
            with target.open("xb") as handle:
                handle.write(payload)
            target.chmod(0o444)
        for directory in sorted(
            (path for path in destination.rglob("*") if path.is_dir()),
            key=lambda path: len(path.parts),
            reverse=True,
        ):
            directory.chmod(0o555)
        destination.chmod(0o555)
        return destination
