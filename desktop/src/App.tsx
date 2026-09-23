import { useEffect, useMemo, useRef, useState, type FormEvent } from 'react'
import {
  ArrowLeft,
  ArrowRight,
  Download,
  FileCode2,
  Lock,
  Maximize2,
  Move,
  PanelRight,
  Play,
  RotateCcw,
  Save,
  Unlock,
} from 'lucide-react'

import './App.css'
import { CanvasStage, type CanvasPoint, type CanvasStageNode } from './canvas/CanvasStage'
import { TierACanvas } from './canvas/TierACanvas'
import { exportTierASvg, TIER_A_MODELS, type TierAModel } from './canvas/tierAControls'
import { appendHistory } from './canvas/history'
import {
  createEngineClient,
  createInsertLayerNormPatchSet,
  createParameterPatchSet,
  createRemoveLayerNormPatchSet,
} from './engine/client'
import type { ArchitectureEdge, ArchitectureNode, CanvasDocument, DesktopSnapshot, ProjectOpenInput, PatchResult, PatchSet } from './engine/types'

const engine = createEngineClient()
const isTauri = '__TAURI_INTERNALS__' in window
const tierAQuery = new URLSearchParams(window.location.search).get('tierA')
const showTierA = isTauri || tierAQuery !== null
const initialTierModel = TIER_A_MODELS.find((model) => model === tierAQuery) ?? (isTauri ? 'transformer' : null)

const EDITABLE_PARAMETER_LABELS: Record<string, string> = {
  num_heads: 'Number of attention heads',
  dropout: 'Dropout probability',
  activation: 'Activation',
}

const EXPORT_PALETTE = {
  ink: '#1b1b18',
  edge: '#5c5c55',
  paper: '#ffffff',
  accent: '#2868b7',
  blue: '#dceafa',
  green: '#ddefd7',
  rose: '#f8d9d4',
} as const

function defaultNodeStyle(kind: string) {
  if (kind === 'input' || kind === 'output') return { fill_color: EXPORT_PALETTE.rose }
  if (kind === 'repeat_group') return { fill_color: EXPORT_PALETTE.green }
  return { fill_color: EXPORT_PALETTE.blue }
}

function toCanvasNodes(snapshot: DesktopSnapshot, exact: boolean): CanvasStageNode[] {
  if (exact) {
    return snapshot.exactNodes.map((node, index) => ({
      ...node,
      publication_node_id: node.id,
      x: 72 + (index % 4) * 222,
      y: 150 + Math.floor(index / 4) * 138,
      width: 178,
      height: 76,
      style: defaultNodeStyle(node.kind),
      collapsed: false,
      locked: true,
    }))
  }
  return snapshot.nodes.flatMap((node) => {
    const visual = snapshot.document.nodes.find((item) => item.publication_node_id === node.id)
    return visual ? [{ ...node, ...visual }] : []
  })
}

function canvasEdges(snapshot: DesktopSnapshot, exact: boolean): ArchitectureEdge[] {
  return exact ? snapshot.exactEdges : snapshot.edges
}

function moveDocument(document: CanvasDocument, positions: Record<string, CanvasPoint>): CanvasDocument {
  if (!Object.keys(positions).length) return document
  return {
    ...document,
    layout_mode: 'manual',
    nodes: document.nodes.map((node) => {
      const position = positions[node.publication_node_id]
      return position ? { ...node, x: position.x, y: position.y } : node
    }),
  }
}

function layoutDocument(document: CanvasDocument): CanvasDocument {
  return {
    ...document,
    layout_mode: 'automatic',
    nodes: document.nodes.map((node, index) => ({
      ...node,
      x: 72 + (index % 4) * 222,
      y: 150 + Math.floor(index / 4) * 138,
    })),
  }
}

function svgEscape(value: string) {
  return value.replace(/[&<>"']/g, (character) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&apos;' })[character] ?? character)
}

function downloadSvg(nodes: CanvasStageNode[], edges: ArchitectureEdge[]) {
  const nodeById = new Map(nodes.map((node) => [node.id, node]))
  const paths = edges.map((edge) => {
    const source = nodeById.get(edge.source)
    const target = nodeById.get(edge.target)
    if (!source || !target) return ''
    const startX = source.x + source.width
    const startY = source.y + source.height / 2
    const endX = target.x
    const endY = target.y + target.height / 2
    const route = edge.residual
      ? `M ${startX} ${startY} C ${startX + 52} ${startY - 72}, ${endX - 52} ${endY - 72}, ${endX} ${endY}`
      : `M ${startX} ${startY} H ${(startX + endX) / 2} V ${endY} H ${endX}`
    return `<path d="${route}" class="${edge.residual ? 'residual' : ''}" marker-end="url(#arrow)"/>`
  }).join('')
  const shapes = nodes.map((node) => {
    const fill = node.style.fill_color ?? defaultNodeStyle(node.kind).fill_color
    const repeat = node.kind === 'repeat_group' ? `<text class="repeat" x="${node.x + node.width - 20}" y="${node.y + 20}">${node.members}x</text>` : ''
    return `<rect x="${node.x}" y="${node.y}" width="${node.width}" height="${node.height}" rx="6" fill="${fill}"/><text x="${node.x + node.width / 2}" y="${node.y + node.height / 2 + 5}" text-anchor="middle">${svgEscape(node.label)}</text>${repeat}`
  }).join('')
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720" viewBox="0 0 1280 720"><style>rect{stroke:${EXPORT_PALETTE.ink};stroke-width:1.4}path{fill:none;stroke:${EXPORT_PALETTE.edge};stroke-width:1.5}.residual{stroke:${EXPORT_PALETTE.accent};stroke-dasharray:5 4}text{fill:${EXPORT_PALETTE.ink};font:16px Georgia,serif}.repeat{font:11px sans-serif;fill:${EXPORT_PALETTE.edge}}</style><defs><marker id="arrow" markerWidth="9" markerHeight="9" refX="8" refY="4" orient="auto"><path d="M 0 0 L 8 4 L 0 8 z" fill="${EXPORT_PALETTE.edge}"/></marker></defs><rect width="1280" height="720" fill="${EXPORT_PALETTE.paper}" stroke="none"/>${paths}${shapes}</svg>`
  const url = URL.createObjectURL(new Blob([svg], { type: 'image/svg+xml' }))
  const link = document.createElement('a')
  link.href = url
  link.download = 'archcanvas-publication.svg'
  link.click()
  URL.revokeObjectURL(url)
}

function App() {
  const [snapshot, setSnapshot] = useState<DesktopSnapshot | null>(null)
  const [selectedIds, setSelectedIds] = useState<string[]>([])
  const [history, setHistory] = useState<CanvasDocument[]>([])
  const [historyIndex, setHistoryIndex] = useState(-1)
  const historyIndexRef = useRef(-1)
  const saveSequence = useRef(0)
  const saveQueue = useRef<Promise<unknown>>(Promise.resolve())
  const [gestureActive, setGestureActive] = useState(false)
  const [notice, setNotice] = useState('Loading desktop canvas...')
  const [view, setView] = useState<'publication' | 'exact'>('publication')
  const [tierModel, setTierModel] = useState<TierAModel | null>(initialTierModel)
  const [openProject, setOpenProject] = useState(false)
  const [opening, setOpening] = useState(false)
  const [patchBusy, setPatchBusy] = useState(false)
  const [patchSet, setPatchSet] = useState<PatchSet | null>(null)
  const [patchResult, setPatchResult] = useState<PatchResult | null>(null)
  const [parameterDrafts, setParameterDrafts] = useState<Record<string, string>>({})
  const [structuralAttribute, setStructuralAttribute] = useState('insert_norm')
  const [structuralShape, setStructuralShape] = useState('256')
  const [projectInput, setProjectInput] = useState<ProjectOpenInput>({
    projectId: 'project:desktop-model', approvedRoot: '', entrypoint: 'model.py:Model',
    pythonExecutable: '', environmentName: 'TFB_py311',
  })

  useEffect(() => {
    engine.load().then((loaded) => {
      if (!tierAQuery) setTierModel(null)
      setSnapshot(loaded)
      setHistory([loaded.document])
      setHistoryIndex(0)
      historyIndexRef.current = 0
      setNotice(loaded.validation.message)
    }).catch((error: unknown) => {
      setNotice(error instanceof Error ? error.message : 'Desktop initialization failed.')
      setOpenProject(!isTauri)
    })
  }, [])

  const nodes = useMemo(() => (snapshot ? toCanvasNodes(snapshot, view === 'exact') : []), [snapshot, view])
  const edges = useMemo(() => (snapshot ? canvasEdges(snapshot, view === 'exact') : []), [snapshot, view])
  const selectedId = selectedIds.at(-1) ?? null
  const selected = (view === 'exact' ? snapshot?.exactNodes : snapshot?.nodes)?.find((node) => node.id === selectedId) ?? null
  const selectedVisual = snapshot?.document.nodes.find((node) => node.publication_node_id === selectedId) ?? null
  const selectedMiniatures = snapshot?.miniatures.filter((miniature) => miniature.targetId === selectedId) ?? []
  const canvasSelectedIds = selectedIds.filter((nodeId) => nodes.some((node) => node.id === nodeId))
  const structuralCandidate = useMemo(() => {
    if (
      !snapshot
      || view !== 'exact'
      || snapshot.mode !== 'engine'
      || !snapshot.structuralPatchOperations.includes('insert_layer_norm')
      || !selected
      || selected.kind !== 'module'
    ) return null
    const incoming = snapshot.exactEdges.filter((edge) => edge.target === selected.id && !edge.residual)
    if (incoming.length !== 1) return null
    const source = snapshot.exactNodes.find((node) => node.id === incoming[0].source)
    if (
      source?.kind !== 'module'
      || !selected.sourceAnchorIds?.some((anchorId) => anchorId.endsWith('.constructor'))
      || incoming[0].evidenceAnchorIds?.length !== 1
    ) return null
    return { source, edge: incoming[0] }
  }, [selected, snapshot, view])
  const structuralRemovalCandidate = useMemo(() => {
    if (
      !snapshot
      || view !== 'exact'
      || snapshot.mode !== 'engine'
      || !snapshot.structuralPatchOperations.includes('remove_layer_norm')
      || !selected
      || selected.opType !== 'nn.LayerNorm'
    ) return null
    const incoming = snapshot.exactEdges.filter((edge) => edge.target === selected.id && !edge.residual)
    const outgoing = snapshot.exactEdges.filter((edge) => edge.source === selected.id && !edge.residual)
    if (incoming.length !== 1 || outgoing.length !== 1 || incoming[0].evidenceAnchorIds?.length !== 1) return null
    const source = snapshot.exactNodes.find((node) => node.id === incoming[0].source)
    const target = snapshot.exactNodes.find((node) => node.id === outgoing[0].target)
    if (
      source?.kind !== 'module'
      || target?.kind !== 'module'
      || !selected.sourceAnchorIds?.some((anchorId) => anchorId.endsWith('.constructor'))
    ) return null
    return { source, target, sourceEdge: incoming[0], targetEdge: outgoing[0] }
  }, [selected, snapshot, view])

  function parseParameterValue(raw: string, before: unknown): unknown {
    if (typeof before === 'number') return Number(raw)
    if (typeof before === 'boolean') return raw === 'true'
    return raw
  }

  async function planCandidatePatch(candidate: PatchSet) {
    if (!snapshot) return
    setPatchBusy(true)
    setPatchSet(null)
    setPatchResult(null)
    try {
      const planned = await engine.planPatch(snapshot.projectId, candidate)
      if (!planned.ok) { setNotice(`${planned.code}: ${planned.message}`); return }
      const validated = await engine.validatePatch(snapshot.projectId, candidate)
      if (validated.ok) {
        setPatchSet(candidate)
        setPatchResult(validated.result)
        setNotice('Candidate patch validated. Source bytes are unchanged; explicit commit is still required.')
      } else {
        setPatchResult(planned.result)
        setNotice(`${validated.code}: ${validated.message}`)
      }
    } catch (error) { setNotice(error instanceof Error ? error.message : 'Patch planning failed.') }
    finally { setPatchBusy(false) }
  }

  async function planParameterPatch(parameter: NonNullable<ArchitectureNode['parameters']>[number]) {
    if (!snapshot || !selected || snapshot.mode !== 'engine' || typeof parameter.value === 'undefined') return
    try {
      const next = parseParameterValue(parameterDrafts[parameter.name] ?? String(parameter.value), parameter.value)
      await planCandidatePatch(createParameterPatchSet(snapshot, selected, parameter, next))
    } catch (error) { setNotice(error instanceof Error ? error.message : 'Patch planning failed.') }
  }

  async function planStructuralPatch() {
    if (!snapshot || !selected || !structuralCandidate) return
    try {
      await planCandidatePatch(createInsertLayerNormPatchSet(
        snapshot,
        structuralCandidate.source,
        selected,
        structuralCandidate.edge,
        structuralAttribute,
        Number(structuralShape),
      ))
    } catch (error) { setNotice(error instanceof Error ? error.message : 'Patch planning failed.') }
  }

  async function planStructuralRemoval() {
    if (!snapshot || !selected || !structuralRemovalCandidate) return
    try {
      await planCandidatePatch(createRemoveLayerNormPatchSet(
        snapshot,
        structuralRemovalCandidate.source,
        selected,
        structuralRemovalCandidate.target,
        structuralRemovalCandidate.sourceEdge,
        structuralRemovalCandidate.targetEdge,
      ))
    } catch (error) { setNotice(error instanceof Error ? error.message : 'Patch planning failed.') }
  }

  function cancelParameterPatch() {
    setPatchSet(null)
    setPatchResult(null)
    setNotice('Candidate patch cancelled. Source bytes are unchanged.')
  }

  async function commitParameterPatch() {
    if (!snapshot || !patchSet) return
    if (!patchResult || patchResult.kind !== 'patch_validated' || !patchResult.confirmation_id) {
      setNotice('Validate the candidate before committing it.')
      return
    }
    setPatchBusy(true)
    try {
      const outcome = await engine.commitPatch(snapshot.projectId, patchSet, patchResult.confirmation_id)
      if (!outcome.ok) setNotice(`${outcome.code}: ${outcome.message}`)
      else {
        const refreshed = await engine.load()
        saveSequence.current += 1
        setSnapshot(refreshed)
        setPatchSet(null)
        setPatchResult(null)
        setNotice('Source patch committed by Engine and analysis refreshed.')
      }
    } finally { setPatchBusy(false) }
  }

  function record(document: CanvasDocument) {
    const nextIndex = historyIndexRef.current + 1
    historyIndexRef.current = nextIndex
    setSnapshot((current) => (current ? { ...current, document } : current))
    setHistory((current) => appendHistory({ entries: current, index: nextIndex - 1 }, document).entries)
    setHistoryIndex(nextIndex)
  }

  async function persist(document: CanvasDocument) {
    const sequence = ++saveSequence.current
    const pending = saveQueue.current.then(() => engine.saveCanvas(document))
    saveQueue.current = pending.catch(() => undefined)
    try {
      const outcome = await pending
      if (sequence !== saveSequence.current) return
      if (outcome.ok) setSnapshot((current) => (current ? { ...current, document: outcome.document } : current))
      setNotice(outcome.message)
    } catch (error) {
      if (sequence === saveSequence.current) setNotice(error instanceof Error ? error.message : 'Visual save failed.')
    }
  }

  function restore(document: CanvasDocument, index: number) {
    historyIndexRef.current = index
    setHistoryIndex(index)
    setSnapshot((current) => (current ? { ...current, document } : current))
    void persist(document)
  }

  function commitMove(positions: Record<string, CanvasPoint>) {
    if (!snapshot || view !== 'publication') return
    const next = moveDocument(snapshot.document, positions)
    if (next === snapshot.document) return
    record(next)
    void persist(next)
  }

  function commitViewport(viewport: CanvasDocument['viewport']) {
    if (!snapshot || view !== 'publication') return
    const next = { ...snapshot.document, viewport }
    setSnapshot((current) => (current ? { ...current, document: next } : current))
    void persist(next)
  }

  function resetLayout() {
    if (!snapshot || view !== 'publication') return
    const next = layoutDocument(snapshot.document)
    record(next)
    void persist(next)
  }

  function toggleVisual(nodeId: string, field: 'locked' | 'collapsed') {
    if (!snapshot || view !== 'publication') return
    const next = {
      ...snapshot.document,
      layout_mode: 'manual' as const,
      nodes: snapshot.document.nodes.map((node) => node.publication_node_id === nodeId ? { ...node, [field]: !node[field] } : node),
    }
    record(next)
    void persist(next)
  }

  function submitProject(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    saveSequence.current += 1
    setOpening(true)
    engine.openProject(projectInput).then((loaded) => {
      setTierModel(null)
      setSnapshot(loaded)
      setSelectedIds([])
      setHistory([loaded.document])
      setHistoryIndex(0)
      historyIndexRef.current = 0
      setNotice(loaded.validation.message)
      setOpenProject(false)
    }).catch((error: unknown) => setNotice(error instanceof Error ? error.message : 'Project open failed.')).finally(() => setOpening(false))
  }

  return (
    <main className={`studio-shell${tierModel ? ' tier-a-mode' : ''}`}>
      <header className="topbar">
        <div className="brand"><span className="brand-mark">AC</span><span>ArchCanvas</span><small>Model Architecture Studio</small></div>
        <div className="project-identity"><FileCode2 size={16} /><span>{tierModel ? `${tierModel} source map` : snapshot?.projectName ?? 'Opening project'}</span><code>{tierModel ? 'Tier A / read-only' : snapshot?.sourceLabel}</code></div>
        <div className="top-actions">
          {isTauri && <button type="button" className="secondary-button" onClick={() => setOpenProject(true)}>Open project</button>}
          <button type="button" className="icon-button" title="Undo visual edit" aria-label="Undo visual edit" onClick={() => historyIndex > 0 && restore(history[historyIndex - 1], historyIndex - 1)} disabled={gestureActive || historyIndex <= 0}><ArrowLeft size={17} /></button>
          <button type="button" className="icon-button" title="Redo visual edit" aria-label="Redo visual edit" onClick={() => historyIndex < history.length - 1 && restore(history[historyIndex + 1], historyIndex + 1)} disabled={gestureActive || historyIndex >= history.length - 1}><ArrowRight size={17} /></button>
          <button type="button" className="icon-button" title="Reset automatic layout" aria-label="Reset automatic layout" onClick={resetLayout} disabled={gestureActive || view === 'exact' || !!tierModel}><RotateCcw size={17} /></button>
          <button type="button" className="icon-button" title="Export architecture SVG" aria-label="Export architecture SVG" onClick={() => tierModel ? exportTierASvg(tierModel) : downloadSvg(nodes, edges)} disabled={!tierModel && !nodes.length}><Download size={17} /></button>
        </div>
      </header>
      <section className={`workspace${tierModel ? ' tier-a-active' : ''}`}>
        <aside className="left-panel">
          <div className="panel-heading"><span>Project</span><span className="mode-chip">{tierModel ? 'SOURCE MAP' : snapshot?.mode === 'fixture-read-only' ? 'READ-ONLY FIXTURE' : 'ENGINE'}</span></div>
          <div className="project-row"><span className="status-dot" /> <span>{tierModel ? `tier-a:${tierModel}` : snapshot?.projectId ?? 'Waiting for client'}</span></div>
          <div className="section-label">Views</div>
          <div className="view-list">
            <button type="button" className={!tierModel && view === 'publication' ? 'active' : ''} onClick={() => { setTierModel(null); setView('publication'); setSelectedIds([]) }}><Play size={15} />Publication</button>
            <button type="button" className={!tierModel && view === 'exact' ? 'active' : ''} onClick={() => { setTierModel(null); setView('exact'); setSelectedIds([]) }}><Move size={15} />Exact Architecture</button>
          </div>
          {showTierA && <><div className="section-label">Tier A source maps</div><div className="view-list">
            {TIER_A_MODELS.map((model) => <button key={model} type="button" className={tierModel === model ? 'active' : ''} onClick={() => { setTierModel(model); setSelectedIds([]) }}><FileCode2 size={15} />{model === 'itransformer' ? 'iTransformer' : model === 'patchtst' ? 'PatchTST' : model === 'timemixer' ? 'TimeMixer' : model === 'autoformer' ? 'Autoformer' : 'Transformer'}</button>)}
          </div></>}
          {!tierModel && <><div className="section-label">Canvas document</div>
          <dl className="metadata"><dt>Layout</dt><dd>{snapshot?.document.layout_mode ?? '...'}</dd><dt>Revision</dt><dd className="revision">{snapshot?.sourceRevision.slice(0, 19) ?? '...'}</dd></dl></>}
        </aside>
        <section className="canvas-host" aria-label="Architecture canvas">
          {tierModel ? <TierACanvas key={tierModel} model={tierModel} /> : <CanvasStage
            key={view}
            editable={view === 'publication'}
            edges={edges}
            miniatures={view === 'publication' ? snapshot?.miniatures ?? [] : []}
            nodes={nodes}
            selectedIds={canvasSelectedIds}
            viewport={snapshot?.document.viewport ?? { x: 0, y: 0, zoom: 1 }}
            onCommitMove={commitMove}
            onCommitViewport={commitViewport}
            onSelectionChange={setSelectedIds}
            onToggleCollapse={(nodeId) => toggleVisual(nodeId, 'collapsed')}
            onGestureChange={setGestureActive}
          />}
        </section>
        <aside className="right-panel">
          <div className="panel-heading"><span>Inspector</span><PanelRight size={16} /></div>
          {tierModel ? <div className="inspector-content"><div className="node-kind">SOURCE-MAPPED SAMPLE</div><h1>{tierModel}</h1><dl className="metadata"><dt>Scope</dt><dd>Bundled archive</dd><dt>Config</dt><dd>Selection pending review</dd><dt>Source</dt><dd>Read-only</dd></dl></div> : selected ? <div className="inspector-content">
            <div className="node-kind">{selected.kind.replace('_', ' ')}</div><h1>{selected.label}</h1>
            <dl className="metadata"><dt>Members</dt><dd>{selected.members}</dd>{selectedVisual && <><dt>Position</dt><dd>{Math.round(selectedVisual.x)}, {Math.round(selectedVisual.y)}</dd></>}<dt>Evidence</dt><dd>{selected.anchor}</dd></dl>
            {selectedMiniatures.length > 0 && <div className="miniature-evidence"><span>Visual evidence</span>{selectedMiniatures.map((miniature) => <div key={miniature.id}><strong>{miniature.label}</strong><em>{miniature.disclosure}</em></div>)}</div>}
            <button type="button" className="source-link" onClick={() => void engine.requestSourceJump(selected.anchorId, selected.anchor).then(setNotice)}><FileCode2 size={15} />View source evidence</button>
            {snapshot?.mode === 'engine' && (selected.parameters ?? []).filter((parameter) => (
              parameter.origin === 'literal'
              && parameter.name in EDITABLE_PARAMETER_LABELS
              && snapshot.patchableParameters.includes(parameter.name)
            )).map((parameter) => (
              <div className="parameter-editor" key={parameter.name}>
                <label htmlFor={`parameter-${parameter.name}`}>{EDITABLE_PARAMETER_LABELS[parameter.name]}</label>
                <input id={`parameter-${parameter.name}`} value={parameterDrafts[parameter.name] ?? String(parameter.value)} onChange={(event) => setParameterDrafts({ ...parameterDrafts, [parameter.name]: event.target.value })} />
                <button type="button" onClick={() => void planParameterPatch(parameter)} disabled={patchBusy}>Plan source patch</button>
              </div>
            ))}
            {structuralCandidate && <div className="parameter-editor structural-editor">
              <label htmlFor="structural-attribute">LayerNorm attribute</label>
              <input id="structural-attribute" value={structuralAttribute} onChange={(event) => setStructuralAttribute(event.target.value)} />
              <label htmlFor="structural-shape">Normalized shape</label>
              <input id="structural-shape" type="number" min="1" step="1" value={structuralShape} onChange={(event) => setStructuralShape(event.target.value)} />
              <button type="button" onClick={() => void planStructuralPatch()} disabled={patchBusy}>Plan LayerNorm insertion</button>
            </div>}
            {structuralRemovalCandidate && <div className="parameter-editor structural-editor">
              <button type="button" onClick={() => void planStructuralRemoval()} disabled={patchBusy}>Plan LayerNorm removal</button>
            </div>}
            {patchResult && <div className="patch-review">
              <div className="node-kind">{patchResult.kind.replace('_', ' ')}</div>
              <pre>{patchResult.candidate_diff}</pre>
              <p>{patchResult.validation.blocking ? 'Validation is blocking; commit is unavailable.' : `Risk: ${patchResult.risk.level}. ${patchResult.risk.reasons.join(' ')}`}</p>
              {patchResult.runtime_validation && <p>Runtime validation: {patchResult.runtime_validation.status} ({patchResult.runtime_validation.trace_id})</p>}
              <div className="inspector-actions">
                <button type="button" onClick={cancelParameterPatch} disabled={patchBusy}>Cancel</button>
                {patchSet && patchResult.kind === 'patch_validated' && <button type="button" onClick={() => void commitParameterPatch()} disabled={patchBusy || patchResult.blocking}>Commit source patch</button>}
              </div>
            </div>}
            {selectedVisual && view === 'publication' && <div className="inspector-actions">
              <button type="button" onClick={() => toggleVisual(selectedVisual.publication_node_id, 'locked')}>{selectedVisual.locked ? <Unlock size={15} /> : <Lock size={15} />}{selectedVisual.locked ? 'Unlock placement' : 'Lock placement'}</button>
              {selected.kind === 'repeat_group' && <button type="button" onClick={() => toggleVisual(selectedVisual.publication_node_id, 'collapsed')}><Maximize2 size={15} />{selectedVisual.collapsed ? 'Expand visual group' : 'Collapse visual group'}</button>}
            </div>}
          </div> : <div className="empty-inspector">Select a semantic module to inspect its source-backed evidence.</div>}
          {!tierModel && <div className="validation-panel"><div><span className={`validation-dot ${snapshot?.validation.status ?? 'unavailable'}`} />Validation</div><p>{snapshot?.validation.message ?? notice}</p><code>source revision {snapshot?.sourceRevision.slice(0, 24) ?? 'unavailable'}</code></div>}
          {!tierModel && <button type="button" className="save-button" onClick={() => snapshot && void persist(snapshot.document)} disabled={!snapshot}><Save size={16} />Save visual document</button>}
        </aside>
      </section>
      <footer className="statusbar"><span>{tierModel ? 'Archived source / read-only diagram' : notice}</span><span>{tierModel ? 'Config and discrepancy review pending' : 'Visual edits never change source bytes'}</span></footer>

      {openProject && isTauri && <div className="dialog-backdrop" role="presentation">
        <form className="open-project-dialog" onSubmit={submitProject}>
          <div><div className="node-kind">Engine session</div><h2>Open approved project</h2></div>
          <label htmlFor="project-id">Project ID</label><input id="project-id" value={projectInput.projectId} pattern="project:[A-Za-z0-9._-]+" onChange={(event) => setProjectInput({ ...projectInput, projectId: event.target.value })} required />
          <label htmlFor="approved-root">Approved root</label><input id="approved-root" value={projectInput.approvedRoot} onChange={(event) => setProjectInput({ ...projectInput, approvedRoot: event.target.value })} placeholder="/absolute/path/to/project" required />
          <label htmlFor="entrypoint">Entrypoint</label><input id="entrypoint" value={projectInput.entrypoint} onChange={(event) => setProjectInput({ ...projectInput, entrypoint: event.target.value })} placeholder="models/model.py:Model" required />
          <label htmlFor="python-executable">Python executable</label><input id="python-executable" value={projectInput.pythonExecutable} onChange={(event) => setProjectInput({ ...projectInput, pythonExecutable: event.target.value })} placeholder="/path/to/python" required />
          <label htmlFor="environment-name">Environment name</label><input id="environment-name" value={projectInput.environmentName ?? ''} onChange={(event) => setProjectInput({ ...projectInput, environmentName: event.target.value || undefined })} placeholder="TFB_py311" />
          <p>Engine validates this approved root and entrypoint. The desktop does not open source files directly.</p>
          <div className="dialog-actions"><button type="button" onClick={() => setOpenProject(false)}>Cancel</button><button type="submit" disabled={opening}>{opening ? 'Opening...' : 'Open and analyze'}</button></div>
        </form>
      </div>}
    </main>
  )
}

export default App
