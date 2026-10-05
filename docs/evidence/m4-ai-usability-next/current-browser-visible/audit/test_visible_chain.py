"""Independent warning/capture counterexamples, not Studio product tests."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

from check_directional import read_capture
from check_visible_chain import check_warning, warning_visible
from test_directional import sample


class VisibleCounterexamples(unittest.TestCase):
    def dom(self):
        return {"warnings": "Linear 1进入network标题区。向下移动。", "warningParent": "main", "warningBox": {"left": 20, "right": 180, "top": 30, "bottom": 60, "width": 160, "height": 30}, "viewport": {"left": 0, "right": 200, "top": 0, "bottom": 100, "width": 200, "height": 100}}

    def test_warning_outside_viewport_is_not_visible(self):
        dom = self.dom(); dom["warningBox"]["top"] = -10
        self.assertFalse(warning_visible(dom))

    def test_header_conflict_without_guidance_is_rejected(self):
        dom = self.dom(); dom["warnings"] = "有布局冲突"
        with self.assertRaisesRegex(ValueError, "guidance"):
            check_warning(dom, {"leafBodiesInContainerHeaderBands": [{}]}, True)

    def test_restore_with_leftover_warning_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "still has"):
            check_warning(self.dom(), {"leafBodiesInContainerHeaderBands": []}, False)

    def test_guidance_without_measured_conflict_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "measured"):
            check_warning(self.dom(), {"leafBodiesInContainerHeaderBands": []}, True)

    def test_raw_dom_envelope_retains_byte_hash(self):
        envelope = {"dom": {"svg": sample(), "paper": "translate(10px, 20px) scale(1)", "expandedIds": "[]", "pinnedIds": "[]"}, "action": {"operation": "drag"}}
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory) / "input.json"; p.write_text(json.dumps(envelope))
            value = read_capture(p)
            self.assertEqual(value["binding"]["bytes"], len(p.read_bytes()))
            self.assertEqual(value["capture"]["paperTransform"], envelope["dom"]["paper"])
            self.assertEqual(value["capture"]["svg"], sample())
