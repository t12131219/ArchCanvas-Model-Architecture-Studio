"""Concrete source, independent expected facts, approval and fault guard evidence."""

import ast
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from archcanvas_python import analyze_project
from archcanvas_transactions import TransactionError, TransactionManager
from archcanvas_transactions.lowering import rewrite_literal


SOURCE = '''from torch import nn
class Model(nn.Module):
    def __init__(self):
        super().__init__()
        self.left = nn.Dropout(0.1)  # preserve me: 0.1
        self.right = nn.Dropout(p=0.1)
    def forward(self, x):
        return self.right(self.left(self.left(x)))
'''


class ParameterTransactionTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="archcanvas-transaction-", dir="/tmp")
        self.root = Path(self.temporary.name) / "project"
        self.root.mkdir()
        self.path = self.root / "model.py"
        self.path.write_bytes(SOURCE.encode())
        self.store = Path(self.temporary.name) / "transactions"
        self.manager = TransactionManager(self.store)

    def tearDown(self):
        self.temporary.cleanup()

    def prepare(self, value=0.2):
        before = analyze_project(self.root, "model:Model")
        selected = next(node for node in before["nodes"] if node.get("instanceId", "").endswith(".left"))
        return self.manager.prepare(self.root, "model:Model", selected["id"], "p", value, before["sourceDigest"])

    def approve(self, receipt):
        self.assertEqual(receipt["status"], "ReviewReady", receipt["blockers"])
        return self.manager.approve(receipt["id"], receipt["reviewDigest"])

    def test_isolation_precise_token_and_shared_calls(self):
        receipt = self.prepare()
        self.assertEqual(receipt["status"], "ReviewReady")
        self.assertEqual(self.path.read_bytes(), SOURCE.encode())
        self.assertEqual(len(receipt["affectedNodeIds"]), 2)
        self.assertEqual(receipt["intent"]["before"], 0.1)
        self.assertEqual(receipt["intent"]["after"], 0.2)
        approved = self.approve(receipt)
        result = self.manager.commit(receipt["id"], approved["approvalId"])
        self.assertEqual(result["status"], "Committed")
        self.assertEqual(self.path.read_bytes(), SOURCE.replace("nn.Dropout(0.1)", "nn.Dropout(0.2)").encode())
        left = [node for node in result["committedArchitecture"]["nodes"] if node.get("instanceId", "").endswith(".left")]
        right = [node for node in result["committedArchitecture"]["nodes"] if node.get("instanceId", "").endswith(".right")]
        self.assertEqual([node["parameters"]["p"] for node in left], [0.2, 0.2])
        self.assertEqual([node["parameters"]["p"] for node in right], [0.1])

    def test_expected_delta_is_not_staged_oracle(self):
        def wrong_target(raw, origin, kind, parameter, old, new, corpus):
            # Intentionally wrong lowering: selected left remains untouched,
            # another identical-valued constructor changes instead.
            return raw.replace(b"p=0.1", b"p=0.2")
        with patch("archcanvas_transactions.service.rewrite_literal", wrong_target):
            receipt = self.prepare()
        self.assertEqual(receipt["status"], "Failed")
        self.assertIn("ExpectedDelta", receipt["blockers"][0])
        self.assertEqual(self.path.read_bytes(), SOURCE.encode())
        with self.assertRaises(TransactionError):
            self.manager.approve(receipt["id"], receipt["reviewDigest"])

    def test_wrong_value_and_extra_semantic_changes_fail_independent_delta(self):
        def wrong(raw, origin, kind, parameter, old, new, corpus):
            return rewrite_literal(raw, origin, kind, parameter, old, 0.3, corpus)
        with patch("archcanvas_transactions.service.rewrite_literal", wrong):
            receipt = self.prepare()
        self.assertEqual(receipt["status"], "Failed")
        self.assertIn("ExpectedDelta", receipt["blockers"][0])

    def test_utf8_bom_crlf_unicode_comment_and_no_final_newline_preserved(self):
        raw = b"\xef\xbb\xbf" + SOURCE.replace("preserve me: 0.1", "保留注释: 0.1").replace("\n", "\r\n").rstrip("\r\n").encode()
        self.path.write_bytes(raw)
        self.path.chmod(0o640)
        receipt = self.prepare(0.123456)
        approved = self.approve(receipt)
        self.assertEqual(self.manager.commit(receipt["id"], approved["approvalId"])["status"], "Committed")
        self.assertEqual(self.path.read_bytes(), raw.replace(b"nn.Dropout(0.1)", b"nn.Dropout(0.123456)"))
        self.assertEqual(self.path.stat().st_mode & 0o777, 0o640)

    def test_constructor_argument_is_frozen_evidence_not_guessed_literal(self):
        self.path.write_text(SOURCE.replace("def __init__(self):", "def __init__(self, probability=0.1):").replace("nn.Dropout(0.1)", "nn.Dropout(probability)"))
        before = analyze_project(self.root, "model:Model")
        left = next(node for node in before["nodes"] if node.get("instanceId", "").endswith(".left"))
        self.assertEqual(left["parameterOrigins"]["p"]["kind"], "constructor_argument")
        self.assertEqual(left["parameters"]["p"], 0.1)
        receipt = self.prepare()
        self.assertEqual(receipt["status"], "Failed")
        self.assertIn("constructor arguments", receipt["blockers"][0])

    def test_local_config_source_corpus_bound_and_unsupported_reference(self):
        (self.root / "settings.py").write_text("PROBABILITY = 0.1\n")
        self.path.write_text(SOURCE.replace("from torch import nn", "from torch import nn\nfrom settings import PROBABILITY").replace("nn.Dropout(0.1)", "nn.Dropout(PROBABILITY)"))
        before = analyze_project(self.root, "model:Model")
        self.assertEqual([source["path"] for source in before["sources"]], ["model.py", "settings.py"])
        receipt = self.prepare()
        self.assertEqual(receipt["status"], "Failed")
        self.assertIn("config references", receipt["blockers"][0])

    def test_full_corpus_freshness_includes_helper_and_new_import_shadow(self):
        self.path.write_text(SOURCE.replace("from torch import nn", "from torch import nn\nfrom helper import NOTE"))
        helper = self.root / "helper.py"
        helper.write_text("NOTE = 1\n")
        receipt = self.prepare()
        approved = self.approve(receipt)
        original = self.path.read_bytes()
        helper.write_text("NOTE = 2\n")
        result = self.manager.commit(receipt["id"], approved["approvalId"])
        self.assertEqual(result["status"], "Stale")
        self.assertEqual(self.path.read_bytes(), original)
        self.assertIn("helper.py", result["blockers"][0])

    def test_approval_replay_and_cross_transaction_are_rejected(self):
        one = self.prepare(0.2)
        two = self.prepare(0.3)
        approved_one = self.approve(one)
        approved_two = self.approve(two)
        with self.assertRaises(TransactionError):
            self.manager.commit(two["id"], approved_one["approvalId"])
        self.assertEqual(self.path.read_bytes(), SOURCE.encode())
        self.assertEqual(self.manager.commit(one["id"], approved_one["approvalId"])["status"], "Committed")
        with self.assertRaises(TransactionError):
            self.manager.commit(one["id"], approved_one["approvalId"])
        self.assertEqual(self.manager.commit(two["id"], approved_two["approvalId"])["status"], "Stale")

    def test_staging_or_review_tamper_cannot_be_written(self):
        for tamper in ("stage", "diff"):
            with self.subTest(tamper=tamper):
                receipt = self.prepare()
                approved = self.approve(receipt)
                if tamper == "stage":
                    stage = self.store / receipt["id"] / "staged/model.py"
                    stage.write_bytes(stage.read_bytes().replace(b"p=0.1", b"p=0.8"))
                else:
                    path = self.store / receipt["id"] / "record.json"
                    record = json.loads(path.read_text())
                    record["diff"] = "an unapproved replacement diff"
                    path.write_text(json.dumps(record))
                result = self.manager.commit(receipt["id"], approved["approvalId"])
                self.assertEqual(result["status"], "Stale")
                self.assertEqual(self.path.read_bytes(), SOURCE.encode())

    def test_failure_after_replace_rolls_back_matching_after_only(self):
        receipt = self.prepare()
        approved = self.approve(receipt)
        with patch.object(self.manager, "_verify_committed", side_effect=OSError("injected post-replace failure")):
            result = self.manager.commit(receipt["id"], approved["approvalId"])
        self.assertEqual(result["status"], "RolledBack")
        self.assertEqual(self.path.read_bytes(), SOURCE.encode())
        self.assertEqual((self.store / receipt["id"] / "backup/model.py").read_bytes(), SOURCE.encode())

    def test_recovery_preserves_later_external_change(self):
        receipt = self.prepare()
        approved = self.approve(receipt)
        external = b"# external editor has newer content\n" + SOURCE.encode()
        def fail_after_external_change(record):
            self.path.write_bytes(external)
            raise OSError("injected concurrent editor and failed verification")
        with patch.object(self.manager, "_verify_committed", fail_after_external_change):
            result = self.manager.commit(receipt["id"], approved["approvalId"])
        self.assertEqual(result["status"], "ManualRecovery")
        self.assertEqual(self.path.read_bytes(), external)
        self.assertTrue(any("later external" in blocker for blocker in result["blockers"]))

    def test_registered_crash_recovery_is_guarded(self):
        receipt = self.prepare()
        approved = self.approve(receipt)
        def simulate_process_exit(record):
            raise SystemExit("simulated process exit after replacement")
        with patch.object(self.manager, "_verify_committed", simulate_process_exit):
            with self.assertRaises(SystemExit):
                self.manager.commit(receipt["id"], approved["approvalId"])
        self.assertIn(b"nn.Dropout(0.2)", self.path.read_bytes())
        restarted = TransactionManager(self.store)
        self.assertEqual(restarted.get(receipt["id"])["status"], "RolledBack")
        self.assertEqual(self.path.read_bytes(), SOURCE.encode())

    def test_completed_journal_cannot_be_relabelled_as_pending_recovery(self):
        receipt = self.prepare()
        approved = self.approve(receipt)
        committed = self.manager.commit(receipt["id"], approved["approvalId"])
        self.assertEqual(committed["status"], "Committed")
        after = self.path.read_bytes()
        path = self.store / receipt["id"] / "record.json"
        record = json.loads(path.read_text())
        record["status"] = "Committing"
        record["_journal"]["phase"] = "replaced"
        path.write_text(json.dumps(record))
        with self.assertRaisesRegex(TransactionError, "recovery binding changed"):
            TransactionManager(self.store)
        self.assertEqual(self.path.read_bytes(), after)

    def test_consumed_approval_cannot_be_reactivated_after_external_revert(self):
        receipt = self.prepare()
        approved = self.approve(receipt)
        self.manager.commit(receipt["id"], approved["approvalId"])
        # Even if an editor restores the exact original bytes, a used human
        # approval is not an instruction to perform a second source commit.
        self.path.write_bytes(SOURCE.encode())
        path = self.store / receipt["id"] / "record.json"
        record = json.loads(path.read_text())
        record["status"] = "Approved"
        record["_approval"]["consumed"] = False
        path.write_text(json.dumps(record))
        with self.assertRaises(TransactionError):
            self.manager.commit(receipt["id"], approved["approvalId"])
        self.assertEqual(self.path.read_bytes(), SOURCE.encode())

    def test_shared_authored_literal_affects_all_custom_instances_across_files(self):
        (self.root / "block.py").write_text('''from torch import nn
class Block(nn.Module):
    def __init__(self):
        self.丢弃 = nn.Dropout(p=0.1)
    def forward(self, x):
        return self.丢弃(x)
''')
        self.path.write_text('''from torch import nn
from block import Block
class Model(nn.Module):
    def __init__(self):
        self.one = Block()
        self.two = Block()
    def forward(self, x):
        return self.two(self.one(x))
''')
        before = analyze_project(self.root, "model:Model")
        selected = next(node for node in before["nodes"] if node["kind"] == "Dropout")
        original_model = self.path.read_bytes()
        original_block = (self.root / "block.py").read_bytes()
        receipt = self.manager.prepare(self.root, "model:Model", selected["id"], "p", 0.2, before["sourceDigest"])
        self.assertEqual(len(receipt["affectedNodeIds"]), 2)
        self.assertEqual(receipt["sourceChanges"][0]["path"], "block.py")
        approved = self.approve(receipt)
        self.assertEqual(self.manager.commit(receipt["id"], approved["approvalId"])["status"], "Committed")
        self.assertEqual(self.path.read_bytes(), original_model)
        self.assertEqual((self.root / "block.py").read_bytes(), original_block.replace(b"p=0.1", b"p=0.2"))

    def test_user_model_code_is_never_imported_or_executed(self):
        sentinel = self.root / "executed"
        source = f'open({str(sentinel)!r}, "w").write("execution")\n' + SOURCE
        self.path.write_text(source)
        receipt = self.prepare()
        approved = self.approve(receipt)
        self.assertEqual(self.manager.commit(receipt["id"], approved["approvalId"])["status"], "Committed")
        self.assertFalse(sentinel.exists())


if __name__ == "__main__":
    unittest.main()
