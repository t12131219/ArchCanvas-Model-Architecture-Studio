"""Deliberately narrow static analyzer for the v1 Transformer fixture.

It demonstrates the required discovery -> anchor/identity -> strict IR pipeline. A
general PyTorch adapter is a later milestone, not an implicit promise of this module.
"""

from __future__ import annotations

import ast

import libcst as cst
from libcst.metadata import MetadataWrapper, PositionProvider

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
)
from archcanvas_core.models.common import source_snapshot_revision
from archcanvas_core.models.source_identity import (
    AnchorKind,
    AnchorLocator,
    Framework,
    NodeIdentity,
    SourceAnchor,
    SourceIdentityDocument,
    SourcePosition,
    SourceSpan,
)

from .fingerprints import content_fingerprint, structural_fingerprint
from .source_revision import file_revision
from .transforms.set_parameter import dotted_name


PROJECT_ID = "fixture:transformer_set_parameter_v1"
RELATIVE_FILE = "model.py"
TARGET_NODE_ID = "node:encoder.layers"
TARGET_IDENTITY_ID = "identity:encoder.layers"
TARGET_ANCHOR_ID = "anchor:encoder.layers.constructor"


class _TargetCallFinder(cst.CSTVisitor):
    METADATA_DEPENDENCIES = (PositionProvider,)

    def __init__(self) -> None:
        self.call: cst.Call | None = None
        self.position = None

    def visit_Call(self, node: cst.Call) -> None:
        if dotted_name(node.func) == "nn.TransformerEncoderLayer":
            if self.call is not None:
                raise ValueError("fixture contains multiple TransformerEncoderLayer calls")
            self.call = node
            self.position = self.get_metadata(PositionProvider, node)


def _literal_argument(module: cst.Module, call: cst.Call, name: str) -> object:
    argument = next(
        argument
        for argument in call.args
        if argument.keyword is not None and argument.keyword.value == name
    )
    return ast.literal_eval(module.code_for_node(argument.value))


def _port(node: str, direction: str, name: str | None) -> ArchitecturePort:
    suffix = "in" if direction == "input" else "out"
    return ArchitecturePort(port_id=f"port:{node}:{suffix}", direction=direction, name=name, tensor=None)


def _node(
    node_id: str,
    identity_id: str,
    op_type: str,
    name: str,
    role: str | None = None,
    parameters: list[ArchitectureParameter] | None = None,
    anchors: list[str] | None = None,
    metadata: dict[str, object] | None = None,
) -> ArchitectureNode:
    base = node_id.removeprefix("node:").replace(".", "_")
    return ArchitectureNode(
        node_id=node_id,
        identity_id=identity_id,
        kind=NodeKind.MODULE,
        op_type=op_type,
        display_name=name,
        parent_id=None,
        parameters=parameters or [],
        input_ports=[_port(base, "input", None)],
        output_ports=[_port(base, "output", None)],
        semantic_role=role,
        source_anchor_ids=anchors or [],
        metadata=metadata or {},
    )


def analyze_transformer_fixture(raw_source: bytes) -> tuple[SourceIdentityDocument, ArchitectureIR]:
    module = cst.parse_module(raw_source.decode("utf-8"))
    finder = _TargetCallFinder()
    MetadataWrapper(module).visit(finder)
    if finder.call is None or finder.position is None:
        raise ValueError("fixture TransformerEncoderLayer call was not found")
    revision = file_revision(raw_source)
    anchor = SourceAnchor(
        anchor_id=TARGET_ANCHOR_ID,
        relative_file=RELATIVE_FILE,
        symbol_path="EncoderModel.__init__",
        semantic_path="encoder.layers.constructor",
        kind=AnchorKind.CALL,
        cst_node_type="Call",
        span=SourceSpan(
            start=SourcePosition(line=finder.position.start.line, column=finder.position.start.column),
            end=SourcePosition(line=finder.position.end.line, column=finder.position.end.column),
        ),
        locator=AnchorLocator(
            class_name="EncoderModel",
            function_name="__init__",
            assignment_target="self.layers",
            callee_text="nn.TransformerEncoderLayer",
            qualified_callee="torch.nn.TransformerEncoderLayer",
            argument_name="nhead",
            occurrence=0,
        ),
        structural_fingerprint=structural_fingerprint(finder.call),
        content_fingerprint=content_fingerprint(finder.call),
        file_revision=revision,
    )
    source = SourceIdentityDocument(
        project_id=PROJECT_ID,
        source_revision=source_snapshot_revision({RELATIVE_FILE: revision}),
        file_revisions={RELATIVE_FILE: revision},
        anchors=[anchor],
        identities=[
            NodeIdentity(
                identity_id=TARGET_IDENTITY_ID,
                framework=Framework.PYTORCH,
                module_path="torch.nn.TransformerEncoderLayer",
                relative_file=RELATIVE_FILE,
                qualified_symbol="EncoderModel.__init__",
                attribute_path="layers",
                semantic_role="encoder",
                structural_fingerprint=anchor.structural_fingerprint,
                anchor_ids=[TARGET_ANCHOR_ID],
                created_revision=revision,
            )
        ],
        reconciliations=[],
    )
    evidence = Evidence(
        source=EvidenceSource.STATIC_CST,
        confidence=Confidence.CONFIRMED,
        description="Literal keyword argument nhead",
        anchor_id=TARGET_ANCHOR_ID,
        trace_id=None,
    )
    d_model = ArchitectureParameter(
        name="d_model",
        source_name="d_model",
        value=256,
        expression="d_model",
        origin=ParameterOrigin(kind=ParameterOriginKind.ARGUMENT, anchor_ids=[TARGET_ANCHOR_ID]),
        evidence=[evidence.model_copy(update={"description": "Resolved constructor default"})],
    )
    num_heads = ArchitectureParameter(
        name="num_heads",
        source_name="nhead",
        value=_literal_argument(module, finder.call, "nhead"),
        expression=None,
        origin=ParameterOrigin(kind=ParameterOriginKind.LITERAL, anchor_ids=[TARGET_ANCHOR_ID]),
        evidence=[evidence],
    )
    nodes = [
        _node("node:tokens", "identity:tokens", "input", "Tokens", "input"),
        _node("node:encoder.embedding", "identity:encoder.embedding", "torch.nn.Embedding", "Embedding"),
        _node(
            TARGET_NODE_ID,
            TARGET_IDENTITY_ID,
            "torch.nn.TransformerEncoderLayer",
            "Transformer Encoder Layer",
            "encoder",
            [d_model, num_heads],
            [TARGET_ANCHOR_ID],
            {"container": "ModuleList"},
        ),
        _node("node:encoder.norm", "identity:encoder.norm", "torch.nn.LayerNorm", "Layer Norm"),
        _node("node:encoder.mean", "identity:encoder.mean", "mean", "Mean"),
        _node("node:encoder.head", "identity:encoder.head", "torch.nn.Linear", "Classifier"),
        _node("node:output", "identity:output", "output", "Output", "output"),
    ]
    # The target identity is source-backed. The other fixture topology nodes are runtime-like
    # placeholders and therefore do not require source anchors in the v1 identity document.
    identities = list(source.identities) + [
        NodeIdentity(
            identity_id=node.identity_id,
            framework=Framework.PYTORCH,
            module_path=None,
            relative_file=None,
            qualified_symbol=None,
            attribute_path=None,
            semantic_role=node.semantic_role,
            structural_fingerprint=anchor.structural_fingerprint,
            anchor_ids=[],
            created_revision=revision,
        )
        for node in nodes
        if node.identity_id != TARGET_IDENTITY_ID
    ]
    source = source.model_copy(update={"identities": identities})
    edges = []
    for left, right in zip(nodes, nodes[1:]):
        edges.append(
            ArchitectureEdge(
                edge_id=f"edge:{left.node_id.removeprefix('node:')}->{right.node_id.removeprefix('node:')}",
                source_node_id=left.node_id,
                source_port_id=left.output_ports[0].port_id,
                target_node_id=right.node_id,
                target_port_id=right.input_ports[0].port_id,
                kind=EdgeKind.DATA,
                tensor=None,
                semantic_role=None,
                evidence=[],
                metadata={},
            )
        )
    ir = ArchitectureIR(
        ir_id="ir:transformer_set_parameter_v1",
        project_id=PROJECT_ID,
        source_revision=source.source_revision,
        model=ModelDescriptor(
            framework=Framework.PYTORCH,
            entrypoint="model.py:EncoderModel",
            model_class="EncoderModel",
        ),
        nodes=nodes,
        edges=edges,
        repeats=[
            RepeatSpec(
                repeat_id="repeat:encoder.layers",
                member_node_ids=[TARGET_NODE_ID],
                count=6,
                count_symbol=None,
                source_anchor_ids=[TARGET_ANCHOR_ID],
            )
        ],
        unresolved=[],
        metadata={"fixture": "transformer_set_parameter_v1"},
    )
    return source, ir
