from __future__ import annotations

import hashlib

import pytest
from pydantic import ValidationError

from archcanvas_core.models import (
    ArtifactEntry,
    CanvasDocument,
    Confidence,
    EditProofStatus,
    EvidenceKind,
    EvidenceRecord,
    VisualPatch,
)
from archcanvas_core.validation import apply_visual_patch


def test_source_evidence_requires_a_location() -> None:
    with pytest.raises(ValidationError):
        EvidenceRecord(
            evidence_id="evidence:missing",
            kind=EvidenceKind.SOURCE,
            revision="content:abc",
            claim="An ungrounded claim",
            confidence=Confidence.EXACT,
            execution_predicate="task=inference",
        )


def test_visual_patch_preserves_source_digest() -> None:
    digest = hashlib.sha256(b"source").hexdigest()
    document = CanvasDocument(
        document_id="document:fixture",
        source_snapshot_id="snapshot:fixture",
        architecture_id="architecture:fixture",
        source_digest=digest,
    )
    changed = apply_visual_patch(
        document,
        VisualPatch(
            patch_id="patch:move-q",
            operation="set-position",
            target_id="node:q",
            value={"x": 120, "y": 80},
        ),
    )
    assert changed.source_digest == digest
    assert changed.visual_patches[0].target_id == "node:q"


def test_proof_status_cannot_claim_commit_eligibility_early() -> None:
    digest = hashlib.sha256(b"proof").hexdigest()
    with pytest.raises(ValidationError, match="eligibility"):
        EditProofStatus(
            intent_id="intent:test",
            status="unproven",
            writeback_eligibility="commit",
            message="No stable source anchor exists.",
            checked_generation=1,
            input_fingerprint=digest,
        )


def test_artifact_entry_rejects_path_escape() -> None:
    with pytest.raises(ValidationError, match="relative paths"):
        ArtifactEntry(
            logical_path="../weights.data",
            size=1,
            sha256=hashlib.sha256(b"x").hexdigest(),
            role="external-data",
        )
