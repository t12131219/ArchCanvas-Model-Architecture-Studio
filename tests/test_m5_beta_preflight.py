"""Independent output-boundary checks for the M5 release preflight."""

import hashlib
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("m5_beta_preflight", ROOT / "scripts/m5_beta_preflight.py")
preflight = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(preflight)


class M5PreflightTests(unittest.TestCase):
    def test_fresh_cli_uses_formal_source_and_preserves_text_svg_dimensions(self):
        source = (ROOT / "fixtures/mlp/model.py").read_bytes()
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run([sys.executable, "scripts/m5_beta_preflight.py", "--formats", "svg", "--output-dir", directory], cwd=ROOT, text=True, capture_output=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr)
            receipt = json.loads((Path(directory) / "receipt.json").read_text())
            self.assertEqual(receipt["status"], "passed")
            self.assertEqual(receipt["sourceFileSha256"], hashlib.sha256(source).hexdigest())
            self.assertTrue(receipt["sourceUnchanged"])
            self.assertTrue(receipt["documentUnchanged"])
            self.assertEqual((ROOT / "fixtures/mlp/model.py").read_bytes(), source)
            self.assertTrue(Path(receipt["capabilities"]["moduleOrigin"]).is_relative_to(ROOT / "src"))
            document = Path(receipt["documentFile"])
            self.assertEqual(hashlib.sha256(document.read_bytes()).hexdigest(), receipt["documentDigest"])
            self.assertEqual(len(receipt["artifacts"]), 2)
            for artifact in receipt["artifacts"]:
                tree = ET.fromstring(Path(artifact["artifact"]).read_bytes())
                self.assertEqual(float(tree.get("width").removesuffix("mm")), artifact["widthMm"])
                self.assertEqual(artifact["glyphCoverage"], "not-checked-text-svg")
                self.assertFalse(artifact["fontEmbeddingGuaranteed"])
                self.assertEqual(artifact["errors"], [])
            # Replaying into the same evidence directory must preserve bytes.
            before = (Path(directory) / "receipt.json").read_bytes()
            repeated = subprocess.run([sys.executable, "scripts/m5_beta_preflight.py", "--formats", "svg", "--output-dir", directory], cwd=ROOT, text=True, capture_output=True, timeout=30)
            self.assertNotEqual(repeated.returncode, 0)
            self.assertEqual((Path(directory) / "receipt.json").read_bytes(), before)

    def test_forged_width_claim_is_rejected_using_actual_svg_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            artifact = Path(directory) / "figure.svg"
            artifact.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="180mm" height="90mm" viewBox="0 0 200 100"/>')
            receipt_path = Path(directory) / "figure.svg.receipt.json"
            receipt = {"format": "svg", "outputDigest": hashlib.sha256(artifact.read_bytes()).hexdigest(), "widthMm": 85, "heightMm": 90,
                       "geometryVerified": True, "fonts": {"embeddingGuaranteed": False},
                       "physicalPreflight": {"minTextPt": 8, "nodeLabelPt": 10, "minMainLinePt": .6, "heightMm": 90}}
            receipt_path.write_text(json.dumps(receipt))
            result = preflight.check_receipt(artifact, receipt_path, width=85, fmt="svg")
            self.assertIn("actual SVG physical dimensions do not match its receipt", result["errors"])

    def test_forged_digest_and_false_raster_font_claim_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            artifact = Path(directory) / "figure.pdf"
            artifact.write_bytes(b"%PDF-1.4\n/MediaBox [0 0 240.944882 120.472441]\n")
            receipt_path = Path(directory) / "figure.pdf.receipt.json"
            receipt = {"format": "pdf", "outputDigest": "0" * 64, "widthMm": 85, "heightMm": 42.5, "geometryVerified": True,
                       "fonts": {"glyphCoverage": {"status": "assumed"}},
                       "physicalPreflight": {"minTextPt": 8, "nodeLabelPt": 10, "minMainLinePt": .6, "heightMm": 42.5}}
            receipt_path.write_text(json.dumps(receipt))
            result = preflight.check_receipt(artifact, receipt_path, width=85, fmt="pdf")
            self.assertIn("receipt outputDigest does not match the artifact", result["errors"])
            self.assertIn("unexpected glyphCoverage status: 'assumed'", result["errors"])


if __name__ == "__main__":
    unittest.main()
