from __future__ import annotations

from pathlib import Path

from archcanvas_python import analyze_project_v2

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "tests" / "fixtures" / "frontend_v2" / "transformer_classic"


def test_classic_transformer_recovers_attention_roles_repeats_and_tying(
    tmp_path: Path,
) -> None:
    bundle = analyze_project_v2(
        FIXTURE,
        "model:Transformer",
        "inference",
        "eval",
        tmp_path / "workspace",
    )
    attention_calls = [
        item
        for item in bundle.exact_ir.calls
        if item.definition_ref
        and item.definition_ref.definition_id == "pytorch.nn.multiheadattention"
    ]
    assert len(attention_calls) == 2
    self_attention = next(
        item for item in attention_calls if "encoder_layers" in (item.instance_id or "")
    )
    cross_attention = next(
        item for item in attention_calls if "decoder_layers" in (item.instance_id or "")
    )

    self_inputs = {item.port_id: item.value_id for item in self_attention.input_bindings}
    assert self_inputs["query"] == self_inputs["key"] == self_inputs["value"]
    assert "key_padding_mask" in self_inputs
    cross_inputs = {item.port_id: item.value_id for item in cross_attention.input_bindings}
    assert cross_inputs["query"] != cross_inputs["key"]
    assert cross_inputs["key"] == cross_inputs["value"]
    assert "key_padding_mask" in cross_inputs

    repeats = {item.repeat_id: item for item in bundle.exact_ir.repeats}
    assert repeats["repeat:transformer.encoder_layers"].count == 2
    assert repeats["repeat:transformer.decoder_layers"].count == 3
    assert self_attention.call_id in repeats["repeat:transformer.encoder_layers"].body_call_ids
    assert cross_attention.call_id in repeats["repeat:transformer.decoder_layers"].body_call_ids

    tied = next(
        item for item in bundle.exact_ir.parameter_groups if item.binding_kind == "tied"
    )
    paths = {item.instance_id: item.instance_path for item in bundle.exact_ir.instances}
    assert {paths[item] for item in tied.member_instance_ids} == {
        "transformer.embedding",
        "transformer.generator",
    }
    binding = next(
        item
        for item in bundle.exact_ir.pattern_bindings
        if item.pattern_id == "pattern:transformer.encoder-decoder"
    )
    assert binding.fidelity == "exact"
    assert binding.slot_bindings["self_attention"] == [self_attention.call_id]
    assert binding.slot_bindings["cross_attention"] == [cross_attention.call_id]
    assert binding.parameters["weight_tying"] is True
    assert binding.pack_digest in bundle.analysis_input.pattern_pack_digests
    root = next(item for item in bundle.compatibility.architecture.nodes if item.parent_id is None)
    summaries = root.attributes["v2_pattern_bindings"]
    assert summaries[0]["binding_id"] == binding.binding_id
    assert "V2_COMPAT_PATTERN_BINDING_LOSSY" in {
        item.code for item in bundle.compatibility.architecture.unresolved
    }
    assert not [item for item in bundle.exact_ir.diagnostics if item.severity == "blocking"]
