from __future__ import annotations

import tempfile
from datetime import UTC, datetime
from pathlib import Path

import pytest

from archcanvas_core.models.patch import PatchSet
from archcanvas_python.transactions.set_parameter import TransactionRejected, plan_set_parameter
from archcanvas_pytorch.static import PyTorchProjectScanner, PyTorchProjectStaticAdapter

SOURCE = b'''import torch.nn as nn


class EncoderModel(nn.Module):
    def __init__(self):
        super().__init__()
        self.layers = nn.ModuleList([
            nn.TransformerEncoderLayer(
                d_model=256,
                nhead=8,
                dropout=0.1,
                activation="relu",
                batch_first=True,
            )
            for _ in range(2)
        ])
        self.norm = nn.LayerNorm(256)
        self.head = nn.Linear(256, 4)

    def forward(self, tokens):
        x = tokens
        for layer in self.layers:
            x = layer(x)
        return self.head(self.norm(x).mean(dim=1))
'''


def _analyze(raw: bytes):
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        (root / "model.py").write_bytes(raw)
        return PyTorchProjectStaticAdapter(project_scanner=PyTorchProjectScanner()).analyze(
            root,
            project_id="project:registered-transform",
            entrypoint="model.py:EncoderModel",
            resolved_config={},
        )


def _patch_set(source, architecture, parameter: str, after: object) -> PatchSet:
    node = next(node for node in architecture.nodes if node.node_id.endswith(".layers"))
    current = next(item for item in node.parameters if item.name == parameter)
    anchor_id = next(anchor for anchor in node.source_anchor_ids if anchor.endswith(".constructor"))
    anchor = next(item for item in source.anchors if item.anchor_id == anchor_id)
    return PatchSet.model_validate(
        {
            "patch_set_id": f"patchset:registered-{parameter}",
            "project_id": "project:registered-transform",
            "base_source_revision": source.file_revisions["model.py"],
            "created_at": datetime(2026, 9, 22, tzinfo=UTC),
            "created_by": "user",
            "patches": [{
                "patch_id": f"patch:registered-{parameter}",
                "target": {"node_id": node.node_id, "parameter": parameter, "anchor_id": anchor_id},
                "before": current.value,
                "after": after,
                "anchor_content_fingerprint": anchor.content_fingerprint,
                "expected_delta": {
                    "required_parameter_changes": [{
                        "node_id": node.node_id, "parameter": parameter,
                        "before": current.value, "after": after,
                    }],
                    "allowed_node_additions": [], "allowed_node_removals": [],
                    "allowed_node_modifications": [], "allowed_edge_additions": [],
                    "allowed_edge_removals": [], "allowed_edge_modifications": [],
                    "require_identity_retention": True,
                },
            }],
        }
    )


@pytest.mark.parametrize(
    ("parameter", "after"),
    [("dropout", 0.2), ("activation", "gelu")],
)
def test_registered_literal_parameter_round_trip(parameter: str, after: object) -> None:
    source, architecture = _analyze(SOURCE)
    patch_set = _patch_set(source, architecture, parameter, after)
    candidate = plan_set_parameter(
        SOURCE,
        patch_set,
        source,
        architecture,
        analyzer=lambda raw: _analyze(raw),
    )

    assert candidate.diff.count("@@ ") == 1
    assert candidate.observed_delta.parameter_changes[0].parameter == parameter
    assert candidate.observed_delta.parameter_changes[0].after == after
    assert not candidate.blocking


@pytest.mark.parametrize(
    ("parameter", "after", "code"),
    [
        ("d_model", 512, "PATCH_RUNTIME_VALIDATION_REQUIRED"),
        ("num_heads", 7, "PARAMETER_RELATION_INVALID"),
        ("activation", "silu", "PARAMETER_VALUE_INVALID"),
    ],
)
def test_registered_transform_rejects_unsafe_or_incompatible_values(
    parameter: str, after: object, code: str
) -> None:
    source, architecture = _analyze(SOURCE)
    with pytest.raises(TransactionRejected) as rejected:
        plan_set_parameter(
            SOURCE,
            _patch_set(source, architecture, parameter, after),
            source,
            architecture,
            analyzer=lambda raw: _analyze(raw),
        )
    assert rejected.value.code == code


def test_hidden_size_candidate_requires_registered_runtime_validation() -> None:
    source, architecture = _analyze(SOURCE)
    candidate = plan_set_parameter(
        SOURCE,
        _patch_set(source, architecture, "d_model", 512),
        source,
        architecture,
        analyzer=lambda raw: _analyze(raw),
        runtime_validation_available=True,
    )
    assert candidate.observed_delta.parameter_changes[0].parameter == "d_model"
