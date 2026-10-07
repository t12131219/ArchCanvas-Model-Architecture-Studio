export type Glyph = 'module' | 'operator' | 'tensor' | 'add' | 'attention' | 'norm' | 'opaque';
export type EdgeRole = 'data' | 'residual' | 'memory' | 'mask';

export interface ArchitecturePort {
  id: string;
  name: string;
  direction: 'in' | 'out';
  role: string;
  ordinal: number;
}
export type OutputPathSegment = { kind: 'index'; index: number } | { kind: 'key'; key: string | number | boolean | null };
export interface ArchitectureNode {
  id: string;
  label: string;
  kind: string;
  category: string;
  parentId?: string;
  children: string[];
  ports: ArchitecturePort[];
  parameters: Record<string, unknown>;
  parameterOrigins?: Record<string, ParameterOrigin>;
  source?: { path: string; line: number; endLine: number; expression: string };
  evidence: 'source' | 'contract' | 'opaque';
  repeat?: { count: number; sharing: 'independent' | 'shared' };
  instanceId?: string;
  callId?: string;
  /** An authored fixed return-container slot; [] denotes the whole return value. */
  outputPath?: OutputPathSegment[];
}
/** Source facts remain separate from visual aliases and detail boundary objects. */
export interface SourceNodeFact {
  id: string; sourceLabel: string; kind: string; category: string; evidence: ArchitectureNode['evidence'];
  instanceId?: string; callId?: string; callCount?: number;
  repeat?: ArchitectureNode['repeat']; outputPath?: OutputPathSegment[]; source?: ArchitectureNode['source'];
}
export interface ParameterOrigin {
  kind: 'literal' | 'constructor_argument' | 'derived' | 'unknown';
  path: string; line: number; endLine: number; column: number; endColumn: number; expression: string;
}
export interface ArchitectureEdge {
  id: string;
  source: { nodeId: string; portId: string };
  target: { nodeId: string; portId: string };
  tensorId: string;
  role: EdgeRole;
  label?: string;
}
export interface Architecture {
  schemaVersion: 1;
  id: string;
  label: string;
  sourceDigest: string;
  irDigest: string;
  entry: string;
  nodes: ArchitectureNode[];
  edges: ArchitectureEdge[];
  diagnostics: { level: string; message: string }[];
  sources: { path: string; content: string; digest: string }[];
}
export interface Position { x: number; y: number; width?: number; height?: number }
export interface NodeStyle { fill?: string; stroke?: string; glyph?: Glyph }
export interface EdgeStyle { stroke?: string; width?: number; dashed?: boolean }
export interface LegendItem { id: string; label: string; color: string; glyph: Glyph }
export interface Annotation { id: string; text: string; x: number; y: number; width?: number; height?: number }
export interface PageSpec { widthMm: number; background: string; preset: 'paper' | 'monochrome' }
export interface CanvasDocument {
  schemaVersion: 1;
  id: string;
  title: string;
  revision: number;
  sourceBindingDigest: string;
  architecture: Architecture;
  displayAliases: Record<string, string>;
  nodeStyleOverrides: Record<string, NodeStyle>;
  edgeStyleOverrides: Record<string, EdgeStyle>;
  legendItems: LegendItem[];
  annotations: Annotation[];
  pageSpec: PageSpec;
  expandedIds: string[];
  layout: Record<string, Position>;
  layoutByFrontier: Record<string, Record<string, Position>>;
  pinnedObjects: string[];
}
export type VisualOperation =
  | { type: 'alias'; id: string; label: string }
  | { type: 'nodeStyle'; id: string; style: NodeStyle }
  | { type: 'edgeStyle'; id: string; style: EdgeStyle }
  | { type: 'move'; ids: string[]; dx: number; dy: number }
  | { type: 'expand'; id: string; expanded: boolean }
  | { type: 'legend'; items: LegendItem[] }
  | { type: 'annotation'; annotation: Annotation }
  | { type: 'removeAnnotation'; id: string }
  | { type: 'page'; page: Partial<PageSpec> }
  | { type: 'pin'; ids: string[]; pinned: boolean };

export interface Bounds { x: number; y: number; width: number; height: number }
export interface ScenePort {
  id: string;
  canonicalNodeId: string;
  canonicalPortId: string;
  canonicalBindings: { nodeId: string; portId: string }[];
  canonicalEdgeIds: string[];
  direction: 'in' | 'out';
  role: string;
  name: string;
  x: number;
  y: number;
  proxy: boolean;
}
export interface SceneNode extends Bounds {
  id: string;
  /** Detail boundary objects retain the external canonical source identity. */
  canonicalNodeId?: string;
  boundary?: boolean;
  localX: number;
  localY: number;
  parentId?: string;
  label: string;
  subtitle: string;
  headerHeight: number;
  kind: string;
  category: string;
  fill: string;
  stroke: string;
  glyph: Glyph;
  expanded: boolean;
  expandable: boolean;
  pinned: boolean;
  evidence: ArchitectureNode['evidence'];
  repeat?: ArchitectureNode['repeat'];
  sourceFact?: SourceNodeFact;
  ports: ScenePort[];
}
export interface SceneEdge {
  id: string;
  sourceId: string;
  targetId: string;
  source: ArchitectureEdge['source'];
  target: ArchitectureEdge['target'];
  canonicalEdgeIds: string[];
  tensorId: string;
  role: EdgeRole;
  path: string;
  stroke: string;
  width: number;
  dashed: boolean;
  /** Derived monochrome pattern; older scenes retain the boolean grammar. */
  dashPattern?: number[];
  label: string;
  labelX: number;
  labelY: number;
}
/** Presentation conflicts are separate from canonical source diagnostics. */
export interface SceneDiagnostic {
  level: string;
  message: string;
  code?: 'layout-overlap' | 'layout-header-overlap' | 'layout-route-blocked' | 'layout-outside-parent';
  objectIds?: string[];
  edgeId?: string;
}
/** Actual visible edge variants, separate from editable node glyph legends. */
export interface SceneEdgeLegend extends Bounds {
  id: string;
  role: EdgeRole;
  label: string;
  stroke: string;
  lineWidth: number;
  dashed: boolean;
  dashPattern?: number[];
  sampleLength: number;
  sceneEdgeIds: string[];
  canonicalEdgeIds: string[];
}
export interface EdgeLegendLayout { x: number; y: number; availableWidth: number }
export interface Scene {
  version: '1.0';
  documentId: string;
  revision: number;
  title: string;
  bounds: Bounds;
  nodes: SceneNode[];
  edges: SceneEdge[];
  hiddenEdges: string[];
  legend: (LegendItem & { x: number; y: number })[];
  edgeLegend?: SceneEdgeLegend[];
  edgeLegendLayout?: EdgeLegendLayout;
  annotations: (Annotation & { width: number; height: number })[];
  pageSpec: PageSpec;
  sourceDigest: string;
  irDigest: string;
  diagnostics: SceneDiagnostic[];
  /** Whole source architecture, including canonical facts hidden by the frontier. */
  sourceFacts: SourceNodeFact[];
  exportScope?: DetailExportScope;
}
export interface DetailExportScope {
  kind: 'detail';
  selectedNodeId: string;
  selectedLabel: string;
  sourceDocumentTitle: string;
  canonicalNodeIds: string[];
  internalEdgeIds: string[];
  hiddenInternalEdgeIds: string[];
  boundaryEdges: { edgeId: string; direction: 'in' | 'out'; source: ArchitectureEdge['source']; target: ArchitectureEdge['target']; tensorId: string; role: EdgeRole }[];
  omittedEdgeIds: string[];
  includedAnnotationIds: string[];
  omittedAnnotationIds: string[];
}
export interface ExportSceneOptions { nodeId?: string; widthMm?: number }
export interface HistoryState { document: CanvasDocument; past: CanvasDocument[]; future: CanvasDocument[] }
export type HistoryAction = { type: 'apply'; operations: VisualOperation[]; baseRevision?: number } | { type: 'undo' } | { type: 'redo' };
