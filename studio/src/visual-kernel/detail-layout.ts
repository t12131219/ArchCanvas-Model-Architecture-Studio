import type {
  KernelDocument,
  KernelNode,
  KernelVisualState,
  RenderNode,
  Size,
} from "./types";
import { templateDetailSize } from "./template-details";

const ATOMIC_SIZE: Size = { width: 166, height: 88 };
const COMPACT_SIZE: Size = { width: 146, height: 70 };
const TECHNICAL_SIZE: Size = { width: 178, height: 102 };
const COLLAPSED_MODULE_SIZE: Size = { width: 184, height: 92 };
const HEADER_HEIGHT = 50;
const CONTENT_PADDING_X = 28;
const CONTENT_PADDING_Y = 26;
const COLUMN_GAP = 44;
const ROW_GAP = 30;

interface ChildPlacement {
  nodeId: string;
  x: number;
  y: number;
}

interface LayoutPlan {
  size: Size;
  children: ChildPlacement[];
}

function immediateChild(nodeById: Map<string, KernelNode>, parentId: string, nodeId: string): string | undefined {
  let cursor = nodeById.get(nodeId);
  while (cursor?.parentNodeId && cursor.parentNodeId !== parentId) cursor = nodeById.get(cursor.parentNodeId);
  return cursor?.parentNodeId === parentId ? cursor.nodeId : undefined;
}

function childRanks(document: KernelDocument, parent: KernelNode, children: KernelNode[]): Map<string, number> {
  const nodeById = new Map(document.nodes.map((node) => [node.nodeId, node]));
  const portOwners = new Map(document.ports.map((port) => [port.portId, port.ownerNodeId]));
  const childIds = new Set(children.map((child) => child.nodeId));
  const outgoing = new Map(children.map((child) => [child.nodeId, new Set<string>()]));
  const indegree = new Map(children.map((child) => [child.nodeId, 0]));

  for (const edge of document.edges) {
    const sourceOwner = portOwners.get(edge.sourcePortId);
    const targetOwner = portOwners.get(edge.targetPortId);
    if (!sourceOwner || !targetOwner) continue;
    const source = immediateChild(nodeById, parent.nodeId, sourceOwner);
    const target = immediateChild(nodeById, parent.nodeId, targetOwner);
    if (!source || !target || source === target || !childIds.has(source) || !childIds.has(target)) continue;
    const targets = outgoing.get(source)!;
    if (targets.has(target)) continue;
    targets.add(target);
    indegree.set(target, (indegree.get(target) ?? 0) + 1);
  }

  const ranks = new Map(children.map((child) => [child.nodeId, 0]));
  const queue = children.filter((child) => indegree.get(child.nodeId) === 0).map((child) => child.nodeId);
  let visited = 0;
  while (queue.length) {
    const current = queue.shift()!;
    visited += 1;
    for (const target of outgoing.get(current) ?? []) {
      ranks.set(target, Math.max(ranks.get(target) ?? 0, (ranks.get(current) ?? 0) + 1));
      indegree.set(target, (indegree.get(target) ?? 1) - 1);
      if (indegree.get(target) === 0) queue.push(target);
    }
  }

  if (document.edges.length === 0) {
    children.forEach((child, index) => ranks.set(child.nodeId, index));
  } else if (visited < children.length) {
    // Residual and feedback cycles are common inside real modules. Keep stable hierarchy order,
    // but form short columns so one cycle cannot expand its parent into an unreadable single row.
    children.forEach((child, index) => ranks.set(child.nodeId, Math.floor(index / 3)));
  }
  return ranks;
}

function leafSize(node: KernelNode, visualState: KernelVisualState): Size {
  const override = visualState.nodeSizes[node.nodeId];
  if (override) return override;
  if (node.renderRole === "collapsed-module") return COLLAPSED_MODULE_SIZE;
  if (["add", "multiply", "concat", "merge"].includes(node.shape)) return { width: 82, height: 82 };
  if (visualState.nodeStyle === "compact") return COMPACT_SIZE;
  if (visualState.nodeStyle === "technical") return TECHNICAL_SIZE;
  return ATOMIC_SIZE;
}

export function layoutHierarchy(document: KernelDocument, visualState: KernelVisualState): RenderNode[] {
  const nodeById = new Map(document.nodes.map((node) => [node.nodeId, node]));
  const bindingById = new Map(document.templateBindings.map((binding) => [binding.bindingId, binding]));
  const plans = new Map<string, LayoutPlan>();

  const measure = (node: KernelNode): LayoutPlan => {
    const cached = plans.get(node.nodeId);
    if (cached) return cached;
    const exactDetailSize = node.expanded ? templateDetailSize(bindingById.get(node.templateBindingId ?? "")) : undefined;
    if (exactDetailSize) {
      const plan = { size: exactDetailSize, children: [] };
      plans.set(node.nodeId, plan);
      return plan;
    }
    const children = node.childNodeIds.map((id) => nodeById.get(id)).filter((item): item is KernelNode => Boolean(item));
    if (node.renderRole !== "expanded-module" || children.length === 0) {
      const plan = { size: leafSize(node, visualState), children: [] };
      plans.set(node.nodeId, plan);
      return plan;
    }

    const ranks = childRanks(document, node, children);
    const distinctRanks = [...new Set(children.map((child) => ranks.get(child.nodeId) ?? 0))].sort((left, right) => left - right);
    const maxColumns = children.length > 9 ? 6 : 8;
    const displayRank = new Map(distinctRanks.map((rank, index) => [
      rank,
      distinctRanks.length > maxColumns ? Math.floor(index * maxColumns / distinctRanks.length) : index,
    ]));
    const columns = new Map<number, KernelNode[]>();
    for (const child of children) {
      const rank = displayRank.get(ranks.get(child.nodeId) ?? 0) ?? 0;
      columns.set(rank, [...(columns.get(rank) ?? []), child]);
    }
    const orderedColumns = [...columns.entries()].sort(([left], [right]) => left - right);
    const columnWidths = orderedColumns.map(([, items]) => Math.max(...items.map((item) => measure(item).size.width)));
    const columnHeights = orderedColumns.map(([, items]) => (
      items.reduce((sum, item) => sum + measure(item).size.height, 0) + Math.max(0, items.length - 1) * ROW_GAP
    ));
    const contentWidth = columnWidths.reduce((sum, width) => sum + width, 0)
      + Math.max(0, orderedColumns.length - 1) * COLUMN_GAP;
    const contentHeight = Math.max(...columnHeights, ATOMIC_SIZE.height);
    const childrenLayout: ChildPlacement[] = [];
    let cursorX = CONTENT_PADDING_X;
    orderedColumns.forEach(([, items], columnIndex) => {
      let cursorY = HEADER_HEIGHT + CONTENT_PADDING_Y + (contentHeight - columnHeights[columnIndex]) / 2;
      for (const child of items) {
        const childPlan = measure(child);
        childrenLayout.push({
          nodeId: child.nodeId,
          x: cursorX + (columnWidths[columnIndex] - childPlan.size.width) / 2,
          y: cursorY,
        });
        cursorY += childPlan.size.height + ROW_GAP;
      }
      cursorX += columnWidths[columnIndex] + COLUMN_GAP;
    });
    const measured: Size = {
      width: Math.max(COLLAPSED_MODULE_SIZE.width, contentWidth + CONTENT_PADDING_X * 2),
      height: HEADER_HEIGHT + contentHeight + CONTENT_PADDING_Y * 2,
    };
    const override = visualState.nodeSizes[node.nodeId];
    const plan = {
      size: override ? { width: Math.max(override.width, measured.width), height: Math.max(override.height, measured.height) } : measured,
      children: childrenLayout,
    };
    plans.set(node.nodeId, plan);
    return plan;
  };

  const roots = document.nodes.filter((node) => !node.parentNodeId);
  roots.forEach(measure);
  const result: RenderNode[] = [];
  const place = (node: KernelNode, x: number, y: number) => {
    const plan = measure(node);
    result.push({ ...node, bounds: { x, y, ...plan.size } });
    for (const childPlacement of plan.children) {
      const child = nodeById.get(childPlacement.nodeId);
      if (child) {
        const childPlan = measure(child);
        const offset = visualState.detailOffsets[child.nodeId] ?? { x: 0, y: 0 };
        const relativeX = Math.max(
          CONTENT_PADDING_X,
          Math.min(plan.size.width - CONTENT_PADDING_X - childPlan.size.width, childPlacement.x + offset.x),
        );
        const relativeY = Math.max(
          HEADER_HEIGHT + CONTENT_PADDING_Y,
          Math.min(plan.size.height - CONTENT_PADDING_Y - childPlan.size.height, childPlacement.y + offset.y),
        );
        place(child, x + relativeX, y + relativeY);
      }
    }
  };
  const rootRecords: Array<{
    node: KernelNode;
    position: { x: number; y: number };
    baseSize: Size;
    plan: LayoutPlan;
    horizontalGrowth: number;
    exactDetail: boolean;
  }> = [];
  let rootX = 72;
  for (const root of roots) {
    const plan = measure(root);
    const baseSize = visualState.nodeSizes[root.nodeId] ?? leafSize({
      ...root,
      expanded: false,
      renderRole: root.childNodeIds.length > 0 ? "collapsed-module" : "atomic",
    }, visualState);
    const position = visualState.nodePositions[root.nodeId] ?? { x: rootX, y: 72 };
    rootRecords.push({
      node: root,
      position,
      baseSize,
      plan,
      horizontalGrowth: Math.max(0, plan.size.width - baseSize.width),
      exactDetail: Boolean(root.expanded && templateDetailSize(bindingById.get(root.templateBindingId ?? ""))),
    });
    rootX = position.x + baseSize.width + 76;
  }
  for (const record of rootRecords) {
    const shiftX = rootRecords.reduce((sum, candidate) => (
      candidate.position.x < record.position.x ? sum + candidate.horizontalGrowth : sum
    ), 0);
    const centeredY = record.exactDetail
      ? Math.max(32, record.position.y + (record.baseSize.height - record.plan.size.height) / 2)
      : record.position.y;
    place(record.node, record.position.x + shiftX, centeredY);
  }
  return result;
}
