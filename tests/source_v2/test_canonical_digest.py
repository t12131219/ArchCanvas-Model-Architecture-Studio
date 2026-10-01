from __future__ import annotations

import hashlib

import pytest
from pydantic import ValidationError

from archcanvas_core.digest_protocol import (
    CanonicalizationError,
    canonical_json_bytes,
    domain_digest,
)
from archcanvas_core.models import SourceSpan
from archcanvas_core.source_v2 import (
    ANALYSIS_INPUT_DIGEST_DOMAIN,
    AnalysisInputManifest,
    ResolverManifest,
    SourceAnchor,
    analysis_input_digest_payload,
)


def _digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def test_canonical_json_uses_utf16_key_order_and_rejects_floats() -> None:
    assert canonical_json_bytes({"b": 1, "a": [True, None]}) == b'{"a":[true,null],"b":1}'
    with pytest.raises(CanonicalizationError, match="floating-point"):
        canonical_json_bytes({"value": 1.5})


def test_analysis_input_digest_is_order_independent_for_pattern_packs() -> None:
    zero = "0" * 64
    one = "1" * 64
    resolver = ResolverManifest(
        resolver_id="resolver:disabled",
        resolver_version="0",
        resolver_digest=zero,
    )
    values = {
        "source_corpus_digest": zero,
        "registry_digest": one,
        "analyzer_build_digest": zero,
        "pattern_pack_digests": [one, zero],
        "resolver": resolver,
        "task": "inference",
        "execution_mode": "eval",
        "entrypoint": "model:Model",
        "config_digest": _digest(b"{}"),
    }
    digest = domain_digest(
        ANALYSIS_INPUT_DIGEST_DOMAIN,
        analysis_input_digest_payload(**values),
    )
    manifest = AnalysisInputManifest(**values, analysis_input_digest=digest)
    reversed_values = {**values, "pattern_pack_digests": list(reversed(values["pattern_pack_digests"]))}
    reversed_digest = domain_digest(
        ANALYSIS_INPUT_DIGEST_DOMAIN,
        analysis_input_digest_payload(**reversed_values),
    )

    assert manifest.analysis_input_digest == reversed_digest


def test_analysis_manifest_rejects_unbound_digest() -> None:
    zero = "0" * 64
    with pytest.raises(ValidationError, match="analysis_input_digest"):
        AnalysisInputManifest(
            source_corpus_digest=zero,
            registry_digest=zero,
            analyzer_build_digest=zero,
            resolver=ResolverManifest(
                resolver_id="resolver:disabled",
                resolver_version="0",
                resolver_digest=zero,
            ),
            task="inference",
            execution_mode="eval",
            entrypoint="model:Model",
            config_digest=zero,
            analysis_input_digest=zero,
        )


def test_source_anchor_rejects_path_escape() -> None:
    digest = "0" * 64
    with pytest.raises(ValidationError, match="confined"):
        SourceAnchor(
            logical_path="../model.py",
            blob_digest=digest,
            byte_start=0,
            byte_length=5,
            line_span=SourceSpan(start_line=1, end_line=1),
            qualified_symbol="model.Model",
            cst_node_kind="ClassDef",
            semantic_role="module-definition",
            subtree_fingerprint=digest,
        )
