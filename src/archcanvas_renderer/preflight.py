"""Publication SVG preflight checks that do not mutate source or Exact IR."""

from __future__ import annotations

from xml.etree import ElementTree

from archcanvas_core.models.publication import PublicationIR, VisualScene
from archcanvas_core.models.validation import Severity, ValidationIssue, ValidationReport
from archcanvas_core.publication_validation import validate_scene_semantics


def publication_preflight(publication: PublicationIR, scene: VisualScene, svg: str) -> ValidationReport:
    issues: list[ValidationIssue] = []
    for code in validate_scene_semantics(scene, publication):
        issues.append(
            ValidationIssue(
                severity=Severity.ERROR,
                code=code,
                message=code,
                blocking=True,
            )
        )
    try:
        ElementTree.fromstring(svg)
    except ElementTree.ParseError as error:
        issues.append(
            ValidationIssue(
                severity=Severity.ERROR,
                code="INVALID_SVG",
                message=str(error),
                blocking=True,
            )
        )
    if "NaN" in svg or "undefined" in svg:
        issues.append(
            ValidationIssue(
                severity=Severity.ERROR,
                code="INVALID_SVG_COORDINATE",
                message="SVG contains an invalid coordinate token",
                blocking=True,
            )
        )
    return ValidationReport(
        validator="publication_preflight_v1",
        blocking=any(issue.blocking for issue in issues),
        issues=issues,
    )
