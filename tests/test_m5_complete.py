from __future__ import annotations

import copy
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from scripts.check_m5_complete import _demo, _host_matrix, validate


class M5CompletionContractTests(unittest.TestCase):
    def test_completion_cannot_promote_open_human_or_public_gates(self) -> None:
        receipt = {
            "schema": "archcanvas-m5-completion/1",
            "state": "complete-local-beta",
            "scope": "local-beta-preview",
            "m4": "complete",
            "runtimeSource": "formal-project",
            "publicRelease": True,
            "humanParticipants": 3,
            "publicationReviewCertified": True,
            "knownLimitations": ["placeholder"],
            "bundle": {"path": "/outside/bundle.tar.gz", "sha256": "0" * 64},
            "evidence": {},
        }
        errors = validate(receipt, Path(tempfile.mkdtemp()))
        self.assertTrue(any("m4 must remain 'partial'" in item for item in errors))
        self.assertTrue(any("publicRelease must remain False" in item for item in errors))
        self.assertTrue(any("humanParticipants must remain 0" in item for item in errors))
        self.assertTrue(any("publicationReviewCertified must remain False" in item for item in errors))

    def test_bundle_traversal_is_rejected_even_with_a_formal_state(self) -> None:
        receipt = {
            "schema": "archcanvas-m5-completion/1",
            "state": "complete-local-beta",
            "scope": "local-beta-preview",
            "m4": "partial",
            "runtimeSource": "formal-project",
            "publicRelease": False,
            "humanParticipants": 0,
            "publicationReviewCertified": False,
            "knownLimitations": ["host clients not tested"],
            "bundle": {"path": "../bundle.tar.gz", "sha256": "0" * 64},
            "evidence": {},
        }
        errors = validate(receipt, Path(tempfile.mkdtemp()))
        self.assertTrue(any("bundle/build" in item and "traversal" in item for item in errors))

    def test_snapshot_demo_is_valid_only_when_its_limits_are_explicit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "frame").mkdir()
            png = b"\x89PNG\r\n\x1a\n" + b"frame"
            frame_rows = []
            start = datetime(2026, 10, 7, 1, 2, 3, tzinfo=timezone.utc)
            for index in range(5):
                path = root / "frame" / f"{index}.png"
                path.write_bytes(png + bytes([index]))
                frame_rows.append({
                    "path": str(path),
                    "sha256": __import__("hashlib").sha256(path.read_bytes()).hexdigest(),
                    "bytes": path.stat().st_size,
                    "capturedAt": (start + timedelta(seconds=index)).isoformat(),
                })
            gif = root / "demo.gif"
            gif.write_bytes(b"GIF89a snapshot")
            html = root / "demo.html"
            html.write_text("<html><!-- snapshot sequence --></html>", encoding="utf-8")
            svg = root / "figure.svg"
            svg.write_text('<svg xmlns="http://www.w3.org/2000/svg"></svg>', encoding="utf-8")
            pdf = root / "figure.pdf"
            pdf.write_bytes(b"%PDF-1.7 snapshot")

            def ref(path: Path) -> dict:
                import hashlib
                data = path.read_bytes()
                return {"path": str(path), "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}

            demo = {
                "schema": "archcanvas-m5-demo/1",
                "status": "passed-bounded",
                "kind": "snapshot-sequence",
                "durationSeconds": 90,
                "operationElapsedSeconds": 12.5,
                "recordingCertified": False,
                "continuousOperationCertified": False,
                "humanAcceptance": False,
                "operator": "AI browser automation",
                "sourceCommit": "not-performed",
                "sourceCommitReason": "runtime unavailable; static semantic proposal retained",
                "buildAssets": [{"path": "studio/dist/index.js", "sha256": "a" * 64}],
                "frames": frame_rows,
                "presentation": [dict(ref(gif), format="gif"), dict(ref(html), format="html")],
                "steps": [{"id": item, "status": "passed", "detail": "bounded evidence"} for item in [
                    "catalog-discovery", "source-overview", "hierarchy-expand", "four-direction-move",
                    "presentation-edit", "undo", "save-reopen", "current-export", "semantic-proposal",
                ]],
                "exports": [dict(ref(svg), format="svg"), dict(ref(pdf), format="pdf")],
            }
            _demo(root / "demo.json", demo, root, {"studio/dist/index.js": "a" * 64})
            forged = copy.deepcopy(demo)
            forged["recordingCertified"] = True
            with self.assertRaisesRegex(ValueError, "cannot certify recordingCertified"):
                _demo(root / "demo.json", forged, root, {"studio/dist/index.js": "a" * 64})

    def test_host_matrix_rejects_false_client_e2e(self) -> None:
        availability = {
            "hosts": [
                {"executableName": "codex", "availableOnPath": True},
                {"executableName": "claude", "availableOnPath": False},
                {"executableName": "dsh", "availableOnPath": False},
                {"executableName": "deepseek-harness", "availableOnPath": False},
            ]
        }
        rows = [
            {"host": "codex", "clientAvailable": True, "e2e": "not-tested", "degradationReason": "client prompt loading not exercised"},
            {"host": "claude-code", "clientAvailable": False, "e2e": "not-tested", "degradationReason": "command unavailable"},
            {"host": "deepseek-harness", "clientAvailable": False, "e2e": "not-tested", "degradationReason": "official client unavailable"},
        ]
        _host_matrix(rows, availability)
        forged = copy.deepcopy(rows)
        forged[0]["e2e"] = "passed"
        with self.assertRaisesRegex(ValueError, "not-tested state"):
            _host_matrix(forged, availability)


if __name__ == "__main__":
    unittest.main()
