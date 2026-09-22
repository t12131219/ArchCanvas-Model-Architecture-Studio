"""Atomic, cache-root-only persistence for Engine project sessions."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from archcanvas_core.models.architecture import ArchitectureIR
from archcanvas_core.models.canvas import CanvasDocument
from archcanvas_core.models.engine import EngineEvent, ProjectManifest, VisualPatch
from archcanvas_core.models.publication import PublicationIR, VisualScene
from archcanvas_core.models.source_identity import SourceIdentityDocument


def _json_bytes(document: object) -> bytes:
    payload = document.model_dump(mode="json")  # type: ignore[attr-defined]
    return (json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


class EngineRepository:
    """Store engine state outside an analyzed project and recover it after restart."""

    def __init__(self, cache_root: Path) -> None:
        self._root = cache_root.resolve()
        self._root.mkdir(parents=True, exist_ok=True)

    def _project_dir(self, project_id: str) -> Path:
        token = project_id.removeprefix("project:")
        if not token or any(character not in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789._-" for character in token):
            raise ValueError("project_id cannot form a cache path")
        return self._root / "projects" / token

    @staticmethod
    def _write(path: Path, value: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as temporary:
            temporary.write(value)
            temporary_path = Path(temporary.name)
        temporary_path.replace(path)

    def save_manifest(self, manifest: ProjectManifest) -> None:
        self._write(self._project_dir(manifest.project_id) / "manifest.json", _json_bytes(manifest))

    def load_manifest(self, project_id: str) -> ProjectManifest:
        path = self._project_dir(project_id) / "manifest.json"
        if not path.is_file():
            raise FileNotFoundError(project_id)
        return ProjectManifest.model_validate_json(path.read_bytes())

    def save_analysis(
        self,
        manifest: ProjectManifest,
        source: SourceIdentityDocument,
        architecture: ArchitectureIR,
        publication: PublicationIR,
        scene: VisualScene,
        svg: str,
    ) -> str:
        root = self._project_dir(manifest.project_id) / "analysis"
        self._write(root / "source-identity.json", _json_bytes(source))
        self._write(root / "architecture.json", _json_bytes(architecture))
        self._write(root / "publication.json", _json_bytes(publication))
        self._write(root / "scene.json", _json_bytes(scene))
        self._write(root / "scene.svg", svg.encode("utf-8"))
        return "analysis/scene.svg"

    def load_analysis(
        self, project_id: str
    ) -> tuple[SourceIdentityDocument, ArchitectureIR, PublicationIR, VisualScene]:
        root = self._project_dir(project_id) / "analysis"
        return (
            SourceIdentityDocument.model_validate_json((root / "source-identity.json").read_bytes()),
            ArchitectureIR.model_validate_json((root / "architecture.json").read_bytes()),
            PublicationIR.model_validate_json((root / "publication.json").read_bytes()),
            VisualScene.model_validate_json((root / "scene.json").read_bytes()),
        )

    def artifact_bytes(self, project_id: str, relative_path: str) -> bytes:
        path = (self._project_dir(project_id) / relative_path).resolve()
        if not path.is_relative_to(self._project_dir(project_id)) or not path.is_file():
            raise FileNotFoundError(relative_path)
        return path.read_bytes()

    def save_visual_patch(self, patch: VisualPatch) -> None:
        self._write(
            self._project_dir(patch.project_id) / "visual-patches" / f"{patch.visual_patch_id.removeprefix('visual-patch:')}.json",
            _json_bytes(patch),
        )

    def load_visual_patches(self, project_id: str) -> list[VisualPatch]:
        root = self._project_dir(project_id) / "visual-patches"
        if not root.is_dir():
            return []
        return [VisualPatch.model_validate_json(path.read_bytes()) for path in sorted(root.glob("*.json"))]

    def save_canvas_document(self, document: CanvasDocument) -> None:
        self._write(
            self._project_dir(document.project_id)
            / "canvas-documents"
            / f"{document.canvas_document_id.removeprefix('canvas-document:')}.json",
            _json_bytes(document),
        )

    def load_canvas_documents(self, project_id: str) -> list[CanvasDocument]:
        root = self._project_dir(project_id) / "canvas-documents"
        if not root.is_dir():
            return []
        return [CanvasDocument.model_validate_json(path.read_bytes()) for path in sorted(root.glob("*.json"))]

    def append_event(self, event: EngineEvent) -> None:
        path = self._project_dir(event.project_id) / "history.json"
        events = [] if not path.is_file() else json.loads(path.read_text(encoding="utf-8"))
        events.append(event.model_dump(mode="json"))
        self._write(path, (json.dumps(events, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8"))

    def load_events(self, project_id: str) -> list[EngineEvent]:
        path = self._project_dir(project_id) / "history.json"
        if not path.is_file():
            return []
        return [EngineEvent.model_validate(item) for item in json.loads(path.read_text(encoding="utf-8"))]
