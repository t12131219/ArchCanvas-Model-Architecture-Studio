from __future__ import annotations

import math
from collections.abc import Callable, Mapping
from copy import deepcopy
from typing import Any, TypeVar

from pydantic import BaseModel

from .architecture_v2 import ExactArchitectureIRV2
from .digest_protocol import domain_digest
from .models import (
    CanvasDocument,
    DraftGraphDocument,
    OfflineBundleManifest,
    ProtocolMigrationReceipt,
    SourceTransaction,
    StateMigrationPlan,
)
from .module_contract import ModuleRegistryBundle

ProtocolModel = TypeVar("ProtocolModel", bound=BaseModel)
Migration = Callable[[dict[str, Any]], dict[str, Any]]
PROTOCOL_PAYLOAD_DIGEST_DOMAIN = "archcanvas:protocol-payload:v1"


def _version(value: object) -> tuple[int, int]:
    if not isinstance(value, str):
        raise TypeError("protocol schema_version must be a major.minor string")
    parts = value.split(".")
    if len(parts) != 2 or any(not part.isdigit() for part in parts):
        raise ValueError("protocol schema_version must be a major.minor string")
    return int(parts[0]), int(parts[1])


def _payload_digest(protocol: str, payload: Mapping[str, Any]) -> str:
    return domain_digest(
        PROTOCOL_PAYLOAD_DIGEST_DOMAIN,
        {"protocol": protocol, "payload": _digest_safe_value(payload)},
    )


def _digest_safe_value(value: Any) -> Any:
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("protocol payload floating-point values must be finite")
        return {"$float": format(value, ".17g")}
    if isinstance(value, Mapping):
        return {str(key): _digest_safe_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_digest_safe_value(item) for item in value]
    return value


def read_versioned_protocol(
    model: type[ProtocolModel],
    payload: Mapping[str, Any],
    *,
    protocol: str,
    current_version: str,
    migrations: Mapping[str, tuple[str, Migration]] | None = None,
) -> tuple[ProtocolModel, ProtocolMigrationReceipt]:
    source = deepcopy(dict(payload))
    source_version = str(source.get("schema_version", ""))
    source_major, source_minor = _version(source_version)
    current_major, current_minor = _version(current_version)
    registered_migration = (migrations or {}).get(source_version)
    if source_major != current_major and registered_migration is None:
        raise ValueError(
            f"unsupported {protocol} schema major {source_major}; expected {current_major}"
        )

    migration_id: str | None = None
    status = "current"
    candidate = source
    if registered_migration is not None:
        migration_id, migrate = registered_migration
        candidate = migrate(source)
        candidate["schema_version"] = current_version
        status = "migrated"
    elif source_minor > current_minor:
        candidate = {**source, "schema_version": current_version}
        status = "compatible-minor"
    elif source_minor < current_minor:
        raise ValueError(
            f"no registered {protocol} migration from {source_version} to {current_version}"
        )

    parsed = model.model_validate(candidate)
    normalized = parsed.model_dump(mode="json")
    input_digest = _payload_digest(protocol, source)
    output_digest = _payload_digest(protocol, normalized)
    receipt = ProtocolMigrationReceipt(
        receipt_id=f"receipt:protocol.{input_digest[:24]}",
        protocol=protocol,
        from_version=source_version,
        to_version=current_version,
        status=status,
        input_digest=input_digest,
        output_digest=output_digest,
        migration_id=migration_id,
    )
    return parsed, receipt


def _migrate_canvas_document_0_9(payload: dict[str, Any]) -> dict[str, Any]:
    migrated = dict(payload)
    migrated.pop("base_scene_ids", None)
    migrated.setdefault("base_hierarchy_id", None)
    migrated.setdefault("redo_patches", [])
    migrated.setdefault("view_state", {})
    return migrated


def read_canvas_document_protocol(
    payload: Mapping[str, Any],
) -> tuple[CanvasDocument, ProtocolMigrationReceipt]:
    return read_versioned_protocol(
        CanvasDocument,
        payload,
        protocol="canvas-document",
        current_version="1.0",
        migrations={
            "0.9": (
                "migration:canvas-document.0-9-to-1-0",
                _migrate_canvas_document_0_9,
            )
        },
    )


def read_exact_architecture_ir_v2_protocol(
    payload: Mapping[str, Any],
) -> tuple[ExactArchitectureIRV2, ProtocolMigrationReceipt]:
    return read_versioned_protocol(
        ExactArchitectureIRV2,
        payload,
        protocol="exact-architecture-ir-v2",
        current_version="2.0",
    )


def read_draft_graph_document_protocol(
    payload: Mapping[str, Any],
) -> tuple[DraftGraphDocument, ProtocolMigrationReceipt]:
    return read_versioned_protocol(
        DraftGraphDocument,
        payload,
        protocol="draft-graph-document",
        current_version="1.0",
    )


def read_module_registry_bundle_protocol(
    payload: Mapping[str, Any],
) -> tuple[ModuleRegistryBundle, ProtocolMigrationReceipt]:
    return read_versioned_protocol(
        ModuleRegistryBundle,
        payload,
        protocol="module-registry-bundle",
        current_version="1.0",
    )


def read_source_transaction_protocol(
    payload: Mapping[str, Any],
) -> tuple[SourceTransaction, ProtocolMigrationReceipt]:
    return read_versioned_protocol(
        SourceTransaction,
        payload,
        protocol="source-transaction",
        current_version="1.0",
    )


def read_state_migration_plan_protocol(
    payload: Mapping[str, Any],
) -> tuple[StateMigrationPlan, ProtocolMigrationReceipt]:
    return read_versioned_protocol(
        StateMigrationPlan,
        payload,
        protocol="state-migration-plan",
        current_version="1.0",
    )


def read_offline_bundle_manifest_protocol(
    payload: Mapping[str, Any],
) -> tuple[OfflineBundleManifest, ProtocolMigrationReceipt]:
    return read_versioned_protocol(
        OfflineBundleManifest,
        payload,
        protocol="offline-bundle-manifest",
        current_version="1.0",
    )
