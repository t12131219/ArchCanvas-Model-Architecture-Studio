"""Validate D5 census evidence without upgrading machine preflight to human approval."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import ClassVar


@dataclass(frozen=True)
class D5ValidationReport:
    """Machine-readable D5 evidence result.

    ``machine_passed`` says the census is internally coherent. ``stage6_exit_ready`` also needs
    human review, so a pending checklist deliberately remains an exit blocker.
    """

    machine_passed: bool
    stage6_exit_ready: bool
    blockers: list[str]
    manual_review_pending_entrypoints: list[str]

    def as_dict(self) -> dict[str, object]:
        return {
            "schema_version": "1.0",
            "report_kind": "d5-census-validation-v1",
            **asdict(self),
        }


class D5CensusValidator:
    """Check the mechanical parts of Section 26.8 from a saved census report."""

    _publication_ready: ClassVar[set[str]] = {
        "publication_svg_ready",
        "publication_svg_ready_with_unresolved_parameter_provenance",
    }

    def validate(
        self,
        census: Mapping[str, object],
        *,
        publication_artifact_root: Path | None = None,
    ) -> D5ValidationReport:
        blockers: list[str] = []
        pending: list[str] = []
        if census.get("report_kind") != "pytorch-model-census-v1":
            blockers.append("INVALID_CENSUS_REPORT_KIND")
        execution = census.get("execution")
        if not isinstance(execution, Mapping):
            blockers.append("MISSING_EXECUTION_EVIDENCE")
        else:
            for field in ("source_imported", "source_executed", "dependencies_installed", "source_written"):
                if execution.get(field) is not False:
                    blockers.append(f"EXECUTION_{field.upper()}_NOT_FALSE")
            if execution.get("source_files_unchanged") is not True:
                blockers.append("SOURCE_FILES_CHANGED_OR_UNPROVEN")

        items = census.get("items")
        aliases = census.get("explicit_aliases")
        if not isinstance(items, list) or not isinstance(aliases, list):
            blockers.append("MISSING_ENTRYPOINT_ACCOUNTING")
            return self._result(blockers, pending)
        discovered = census.get("discovered_entrypoint_count")
        assessed = census.get("assessed_entrypoint_count")
        alias_count = census.get("explicit_alias_count")
        if not all(isinstance(value, int) for value in (discovered, assessed, alias_count)):
            blockers.append("INVALID_ENTRYPOINT_COUNTS")
        elif discovered != assessed + alias_count or assessed != len(items) or alias_count != len(aliases):
            blockers.append("ENTRYPOINT_COMPLETENESS_MISMATCH")

        entrypoints: set[str] = set()
        for item in items:
            if not isinstance(item, Mapping):
                blockers.append("INVALID_ENTRYPOINT_RECORD")
                continue
            entrypoint = item.get("entrypoint")
            if not isinstance(entrypoint, str) or not entrypoint or entrypoint in entrypoints:
                blockers.append("DUPLICATE_OR_MISSING_ENTRYPOINT")
                continue
            entrypoints.add(entrypoint)
            self._validate_item(item, blockers)
            status = item.get("publication_status")
            if status in self._publication_ready:
                self._validate_publication_artifact(
                    entrypoint,
                    publication_artifact_root,
                    blockers,
                    pending,
                )
            elif item.get("status") == "supported":
                blockers.append("SUPPORTED_ENTRYPOINT_MISSING_PUBLICATION_EVIDENCE")
        for alias in aliases:
            if not isinstance(alias, Mapping) or alias.get("target_entrypoint") not in entrypoints:
                blockers.append("ALIAS_TARGET_NOT_ASSESSED")

        return self._result(blockers, pending)

    @staticmethod
    def _validate_item(item: Mapping[str, object], blockers: list[str]) -> None:
        required = ("owner", "status", "source_revision", "file_revisions", "source_files_unchanged")
        if any(not item.get(field) for field in required[:4]) or item.get("source_files_unchanged") is not True:
            blockers.append("ENTRYPOINT_SOURCE_EVIDENCE_INCOMPLETE")
        if item.get("status") not in {"supported", "unresolved", "unsupported", "blocked"}:
            blockers.append("INVALID_ENTRYPOINT_STATUS")

    @classmethod
    def _validate_publication_artifact(
        cls,
        entrypoint: str,
        artifact_root: Path | None,
        blockers: list[str],
        pending: list[str],
    ) -> None:
        if artifact_root is None:
            blockers.append("PUBLICATION_ARTIFACT_ROOT_NOT_PROVIDED")
            return
        token = cls._token(entrypoint)
        destination = artifact_root / token
        expected = {
            "publication.json",
            "scene-overview.json",
            "scene-detail.json",
            "overview.svg",
            "detail.svg",
            "publication-checklist.json",
        }
        if not destination.is_dir() or not expected.issubset({path.name for path in destination.iterdir()}):
            blockers.append("PUBLICATION_ARTIFACTS_INCOMPLETE")
            return
        try:
            checklist = json.loads((destination / "publication-checklist.json").read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            blockers.append("PUBLICATION_CHECKLIST_UNREADABLE")
            return
        if not isinstance(checklist, dict) or checklist.get("machine_preflight") != "passed":
            blockers.append("PUBLICATION_MACHINE_PREFLIGHT_NOT_PASSED")
            return
        if checklist.get("entrypoint") != entrypoint:
            blockers.append("PUBLICATION_CHECKLIST_ENTRYPOINT_MISMATCH")
            return
        if checklist.get("manual_review") != "approved":
            pending.append(entrypoint)

    @staticmethod
    def _token(entrypoint: str) -> str:
        from archcanvas_core.models.common import sha256_digest

        return sha256_digest(entrypoint.encode("utf-8")).removeprefix("sha256:")

    @staticmethod
    def _result(blockers: list[str], pending: list[str]) -> D5ValidationReport:
        unique_blockers = sorted(set(blockers))
        unique_pending = sorted(set(pending))
        return D5ValidationReport(
            machine_passed=not unique_blockers,
            stage6_exit_ready=not unique_blockers and not unique_pending,
            blockers=unique_blockers,
            manual_review_pending_entrypoints=unique_pending,
        )
