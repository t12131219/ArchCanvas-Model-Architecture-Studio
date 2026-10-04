"""Independent M2 black-box expectations from handwritten source and intent.

All source mutation is confined to TemporaryDirectory under /tmp. These tests
do not derive expected changed bytes or facts from transaction staging/output.
"""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from archcanvas_python import analyze_project


SOURCE = '''from torch import nn
from helper import NOTE

class Model(nn.Module):
    def __init__(self):
        super().__init__()
        self.left = nn.Dropout(p=0.1)  # target literal, not every 0.1
        self.right = nn.Dropout(p=0.1)
        self.attn = nn.MultiheadAttention(8, 2, dropout=0.1)

    def forward(self, q, memory):
        first = self.left(q)
        second = self.left(first)
        third = self.right(second)
        return self.attn(third, memory, memory, need_weights=False)[0]
'''


def handwritten_expected(parameter: str, value: str = "0.2") -> bytes:
    before = b"self.left = nn.Dropout(p=0.1)" if parameter == "p" else b"self.attn = nn.MultiheadAttention(8, 2, dropout=0.1)"
    after = b"self.left = nn.Dropout(p=" + value.encode() + b")" if parameter == "p" else b"self.attn = nn.MultiheadAttention(8, 2, dropout=" + value.encode() + b")"
    assert SOURCE.encode().count(before) == 1
    return SOURCE.encode().replace(before, after, 1)


class Stage2InvariantTests(unittest.TestCase):
    def setUp(self):
        # This module is introduced with M2. Its absence is an implementation
        # error once these tests are part of the stage's required test command.
        from archcanvas_transactions import TransactionError, TransactionManager
        self.TransactionError = TransactionError
        self.directory = tempfile.TemporaryDirectory(prefix="archcanvas-m2-oracle-", dir="/tmp")
        self.base = Path(self.directory.name)
        self.project = self.base / "project"
        self.project.mkdir()
        self.model = self.project / "model.py"
        self.model.write_bytes(SOURCE.encode())
        (self.project / "helper.py").write_text('NOTE = "full corpus freshness evidence"\n', encoding="utf-8")
        self.store = self.base / "transactions"
        self.manager = TransactionManager(self.store)
        self.architecture = analyze_project(self.project, "model:Model")

    def tearDown(self):
        self.directory.cleanup()

    def prepare(self, parameter="p", value=0.2, manager=None):
        node = next(
            n for n in self.architecture["nodes"]
            if n.get("instanceId", "").endswith(".left" if parameter == "p" else ".attn")
        )
        return (manager or self.manager).prepare(
            root=self.project, entry="model:Model", nodeId=node["id"],
            parameter=parameter, value=value,
            baseSourceDigest=self.architecture["sourceDigest"],
        )

    def approve(self, record):
        return self.manager.approve(record["id"], record["reviewDigest"])

    def assert_original(self, expected=SOURCE.encode()):
        self.assertEqual(self.model.read_bytes(), expected)

    def assert_rejected(self, action):
        """Both invalid-request exceptions and explicit blocked receipts reject."""
        try:
            result = action()
        except self.TransactionError:
            return None
        self.assertIn(result["status"], {"Failed", "Stale", "RolledBack", "ManualRecovery"})
        self.assertTrue(result.get("blockers") or result.get("recovery"), "A rejected operation needs a concrete explanation")
        return result

    def graph_shape(self, graph):
        """Relationship oracle ignores only constructor parameter values/digest."""
        return {
            "nodes": [(n["id"], n["kind"], n.get("instanceId"), n.get("repeat"), n["ports"]) for n in graph["nodes"]],
            "edges": graph["edges"],
        }

    def test_literal_targets_are_unique_and_shared_calls_all_change(self):
        record = self.prepare()
        self.assertEqual(record["status"], "ReviewReady")
        self.assert_original()
        approved = self.approve(record)
        committed = self.manager.commit(record["id"], approved["approvalId"])
        self.assertEqual(committed["status"], "Committed")
        self.assert_original(handwritten_expected("p"))
        observed = analyze_project(self.project, "model:Model")
        self.assertEqual(self.graph_shape(observed), self.graph_shape(self.architecture))
        left = [n for n in observed["nodes"] if n.get("instanceId", "").endswith(".left")]
        self.assertEqual(len(left), 2)
        self.assertEqual(len({n["instanceId"] for n in left}), 1)
        self.assertEqual({n["parameters"]["p"] for n in left}, {0.2})
        right = next(n for n in observed["nodes"] if n.get("instanceId", "").endswith(".right"))
        attention = next(n for n in observed["nodes"] if n.get("instanceId", "").endswith(".attn"))
        self.assertEqual(right["parameters"]["p"], 0.1)
        self.assertEqual(attention["parameters"]["dropout"], 0.1)

    def test_attention_literal_only_changes_authored_dropout(self):
        record = self.prepare("dropout")
        approved = self.approve(record)
        self.manager.commit(record["id"], approved["approvalId"])
        self.assert_original(handwritten_expected("dropout"))
        observed = analyze_project(self.project, "model:Model")
        self.assertEqual(self.graph_shape(observed), self.graph_shape(self.architecture))

    def test_prepare_rejects_derived_reference_and_invalid_values(self):
        for expression in ("0.05 * 2", "P", "config.dropout", "0", "True"):
            with self.subTest(expression=expression):
                source = SOURCE.replace("self.left = nn.Dropout(p=0.1)", f"self.left = nn.Dropout(p={expression})")
                self.model.write_text(source, encoding="utf-8")
                self.architecture = analyze_project(self.project, "model:Model")
                self.assert_rejected(self.prepare)
                self.assertEqual(self.model.read_text(encoding="utf-8"), source)
        self.model.write_bytes(SOURCE.encode())
        self.architecture = analyze_project(self.project, "model:Model")
        for value in (-0.01, 1.01, float("nan"), float("inf"), True, "0.2"):
            with self.subTest(value=repr(value)):
                self.assert_rejected(lambda: self.prepare(value=value))
                self.assert_original()

    def test_approval_binds_exact_review_and_rejects_reuse(self):
        record = self.prepare()
        with self.assertRaises(self.TransactionError):
            self.manager.approve(record["id"], "unrelated-review-digest")
        self.assert_original()
        approved = self.approve(record)
        self.manager.commit(record["id"], approved["approvalId"])
        committed_bytes = self.model.read_bytes()
        self.assert_rejected(lambda: self.manager.commit(record["id"], approved["approvalId"]))
        self.assert_original(committed_bytes)

    def test_approval_from_other_transaction_does_not_authorize_commit(self):
        left = self.prepare()
        attention = self.prepare("dropout")
        approved = self.approve(left)
        self.assert_rejected(lambda: self.manager.commit(attention["id"], approved["approvalId"]))
        self.assert_original()

    def test_imported_helper_change_invalidates_prepared_commit(self):
        record = self.prepare()
        approved = self.approve(record)
        helper = self.project / "helper.py"
        changed = b'NOTE = "a later human edit in another corpus file"\n'
        helper.write_bytes(changed)
        self.assert_rejected(lambda: self.manager.commit(record["id"], approved["approvalId"]))
        self.assert_original()
        self.assertEqual(helper.read_bytes(), changed)

    def test_source_edit_after_approval_is_never_overwritten(self):
        record = self.prepare()
        approved = self.approve(record)
        changed = SOURCE.encode() + b"\n# human changed file after review\n"
        self.model.write_bytes(changed)
        self.assert_rejected(lambda: self.manager.commit(record["id"], approved["approvalId"]))
        self.assert_original(changed)

    def test_staging_change_to_unapproved_literal_is_rejected(self):
        record = self.prepare()
        approved = self.approve(record)
        staged = self.store / record["id"] / "staged" / "model.py"
        altered = staged.read_bytes().replace(b"self.right = nn.Dropout(p=0.1)", b"self.right = nn.Dropout(p=0.8)")
        staged.write_bytes(altered)
        self.assert_rejected(lambda: self.manager.commit(record["id"], approved["approvalId"]))
        self.assert_original()

    def test_record_review_tamper_cannot_reuse_approval(self):
        record = self.prepare()
        approved = self.approve(record)
        path = self.store / record["id"] / "record.json"
        saved = json.loads(path.read_text(encoding="utf-8"))
        saved["reviewDigest"] = "changed-review-after-approval"
        path.write_text(json.dumps(saved), encoding="utf-8")
        self.assert_rejected(lambda: self.manager.commit(record["id"], approved["approvalId"]))
        self.assert_original()

    def test_approval_token_tamper_is_not_a_new_human_approval(self):
        record = self.prepare()
        self.approve(record)
        path = self.store / record["id"] / "record.json"
        saved = json.loads(path.read_text(encoding="utf-8"))
        chosen = "f" * 64
        saved["approvalId"] = chosen
        saved["_approval"]["id"] = chosen
        path.write_text(json.dumps(saved), encoding="utf-8")
        self.assert_rejected(lambda: self.manager.commit(record["id"], chosen))
        self.assert_original()

    def test_new_local_framework_shadow_invalidates_frozen_corpus(self):
        record = self.prepare()
        approved = self.approve(record)
        (self.project / "torch.py").write_text("nn = object()\n", encoding="utf-8")
        self.assert_rejected(lambda: self.manager.commit(record["id"], approved["approvalId"]))
        self.assert_original()

    def test_replace_failure_before_commit_leaves_original_bytes(self):
        record = self.prepare()
        approved = self.approve(record)
        original_replace = self.manager._replace
        def fail_replace(path, data, mode):
            if Path(path).resolve() == self.model.resolve():
                raise OSError("independent injected replace failure")
            return original_replace(path, data, mode)
        self.manager._replace = fail_replace
        self.assert_rejected(lambda: self.manager.commit(record["id"], approved["approvalId"]))
        self.assert_original()
        self.assertIn(self.manager.get(record["id"])["status"], {"Failed", "RolledBack", "ManualRecovery"})

    def test_written_source_verification_failure_recovers_exact_original(self):
        record = self.prepare()
        approved = self.approve(record)
        def fail_after_write(_record):
            self.assert_original(handwritten_expected("p"))
            raise self.TransactionError("independent write-after-verification failure")
        self.manager._verify_committed = fail_after_write
        result = self.assert_rejected(lambda: self.manager.commit(record["id"], approved["approvalId"]))
        self.assertEqual(result["status"], "RolledBack")
        self.assert_original()

    def test_recovery_never_overwrites_later_external_source_change(self):
        record = self.prepare()
        approved = self.approve(record)
        later = handwritten_expected("p") + b"\n# an editor changed source after source replacement\n"
        def edit_then_fail(_record):
            self.model.write_bytes(later)
            raise self.TransactionError("external source modification after replacement")
        self.manager._verify_committed = edit_then_fail
        result = self.assert_rejected(lambda: self.manager.commit(record["id"], approved["approvalId"]))
        self.assertEqual(result["status"], "ManualRecovery")
        self.assert_original(later)


if __name__ == "__main__":
    unittest.main()
