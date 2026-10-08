"""Independent source-module contracts; no torch import or model execution."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from archcanvas_authoring import (DraftError, generate_model, import_source_draft,
                                  preview_custom_module, rebase_source_frontier,
                                  validate_draft)
from archcanvas_cli.drafts import DraftStore
from archcanvas_python import analyze_project, analyze_source
from archcanvas_authoring.source_module_contracts import source_module_contracts

ROOT = Path(__file__).resolve().parents[1]
SOURCE = """from torch import nn
class Fusion(nn.Module):
    def __init__(self, width, bias=False):
        super().__init__()
        self.project = nn.Linear(width, width, bias=bias)
    def forward(self, features, *, memory):
        hidden = self.project(features)
        return {"features": (hidden, memory), "merged": hidden + memory}
"""


def preview(source=SOURCE, entry="Fusion", constructor=None, label="自定义融合"):
    return preview_custom_module({"source": source, "entry": entry, "label": label,
                                  "constructorValues": {"width": 4} if constructor is None else constructor})


def node(identity, kind, parameters=None):
    return {"id": identity, "kind": kind, "label": identity, "parameters": parameters or {},
            "position": {"x": 100, "y": 100}}


def edge(identity, source, source_port, target, target_port):
    return {"id": identity, "source": {"nodeId": source, "portId": source_port},
            "target": {"nodeId": target, "portId": target_port}}


def authored(definition):
    return {"schemaVersion": 1, "mode": "authored-draft", "id": "draft-cafe", "title": "Custom architecture", "revision": 0,
            "customModules": [definition],
            "nodes": [node("input_a", "Input", {"shape": [2, 4], "dtype": "float32"}),
                      node("input_b", "Input", {"shape": [2, 4], "dtype": "float32"}),
                      node("fusion", definition["kind"]), node("relu", "ReLU"),
                      node("out_a", "Output"), node("out_b", "Output"), node("out_c", "Output")],
            "edges": [edge("e1", "input_a", "output", "fusion", "features"),
                      edge("e2", "input_b", "output", "fusion", "memory"),
                      edge("e3", "fusion", "output_1", "relu", "input"),
                      edge("e4", "relu", "output", "out_a", "input"),
                      edge("e5", "fusion", "output_2", "out_b", "input"),
                      edge("e6", "fusion", "output_3", "out_c", "input")]}


class CustomModuleTests(unittest.TestCase):
    def test_preview_infers_named_keyword_inputs_and_nested_return_slots(self):
        result = preview()
        definition = result["definition"]
        self.assertEqual([port["id"] for port in definition["inputs"]], ["features", "memory"])
        self.assertEqual([port["path"] for port in definition["outputs"]],
                         [[{"kind": "key", "key": "features"}, {"kind": "index", "index": 0}],
                          [{"kind": "key", "key": "features"}, {"kind": "index", "index": 1}],
                          [{"kind": "key", "key": "merged"}]])
        self.assertEqual(definition["constructorValues"], {"width": 4, "bias": False})
        self.assertEqual(result["verification"]["modelExecution"], "not_run")
        self.assertEqual(result["verification"]["shapeInference"], "unknown")
        # No mutable cached object can change a later preview.
        definition["inputs"][0]["id"] = "forged"
        self.assertEqual(preview()["definition"]["inputs"][0]["id"], "features")

    def test_static_generation_retains_source_constructor_and_exact_distinct_outputs(self):
        definition = preview()["definition"]
        draft = authored(definition)
        checked = validate_draft(draft, require_complete=True)
        self.assertTrue(checked["complete"])
        self.assertEqual(set(checked["tensors"]), {"input_a", "input_b"})
        self.assertIn("relu", checked["unknownTensorNodeIds"])
        result = generate_model(draft)
        self.assertEqual(result["draft"], draft)
        self.assertEqual(result["verification"]["customOutputShapes"], "unknown")
        custom_files = [item for item in result["architecture"]["sources"] if item["path"].startswith("archcanvas_custom_")]
        self.assertEqual(len(custom_files), 1)
        self.assertTrue(custom_files[0]["content"].startswith(SOURCE.rstrip()))
        instances = [item for item in result["architecture"]["nodes"] if item.get("instanceId", "").endswith(".inner.project")]
        self.assertEqual([item["parameters"] for item in instances], [{"in_features": 4, "out_features": 4, "bias": False}])
        facts = {item["id"]: item for item in result["architecture"]["nodes"]}
        canonical_edges = {item["id"]: item for item in result["architecture"]["edges"]}
        custom_id = result["nodeBindings"]["fusion"]
        output_producers = []
        for draft_edge in ("e3", "e5", "e6"):
            mapped = result["edgeBindings"][draft_edge]
            self.assertEqual(len(mapped), 1)
            relation = canonical_edges[mapped[0]]
            producer = facts[relation["source"]["nodeId"]]
            self.assertEqual(producer["kind"], "Identity")
            self.assertEqual(producer["parentId"], custom_id)
            output_producers.append(producer["id"])
        self.assertEqual(len(set(output_producers)), 3)
        for draft_edge, port_name in (("e1", "features"), ("e2", "memory")):
            relation = canonical_edges[result["edgeBindings"][draft_edge][0]]
            self.assertEqual(relation["target"], {"nodeId": custom_id, "portId": custom_id + ":in:" + port_name})

    def test_repeated_instances_and_same_class_names_are_namespaced(self):
        first = preview()["definition"]
        second = preview(constructor={"width": 8})["definition"]
        self.assertNotEqual(first["kind"], second["kind"])
        draft = authored(first)
        draft["customModules"].append(second)
        draft["nodes"] += [node("repeat", first["kind"]), node("other", second["kind"]), node("out_repeat", "Output"), node("out_other", "Output")]
        draft["edges"] += [edge("r1", "input_a", "output", "repeat", "features"), edge("r2", "input_b", "output", "repeat", "memory"),
                           edge("r3", "repeat", "output_1", "out_repeat", "input"), edge("s1", "input_a", "output", "other", "features"),
                           edge("s2", "input_b", "output", "other", "memory"), edge("s3", "other", "output_3", "out_other", "input")]
        result = generate_model(draft)
        self.assertEqual(len({result["nodeBindings"][identity] for identity in ("fusion", "repeat", "other")}), 3)
        self.assertEqual(len([source for source in result["architecture"]["sources"] if source["path"].startswith("archcanvas_custom_")]), 2)
        project_widths = sorted(item["parameters"]["in_features"] for item in result["architecture"]["nodes"] if item.get("instanceId", "").endswith(".inner.project"))
        self.assertEqual(project_widths, [4, 4, 8])

    def test_definitions_persist_and_source_or_port_forgery_is_rejected(self):
        draft = authored(preview()["definition"])
        with tempfile.TemporaryDirectory() as temporary:
            store = DraftStore(Path(temporary))
            saved = store.put(draft["id"], draft, 0)
            reopened = DraftStore(Path(temporary)).get(draft["id"])
            self.assertEqual(reopened, saved)
            self.assertEqual(generate_model(reopened["draft"])["draft"], draft)
        for mutate in (lambda item: item.__setitem__("source", item["source"].replace("width, width", "width, 9")),
                       lambda item: item["outputs"][0]["path"][1].__setitem__("index", 1),
                       lambda item: item.__setitem__("digest", "0" * 64)):
            invalid = deepcopy(draft); mutate(invalid["customModules"][0])
            with self.assertRaises(DraftError): validate_draft(invalid)
        invalid = deepcopy(draft); invalid["edges"][2]["source"]["portId"] = "guessed_output"
        with self.assertRaises(DraftError): generate_model(invalid)

    def test_errors_are_explicit_and_unknown_internal_results_are_not_shapes(self):
        for request in ({"source": "broken :", "entry": "Fusion", "label": "bad", "constructorValues": {}},
                        {"source": SOURCE, "entry": "Missing", "label": "bad", "constructorValues": {}},
                        {"source": SOURCE, "entry": "Fusion", "label": "bad", "constructorValues": {}},
                        {"source": SOURCE, "entry": "Fusion", "label": "bad", "constructorValues": {"width": 4, "unknown": 2}},
                        {"source": SOURCE.replace("features, *, memory", "*args"), "entry": "Fusion", "label": "bad", "constructorValues": {"width": 4}}):
            with self.assertRaises(DraftError): preview_custom_module(request)
        opaque = preview(source="from torch import nn\nclass Unknown(nn.Module):\n def forward(self, x):\n  return unknown_transform(x)\n", entry="Unknown", constructor={})
        self.assertTrue(opaque["verification"]["opaqueNodeIds"])
        self.assertEqual(opaque["verification"]["shapeInference"], "unknown")

    def test_top_level_and_constructor_side_effects_never_execute(self):
        with tempfile.TemporaryDirectory() as temporary:
            sentinel = Path(temporary) / "source-was-executed"
            source = f"from torch import nn\nopen({str(sentinel)!r}, 'w').write('unsafe')\nclass SafeStatic(nn.Module):\n def __init__(self):\n  super().__init__()\n  raise RuntimeError('Do not execute this constructor')\n def forward(self, x):\n  return x\n"
            result = preview(source=source, entry="SafeStatic", constructor={})
            definition = result["definition"]
            draft = {"schemaVersion": 1, "mode": "authored-draft", "id": "draft-cafe", "title": "static", "revision": 0,
                     "customModules": [definition], "nodes": [node("input", "Input", {"shape": [1, 4], "dtype": "float32"}), node("custom", definition["kind"]), node("out", "Output")],
                     "edges": [edge("e1", "input", "output", "custom", "x"), edge("e2", "custom", "output", "out", "input")]}
            self.assertEqual(generate_model(draft)["verification"]["modelExecution"], "not_run")
            self.assertFalse(sentinel.exists())

    def test_source_globals_are_retained_without_becoming_constructor_arguments(self):
        source = "from torch import nn\nWIDTH = 4\nclass GlobalBlock(nn.Module):\n def __init__(self):\n  super().__init__()\n  self.project = nn.Linear(WIDTH, WIDTH)\n def forward(self, x):\n  return self.project(x)\n"
        definition = preview(source=source, entry="GlobalBlock", constructor={})["definition"]
        draft = {"schemaVersion": 1, "mode": "authored-draft", "id": "draft-cafe", "title": "globals", "revision": 0,
                 "customModules": [definition], "nodes": [node("input", "Input", {"shape": [1, 4], "dtype": "float32"}), node("custom", definition["kind"]), node("out", "Output")],
                 "edges": [edge("e1", "input", "output", "custom", "x"), edge("e2", "custom", "output", "out", "input")]}
        result = generate_model(draft)
        self.assertEqual(result["verification"]["customOutputShapes"], "unknown")
        self.assertTrue(any(source["content"].startswith(definition["source"].rstrip()) for source in result["architecture"]["sources"]))

    def test_private_and_output_named_arguments_have_unique_port_ids(self):
        source = "from torch import nn\n_archcanvas_nn = 7\nclass PrivateBlock(nn.Module):\n def forward(self, _features, output):\n  return _features + output\n"
        result = preview(source=source, entry="PrivateBlock", constructor={})
        definition = result["definition"]
        self.assertEqual([item["name"] for item in definition["inputs"]], ["_features", "output"])
        input_ids = [item["id"] for item in definition["inputs"]]
        self.assertEqual(len(set(input_ids + ["output"])), 3)
        self.assertTrue(all(identity.startswith("input_") for identity in input_ids))
        draft = {"schemaVersion": 1, "mode": "authored-draft", "id": "draft-cafe", "title": "private", "revision": 0,
                 "customModules": [definition], "nodes": [node("input", "Input", {"shape": [1, 4], "dtype": "float32"}), node("custom", definition["kind"]), node("out", "Output")],
                 "edges": [edge("e1", "input", "output", "custom", input_ids[0]), edge("e2", "input", "output", "custom", input_ids[1]), edge("e3", "custom", "output", "out", "input")]}
        generated = generate_model(draft)
        custom_file = next(item["content"] for item in generated["architecture"]["sources"] if item["path"].startswith("archcanvas_custom_"))
        self.assertIn("from torch import nn as _archcanvas_nn_1", custom_file)
        self.assertIn("_features=", generated["source"])
        self.assertIn("output=", generated["source"])

        imported_alias = preview(source="from torch import nn\nimport torch as _archcanvas_nn\nclass AliasBlock(nn.Module):\n def forward(self, x):\n  return x\n", entry="AliasBlock", constructor={})["definition"]
        alias_file = next(item["content"] for item in generate_model({"schemaVersion": 1, "mode": "authored-draft", "id": "draft-alias", "title": "alias", "revision": 0,
            "customModules": [imported_alias], "nodes": [node("input", "Input", {"shape": [1, 4], "dtype": "float32"}), node("custom", imported_alias["kind"]), node("out", "Output")],
            "edges": [edge("e1", "input", "output", "custom", "x"), edge("e2", "custom", "output", "out", "input")]})["architecture"]["sources"] if item["path"].startswith("archcanvas_custom_"))
        self.assertIn("from torch import nn as _archcanvas_nn_1", alias_file)

    def test_input_identity_collisions_stay_unique_and_unsupported_methods_are_diagnosed(self):
        collision = "input_" + hashlib.sha256(b"_features").hexdigest()[:16]
        source = f"from torch import nn\nclass Collision(nn.Module):\n def forward(self, _features, {collision}):\n  return _features + {collision}\n"
        definition = preview(source=source, entry="Collision", constructor={})["definition"]
        self.assertEqual(len({item["id"] for item in definition["inputs"]}), 2)
        self.assertEqual(definition["inputs"][1]["id"], definition["inputs"][0]["id"] + "_2")
        draft = {"schemaVersion": 1, "mode": "authored-draft", "id": "draft-cafe", "title": "collision", "revision": 0,
                 "customModules": [definition], "nodes": [node("input", "Input", {"shape": [1, 4], "dtype": "float32"}), node("custom", definition["kind"]), node("out", "Output")],
                 "edges": [edge("e1", "input", "output", "custom", definition["inputs"][0]["id"]),
                           edge("e2", "input", "output", "custom", definition["inputs"][1]["id"]), edge("e3", "custom", "output", "out", "input")]}
        result = generate_model(draft)
        self.assertEqual(result["verification"]["customBoundaryBindings"], 3)
        for source, entry in (
            ("from torch import nn\nclass Bad(nn.Module):\n async def forward(self, x):\n  return x\n", "Bad"),
            ("from torch import nn\nclass Bad(nn.Module):\n def forward(self, x):\n  return x\n def forward(self, y):\n  return y\n", "Bad"),
            ("from torch import nn\nclass Bad(nn.Module):\n async def __init__(self):\n  pass\n def forward(self, x):\n  return x\n", "Bad"),
            ("from torch import nn\nclass Bad(nn.Module):\n @staticmethod\n def forward(self, x):\n  return x\n", "Bad"),
            ("from torch import nn\nclass Bad(nn.Module):\n def __init__(self):\n  super().__init__()\n def __init__(self, width):\n  super().__init__()\n def forward(self, x):\n  return x\n", "Bad"),
            ("from torch import nn\nclass Bad(nn.Module):\n def forward(self, x, x):\n  return x\n", "Bad"),
            ("from torch import nn\nclass Bad(nn.Module):\n def forward(self, x):\n  return x\n forward = unknown_callable\n", "Bad"),
            ("from torch import nn\nclass Bad(nn.Module):\n def forward(self, x):\n  return x\nBad = unknown_class\n", "Bad"),
            ("from torch import nn\n@unknown_wrapper\nclass Bad(nn.Module):\n def forward(self, x):\n  return x\n", "Bad"),
            ("from torch import nn\nclass Parent(nn.Module):\n def __init__(self, width):\n  super().__init__()\nclass Bad(Parent):\n def forward(self, x):\n  return x\n", "Bad"),
        ):
            with self.assertRaises(DraftError):
                preview(source=source, entry=entry, constructor={})
        with self.assertRaises(DraftError):
            preview(source="from torch import nn\nreturn 3\nclass Bad(nn.Module):\n def forward(self, x):\n  return x\n", entry="Bad", constructor={})

    def test_fresh_import_of_generated_module_preserves_multislot_source_without_session_metadata(self):
        original = generate_model(authored(preview()["definition"]))
        script = """import fs from 'node:fs';
import {createDocument,buildScene} from './src/core/index.ts';
const architecture=JSON.parse(fs.readFileSync(0,'utf8'));
const document=createDocument(architecture);
document.expandedIds=architecture.nodes.filter(n=>!n.parentId&&n.children.length).map(n=>n.id);
process.stdout.write(JSON.stringify({document,scene:buildScene(document)}));"""
        rendered = subprocess.run(["node", "--experimental-strip-types", "--input-type=module", "-e", script],
                                  cwd=ROOT / "studio", input=json.dumps(original["architecture"]), text=True, capture_output=True, check=True)
        view = json.loads(rendered.stdout)
        imported = import_source_draft(view["document"], view["scene"])["draft"]
        self.assertNotIn("customModules", imported)
        result = generate_model(imported)
        self.assertEqual(result["verification"]["retainedSourceModules"], 1)
        # A new wrapper filename avoids replacing the prior generated corpus.
        self.assertEqual(result["entry"], "archcanvas_composed:AuthoredModel")
        old_custom = next(source for source in original["architecture"]["sources"] if source["path"].startswith("archcanvas_custom_"))
        self.assertIn(old_custom, result["architecture"]["sources"])
        output_ports = [item for item in result["architecture"]["nodes"] if item["kind"] == "Output"]
        self.assertEqual(len(output_ports), 3)

    def test_retained_source_boundaries_do_not_certify_unsupported_call_signatures(self):
        host = "\nclass Host(nn.Module):\n def __init__(self):\n  super().__init__()\n  self.block = Block()\n def forward(self, x):\n  return self.block(x)\n"
        for block in (
            "class Block(nn.Module):\n @staticmethod\n def forward(self, x):\n  return x\n",
            "class Block(nn.Module):\n def __init__(self, /):\n  super().__init__()\n def forward(self, x):\n  return x\n",
            "class Block(nn.Module):\n def forward(self, x):\n  return x\n forward = unknown_callable\n",
        ):
            architecture = analyze_source("from torch import nn\n" + block + host, "model:Host")
            contracts = source_module_contracts(architecture)
            block_id = next(item["id"] for item in architecture["nodes"] if item.get("instanceId", "").endswith("Host.block"))
            self.assertNotIn(block_id, contracts)
            self.assertTrue(any(contract["class"] == "Host" for contract in contracts.values()))
        invalid = analyze_source("from torch import nn\nreturn 3\nclass Host(nn.Module):\n def forward(self, x):\n  return x\n", "model:Host")
        with self.assertRaises(DraftError):
            source_module_contracts(invalid)

    def test_visual_card_fields_are_checked_persisted_and_never_change_source(self):
        draft = authored(preview()["definition"])
        baseline = generate_model(draft)
        style = {"width": 230, "height": 120, "fill": "#dfeee7", "stroke": "#0b4455"}
        draft["nodes"][2]["visual"] = style
        checked = validate_draft(draft)
        self.assertEqual(checked["draft"]["nodes"][2]["visual"], style)
        generated = generate_model(draft)
        self.assertEqual(generated["architecture"], baseline["architecture"])
        self.assertEqual(generated["source"], baseline["source"])
        for bad_style in ({**style, "width": True}, {**style, "height": float("inf")}, {**style, "fill": "url(file:///tmp/arbitrary)"}, {**style, "extra": "field"}):
            invalid = deepcopy(draft); invalid["nodes"][2]["visual"] = bad_style
            with self.assertRaises(DraftError): validate_draft(invalid)

    def test_source_derived_graph_and_frontier_rebase_keep_custom_definitions(self):
        architecture = analyze_project(ROOT / "fixtures" / "mlp", "model:MLP")
        script = """import fs from 'node:fs';
import {createDocument,buildScene} from './src/core/index.ts';
const architecture=JSON.parse(fs.readFileSync(0,'utf8'));
const document=createDocument(architecture);
document.expandedIds=architecture.nodes.filter(n=>n.children.length).map(n=>n.id);
process.stdout.write(JSON.stringify({document,scene:buildScene(document)}));"""
        rendered = subprocess.run(["node", "--experimental-strip-types", "--input-type=module", "-e", script],
                                  cwd=ROOT / "studio", input=json.dumps(architecture), text=True, capture_output=True, check=True)
        view = json.loads(rendered.stdout)
        draft = import_source_draft(view["document"], view["scene"])["draft"]
        definition = preview(source="from torch import nn\nclass Tail(nn.Module):\n def forward(self, x):\n  return x\n", entry="Tail", constructor={})["definition"]
        draft["customModules"] = [definition]
        draft["nodes"][0]["visual"] = {"width": 340, "height": 280, "fill": "#fff", "stroke": "#123456"}
        output = next(item for item in draft["nodes"] if draft["sourceProvenance"]["nodeRefs"][item["id"]]["kind"] == "Output")
        preceding = next(item for item in draft["edges"] if item["target"]["nodeId"] == output["id"])
        old_source = deepcopy(preceding["source"])
        draft["nodes"].append(node("custom_tail", definition["kind"]))
        preceding["source"] = {"nodeId": "custom_tail", "portId": "output"}
        draft["edges"].append({"id": "to_custom", "source": old_source, "target": {"nodeId": "custom_tail", "portId": "x"}})
        rebased = rebase_source_frontier(draft, view["document"], view["scene"])["draft"]
        self.assertEqual(rebased["customModules"], draft["customModules"])
        self.assertEqual(rebased["nodes"][0]["visual"], draft["nodes"][0]["visual"])
        generated = generate_model(rebased)
        self.assertIn("custom_tail", generated["nodeBindings"])
        self.assertTrue(any(source["content"].startswith(definition["source"].rstrip()) for source in generated["architecture"]["sources"]))
        self.assertEqual(generated["verification"]["modelExecution"], "not_run")


if __name__ == "__main__":
    unittest.main()
