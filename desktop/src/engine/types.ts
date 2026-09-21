export type CanvasLayoutMode = 'automatic' | 'manual'

export type CanvasNodeStyle = {
  fill_color?: string | null
  stroke_color?: string | null
  accent_color?: string | null
}

export type CanvasNodeState = {
  publication_node_id: string
  x: number
  y: number
  width: number
  height: number
  style: CanvasNodeStyle
  collapsed: boolean
  locked: boolean
}

export type CanvasAnnotation = {
  annotation_id: string
  target_node_id: string
  text: string
}

export type CanvasDocument = {
  schema_version: '1.0'
  canvas_document_id: string
  project_id: string
  publication_id: string
  base_source_revision: string
  layout_mode: CanvasLayoutMode
  viewport: { x: number; y: number; zoom: number }
  nodes: CanvasNodeState[]
  annotations: CanvasAnnotation[]
}

export type ArchitectureNode = {
  id: string
  label: string
  kind: string
  anchor: string
  anchorId?: string
  members: number
}

export type ArchitectureEdge = { id: string; source: string; target: string; residual?: boolean }

export type DesktopSnapshot = {
  mode: 'fixture-read-only' | 'engine'
  projectName: string
  projectId: string
  publicationId: string
  sourceRevision: string
  sourceLabel: string
  nodes: ArchitectureNode[]
  edges: ArchitectureEdge[]
  exactNodes: ArchitectureNode[]
  exactEdges: ArchitectureEdge[]
  document: CanvasDocument
  validation: { status: 'ready' | 'stale' | 'unavailable'; message: string }
}

export type SaveOutcome =
  | { ok: true; document: CanvasDocument; message: string }
  | { ok: false; code: string; message: string }

export type ProjectOpenInput = {
  projectId: string
  approvedRoot: string
  entrypoint: string
  pythonExecutable: string
  environmentName?: string
}

export interface EngineClient {
  load(): Promise<DesktopSnapshot>
  openProject(input: ProjectOpenInput): Promise<DesktopSnapshot>
  saveCanvas(document: CanvasDocument): Promise<SaveOutcome>
  requestSourceJump(anchorId: string | undefined, label: string): Promise<string>
}
