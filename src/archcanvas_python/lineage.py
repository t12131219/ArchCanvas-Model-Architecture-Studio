from __future__ import annotations

import hashlib
from collections import defaultdict
from typing import Literal

from pydantic import Field

from archcanvas_core.architecture_v2 import ArchitectureCall, ExactArchitectureIRV2
from archcanvas_core.models import Identifier, StrictModel


class LineageRecord(StrictModel):
    status: Literal["preserved", "replaced", "ambiguous", "deleted", "created"]
    old_call_ids: list[Identifier] = Field(default_factory=list)
    new_call_ids: list[Identifier] = Field(default_factory=list)
    lineage_key: str = Field(min_length=1)


class LineageReport(StrictModel):
    old_exact_ir_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    new_exact_ir_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    records: list[LineageRecord]


def _instance_paths(ir: ExactArchitectureIRV2) -> dict[str, str]:
    return {item.instance_id: item.instance_path for item in ir.instances}


def _lineage_key(call: ArchitectureCall, instance_paths: dict[str, str]) -> str:
    definition = (
        call.definition_ref.definition_id
        if call.definition_ref
        else call.local_definition_id or "unresolved"
    )
    instance = instance_paths.get(call.instance_id or "", call.instance_id or "functional")
    payload = ":".join(
        [
            definition,
            instance,
            call.anchor.qualified_symbol,
            call.anchor.semantic_role,
            call.anchor.subtree_fingerprint,
            call.anchor.parent_fingerprint or "",
        ]
    )
    return hashlib.sha256(payload.encode()).hexdigest()


def build_lineage_report(
    old: ExactArchitectureIRV2,
    new: ExactArchitectureIRV2,
) -> LineageReport:
    old_groups: dict[str, list[ArchitectureCall]] = defaultdict(list)
    new_groups: dict[str, list[ArchitectureCall]] = defaultdict(list)
    old_paths = _instance_paths(old)
    new_paths = _instance_paths(new)
    for call in old.calls:
        old_groups[_lineage_key(call, old_paths)].append(call)
    for call in new.calls:
        new_groups[_lineage_key(call, new_paths)].append(call)

    records: list[LineageRecord] = []
    for key in sorted(set(old_groups) | set(new_groups)):
        old_calls = old_groups.get(key, [])
        new_calls = new_groups.get(key, [])
        old_ids = sorted(item.call_id for item in old_calls)
        new_ids = sorted(item.call_id for item in new_calls)
        if len(old_calls) > 1 or len(new_calls) > 1:
            status = "ambiguous"
        elif old_calls and new_calls:
            status = "preserved" if old_ids == new_ids else "replaced"
        elif old_calls:
            status = "deleted"
        else:
            status = "created"
        records.append(
            LineageRecord(
                status=status,
                old_call_ids=old_ids,
                new_call_ids=new_ids,
                lineage_key=key,
            )
        )
    return LineageReport(
        old_exact_ir_digest=old.exact_ir_digest,
        new_exact_ir_digest=new.exact_ir_digest,
        records=records,
    )
