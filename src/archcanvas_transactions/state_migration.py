from __future__ import annotations

import hashlib
import json

from archcanvas_core.models import (
    Diagnostic,
    GraphDelta,
    StateAssetBinding,
    StateMigrationAction,
    StateMigrationEntry,
    StateMigrationPlan,
)


def state_inventory_digest(binding: StateAssetBinding) -> str:
    payload = [entry.model_dump(mode="json") for entry in binding.inventory]
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def build_state_migration_plan(
    binding: StateAssetBinding,
    *,
    framework: str,
    base_source_digest: str,
    result_source_digest: str,
    result_exact_ir_digest: str,
    expected_delta: GraphDelta,
) -> StateMigrationPlan:
    """Build a conservative plan without loading an untrusted checkpoint.

    The current adapter contract inventories source state but cannot yet derive a complete
    target state schema. Keeping every entry blocked is intentional: source-only commits
    remain possible while source+state can never be presented as verified prematurely.
    """
    if binding.framework != framework:
        raise ValueError("state asset framework does not match the source transaction")
    actual_inventory_digest = state_inventory_digest(binding)
    if actual_inventory_digest != binding.inventory_digest:
        raise ValueError("state asset inventory digest does not match its entries")
    schema_payload = {
        "result_exact_ir_digest": result_exact_ir_digest,
        "expected_delta": expected_delta.model_dump(mode="json"),
        "inventory_digest": binding.inventory_digest,
    }
    target_schema_digest = hashlib.sha256(
        json.dumps(schema_payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    diagnostic = Diagnostic(
        code="STATE_TARGET_SCHEMA_UNRESOLVED",
        severity="blocking",
        message=(
            "The source transaction has a bound state asset, but the framework adapter did "
            "not produce a verified target parameter/buffer schema. Source+state commit is blocked."
        ),
        target_ids=[binding.binding_id],
    )
    entries = [
        StateMigrationEntry(
            old_state_key=entry.state_key,
            new_state_key=entry.state_key,
            action=StateMigrationAction.BLOCK,
            old_tensor=entry.tensor,
            parameter_group_id=entry.parameter_group_id,
            optimizer_slot_keys=entry.optimizer_slot_keys,
            evidence_ids=entry.evidence_ids,
            diagnostics=[diagnostic],
        )
        for entry in binding.inventory
    ]
    shared_checks = sorted(
        {
            entry.parameter_group_id
            for entry in binding.inventory
            if entry.parameter_group_id is not None
        }
    )
    plan_seed = json.dumps(
        {
            "binding_id": binding.binding_id,
            "base_source_digest": base_source_digest,
            "result_source_digest": result_source_digest,
            "target_state_schema_digest": target_schema_digest,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return StateMigrationPlan(
        plan_id=f"state-plan:{hashlib.sha256(plan_seed.encode()).hexdigest()[:20]}",
        framework=binding.framework,
        base_source_digest=base_source_digest,
        result_source_digest=result_source_digest,
        source_state_digest=binding.source_state_digest,
        target_state_schema_digest=target_schema_digest,
        entries=entries,
        shared_identity_checks=shared_checks,
        status="blocked",
    )
