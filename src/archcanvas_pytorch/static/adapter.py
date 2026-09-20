"""Convert conservative PyTorch discoveries into strict v1 protocol documents."""

from __future__ import annotations

from hashlib import sha256

from archcanvas_core.models.architecture import (
    ArchitectureEdge,
    ArchitectureIR,
    ArchitectureNode,
    ArchitectureParameter,
    ArchitecturePort,
    Confidence,
    EdgeKind,
    Evidence,
    EvidenceSource,
    ModelDescriptor,
    NodeKind,
    ParameterOrigin,
    ParameterOriginKind,
    RepeatSpec,
    UnresolvedFact,
)
from archcanvas_core.models.common import source_snapshot_revision
from archcanvas_core.models.source_identity import (
    AnchorKind,
    AnchorLocator,
    Framework,
    IdentityReconciliation,
    NodeIdentity,
    ReconciliationDecision,
    SourceAnchor,
    SourceIdentityDocument,
    SourcePosition,
    SourceSpan,
)
from archcanvas_python.source_revision import file_revision

from .scanner import ParameterDiscovery, PyTorchStaticScanner


def _digest(text: str) -> str:
    return "sha256:" + sha256(text.encode("utf-8")).hexdigest()


def _node_id(model_class: str, attribute: str) -> str:
    return f"node:{model_class.lower()}.{attribute}"


def _identity_id(model_class: str, attribute: str) -> str:
    return f"identity:{model_class.lower()}.{attribute}"


def _port(node_id: str, direction: str) -> ArchitecturePort:
    suffix = "in" if direction == "input" else "out"
    return ArchitecturePort(
        port_id=f"port:{node_id.removeprefix('node:')}:{suffix}",
        direction=direction,
        name=None,
        tensor=None,
    )


def _span_text(lines: list[str], *, line: int, column: int, end_line: int, end_column: int) -> str:
    if line == end_line:
        return lines[line - 1][column:end_column]
    return "".join([lines[line - 1][column:], *lines[line:end_line - 1], lines[end_line - 1][:end_column]])


def _parameter_anchor_id(model_class: str, attribute: str, source_name: str) -> str:
    return f"anchor:{model_class.lower()}.{attribute}.parameter.{source_name}"


def _provenance_coordinate(value: int | None, fallback: int) -> int:
    return fallback if value is None else value


def _parameter_from_discovery(
    discovery: ParameterDiscovery,
    *,
    model_class: str,
    attribute: str,
    relative_file: str,
    revision: str,
    lines: list[str],
    qualified_callee: str,
) -> tuple[SourceAnchor, ArchitectureParameter]:
    anchor_id = _parameter_anchor_id(model_class, attribute, discovery.source_name)
    content = _span_text(
        lines,
        line=_provenance_coordinate(discovery.origin_line, discovery.line),
        column=_provenance_coordinate(discovery.origin_column, discovery.column),
        end_line=_provenance_coordinate(discovery.origin_end_line, discovery.end_line),
        end_column=_provenance_coordinate(discovery.origin_end_column, discovery.end_column),
    )
    anchor = SourceAnchor(
        anchor_id=anchor_id,
        relative_file=relative_file,
        symbol_path=f"{model_class}.__init__",
        semantic_path=f"{model_class.lower()}.{attribute}.parameter.{discovery.source_name}",
        kind=AnchorKind.EXPRESSION,
        cst_node_type="Expression",
        span=SourceSpan(
            start=SourcePosition(
                line=_provenance_coordinate(discovery.origin_line, discovery.line),
                column=_provenance_coordinate(discovery.origin_column, discovery.column),
            ),
            end=SourcePosition(
                line=_provenance_coordinate(discovery.origin_end_line, discovery.end_line),
                column=_provenance_coordinate(discovery.origin_end_column, discovery.end_column),
            ),
        ),
        locator=AnchorLocator(
            class_name=model_class,
            function_name="__init__",
            assignment_target=f"self.{attribute}",
            callee_text=None,
            qualified_callee=qualified_callee,
            argument_name=discovery.source_name,
            occurrence=0,
        ),
        structural_fingerprint=_digest(f"{qualified_callee}:{discovery.source_name}:{discovery.origin}"),
        content_fingerprint=_digest(content),
        file_revision=revision,
    )
    origin = ParameterOriginKind(discovery.origin)
    evidence = Evidence(
        source=EvidenceSource.STATIC_AST,
        confidence=Confidence.CONFIRMED if origin is not ParameterOriginKind.COMPUTED else Confidence.UNRESOLVED,
        description=f"Constructor parameter provenance: {origin.value}",
        anchor_id=anchor_id,
        trace_id=None,
    )
    parameter = ArchitectureParameter(
        name=discovery.name,
        source_name=discovery.source_name,
        value=discovery.value,
        expression=discovery.expression,
        origin=ParameterOrigin(kind=origin, anchor_ids=[anchor_id]),
        evidence=[evidence],
    )
    return anchor, parameter


def _reconcile_identities(
    identities: list[NodeIdentity], previous: SourceIdentityDocument | None
) -> tuple[list[IdentityReconciliation], list[UnresolvedFact]]:
    reconciliations: list[IdentityReconciliation] = []
    unresolved: list[UnresolvedFact] = []
    previous_identities = previous.identities if previous is not None else []
    for identity in identities:
        if identity.relative_file is None:
            continue
        discovery_id = f"discovery:{identity.qualified_symbol}:{identity.attribute_path}"
        candidates = [
            prior
            for prior in previous_identities
            if prior.framework == identity.framework
            and prior.relative_file == identity.relative_file
            and prior.qualified_symbol == identity.qualified_symbol
            and prior.attribute_path == identity.attribute_path
        ]
        if not candidates:
            reconciliations.append(
                IdentityReconciliation(
                    old_identity_id=None,
                    new_discovery_id=discovery_id,
                    resolved_identity_id=identity.identity_id,
                    score=1.0,
                    decision=ReconciliationDecision.NEW,
                    reasons=["new source-backed discovery"],
                )
            )
        elif len(candidates) == 1:
            reconciliations.append(
                IdentityReconciliation(
                    old_identity_id=candidates[0].identity_id,
                    new_discovery_id=discovery_id,
                    resolved_identity_id=identity.identity_id,
                    score=1.0,
                    decision=ReconciliationDecision.EXACT,
                    reasons=["qualified_symbol and attribute_path match"],
                )
            )
        else:
            reconciliations.append(
                IdentityReconciliation(
                    old_identity_id=None,
                    new_discovery_id=discovery_id,
                    resolved_identity_id=None,
                    score=0.0,
                    decision=ReconciliationDecision.AMBIGUOUS,
                    reasons=["multiple prior identities match the same source symbol and attribute"],
                )
            )
            unresolved.append(
                UnresolvedFact(
                    code="AMBIGUOUS_IDENTITY",
                    message=f"identity reconciliation is ambiguous for {identity.attribute_path}",
                    anchor_ids=identity.anchor_ids,
                    blocking=True,
                )
            )
    return reconciliations, unresolved


class PyTorchStaticAdapter:
    """Stage 2 v1 adapter for statically proven nn.Module constructor/forward subsets."""

    def __init__(self, scanner: PyTorchStaticScanner | None = None) -> None:
        self._scanner = scanner or PyTorchStaticScanner()

    def analyze(
        self,
        raw_source: bytes,
        *,
        project_id: str,
        relative_file: str,
        entrypoint: str,
        previous_source: SourceIdentityDocument | None = None,
    ) -> tuple[SourceIdentityDocument, ArchitectureIR]:
        recovery = self._scanner.scan(raw_source)
        if len(recovery.model_classes) != 1:
            raise ValueError("v1 static adapter requires exactly one nn.Module class per entrypoint")
        model_class = recovery.model_classes[0]
        revision = file_revision(raw_source)
        lines = raw_source.decode("utf-8").splitlines(keepends=True)
        anchors: list[SourceAnchor] = []
        identities: list[NodeIdentity] = []
        modules: list[ArchitectureNode] = []
        repeats: list[RepeatSpec] = []
        for discovery in recovery.modules:
            segment = "".join(lines[discovery.line - 1 : discovery.end_line])
            anchor_id = f"anchor:{model_class.lower()}.{discovery.attribute_path}.constructor"
            anchor = SourceAnchor(
                anchor_id=anchor_id,
                relative_file=relative_file,
                symbol_path=f"{model_class}.__init__",
                semantic_path=f"{model_class.lower()}.{discovery.attribute_path}.constructor",
                kind=AnchorKind.CALL,
                cst_node_type="Call",
                span=SourceSpan(
                    start=SourcePosition(line=discovery.line, column=discovery.column),
                    end=SourcePosition(line=discovery.end_line, column=discovery.end_column),
                ),
                locator=AnchorLocator(
                    class_name=model_class,
                    function_name="__init__",
                    assignment_target=f"self.{discovery.attribute_path}",
                    callee_text=None,
                    qualified_callee=discovery.op_type,
                    argument_name=None,
                    occurrence=0,
                ),
                structural_fingerprint=_digest(discovery.op_type),
                content_fingerprint=_digest(segment),
                file_revision=revision,
            )
            node_id = _node_id(model_class, discovery.attribute_path)
            identity_id = _identity_id(model_class, discovery.attribute_path)
            anchors.append(anchor)
            parameters: list[ArchitectureParameter] = []
            for parameter_discovery in discovery.parameters:
                parameter_anchor, parameter = _parameter_from_discovery(
                    parameter_discovery,
                    model_class=model_class,
                    attribute=discovery.attribute_path,
                    relative_file=relative_file,
                    revision=revision,
                    lines=lines,
                    qualified_callee=discovery.op_type,
                )
                anchors.append(parameter_anchor)
                parameters.append(parameter)
            identities.append(
                NodeIdentity(
                    identity_id=identity_id,
                    framework=Framework.PYTORCH,
                    module_path=discovery.op_type,
                    relative_file=relative_file,
                    qualified_symbol=f"{model_class}.__init__",
                    attribute_path=discovery.attribute_path,
                    semantic_role=None,
                    structural_fingerprint=anchor.structural_fingerprint,
                    anchor_ids=[anchor_id],
                    created_revision=revision,
                )
            )
            modules.append(
                ArchitectureNode(
                    node_id=node_id,
                    identity_id=identity_id,
                    kind=NodeKind.MODULE,
                    op_type=discovery.op_type,
                    display_name=discovery.attribute_path,
                    parent_id=None,
                    parameters=parameters,
                    input_ports=[_port(node_id, "input")],
                    output_ports=[_port(node_id, "output")],
                    semantic_role=None,
                    source_anchor_ids=[anchor_id],
                    metadata={"container": discovery.container} if discovery.container else {},
                )
            )
            if discovery.repeat_count is not None or discovery.repeat_symbol is not None:
                repeats.append(
                    RepeatSpec(
                        repeat_id=f"repeat:{model_class.lower()}.{discovery.attribute_path}",
                        member_node_ids=[node_id],
                        count=discovery.repeat_count,
                        count_symbol=discovery.repeat_symbol,
                        source_anchor_ids=[anchor_id],
                    )
                )
        merge_nodes = []
        for merge in recovery.merges:
            node_id = f"node:merge.{merge.name.removeprefix('merge:')}"
            identity_id = f"identity:merge.{merge.name.removeprefix('merge:')}"
            identities.append(NodeIdentity(identity_id=identity_id, framework=Framework.PYTORCH, module_path=None, relative_file=None, qualified_symbol=None, attribute_path=None, semantic_role="merge", structural_fingerprint=_digest(merge.operation), anchor_ids=[], created_revision=revision))
            merge_nodes.append(ArchitectureNode(node_id=node_id, identity_id=identity_id, kind=NodeKind.MERGE, op_type=merge.operation, display_name=merge.operation.removeprefix("torch."), parent_id=None, parameters=[], input_ports=[_port(node_id, "input")], output_ports=[_port(node_id, "output")], semantic_role="merge", source_anchor_ids=[], metadata={"input_count": len(merge.inputs)}))
        input_node = ArchitectureNode(
            node_id="node:input",
            identity_id="identity:input",
            kind=NodeKind.INPUT,
            op_type="input",
            display_name="Input",
            parent_id=None,
            parameters=[],
            input_ports=[],
            output_ports=[_port("node:input", "output")],
            semantic_role="input",
            source_anchor_ids=[],
            metadata={},
        )
        output_node = ArchitectureNode(
            node_id="node:output",
            identity_id="identity:output",
            kind=NodeKind.OUTPUT,
            op_type="output",
            display_name="Output",
            parent_id=None,
            parameters=[],
            input_ports=[_port("node:output", "input")],
            output_ports=[],
            semantic_role="output",
            source_anchor_ids=[],
            metadata={},
        )
        identities.extend(
            [
                NodeIdentity(identity_id="identity:input", framework=Framework.PYTORCH, module_path=None, relative_file=None, qualified_symbol=None, attribute_path=None, semantic_role="input", structural_fingerprint=_digest("input"), anchor_ids=[], created_revision=revision),
                NodeIdentity(identity_id="identity:output", framework=Framework.PYTORCH, module_path=None, relative_file=None, qualified_symbol=None, attribute_path=None, semantic_role="output", structural_fingerprint=_digest("output"), anchor_ids=[], created_revision=revision),
            ]
        )
        nodes = [input_node, *modules, *merge_nodes, output_node]
        node_lookup = {"input": input_node, "output": output_node, **{item.display_name: item for item in modules}, **{f"merge:{item.node_id.removeprefix('node:merge.')}": item for item in merge_nodes}}
        edges: list[ArchitectureEdge] = []
        for edge in recovery.edges:
            source, target = node_lookup.get(edge.source), node_lookup.get(edge.target)
            if source is None or target is None:
                continue
            edges.append(ArchitectureEdge(edge_id=f"edge:{edge.source}->{edge.target}:{edge.kind}", source_node_id=source.node_id, source_port_id=source.output_ports[0].port_id if source.output_ports else None, target_node_id=target.node_id, target_port_id=target.input_ports[0].port_id if target.input_ports else None, kind=EdgeKind(edge.kind), tensor=None, semantic_role=None, evidence=[Evidence(source=EvidenceSource.STATIC_AST, confidence=Confidence.CONFIRMED, description="Forward data flow", anchor_id=None, trace_id=None)], metadata={}))
        reconciliations, identity_unresolved = _reconcile_identities(identities, previous_source)
        source = SourceIdentityDocument(
            project_id=project_id,
            source_revision=source_snapshot_revision({relative_file: revision}),
            file_revisions={relative_file: revision},
            anchors=anchors,
            identities=identities,
            reconciliations=reconciliations,
        )
        ir = ArchitectureIR(
            ir_id=f"ir:{project_id.removeprefix('project:').replace(':', '-')}",
            project_id=project_id,
            source_revision=source.source_revision,
            model=ModelDescriptor(
                framework=Framework.PYTORCH,
                entrypoint=entrypoint,
                model_class=model_class,
            ),
            nodes=nodes,
            edges=edges,
            repeats=repeats,
            unresolved=[
                UnresolvedFact(code=item.code, message=item.message, anchor_ids=[], blocking=False)
                for item in recovery.unresolved
            ]
            + identity_unresolved,
            metadata={"adapter": "pytorch-static-v1"},
        )
        return source, ir
