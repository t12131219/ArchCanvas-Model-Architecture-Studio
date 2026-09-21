"""Generate or verify deterministic Stage 4 publication-view golden documents."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from archcanvas_publication import PublicationCompiler, StageLayout
from archcanvas_pytorch.static import PyTorchStaticAdapter
from archcanvas_renderer import render_svg

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = (
    (
        "transformer_static_v1",
        "publication_transformer_v1",
        "fixture:transformer_static_v1",
        "model.py:EncoderModel",
    ),
    (
        "resnet_static_v1",
        "publication_cnn_v1",
        "fixture:resnet_static_v1",
        "model.py:ResidualBlock",
    ),
)


def _document_bytes(document: object) -> bytes:
    payload = document.model_dump(mode="json")  # type: ignore[attr-defined]
    return (json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def expected_documents() -> dict[Path, bytes]:
    adapter = PyTorchStaticAdapter()
    compiler = PublicationCompiler()
    layout = StageLayout()
    documents: dict[Path, bytes] = {}
    for source_fixture, publication_fixture, project_id, entrypoint in FIXTURES:
        source_root = ROOT / "fixtures" / source_fixture
        _, exact = adapter.analyze(
            (source_root / "source" / "model.py").read_bytes(),
            project_id=project_id,
            relative_file="model.py",
            entrypoint=entrypoint,
        )
        publication = compiler.compile(exact)
        scene = layout.layout(publication)
        expected_root = ROOT / "fixtures" / publication_fixture / "expected"
        documents[expected_root / "publication.json"] = _document_bytes(publication)
        documents[expected_root / "scene.json"] = _document_bytes(scene)
        documents[expected_root / "scene.svg"] = render_svg(publication, scene).encode("utf-8")
        repeat_groups = [node for node in publication.nodes if node.kind.value == "repeat_group"]
        if repeat_groups:
            expanded_scene = layout.layout(
                publication,
                expanded_node_ids={repeat_groups[0].node_id},
            )
            documents[expected_root / "expanded-scene.json"] = _document_bytes(expanded_scene)
            documents[expected_root / "expanded-scene.svg"] = render_svg(
                publication,
                expanded_scene,
            ).encode("utf-8")
    return documents


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true", help="write reviewed golden candidates")
    arguments = parser.parse_args()
    mismatches: list[Path] = []
    for path, expected in expected_documents().items():
        actual = path.read_bytes() if path.exists() else None
        if actual == expected:
            continue
        if arguments.write:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(expected)
        else:
            mismatches.append(path)
    if mismatches:
        for path in mismatches:
            print(f"publication golden mismatch: {path.relative_to(ROOT)}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
