import type { CanvasPoint, CanvasViewport } from './coordinates'

export type DragGesture = { kind: 'drag'; start: CanvasPoint; positions: Record<string, CanvasPoint>; selected: string[] }
export type PanGesture = { kind: 'pan'; start: CanvasPoint; viewport: CanvasViewport }
export type MarqueeGesture = { kind: 'marquee'; start: CanvasPoint; current: CanvasPoint }
export type CanvasGesture = DragGesture | PanGesture | MarqueeGesture

