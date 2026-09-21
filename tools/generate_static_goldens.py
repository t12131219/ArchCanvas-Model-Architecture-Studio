"""Generate or verify deterministic Stage 2 static-recovery golden documents."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from archcanvas_pytorch.static import PyTorchStaticAdapter

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = (
    ("transformer_static_v1", "fixture:transformer_static_v1", "model.py:EncoderModel"),
    ("resnet_static_v1", "fixture:resnet_static_v1", "model.py:ResidualBlock"),
)


def _document_bytes(document: object) -> bytes:
    payload = document.model_dump(mode="json")  # type: ignore[attr-defined]
    return (json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _expected_documents() -> dict[Path, bytes]:
    adapter = PyTorchStaticAdapter()
    documents: dict[Path, bytes] = {}
    for fixture_name, project_id, entrypoint in FIXTURES:
        root = ROOT / "fixtures" / fixture_name
        source, architecture = adapter.analyze(
            (root / "source" / "model.py").read_bytes(),
            project_id=project_id,
            relative_file="model.py",
            entrypoint=entrypoint,
        )
        documents[root / "expected" / "source-identity.json"] = _document_bytes(source)
        documents[root / "expected" / "architecture.json"] = _document_bytes(architecture)
    return documents


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true", help="write reviewed golden candidates")
    arguments = parser.parse_args()
    mismatches: list[Path] = []
    for path, expected in _expected_documents().items():
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
            print(f"static golden mismatch: {path.relative_to(ROOT)}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
