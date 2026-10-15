"""Independent text-only discovery and durable adapter API/CLI integration."""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import ProxyHandler, Request, build_opener

from archcanvas_cli.server import ArchCanvasServer

ROOT = Path(__file__).resolve().parents[1]
FILES = {"unknown.py": """from torch import nn
class Hidden(nn.Module):
    def __init__(self):
        super().__init__()
        self.map = nn.Linear(4, 4)
    def forward(self, x):
        if x.sum() > 0:
            return self.map(x)
        return x
class Wrapper(nn.Module):
    def __init__(self):
        super().__init__()
        self.part = Hidden()
    def __call__(self, x):
        return self.part(x)
"""}

# This comprehension is deliberately outside the built-in inspection tree's
# selected operands. An Agent-authored rule must add source facts, not merely
# rename the opaque card already produced by that parser.
RULE_FILES = {"foreign.py": """from torch import nn
class CopperSprig(nn.Module):
    def __init__(self):
        super().__init__()
        self.parts = nn.ModuleList([nn.Identity()])
    def forward(self, x):
        values = [part(x) for part in self.parts]
        return values
"""}
RULE = {
    "schema": "archcanvas-source-rule/1", "name": "Comprehension source operands",
    "match": {"type": "ListComp", "fields": {
        "elt": {"type": "Call", "fields": {"args": [{"type": "Name"}]}},
        "generators": [{"type": "comprehension", "fields": {"is_async": 0}}],
    }},
    "nodes": [
        {"key": "region", "at": [], "parent": None, "kind": "SourceLoop"},
        {"key": "iterator", "at": ["generators", 0, "iter"], "parent": "region", "kind": "SourceExpression"},
        {"key": "input", "at": ["elt", "args", 0], "parent": "region", "kind": "SourceExpression"},
        {"key": "operation", "at": ["elt"], "parent": "region", "kind": "SourceCall"},
    ],
    "relations": [
        {"source": "iterator", "target": "operation", "proof": "comprehension-iteration"},
        {"source": "input", "target": "operation", "proof": "expression-input"},
    ],
}


class SourceAdaptationHTTPTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="archcanvas-adapter-http-")
        self.root = Path(self.temporary.name)
        try:
            self.server = ArchCanvasServer(("127.0.0.1", 0), data_dir=self.root)
        except PermissionError:
            self.temporary.cleanup()
            self.skipTest("Loopback unavailable in this sandbox; requires the permitted local HTTP check.")
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"
        self.client = build_opener(ProxyHandler({}))
        self.token = self.request("/api/session")[1]["token"]

    def tearDown(self):
        self.server.shutdown(); self.server.server_close(); self.thread.join()
        self.temporary.cleanup()

    def request(self, path, payload=None, token=None):
        request = Request(self.url + path, data=json.dumps(payload).encode() if payload is not None else None,
                          headers={"Content-Type": "application/json", **({"X-ArchCanvas-Session": token} if token else {})})
        try:
            with self.client.open(request, timeout=30) as response:
                return response.status, json.loads(response.read())
        except HTTPError as error:
            return error.code, json.loads(error.read())

    def test_discovery_and_both_entry_methods_have_no_preset_dependency(self):
        status, result = self.request("/api/models/discover", {"files": FILES})
        self.assertEqual(status, 200, result)
        self.assertEqual({m["entry"] for m in result["models"]}, {"unknown:Hidden", "unknown:Wrapper"})
        wrapper = next(m for m in result["models"] if m["name"] == "Wrapper")
        self.assertEqual(wrapper["entryMethod"], "__call__")
        self.assertTrue(any(r["owner"] == "unknown:Wrapper" and r["target"] == "unknown:Hidden" for r in result["relationships"]))
        status, preview = self.request("/api/preview/analyze", {"files": FILES, "entry": "unknown:Wrapper"})
        self.assertEqual(status, 200, preview)
        self.assertTrue(any(n.get("sourceStructure") for n in preview["ir"]["nodes"]))
        status, architecture = self.request("/api/preview/edit-source", {"files": FILES, "entry": "unknown:Wrapper"}, self.token)
        self.assertEqual(status, 200, architecture)
        self.assertEqual(architecture["entry"], preview["entry"])
        self.assertEqual({s["path"]: s["content"] for s in architecture["sources"]}, FILES)

    def test_persisted_definition_is_revalidated_and_does_not_create_source_projects(self):
        payload = {"files": FILES, "entry": "unknown:Hidden"}
        self.assertEqual(self.request("/api/adapters/scaffold", payload)[0], 403)
        status, definition = self.request("/api/adapters/scaffold", payload, self.token)
        self.assertEqual(status, 200, definition)
        self.assertIsNone(definition["generationContract"])
        label_target = definition["children"][0]["id"]
        definition["presentation"]["labels"][label_target] = "Reviewed source branch"
        status, registered = self.request("/api/adapters/register", {"files": FILES, "definition": definition}, self.token)
        self.assertEqual(status, 201, registered)
        self.assertTrue(list((self.root / "adapters").glob("*.json")))
        status, preview = self.request("/api/preview/analyze", {"files": FILES, "entry": "unknown:Hidden"})
        self.assertEqual(status, 200, preview)
        self.assertTrue(any(n["label"] == "Reviewed source branch" for n in preview["ir"]["nodes"]))
        self.assertEqual(list((self.root / "projects").glob("*/project.json")), [])
        forged = copy.deepcopy(definition); forged["generationContract"] = {"execute": "arbitrary plugin"}
        self.assertEqual(self.request("/api/adapters/register", {"files": FILES, "definition": forged}, self.token)[0], 400)
        changed = {key: text + "\n# a new source revision\n" for key, text in FILES.items()}
        self.assertEqual(self.request("/api/adapters/validate", {"files": changed, "definition": definition}, self.token)[0], 400)

    def test_http_rejects_filesystem_roots_and_wrong_adapter_fields(self):
        for path, payload in [("/api/models/discover", {"root": "/etc"}),
                              ("/api/adapters/scaffold", {"files": FILES, "entry": "unknown:Hidden", "root": "/etc"}),
                              ("/api/adapters/list", {"files": {"../escape.py": FILES["unknown.py"]}})]:
            self.assertEqual(self.request(path, payload, self.token)[0], 400)

    def test_agent_rule_adds_internal_structure_and_rebinds_after_source_renaming(self):
        payload = {"files": RULE_FILES, "entry": "foreign:CopperSprig"}
        status, original = self.request("/api/preview/analyze", payload)
        self.assertEqual(status, 200, original)
        self.assertFalse(any(node.get("expression") == "self.parts" for node in original["ir"]["nodes"]))

        status, template = self.request("/api/adapters/rule-validate", {"rule": RULE}, self.token)
        self.assertEqual(status, 200, template)
        self.assertRegex(template["id"], r"^rule-[a-f0-9]{24}$")
        # HTTP accepts both one rule object and a rule array.
        status, definition = self.request("/api/adapters/scaffold", {**payload, "rules": RULE}, self.token)
        self.assertEqual(status, 200, definition)
        self.assertEqual(definition["schema"], "archcanvas-source-adapter/2")
        self.assertEqual(len(definition["applications"]), 1)
        self.assertIsNone(definition["generationContract"])
        status, verified = self.request("/api/adapters/validate", {"files": RULE_FILES, "definition": definition}, self.token)
        self.assertEqual(status, 200, verified)
        self.assertEqual(verified, definition)
        status, registered = self.request("/api/adapters/register", {"files": RULE_FILES, "definition": definition}, self.token)
        self.assertEqual(status, 201, registered)
        status, rules = self.request("/api/adapters/rules", {}, self.token)
        self.assertEqual(status, 200, rules)
        self.assertEqual(len(rules), 1)
        self.assertEqual(rules[0]["id"], template["id"])
        self.assertEqual(rules[0]["status"], "valid")
        self.assertEqual(rules[0]["definition"], template)
        self.assertTrue(Path(rules[0]["path"]).is_file())

        status, adapted = self.request("/api/preview/analyze", payload)
        self.assertEqual(status, 200, adapted)
        original_nodes = {node["id"]: node for node in original["ir"]["nodes"]}
        original_edges = {edge["id"]: edge for edge in original["ir"]["edges"]}
        added = [node for node in adapted["ir"]["nodes"] if node["id"] not in original_nodes]
        self.assertEqual({node["expression"] for node in added}, {"self.parts", "x"})
        self.assertTrue(all(node == original_nodes[node["id"]] for node in adapted["ir"]["nodes"] if node["id"] in original_nodes))
        self.assertTrue(all(edge == original_edges[edge["id"]] for edge in adapted["ir"]["edges"] if edge["id"] in original_edges))
        self.assertTrue(set(original_nodes) <= {node["id"] for node in adapted["ir"]["nodes"]})
        self.assertTrue(set(original_edges) <= {edge["id"] for edge in adapted["ir"]["edges"]})
        call = next(node for node in original["ir"]["nodes"] if node.get("expression") == "part(x)")
        proof_edges = [edge for edge in adapted["ir"]["edges"] if edge.get("sourceRuleId")]
        self.assertEqual(len(proof_edges), 2)
        self.assertTrue(all(edge["target"] == call["id"] and edge["syntaxOnly"] and edge["role"] == "source_dependency" for edge in proof_edges))
        self.assertEqual(adapted["sourceSha256"], original["sourceSha256"])
        self.assertFalse(adapted["ir"]["modelExecuted"])

        renamed = {"renamed.py": RULE_FILES["foreign.py"].replace("CopperSprig", "SilverBranch")
                   .replace("parts", "stages").replace("part(x)", "stage(inputs)")
                   .replace("for part in", "for stage in").replace("(self, x)", "(self, inputs)")}
        status, stale = self.request("/api/adapters/validate", {"files": renamed, "definition": definition}, self.token)
        self.assertEqual(status, 400, stale)
        self.assertIn("stale", stale["error"].lower())
        renamed_payload = {"files": renamed, "entry": "renamed:SilverBranch"}
        status, rebound = self.request("/api/adapters/scaffold", {**renamed_payload, "useRegistryRules": True}, self.token)
        self.assertEqual(status, 200, rebound)
        self.assertEqual(rebound["schema"], "archcanvas-source-adapter/2")
        self.assertNotEqual(rebound["id"], definition["id"])
        self.assertEqual(len(rebound["applications"]), 1)
        status, preview = self.request("/api/preview/analyze", renamed_payload)
        self.assertEqual(status, 200, preview)
        self.assertEqual(len(preview["sourceRuleApplications"]), 1)
        self.assertTrue(any(node.get("expression") == "self.stages" for node in preview["ir"]["nodes"]))
        self.assertTrue(any(node.get("expression") == "inputs" and node.get("sourceRuleId") for node in preview["ir"]["nodes"]))
        self.assertEqual(preview["availableSourceRules"], [template["id"]])
        self.assertEqual(list((self.root / "projects").glob("*/project.json")), [])

    def test_bad_rule_or_false_operand_proof_cannot_replace_existing_preview(self):
        payload = {"files": RULE_FILES, "entry": "foreign:CopperSprig"}
        changed = {"foreign.py": RULE_FILES["foreign.py"].replace("part(x)", "fixed(x)")}
        status, changed_original = self.request("/api/preview/analyze", {**payload, "files": changed})
        self.assertEqual(status, 200, changed_original)
        independent = copy.deepcopy(RULE)
        independent["name"] = "Direct call operand only"
        independent["relations"] = independent["relations"][1:]
        receipts = []
        for rule in (RULE, independent):
            status, definition = self.request("/api/adapters/scaffold", {**payload, "rules": [rule]}, self.token)
            self.assertEqual(status, 200, definition)
            status, receipt = self.request("/api/adapters/register", {"files": RULE_FILES, "definition": definition}, self.token)
            self.assertEqual(status, 201, receipt)
            receipts.append(receipt)
        status, good = self.request("/api/preview/analyze", payload)
        self.assertEqual(status, 200, good)
        registry_before = {str(path.relative_to(self.root)): path.read_bytes() for path in (self.root / "adapters").rglob("*.json")}

        hook = {**copy.deepcopy(RULE), "python": "__import__('os').remove('model.py')"}
        status, rejected = self.request("/api/adapters/rule-validate", {"rule": hook}, self.token)
        self.assertEqual(status, 400, rejected)
        false_proof = copy.deepcopy(RULE)
        false_proof["relations"][0]["proof"] = "expression-input"
        status, rejected = self.request("/api/adapters/scaffold", {**payload, "rules": [false_proof]}, self.token)
        self.assertEqual(status, 400, rejected)
        self.assertIn("immediate value operand", rejected["error"])
        forged = copy.deepcopy(definition)
        forged["children"][0]["source"]["expression"] = "a fact absent from this Python source"
        status, rejected = self.request("/api/adapters/register", {"files": RULE_FILES, "definition": forged}, self.token)
        self.assertEqual(status, 400, rejected)
        self.assertEqual({str(path.relative_to(self.root)): path.read_bytes() for path in (self.root / "adapters").rglob("*.json")}, registry_before)
        self.assertEqual(self.request("/api/preview/analyze", payload)[1], good)

        # The iterable no longer supplies the called function. That saved rule
        # must fail its proof without suppressing the independently valid rule.
        status, recovered = self.request("/api/preview/analyze", {**payload, "files": changed})
        self.assertEqual(status, 200, recovered)
        failed_id = receipts[0]["rules"][0]["id"]
        successful_id = receipts[1]["rules"][0]["id"]
        self.assertTrue(any(item["ruleId"] == failed_id for item in recovered["ruleDiagnostics"]))
        self.assertEqual({item["ruleId"] for item in recovered["sourceRuleApplications"]}, {successful_id})
        nodes = {node["id"]: node for node in recovered["ir"]["nodes"]}
        edges = {edge["id"]: edge for edge in recovered["ir"]["edges"]}
        self.assertTrue(all(nodes.get(node["id"]) == node for node in changed_original["ir"]["nodes"]))
        self.assertTrue(all(edges.get(edge["id"]) == edge for edge in changed_original["ir"]["edges"]))
        self.assertTrue(any(node.get("expression") == "self.parts" for node in nodes.values()))
        self.assertEqual(list((self.root / "projects").glob("*/project.json")), [])

    def test_rule_api_requires_session_and_rejects_unknown_or_filesystem_fields(self):
        for path, payload in (("/api/adapters/rule-validate", {"rule": RULE}),
                              ("/api/adapters/rules", {}),
                              ("/api/adapters/scaffold", {"files": RULE_FILES, "entry": "foreign:CopperSprig", "rules": [RULE]})):
            with self.subTest(path=path, authorization="missing"):
                self.assertEqual(self.request(path, payload)[0], 403)
        for path, payload in (("/api/adapters/rules", {"root": "/etc"}),
                              ("/api/adapters/rules", {"unexpected": True}),
                              ("/api/adapters/rule-validate", {"rule": RULE, "root": "/etc"}),
                              ("/api/adapters/scaffold", {"files": RULE_FILES, "entry": "foreign:CopperSprig", "rules": [RULE], "useRegistryRules": "yes"}),
                              ("/api/adapters/scaffold", {"files": RULE_FILES, "entry": "foreign:CopperSprig", "rules": "plugin.py"})):
            with self.subTest(path=path, payload=payload):
                self.assertEqual(self.request(path, payload, self.token)[0], 400)
        self.assertEqual(self.request("/api/adapters/rules", {}, self.token), (200, []))

    def test_open_attaches_a_managed_source_to_a_legacy_canvas_without_losing_visual_history(self):
        from archcanvas_cli.canvas import canvas_operation
        status, architecture = self.request("/api/preview/edit-source", {"files": FILES, "entry": "unknown:Wrapper"}, self.token)
        self.assertEqual(status, 200, architecture)
        history = canvas_operation(ROOT, {"action": "create", "architecture": architecture})
        document = history["document"]
        document["title"] = "Retained visual edits"
        self.server.store.put(document["id"], document, 0, history=history)
        status, opened = self.request("/api/open", {"architecture": architecture}, self.token)
        self.assertEqual(status, 201, opened)
        self.assertTrue(opened["projectId"])
        saved = self.server.store.get(document["id"])
        self.assertEqual(saved["document"], document)
        self.assertEqual(saved["history"], history)
        self.assertEqual(saved["projectId"], opened["projectId"])
        project = self.root / "projects" / opened["projectId"] / "source" / "unknown.py"
        self.assertEqual(project.read_text(), FILES["unknown.py"])


class SourceAdaptationCLITests(unittest.TestCase):
    def test_source_checkout_launcher_discover_scaffold_register_and_reuse(self):
        with tempfile.TemporaryDirectory(prefix="archcanvas-adapter-cli-") as temporary:
            folder = Path(temporary); source = folder / "source"; source.mkdir()
            (source / "unknown.py").write_text(FILES["unknown.py"])
            environment = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
            def command(*args):
                result = subprocess.run([sys.executable, "-B", "-m", "archcanvas_cli", *args], env=environment,
                                        cwd=ROOT, capture_output=True, text=True, timeout=45)
                self.assertEqual(result.returncode, 0, result.stderr)
                return json.loads(result.stdout)
            discovered = command("discover", "--root", str(source))
            self.assertEqual(len(discovered["models"]), 2)
            definition = command("adapter", "scaffold", "--root", str(source), "--entry", "unknown:Hidden")
            path = folder / "definition.json"; path.write_text(json.dumps(definition))
            command("adapter", "register", "--root", str(source), "--definition", str(path), "--registry", str(folder / "registry"))
            preview = command("adapter", "preview", "--root", str(source), "--entry", "unknown:Hidden", "--registry", str(folder / "registry"))
            self.assertTrue(preview.get("sourceAdapters"))
            self.assertFalse(preview["ir"]["modelExecuted"])


if __name__ == "__main__":
    unittest.main()
