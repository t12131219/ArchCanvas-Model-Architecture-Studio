from __future__ import annotations

import hashlib
from collections.abc import Callable
from dataclasses import dataclass

from archcanvas_core.architecture_v2 import (
    SEMANTIC_GRAPH_DIGEST_DOMAIN,
    PatternBindingV2,
    PythonSemanticGraph,
    semantic_graph_payload,
)
from archcanvas_core.digest_protocol import domain_digest

PATTERN_PACK_DOMAIN = "archcanvas:python-pattern-pack:v2"


@dataclass(frozen=True)
class PatternPack:
    pack_id: str
    version: str
    description: str
    matcher: Callable[[PythonSemanticGraph, str], PatternBindingV2 | None]

    @property
    def digest(self) -> str:
        return domain_digest(
            PATTERN_PACK_DOMAIN,
            {
                "pack_id": self.pack_id,
                "version": self.version,
                "description": self.description,
            },
        )


def _evidence_ids(graph: PythonSemanticGraph, subjects: set[str]) -> list[str]:
    anchors = []
    for item in [*graph.instances, *graph.calls, *graph.repeats, *graph.parameter_groups]:
        identifier = getattr(item, "instance_id", None) or getattr(item, "call_id", None) or getattr(item, "repeat_id", None)
        identifier = identifier or getattr(item, "parameter_group_id", None)
        if identifier in subjects:
            anchors.append(item.anchor)
    return sorted(
        {
            evidence.evidence_id
            for evidence in graph.evidence
            for anchor in anchors
            if evidence.anchor.logical_path == anchor.logical_path
            and evidence.anchor.byte_start == anchor.byte_start
            and evidence.anchor.byte_length == anchor.byte_length
        }
    )


def _binding_id(pack_id: str, graph: PythonSemanticGraph) -> str:
    seed = hashlib.sha256(f"{pack_id}:{graph.graph_id}".encode()).hexdigest()[:20]
    return f"pattern-binding:{pack_id.rsplit(':', 1)[-1]}.{seed}"


def _transformer_match(graph: PythonSemanticGraph, digest: str) -> PatternBindingV2 | None:
    attention = [
        call
        for call in graph.calls
        if call.definition_ref
        and call.definition_ref.definition_id == "pytorch.nn.multiheadattention"
    ]
    if not attention:
        return None
    self_attention = []
    cross_attention = []
    mask_bindings: list[str] = []
    for call in attention:
        inputs = {item.port_id: item.value_id for item in call.input_bindings}
        if inputs.get("query") == inputs.get("key") == inputs.get("value"):
            self_attention.append(call.call_id)
        elif inputs.get("key") == inputs.get("value") and inputs.get("query") != inputs.get("key"):
            cross_attention.append(call.call_id)
        mask_bindings.extend(
            item.value_id
            for item in call.input_bindings
            if item.port_id in {"attention_mask", "key_padding_mask"}
        )
    repeat_ids = [item.repeat_id for item in graph.repeats]
    subjects = {
        *[item.call_id for item in attention],
        *repeat_ids,
    }
    tied_groups = [
        item.parameter_group_id
        for item in graph.parameter_groups
        if item.binding_kind == "tied"
    ]
    subjects.update(tied_groups)
    fidelity = "exact" if self_attention and cross_attention and repeat_ids else "schematic"
    return PatternBindingV2(
        binding_id=_binding_id("pattern-pack:transformer-v2", graph),
        pack_id="pattern-pack:transformer-v2",
        pack_digest=digest,
        pattern_id="pattern:transformer.encoder-decoder",
        fidelity=fidelity,
        subject_ids=sorted(subjects),
        template_id="template:transformer.encoder-decoder",
        parameters={
            "self_attention_count": len(self_attention),
            "cross_attention_count": len(cross_attention),
            "repeat_count": len(repeat_ids),
            "weight_tying": bool(tied_groups),
        },
        slot_bindings={
            "self_attention": sorted(self_attention),
            "cross_attention": sorted(cross_attention),
            "mask_values": sorted(set(mask_bindings)),
            "repeats": sorted(repeat_ids),
            "parameter_sharing": sorted(tied_groups),
        },
        evidence_ids=_evidence_ids(graph, subjects),
    )


def _family_matcher(
    family: str,
    tokens: tuple[str, ...],
) -> Callable[[PythonSemanticGraph, str], PatternBindingV2 | None]:
    def match(graph: PythonSemanticGraph, digest: str) -> PatternBindingV2 | None:
        searchable = " ".join(
            [
                graph.entrypoint,
                *[item.qualified_name for item in graph.definitions],
                *[item.instance_path for item in graph.instances],
            ]
        ).lower()
        if not any(token in searchable for token in tokens):
            return None
        subjects = {
            *[item.definition_id for item in graph.definitions],
            *[item.instance_id for item in graph.instances],
            *[item.call_id for item in graph.calls],
            *[item.repeat_id for item in graph.repeats],
        }
        structural = bool(graph.calls and graph.instances)
        return PatternBindingV2(
            binding_id=_binding_id(f"pattern-pack:{family}-v2", graph),
            pack_id=f"pattern-pack:{family}-v2",
            pack_digest=digest,
            pattern_id=f"pattern:{family}.family",
            fidelity="schematic" if structural else "opaque",
            subject_ids=sorted(subjects),
            template_id=f"template:{family}.family",
            parameters={
                "call_count": len(graph.calls),
                "repeat_count": len(graph.repeats),
                "classification_basis": "semantic-graph-predicate",
            },
            slot_bindings={
                "calls": sorted(item.call_id for item in graph.calls),
                "repeats": sorted(item.repeat_id for item in graph.repeats),
            },
            evidence_ids=_evidence_ids(graph, subjects),
        )

    return match


BUILTIN_V2_PATTERN_PACKS = (
    PatternPack(
        "pattern-pack:transformer-v2",
        "1.0.0",
        "Evidence-backed Transformer self/cross attention, repeat, mask, and sharing binding.",
        _transformer_match,
    ),
    PatternPack(
        "pattern-pack:autoformer-v2",
        "1.0.0",
        "Semantic refinement for Autoformer family structures.",
        _family_matcher("autoformer", ("autoformer", "autocorrelation", "seriesdecomp")),
    ),
    PatternPack(
        "pattern-pack:itransformer-v2",
        "1.0.0",
        "Semantic refinement for iTransformer family structures.",
        _family_matcher("itransformer", ("itransformer",)),
    ),
    PatternPack(
        "pattern-pack:patchtst-v2",
        "1.0.0",
        "Semantic refinement for PatchTST family structures.",
        _family_matcher("patchtst", ("patchtst", "patch_embedding")),
    ),
    PatternPack(
        "pattern-pack:timemixer-v2",
        "1.0.0",
        "Semantic refinement for TimeMixer family structures.",
        _family_matcher("timemixer", ("timemixer", "pastdecomposablemixing")),
    ),
)


def builtin_pattern_pack_digests() -> list[str]:
    return sorted(item.digest for item in BUILTIN_V2_PATTERN_PACKS)


def apply_builtin_pattern_packs(graph: PythonSemanticGraph) -> PythonSemanticGraph:
    bindings = [
        binding
        for pack in BUILTIN_V2_PATTERN_PACKS
        if (binding := pack.matcher(graph, pack.digest)) is not None
    ]
    values = {
        "schema_version": graph.schema_version,
        "graph_id": graph.graph_id,
        "source_corpus_digest": graph.source_corpus_digest,
        "entrypoint": graph.entrypoint,
        "definitions": graph.definitions,
        "instances": graph.instances,
        "calls": graph.calls,
        "values": graph.values,
        "graph_input_value_ids": graph.graph_input_value_ids,
        "graph_output_value_ids": graph.graph_output_value_ids,
        "control_regions": graph.control_regions,
        "parameter_groups": graph.parameter_groups,
        "repeats": graph.repeats,
        "pattern_bindings": bindings,
        "evidence": graph.evidence,
        "diagnostics": graph.diagnostics,
    }
    prototype = PythonSemanticGraph.model_construct(
        semantic_graph_digest="0" * 64,
        **values,
    )
    digest = domain_digest(SEMANTIC_GRAPH_DIGEST_DOMAIN, semantic_graph_payload(prototype))
    return PythonSemanticGraph(semantic_graph_digest=digest, **values)
