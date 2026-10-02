from __future__ import annotations

import hashlib

import pytest
from pydantic import ValidationError

from archcanvas_adapters import (
    adapter_capabilities,
    default_framework_form_id,
    framework_form_capability,
)
from archcanvas_core.digest_protocol import domain_digest
from archcanvas_core.models import (
    AffectedObjectReviewBinding,
    EditTargetScope,
    SemanticIntentV2,
    ValueOrigin,
    ValueOriginKind,
)
from archcanvas_core.source_v2 import (
    ANALYSIS_ENVIRONMENT_DIGEST_DOMAIN,
    AnalysisEnvironmentManifest,
    analysis_environment_manifest_payload,
)


def _digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def test_analysis_environment_manifest_digest_binds_reproducibility_inputs() -> None:
    digest = _digest(b"fixture")
    values = {
        "python_implementation": "cpython",
        "python_version": "3.11.9",
        "platform": "linux-x86_64",
        "framework_versions": {"torch": "2.7.1", "keras": None},
        "adapter_digests": {"archcanvas_adapters/registry.py": digest},
        "analyzer_digest": digest,
        "schema_bundle_digest": digest,
        "registry_digest": digest,
        "pattern_pack_digests": [digest],
        "pyright_version": None,
        "lockfile_digests": {"pyproject.toml": digest},
        "environment_variables_allowlist_digest": digest,
        "reproducibility_level": "partially-locked",
    }
    manifest_digest = domain_digest(
        ANALYSIS_ENVIRONMENT_DIGEST_DOMAIN,
        analysis_environment_manifest_payload(**values),
    )
    manifest = AnalysisEnvironmentManifest(
        environment_manifest_digest=manifest_digest,
        **values,
    )

    assert manifest.environment_manifest_digest == manifest_digest
    with pytest.raises(ValidationError, match="environment_manifest_digest"):
        manifest.model_copy(
            update={"python_version": "3.12.0"},
        ).model_dump_json()
        AnalysisEnvironmentManifest.model_validate(
            {**manifest.model_dump(mode="json"), "python_version": "3.12.0"}
        )


def test_framework_form_capability_is_action_specific() -> None:
    adapters = {item.framework: item for item in adapter_capabilities()}
    pytorch = adapters["pytorch"]
    keras = adapters["keras"]

    assert pytorch.capability_for(
        "form:pytorch-module-forward", "code_generation"
    ) == "partial"
    assert keras.capability_for("form:keras-functional", "code_generation") == "unavailable"
    assert (
        framework_form_capability("onnx", "form:onnx-custom-op", "artifact_commit")
        == "unavailable"
    )
    assert (
        framework_form_capability("pytorch", "form:missing", "code_generation")
        == "unavailable"
    )
    assert default_framework_form_id("pytorch") == "form:pytorch-module-forward"
    assert default_framework_form_id("missing") == "form:python-callable"


def test_set_parameter_semantic_intent_requires_origin_scope_and_review_binding() -> None:
    digest = _digest(b"source")
    origin = ValueOrigin(
        origin_id="origin:weight",
        kind=ValueOriginKind.CONFIG_KEY,
        source_anchor_ids=["anchor:config.weight"],
        config_path="config.json",
        config_key_path=["model", "weight"],
        confidence="exact",
        editability="direct",
        evidence_ids=["evidence:weight"],
    )
    review = AffectedObjectReviewBinding(
        review_id="review:set-weight",
        affected_object_ids=["node:model", "node:model.call.1"],
        source_anchor_ids=["anchor:config.weight"],
        parameter_sharing_group_ids=["parameter-group:weight"],
        decision="confirmed",
        reviewed_generation=2,
    )
    intent = SemanticIntentV2(
        intent_id="intent:set-weight",
        project_id="project:fixture",
        project_generation=2,
        base_source_digest=digest,
        base_exact_ir_digest=digest,
        framework="pytorch",
        form_id="form:pytorch-module-forward",
        operation="set-parameter",
        target_ids=["node:model"],
        payload={"parameter_name": "weight", "new_value": 2},
        value_origin=origin,
        edit_target_scope=EditTargetScope.CONFIG_VALUE,
        affected_object_review=review,
    )

    assert intent.affected_object_review.decision == "confirmed"
    with pytest.raises(ValidationError, match="ValueOrigin"):
        SemanticIntentV2.model_validate(
            {**intent.model_dump(mode="json"), "value_origin": None}
        )
    with pytest.raises(ValidationError, match="affected-object review"):
        SemanticIntentV2.model_validate(
            {
                **intent.model_dump(mode="json"),
                "target_ids": ["node:unreviewed"],
            }
        )
