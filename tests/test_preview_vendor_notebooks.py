"""Refreshing upstream examples must not reintroduce Notebook assets."""
from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "studio/scripts/vendor-summary-preview.py"
SPEC = importlib.util.spec_from_file_location("preview_vendor_notebook_tests", SCRIPT)
vendor = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(vendor)


class PreviewVendorNotebookTests(unittest.TestCase):
    def test_initial_and_repeated_refresh_publish_python_without_notebooks(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, target = root / "upstream", root / "bundled"
            for tree in vendor.TREES:
                (source / tree).mkdir(parents=True)
            (source / "source_adapter").mkdir()
            (source / "README.md").write_text("Original source materials\n")
            (source / "source_adapter/README.md").write_text("Static source adapter\n")
            (source / "data/catalog.json").write_text(json.dumps({"counts": {}, "cases": []}))
            notebook = source / "snapshots/examples/sources/reference/model.ipynb"
            notebook.parent.mkdir(parents=True)
            sentinel = root / "must-not-execute"
            code = f"from pathlib import Path\nPath({str(sentinel)!r}).write_text('unsafe')\n"
            raw = json.dumps({"cells": [{"cell_type": "code", "source": code}],
                              "nbformat": 4, "nbformat_minor": 5}).encode()
            notebook.write_bytes(raw)
            target.mkdir()
            integration = target / "integration-manifest.json"
            integration.write_text(json.dumps({"schema": "existing-integration/1", "files": [
                {"path": "data/notebook-conversions.json", "bytes": 0, "sha256": "old"},
                {"path": "data/catalog-sources.json", "bytes": 0, "sha256": "old"}]}))
            vendor.main(["--source", str(source), "--target", str(target)])
            ledger = target / "data/notebook-conversions.json"
            first_ledger = ledger.read_bytes()
            manifest = json.loads((target / "vendor-manifest.json").read_bytes())
            self.assertFalse(list(target.rglob("*.ipynb")))
            self.assertFalse(sentinel.exists())
            for item in json.loads(integration.read_bytes())["files"]:
                data = (target / item["path"]).read_bytes()
                self.assertEqual(item["bytes"], len(data))
                self.assertEqual(item["sha256"], hashlib.sha256(data).hexdigest())
            self.assertFalse(any(item["path"].endswith(".ipynb") for item in manifest["files"]))
            conversion = manifest["convertedSources"][0]
            self.assertEqual(conversion["path"], notebook.relative_to(source).as_posix())
            self.assertEqual(conversion["sha256"], hashlib.sha256(raw).hexdigest())
            self.assertEqual(conversion["bytes"], len(raw))
            self.assertTrue(conversion["removed"])
            python = (target / conversion["replacement"]).read_bytes()
            ast.parse(python)
            self.assertEqual(hashlib.sha256(python).hexdigest(), conversion["replacement_sha256"])
            vendor.main(["--source", str(source), "--target", str(target)])
            self.assertFalse(list(target.rglob("*.ipynb")))
            self.assertEqual(ledger.read_bytes(), first_ledger)
            # A new upstream source is processed even after the old ledger
            # already contains only removed Notebook records.
            extra = notebook.with_name("additional.ipynb")
            extra.write_bytes(json.dumps({"cells": [{"cell_type": "code", "source": "answer = 42\n"}]}).encode())
            vendor.main(["--source", str(source), "--target", str(target)])
            self.assertEqual(json.loads(ledger.read_bytes())["notebook_count"], 2)
            self.assertFalse(list(target.rglob("*.ipynb")))
            self.assertFalse(sentinel.exists())


if __name__ == "__main__":
    unittest.main()
