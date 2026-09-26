from __future__ import annotations

import hashlib
import json
import re
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Any

from archcanvas_core.models import (
    ArchitectureEdge,
    ArchitectureIR,
    ArchitectureNode,
    PatternCapture,
    PatternPackManifest,
    PatternPredicate,
    PatternRelationConstraint,
    PatternTemplateRule,
    Port,
    TensorValue,
    VisualTemplateBinding,
    VisualTemplateManifest,
)


@dataclass(frozen=True)
class _PortRef:
    node_id: str
    port: Port
    evidence_ids: tuple[str, ...]


Entity = ArchitectureNode | ArchitectureEdge | TensorValue | _PortRef
Assignment = dict[str, tuple[str, ...]]


def _matches(value: Any, predicate: PatternPredicate) -> bool:
    if predicate.operator == "exists":
        return value is not None
    if predicate.operator == "contains":
        if isinstance(value, (list, tuple, set)):
            return any(str(predicate.value).lower() in str(item).lower() for item in value)
        return str(predicate.value).lower() in str(value).lower()
    return value == predicate.value or str(value) == str(predicate.value)


def _entity_id(entity: Entity) -> str:
    if isinstance(entity, ArchitectureNode):
        return entity.node_id
    if isinstance(entity, ArchitectureEdge):
        return entity.edge_id
    if isinstance(entity, TensorValue):
        return entity.tensor_id
    return entity.port.port_id


def _entity_evidence(entity: Entity) -> list[str]:
    if isinstance(entity, _PortRef):
        return list(entity.evidence_ids)
    return entity.evidence_ids


def _entity_accepts(entity: Entity, accepted: list[str]) -> bool:
    if isinstance(entity, ArchitectureNode):
        facts = [
            entity.kind.value,
            str(entity.attributes.get("op_type") or ""),
            str(entity.attributes.get("transform") or ""),
        ]
    elif isinstance(entity, ArchitectureEdge):
        facts = [entity.edge_type.value, entity.role]
    elif isinstance(entity, TensorValue):
        facts = [entity.role, entity.symbolic_shape, *entity.semantic_axes]
    else:
        facts = [entity.port.role, entity.port.name, entity.port.direction]
    normalized_facts = [fact.lower() for fact in facts if fact]
    return any(
        expected.lower() == fact or expected.lower() in fact
        for expected in accepted
        for fact in normalized_facts
    )


def _entity_matches(entity: Entity, predicate: PatternPredicate) -> bool:
    if isinstance(entity, ArchitectureNode):
        if predicate.fact == "node-kind":
            return _matches(entity.kind.value, predicate)
        if predicate.fact == "node-attribute":
            return _matches(entity.attributes.get(predicate.field or ""), predicate)
        if predicate.fact == "execution-predicate":
            return _matches(entity.execution_predicate, predicate)
        if predicate.fact == "name-hint":
            return _matches(
                " ".join(filter(None, (entity.node_id, entity.semantic_name, entity.source_symbol))),
                predicate,
            )
    elif isinstance(entity, ArchitectureEdge):
        if predicate.fact == "edge-type":
            return _matches(entity.edge_type.value, predicate)
        if predicate.fact == "edge-route":
            return _matches(
                f"{entity.producer_id}:{entity.producer_port}->"
                f"{entity.consumer_id}:{entity.consumer_port}",
                predicate,
            )
        if predicate.fact == "shape-axis":
            return _matches(entity.symbolic_shape, predicate) or _matches(
                entity.semantic_axes, predicate
            )
        if predicate.fact == "name-hint":
            return _matches(f"{entity.edge_id} {entity.role}", predicate)
    elif isinstance(entity, TensorValue):
        if predicate.fact == "tensor-role":
            return _matches(entity.role, predicate)
        if predicate.fact == "shape-axis":
            return _matches(entity.symbolic_shape, predicate) or _matches(
                entity.semantic_axes, predicate
            )
        if predicate.fact == "name-hint":
            return _matches(f"{entity.tensor_id} {entity.role}", predicate)
    elif predicate.fact == "port-role":
        return _matches(entity.port.role, predicate)
    elif predicate.fact == "name-hint":
        return _matches(f"{entity.port.port_id} {entity.port.name} {entity.port.role}", predicate)
    return False


class _GraphFacts:
    def __init__(self, architecture: ArchitectureIR) -> None:
        self.architecture = architecture
        self.nodes = {node.node_id: node for node in architecture.nodes}
        self.edges = {edge.edge_id: edge for edge in architecture.edges}
        self.tensors = {tensor.tensor_id: tensor for tensor in architecture.tensors}
        self.ports = {
            port.port_id: _PortRef(node.node_id, port, tuple(node.evidence_ids))
            for node in architecture.nodes
            for port in [*node.input_ports, *node.output_ports]
        }
        self.outgoing: dict[str, list[ArchitectureEdge]] = defaultdict(list)
        self.incoming: dict[str, list[ArchitectureEdge]] = defaultdict(list)
        for edge in architecture.edges:
            self.outgoing[edge.producer_id].append(edge)
            self.incoming[edge.consumer_id].append(edge)
        self._distance_cache: dict[tuple[str, str, str | None], int | None] = {}

    def entities(self, entity: str) -> dict[str, Entity]:
        return {
            "node": self.nodes,
            "edge": self.edges,
            "port": self.ports,
            "tensor": self.tensors,
        }[entity]

    def distance(self, source: str, target: str, edge_type: str | None = None) -> int | None:
        key = (source, target, edge_type)
        if key in self._distance_cache:
            return self._distance_cache[key]
        queue = deque([(source, 0)])
        visited = {source}
        while queue:
            current, distance = queue.popleft()
            for edge in self.outgoing[current]:
                if edge_type is not None and edge.edge_type.value != edge_type:
                    continue
                if edge.consumer_id == target:
                    self._distance_cache[key] = distance + 1
                    return distance + 1
                if edge.consumer_id not in visited:
                    visited.add(edge.consumer_id)
                    queue.append((edge.consumer_id, distance + 1))
        self._distance_cache[key] = None
        return None


def _candidate_choices(capture: PatternCapture, facts: _GraphFacts) -> list[tuple[str, ...]]:
    candidates = tuple(
        sorted(
            entity_id
            for entity_id, entity in facts.entities(capture.entity).items()
            if _entity_matches(entity, capture.selector)
        )
    )
    if capture.cardinality == "one":
        return [(candidate,) for candidate in candidates]
    if capture.cardinality == "optional":
        return [(), *((candidate,) for candidate in candidates)]
    if capture.cardinality == "one-or-more":
        return [candidates] if candidates else []
    return [candidates]


def _filtered_direct_edges(
    facts: _GraphFacts,
    source: str,
    target: str,
    relation: PatternRelationConstraint,
) -> list[ArchitectureEdge]:
    edges = [edge for edge in facts.outgoing[source] if edge.consumer_id == target]
    if relation.edge_type is not None:
        edges = [edge for edge in edges if edge.edge_type.value == relation.edge_type]
    if relation.port_role is not None:
        edges = [
            edge
            for edge in edges
            if relation.port_role
            in {
                facts.ports[edge.producer_port].port.role,
                facts.ports[edge.consumer_port].port.role,
            }
        ]
    return edges


def _node_relation(
    facts: _GraphFacts,
    source: str,
    target: str,
    relation: PatternRelationConstraint,
) -> tuple[bool, int]:
    if source not in facts.nodes or target not in facts.nodes:
        return False, 0
    if relation.relation == "produces":
        matched = bool(_filtered_direct_edges(facts, source, target, relation))
        return matched, 1 if matched else 0
    if relation.relation == "consumes":
        matched = bool(_filtered_direct_edges(facts, target, source, relation))
        return matched, 1 if matched else 0
    if relation.relation == "connects":
        matched = bool(
            _filtered_direct_edges(facts, source, target, relation)
            or _filtered_direct_edges(facts, target, source, relation)
        )
        return matched, 1 if matched else 0
    if relation.relation == "contains":
        cursor = facts.nodes[target].parent_id
        distance = 1
        while cursor is not None:
            if cursor == source:
                return True, distance
            parent = facts.nodes.get(cursor)
            cursor = parent.parent_id if parent is not None else None
            distance += 1
        return False, 0
    if relation.relation == "shares-input":
        source_inputs = {
            (edge.producer_id, edge.tensor_id) for edge in facts.incoming[source]
        }
        target_inputs = {
            (edge.producer_id, edge.tensor_id) for edge in facts.incoming[target]
        }
        matched = bool(source_inputs & target_inputs)
        return matched, 1 if matched else 0
    if relation.relation == "shares-parameter":
        left = facts.nodes[source].parameter_identity
        right = facts.nodes[target].parameter_identity
        matched = left == right and left != "not-applicable"
        return matched, 1 if matched else 0
    distance = facts.distance(source, target, relation.edge_type)
    return distance is not None, distance or 0


def _relation_result(
    facts: _GraphFacts,
    assignment: Assignment,
    relation: PatternRelationConstraint,
) -> tuple[bool, int]:
    sources = assignment[relation.source_capture]
    targets = assignment[relation.target_capture]
    results = [
        _node_relation(facts, source, target, relation)
        for source in sources
        for target in targets
    ]
    if not results:
        return False, 0
    matched = [distance for passed, distance in results if passed]
    return bool(matched), min(matched) if matched else 0


def _weak_name_score(
    assignment: Assignment,
    captures: dict[str, PatternCapture],
    facts: _GraphFacts,
) -> int:
    score = 0
    aliases = {"projection": "proj", "weights": "weight", "scores": "score"}
    for capture_id, entity_ids in assignment.items():
        tokens = [aliases.get(token, token) for token in re.split(r"[._:-]+", capture_id)]
        for entity_id in entity_ids:
            entity = facts.entities(captures[capture_id].entity)[entity_id]
            if isinstance(entity, ArchitectureNode):
                text = " ".join(
                    filter(
                        None,
                        (
                            entity.node_id,
                            entity.semantic_name,
                            entity.source_symbol,
                            str(entity.attributes.get("op_type") or ""),
                        ),
                    )
                ).lower()
            else:
                text = entity_id.lower()
            normalized = set(re.split(r"[^a-z0-9]+", text))
            score += sum(token in normalized for token in tokens)
    return score


def _assignment_score(
    assignment: Assignment,
    rule: PatternTemplateRule,
    captures: dict[str, PatternCapture],
    facts: _GraphFacts,
) -> tuple[int, int, int]:
    optional_hits = 0
    distance = 0
    for relation in rule.relations:
        passed, relation_distance = _relation_result(facts, assignment, relation)
        optional_hits += int(passed and not relation.required)
        if passed:
            distance += relation_distance
    return optional_hits, -distance, _weak_name_score(assignment, captures, facts)


def _slot_map(
    template: VisualTemplateManifest,
    captures: dict[str, PatternCapture],
    assignment: Assignment,
    entity: str,
) -> dict[str, list[str]]:
    slots = {slot.slot_id: slot for slot in template.slots}
    return {
        capture_id: list(entity_ids)
        for capture_id, entity_ids in sorted(assignment.items())
        if captures[capture_id].entity == entity
        and capture_id in slots
        and entity_ids
    }


def binding_digest(
    *,
    template: VisualTemplateManifest,
    exact_ir_digest: str,
    root_canonical_node_ids: list[str],
    node_slots: dict[str, list[str]],
    edge_slots: dict[str, list[str]],
    port_slots: dict[str, list[str]],
    tensor_slots: dict[str, list[str]],
    fidelity: str,
) -> str:
    payload = {
        "template_id": template.template_id,
        "template_version": template.version,
        "exact_ir_digest": exact_ir_digest,
        "root_canonical_node_ids": sorted(root_canonical_node_ids),
        "node_slots": {key: sorted(value) for key, value in sorted(node_slots.items())},
        "edge_slots": {key: sorted(value) for key, value in sorted(edge_slots.items())},
        "port_slots": {key: sorted(value) for key, value in sorted(port_slots.items())},
        "tensor_slots": {key: sorted(value) for key, value in sorted(tensor_slots.items())},
        "fidelity": fidelity,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def validate_template_binding(
    architecture: ArchitectureIR,
    template: VisualTemplateManifest,
    binding: VisualTemplateBinding,
    *,
    exact_ir_digest: str,
) -> None:
    if binding.template_id != template.template_id or binding.template_version != template.version:
        raise ValueError("visual template binding references an incompatible template version")
    facts = _GraphFacts(architecture)
    if any(node_id not in facts.nodes for node_id in binding.root_canonical_node_ids):
        raise ValueError("visual template binding root references a missing canonical node")
    mappings = {
        "node": binding.node_slots,
        "edge": binding.edge_slots,
        "port": binding.port_slots,
        "tensor": binding.tensor_slots,
    }
    slot_by_id = {slot.slot_id: slot for slot in template.slots}
    for entity, mapping in mappings.items():
        for slot_id, canonical_ids in mapping.items():
            slot = slot_by_id.get(slot_id)
            if slot is None or slot.kind != entity:
                raise ValueError(f"visual template binding uses invalid {entity} slot {slot_id}")
            if any(item not in facts.entities(entity) for item in canonical_ids):
                raise ValueError(
                    f"visual template {entity} slot {slot_id} references a missing canonical ID"
                )
            if any(
                not _entity_accepts(facts.entities(entity)[item], slot.accepts)
                for item in canonical_ids
            ):
                raise ValueError(
                    f"visual template {entity} slot {slot_id} rejects a bound canonical entity"
                )
    if binding.fidelity == "exact":
        for slot in template.slots:
            count = len(mappings[slot.kind].get(slot.slot_id, []))
            valid = {
                "one": count == 1,
                "optional": count <= 1,
                "one-or-more": count >= 1,
                "many": True,
            }[slot.cardinality]
            if not valid:
                raise ValueError(
                    f"exact visual template binding violates cardinality for {slot.slot_id}"
                )
    bound_nodes = {item for values in binding.node_slots.values() for item in values}
    bound_ports = {item for values in binding.port_slots.values() for item in values}
    for values in binding.edge_slots.values():
        for edge_id in values:
            edge = facts.edges[edge_id]
            if bound_nodes and not {edge.producer_id, edge.consumer_id} <= bound_nodes:
                raise ValueError("visual template edge endpoint is not covered by bound nodes")
            if bound_ports and not {edge.producer_port, edge.consumer_port} <= bound_ports:
                raise ValueError("visual template edge endpoint is not covered by bound ports")
    evidence_ids = {
        evidence_id
        for node_id in binding.root_canonical_node_ids
        for evidence_id in facts.nodes[node_id].evidence_ids
    }
    for entity, mapping in mappings.items():
        for canonical_ids in mapping.values():
            for canonical_id in canonical_ids:
                evidence_ids.update(_entity_evidence(facts.entities(entity)[canonical_id]))
    if binding.evidence_ids != sorted(evidence_ids):
        raise ValueError("visual template binding evidence is not the stable entity evidence union")
    expected_digest = binding_digest(
        template=template,
        exact_ir_digest=exact_ir_digest,
        root_canonical_node_ids=binding.root_canonical_node_ids,
        node_slots=binding.node_slots,
        edge_slots=binding.edge_slots,
        port_slots=binding.port_slots,
        tensor_slots=binding.tensor_slots,
        fidelity=binding.fidelity,
    )
    if binding.binding_digest != expected_digest:
        raise ValueError("visual template binding digest is stale")


def create_template_binding(
    architecture: ArchitectureIR,
    template: VisualTemplateManifest,
    *,
    exact_ir_digest: str,
    root_canonical_node_ids: list[str],
    node_slots: dict[str, list[str]] | None = None,
    edge_slots: dict[str, list[str]] | None = None,
    port_slots: dict[str, list[str]] | None = None,
    tensor_slots: dict[str, list[str]] | None = None,
    predicate_ids: list[str] | None = None,
    fidelity: str = "exact",
) -> VisualTemplateBinding:
    facts = _GraphFacts(architecture)
    normalized = {
        "node": {key: sorted(value) for key, value in sorted((node_slots or {}).items())},
        "edge": {key: sorted(value) for key, value in sorted((edge_slots or {}).items())},
        "port": {key: sorted(value) for key, value in sorted((port_slots or {}).items())},
        "tensor": {key: sorted(value) for key, value in sorted((tensor_slots or {}).items())},
    }
    roots = sorted(root_canonical_node_ids)
    evidence_ids = {
        evidence_id
        for node_id in roots
        if node_id in facts.nodes
        for evidence_id in facts.nodes[node_id].evidence_ids
    }
    for entity, mapping in normalized.items():
        entities = facts.entities(entity)
        for canonical_ids in mapping.values():
            for canonical_id in canonical_ids:
                if canonical_id in entities:
                    evidence_ids.update(_entity_evidence(entities[canonical_id]))
    digest = binding_digest(
        template=template,
        exact_ir_digest=exact_ir_digest,
        root_canonical_node_ids=roots,
        node_slots=normalized["node"],
        edge_slots=normalized["edge"],
        port_slots=normalized["port"],
        tensor_slots=normalized["tensor"],
        fidelity=fidelity,
    )
    binding = VisualTemplateBinding(
        binding_id=f"binding:{template.template_id}:{digest[:16]}",
        template_id=template.template_id,
        template_version=template.version,
        root_canonical_node_ids=roots,
        node_slots=normalized["node"],
        edge_slots=normalized["edge"],
        port_slots=normalized["port"],
        tensor_slots=normalized["tensor"],
        evidence_ids=sorted(evidence_ids),
        predicate_ids=sorted(set(predicate_ids or [])),
        fidelity=fidelity,
        binding_digest=digest,
    )
    validate_template_binding(
        architecture,
        template,
        binding,
        exact_ir_digest=exact_ir_digest,
    )
    return binding


def _rule_assignments(
    architecture: ArchitectureIR,
    rule: PatternTemplateRule,
) -> tuple[list[Assignment], list[str]]:
    facts = _GraphFacts(architecture)
    captures = {capture.capture_id: capture for capture in rule.captures}
    choices = {
        capture.capture_id: _candidate_choices(capture, facts) for capture in rule.captures
    }
    missing = sorted(capture_id for capture_id, values in choices.items() if not values)
    if missing:
        return [], [f"template_capture_unmatched:{rule.rule_id}:{capture_id}" for capture_id in missing]
    root_choices = choices[rule.root_capture]
    remaining = sorted(
        (capture_id for capture_id in captures if capture_id != rule.root_capture),
        key=lambda capture_id: (len(choices[capture_id]), capture_id),
    )
    selected: list[Assignment] = []
    reasons: list[str] = []

    for root_choice in root_choices:
        valid: list[Assignment] = []

        def visit(
            index: int,
            assignment: Assignment,
            valid_assignments: list[Assignment] = valid,
        ) -> None:
            if index == len(remaining):
                if all(
                    not relation.required or _relation_result(facts, assignment, relation)[0]
                    for relation in rule.relations
                ):
                    valid_assignments.append(dict(assignment))
                return
            capture_id = remaining[index]
            capture = captures[capture_id]
            used = {
                entity_id
                for assigned_id, entity_ids in assignment.items()
                if captures[assigned_id].entity == capture.entity
                for entity_id in entity_ids
            }
            for choice in choices[capture_id]:
                if used & set(choice):
                    continue
                assignment[capture_id] = choice
                failed = any(
                    relation.required
                    and relation.source_capture in assignment
                    and relation.target_capture in assignment
                    and not _relation_result(facts, assignment, relation)[0]
                    for relation in rule.relations
                )
                if not failed:
                    visit(index + 1, assignment)
                assignment.pop(capture_id)

        visit(0, {rule.root_capture: root_choice})
        if not valid:
            continue
        scored = [(_assignment_score(item, rule, captures, facts), item) for item in valid]
        best_score = max(score for score, _ in scored)
        best = [item for score, item in scored if score == best_score]
        if len(best) != 1:
            reasons.append(
                f"ambiguous_template_binding:{rule.rule_id}:{root_choice[0]}:{len(best)}"
            )
            continue
        selected.append(best[0])
    return selected, reasons


def build_template_bindings(
    architecture: ArchitectureIR,
    manifest: PatternPackManifest,
    templates: dict[str, VisualTemplateManifest],
    *,
    exact_ir_digest: str,
) -> tuple[list[VisualTemplateBinding], list[str]]:
    bindings: list[VisualTemplateBinding] = []
    reasons: list[str] = []
    for rule in manifest.template_rules:
        template = templates.get(rule.template_id)
        if template is None:
            reasons.append(f"template_not_loaded:{rule.rule_id}:{rule.template_id}")
            continue
        if architecture.schema_version not in template.supported_ir_versions:
            reasons.append(f"template_ir_version_unsupported:{rule.rule_id}")
            continue
        assignments, assignment_reasons = _rule_assignments(architecture, rule)
        reasons.extend(assignment_reasons)
        captures = {capture.capture_id: capture for capture in rule.captures}
        for assignment in assignments:
            try:
                bindings.append(
                    create_template_binding(
                        architecture,
                        template,
                        exact_ir_digest=exact_ir_digest,
                        root_canonical_node_ids=list(assignment[rule.root_capture]),
                        node_slots=_slot_map(template, captures, assignment, "node"),
                        edge_slots=_slot_map(template, captures, assignment, "edge"),
                        port_slots=_slot_map(template, captures, assignment, "port"),
                        tensor_slots=_slot_map(template, captures, assignment, "tensor"),
                        predicate_ids=[
                            *[capture.selector.predicate_id for capture in rule.captures],
                            *[relation.relation_id for relation in rule.relations],
                        ],
                        fidelity="exact",
                    )
                )
            except ValueError as exc:
                reasons.append(f"template_binding_invalid:{rule.rule_id}:{exc}")
    return sorted(bindings, key=lambda item: item.binding_id), sorted(set(reasons))
