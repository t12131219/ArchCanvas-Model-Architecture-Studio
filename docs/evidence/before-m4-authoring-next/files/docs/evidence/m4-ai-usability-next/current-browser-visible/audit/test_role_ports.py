"""Independent multi-role canonical port counterexamples."""
import unittest
from check_directional_roles_v3 import svg_snapshot
from test_directional import sample


class RolePortCounterexamples(unittest.TestCase):
    def text(self):
        return sample().replace('<g data-edge-id="e"', '<g data-port-id="input:input-out:residual" data-node-id="input"><circle cx="90" cy="30" r="2.6"/></g><g data-edge-id="e"')

    def test_binding_role_selects_actual_scene_port(self):
        scene = svg_snapshot(self.text())
        self.assertEqual(scene["endpointChecks"][0]["scenePort"], "input:input-out:data")

    def test_wrong_role_endpoint_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "detached"):
            svg_snapshot(self.text().replace('d="M 70 30', 'd="M 90 30'))

    def test_missing_declared_role_port_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Ambiguous/missing"):
            svg_snapshot(sample().replace("input:input-out:data", "input:input-out:residual"))
