"""Independent counterexamples for the public-SVG audit, not product tests."""
import copy
import json
import unittest

from check_directional import check_export, check_move, check_pan, geometric_findings, matrix_of, svg_snapshot


def sample(*, x=50, y=60, revision=0, edge_end=60, bad_digest=False):
    metadata = {
        "documentId": "d", "revision": revision,
        "sourceDigest": ("b" if bad_digest else "a") * 64,
        "irDigest": "c" * 64,
        "sourceFacts": [{"id": "input", "kind": "Input", "category": "input"}, {"id": "linear", "kind": "Linear", "category": "linear"}],
        "sourceFactScope": "whole-source-architecture",
        "renderedNodes": [{"sceneNodeId": name, "canonicalNodeId": name, "boundary": False} for name in ("input", "linear")],
        "renderedBindings": [{"sceneEdgeId": "e", "canonicalEdgeIds": ["e"], "source": {"nodeId": "input", "portId": "input-out"}, "target": {"nodeId": "linear", "portId": "linear-in"}, "tensorId": "t", "role": "data"}],
    }
    return f'''<svg xmlns="http://www.w3.org/2000/svg" data-document-id="d" data-revision="{revision}" viewBox="0 0 300 300"><metadata>{json.dumps(metadata,separators=(',', ':'))}</metadata><g data-node-id="input" data-canonical-id="input"><rect x="50" y="10" width="40" height="20" stroke-width="1.5"/></g><g data-node-id="linear" data-canonical-id="linear"><rect x="{x}" y="{y}" width="40" height="20" stroke-width="1.5"/></g><g data-port-id="input:input-out:data" data-node-id="input"><circle cx="70" cy="30" r="2.6"/></g><g data-port-id="linear:linear-in:data" data-node-id="linear"><circle cx="{x+20}" cy="{y}" r="2.6"/></g><g data-edge-id="e" data-tensor-id="t"><path d="M 70 30 V 40 H {x+20} V {edge_end}" stroke="#000" stroke-width="1.5"/></g></svg>'''


def capture(svg, matrix=None):
    return {"scene": svg_snapshot(svg), "capture": {"expandedIds": [], "pinnedIds": [], "camera": {"matrix": dict(zip("abcdef", matrix or [1, 0, 0, 1, 10, 20]))}}, "binding": {"path": "authored-test", "bytes": len(svg), "sha256": "test"}}


class Counterexamples(unittest.TestCase):
    def phases(self):
        return {"before": capture(sample()), "moved": capture(sample(x=70, revision=1)), "undo": capture(sample(revision=2)), "redo": capture(sample(x=70, revision=3))}

    def case(self):
        return {"kind": "move", "direction": "right", "targetId": "linear", "input": {"from": [0, 0], "to": [20, 0]}}

    def test_full_xml_except_revision_restores(self):
        self.assertTrue(check_move(self.case(), self.phases())["undoFullSvgExceptRevision"])

    def test_wrong_direction_is_rejected(self):
        case = self.case(); case["direction"] = "left"
        with self.assertRaisesRegex(ValueError, "direction"):
            check_move(case, self.phases())

    def test_missing_phase_is_rejected(self):
        phases = self.phases(); phases.pop("redo")
        with self.assertRaisesRegex(ValueError, "four complete"):
            check_move(self.case(), phases)

    def test_undo_unrelated_geometry_is_rejected(self):
        phases = self.phases(); phases["undo"] = capture(sample(x=54, revision=2))
        with self.assertRaisesRegex(ValueError, "Undo"):
            check_move(self.case(), phases)

    def test_source_digest_change_is_rejected(self):
        phases = self.phases(); phases["moved"] = capture(sample(x=70, revision=1, bad_digest=True))
        with self.assertRaisesRegex(ValueError, "continuity"):
            check_move(self.case(), phases)

    def test_endpoint_detachment_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "detached"):
            svg_snapshot(sample(edge_end=64))

    def test_unknown_curve_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Unsupported path"):
            svg_snapshot(sample().replace("M 70 30 V 40 H 70 V 60", "M 70 30 Q 40 40 70 60"))

    def test_snapped_terminal_mismatch_is_rejected(self):
        case = self.case(); case["input"]["to"] = [28, 0]
        with self.assertRaisesRegex(ValueError, "snapped"):
            check_move(case, self.phases())

    def test_pan_exact_svg_and_reverse(self):
        text = sample()
        phases = {"before": capture(text), "panned": capture(text, [1, 0, 0, 1, 30, 20]), "reversed": capture(text)}
        self.assertTrue(check_pan({"direction": "right"}, phases)["exactSvgUnchanged"])

    def test_pan_document_revision_change_is_rejected(self):
        phases = {"before": capture(sample()), "panned": capture(sample(revision=1), [1, 0, 0, 1, 30, 20]), "reversed": capture(sample())}
        with self.assertRaisesRegex(ValueError, "exact SVG"):
            check_pan({"direction": "right"}, phases)

    def test_pan_failed_reverse_is_rejected(self):
        phases = {"before": capture(sample()), "panned": capture(sample(), [1, 0, 0, 1, 30, 20]), "reversed": capture(sample(), [1, 0, 0, 1, 11, 20])}
        with self.assertRaisesRegex(ValueError, "restore"):
            check_pan({"direction": "right"}, phases)

    def test_leaf_overlap_is_finding_not_aesthetic_pass(self):
        findings = geometric_findings(svg_snapshot(sample(y=25, edge_end=25)))
        self.assertEqual(len(findings["leafBodyOverlaps"]), 1)
        self.assertFalse(findings["aestheticCertified"])

    def test_actual_export_compares_public_appearance(self):
        value = capture(sample())
        self.assertTrue(check_export({"id": "e"}, {"interactive": value, "exported": value})["publicationAppearanceExactExceptInteractiveControls"])

    def test_actual_export_stale_revision_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "metadata"):
            check_export({"id": "e"}, {"interactive": capture(sample(revision=1)), "exported": capture(sample())})

    def test_actual_export_styling_drift_is_rejected(self):
        a = capture(sample())
        b = capture(sample().replace('stroke="#000"', 'stroke="#f00"'))
        with self.assertRaisesRegex(ValueError, "routing"):
            check_export({"id": "e"}, {"interactive": a, "exported": b})

    def test_public_inline_paper_transform(self):
        self.assertEqual(matrix_of({"paperTransform": "width: 595px; height: 942px; transform: translate(140.509px, 46px) scale(0.657113);"}), [.657113, 0, 0, .657113, 140.509, 46])

    def test_unsupported_inline_transform_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Unsupported camera"):
            matrix_of({"paperTransform": "transform: rotate(4deg);"})

    def test_unrelated_leaf_movement_is_rejected(self):
        phases = self.phases(); phases["moved"] = capture(sample(x=70, revision=1).replace('x="50" y="10"', 'x="52" y="10"'))
        with self.assertRaisesRegex(ValueError, "another visible leaf"):
            check_move(self.case(), phases)

    def test_multiple_undo_revisions_is_rejected(self):
        phases = self.phases(); phases["undo"] = capture(sample(revision=9))
        with self.assertRaisesRegex(ValueError, "one revision"):
            check_move(self.case(), phases)

    def test_header_intrusion_is_retained_as_geometric_finding(self):
        scene = svg_snapshot(sample())
        scene["headers"]["container"] = {"x": 40, "y": 50, "width": 100, "height": 15}
        findings = geometric_findings(scene)
        self.assertEqual(findings["leafBodiesInContainerHeaderBands"][0]["leafNode"], "linear")
        self.assertFalse(findings["aestheticCertified"])


if __name__ == "__main__":
    unittest.main()
