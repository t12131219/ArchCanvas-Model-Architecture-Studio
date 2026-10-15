"""Static source conversion must preserve evidence and never execute a cell."""
from __future__ import annotations

import ast
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "studio/scripts/convert-preview-notebooks.py"
SPEC = importlib.util.spec_from_file_location("preview_notebooks", SCRIPT)
converter = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(converter)


def notebook(*cells: str) -> bytes:
    return json.dumps({"cells": [{"cell_type": "code", "source": cell} for cell in cells],
                       "nbformat": 4, "nbformat_minor": 5}).encode()


class PreviewNotebookConversionTests(unittest.TestCase):
    def test_existing_evidence_lines_and_bytes_are_preserved(self):
        raw = notebook("value = 3\n", "class Model:\n    def forward(self, x):\n        return x + value\n")
        expected, expected_map, _ = converter.extract(json.loads(raw))
        result, strategy, mapping, _ = converter.convert(raw, expected.encode())
        self.assertEqual(result, expected.encode())
        self.assertEqual(strategy, "reuse-exact-python")
        self.assertEqual(mapping, expected_map)
        self.assertEqual(mapping[-1], {"derived_line": 7, "cell_index": 1,
                                       "cell_line": 3, "transform": "identity"})

    def test_valid_equivalent_existing_source_is_copied_and_remapped(self):
        raw = notebook("answer = 42\n")
        existing = b"# Existing source evidence header\n\nanswer = 42\n"
        result, strategy, mapping, _ = converter.convert(raw, existing)
        self.assertEqual(result, existing)
        self.assertEqual(strategy, "reuse-equivalent-python")
        self.assertEqual(mapping[0]["derived_line"], 3)

    def test_magic_shell_and_non_python_cells_are_static_comments(self):
        raw = notebook("%matplotlib inline\nanswer = 1\n", "%%bash\necho unsafe > /tmp/do-not-create\n",
                       "class Model:\n    def forward(self, x):\n        return x\n")
        result, strategy, mapping, diagnostics = converter.convert(raw, None)
        tree = ast.parse(result.decode())
        self.assertEqual([node.name for node in tree.body if isinstance(node, ast.ClassDef)], ["Model"])
        self.assertIn(b"# NOTEBOOK_CELL echo unsafe", result)
        self.assertEqual(strategy, "extract-static-python-with-commented-cells")
        self.assertTrue(diagnostics)
        self.assertTrue(all(item["derived_line"] is not None for item in mapping))

    def test_percent_format_continuation_remains_python(self):
        raw = notebook("text = ('value %d'\n        % value)\n")
        result, _, _, _ = converter.convert(raw, None)
        self.assertIn(b"        % value", result)
        self.assertNotIn(b"NOTEBOOK_MAGIC", result)
        ast.parse(result)

    def test_training_and_import_side_effects_are_never_executed(self):
        with tempfile.TemporaryDirectory() as directory:
            sentinel = Path(directory) / "execution-is-forbidden"
            source = f"from pathlib import Path\nPath({str(sentinel)!r}).write_text('bad')\nraise RuntimeError('do not run')\n"
            result, _, _, _ = converter.convert(notebook(source), None)
            ast.parse(result)
            self.assertFalse(sentinel.exists())

    def test_canonical_paths_are_legal_and_conflicts_cannot_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for scope, value in (("active", 1), ("history", 2)):
                target = root / "snapshots" / scope / "sources/9-batch/pytorch_ipynb/cnn-net.ipynb"
                target.parent.mkdir(parents=True)
                target.write_bytes(notebook(f"answer = {value}\n"))
            report, outputs = converter.build_plan(root)
            self.assertEqual(len(outputs), 2)
            self.assertEqual(report["notebook_count"], 2)
            for relative in outputs:
                path = Path(relative)
                self.assertTrue(all(part.isidentifier() for part in path.parts[:-1]))
                self.assertTrue(path.stem.isidentifier())
                self.assertTrue(path.name.startswith("cnn_net_"))
            again = converter.build_plan(root)
            self.assertEqual((report, outputs), again)

    def test_duplicate_notebooks_publish_one_python_and_keep_every_origin(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            raw = notebook("answer = 42\n")
            for scope in ("active", "history"):
                target = root / "snapshots" / scope / "sources/model.py.ipynb"
                target.parent.mkdir(parents=True)
                target.write_bytes(raw)
            report, outputs = converter.build_plan(root)
            self.assertEqual(report["notebook_count"], 2)
            self.assertEqual(report["unique_notebook_count"], 1)
            self.assertEqual(report["python_asset_count"], 1)
            self.assertEqual(len(report["conversions"]), 1)
            self.assertEqual(len(outputs), 1)

    def test_identical_code_at_distinct_import_paths_keeps_correct_line_maps(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            raw = notebook("answer = 42\n")
            for package in ("model-library", "module-library"):
                target = root / "snapshots/sources" / package / "model.ipynb"
                target.parent.mkdir(parents=True)
                target.write_bytes(raw)
            report, outputs = converter.build_plan(root)
            self.assertEqual(len(outputs), 2)
            self.assertEqual(report["unique_notebook_count"], 1)
            for record in report["notebooks"]:
                conversion = report["conversions"][record["conversion_id"]]
                self.assertEqual(record["canonical_python"], conversion["canonical_python"])

    def test_invalid_existing_encoding_cannot_replace_valid_extraction(self):
        result, strategy, _, _ = converter.convert(notebook(""), b"\xff")
        ast.parse(result)
        self.assertEqual(strategy, "extract-static-python")

    def test_check_detects_tamper_without_mutation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "snapshots/sources/model.ipynb"
            target.parent.mkdir(parents=True)
            target.write_bytes(notebook("answer = 42\n"))
            self.assertEqual(converter.main(["--preview-root", str(root)]), 0)
            self.assertEqual(converter.main(["--preview-root", str(root), "--check"]), 0)
            asset = root / "sources/notebooks/model.py"
            asset.write_text("answer = 43\n")
            self.assertEqual(converter.main(["--preview-root", str(root), "--check"]), 1)
            self.assertEqual(asset.read_text(), "answer = 43\n")

    def test_optional_removal_preserves_provenance_and_can_be_checked(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "snapshots/sources/model.ipynb"
            target.parent.mkdir(parents=True)
            target.write_bytes(notebook("answer = 42\n"))
            self.assertEqual(converter.main(["--preview-root", str(root), "--remove-notebooks"]), 0)
            self.assertFalse(target.exists())
            self.assertEqual(converter.main(["--preview-root", str(root), "--check"]), 0)
            report = json.loads((root / "data/notebook-conversions.json").read_text())
            self.assertEqual(report["notebooks"][0]["notebook"], "snapshots/sources/model.ipynb")
            self.assertFalse(report["notebooks"][0]["notebook_retained"])


if __name__ == "__main__":
    unittest.main()
