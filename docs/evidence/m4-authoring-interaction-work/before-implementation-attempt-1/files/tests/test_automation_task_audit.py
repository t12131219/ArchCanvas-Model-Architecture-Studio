"""Reject changed evidence without editing any retained raw task artifacts."""
import copy
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("automation_task_audit", ROOT / "scripts/validate_automation_task.py")
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)
EVIDENCE = ROOT / "docs/evidence/automation-full-task"
COLLECTION = EVIDENCE / "collection"


def read(path):
    return json.loads(path.read_text())


class AutomationTaskAuditRejectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plan = read(EVIDENCE / "expected-plan.json")
        cls.baseline = read(COLLECTION / "baseline/canvas.json")
        cls.before = read(COLLECTION / "incoming/undo-before-DOM.json")
        cls.after = read(COLLECTION / "incoming/drag-after-DOM.json")
        cls.reopened = read(COLLECTION / "incoming/reopened-DOM.json")
        cls.saved = read(COLLECTION / "incoming/saved-after-reload.json")

    def status(self, audit, name):
        return next(c["status"] for c in audit.checks if c["name"] == name)

    def compare_after(self, value):
        audit = AUDIT.Audit()
        AUDIT.compare_dom(audit, "after", self.before, value, self.plan, 32, 20)
        return audit

    def saved_audit(self, value):
        audit = AUDIT.Audit()
        AUDIT.saved_checks(audit, "saved", value, self.reopened, self.plan, self.baseline)
        return audit

    def test_wrong_delta_is_rejected_even_when_revision_identity_match(self):
        target = self.plan["canonicalTargets"]["movedNode"]
        original = self.compare_after(self.after)
        self.assertEqual(self.status(original, "after.node." + target), "pass")
        altered = copy.deepcopy(self.after)
        next(n for n in altered["nodes"] if n["id"] == target)["body"]["x"] += 4
        self.assertEqual(self.status(self.compare_after(altered), "after.node." + target), "fail")

    def test_wrong_target_identity_is_rejected(self):
        altered = copy.deepcopy(self.after)
        target = self.plan["canonicalTargets"]["movedNode"]
        next(n for n in altered["nodes"] if n["id"] == target)["canonicalId"] = self.plan["canonicalTargets"]["feedforward"]
        self.assertEqual(self.status(self.compare_after(altered), "after.node." + target), "fail")

    def test_viewport_shift_cannot_be_hidden_by_unchanged_camera(self):
        altered = copy.deepcopy(self.before)
        altered["viewport"]["x"] += 30
        audit = AUDIT.Audit()
        AUDIT.compare_dom(audit, "undo", self.before, altered, self.plan)
        self.assertEqual(self.status(audit, "undo.camera"), "pass")
        self.assertEqual(self.status(audit, "undo.viewport"), "fail")

    def test_real_ancestor_resize_is_not_silently_added_to_expected(self):
        audit = self.compare_after(self.after)
        self.assertEqual(self.status(audit, "after.node.call:instance:model.Transformer"), "fail")
        self.assertEqual(self.status(audit, "after.nodeOrigin.call:instance:model.Transformer"), "pass")

    def test_source_binding_edit_rejected_even_with_unchanged_digest_strings(self):
        altered = copy.deepcopy(self.saved)
        altered["document"]["architecture"]["edges"][0]["source"]["portId"] += "-tampered"
        self.assertEqual(self.status(self.saved_audit(altered), "saved.sourceArchitectureExact"), "fail")

    def test_monochrome_display_does_not_authorize_losing_saved_color_override(self):
        self.assertEqual(self.status(self.saved_audit(self.saved), "saved.intended.nodeStyleOverrides"), "pass")
        altered = copy.deepcopy(self.saved)
        altered["document"]["nodeStyleOverrides"][self.plan["canonicalTargets"]["encoder"]]["fill"] = "#ffffff"
        self.assertEqual(self.status(self.saved_audit(altered), "saved.intended.nodeStyleOverrides"), "fail")

    def test_annotation_and_legend_tampering_rejected(self):
        altered = copy.deepcopy(self.saved)
        altered["document"]["annotations"][0]["id"] = "annotation-not-a-uuid"
        altered["document"]["legendItems"].reverse()
        audit = self.saved_audit(altered)
        self.assertEqual(self.status(audit, "saved.annotationIntended"), "fail")
        self.assertEqual(self.status(audit, "saved.legendExact"), "fail")

    def test_same_revision_export_with_different_fields_is_rejected(self):
        identity = "77de76b8a527438c83c0348e8b22ad4a"
        with tempfile.TemporaryDirectory(prefix="archcanvas-audit-negative-") as temporary:
            directory = Path(temporary) / identity
            shutil.copytree(COLLECTION / "workspace-exports" / identity, directory)
            input_path = directory / "document.json"
            altered = read(input_path)
            altered["annotations"][0]["text"] = "tampered but same revision"
            input_path.write_text(json.dumps(altered))
            audit = AUDIT.Audit()
            AUDIT.export_checks(audit, directory, self.saved["document"], self.reopened, self.plan, self.baseline)
            self.assertEqual(self.status(audit, "export." + identity + ".exactFinalCanvasInput"), "fail")
            self.assertEqual(self.status(audit, "export." + identity + ".receipt.revision"), "pass")

    def test_editable_receipt_hash_cannot_hide_svg_tensor_tampering(self):
        identity = "77de76b8a527438c83c0348e8b22ad4a"
        with tempfile.TemporaryDirectory(prefix="archcanvas-audit-negative-") as temporary:
            directory = Path(temporary) / identity
            shutil.copytree(COLLECTION / "workspace-exports" / identity, directory)
            figure = directory / "figure.svg"
            raw = figure.read_bytes()
            old = b'data-tensor-id="tensor:call:instance:model.Transformer.encoder.0.feedforward.expand:output"'
            self.assertEqual(raw.count(old), 1)
            raw = raw.replace(old, b'data-tensor-id="tensor:tampered"')
            figure.write_bytes(raw)
            receipt_path = directory / "figure.svg.receipt.json"
            receipt = read(receipt_path)
            receipt["outputDigest"], receipt["bytes"] = AUDIT.digest(raw), len(raw)
            receipt_path.write_text(json.dumps(receipt))
            audit = AUDIT.Audit()
            AUDIT.export_checks(audit, directory, self.saved["document"], self.reopened, self.plan, self.baseline)
            self.assertEqual(self.status(audit, "export." + identity + ".outputBytes"), "pass")
            self.assertEqual(self.status(audit, "export." + identity + ".svg.canonicalBinding.edge:18"), "fail")

    def test_missing_native_and_initial_position_stay_unknown(self):
        with tempfile.TemporaryDirectory(prefix="archcanvas-audit-missing-") as temporary:
            report_path = Path(temporary) / "report.json"
            result = subprocess.run([sys.executable, str(ROOT / "scripts/validate_automation_task.py"),
                "--plan", str(EVIDENCE / "expected-plan.json"), "--baseline", str(COLLECTION / "baseline/canvas.json"),
                "--before", str(COLLECTION / "incoming/undo-before-DOM.json"), "--output", str(report_path)],
                capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            report = read(report_path)
            statuses = {c["name"]: c["status"] for c in report["checks"]}
            for name in ("native.trustedSamePointerDownMovesUp", "annotation.initialPosition", "pin.screenCoverage", "afterDOM"):
                self.assertEqual(statuses[name], "unknown")
            self.assertFalse(report["humanSuccessCertified"])
            self.assertEqual(report["researchGate"], "not_run")

    def test_output_cannot_replace_raw_evidence(self):
        with tempfile.TemporaryDirectory(prefix="archcanvas-audit-protected-") as temporary:
            path = Path(temporary) / "plan.json"
            shutil.copyfile(EVIDENCE / "expected-plan.json", path)
            before = path.read_bytes()
            result = subprocess.run([sys.executable, str(ROOT / "scripts/validate_automation_task.py"),
                "--plan", str(path), "--baseline", str(COLLECTION / "baseline/canvas.json"), "--output", str(path)],
                capture_output=True, text=True)
            self.assertEqual(result.returncode, 2)
            self.assertEqual(path.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
