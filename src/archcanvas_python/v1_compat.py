from __future__ import annotations

import hashlib
import re
from collections import defaultdict
from pathlib import Path

from archcanvas_core.architecture_v2 import ExactArchitectureIRV2
from archcanvas_core.builtin_registry import BuiltinModuleRegistry
from archcanvas_core.models import (
    ArchitectureEdge,
    ArchitectureIR,
    ArchitectureNode,
    ArchitectureParameter,
    Confidence,
    EdgeType,
    EvidenceKind,
    EvidenceRecord,
    FanoutRelation,
    NodeKind,
    ParameterOrigin,
    Port,
    Repeat,
    SourceFile,
    SourceSnapshot,
    TensorValue,
    UnresolvedFact,
)
from archcanvas_core.source_v2 import AnalysisInputManifest, SourceCorpus

from .analyzer import AnalysisBundle


def _node_id(call_id: str) -> str:
    return f"node:{call_id.removeprefix('call:')}"


def _container_node_id(instance_path: str) -> str:
    normalized = re.sub(r"[^a-z0-9._:-]+", "-", instance_path.lower()).strip("-.")
    return f"node:module.{normalized}"


def _port_id(node_id: str, port_id: str) -> str:
    return f"port:{node_id.removeprefix('node:')}.{port_id}"


def _evidence_for_anchor(ir: ExactArchitectureIRV2, anchor: object) -> list[str]:
    return [
        item.evidence_id
        for item in ir.evidence
        if item.anchor.logical_path == anchor.logical_path
        and item.anchor.byte_start == anchor.byte_start
        and item.anchor.byte_length == anchor.byte_length
    ]


def _nearest_local_parent(
    ir: ExactArchitectureIRV2,
    instance_id: str,
) -> str | None:
    instances = {item.instance_id: item for item in ir.instances}
    current = instances.get(instance_id)
    while current is not None:
        if current.local_definition_id is not None:
            return _container_node_id(current.instance_path)
        current = instances.get(current.parent_instance_id) if current.parent_instance_id else None
    return None


def _v1_evidence(ir: ExactArchitectureIRV2) -> list[EvidenceRecord]:
    return [
        EvidenceRecord(
            evidence_id=item.evidence_id,
            kind=EvidenceKind.SOURCE,
            path=item.anchor.logical_path,
            symbol=item.anchor.qualified_symbol,
            span=item.anchor.line_span,
            file_sha256=item.anchor.blob_digest,
            revision=f"corpus:{ir.source_corpus_digest}",
            claim=item.claim,
            confidence=item.confidence,
            execution_predicate="static-v2",
        )
        for item in ir.evidence
    ]


def project_v1_compatibility(
    ir: ExactArchitectureIRV2,
    corpus: SourceCorpus,
    analysis_input: AnalysisInputManifest,
    registry: BuiltinModuleRegistry,
    snapshot_root: Path,
    *,
    task: str,
    execution_mode: str,
) -> AnalysisBundle:
    if corpus.source_corpus_digest != ir.source_corpus_digest:
        raise ValueError("v1 compatibility projection received a different source corpus")
    snapshot_id = f"snapshot:v2.{ir.source_corpus_digest[:24]}"
    snapshot = SourceSnapshot(
        snapshot_id=snapshot_id,
        project_root=str(snapshot_root.resolve()),
        revision=f"corpus:{ir.source_corpus_digest}",
        entrypoint=ir.entrypoint,
        task=task,
        execution_mode=execution_mode,  # type: ignore[arg-type]
        framework=ir.framework,
        adapter_version="python-frontend-v2",
        config_digest=analysis_input.config_digest,
        source_files=[
            SourceFile(path=item.logical_path, sha256=item.sha256)
            for item in corpus.files
        ],
    )
    evidence = _v1_evidence(ir)
    fallback_evidence = evidence[0].evidence_id if evidence else None
    instances = {item.instance_id: item for item in ir.instances}
    registry_calls = [item for item in ir.calls if item.definition_ref is not None]
    non_registry_calls = [item for item in ir.calls if item.definition_ref is None]
    node_by_call = {item.call_id: _node_id(item.call_id) for item in ir.calls}
    definitions = {item.definition_id: item for item in ir.definitions}
    parameter_group_by_instance = {
        instance_id: group
        for group in ir.parameter_groups
        for instance_id in group.member_instance_ids
    }
    repeat_by_call = {
        call_id: repeat.repeat_id
        for repeat in ir.repeats
        for call_id in repeat.body_call_ids
    }
    pattern_summaries = [
        {
            "binding_id": item.binding_id,
            "pack_id": item.pack_id,
            "pack_digest": item.pack_digest,
            "pattern_id": item.pattern_id,
            "fidelity": item.fidelity,
            "template_id": item.template_id,
            "subject_ids": item.subject_ids,
            "slot_bindings": item.slot_bindings,
            "evidence_ids": item.evidence_ids,
        }
        for item in ir.pattern_bindings
    ]

    nodes: list[ArchitectureNode] = []
    container_ids: dict[str, str] = {}
    for instance in ir.instances:
        if instance.local_definition_id is None:
            continue
        node_id = _container_node_id(instance.instance_path)
        container_ids[instance.instance_id] = node_id
        parent_id = (
            container_ids.get(instance.parent_instance_id)
            if instance.parent_instance_id
            else None
        )
        evidence_ids = _evidence_for_anchor(ir, instance.anchor) or (
            [fallback_evidence] if fallback_evidence else []
        )
        nodes.append(
            ArchitectureNode(
                node_id=node_id,
                kind=NodeKind.MODULE_CONTAINER,
                semantic_name=instance.instance_path.split(".")[-1],
                source_symbol=instance.anchor.qualified_symbol,
                parent_id=parent_id,
                execution_predicate="static-v2",
                evidence_ids=evidence_ids,
                confidence=Confidence.EXACT,
                attributes={
                    "v2_instance_id": instance.instance_id,
                    "v2_definition_id": instance.local_definition_id,
                    **(
                        {"v2_pattern_bindings": pattern_summaries}
                        if instance.parent_instance_id is None and pattern_summaries
                        else {}
                    ),
                },
            )
        )

    for call in registry_calls:
        definition = registry.resolve_ref(
            call.definition_ref.definition_id,
            call.definition_ref.version,
            call.definition_ref.digest,
        )
        if definition is None:
            continue
        node_id = node_by_call[call.call_id]
        instance = instances.get(call.instance_id) if call.instance_id else None
        parameters = [
            ArchitectureParameter(
                name=item.parameter_name,
                source_expression=item.source_expression,
                value=item.value,
                origin=ParameterOrigin.LITERAL,
                evidence_ids=_evidence_for_anchor(ir, item.anchor)
                or _evidence_for_anchor(ir, call.anchor),
            )
            for item in (instance.constructor_arguments if instance else [])
        ]
        evidence_ids = _evidence_for_anchor(ir, call.anchor) or (
            [fallback_evidence] if fallback_evidence else []
        )
        nodes.append(
            ArchitectureNode(
                node_id=node_id,
                kind=NodeKind.OPERATOR,
                semantic_name=(
                    instance.instance_path.split(".")[-1]
                    if instance
                    else definition.definition_id.split(".")[-1]
                ),
                source_symbol=call.anchor.qualified_symbol,
                parent_id=_nearest_local_parent(ir, call.parent_module_id),
                input_ports=[
                    Port(
                        port_id=_port_id(node_id, item.port_id),
                        name=item.port_id,
                        direction="input",
                        role=item.port_id,
                    )
                    for item in definition.ports
                    if item.direction == "input"
                ],
                output_ports=[
                    Port(
                        port_id=_port_id(node_id, item.port_id),
                        name=item.port_id,
                        direction="output",
                        role=item.port_id,
                    )
                    for item in definition.ports
                    if item.direction == "output"
                ],
                parameters=parameters,
                parameter_identity=(
                    parameter_group_by_instance[instance.instance_id].parameter_group_id
                    if instance and instance.instance_id in parameter_group_by_instance
                    else "functional"
                ),
                repeat_id=repeat_by_call.get(call.call_id),
                execution_predicate="static-v2",
                evidence_ids=evidence_ids,
                confidence=call.confidence,
                attributes={
                    "v2_call_id": call.call_id,
                    "v2_instance_id": call.instance_id,
                    "definition_id": definition.definition_id,
                    "definition_version": definition.version,
                    "definition_digest": definition.digest,
                    "glyph_id": definition.glyph_id,
                    "semantic_kind": definition.semantic_kind,
                },
            )
        )

    for call in non_registry_calls:
        node_id = node_by_call[call.call_id]
        instance = instances.get(call.instance_id) if call.instance_id else None
        definition = definitions.get(call.local_definition_id or "")
        input_port_ids = list(dict.fromkeys(item.port_id for item in call.input_bindings))
        output_port_ids = list(dict.fromkeys(item.port_id for item in call.output_bindings))
        evidence_ids = _evidence_for_anchor(ir, call.anchor) or (
            [fallback_evidence] if fallback_evidence else []
        )
        nodes.append(
            ArchitectureNode(
                node_id=node_id,
                kind=NodeKind.OPAQUE_COMPOSITE,
                semantic_name=(
                    instance.instance_path.split(".")[-1]
                    if instance is not None
                    else (
                        definition.qualified_name.rsplit(".", 1)[-1]
                        if definition is not None
                        else call.anchor.qualified_symbol.rsplit(".", 1)[-1]
                    )
                ),
                source_symbol=call.anchor.qualified_symbol,
                parent_id=_nearest_local_parent(ir, call.parent_module_id),
                input_ports=[
                    Port(
                        port_id=_port_id(node_id, port_id),
                        name=port_id,
                        direction="input",
                        role=port_id,
                    )
                    for port_id in input_port_ids
                ],
                output_ports=[
                    Port(
                        port_id=_port_id(node_id, port_id),
                        name=port_id,
                        direction="output",
                        role=port_id,
                    )
                    for port_id in output_port_ids
                ],
                parameter_identity="functional",
                execution_predicate="static-v2",
                evidence_ids=evidence_ids,
                confidence=call.confidence,
                attributes={
                    "v2_call_id": call.call_id,
                    "v2_instance_id": call.instance_id,
                    "v2_local_definition_id": call.local_definition_id,
                    "implementation_status": "boundary-only",
                    "semantic_status": "unresolved",
                },
            )
        )

    values = {item.value_id: item for item in ir.values}
    root_container = next((item for item in nodes if item.parent_id is None), None)
    root_parent = root_container.node_id if root_container else None
    input_nodes: dict[str, str] = {}
    graph_input_ids = set(ir.graph_input_value_ids)
    for value in ir.values:
        if value.value_id not in graph_input_ids:
            continue
        node_id = f"node:input.{value.value_id.removeprefix('value:')}"
        input_nodes[value.value_id] = node_id
        evidence_ids = _evidence_for_anchor(ir, value.anchor) or (
            [fallback_evidence] if fallback_evidence else []
        )
        nodes.append(
            ArchitectureNode(
                node_id=node_id,
                kind=NodeKind.INPUT_OUTPUT,
                semantic_name=value.semantic_name,
                source_symbol=ir.entrypoint,
                parent_id=root_parent,
                output_ports=[
                    Port(
                        port_id=_port_id(node_id, "output"),
                        name="output",
                        direction="output",
                        role=value.semantic_name,
                    )
                ],
                execution_predicate="static-v2",
                evidence_ids=evidence_ids,
                confidence=Confidence.EXACT,
                attributes={"io": "input", "v2_value_id": value.value_id},
            )
        )

    edge_drafts: list[tuple[str, str, str, str, str, list[str]]] = []
    projected_consumer_values: set[str] = set()
    for call in ir.calls:
        consumer_id = node_by_call[call.call_id]
        for binding in call.input_bindings:
            projected_consumer_values.add(binding.value_id)
            value = values.get(binding.value_id)
            if value is None:
                continue
            if value.producer_call_id in node_by_call:
                producer_id = node_by_call[value.producer_call_id]
                producer_port = _port_id(producer_id, value.producer_port_id or "output")
            elif binding.value_id in input_nodes:
                producer_id = input_nodes[binding.value_id]
                producer_port = _port_id(producer_id, "output")
            else:
                continue
            edge_drafts.append(
                (
                    binding.value_id,
                    producer_id,
                    producer_port,
                    consumer_id,
                    _port_id(consumer_id, binding.port_id),
                    _evidence_for_anchor(ir, binding.anchor)
                    or _evidence_for_anchor(ir, call.anchor),
                )
            )

    terminal_values = [
        values[value_id]
        for value_id in ir.graph_output_value_ids
        if value_id in values and values[value_id].producer_call_id in node_by_call
    ]
    unresolved: list[UnresolvedFact] = []
    unresolved.extend(
        UnresolvedFact(
            code="V2_COMPAT_PATTERN_BINDING_LOSSY",
            message=(
                f"v1 compatibility preserves {item.binding_id} as trace metadata; "
                "its typed pattern slots require Exact Architecture IR v2."
            ),
            blocking=False,
            evidence_ids=item.evidence_ids,
        )
        for item in ir.pattern_bindings
    )
    unresolved.extend(
        UnresolvedFact(
            code="V2_COMPAT_CONTROL_FLOW_LOSSY",
            message=(
                f"v1 compatibility cannot preserve {item.kind} control region "
                f"{item.control_region_id}; use Exact Architecture IR v2 for control flow."
            ),
            blocking=False,
            evidence_ids=_evidence_for_anchor(ir, item.anchor),
        )
        for item in ir.control_regions
        if item.kind != "function"
    )
    if len(terminal_values) > 1:
        unresolved.append(
            UnresolvedFact(
                code="V2_COMPAT_MULTIPLE_OUTPUTS",
                message="v1 compatibility projection selected the first of multiple terminal outputs.",
                blocking=False,
            )
        )
    if terminal_values:
        terminal = terminal_values[0]
        output_id = "node:output"
        evidence_ids = _evidence_for_anchor(ir, terminal.anchor) or (
            [fallback_evidence] if fallback_evidence else []
        )
        nodes.append(
            ArchitectureNode(
                node_id=output_id,
                kind=NodeKind.INPUT_OUTPUT,
                semantic_name="output",
                source_symbol=ir.entrypoint,
                parent_id=root_parent,
                input_ports=[
                    Port(
                        port_id=_port_id(output_id, "input"),
                        name="input",
                        direction="input",
                        role="output",
                    )
                ],
                execution_predicate="static-v2",
                evidence_ids=evidence_ids,
                confidence=Confidence.EXACT,
                attributes={"io": "output", "v2_value_id": terminal.value_id},
            )
        )
        producer_id = node_by_call[terminal.producer_call_id]
        edge_drafts.append(
            (
                terminal.value_id,
                producer_id,
                _port_id(producer_id, terminal.producer_port_id or "output"),
                output_id,
                _port_id(output_id, "input"),
                evidence_ids,
            )
        )

    child_ids: dict[str, list[str]] = defaultdict(list)
    for node in nodes:
        if node.parent_id:
            child_ids[node.parent_id].append(node.node_id)
    nodes = [
        node.model_copy(update={"children": child_ids.get(node.node_id, [])})
        if node.kind is NodeKind.MODULE_CONTAINER
        else node
        for node in nodes
    ]

    edges: list[ArchitectureEdge] = []
    edge_consumers: dict[str, list[str]] = defaultdict(list)
    tensor_producers: dict[str, tuple[str, str, list[str]]] = {}
    for value_id, producer_id, producer_port, consumer_id, consumer_port, ids in edge_drafts:
        tensor_id = f"tensor:{value_id.removeprefix('value:')}"
        evidence_ids = ids or ([fallback_evidence] if fallback_evidence else [])
        edge_identity = f"{producer_id}:{producer_port}:{consumer_id}:{consumer_port}"
        edge_id = f"edge:v2.{hashlib.sha256(edge_identity.encode()).hexdigest()[:20]}"
        edges.append(
            ArchitectureEdge(
                edge_id=edge_id,
                tensor_id=tensor_id,
                producer_id=producer_id,
                producer_port=producer_port,
                consumer_id=consumer_id,
                consumer_port=consumer_port,
                role=consumer_port.rsplit(".", 1)[-1],
                edge_type=EdgeType.MAIN,
                evidence_ids=evidence_ids,
                confidence=Confidence.EXACT,
                execution_predicate="static-v2",
            )
        )
        edge_consumers[tensor_id].append(consumer_id)
        tensor_producers[tensor_id] = (producer_id, producer_port, evidence_ids)
    tensors = [
        TensorValue(
            tensor_id=tensor_id,
            role=tensor_id.removeprefix("tensor:"),
            producer_id=producer_id,
            producer_port=producer_port,
            consumer_ids=sorted(set(edge_consumers[tensor_id])),
            provenance="python-frontend-v2",
            confidence=Confidence.EXACT,
            evidence_ids=evidence_ids,
        )
        for tensor_id, (producer_id, producer_port, evidence_ids) in tensor_producers.items()
    ]
    fanouts = [
        FanoutRelation(
            relation_id=f"fanout:{tensor.tensor_id.removeprefix('tensor:')}",
            tensor_id=tensor.tensor_id,
            producer_id=tensor.producer_id,
            consumer_ids=tensor.consumer_ids,
            evidence_ids=tensor.evidence_ids,
        )
        for tensor in tensors
        if len(tensor.consumer_ids) > 1
    ]
    repeats = [
        Repeat(
            repeat_id=item.repeat_id,
            kind=item.kind,
            member_node_ids=[
                node_by_call[call_id]
                for call_id in item.body_call_ids
                if call_id in node_by_call
            ],
            count=item.count,
            count_symbol=item.count_symbol,
            parameter_identity=item.parameter_identity,
            evidence_ids=_evidence_for_anchor(ir, item.anchor),
        )
        for item in ir.repeats
        if any(call_id in node_by_call for call_id in item.body_call_ids)
    ]
    architecture = ArchitectureIR(
        architecture_id=f"architecture:compat.{ir.exact_ir_digest[:24]}",
        source_snapshot_id=snapshot_id,
        framework=ir.framework,
        entrypoint=ir.entrypoint,
        nodes=nodes,
        tensors=tensors,
        edges=edges,
        fanouts=fanouts,
        repeats=repeats,
        unresolved=unresolved,
    )
    return AnalysisBundle(snapshot=snapshot, evidence=evidence, architecture=architecture)
