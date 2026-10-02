from __future__ import annotations

import hashlib
from typing import Any

from archcanvas_core.architecture_v2 import (
    EXACT_IR_DIGEST_DOMAIN,
    ExactArchitectureIRV2,
    PythonSemanticGraph,
    exact_ir_payload,
)
from archcanvas_core.builtin_registry import BuiltinModuleRegistry
from archcanvas_core.digest_protocol import domain_digest
from archcanvas_core.models import Diagnostic
from archcanvas_core.source_v2 import AnalysisInputManifest


def _binding_diagnostics(
    graph: PythonSemanticGraph,
    registry: BuiltinModuleRegistry,
) -> list[Diagnostic]:
    diagnostics = list(graph.diagnostics)
    for call in graph.calls:
        if call.definition_ref is None:
            continue
        definition = registry.resolve_ref(
            call.definition_ref.definition_id,
            call.definition_ref.version,
            call.definition_ref.digest,
        )
        if definition is None:
            diagnostics.append(
                Diagnostic(
                    code="V2_REGISTRY_DEFINITION_MISSING",
                    severity="blocking",
                    message=f"Registry definition is unavailable for {call.call_id}.",
                    target_ids=[call.call_id],
                )
            )
            continue
        input_counts = {
            port.port_id: sum(1 for item in call.input_bindings if item.port_id == port.port_id)
            for port in definition.ports
            if port.direction == "input"
        }
        for port in (item for item in definition.ports if item.direction == "input"):
            count = input_counts[port.port_id]
            maximum = port.max_connections
            if count < port.min_connections or (
                isinstance(maximum, int) and count > maximum
            ):
                diagnostics.append(
                    Diagnostic(
                        code="V2_PORT_CARDINALITY_INVALID",
                        severity="blocking",
                        message=(
                            f"{call.call_id}.{port.port_id} has {count} bindings; "
                            f"expected {port.min_connections}..{maximum}."
                        ),
                        target_ids=[call.call_id],
                    )
                )
        declared_outputs = {
            item.port_id for item in definition.ports if item.direction == "output"
        }
        actual_outputs = {item.port_id for item in call.output_bindings}
        if declared_outputs != actual_outputs:
            diagnostics.append(
                Diagnostic(
                    code="V2_OUTPUT_BINDING_INVALID",
                    severity="blocking",
                    message=f"Output bindings do not match {definition.definition_id}.",
                    target_ids=[call.call_id],
                )
            )
    return diagnostics


def build_exact_ir_v2(
    graph: PythonSemanticGraph,
    analysis_input: AnalysisInputManifest,
    registry: BuiltinModuleRegistry,
    *,
    framework: str = "pytorch",
) -> ExactArchitectureIRV2:
    if analysis_input.source_corpus_digest != graph.source_corpus_digest:
        raise ValueError("analysis input and semantic graph reference different source corpora")
    if analysis_input.registry_digest != registry.bundle.bundle_digest:
        raise ValueError("analysis input and registry digest disagree")
    diagnostics = _binding_diagnostics(graph, registry)
    seed = hashlib.sha256(
        f"{analysis_input.analysis_input_digest}:{graph.semantic_graph_digest}".encode()
    ).hexdigest()[:24]
    values: dict[str, Any] = {
        "architecture_id": f"architecture:v2.{seed}",
        "source_corpus_digest": graph.source_corpus_digest,
        "analysis_input_digest": analysis_input.analysis_input_digest,
        "registry_digest": registry.bundle.bundle_digest,
        "semantic_graph_digest": graph.semantic_graph_digest,
        "framework": framework,
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
        "pattern_bindings": graph.pattern_bindings,
        "evidence": graph.evidence,
        "diagnostics": diagnostics,
    }
    prototype = ExactArchitectureIRV2.model_construct(exact_ir_digest="0" * 64, **values)
    digest = domain_digest(EXACT_IR_DIGEST_DOMAIN, exact_ir_payload(prototype))
    return ExactArchitectureIRV2(exact_ir_digest=digest, **values)
