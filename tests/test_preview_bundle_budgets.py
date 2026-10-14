"""Archive budget tests that do not stage or pack the full Studio catalog."""
from __future__ import annotations

import gzip
import hashlib
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch

from scripts import m5_beta_bundle as bundle


def portable_archive(path: Path, asset_count: int = 1) -> tuple[int, int]:
    version = "0.1.0-beta.4"
    contents = {f"studio/dist/preview/asset-{i}.json": b"{}" for i in range(asset_count)}
    contents["docs/evidence/m5-beta-release-manifest.json"] = json.dumps({"releaseVersion": version}).encode()
    manifest = {
        "schemaVersion": 1, "product": "archcanvas", "kind": "local-beta-preview",
        "version": version, "releaseMetadataVersion": version,
        "status": "in_progress", "gates": {"m4": "partial", "m5": "in_progress"},
        "hostE2E": {"codex": "not-tested", "claude-code": "not-tested", "deepseek-harness": "not-tested"},
        "dependenciesBundled": False, "modelExecution": False,
        "releaseManifestSha256": hashlib.sha256(contents["docs/evidence/m5-beta-release-manifest.json"]).hexdigest(),
        "files": [{"path": name, "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)} for name, data in contents.items()],
    }
    contents[bundle.BUNDLE_MANIFEST] = json.dumps(manifest).encode()
    with tarfile.open(path, "w:gz") as archive:
        for name, data in contents.items():
            member = tarfile.TarInfo(f"archcanvas-{version}/{name}")
            member.size = len(data)
            archive.addfile(member, io.BytesIO(data))
    return sum(map(len, contents.values())), len(contents)


class PreviewBundleBudgetTests(unittest.TestCase):
    def test_current_source_inventory_carries_migration_evidence_without_old_local_runs(self):
        root = Path(__file__).resolve().parents[1]
        inventory = {path.relative_to(root).as_posix() for path in bundle.source_paths(root)}
        migration_evidence = {
            "docs/preview-migration.md",
            "docs/preview-migration-validation.json",
            "docs/evidence/preview-migration-20261014/backend-regression.log",
            "docs/evidence/preview-migration-20261014/frontend-regression.log",
            "docs/evidence/preview-migration-20261014/http-assets.json",
            "docs/evidence/preview-migration-20261014/engine-regression.log",
            "docs/evidence/preview-migration-20261014/engine-regression.json",
            "docs/evidence/preview-migration-20261014/draft-constraints-final.log",
            "docs/evidence/preview-migration-20261014/ui-verification.json",
            "docs/evidence/preview-migration-20261014/ui-export-pdf-receipt.json",
            "docs/evidence/preview-migration-20261014/ui-export-png-receipt.json",
        }
        self.assertTrue(migration_evidence.issubset(inventory))
        self.assertFalse(any(path.startswith("docs/evidence/act-view-20261010/") for path in inventory))
        # Optional additions must not invalidate immutable historical bundles.
        self.assertTrue(migration_evidence.isdisjoint(bundle.required_release_files("0.1.0-beta.1")))

    def test_archive_with_full_preview_file_count_exceeds_old_limit_and_passes_new_budget(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "preview-assets.tar.gz"
            _, count = portable_archive(path, asset_count=7_500)
            self.assertGreater(count, 5_000)
            # Release schema checks have separate full-package tests. This
            # fixture exercises actual tar reading and complete hash inventory.
            with patch.object(bundle, "validate_release_contents", return_value={"releaseVersion": "0.1.0-beta.4"}):
                manifest, contents = bundle.read_bundle(path)
            self.assertEqual(len(contents), 7_501)
            self.assertEqual(len(manifest["files"]), 7_501)

    def test_exact_archive_byte_and_file_budgets_include_manifest(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "boundary.tar.gz"
            size, count = portable_archive(path)
            with patch.object(bundle, "validate_release_contents", return_value={"releaseVersion": "0.1.0-beta.4"}), patch.object(bundle, "MAX_BYTES", size), patch.object(bundle, "MAX_FILES", count):
                _, contents = bundle.read_bundle(path)
                self.assertEqual(len(contents), count - 1)
            with patch.object(bundle, "MAX_BYTES", size - 1), self.assertRaisesRegex(ValueError, "bounded size or file count"):
                bundle.read_bundle(path)
            with patch.object(bundle, "MAX_FILES", count - 1), self.assertRaisesRegex(ValueError, "bounded size or file count"):
                bundle.read_bundle(path)

    def test_oversized_archive_member_is_rejected_before_payload_allocation(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "oversized-header.tar.gz"
            member = tarfile.TarInfo("archcanvas-0.1.0-beta.4/studio/dist/preview/too-large.svg")
            member.size = bundle.MAX_BYTES + 1
            with gzip.open(path, "wb") as stream:
                stream.write(member.tobuf())
                stream.write(b"\0" * 1024)
            with self.assertRaisesRegex(ValueError, "bounded size or file count"):
                bundle.read_bundle(path)


if __name__ == "__main__":
    unittest.main()
