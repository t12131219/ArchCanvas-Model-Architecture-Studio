from __future__ import annotations

import json
import secrets
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from archcanvas_core.builtin_registry import BuiltinModuleRegistry
from archcanvas_core.contract_review import (
    ContractChange,
    ContractDefinitionDraft,
    ContractDiff,
    ContractMaintenanceCapability,
    ContractMaintenanceSession,
    ContractReviewReceipt,
    ContractValidation,
    DefinitionMigration,
    contract_candidate_digest,
    contract_validation_digest,
)
from archcanvas_core.models import Diagnostic
from archcanvas_core.module_contract import (
    ModuleDefinition,
    ParameterContract,
    PortContract,
    define_module,
)

_BUMP_RANK = {"none": 0, "patch": 1, "minor": 2, "major": 3}


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json")
    path.write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )


def _same(left: object, right: object) -> bool:
    return json.dumps(left, sort_keys=True, separators=(",", ":")) == json.dumps(
        right, sort_keys=True, separators=(",", ":")
    )


def _change(
    changes: list[ContractChange],
    subject: str,
    kind: str,
    compatibility: str,
    message: str,
) -> None:
    changes.append(
        ContractChange(
            subject=subject,
            kind=kind,  # type: ignore[arg-type]
            compatibility=compatibility,  # type: ignore[arg-type]
            message=message,
        )
    )


def diff_definitions(base: ModuleDefinition, candidate: ModuleDefinition) -> ContractDiff:
    changes: list[ContractChange] = []
    if base.definition_id != candidate.definition_id:
        _change(changes, "definition_id", "semantic", "breaking", "Definition identity changed.")
    if base.semantic_kind != candidate.semantic_kind:
        _change(changes, "semantic_kind", "semantic", "breaking", "Semantic kind changed.")
    if base.parameter_schema_version != candidate.parameter_schema_version:
        _change(
            changes,
            "parameter_schema_version",
            "semantic",
            "breaking",
            "Parameter schema version changed.",
        )

    before_parameters = {item.parameter_id: item for item in base.parameters}
    after_parameters = {item.parameter_id: item for item in candidate.parameters}
    for parameter_id, prior in before_parameters.items():
        current = after_parameters.get(parameter_id)
        if current is None:
            _change(changes, parameter_id, "parameter", "breaking", "Parameter was removed or renamed.")
        elif (
            prior.value_type != current.value_type
            or prior.required != current.required
            or prior.positional_index != current.positional_index
            or not _same(prior.default, current.default)
            or sorted(prior.affects) != sorted(current.affects)
            or prior.editability != current.editability
        ):
            _change(changes, parameter_id, "parameter", "breaking", "Parameter runtime contract changed.")
    for parameter_id, current in after_parameters.items():
        if parameter_id not in before_parameters:
            _change(
                changes,
                parameter_id,
                "parameter",
                "breaking" if current.required else "backward-compatible",
                "A required parameter was added." if current.required else "An optional parameter was added.",
            )

    before_ports = {item.port_id: item for item in base.ports}
    after_ports = {item.port_id: item for item in candidate.ports}
    for port_id, prior in before_ports.items():
        current = after_ports.get(port_id)
        if current is None:
            _change(changes, port_id, "port", "breaking", "Port was removed or renamed.")
        elif (
            prior.direction != current.direction
            or prior.required != current.required
            or prior.min_connections != current.min_connections
            or prior.max_connections != current.max_connections
            or prior.ordering != current.ordering
            or sorted(prior.accepted_relations) != sorted(current.accepted_relations)
            or sorted(prior.tensor_ranks) != sorted(current.tensor_ranks)
            or sorted(prior.tensor_layouts) != sorted(current.tensor_layouts)
        ):
            _change(changes, port_id, "port", "breaking", "Port contract changed.")
    for port_id, current in after_ports.items():
        if port_id not in before_ports:
            compatibility = (
                "breaking"
                if current.required or current.min_connections > 0
                else "backward-compatible"
            )
            _change(changes, port_id, "port", compatibility, "A port was added.")

    before_names = set(base.qualified_names)
    after_names = set(candidate.qualified_names)
    for name in sorted(before_names - after_names):
        _change(changes, name, "matcher", "breaking", "Source matcher was removed.")
    for name in sorted(after_names - before_names):
        _change(changes, name, "matcher", "backward-compatible", "Source matcher was added.")
    for field in ("shape_rule_id", "cost_rule_id", "codegen_rule_id"):
        if getattr(base, field) != getattr(candidate, field):
            _change(changes, field, "rule", "breaking", f"{field} changed.")
    for field in ("glyph_id", "detail_template_id"):
        if getattr(base, field) != getattr(candidate, field):
            _change(changes, field, "visual", "visual-only", f"{field} changed.")

    compatibility = (
        "breaking"
        if any(item.compatibility == "breaking" for item in changes)
        else "backward-compatible"
        if any(item.compatibility == "backward-compatible" for item in changes)
        else "visual-only"
        if changes
        else "unchanged"
    )
    required = {
        "breaking": "major",
        "backward-compatible": "minor",
        "visual-only": "patch",
        "unchanged": "none",
    }[compatibility]
    return ContractDiff(
        changes=changes,
        compatibility=compatibility,  # type: ignore[arg-type]
        required_version_bump=required,  # type: ignore[arg-type]
    )


def _actual_version_bump(base: str, candidate: str) -> str:
    before = tuple(int(item) for item in base.split("."))
    after = tuple(int(item) for item in candidate.split("."))
    if after[0] > before[0] and after[1:] == (0, 0):
        return "major"
    if after[0] != before[0]:
        return "invalid"
    if after[1] > before[1] and after[2] == 0:
        return "minor"
    if after[1] != before[1]:
        return "invalid"
    if after[2] > before[2]:
        return "patch"
    return "none" if after[2] == before[2] else "invalid"


def _candidate(payload: dict[str, Any]) -> ModuleDefinition:
    return define_module(
        definition_id=str(payload["definition_id"]),
        version=str(payload["version"]),
        semantic_kind=str(payload["semantic_kind"]),
        qualified_names=[str(item) for item in payload["qualified_names"]],
        parameter_schema_version=str(payload.get("parameter_schema_version", "1.0")),  # type: ignore[arg-type]
        parameters=[ParameterContract.model_validate(item) for item in payload.get("parameters", [])],
        ports=[PortContract.model_validate(item) for item in payload["ports"]],
        glyph_id=str(payload["glyph_id"]),
        detail_template_id=(
            str(payload["detail_template_id"])
            if payload.get("detail_template_id") is not None
            else None
        ),
        shape_rule_id=(str(payload["shape_rule_id"]) if payload.get("shape_rule_id") else None),
        cost_rule_id=(str(payload["cost_rule_id"]) if payload.get("cost_rule_id") else None),
        codegen_rule_id=(str(payload["codegen_rule_id"]) if payload.get("codegen_rule_id") else None),
    )


class ContractMaintenanceManager:
    def __init__(self, workspace: Path, registry: BuiltinModuleRegistry) -> None:
        self.workspace = workspace
        self.registry = registry
        self.session: ContractMaintenanceSession | None = None
        self.draft: ContractDefinitionDraft | None = None
        self.validation: ContractValidation | None = None
        self.receipt: ContractReviewReceipt | None = None

    def state(self) -> dict[str, object]:
        return {
            "session": self.session.model_dump(mode="json") if self.session else None,
            "draft": self.draft.model_dump(mode="json") if self.draft else None,
            "validation": self.validation.model_dump(mode="json") if self.validation else None,
            "review_receipt": self.receipt.model_dump(mode="json") if self.receipt else None,
            "published": self._published_records(),
        }

    def _published_records(self) -> list[dict[str, object]]:
        records: list[dict[str, object]] = []
        root = self.workspace / "contracts" / "approved"
        for path in sorted(root.glob("*/*.json")) if root.is_dir() else []:
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            records.append(payload)
        return records

    def begin(self, definition_id: str, version: str, digest: str, subject: str) -> None:
        base = self.registry.resolve_ref(definition_id, version, digest)
        if base is None:
            raise ValueError("contract maintenance requires an exact approved base definition")
        now = datetime.now(UTC)
        draft_id = f"contract-draft:{secrets.token_hex(12)}"
        candidate_digest = contract_candidate_digest(base)
        capability = ContractMaintenanceCapability(
            capability_id=f"capability:contract.{secrets.token_hex(12)}",
            subject=subject,
            draft_id=draft_id,
            base=base.ref,
            allowed_commands=["UpdateCandidate", "Validate", "Review", "Publish", "Discard"],
            issued_at=now.isoformat(),
            expires_at=(now + timedelta(minutes=30)).isoformat(),
        )
        self.draft = ContractDefinitionDraft(
            draft_id=draft_id,
            base=base.ref,
            candidate=base,
            candidate_digest=candidate_digest,
            author=subject,
            created_at=now.isoformat(),
        )
        self.session = ContractMaintenanceSession(
            capability=capability, candidate_digest=candidate_digest
        )
        self.validation = None
        self.receipt = None
        self._persist()

    def _authorize(self, command: str, capability_id: str, subject: str) -> None:
        if self.session is None or self.draft is None:
            raise ValueError("contract-maintenance mode is required")
        capability = self.session.capability
        if capability.subject != subject or capability.capability_id != capability_id:
            raise ValueError("contract maintenance capability is missing or invalid")
        if command not in capability.allowed_commands:
            raise ValueError(f"contract maintenance capability denies {command}")
        if datetime.now(UTC) >= datetime.fromisoformat(capability.expires_at):
            raise ValueError("contract maintenance capability has expired")

    def update_candidate(
        self,
        payload: dict[str, Any],
        capability_id: str,
        subject: str,
    ) -> None:
        self._authorize("UpdateCandidate", capability_id, subject)
        assert self.draft is not None
        expected_digest = str(payload["expected_candidate_digest"])
        if expected_digest != self.draft.candidate_digest:
            raise ValueError("contract candidate digest is stale")
        candidate = _candidate(dict(payload["candidate"]))
        if candidate.definition_id != self.draft.base.definition_id:
            raise ValueError("approved definition identity cannot be changed in place")
        migration = (
            DefinitionMigration.model_validate(payload["migration"])
            if payload.get("migration") is not None
            else None
        )
        self.draft = self.draft.model_copy(
            update={
                "candidate": candidate,
                "candidate_digest": contract_candidate_digest(candidate),
                "migration": migration,
                "revision": self.draft.revision + 1,
                "state": "draft",
            }
        )
        self.session = self.session.model_copy(
            update={"candidate_digest": self.draft.candidate_digest}
        )
        self.validation = None
        self.receipt = None
        self._persist()

    def validate(self, capability_id: str, subject: str) -> ContractValidation:
        self._authorize("Validate", capability_id, subject)
        assert self.draft is not None
        base = self.registry.resolve_ref(
            self.draft.base.definition_id,
            self.draft.base.version,
            self.draft.base.digest,
        )
        diagnostics: list[Diagnostic] = []
        if base is None:
            diagnostics.append(
                Diagnostic(
                    code="CONTRACT_BASE_STALE",
                    severity="blocking",
                    message="The exact approved base definition is no longer available.",
                )
            )
            base = self.draft.candidate
        diff = diff_definitions(base, self.draft.candidate)
        actual = _actual_version_bump(base.version, self.draft.candidate.version)
        if actual == "invalid" or _BUMP_RANK.get(actual, -1) < _BUMP_RANK[
            diff.required_version_bump
        ]:
            diagnostics.append(
                Diagnostic(
                    code="CONTRACT_VERSION_INSUFFICIENT",
                    severity="blocking",
                    message=f"The contract requires a {diff.required_version_bump} version bump.",
                )
            )
        allowed_rules = {
            value
            for definition in self.registry.bundle.definitions
            for value in (
                definition.shape_rule_id,
                definition.cost_rule_id,
                definition.codegen_rule_id,
            )
            if value is not None
        }
        candidate_rules = {
            value
            for value in (
                self.draft.candidate.shape_rule_id,
                self.draft.candidate.cost_rule_id,
                self.draft.candidate.codegen_rule_id,
            )
            if value is not None
        }
        unknown_rules = sorted(candidate_rules - allowed_rules)
        if unknown_rules:
            diagnostics.append(
                Diagnostic(
                    code="CONTRACT_RULE_UNAPPROVED",
                    severity="blocking",
                    message="Candidate references unapproved rule IDs: " + ", ".join(unknown_rules),
                )
            )
        conflicting_names = sorted(
            name
            for definition in self.registry.bundle.definitions
            if definition.definition_id != self.draft.candidate.definition_id
            for name in self.draft.candidate.qualified_names
            if name in definition.qualified_names
        )
        if conflicting_names:
            diagnostics.append(
                Diagnostic(
                    code="CONTRACT_MATCHER_AMBIGUOUS",
                    severity="blocking",
                    message="Candidate source matchers collide with approved definitions: "
                    + ", ".join(conflicting_names),
                )
            )
        if diff.compatibility == "breaking" and not self._migration_covers(diff):
            diagnostics.append(
                Diagnostic(
                    code="CONTRACT_MIGRATION_REQUIRED",
                    severity="blocking",
                    message=(
                        "Breaking contract changes require complete parameter/port maps "
                        "and passing migration fixtures."
                    ),
                )
            )
        status = "failed" if diagnostics else "passed"
        validation_id = f"contract-validation:{secrets.token_hex(12)}"
        validated_at = datetime.now(UTC).isoformat()
        digest = contract_validation_digest(
            draft_id=self.draft.draft_id,
            candidate_digest=self.draft.candidate_digest,
            status=status,
            diff=diff,
            diagnostics=diagnostics,
        )
        self.validation = ContractValidation(
            validation_id=validation_id,
            draft_id=self.draft.draft_id,
            candidate_digest=self.draft.candidate_digest,
            validation_digest=digest,
            status=status,
            diff=diff,
            diagnostics=diagnostics,
            validated_at=validated_at,
        )
        self.draft = self.draft.model_copy(
            update={"state": "review-ready" if status == "passed" else "draft"}
        )
        self.receipt = None
        self._persist()
        return self.validation

    def _migration_covers(self, diff: ContractDiff) -> bool:
        migration = self.draft.migration if self.draft else None
        if migration is None or not migration.fixture_results:
            return False
        if migration.from_version != self.draft.base.version:
            return False
        if migration.to_version != self.draft.candidate.version:
            return False
        if any(item.status != "passed" for item in migration.fixture_results):
            return False
        for change in diff.changes:
            if change.compatibility != "breaking":
                continue
            if change.kind == "port" and change.subject not in migration.port_map:
                return False
            if change.kind == "parameter" and change.subject not in migration.parameter_map:
                return False
        return True

    def review(
        self, decision: str, capability_id: str, subject: str
    ) -> ContractReviewReceipt:
        self._authorize("Review", capability_id, subject)
        assert self.draft is not None
        if self.validation is None:
            raise ValueError("contract candidate must be validated before review")
        if self.validation.candidate_digest != self.draft.candidate_digest:
            raise ValueError("contract validation is stale for the current candidate")
        if decision not in {"approved", "rejected"}:
            raise ValueError("contract review decision is invalid")
        if decision == "approved" and self.validation.status != "passed":
            raise ValueError("failed contract validation cannot be approved")
        self.receipt = ContractReviewReceipt(
            receipt_id=f"contract-receipt:{secrets.token_hex(12)}",
            draft_id=self.draft.draft_id,
            candidate_digest=self.draft.candidate_digest,
            validation_digest=self.validation.validation_digest,
            reviewer=subject,
            decision=decision,  # type: ignore[arg-type]
            decided_at=datetime.now(UTC).isoformat(),
        )
        self.draft = self.draft.model_copy(
            update={"state": "approved" if decision == "approved" else "rejected"}
        )
        self._persist()
        return self.receipt

    def publish(self, capability_id: str, subject: str) -> Path:
        self._authorize("Publish", capability_id, subject)
        assert self.draft is not None
        if self.validation is None or self.receipt is None:
            raise ValueError("contract publication requires validation and review receipt")
        current_digest = contract_candidate_digest(self.draft.candidate)
        if (
            self.draft.state != "approved"
            or self.receipt.decision != "approved"
            or current_digest != self.draft.candidate_digest
            or self.validation.candidate_digest != current_digest
            or self.receipt.candidate_digest != current_digest
            or self.receipt.validation_digest != self.validation.validation_digest
        ):
            raise ValueError("contract publication bindings are stale or incomplete")
        directory = (
            self.workspace
            / "contracts"
            / "approved"
            / self.draft.candidate.definition_id
        )
        target = directory / (
            f"{self.draft.candidate.version}-{self.draft.candidate.digest}.json"
        )
        existing_versions = list(directory.glob(f"{self.draft.candidate.version}-*.json"))
        if existing_versions and target not in existing_versions:
            raise ValueError("an approved definition version cannot be replaced in place")
        record = {
            "definition": self.draft.candidate.model_dump(mode="json"),
            "candidate_digest": current_digest,
            "validation": self.validation.model_dump(mode="json"),
            "review_receipt": self.receipt.model_dump(mode="json"),
            "published_at": datetime.now(UTC).isoformat(),
        }
        if target.is_file():
            if json.loads(target.read_text(encoding="utf-8"))["definition"] != record["definition"]:
                raise ValueError("published definition content is immutable")
        else:
            _write_json(target, record)
        self.session = None
        self._persist()
        return target

    def discard(self, capability_id: str, subject: str) -> None:
        self._authorize("Discard", capability_id, subject)
        self.session = None
        self.draft = None
        self.validation = None
        self.receipt = None

    def _persist(self) -> None:
        if self.draft is None:
            return
        directory = self.workspace / "contracts" / "drafts" / self.draft.draft_id
        _write_json(directory / "draft.json", self.draft)
        if self.validation is not None:
            _write_json(directory / "validation.json", self.validation)
        if self.receipt is not None:
            _write_json(directory / "review-receipt.json", self.receipt)
