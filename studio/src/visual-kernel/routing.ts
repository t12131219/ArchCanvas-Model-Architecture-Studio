import type { Bounds, Point, RenderEdge, RenderNode, RouteStyle } from "./types";

function compact(points: Point[]): Point[] {
  const result: Point[] = [];
  for (const point of points) {
    const previous = result.at(-1);
    if (previous && previous.x === point.x && previous.y === point.y) continue;
    const before = result.at(-2);
    if (before && previous) {
      const collinear = (before.x === previous.x && previous.x === point.x)
        || (before.y === previous.y && previous.y === point.y);
      if (collinear) result.pop();
    }
    result.push(point);
  }
  return result;
}

function endpoint(bounds: Bounds, side: "left" | "right" | "top" | "bottom"): Point {
  if (side === "left") return { x: bounds.x, y: bounds.y + bounds.height / 2 };
  if (side === "right") return { x: bounds.x + bounds.width, y: bounds.y + bounds.height / 2 };
  if (side === "top") return { x: bounds.x + bounds.width / 2, y: bounds.y };
  return { x: bounds.x + bounds.width / 2, y: bounds.y + bounds.height };
}

export function routePoints(source: Bounds, target: Bounds, style: RouteStyle, via: Point[] = []): Point[] {
  const sourceCenter = { x: source.x + source.width / 2, y: source.y + source.height / 2 };
  const targetCenter = { x: target.x + target.width / 2, y: target.y + target.height / 2 };
  const horizontal = Math.abs(targetCenter.x - sourceCenter.x) >= Math.abs(targetCenter.y - sourceCenter.y);
  const sourceSide = horizontal ? (targetCenter.x >= sourceCenter.x ? "right" : "left") : (targetCenter.y >= sourceCenter.y ? "bottom" : "top");
  const targetSide = horizontal ? (targetCenter.x >= sourceCenter.x ? "left" : "right") : (targetCenter.y >= sourceCenter.y ? "top" : "bottom");
  const start = endpoint(source, sourceSide);
  const end = endpoint(target, targetSide);
  if (via.length && style === "curve") return [start, ...via, end];
  if (via.length) {
    const anchors = [start, ...via, end];
    const routed: Point[] = [start];
    for (let index = 1; index < anchors.length; index += 1) {
      const previous = anchors[index - 1];
      const current = anchors[index];
      if (previous.x !== current.x && previous.y !== current.y) {
        const channelX = (previous.x + current.x) / 2;
        routed.push({ x: channelX, y: previous.y }, { x: channelX, y: current.y });
      }
      routed.push(current);
    }
    return compact(routed);
  }
  if (style === "direct" || style === "curve") return [start, end];
  if (horizontal) {
    const channelX = style === "channel"
      ? Math.max(source.x + source.width, target.x + target.width) + 38
      : (start.x + end.x) / 2;
    return compact([start, { x: channelX, y: start.y }, { x: channelX, y: end.y }, end]);
  }
  const channelY = style === "channel"
    ? Math.max(source.y + source.height, target.y + target.height) + 38
    : (start.y + end.y) / 2;
  return compact([start, { x: start.x, y: channelY }, { x: end.x, y: channelY }, end]);
}

export function roundedPath(points: Point[], radius = 8): string {
  if (points.length < 2) return "";
  if (points.length === 2) return `M ${points[0].x} ${points[0].y} L ${points[1].x} ${points[1].y}`;
  let path = `M ${points[0].x} ${points[0].y}`;
  for (let index = 1; index < points.length - 1; index += 1) {
    const previous = points[index - 1];
    const current = points[index];
    const next = points[index + 1];
    const incoming = Math.hypot(current.x - previous.x, current.y - previous.y);
    const outgoing = Math.hypot(next.x - current.x, next.y - current.y);
    const corner = Math.min(radius, incoming / 2, outgoing / 2);
    const before = {
      x: current.x - Math.sign(current.x - previous.x) * corner,
      y: current.y - Math.sign(current.y - previous.y) * corner,
    };
    const after = {
      x: current.x + Math.sign(next.x - current.x) * corner,
      y: current.y + Math.sign(next.y - current.y) * corner,
    };
    path += ` L ${before.x} ${before.y} Q ${current.x} ${current.y} ${after.x} ${after.y}`;
  }
  const end = points.at(-1)!;
  return `${path} L ${end.x} ${end.y}`;
}

export function curvePath(points: Point[]): string {
  let path = `M ${points[0].x} ${points[0].y}`;
  for (let index = 1; index < points.length; index += 1) {
    const start = points[index - 1];
    const end = points[index];
    if (Math.abs(end.x - start.x) >= Math.abs(end.y - start.y)) {
      const offset = Math.max(18, Math.abs(end.x - start.x) * 0.38);
      path += ` C ${start.x + Math.sign(end.x - start.x || 1) * offset} ${start.y}, ${end.x - Math.sign(end.x - start.x || 1) * offset} ${end.y}, ${end.x} ${end.y}`;
    } else {
      const offset = Math.max(18, Math.abs(end.y - start.y) * 0.38);
      path += ` C ${start.x} ${start.y + Math.sign(end.y - start.y || 1) * offset}, ${end.x} ${end.y - Math.sign(end.y - start.y || 1) * offset}, ${end.x} ${end.y}`;
    }
  }
  return path;
}

export function labelGeometry(points: Point[]): { point: Point; angle: number } {
  let best = { start: points[0], end: points.at(-1)!, length: -1 };
  for (let index = 1; index < points.length; index += 1) {
    const start = points[index - 1];
    const end = points[index];
    const length = Math.hypot(end.x - start.x, end.y - start.y);
    if (length > best.length) best = { start, end, length };
  }
  return {
    point: { x: (best.start.x + best.end.x) / 2, y: (best.start.y + best.end.y) / 2 },
    angle: Math.abs(best.end.y - best.start.y) > Math.abs(best.end.x - best.start.x) ? -90 : 0,
  };
}

export function routeRenderEdge(
  edge: Omit<RenderEdge, "points" | "path" | "labelPoint" | "labelAngle">,
  source: RenderNode,
  target: RenderNode,
  style: RouteStyle,
  via: Point[] = [],
): RenderEdge {
  const points = routePoints(source.bounds, target.bounds, style, via);
  const label = labelGeometry(points);
  return {
    ...edge,
    points,
    path: style === "curve" ? curvePath(points) : roundedPath(points),
    labelPoint: label.point,
    labelAngle: label.angle,
  };
}
