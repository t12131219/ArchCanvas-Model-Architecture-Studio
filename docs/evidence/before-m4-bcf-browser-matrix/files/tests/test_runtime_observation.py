"""Handwritten state/identity oracles for the isolated CPU observer."""

from pathlib import Path
import tempfile
import unittest

from archcanvas_runtime import RuntimeProfileError, normalize_input_spec, runtime_capabilities, verify_structural


ROOT = Path(__file__).resolve().parents[1]
CONFIG = {"interpreter": str(ROOT / ".venv-runtime/bin/python"), "dependencyLock": str(ROOT / "requirements-runtime.lock")}
SPEC = {"schemaVersion": 1, "inputs": {"x": {"shape": [2, 3], "dtype": "float32", "fill": "ones"}}, "modes": ["eval", "train"], "seed": 73}


class RuntimeProfileValidationTests(unittest.TestCase):
    def test_execution_requires_declared_modes_and_bounded_named_inputs(self):
        for bad in ({**SPEC, "modes": []}, {**SPEC, "modes": ["train", "train"]}, {**SPEC, "constructor": {"hidden": 3}}, {**SPEC, "inputs": {"x": {"shape": [2000, 2000], "dtype": "float32"}}}):
            with self.subTest(spec=bad), self.assertRaises(RuntimeProfileError):
                normalize_input_spec(bad)

    def test_missing_explicit_environment_disables_execution(self):
        self.assertFalse(runtime_capabilities()["available"])
        result = verify_structural(ROOT / "fixtures/rebind", "model:RebindDemo", {"schemaVersion": 1, "inputs": {"features": {"shape": [2, 3], "dtype": "float32"}}, "modes": ["eval"]})
        self.assertEqual(result["status"], "unavailable")
        self.assertFalse(result["runtimeVerified"])


class RuntimeStateObservationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        result = runtime_capabilities(CONFIG)
        if not result["available"]:
            raise unittest.SkipTest(result.get("unavailableReason", "Actual Linux sandbox unavailable"))

    def run_source(self, source, config=None):
        with tempfile.TemporaryDirectory(prefix="archcanvas-runtime-state-") as directory:
            root = Path(directory)
            (root / "model.py").write_text(source)
            return verify_structural(root, "model:Model", SPEC, config or CONFIG)

    def test_capabilities_probe_real_infrastructure_and_dependency_binding(self):
        result = runtime_capabilities(CONFIG)
        self.assertTrue(result["available"], result)
        self.assertTrue(result["structuralVerified"])
        self.assertTrue(all(result["isolation"]["checks"].values()))
        self.assertEqual(result["environment"]["frameworkVersion"], "2.5.1+cpu")
        self.assertTrue(Path(result["environment"]["frameworkOrigin"]).is_relative_to(ROOT / ".venv-runtime"))
        self.assertGreater(result["environment"]["virtualEnvironmentFileCount"], 1000)
        self.assertTrue(result["environmentDigest"])
        self.assertTrue(result["isolation"]["checks"]["baseEnvironmentUnexposed"])
        self.assertTrue(result["environment"]["stdlibContentDigest"])
        self.assertTrue(result["environment"]["sharedLibraryContentDigest"])

    def test_worker_cannot_read_base_conda_metadata_or_base_site_packages(self):
        hidden = str(Path("/home/fzg/anaconda3/conda-meta/history"))
        self.assertTrue(Path(hidden).is_file())
        source = '''from torch import nn
import os
class Model(nn.Module):
    def forward(self, x):
        if os.path.exists(%r) or os.path.exists("/home/fzg/anaconda3/lib/python3.11/site-packages"):
            raise RuntimeError("Base environment outside the runtime mount contract is exposed")
        return x
''' % hidden
        result = self.run_source(source)
        self.assertEqual(result["status"], "passed", result.get("reason"))

    def test_tied_weights_buffers_and_train_state_are_observed_separately(self):
        result = self.run_source('''from torch import nn
import torch
class Model(nn.Module):
    def __init__(self):
        super().__init__()
        self.first = nn.Linear(3, 3)
        self.second = nn.Linear(3, 3)
        self.second.weight = self.first.weight
        self.register_buffer("scale", torch.ones(3))
        self.register_buffer("ticks", torch.zeros((), dtype=torch.int64))
    def forward(self, x):
        if self.training:
            self.ticks.add_(1)
        return self.second(self.first(x)) * self.scale
''')
        self.assertEqual(result["status"], "passed", result.get("reason"))
        for mode in result["observation"]["modes"]:
            state = mode["state"]
            facts = {entry["key"]: (entry["role"], entry["shape"], entry["dtype"]) for entry in state["before"]["entries"]}
            self.assertEqual(facts, {"first.weight": ("parameter", [3, 3], "float32"), "second.weight": ("parameter", [3, 3], "float32"), "first.bias": ("parameter", [3], "float32"), "second.bias": ("parameter", [3], "float32"), "scale": ("buffer", [3], "float32"), "ticks": ("buffer", [], "int64")})
            self.assertEqual(state["before"]["sharedGroups"], [["first.weight", "second.weight"]])
            self.assertEqual(state["mutatedKeys"], ["ticks"] if mode["mode"] == "train" else [])
            self.assertTrue(mode["replay"]["stateEqual"])
            self.assertTrue(mode["replay"]["gradientsEqual"])
        self.assertEqual(result["stateCompatibility"]["checkpoint"], "not_provided")

    def test_shared_module_has_one_instance_and_distinct_call_identities(self):
        result = self.run_source('''from torch import nn
class Model(nn.Module):
    def __init__(self):
        super().__init__()
        self.left = nn.Identity()
        self.right = self.left
    def forward(self, x):
        a = self.left(x)
        return self.right(a)
''')
        self.assertEqual(result["status"], "passed", result.get("reason"))
        for mode in result["observation"]["modes"]:
            calls = [call for call in mode["calls"] if call["modulePath"]]
            self.assertEqual([call["instanceId"] for call in calls], ["module:left", "module:left"])
            self.assertEqual([call["callId"] for call in calls], ["call:left:0", "call:left:1"])
            history = calls[1]["inputs"]["input"]["producerHistory"]
            self.assertEqual(history[0], {"kind": "input", "name": "x"})
            self.assertEqual(history[-1]["callId"], "call:left:0")

    def test_wrong_framework_pin_disables_profile(self):
        with tempfile.TemporaryDirectory(prefix="archcanvas-runtime-lock-") as directory:
            lock = Path(directory) / "requirements.lock"
            lock.write_text((ROOT / "requirements-runtime.lock").read_text().replace("torch==2.5.1+cpu", "torch==0.0.0+cpu"))
            result = self.run_source('''from torch import nn
class Model(nn.Module):
    def forward(self, x):
        return x
''', {**CONFIG, "dependencyLock": str(lock)})
            self.assertEqual(result["status"], "unavailable")
            self.assertIn("expected 0.0.0+cpu", result["reason"])

    def test_cpu_limit_terminates_an_actual_model_loop(self):
        result = self.run_source('''from torch import nn
import sys
class Model(nn.Module):
    def forward(self, x):
        print("model-loop-entered", file=sys.stderr, flush=True)
        while True:
            pass
''', {**CONFIG, "cpuSeconds": 2, "timeoutSeconds": 10})
        self.assertEqual(result["status"], "failed", result.get("reason"))
        self.assertIn("model-loop-entered", result["reason"])
        self.assertIn("worker exit", result["reason"])


if __name__ == "__main__":
    unittest.main()
