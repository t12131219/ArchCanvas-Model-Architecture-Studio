"""Build committed golden JSON from real fixture source bytes."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from archcanvas_core.graph_delta import GraphDeltaValidator, architecture_diff
from archcanvas_core.models.common import canonical_json
from archcanvas_core.models.patch import (
    ExpectedGraphDelta,
    ParameterChange,
    PatchSet,
    PatchTarget,
    SetParameterPatch,
)
from archcanvas_python.fixture_analyzer import (
    PROJECT_ID,
    TARGET_ANCHOR_ID,
    TARGET_NODE_ID,
    analyze_transformer_fixture,
)

ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "transformer_set_parameter_v1"


def dump(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_json(value) + b"\n")


def main() -> None:
    before_raw = (ROOT / "source" / "before" / "model.py").read_bytes()
    after_raw = (ROOT / "source" / "after" / "model.py").read_bytes()
    before_source, before_ir = analyze_transformer_fixture(before_raw)
    after_source, after_ir = analyze_transformer_fixture(after_raw)
    anchor = before_source.anchors[0]
    expected = ExpectedGraphDelta(
        required_parameter_changes=[ParameterChange(node_id=TARGET_NODE_ID, parameter="num_heads", before=8, after=16)],
        allowed_node_additions=[],
        allowed_node_removals=[],
        allowed_node_modifications=[],
        allowed_edge_additions=[],
        allowed_edge_removals=[],
        allowed_edge_modifications=[],
        require_identity_retention=True,
    )
    patch_set = PatchSet(
        patch_set_id="patchset:set-num-heads-16",
        project_id=PROJECT_ID,
        base_source_revision=anchor.file_revision,
        created_at=datetime(2026, 9, 20, 8, 0, tzinfo=UTC),
        created_by="user",
        patches=[
            SetParameterPatch(
                patch_id="patch:set-num-heads-16",
                target=PatchTarget(node_id=TARGET_NODE_ID, parameter="num_heads", anchor_id=TARGET_ANCHOR_ID),
                before=8,
                after=16,
                anchor_content_fingerprint=anchor.content_fingerprint,
                expected_delta=expected,
            )
        ],
    )
    observed = architecture_diff(before_ir, after_ir)
    report = GraphDeltaValidator().validate(expected, observed)
    dump(ROOT / "expected" / "source-identity.before.json", before_source.model_dump(mode="json"))
    dump(ROOT / "expected" / "architecture.before.json", before_ir.model_dump(mode="json"))
    dump(ROOT / "expected" / "architecture.after.json", after_ir.model_dump(mode="json"))
    dump(ROOT / "request.patch.json", patch_set.model_dump(mode="json"))
    dump(ROOT / "expected" / "graph-delta.json", observed.model_dump(mode="json"))
    dump(ROOT / "expected" / "validation.json", report.model_dump(mode="json"))
    dump(ROOT / "expected" / "source-identity.after.json", after_source.model_dump(mode="json"))


if __name__ == "__main__":
    main()
