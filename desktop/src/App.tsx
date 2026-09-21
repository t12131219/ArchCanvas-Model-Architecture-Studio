import { useEffect, useMemo, useState, type FormEvent } from 'react'
import {
  Background,
  Controls,
  MiniMap,
  ReactFlow,
  type Edge,
  type Node,
  type NodeChange,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
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
import { createEngineClient } from './engine/client'
import type { ArchitectureNode, CanvasDocument, DesktopSnapshot, ProjectOpenInput } from './engine/types'

const engine = createEngineClient()
const isTauri = '__TAURI_INTERNALS__' in window

type FlowNodeData = {
  label: string
  kind: ArchitectureNode['kind']
  members: number
  locked: boolean
}

function toFlowNodes(snapshot: DesktopSnapshot, exact: boolean): Node<FlowNodeData>[] {
  if (exact) {
    return snapshot.exactNodes.map((node, index) => ({
      id: node.id,
      position: { x: 42 + index * 188, y: 230 },
      data: { label: node.label, kind: node.kind, members: node.members, locked: true },
      draggable: false,
      className: `architecture-node node-${node.kind} is-locked`,
      style: { width: 154, height: 64 },
    }))
  }
  return snapshot.nodes.map((architectureNode) => {
    const visual = snapshot.document.nodes.find((node) => node.publication_node_id === architectureNode.id)!
    const label = visual.collapsed ? architectureNode.label : `${architectureNode.label} (expanded)`
    return {
      id: architectureNode.id,
      position: { x: visual.x, y: visual.y },
      data: { label, kind: architectureNode.kind, members: architectureNode.members, locked: visual.locked },
      draggable: !visual.locked,
      className: `architecture-node node-${architectureNode.kind}${visual.locked ? ' is-locked' : ''}`,
      style: {
        width: visual.width,
        height: visual.height,
        background: visual.style.fill_color ?? undefined,
        borderColor: visual.style.stroke_color ?? undefined,
        borderTopColor: visual.style.accent_color ?? undefined,
      },
    }
  })
}

function toFlowEdges(snapshot: DesktopSnapshot, exact: boolean): Edge[] {
  return (exact ? snapshot.exactEdges : snapshot.edges).map((edge) => ({
    id: edge.id,
    source: edge.source,
    target: edge.target,
    animated: edge.residual,
    type: 'smoothstep',
  }))
}

function withPosition(document: CanvasDocument, changes: NodeChange[]): CanvasDocument {
  const moved = new Map<string, { x: number; y: number }>()
  for (const change of changes) {
    if (change.type === 'position' && change.position) moved.set(change.id, change.position)
  }
  if (!moved.size) return document
  return {
    ...document,
    layout_mode: 'manual',
    nodes: document.nodes.map((node) => {
      const position = moved.get(node.publication_node_id)
      return position ? { ...node, x: position.x, y: position.y } : node
    }),
  }
}

function layoutDocument(document: CanvasDocument): CanvasDocument {
  return {
    ...document,
    layout_mode: 'automatic',
    nodes: document.nodes.map((node, index) => ({ ...node, x: 64 + index * 242, y: index === 2 ? 188 : 230 })),
  }
}

function downloadSvg(nodes: Node<FlowNodeData>[], edges: Edge[]) {
  const shapes = nodes
    .map((node) => `<rect x="${node.position.x}" y="${node.position.y}" width="180" height="74" rx="6" fill="#f7faf8" stroke="#45665b"/><text x="${node.position.x + 14}" y="${node.position.y + 42}" font-family="sans-serif" font-size="13">${node.data.label}</text>`)
    .join('')
  const paths = edges
    .map((edge) => {
      const source = nodes.find((node) => node.id === edge.source)
      const target = nodes.find((node) => node.id === edge.target)
      if (!source || !target) return ''
      return `<path d="M ${source.position.x + 180} ${source.position.y + 37} L ${target.position.x} ${target.position.y + 37}" stroke="#7f918a" fill="none" marker-end="url(#arrow)"/>`
    })
    .join('')
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="620" viewBox="0 0 1280 620"><defs><marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="3" orient="auto"><path d="M0,0 L0,6 L8,3 z" fill="#7f918a"/></marker></defs>${paths}${shapes}</svg>`
  const url = URL.createObjectURL(new Blob([svg], { type: 'image/svg+xml' }))
  const link = document.createElement('a')
  link.href = url
  link.download = 'archcanvas-publication.svg'
  link.click()
  URL.revokeObjectURL(url)
}

function App() {
  const [snapshot, setSnapshot] = useState<DesktopSnapshot | null>(null)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [history, setHistory] = useState<CanvasDocument[]>([])
  const [historyIndex, setHistoryIndex] = useState(-1)
  const [notice, setNotice] = useState('Loading desktop canvas...')
  const [view, setView] = useState<'publication' | 'exact'>('publication')
  const [openProject, setOpenProject] = useState(false)
  const [opening, setOpening] = useState(false)
  const [projectInput, setProjectInput] = useState<ProjectOpenInput>({
    projectId: 'project:desktop-model', approvedRoot: '', entrypoint: 'model.py:Model',
    pythonExecutable: '', environmentName: 'TFB_py311',
  })

  useEffect(() => {
    engine.load().then((loaded) => {
      setSnapshot(loaded)
      setHistory([loaded.document])
      setHistoryIndex(0)
      setNotice(loaded.validation.message)
    }).catch((error: unknown) => {
      setNotice(error instanceof Error ? error.message : 'Desktop initialization failed.')
      setOpenProject(true)
    })
  }, [])

  const flowNodes = useMemo(() => (snapshot ? toFlowNodes(snapshot, view === 'exact') : []), [snapshot, view])
  const flowEdges = useMemo(() => (snapshot ? toFlowEdges(snapshot, view === 'exact') : []), [snapshot, view])
  const selected = (view === 'exact' ? snapshot?.exactNodes : snapshot?.nodes)?.find((node) => node.id === selectedId) ?? null
  const selectedVisual = snapshot?.document.nodes.find((node) => node.publication_node_id === selectedId) ?? null

  function record(document: CanvasDocument) {
    setSnapshot((current) => (current ? { ...current, document } : current))
    setHistory((current) => [...current.slice(0, historyIndex + 1), document])
    setHistoryIndex((current) => current + 1)
  }

  async function persist(document: CanvasDocument) {
    const outcome = await engine.saveCanvas(document)
    if (outcome.ok) setSnapshot((current) => (current ? { ...current, document: outcome.document } : current))
    setNotice(outcome.message)
  }

  function onNodesChange(changes: NodeChange[]) {
    if (!snapshot) return
    const next = withPosition(snapshot.document, changes)
    if (next === snapshot.document) return
    record(next)
    if (changes.some((change) => change.type === 'position' && change.dragging === false)) void persist(next)
  }

  function restore(document: CanvasDocument, index: number) {
    setHistoryIndex(index)
    setSnapshot((current) => (current ? { ...current, document } : current))
    void persist(document)
  }

  function resetLayout() {
    if (!snapshot) return
    const next = layoutDocument(snapshot.document)
    record(next)
    void persist(next)
  }

  function toggleSelected(field: 'locked' | 'collapsed') {
    if (!snapshot || !selectedVisual) return
    const next = {
      ...snapshot.document,
      layout_mode: 'manual' as const,
      nodes: snapshot.document.nodes.map((node) => node.publication_node_id === selectedVisual.publication_node_id ? { ...node, [field]: !node[field] } : node),
    }
    record(next)
    void persist(next)
  }

  function submitProject(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setOpening(true)
    engine.openProject(projectInput).then((loaded) => {
      setSnapshot(loaded)
      setHistory([loaded.document])
      setHistoryIndex(0)
      setNotice(loaded.validation.message)
      setOpenProject(false)
    }).catch((error: unknown) => setNotice(error instanceof Error ? error.message : 'Project open failed.')).finally(() => setOpening(false))
  }

  return (
    <main className="studio-shell">
      <header className="topbar">
        <div className="brand"><span className="brand-mark">AC</span><span>ArchCanvas</span><small>Model Architecture Studio</small></div>
        <div className="project-identity"><FileCode2 size={16} /><span>{snapshot?.projectName ?? 'Opening project'}</span><code>{snapshot?.sourceLabel}</code></div>
        <div className="top-actions">
          {isTauri && <button type="button" className="open-button" onClick={() => setOpenProject(true)}>Open project</button>}
          <button type="button" className="icon-button" title="Undo visual edit" onClick={() => historyIndex > 0 && restore(history[historyIndex - 1], historyIndex - 1)} disabled={historyIndex <= 0}><ArrowLeft size={17} /></button>
          <button type="button" className="icon-button" title="Redo visual edit" onClick={() => historyIndex < history.length - 1 && restore(history[historyIndex + 1], historyIndex + 1)} disabled={historyIndex >= history.length - 1}><ArrowRight size={17} /></button>
          <button type="button" className="icon-button" title="Reset automatic layout" onClick={resetLayout}><RotateCcw size={17} /></button>
          <button type="button" className="icon-button" title="Export publication SVG" onClick={() => downloadSvg(flowNodes, flowEdges)}><Download size={17} /></button>
        </div>
      </header>
      <section className="workspace">
        <aside className="left-panel">
          <div className="panel-heading"><span>Project</span><span className="mode-chip">{snapshot?.mode === 'fixture-read-only' ? 'READ-ONLY FIXTURE' : 'ENGINE'}</span></div>
          <div className="project-row"><span className="status-dot" /> <span>{snapshot?.projectId ?? 'Waiting for client'}</span></div>
          <div className="section-label">Views</div>
          <div className="view-list">
            <button type="button" className={view === 'publication' ? 'active' : ''} onClick={() => { setView('publication'); setSelectedId(null) }}><Play size={15} />Publication</button>
            <button type="button" className={view === 'exact' ? 'active' : ''} onClick={() => { setView('exact'); setSelectedId(null) }}><Move size={15} />Exact Architecture</button>
          </div>
          <div className="section-label">Canvas document</div>
          <dl className="metadata"><dt>Layout</dt><dd>{snapshot?.document.layout_mode ?? '...'}</dd><dt>Revision</dt><dd className="revision">{snapshot?.sourceRevision.slice(0, 19) ?? '...'}</dd></dl>
        </aside>
        <section className="canvas-stage" aria-label="Architecture canvas">
          <div className="canvas-toolbar"><span>{view === 'publication' ? 'Publication canvas' : 'Exact architecture canvas'}</span><span>Visual edits only</span></div>
          <ReactFlow nodes={flowNodes} edges={flowEdges} fitView nodesDraggable={view === 'publication'} nodesConnectable={false} elementsSelectable onNodesChange={view === 'publication' ? onNodesChange : undefined} onNodeClick={(_, node) => setSelectedId(node.id)}>
            <Background gap={20} size={1} color="#d7dfdb" /><Controls showInteractive={false} /><MiniMap zoomable pannable nodeColor="#6f9c83" />
          </ReactFlow>
        </section>
        <aside className="right-panel">
          <div className="panel-heading"><span>Inspector</span><PanelRight size={16} /></div>
          {selected ? <div className="inspector-content">
            <div className="node-kind">{selected.kind.replace('_', ' ')}</div><h1>{selected.label}</h1>
            <dl className="metadata"><dt>Members</dt><dd>{selected.members}</dd><dt>Anchor</dt><dd>{selected.anchor}</dd>{selectedVisual && <><dt>Position</dt><dd>{Math.round(selectedVisual.x)}, {Math.round(selectedVisual.y)}</dd></>}</dl>
            <button type="button" className="source-link" onClick={() => void engine.requestSourceJump(selected.anchorId, selected.anchor).then(setNotice)}><FileCode2 size={15} />Request source jump</button>
            {selectedVisual && <div className="inspector-actions">
              <button type="button" onClick={() => toggleSelected('locked')}>{selectedVisual.locked ? <Unlock size={15} /> : <Lock size={15} />}{selectedVisual.locked ? 'Unlock placement' : 'Lock placement'}</button>
              {selected.kind === 'repeat_group' && <button type="button" onClick={() => toggleSelected('collapsed')}><Maximize2 size={15} />{selectedVisual.collapsed ? 'Expand visual group' : 'Collapse visual group'}</button>}
            </div>}
          </div> : <div className="empty-inspector">Select a canvas node to inspect its source-backed publication mapping.</div>}
          <div className="validation-panel"><div><span className={`validation-dot ${snapshot?.validation.status ?? 'unavailable'}`} />Validation</div><p>{snapshot?.validation.message ?? notice}</p><code>source revision {snapshot?.sourceRevision.slice(0, 24) ?? 'unavailable'}</code></div>
          <button type="button" className="save-button" onClick={() => snapshot && void persist(snapshot.document)} disabled={!snapshot}><Save size={16} />Save visual document</button>
        </aside>
      </section>
      <footer className="statusbar"><span>{notice}</span><span>CanvasDocument has no source-write authority</span></footer>
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
