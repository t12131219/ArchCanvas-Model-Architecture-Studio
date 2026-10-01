from __future__ import annotations

import json

import pytest

from archcanvas_core.builtin_registry import builtin_registry_bundle
from archcanvas_core.module_contract import (
    ModuleDefinition,
    ModuleRegistryBundle,
    migrate_parameter_values,
)


def test_every_definition_schema_round_trips_and_runs_its_pinned_migration() -> None:
    bundle = builtin_registry_bundle()

    assert ModuleRegistryBundle.model_validate_json(
        bundle.model_dump_json()
    ).model_dump(mode="json") == bundle.model_dump(mode="json")
    for definition in bundle.definitions:
        payload = json.loads(definition.model_dump_json())
        assert ModuleDefinition.model_validate(payload) == definition
        defaults = {
            parameter.parameter_id: parameter.default
            for parameter in definition.parameters
        }
        assert migrate_parameter_values(
            definition,
            definition.parameter_schema_version,
            defaults,
        ) == defaults
        with pytest.raises(ValueError, match="no registered parameter migration"):
            migrate_parameter_values(definition, "0.0", {})


def test_every_definition_declares_deterministic_parameter_and_port_contracts() -> None:
    bundle = builtin_registry_bundle()

    for definition in bundle.definitions:
        assert definition.parameter_schema_version == "1.0"
        assert len({item.parameter_id for item in definition.parameters}) == len(
            definition.parameters
        )
        assert len({item.port_id for item in definition.ports}) == len(definition.ports)
        assert any(item.direction == "output" for item in definition.ports)
        for parameter in definition.parameters:
            assert parameter.affects
            assert len(parameter.affects) == len(set(parameter.affects))
        for port in definition.ports:
            assert port.accepted_relations
            assert port.min_connections >= 0
            assert port.max_connections == "many" or (
                port.max_connections >= port.min_connections
            )
            assert len(port.tensor_ranks) == len(set(port.tensor_ranks))


def test_parameter_migration_rejects_unknown_fields() -> None:
    definition = builtin_registry_bundle().definitions[0]

    with pytest.raises(ValueError, match="unknown module parameters"):
        migrate_parameter_values(
            definition,
            definition.parameter_schema_version,
            {"not_in_schema": 1},
        )
