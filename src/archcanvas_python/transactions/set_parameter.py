from __future__ import annotations

from dataclasses import dataclass
from difflib import unified_diff
import os
from pathlib import Path
import tempfile
from typing import Callable

import libcst as cst

from archcanvas_core.graph_delta import GraphDeltaValidator, architecture_diff
from archcanvas_core.models.architecture import ArchitectureIR
from archcanvas_core.models.patch import PatchSet
from archcanvas_core.models.source_identity import SourceIdentityDocument
from archcanvas_core.models.source_identity import ReconciliationDecision
from archcanvas_core.models.validation import ObservedGraphDelta, ValidationReport
from archcanvas_core.semantic_validation import validate_architecture_semantics

from ..fixture_analyzer import analyze_transformer_fixture
from ..source_revision import file_revision
from ..transforms.set_parameter import TransformRejected, apply_set_parameter


class TransactionRejected(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message


Analyzer = Callable[[bytes], tuple[SourceIdentityDocument, ArchitectureIR]]


@dataclass(frozen=True)
class CandidateTransaction:
    candidate_bytes: bytes
    diff: str
    before_source: SourceIdentityDocument
    before_ir: ArchitectureIR
    after_source: SourceIdentityDocument
    after_ir: ArchitectureIR
    observed_delta: ObservedGraphDelta
    validation: ValidationReport

    @property
    def blocking(self) -> bool:
        return self.validation.blocking


def _assert_semantics(ir: ArchitectureIR, source: SourceIdentityDocument, phase: str) -> None:
    errors = validate_architecture_semantics(ir, source)
    if errors:
        raise TransactionRejected(f"{phase}_SEMANTIC_VALIDATION", ", ".join(errors))
    if any(item.blocking for item in ir.unresolved):
        raise TransactionRejected(f"{phase}_UNRESOLVED_FACT", "candidate contains blocking unresolved facts")
    if any(item.decision is ReconciliationDecision.AMBIGUOUS for item in source.reconciliations):
        raise TransactionRejected(f"{phase}_AMBIGUOUS_IDENTITY", "identity reconciliation is ambiguous")


def _single_hunk_diff(before: bytes, after: bytes, relative_file: str) -> str:
    if before == after:
        raise TransactionRejected("EMPTY_CANDIDATE", "transform did not change source bytes")
    try:
        before_lines = before.decode("utf-8").splitlines(keepends=True)
        after_lines = after.decode("utf-8").splitlines(keepends=True)
    except UnicodeDecodeError as error:
        raise TransactionRejected("SOURCE_NOT_UTF8", relative_file) from error
    diff = "".join(
        unified_diff(before_lines, after_lines, fromfile=f"a/{relative_file}", tofile=f"b/{relative_file}")
    )
    if sum(line.startswith("@@ ") for line in diff.splitlines()) != 1:
        raise TransactionRejected("TEXTUAL_HUNK_CARDINALITY", "candidate must contain exactly one diff hunk")
    return diff


def plan_set_parameter(
    raw_source: bytes,
    patch_set: PatchSet,
    source: SourceIdentityDocument,
    ir: ArchitectureIR,
    analyzer: Analyzer = analyze_transformer_fixture,
) -> CandidateTransaction:
    """Create and validate a candidate without modifying any file."""

    if len(patch_set.patches) != 1:
        raise TransactionRejected("PATCHSET_CARDINALITY", "v1 accepts exactly one patch")
    if patch_set.project_id != source.project_id or patch_set.project_id != ir.project_id:
        raise TransactionRejected("PROJECT_ID_MISMATCH", patch_set.project_id)
    _assert_semantics(ir, source, "BEFORE")
    patch = patch_set.patches[0]
    try:
        anchor = next(item for item in source.anchors if item.anchor_id == patch.target.anchor_id)
        parameter = ir.parameter(patch.target.node_id, patch.target.parameter)
    except StopIteration as error:
        raise TransactionRejected("PATCH_TARGET_NOT_FOUND", patch.target.anchor_id) from error
    if patch_set.base_source_revision != source.file_revisions.get(anchor.relative_file):
        raise TransactionRejected("PATCH_SOURCE_REVISION_MISMATCH", anchor.relative_file)
    try:
        transformed = apply_set_parameter(
            raw_source, patch, anchor, parameter, patch_set.base_source_revision
        )
    except TransformRejected as error:
        raise TransactionRejected(error.code, error.message) from error
    diff = _single_hunk_diff(raw_source, transformed.output_bytes, anchor.relative_file)
    try:
        cst.parse_module(transformed.output_bytes.decode("utf-8"))
    except (UnicodeDecodeError, cst.ParserSyntaxError) as error:
        raise TransactionRejected("CANDIDATE_SYNTAX_INVALID", str(error)) from error
    after_source, after_ir = analyzer(transformed.output_bytes)
    _assert_semantics(after_ir, after_source, "AFTER")
    observed = architecture_diff(ir, after_ir)
    validation = GraphDeltaValidator().validate(patch.expected_delta, observed)
    if validation.blocking:
        raise TransactionRejected("GRAPH_DELTA_BLOCKING", validation.model_dump_json())
    return CandidateTransaction(
        candidate_bytes=transformed.output_bytes,
        diff=diff,
        before_source=source,
        before_ir=ir,
        after_source=after_source,
        after_ir=after_ir,
        observed_delta=observed,
        validation=validation,
    )


def commit_candidate(path: Path, candidate: CandidateTransaction) -> str:
    """Atomically replace a file after a final source-revision check."""

    original = path.read_bytes()
    expected = candidate.before_source.file_revisions.get(path.name)
    if expected is None:
        raise TransactionRejected("TARGET_NOT_IN_SOURCE_DOCUMENT", path.name)
    actual = file_revision(original)
    if actual != expected:
        raise TransactionRejected("STALE_COMMIT_REVISION", actual)
    if candidate.blocking:
        raise TransactionRejected("BLOCKING_CANDIDATE", "candidate report is blocking")
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(candidate.candidate_bytes)
            handle.flush()
            os.fsync(handle.fileno())
        # The source may have changed while candidate bytes were being written.
        if file_revision(path.read_bytes()) != expected:
            raise TransactionRejected("STALE_COMMIT_REVISION", str(path))
        os.replace(temporary, path)
        try:
            directory_fd = os.open(path.parent, os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        except OSError:
            # Directory fsync is unavailable on some supported filesystems; replacement has
            # already completed and must not be reported as a failed transaction.
            pass
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    return file_revision(candidate.candidate_bytes)
