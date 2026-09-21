import type { CanvasPoint, CanvasViewport } from './coordinates'

export type SpatialNode = { x: number; y: number; width: number; height: number }

export const MIN_ZOOM = 0.35
export const MAX_ZOOM = 2.2

export function clampZoom(value: number) {
  return Math.min(Math.max(value, MIN_ZOOM), MAX_ZOOM)
}

export function fitViewport(nodes: SpatialNode[], width: number, height: number): CanvasViewport | null {
  if (!nodes.length || width <= 0 || height <= 0) return null
  const left = Math.min(...nodes.map((node) => node.x))
  const top = Math.min(...nodes.map((node) => node.y))
  const right = Math.max(...nodes.map((node) => node.x + node.width))
  const bottom = Math.max(...nodes.map((node) => node.y + node.height))
  const padding = 92
  const zoom = Math.min(clampZoom(Math.min((width - padding * 2) / (right - left), (height - padding * 2) / (bottom - top))), 1)
  return { x: (width - (right - left) * zoom) / 2 - left * zoom, y: (height - (bottom - top) * zoom) / 2 - top * zoom, zoom }
}

export function zoomAtPoint(viewport: CanvasViewport, point: CanvasPoint, deltaY: number): CanvasViewport {
  const world = { x: (point.x - viewport.x) / viewport.zoom, y: (point.y - viewport.y) / viewport.zoom }
  const zoom = clampZoom(viewport.zoom * Math.exp(-deltaY * 0.0015))
  return { x: point.x - world.x * zoom, y: point.y - world.y * zoom, zoom }
}

