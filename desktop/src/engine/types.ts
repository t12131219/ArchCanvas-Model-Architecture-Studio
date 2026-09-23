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
  sourceNodeId?: string
  label: string
  kind: string
  opType?: string
  anchor: string
  anchorId?: string
  sourceAnchorIds?: string[]
  members: number
  parameters?: Array<{
    name: string
    value: unknown
    sourceName?: string | null
    origin: string
    anchorId?: string
  }>
}

export type ArchitectureEdge = {
  id: string
  source: string
  target: string
  residual?: boolean
  evidenceAnchorIds?: string[]
}

export type ScientificMiniature = {
  id: string
  targetId: string
  kind: 'tensor_strip' | 'signal_preview' | 'distribution_preview' | 'equation_note' | 'inset_callout'
  evidenceKind: 'static_tensor_spec' | 'runtime_summary' | 'deterministic_schematic' | 'publication_annotation'
  disclosure: 'evidence' | 'illustrative'
  label: string
}

export type DesktopSnapshot = {
  mode: 'fixture-read-only' | 'engine'
  projectName: string
  projectId: string
  publicationId: string
  sourceRevision: string
  sourceLabel: string
  patchableParameters: string[]
  structuralPatchOperations: Array<'insert_layer_norm' | 'remove_layer_norm'>
  sourceAnchors: Record<string, { relativeFile: string; fileRevision: string; contentFingerprint: string }>
  nodes: ArchitectureNode[]
  edges: ArchitectureEdge[]
  miniatures: ScientificMiniature[]
  exactNodes: ArchitectureNode[]
  exactEdges: ArchitectureEdge[]
  document: CanvasDocument
  validation: { status: 'ready' | 'stale' | 'unavailable'; message: string }
}

export type SaveOutcome =
  | { ok: true; document: CanvasDocument; message: string }
  | { ok: false; code: string; message: string }

export type PatchSet = Record<string, unknown>

export type PatchResult = {
  kind: 'patch_planned' | 'patch_validated' | 'patch_committed'
  project_id: string
  patch_set_id: string
  patch_id: string
  candidate_diff: string
  before_source_revision: string
  after_source_revision: string
  observed_delta: Record<string, unknown>
  validation: { blocking: boolean; issues: Array<Record<string, unknown>> }
  provenance: Record<string, unknown>
  risk: { level: 'low' | 'medium' | 'high'; reasons: string[] }
  blocking: boolean
  confirmation_id?: string | null
  runtime_validation?: { status: string; message?: string | null; trace_id: string } | null
  analysis?: Record<string, unknown> | null
}

export type PatchOutcome =
  | { ok: true; result: PatchResult; message: string }
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
  planPatch(projectId: string, patchSet: PatchSet): Promise<PatchOutcome>
  validatePatch(projectId: string, patchSet: PatchSet): Promise<PatchOutcome>
  commitPatch(projectId: string, patchSet: PatchSet, confirmationId: string): Promise<PatchOutcome>
  requestSourceJump(anchorId: string | undefined, label: string): Promise<string>
}
