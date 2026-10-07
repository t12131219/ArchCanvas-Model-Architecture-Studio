"""Independent original-source and edge expectations for registered RebindInput."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from archcanvas_python import analyze_project
from archcanvas_transactions import TransactionError, TransactionManager
from archcanvas_transactions.rebind import rewrite_name


SOURCE = '''from torch import nn
class Model(nn.Module):
    def __init__(self):
        super().__init__()
        self.first = nn.Identity()
        self.branch = nn.ReLU()
        self.finish = nn.Dropout(0.1)
    def forward(self, features):
        initial = self.first(features)
        alternate = self.branch(initial)
        result = self.finish(initial)  # initial stays in this comment
        return result
'''


class RebindTransactionTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="archcanvas-rebind-", dir="/tmp")
        self.root = Path(self.temporary.name) / "project"
        self.root.mkdir()
        self.path = self.root / "model.py"
        self.path.write_bytes(SOURCE.encode())
        self.store = Path(self.temporary.name) / "transactions"
        self.manager = TransactionManager(self.store)

    def tearDown(self):
        self.temporary.cleanup()

    def request(self, producer="branch", target="finish"):
        architecture = analyze_project(self.root, "model:Model")
        selected = next(node for node in architecture["nodes"] if node.get("instanceId", "").endswith("." + target))
        if producer == "input":
            prior = next(node for node in architecture["nodes"] if node["kind"] == "Input")
        else:
            prior = next(node for node in architecture["nodes"] if node.get("instanceId", "").endswith("." + producer))
        port = next(port for port in selected["ports"] if port["direction"] == "in")
        output = next(port for port in prior["ports"] if port["direction"] == "out")
        return {"root": self.root, "entry": "model:Model", "nodeId": selected["id"], "portId": port["id"], "producerNodeId": prior["id"], "producerPortId": output["id"], "baseSourceDigest": architecture["sourceDigest"]}, architecture

    def prepare(self, producer="branch", target="finish"):
        request, before = self.request(producer, target)
        return self.manager.prepare_rebind(**request), before

    def approve(self, receipt):
        self.assertEqual(receipt["status"], "ReviewReady", receipt["blockers"])
        return self.manager.approve(receipt["id"], receipt["reviewDigest"])

    def test_single_name_and_exact_independent_edge_change(self):
        receipt, before = self.prepare()
        self.assertEqual(self.path.read_bytes(), SOURCE.encode())
        self.assertEqual(receipt["intent"]["before"]["variable"], "initial")
        self.assertEqual(receipt["intent"]["after"]["variable"], "alternate")
        target = receipt["intent"]["nodeId"]
        first = next(node for node in before["nodes"] if node.get("instanceId", "").endswith(".first"))
        branch = next(node for node in before["nodes"] if node.get("instanceId", "").endswith(".branch"))
        before_edge = next(edge for edge in before["edges"] if edge["target"]["nodeId"] == target)
        after_edge = next(edge for edge in receipt["afterArchitecture"]["edges"] if edge["target"]["nodeId"] == target)
        self.assertEqual(before_edge["source"]["nodeId"], first["id"])
        self.assertEqual(after_edge, {**before_edge, "source": {"nodeId": branch["id"], "portId": f"{branch['id']}:out:output"}, "tensorId": f"tensor:{branch['id']}:output"})
        self.assertEqual([edge for edge in before["edges"] if edge is not before_edge], [edge for edge in receipt["afterArchitecture"]["edges"] if edge is not after_edge])
        for identity in ("G0", "G4", "G5"):
            self.assertEqual(next(gate for gate in receipt["gates"] if gate["id"] == identity)["status"], "passed")
        self.assertEqual(next(gate for gate in receipt["gates"] if gate["id"] == "G6")["status"], "not_run")
        approved = self.approve(receipt)
        result = self.manager.commit(receipt["id"], approved["approvalId"])
        self.assertEqual(result["status"], "Committed")
        self.assertEqual(self.path.read_bytes(), SOURCE.replace("self.finish(initial)", "self.finish(alternate)").encode())

    def test_input_candidate_and_final_direct_return(self):
        self.path.write_text(SOURCE.replace("        result = self.finish(initial)  # initial stays in this comment\n        return result", "        return self.finish(initial)  # still direct"))
        receipt, before = self.prepare("input")
        self.assertEqual(receipt["status"], "ReviewReady", receipt["blockers"])
        self.assertEqual(receipt["intent"]["after"]["variable"], "features")
        approved = self.approve(receipt)
        self.assertEqual(self.manager.commit(receipt["id"], approved["approvalId"])["status"], "Committed")
        self.assertIn("return self.finish(features)", self.path.read_text())

    def test_noop_and_non_dominating_producer_blocked(self):
        same, _ = self.prepare("first")
        self.assertEqual(same["status"], "Failed")
        self.assertIn("already bound", same["blockers"][0])
        late, _ = self.prepare("finish", "branch")
        self.assertEqual(late["status"], "Failed")
        self.assertIn("candidate", late["blockers"][0])
        self.assertEqual(self.path.read_bytes(), SOURCE.encode())

    def test_wrong_lowering_cannot_supply_expected_graph(self):
        def wrong(raw, origin, before_name, after_name):
            return rewrite_name(raw, origin, before_name, "features")
        with patch("archcanvas_transactions.service.rewrite_name", wrong):
            receipt, before = self.prepare()
        self.assertEqual(receipt["status"], "Failed")
        self.assertIn("ExpectedDelta", receipt["blockers"][0])
        self.assertEqual(self.path.read_bytes(), SOURCE.encode())

    def test_staging_rebound_to_other_valid_candidate_is_not_approved(self):
        receipt, before = self.prepare()
        approved = self.approve(receipt)
        stage = self.store / receipt["id"] / "staged/model.py"
        stage.write_bytes(stage.read_bytes().replace(b"self.finish(alternate)", b"self.finish(features)"))
        result = self.manager.commit(receipt["id"], approved["approvalId"])
        self.assertEqual(result["status"], "Stale")
        self.assertEqual(self.path.read_bytes(), SOURCE.encode())

    def test_exact_rebind_approval_cannot_authorize_parameter_transaction(self):
        receipt, before = self.prepare()
        approved = self.approve(receipt)
        selected = next(node for node in before["nodes"] if node["kind"] == "Dropout")
        parameter = self.manager.prepare(self.root, "model:Model", selected["id"], "p", 0.2, before["sourceDigest"])
        parameter_approved = self.manager.approve(parameter["id"], parameter["reviewDigest"])
        with self.assertRaises(TransactionError):
            self.manager.commit(parameter["id"], approved["approvalId"])
        self.assertEqual(self.path.read_bytes(), SOURCE.encode())

    def test_rebind_preserves_utf8_bom_crlf_unicode_names_and_permissions(self):
        raw = b"\xef\xbb\xbf" + SOURCE.replace("initial", "原始").replace("alternate", "备用张量").replace("\n", "\r\n").rstrip("\r\n").encode()
        self.path.write_bytes(raw)
        self.path.chmod(0o640)
        receipt, before = self.prepare()
        approved = self.approve(receipt)
        self.assertEqual(self.manager.commit(receipt["id"], approved["approvalId"])["status"], "Committed")
        self.assertEqual(self.path.read_bytes(), raw.replace("self.finish(原始)".encode(), "self.finish(备用张量)".encode()))
        self.assertEqual(self.path.stat().st_mode & 0o777, 0o640)

    def test_rebind_write_fault_uses_existing_guarded_recovery(self):
        receipt, before = self.prepare()
        approved = self.approve(receipt)
        with patch.object(self.manager, "_verify_committed", side_effect=OSError("rebind post-write verification fault")):
            result = self.manager.commit(receipt["id"], approved["approvalId"])
        self.assertEqual(result["status"], "RolledBack")
        self.assertEqual(self.path.read_bytes(), SOURCE.encode())

    def test_producer_contract_and_intent_tamper_invalidates_approval(self):
        receipt, before = self.prepare()
        approved = self.approve(receipt)
        path = self.store / receipt["id"] / "record.json"
        record = json.loads(path.read_text())
        record["intent"]["contract"]["baseTensorId"] = "tensor:different-input"
        path.write_text(json.dumps(record))
        result = self.manager.commit(receipt["id"], approved["approvalId"])
        self.assertEqual(result["status"], "Stale")
        self.assertEqual(self.path.read_bytes(), SOURCE.encode())


if __name__ == "__main__":
    unittest.main()
