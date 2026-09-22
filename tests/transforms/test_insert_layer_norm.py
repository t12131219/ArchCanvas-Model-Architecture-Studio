from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from archcanvas_core.graph_delta import GraphDeltaValidator, architecture_diff
from archcanvas_core.models.patch import InsertLayerNormPatch, PatchSet
from archcanvas_python.transactions.insert_layer_norm import plan_insert_layer_norm
from archcanvas_python.transforms.insert_layer_norm import apply_insert_layer_norm
from archcanvas_python.transforms.set_parameter import TransformRejected
from archcanvas_pytorch.static import PyTorchStaticAdapter

ROOT = Path(__file__).resolve().parents[2]


def _before():
    raw = (ROOT / "fixtures/transformer_static_v1/source/model.py").read_bytes()
    source, architecture = PyTorchStaticAdapter().analyze(
        raw, project_id="project:stage8-fixture", relative_file="model.py", entrypoint="model.py:EncoderModel"
    )
    return raw, source, architecture


def _patch(source, architecture) -> InsertLayerNormPatch:
    source_node = next(node for node in architecture.nodes if node.display_name == "layers")
    target_node = next(node for node in architecture.nodes if node.display_name == "norm")
    constructor = next(anchor for anchor in source.anchors if anchor.anchor_id.endswith(".norm.constructor"))
    forward = next(
        anchor for anchor in source.anchors if anchor.anchor_id.endswith(".layers.norm")
    )
    return InsertLayerNormPatch(
        patch_id="patch:stage8-insert-norm",
        source_node_id=source_node.node_id,
        target_node_id=target_node.node_id,
        constructor_anchor_id=constructor.anchor_id,
        forward_anchor_id=forward.anchor_id,
        attribute_name="insert_norm",
        normalized_shape=256,
        constructor_anchor_content_fingerprint=constructor.content_fingerprint,
        forward_anchor_content_fingerprint=forward.content_fingerprint,
        expected_delta={
            "allowed_node_additions": ["node:encodermodel.insert_norm"],
            "allowed_node_removals": [],
            "allowed_node_modifications": [],
            "allowed_edge_additions": [
                "edge:layers->insert_norm:data",
                "edge:insert_norm->norm:data",
            ],
            "allowed_edge_removals": ["edge:layers->norm:data"],
            "allowed_edge_modifications": [],
            "require_identity_retention": True,
        },
    )


def test_insert_layer_norm_splices_one_proven_edge_and_preserves_identities() -> None:
    raw, source, architecture = _before()
    patch = _patch(source, architecture)
    constructor = next(anchor for anchor in source.anchors if anchor.anchor_id == patch.constructor_anchor_id)
    forward = next(anchor for anchor in source.anchors if anchor.anchor_id == patch.forward_anchor_id)
    result = apply_insert_layer_norm(raw, patch, constructor, forward, source.file_revisions["model.py"])
    after_source, after_architecture = PyTorchStaticAdapter().analyze(
        result.output_bytes,
        project_id="project:stage8-fixture",
        relative_file="model.py",
        entrypoint="model.py:EncoderModel",
        previous_source=source,
    )
    observed = architecture_diff(architecture, after_architecture)
    report = GraphDeltaValidator().validate(patch.expected_delta, observed)

    assert b"self.insert_norm = nn.LayerNorm(256)" in result.output_bytes
    assert b"x = self.insert_norm(x)" in result.output_bytes
    assert not report.blocking
    assert observed.identity_changes == []
    assert after_source.source_revision != source.source_revision


def test_insert_layer_norm_rejects_a_changed_forward_anchor() -> None:
    raw, source, architecture = _before()
    patch = _patch(source, architecture)
    constructor = next(anchor for anchor in source.anchors if anchor.anchor_id == patch.constructor_anchor_id)
    forward = next(anchor for anchor in source.anchors if anchor.anchor_id == patch.forward_anchor_id)
    changed = raw.replace(b"x = self.norm(x)", b"x = self.norm(x)  # changed")

    with pytest.raises(TransformRejected, match="STALE_TARGET_FILE_REVISION"):
        apply_insert_layer_norm(changed, patch, constructor, forward, source.file_revisions["model.py"])


def test_insert_layer_norm_transaction_requires_exact_observed_graph_delta() -> None:
    raw, source, architecture = _before()
    patch = _patch(source, architecture)
    patch_set = {
        "patch_set_id": "patchset:stage8-insert-norm",
        "project_id": "project:stage8-fixture",
        "base_source_revision": source.file_revisions["model.py"],
        "created_at": datetime(2026, 9, 22, tzinfo=UTC),
        "created_by": "user",
        "patches": [patch.model_dump(mode="json")],
    }
    candidate = plan_insert_layer_norm(
        raw,
        patch_set=PatchSet.model_validate(patch_set),
        source=source,
        ir=architecture,
        analyzer=lambda output: PyTorchStaticAdapter().analyze(
            output,
            project_id="project:stage8-fixture",
            relative_file="model.py",
            entrypoint="model.py:EncoderModel",
            previous_source=source,
        ),
    )
    assert candidate.diff.count("@@ ") == 2
    assert candidate.observed_delta.added_node_ids == ["node:encodermodel.insert_norm"]
