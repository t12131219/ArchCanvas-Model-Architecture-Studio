"""Static source conversion must preserve evidence and never execute a cell."""
from __future__ import annotations

import ast
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

SCRIPT = Path(__file__).resolve().parents[1] / "studio/scripts/convert-preview-notebooks.py"
SPEC = importlib.util.spec_from_file_location("preview_notebooks", SCRIPT)
converter = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(converter)


def notebook(*cells: str) -> bytes:
    return json.dumps({"cells": [{"cell_type": "code", "source": cell} for cell in cells],
                       "nbformat": 4, "nbformat_minor": 5}).encode()


class PreviewNotebookConversionTests(unittest.TestCase):
    def removed_ledger(self, root: Path, original: str, original_bytes: bytes):
        canonical = root / "sources/notebooks/model.py"
        canonical.parent.mkdir(parents=True, exist_ok=True)
        canonical.write_bytes(b"answer = 42\n")
        digest = converter.sha256(canonical.read_bytes())
        report = {"schema": converter.SCHEMA, "notebook_count": 1, "unique_notebook_count": 1,
                  "python_asset_count": 1, "notebooks": [{"notebook": original,
                  "notebook_sha256": converter.sha256(original_bytes),
                  "canonical_python": "sources/notebooks/model.py", "python_sha256": digest,
                  "conversion_id": "forged", "notebook_retained": False}],
                  "conversions": {"forged": {"canonical_python": "sources/notebooks/model.py",
                                             "python_sha256": digest, "line_map": []}}}
        ledger = root / "data/notebook-conversions.json"
        ledger.parent.mkdir(parents=True)
        ledger.write_bytes(converter.ledger_bytes(report))
        return report

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
            self.assertFalse(target.exists())
            self.assertEqual(converter.main(["--preview-root", str(root), "--check"]), 0)
            asset = root / "sources/notebooks/model.py"
            asset.write_text("answer = 43\n")
            self.assertEqual(converter.main(["--preview-root", str(root), "--check"]), 1)
            self.assertEqual(asset.read_text(), "answer = 43\n")

    def test_compatible_removal_flag_preserves_provenance_and_can_be_checked(self):
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

    def test_new_notebooks_after_completed_removal_extend_the_same_ledger(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = root / "snapshots/sources/first.ipynb"
            first.parent.mkdir(parents=True)
            first.write_bytes(notebook("answer = 41\n"))
            converter.migrate(root)
            ledger = root / "data/notebook-conversions.json"
            old = json.loads(ledger.read_bytes())
            second = first.with_name("second.IPYNB")
            second.write_bytes(notebook("answer = 42\n"))
            before = second.read_bytes()
            self.assertEqual(converter.main(["--preview-root", str(root), "--check"]), 1)
            self.assertEqual(second.read_bytes(), before)
            self.assertEqual(converter.main(["--preview-root", str(root)]), 0)
            self.assertFalse(second.exists())
            final = json.loads(ledger.read_bytes())
            self.assertEqual(final["notebook_count"], 2)
            self.assertEqual(final["notebooks"][0], old["notebooks"][0])
            self.assertEqual(final["conversions"][old["notebooks"][0]["conversion_id"]],
                             old["conversions"][old["notebooks"][0]["conversion_id"]])
            self.assertEqual(converter.main(["--preview-root", str(root), "--check"]), 0)
            stable = ledger.read_bytes()
            converter.migrate(root)
            self.assertEqual(ledger.read_bytes(), stable)

    def test_refresh_reintroduced_notebook_preserves_canonical_url_and_provenance(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "snapshots/sources/model.ipynb"
            target.parent.mkdir(parents=True)
            raw = notebook("answer = 42\n")
            target.write_bytes(raw)
            converter.migrate(root)
            ledger = root / "data/notebook-conversions.json"
            expected = ledger.read_bytes()
            target.write_bytes(raw)
            converter.migrate(root)
            self.assertEqual(ledger.read_bytes(), expected)
            self.assertFalse(target.exists())

    def test_failure_to_convert_any_input_retains_every_notebook(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = root / "snapshots/sources/a.ipynb"
            first.parent.mkdir(parents=True)
            first.write_bytes(notebook("answer = 42\n"))
            invalid = first.with_name("z.ipynb")
            invalid.write_bytes(b"invalid notebook JSON")
            with self.assertRaises(ValueError):
                converter.migrate(root)
            self.assertTrue(first.exists())
            self.assertTrue(invalid.exists())
            self.assertFalse((root / "data/notebook-conversions.json").exists())

    def test_new_logical_collision_cannot_overwrite_a_previously_published_asset(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = root / "snapshots/active/sources/model.ipynb"
            first.parent.mkdir(parents=True)
            first.write_bytes(notebook("answer = 41\n"))
            old = converter.migrate(root)
            canonical = old["notebooks"][0]["canonical_python"]
            old_data = (root / canonical).read_bytes()
            second = root / "snapshots/history/sources/model.ipynb"
            second.parent.mkdir(parents=True)
            second.write_bytes(notebook("answer = 42\n"))
            report = converter.migrate(root)
            self.assertEqual((root / canonical).read_bytes(), old_data)
            self.assertEqual(len({record["canonical_python"] for record in report["notebooks"]}), 2)
            self.assertFalse(converter.check_removed_records(root, report))

    def test_failed_python_publication_never_removes_notebook_inputs(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "snapshots/sources/model.ipynb"
            target.parent.mkdir(parents=True)
            raw = notebook("answer = 42\n")
            target.write_bytes(raw)
            original_write = Path.write_bytes
            def fail_python(path, data):
                if path.suffix == ".py":
                    raise OSError("simulated publication failure")
                return original_write(path, data)
            with mock.patch.object(Path, "write_bytes", fail_python):
                with self.assertRaisesRegex(OSError, "simulated publication failure"):
                    converter.migrate(root)
            self.assertEqual(target.read_bytes(), raw)
            self.assertFalse((root / "data/notebook-conversions.json").exists())

    def test_forged_ledger_cannot_delete_non_notebook_snapshot_file(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            victim = root / "snapshots/keep.py"
            victim.parent.mkdir(parents=True)
            raw = b"important = True\n"
            victim.write_bytes(raw)
            report = self.removed_ledger(root, "snapshots/keep.py", raw)
            ledger_bytes = (root / "data/notebook-conversions.json").read_bytes()
            for operation in (lambda: converter.build_plan(root, previous_report=report),
                              lambda: converter.check_removed_records(root, report),
                              lambda: converter.migrate(root)):
                with self.assertRaisesRegex(ValueError, "snapshots/.*ipynb"):
                    operation()
            self.assertEqual(victim.read_bytes(), raw)
            self.assertEqual((root / "data/notebook-conversions.json").read_bytes(), ledger_bytes)

    def test_forged_ledger_cannot_delete_notebook_outside_snapshots(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "snapshots").mkdir()
            victim = root / "sources/keep.ipynb"
            victim.parent.mkdir()
            raw = notebook("important = True\n")
            victim.write_bytes(raw)
            report = self.removed_ledger(root, "sources/keep.ipynb", raw)
            for operation in (lambda: converter.build_plan(root, previous_report=report),
                              lambda: converter.check_removed_records(root, report),
                              lambda: converter.migrate(root)):
                with self.assertRaisesRegex(ValueError, "snapshots/.*ipynb"):
                    operation()
            self.assertEqual(victim.read_bytes(), raw)

    def test_notebook_symlinks_are_neither_converted_nor_deleted(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            victim = root / "snapshots/source.bin"
            victim.parent.mkdir(parents=True)
            raw = notebook("important = True\n")
            victim.write_bytes(raw)
            link = victim.with_name("linked.IPYNB")
            link.symlink_to(victim)
            with self.assertRaisesRegex(ValueError, "symlink"):
                converter.build_plan(root)
            report = self.removed_ledger(root, "snapshots/linked.IPYNB", raw)
            for operation in (lambda: converter.check_removed_records(root, report),
                              lambda: converter.migrate(root)):
                with self.assertRaisesRegex(ValueError, "symlink"):
                    operation()
            self.assertTrue(link.is_symlink())
            self.assertEqual(victim.read_bytes(), raw)

    def test_ledger_cannot_delete_through_a_symlink_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            victim = root / "retained/source.ipynb"
            victim.parent.mkdir()
            raw = notebook("important = True\n")
            victim.write_bytes(raw)
            (root / "snapshots").mkdir()
            link = root / "snapshots/alias"
            link.symlink_to(victim.parent, target_is_directory=True)
            report = self.removed_ledger(root, "snapshots/alias/source.ipynb", raw)
            for operation in (lambda: converter.check_removed_records(root, report),
                              lambda: converter.migrate(root)):
                with self.assertRaisesRegex(ValueError, "symlink"):
                    operation()
            self.assertTrue(link.is_symlink())
            self.assertEqual(victim.read_bytes(), raw)

    def test_migration_refreshes_only_its_existing_integration_receipt(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            original = root / "snapshots/model.ipynb"
            original.parent.mkdir()
            original.write_bytes(notebook("answer = 42\n"))
            unrelated = {"path": "app.js", "bytes": 123, "sha256": "unchanged-receipt"}
            manifest = root / "integration-manifest.json"
            manifest.write_text(json.dumps({"schema": "existing-integration/1", "files": [
                {"path": "data/notebook-conversions.json", "bytes": 0, "sha256": "old-receipt"}, unrelated]}))
            converter.migrate(root)
            records = json.loads(manifest.read_bytes())["files"]
            data = (root / "data/notebook-conversions.json").read_bytes()
            self.assertEqual(records[0]["bytes"], len(data))
            self.assertEqual(records[0]["sha256"], converter.sha256(data))
            self.assertEqual(records[1], unrelated)
            self.assertFalse(original.exists())


if __name__ == "__main__":
    unittest.main()
