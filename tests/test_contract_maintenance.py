from __future__ import annotations

from pathlib import Path

import pytest

from archcanvas_core.builtin_registry import BuiltinModuleRegistry
from archcanvas_studio.contract_maintenance import ContractMaintenanceManager


def _candidate(definition, **changes: object) -> dict[str, object]:  # type: ignore[no-untyped-def]
    payload = definition.model_dump(mode="json")
    payload.update(changes)
    return payload


def test_contract_maintenance_publishes_only_digest_bound_reviewed_candidate(
    tmp_path: Path,
) -> None:
    registry = BuiltinModuleRegistry()
    base = registry.resolve_qualified_name("torch.nn.ReLU")
    assert base is not None
    manager = ContractMaintenanceManager(tmp_path, registry)
    manager.begin(base.definition_id, base.version, base.digest, "reviewer:test")
    assert manager.session is not None
    capability_id = manager.session.capability.capability_id
    initial_digest = manager.draft.candidate_digest if manager.draft else ""

    manager.update_candidate(
        {
            "capability_id": capability_id,
            "expected_candidate_digest": initial_digest,
            "candidate": _candidate(base, version="1.0.1", glyph_id="relu-reviewed"),
        },
        capability_id,
        "reviewer:test",
    )
    validation = manager.validate(capability_id, "reviewer:test")
    assert validation.status == "passed"
    assert validation.diff.required_version_bump == "patch"
    receipt = manager.review("approved", capability_id, "reviewer:test")

    published = manager.publish(capability_id, "reviewer:test")

    assert published.is_file()
    assert receipt.candidate_digest in published.read_text(encoding="utf-8")
    assert manager.session is None
    assert manager.state()["published"]


def test_contract_maintenance_rejects_breaking_change_without_passing_migration(
    tmp_path: Path,
) -> None:
    registry = BuiltinModuleRegistry()
    base = registry.resolve_qualified_name("torch.nn.MultiheadAttention")
    assert base is not None
    manager = ContractMaintenanceManager(tmp_path, registry)
    manager.begin(base.definition_id, base.version, base.digest, "reviewer:test")
    assert manager.session is not None and manager.draft is not None
    capability_id = manager.session.capability.capability_id
    changed_ports = [
        port.model_dump(mode="json")
        for port in base.ports
        if port.port_id != "attention_mask"
    ]
    manager.update_candidate(
        {
            "expected_candidate_digest": manager.draft.candidate_digest,
            "candidate": _candidate(base, version="2.0.0", ports=changed_ports),
        },
        capability_id,
        "reviewer:test",
    )

    failed = manager.validate(capability_id, "reviewer:test")

    assert failed.status == "failed"
    assert "CONTRACT_MIGRATION_REQUIRED" in {
        item.code for item in failed.diagnostics
    }
    with pytest.raises(ValueError, match="cannot be approved"):
        manager.review("approved", capability_id, "reviewer:test")

    assert manager.draft is not None
    manager.update_candidate(
        {
            "expected_candidate_digest": manager.draft.candidate_digest,
            "candidate": _candidate(base, version="2.0.0", ports=changed_ports),
            "migration": {
                "migration_id": "migration:mha-v2",
                "from_version": "1.0.0",
                "to_version": "2.0.0",
                "parameter_map": {},
                "port_map": {"attention_mask": None},
                "fixture_results": [
                    {
                        "fixture_id": "fixture:mha-mask",
                        "status": "passed",
                        "message": "Existing masked-attention graph migrated deterministically.",
                    }
                ],
            },
        },
        capability_id,
        "reviewer:test",
    )
    assert manager.validation is None
    assert manager.receipt is None
    passed = manager.validate(capability_id, "reviewer:test")
    assert passed.status == "passed"


def test_contract_candidate_update_invalidates_old_validation_and_receipt(
    tmp_path: Path,
) -> None:
    registry = BuiltinModuleRegistry()
    base = registry.resolve_qualified_name("torch.nn.ReLU")
    assert base is not None
    manager = ContractMaintenanceManager(tmp_path, registry)
    manager.begin(base.definition_id, base.version, base.digest, "reviewer:test")
    assert manager.session is not None and manager.draft is not None
    capability_id = manager.session.capability.capability_id
    manager.update_candidate(
        {
            "expected_candidate_digest": manager.draft.candidate_digest,
            "candidate": _candidate(base, version="1.0.1", glyph_id="relu-v2"),
        },
        capability_id,
        "reviewer:test",
    )
    manager.validate(capability_id, "reviewer:test")
    manager.review("approved", capability_id, "reviewer:test")
    assert manager.draft is not None

    manager.update_candidate(
        {
            "expected_candidate_digest": manager.draft.candidate_digest,
            "candidate": _candidate(base, version="1.0.1", glyph_id="relu-v3"),
        },
        capability_id,
        "reviewer:test",
    )

    assert manager.validation is None
    assert manager.receipt is None
    with pytest.raises(ValueError, match="requires validation"):
        manager.publish(capability_id, "reviewer:test")


def test_contract_diff_includes_parameter_impact_and_tensor_constraints(
    tmp_path: Path,
) -> None:
    registry = BuiltinModuleRegistry()
    base = registry.resolve_qualified_name("torch.nn.Conv2d")
    assert base is not None
    manager = ContractMaintenanceManager(tmp_path, registry)
    manager.begin(base.definition_id, base.version, base.digest, "reviewer:test")
    assert manager.session is not None and manager.draft is not None
    capability_id = manager.session.capability.capability_id
    parameters = [item.model_dump(mode="json") for item in base.parameters]
    next(item for item in parameters if item["parameter_id"] == "out_channels")[
        "affects"
    ] = ["visual"]
    ports = [item.model_dump(mode="json") for item in base.ports]
    next(item for item in ports if item["port_id"] == "input")["tensor_ranks"] = [3, 4]

    manager.update_candidate(
        {
            "expected_candidate_digest": manager.draft.candidate_digest,
            "candidate": _candidate(
                base,
                version="2.0.0",
                parameters=parameters,
                ports=ports,
            ),
        },
        capability_id,
        "reviewer:test",
    )

    validation = manager.validate(capability_id, "reviewer:test")
    assert validation.diff.compatibility == "breaking"
    assert validation.diff.required_version_bump == "major"
    assert {item.subject for item in validation.diff.changes} >= {
        "out_channels",
        "input",
    }
