"""Deliberate geometric counterexamples for the independent saved-SVG auditor."""

import json
from pathlib import Path
import tempfile
import unittest

from audit_geometry import OUT, inspect, primitive_counterexamples


class GeometryAuditTests(unittest.TestCase):
    def run_svg(self, *, route="M 10 20 V 60 H 110 V 100", source_dot=(10, 20), target_dot=(110, 100),
                marker=True, obstacle=(60, 40, 30, 40), parent=None):
        architecture = {"sourceDigest": "fixture-source", "irDigest": "fixture-ir", "nodes": [
            {"id": "a"}, {"id": "b"}, {"id": "c"}]}
        if parent:
            architecture["nodes"][1]["parentId"] = parent
        metadata = {"documentId": "geometry-counterexample", "revision": 0, "sourceDigest": "fixture-source",
                    "irDigest": "fixture-ir", "renderedBindings": [{"sceneEdgeId": "edge", "canonicalEdgeIds": ["edge"],
                    "source": {"nodeId": "a", "portId": "a:out:x"}, "target": {"nodeId": "b", "portId": "b:in:x"}, "role": "data"}]}
        x, y, width, height = obstacle
        svg = f'''<svg xmlns="http://www.w3.org/2000/svg"><metadata>{json.dumps(metadata)}</metadata>
<defs>{'<marker id="arrow"/>' if marker else ''}</defs>
<g data-node-id="a" data-canonical-id="a" aria-label="A"><rect x="0" y="0" width="20" height="20"/></g>
<g data-node-id="b" data-canonical-id="b" aria-label="B"><rect x="100" y="100" width="20" height="20"/></g>
<g data-node-id="c" data-canonical-id="c" aria-label="C"><rect x="{x}" y="{y}" width="{width}" height="{height}"/></g>
<g data-port-id="a:a:out:x:data" data-node-id="a"><circle cx="{source_dot[0]}" cy="{source_dot[1]}" r="2.6" fill="black"/></g>
<g data-port-id="b:b:in:x:data" data-node-id="b"><circle cx="{target_dot[0]}" cy="{target_dot[1]}" r="2.6" fill="black"/></g>
<g data-edge-id="edge" data-tensor-id="tensor"><path d="{route}" marker-end="url(#arrow)"/></g></svg>'''
        with tempfile.TemporaryDirectory(prefix="counterexample-", dir=OUT) as temporary:
            path = Path(temporary) / "actual.svg"
            path.write_text(svg)
            return inspect(path, {"architecture": architecture}, "deliberate-counterexample")

    def test_primitives_reject_curve_and_distinguish_touch_and_crossing(self):
        self.assertTrue(primitive_counterexamples()["passed"])

    def test_actual_route_crossing_unrelated_body_is_reported(self):
        result = self.run_svg()
        self.assertEqual([(risk["edgeId"], risk["nodeId"], risk["segments"]) for risk in result["unrelatedBodyPenetrations"]], [("edge", "c", [1])])
        self.assertEqual(result["endpointDefects"], [])

    def test_ancestor_body_does_not_count_as_unrelated_penetration(self):
        result = self.run_svg(parent="c")
        self.assertEqual(result["unrelatedBodyPenetrations"], [])

    def test_stale_endpoint_dot_is_rejected(self):
        result = self.run_svg(target_dot=(100, 100))
        self.assertEqual([(risk["edgeId"], risk["direction"]) for risk in result["endpointDefects"]], [("edge", "target")])

    def test_missing_marker_definition_is_reported(self):
        result = self.run_svg(marker=False)
        self.assertEqual(result["endpointDefects"][0]["reason"], "marker-end has no saved marker definition")

    def test_true_body_overlap_is_reported(self):
        result = self.run_svg(obstacle=(5, 5, 20, 20))
        self.assertEqual(result["unrelatedBodyOverlaps"][0]["firstNodeId"], "a")
        self.assertEqual(result["unrelatedBodyOverlaps"][0]["secondNodeId"], "c")
        self.assertEqual(result["unrelatedBodyOverlaps"][0]["overlapArea"], 225)

    def test_border_only_contact_is_not_a_body_penetration(self):
        result = self.run_svg(obstacle=(60, 60, 30, 40))
        self.assertEqual(result["unrelatedBodyPenetrations"], [])


if __name__ == "__main__":
    unittest.main()
