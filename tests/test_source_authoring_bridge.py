"""Current renderer → source draft boundary tests, without executing model code."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import unittest
from unittest.mock import patch

from archcanvas_authoring import DraftError, generate_model, import_source_draft, rebase_source_frontier, validate_draft, module_catalog
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
if(input.expanded !== 'overview') document=applyVisualBatch(document,document.architecture.nodes.filter(n=>n.children.length && !n.id.startsWith('instance:'))
 .map(n=>({type:'expand',id:n.id,expanded:input.expanded})));
process.stdout.write(JSON.stringify({document,scene:buildScene(document)}));
"""
    result = subprocess.run(["node", "--experimental-strip-types", "--input-type=module", "-e", script],
                            cwd=ROOT / "studio", input=json.dumps({"architecture": architecture, "expanded": expanded, "document": document}),
                            text=True, capture_output=True, check=True)
    return json.loads(result.stdout)


@unittest.skipUnless(shutil.which("node"), "Current renderer requires Node.js")
class SourceAuthoringBridgeTests(unittest.TestCase):
    def test_partial_transformer_generation_preserves_visible_node_and_proxy_edge_bindings(self):
        view = source_view('transformer', expanded='overview')
        draft = import_source_draft(view['document'], view['scene'])['draft']
        self.assertEqual(len(draft['nodes']), 12)
        self.assertTrue(any(not n['presentation']['group'] and
                            draft['sourceProvenance']['nodeRefs'][n['id']]['kind'] == 'Repeat' for n in draft['nodes']))
        draft['nodes'][1]['position']['x'] -= 7
        before = deepcopy(draft)
        result = generate_model(draft)
        self.assertEqual(draft, before)
        self.assertEqual(result['draft'], before)
        self.assertEqual(len(result['architecture']['nodes']), 49)
        self.assertEqual(set(result['nodeBindings']) | set(result['containerBindings']), {n['id'] for n in draft['nodes']})
        self.assertEqual(set(result['edgeBindings']), {e['id'] for e in draft['edges']})
        actual_edges = {e['id'] for e in result['architecture']['edges']}
        self.assertTrue(all(ids and set(ids) <= actual_edges for ids in result['edgeBindings'].values()))

    def test_partial_transformer_rejects_unconnected_attention_before_materialization(self):
        view = source_view('transformer', expanded='overview')
        draft = import_source_draft(view['document'], view['scene'])['draft']
        spec = next(m for m in module_catalog()['modules'] if m['kind'] == 'MultiheadAttention')
        draft['nodes'].append(dict(id='unconnected_attention', kind=spec['kind'], label=spec['label'],
                                   parameters=deepcopy(spec['defaults']), position=dict(x=99, y=511)))
        before = deepcopy(draft)
        with patch('archcanvas_authoring.source_import._materialize_collapsed_frontier', side_effect=AssertionError('Invalid graph was expanded')):
            with self.assertRaises(DraftError) as caught:
                generate_model(draft)
        self.assertEqual({d['portId'] for d in caught.exception.diagnostics}, {'query', 'key', 'value'})
        self.assertTrue(all(d['nodeId'] == 'unconnected_attention' for d in caught.exception.diagnostics))
        self.assertEqual(draft, before)

    def test_partial_transformer_connected_addition_preserves_rebased_proxy_bindings(self):
        view = source_view('transformer', expanded='overview')
        draft = import_source_draft(view['document'], view['scene'])['draft']
        encoder = next(n for n in draft['nodes'] if n['label'] == 'encoder')
        existing = next(e for e in draft['edges'] if e['source']['nodeId'] == encoder['id'])
        draft['nodes'].append(dict(id='tap', kind='Identity', label='Identity', parameters={}, position=dict(x=99, y=511)))
        draft['edges'].append(dict(id='tap_edge', source=deepcopy(existing['source']), target=dict(nodeId='tap', portId='input')))
        before = deepcopy(draft)
        result = generate_model(draft)
        self.assertEqual(result['draft'], before)
        self.assertIn('tap', result['nodeBindings'])
        self.assertTrue(result['edgeBindings']['tap_edge'])
        self.assertEqual(set(result['edgeBindings']), {e['id'] for e in draft['edges']})

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

    def test_folded_custom_child_reappears_with_its_owner_and_deleted_owner_never_resurrects_it(self):
        full = source_view(expanded=True)
        draft = import_source_draft(full["document"], full["scene"])["draft"]
        owner = next(node for node in draft["nodes"] if node["presentation"]["group"] and not node["presentation"].get("parentId"))
        custom = {"id": "local_identity", "kind": "Identity", "label": "Nested Identity", "parameters": {},
                  "position": {"x": 20, "y": 40}, "presentation": {"width": 120, "height": 62, "fill": "#ffffff",
                  "stroke": "#355247", "group": False, "parentId": owner["id"], "ports": {}}}
        draft["nodes"].append(custom)
        compact = source_view(document=full["document"], expanded=False)
        folded = rebase_source_frontier(draft, compact["document"], compact["scene"])["draft"]
        self.assertNotIn(custom["id"], {node["id"] for node in folded["nodes"]})
        self.assertIn(custom, folded["sourceCache"]["nodes"])
        opened = rebase_source_frontier(json.loads(json.dumps(folded)), full["document"], full["scene"])["draft"]
        self.assertIn(custom, opened["nodes"])
        folded["nodes"] = []
        folded["edges"] = []
        deleted = rebase_source_frontier(folded, full["document"], full["scene"])["draft"]
        self.assertEqual(deleted["nodes"], [])
        self.assertIn(custom["id"], deleted["sourceCache"]["removedNodeIds"])
        self.assertTrue({node["id"] for node in draft["nodes"]} <= set(deleted["sourceCache"]["removedNodeIds"]))
        self.assertIn(custom, deleted["sourceCache"]["nodes"])

    def test_deleted_source_baseline_is_saved_for_recovery_after_rebase(self):
        full = source_view(expanded=True)
        draft = import_source_draft(full["document"], full["scene"])["draft"]
        removed = next(node for node in draft["nodes"] if draft["sourceProvenance"]["nodeRefs"][node["id"]]["kind"] == "Dropout")
        draft["nodes"] = [node for node in draft["nodes"] if node["id"] != removed["id"]]
        draft["edges"] = [edge for edge in draft["edges"] if removed["id"] not in (edge["source"]["nodeId"], edge["target"]["nodeId"])]
        rebased = rebase_source_frontier(draft, full["document"], full["scene"])["draft"]
        self.assertIn(removed, rebased["sourceCache"]["nodes"])
        self.assertIn(removed["id"], rebased["sourceCache"]["removedNodeIds"])
        self.assertNotIn(removed["id"], {node["id"] for node in rebased["nodes"]})
        self.assertEqual(rebased["sourceCache"]["removedCanonicalEdgeIds"], [])

    def test_explicit_edge_deletion_survives_a_deleted_endpoint_restore(self):
        full = source_view(expanded=True)
        draft = import_source_draft(full["document"], full["scene"])["draft"]
        edge = next(edge for edge in draft["edges"] if not any(node["id"] == edge["target"]["nodeId"] and node["presentation"]["group"] for node in draft["nodes"]))
        draft["edges"] = [item for item in draft["edges"] if item["id"] != edge["id"]]
        without_edge = rebase_source_frontier(draft, full["document"], full["scene"])["draft"]
        canonical = set(draft["sourceProvenance"]["edgeRefs"][edge["id"]])
        self.assertTrue(canonical <= set(without_edge["sourceCache"]["removedCanonicalEdgeIds"]))
        target = next(node for node in without_edge["nodes"] if node["id"] == edge["target"]["nodeId"])
        without_edge["nodes"] = [node for node in without_edge["nodes"] if node["id"] != target["id"]]
        without_edge["edges"] = [item for item in without_edge["edges"] if target["id"] not in (item["source"]["nodeId"], item["target"]["nodeId"])]
        deleted = rebase_source_frontier(without_edge, full["document"], full["scene"])["draft"]
        deleted["nodes"].append(deepcopy(target))
        deleted["sourceCache"]["removedNodeIds"].remove(target["id"])
        restored = rebase_source_frontier(deleted, full["document"], full["scene"])["draft"]
        self.assertNotIn(edge["id"], {item["id"] for item in restored["edges"]})
        self.assertTrue(canonical <= set(restored["sourceCache"]["removedCanonicalEdgeIds"]))

    def test_source_cache_malformed_tombstones_and_duplicate_snapshots_are_rejected(self):
        view = source_view(expanded=True)
        pristine = import_source_draft(view["document"], view["scene"])["draft"]
        for changed in ({"removedNodeIds": "wrong"}, {"removedNodeIds": ["same", "same"]},
                        {"removedCanonicalEdgeIds": [{}]}, {"nodes": [pristine["nodes"][0], pristine["nodes"][0]]}):
            with self.subTest(changed=changed):
                draft = deepcopy(pristine)
                draft["sourceCache"] = {"nodes": [], "edges": [], "removedNodeIds": [], "removedCanonicalEdgeIds": [], **changed}
                with self.assertRaises(DraftError):
                    validate_draft(draft)

    def test_never_expanded_conditional_branch_deletes_hidden_descendants_and_recovers_baseline(self):
        from tests.test_source_preservation import source_draft, SOURCE
        from archcanvas_python import analyze_source
        complete = source_draft(analyze_source(SOURCE, "model:Meadow"))
        document = complete["sourceProvenance"]["canvas"]
        branch = next(node for node in document["architecture"]["nodes"] if node["kind"] == "SourceBranch" and node["children"])
        script = """import fs from 'node:fs';
import {applyVisualBatch,buildScene} from './src/core/index.ts';
const input=JSON.parse(fs.readFileSync(0,'utf8'));
const document=applyVisualBatch(input.document,[{type:'expand',id:input.id,expanded:false}]);
process.stdout.write(JSON.stringify({document,scene:buildScene(document)}));"""
        result = subprocess.run(["node", "--experimental-strip-types", "--input-type=module", "-e", script],
                                cwd=ROOT / "studio", input=json.dumps({"document": document, "id": branch["id"]}),
                                text=True, capture_output=True, check=True)
        folded_view = json.loads(result.stdout)
        draft = import_source_draft(folded_view["document"], folded_view["scene"])["draft"]
        refs = draft["sourceProvenance"]["nodeRefs"]
        branch_id = next(identity for identity, ref in refs.items() if ref["nodeId"] == branch["id"])
        draft["nodes"] = [node for node in draft["nodes"] if node["id"] != branch_id]
        draft["edges"] = [edge for edge in draft["edges"] if branch_id not in (edge["source"]["nodeId"], edge["target"]["nodeId"])]
        full = source_view(document=document, expanded="overview")
        deleted = rebase_source_frontier(draft, full["document"], full["scene"])["draft"]
        facts = {node["id"]: node for node in document["architecture"]["nodes"]}
        subtree, pending = set(), [branch["id"]]
        while pending:
            identity = pending.pop(); subtree.add(identity); pending.extend(facts[identity]["children"])
        refs = deleted["sourceProvenance"]["nodeRefs"]
        self.assertFalse(any(refs[node["id"]]["nodeId"] in subtree for node in deleted["nodes"]))
        recover = [node for node in deleted["sourceProvenance"]["originalGraph"]["nodes"] if refs[node["id"]]["nodeId"] in subtree]
        deleted["nodes"].extend(deepcopy(recover))
        restore_ids = {node["id"] for node in recover}
        deleted["sourceCache"]["removedNodeIds"] = [identity for identity in deleted["sourceCache"]["removedNodeIds"] if identity not in restore_ids]
        recovered = rebase_source_frontier(json.loads(json.dumps(deleted)), full["document"], full["scene"])["draft"]
        self.assertTrue(restore_ids <= {node["id"] for node in recovered["nodes"]})
        self.assertTrue(validate_draft(recovered)["generation"]["supported"])
