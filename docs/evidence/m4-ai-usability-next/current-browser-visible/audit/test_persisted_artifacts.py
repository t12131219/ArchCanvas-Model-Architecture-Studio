"""Independent mutations of real captured storage evidence, no product imports."""
import copy
import json
from pathlib import Path
import unittest

from check_final_artifacts import document_matches_scene
from check_directional_roles_v3 import read_capture


class PersistenceCounterexamples(unittest.TestCase):
    def setUp(self):
        scope = Path(__file__).resolve().parent.parent
        self.document = json.loads((scope / "actual-saved-document.json").read_text())["document"]
        self.capture = read_capture(scope / "save-reopened.json")

    def test_actual_stored_document_matches_public_reopened_scene(self):
        self.assertTrue(document_matches_scene(self.document, self.capture)["completeCanonicalFactsMatched"])

    def test_stale_document_revision_is_rejected(self):
        self.document["revision"] -= 1
        with self.assertRaisesRegex(ValueError, "identity/revision"):
            document_matches_scene(self.document, self.capture)

    def test_changed_local_anchor_is_rejected(self):
        self.document["layout"]["call:instance:model.MLP.network.0"]["y"] += 4
        with self.assertRaisesRegex(ValueError, "anchor"):
            document_matches_scene(self.document, self.capture)

    def test_source_bytes_changed_without_digest_are_rejected(self):
        self.document["architecture"]["sources"][0]["content"] += "# drift\n"
        with self.assertRaisesRegex(ValueError, "source bytes"):
            document_matches_scene(self.document, self.capture)

    def test_changed_canonical_port_is_rejected(self):
        self.document["architecture"]["edges"][2]["target"]["portId"] += ":wrong"
        with self.assertRaisesRegex(ValueError, "canonical edge"):
            document_matches_scene(self.document, self.capture)

    def test_changed_membership_is_rejected(self):
        self.document["expandedIds"] = []
        with self.assertRaisesRegex(ValueError, "membership"):
            document_matches_scene(self.document, self.capture)
