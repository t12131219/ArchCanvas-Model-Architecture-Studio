"""Deterministic polling watcher for approved source files."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from archcanvas_core.models.common import source_snapshot_revision
from archcanvas_core.models.engine import ProjectManifest
from archcanvas_python.source_revision import file_revision

from .service_errors import EngineRejected


@dataclass(frozen=True)
class SourceObservation:
    source_revision: str
    file_revisions: dict[str, str]


class ProjectSourceWatcher:
    """Poll a manifest's bounded file set without touching paths outside its approved root."""

    def observe(self, manifest: ProjectManifest) -> SourceObservation:
        root = Path(manifest.approved_root).resolve(strict=True)
        observed: dict[str, str] = {}
        for relative_file in manifest.file_revisions:
            path = (root / relative_file).resolve(strict=False)
            if not path.is_file() or not path.is_relative_to(root):
                raise EngineRejected("SOURCE_FILE_MISSING", relative_file)
            observed[relative_file] = file_revision(path.read_bytes())
        return SourceObservation(
            source_revision=source_snapshot_revision(observed),
            file_revisions=observed,
        )
