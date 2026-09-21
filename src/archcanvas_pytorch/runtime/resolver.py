"""Merge bounded runtime observations into Exact IR without changing source identity."""

from __future__ import annotations

from archcanvas_core.models.architecture import (
    ArchitectureIR,
    Confidence,
    Evidence,
    EvidenceSource,
    TensorSpec,
)
from archcanvas_core.models.runtime import RuntimeResolution, RuntimeTraceResult, TraceStatus
from archcanvas_core.models.validation import Severity, ValidationIssue, ValidationReport


def _matches(display_name: str, target: str) -> bool:
    return target == display_name or target.startswith(f"{display_name}.")


def _same_shape(expected: TensorSpec, observed: TensorSpec) -> bool:
    return expected.shape == observed.shape and expected.dtype == observed.dtype


class RuntimeEvidenceResolver:
    """Annotate static facts with runtime observations from a single bounded trace.

    Runtime observations can add evidence and output tensor metadata. They cannot create source
    anchors, remove static nodes, or replace source-backed identity fields.
    """

    def resolve(self, ir: ArchitectureIR, trace: RuntimeTraceResult) -> tuple[ArchitectureIR, RuntimeResolution]:
        source_backed = [node for node in ir.nodes if node.source_anchor_ids]
        if trace.source_revision != ir.source_revision:
            return ir, RuntimeResolution(
                trace_id=trace.trace_id,
                observed_node_ids=[],
                unobserved_node_ids=sorted(node.node_id for node in source_backed),
                unmatched_runtime_targets=[],
            )
        matched: dict[str, object] = {}
        unmatched_targets: list[str] = []
        for observation in trace.observations:
            candidates = [node for node in source_backed if _matches(node.display_name, observation.target)]
            if len(candidates) == 1:
                matched[candidates[0].node_id] = observation
            elif observation.operation not in {"placeholder", "output"}:
                unmatched_targets.append(observation.target)
        observed_node_ids = sorted(matched)
        unobserved_node_ids = sorted(node.node_id for node in source_backed if node.node_id not in matched)
        resolution = RuntimeResolution(
            trace_id=trace.trace_id,
            observed_node_ids=observed_node_ids,
            unobserved_node_ids=unobserved_node_ids,
            unmatched_runtime_targets=sorted(set(unmatched_targets)),
        )

        if trace.status is not TraceStatus.SUCCEEDED:
            return ir, resolution
        nodes = []
        for node in ir.nodes:
            observation = matched.get(node.node_id)
            status = "observed" if observation is not None else "not_observed"
            metadata = {**node.metadata, "runtime_status": status, "runtime_trace_id": trace.trace_id}
            output_ports = node.output_ports
            if observation is not None and observation.output_tensor is not None and output_ports:
                output_ports = [
                    port.model_copy(update={"tensor": observation.output_tensor})
                    if index == 0
                    else port
                    for index, port in enumerate(output_ports)
                ]
            nodes.append(node.model_copy(update={"metadata": metadata, "output_ports": output_ports}))

        observed_set = set(observed_node_ids)
        edges = []
        for edge in ir.edges:
            if edge.source_node_id in observed_set and edge.target_node_id in observed_set:
                evidence = [
                    *edge.evidence,
                    Evidence(
                        source=EvidenceSource.FX
                        if trace.provider.value == "torch_fx"
                        else EvidenceSource.TORCH_EXPORT,
                        confidence=Confidence.CONFIRMED,
                        description="Observed in isolated runtime trace",
                        anchor_id=None,
                        trace_id=trace.trace_id,
                    ),
                ]
                edges.append(edge.model_copy(update={"evidence": evidence}))
            else:
                edges.append(edge)
        return ir.model_copy(update={"nodes": nodes, "edges": edges}), resolution


class RuntimeShapeValidator:
    """Compare runtime tensors with any statically declared port tensors.

    A trace failure or uncovered source-backed node becomes blocking for a structural operation.
    This module never invokes a trace itself.
    """

    validator_id = "runtime_shape_v1"

    def validate(
        self,
        ir: ArchitectureIR,
        trace: RuntimeTraceResult,
        *,
        structural_change: bool,
    ) -> ValidationReport:
        _, resolution = RuntimeEvidenceResolver().resolve(ir, trace)
        issues: list[ValidationIssue] = []
        if trace.status is not TraceStatus.SUCCEEDED:
            issues.append(
                ValidationIssue(
                    severity=Severity.ERROR if structural_change else Severity.WARNING,
                    code="RUNTIME_TRACE_UNAVAILABLE",
                    message=trace.message or "runtime trace did not succeed",
                    blocking=structural_change,
                )
            )
        if resolution.unobserved_node_ids:
            issues.append(
                ValidationIssue(
                    severity=Severity.ERROR if structural_change else Severity.WARNING,
                    code="RUNTIME_COVERAGE_GAP",
                    message=repr(resolution.unobserved_node_ids),
                    node_ids=resolution.unobserved_node_ids,
                    blocking=structural_change,
                )
            )
        observations = {
            observation.target: observation
            for observation in trace.observations
            if observation.output_tensor is not None
        }
        for node in ir.nodes:
            expected = node.output_ports[0].tensor if node.output_ports else None
            observation = next(
                (item for target, item in observations.items() if _matches(node.display_name, target)), None
            )
            if expected is None or observation is None or observation.output_tensor is None:
                continue
            if not _same_shape(expected, observation.output_tensor):
                issues.append(
                    ValidationIssue(
                        severity=Severity.ERROR,
                        code="RUNTIME_SHAPE_MISMATCH",
                        message=(
                            f"{node.node_id}: expected {expected.shape}/{expected.dtype}, observed "
                            f"{observation.output_tensor.shape}/{observation.output_tensor.dtype}"
                        ),
                        node_ids=[node.node_id],
                        blocking=True,
                    )
                )
        return ValidationReport(
            validator=self.validator_id,
            blocking=any(issue.blocking for issue in issues),
            issues=issues,
        )
