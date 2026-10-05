"""Independent actual-export decimal counterexamples, not product tests."""
import json
import unittest
import xml.etree.ElementTree as ET

from check_directional_export_v2 import check_export, svg_snapshot
from test_directional import sample


def capture(height="284.97mm", width="180mm", canonical=284.97478991596637):
    root = ET.fromstring(sample())
    root.set("width", width); root.set("height", height)
    metadata = root.find("{http://www.w3.org/2000/svg}metadata")
    value = json.loads(metadata.text); value.update(widthMm=180, heightMm=canonical)
    metadata.text = json.dumps(value, separators=(",", ":"))
    # Serialization prefixes metadata, while the checker's raw normalization
    # deliberately requires the actual exported explicit unprefixed spelling.
    ET.register_namespace("", "http://www.w3.org/2000/svg")
    text = ET.tostring(root, encoding="unicode")
    return {"scene": svg_snapshot(text), "capture": {}, "binding": {"path": "authored-counterexample"}}


class ExportPrecisionCounterexamples(unittest.TestCase):
    def test_actual_two_and_six_decimals_are_recorded(self):
        result = check_export({"id": "e"}, {"interactive": capture(), "exported": capture("284.974790mm")})
        self.assertFalse(result["rootPhysicalDimensionSpellingsExact"])
        self.assertAlmostEqual(result["physicalDimensionRounding"][1]["absoluteRootDeltaMm"], .00479)

    def test_two_decimal_drift_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "decimal precision"):
            check_export({"id": "e"}, {"interactive": capture(), "exported": capture("284.98mm")})

    def test_six_decimal_drift_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "decimal precision"):
            check_export({"id": "e"}, {"interactive": capture(), "exported": capture("284.974792mm")})

    def test_pixel_units_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "decimal mm"):
            check_export({"id": "e"}, {"interactive": capture(), "exported": capture("284.97px")})

    def test_missing_physical_metadata_is_rejected(self):
        a = capture(); b = capture(); a["scene"]["metadata"].pop("heightMm"); b["scene"]["metadata"].pop("heightMm")
        with self.assertRaisesRegex(ValueError, "canonical physical"):
            check_export({"id": "e"}, {"interactive": a, "exported": b})

    def test_appearance_drift_is_still_rejected(self):
        a = capture(); b = capture("284.974790mm")
        b["scene"]["root"].find(".//{http://www.w3.org/2000/svg}rect").set("fill", "red")
        with self.assertRaisesRegex(ValueError, "appearance"):
            check_export({"id": "e"}, {"interactive": a, "exported": b})
