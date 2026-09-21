import type { CanvasPoint } from './coordinates'

export type CanvasGuide = { axis: 'x' | 'y'; value: number }
export type SnappableNode = { id: string; x: number; y: number; width: number; height: number }

const GRID = 16

export function snapPosition(position: CanvasPoint, moving: SnappableNode | undefined, nodes: SnappableNode[], selectedIds: string[], zoom: number, bypass: boolean) {
  if (bypass) return { position, guides: [] as CanvasGuide[] }
  const snapped = { x: Math.round(position.x / GRID) * GRID, y: Math.round(position.y / GRID) * GRID }
  if (!moving) return { position: snapped, guides: [] as CanvasGuide[] }
  const threshold = 7 / zoom
  const guides: CanvasGuide[] = []
  for (const candidate of nodes) {
    if (candidate.id === moving.id || selectedIds.includes(candidate.id)) continue
    for (const [axis, own, other] of [
      ['x', snapped.x, candidate.x],
      ['x', snapped.x + moving.width / 2, candidate.x + candidate.width / 2],
      ['y', snapped.y, candidate.y],
      ['y', snapped.y + moving.height / 2, candidate.y + candidate.height / 2],
    ] as const) {
      if (Math.abs(own - other) <= threshold) {
        if (axis === 'x') snapped.x += other - own
        else snapped.y += other - own
        guides.push({ axis, value: other })
      }
    }
  }
  return { position: snapped, guides }
}

