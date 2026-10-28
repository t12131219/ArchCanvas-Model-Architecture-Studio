"""Independent static-module holdouts, including executable-looking source."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from archcanvas_preview import AdapterError, capabilities
from archcanvas_preview.authoring_bridge import compile_source_module, _COMPILATION
from archcanvas_summary_semantic.schema import validate_ir

SOURCE = '''from torch import nn
class Block(nn.Module):
 def __init__(self,width=4):
  super().__init__()
  self.linear=nn.Linear(width,width)
 def forward(self,x,skip):
  return self.linear(x)+skip
'''


class SummarySourceModuleTests(unittest.TestCase):
    def test_actual_module_keeps_source_constructor_slots_and_stable_portable_evidence(self):
        before = compile_source_module(SOURCE, "Block", {"width": 7})
        again = compile_source_module(SOURCE, "Block", {"width": 7})
        self.assertEqual(before, again)
        self.assertEqual(before["source"], SOURCE)
        self.assertEqual(before["constructor"], {"width": 7})
        self.assertTrue(validate_ir(before["ir"])["ok"])
        self.assertFalse(before["analysis"]["executed"])
        self.assertFalse(before["analysis"]["boundary"]["sourceTransactionBinding"])
        self.assertNotIn("archcanvas-authoring-", json.dumps(before))
        self.assertTrue(all(s["path"].startswith("authoring://module/") for s in before["ir"]["sources"]))
        self.assertTrue(any(n.get("constructor", {}).get("args") == [7, 7] for n in before["ir"]["nodes"]))
        self.assertEqual({n["label"] for n in before["ir"]["nodes"] if n.get("role") == "input"}, {"x", "skip"})

    def test_top_level_constructor_forward_and_imports_are_not_executed(self):
        with tempfile.TemporaryDirectory() as directory:
            marker = Path(directory) / "executed"
            statement = f"open({str(marker)!r},'w').write('executed')"
            source = statement + "\n" + SOURCE.replace("super().__init__()", statement).replace("return self.linear(x)+skip", statement + "\n  return x+skip")
            result = compile_source_module(source, "Block", {"width": 9})
            self.assertFalse(marker.exists())
            self.assertFalse(result["analysis"]["executed"])

    def test_bad_source_entry_config_and_resource_requests_reject(self):
        for source, entry, config in [("", "Block", {}), ("x" * 120001, "Block", {}), (SOURCE, "missing", {}), (SOURCE, "x:Block", {}), (SOURCE, "Block", []), (SOURCE, "Block", {"x": float("nan")}), (SOURCE, "Block", {"x": "x" * 16001})]:
            with self.subTest(entry=entry, config=str(config)[:30]), self.assertRaises(AdapterError):
                compile_source_module(source, entry, config)
        large = "from torch import nn\nclass Large(nn.Module):\n def forward(self,x):\n" + "  x=x+x\n" * 500 + "  return x\n"
        with self.assertRaisesRegex(AdapterError, "预算"):
            compile_source_module(large, "Large")

    def test_concurrent_compilation_and_timed_out_worker_release_the_single_slot(self):
        _COMPILATION.acquire()
        try:
            with self.assertRaisesRegex(AdapterError, "另一个"):
                compile_source_module(SOURCE, "Block")
        finally:
            _COMPILATION.release()
        import subprocess
        with patch("archcanvas_preview.authoring_bridge.subprocess.run", side_effect=subprocess.TimeoutExpired("worker", 15)):
            with self.assertRaisesRegex(AdapterError, "15 秒"):
                compile_source_module(SOURCE, "Block")
        self.assertTrue(_COMPILATION.acquire(blocking=False))
        _COMPILATION.release()

    def test_actual_capabilities_describe_static_module_boundary(self):
        capability = capabilities()["nativeAuthoring"]
        self.assertEqual(capability["module"], "/api/preview/authoring/module")
        self.assertFalse(capability["modelExecuted"])
        self.assertFalse(capability["sourceTransactionBinding"])


if __name__ == "__main__":
    unittest.main()
