import type {
  Bounds,
  DetailTone,
  HierarchyRoutingMode,
  KernelTemplateBinding,
  Point,
  RenderDetailPrimitive,
  RenderTemplateDetail,
  Size,
} from "./types";
import type { DetailPrimitive } from "./module-details";
import { buildModuleDetail, EXPANDED_DETAIL_SIZES } from "./module-details";
import type { NodeDetailKind } from "./types";
import {
  buildAtomicHierarchyProjection,
  projectedAtomicEntry,
  projectedAtomicExit,
  projectedNestedEntryBridgeIds,
  projectedNestedExitBridgeIds,
} from "./atomic-hierarchy";
import {
  buildInlineDetailLayout,
  expandedDetailSize,
  inlineExpandedChildren,
  type DetailExpansionBranch,
  type InlineDetailLevel,
} from "./recursive-detail-layout";

const ATTENTION_SIZE: Size = { width: 900, height: 380 };

export const PRODUCTION_DETAIL_KINDS = Object.freeze(Object.keys(EXPANDED_DETAIL_SIZES) as NodeDetailKind[]);

function detailKindForTemplate(templateId: string): NodeDetailKind | undefined {
  if (templateId === "attention.qkv-v1") return "attention";
  const normalized = templateId
    .replace(/^(?:catalog|module|detail)\./, "")
    .replace(/(?:\.v?\d+|-v\d+)$/, "");
  return PRODUCTION_DETAIL_KINDS.find((kind) => kind === normalized);
}

export function templateDetailSize(
  binding: KernelTemplateBinding | undefined,
  expansion?: DetailExpansionBranch,
): Size | undefined {
  if (binding?.fidelity !== "exact") return undefined;
  const kind = detailKindForTemplate(binding.templateId);
  if (!kind) return undefined;
  if (expansion) return expandedDetailSize(kind, expansion);
  return kind === "attention" ? ATTENTION_SIZE : EXPANDED_DETAIL_SIZES[kind];
}

function canonical(binding: KernelTemplateBinding, slotId: string): string[] {
  return binding.nodeSlots[slotId] ?? binding.edgeSlots[slotId] ?? binding.portSlots[slotId] ?? binding.tensorSlots[slotId] ?? [];
}

function slotId(binding: KernelTemplateBinding, slot: string): string {
  return `${binding.bindingId}:${slot}`;
}

function attentionDetail(binding: KernelTemplateBinding, bounds: Bounds): RenderTemplateDetail {
  const { x, y } = bounds;
  const centerY = y + bounds.height / 2;
  const branchX = x + 28;
  const rows = [y + 105, y + 170, y + 255];
  const tones: DetailTone[] = ["blue", "green", "pink"];
  const labels = ["Q", "K", "V"];
  const projectionSlots = ["q_projection", "k_projection", "v_projection"];
  const splitSlots = ["q_split", "k_split", "v_split"];
  const primitives: RenderDetailPrimitive[] = [];

  const flow = (id: string, points: Point[], tone: DetailTone = "neutral", mappedSlot = id, marker = true) => primitives.push({
    primitiveId: slotId(binding, `flow:${id}`),
    kind: "flow",
    slotId: `flow:${id}`,
    canonicalIds: canonical(binding, mappedSlot),
    points,
    tone,
    marker,
  });
  const box = (slot: string, bx: number, by: number, width: number, height: number, label: string, tone: DetailTone, note?: string) => primitives.push({
    primitiveId: slotId(binding, slot), kind: "box", slotId: slot, canonicalIds: canonical(binding, slot), x: bx, y: by, width, height, label, note, tone,
  });
  const matrix = (slot: string, mx: number, my: number, width: number, height: number, label: string, tone: DetailTone, depth = 0) => primitives.push({
    primitiveId: slotId(binding, slot), kind: "matrix", slotId: slot, canonicalIds: canonical(binding, slot), x: mx, y: my, width, height, label, columns: 4, rows: 3, depth, tone,
  });
  const operator = (slot: string, cx: number, cy: number, label: string) => primitives.push({
    primitiveId: slotId(binding, slot), kind: "operator", slotId: slot, canonicalIds: canonical(binding, slot), cx, cy, radius: 13, label, tone: "orange",
  });

  primitives.push({
    primitiveId: slotId(binding, "frame:attention-head"), kind: "box", slotId: "frame:attention-head", canonicalIds: [],
    x: x + 250, y: y + 72, width: 360, height: 230, label: "", tone: "orange",
  }, {
    primitiveId: slotId(binding, "label:attention-head"), kind: "text", slotId: "label:attention-head", canonicalIds: [],
    x: x + 415, y: y + 91, value: "Scaled dot-product attention / head", emphasis: true, tone: "orange",
  });
  flow("entry", [{ x, y: centerY }, { x: branchX, y: centerY }], "neutral", "visual:entry", false);

  rows.forEach((row, index) => {
    const projection = projectionSlots[index];
    const split = splitSlots[index];
    flow(`${labels[index].toLowerCase()}:entry`, [{ x: branchX, y: centerY }, { x: branchX + 8, y: row }, { x: x + 46, y: row }], tones[index], projection);
    matrix(`visual:${labels[index].toLowerCase()}-input`, x + 46, row - 20, 46, 40, labels[index], tones[index]);
    flow(`${labels[index].toLowerCase()}:input-projection`, [{ x: x + 92, y: row }, { x: x + 110, y: row }], tones[index], projection);
    box(projection, x + 110, row - 20, 54, 40, "Linear", tones[index]);
    flow(`${labels[index].toLowerCase()}:projection-split`, [{ x: x + 164, y: row }, { x: x + 180, y: row }], tones[index], split);
    matrix(split, x + 180, row - 20, 52, 40, `h × ${labels[index]}`, tones[index], 5);
  });

  flow("q:score", [{ x: x + 232, y: rows[0] }, { x: x + 272, y: rows[0] }, { x: x + 272, y: y + 142 }, { x: x + 293, y: y + 142 }], "blue", "score_matmul");
  // K^T is a formal routing annotation in the prototype, so its connector
  // remains neutral instead of introducing a second green data channel.
  flow("k:split-transpose", [{ x: x + 232, y: rows[1] }, { x: x + 242, y: rows[1] }], "neutral", "key_transpose");
  box("key_transpose", x + 242, rows[1] - 18, 50, 36, "K^T", "neutral", "transpose");
  flow("k:score", [{ x: x + 292, y: rows[1] }, { x: x + 298, y: rows[1] }, { x: x + 298, y: y + 155 }, { x: x + 293, y: y + 155 }], "green", "score_matmul");
  operator("score_matmul", x + 306, y + 142, "×");
  flow("score:scale", [{ x: x + 319, y: y + 142 }, { x: x + 330, y: y + 142 }], "neutral", "score_matmul");
  box("visual:scale", x + 330, y + 120, 60, 44, "Scale", "neutral", "1 / √d_k");
  flow("scale:softmax", [{ x: x + 390, y: y + 142 }, { x: x + 410, y: y + 142 }], "neutral", "softmax");
  box("softmax", x + 410, y + 120, 70, 44, "Softmax", "green");
  flow("softmax:weights", [{ x: x + 480, y: y + 142 }, { x: x + 500, y: y + 142 }], "green", "softmax");
  matrix("visual:attention-weights", x + 500, y + 122, 48, 40, "weights", "green");
  flow("weights:value", [{ x: x + 548, y: y + 142 }, { x: x + 580, y: y + 142 }, { x: x + 580, y: centerY - 13 }], "green", "value_matmul");
  flow("v:value", [{ x: x + 232, y: rows[2] }, { x: x + 520, y: rows[2] }, { x: x + 520, y: centerY }, { x: x + 567, y: centerY }], "pink", "value_matmul");
  operator("value_matmul", x + 580, centerY, "×");
  flow("value:context", [{ x: x + 593, y: centerY }, { x: x + 610, y: centerY }], "neutral", "value_matmul");
  matrix("visual:context", x + 610, centerY - 24, 56, 48, "context", "orange");
  flow("context:concat", [{ x: x + 666, y: centerY }, { x: x + 686, y: centerY }], "neutral", "concat");
  matrix("concat", x + 686, centerY - 22, 62, 44, "Concat h", "violet");
  flow("concat:output-projection", [{ x: x + 748, y: centerY }, { x: x + 765, y: centerY }], "neutral", "concat");
  box("output_projection", x + 765, centerY - 24, 76, 48, "Output Wᴼ", "violet", "h·d_k → d_model");
  flow("output-projection:matrix", [{ x: x + 841, y: centerY }, { x: x + 850, y: centerY }], "neutral", "output_projection");
  matrix("visual:output", x + 850, centerY - 22, 34, 44, "Output", "blue");
  flow("exit", [{ x: x + 884, y: centerY }, { x: x + bounds.width, y: centerY }], "neutral", "output_projection");
  primitives.push({
    primitiveId: slotId(binding, "label:qkv"), kind: "text", slotId: "label:qkv", canonicalIds: [],
    x: x + 126, y: y + 329, value: "Q / K / V projections", emphasis: false, tone: "neutral",
  }, {
    primitiveId: slotId(binding, "label:output"), kind: "text", slotId: "label:output", canonicalIds: [],
    x: x + 729, y: y + 329, value: "merge heads → project → next module", emphasis: false, tone: "neutral",
  });

  return {
    nodeId: "",
    bindingId: binding.bindingId,
    templateId: binding.templateId,
    evidenceIds: binding.evidenceIds,
    bounds: { ...bounds },
    entryPoint: { x, y: centerY },
    exitPoint: { x: x + bounds.width, y: centerY },
    primitives,
  };
}

function genericDetail(binding: KernelTemplateBinding, kind: NodeDetailKind, bounds: Bounds): RenderTemplateDetail {
  const diagram = buildModuleDetail(kind, bounds);
  const slotIds = Object.keys(binding.nodeSlots).sort();
  const slotFor = (primitive: DetailPrimitive, index: number) => (
    primitive.kind === "flow" && primitive.channel ? primitive.channel : slotIds[index] ?? `visual:${index}`
  );
  const primitives = diagram.primitives.map((primitive, index): RenderDetailPrimitive => {
    const rawSlot = slotFor(primitive, index);
    const slot = primitive.kind === "rect" && primitive.variant === "frame"
      ? `frame:${rawSlot}`
      : primitive.kind === "rect" && primitive.variant === "capsule"
        ? `capsule:${rawSlot}`
        : rawSlot;
    const common = {
      primitiveId: slotId(binding, slot),
      slotId: slot,
      canonicalIds: canonical(binding, slot),
    };
    if (primitive.kind === "rect") return {
      ...common,
      kind: "box",
      x: primitive.x,
      y: primitive.y,
      width: primitive.width,
      height: primitive.height,
      label: primitive.label ?? "",
      note: primitive.note,
      tone: primitive.tone,
    };
    if (primitive.kind === "circle") return {
      ...common,
      kind: "operator",
      cx: primitive.cx,
      cy: primitive.cy,
      radius: primitive.radius,
      label: primitive.label,
      tone: primitive.tone,
    };
    if (primitive.kind === "matrix") return {
      ...common,
      kind: "matrix",
      x: primitive.x,
      y: primitive.y,
      width: primitive.width,
      height: primitive.height,
      label: primitive.label ?? "",
      columns: primitive.columns,
      rows: primitive.rows,
      depth: primitive.depth ?? 0,
      tone: primitive.tone,
    };
    if (primitive.kind === "flow") return {
      ...common,
      kind: "flow",
      points: primitive.points,
      tone: primitive.tone ?? "neutral",
      marker: primitive.marker !== false,
    };
    return {
      ...common,
      kind: "text",
      x: primitive.x,
      y: primitive.y,
      value: primitive.value,
      emphasis: primitive.emphasis ?? false,
      tone: primitive.tone ?? "neutral",
    };
  });
  return {
    nodeId: "",
    bindingId: binding.bindingId,
    templateId: binding.templateId,
    evidenceIds: binding.evidenceIds,
    bounds: { ...bounds },
    entryPoint: diagram.entryPoint,
    exitPoint: diagram.exitPoint,
    primitives,
  };
}

function recursiveDetail(
  binding: KernelTemplateBinding,
  kind: NodeDetailKind,
  bounds: Bounds,
  expansion: DetailExpansionBranch,
  options: {
    mode: HierarchyRoutingMode;
    hideEntryBridge?: boolean;
    hideExitBridge?: boolean;
  },
): RenderTemplateDetail {
  const root = buildInlineDetailLayout(
    kind,
    bounds,
    expansion,
    {},
    binding.bindingId,
    [],
    options.mode,
  );
  const projection = buildAtomicHierarchyProjection(root);
  const atomicEntry = options.hideEntryBridge ? projectedAtomicEntry(projection) : undefined;
  const atomicExit = options.hideExitBridge ? projectedAtomicExit(projection) : undefined;
  const hiddenFlowIds = new Set([
    ...(options.mode === "atomic-bottom-up" ? projectedNestedEntryBridgeIds(projection) : []),
    ...(options.mode === "atomic-bottom-up" ? projectedNestedExitBridgeIds(projection) : []),
    ...(atomicEntry?.bridgeEdgeIds ?? []),
    ...(atomicExit?.bridgeEdgeIds ?? []),
  ]);
  const convert = (
    primitive: DetailPrimitive,
    index: number,
    level: InlineDetailLevel,
  ): RenderDetailPrimitive => {
    const mappedSlot = primitive.kind === "flow" && primitive.channel
      ? primitive.channel
      : `visual:${level.levelKey}:${index}`;
    const stableSlot = `${level.levelKey}:${mappedSlot}`;
    const common = {
      primitiveId: slotId(binding, stableSlot),
      slotId: stableSlot,
      canonicalIds: canonical(binding, mappedSlot),
    };
    if (primitive.kind === "rect") return {
      ...common,
      kind: "box",
      x: primitive.x,
      y: primitive.y,
      width: primitive.width,
      height: primitive.height,
      label: primitive.label ?? "",
      note: primitive.note,
      tone: primitive.tone,
    };
    if (primitive.kind === "circle") return {
      ...common,
      kind: "operator",
      cx: primitive.cx,
      cy: primitive.cy,
      radius: primitive.radius,
      label: primitive.label,
      tone: primitive.tone,
    };
    if (primitive.kind === "matrix") return {
      ...common,
      kind: "matrix",
      x: primitive.x,
      y: primitive.y,
      width: primitive.width,
      height: primitive.height,
      label: primitive.label ?? "",
      columns: primitive.columns,
      rows: primitive.rows,
      depth: primitive.depth ?? 0,
      tone: primitive.tone,
    };
    if (primitive.kind === "flow") return {
      ...common,
      kind: "flow",
      points: primitive.points,
      tone: primitive.tone ?? "neutral",
      marker: primitive.marker !== false,
    };
    return {
      ...common,
      kind: "text",
      x: primitive.x,
      y: primitive.y,
      value: primitive.value,
      emphasis: primitive.emphasis ?? false,
      tone: primitive.tone ?? "neutral",
    };
  };
  const semanticPrimitiveKey = (primitive: DetailPrimitive): string => {
    if (primitive.kind === "flow") return `flow:${primitive.channel ?? "unnamed"}`;
    if (primitive.kind === "text") return `text:${primitive.value}`;
    const label = primitive.label ?? (primitive.kind === "matrix" ? "tensor" : "submodule");
    return `${primitive.kind}:${label}`;
  };
  const stablePrimitiveSlot = (level: InlineDetailLevel, primitive: DetailPrimitive, index: number): string => {
    const key = semanticPrimitiveKey(primitive);
    const occurrence = level.diagram.primitives.slice(0, index)
      .filter((candidate) => semanticPrimitiveKey(candidate) === key).length;
    return `${level.levelKey}:${key}${occurrence ? `:${occurrence + 1}` : ""}`;
  };
  const flatten = (level: InlineDetailLevel): RenderDetailPrimitive[] => {
    const expanded = inlineExpandedChildren(level);
    const expandedIds = new Set(expanded.map((child) => child.node.id));
    const current = level.diagram.primitives.flatMap((primitive, index) => {
      const node = level.nodes.find((candidate) => candidate.primitiveIndex === index);
      const edgeId = primitive.kind === "flow" ? `${level.levelKey}:flow:${index}` : undefined;
      if (node && expandedIds.has(node.id)) return [];
      if (edgeId && hiddenFlowIds.has(edgeId)) return [];
      const converted = convert(primitive, index, level);
      const stableSlot = stablePrimitiveSlot(level, primitive, index);
      return [{
        ...converted,
        primitiveId: slotId(binding, stableSlot),
        slotId: stableSlot,
      }];
    });
    return [...current, ...expanded.flatMap((child) => flatten(child.level))];
  };
  return {
    nodeId: "",
    bindingId: binding.bindingId,
    templateId: binding.templateId,
    evidenceIds: binding.evidenceIds,
    bounds: { ...bounds },
    entryPoint: atomicEntry?.point ?? root.diagram.entryPoint,
    exitPoint: atomicExit?.point ?? root.diagram.exitPoint,
    entrySide: atomicEntry?.side,
    exitSide: atomicExit?.side,
    entryIsInterior: Boolean(atomicEntry?.atomId),
    exitIsInterior: Boolean(atomicExit),
    hierarchyRoutingMode: options.mode,
    primitives: flatten(root),
  };
}

export function buildTemplateDetail(
  nodeId: string,
  binding: KernelTemplateBinding | undefined,
  bounds: Bounds,
  detailOffsets: Record<string, Point> = {},
  expansion?: DetailExpansionBranch,
  routing: {
    mode?: HierarchyRoutingMode;
    hasIncoming?: boolean;
    hasOutgoing?: boolean;
  } = {},
): RenderTemplateDetail | undefined {
  if (!templateDetailSize(binding, expansion) || !binding) return undefined;
  const kind = detailKindForTemplate(binding.templateId);
  if (!kind) return undefined;
  const hierarchyRoutingMode = routing.mode ?? "atomic-bottom-up";
  const detail = {
    // Keep the exact Q/K/V binding contract stable: its slot IDs and adjacent
    // flow anchors are part of the formal interaction surface. Catalog kinds
    // use the shared prototype detail primitive stream below.
    ...(expansion
      ? recursiveDetail(binding, kind, bounds, expansion, {
        mode: hierarchyRoutingMode,
        hideEntryBridge: hierarchyRoutingMode === "atomic-bottom-up" && routing.hasIncoming,
        hideExitBridge: hierarchyRoutingMode === "atomic-bottom-up" && routing.hasOutgoing,
      })
      : binding.templateId === "attention.qkv-v1"
      ? attentionDetail(binding, bounds)
      : genericDetail(binding, kind, bounds)),
    nodeId,
  };
  const originalShapes = detail.primitives.filter((primitive) => primitive.kind === "box" || primitive.kind === "matrix" || primitive.kind === "operator");
  const shapeBounds = (primitive: Extract<RenderDetailPrimitive, { kind: "box" | "matrix" | "operator" }>): Bounds => primitive.kind === "operator"
    ? { x: primitive.cx - primitive.radius, y: primitive.cy - primitive.radius, width: primitive.radius * 2, height: primitive.radius * 2 }
    : { x: primitive.x, y: primitive.y, width: primitive.width, height: primitive.height };
  const clampedOffsets = new Map(originalShapes.map((primitive) => {
    const requested = detailOffsets[primitive.primitiveId] ?? { x: 0, y: 0 };
    const primitiveBounds = shapeBounds(primitive);
    return [primitive.primitiveId, {
      x: Math.max(bounds.x - primitiveBounds.x, Math.min(bounds.x + bounds.width - primitiveBounds.x - primitiveBounds.width, requested.x)),
      y: Math.max(bounds.y + 56 - primitiveBounds.y, Math.min(bounds.y + bounds.height - primitiveBounds.y - primitiveBounds.height, requested.y)),
    }];
  }));
  const touches = (point: Point, primitiveBounds: Bounds) => {
    const tolerance = 2;
    const withinX = point.x >= primitiveBounds.x - tolerance && point.x <= primitiveBounds.x + primitiveBounds.width + tolerance;
    const withinY = point.y >= primitiveBounds.y - tolerance && point.y <= primitiveBounds.y + primitiveBounds.height + tolerance;
    const onVertical = Math.abs(point.x - primitiveBounds.x) <= tolerance || Math.abs(point.x - primitiveBounds.x - primitiveBounds.width) <= tolerance;
    const onHorizontal = Math.abs(point.y - primitiveBounds.y) <= tolerance || Math.abs(point.y - primitiveBounds.y - primitiveBounds.height) <= tolerance;
    return withinX && withinY && (onVertical || onHorizontal);
  };
  const moveEndpoint = (points: Point[], index: number, offset: Point): Point[] => {
    if (offset.x === 0 && offset.y === 0) return points;
    const result = points.map((point) => ({ ...point }));
    const neighborIndex = index === 0 ? 1 : result.length - 2;
    const original = result[index];
    const neighbor = result[neighborIndex];
    result[index] = { x: original.x + offset.x, y: original.y + offset.y };
    if (neighbor) {
      if (neighbor.x === original.x) neighbor.x += offset.x;
      if (neighbor.y === original.y) neighbor.y += offset.y;
    }
    return result;
  };
  const moved = detail.primitives.map((primitive): RenderDetailPrimitive => {
    if (primitive.kind !== "flow") {
      const offset = clampedOffsets.get(primitive.primitiveId) ?? { x: 0, y: 0 };
      if (primitive.kind === "box" || primitive.kind === "matrix") return { ...primitive, x: primitive.x + offset.x, y: primitive.y + offset.y };
      if (primitive.kind === "operator") return { ...primitive, cx: primitive.cx + offset.x, cy: primitive.cy + offset.y };
      return primitive;
    }
    let points = primitive.points;
    const first = primitive.points[0];
    const last = primitive.points.at(-1)!;
    const source = originalShapes.find((shape) => touches(first, shapeBounds(shape)));
    const target = originalShapes.find((shape) => touches(last, shapeBounds(shape)));
    if (source) points = moveEndpoint(points, 0, clampedOffsets.get(source.primitiveId) ?? { x: 0, y: 0 });
    if (target) points = moveEndpoint(points, points.length - 1, clampedOffsets.get(target.primitiveId) ?? { x: 0, y: 0 });
    return { ...primitive, points };
  });
  return { ...detail, primitives: moved };
}
