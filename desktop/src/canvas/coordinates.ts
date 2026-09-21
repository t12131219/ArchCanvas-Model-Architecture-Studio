export type CanvasPoint = { x: number; y: number }

export type CanvasViewport = { x: number; y: number; zoom: number }

export function clientToViewportPoint(event: { clientX: number; clientY: number }, stage: HTMLElement): CanvasPoint {
  const bounds = stage.getBoundingClientRect()
  return { x: event.clientX - bounds.left, y: event.clientY - bounds.top }
}

export function screenToWorld(point: CanvasPoint, viewport: CanvasViewport): CanvasPoint {
  return { x: (point.x - viewport.x) / viewport.zoom, y: (point.y - viewport.y) / viewport.zoom }
}

