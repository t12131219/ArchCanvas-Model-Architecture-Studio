"""Complete source-authored base-model checks and deliberate corruption probes."""

from collections import Counter, defaultdict
from copy import deepcopy
import hashlib
from pathlib import Path
import unittest

from archcanvas_python import analyze_project

from m4_base_model_oracle import BASE_MODELS


ROOT = Path(__file__).resolve().parents[1]


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def named_nodes(architecture, expected):
    """Resolve authored members/call occurrences, never by display order."""
    prefix = "instance:" + expected["entry"].replace(":", ".")
    names, nodes, operators = {}, {}, []
    for value in architecture["nodes"]:
        identity = value["id"]
        require(identity not in names, "duplicate node identity: " + identity)
        instance = value.get("instanceId", "")
        if instance == prefix:
            name = "root"
        elif instance.startswith(prefix + "."):
            name = instance[len(prefix) + 1:]
            if "@" in identity:
                name += "@" + identity.rsplit("@", 1)[1]
        elif value["kind"] == "Input":
            name = "input." + value["label"]
        elif value["kind"] == "Output":
            name = "output"
        elif value["kind"] == "Repeat":
            name = "repeat." + value["label"]
        else:
            operators.append(value)
            continue
        require(name not in nodes, "ambiguous authored node: " + name)
        names[identity], nodes[name] = name, value
    for value in operators:
        require(value["kind"] == "Add" and value["source"]["expression"] == "x + residual",
                "unexpected source operation")
        parent = names.get(value.get("parentId"))
        require(parent in ("blocks.0", "blocks.1"), "unexpected Add containment")
        name = parent + ".add"
        require(name not in nodes and value["id"] not in names, "duplicate Add occurrence")
        names[value["id"]], nodes[name] = name, value
    require(set(nodes) == set(expected["nodes"]), "complete authored node inventory differs")
    return names, nodes


def check_base_model(architecture, model_name, fixture_root):
    """Compare every node, port, binding, tensor producer and hierarchy fact."""
    expected = BASE_MODELS[model_name]
    require(architecture["entry"] == expected["entry"], "entry differs")
    sources = {source["path"]: source for source in architecture["sources"]}
    require(tuple(sources) == expected["sources"], "complete source inventory differs")
    require(len(sources) == len(architecture["sources"]), "duplicate source")
    for path, source in sources.items():
        raw = (fixture_root / path).read_bytes()
        require(raw.decode("utf-8") == source["content"], "source content differs: " + path)
        require(hashlib.sha256(raw).hexdigest() == source["digest"], "source SHA differs: " + path)
    require(not [item for item in architecture["diagnostics"] if item["level"] in ("warning", "error")],
            "base model has unresolved diagnostics")
    names, nodes = named_nodes(architecture, expected)
    ports = {}
    calls, instance_calls = set(), defaultdict(list)
    for name, value in nodes.items():
        authored = expected["nodes"][name]
        for field in ("kind", "category", "evidence", "parameters"):
            require(value[field] == authored[field], name + ": " + field + " differs")
        parent = names.get(value.get("parentId"))
        require(parent == authored["parent"] and (value.get("parentId") is None or value["parentId"] in names),
                name + ": parent differs")
        children = value["children"]
        require(all(child in names for child in children), name + ": dangling child")
        require(tuple(names[child] for child in children) == expected["children"].get(name, ()),
                name + ": complete ordered children differ")
        require(value.get("repeat") == authored["repeat"], name + ": repeat/sharing differs")
        facts = tuple((port["name"], port["direction"], port["role"], port["ordinal"]) for port in value["ports"])
        require(facts == authored["ports"], name + ": complete port contract differs")
        for port in value["ports"]:
            key = (value["id"], port["id"])
            require(key not in ports, name + ": duplicate local port identity")
            ports[key] = port
        source = value["source"]
        require(source["path"] == authored["sourcePath"], name + ": source path differs")
        lines = sources[source["path"]]["content"].splitlines()
        require(1 <= source["line"] <= source["endLine"] <= len(lines), name + ": invalid source range")
        require(source["expression"] in "\n".join(lines[source["line"] - 1:source["endLine"]]),
                name + ": expression not present in source range")
        if authored["expression"] is not None:
            require(source["expression"] == authored["expression"], name + ": authored expression differs")
        if authored["instance"] is not None:
            member = authored["instance"]
            wanted = "instance:" + expected["entry"].replace(":", ".") + ("." + member if member != "root" else "")
            require(value.get("instanceId") == wanted, name + ": instance identity differs")
            call = value.get("callId")
            require(isinstance(call, str) and call and call not in calls, name + ": call identity is missing/duplicated")
            calls.add(call)
            instance_calls[wanted].append(name)
        else:
            require("instanceId" not in value and "callId" not in value, name + ": invented instance/call")
        if name == "output":
            require(value.get("outputPath") == [], "single tensor return path differs")
        else:
            require("outputPath" not in value, name + ": invented return slot")
    require(len(calls) == expected["callCount"], "complete call count differs")
    require(len(instance_calls) == expected["instanceCount"], "complete independent/shared instance count differs")

    relations, edge_ids = [], set()
    producer_tensors, tensor_producers, tensor_consumers = {}, {}, defaultdict(list)
    for edge in architecture["edges"]:
        require(edge["id"] not in edge_ids, "duplicate edge identity")
        edge_ids.add(edge["id"])
        source, target = edge["source"], edge["target"]
        source_key, target_key = (source["nodeId"], source["portId"]), (target["nodeId"], target["portId"])
        require(source_key in ports, "source binding uses a foreign or missing local port")
        require(target_key in ports, "target binding uses a foreign or missing local port")
        source_port, target_port = ports[source_key], ports[target_key]
        require(source_port["direction"] == "out" and target_port["direction"] == "in", "edge direction differs")
        require(edge["role"] == target_port["role"], "edge role differs from consumer port")
        producer = (names[source["nodeId"]], source_port["name"])
        consumer = (names[target["nodeId"]], target_port["name"])
        relation = (*producer, *consumer, edge["role"])
        relations.append(relation)
        tensor = edge["tensorId"]
        require(isinstance(tensor, str) and tensor, "missing tensor identity")
        require(producer_tensors.get(producer, tensor) == tensor, "one producer split into multiple tensor identities")
        require(tensor_producers.get(tensor, producer) == producer, "two producers merged into one tensor identity")
        producer_tensors[producer], tensor_producers[tensor] = tensor, producer
        tensor_consumers[tensor].append((*consumer, edge["role"]))
    require(Counter(relations) == Counter(expected["relations"]), "complete producer/port relations differ")
    require(len(tensor_producers) == expected["tensorCount"], "complete tensor producer inventory differs")
    return {
        "nodeCount": len(nodes), "edgeCount": len(relations), "tensorCount": len(tensor_producers),
        "portCount": len(ports), "callCount": len(calls), "instanceCount": len(instance_calls),
        "nodes": sorted(nodes), "relations": sorted(relations),
        "tensors": [{"producer": producer, "consumers": sorted(tensor_consumers[tensor])}
                    for producer, tensor in sorted(producer_tensors.items())],
        "instanceCalls": {key: sorted(values) for key, values in sorted(instance_calls.items())},
    }


class M4BaseModelTests(unittest.TestCase):
    def analyzed(self, name):
        expected = BASE_MODELS[name]
        fixture = ROOT / "fixtures" / expected["fixture"]
        architecture = analyze_project(fixture, expected["entry"])
        check_base_model(architecture, name, fixture)
        return architecture, fixture

    def corrupted(self, name):
        architecture, fixture = self.analyzed(name)
        copy = deepcopy(architecture)
        _, nodes = named_nodes(copy, BASE_MODELS[name])
        return copy, fixture, nodes

    def test_mlp_complete_node_port_tensor_containment_oracle(self):
        self.analyzed("MLP")

    def test_cnn_complete_node_port_tensor_containment_repeat_oracle(self):
        self.analyzed("ResidualCNN")

    def test_checker_rejects_wrong_add_target_port(self):
        copy, fixture, nodes = self.corrupted("ResidualCNN")
        add = nodes["blocks.0.add"]
        edge = next(edge for edge in copy["edges"] if edge["target"]["nodeId"] == add["id"] and edge["role"] == "residual")
        edge["target"]["portId"] = next(port["id"] for port in add["ports"] if port["name"] == "left")
        with self.assertRaisesRegex(AssertionError, "edge role differs"):
            check_base_model(copy, "ResidualCNN", fixture)

    def test_checker_rejects_valid_port_from_wrong_producer(self):
        copy, fixture, nodes = self.corrupted("ResidualCNN")
        edge = next(edge for edge in copy["edges"] if edge["target"]["nodeId"] == nodes["blocks.1.add"]["id"] and edge["role"] == "residual")
        donor = next(edge for edge in copy["edges"] if edge["source"]["nodeId"] == nodes["stem"]["id"])
        edge["source"], edge["tensorId"] = deepcopy(donor["source"]), donor["tensorId"]
        with self.assertRaisesRegex(AssertionError, "complete producer/port relations differ"):
            check_base_model(copy, "ResidualCNN", fixture)

    def test_checker_rejects_foreign_port_even_with_same_name(self):
        copy, fixture, nodes = self.corrupted("MLP")
        edge = next(edge for edge in copy["edges"] if edge["target"]["nodeId"] == nodes["network.1"]["id"])
        edge["target"]["portId"] = next(port["id"] for port in nodes["network.2"]["ports"] if port["name"] == "input")
        with self.assertRaisesRegex(AssertionError, "foreign or missing local port"):
            check_base_model(copy, "MLP", fixture)

    def test_checker_rejects_split_tensor_at_sequential_adapter(self):
        copy, fixture, nodes = self.corrupted("MLP")
        edge = next(edge for edge in copy["edges"] if edge["target"]["nodeId"] == nodes["network"]["id"] and edge["source"]["nodeId"] == nodes["network.3"]["id"])
        edge["tensorId"] += ":invented-boundary"
        with self.assertRaisesRegex(AssertionError, "one producer split"):
            check_base_model(copy, "MLP", fixture)

    def test_checker_rejects_merged_tensor_producers(self):
        copy, fixture, nodes = self.corrupted("MLP")
        incoming = next(edge for edge in copy["edges"] if edge["source"]["nodeId"] == nodes["network.0"]["id"])
        outgoing = next(edge for edge in copy["edges"] if edge["source"]["nodeId"] == nodes["network.1"]["id"])
        outgoing["tensorId"] = incoming["tensorId"]
        with self.assertRaisesRegex(AssertionError, "two producers merged"):
            check_base_model(copy, "MLP", fixture)

    def test_checker_rejects_extra_unbound_port(self):
        copy, fixture, nodes = self.corrupted("MLP")
        nodes["network.2"]["ports"].append({"id": "invented", "name": "extra", "direction": "out", "role": "data", "ordinal": 1})
        with self.assertRaisesRegex(AssertionError, "complete port contract differs"):
            check_base_model(copy, "MLP", fixture)

    def test_checker_rejects_wrong_complete_containment(self):
        copy, fixture, nodes = self.corrupted("ResidualCNN")
        nodes["blocks.0"]["children"].remove(nodes["blocks.0.conv2"]["id"])
        with self.assertRaisesRegex(AssertionError, "complete ordered children differ"):
            check_base_model(copy, "ResidualCNN", fixture)

    def test_checker_rejects_false_independent_activation_instances(self):
        copy, fixture, nodes = self.corrupted("ResidualCNN")
        nodes["blocks.0.activation@2"]["instanceId"] += "_independent"
        with self.assertRaisesRegex(AssertionError, "complete authored node inventory differs"):
            check_base_model(copy, "ResidualCNN", fixture)

    def test_checker_rejects_false_repeat_count(self):
        copy, fixture, nodes = self.corrupted("ResidualCNN")
        nodes["repeat.blocks"]["repeat"]["count"] = 3
        with self.assertRaisesRegex(AssertionError, "repeat/sharing differs"):
            check_base_model(copy, "ResidualCNN", fixture)


if __name__ == "__main__":
    unittest.main()
