from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from archcanvas_core.graph_delta import GraphDeltaValidator, architecture_diff
from archcanvas_core.models.architecture import EdgeKind
from archcanvas_core.models.patch import InsertLayerNormPatch, PatchSet, RemoveLayerNormPatch
from archcanvas_python.transactions.insert_layer_norm import plan_insert_layer_norm
from archcanvas_python.transactions.remove_layer_norm import plan_remove_layer_norm
from archcanvas_python.transactions.set_parameter import TransactionRejected
from archcanvas_python.transforms.insert_layer_norm import apply_insert_layer_norm
from archcanvas_python.transforms.remove_layer_norm import apply_remove_layer_norm
from archcanvas_python.transforms.set_parameter import TransformRejected
from archcanvas_pytorch.static import PyTorchStaticAdapter

ROOT = Path(__file__).resolve().parents[2]

CHAIN_SOURCE = (ROOT / "fixtures/structural_embedding_encoder_v1/source/model.py").read_bytes()


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


def _remove_patch(source, architecture) -> RemoveLayerNormPatch:
    removed = next(node for node in architecture.nodes if node.display_name == "insert_norm")
    constructor = next(
        anchor for anchor in source.anchors if anchor.anchor_id.endswith(".insert_norm.constructor")
    )
    forward = next(
        anchor
        for anchor in source.anchors
        if ".forward.edge." in anchor.anchor_id and anchor.anchor_id.endswith(".insert_norm")
    )
    return RemoveLayerNormPatch(
        patch_id="patch:stage8-remove-norm",
        source_node_id="node:encodermodel.layers",
        target_node_id="node:encodermodel.norm",
        removed_node_id=removed.node_id,
        constructor_anchor_id=constructor.anchor_id,
        forward_anchor_id=forward.anchor_id,
        attribute_name="insert_norm",
        constructor_anchor_content_fingerprint=constructor.content_fingerprint,
        forward_anchor_content_fingerprint=forward.content_fingerprint,
        expected_delta={
            "allowed_node_additions": [],
            "allowed_node_removals": [removed.node_id],
            "allowed_node_modifications": [],
            "allowed_edge_additions": ["edge:layers->norm:data"],
            "allowed_edge_removals": [
                "edge:layers->insert_norm:data",
                "edge:insert_norm->norm:data",
            ],
            "allowed_edge_modifications": [],
            "require_identity_retention": True,
        },
    )


def test_insert_layer_norm_supports_the_embedding_to_encoder_fixture_path() -> None:
    source, architecture = PyTorchStaticAdapter().analyze(
        CHAIN_SOURCE,
        project_id="project:stage8-chain",
        relative_file="model.py",
        entrypoint="model.py:ChainModel",
    )
    embedding = next(node for node in architecture.nodes if node.display_name == "embedding")
    encoder = next(node for node in architecture.nodes if node.display_name == "encoder")
    constructor = next(anchor for anchor in source.anchors if anchor.anchor_id.endswith(".encoder.constructor"))
    forward = next(anchor for anchor in source.anchors if anchor.anchor_id.endswith(".embedding.encoder"))
    patch = InsertLayerNormPatch(
        patch_id="patch:stage8-chain-insert-norm",
        source_node_id=embedding.node_id,
        target_node_id=encoder.node_id,
        constructor_anchor_id=constructor.anchor_id,
        forward_anchor_id=forward.anchor_id,
        attribute_name="insert_norm",
        normalized_shape=16,
        constructor_anchor_content_fingerprint=constructor.content_fingerprint,
        forward_anchor_content_fingerprint=forward.content_fingerprint,
        expected_delta={
            "allowed_node_additions": ["node:chainmodel.insert_norm"],
            "allowed_node_removals": [],
            "allowed_node_modifications": [],
            "allowed_edge_additions": [
                "edge:embedding->insert_norm:data",
                "edge:insert_norm->encoder:data",
            ],
            "allowed_edge_removals": ["edge:embedding->encoder:data"],
            "allowed_edge_modifications": [],
            "require_identity_retention": True,
        },
    )
    result = apply_insert_layer_norm(
        CHAIN_SOURCE,
        patch,
        constructor,
        forward,
        source.file_revisions["model.py"],
    )
    _, after_architecture = PyTorchStaticAdapter().analyze(
        result.output_bytes,
        project_id="project:stage8-chain",
        relative_file="model.py",
        entrypoint="model.py:ChainModel",
        previous_source=source,
    )
    report = GraphDeltaValidator().validate(patch.expected_delta, architecture_diff(architecture, after_architecture))

    assert b"self.insert_norm = nn.LayerNorm(16)" in result.output_bytes
    assert b"x = self.insert_norm(x)\n        x = self.encoder(x)" in result.output_bytes
    assert not report.blocking


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


def test_structural_patch_rejects_an_overbroad_allowed_delta() -> None:
    raw, source, architecture = _before()
    patch = _patch(source, architecture)
    overbroad = patch.model_copy(update={
        "expected_delta": patch.expected_delta.model_copy(update={
            "allowed_edge_additions": [*patch.expected_delta.allowed_edge_additions, "edge:unrelated->node:data"],
        }),
    })
    patch_set = PatchSet(
        patch_set_id="patchset:stage8-overbroad", project_id="project:stage8-fixture",
        base_source_revision=source.file_revisions["model.py"],
        created_at=datetime(2026, 9, 22, tzinfo=UTC), created_by="user", patches=[overbroad],
    )
    with pytest.raises(TransactionRejected, match="STRUCTURAL_DELTA_DECLARATION_MISMATCH"):
        plan_insert_layer_norm(
            raw, patch_set, source, architecture,
            analyzer=lambda output: PyTorchStaticAdapter().analyze(
                output, project_id="project:stage8-fixture", relative_file="model.py",
                entrypoint="model.py:EncoderModel", previous_source=source,
            ),
        )


def test_remove_layer_norm_reverses_the_verified_splice() -> None:
    raw, source, architecture = _before()
    insert = _patch(source, architecture)
    constructor = next(anchor for anchor in source.anchors if anchor.anchor_id == insert.constructor_anchor_id)
    forward = next(anchor for anchor in source.anchors if anchor.anchor_id == insert.forward_anchor_id)
    inserted = apply_insert_layer_norm(raw, insert, constructor, forward, source.file_revisions["model.py"])
    inserted_source, inserted_ir = PyTorchStaticAdapter().analyze(
        inserted.output_bytes, project_id="project:stage8-fixture", relative_file="model.py",
        entrypoint="model.py:EncoderModel", previous_source=source,
    )
    patch = _remove_patch(inserted_source, inserted_ir)
    patch_set = PatchSet(
        patch_set_id="patchset:stage8-remove-norm", project_id="project:stage8-fixture",
        base_source_revision=inserted_source.file_revisions["model.py"], created_at=datetime(2026, 9, 22, tzinfo=UTC),
        created_by="user", patches=[patch],
    )
    candidate = plan_remove_layer_norm(
        inserted.output_bytes, patch_set, inserted_source, inserted_ir,
        analyzer=lambda output: PyTorchStaticAdapter().analyze(
            output, project_id="project:stage8-fixture", relative_file="model.py",
            entrypoint="model.py:EncoderModel", previous_source=inserted_source,
        ),
    )
    assert candidate.candidate_bytes == raw
    assert candidate.diff.count("@@ ") == 2


@pytest.mark.parametrize("mutation", ["extra_consumer", "wrong_kind", "unproven_target"])
def test_remove_layer_norm_requires_an_exclusive_source_proven_data_chain(mutation: str) -> None:
    raw, source, architecture = _before()
    insert = _patch(source, architecture)
    constructor = next(anchor for anchor in source.anchors if anchor.anchor_id == insert.constructor_anchor_id)
    forward = next(anchor for anchor in source.anchors if anchor.anchor_id == insert.forward_anchor_id)
    inserted = apply_insert_layer_norm(raw, insert, constructor, forward, source.file_revisions["model.py"])
    inserted_source, inserted_ir = PyTorchStaticAdapter().analyze(
        inserted.output_bytes, project_id="project:stage8-fixture", relative_file="model.py",
        entrypoint="model.py:EncoderModel", previous_source=source,
    )
    patch = _remove_patch(inserted_source, inserted_ir)
    edges = list(inserted_ir.edges)
    incoming = next(edge for edge in edges if edge.target_node_id == patch.removed_node_id)
    outgoing = next(edge for edge in edges if edge.source_node_id == patch.removed_node_id)
    if mutation == "extra_consumer":
        head_input = inserted_ir.node("node:encodermodel.head").input_ports[0].port_id
        edges.append(outgoing.model_copy(update={
            "edge_id": "edge:insert_norm->head:data", "target_node_id": "node:encodermodel.head",
            "target_port_id": head_input,
        }))
    elif mutation == "wrong_kind":
        edges = [edge.model_copy(update={"kind": EdgeKind.RESIDUAL}) if edge == incoming else edge for edge in edges]
    else:
        edges = [edge.model_copy(update={"evidence": []}) if edge == outgoing else edge for edge in edges]
    altered_ir = inserted_ir.model_copy(update={"edges": edges})
    patch_set = PatchSet(
        patch_set_id="patchset:stage8-remove-unproven", project_id="project:stage8-fixture",
        base_source_revision=inserted_source.file_revisions["model.py"],
        created_at=datetime(2026, 9, 22, tzinfo=UTC), created_by="user", patches=[patch],
    )
    expected = "REMOVE_TARGET_EDGE_UNPROVEN" if mutation == "unproven_target" else "REMOVE_LINEAR_SPLICE_NOT_PROVEN"
    with pytest.raises(TransactionRejected, match=expected):
        plan_remove_layer_norm(
            inserted.output_bytes, patch_set, inserted_source, altered_ir,
            analyzer=lambda _: (inserted_source, inserted_ir),
        )


@pytest.mark.parametrize("mutation", ["duplicate", "residual"])
def test_insert_layer_norm_requires_one_direct_data_edge(mutation: str) -> None:
    raw, source, architecture = _before()
    patch = _patch(source, architecture)
    edge = next(edge for edge in architecture.edges if edge.source_node_id == patch.source_node_id and edge.target_node_id == patch.target_node_id)
    edges = list(architecture.edges)
    if mutation == "duplicate":
        edges.append(edge.model_copy(update={"edge_id": "edge:layers->norm:second"}))
    else:
        edges = [item.model_copy(update={"kind": EdgeKind.RESIDUAL}) if item == edge else item for item in edges]
    altered_ir = architecture.model_copy(update={"edges": edges})
    patch_set = PatchSet(
        patch_set_id="patchset:stage8-insert-unproven", project_id="project:stage8-fixture",
        base_source_revision=source.file_revisions["model.py"],
        created_at=datetime(2026, 9, 22, tzinfo=UTC), created_by="user", patches=[patch],
    )
    with pytest.raises(TransactionRejected, match="INSERT_DIRECT_EDGE_NOT_UNIQUE"):
        plan_insert_layer_norm(
            raw, patch_set, source, altered_ir, analyzer=lambda _: (source, architecture),
        )


def test_remove_layer_norm_rejects_a_non_identity_local_call() -> None:
    raw, source, architecture = _before()
    insert = _patch(source, architecture)
    constructor = next(anchor for anchor in source.anchors if anchor.anchor_id == insert.constructor_anchor_id)
    forward = next(anchor for anchor in source.anchors if anchor.anchor_id == insert.forward_anchor_id)
    inserted = apply_insert_layer_norm(raw, insert, constructor, forward, source.file_revisions["model.py"])
    changed = inserted.output_bytes.replace(b"x = self.insert_norm(x)", b"x = self.insert_norm(tokens)")
    changed_source, changed_ir = PyTorchStaticAdapter().analyze(
        changed,
        project_id="project:stage8-fixture",
        relative_file="model.py",
        entrypoint="model.py:EncoderModel",
        previous_source=source,
    )
    patch = _remove_patch(changed_source, changed_ir)
    constructor = next(anchor for anchor in changed_source.anchors if anchor.anchor_id == patch.constructor_anchor_id)
    forward = next(anchor for anchor in changed_source.anchors if anchor.anchor_id == patch.forward_anchor_id)

    with pytest.raises(TransformRejected, match="REMOVE_FORWARD_ARGUMENT_UNSUPPORTED"):
        apply_remove_layer_norm(changed, patch, constructor, forward, changed_source.file_revisions["model.py"])


def test_remove_layer_norm_requires_the_declared_forward_edge_evidence() -> None:
    raw, source, architecture = _before()
    insert = _patch(source, architecture)
    constructor = next(anchor for anchor in source.anchors if anchor.anchor_id == insert.constructor_anchor_id)
    forward = next(anchor for anchor in source.anchors if anchor.anchor_id == insert.forward_anchor_id)
    inserted = apply_insert_layer_norm(raw, insert, constructor, forward, source.file_revisions["model.py"])
    inserted_source, inserted_ir = PyTorchStaticAdapter().analyze(
        inserted.output_bytes,
        project_id="project:stage8-fixture",
        relative_file="model.py",
        entrypoint="model.py:EncoderModel",
        previous_source=source,
    )
    patch = _remove_patch(inserted_source, inserted_ir)
    unrelated = next(anchor for anchor in inserted_source.anchors if anchor.anchor_id.endswith(".norm.head"))
    patch = patch.model_copy(
        update={
            "forward_anchor_id": unrelated.anchor_id,
            "forward_anchor_content_fingerprint": unrelated.content_fingerprint,
        }
    )
    patch_set = PatchSet(
        patch_set_id="patchset:stage8-remove-wrong-forward",
        project_id="project:stage8-fixture",
        base_source_revision=inserted_source.file_revisions["model.py"],
        created_at=datetime(2026, 9, 22, tzinfo=UTC),
        created_by="user",
        patches=[patch],
    )

    with pytest.raises(TransactionRejected, match="REMOVE_FORWARD_EDGE_MISMATCH"):
        plan_remove_layer_norm(
            inserted.output_bytes,
            patch_set,
            inserted_source,
            inserted_ir,
            analyzer=lambda output: PyTorchStaticAdapter().analyze(
                output,
                project_id="project:stage8-fixture",
                relative_file="model.py",
                entrypoint="model.py:EncoderModel",
                previous_source=inserted_source,
            ),
        )
