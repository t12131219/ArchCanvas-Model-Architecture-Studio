import { invoke } from '@tauri-apps/api/core'

import type {
  ArchitectureEdge,
  ArchitectureNode,
  CanvasDocument,
  DesktopSnapshot,
  EngineClient,
  ProjectOpenInput,
  SaveOutcome,
} from './types'

const STORAGE_KEY = 'archcanvas.stage6.fixture.canvas.v1'
const ENGINE_PROJECT_KEY = 'archcanvas.stage6.engine.project-id'
const sourceRevision = 'sha256:6ce0700eab3c7fa3ed84cb6b65ee2a1fbe91b9cf42a65f7c1dcba4cff30f8e78'
const projectId = 'project:transformer-fixture'
const publicationId = 'publication:transformer-fixture'

const fixtureNodes: ArchitectureNode[] = [
  { id: 'publication-node:input', label: 'Input sequence', kind: 'input', anchor: 'model.py:18', members: 1 },
  { id: 'publication-node:embedding', label: 'Token embedding', kind: 'module', anchor: 'model.py:30', members: 1 },
  { id: 'publication-node:transformer-encoder', label: 'Transformer encoder x 6', kind: 'repeat_group', anchor: 'model.py:42', members: 6 },
  { id: 'publication-node:head', label: 'Prediction head', kind: 'module', anchor: 'model.py:58', members: 1 },
  { id: 'publication-node:output', label: 'Logits', kind: 'output', anchor: 'model.py:64', members: 1 },
]

const fixtureEdges: ArchitectureEdge[] = fixtureNodes.slice(1).map((node, index) => ({
  id: `publication-edge:${index}`,
  source: fixtureNodes[index].id,
  target: node.id,
}))

const exactNodes: ArchitectureNode[] = [
  { id: 'exact-node:input', label: 'input_ids', kind: 'input', anchor: 'model.py:18', members: 1 },
  { id: 'exact-node:embedding', label: 'self.embedding', kind: 'module', anchor: 'model.py:30', members: 1 },
  ...Array.from({ length: 6 }, (_, index) => ({
    id: `exact-node:encoder-${index}`, label: `self.encoder.layers.${index}`, kind: 'module' as const,
    anchor: 'model.py:42', members: 1,
  })),
  { id: 'exact-node:head', label: 'self.head', kind: 'module', anchor: 'model.py:58', members: 1 },
  { id: 'exact-node:output', label: 'logits', kind: 'output', anchor: 'model.py:64', members: 1 },
]

const exactEdges: ArchitectureEdge[] = exactNodes.slice(1).map((node, index) => ({
  id: `exact-edge:${index}`,
  source: exactNodes[index].id,
  target: node.id,
}))

function defaultDocument(): CanvasDocument {
  return {
    schema_version: '1.0', canvas_document_id: 'canvas-document:transformer-fixture-default',
    project_id: projectId, publication_id: publicationId, base_source_revision: sourceRevision,
    layout_mode: 'automatic', viewport: { x: 0, y: 0, zoom: 1 },
    nodes: fixtureNodes.map((node, index) => ({
      publication_node_id: node.id, x: 64 + index * 242, y: node.kind === 'repeat_group' ? 188 : 230,
      width: node.kind === 'repeat_group' ? 230 : 180, height: 74, style: {},
      collapsed: node.kind === 'repeat_group', locked: node.kind === 'input' || node.kind === 'output',
    })),
    annotations: [{ annotation_id: 'canvas-annotation:transformer-repeat', target_node_id: 'publication-node:transformer-encoder', text: 'Repeated encoder block, sourced from the publication reduction.' }],
  }
}

function fixtureSnapshot(document: CanvasDocument): DesktopSnapshot {
  return {
    mode: 'fixture-read-only', projectName: 'Transformer publication fixture', projectId, publicationId,
    sourceRevision, sourceLabel: 'fixtures/transformer_static_v1/source/model.py', nodes: fixtureNodes,
    edges: fixtureEdges, exactNodes, exactEdges, document,
    validation: { status: 'ready', message: 'Read-only fixture. Visual state is isolated from source bytes.' },
  }
}

class ReadOnlyFixtureClient implements EngineClient {
  async load(): Promise<DesktopSnapshot> {
    const stored = window.localStorage.getItem(STORAGE_KEY)
    if (!stored) return fixtureSnapshot(defaultDocument())
    try { return fixtureSnapshot(JSON.parse(stored) as CanvasDocument) }
    catch { window.localStorage.removeItem(STORAGE_KEY); return fixtureSnapshot(defaultDocument()) }
  }

  async saveCanvas(document: CanvasDocument): Promise<SaveOutcome> {
    if (document.base_source_revision !== sourceRevision) return { ok: false, code: 'CANVAS_DOCUMENT_STALE', message: 'Fixture revision changed.' }
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(document))
    return { ok: true, document, message: 'Fixture visual state saved locally; source remains read-only.' }
  }

  async openProject(_input: ProjectOpenInput): Promise<DesktopSnapshot> {
    return fixtureSnapshot(defaultDocument())
  }

  async requestSourceJump(_anchorId: string | undefined, label: string): Promise<string> {
    return `Source jump requested for ${label}. Fixture mode never opens or writes source files.`
  }
}

type RpcResponse = {
  status: 'succeeded' | 'rejected' | 'failed'
  result?: Record<string, unknown>
  error?: { code: string; message: string }
}

type EngineAnalysis = {
  kind: 'analysis_completed' | 'analysis_loaded'
  manifest: { project_id: string; source_revision: string; entrypoint: string }
  source: { anchors: Array<{ anchor_id: string; relative_file: string; span: { start: { line: number } } }> }
  architecture: {
    nodes: Array<{ node_id: string; display_name: string; kind: string; op_type: string; source_anchor_ids: string[] }>
    edges: Array<{ edge_id: string; source_node_id: string; target_node_id: string; kind: string }>
  }
  publication: {
    publication_id: string
    nodes: Array<{ node_id: string; label: string; kind: string; member_node_ids: string[]; collapsed: boolean }>
    edges: Array<{ edge_id: string; source_node_id: string; target_node_id: string; kind: string }>
  }
  scene: { nodes: Array<{ publication_node_id: string; x: number; y: number; width: number; height: number }> }
}

function requestId(prefix: string) {
  return `engine-request:${prefix}-${Date.now()}`
}

function anchorLabels(analysis: EngineAnalysis) {
  return new Map(analysis.source.anchors.map((anchor) => [anchor.anchor_id, `${anchor.relative_file}:${anchor.span.start.line}`]))
}

function defaultEngineDocument(analysis: EngineAnalysis): CanvasDocument {
  const sceneByPublicationId = new Map(analysis.scene.nodes.map((node) => [node.publication_node_id, node]))
  return {
    schema_version: '1.0',
    canvas_document_id: `canvas-document:${analysis.manifest.project_id.replace('project:', '')}-default`,
    project_id: analysis.manifest.project_id,
    publication_id: analysis.publication.publication_id,
    base_source_revision: analysis.manifest.source_revision,
    layout_mode: 'automatic', viewport: { x: 0, y: 0, zoom: 1 },
    nodes: analysis.publication.nodes.map((node, index) => {
      const scene = sceneByPublicationId.get(node.node_id)
      return {
        publication_node_id: node.node_id,
        x: scene?.x ?? 64 + index * 220, y: scene?.y ?? 180,
        width: scene?.width ?? 180, height: scene?.height ?? 72, style: {},
        collapsed: node.collapsed, locked: node.kind === 'input' || node.kind === 'output',
      }
    }),
    annotations: [],
  }
}

function snapshotFromAnalysis(analysis: EngineAnalysis, document?: CanvasDocument): DesktopSnapshot {
  const anchors = anchorLabels(analysis)
  const architectureById = new Map(analysis.architecture.nodes.map((node) => [node.node_id, node]))
  const publicationNodes = analysis.publication.nodes.map((node) => {
    const member = architectureById.get(node.member_node_ids[0])
    const anchorId = member?.source_anchor_ids[0]
    return {
      id: node.node_id, label: node.label, kind: node.kind,
      anchor: member?.source_anchor_ids.map((anchor) => anchors.get(anchor)).find(Boolean) ?? 'unresolved source anchor', anchorId,
      members: node.member_node_ids.length,
    }
  })
  return {
    mode: 'engine', projectName: analysis.manifest.entrypoint, projectId: analysis.manifest.project_id,
    publicationId: analysis.publication.publication_id, sourceRevision: analysis.manifest.source_revision,
    sourceLabel: analysis.manifest.entrypoint, nodes: publicationNodes,
    edges: analysis.publication.edges.map((edge) => ({ id: edge.edge_id, source: edge.source_node_id, target: edge.target_node_id, residual: edge.kind === 'residual' })),
    exactNodes: analysis.architecture.nodes.map((node) => ({
      id: node.node_id, label: node.display_name, kind: node.kind,
      anchor: node.source_anchor_ids.map((anchor) => anchors.get(anchor)).find(Boolean) ?? 'unresolved source anchor', anchorId: node.source_anchor_ids[0], members: 1,
    })),
    exactEdges: analysis.architecture.edges.map((edge) => ({ id: edge.edge_id, source: edge.source_node_id, target: edge.target_node_id, residual: edge.kind === 'residual' })),
    document: document ?? defaultEngineDocument(analysis),
    validation: { status: 'ready', message: 'Engine-backed analysis loaded. Visual saves re-check the source revision.' },
  }
}

class TauriEngineClient implements EngineClient {
  private async rpc(command: Record<string, unknown>, prefix: string): Promise<RpcResponse> {
    return invoke<RpcResponse>('engine_rpc', { request: { schema_version: '1.0', request_id: requestId(prefix), command } })
  }

  private async analysis(projectId: string): Promise<EngineAnalysis> {
    const response = await this.rpc({ operation: 'load_analysis', project_id: projectId }, 'load-analysis')
    if (response.status !== 'succeeded' || !response.result) throw new Error(response.error?.message ?? 'Engine analysis is unavailable.')
    return response.result as unknown as EngineAnalysis
  }

  async load(): Promise<DesktopSnapshot> {
    const projectId = window.localStorage.getItem(ENGINE_PROJECT_KEY)
    if (!projectId) throw new Error('Open an Engine-approved project to begin.')
    const analysis = await this.analysis(projectId)
    const replay = await this.rpc({ operation: 'replay_canvas_documents', project_id: projectId }, 'replay-canvas')
    const documents = replay.status === 'succeeded' ? (replay.result?.canvas_documents as CanvasDocument[] | undefined) : undefined
    return snapshotFromAnalysis(analysis, documents?.find((document) => document.publication_id === analysis.publication.publication_id))
  }

  async openProject(input: ProjectOpenInput): Promise<DesktopSnapshot> {
    const opened = await this.rpc({
      operation: 'open_project', project_id: input.projectId, approved_root: input.approvedRoot,
      entrypoint: input.entrypoint,
      environment: { python_executable: input.pythonExecutable, environment_name: input.environmentName ?? null },
    }, 'open-project')
    if (opened.status !== 'succeeded') throw new Error(opened.error?.message ?? 'Engine rejected the project.')
    const analyzed = await this.rpc({ operation: 'analyze_project', project_id: input.projectId }, 'analyze-project')
    if (analyzed.status !== 'succeeded' || !analyzed.result) throw new Error(analyzed.error?.message ?? 'Engine analysis failed.')
    window.localStorage.setItem(ENGINE_PROJECT_KEY, input.projectId)
    const analysis = analyzed.result as unknown as EngineAnalysis
    const replay = await this.rpc({ operation: 'replay_canvas_documents', project_id: input.projectId }, 'replay-canvas')
    const documents = replay.status === 'succeeded' ? (replay.result?.canvas_documents as CanvasDocument[] | undefined) : undefined
    return snapshotFromAnalysis(analysis, documents?.find((document) => document.publication_id === analysis.publication.publication_id))
  }

  async saveCanvas(document: CanvasDocument): Promise<SaveOutcome> {
    const response = await this.rpc({ operation: 'save_canvas_document', canvas_document: document }, 'canvas')
    if (response.status !== 'succeeded') return { ok: false, code: response.error?.code ?? 'ENGINE_RPC_FAILED', message: response.error?.message ?? 'The Engine rejected the visual document.' }
    const saved = (response.result?.canvas_documents as CanvasDocument[] | undefined)?.[0]
    return saved ? { ok: true, document: saved, message: 'Visual state saved by Engine RPC.' } : { ok: false, code: 'ENGINE_RPC_INVALID_RESPONSE', message: 'Engine returned no CanvasDocument.' }
  }

  async requestSourceJump(anchorId: string | undefined, label: string): Promise<string> {
    if (!anchorId) return `No Engine-backed source anchor is available for ${label}.`
    const response = await this.rpc({ operation: 'resolve_source_anchor', project_id: window.localStorage.getItem(ENGINE_PROJECT_KEY), anchor_id: anchorId }, 'source-jump')
    if (response.status !== 'succeeded' || !response.result) return response.error?.message ?? 'Engine could not resolve the source location.'
    const location = response.result as { relative_file: string; line: number; column: number }
    return `Engine resolved ${location.relative_file}:${location.line}:${location.column}.`
  }
}

export function createEngineClient(): EngineClient {
  return '__TAURI_INTERNALS__' in window ? new TauriEngineClient() : new ReadOnlyFixtureClient()
}
