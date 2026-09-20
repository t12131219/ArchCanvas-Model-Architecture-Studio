from __future__ import annotations

from archcanvas_core.semantic_validation import validate_architecture_semantics


def test_fixture_cross_document_semantics_are_clean(before_ir, source_document) -> None:
    assert validate_architecture_semantics(before_ir, source_document) == []


def test_source_backed_identity_without_anchor_is_rejected(source_document) -> None:
    identity = source_document.identities[0].model_copy(update={"anchor_ids": []})
    try:
        identity.__class__.model_validate(identity.model_dump(mode="python"))
    except ValueError as error:
        assert "source-backed identity requires" in str(error)
    else:
        raise AssertionError("invalid source-backed identity was accepted")
