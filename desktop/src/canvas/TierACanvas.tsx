import { useEffect, useMemo, useState } from 'react'
import type { TierAModel } from './tierAControls'

import './TierACanvas.css'

type Evidence = { file: string; line: number; expression: string; file_sha256?: string; grade: string }
type Node = {
  id: string; label: string; parent: string | null; lane: string; role: string
  shape: string; level: number; repeat: string; evidence: Evidence
}
type Edge = {
  id: string; source: string; target: string; kind: string
  source_port: string; target_port: string; evidence: Evidence
}
export type TierAGraph = {
  model: string; archive: string; archive_sha256: string; entrypoint: string
  task_branch: string; selection_status: string; config: Record<string, unknown>
  nodes: Node[]; edges: Edge[]
  discrepancies: Array<{ reference: string; element: string; resolution: string; status: string }>
}
type Box = { x: number; y: number; width: number; height: number }
type Scene = { boxes: Map<string, Box>; edges: Array<{ edge: Edge; source: Box; target: Box }>; width: number; height: number }
type Primitive =
  | 'container'
  | 'tensor'
  | 'projection-tensor'
  | 'fused-qkv'
  | 'merge'
  | 'condition'
  | 'axis-transform'
  | 'patch-tensor'
  | 'scale-stack'
  | 'decomposition'
  | 'operator'

const GAP = 25
const HEADER = 36

function primitiveFor(node: Node, hasChildren: boolean): Primitive {
  if (hasChildren || node.role === 'repeat') return 'container'
  if (/^Q\/K\/V projection$/i.test(node.label)) return 'fused-qkv'
  if (/^(Q|K|V) projection/i.test(node.label)) return 'projection-tensor'
  if (node.role === 'condition') return 'condition'
  if (node.role === 'merge') return 'merge'
  if (/invert .*axes|channel-first axes|restore forecast axes/i.test(node.label)) return 'axis-transform'
  if (/unfold\s*\/\s*patching/i.test(node.label)) return 'patch-tensor'
  if (/scale pyramid/i.test(node.label)) return 'scale-stack'
  if (node.role === 'decomposition' && /decomposition/i.test(node.label)) return 'decomposition'
  if (node.role === 'input' || node.role === 'output' || node.role === 'data') return 'tensor'
  return 'operator'
}

function tensorRole(node: Node): string {
  const role = node.label.match(/^(Q|K|V) projection/)?.[1]
  return role ?? (node.role === 'input' ? 'X' : node.role === 'output' ? 'Y' : 'T')
}

function mergeSymbol(node: Node): string {
  if (/sum/i.test(node.label)) return 'Σ'
  if (/concat|combine/i.test(node.label)) return '‖'
  if (/gate|weight/i.test(node.label)) return '×'
  return '+'
}

function buildScene(graph: TierAGraph, detail: number, expansions: Record<string, number>): Scene {
  const children = new Map<string | null, Node[]>()
  const byId = new Map(graph.nodes.map((node) => [node.id, node]))
  graph.nodes.forEach((node) => children.set(node.parent, [...(children.get(node.parent) ?? []), node]))
  const boxes = new Map<string, Box>()
  const visible = new Set<string>()
  const measured = new Map<string, number>()
  const rootWidth = detail >= 3 ? 470 : 344
  const leafHeight = detail >= 3 ? 62 : 70

  function included(node: Node): Node[] {
    const cap = expansions[node.id] ?? detail
    return (children.get(node.id) ?? []).filter((child) => child.level <= cap)
  }
  function rows(node: Node): Node[][] {
    const shown = included(node)
    const result: Node[][] = []
    for (let index = 0; index < shown.length;) {
      const trio = shown.slice(index, index + 3)
      const projections = node.role === 'attention' && trio.length === 3 &&
        trio.map((child) => child.id.match(/(?:^|_)(q|k|v)$/)?.[1]).join('') === 'qkv'
      const feedForward = node.role === 'ffn' && trio.length === 3 &&
        trio.every((child) => child.parent === node.id)
      if (projections || feedForward) {
        result.push(trio)
        index += 3
      } else {
        result.push([shown[index]])
        index++
      }
    }
    return result
  }
  function height(node: Node): number {
    if (measured.has(node.id)) return measured.get(node.id)!
    const shown = included(node)
    const summaryCount = (children.get(node.id) ?? []).filter((child) => child.role !== 'data').length
    const primitive = primitiveFor(node, false)
    const ownHeight = primitive === 'projection-tensor' ? 90
      : primitive === 'fused-qkv' ? 108
        : primitive === 'axis-transform' || primitive === 'patch-tensor' || primitive === 'scale-stack' ? 98
          : primitive === 'decomposition' ? 94
            : primitive === 'merge' && !/norm/i.test(node.label) ? 82
            : primitive === 'tensor' ? 76 : leafHeight
    const size = shown.length ? HEADER + 12 + rows(node).reduce((sum, row) => sum + Math.max(...row.map(height)) + 8, 0)
      : node.role === 'repeat' ? Math.max(150, 42 + summaryCount * 27) : ownHeight
    measured.set(node.id, size)
    return size
  }
  function place(node: Node, x: number, y: number, width: number): void {
    const box = { x, y, width, height: height(node) }
    boxes.set(node.id, box)
    visible.add(node.id)
    let offset = y + box.height - 8
    for (const row of rows(node)) {
      const rowHeight = Math.max(...row.map(height))
      offset -= rowHeight
      const columnWidth = (width - 32 - (row.length - 1) * 8) / row.length
      row.forEach((child, index) => place(child, x + 16 + index * (columnWidth + 8), offset, columnWidth))
      offset -= 8
    }
  }
  const roots = children.get(null) ?? []
  const hasTwoLanes = roots.some((node) => node.lane === 'encoder') && roots.some((node) => node.lane === 'decoder')
  const lanes = hasTwoLanes ? ['encoder', 'decoder'] : ['main']
  const width = hasTwoLanes ? 2 * rootWidth + 250 : rootWidth + 96
  const assigned = (lane: string) => roots.filter((node) => hasTwoLanes
    ? (lane === 'encoder' ? node.lane !== 'decoder' : node.lane === 'decoder')
    : true)
  const laneHeights = lanes.map((lane) => assigned(lane).reduce((sum, node) => sum + height(node) + GAP, 0))
  const total = Math.max(400, ...laneHeights) + 64
  lanes.forEach((lane, index) => {
    let bottom = total - 32
    const x = hasTwoLanes ? (index === 0 ? 42 : rootWidth + 208) : 48
    for (const node of assigned(lane)) {
      bottom -= height(node)
      place(node, x, bottom, rootWidth)
      bottom -= GAP
    }
  })
  function endpoint(id: string): Box | undefined {
    let node = byId.get(id)
    while (node && !visible.has(node.id)) node = node.parent ? byId.get(node.parent) : undefined
    return node ? boxes.get(node.id) : undefined
  }
  return {
    boxes, width, height: total,
    edges: graph.edges.flatMap((edge) => {
      const source = endpoint(edge.source)
      const target = endpoint(edge.target)
      return source && target && source !== target ? [{ edge, source, target }] : []
    }),
  }
}

function route(source: Box, target: Box, kind: string, targetPort: string): string {
  if (kind === 'memory') {
    const x1 = source.x + source.width
    const x2 = target.x
    const offset = targetPort === 'K_in' ? -10 : targetPort === 'V_in' ? 10 : 0
    const y1 = source.y + source.height / 2 + offset
    const y2 = target.y + target.height / 2 + offset
    return `M${x1} ${y1} H${(x1 + x2) / 2} V${y2} H${x2}`
  }
  if (kind === 'residual') {
    const x = source.x - 10
    return `M${source.x} ${source.y + source.height / 2} H${x} V${target.y + target.height / 2} H${target.x}`
  }
  if (Math.abs(source.y - target.y) < 2 && source.x + source.width < target.x) {
    return `M${source.x + source.width} ${source.y + source.height / 2} H${target.x}`
  }
  const x1 = source.x + source.width / 2
  const x2 = target.x + target.width / 2
  const y1 = source.y
  const y2 = target.y + target.height
  return `M${x1} ${y1} V${(y1 + y2) / 2} H${x2} V${y2}`
}

function edgeRole(edge: Edge): string {
  if (edge.kind === 'memory') return edge.target_port === 'K_in' ? 'K memory' : edge.target_port === 'V_in' ? 'V memory' : 'memory'
  if (edge.kind === 'residual') return 'skip'
  if (edge.kind === 'condition') return 'mask'
  if (edge.target_port === 'Q_in' || edge.target_port === 'K_in' || edge.target_port === 'V_in') return edge.target_port.slice(0, 1)
  const sourceRole = edge.source.match(/(?:^|_)(q|k|v)$/)?.[1]
  if (sourceRole) return sourceRole.toUpperCase()
  return ''
}

function edgeLabelPoint(source: Box, target: Box, kind: string, targetPort: string) {
  if (kind === 'memory') return { x: (source.x + source.width + target.x) / 2, y: target.y + target.height / 2 + (targetPort === 'K_in' ? -14 : 18) }
  if (kind === 'residual') return { x: source.x - 16, y: (source.y + target.y + target.height) / 2 }
  if (kind === 'condition') return { x: (source.x + target.x + target.width) / 2, y: (source.y + target.y + target.height) / 2 - 6 }
  return { x: (source.x + source.width / 2 + target.x + target.width / 2) / 2, y: (source.y + target.y + target.height) / 2 - 5 }
}

function MatrixGlyph({ x, y, width, role }: { x: number; y: number; width: number; role: string }) {
  const columns = 5
  const rows = 3
  const cell = Math.min(9, Math.max(5, (width - 8) / columns))
  const matrixWidth = columns * cell
  return <g className={`tier-a-matrix tier-a-matrix-${role.toLowerCase()}`} data-tensor-role={role}>
    {Array.from({ length: rows * columns }, (_, index) => <rect
      key={index}
      x={x + (index % columns) * cell}
      y={y + Math.floor(index / columns) * cell}
      width={cell - 1}
      height={cell - 1}
      rx=".5"
    />)}
    <text x={x + matrixWidth / 2} y={y - 4} textAnchor="middle" className="tier-a-matrix-role">{role}</text>
  </g>
}

function FusedQkvGlyph({ box }: { box: Box }) {
  const centerX = box.x + box.width / 2
  return <>
    <rect className="tier-a-primitive tier-a-operator-capsule" x={box.x + 8} y={box.y + 7} width={box.width - 16} height="27" rx="4" />
    <path className="tier-a-qkv-branch" d={`M${centerX} ${box.y + 34} V${box.y + 45} M${box.x + 25} ${box.y + 45} H${box.x + box.width - 25}`} />
    {['Q', 'K', 'V'].map((role, index) => {
      const x = box.x + 25 + index * ((box.width - 50) / 2)
      return <g key={role}>
        <path className="tier-a-inner-arrow" d={`M${x} ${box.y + 45} V${box.y + 55}`} markerEnd="url(#tier-arrow-small)" />
        <MatrixGlyph x={x - 17} y={box.y + 64} width={34} role={role} />
      </g>
    })}
  </>
}

function AxisTransformGlyph({ box }: { box: Box }) {
  const y = box.y + 51
  return <>
    <g className="tier-a-axis-grid tier-a-axis-before">
      {[0, 1, 2].map((row) => [0, 1, 2, 3].map((column) => <rect key={`${row}-${column}`} x={box.x + 18 + column * 8} y={y + row * 8} width="7" height="7" />))}
    </g>
    <path className="tier-a-axis-arrow" d={`M${box.x + 57} ${y + 12} H${box.x + box.width - 60}`} markerEnd="url(#tier-arrow-small)" />
    <g className="tier-a-axis-grid tier-a-axis-after">
      {[0, 1, 2, 3].map((row) => [0, 1, 2].map((column) => <rect key={`${row}-${column}`} x={box.x + box.width - 43 + column * 8} y={y - 4 + row * 8} width="7" height="7" />))}
    </g>
    <text className="tier-a-axis-caption" x={box.x + 34} y={y - 5} textAnchor="middle">L x N</text>
    <text className="tier-a-axis-caption" x={box.x + box.width - 31} y={y - 9} textAnchor="middle">N x L</text>
  </>
}

function PatchGlyph({ box }: { box: Box }) {
  const startX = box.x + 22
  const y = box.y + 55
  return <>
    <path className="tier-a-patch-signal" d={`M${startX} ${y + 13} q10 -20 20 0 t20 0 t20 0 t20 0`} />
    {[0, 1, 2, 3].map((index) => <rect key={index} className="tier-a-patch-window" x={startX + 9 + index * 21} y={y - 2} width="27" height="30" rx="2" />)}
    <path className="tier-a-axis-arrow" d={`M${startX + 99} ${y + 13} H${box.x + box.width - 24}`} markerEnd="url(#tier-arrow-small)" />
    <g className="tier-a-patch-stack">
      {[0, 1, 2].map((index) => <rect key={index} x={box.x + box.width - 21 + index * 3} y={y + 4 - index * 3} width="13" height="19" />)}
    </g>
  </>
}

function ScaleStackGlyph({ box }: { box: Box }) {
  const widths = [92, 72, 52, 34]
  return <g className="tier-a-scale-stack">
    {widths.map((width, index) => <g key={width}>
      <rect x={box.x + 18} y={box.y + 48 + index * 10} width={width} height="7" rx="1" />
      <text x={box.x + 116} y={box.y + 55 + index * 10}>x{2 ** index}</text>
    </g>)}
    <path d={`M${box.x + 139} ${box.y + 48} V${box.y + 79}`} markerEnd="url(#tier-arrow-small)" />
  </g>
}

function DecompositionGlyph({ box }: { box: Box }) {
  const centerX = box.x + box.width / 2
  const y = box.y + 49
  return <>
    <path className="tier-a-decomp-line" d={`M${centerX} ${y - 8} V${y + 4} M${box.x + 45} ${y + 4} H${box.x + box.width - 45}`} />
    <circle className="tier-a-junction" cx={centerX} cy={y - 8} r="3.5" />
    <path className="tier-a-inner-arrow" d={`M${box.x + 45} ${y + 4} V${y + 14}`} markerEnd="url(#tier-arrow-small)" />
    <path className="tier-a-inner-arrow" d={`M${box.x + box.width - 45} ${y + 4} V${y + 14}`} markerEnd="url(#tier-arrow-small)" />
    <rect className="tier-a-season-strip" x={box.x + 18} y={y + 18} width="54" height="17" rx="2" />
    <rect className="tier-a-trend-strip" x={box.x + box.width - 72} y={y + 18} width="54" height="17" rx="2" />
    <text className="tier-a-branch-caption" x={box.x + 45} y={y + 30} textAnchor="middle">season</text>
    <text className="tier-a-branch-caption" x={box.x + box.width - 45} y={y + 30} textAnchor="middle">trend</text>
  </>
}

function PrimitiveShape({ node, box, expanded, selected }: { node: Node; box: Box; expanded: boolean; selected: boolean }) {
  const primitive = primitiveFor(node, expanded)
  const selectedClass = selected ? ' tier-a-selected' : ''
  const centerX = box.x + box.width / 2
  const centerY = box.y + box.height / 2
  if (primitive === 'condition') {
    const rx = Math.min(56, box.width / 2 - 8)
    const ry = Math.min(27, box.height / 2 - 5)
    return <>
      <rect className="tier-a-hit" x={box.x} y={box.y} width={box.width} height={box.height} />
      <path className={`tier-a-primitive tier-a-condition-shape${selectedClass}`} d={`M${centerX} ${centerY - ry} L${centerX + rx} ${centerY} L${centerX} ${centerY + ry} L${centerX - rx} ${centerY} Z`} />
    </>
  }
  if (primitive === 'merge') {
    const compoundNorm = /norm/i.test(node.label)
    return <>
      <rect className="tier-a-hit" x={box.x} y={box.y} width={box.width} height={box.height} />
      <circle className={`tier-a-primitive tier-a-merge-circle${selectedClass}`} cx={compoundNorm ? box.x + 44 : centerX} cy={centerY} r="17" />
      <text className="tier-a-merge-symbol" x={compoundNorm ? box.x + 44 : centerX} y={centerY + 6} textAnchor="middle">{mergeSymbol(node)}</text>
      {compoundNorm && <><path className="tier-a-inner-arrow" d={`M${box.x + 62} ${centerY} H${box.x + 83}`} markerEnd="url(#tier-arrow-small)" /><rect className={`tier-a-norm-capsule${selectedClass}`} x={box.x + 87} y={centerY - 18} width={box.width - 103} height="36" rx="5" /></>}
    </>
  }
  if (primitive === 'projection-tensor') {
    const role = tensorRole(node)
    return <>
      <rect className="tier-a-hit" x={box.x} y={box.y} width={box.width} height={box.height} />
      <rect className={`tier-a-primitive tier-a-operator-capsule${selectedClass}`} x={box.x + 8} y={box.y + 7} width={box.width - 16} height="27" rx="4" />
      <path className="tier-a-inner-arrow" d={`M${centerX} ${box.y + 35} V${box.y + 46}`} markerEnd="url(#tier-arrow-small)" />
      <MatrixGlyph x={centerX - 22} y={box.y + 55} width={44} role={role} />
    </>
  }
  if (primitive === 'fused-qkv') {
    return <>
      <rect className="tier-a-hit" x={box.x} y={box.y} width={box.width} height={box.height} />
      <FusedQkvGlyph box={box} />
    </>
  }
  if (primitive === 'axis-transform' || primitive === 'patch-tensor' || primitive === 'scale-stack' || primitive === 'decomposition') {
    return <>
      <rect className="tier-a-hit" x={box.x} y={box.y} width={box.width} height={box.height} />
      <rect className={`tier-a-primitive tier-a-${primitive}-shape${selectedClass}`} x={box.x} y={box.y} width={box.width} height={box.height} rx="4" />
      {primitive === 'axis-transform' && <AxisTransformGlyph box={box} />}
      {primitive === 'patch-tensor' && <PatchGlyph box={box} />}
      {primitive === 'scale-stack' && <ScaleStackGlyph box={box} />}
      {primitive === 'decomposition' && <DecompositionGlyph box={box} />}
    </>
  }
  if (primitive === 'tensor') {
    const role = tensorRole(node)
    return <>
      <rect className="tier-a-hit" x={box.x} y={box.y} width={box.width} height={box.height} />
      <path className={`tier-a-primitive tier-a-tensor-shell${selectedClass}`} d={`M${box.x + 8} ${box.y + 7} H${box.x + box.width - 17} L${box.x + box.width - 8} ${box.y + 16} V${box.y + box.height - 7} H${box.x + 8} Z`} />
      <MatrixGlyph x={box.x + 18} y={centerY - 10} width={48} role={role} />
    </>
  }
  return <>
    <rect className="tier-a-hit" x={box.x} y={box.y} width={box.width} height={box.height} />
    {node.role === 'repeat' && <>
      <rect className="tier-a-stack-back" x={box.x + 8} y={box.y - 7} width={box.width - 8} height={box.height} rx="5" />
      <rect className="tier-a-stack-middle" x={box.x + 4} y={box.y - 3} width={box.width - 4} height={box.height} rx="5" />
    </>}
    <rect className={`tier-a-primitive tier-a-${primitive}-shape${selectedClass}`} x={box.x} y={box.y} width={box.width} height={box.height} rx={primitive === 'container' ? 6 : 4} />
  </>
}

export function TierACanvas({ model }: { model: TierAModel }) {
  const [graph, setGraph] = useState<TierAGraph | null>(null)
  const [error, setError] = useState('')
  const [detail, setDetail] = useState(1)
  const [expansions, setExpansions] = useState<Record<string, number>>({})
  const [selectedId, setSelectedId] = useState<string | null>(null)
  useEffect(() => {
    let active = true
    fetch(`/tier-a/${model}.json`).then((response) => {
      if (!response.ok) throw new Error(`Tier A contract unavailable: ${model}`)
      return response.json() as Promise<TierAGraph>
    }).then((value) => {
      if (!active) return
      try {
        const saved = JSON.parse(localStorage.getItem(`archcanvas:tier-a:${model}:${value.archive_sha256}`) ?? 'null')
        if (saved && Number.isInteger(saved.detail) && saved.detail >= 1 && saved.detail <= 4 &&
          saved.expansions && typeof saved.expansions === 'object') {
          const known = new Set(value.nodes.map((node) => node.id))
          setDetail(saved.detail)
          setExpansions(Object.fromEntries(Object.entries(saved.expansions).filter(([id, level]) =>
            known.has(id) && Number.isInteger(level) && (level as number) >= 0 && (level as number) <= 4)) as Record<string, number>)
        }
      } catch { /* Browser storage may be disabled; the diagram remains usable. */ }
      setGraph(value)
    })
      .catch((reason: unknown) => { if (active) setError(String(reason)) })
    return () => { active = false }
  }, [model])
  useEffect(() => {
    if (!graph || graph.model !== model) return
    try {
      localStorage.setItem(`archcanvas:tier-a:${model}:${graph.archive_sha256}`, JSON.stringify({ detail, expansions }))
    } catch { /* Local visual state is optional. */ }
  }, [graph, model, detail, expansions])
  const scene = useMemo(() => graph ? buildScene(graph, detail, expansions) : null, [graph, detail, expansions])
  const selected = graph?.nodes.find((node) => node.id === selectedId)
  if (error) return <div className="tier-a-error" role="alert">{error}</div>
  if (!graph || !scene) return <div className="tier-a-error">Loading source-mapped architecture...</div>
  const visibleNodes = graph.nodes.filter((node) => scene.boxes.has(node.id))
  const expanded = (node: Node) => visibleNodes.some((child) => child.parent === node.id)
  const expandOne = (node: Node) => setExpansions((current) => ({
    ...current,
    [node.id]: expanded(node) ? Math.min(4, (current[node.id] ?? detail) + 1) : Math.min(4, node.level + 1),
  }))
  return <div className="tier-a-workspace">
    <div className="tier-a-toolbar" aria-label="Architecture detail">
      <span>{model === 'itransformer' ? 'iTransformer' : model === 'patchtst' ? 'PatchTST' : model === 'timemixer' ? 'TimeMixer' : model === 'autoformer' ? 'Autoformer' : 'Transformer'}</span>
      <div className="tier-a-segments">{[1, 2, 3, 4].map((level) => <button key={level} type="button" aria-pressed={detail === level} onClick={() => { setDetail(level); setExpansions({}) }} title={`Show L${level} architecture`}>L{level}</button>)}</div>
      <button type="button" className="tier-a-command" onClick={() => { setDetail(4); setExpansions({}) }}>Open full</button>
      <div className="tier-a-legend" aria-label="Diagram legend">
        <span><i className="legend-tensor" />Tensor</span>
        <span><i className="legend-operator" />Operator</span>
        <span><i className="legend-merge">+</i>Merge</span>
        <span><i className="legend-condition" />Condition</span>
        <span><i className="legend-repeat" />Repeat</span>
      </div>
    </div>
    <div className="tier-a-scroll">
      <svg className="tier-a-svg" xmlns="http://www.w3.org/2000/svg" width={scene.width} height={scene.height} viewBox={`0 0 ${scene.width} ${scene.height}`} role="img" aria-label={`${graph.model} source-mapped architecture L${detail}`}>
        <defs>
          <marker id="tier-arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0 0 L8 4 L0 8 Z" className="tier-a-arrowhead" /></marker>
          <marker id="tier-arrow-small" markerWidth="6" markerHeight="6" refX="5" refY="3" orient="auto"><path d="M0 0 L6 3 L0 6 Z" className="tier-a-arrowhead" /></marker>
        </defs>
        <rect width="100%" height="100%" fill="#ffffff" />
        {scene.edges.map(({ edge, source, target }) => {
          const label = edgeRole(edge)
          const point = edgeLabelPoint(source, target, edge.kind, edge.target_port)
          return <g key={edge.id} className="tier-a-edge-group">
            <path data-edge-id={edge.id} data-source-id={edge.source} data-target-id={edge.target} data-source-port={edge.source_port} data-target-port={edge.target_port} d={route(source, target, edge.kind, edge.target_port)} className={`tier-a-edge tier-a-${edge.kind}`} markerEnd="url(#tier-arrow)"><title>{`${edge.kind}: ${edge.source}.${edge.source_port} -> ${edge.target}.${edge.target_port}\n${edge.evidence.grade}: ${edge.evidence.file}:${edge.evidence.line}`}</title></path>
            {label && <text x={point.x} y={point.y} textAnchor="middle" className={`tier-a-edge-label tier-a-edge-label-${edge.kind}`}>{label}</text>}
          </g>
        })}
        {visibleNodes.map((node) => {
          const box = scene.boxes.get(node.id)!
          const isExpanded = expanded(node)
          const primitive = primitiveFor(node, isExpanded)
          return <g key={node.id} className={`tier-a-node tier-a-role-${node.role}`} data-canonical-id={node.id} data-primitive={primitive} tabIndex={0} role="button" aria-label={`${node.label}, ${isExpanded ? 'expanded' : 'collapsed'}`} onClick={(event) => { event.stopPropagation(); setSelectedId(node.id); expandOne(node) }} onKeyDown={(event) => { if (event.key === 'Enter') { event.preventDefault(); event.stopPropagation(); setSelectedId(node.id); expandOne(node) } }}>
            <title>{`${node.evidence.file}:${node.evidence.line}\n${node.evidence.expression}`}</title>
            <PrimitiveShape node={node} box={box} expanded={isExpanded} selected={selectedId === node.id} />
          </g>
        })}
        {visibleNodes.map((node) => {
          const box = scene.boxes.get(node.id)!
          const isExpanded = expanded(node)
          const primitive = primitiveFor(node, isExpanded)
          const compact = box.width < 130
          const miniature = primitive === 'axis-transform' || primitive === 'patch-tensor' || primitive === 'scale-stack' || primitive === 'decomposition'
          const labelX = primitive === 'tensor' ? box.x + box.width * .63 : primitive === 'merge' && /norm/i.test(node.label) ? box.x + 87 + (box.width - 103) / 2 : box.x + box.width / 2
          const labelY = primitive === 'projection-tensor' || primitive === 'fused-qkv' ? box.y + 25 : miniature ? box.y + 22 : primitive === 'merge' ? (/norm/i.test(node.label) ? box.y + box.height / 2 + 5 : box.y + 15) : box.y + (isExpanded ? 24 : node.shape ? 21 : box.height / 2 + 5)
          const visibleLabel = primitive === 'projection-tensor' ? (node.label.includes('+ split') ? 'Project + split' : 'Linear') : primitive === 'fused-qkv' ? 'Q/K/V projections' : primitive === 'merge' && /norm/i.test(node.label) ? node.label.replace(/^(Add|Residual)\s*\+\s*/, '') : compact ? node.label.replace(' projection', '') : node.label
          return <g key={`label-${node.id}`} pointerEvents="none">
            <text x={labelX} y={labelY} textAnchor="middle" className={`tier-a-label${compact ? ' tier-a-compact' : ''}${compact && visibleLabel.length > 12 ? ' tier-a-tight' : ''}`}>{visibleLabel}</text>
            {node.repeat && <text x={box.x + box.width - 12} y={box.y + 17} textAnchor="end" className="tier-a-repeat">{node.repeat}</text>}
            {!isExpanded && node.shape && primitive !== 'projection-tensor' && primitive !== 'fused-qkv' && !miniature && <text x={primitive === 'tensor' ? labelX : box.x + box.width / 2} y={box.y + box.height - 11} textAnchor="middle" className="tier-a-shape">{node.shape}</text>}
            {primitive === 'projection-tensor' && node.shape && <text x={box.x + box.width - 7} y={box.y + box.height - 7} textAnchor="end" className="tier-a-shape tier-a-shape-compact">{node.shape}</text>}
            {!isExpanded && node.role === 'repeat' && graph.nodes.filter((child) => child.parent === node.id && child.role !== 'data').map((child, index) => <g key={child.id} className={`tier-a-summary-node tier-a-role-${child.role}`}><rect x={box.x + 14} y={box.y + 27 + index * 26} width={box.width - 28} height="23" rx="3" /><text x={box.x + box.width / 2} y={box.y + 43 + index * 26} textAnchor="middle" className="tier-a-summary">{child.label}</text></g>)}
          </g>
        })}
      </svg>
    </div>
    {selected && <div className="tier-a-evidence"><strong>{selected.label}</strong><span>{selected.evidence.grade} | {selected.evidence.file}:{selected.evidence.line}</span><code>{selected.evidence.expression}</code><button type="button" onClick={() => setExpansions((current) => ({ ...current, [selected.id]: 0 }))}>Collapse</button><button type="button" onClick={() => setExpansions((current) => ({ ...current, [selected.id]: 4 }))}>Expand fully</button></div>}
  </div>
}
