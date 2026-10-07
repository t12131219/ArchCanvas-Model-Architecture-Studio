"""Current renderer → source draft boundary tests, without executing model code."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import unittest

from archcanvas_authoring import DraftError, generate_model, import_source_draft, rebase_source_frontier, validate_draft
from archcanvas_python import analyze_project

ROOT = Path(__file__).resolve().parents[1]


def source_view(fixture="mlp", expanded=False, document=None):
    architecture = analyze_project(ROOT / "fixtures" / fixture,
                                   {"mlp": "model:MLP", "residual_cnn": "model:ResidualCNN", "transformer": "model:Transformer"}[fixture])
    script = """
import fs from 'node:fs';
import {createDocument,applyVisualBatch,buildScene} from './src/core/index.ts';
const input=JSON.parse(fs.readFileSync(0,'utf8'));
let document=input.document ?? createDocument(input.architecture);
document=applyVisualBatch(document,document.architecture.nodes.filter(n=>n.children.length && !n.id.startsWith('instance:'))
 .map(n=>({type:'expand',id:n.id,expanded:input.expanded})));
process.stdout.write(JSON.stringify({document,scene:buildScene(document)}));
"""
    result = subprocess.run(["node", "--experimental-strip-types", "--input-type=module", "-e", script],
                            cwd=ROOT / "studio", input=json.dumps({"architecture": architecture, "expanded": expanded, "document": document}),
                            text=True, capture_output=True, check=True)
    return json.loads(result.stdout)


@unittest.skipUnless(shutil.which("node"), "Current renderer requires Node.js")
class SourceAuthoringBridgeTests(unittest.TestCase):
    def test_actual_current_frontiers_retain_complete_source_and_ports(self):
        for fixture in ("mlp", "residual_cnn", "transformer"):
            for expanded in (False, True):
                with self.subTest(fixture=fixture, expanded=expanded):
                    view = source_view(fixture, expanded)
                    before = json.dumps(view, sort_keys=True)
                    imported = import_source_draft(view["document"], view["scene"])
                    draft = imported["draft"]
                    result = validate_draft(draft)
                    self.assertTrue(result["complete"])
                    self.assertEqual(draft["sourceProvenance"]["architecture"], view["document"]["architecture"])
                    self.assertEqual(len(draft["nodes"]), len(view["scene"]["nodes"]))
                    for node in draft["nodes"]:
                        ref = draft["sourceProvenance"]["nodeRefs"][node["id"]]
                        shown = next(n for n in view["scene"]["nodes"] if n["id"] == ref["sceneNodeId"])
                        self.assertEqual(node["position"], {"x": shown["x"], "y": shown["y"]})
                        self.assertEqual(node["presentation"]["width"], shown["width"])
                        self.assertEqual(node["presentation"]["height"], shown["height"])
                        self.assertEqual(len(node["presentation"]["ports"]), len(shown["ports"]))
                    self.assertEqual(json.dumps(view, sort_keys=True), before)

    def test_collapsed_frontier_generation_materializes_only_canonical_facts(self):
        # A collapsed root card has no visible Input/Output cards or displayed
        # edges.  Generation must still recover the complete graph from bound
        # source provenance, without inferring topology from its display label.
        for fixture in ("mlp", "residual_cnn", "transformer"):
            with self.subTest(fixture=fixture):
                view = source_view(fixture, expanded=False)
                draft = import_source_draft(view["document"], view["scene"])["draft"]
                root = draft["nodes"][0]
                root["label"] = "Renamed collapsed card"
                result = generate_model(draft)
                self.assertEqual(result["entry"], "archcanvas_grouped:AuthoredModel")
                self.assertEqual(result["draft"], draft)
                self.assertIn(root["id"], result["containerBindings"])
                kinds = {node["kind"] for node in result["architecture"]["nodes"]}
                self.assertTrue({"Input", "Output"} <= kinds)
                self.assertEqual(result["verification"]["modelExecution"], "not_run")
                self.assertEqual(result["verification"]["scope"], "source-preserved-collapsed-frontier-materialized-from-canonical-facts")

    def test_collapsed_generation_retains_cached_parameter_edits_deletion_and_rewire(self):
        full = source_view(expanded=True)
        draft = import_source_draft(full["document"], full["scene"])["draft"]
        refs = draft["sourceProvenance"]["nodeRefs"]
        by_kind = lambda kind: [node for node in draft["nodes"] if refs[node["id"]]["kind"] == kind]
        first, last = by_kind("Linear")
        first["parameters"]["out_features"] = 48
        last["parameters"]["in_features"] = 48
        activation, deleted = by_kind("GELU")[0], by_kind("Dropout")[0]
        draft["nodes"] = [node for node in draft["nodes"] if node["id"] != deleted["id"]]
        draft["edges"] = [edge for edge in draft["edges"] if deleted["id"] not in (edge["source"]["nodeId"], edge["target"]["nodeId"])]
        specs = {module["kind"]: module for module in draft["sourceProvenance"]["modules"]}
        port = lambda node, direction: next(item["id"] for item in specs[node["kind"]]["ports"] if item["direction"] == direction)
        draft["edges"].append({"id": "skip_removed_dropout", "source": {"nodeId": activation["id"], "portId": port(activation, "out")}, "target": {"nodeId": last["id"], "portId": port(last, "in")}})
        self.assertTrue(validate_draft(draft)["complete"])
        compact = source_view(document=full["document"], expanded=False)
        collapsed = rebase_source_frontier(draft, compact["document"], compact["scene"])["draft"]
        before = deepcopy(collapsed)
        self.assertIn(deleted["id"], collapsed["sourceCache"]["removedNodeIds"])
        self.assertTrue(any(edge["id"] == "skip_removed_dropout" for edge in collapsed["sourceCache"]["edges"]))
        result = generate_model(collapsed)
        self.assertEqual(collapsed, before)
        self.assertEqual(result["draft"], before)
        generated = result["architecture"]
        self.assertFalse(any(node["kind"] == "Dropout" for node in generated["nodes"]))
        self.assertCountEqual([node["parameters"] for node in generated["nodes"] if node["kind"] == "Linear"],
                              [{"in_features": 16, "out_features": 48}, {"in_features": 48, "out_features": 4}])
        producer = next(node for node in generated["nodes"] if node["kind"] == "GELU")
        consumer = next(node for node in generated["nodes"] if node["kind"] == "Linear" and node["parameters"]["out_features"] == 4)
        self.assertTrue(any(edge["source"]["nodeId"] == producer["id"] and edge["target"]["nodeId"] == consumer["id"] for edge in generated["edges"]))
        # Hidden/deleted source refs must not escape in bindings for a visible
        # collapsed draft; generated-canvas callers require actual draft IDs.
        visible = {node["id"] for node in collapsed["nodes"]}
        self.assertEqual(set(result["nodeBindings"]) | set(result["containerBindings"]), visible)

    def test_collapsed_generation_rejects_disconnected_added_module(self):
        view = source_view(expanded=False)
        draft = import_source_draft(view["document"], view["scene"])["draft"]
        draft["nodes"].append({"id": "new_identity", "kind": "Identity", "label": "Must not disappear",
                               "parameters": {}, "position": {"x": 900, "y": -80}})
        with self.assertRaises(DraftError) as caught:
            generate_model(draft)
        self.assertTrue(any(issue.get("nodeId") == "new_identity" and issue["code"] == "unbound-input" for issue in caught.exception.diagnostics))

    def test_collapsed_generation_rejects_tampered_provenance_digest(self):
        view = source_view(expanded=False)
        draft = import_source_draft(view["document"], view["scene"])["draft"]
        draft["sourceProvenance"]["digest"] = "0" * 64
        with self.assertRaisesRegex(DraftError, "provenance digest changed"):
            generate_model(draft)

    def test_collapsed_generation_refuses_unlowered_group_parameters(self):
        view = source_view(expanded=False)
        draft = import_source_draft(view["document"], view["scene"])["draft"]
        root = draft["nodes"][0]
        root["parameters"]["hidden_dim"] = 64
        with self.assertRaises(DraftError) as caught:
            generate_model(draft)
        self.assertEqual(caught.exception.diagnostics[0]["code"], "unsupported-group-parameters")
        self.assertEqual(caught.exception.diagnostics[0]["nodeId"], root["id"])

    def test_collapse_expand_rebase_keeps_edits_new_nodes_connections_and_deletion(self):
        full = source_view(expanded=True)
        draft = import_source_draft(full["document"], full["scene"])["draft"]
        refs = draft["sourceProvenance"]["nodeRefs"]
        linear = next(n for n in draft["nodes"] if refs[n["id"]]["kind"] == "Linear")
        linear["label"] = "My editable projection"
        linear["parameters"]["out_features"] = 77
        linear["position"]["x"] -= 32
        linear["presentation"]["fill"] = "#abcdef"
        # A disconnected new module may be saved while the graph is unfinished.
        draft["nodes"].append({"id": "new_identity", "kind": "Identity", "label": "Added in editor",
                               "parameters": {}, "position": {"x": 900, "y": -80}})
        deleted = next(n for n in draft["nodes"] if refs.get(n["id"], {}).get("kind") == "Dropout")
        deleted_id = deleted["id"]
        draft["nodes"] = [n for n in draft["nodes"] if n["id"] != deleted_id]
        draft["edges"] = [e for e in draft["edges"] if deleted_id not in (e["source"]["nodeId"], e["target"]["nodeId"])]
        out_port = next(p["id"] for m in draft["sourceProvenance"]["modules"] if m["kind"] == linear["kind"] for p in m["ports"] if p["direction"] == "out")
        draft["edges"].append({"id": "user_connection", "source": {"nodeId": linear["id"], "portId": out_port},
                               "target": {"nodeId": "new_identity", "portId": "input"}})
        before = deepcopy(draft)
        compact = source_view(document=full["document"], expanded=False)
        collapsed = rebase_source_frontier(draft, compact["document"], compact["scene"])["draft"]
        reopened = rebase_source_frontier(collapsed, full["document"], full["scene"])["draft"]
        self.assertEqual(draft, before)
        self.assertEqual(next(n for n in reopened["nodes"] if n["id"] == linear["id"])["parameters"]["out_features"], 77)
        reopened_linear = next(n for n in reopened["nodes"] if n["id"] == linear["id"])
        for key in ("position", "label"):
            self.assertEqual(reopened_linear[key], linear[key])
        self.assertEqual(reopened_linear["presentation"]["fill"], "#abcdef")
        self.assertFalse(any(n["id"] == deleted_id for n in reopened["nodes"]))
        self.assertTrue(any(n["id"] == "new_identity" for n in reopened["nodes"]))
        self.assertTrue(any(e["id"] == "user_connection" for e in reopened["edges"]))
        self.assertIn(deleted_id, reopened["sourceCache"]["removedNodeIds"])
        self.assertEqual(json.loads(json.dumps(reopened)), reopened)

    def test_forged_source_ir_and_port_binding_are_rejected(self):
        view = source_view(expanded=True)
        original_bytes = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT / "fixtures" / "mlp").glob("*.py")}
        for mutate in (lambda d: d["architecture"].update(sourceDigest="0" * 64),
                       lambda d: d["architecture"].update(irDigest="0" * 64),
                       lambda d: d["architecture"]["sources"][0].update(content="raise RuntimeError('must never execute')")):
            forged = deepcopy(view["document"]); mutate(forged)
            with self.assertRaises(DraftError):
                import_source_draft(forged, view["scene"])
        forged_scene = deepcopy(view["scene"])
        port = next(p for n in forged_scene["nodes"] for p in n["ports"] if p.get("canonicalBindings"))
        port["canonicalBindings"][0]["portId"] = "foreign_port"
        with self.assertRaises(DraftError):
            import_source_draft(view["document"], forged_scene)
        draft = import_source_draft(view["document"], view["scene"])["draft"]
        other = source_view("residual_cnn", expanded=True)
        with self.assertRaises(DraftError):
            rebase_source_frontier(draft, other["document"], other["scene"])
        self.assertEqual({p: hashlib.sha256(p.read_bytes()).hexdigest() for p in original_bytes}, original_bytes)
