import type { CanvasPoint } from './coordinates'

type SelectionEvent = { shiftKey: boolean; metaKey: boolean; ctrlKey: boolean }
type SpatialNode = { id: string; x: number; y: number; width: number; height: number }

export function selectionAfter(event: SelectionEvent, nodeId: string, selected: string[]) {
  if (event.shiftKey || event.metaKey || event.ctrlKey) {
    return selected.includes(nodeId) ? selected.filter((id) => id !== nodeId) : [...selected, nodeId]
  }
  return selected.includes(nodeId) ? selected : [nodeId]
}

export function marqueeSelection(nodes: SpatialNode[], start: CanvasPoint, end: CanvasPoint) {
  const left = Math.min(start.x, end.x)
  const right = Math.max(start.x, end.x)
  const top = Math.min(start.y, end.y)
  const bottom = Math.max(start.y, end.y)
  return nodes
    .filter((node) => node.x >= left && node.y >= top && node.x + node.width <= right && node.y + node.height <= bottom)
    .map((node) => node.id)
}

