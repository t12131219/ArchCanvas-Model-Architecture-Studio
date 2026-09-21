import { useEffect, useLayoutEffect, useMemo, useRef, useState, type KeyboardEvent, type PointerEvent, type WheelEvent } from 'react'
import { Maximize, Minus, MousePointer2, Plus, Scan, Undo2 } from 'lucide-react'

import type { ArchitectureEdge, ArchitectureNode, CanvasNodeState, ScientificMiniature } from '../engine/types'
import { clientToViewportPoint, screenToWorld, type CanvasPoint, type CanvasViewport } from './coordinates'
import type { CanvasGesture, MarqueeGesture } from './interactions'
import { marqueeSelection, selectionAfter } from './selection'
import { snapPosition, type CanvasGuide } from './snapping'
import { clampZoom, fitViewport, zoomAtPoint } from './viewport'
import './CanvasStage.css'

export type { CanvasPoint } from './coordinates'

export type CanvasStageNode = ArchitectureNode & CanvasNodeState

type CanvasStageProps = {
  editable: boolean
  edges: ArchitectureEdge[]
  miniatures: ScientificMiniature[]
  nodes: CanvasStageNode[]
  selectedIds: string[]
  viewport: CanvasViewport
  onCommitMove: (positions: Record<string, CanvasPoint>) => void
  onCommitViewport: (viewport: CanvasViewport) => void
  onSelectionChange: (ids: string[]) => void
  onToggleCollapse: (nodeId: string) => void
  onGestureChange: (active: boolean) => void
}

function nodeStyle(node: CanvasStageNode) {
  if (node.style.fill_color) return { background: node.style.fill_color }
  return undefined
}

function nodeLabel(node: CanvasStageNode) {
  if (node.kind === 'repeat_group') {
    const alreadyIncludesCount = /(?:x|times)\s+\d+/i.test(node.label)
    return `${node.label}${node.members > 1 && !alreadyIncludesCount ? ` x ${node.members}` : ''}`
  }
  return node.label
}

function ScientificMiniaturePreview({ miniatures }: { miniatures: ScientificMiniature[] }) {
  if (!miniatures.length) return null
  return <span className="scientific-miniatures" aria-label="Scientific visual previews">
    {miniatures.map((miniature) => <span
      key={miniature.id}
      className={`scientific-miniature miniature-${miniature.kind}`}
      data-disclosure={miniature.disclosure}
      data-miniature-kind={miniature.kind}
      title={`${miniature.label} (${miniature.disclosure})`}
    >
      {miniature.kind === 'signal_preview' && <svg viewBox="0 0 64 18" aria-hidden="true"><path d="M1 10 C8 1 14 17 22 9 S36 1 43 9 S55 17 63 7" /></svg>}
      {miniature.kind === 'tensor_strip' && <i className="tensor-cells" aria-hidden="true"><b /><b /><b /><b /></i>}
      {miniature.kind === 'distribution_preview' && <svg viewBox="0 0 64 18" aria-hidden="true"><path d="M1 15 C15 15 17 2 32 2 S49 15 63 15" /></svg>}
      {miniature.kind === 'equation_note' && <strong aria-hidden="true">N x</strong>}
      {miniature.kind === 'inset_callout' && <i className="inset-frame" aria-hidden="true" />}
      <em>{miniature.disclosure === 'illustrative' ? 'schematic' : 'evidence'}</em>
    </span>)}
  </span>
}

function edgePath(source: CanvasStageNode, target: CanvasStageNode, residual: boolean) {
  const startX = source.x + source.width
  const startY = source.y + source.height / 2
  const endX = target.x
  const endY = target.y + target.height / 2
  if (residual) {
    const bend = Math.max(44, Math.abs(endX - startX) * 0.28)
    return `M ${startX} ${startY} C ${startX + bend} ${startY - 82}, ${endX - bend} ${endY - 82}, ${endX} ${endY}`
  }
  const middle = startX + (endX - startX) / 2
  return `M ${startX} ${startY} H ${middle} V ${endY} H ${endX}`
}

export function CanvasStage({
  editable,
  edges,
  miniatures,
  nodes,
  selectedIds,
  viewport,
  onCommitMove,
  onCommitViewport,
  onSelectionChange,
  onToggleCollapse,
  onGestureChange,
}: CanvasStageProps) {
  const stageRef = useRef<HTMLDivElement>(null)
  const gestureRef = useRef<CanvasGesture | null>(null)
  const wheelTimer = useRef<number | null>(null)
  const [previewPositions, setPreviewPositions] = useState<Record<string, CanvasPoint>>({})
  const [localViewport, setLocalViewport] = useState(viewport)
  const [guides, setGuides] = useState<CanvasGuide[]>([])
  const [marquee, setMarquee] = useState<MarqueeGesture | null>(null)
  const [fitMode, setFitMode] = useState(true)
  const spaceHeld = useRef(false)

  useEffect(() => {
    if (!fitMode) setLocalViewport(viewport)
  }, [fitMode, viewport])

  const displayedNodes = useMemo(
    () => nodes.map((node) => ({ ...node, ...(previewPositions[node.id] ?? {}) })),
    [nodes, previewPositions],
  )

  const nodeById = useMemo(() => new Map(displayedNodes.map((node) => [node.id, node])), [displayedNodes])
  const miniaturesByTarget = useMemo(() => {
    const grouped = new Map<string, ScientificMiniature[]>()
    for (const miniature of miniatures) grouped.set(miniature.targetId, [...(grouped.get(miniature.targetId) ?? []), miniature])
    return grouped
  }, [miniatures])

  function commitViewport(next: CanvasViewport) {
    setLocalViewport(next)
    onCommitViewport(next)
  }

  function fit() {
    const stage = stageRef.current
    if (!stage || !nodes.length) return
    const next = fitViewport(nodes, stage.clientWidth, stage.clientHeight)
    if (!next) return
    setLocalViewport(next)
    onCommitViewport(next)
  }

  useLayoutEffect(() => {
    const stage = stageRef.current
    if (!stage) return
    const observer = new ResizeObserver(() => {
      if (fitMode) fit()
    })
    observer.observe(stage)
    return () => observer.disconnect()
  // fit reads current nodes and stage dimensions; only re-fit when the canvas model changes.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fitMode, nodes])

  useEffect(() => () => {
    if (wheelTimer.current !== null) window.clearTimeout(wheelTimer.current)
  }, [])

  useEffect(() => {
    function onWindowKeyDown(event: globalThis.KeyboardEvent) {
      if (event.code === 'Space' && event.target instanceof HTMLElement && !['INPUT', 'TEXTAREA', 'SELECT'].includes(event.target.tagName)) spaceHeld.current = true
    }
    function onWindowKeyUp(event: globalThis.KeyboardEvent) {
      if (event.code === 'Space') spaceHeld.current = false
    }
    function onWindowBlur() {
      spaceHeld.current = false
      cancelGesture()
    }
    window.addEventListener('keydown', onWindowKeyDown)
    window.addEventListener('keyup', onWindowKeyUp)
    window.addEventListener('blur', onWindowBlur)
    return () => {
      window.removeEventListener('keydown', onWindowKeyDown)
      window.removeEventListener('keyup', onWindowKeyUp)
      window.removeEventListener('blur', onWindowBlur)
    }
  })

  function finishGesture() {
    const gesture = gestureRef.current
    gestureRef.current = null
    onGestureChange(false)
    setGuides([])
    setMarquee(null)
    if (!gesture) return
    if (gesture.kind === 'drag') {
      const committed = previewPositions
      setPreviewPositions({})
      if (Object.keys(committed).length) onCommitMove(committed)
      return
    }
    if (gesture.kind === 'pan') commitViewport(localViewport)
    if (gesture.kind === 'marquee') {
      const worldStart = screenToWorld(gesture.start, localViewport)
      const worldEnd = screenToWorld(gesture.current, localViewport)
      const left = Math.min(worldStart.x, worldEnd.x)
      const right = Math.max(worldStart.x, worldEnd.x)
      const top = Math.min(worldStart.y, worldEnd.y)
      const bottom = Math.max(worldStart.y, worldEnd.y)
      onSelectionChange(marqueeSelection(displayedNodes, { x: left, y: top }, { x: right, y: bottom }))
    }
  }

  function cancelGesture() {
    gestureRef.current = null
    onGestureChange(false)
    setPreviewPositions({})
    setGuides([])
    setMarquee(null)
  }

  function onPointerMove(event: PointerEvent<HTMLDivElement>) {
    const gesture = gestureRef.current
    const stage = stageRef.current
    if (!gesture || !stage) return
    const point = clientToViewportPoint(event, stage)
    if (gesture.kind === 'pan') {
      setLocalViewport({ ...gesture.viewport, x: gesture.viewport.x + point.x - gesture.start.x, y: gesture.viewport.y + point.y - gesture.start.y })
      return
    }
    if (gesture.kind === 'marquee') {
      const next = { ...gesture, current: point }
      gestureRef.current = next
      setMarquee(next)
      return
    }
    const delta = { x: (point.x - gesture.start.x) / localViewport.zoom, y: (point.y - gesture.start.y) / localViewport.zoom }
    const next: Record<string, CanvasPoint> = {}
    let activeGuides: CanvasGuide[] = []
    for (const id of gesture.selected) {
      const initial = gesture.positions[id]
      const result = snapPosition({ x: initial.x + delta.x, y: initial.y + delta.y }, nodes.find((node) => node.id === id), nodes, selectedIds, localViewport.zoom, event.altKey)
      next[id] = result.position
      activeGuides = [...activeGuides, ...result.guides]
    }
    setPreviewPositions(next)
    setGuides(activeGuides)
  }

  function onStagePointerDown(event: PointerEvent<HTMLDivElement>) {
    const stage = stageRef.current
    if (!stage || (event.target instanceof Element && event.target.closest('.architecture-node, .canvas-controls'))) return
    const point = clientToViewportPoint(event, stage)
    if (event.button === 1 || spaceHeld.current) {
      event.preventDefault()
      setFitMode(false)
      gestureRef.current = { kind: 'pan', start: point, viewport: localViewport }
      onGestureChange(true)
      event.currentTarget.setPointerCapture(event.pointerId)
      return
    }
    if (event.button === 0) {
      gestureRef.current = { kind: 'marquee', start: point, current: point }
      onGestureChange(true)
      setMarquee(gestureRef.current)
      event.currentTarget.setPointerCapture(event.pointerId)
    }
  }

  function onNodePointerDown(event: PointerEvent<HTMLButtonElement>, node: CanvasStageNode) {
    if (event.button !== 0) return
    event.stopPropagation()
    const nextSelection = selectionAfter(event, node.id, selectedIds)
    onSelectionChange(nextSelection)
    if (!editable || node.locked || !nextSelection.includes(node.id)) return
    const stage = stageRef.current
    if (!stage) return
    const positions = Object.fromEntries(
      displayedNodes.filter((item) => nextSelection.includes(item.id) && !item.locked).map((item) => [item.id, { x: item.x, y: item.y }]),
    )
    if (!Object.keys(positions).length) return
    setFitMode(false)
    gestureRef.current = { kind: 'drag', start: clientToViewportPoint(event, stage), positions, selected: Object.keys(positions) }
    onGestureChange(true)
    stage.setPointerCapture(event.pointerId)
  }

  function onWheel(event: WheelEvent<HTMLDivElement>) {
    event.preventDefault()
    const stage = stageRef.current
    if (!stage) return
    const point = clientToViewportPoint(event, stage)
    const next = zoomAtPoint(localViewport, point, event.deltaY)
    setFitMode(false)
    setLocalViewport(next)
    if (wheelTimer.current !== null) window.clearTimeout(wheelTimer.current)
    wheelTimer.current = window.setTimeout(() => onCommitViewport(next), 180)
  }

  function onKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'a') {
      event.preventDefault()
      onSelectionChange(displayedNodes.map((node) => node.id))
      return
    }
    if (event.key === 'Escape') {
      onSelectionChange([])
      return
    }
    if (!editable || !selectedIds.length || !['ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight'].includes(event.key)) return
    event.preventDefault()
    const amount = event.shiftKey ? 16 : 4
    const delta = event.key === 'ArrowUp' ? { x: 0, y: -amount }
      : event.key === 'ArrowDown' ? { x: 0, y: amount }
        : event.key === 'ArrowLeft' ? { x: -amount, y: 0 } : { x: amount, y: 0 }
    const positions = Object.fromEntries(displayedNodes.filter((node) => selectedIds.includes(node.id) && !node.locked).map((node) => [node.id, { x: node.x + delta.x, y: node.y + delta.y }]))
    if (Object.keys(positions).length) onCommitMove(positions)
  }

  const marqueeStyle = marquee && {
    left: Math.min(marquee.start.x, marquee.current.x),
    top: Math.min(marquee.start.y, marquee.current.y),
    width: Math.abs(marquee.current.x - marquee.start.x),
    height: Math.abs(marquee.current.y - marquee.start.y),
  }

  return (
    <div
      ref={stageRef}
      aria-label="Model architecture canvas"
      className={`canvas-stage${localViewport.zoom < 0.58 ? ' is-low-detail' : ''}`}
      data-canvas-stage
      onKeyDown={onKeyDown}
      onPointerCancel={cancelGesture}
      onPointerDown={onStagePointerDown}
      onPointerMove={onPointerMove}
      onPointerUp={finishGesture}
      onWheel={onWheel}
      tabIndex={0}
    >
      <div className="canvas-chrome" aria-hidden="true"><span>Publication canvas</span><span>{editable ? 'Visual edits only' : 'Evidence view'}</span></div>
      <div className="canvas-controls" role="toolbar" aria-label="Canvas viewport controls">
        <button type="button" title="Zoom out" onClick={() => { setFitMode(false); commitViewport({ ...localViewport, zoom: clampZoom(localViewport.zoom - 0.1) }) }}><Minus size={15} /></button>
        <button type="button" title="Fit canvas" onClick={() => { setFitMode(true); fit() }}><Scan size={15} /></button>
        <button type="button" title="Zoom in" onClick={() => { setFitMode(false); commitViewport({ ...localViewport, zoom: clampZoom(localViewport.zoom + 0.1) }) }}><Plus size={15} /></button>
        <span className="zoom-readout">{Math.round(localViewport.zoom * 100)}%</span>
      </div>
      <div className="canvas-tool-hint" aria-hidden="true"><MousePointer2 size={13} />Drag to move <span>Space to pan</span></div>
      <div className="canvas-world" style={{ transform: `translate(${localViewport.x}px, ${localViewport.y}px) scale(${localViewport.zoom})` }}>
        <svg className="canvas-edges" aria-hidden="true" width="1800" height="1100">
          <defs><marker id="canvas-arrow" markerWidth="9" markerHeight="9" refX="8" refY="4" orient="auto"><path d="M 0 0 L 8 4 L 0 8 z" /></marker></defs>
          {edges.map((edge) => {
            const source = nodeById.get(edge.source)
            const target = nodeById.get(edge.target)
            return source && target ? <path key={edge.id} className={edge.residual ? 'canvas-edge residual' : 'canvas-edge'} d={edgePath(source, target, !!edge.residual)} markerEnd="url(#canvas-arrow)" /> : null
          })}
        </svg>
        {guides.map((guide, index) => guide.axis === 'x'
          ? <div key={`${guide.axis}-${index}`} className="canvas-guide vertical" style={{ left: guide.value }} />
          : <div key={`${guide.axis}-${index}`} className="canvas-guide horizontal" style={{ top: guide.value }} />)}
        {displayedNodes.map((node) => (
          <button
            key={node.id}
            aria-label={`${node.label}${node.locked ? ', locked' : ''}`}
            className={`architecture-node node-${node.kind}${selectedIds.includes(node.id) ? ' is-selected' : ''}${node.locked ? ' is-locked' : ''}`}
            data-id={node.id}
            data-canvas-node={node.id}
            onDoubleClick={() => editable && node.kind === 'repeat_group' && onToggleCollapse(node.id)}
            onPointerDown={(event) => onNodePointerDown(event, node)}
            style={{ ...nodeStyle(node), height: node.height, transform: `translate(${node.x}px, ${node.y}px)`, width: node.width }}
            type="button"
          >
            {node.kind === 'repeat_group' && <span className="repeat-stack" aria-hidden="true"><i /><i /></span>}
            <span className="node-eyebrow">{node.kind === 'repeat_group' ? `${node.members || 1}x repeated block` : node.kind === 'input' || node.kind === 'output' ? 'data terminal' : 'model operation'}</span>
            <span className="node-label">{nodeLabel(node)}</span>
            {node.kind === 'repeat_group' && <span className="repeat-hint">{node.collapsed ? 'Double-click for detail' : 'Detail open'}</span>}
            <ScientificMiniaturePreview miniatures={miniaturesByTarget.get(node.id) ?? []} />
          </button>
        ))}
      </div>
      {marqueeStyle && <div className="selection-marquee" style={marqueeStyle} />}
      {selectedIds.length > 1 && <div className="selection-summary"><Maximize size={13} />{selectedIds.length} selected</div>}
      {editable && <div className="canvas-undo-hint" aria-hidden="true"><Undo2 size={13} />One drag, one undo step</div>}
    </div>
  )
}
