from __future__ import annotations

from typing import Any

from .models.architecture import ArchitectureIR
from .models.common import canonical_json
from .models.patch import ExpectedGraphDelta
from .models.validation import (
    IdentityChange,
    ObservedGraphDelta,
    ObservedParameterChange,
    Severity,
    ValidationIssue,
    ValidationReport,
)


def _canonical(value: Any) -> bytes:
    return canonical_json(value)


def _parameters(node: Any) -> dict[str, Any]:
    return {item.name: item.value for item in node.parameters}


def _parameter_descriptors(node: Any) -> dict[str, Any]:
    return {
        item.name: {
            "source_name": item.source_name,
            "expression": item.expression,
            "origin": item.origin.model_dump(mode="json"),
            "evidence_sources": sorted((e.source.value, e.confidence.value) for e in item.evidence),
        }
        for item in node.parameters
    }


def _node_semantics(node: Any) -> dict[str, Any]:
    data = node.model_dump(mode="json")
    for key in ("parameters", "identity_id", "source_anchor_ids"):
        data.pop(key)
    data["metadata"] = {
        key: value
        for key, value in data.get("metadata", {}).items()
        if key not in {"analysis_ms", "cache_key", "source_revision"}
    }
    return data


def _edge_semantics(edge: Any) -> dict[str, Any]:
    data = edge.model_dump(mode="json")
    evidence = data.pop("evidence", [])
    data["evidence_sources"] = sorted((item["source"], item["confidence"]) for item in evidence)
    return data


def architecture_diff(before: ArchitectureIR, after: ArchitectureIR) -> ObservedGraphDelta:
    old_nodes = {node.node_id: node for node in before.nodes}
    new_nodes = {node.node_id: node for node in after.nodes}
    old_edges = {edge.edge_id: edge for edge in before.edges}
    new_edges = {edge.edge_id: edge for edge in after.edges}
    old_repeats = {repeat.repeat_id: repeat for repeat in before.repeats}
    new_repeats = {repeat.repeat_id: repeat for repeat in after.repeats}
    modified_nodes: list[str] = []
    parameter_changes: list[ObservedParameterChange] = []
    identity_changes: list[IdentityChange] = []
    for node_id in sorted(set(old_nodes) & set(new_nodes)):
        old_node, new_node = old_nodes[node_id], new_nodes[node_id]
        if _canonical(_node_semantics(old_node)) != _canonical(_node_semantics(new_node)):
            modified_nodes.append(node_id)
        if _canonical(_parameter_descriptors(old_node)) != _canonical(_parameter_descriptors(new_node)):
            modified_nodes.append(node_id)
        old_params, new_params = _parameters(old_node), _parameters(new_node)
        for name in sorted(set(old_params) | set(new_params)):
            if name not in old_params or name not in new_params:
                modified_nodes.append(node_id)
            elif type(old_params[name]) is not type(new_params[name]) or old_params[name] != new_params[name]:
                parameter_changes.append(
                    ObservedParameterChange(
                        node_id=node_id, parameter=name, before=old_params[name], after=new_params[name]
                    )
                )
        if old_node.identity_id != new_node.identity_id:
            identity_changes.append(
                IdentityChange(
                    node_id=node_id,
                    before_identity_id=old_node.identity_id,
                    after_identity_id=new_node.identity_id,
                )
            )
    return ObservedGraphDelta(
        added_node_ids=sorted(set(new_nodes) - set(old_nodes)),
        removed_node_ids=sorted(set(old_nodes) - set(new_nodes)),
        modified_node_ids=sorted(set(modified_nodes)),
        added_edge_ids=sorted(set(new_edges) - set(old_edges)),
        removed_edge_ids=sorted(set(old_edges) - set(new_edges)),
        modified_edge_ids=sorted(
            edge_id
            for edge_id in set(old_edges) & set(new_edges)
            if _canonical(_edge_semantics(old_edges[edge_id])) != _canonical(_edge_semantics(new_edges[edge_id]))
        ),
        modified_repeat_ids=sorted(
            repeat_id
            for repeat_id in set(old_repeats) | set(new_repeats)
            if repeat_id not in old_repeats
            or repeat_id not in new_repeats
            or old_repeats[repeat_id] != new_repeats[repeat_id]
        ),
        parameter_changes=parameter_changes,
        identity_changes=identity_changes,
    )


def _change_key(change: Any) -> tuple[str, str, bytes, bytes]:
    return change.node_id, change.parameter, _canonical(change.before), _canonical(change.after)


class GraphDeltaValidator:
    validator_id = "graph_delta_v1"

    def validate(self, expected: ExpectedGraphDelta, observed: ObservedGraphDelta) -> ValidationReport:
        issues: list[ValidationIssue] = []
        required = {_change_key(change) for change in expected.required_parameter_changes}
        actual = {_change_key(change) for change in observed.parameter_changes}
        for code, values in (
            ("EXPECTED_PARAMETER_CHANGE_MISSING", sorted(required - actual)),
            ("UNEXPECTED_PARAMETER_CHANGE", sorted(actual - required)),
        ):
            if values:
                issues.append(
                    ValidationIssue(
                        severity=Severity.ERROR,
                        code=code,
                        message=repr(values),
                        node_ids=sorted({value[0] for value in values}),
                        blocking=True,
                    )
                )
        categories = (
            ("UNEXPECTED_NODE_ADDITION", observed.added_node_ids, expected.allowed_node_additions, "node"),
            ("UNEXPECTED_NODE_REMOVAL", observed.removed_node_ids, expected.allowed_node_removals, "node"),
            ("UNEXPECTED_NODE_MODIFICATION", observed.modified_node_ids, expected.allowed_node_modifications, "node"),
            ("UNEXPECTED_EDGE_ADDITION", observed.added_edge_ids, expected.allowed_edge_additions, "edge"),
            ("UNEXPECTED_EDGE_REMOVAL", observed.removed_edge_ids, expected.allowed_edge_removals, "edge"),
            ("UNEXPECTED_EDGE_MODIFICATION", observed.modified_edge_ids, expected.allowed_edge_modifications, "edge"),
        )
        for code, found, allowed, kind in categories:
            values = sorted(set(found) - set(allowed))
            if values:
                issues.append(
                    ValidationIssue(
                        severity=Severity.ERROR,
                        code=code,
                        message=repr(values),
                        node_ids=values if kind == "node" else [],
                        edge_ids=values if kind == "edge" else [],
                        blocking=True,
                    )
                )
        if observed.modified_repeat_ids:
            issues.append(
                ValidationIssue(
                    severity=Severity.ERROR,
                    code="UNEXPECTED_REPEAT_MODIFICATION",
                    message=repr(observed.modified_repeat_ids),
                    blocking=True,
                )
            )
        if expected.require_identity_retention and observed.identity_changes:
            changed = [item.node_id for item in observed.identity_changes]
            issues.append(
                ValidationIssue(
                    severity=Severity.ERROR,
                    code="IDENTITY_NOT_RETAINED",
                    message=repr(changed),
                    node_ids=changed,
                    blocking=True,
                )
            )
        return ValidationReport(
            validator=self.validator_id,
            blocking=any(issue.blocking for issue in issues),
            issues=issues,
        )
