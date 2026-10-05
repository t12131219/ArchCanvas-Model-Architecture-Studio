"""Independent counterexamples for conservative M4 static boundaries.

These snippets are source data.  They are intentionally never imported or
executed; each assertion checks that an uncertain region cannot retain a
previously inferred contract or invent tensor slots.
"""

import unittest

from archcanvas_python import analyze_source


def nodes(graph, kind=None):
    return [item for item in graph["nodes"] if kind is None or item["kind"] == kind]


class UnknownBoundaryTests(unittest.TestCase):
    def test_conditional_initializer_does_not_leave_stale_contract(self):
        source = '''from torch import nn
class Plugin:
    pass
class Model(nn.Module):
    def __init__(self, enabled=True):
        super().__init__()
        self.project = nn.Linear(4, 4)
        if enabled:
            self.project = Plugin()
        self.shared = nn.ReLU()
    def forward(self, x):
        return self.shared(self.project(x))
'''
        graph = analyze_source(source, "Model")
        project = next(item for item in nodes(graph) if item.get("instanceId") == "instance:model.Model.project")
        self.assertEqual((project["category"], project["evidence"]), ("opaque", "opaque"))
        self.assertEqual(sum(item["kind"] == "ReLU" for item in nodes(graph)), 1)
        self.assertTrue(any("Unknown constructor" in item["message"] for item in graph["diagnostics"]))

    def test_known_constant_branch_keeps_only_selected_constructor(self):
        source = '''from torch import nn
class Model(nn.Module):
    def __init__(self):
        super().__init__()
        self.project = nn.Linear(4, 4)
        if False:
            self.project = nn.ReLU()
    def forward(self, x):
        return self.project(x)
'''
        graph = analyze_source(source, "Model")
        self.assertEqual([(item["kind"], item["evidence"]) for item in nodes(graph)
                          if item.get("instanceId") == "instance:model.Model.project"],
                         [("Linear", "contract")])

    def test_unknown_direct_reassignment_replaces_prior_contract(self):
        source = '''from torch import nn
class Model(nn.Module):
    def __init__(self):
        super().__init__()
        self.project = nn.Linear(4, 4)
        self.project = plugin_factory()
    def forward(self, x):
        return self.project(x)
'''
        graph = analyze_source(source, "Model")
        project = next(item for item in nodes(graph) if item.get("instanceId") == "instance:model.Model.project")
        self.assertEqual((project["category"], project["evidence"]), ("opaque", "opaque"))
        self.assertFalse(nodes(graph, "Linear"))

    def test_unknown_conditional_write_invalidates_only_affected_attribute(self):
        source = '''from torch import nn
class Model(nn.Module):
    def __init__(self, enabled):
        super().__init__()
        self.project = nn.Linear(4, 4)
        self.sibling = nn.ReLU()
        if enabled:
            self.project = nn.GELU()
    def forward(self, x):
        return self.sibling(self.project(x))
'''
        graph = analyze_source(source, "Model")
        project = next(item for item in nodes(graph) if item.get("instanceId") == "instance:model.Model.project")
        sibling = next(item for item in nodes(graph) if item.get("instanceId") == "instance:model.Model.sibling")
        self.assertEqual((project["category"], project["evidence"]), ("opaque", "opaque"))
        self.assertEqual((sibling["kind"], sibling["evidence"]), ("ReLU", "contract"))
        self.assertFalse(nodes(graph, "Linear"))
        self.assertFalse(nodes(graph, "GELU"))
        self.assertTrue(any("affected attributes (project)" in item["message"] for item in graph["diagnostics"]))

    def test_direct_constructor_after_unknown_branch_restores_contract(self):
        source = '''from torch import nn
class Model(nn.Module):
    def __init__(self, enabled):
        super().__init__()
        self.project = nn.Linear(4, 4)
        if enabled:
            self.project = plugin_factory()
        self.project = nn.ReLU()
    def forward(self, x):
        return self.project(x)
'''
        graph = analyze_source(source, "Model")
        project = next(item for item in nodes(graph) if item.get("instanceId") == "instance:model.Model.project")
        self.assertEqual((project["kind"], project["evidence"]), ("ReLU", "contract"))
        self.assertFalse(nodes(graph, "Linear"))

    def test_unknown_mutation_preserves_shared_alias_identity(self):
        source = '''from torch import nn
class Model(nn.Module):
    def __init__(self, enabled):
        super().__init__()
        self.layer = nn.Linear(4, 4)
        self.alias = self.layer
        self.sibling = nn.ReLU()
        if enabled:
            self.layer.weight = plugin_weight()
    def forward(self, x):
        return self.layer(x), self.alias(x), self.sibling(x)
'''
        graph = analyze_source(source, "Model")
        opaque = [item for item in nodes(graph) if item["evidence"] == "opaque"]
        self.assertEqual(len(opaque), 2)
        self.assertEqual({item["instanceId"] for item in opaque}, {"instance:model.Model.layer"})
        self.assertEqual(len({item["callId"] for item in opaque}), 2)
        self.assertFalse(nodes(graph, "Linear"))
        self.assertEqual([(item["kind"], item["evidence"]) for item in nodes(graph)
                          if item.get("instanceId") == "instance:model.Model.sibling"], [("ReLU", "contract")])

    def test_unknown_mutation_invalidates_specs_captured_in_containers(self):
        template = '''from torch import nn
class Model(nn.Module):
    def __init__(self, enabled):
        super().__init__()
        self.layer = nn.Linear(4, 4)
        self.layers = CONSTRUCTION
        if enabled:
            self.layer.weight = plugin_weight()
    def forward(self, x):
        FORWARD
'''
        cases = [("nn.Sequential(self.layer)", "return self.layers(x)"),
                 ("nn.ModuleList([self.layer])", "for layer in self.layers:\n            x = layer(x)\n        return x")]
        for construction, forward in cases:
            with self.subTest(container=construction):
                graph = analyze_source(template.replace("CONSTRUCTION", construction).replace("FORWARD", forward), "Model")
                self.assertFalse(nodes(graph, "Linear"))
                captured = [item for item in nodes(graph) if item.get("instanceId") == "instance:model.Model.layer"]
                self.assertEqual(len(captured), 1)
                self.assertEqual((captured[0]["category"], captured[0]["evidence"]), ("opaque", "opaque"))

    def test_reassignment_does_not_invalidate_old_object_captured_by_container(self):
        source = '''from torch import nn
class Model(nn.Module):
    def __init__(self, enabled):
        super().__init__()
        self.layer = nn.Linear(4, 4)
        self.layers = nn.Sequential(self.layer)
        if enabled:
            self.layer = nn.ReLU()
    def forward(self, x):
        return self.layer(x), self.layers(x)
'''
        graph = analyze_source(source, "Model")
        self.assertEqual(len(nodes(graph, "Linear")), 1)
        self.assertEqual(nodes(graph, "Linear")[0]["evidence"], "contract")
        opaque = [item for item in nodes(graph) if item["evidence"] == "opaque"]
        self.assertEqual(len(opaque), 1)
        self.assertNotEqual(opaque[0]["instanceId"], nodes(graph, "Linear")[0]["instanceId"])

    def test_direct_reassignment_keeps_captured_old_constructor_distinct(self):
        source = '''from torch import nn
class Model(nn.Module):
    def __init__(self):
        super().__init__()
        self.layer = nn.Linear(4, 4)
        self.layers = nn.Sequential(self.layer)
        self.layer = nn.ReLU()
    def forward(self, x):
        return self.layer(x), self.layers(x)
'''
        graph = analyze_source(source, "Model")
        linear, activation = nodes(graph, "Linear")[0], nodes(graph, "ReLU")[0]
        self.assertEqual((linear["evidence"], activation["evidence"]), ("contract", "contract"))
        self.assertNotEqual(linear["instanceId"], activation["instanceId"])
        self.assertEqual(activation["instanceId"], "instance:model.Model.layer")
        self.assertEqual(linear["label"], "layer")
        self.assertNotIn("construction", linear["label"])
        shifted = analyze_source("# comment shifts source lines\n" + source, "Model")
        self.assertEqual(graph["irDigest"], shifted["irDigest"])
        self.assertEqual([item.get("instanceId") for item in nodes(graph)],
                         [item.get("instanceId") for item in nodes(shifted)])

    def test_rebinding_an_alias_does_not_retire_original_owner(self):
        source = '''from torch import nn
class Model(nn.Module):
    def __init__(self):
        super().__init__()
        self.layer = nn.Linear(4, 4)
        self.alias = self.layer
        self.alias = nn.ReLU()
    def forward(self, x):
        return self.layer(x), self.alias(x)
'''
        graph = analyze_source(source, "Model")
        self.assertEqual(nodes(graph, "Linear")[0]["instanceId"], "instance:model.Model.layer")
        self.assertEqual(nodes(graph, "ReLU")[0]["instanceId"], "instance:model.Model.alias")

    def test_multi_target_constructor_rhs_has_one_shared_instance(self):
        source = '''from torch import nn
class Model(nn.Module):
    def __init__(self):
        super().__init__()
        self.left = self.right = nn.Linear(4, 4)
        self.layers = nn.ModuleList([self.left, self.right])
    def forward(self, x):
        for layer in self.layers:
            x = layer(x)
        return self.left(x), self.right(x)
'''
        graph = analyze_source(source, "Model")
        calls = nodes(graph, "Linear")
        self.assertEqual(len(calls), 4)
        self.assertEqual({item["instanceId"] for item in calls}, {"instance:model.Model.left"})
        self.assertEqual(len({item["callId"] for item in calls}), 4)
        self.assertEqual(nodes(graph, "Repeat")[0]["repeat"], {"count": 2, "sharing": "shared"})

    def test_unknown_helper_mutation_invalidates_captured_argument(self):
        source = '''from torch import nn
class Model(nn.Module):
    def __init__(self, enabled):
        super().__init__()
        self.layer = nn.Linear(4, 4)
        self.layers = nn.Sequential(self.layer)
        if enabled:
            mutate_layer(self.layer)
    def forward(self, x):
        return self.layers(x)
'''
        graph = analyze_source(source, "Model")
        self.assertFalse(nodes(graph, "Linear"))
        captured = [item for item in nodes(graph) if item.get("instanceId") == "instance:model.Model.layer"]
        self.assertEqual(len(captured), 1)
        self.assertEqual((captured[0]["category"], captured[0]["evidence"]), ("opaque", "opaque"))

    def test_unknown_rhs_helper_can_mutate_existing_captured_argument(self):
        source = '''from torch import nn
class Model(nn.Module):
    def __init__(self):
        super().__init__()
        self.layer = nn.Linear(4, 4)
        self.layers = nn.Sequential(self.layer)
        self.result = mutate_layer(self.layer)
    def forward(self, x):
        return self.layers(x)
'''
        graph = analyze_source(source, "Model")
        self.assertFalse(nodes(graph, "Linear"))
        captured = [item for item in nodes(graph) if item.get("instanceId") == "instance:model.Model.layer"]
        self.assertEqual(len(captured), 1)
        self.assertEqual((captured[0]["category"], captured[0]["evidence"]), ("opaque", "opaque"))

    def test_modulelist_direct_call_is_opaque(self):
        source = '''from torch import nn
class Model(nn.Module):
    def __init__(self):
        super().__init__()
        self.layers = nn.ModuleList([nn.Linear(4, 4), nn.ReLU()])
    def forward(self, x):
        return self.layers(x)
'''
        graph = analyze_source(source, "Model")
        layer = next(item for item in nodes(graph) if item.get("instanceId") == "instance:model.Model.layers")
        self.assertEqual((layer["category"], layer["evidence"], layer["children"]), ("opaque", "opaque", []))
        self.assertFalse(nodes(graph, "Linear"))
        self.assertTrue(any("ModuleList" in item["message"] for item in graph["diagnostics"]))

    def test_chunk_without_shape_does_not_claim_fixed_output_count(self):
        source = '''from torch import nn
class Model(nn.Module):
    def forward(self, x):
        return x.chunk(3)
'''
        graph = analyze_source(source, "Model")
        self.assertEqual(len(nodes(graph, "Output")), 1)
        boundary = next(item for item in nodes(graph) if item["kind"] == "Chunk")
        self.assertEqual((boundary["category"], boundary["evidence"]), ("opaque", "opaque"))
        self.assertTrue(any("shape" in item["message"] for item in graph["diagnostics"]))

    def test_for_else_and_shadowed_range_are_not_unrolled(self):
        source = '''from torch import nn
class Model(nn.Module):
    def __init__(self):
        super().__init__()
        self.layer = nn.Linear(4, 4)
    def forward(self, x, range):
        for index in range(2):
            x = self.layer(x)
        else:
            x = self.layer(x)
        return x
'''
        graph = analyze_source(source, "Model")
        self.assertEqual(len(nodes(graph, "Linear")), 0)
        self.assertTrue(any(item["kind"] == "DynamicLoop" and item["evidence"] == "opaque"
                            for item in nodes(graph)))

    def test_known_range_else_executes_after_loop_with_shared_calls(self):
        source = '''from torch import nn
class Model(nn.Module):
    def __init__(self):
        super().__init__()
        self.layer = nn.Linear(4, 4)
    def forward(self, x):
        for index in range(1):
            x = self.layer(x)
        else:
            x = self.layer(x)
        return x
'''
        graph = analyze_source(source, "Model")
        calls = nodes(graph, "Linear")
        self.assertEqual(len(calls), 2)
        self.assertEqual({item["instanceId"] for item in calls}, {"instance:model.Model.layer"})
        self.assertEqual(len({item["callId"] for item in calls}), 2)
        self.assertTrue(any(edge["source"]["nodeId"] == calls[0]["id"]
                            and edge["target"]["nodeId"] == calls[1]["id"] for edge in graph["edges"]))

    def test_break_loop_does_not_claim_full_unroll_or_else_execution(self):
        source = '''from torch import nn
class Model(nn.Module):
    def __init__(self):
        super().__init__()
        self.layer = nn.Linear(4, 4)
        self.activation = nn.ReLU()
    def forward(self, x):
        for index in range(2):
            x = self.layer(x)
            break
        else:
            x = self.activation(x)
        return x
'''
        graph = analyze_source(source, "Model")
        self.assertFalse(nodes(graph, "Linear"))
        self.assertFalse(nodes(graph, "ReLU"))
        self.assertEqual([(item["kind"], item["evidence"]) for item in nodes(graph)
                          if item["category"] == "opaque"], [("DynamicLoop", "opaque")])


if __name__ == "__main__":
    unittest.main()
