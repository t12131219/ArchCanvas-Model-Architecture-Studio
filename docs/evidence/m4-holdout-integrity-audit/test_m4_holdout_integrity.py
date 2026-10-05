"""Exact holdout source inventories plus deliberate, independently rejected corruption.

These checks neither import nor execute a fixture. Every corruption first proves
that its original graph satisfies the complete oracle, so an unrelated failure
cannot masquerade as detection of the intended defect.
"""

from collections import Counter, defaultdict
from copy import deepcopy
import hashlib
from pathlib import Path
import unittest

from archcanvas_python import analyze_project
from m4_holdout_integrity_oracle import HOLDOUTS


ROOT = Path(__file__).resolve().parents[1]


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def named_nodes(architecture, expected):
    prefix = "instance:" + expected["entry"].replace(":", ".")
    names, nodes = {}, {}
    for value in architecture["nodes"]:
        identity = value["id"]
        require(identity not in names, "duplicate node identity")
        instance = value.get("instanceId")
        if instance is not None:
            member = "root" if instance == prefix else instance.removeprefix(prefix + ".")
            candidates = [name for name, facts in expected["nodes"].items()
                          if facts["member"] == member
                          and (facts["expression"] is None or facts["expression"] == value["source"]["expression"])]
        elif value["kind"] == "Input":
            candidates = [name for name, facts in expected["nodes"].items()
                          if facts["kind"] == "Input" and facts["ports"][0][0] == value["label"]]
        elif value["kind"] == "Output":
            candidates = [name for name, facts in expected["nodes"].items()
                          if facts["kind"] == "Output" and facts["outputPath"] == value.get("outputPath")]
        elif value["kind"] == "Repeat":
            candidates = [name for name, facts in expected["nodes"].items()
                          if facts["kind"] == "Repeat" and name == "repeat." + value["label"]]
        else:
            candidates = [name for name, facts in expected["nodes"].items()
                          if facts["member"] is None and facts["kind"] == value["kind"]
                          and facts["expression"] == value["source"]["expression"]]
        require(len(candidates) == 1, "missing or ambiguous authored node occurrence")
        name = candidates[0]
        require(name not in nodes, "duplicate authored node occurrence")
        names[identity], nodes[name] = name, value
    require(set(nodes) == set(expected["nodes"]), "complete authored node inventory differs")
    return names, nodes


def check_holdout(architecture, entry, fixture_root):
    expected = HOLDOUTS[entry]
    require(architecture["entry"] == expected["entry"], "entry differs")
    require(len(architecture["sources"]) == 1 and architecture["sources"][0]["path"] == "model.py",
            "complete source inventory differs")
    source = architecture["sources"][0]
    raw = fixture_root.joinpath("model.py").read_bytes()
    require(source["content"] == raw.decode("utf-8"), "source content differs")
    require(source["digest"] == hashlib.sha256(raw).hexdigest(), "source SHA differs")
    names, nodes = named_nodes(architecture, expected)
    local_ports, calls, instance_calls = {}, set(), defaultdict(list)
    prefix = "instance:" + expected["entry"].replace(":", ".")
    for name, value in nodes.items():
        facts = expected["nodes"][name]
        for field in ("kind", "category", "evidence", "parameters"):
            require(value[field] == facts[field], name + ": " + field + " differs")
        parent = value.get("parentId")
        require(parent is None or parent in names, name + ": dangling parent")
        require(names.get(parent) == facts["parent"], name + ": parent differs")
        require(all(child in names for child in value["children"]), name + ": dangling child")
        # A custom root's sibling membership does not claim layout/source order.
        # Counter preserves multiplicity; repeats/Sequential additionally retain
        # the authored execution order of their independent members.
        observed_children = [names[child] for child in value["children"]]
        wanted_children = expected["children"].get(name, ())
        require(Counter(observed_children) == Counter(wanted_children), name + ": complete containment differs")
        if facts["repeat"] is not None:
            require(tuple(observed_children) == tuple(wanted_children), name + ": ordered repeat members differ")
        require(value.get("repeat") == facts["repeat"], name + ": repeat/sharing differs")
        port_facts = tuple((port["name"], port["direction"], port["role"], port["ordinal"])
                           for port in value["ports"])
        require(port_facts == facts["ports"], name + ": complete declared port contract differs")
        for port in value["ports"]:
            key = value["id"], port["id"]
            require(key not in local_ports, name + ": duplicate local port identity")
            local_ports[key] = port
        origin = value["source"]
        require(origin["path"] == "model.py", name + ": source path differs")
        lines = source["content"].splitlines()
        require(1 <= origin["line"] <= origin["endLine"] <= len(lines), name + ": invalid source range")
        require(origin["expression"] in "\n".join(lines[origin["line"] - 1:origin["endLine"]]),
                name + ": expression absent from source range")
        if facts["expression"] is not None:
            require(origin["expression"] == facts["expression"], name + ": authored call expression differs")
        if facts["member"] is not None:
            member = facts["member"]
            wanted_instance = prefix + ("." + member if member != "root" else "")
            require(value.get("instanceId") == wanted_instance, name + ": instance identity differs")
            call = value.get("callId")
            require(isinstance(call, str) and call and call not in calls, name + ": call identity missing/duplicated")
            calls.add(call)
            instance_calls[wanted_instance].append(name)
        else:
            require("instanceId" not in value and "callId" not in value, name + ": invented instance/call")
        if facts["kind"] == "Output":
            require(value.get("outputPath") == facts["outputPath"], name + ": return slot differs")
        else:
            require("outputPath" not in value, name + ": invented return slot")
    require(len(calls) == expected["callCount"], "complete call inventory differs")
    require(len(instance_calls) == expected["instanceCount"], "complete independent/shared instance inventory differs")

    relations, edge_ids = [], set()
    producer_tensors, tensor_producers, tensor_consumers = {}, {}, defaultdict(list)
    for edge in architecture["edges"]:
        require(edge["id"] not in edge_ids, "duplicate edge identity")
        edge_ids.add(edge["id"])
        source_key = edge["source"]["nodeId"], edge["source"]["portId"]
        target_key = edge["target"]["nodeId"], edge["target"]["portId"]
        require(source_key in local_ports, "source binding uses a foreign or missing local port")
        require(target_key in local_ports, "target binding uses a foreign or missing local port")
        producer_port, consumer_port = local_ports[source_key], local_ports[target_key]
        require(producer_port["direction"] == "out" and consumer_port["direction"] == "in", "edge direction differs")
        require(edge["role"] == consumer_port["role"], "edge role differs from declared consumer port")
        producer = names[source_key[0]], producer_port["name"]
        consumer = names[target_key[0]], consumer_port["name"]
        relations.append((*producer, *consumer, edge["role"]))
        tensor = edge["tensorId"]
        require(isinstance(tensor, str) and tensor, "missing tensor identity")
        require(producer_tensors.get(source_key, tensor) == tensor, "one producer split into multiple tensor identities")
        require(tensor_producers.get(tensor, source_key) == source_key, "two producers merged into one tensor identity")
        producer_tensors[source_key], tensor_producers[tensor] = tensor, source_key
        tensor_consumers[tensor].append((*consumer, edge["role"]))
    require(Counter(relations) == Counter(expected["relations"]), "complete producer/port relation multiplicity differs")
    require(len(tensor_producers) == expected["tensorCount"], "complete tensor producer inventory differs")
    warnings = [item["message"] for item in architecture["diagnostics"] if item["level"] == "warning"]
    require(not [item for item in architecture["diagnostics"] if item["level"] == "error"], "unexpected error diagnostic")
    require(len(warnings) == len(expected["warnings"]), "complete warning inventory differs")
    for fragment in expected["warnings"]:
        require(any(fragment in warning for warning in warnings), "required opaque warning missing")
    return {
        "entry": expected["entry"], "nodeCount": len(nodes), "edgeCount": len(relations),
        "portCount": len(local_ports), "tensorCount": len(tensor_producers), "callCount": len(calls),
        "instanceCount": len(instance_calls), "opaqueNodeCount": sum(node["evidence"] == "opaque" for node in nodes.values()),
        "nodes": sorted(nodes), "relations": sorted(relations),
        "containment": {name: sorted(names[child] for child in node["children"]) for name, node in sorted(nodes.items()) if node["children"]},
        "instanceCalls": {key: sorted(values) for key, values in sorted(instance_calls.items())},
        "tensors": [{"producer": [names[producer[0]], local_ports[producer]["name"]],
                     "consumers": sorted(tensor_consumers[tensor])} for producer, tensor in sorted(producer_tensors.items())],
    }


class M4HoldoutIntegrityTests(unittest.TestCase):
    def analyzed(self, entry):
        facts = HOLDOUTS[entry]
        fixture = ROOT / "fixtures" / facts["fixture"]
        architecture = analyze_project(fixture, facts["entry"])
        check_holdout(architecture, entry, fixture)
        return architecture, fixture

    def corrupted(self, entry):
        architecture, fixture = self.analyzed(entry)
        copy = deepcopy(architecture)
        _, nodes = named_nodes(copy, HOLDOUTS[entry])
        return copy, fixture, nodes

    def test_vit_complete_declared_ports_tensors_and_containment(self):
        self.analyzed("PatchVisionEncoder")

    def test_unsupported_vision_complete_source_backed_boundary(self):
        self.analyzed("UnsupportedVision")

    def test_temporal_complete_lstm_slots_and_shared_calls(self):
        self.analyzed("TemporalForecaster")

    def test_segmentation_complete_skip_concat_and_independent_repeat(self):
        self.analyzed("SkipSegmentation")

    def test_graph_complete_unknown_and_conditional_boundaries(self):
        self.analyzed("GraphForecast")

    def test_ssm_complete_unknown_and_dynamic_loop_boundaries(self):
        self.analyzed("DynamicStateSpace")

    def test_rejects_foreign_same_named_port(self):
        copy, fixture, nodes = self.corrupted("TemporalForecaster")
        edge = next(edge for edge in copy["edges"] if edge["target"]["nodeId"] == nodes["projection"]["id"])
        edge["target"]["portId"] = next(port["id"] for port in nodes["projection@2"]["ports"] if port["name"] == "input")
        with self.assertRaisesRegex(AssertionError, "foreign or missing local port"):
            check_holdout(copy, "TemporalForecaster", fixture)

    def test_rejects_split_shared_tensor(self):
        copy, fixture, nodes = self.corrupted("TemporalForecaster")
        edge = next(edge for edge in copy["edges"] if edge["target"]["nodeId"] == nodes["projection@2"]["id"])
        edge["tensorId"] += ":false-independent"
        with self.assertRaisesRegex(AssertionError, "one producer split"):
            check_holdout(copy, "TemporalForecaster", fixture)

    def test_rejects_merged_lstm_output_slots(self):
        copy, fixture, nodes = self.corrupted("TemporalForecaster")
        hidden = next(edge for edge in copy["edges"] if edge["target"]["nodeId"] == nodes["output2"]["id"])
        cell = next(edge for edge in copy["edges"] if edge["target"]["nodeId"] == nodes["output3"]["id"])
        cell["tensorId"] = hidden["tensorId"]
        with self.assertRaisesRegex(AssertionError, "two producers merged"):
            check_holdout(copy, "TemporalForecaster", fixture)

    def test_rejects_extra_unbound_port(self):
        copy, fixture, nodes = self.corrupted("PatchVisionEncoder")
        nodes["attention"]["ports"].append({"id": "invented", "name": "extra", "direction": "out", "role": "data", "ordinal": 2})
        with self.assertRaisesRegex(AssertionError, "complete declared port contract"):
            check_holdout(copy, "PatchVisionEncoder", fixture)

    def test_rejects_port_role_or_ordinal_corruption(self):
        for field, value in (("role", "memory"), ("ordinal", 1)):
            with self.subTest(field=field):
                copy, fixture, nodes = self.corrupted("PatchVisionEncoder")
                next(port for port in nodes["norm"]["ports"] if port["name"] == "input")[field] = value
                with self.assertRaisesRegex(AssertionError, "complete declared port contract"):
                    check_holdout(copy, "PatchVisionEncoder", fixture)

    def test_rejects_relation_multiplicity_even_with_unique_edge_ids(self):
        copy, fixture, _ = self.corrupted("PatchVisionEncoder")
        duplicate = deepcopy(copy["edges"][0])
        duplicate["id"] = "edge:invented-copy"
        copy["edges"].append(duplicate)
        with self.assertRaisesRegex(AssertionError, "relation multiplicity differs"):
            check_holdout(copy, "PatchVisionEncoder", fixture)

    def test_rejects_duplicate_containment_members(self):
        copy, fixture, nodes = self.corrupted("SkipSegmentation")
        nodes["repeat.refinement"]["children"].append(nodes["refinement.0"]["id"])
        with self.assertRaisesRegex(AssertionError, "complete containment differs"):
            check_holdout(copy, "SkipSegmentation", fixture)

    def test_rejects_wrong_parent_without_changing_visible_relations(self):
        copy, fixture, nodes = self.corrupted("SkipSegmentation")
        nodes["refinement.1.conv"]["parentId"] = nodes["root"]["id"]
        with self.assertRaisesRegex(AssertionError, "parent differs"):
            check_holdout(copy, "SkipSegmentation", fixture)

    def test_rejects_swapped_repeat_members(self):
        copy, fixture, nodes = self.corrupted("SkipSegmentation")
        nodes["repeat.refinement"]["children"].reverse()
        with self.assertRaisesRegex(AssertionError, "ordered repeat members differ"):
            check_holdout(copy, "SkipSegmentation", fixture)

    def test_rejects_false_repeat_sharing(self):
        copy, fixture, nodes = self.corrupted("SkipSegmentation")
        nodes["repeat.refinement"]["repeat"]["sharing"] = "shared"
        with self.assertRaisesRegex(AssertionError, "repeat/sharing differs"):
            check_holdout(copy, "SkipSegmentation", fixture)

    def test_rejects_merged_call_identity_on_shared_instance(self):
        copy, fixture, nodes = self.corrupted("TemporalForecaster")
        nodes["projection@2"]["callId"] = nodes["projection"]["callId"]
        with self.assertRaisesRegex(AssertionError, "call identity missing/duplicated"):
            check_holdout(copy, "TemporalForecaster", fixture)

    def test_rejects_converted_unknown_to_registered_semantics(self):
        copy, fixture, nodes = self.corrupted("GraphForecast")
        nodes["message"]["kind"], nodes["message"]["category"], nodes["message"]["evidence"] = "MultiheadAttention", "attention", "contract"
        with self.assertRaisesRegex(AssertionError, "kind differs"):
            check_holdout(copy, "GraphForecast", fixture)

    def test_rejects_invented_internal_child_of_opaque_boundary(self):
        copy, fixture, nodes = self.corrupted("DynamicStateSpace")
        nodes["DynamicLoop"]["children"].append(nodes["scan"]["id"])
        with self.assertRaisesRegex(AssertionError, "complete containment differs"):
            check_holdout(copy, "DynamicStateSpace", fixture)

    def test_rejects_opaque_constructor_argument_change(self):
        copy, fixture, nodes = self.corrupted("UnsupportedVision")
        nodes["mixer.mixer"]["parameters"]["arg0"] = 32
        with self.assertRaisesRegex(AssertionError, "parameters differs"):
            check_holdout(copy, "UnsupportedVision", fixture)

    def test_rejects_missing_required_unknown_diagnostic(self):
        copy, fixture, _ = self.corrupted("GraphForecast")
        copy["diagnostics"] = [item for item in copy["diagnostics"] if "Unknown constructor" not in item["message"]]
        with self.assertRaisesRegex(AssertionError, "warning inventory differs"):
            check_holdout(copy, "GraphForecast", fixture)

    def test_rejects_wrong_source_digest_or_expression(self):
        copy, fixture, _ = self.corrupted("TemporalForecaster")
        copy["sources"][0]["digest"] = "0" * 64
        with self.assertRaisesRegex(AssertionError, "source SHA differs"):
            check_holdout(copy, "TemporalForecaster", fixture)
        copy, fixture, nodes = self.corrupted("TemporalForecaster")
        nodes["projection"]["source"]["expression"] = "self.recurrent(series)"
        with self.assertRaisesRegex(AssertionError, "authored node occurrence"):
            check_holdout(copy, "TemporalForecaster", fixture)


if __name__ == "__main__":
    unittest.main()
