"""Deterministic stage-based publication layout and orthogonal edge routing."""

from __future__ import annotations

from collections.abc import Collection
from heapq import heappop, heappush

from archcanvas_core.models.publication import (
    PublicationEdgeKind,
    PublicationIR,
    PublicationNodeKind,
    SceneEdge,
    SceneNode,
    ScenePoint,
    VisualScene,
)
from archcanvas_core.models.visual_spec import VisualSpec
from archcanvas_core.publication_validation import validate_visual_spec_semantics


class StageLayout:
    margin = 48
    node_width = 168
    node_height = 64
    expanded_repeat_height = 136
    stage_gap = 96

    def layout(
        self,
        publication: PublicationIR,
        *,
        expanded_node_ids: Collection[str] = (),
        visual_spec: VisualSpec | None = None,
    ) -> VisualScene:
        """Lay out a publication view with optional visual-only repeat expansion.

        Expansion never changes the Publication IR or introduces additional Exact-node mappings.
        It reserves extra scene space for a deterministic preview of a repeat group's layers.
        """

        ordered_nodes = publication.nodes
        if visual_spec is not None:
            errors = validate_visual_spec_semantics(visual_spec, publication)
            if errors:
                raise ValueError(f"invalid visual spec: {errors}")
            by_id = {node.node_id: node for node in publication.nodes}
            rank = {node.node_id: index for index, node in enumerate(publication.nodes)}
            successors: dict[str, set[str]] = {node_id: set() for node_id in by_id}
            indegree = {node_id: 0 for node_id in by_id}
            for constraint in visual_spec.constraints:
                source, target = constraint.source_node_id, constraint.target_node_id
                if target not in successors[source]:
                    successors[source].add(target)
                    indegree[target] += 1
            ready: list[tuple[int, str]] = []
            for node_id, degree in indegree.items():
                if degree == 0:
                    heappush(ready, (rank[node_id], node_id))
            ordered_nodes = []
            while ready:
                _, node_id = heappop(ready)
                ordered_nodes.append(by_id[node_id])
                for target in successors[node_id]:
                    indegree[target] -= 1
                    if indegree[target] == 0:
                        heappush(ready, (rank[target], target))
            if len(ordered_nodes) != len(by_id):
                raise ValueError("visual spec order constraints contain a cycle")

        requested_expansion = frozenset(expanded_node_ids)
        publication_nodes = {node.node_id: node for node in publication.nodes}
        unknown = requested_expansion - set(publication_nodes)
        if unknown:
            raise ValueError(f"unknown publication node requested for expansion: {sorted(unknown)}")
        non_repeat = {
            node_id
            for node_id in requested_expansion
            if publication_nodes[node_id].kind is not PublicationNodeKind.REPEAT_GROUP
        }
        if non_repeat:
            raise ValueError(f"only repeat groups may be expanded: {sorted(non_repeat)}")
        has_expanded_repeat = bool(requested_expansion)
        scene_height = (
            self.expanded_repeat_height + self.margin * 2 if has_expanded_repeat else 180
        )
        nodes = [
            SceneNode(
                scene_node_id=f"scene-node:{node.node_id.removeprefix('publication-node:')}",
                publication_node_id=node.node_id,
                expanded=node.node_id in requested_expansion,
                x=self.margin + index * (self.node_width + self.stage_gap),
                y=(
                    (scene_height - self.expanded_repeat_height) // 2
                    if node.node_id in requested_expansion
                    else (scene_height - self.node_height) // 2
                ),
                width=self.node_width,
                height=(
                    self.expanded_repeat_height
                    if node.node_id in requested_expansion
                    else self.node_height
                ),
            )
            for index, node in enumerate(ordered_nodes)
        ]
        positions = {node.publication_node_id: node for node in nodes}
        edges: list[SceneEdge] = []
        for edge in publication.edges:
            source, target = positions[edge.source_node_id], positions[edge.target_node_id]
            if edge.kind is PublicationEdgeKind.RESIDUAL and source.publication_node_id == target.publication_node_id:
                points = [
                    ScenePoint(x=source.x + source.width, y=source.y + source.height // 2),
                    ScenePoint(x=source.x + source.width + 28, y=source.y - 20),
                    ScenePoint(x=source.x + source.width // 2, y=source.y - 20),
                    ScenePoint(x=source.x + source.width // 2, y=source.y),
                ]
            else:
                midpoint = (source.x + source.width + target.x) // 2
                points = [
                    ScenePoint(x=source.x + source.width, y=source.y + source.height // 2),
                    ScenePoint(x=midpoint, y=source.y + source.height // 2),
                    ScenePoint(x=midpoint, y=target.y + target.height // 2),
                    ScenePoint(x=target.x, y=target.y + target.height // 2),
                ]
            edges.append(
                SceneEdge(
                    scene_edge_id=f"scene-edge:{edge.edge_id.removeprefix('publication-edge:')}",
                    publication_edge_id=edge.edge_id,
                    points=points,
                )
            )
        width = self.margin * 2 + len(nodes) * self.node_width + max(0, len(nodes) - 1) * self.stage_gap
        return VisualScene(
            scene_id=f"scene:{publication.publication_id.removeprefix('publication:')}",
            publication_id=publication.publication_id,
            width=width,
            height=scene_height,
            nodes=nodes,
            edges=edges,
        )
