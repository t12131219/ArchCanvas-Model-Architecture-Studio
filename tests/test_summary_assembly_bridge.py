"""Actual local recognizer and formal HTTP boundary for declared assemblies."""
import copy
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from archcanvas_preview import AdapterError
from archcanvas_preview.authoring_bridge import compile_source_module, _COMPILATION
from archcanvas_preview.assembly_bridge import certify_declared_assembly, SCOPE
import test_preview_backend as preview_http

SOURCE = '''from torch import nn
class Residual(nn.Module):
 def __init__(self):
  super().__init__()
  self.linear=nn.Linear(4,4)
 def forward(self,x):
  return x+self.linear(x)
'''


def assembly():
    ir = compile_source_module(SOURCE, "Residual")["ir"]
    ir.update(authoring={"schema": "semantic-authoring/1", "edited": True, "modules": {}},
              coverage={"status": "not-verified", "scope": "user-authored-assembly", "complete": False},
              runtime={"status": "not-requested", "model_executed": False})
    return ir


class SummaryAssemblyTests(unittest.TestCase):
    def test_actual_recognition_recomputes_local_contracts_without_changing_facts_or_executing(self):
        ir = assembly()
        with tempfile.TemporaryDirectory() as directory:
            marker = Path(directory) / "executed"
            ir["authoring"]["modules"] = {"declaration": {"source": f"open({str(marker)!r},'w').write('executed')"}}
            ir["semantic_contracts"] = [{"id": "forged-old-certificate"}]
            before = copy.deepcopy(ir)
            result = certify_declared_assembly(ir)
            self.assertEqual(ir, before)
            self.assertFalse(marker.exists())
        self.assertEqual(result["schema"], "archcanvas-summary-local-assembly/1")
        output = json.loads(result["irText"])
        self.assertEqual(output["nodes"], before["nodes"])
        self.assertEqual(output["edges"], before["edges"])
        self.assertEqual(output["coverage"], before["coverage"])
        self.assertFalse(output["runtime"]["model_executed"])
        self.assertTrue(output["authoring"]["local_contracts_recomputed"])
        self.assertGreater(result["analysis"]["contracts"], 0)
        self.assertFalse(result["analysis"]["sourceTransactionBinding"])
        for contract in output["semantic_contracts"]:
            self.assertEqual(contract["scope"], SCOPE)
            self.assertIn("assembled-program execution", contract["not_asserted"])
            self.assertIn("shape compatibility", contract["not_asserted"])
            self.assertNotEqual(contract["id"], "forged-old-certificate")

    def test_invalid_graphs_and_execution_claims_reject(self):
        ir = assembly()
        values = [None, {}, {**ir, "authoring": []}, {**ir, "runtime": []}, {**ir, "runtime": {"model_executed": True}}, {**ir, "invalid": float("nan")}, {**ir, "nodes": ir["nodes"] * 481}]
        cyclic = copy.deepcopy(ir);cyclic["nodes"][0]["parent"] = cyclic["nodes"][0]["id"];values.append(cyclic)
        broken = copy.deepcopy(ir);broken["edges"][0]["target"] = "missing";values.append(broken)
        for value in values:
            with self.subTest(value=str(value)[:50]), self.assertRaises(AdapterError):
                certify_declared_assembly(value)

    def test_analysis_slot_and_timeout_leave_the_service_usable(self):
        ir = assembly();_COMPILATION.acquire()
        try:
            with self.assertRaisesRegex(AdapterError, "另一个"):
                certify_declared_assembly(ir)
        finally:
            _COMPILATION.release()
        with patch("archcanvas_preview.assembly_bridge.subprocess.run", side_effect=subprocess.TimeoutExpired("worker", 15)):
            with self.assertRaisesRegex(AdapterError, "15 秒"):
                certify_declared_assembly(ir)
        self.assertEqual(certify_declared_assembly(ir)["schema"], "archcanvas-summary-local-assembly/1")


class SummaryAssemblyHTTPTests(unittest.TestCase):
    setUp = preview_http.PreviewHTTPTests.setUp
    tearDown = preview_http.PreviewHTTPTests.tearDown
    request = preview_http.PreviewHTTPTests.request

    def test_actual_session_origin_and_declared_only_endpoint(self):
        path = "/api/preview/authoring/certify";payload = {"ir": assembly()}
        self.assertEqual(self.request(path, payload, token=False)[0], 403)
        self.assertEqual(self.request(path, payload, origin="http://untrusted.invalid")[0], 403)
        self.assertEqual(self.request(path, {**payload, "root": "/etc"})[0], 400)
        status, value = self.request(path, payload, origin=self.url)
        self.assertEqual(status, 200, value)
        self.assertFalse(value["analysis"]["modelExecuted"])
        self.assertEqual(list((self.root / "managed").glob("projects/*")), [])


if __name__ == "__main__":
    unittest.main()
