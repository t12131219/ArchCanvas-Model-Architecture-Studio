"""Build a bounded static IR for one selected project entrypoint."""

from __future__ import annotations

import ast
from hashlib import sha256
from pathlib import Path

from archcanvas_core.models.architecture import ArchitectureIR
from archcanvas_core.models.common import source_snapshot_revision
from archcanvas_core.models.source_identity import (
    AnchorKind,
    AnchorLocator,
    SourceAnchor,
    SourceIdentityDocument,
    SourcePosition,
    SourceSpan,
)
from archcanvas_python.source_revision import file_revision

from .adapter import PyTorchStaticAdapter
from .project import PyTorchProjectScanner
from .symbols import EntrypointSymbolResolution, LocalModuleBinding, PyTorchProjectSymbolTable


def _digest(text: str) -> str:
    return "sha256:" + sha256(text.encode("utf-8")).hexdigest()


def _target_anchor_id(binding: LocalModuleBinding) -> str:
    file_token = binding.target_relative_file.removesuffix(".py").replace("/", ".").lower()
    return f"anchor:local.{file_token}.{binding.target_class_name.lower()}.class"


def _target_class_anchor(
    binding: LocalModuleBinding, raw_source: bytes, revision: str
) -> SourceAnchor:
    tree = ast.parse(raw_source.decode("utf-8"))
    class_node = next(
        (
            node
            for node in tree.body
            if isinstance(node, ast.ClassDef) and node.name == binding.target_class_name
        ),
        None,
    )
    if class_node is None:
        raise ValueError("resolved local module target changed before source identity creation")
    lines = raw_source.decode("utf-8").splitlines(keepends=True)
    content = "".join(lines[class_node.lineno - 1 : class_node.end_lineno])
    qualified_callee = f"local:{binding.target_relative_file}:{binding.target_class_name}"
    return SourceAnchor(
        anchor_id=_target_anchor_id(binding),
        relative_file=binding.target_relative_file,
        symbol_path=binding.target_class_name,
        semantic_path=f"local.{binding.target_class_name.lower()}.class",
        kind=AnchorKind.CLASS,
        cst_node_type="ClassDef",
        span=SourceSpan(
            start=SourcePosition(line=class_node.lineno, column=class_node.col_offset),
            end=SourcePosition(line=class_node.end_lineno, column=class_node.end_col_offset),
        ),
        locator=AnchorLocator(
            class_name=binding.target_class_name,
            function_name=None,
            assignment_target=None,
            callee_text=None,
            qualified_callee=qualified_callee,
            argument_name=None,
            occurrence=0,
        ),
        structural_fingerprint=_digest(qualified_callee),
        content_fingerprint=_digest(content),
        file_revision=revision,
    )


class PyTorchProjectStaticAdapter:
    """Adapt direct, statically resolved local constructor calls without executing source.

    The adapter deliberately models a local class invocation as one module node. It does not
    flatten the imported class implementation into the entrypoint's topology, which would need
    interprocedural proof that this Stage 2 subset does not yet provide.
    """

    def __init__(
        self,
        project_scanner: PyTorchProjectScanner | None = None,
        adapter: PyTorchStaticAdapter | None = None,
        *,
        max_transitive_evidence_depth: int = 3,
    ) -> None:
        if max_transitive_evidence_depth < 1:
            raise ValueError("max_transitive_evidence_depth must be positive")
        self._project_scanner = project_scanner or PyTorchProjectScanner()
        self._adapter = adapter or PyTorchStaticAdapter()
        self._max_transitive_evidence_depth = max_transitive_evidence_depth

    @staticmethod
    def _aliases(resolution: EntrypointSymbolResolution) -> dict[str, str]:
        return {
            binding.local_name: f"local:{binding.target_relative_file}:{binding.target_class_name}"
            for binding in resolution.local_module_bindings
        }

    def _analyze_entrypoint(
        self,
        root: Path,
        resolution: EntrypointSymbolResolution,
        *,
        project_id: str,
        previous_source: SourceIdentityDocument | None = None,
    ) -> tuple[SourceIdentityDocument, ArchitectureIR]:
        raw_source = (root / resolution.relative_file).read_bytes()
        return self._adapter.analyze(
            raw_source,
            project_id=project_id,
            relative_file=resolution.relative_file,
            entrypoint=f"{resolution.relative_file}:{resolution.model_class}",
            previous_source=previous_source,
            local_module_aliases=self._aliases(resolution),
        )

    def _collect_transitive_evidence(
        self,
        root: Path,
        symbols: PyTorchProjectSymbolTable,
        root_resolution: EntrypointSymbolResolution,
        *,
        project_id: str,
        root_local_node_types: set[str],
    ) -> tuple[list[dict[str, object]], dict[str, SourceAnchor], dict[str, str]]:
        """Collect source-backed call declarations without treating them as root IR topology."""

        evidence: list[dict[str, object]] = []
        anchors: dict[str, SourceAnchor] = {}
        file_revisions: dict[str, str] = {}
        visited = {f"{root_resolution.relative_file}:{root_resolution.model_class}"}

        def visit(
            resolution: EntrypointSymbolResolution, depth: int, ancestry: set[str]
        ) -> None:
            if depth > self._max_transitive_evidence_depth:
                return
            source, ir = self._analyze_entrypoint(root, resolution, project_id=project_id)
            file_revisions.update(source.file_revisions)
            bindings = {
                f"local:{binding.target_relative_file}:{binding.target_class_name}": binding
                for binding in resolution.local_module_bindings
            }
            for node in ir.nodes:
                binding = bindings.get(node.op_type)
                if binding is None:
                    continue
                target_path = root / binding.target_relative_file
                target_raw = target_path.read_bytes()
                target_revision = file_revision(target_raw)
                file_revisions[binding.target_relative_file] = target_revision
                target_anchor = _target_class_anchor(binding, target_raw, target_revision)
                anchors.setdefault(target_anchor.anchor_id, target_anchor)
                referenced_anchor_ids = {
                    *node.source_anchor_ids,
                    *(anchor_id for parameter in node.parameters for anchor_id in parameter.origin.anchor_ids),
                }
                for anchor in source.anchors:
                    if anchor.anchor_id in referenced_anchor_ids:
                        anchors.setdefault(anchor.anchor_id, anchor)
                target_entrypoint = f"{binding.target_relative_file}:{binding.target_class_name}"
                if target_entrypoint in ancestry:
                    traversal_status = "cycle"
                elif depth >= self._max_transitive_evidence_depth:
                    traversal_status = "depth_limit"
                elif target_entrypoint in visited:
                    traversal_status = "duplicate"
                else:
                    traversal_status = "expanded"
                evidence.append(
                    {
                        "depth": depth,
                        "from_entrypoint": f"{resolution.relative_file}:{resolution.model_class}",
                        "call_node_id": node.node_id,
                        "call_anchor_ids": node.source_anchor_ids,
                        "target_entrypoint": target_entrypoint,
                        "target_class_anchor_id": target_anchor.anchor_id,
                        "traversal_status": traversal_status,
                    }
                )
                if traversal_status == "expanded":
                    visited.add(target_entrypoint)
                    visit(
                        symbols.resolve_entrypoint(target_entrypoint),
                        depth + 1,
                        {target_entrypoint, *ancestry},
                    )

        for binding in root_resolution.local_module_bindings:
            target_entrypoint = f"{binding.target_relative_file}:{binding.target_class_name}"
            target_type = f"local:{binding.target_relative_file}:{binding.target_class_name}"
            if target_type in root_local_node_types and target_entrypoint not in visited:
                visited.add(target_entrypoint)
                visit(
                    symbols.resolve_entrypoint(target_entrypoint),
                    1,
                    {f"{root_resolution.relative_file}:{root_resolution.model_class}", target_entrypoint},
                )
        return evidence, anchors, file_revisions

    def analyze(
        self,
        root: Path,
        *,
        project_id: str,
        entrypoint: str,
        previous_source: SourceIdentityDocument | None = None,
    ) -> tuple[SourceIdentityDocument, ArchitectureIR]:
        """Return an Exact IR for an approved root and selected direct-import entrypoint."""

        resolved_root = root.resolve(strict=True)
        symbols = self._project_scanner.build_symbol_table(resolved_root)
        resolution = symbols.resolve_entrypoint(entrypoint)
        source, ir = self._analyze_entrypoint(
            resolved_root,
            resolution,
            project_id=project_id,
            previous_source=previous_source,
        )

        # A local-call node is only valid against both the call-site and imported-class revisions.
        file_revisions = dict(source.file_revisions)
        target_anchors: dict[str, SourceAnchor] = {}
        local_node_types = {node.op_type for node in ir.nodes if node.op_type.startswith("local:")}
        for binding in resolution.local_module_bindings:
            target_path = resolved_root / binding.target_relative_file
            target_raw_source = target_path.read_bytes()
            target_revision = file_revision(target_raw_source)
            file_revisions[binding.target_relative_file] = target_revision
            target_type = f"local:{binding.target_relative_file}:{binding.target_class_name}"
            if target_type in local_node_types and target_type not in target_anchors:
                target_anchors[target_type] = _target_class_anchor(
                    binding, target_raw_source, target_revision
                )
        nodes = [
            node.model_copy(
                update={
                    "source_anchor_ids": [
                        *node.source_anchor_ids,
                        target_anchors[node.op_type].anchor_id,
                    ]
                }
            )
            if node.op_type in target_anchors
            else node
            for node in ir.nodes
        ]
        identity_anchor_ids = {
            node.identity_id: node.source_anchor_ids for node in nodes if node.op_type in target_anchors
        }
        identities = [
            identity.model_copy(update={"anchor_ids": identity_anchor_ids[identity.identity_id]})
            if identity.identity_id in identity_anchor_ids
            else identity
            for identity in source.identities
        ]
        transitive_evidence, transitive_anchors, transitive_file_revisions = (
            self._collect_transitive_evidence(
                resolved_root,
                symbols,
                resolution,
                project_id=project_id,
                root_local_node_types=local_node_types,
            )
        )
        file_revisions.update(transitive_file_revisions)
        revision = source_snapshot_revision(file_revisions)
        combined_anchors = {
            anchor.anchor_id: anchor
            for anchor in [*source.anchors, *target_anchors.values(), *transitive_anchors.values()]
        }
        source = source.model_copy(
            update={
                "file_revisions": file_revisions,
                "source_revision": revision,
                "anchors": list(combined_anchors.values()),
                "identities": identities,
            }
        )
        ir = ir.model_copy(
            update={
                "source_revision": revision,
                "nodes": nodes,
                "metadata": {
                    **ir.metadata,
                    "adapter": "pytorch-project-static-v1",
                    "direct_local_binding_count": len(resolution.local_module_bindings),
                    "transitive_local_call_evidence": transitive_evidence,
                    "transitive_local_call_evidence_depth": self._max_transitive_evidence_depth,
                },
            }
        )
        return source, ir
