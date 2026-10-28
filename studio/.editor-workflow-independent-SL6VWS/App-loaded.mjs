import { jsx as _jsx, jsxs as _jsxs, Fragment as _Fragment } from "react/jsx-runtime";
import { rememberPreviewSave, matchesPreviewSave } from 'file:///home/fzg/PycharmProjects/ArchCanvas/ArchCanvas_Model_Architecture_Studio/studio/src/previewSaveState.ts';
import { SourceImportDialog } from 'file:///home/fzg/PycharmProjects/ArchCanvas/ArchCanvas_Model_Architecture_Studio/studio/.editor-workflow-independent-SL6VWS/SourceImportDialog.mjs';
import { SummaryViewPanel } from 'file:///home/fzg/PycharmProjects/ArchCanvas/ArchCanvas_Model_Architecture_Studio/studio/.editor-workflow-independent-SL6VWS/SummaryViewPanel.mjs';
import { SummaryAuthoringPanel } from 'file:///home/fzg/PycharmProjects/ArchCanvas/ArchCanvas_Model_Architecture_Studio/studio/.editor-workflow-independent-SL6VWS/SummaryAuthoringPanel.mjs';
import { SummarySemanticPanel } from 'file:///home/fzg/PycharmProjects/ArchCanvas/ArchCanvas_Model_Architecture_Studio/studio/.editor-workflow-independent-SL6VWS/SummarySemanticPanel.mjs';
import { SummaryCatalogPanel } from 'file:///home/fzg/PycharmProjects/ArchCanvas/ArchCanvas_Model_Architecture_Studio/studio/.editor-workflow-independent-SL6VWS/SummaryCatalogPanel.mjs';
import { loadSummaryCatalogModel } from 'file:///home/fzg/PycharmProjects/ArchCanvas/ArchCanvas_Model_Architecture_Studio/studio/src/summaryCatalog.ts';
import { useWorkspaceMenus } from 'file:///home/fzg/PycharmProjects/ArchCanvas/ArchCanvas_Model_Architecture_Studio/studio/.editor-workflow-independent-SL6VWS/WorkspaceUI.mjs';
import { sameSourceSemantics, sourcePresentationOperations } from 'file:///home/fzg/PycharmProjects/ArchCanvas/ArchCanvas_Model_Architecture_Studio/studio/src/sourcePresentation.ts';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { buildScene, createDocument, createHistory, reconcileDocument, reduceHistory, validateArchitecture } from 'file:///home/fzg/PycharmProjects/ArchCanvas/ArchCanvas_Model_Architecture_Studio/studio/src/core/index.ts';
import { api } from 'file:///home/fzg/PycharmProjects/ArchCanvas/ArchCanvas_Model_Architecture_Studio/studio/src/api.ts';
import { Icon } from 'file:///home/fzg/PycharmProjects/ArchCanvas/ArchCanvas_Model_Architecture_Studio/studio/.editor-workflow-independent-SL6VWS/icons.mjs';
import { ParameterEditor } from 'file:///home/fzg/PycharmProjects/ArchCanvas/ArchCanvas_Model_Architecture_Studio/studio/.editor-workflow-independent-SL6VWS/ParameterEditor.mjs';
import { ActivationEditor } from 'file:///home/fzg/PycharmProjects/ArchCanvas/ArchCanvas_Model_Architecture_Studio/studio/.editor-workflow-independent-SL6VWS/ActivationEditor.mjs';
import { ConnectionEditor } from 'file:///home/fzg/PycharmProjects/ArchCanvas/ArchCanvas_Model_Architecture_Studio/studio/.editor-workflow-independent-SL6VWS/ConnectionEditor.mjs';
import { RuntimeProfileDialog } from 'file:///home/fzg/PycharmProjects/ArchCanvas/ArchCanvas_Model_Architecture_Studio/studio/.editor-workflow-independent-SL6VWS/RuntimeProfileDialog.mjs';
import { ReviewDialog } from 'file:///home/fzg/PycharmProjects/ArchCanvas/ArchCanvas_Model_Architecture_Studio/studio/.editor-workflow-independent-SL6VWS/ReviewDialog.mjs';
import { ExportDialog } from 'file:///home/fzg/PycharmProjects/ArchCanvas/ArchCanvas_Model_Architecture_Studio/studio/.editor-workflow-independent-SL6VWS/ExportDialog.mjs';
import { ObjectFacts } from 'file:///home/fzg/PycharmProjects/ArchCanvas/ArchCanvas_Model_Architecture_Studio/studio/.editor-workflow-independent-SL6VWS/ObjectFacts.mjs';
import { HierarchyTree } from 'file:///home/fzg/PycharmProjects/ArchCanvas/ArchCanvas_Model_Architecture_Studio/studio/.editor-workflow-independent-SL6VWS/HierarchyTree.mjs';
import { previewFrontier, previewHierarchy, previewHierarchyExpansion } from 'file:///home/fzg/PycharmProjects/ArchCanvas/ArchCanvas_Model_Architecture_Studio/studio/src/previewHierarchy.ts';
import { studioTelemetry } from 'file:///home/fzg/PycharmProjects/ArchCanvas/ArchCanvas_Model_Architecture_Studio/studio/src/perf.ts';
import { cameraViewportSize } from 'file:///home/fzg/PycharmProjects/ArchCanvas/ArchCanvas_Model_Architecture_Studio/studio/src/cameraViewport.ts';
import { edgePatternLabel } from 'file:///home/fzg/PycharmProjects/ArchCanvas/ArchCanvas_Model_Architecture_Studio/studio/src/core/edgePresentation.ts';
import { parseMoveCommand } from 'file:///home/fzg/PycharmProjects/ArchCanvas/ArchCanvas_Model_Architecture_Studio/studio/src/moveCommand.ts';
import { AuthoringStudio } from 'file:///home/fzg/PycharmProjects/ArchCanvas/ArchCanvas_Model_Architecture_Studio/studio/.editor-workflow-independent-SL6VWS/AuthoringStudio.mjs';
import { createGeneratedCanvas } from 'file:///home/fzg/PycharmProjects/ArchCanvas/ArchCanvas_Model_Architecture_Studio/studio/src/generatedCanvas.ts';
import { followSourceView, resumeSourceAuthoring, sourceAuthoringKey } from 'file:///home/fzg/PycharmProjects/ArchCanvas/ArchCanvas_Model_Architecture_Studio/studio/src/sourceAuthoringSession.ts';
import { readSourceAuthoringWorkspace, writeSourceAuthoringWorkspace } from 'file:///home/fzg/PycharmProjects/ArchCanvas/ArchCanvas_Model_Architecture_Studio/studio/src/sourceAuthoringCache.ts';
import { WorkspaceModeSwitch } from 'file:///home/fzg/PycharmProjects/ArchCanvas/ArchCanvas_Model_Architecture_Studio/studio/.editor-workflow-independent-SL6VWS/WorkspaceModeSwitch.mjs';
import { resumeGeneratedWorkspace, generatedSourceView, sameGeneratedDraft, readPersistentGeneratedWorkspace, writePersistentGeneratedWorkspace, authoringViewSelection } from 'file:///home/fzg/PycharmProjects/ArchCanvas/ArchCanvas_Model_Architecture_Studio/studio/src/generatedWorkspace.ts';
import { blankDraft } from 'file:///home/fzg/PycharmProjects/ArchCanvas/ArchCanvas_Model_Architecture_Studio/studio/src/authoring.ts';
import { PreviewStudio } from 'file:///home/fzg/PycharmProjects/ArchCanvas/ArchCanvas_Model_Architecture_Studio/studio/.editor-workflow-independent-SL6VWS/PreviewStudio.mjs';
import { architecturePreviewRequest, bundlePreviewRequest, rawPreviewSourceRequest, previewNodeLayoutOperation, previewExpansionOperations, previewSourceMatchesArchitecture, previewUniqueNodeBindings, previewSourceLocation } from 'file:///home/fzg/PycharmProjects/ArchCanvas/ArchCanvas_Model_Architecture_Studio/studio/src/previewInterop.ts';
import { previewMappingSignature, previewNeedsPanelDocument, previewPanelDocument, projectPreviewHistory } from 'file:///home/fzg/PycharmProjects/ArchCanvas/ArchCanvas_Model_Architecture_Studio/studio/src/previewPanelDocument.ts';
import { isPreviewDraftEdge, previewEdgeAppearance, previewFormalEdgeIds, previewGraphEdges, previewDocumentSyncOperations, previewNodePresentation, previewPresentation, previewAnnotationConflicts, previewAnnotationPosition } from 'file:///home/fzg/PycharmProjects/ArchCanvas/ArchCanvas_Model_Architecture_Studio/studio/src/previewPresentation.ts';
import { previewExportBinding } from 'file:///home/fzg/PycharmProjects/ArchCanvas/ArchCanvas_Model_Architecture_Studio/studio/src/previewPublication.ts';
const PALETTE = ['#dcebf6', '#deeee6', '#f4e6d0', '#ece3f4', '#f5dfe3', '#e8ecf0'];
const KEY = 'archcanvas.active-document.v1';
const ACTIVE = 'archcanvas.active-canvas.v2';
const REVIEW = 'archcanvas.source-review.v1';
function download(name, content, type) {
    const url = URL.createObjectURL(new Blob([content], { type }));
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = name;
    anchor.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
}
function editingTarget(target) { return target instanceof Element && !!target.closest('input,textarea,select,[contenteditable]'); }
function statusText(evidence) { return evidence === 'opaque' ? '未解析内部' : evidence === 'contract' ? '框架契约' : '源码事实'; }
export default function App() {
    const previewEngine = useRef(null);
    const previewSnapshot = useRef(null);
    const previewSource = useRef(undefined);
    const previewBoundSource = useRef('');
    const previewSourceMatch = useRef(null);
    const previewNodeBindings = useRef(null);
    const previewCase = useRef('');
    const previewLoading = useRef(false);
    const [previewConnecting, setPreviewConnecting] = useState(true);
    const [previewBusy, setPreviewBusy] = useState(false);
    const [summaryCatalogOpen, setSummaryCatalogOpen] = useState(false);
    const synchronizingPreview = useRef(false);
    const initialModelLoading = useRef(true);
    const previewSequence = useRef(0);
    const [previewVersion, setPreviewVersion] = useState(0);
    const [previewDirty, setPreviewDirty] = useState(false);
    const [previewUndo, setPreviewUndo] = useState(false);
    const [previewRedo, setPreviewRedo] = useState(false);
    const [previewSelectedNodeIds, setPreviewSelectedNodeIds] = useState([]);
    const savedPreviewGraph = useRef(null);
    const enteringAuthoring = useRef(false);
    const openingExport = useRef(false);
    const [authoringOpen, setAuthoringOpen] = useState(false);
    const [summaryEditorId, setSummaryEditorId] = useState(null);
    const [authoringWorkspace, setAuthoringWorkspace] = useState();
    const authoringSessions = useRef(new Map());
    const authoringSessionKey = useRef(null);
    const generatedWorkspaces = useRef(new Map());
    const [browseBaseline, setBrowseBaseline] = useState();
    const [history, setHistory] = useState({ "document": { "schemaVersion": 1, "id": "canvas-architecture-model.AuthoredModel-ace9d329992d-1cd31276", "title": "独立连续工作流", "revision": 0, "sourceBindingDigest": "ace9d329992d50543f1614d535ff23dffd7005d25b1119934ed9bbfc1ddc7e37", "architecture": { "schemaVersion": 1, "id": "architecture:model.AuthoredModel", "label": "AuthoredModel", "sourceDigest": "ace9d329992d50543f1614d535ff23dffd7005d25b1119934ed9bbfc1ddc7e37", "irDigest": "1cd3127635084258c9c82c20a5e56532cc97ba0ec44a196f2df13fe7dec0e42b", "entry": "model:AuthoredModel", "nodes": [{ "id": "input:model.AuthoredModel:node_c96c6d5be8d08a12", "label": "node_c96c6d5be8d08a12", "kind": "Input", "category": "input", "children": [], "ports": [{ "id": "input:model.AuthoredModel:node_c96c6d5be8d08a12:out:node_c96c6d5be8d08a12", "name": "node_c96c6d5be8d08a12", "direction": "out", "role": "data", "ordinal": 0 }], "parameters": {}, "source": { "path": "model.py", "line": 11, "endLine": 13, "expression": "def forward(self, node_c96c6d5be8d08a12):\n        node_7f2fe580edb35154 = self.node_7f2fe580edb35154(node_c96c6d5be8d08a12)\n        return {'output': node_7f2fe580edb35154}" }, "evidence": "source", "parentId": "call:instance:model.AuthoredModel" }, { "id": "call:instance:model.AuthoredModel", "label": "AuthoredModel", "kind": "Module", "category": "container", "children": ["input:model.AuthoredModel:node_c96c6d5be8d08a12", "call:instance:model.AuthoredModel.node_7f2fe580edb35154", "output:model.AuthoredModel:0"], "ports": [{ "id": "call:instance:model.AuthoredModel:in:node_c96c6d5be8d08a12", "name": "node_c96c6d5be8d08a12", "direction": "in", "role": "data", "ordinal": 0 }], "parameters": {}, "source": { "path": "model.py", "line": 6, "endLine": 13, "expression": "class AuthoredModel(nn.Module):\n    def __init__(self):\n        super().__init__()\n        self.node_7f2fe580edb35154 = nn.Linear(in_features=4, out_features=4, bias=True, dtype=torch.float32)\n\n    def forward(self, node_c96c6d5be8d08a12):\n        node_7f2fe580edb35154 = self.node_7f2fe580edb35154(node_c96c6d5be8d08a12)\n        return {'output': node_7f2fe580edb35154}" }, "evidence": "source", "instanceId": "instance:model.AuthoredModel", "callId": "call:instance:model.AuthoredModel" }, { "id": "call:instance:model.AuthoredModel.node_7f2fe580edb35154", "label": "node 7f2fe580edb35154", "kind": "Linear", "category": "linear", "children": [], "ports": [{ "id": "call:instance:model.AuthoredModel.node_7f2fe580edb35154:in:input", "name": "input", "direction": "in", "role": "data", "ordinal": 0 }, { "id": "call:instance:model.AuthoredModel.node_7f2fe580edb35154:out:output", "name": "output", "direction": "out", "role": "data", "ordinal": 0 }], "parameters": { "in_features": 4, "out_features": 4, "bias": true, "dtype": { "expression": "torch.float32", "origin": "unknown" } }, "source": { "path": "model.py", "line": 12, "endLine": 12, "expression": "self.node_7f2fe580edb35154(node_c96c6d5be8d08a12)" }, "evidence": "contract", "parentId": "call:instance:model.AuthoredModel", "instanceId": "instance:model.AuthoredModel.node_7f2fe580edb35154", "callId": "call:instance:model.AuthoredModel.node_7f2fe580edb35154", "parameterOrigins": { "in_features": { "kind": "literal", "path": "model.py", "line": 9, "endLine": 9, "expression": "4", "column": 59, "endColumn": 60 }, "out_features": { "kind": "literal", "path": "model.py", "line": 9, "endLine": 9, "expression": "4", "column": 75, "endColumn": 76 }, "bias": { "kind": "literal", "path": "model.py", "line": 9, "endLine": 9, "expression": "True", "column": 83, "endColumn": 87 }, "dtype": { "kind": "unknown", "path": "model.py", "line": 9, "endLine": 9, "expression": "torch.float32", "column": 95, "endColumn": 108 } } }, { "id": "output:model.AuthoredModel:0", "label": "output", "kind": "Output", "category": "output", "children": [], "ports": [{ "id": "output:model.AuthoredModel:0:in:value", "name": "value", "direction": "in", "role": "data", "ordinal": 0 }], "parameters": {}, "source": { "path": "model.py", "line": 11, "endLine": 13, "expression": "def forward(self, node_c96c6d5be8d08a12):\n        node_7f2fe580edb35154 = self.node_7f2fe580edb35154(node_c96c6d5be8d08a12)\n        return {'output': node_7f2fe580edb35154}" }, "evidence": "source", "parentId": "call:instance:model.AuthoredModel", "outputPath": [{ "kind": "key", "key": "output" }] }], "edges": [{ "id": "edge:0", "source": { "nodeId": "input:model.AuthoredModel:node_c96c6d5be8d08a12", "portId": "input:model.AuthoredModel:node_c96c6d5be8d08a12:out:node_c96c6d5be8d08a12" }, "target": { "nodeId": "call:instance:model.AuthoredModel", "portId": "call:instance:model.AuthoredModel:in:node_c96c6d5be8d08a12" }, "tensorId": "tensor:input:model.AuthoredModel:node_c96c6d5be8d08a12:node_c96c6d5be8d08a12", "role": "data" }, { "id": "edge:1", "source": { "nodeId": "input:model.AuthoredModel:node_c96c6d5be8d08a12", "portId": "input:model.AuthoredModel:node_c96c6d5be8d08a12:out:node_c96c6d5be8d08a12" }, "target": { "nodeId": "call:instance:model.AuthoredModel.node_7f2fe580edb35154", "portId": "call:instance:model.AuthoredModel.node_7f2fe580edb35154:in:input" }, "tensorId": "tensor:input:model.AuthoredModel:node_c96c6d5be8d08a12:node_c96c6d5be8d08a12", "role": "data" }, { "id": "edge:2", "source": { "nodeId": "call:instance:model.AuthoredModel.node_7f2fe580edb35154", "portId": "call:instance:model.AuthoredModel.node_7f2fe580edb35154:out:output" }, "target": { "nodeId": "output:model.AuthoredModel:0", "portId": "output:model.AuthoredModel:0:in:value" }, "tensorId": "tensor:call:instance:model.AuthoredModel.node_7f2fe580edb35154:output", "role": "data" }], "diagnostics": [{ "level": "info", "message": "Static AST subset only. User code was not imported or executed; no inferred shapes or runtime verification. Source editing uses separately reviewed registered transactions." }], "sources": [{ "path": "model.py", "content": "\"\"\"Fresh ArchCanvas authored model; static declarations are not runtime verification.\"\"\"\nimport torch\nfrom torch import nn\n\n\nclass AuthoredModel(nn.Module):\n    def __init__(self):\n        super().__init__()\n        self.node_7f2fe580edb35154 = nn.Linear(in_features=4, out_features=4, bias=True, dtype=torch.float32)\n\n    def forward(self, node_c96c6d5be8d08a12):\n        node_7f2fe580edb35154 = self.node_7f2fe580edb35154(node_c96c6d5be8d08a12)\n        return {'output': node_7f2fe580edb35154}\n", "digest": "e34b58605d64958ea31a4e28b01bb20b939fc94cabdbc6ea5450cdab60ba2113" }] }, "displayAliases": { "input:model.AuthoredModel:node_c96c6d5be8d08a12": "输入", "call:instance:model.AuthoredModel.node_7f2fe580edb35154": "我的投影", "output:model.AuthoredModel:0": "输出" }, "nodeStyleOverrides": {}, "edgeStyleOverrides": {}, "legendItems": [{ "id": "legend:input", "label": "Input", "color": "#eef2f5", "glyph": "tensor" }, { "id": "legend:container", "label": "Container", "color": "#f5f8fc", "glyph": "module" }, { "id": "legend:linear", "label": "Linear", "color": "#e5f1ed", "glyph": "operator" }, { "id": "legend:output", "label": "Output", "color": "#eef2f5", "glyph": "tensor" }], "annotations": [], "pageSpec": { "widthMm": 180, "background": "#ffffff", "preset": "paper" }, "expandedIds": ["call:instance:model.AuthoredModel"], "layout": { "call:instance:model.AuthoredModel": { "x": -558, "y": -322, "width": 1010, "height": 762 }, "input:model.AuthoredModel:node_c96c6d5be8d08a12": { "x": 28, "y": 62, "width": 194, "height": 62 }, "call:instance:model.AuthoredModel.node_7f2fe580edb35154": { "x": 398, "y": 362, "width": 194, "height": 62 }, "output:model.AuthoredModel:0": { "x": 788, "y": 672, "width": 194, "height": 62 } }, "layoutByFrontier": {}, "pinnedObjects": [] }, "past": [], "future": [] });
    const [examples, setExamples] = useState([]);
    const [exampleId, setExampleId] = useState('');
    const [selection, setSelection] = useState({ kind: 'node', ids: [] });
    const [tool, setTool] = useState('select');
    const [previewTool, setPreviewTool] = useState('select');
    const [portEditing, setPortEditing] = useState(false);
    const [layoutMoveScope, setLayoutMoveScope] = useState('all-frontiers');
    const [panel, setPanel] = useState('object');
    const [sourceOpen, setSourceOpen] = useState(false);
    useWorkspaceMenus();
    const [leftCollapsed, setLeftCollapsed] = useState(false);
    const [rightCollapsed, setRightCollapsed] = useState(false);
    const [treeSearch, setTreeSearch] = useState('');
    const [actionFeedback, setActionFeedback] = useState(null);
    const [importOpen, setImportOpen] = useState(false);
    const [sourceText, setSourceText] = useState('');
    const [entry, setEntry] = useState('Model');
    const [filename, setFilename] = useState('model.py');
    const [busy, setBusy] = useState(false);
    const [grid, setGrid] = useState(true);
    const [notice, setNotice] = useState('正在连接独立 runtime…');
    const [failure, setFailure] = useState('');
    const [storageRevision, setStorageRevision] = useState(0);
    const [savedVisualRevision, setSavedVisualRevision] = useState(-1);
    const [command, setCommand] = useState('');
    const [capabilities, setCapabilities] = useState(null);
    const [projectId, setProjectId] = useState(null);
    const [review, setReview] = useState(null);
    const [reviewError, setReviewError] = useState('');
    const [exportDocument, setExportDocument] = useState(null);
    const [exportPreview, setExportPreview] = useState(null);
    const [inputSpec, setInputSpec] = useState(null);
    const [runtimeOpen, setRuntimeOpen] = useState(false);
    const [runtimeCancel, setRuntimeCancel] = useState(null);
    const [cancelling, setCancelling] = useState(false);
    const [connectionProposal, setConnectionProposal] = useState(null);
    const viewportRef = useRef(null);
    const historyRef = useRef(history);
    historyRef.current = history;
    // Retained formal source-editor view metadata; never controls the Summary canvas.
    const cameraRef = useRef({ x: 30, y: 30, zoom: 1 });
    const loadSequence = useRef(0);
    const saving = useRef(false);
    const current = history?.document;
    const architecture = current?.architecture;
    const summaryEditing = !!summaryEditorId && summaryEditorId === previewSnapshot.current?.caseId;
    const summaryIR = previewSnapshot.current?.graph?.generic?.ir;
    const summaryCounts = summaryIR?.schema === 'archcanvas-source-semantic/2' && Array.isArray(summaryIR.nodes) && Array.isArray(summaryIR.edges)
        ? { nodes: summaryIR.nodes.length, edges: summaryIR.edges.length } : null;
    const navigation = useMemo(() => previewHierarchy(previewSnapshot.current), [previewVersion]);
    const frontier = useMemo(() => previewFrontier(previewSnapshot.current, navigation), [previewVersion, navigation]);
    const previewSourceIdentity = previewSnapshot.current?.sourceIdentity;
    const selectedNode = selection.kind === 'node' ? architecture?.nodes.find(n => n.id === selection.ids[0]) : undefined;
    const formalPreviewBindings = currentPreviewNodeBindings();
    const selectedEdge = selection.kind === 'edge' ? architecture?.edges.find(n => n.id === selection.ids[0]) : undefined;
    const selectedPreviewEdge = selection.kind === 'preview-edge' ? previewGraphEdges(previewSnapshot.current?.graph).find(edge => edge.id === selection.ids[0]) : undefined;
    const selectedEdgePreview = selectedEdge && architecture ? previewGraphEdges(previewSnapshot.current?.graph).find(edge => {
        const ids = previewFormalEdgeIds(architecture, edge, previewSnapshot.current?.graph, previewSource.current, formalPreviewBindings);
        return ids.length === 1 && ids[0] === selectedEdge.id;
    }) : undefined;
    const selectedEdgeAppearance = selectedEdgePreview ? previewEdgeAppearance(previewSnapshot.current?.graph, selectedEdgePreview) : undefined;
    const selectedPreviewEdgeAppearance = selectedPreviewEdge ? previewEdgeAppearance(previewSnapshot.current?.graph, selectedPreviewEdge) : undefined;
    const selectedAnnotation = selection.kind === 'annotation' ? current?.annotations.find(n => n.id === selection.ids[0]) : undefined;
    const selectedVisiblePreviewNode = selectedNode && architecture ? graphFromSnapshot()?.nodes.find(node => formalPreviewBindings.get(node.id) === selectedNode.id) : undefined;
    const selectedPreviewNodePresentation = selectedVisiblePreviewNode ? previewNodePresentation(previewSnapshot.current?.graph, selectedVisiblePreviewNode) : undefined;
    const previewSelectedNodes = (graphFromSnapshot()?.nodes ?? []).filter(node => previewSelectedNodeIds.includes(node.id) && !node.junction);
    const inspectionNode = !selectedNode && selection.kind === 'node' && !selection.ids.length && previewSelectedNodes.length === 1 ? previewSelectedNodes[0] : undefined;
    const inspectionPresentation = inspectionNode ? previewNodePresentation(previewSnapshot.current?.graph, inspectionNode) : undefined;
    const inspectionSource = inspectionNode ? previewSourceLocation({ nodeId: inspectionNode.id, node: inspectionNode }, previewSource.current) : null;
    const previewSourceSpan = selectedNode?.source ?? inspectionSource;
    const inspectionExpandable = inspectionNode && (graphFromSnapshot()?.nodes.some(node => node.parent === inspectionNode.id) ||
        navigation?.nodes.some(node => node.parentId === inspectionNode.id));
    const previewPinnedCount = previewSelectedNodes.filter(node => previewPresentation(previewSnapshot.current?.graph)?.nodes?.[node.id]?.pinned).length;
    const previewAllPinned = previewSelectedNodes.length > 0 && previewPinnedCount === previewSelectedNodes.length;
    const previewLayoutDisabled = !current || busy || previewConnecting || previewBusy;
    const previewCanAlign = previewSelectedNodes.length >= 2 && previewSelectedNodes.every(node => (node.parent ?? null) === (previewSelectedNodes[0].parent ?? null));
    const annotationConflicts = selectedAnnotation && previewSnapshot.current?.graph ? previewAnnotationConflicts(previewSnapshot.current.graph, selectedAnnotation.id) : [];
    const dirty = previewDirty || (!!current && current.revision !== savedVisualRevision);
    function sourceFromResult(result) {
        return (result.bundle ?? result.source ?? result.document?.adapter);
    }
    function graphFromSnapshot(snapshot = previewSnapshot.current) {
        const graph = snapshot?.graph;
        return graph && Array.isArray(graph.nodes) ? graph : null;
    }
    function currentPreviewSourceMatches(architecture) {
        const source = previewSource.current;
        if (!source)
            return false;
        // Imported source corpora and architecture are immutable for a generation;
        // all source edits install new objects and invalidate this checked pair.
        const checked = previewSourceMatch.current;
        if (checked?.source === source && checked.architecture === architecture)
            return checked.matches;
        const matches = previewSourceMatchesArchitecture(source, architecture);
        previewSourceMatch.current = { source, architecture, matches };
        return matches;
    }
    function currentPreviewNodeBindings() {
        const architecture = historyRef.current?.document.architecture, snapshot = previewSnapshot.current;
        if (!architecture || !snapshot?.graph)
            return new Map();
        const source = previewSource.current, signature = previewMappingSignature(snapshot), cached = previewNodeBindings.current;
        if (cached?.architecture === architecture && cached.source === source && cached.signature === signature)
            return cached.bindings;
        const bindings = previewUniqueNodeBindings(architecture, snapshot.graph, source);
        previewNodeBindings.current = { architecture, source, signature, bindings };
        return bindings;
    }
    function readyPreview(document = historyRef.current?.document) {
        if (!document || initialModelLoading.current || previewLoading.current || synchronizingPreview.current || !previewSnapshot.current?.graph || previewSnapshot.current.busy)
            return false;
        if (document.sourceBindingDigest.startsWith('preview-only:'))
            return document.sourceBindingDigest === `preview-only:${previewCase.current}`;
        return !!previewSource.current && previewBoundSource.current === document.architecture.sourceDigest + ':' + document.architecture.irDigest &&
            currentPreviewSourceMatches(document.architecture) &&
            (previewSource.current.schema === 'summary-source-adapter/1' ? previewSource.current.id : previewSource.current.caseId) === previewCase.current;
    }
    async function restoreMatchingPreview(document, caseId, sequence) {
        if (!caseId)
            return null;
        try {
            const snapshot = await previewEngine.current.snapshot();
            if (sequence !== loadSequence.current || snapshot.caseId !== caseId)
                return null;
            if (snapshot.importedDocument && document.sourceBindingDigest === `preview-only:${caseId}`) {
                previewSource.current = undefined;
                previewCase.current = caseId;
                previewSnapshot.current = snapshot;
                previewBoundSource.current = '';
                const saved = await matchesPreviewSave(localStorage, document, snapshot.graph);
                if (sequence !== loadSequence.current)
                    return null;
                if (saved)
                    savedPreviewGraph.current = JSON.stringify(snapshot.graph);
                setPreviewConnecting(false);
                return snapshot;
            }
            const result = await previewEngine.current.source(), source = sourceFromResult(result);
            if (sequence !== loadSequence.current || result.document?.caseId !== caseId || !source || !previewSourceMatchesArchitecture(source, document.architecture))
                return null;
            previewSource.current = source;
            previewCase.current = caseId;
            previewSnapshot.current = snapshot;
            previewBoundSource.current = document.architecture.sourceDigest + ':' + document.architecture.irDigest;
            const saved = await matchesPreviewSave(localStorage, document, snapshot.graph);
            if (sequence !== loadSequence.current)
                return null;
            if (saved)
                savedPreviewGraph.current = JSON.stringify(snapshot.graph);
            setPreviewConnecting(false);
            return snapshot;
        }
        catch {
            return null;
        }
    }
    function previewNodeId(id) {
        const document = historyRef.current?.document, graph = graphFromSnapshot();
        if (!document || !graph)
            return undefined;
        const detail = previewSnapshot.current?.graph?.recursive?.authority?.detail;
        const nodes = detail?.nodes ?? graph.nodes;
        const bindings = currentPreviewNodeBindings();
        return nodes.find(node => bindings.get(node.id) === id)?.id;
    }
    function focusPreviewNode(id) {
        const nodeId = previewNodeId(id);
        if (nodeId)
            previewEngine.current?.focus({ nodeId });
        else
            setNotice('该源码对象在当前目录图中没有直接对应图元；可在源码面板查看，或进入模型编辑。');
    }
    function mapPreviewOperations(operations) {
        const byId = (id) => {
            const mapped = previewNodeId(id);
            if (!mapped)
                throw new Error('当前源码对象未显示为独立图元；可进入模型编辑，或在原型画布选择对应的展示对象。');
            return mapped;
        };
        return operations.flatMap(operation => {
            if (operation.type === 'edgeStyle') {
                const architecture = historyRef.current?.document.architecture;
                const formal = architecture?.edges.find(edge => edge.id === operation.id);
                const graph = previewSnapshot.current?.graph;
                if (!formal || !architecture || !graph)
                    throw new Error('连接的源码绑定不可用。');
                const bindings = currentPreviewNodeBindings();
                const found = previewGraphEdges(graph).filter(edge => {
                    const ids = previewFormalEdgeIds(architecture, edge, graph, previewSource.current, bindings);
                    return ids.length === 1 && ids[0] === formal.id;
                });
                if (!found.length)
                    throw new Error('当前前沿没有显示该连接，请先展开所属模块。');
                return found.map(edge => ({ ...operation, id: edge.id }));
            }
            if (operation.type === 'move' || operation.type === 'pin')
                return [{ ...operation, ids: operation.ids.map(byId) }];
            if (operation.type === 'nodeLayout') {
                return [previewNodeLayoutOperation(historyRef.current.document, operation, graphFromSnapshot(), previewSource.current)];
            }
            if (operation.type === 'alias' || operation.type === 'nodeStyle' || operation.type === 'expand')
                return [{ ...operation, id: byId(operation.id) }];
            if (operation.type === 'portLayout')
                return [{ ...operation, ownerId: byId(operation.ownerId), nodeId: byId(operation.nodeId) }];
            return [{ ...operation }];
        });
    }
    async function bindPreviewSource(result, openEditor = false) {
        const source = sourceFromResult(result);
        if (!source)
            throw new Error('当前示例没有模型源码；可新建模型或导入 Python 源码。');
        previewSource.current = source;
        const sequence = ++previewSequence.current;
        const expectedCase = previewCase.current;
        setPreviewConnecting(true);
        const bound = historyRef.current?.document;
        // A source-inspection projection may contain additional opaque objects.
        // That does not revoke an existing, byte-matched formal source contract.
        if (bound && !bound.sourceBindingDigest.startsWith('preview-only:') && previewSourceMatchesArchitecture(source, bound.architecture)) {
            previewBoundSource.current = bound.architecture.sourceDigest + ':' + bound.architecture.irDigest;
            if (previewSnapshot.current)
                await receivePreviewState(previewSnapshot.current);
            setPreviewConnecting(false);
            if (openEditor)
                await continueModelAuthoring();
            return;
        }
        let arch;
        try {
            const request = source.schema === 'summary-source-adapter/1' ? bundlePreviewRequest(source) : rawPreviewSourceRequest(source);
            arch = await api.previewEditSource(request);
        }
        catch (error) {
            if (sequence !== previewSequence.current || expectedCase !== previewCase.current)
                return;
            if (previewSnapshot.current) {
                const panelDocument = previewPanelDocument(previewSnapshot.current, source);
                historyRef.current = createHistory(panelDocument);
                setHistory(historyRef.current);
                previewBoundSource.current = '';
                setProjectId(null);
                setStorageRevision(0);
                setSavedVisualRevision(-1);
                await receivePreviewState(previewSnapshot.current);
                setPreviewConnecting(false);
                setNotice(`源码文本已打开，只读查看；此入口暂超出模型编辑契约：${String(error)}`);
            }
            if (openEditor) {
                setSourceOpen(true);
                throw error;
            }
            return;
        }
        if (sequence !== previewSequence.current || expectedCase !== previewCase.current)
            return;
        if (!openEditor && previewSnapshot.current && previewNeedsPanelDocument(previewSnapshot.current, arch, source)) {
            historyRef.current = createHistory(previewPanelDocument(previewSnapshot.current, source));
            setHistory(historyRef.current);
            previewBoundSource.current = '';
            setProjectId(null);
            setStorageRevision(0);
            setSavedVisualRevision(-1);
            await receivePreviewState(previewSnapshot.current);
            setExampleId('');
            setPreviewConnecting(false);
            setNotice('原型视图与源码已打开；展示对象可独立编辑，进入编辑模式后按源码建立模型绑定。');
            return;
        }
        previewBoundSource.current = arch.sourceDigest + ':' + arch.irDigest;
        await openArchitecture(arch, true);
        if (sequence !== previewSequence.current || expectedCase !== previewCase.current)
            return;
        const before = historyRef.current;
        if (before && previewSnapshot.current)
            await receivePreviewState(previewSnapshot.current);
        setExampleId('');
        setPreviewConnecting(false);
        if (openEditor)
            await continueModelAuthoring();
    }
    function receivePreviewSelection(message) {
        if (message.caseId && message.caseId !== previewCase.current)
            return;
        synchronizePreviewNodeSelection(message.nodeIds ?? message.selectedNodes);
        if (typeof message.annotationId === 'string') {
            setSelection({ kind: 'annotation', ids: [message.annotationId] });
            setPanel('object');
            return;
        }
        const architecture = historyRef.current?.document.architecture;
        if (!architecture)
            return;
        const edge = message.edge;
        const graph = graphFromSnapshot();
        if (edge && graph) {
            const raw = previewGraphEdges(previewSnapshot.current?.graph).find(item => item.id === edge.id);
            const ids = raw ? previewFormalEdgeIds(architecture, raw, previewSnapshot.current?.graph, previewSource.current, currentPreviewNodeBindings()) : [];
            setSelection(ids.length === 1 ? { kind: 'edge', ids } : { kind: 'preview-edge', ids: [edge.id] });
            setPanel('object');
            return;
        }
        const selected = (message.nodeIds ?? message.selectedNodes);
        const bindings = currentPreviewNodeBindings();
        const ids = selected?.length && graph ? [...new Set(selected.flatMap(id => bindings.has(id) ? [bindings.get(id)] : []))] :
            typeof message.nodeId === 'string' && bindings.has(message.nodeId) ? [bindings.get(message.nodeId)] : [];
        setSelection({ kind: 'node', ids });
        setPanel('object');
    }
    async function receivePreviewState(snapshot) {
        previewSnapshot.current = snapshot;
        synchronizePreviewNodeSelection(snapshot.selectedNodes);
        if (snapshot.tool === 'select' || snapshot.tool === 'connect' || snapshot.tool === 'bend')
            setPreviewTool(snapshot.tool);
        if (typeof snapshot.showPorts === 'boolean')
            setPortEditing(snapshot.showPorts);
        if (typeof snapshot.gridVisible === 'boolean')
            setGrid(snapshot.gridVisible);
        setPreviewBusy(Boolean(snapshot.busy));
        const graph = snapshot.graph;
        const caseId = String(graph?.caseId ?? snapshot.caseId ?? '');
        setPreviewDirty(Boolean(snapshot.dirty) && JSON.stringify(graph) !== savedPreviewGraph.current);
        setPreviewUndo(Boolean(snapshot.canUndo));
        setPreviewRedo(Boolean(snapshot.canRedo));
        setPreviewVersion(version => version + 1);
        setSelection(before => before.kind === 'preview-edge' && !previewGraphEdges(graph).some(edge => edge.id === before.ids[0]) ? { kind: 'node', ids: [] } : before);
        if (initialModelLoading.current) {
            previewCase.current = caseId;
            return;
        }
        if (previewLoading.current) {
            previewCase.current = caseId;
            return;
        }
        // A loading/route transaction publishes toolbar state with the previous
        // committed graph. Source ownership changes only after its final snapshot.
        if (snapshot.busy)
            return;
        if (caseId && caseId !== previewCase.current) {
            ++previewSequence.current;
            ++loadSequence.current;
            previewCase.current = caseId;
            previewBoundSource.current = '';
            previewSource.current = undefined;
            setBusy(false);
            setPreviewConnecting(true);
            const panelDocument = previewPanelDocument(snapshot);
            historyRef.current = createHistory(panelDocument);
            setHistory(historyRef.current);
            setSelection({ kind: 'node', ids: [] });
            setExampleId('');
            setProjectId(null);
            if (snapshot.importedDocument) {
                setPreviewConnecting(false);
                setNotice('已打开 Summary 文档；视觉编辑保存到浏览器，可通过编辑 JSON 搬运。文档证据未绑定 Python 源码。');
                return;
            }
            const frozenCase = caseId;
            const generation = previewSequence.current, loadGeneration = loadSequence.current;
            try {
                const result = await previewEngine.current.source();
                if (previewCase.current !== frozenCase || generation !== previewSequence.current || loadGeneration !== loadSequence.current)
                    return;
                await bindPreviewSource(result);
            }
            catch (error) {
                if (previewCase.current === frozenCase && generation === previewSequence.current && loadGeneration === loadSequence.current) {
                    setPreviewConnecting(false);
                    setNotice(`预览已打开；源码编辑入口：${String(error)}`);
                }
            }
            return;
        }
        if (synchronizingPreview.current)
            return;
        if (snapshot.authoring && historyRef.current?.document.sourceBindingDigest.startsWith('preview-only:')) {
            const next = createHistory(previewPanelDocument(snapshot));
            historyRef.current = next;
            setHistory(next);
            return;
        }
        const before = historyRef.current;
        const visual = graphFromSnapshot(snapshot);
        if (before && !before.document.sourceBindingDigest.startsWith('preview-only:') && (!previewSource.current ||
            !currentPreviewSourceMatches(before.document.architecture) ||
            (previewSource.current.schema === 'summary-source-adapter/1' ? previewSource.current.id : previewSource.current.caseId) !== caseId))
            return;
        // Project uniquely mapped presentation only. Extra inspection objects stay
        // in the preview graph and never replace formal facts or project ownership.
        if (before && visual) {
            const presentationTitle = (graph?.recursive?.state?.studioPresentation ?? graph?.studioPresentation);
            const next = projectPreviewHistory(before, visual, previewSource.current, presentationTitle?.title ?? String(snapshot.title ?? before.document.title), currentPreviewNodeBindings());
            if (next !== before) {
                historyRef.current = next;
                setHistory(next);
            }
        }
    }
    useEffect(() => {
        const architecture = current?.architecture;
        if (!architecture)
            return;
        if (architecture.sourceDigest.startsWith('preview-only:'))
            return;
        const identity = architecture.sourceDigest + ':' + architecture.irDigest;
        if (previewBoundSource.current === identity)
            return;
        const sequence = ++previewSequence.current;
        previewBoundSource.current = identity;
        previewLoading.current = true;
        setPreviewConnecting(true);
        let alive = true;
        (async () => {
            try {
                const bundle = await api.previewAnalyze(architecturePreviewRequest(architecture));
                if (!alive || sequence !== previewSequence.current)
                    return;
                previewSource.current = bundle;
                previewCase.current = bundle.id;
                await previewEngine.current.load(bundle);
                const document = historyRef.current?.document;
                if (document?.architecture.sourceDigest === architecture.sourceDigest && document.architecture.irDigest === architecture.irDigest) {
                    const detail = previewSnapshot.current?.graph?.recursive?.authority?.detail;
                    const expansion = detail ? previewExpansionOperations(document, detail, previewSource.current) : [];
                    const operations = previewDocumentSyncOperations(undefined, document, previewSnapshot.current?.graph, previewSource.current);
                    await previewEngine.current.visual([...expansion, ...operations]);
                    await previewEngine.current.command('fit');
                }
                if (alive)
                    setNotice('源码已接入递归预览；模型未执行。');
            }
            catch (error) {
                if (alive) {
                    previewBoundSource.current = '';
                    setFailure(`预览解析失败：${String(error)}`);
                }
            }
            finally {
                if (sequence === previewSequence.current) {
                    previewLoading.current = false;
                    setPreviewConnecting(false);
                    if (alive && previewSnapshot.current)
                        await receivePreviewState(previewSnapshot.current);
                }
            }
        })();
        return () => { alive = false; };
    }, [current?.architecture.sourceDigest, current?.architecture.irDigest]);
    useEffect(() => {
        try {
            setInputSpec(JSON.parse(localStorage.getItem(`archcanvas.runtime-profile:${current?.id}`) ?? 'null'));
        }
        catch {
            setInputSpec(null);
        }
        setRuntimeOpen(false);
    }, [current?.id]);
    function saveInputSpec(spec) {
        if (current)
            localStorage.setItem(`archcanvas.runtime-profile:${current.id}`, JSON.stringify(spec));
        setInputSpec(spec);
        setRuntimeOpen(false);
        setNotice('运行输入已登记；候选检查仍是静态，连接预览才执行隔离验证');
    }
    useEffect(() => { document.querySelector('.inspector-content')?.scrollTo({ top: 0 }); }, [selection.ids[0], panel]);
    function readCameraViewport() {
        return cameraViewportSize(viewportRef.current?.getBoundingClientRect());
    }
    // Source-editor sessions retain their own camera, independently of preview navigation.
    const commitCamera = useCallback((view) => { cameraRef.current = { ...view }; }, []);
    const cancelGesture = useCallback(() => { if (previewSnapshot.current?.dragging)
        previewEngine.current?.command('cancel-gesture'); }, []);
    function chooseTool(next) {
        cancelGesture();
        setPreviewTool(next);
        previewEngine.current?.command(`${next}-tool`);
    }
    function chooseMoveScope(next) { cancelGesture(); setLayoutMoveScope(next); }
    useEffect(() => { if (review || exportDocument || importOpen || connectionProposal || runtimeOpen)
        cancelGesture(); }, [review, exportDocument, importOpen, connectionProposal, runtimeOpen, cancelGesture]);
    const apply = useCallback((operations, message) => {
        cancelGesture();
        const interaction = studioTelemetry.beginInteraction(`visual:${operations.map(operation => operation.type === 'expand' && !operation.expanded ? 'collapse' : operation.type).join('+') || 'noop'}`);
        try {
            const previous = historyRef.current;
            if (!previous)
                return;
            if (!readyPreview(previous.document))
                throw new Error('预览正在接入当前源码，请完成后再编辑画布。');
            const translated = mapPreviewOperations(operations);
            if (operations.some(operation => operation.type === 'expand')) {
                // The preview transaction owns validation, neighbor displacement and
                // one undo entry. Its resulting snapshot updates the formal mirror.
                const sequence = loadSequence.current;
                void previewEngine.current?.visual(translated).catch(error => {
                    if (sequence === loadSequence.current)
                        setFailure(String(error));
                });
                if (message)
                    setNotice(message);
                setFailure('');
                return;
            }
            const next = reduceHistory(previous, { type: 'apply', baseRevision: previous.document.revision, operations });
            historyRef.current = next;
            setHistory(next);
            void previewEngine.current?.visual(translated).catch(error => {
                if (historyRef.current === next) {
                    historyRef.current = previous;
                    setHistory(previous);
                }
                setFailure(String(error));
            });
            if (message)
                setNotice(message);
            setFailure('');
        }
        catch (error) {
            setFailure(String(error));
        }
        finally {
            studioTelemetry.endInteraction(interaction);
        }
    }, [cancelGesture]);
    async function stylePreviewEdge(id, style) {
        const engine = previewEngine.current;
        if (!engine || !readyPreview() || !previewGraphEdges(previewSnapshot.current?.graph).some(edge => edge.id === id))
            return;
        try {
            await engine.visual([{ type: 'edgeStyle', id, style }]);
            setFailure('');
        }
        catch (error) {
            setFailure(String(error));
        }
    }
    function optimizeAutomaticPorts(id, previewIdentity = false) {
        if (!readyPreview())
            return;
        const nodeId = previewIdentity ? graphFromSnapshot()?.nodes.find(node => node.id === id)?.id : previewNodeId(id);
        if (!nodeId) {
            setFailure('此对象没有唯一对应的可见 Summary 图元。');
            return;
        }
        const sequence = loadSequence.current;
        void previewEngine.current?.visual([{ type: 'portLayout', ownerId: nodeId, nodeId, layout: null }]).then(() => {
            if (sequence === loadSequence.current) {
                setNotice('已由 Summary 恢复当前图元的自动连接点；可撤销。');
                setFailure('');
            }
        }).catch(error => { if (sequence === loadSequence.current)
            setFailure(String(error)); });
    }
    const selectHierarchyNode = useCallback((id, additive = false) => {
        const graph = graphFromSnapshot();
        const detail = previewSnapshot.current?.graph?.recursive?.authority?.detail ?? graph;
        const mapped = detail?.nodes.some(node => node.id === id && !node.junction) ? id : previewNodeId(id);
        if (!mapped) {
            setFailure('此源码对象没有唯一对应的画布图元；可直接在画布选择或查看源码。');
            return;
        }
        setFailure('');
        setPanel('object');
        previewEngine.current?.focus({ nodeId: mapped, additive });
    }, []);
    const expandHierarchyNode = useCallback((id, expanded) => {
        const hierarchy = previewHierarchy(previewSnapshot.current);
        if (!hierarchy?.nodes.some(node => node.id === id)) {
            apply([{ type: 'expand', id, expanded }]);
            return;
        }
        if (!readyPreview()) {
            setFailure('预览正在接入当前源码，请完成后再展开。');
            return;
        }
        setFailure('');
        const operations = previewHierarchyExpansion(hierarchy, id, expanded);
        if (!operations.length)
            return;
        const sequence = loadSequence.current;
        void previewEngine.current?.visual(operations).catch(error => {
            if (sequence === loadSequence.current)
                setFailure(String(error));
        });
    }, [apply]);
    function setSemanticFrontier(preset) {
        cancelGesture();
        if (!readyPreview()) {
            setFailure('预览正在接入当前源码，请完成后再切换语义前沿。');
            return;
        }
        setFailure('');
        setNotice(preset === 'overview' ? '正在切换到架构概览（F0）…' : '正在切换到架构详图（F1）…');
        previewEngine.current?.command('set-frontier', { preset });
    }
    function focusCurrentFrontier() {
        const id = previewSelectedNodeIds[0] ?? frontier?.expandedIds[frontier.expandedIds.length - 1];
        if (id) {
            previewEngine.current?.focus({ nodeId: id });
            return;
        }
        fit();
    }
    const undo = useCallback(() => { cancelGesture(); previewEngine.current?.command('undo'); setActionFeedback(null); setNotice('已撤销一次画布操作'); }, [cancelGesture]);
    const redo = useCallback(() => { cancelGesture(); previewEngine.current?.command('redo'); setActionFeedback(null); setNotice('已重做一次画布操作'); }, [cancelGesture]);
    function repairSummaryLayout() {
        if (!readyPreview())
            return;
        cancelGesture();
        previewEngine.current?.command('apply-layout');
    }
    const fit = useCallback(() => { cancelGesture(); previewEngine.current?.command('fit'); }, [cancelGesture]);
    const openArchitecture = useCallback(async (arch, restore = true, requestSequence) => {
        const sequence = requestSequence ?? ++loadSequence.current;
        if (sequence !== loadSequence.current)
            return;
        let document = createDocument(arch);
        let saved = -1;
        let version = 0;
        if (restore) {
            try {
                const stored = await api.document(document.id);
                if (stored.document.sourceBindingDigest === arch.sourceDigest && stored.document.architecture.irDigest === arch.irDigest) {
                    document = stored.document;
                    saved = document.revision;
                    version = stored.revision;
                }
            }
            catch { /* A new source has no saved document yet. */ }
        }
        if (sequence !== loadSequence.current)
            return;
        historyRef.current = createHistory(document);
        setHistory(historyRef.current);
        setStorageRevision(version);
        setSavedVisualRevision(saved);
        setProjectId(null);
        setReview(null);
        localStorage.removeItem(REVIEW);
        setSelection({ kind: 'node', ids: [] });
        setSourceOpen(false);
        setNotice(saved >= 0 ? '已重开保存的画布' : '静态源码已导入；模型未被执行');
        setFailure('');
    }, []);
    const loadExample = useCallback(async (id) => {
        cancelGesture();
        const sequence = ++loadSequence.current;
        setBusy(true);
        setFailure('');
        try {
            const arch = await api.example(id);
            if (sequence !== loadSequence.current)
                return;
            setExampleId(id);
            await openArchitecture(arch, true, sequence);
        }
        catch (error) {
            if (sequence === loadSequence.current)
                setFailure(String(error));
        }
        finally {
            if (sequence === loadSequence.current) {
                setBusy(false);
                setRuntimeCancel(null);
                setCancelling(false);
            }
        }
    }, [openArchitecture, cancelGesture]);
    useEffect(() => {
        let alive = true;
        const sequence = ++loadSequence.current;
        api.capabilities().then(result => { if (alive)
            setCapabilities(result); }).catch(() => { });
        api.examples().then(async (items) => {
            if (!alive || sequence !== loadSequence.current)
                return;
            setExamples(items);
            const requested = new URLSearchParams(window.location.search).get('documentId');
            if (requested) {
                try {
                    const stored = await api.document(requested);
                    if (!alive || sequence !== loadSequence.current)
                        return;
                    const active = JSON.parse(localStorage.getItem(ACTIVE) ?? 'null');
                    const restored = await restoreMatchingPreview(stored.document, active?.documentId === requested ? active.previewCaseId : undefined, sequence);
                    if (!alive || sequence !== loadSequence.current)
                        return;
                    historyRef.current = stored.history ?? createHistory(stored.document);
                    setHistory(historyRef.current);
                    setStorageRevision(stored.revision);
                    setSavedVisualRevision(stored.document.revision);
                    setProjectId(stored.projectId ?? null);
                    setExampleId('');
                    setReview(null);
                    setNotice('已打开指定模型画布');
                    setFailure('');
                    if (restored) {
                        initialModelLoading.current = false;
                        await receivePreviewState(restored);
                    }
                }
                catch (error) {
                    if (alive) {
                        setFailure(`无法打开指定画布：${String(error)}`);
                        setNotice('请核对文档地址与当前运行时');
                    }
                }
                return;
            }
            try {
                const active = JSON.parse(localStorage.getItem(ACTIVE) ?? 'null');
                if (active) {
                    const stored = await api.document(active.documentId).catch(async (error) => {
                        if (!active.previewCaseId)
                            throw error;
                        const snapshot = await previewEngine.current.snapshot();
                        if (snapshot.caseId !== active.previewCaseId || !alive || sequence !== loadSequence.current)
                            throw error;
                        initialModelLoading.current = false;
                        previewCase.current = '';
                        await receivePreviewState(snapshot);
                        setNotice('已从浏览器重开递归预览；可通过编辑 JSON 搬运完整图。');
                        return null;
                    });
                    if (!stored)
                        return;
                    let doc = stored.document;
                    let version = stored.revision;
                    let saved = doc.revision;
                    if (active.projectId) {
                        const project = await api.project(active.projectId);
                        if (project.sourceDigest !== doc.sourceBindingDigest || project.irDigest !== doc.architecture.irDigest) {
                            doc = reconcileDocument(doc, project.architecture).document;
                            version = 0;
                            saved = -1;
                        }
                    }
                    if (!alive || sequence !== loadSequence.current)
                        return;
                    const restored = await restoreMatchingPreview(doc, active.previewCaseId, sequence);
                    if (!alive || sequence !== loadSequence.current)
                        return;
                    historyRef.current = stored.history && doc === stored.document ? stored.history : createHistory(doc);
                    setHistory(historyRef.current);
                    setStorageRevision(version);
                    setSavedVisualRevision(saved);
                    setProjectId(active.projectId);
                    setNotice(active.projectId ? '已重开工作副本及保存的画布' : '已重开保存的画布');
                    if (restored) {
                        initialModelLoading.current = false;
                        await receivePreviewState(restored);
                    }
                    const pending = JSON.parse(localStorage.getItem(REVIEW) ?? 'null');
                    if (pending && pending.projectId === active.projectId) {
                        const transaction = await api.transaction(pending.projectId, pending.id);
                        if (alive && transaction.status !== 'Discarded')
                            setReview({ transaction, base: doc, projectId: pending.projectId });
                    }
                    return;
                }
            }
            catch { /* A missing stored snapshot falls back to an analyzed example. */ }
            if (!alive || sequence !== loadSequence.current)
                return;
            const prior = localStorage.getItem(KEY);
            await loadExample(items.find(x => x.id === prior)?.id ?? items[0]?.id ?? 'transformer');
        }).catch(error => { if (alive) {
            setFailure(`Runtime 未连接：${String(error)}`);
            setNotice('请按 README 启动正式服务');
        } }).finally(() => { if (alive)
            initialModelLoading.current = false; });
        return () => { alive = false; };
    }, [loadExample]);
    useEffect(() => {
        if (!current || authoringOpen || busy || exportDocument || review)
            return;
        let alive = true, inFlight = false;
        const synchronize = async () => {
            if (inFlight || saving.current || openingExport.current || previewLoading.current)
                return;
            const before = historyRef.current;
            if (!before || before.document.id !== current.id)
                return;
            inFlight = true;
            try {
                const saved = await api.document(current.id);
                if (!alive || saved.revision <= storageRevision || historyRef.current !== before)
                    return;
                if (before.document.revision !== savedVisualRevision) {
                    setFailure('同一画布已被其他操作更新；当前未保存编辑保留，请先另存或核对后重开。');
                    return;
                }
                if (saved.document.sourceBindingDigest === before.document.sourceBindingDigest && saved.document.architecture.irDigest === before.document.architecture.irDigest) {
                    if (!readyPreview(before.document))
                        return;
                    const operations = previewDocumentSyncOperations(before.document, saved.document, previewSnapshot.current?.graph, previewSource.current);
                    if (operations.length) {
                        synchronizingPreview.current = true;
                        setPreviewConnecting(true);
                        for (let offset = 0; offset < operations.length; offset += 200) {
                            if (!alive || historyRef.current !== before)
                                return;
                            await previewEngine.current.visual(operations.slice(offset, offset + 200));
                        }
                    }
                    if (!alive || historyRef.current !== before)
                        return;
                    const snapshot = await previewEngine.current.snapshot();
                    if (!alive || historyRef.current !== before || snapshot.caseId !== previewCase.current)
                        return;
                    previewSnapshot.current = snapshot;
                    savedPreviewGraph.current = JSON.stringify(snapshot.graph);
                    setPreviewDirty(false);
                }
                historyRef.current = saved.history ?? createHistory(saved.document);
                setHistory(historyRef.current);
                setStorageRevision(saved.revision);
                setSavedVisualRevision(saved.document.revision);
                synchronizingPreview.current = false;
                if (previewSnapshot.current)
                    await receivePreviewState(previewSnapshot.current);
                setNotice('已同步当前模型的视觉操作与撤销记录');
            }
            catch (error) {
                if (alive && synchronizingPreview.current)
                    setFailure(`外部视觉同步失败，当前预览已保留：${String(error)}`);
            }
            finally {
                synchronizingPreview.current = false;
                setPreviewConnecting(false);
                inFlight = false;
            }
        };
        const timer = setInterval(() => void synchronize(), 2000);
        return () => { alive = false; clearInterval(timer); };
    }, [current?.id, authoringOpen, busy, exportDocument, review, storageRevision, savedVisualRevision]);
    useEffect(() => { if (exampleId)
        localStorage.setItem(KEY, exampleId); }, [exampleId]);
    useEffect(() => { if (current)
        localStorage.setItem(ACTIVE, JSON.stringify({ documentId: current.id, projectId, previewCaseId: previewCase.current })); }, [current?.id, projectId, previewCase.current]);
    function updateDocumentUrl(documentId) {
        const url = new URL(window.location.href);
        url.searchParams.set('documentId', documentId);
        window.history.replaceState(window.history.state, '', url);
    }
    const save = useCallback(async () => {
        if (!historyRef.current || saving.current)
            return;
        if (!readyPreview()) {
            setFailure('预览正在接入当前源码，请完成后再保存。');
            return;
        }
        if (historyRef.current.document.sourceBindingDigest.startsWith('preview-only:')) {
            try {
                await previewEngine.current?.save();
                const snapshot = await previewEngine.current?.snapshot();
                if (snapshot) {
                    await receivePreviewState(snapshot);
                    savedPreviewGraph.current = JSON.stringify(snapshot.graph);
                    if (historyRef.current)
                        await rememberPreviewSave(localStorage, historyRef.current.document, snapshot.graph);
                }
                setPreviewDirty(false);
                setSavedVisualRevision(historyRef.current?.document.revision ?? -1);
                setNotice('当前预览已保存到浏览器；可下载编辑 JSON 搬运完整图。');
                setFailure('');
            }
            catch (error) {
                setFailure(String(error));
            }
            return;
        }
        saving.current = true;
        const sequence = loadSequence.current;
        setBusy(true);
        try {
            await previewEngine.current?.save();
            const snapshot = await previewEngine.current?.snapshot();
            if (sequence !== loadSequence.current)
                return;
            if (snapshot)
                await receivePreviewState(snapshot);
            const frozenHistory = historyRef.current;
            if (!frozenHistory || sequence !== loadSequence.current)
                return;
            const frozen = frozenHistory.document;
            const result = await api.save(frozen, storageRevision, frozenHistory);
            if (sequence !== loadSequence.current || historyRef.current?.document.id !== frozen.id)
                return;
            if (snapshot) {
                savedPreviewGraph.current = JSON.stringify(snapshot.graph);
                await rememberPreviewSave(localStorage, frozen, snapshot.graph);
            }
            setPreviewDirty(false);
            setStorageRevision(result.revision);
            setSavedVisualRevision(frozen.revision);
            updateDocumentUrl(frozen.id);
            setNotice('画布已保存到正式工程 .archcanvas；可重开继续编辑');
            setFailure('');
        }
        catch (error) {
            if (sequence === loadSequence.current)
                setFailure(`保存失败，当前编辑已保留：${String(error)}`);
        }
        finally {
            saving.current = false;
            if (sequence === loadSequence.current)
                setBusy(false);
        }
    }, [storageRevision]);
    useEffect(() => {
        const down = (event) => {
            if (event.defaultPrevented || authoringOpen || editingTarget(event.target) || review || exportDocument || connectionProposal || runtimeOpen || importOpen)
                return;
            if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'z') {
                event.preventDefault();
                event.shiftKey ? redo() : undo();
            }
            if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'y') {
                event.preventDefault();
                redo();
            }
            if ((event.ctrlKey || event.metaKey) && event.key === 'Enter') {
                event.preventDefault();
                previewEngine.current?.command('apply-layout');
            }
            if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 's') {
                event.preventDefault();
                void save();
            }
            if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'a') {
                event.preventDefault();
                previewEngine.current?.command('select-nodes', { scope: 'all' });
            }
            if (event.key === 'Escape') {
                cancelGesture();
                previewEngine.current?.command('select-nodes', { scope: 'clear' });
                setSelection({ kind: 'node', ids: [] });
            }
            if (!event.ctrlKey && !event.metaKey && !event.altKey) {
                if (event.key.toLowerCase() === 'f')
                    fit();
                if (event.key.toLowerCase() === 'v')
                    chooseTool('select');
                if (event.key.toLowerCase() === 'c')
                    chooseTool('connect');
                if (event.key.toLowerCase() === 'b')
                    chooseTool('bend');
            }
        };
        window.addEventListener('keydown', down);
        return () => { window.removeEventListener('keydown', down); };
    }, [fit, redo, save, undo, review, exportDocument, connectionProposal, runtimeOpen, importOpen, cancelGesture, authoringOpen]);
    async function semanticProject(base, sequence) {
        if (base.sourceBindingDigest.startsWith('preview-only:'))
            throw new Error('请先进入编辑模式，从原 Python 建立正式源码绑定。');
        // Save the current presentation before opening a source-bound review.
        if (base.revision !== savedVisualRevision) {
            const saved = await api.save(base, storageRevision);
            if (sequence !== loadSequence.current)
                throw new Error('已切换文档，请重新准备');
            setStorageRevision(saved.revision);
            setSavedVisualRevision(base.revision);
        }
        const project = projectId ?? (await api.register(base.architecture)).id;
        if (sequence !== loadSequence.current)
            throw new Error('已切换文档，请重新准备');
        setProjectId(project);
        return project;
    }
    async function prepareSemantic(prepare) {
        const base = historyRef.current?.document;
        if (!base || busy)
            return;
        const sequence = loadSequence.current;
        setBusy(true);
        setFailure('');
        setReviewError('');
        try {
            const project = await semanticProject(base, sequence);
            const transaction = await prepare(project, base.architecture);
            if (sequence !== loadSequence.current)
                return;
            setReview({ transaction, base, projectId: project });
            localStorage.setItem(REVIEW, JSON.stringify({ projectId: project, id: transaction.id }));
            setNotice(transaction.status === 'ReviewReady' ? '工作副本修改已验证，等待具体审核' : '已保留未通过的事务及原因');
        }
        catch (error) {
            if (sequence === loadSequence.current)
                setFailure(`修改预览失败：${String(error)}`);
        }
        finally {
            if (sequence === loadSequence.current) {
                setBusy(false);
                setRuntimeCancel(null);
                setCancelling(false);
            }
        }
    }
    async function inspectRebind(nodeId, portId) {
        const base = historyRef.current?.document;
        if (!base || busy)
            throw new Error('画布正在处理，请稍后重试');
        const sequence = loadSequence.current;
        setBusy(true);
        setFailure('');
        try {
            const project = await semanticProject(base, sequence);
            if (!inputSpec)
                throw new Error('先设置运行输入与模式；连接操作不会自动降级为静态提交');
            return await api.structuralRebindOptions(project, base.architecture, nodeId, portId, inputSpec);
        }
        finally {
            if (sequence === loadSequence.current)
                setBusy(false);
        }
    }
    async function inspectConfiguration(parameter) {
        const base = historyRef.current?.document;
        if (!base || busy || !selectedNode)
            throw new Error('先选择参数对象');
        const sequence = loadSequence.current;
        setBusy(true);
        try {
            return await api.configurationOptions(await semanticProject(base, sequence), base.architecture, selectedNode.id, parameter);
        }
        finally {
            if (sequence === loadSequence.current)
                setBusy(false);
        }
    }
    function prepareParameter(parameter, value, configuration) {
        if (selectedNode)
            void prepareSemantic((project, architecture) => (configuration ? api.prepareConfiguration : api.prepare)(project, architecture, selectedNode.id, parameter, value));
    }
    function prepareActivation(activation) {
        if (!inputSpec || !selectedNode)
            return;
        void prepareSemantic((project, architecture) => api.prepareActivation(project, architecture, selectedNode.id, activation, inputSpec, cancel => setRuntimeCancel(() => cancel)));
    }
    function prepareRebind(nodeId, portId, producer) {
        if (!inputSpec) {
            setFailure('缺少运行输入与模式，连接提案无法提交');
            return;
        }
        void prepareSemantic((project, architecture) => api.prepareStructuralRebind(project, architecture, nodeId, portId, producer, inputSpec, cancel => setRuntimeCancel(() => cancel)));
    }
    async function cancelRuntime() {
        if (!runtimeCancel || cancelling)
            return;
        setCancelling(true);
        setNotice('正在取消运行验证…');
        try {
            await runtimeCancel();
        }
        catch (error) {
            setFailure(`取消请求失败：${String(error)}`);
            setCancelling(false);
        }
    }
    async function approveParameter() {
        if (!review || busy)
            return;
        setBusy(true);
        setReviewError('');
        try {
            const transaction = await api.approve(review.projectId, review.transaction);
            setReview({ ...review, transaction });
        }
        catch (error) {
            setReviewError(String(error));
        }
        finally {
            setBusy(false);
        }
    }
    async function commitParameter() {
        if (!review || busy)
            return;
        setBusy(true);
        setReviewError('');
        try {
            const transaction = await api.commit(review.projectId, review.transaction);
            setReview({ ...review, transaction });
            if (transaction.status !== 'Committed' || !transaction.committedArchitecture)
                return;
            const prior = historyRef.current?.document ?? review.base;
            const reconciled = reconcileDocument(prior, transaction.committedArchitecture);
            const next = createHistory(reconciled.document);
            if (inputSpec)
                localStorage.setItem(`archcanvas.runtime-profile:${next.document.id}`, JSON.stringify(inputSpec));
            historyRef.current = next;
            setHistory(next);
            setStorageRevision(0);
            setSavedVisualRevision(-1);
            setNotice(`工作副本已提交；保留 ${reconciled.preservedNodeIds.length} 个对象的视觉编辑。源码变更不属于画布撤销。`);
            setExampleId('');
            localStorage.removeItem(REVIEW);
            try {
                const saved = await api.save(next.document, 0);
                setStorageRevision(saved.revision);
                setSavedVisualRevision(next.document.revision);
            }
            catch (error) {
                setReviewError(`源码已提交，画布保存失败；当前编辑仍保留：${String(error)}`);
            }
        }
        catch (error) {
            setReviewError(String(error));
        }
        finally {
            setBusy(false);
        }
    }
    async function closeReview() {
        if (!review || busy)
            return;
        if (['ReviewReady', 'Approved', 'Failed', 'Stale'].includes(review.transaction.status)) {
            setBusy(true);
            try {
                await api.discard(review.projectId, review.transaction.id);
            }
            catch (error) {
                setReviewError(String(error));
                setBusy(false);
                return;
            }
            setBusy(false);
        }
        localStorage.removeItem(REVIEW);
        setReview(null);
        setReviewError('');
    }
    function synchronizePreviewNodeSelection(value) {
        const ids = Array.isArray(value) ? [...new Set(value.filter((id) => typeof id === 'string'))] : [];
        setPreviewSelectedNodeIds(previous => previous.length === ids.length && previous.every((id, index) => id === ids[index]) ? previous : ids);
    }
    function arrangePreview(kind) {
        if (previewLayoutDisabled || !previewCanAlign)
            return;
        setFailure('');
        setActionFeedback(null);
        previewEngine.current?.command('arrange-selection', { kind, scope: layoutMoveScope });
    }
    function pinPreviewSelection() {
        if (previewLayoutDisabled || !previewSelectedNodes.length)
            return;
        setFailure('');
        previewEngine.current?.command('pin-selection', { pinned: !previewAllPinned });
    }
    async function applyInspectionVisual(operations) {
        if (!readyPreview() || previewLayoutDisabled)
            return;
        const sequence = loadSequence.current;
        try {
            await previewEngine.current.visual(operations);
        }
        catch (error) {
            if (sequence === loadSequence.current)
                setFailure(String(error));
        }
    }
    function runCommand() {
        if (!selectedNode || !current) {
            setFailure('先在画布或层级中选择一个节点');
            return;
        }
        const text = command.trim();
        const ops = [];
        const movement = parseMoveCommand(text, selection.ids, layoutMoveScope);
        if (movement.status === 'invalid') {
            setFailure(movement.reason);
            return;
        }
        if (movement.status === 'ready') {
            apply([movement.operation], `文字移动已应用 · ${movement.operation.scope === 'current-frontier' ? '仅当前视图' : '所有视图'}；Ctrl+Z 可撤销。`);
            setCommand('');
            return;
        }
        const colors = { 蓝色: '#dcebf6', 绿色: '#deeee6', 紫色: '#ece3f4', 橙色: '#f4e6d0', 灰色: '#e8ecf0' };
        const color = Object.keys(colors).find(c => text.includes(c));
        const alias = text.match(/(?:命名为|改名为|显示名设为|显示名改为)\s*[“"']?(.+?)[”"']?$/);
        if (color)
            for (const id of selection.ids)
                ops.push({ type: 'nodeStyle', id, style: { fill: colors[color] } });
        if (alias && selection.ids.length !== 1) {
            setFailure('修改显示名称时请选择一个节点。');
            return;
        }
        if (alias)
            ops.push({ type: 'alias', id: selectedNode.id, label: alias[1] });
        if (text.includes('展开') && selectedNode.children.length > 0)
            ops.push({ type: 'expand', id: selectedNode.id, expanded: true });
        if (text.includes('收起') && selectedNode.children.length > 0)
            ops.push({ type: 'expand', id: selectedNode.id, expanded: false });
        if (text.includes('固定'))
            ops.push({ type: 'pin', ids: selection.ids, pinned: !text.includes('取消固定') });
        if (!ops.length) {
            setFailure('本地视觉指令支持：向右移动 24、仅当前视图向下移动 16、设为蓝色/绿色/紫色、命名为…、展开、收起、固定。Dropout 参数请在对象面板预览并审核。');
            return;
        }
        apply(ops, '文字指令已写入同一画布操作历史');
        setCommand('');
    }
    async function importSource() {
        if (busy || previewConnecting || previewBusy) {
            setFailure('请等待当前模型载入或图操作完成后再导入。');
            return;
        }
        cancelGesture();
        const sequence = ++loadSequence.current;
        ++previewSequence.current;
        previewLoading.current = true;
        setPreviewConnecting(true);
        setBusy(true);
        setFailure('');
        try {
            const request = { files: { [filename]: sourceText }, entry, config: {}, semanticMode: 'summary' };
            const bundle = await api.previewAnalyze(request);
            if (sequence !== loadSequence.current)
                return;
            previewSource.current = bundle;
            previewCase.current = bundle.id;
            await previewEngine.current.load(bundle);
            const snapshot = await previewEngine.current.snapshot();
            if (sequence !== loadSequence.current)
                return;
            previewSnapshot.current = snapshot;
            try {
                const arch = await api.previewEditSource(request);
                if (sequence !== loadSequence.current)
                    return;
                if (previewNeedsPanelDocument(snapshot, arch, bundle)) {
                    previewBoundSource.current = '';
                    historyRef.current = createHistory(previewPanelDocument(snapshot, bundle));
                    setHistory(historyRef.current);
                    setProjectId(null);
                    setStorageRevision(0);
                    setSavedVisualRevision(-1);
                    setNotice('递归预览与源码已打开；展示图元可独立编辑，模型编辑使用已解析的源码对象。');
                }
                else {
                    previewBoundSource.current = arch.sourceDigest + ':' + arch.irDigest;
                    await openArchitecture(arch, true, sequence);
                }
            }
            catch (error) {
                if (sequence !== loadSequence.current)
                    return;
                previewBoundSource.current = '';
                historyRef.current = createHistory(previewPanelDocument(snapshot, bundle));
                setHistory(historyRef.current);
                setProjectId(null);
                setStorageRevision(0);
                setSavedVisualRevision(-1);
                setNotice(`递归预览已打开；此源码暂超出现有编辑契约：${String(error)}`);
            }
            if (sequence !== loadSequence.current)
                return;
            previewLoading.current = false;
            await receivePreviewState(snapshot);
            setExampleId('');
            setImportOpen(false);
        }
        catch (error) {
            if (sequence === loadSequence.current)
                setFailure(String(error));
        }
        finally {
            if (sequence === loadSequence.current) {
                previewLoading.current = false;
                setPreviewConnecting(false);
                setBusy(false);
            }
        }
    }
    async function importCanvasJson(text) {
        const value = JSON.parse(text);
        if (['summary-source-adapter/1', 'summary-merge-recursive/1', 'archcanvas-native-semantic/1', 'semantic-canvas/1', 'archcanvas-architecture-document/1', 'semantic-authoring/1', 'archcanvas-source-semantic/2'].includes(value?.schema) || value?.graph?.recursive) {
            await previewEngine.current.load(value);
        }
        else {
            await openArchitecture(validateArchitecture(value));
        }
        setExampleId('');
        setImportOpen(false);
    }
    function focusNode(id) {
        cancelGesture();
        focusPreviewNode(id);
        setSelection({ kind: 'node', ids: [id] });
        setPanel('object');
    }
    function focusAnnotation(id) {
        cancelGesture();
        previewEngine.current?.focus({ annotationId: id });
    }
    function addAnnotation() {
        if (!current || !readyPreview())
            return;
        const id = `annotation-${crypto.randomUUID()}`;
        const raw = previewSnapshot.current?.graph;
        const visible = raw?.nodes?.filter(node => Number.isFinite(node.x) && Number.isFinite(node.y)) ?? [];
        const maxY = visible.length ? Math.max(...visible.map(node => node.y + (node.h ?? 70))) : 40;
        const maxX = visible.length ? Math.max(...visible.map(node => node.x + (node.w ?? 180))) : 40;
        const canvas = raw?.canvas;
        const width = 380, height = 64;
        const x = canvas ? Math.max(12, Math.min(maxX - width, canvas[0] - width - 12)) : Math.max(12, maxX - width);
        const y = canvas ? Math.max(12, Math.min(maxY + 24, canvas[1] - height - 12)) : maxY + 24;
        apply([{ type: 'annotation', annotation: { id, text: '双击模块展开或收起；显示名在右侧对象面板编辑。', x, y, width } }]);
        setSelection({ kind: 'annotation', ids: [id] });
        setPanel('object');
        focusAnnotation(id);
    }
    function moveAnnotationBelow() {
        if (!selectedAnnotation)
            return;
        const graph = previewSnapshot.current?.graph;
        if (!graph)
            return;
        const position = previewAnnotationPosition(graph, selectedAnnotation.id);
        if (position.x !== selectedAnnotation.x || position.y !== selectedAnnotation.y)
            apply([{ type: 'annotation', annotation: { ...selectedAnnotation, ...position } }], '说明已移到图下方；可撤销恢复原位置');
        focusAnnotation(selectedAnnotation.id);
    }
    function zoomCamera(factor) {
        cancelGesture();
        previewEngine.current?.command('zoom', { factor });
    }
    function sourceDraftKey(document) { return sourceAuthoringKey(document); }
    async function cacheGeneratedWorkspace(workspace, binding) {
        const sequence = loadSequence.current;
        try {
            await writePersistentGeneratedWorkspace(workspace, binding);
        }
        catch {
            if (sequence === loadSequence.current)
                setFailure('浏览器未能保留工作区恢复记录；请保存当前草稿与画布。');
        }
    }
    function retainAuthoringWorkspace(workspace) {
        const key = authoringSessionKey.current;
        if (!key)
            return;
        const retained = { ...workspace, viewBaseline: workspace.viewBaseline ?? authoringSessions.current.get(key)?.viewBaseline,
            sourceHistory: { past: historyRef.current?.past.length ?? 0, future: historyRef.current?.future.length ?? 0 } };
        authoringSessions.current.set(key, retained);
        if (retained.draft.sourceProvenance) {
            const sequence = loadSequence.current;
            void writeSourceAuthoringWorkspace(retained).catch(() => {
                if (sequence === loadSequence.current)
                    setFailure('浏览器未能保留源码编辑恢复记录；请保存当前草稿。');
            });
        }
        for (const binding of generatedWorkspaces.current.values())
            if (binding.workspaceKey === key)
                cacheGeneratedWorkspace(retained, binding);
    }
    function openBlankAuthoring() {
        cancelGesture();
        const draft = blankDraft(`draft-${crypto.randomUUID()}`);
        const key = `draft:${draft.id}`;
        const workspace = { draft, storageRevision: 0, savedRevision: -1 };
        authoringSessions.current.set(key, workspace);
        authoringSessionKey.current = key;
        setAuthoringWorkspace(workspace);
        setBrowseBaseline(undefined);
        setAuthoringOpen(true);
    }
    async function continueModelAuthoring() {
        cancelGesture();
        const frozen = historyRef.current?.document;
        if (!frozen || busy)
            return;
        if (frozen.sourceBindingDigest.startsWith('preview-only:')) {
            try {
                await bindPreviewSource(await previewEngine.current.source(), true);
            }
            catch (error) {
                setFailure(`当前源码暂不能进入现有编辑契约：${String(error)}`);
            }
            return;
        }
        const sequence = loadSequence.current, key = sourceDraftKey(frozen);
        let generatedBinding = generatedWorkspaces.current.get(key);
        if (!generatedBinding) {
            const recovered = await readPersistentGeneratedWorkspace(frozen);
            if (sequence !== loadSequence.current || frozen !== historyRef.current?.document)
                return;
            if (recovered) {
                generatedBinding = recovered.binding;
                generatedWorkspaces.current.set(key, generatedBinding);
                authoringSessions.current.set(generatedBinding.workspaceKey, recovered.workspace);
            }
        }
        if (generatedBinding) {
            const workspace = authoringSessions.current.get(generatedBinding.workspaceKey);
            if (workspace) {
                setBusy(true);
                setFailure('');
                try {
                    const view = { selection: selection.kind === 'node' ? selection.ids : [],
                        camera: { ...cameraRef.current }, viewport: readCameraViewport() ?? undefined, tool,
                        sourceHistory: { past: historyRef.current?.past.length ?? 0, future: historyRef.current?.future.length ?? 0 } };
                    const translated = generatedSourceView(workspace, frozen, generatedBinding);
                    const rebased = translated ? await resumeSourceAuthoring(workspace, translated, view, (draft, document, scene) => api.sourceDraftFrontier(draft, document, scene, true)) : workspace;
                    if (sequence !== loadSequence.current || frozen !== historyRef.current?.document)
                        return;
                    const resumed = resumeGeneratedWorkspace(rebased, frozen, generatedBinding, view);
                    authoringSessions.current.set(generatedBinding.workspaceKey, resumed);
                    authoringSessionKey.current = generatedBinding.workspaceKey;
                    cacheGeneratedWorkspace(resumed, generatedBinding);
                    setBrowseBaseline(resumed.draft);
                    setAuthoringWorkspace(resumed);
                    setAuthoringOpen(true);
                    return;
                }
                catch (error) {
                    if (sequence === loadSequence.current)
                        setFailure(String(error));
                    return;
                }
                finally {
                    if (sequence === loadSequence.current)
                        setBusy(false);
                }
            }
        }
        let retained = authoringSessions.current.get(key), recoveredSource = false;
        if (!retained) {
            try {
                const recovered = await readSourceAuthoringWorkspace(frozen);
                if (sequence !== loadSequence.current || frozen !== historyRef.current?.document)
                    return;
                if (recovered) {
                    retained = recovered;
                    recoveredSource = true;
                    authoringSessions.current.set(key, recovered);
                }
            }
            catch (error) {
                if (sequence === loadSequence.current)
                    setFailure(`无法恢复源码编辑副本，原记录与画布已保留：${String(error)}`);
                return;
            }
        }
        if (retained) {
            const sourceView = { selection: recoveredSource ? authoringViewSelection(retained) : selection.kind === 'node' ? selection.ids : [],
                camera: recoveredSource && retained.camera ? { ...retained.camera } : { ...cameraRef.current },
                viewport: recoveredSource ? retained.viewport : readCameraViewport() ?? undefined, tool: recoveredSource ? retained.tool ?? tool : tool,
                sourceHistory: recoveredSource && retained.sourceHistory ? { ...retained.sourceHistory } : { past: historyRef.current?.past.length ?? 0, future: historyRef.current?.future.length ?? 0 } };
            const retainedRevision = retained.draft.sourceProvenance?.visualRevision;
            if (retainedRevision === frozen.revision) {
                const workspace = recoveredSource ? retained : followSourceView(retained, sourceView);
                authoringSessions.current.set(key, workspace);
                authoringSessionKey.current = key;
                setBrowseBaseline(workspace.viewBaseline);
                setAuthoringWorkspace(workspace);
                setAuthoringOpen(true);
                return;
            }
            setBusy(true);
            setFailure('');
            try {
                const workspace = await resumeSourceAuthoring(retained, frozen, sourceView, (draft, document, scene) => api.sourceDraftFrontier(draft, document, scene, true));
                if (sequence !== loadSequence.current || frozen !== historyRef.current?.document)
                    return;
                authoringSessions.current.set(key, workspace);
                authoringSessionKey.current = key;
                setBrowseBaseline(workspace.viewBaseline);
                setAuthoringWorkspace(workspace);
                setAuthoringOpen(true);
                return;
            }
            catch (error) {
                if (sequence === loadSequence.current)
                    setFailure(`源码视图已变化，无法安全重连编辑副本：${String(error)}`);
                return;
            }
            finally {
                if (sequence === loadSequence.current)
                    setBusy(false);
            }
        }
        const conflicting = [...authoringSessions.current.values()].find(workspace => workspace.draft.sourceProvenance?.documentId === frozen.id &&
            (workspace.draft.sourceProvenance.sourceDigest !== frozen.sourceBindingDigest || workspace.draft.sourceProvenance.irDigest !== frozen.architecture.irDigest));
        if (conflicting) {
            setFailure('源码或 IR 摘要已变化；原搭建会话仍保留，请先回到原模型或另建独立草稿。');
            return;
        }
        setBusy(true);
        setFailure('');
        try {
            const imported = await api.importSourceDraft(frozen, buildScene(frozen));
            if (sequence !== loadSequence.current || frozen !== historyRef.current?.document)
                return;
            const workspace = { draft: imported.draft, viewBaseline: structuredClone(imported.draft), storageRevision: 0, savedRevision: -1,
                selection: selection.kind === 'node' ? selection.ids.map(id => imported.sceneNodeBindings[id]).filter(Boolean) : [],
                camera: imported.draft.sourceProvenance?.viewCanvas ? undefined : { ...cameraRef.current },
                viewport: imported.draft.sourceProvenance?.viewCanvas ? undefined : readCameraViewport() ?? undefined, tool,
                sourceHistory: { past: historyRef.current?.past.length ?? 0, future: historyRef.current?.future.length ?? 0 } };
            authoringSessions.current.set(key, workspace);
            authoringSessionKey.current = key;
            setBrowseBaseline(workspace.draft);
            setAuthoringWorkspace(workspace);
            setAuthoringOpen(true);
        }
        catch (error) {
            if (sequence === loadSequence.current)
                setFailure(`无法进入模型编辑，当前画布已保留：${String(error)}`);
        }
        finally {
            if (sequence === loadSequence.current)
                setBusy(false);
        }
    }
    async function editCurrentPreview() {
        if (enteringAuthoring.current || busy || !historyRef.current)
            return;
        if (!readyPreview()) {
            setFailure('预览正在接入当前源码，请完成后再进入模型编辑。');
            return;
        }
        enteringAuthoring.current = true;
        const sequence = loadSequence.current;
        try {
            const snapshot = await previewEngine.current?.snapshot();
            if (sequence !== loadSequence.current)
                return;
            if (snapshot)
                await receivePreviewState(snapshot);
            if (sequence !== loadSequence.current)
                return;
            if (snapshot?.graph?.generic) {
                const edited = await previewEngine.current.author({ action: 'begin' });
                await receivePreviewState(edited);
                setSummaryEditorId(String(edited.caseId));
                setPanel('object');
                setFailure('');
            }
            else
                await continueModelAuthoring();
        }
        catch (error) {
            setFailure(`无法同步当前预览，画布与编辑副本均已保留：${String(error)}`);
        }
        finally {
            enteringAuthoring.current = false;
        }
    }
    async function openSummaryCatalog(model) {
        if (busy || previewBusy || previewConnecting || review)
            throw Error('请先完成当前模型操作。');
        const sequence = ++loadSequence.current;
        ++previewSequence.current;
        previewLoading.current = true;
        setBusy(true);
        setPreviewConnecting(true);
        setFailure('');
        try {
            const document = await loadSummaryCatalogModel(model);
            if (sequence !== loadSequence.current)
                return;
            await previewEngine.current.load(document);
            const snapshot = await previewEngine.current.snapshot();
            if (sequence !== loadSequence.current)
                return;
            previewSource.current = undefined;
            previewBoundSource.current = '';
            previewCase.current = String(snapshot.caseId);
            historyRef.current = createHistory(previewPanelDocument(snapshot));
            setHistory(historyRef.current);
            setSelection({ kind: 'node', ids: [] });
            setProjectId(null);
            setStorageRevision(0);
            setSavedVisualRevision(-1);
            setExampleId('');
            setSummaryEditorId(null);
            setPanel('object');
            previewLoading.current = false;
            await receivePreviewState(snapshot);
            setNotice(`已打开 ${model.title}；保留原始语义与归档证据，本次未执行模型。`);
        }
        finally {
            if (sequence === loadSequence.current) {
                previewLoading.current = false;
                setBusy(false);
                setPreviewConnecting(false);
            }
        }
    }
    async function newSummaryModel() {
        if (busy || previewBusy || review)
            return;
        try {
            const snapshot = await previewEngine.current.author({ action: 'begin', blank: true });
            await receivePreviewState(snapshot);
            setSummaryEditorId(String(snapshot.caseId));
            setPanel('object');
            setFailure('');
        }
        catch (error) {
            setFailure(String(error));
        }
    }
    async function editSummary(operation) {
        const snapshot = await previewEngine.current.author(operation);
        await receivePreviewState(snapshot);
    }
    async function compileSummaryModule(value) {
        const generation = loadSequence.current, caseId = previewCase.current;
        const module = await api.summaryModule(value);
        if (generation !== loadSequence.current || caseId !== previewCase.current)
            throw new Error('模型已切换；源码解析结果未应用。');
        return module;
    }
    async function certifySummaryAssembly(ir) {
        const generation = loadSequence.current, caseId = previewCase.current;
        const result = await api.summaryAssembly(ir);
        if (generation !== loadSequence.current || caseId !== previewCase.current)
            throw new Error('模型已切换；局部复核结果未应用。');
        return result;
    }
    async function formalSourceEditor() {
        try {
            if (previewSnapshot.current?.authoring) {
                const snapshot = await previewEngine.current.author({ action: 'source' });
                await receivePreviewState(snapshot);
                setSummaryEditorId(null);
                await bindPreviewSource(await previewEngine.current.source(), true);
            }
            else
                await continueModelAuthoring();
        }
        catch (error) {
            setFailure(`正式源码工作副本未打开：${String(error)}`);
        }
    }
    async function openPreviewExport() {
        if (openingExport.current || !readyPreview() || busy)
            return;
        const engine = previewEngine.current;
        const sequence = loadSequence.current, generation = previewSequence.current;
        openingExport.current = true;
        setPreviewConnecting(true);
        try {
            const snapshot = await engine.snapshot();
            if (sequence !== loadSequence.current || generation !== previewSequence.current || snapshot.caseId !== previewCase.current)
                throw new Error('模型已切换，请重新打开导出。');
            await receivePreviewState(snapshot);
            const frozen = historyRef.current?.document;
            if (!frozen || !readyPreview(frozen))
                throw new Error('预览与当前源码尚未完成绑定。');
            const signature = JSON.stringify(snapshot.graph), frozenCase = String(snapshot.caseId), sourceDigest = frozen.sourceBindingDigest, irDigest = frozen.architecture.irDigest;
            const assertFrozen = async () => {
                const actual = await engine.snapshot();
                if (sequence !== loadSequence.current || generation !== previewSequence.current || actual.caseId !== frozenCase ||
                    historyRef.current?.document.sourceBindingDigest !== sourceDigest || historyRef.current.document.architecture.irDigest !== irDigest ||
                    JSON.stringify(actual.graph) !== signature)
                    throw new Error('当前预览已变化，请关闭并重新打开导出，以保持图与来源一致。');
            };
            const whole = await engine.svg();
            await assertFrozen();
            const graph = graphFromSnapshot(snapshot);
            const mapped = new Map(), choices = [];
            const bindings = currentPreviewNodeBindings();
            for (const node of graph.nodes) {
                const id = bindings.get(node.id);
                if (!id)
                    continue;
                mapped.set(id, node.id);
                if (node.expanded && frozen.architecture.nodes.find(item => item.id === id)?.children.length) {
                    choices.push({ nodeId: id, pathLabel: frozen.displayAliases[id] ?? node.label ?? id });
                }
            }
            const detailSvg = new Map();
            setExportPreview({ binding: previewExportBinding({ caseId: frozenCase, sourceDigest, irDigest, revision: previewVersion }), detailChoices: choices,
                editingDocument: JSON.stringify(snapshot, null, 2),
                sourcePackage: snapshot.adapter ? JSON.stringify(snapshot.adapter, null, 2) : undefined,
                svg: async (id) => {
                    if (!id)
                        return whole;
                    if (detailSvg.has(id))
                        return detailSvg.get(id);
                    const raw = mapped.get(id);
                    if (!raw)
                        throw new Error('所选详情没有对应的可见预览图元，请先展开并选择该模块。');
                    await assertFrozen();
                    const svg = await engine.svg(raw);
                    await assertFrozen();
                    detailSvg.set(id, svg);
                    return svg;
                } });
            setExportDocument(structuredClone(frozen));
            setFailure('');
        }
        catch (error) {
            setFailure(`无法打开当前预览导出：${String(error)}`);
        }
        finally {
            openingExport.current = false;
            setPreviewConnecting(false);
        }
    }
    async function openGeneratedModel(generated) {
        cancelGesture();
        const workspaceKey = authoringSessionKey.current;
        const workspace = workspaceKey ? authoringSessions.current.get(workspaceKey) : undefined;
        const sequence = ++loadSequence.current;
        const retained = createGeneratedCanvas(generated.architecture, generated.draft, generated, generated.presentationDraft);
        const document = retained.document;
        // Persist the exact generated model and its retained presentation before
        // switching away from the editor. Reload must reopen this generation.
        const opened = await api.open(generated.architecture);
        if (sequence !== loadSequence.current)
            return;
        if (opened.documentId !== document.id)
            throw new Error('新模型画布身份与生成结果不一致；当前编辑已保留。');
        const next = createHistory(document);
        const saved = await api.save(document, opened.revision, next);
        if (sequence !== loadSequence.current)
            return;
        if (workspace && workspaceKey) {
            const binding = { workspaceKey,
                documentId: document.id, sourceDigest: document.sourceBindingDigest, irDigest: document.architecture.irDigest,
                draft: structuredClone(workspace.draft), nodeBindings: { ...generated.nodeBindings, ...generated.containerBindings, ...retained.nodeBindings }, edgeBindings: generated.edgeBindings, visualRevision: document.revision };
            generatedWorkspaces.current.set(sourceDraftKey(document), binding);
            await cacheGeneratedWorkspace(workspace, binding);
        }
        if (sequence !== loadSequence.current)
            return;
        historyRef.current = next;
        setHistory(next);
        setStorageRevision(saved.revision);
        setSavedVisualRevision(document.revision);
        setReview(null);
        localStorage.removeItem(REVIEW);
        setSourceOpen(false);
        setSelection({ kind: 'node', ids: (workspace?.selection ?? []).flatMap(id => retained.nodeBindings[id] ? [retained.nodeBindings[id]] : []) });
        setProjectId(opened.projectId);
        setExampleId('');
        setAuthoringOpen(false);
        updateDocumentUrl(document.id);
        if (workspace?.camera && !workspace.draft.sourceProvenance?.viewCanvas) {
            commitCamera(workspace.camera);
            setTool(workspace.tool ?? 'select');
        }
        setNotice(`已打开新模型工作副本。${retained.hierarchyReflowed ? '新源码层级已重新排布，原草稿布局保留。' : '已保留搭建位置与视角。'}模型未执行。${retained.unmappedNodeIds.length ? ` ${retained.unmappedNodeIds.length} 个展示框没有对应的新源码节点。` : ''}${retained.unresolvedEdgeStyles.length ? ` ${retained.unresolvedEdgeStyles.length} 条连线样式待核对。` : ''}`);
    }
    async function openSourceEditedModel(architecture) {
        cancelGesture();
        const sequence = ++loadSequence.current;
        const opened = await api.open(architecture);
        if (sequence !== loadSequence.current)
            return;
        await openArchitecture(architecture, true, sequence);
        if (sequence !== loadSequence.current)
            return;
        setProjectId(opened.projectId);
        setExampleId('');
        setAuthoringOpen(false);
        updateDocumentUrl(opened.documentId);
        setNotice('已打开源码修改后的独立模型，并重新建立已解析的模型层级；原草稿与原始项目保留。模型未执行。');
    }
    const authoringView = authoringOpen ? _jsx(AuthoringStudio, { initialWorkspace: authoringWorkspace, browseBaseline: browseBaseline, onViewState: retainAuthoringWorkspace, onClose: () => setAuthoringOpen(false), onOpen: openGeneratedModel, onSourceOpen: openSourceEditedModel, onNewBlank: workspace => { retainAuthoringWorkspace(workspace); openBlankAuthoring(); }, onReuseView: async (workspace) => {
            retainAuthoringWorkspace(workspace);
            if (!browseBaseline)
                throw new Error('缺少原视图绑定。');
            if (!sameGeneratedDraft(workspace.draft, browseBaseline)) {
                if (!sameSourceSemantics(workspace.draft, browseBaseline) || !historyRef.current)
                    throw new Error('编辑内容已变化，需要重新生成视图。');
                if (workspace.draft.sourceProvenance?.documentId !== historyRef.current.document.id)
                    return false;
                const operations = sourcePresentationOperations(historyRef.current.document, browseBaseline, workspace.draft);
                if (operations.length) {
                    const before = historyRef.current;
                    await previewEngine.current?.visual(mapPreviewOperations(operations));
                    const next = reduceHistory(before, { type: 'apply', operations });
                    historyRef.current = next;
                    setHistory(next);
                }
            }
            if (workspace.camera && !workspace.draft.sourceProvenance?.viewCanvas)
                commitCamera(workspace.camera);
            const selected = authoringViewSelection(workspace, current ? generatedWorkspaces.current.get(sourceDraftKey(current)) : undefined);
            setSelection({ kind: 'node', ids: selected });
            const focus = selected[0] ? previewNodeId(selected[0]) : undefined;
            if (focus)
                previewEngine.current?.focus({ nodeId: focus });
            setTool(workspace.tool ?? 'select');
            setAuthoringOpen(false);
        } }, authoringSessionKey.current) : null;
    return _jsxs(_Fragment, { children: [_jsxs("div", { className: "studio", hidden: authoringOpen, children: [_jsxs("header", { className: "topbar", children: [_jsxs("div", { className: "brand", children: [_jsxs("span", { className: "brand-mark", children: [_jsx("i", {}), _jsx("i", {}), _jsx("i", {})] }), _jsxs("span", { children: ["ArchCanvas", _jsx("small", { children: "\u6A21\u578B\u67B6\u6784\u5DE5\u4F5C\u53F0" })] })] }), _jsxs("div", { className: "project-breadcrumb", children: [_jsx("span", { className: "slash", children: "/" }), _jsx(Icon, { name: "file", size: 15 }), _jsx("span", { children: current?.title ?? '模型工作台' })] }), _jsxs("div", { className: "header-actions", children: [_jsxs("details", { className: "workspace-menu", children: [_jsxs("summary", { children: ["\u6A21\u578B ", _jsx("span", { children: "\u2304" })] }), _jsxs("div", { children: [_jsxs("button", { disabled: busy || !!review, onClick: () => void newSummaryModel(), children: [_jsx(Icon, { name: "plus", size: 15 }), "\u65B0\u5EFA\u7A7A\u767D\u6A21\u578B"] }), _jsx("button", { disabled: busy || !!review, onClick: openBlankAuthoring, children: "\u65B0\u5EFA\u6B63\u5F0F\u6E90\u7801\u6A21\u578B" }), _jsx("button", { disabled: !current || busy || previewBusy || previewConnecting, onClick: () => void formalSourceEditor(), children: "\u6B63\u5F0F\u6E90\u7801\u5DE5\u4F5C\u526F\u672C" }), _jsxs("button", { disabled: busy || !!review, onClick: () => { setFailure(''); setImportOpen(true); }, children: [_jsx(Icon, { name: "file", size: 15 }), "\u5BFC\u5165 Python \u6E90\u7801"] }), _jsxs("button", { disabled: !current, onClick: () => setSourceOpen(true), children: [_jsx(Icon, { name: "code", size: 15 }), "\u67E5\u770B\u6E90\u7801"] }), _jsxs("label", { className: "menu-field", children: ["\u5185\u7F6E\u793A\u4F8B", _jsxs("select", { "aria-label": "\u793A\u4F8B\u6A21\u578B", value: exampleId, onChange: e => void loadExample(e.target.value), disabled: busy, children: [_jsx("option", { value: "", disabled: true, children: "\u9009\u62E9\u793A\u4F8B" }), examples.map(e => _jsx("option", { value: e.id, children: e.name }, e.id))] })] }), _jsxs("button", { onClick: () => { setSummaryCatalogOpen(true); setRightCollapsed(false); setPanel('object'); }, children: [_jsx(Icon, { name: "layers", size: 15 }), "Summary \u6A21\u578B\u5E93"] }), _jsxs("button", { onClick: () => previewEngine.current?.command("show-library"), children: [_jsx(Icon, { name: "layers", size: 15 }), "\u793A\u4F8B\u4E0E\u6A21\u5757\u5E93"] }), _jsxs("button", { onClick: () => previewEngine.current?.command("show-evidence"), children: [_jsx(Icon, { name: "info", size: 15 }), "\u539F\u578B\u6765\u6E90\u4E0E\u5BA1\u67E5\u8BB0\u5F55"] })] })] }), _jsx(WorkspaceModeSwitch, { mode: summaryEditing ? "edit" : "view", disabled: !current || busy || previewConnecting || previewBusy || !!review, onView: () => setSummaryEditorId(null), onEdit: () => void editCurrentPreview() }), _jsxs("span", { className: `save-state ${dirty ? 'dirty' : ''}`, children: [_jsx("i", {}), current ? dirty ? '有未保存编辑' : '已保存' : '等待文档'] }), _jsxs("button", { onClick: save, disabled: !current || busy || previewConnecting || previewBusy, children: [_jsx(Icon, { name: "save", size: 15 }), "\u4FDD\u5B58"] }), _jsxs("button", { className: "primary", onClick: () => void openPreviewExport(), disabled: !current || busy || previewConnecting || previewBusy, children: [_jsx(Icon, { name: "export", size: 16 }), "\u5BFC\u51FA"] })] })] }), _jsxs("div", { className: `workspace ${leftCollapsed ? 'left-collapsed' : ''} ${rightCollapsed ? 'right-collapsed' : ''}`, children: [_jsxs("aside", { className: "navigator", children: [_jsxs("div", { className: "navigator-top", children: [_jsxs("div", { className: "panel-title", children: [_jsx(Icon, { name: "layers", size: 16 }), _jsx("b", { children: "\u6A21\u578B\u5C42\u7EA7" }), _jsx("span", { children: navigation?.nodes.length ?? architecture?.nodes.length ?? 0 })] }), _jsxs("label", { className: "tree-search", children: [_jsx(Icon, { name: "search", size: 14 }), _jsx("input", { "aria-label": "\u641C\u7D22\u6A21\u578B\u5C42\u7EA7", placeholder: "\u641C\u7D22\u6A21\u5757\u2026", value: treeSearch, onChange: e => setTreeSearch(e.target.value) }), treeSearch && _jsx("button", { className: "tool", "aria-label": "\u6E05\u9664\u5C42\u7EA7\u641C\u7D22", onClick: () => setTreeSearch(''), children: _jsx(Icon, { name: "close", size: 12 }) })] })] }), _jsx("div", { className: "tree", role: "tree", "aria-label": "\u6A21\u578B\u5C42\u7EA7", "aria-multiselectable": "true", children: architecture && current && _jsx(HierarchyTree, { architecture: navigation ?? architecture, document: navigation ?? current, mandatoryIds: navigation?.mandatoryIds, selected: navigation ? previewSelectedNodeIds : selection.ids, onSelect: selectHierarchyNode, onExpand: expandHierarchyNode, query: treeSearch }) }), _jsxs("div", { className: "navigator-bottom", children: [_jsxs("button", { className: sourceOpen ? 'active' : '', onClick: () => setSourceOpen(x => !x), disabled: !current, children: [_jsx(Icon, { name: "code", size: 16 }), "\u67E5\u770B\u6E90\u7801\u8BC1\u636E", _jsx(Icon, { name: "chevron", size: 13 })] }), _jsxs("div", { className: "source-note", children: [_jsx("span", { className: "live-dot" }), previewSnapshot.current?.importedDocument ? '导入文档证据' : '静态源码视图'] })] })] }), _jsxs("main", { className: "main", children: [_jsxs("div", { className: "workspace-caption", children: [_jsx("button", { className: "tool", "aria-label": leftCollapsed ? '展开模型层级面板' : '收起模型层级面板', "aria-pressed": !leftCollapsed, onClick: () => setLeftCollapsed(value => !value), title: "\u6A21\u578B\u5C42\u7EA7\u9762\u677F", children: _jsx(Icon, { name: "panelLeft", size: 16 }) }), _jsx("b", { children: current?.title ?? '模型工作台' }), _jsx("span", { children: summaryEditing ? "Summary 编辑副本" : "预览" }), _jsx("button", { className: "tool", "aria-label": rightCollapsed ? '展开属性面板' : '收起属性面板', "aria-pressed": !rightCollapsed, onClick: () => setRightCollapsed(value => !value), title: "\u5C5E\u6027\u9762\u677F", children: _jsx(Icon, { name: "panelRight", size: 16 }) })] }), _jsxs("div", { className: "canvas-toolbar", role: "toolbar", "aria-label": "\u753B\u5E03\u7F16\u8F91\u5DE5\u5177", children: [_jsxs("div", { className: "tool-group", children: [_jsx("button", { className: `tool ${previewTool === 'select' ? 'selected' : ''}`, title: "\u9009\u62E9 \u00B7 \u5355\u51FB\u9009\u4E2D\uFF1BCtrl / Shift / \u2318 \u70B9\u51FB\u589E\u51CF\u9009\u533A\uFF1B\u62D6\u52A8\u7A7A\u767D\u6846\u9009 \u00B7 V", "aria-label": "\u9009\u62E9\u5BF9\u8C61", "aria-pressed": previewTool === 'select', disabled: previewLayoutDisabled, onClick: () => chooseTool('select'), children: _jsx(Icon, { name: "arrow" }) }), _jsxs("details", { className: "selection-menu", children: [_jsx("summary", { "aria-label": "\u9009\u533A\u64CD\u4F5C", title: "\u9009\u533A\u64CD\u4F5C", children: _jsx(Icon, { name: "chevron", size: 13 }) }), _jsxs("div", { children: [_jsx("div", { className: "menu-heading", children: previewSelectedNodes.length ? `已选 ${previewSelectedNodes.length} 个节点` : '选择对象' }), _jsx("p", { className: "menu-help", children: "\u5355\u51FB\u9009\u62E9\uFF1BCtrl / Shift / \u2318 \u70B9\u51FB\u589E\u51CF\u9009\u533A\uFF0C\u62D6\u52A8\u7A7A\u767D\u5904\u6846\u9009\u3002" }), _jsx("button", { disabled: previewLayoutDisabled || !previewSelectedNodes.length, onClick: () => previewEngine.current?.command('select-nodes', { scope: 'siblings' }), children: "\u9009\u62E9\u540C\u7EA7\u8282\u70B9" }), _jsxs("button", { disabled: previewLayoutDisabled, onClick: () => previewEngine.current?.command('select-nodes', { scope: 'all' }), children: ["\u9009\u62E9\u5168\u90E8\u53EF\u89C1\u6A21\u5757 ", _jsx("kbd", { children: "Ctrl A" })] }), _jsxs("button", { disabled: previewLayoutDisabled || !previewSelectedNodes.length, onClick: () => previewEngine.current?.command('select-nodes', { scope: 'clear' }), children: ["\u6E05\u7A7A\u9009\u533A ", _jsx("kbd", { children: "Esc" })] })] })] }), [{ id: 'connect', icon: 'connect', label: '创建连接', hint: '创建视觉草稿连接 · C' }, { id: 'bend', icon: 'bend', label: '编辑折点', hint: '选择连线，添加或拖动折点 · B' }].map(item => _jsx("button", { title: item.hint, "aria-label": item.label, "aria-pressed": previewTool === item.id, className: `tool ${previewTool === item.id ? 'selected' : ''}`, disabled: !current || busy || previewConnecting || previewBusy, onClick: () => chooseTool(item.id), children: _jsx(Icon, { name: item.icon }) }, item.id)), _jsx("button", { className: `tool ${portEditing ? 'selected' : ''}`, title: "\u663E\u793A\u8282\u70B9\u7AEF\u53E3\uFF1B\u9009\u4E2D\u8FDE\u7EBF\u540E\u53EF\u62D6\u52A8 S / T \u7AEF\u70B9", "aria-label": "\u663E\u793A\u8FDE\u63A5\u70B9", "aria-pressed": portEditing, disabled: !current || busy || previewConnecting || previewBusy, onClick: () => { cancelGesture(); previewEngine.current?.command('show-ports', { visible: !portEditing }); }, children: _jsx(Icon, { name: "ports" }) }), _jsx("span", { className: "tool-divider" }), _jsx("button", { className: "tool", onClick: undo, disabled: !previewUndo || busy || previewConnecting || previewBusy, title: "\u64A4\u9500 Ctrl+Z", "aria-label": "\u64A4\u9500\u753B\u5E03\u7F16\u8F91", children: _jsx(Icon, { name: "undo" }) }), _jsx("button", { className: "tool", onClick: redo, disabled: !previewRedo || busy || previewConnecting || previewBusy, title: "\u91CD\u505A Ctrl+Shift+Z", "aria-label": "\u91CD\u505A\u753B\u5E03\u7F16\u8F91", children: _jsx(Icon, { name: "redo" }) }), _jsx("span", { className: "tool-divider" }), _jsx("button", { className: "tool", "aria-label": "\u5DE6\u5BF9\u9F50\u6240\u9009\u8282\u70B9", onClick: () => arrangePreview('left'), disabled: previewLayoutDisabled || !previewCanAlign, title: "\u5DE6\u5BF9\u9F50 \u00B7 \u9009\u62E9\u540C\u4E00\u5BB9\u5668\u5185\u7684\u4E24\u4E2A\u4EE5\u4E0A\u8282\u70B9", children: _jsx(Icon, { name: "align" }) }), _jsxs("details", { className: "alignment-menu", children: [_jsx("summary", { title: "\u66F4\u591A\u5BF9\u9F50\u4E0E\u5206\u5E03", "aria-label": "\u66F4\u591A\u5BF9\u9F50\u4E0E\u5206\u5E03", children: _jsx(Icon, { name: "chevron", size: 13 }) }), _jsxs("div", { children: [_jsx("div", { className: "menu-heading", children: "\u5BF9\u9F50\u4E0E\u5206\u5E03" }), _jsx("p", { className: "menu-help", children: "\u9009\u62E9\u540C\u7EA7\u8282\u70B9\uFF1B\u81F3\u5C11 2 \u4E2A\u5BF9\u9F50\u30013 \u4E2A\u5206\u5E03\u3002" }), ([{ kind: 'left', label: '左对齐' }, { kind: 'hcenter', label: '水平居中对齐' }, { kind: 'right', label: '右对齐' }, { kind: 'top', label: '顶部对齐' }, { kind: 'vcenter', label: '垂直居中对齐' }, { kind: 'bottom', label: '底部对齐' }, { kind: 'distribute-x', label: '水平等距分布' }, { kind: 'distribute-y', label: '垂直等距分布' }]).map(item => _jsx("button", { disabled: previewLayoutDisabled || !previewCanAlign || (item.kind.startsWith('distribute') && (previewSelectedNodes.length < 3 || previewPinnedCount > 0)), onClick: event => { arrangePreview(item.kind); event.currentTarget.closest('details')?.removeAttribute('open'); }, children: item.label }, item.kind))] })] }), _jsx("button", { className: `tool ${previewAllPinned ? 'selected' : ''}`, "aria-label": previewAllPinned ? '解锁所选节点' : '固定所选节点', "aria-pressed": previewAllPinned, onClick: pinPreviewSelection, disabled: previewLayoutDisabled || !previewSelectedNodes.length, title: previewAllPinned ? '解锁所选节点，恢复直接拖动' : '固定所选节点的直接拖动；子图仍随父容器移动', children: _jsx(Icon, { name: "pin" }) })] }), _jsxs("button", { className: "layout-apply", "aria-label": "Apply layout", title: "\u6309\u5F53\u524D\u5E03\u7EBF\u8BBE\u7F6E\u5E94\u7528\u5E03\u5C40 \u00B7 Ctrl+Enter", disabled: !current || busy || previewConnecting || previewBusy, onClick: () => previewEngine.current?.command('apply-layout'), children: [_jsx(Icon, { name: "bend", size: 16 }), "\u4F18\u5316\u8FDE\u7EBF"] }), _jsxs("div", { className: "tool-group", children: [_jsx("button", { className: `tool ${grid ? 'selected' : ''}`, title: "\u663E\u793A\u70B9\u9635\u7F51\u683C", "aria-label": "\u663E\u793A\u70B9\u9635\u7F51\u683C", "aria-pressed": grid, disabled: previewLayoutDisabled, onClick: () => previewEngine.current?.command('grid', { enabled: !grid }), children: _jsx(Icon, { name: "grid", size: 16 }) }), _jsx("button", { className: "tool", onClick: () => fit(), title: "\u9002\u5408\u753B\u5E03 F", "aria-label": "\u9002\u5408\u753B\u5E03", disabled: previewLayoutDisabled, children: _jsx(Icon, { name: "fit" }) }), _jsxs("details", { className: "canvas-options", children: [_jsx("summary", { "aria-label": "\u753B\u5E03\u9009\u9879", title: "\u753B\u5E03\u9009\u9879", children: _jsx(Icon, { name: "more", size: 16 }) }), _jsxs("div", { children: [_jsx("div", { className: "menu-heading", children: "\u753B\u5E03" }), _jsx("button", { disabled: previewLayoutDisabled, onClick: () => previewEngine.current?.command('show-routing'), children: "\u5E03\u7EBF\u4E0E\u7BAD\u5934\u8BBE\u7F6E" }), _jsx("button", { disabled: previewLayoutDisabled, onClick: () => setSemanticFrontier('overview'), children: "\u67B6\u6784\u6982\u89C8\uFF08F0\uFF09" }), _jsx("button", { disabled: previewLayoutDisabled, onClick: () => setSemanticFrontier('detail'), children: "\u67B6\u6784\u8BE6\u56FE\uFF08F1\uFF09" }), _jsx("button", { disabled: previewLayoutDisabled, onClick: focusCurrentFrontier, children: "\u8FD4\u56DE\u5F53\u524D\u524D\u6CBF" }), _jsx("button", { disabled: previewLayoutDisabled, onClick: () => previewEngine.current?.command('expand-all'), children: "\u5C55\u5F00\u5168\u90E8" }), _jsx("button", { disabled: previewLayoutDisabled, onClick: () => previewEngine.current?.command('collapse-all'), children: "\u6536\u8D77\u5168\u90E8" }), _jsx("button", { disabled: previewLayoutDisabled, onClick: () => { cancelGesture(); previewEngine.current?.command('reset'); }, children: "\u6062\u590D\u521D\u59CB\u89C6\u56FE\uFF08\u53EF\u64A4\u9500\uFF09" })] })] })] })] }), actionFeedback && _jsxs("div", { className: `canvas-feedback ${actionFeedback.error ? 'error' : ''}`, role: actionFeedback.error ? 'alert' : 'status', children: [_jsx(Icon, { name: actionFeedback.error ? 'info' : 'check', size: 15 }), _jsx("span", { children: actionFeedback.message }), _jsx("button", { className: "tool", "aria-label": "\u5173\u95ED\u64CD\u4F5C\u53CD\u9988", onClick: () => setActionFeedback(null), children: _jsx(Icon, { name: "close", size: 13 }) })] }), _jsx("div", { ref: viewportRef, className: "canvas-viewport prototype-canvas", "data-canvas-surface": "recursive-preview", children: _jsx(PreviewStudio, { ref: previewEngine, visible: !authoringOpen, onState: snapshot => void receivePreviewState(snapshot), onSelection: receivePreviewSelection, onEditSource: result => { void bindPreviewSource(result, true).catch(error => setFailure(String(error))); }, onError: message => { setFailure(message); setActionFeedback({ message, error: true }); }, onNotice: (message, error) => { setNotice(message); setFailure(error ? message : ''); setActionFeedback({ message, error }); }, onSave: () => void save() }) }), _jsxs("div", { className: "command-bar", children: [_jsx("span", { className: "command-icon", children: _jsx(Icon, { name: "message", size: 17 }) }), _jsx("input", { disabled: !selectedNode || previewLayoutDisabled, "aria-label": "\u753B\u5E03\u6587\u5B57\u6307\u4EE4", placeholder: selection.ids.length > 1 ? '向右移动 24，或批量设为蓝色…' : selectedNode ? '向右移动 24，或设为蓝色、命名为…' : '选择一个节点，用文字修改画布…', value: command, onChange: e => setCommand(e.target.value), onKeyDown: e => { if (e.key === 'Enter' && !e.nativeEvent.isComposing)
                                                    runCommand(); } }), _jsx("span", { className: "local-label", children: "\u672C\u5730\u89C6\u89C9\u6307\u4EE4" }), _jsxs("button", { onClick: runCommand, disabled: !command.trim() || !selectedNode || previewLayoutDisabled, children: ["\u5E94\u7528 ", _jsx("span", { children: "\u21B5" })] })] }), sourceOpen && architecture && _jsxs("div", { className: "source-drawer", children: [_jsxs("div", { className: "drawer-header", children: [_jsx(Icon, { name: "code", size: 16 }), _jsx("b", { children: "\u6E90\u7801\u8BC1\u636E" }), _jsx("span", { children: previewSourceSpan ? `${previewSourceSpan.path}:${previewSourceSpan.line}` : '只读 · 未执行' }), _jsx("button", { className: "tool", onClick: () => setSourceOpen(false), "aria-label": "\u5173\u95ED\u6E90\u7801", children: _jsx(Icon, { name: "close", size: 16 }) })] }), _jsxs("div", { className: "source-content", children: [current?.sourceBindingDigest.startsWith('preview-only:') && _jsx("p", { className: "field-help", children: "\u53EA\u8BFB\u6E90\u7801\u6587\u672C\u3002\u5C55\u793A\u5BF9\u8C61\u6CA1\u6709\u7ECF\u8FC7\u6B63\u5F0F\u6A21\u578B\u89E3\u6790\u7684\u8BA1\u7B97\u7ED1\u5B9A\uFF1B\u53EF\u5728\u7F16\u8F91\u6A21\u5F0F\u4E2D\u89E3\u6790\u652F\u6301\u7684\u6E90\u7801\u5165\u53E3\u3002" }), !previewSourceSpan && architecture.sources.length > 0 && _jsx("p", { className: "field-help", children: "\u5F53\u524D\u56FE\u5143\u6CA1\u6709\u72EC\u7ACB\u7684\u6E90\u7801\u884C\u8BC1\u636E\uFF0C\u4EE5\u4E0B\u63D0\u4F9B\u5B8C\u6574\u6A21\u578B\u6E90\u7801\u4F9B\u67E5\u9605\u3002" }), architecture.sources.length === 0 && _jsx("p", { className: "field-help", children: previewSnapshot.current?.importedDocument ? '当前为 Summary 导入文档，源码位置尚未与 Python 文本验证绑定；可通过原始文档检查声明证据。' : '当前案例是视觉或路由示例，没有模型源码。' }), architecture.sources.map(source => _jsxs("div", { children: [_jsx("div", { className: "source-filename", children: source.path }), _jsx("pre", { children: source.content.split('\n').map((line, i) => _jsxs("div", { className: previewSourceSpan?.path === source.path && i + 1 >= previewSourceSpan.line && i + 1 <= previewSourceSpan.endLine ? 'source-highlight' : '', children: [_jsx("span", { children: i + 1 }), line || ' '] }, i)) })] }, source.path))] })] })] }), _jsxs("aside", { className: "inspector", children: [_jsxs("div", { className: "inspector-tabs", children: [_jsx("button", { className: panel === 'object' ? 'active' : '', onClick: () => setPanel('object'), children: "\u5BF9\u8C61" }), _jsx("button", { className: panel === 'legend' ? 'active' : '', onClick: () => setPanel('legend'), children: "\u56FE\u4F8B" }), _jsx("button", { className: panel === 'page' ? 'active' : '', onClick: () => setPanel('page'), children: "\u9875\u9762" })] }), _jsxs("div", { className: "inspector-content", children: [panel === 'object' && frontier && _jsxs("details", { className: "inspector-section semantic-frontier", open: true, children: [_jsxs("summary", { children: ["\u8BED\u4E49\u89C6\u56FE", _jsx("span", { className: "read-only", children: "\u9884\u89C8\u524D\u6CBF" })] }), _jsxs("div", { className: "object-heading", children: [_jsx("span", { className: "object-icon", children: _jsx(Icon, { name: "layers", size: 18 }) }), _jsxs("div", { children: [_jsx("h2", { children: frontier.label }), _jsx("span", { children: "\u540C\u4E00\u6E90\u7801\u8BED\u4E49\u56FE\u7684\u53EF\u89C1\u5207\u9762" })] })] }), _jsxs("div", { className: "coordinate-row", children: [_jsxs("label", { children: ["\u8282\u70B9 ", _jsx("output", { children: frontier.visibleNodeCount })] }), _jsxs("label", { children: ["\u8FB9 ", _jsx("output", { children: frontier.visibleEdgeCount })] })] }), _jsxs("p", { className: "field-help", children: ["\u5F53\u524D\u6DF1\u5EA6 ", frontier.depth, " \u00B7 ", frontier.expandableCount ? `还有 ${frontier.expandableCount} 个容器可继续细化。` : '当前前沿已展开到可见层级。'] }), _jsxs("div", { className: "segmented", children: [_jsx("button", { className: frontier.preset === 'overview' ? 'active' : '', disabled: previewLayoutDisabled, onClick: () => setSemanticFrontier('overview'), children: "F0 \u6982\u89C8" }), _jsx("button", { className: frontier.preset === 'detail' ? 'active' : '', disabled: previewLayoutDisabled, onClick: () => setSemanticFrontier('detail'), children: "F1 \u8BE6\u56FE" })] }), _jsx("button", { className: "full-button", disabled: previewLayoutDisabled, onClick: focusCurrentFrontier, children: "\u8FD4\u56DE\u5F53\u524D\u524D\u6CBF" })] }), panel === 'object' && current && _jsxs("details", { className: "inspector-section summary-interaction", children: [_jsxs("summary", { children: ["Summary \u4EA4\u4E92", _jsx("span", { className: "read-only", children: "\u9884\u89C8\u8F85\u52A9" })] }), _jsx("label", { className: "field-label", htmlFor: "preview-interaction-mode", children: "\u62D6\u52A8\u6A21\u5F0F" }), _jsxs("select", { id: "preview-interaction-mode", className: "field-select", value: previewSnapshot.current?.interactionMode === 'realtime' ? 'realtime' : 'compat', disabled: previewLayoutDisabled, onChange: event => previewEngine.current?.command('interaction-mode', { mode: event.target.value }), children: [_jsx("option", { value: "compat", children: "\u517C\u5BB9\u6A21\u5F0F \u00B7 \u91CA\u653E\u540E\u6821\u9A8C" }), _jsx("option", { value: "realtime", children: "\u5B9E\u65F6\u6A21\u5F0F \u00B7 \u62D6\u52A8\u4E2D\u540C\u6B65" })] }), _jsxs("div", { className: "segmented", children: [_jsx("button", { className: previewSnapshot.current?.showGhost ? 'active' : '', disabled: previewLayoutDisabled, onClick: () => previewEngine.current?.command('show-ghost', { enabled: !previewSnapshot.current?.showGhost }), children: "\u4E0A\u6B21\u8DEF\u5F84" }), _jsx("button", { className: previewSnapshot.current?.showObstacles ? 'active' : '', disabled: previewLayoutDisabled, onClick: () => previewEngine.current?.command('show-obstacles', { enabled: !previewSnapshot.current?.showObstacles }), children: "\u5B89\u5168\u8FB9\u754C" })] }), _jsxs("div", { className: "coordinate-row", children: [_jsxs("label", { children: ["\u5FEB\u7167 ", _jsx("output", { children: previewSnapshot.current?.snapshotRevision ?? 0 })] }), _jsxs("label", { children: ["\u6E90\u7801 ", _jsx("output", { children: previewSnapshot.current?.importedDocument ? '文档证据' : previewSourceIdentity?.sourceSha256 ? '已绑定' : '预览' })] })] }), _jsx("button", { className: "full-button", disabled: previewLayoutDisabled, onClick: () => previewEngine.current?.command('show-routing'), children: "\u6253\u5F00\u5E03\u7EBF\u4E0E\u7BAD\u5934\u8BBE\u7F6E" }), _jsx("button", { className: "full-button", disabled: previewLayoutDisabled, onClick: repairSummaryLayout, children: "\u4F18\u5316\u5F53\u524D\u5E03\u7EBF" }), _jsx("button", { className: "full-button", disabled: previewLayoutDisabled || previewSelectedNodeIds.length !== 1, onClick: () => optimizeAutomaticPorts(previewSelectedNodeIds[0], true), children: "\u6062\u590D\u6240\u9009\u81EA\u52A8\u8FDE\u63A5\u70B9" }), _jsx("button", { className: "full-button", disabled: previewLayoutDisabled, onClick: () => previewEngine.current?.command('show-evidence'), children: "\u6253\u5F00\u6E90\u7801\u4E0E\u8BC1\u636E" })] }), panel === 'object' && _jsx(SummaryCatalogPanel, { open: summaryCatalogOpen, onToggle: setSummaryCatalogOpen, disabled: busy || previewBusy || previewConnecting || !!review, onOpen: openSummaryCatalog }), panel === 'object' && summaryEditing && _jsx(SummaryAuthoringPanel, { snapshot: previewSnapshot.current, selected: previewSelectedNodeIds, disabled: previewLayoutDisabled, onEdit: editSummary, onCompile: compileSummaryModule, onCertify: certifySummaryAssembly, onFormal: () => void formalSourceEditor() }), panel === 'object' && _jsx(SummaryViewPanel, { onContinue: () => previewEngine.current?.command('continue-routing'), snapshot: previewSnapshot.current, selectedIds: previewSelectedNodeIds, disabled: previewLayoutDisabled, onCommand: payload => previewEngine.current?.command('semantic-view', payload), onFocus: id => previewEngine.current?.focus({ nodeId: id }) }), panel === 'object' && current && _jsx(SummarySemanticPanel, { source: previewSource.current, selectedIds: previewSelectedNodeIds, onFocus: id => previewEngine.current?.focus({ nodeId: id }), onEvidence: () => previewEngine.current?.command('show-evidence') }), panel === 'object' && previewSelectedNodes.length > 0 && _jsxs("section", { className: "preview-selection-tools", "aria-label": "\u753B\u5E03\u9009\u533A", children: [_jsxs("h3", { children: ["\u5DF2\u9009 ", previewSelectedNodes.length, " \u4E2A\u8282\u70B9", _jsx("span", { children: previewPinnedCount ? `${previewPinnedCount} 个已固定` : '' }), _jsx("button", { className: "tool", "aria-label": "\u6E05\u7A7A\u9009\u533A", onClick: () => previewEngine.current?.command('select-nodes', { scope: 'clear' }), children: _jsx(Icon, { name: "close", size: 13 }) })] }), _jsx("p", { className: "selection-names", title: previewSelectedNodes.map(node => node.label || node.id).join('、'), children: previewSelectedNodes.map(node => node.label || node.id).join('、') }), previewSelectedNodes.length > 1 && _jsx("p", { className: "field-help", children: previewCanAlign ? '使用工具栏的对齐与分布整理所选节点。' : '选区跨越不同容器；选择同级节点后可对齐。' })] }), panel === 'object' && previewSelectedNodes.length <= 1 && inspectionNode && inspectionPresentation && _jsxs(_Fragment, { children: [_jsxs("div", { className: "object-heading", children: [_jsx("span", { className: "object-icon", style: { background: inspectionPresentation.fill }, children: _jsx(Icon, { name: "layers", size: 20 }) }), _jsxs("div", { children: [_jsx("h2", { children: previewPresentation(previewSnapshot.current?.graph)?.nodes?.[inspectionNode.id]?.alias ?? inspectionNode.label ?? inspectionNode.id }), _jsx("span", { children: inspectionNode.semantic?.moduleType ?? inspectionNode.semantic?.kind ?? inspectionNode.kind ?? '检查对象' })] })] }), _jsx("div", { className: "evidence-tag opaque", children: "\u6E90\u7801\u68C0\u67E5 \u00B7 \u89C6\u89C9\u5BF9\u8C61" }), _jsxs("section", { className: "property-section", children: [_jsx("h3", { children: "\u663E\u793A" }), _jsx(TextField, { label: "\u9884\u89C8\u663E\u793A\u540D\u79F0", value: previewPresentation(previewSnapshot.current?.graph)?.nodes?.[inspectionNode.id]?.alias ?? inspectionNode.label ?? inspectionNode.id, onCommit: label => void applyInspectionVisual([{ type: 'alias', id: inspectionNode.id, label }]) }), _jsx("label", { className: "field-label", children: "\u586B\u5145\u989C\u8272" }), _jsx("input", { type: "color", "aria-label": "\u68C0\u67E5\u5BF9\u8C61\u586B\u5145\u989C\u8272", disabled: previewLayoutDisabled || current?.pageSpec.preset === 'monochrome', value: inspectionPresentation.fill, onChange: event => void applyInspectionVisual([{ type: 'nodeStyle', id: inspectionNode.id, style: { fill: event.target.value } }]) }), _jsx("label", { className: "field-label", children: "\u8FB9\u6846\u989C\u8272" }), _jsx("input", { type: "color", "aria-label": "\u68C0\u67E5\u5BF9\u8C61\u8FB9\u6846\u989C\u8272", disabled: previewLayoutDisabled || current?.pageSpec.preset === 'monochrome', value: inspectionPresentation.stroke, onChange: event => void applyInspectionVisual([{ type: 'nodeStyle', id: inspectionNode.id, style: { stroke: event.target.value } }]) })] }), _jsxs("details", { className: "inspector-section", children: [_jsx("summary", { children: "\u6392\u5217\u4E0E\u5C42\u7EA7" }), _jsxs("div", { className: "coordinate-row", children: [_jsxs("label", { children: ["X ", _jsx("output", { children: Math.round(inspectionPresentation.x) })] }), _jsxs("label", { children: ["Y ", _jsx("output", { children: Math.round(inspectionPresentation.y) })] })] }), inspectionExpandable && _jsxs("button", { className: "full-button", disabled: previewLayoutDisabled, onClick: () => void applyInspectionVisual([{ type: 'expand', id: inspectionNode.id, expanded: !inspectionNode.expanded }]), children: [_jsx(Icon, { name: "layers", size: 14 }), inspectionNode.expanded ? '原位收起检查结构' : '原位展开检查结构'] }), _jsx("button", { className: "text-button", onClick: () => previewEngine.current?.focus({ nodeId: inspectionNode.id }), children: "\u805A\u7126\u8FD9\u4E2A\u68C0\u67E5\u5BF9\u8C61" })] }), _jsxs("section", { className: "property-section", children: [_jsx("h3", { children: "\u6E90\u7801\u8BC1\u636E" }), _jsx("p", { className: "field-help", children: inspectionSource ? `${inspectionSource.path}:${inspectionSource.line}–${inspectionSource.endLine}` : '此展示对象没有独立的源码位置。' }), _jsxs("button", { className: "full-button", onClick: () => setSourceOpen(true), children: [_jsx(Icon, { name: "code", size: 14 }), "\u67E5\u770B\u68C0\u67E5\u5BF9\u8C61\u6E90\u7801"] }), _jsx("p", { className: "field-help", children: "\u5C55\u793A\u548C\u5C55\u5F00\u4FDD\u5B58\u5728\u9012\u5F52\u9884\u89C8\u4E2D\u3002\u6B64\u5BF9\u8C61\u6CA1\u6709\u552F\u4E00\u7684\u6B63\u5F0F\u8BA1\u7B97\u7ED1\u5B9A\uFF0C\u53C2\u6570\u6216\u8FDE\u63A5\u6539\u5199\u8BF7\u8FDB\u5165\u6A21\u578B\u7F16\u8F91\uFF1B\u89C6\u89C9\u8C03\u6574\u4E0D\u6539\u53D8\u6A21\u578B\u6E90\u7801\u3002" })] })] }), panel === 'object' && previewSelectedNodes.length <= 1 && selectedNode && current && _jsxs(_Fragment, { children: [_jsxs("div", { className: "object-heading", children: [_jsx("span", { className: "object-icon", style: { background: (selectedPreviewNodePresentation?.fill) }, children: _jsx(Icon, { name: "layers", size: 20 }) }), _jsxs("div", { children: [_jsx("h2", { children: current.displayAliases[selectedNode.id] ?? selectedNode.label }), _jsx("span", { children: selectedNode.kind })] })] }), _jsxs("div", { className: `evidence-tag ${selectedNode.evidence}`, children: [_jsx(Icon, { name: "check", size: 12 }), statusText(selectedNode.evidence)] }), _jsxs("section", { className: "property-section", children: [_jsx("h3", { children: "\u663E\u793A" }), _jsx(TextField, { label: "\u663E\u793A\u540D\u79F0", value: current.displayAliases[selectedNode.id] ?? selectedNode.label, onCommit: label => apply([{ type: 'alias', id: selectedNode.id, label }]) }), _jsxs("p", { className: "field-help", children: ["\u6E90\u540D\u79F0\uFF1A", selectedNode.label] }), _jsx("label", { className: "field-label", children: "\u56FE\u5143\u6837\u5F0F" }), _jsx("select", { className: "field-select", "aria-label": "\u56FE\u5143\u6837\u5F0F", value: current.nodeStyleOverrides[selectedNode.id]?.glyph ?? (selectedPreviewNodePresentation?.glyph) ?? 'module', onChange: e => apply([{ type: 'nodeStyle', id: selectedNode.id, style: { glyph: e.target.value } }]), children: ['module', 'operator', 'tensor', 'attention', 'norm', 'add', 'opaque'].map(g => _jsx("option", { value: g, children: { module: '模块框', operator: '紧凑算子', tensor: '张量条带', attention: 'Attention 图元', norm: '归一化图元', add: '加法图元', opaque: '未知边界' }[g] }, g)) }), _jsx("label", { className: "field-label", children: "\u586B\u5145\u989C\u8272" }), _jsxs("div", { className: "color-palette", children: [PALETTE.map(color => _jsx("button", { "aria-label": `填充 ${color}`, className: (selectedPreviewNodePresentation?.fill) === color ? 'picked' : '', style: { background: color }, onClick: () => apply(selection.ids.map(id => ({ type: 'nodeStyle', id, style: { fill: color } }))) }, color)), _jsx("input", { type: "color", "aria-label": "\u81EA\u5B9A\u4E49\u586B\u5145\u989C\u8272", value: (selectedPreviewNodePresentation?.fill) ?? '#dcebf6', onChange: e => apply(selection.ids.map(id => ({ type: 'nodeStyle', id, style: { fill: e.target.value } }))) })] }), _jsx("label", { className: "field-label", children: "\u8FB9\u6846\u989C\u8272" }), _jsxs("div", { className: "color-field", children: [_jsx("input", { type: "color", "aria-label": "\u8FB9\u6846\u989C\u8272", value: (selectedPreviewNodePresentation?.stroke) ?? '#607d91', onChange: e => apply([{ type: 'nodeStyle', id: selectedNode.id, style: { stroke: e.target.value } }]) }), _jsx("code", { children: (selectedPreviewNodePresentation?.stroke) })] })] }), _jsxs("details", { className: "inspector-section", children: [_jsx("summary", { children: "\u6392\u5217\u4E0E\u5C42\u7EA7" }), _jsxs("div", { className: "coordinate-row", children: [_jsxs("label", { children: ["X ", _jsx("output", { children: Math.round(selectedPreviewNodePresentation?.x ?? 0) })] }), _jsxs("label", { children: ["Y ", _jsx("output", { children: Math.round(selectedPreviewNodePresentation?.y ?? 0) })] })] }), _jsx("label", { className: "field-label", htmlFor: "layout-move-scope", children: "\u79FB\u52A8\u8303\u56F4" }), _jsxs("select", { id: "layout-move-scope", className: "field-select", "aria-label": "\u79FB\u52A8\u8303\u56F4", value: layoutMoveScope, onChange: e => chooseMoveScope(e.target.value), children: [_jsx("option", { value: "all-frontiers", children: "\u6240\u6709\u89C6\u56FE" }), _jsx("option", { value: "current-frontier", children: "\u4EC5\u5F53\u524D\u89C6\u56FE" })] }), _jsxs("p", { className: "field-help", children: ["\u5BF9\u9F50\u548C\u6587\u5B57\u79FB\u52A8\u4F7F\u7528\u6B64\u8303\u56F4\u3002\u5E03\u7EBF\u4F7F\u7528 Summary \u8BBE\u7F6E\u4E2D\u7684\u5904\u7406\u8303\u56F4\u3002", layoutMoveScope === 'current-frontier' ? '调整当前可见前沿；其他层级保留自己的布局。' : '同步调整已保存的展开层级布局。'] }), !!selectedNode.children.length && _jsxs("button", { className: "full-button", disabled: previewLayoutDisabled, onClick: () => apply([{ type: 'expand', id: selectedNode.id, expanded: !current.expandedIds.includes(selectedNode.id) }]), children: [_jsx(Icon, { name: "layers", size: 14 }), current.expandedIds.includes(selectedNode.id) ? '原位收起' : '原位展开'] }), _jsxs("button", { className: "full-button", onClick: repairSummaryLayout, disabled: previewLayoutDisabled, children: [_jsx(Icon, { name: "align", size: 14 }), "\u4F18\u5316\u5F53\u524D\u5E03\u7EBF"] }), _jsx("button", { className: "text-button", onClick: () => focusNode(selectedNode.id), children: "\u805A\u7126\u8FD9\u4E2A\u5BF9\u8C61" })] }), _jsxs("details", { className: "inspector-section", children: [_jsx("summary", { children: "\u8FDE\u63A5\u70B9" }), _jsx("p", { className: "field-help", children: portEditing ? "拖动端口到模块任一边缘。" : "点击“优化自动连接点”比较侧面；使用“显示连接点”查看端口；选中连线后可拖动 S / T 端点。" }), _jsx("button", { className: "full-button", disabled: busy || (!selectedNode.ports.length && !selectedNode.children.length), onClick: () => optimizeAutomaticPorts(selectedNode.id), children: "\u4F18\u5316\u81EA\u52A8\u8FDE\u63A5\u70B9" })] }), _jsx(ParameterEditor, { node: selectedNode, busy: busy, enabled: !current.sourceBindingDigest.startsWith('preview-only:') && !!capabilities?.semanticWriteback, onPrepare: prepareParameter, onInspectConfiguration: inspectConfiguration }), _jsx(ActivationEditor, { node: selectedNode, busy: busy, enabled: !current.sourceBindingDigest.startsWith('preview-only:') && !!capabilities?.supportedIntents?.includes('replace_activation'), inputSpec: inputSpec, onSetup: () => setRuntimeOpen(true), onPrepare: prepareActivation }), _jsx(ObjectFacts, { architecture: current.architecture, node: selectedNode, onSelect: id => { setSelection({ kind: 'node', ids: [id] }); setPanel('object'); } }), selectedNode.ports.some(p => p.direction === 'in') && _jsx(ConnectionEditor, { document: current, nodeId: selectedNode.id, portId: selectedNode.ports.find(p => p.direction === 'in').id, busy: busy, inputSpec: inputSpec, onSetup: () => setRuntimeOpen(true), enabled: !current.sourceBindingDigest.startsWith('preview-only:') && !!capabilities?.supportedIntents?.includes('rebind_input'), onInspect: inspectRebind, onPrepare: prepareRebind }, `${architecture?.sourceDigest}:${selectedNode.id}:${JSON.stringify(inputSpec)}`), _jsxs("details", { className: "inspector-section", children: [_jsxs("summary", { children: ["\u6A21\u578B\u4E8B\u5B9E", _jsx("span", { className: "read-only", children: "\u53EA\u8BFB" })] }), Object.entries(selectedNode.parameters).length ? _jsx("dl", { className: "parameters", children: Object.entries(selectedNode.parameters).map(([name, value]) => _jsxs("div", { children: [_jsx("dt", { children: name }), _jsx("dd", { children: typeof value === 'string' ? value : JSON.stringify(value) })] }, name)) }) : _jsx("p", { className: "field-help", children: "\u6CA1\u6709\u5DF2\u89E3\u6790\u7684\u6784\u9020\u53C2\u6570\u3002" }), _jsxs("button", { className: "full-button", onClick: () => setSourceOpen(true), children: [_jsx(Icon, { name: "code", size: 14 }), "\u67E5\u770B\u6E90\u7801\u4F4D\u7F6E"] })] })] }), panel === 'object' && selectedEdge && current && _jsxs(_Fragment, { children: [_jsxs("div", { className: "object-heading", children: [_jsx(Icon, { name: "arrow" }), _jsxs("div", { children: [_jsx("h2", { children: selectedEdge.label || selectedEdge.role }), _jsxs("span", { children: ["\u5F20\u91CF\u5173\u7CFB \u00B7 ", selectedEdge.role] })] })] }), _jsxs("section", { className: "property-section", children: [_jsx("h3", { children: "\u8FDE\u7EBF\u6837\u5F0F" }), _jsx("label", { className: "field-label", children: "\u989C\u8272" }), _jsx("input", { type: "color", "aria-label": "\u8FDE\u7EBF\u989C\u8272", disabled: current.pageSpec.preset === 'monochrome', value: selectedEdgeAppearance?.stroke ?? '#64748b', onChange: e => apply([{ type: 'edgeStyle', id: selectedEdge.id, style: { stroke: e.target.value } }]) }), current.pageSpec.preset === 'monochrome' && _jsx("p", { className: "field-help", children: "\u9ED1\u767D\u6A21\u5F0F\u7EDF\u4E00\u4F7F\u7528\u7070\u8272\uFF1B\u5DF2\u8BBE\u7F6E\u7684\u989C\u8272\u5728\u8BBA\u6587\u5F69\u8272\u6A21\u5F0F\u751F\u6548\u3002" }), _jsx("label", { className: "field-label", children: "\u7EBF\u5BBD" }), _jsx("input", { "aria-label": "\u8FDE\u7EBF\u5BBD\u5EA6", type: "range", min: "1", max: "4", step: "0.5", value: selectedEdgeAppearance?.width ?? 1.5, onChange: e => apply([{ type: 'edgeStyle', id: selectedEdge.id, style: { width: Number(e.target.value) } }]) }), _jsxs("label", { className: "check-field", children: [_jsx("input", { type: "checkbox", checked: selectedEdgeAppearance?.dashed ?? false, onChange: e => apply([{ type: 'edgeStyle', id: selectedEdge.id, style: { dashed: e.target.checked } }]) }), "\u4F7F\u7528\u865A\u7EBF"] }), selectedEdgeAppearance && _jsxs("p", { className: "field-help", children: ["\u5F53\u524D\u7EBF\u578B\uFF1A", edgePatternLabel(selectedEdgeAppearance), " \u00B7 ", current.edgeStyleOverrides[selectedEdge.id]?.dashed === undefined ? '角色默认' : '用户覆盖', "\u3002\u66F4\u6539\u590D\u9009\u6846\u540E\u4F7F\u7528\u663E\u5F0F\u5B9E\u7EBF\u6216\u901A\u7528\u865A\u7EBF\uFF1B\u53EF\u64A4\u9500\u6700\u8FD1\u7F16\u8F91\u3002"] })] }), _jsxs("section", { className: "property-section", children: [_jsx("h3", { children: "\u5F53\u524D\u7AEF\u53E3\u7ED1\u5B9A" }), _jsxs("p", { className: "field-help", children: [selectedEdge.source.portId, " \u2192 ", selectedEdge.target.portId] }), _jsx("p", { className: "field-help", children: "\u6539\u8D70\u7EBF\u6837\u5F0F\u4E0D\u4F1A\u6539\u53D8\u6A21\u578B\u8BA1\u7B97\u5173\u7CFB\u3002" })] }), _jsx(ConnectionEditor, { document: current, nodeId: selectedEdge.target.nodeId, portId: selectedEdge.target.portId, busy: busy, inputSpec: inputSpec, onSetup: () => setRuntimeOpen(true), enabled: !current.sourceBindingDigest.startsWith('preview-only:') && !!capabilities?.supportedIntents?.includes('rebind_input'), onInspect: inspectRebind, onPrepare: prepareRebind }, `${architecture?.sourceDigest}:${selectedEdge.id}:${JSON.stringify(inputSpec)}`)] }), panel === 'object' && selectedAnnotation && _jsxs(_Fragment, { children: [_jsx("h2", { children: "\u8BF4\u660E\u6587\u5B57" }), _jsx(TextField, { label: "\u5185\u5BB9", value: selectedAnnotation.text, onCommit: text => apply([{ type: 'annotation', annotation: { ...selectedAnnotation, text } }]) }), annotationConflicts.length > 0 && _jsxs("p", { className: "annotation-overlap", role: "status", children: ["\u8BF4\u660E\u6B63\u6587\u4E0E ", annotationConflicts.length, " \u4E2A\u5BF9\u8C61\u91CD\u53E0\u3002\u53EF\u79FB\u5230\u56FE\u4E0B\u65B9\uFF0C\u518D\u68C0\u67E5\u5BFC\u51FA\u3002"] }), _jsxs("button", { className: "full-button", onClick: moveAnnotationBelow, children: [_jsx(Icon, { name: "align", size: 14 }), "\u79FB\u5230\u56FE\u4E0B\u65B9"] }), _jsx("button", { className: "text-button", onClick: () => focusAnnotation(selectedAnnotation.id), children: "\u805A\u7126\u8FD9\u6BB5\u8BF4\u660E" }), _jsx("button", { className: "full-button", onClick: () => { apply([{ type: 'removeAnnotation', id: selectedAnnotation.id }]); setSelection({ kind: 'node', ids: [] }); }, children: "\u79FB\u9664\u8BF4\u660E" })] }), panel === 'object' && selectedPreviewEdge && _jsxs(_Fragment, { children: [_jsxs("div", { className: "object-heading", children: [_jsx(Icon, { name: "arrow" }), _jsxs("div", { children: [_jsx("h2", { children: isPreviewDraftEdge(selectedPreviewEdge) ? '视觉草稿连接' : '预览连接' }), _jsx("span", { children: selectedPreviewEdge.id })] })] }), _jsxs("section", { className: "property-section", children: [_jsx("h3", { children: "\u8FDE\u7EBF\u6837\u5F0F" }), _jsx("label", { className: "field-label", children: "\u989C\u8272" }), _jsx("input", { type: "color", "aria-label": "\u89C6\u89C9\u8FDE\u63A5\u989C\u8272", disabled: busy || current?.pageSpec.preset === 'monochrome', value: selectedPreviewEdgeAppearance?.stroke ?? '#263b4b', onChange: e => void stylePreviewEdge(selectedPreviewEdge.id, { stroke: e.target.value }) }), current?.pageSpec.preset === 'monochrome' && _jsx("p", { className: "field-help", children: "\u9ED1\u767D\u6A21\u5F0F\u7EDF\u4E00\u4F7F\u7528\u7070\u8272\uFF1B\u5DF2\u8BBE\u7F6E\u7684\u989C\u8272\u5728\u8BBA\u6587\u5F69\u8272\u6A21\u5F0F\u751F\u6548\u3002" }), _jsx("label", { className: "field-label", children: "\u7EBF\u5BBD" }), _jsx("input", { "aria-label": "\u89C6\u89C9\u8FDE\u63A5\u5BBD\u5EA6", type: "range", min: "0.5", max: "12", step: "0.1", disabled: busy, value: selectedPreviewEdgeAppearance?.width ?? 2.2, onChange: e => void stylePreviewEdge(selectedPreviewEdge.id, { width: Number(e.target.value) }) }), _jsxs("label", { className: "check-field", children: [_jsx("input", { type: "checkbox", disabled: busy, checked: selectedPreviewEdgeAppearance?.dashed ?? false, onChange: e => void stylePreviewEdge(selectedPreviewEdge.id, { dashed: e.target.checked }) }), "\u4F7F\u7528\u865A\u7EBF"] })] }), _jsxs("section", { className: "property-section", children: [_jsx("h3", { children: "\u5F53\u524D\u89C6\u89C9\u7AEF\u70B9" }), _jsxs("p", { className: "field-help", children: [graphFromSnapshot()?.nodes.find(node => node.id === selectedPreviewEdge.source)?.label ?? selectedPreviewEdge.source, " \u2192 ", graphFromSnapshot()?.nodes.find(node => node.id === selectedPreviewEdge.target)?.label ?? selectedPreviewEdge.target] }), _jsx("p", { className: "field-help", children: "\u8FDE\u63A5\u53CA\u6837\u5F0F\u4FDD\u5B58\u5728\u5F53\u524D\u9884\u89C8\u4E2D\uFF0C\u53EF\u64A4\u9500\u6216\u901A\u8FC7\u7F16\u8F91 JSON \u6062\u590D\u3002\u89C6\u89C9\u8349\u7A3F\u4E0D\u4F1A\u81EA\u52A8\u5199\u5165\u6A21\u578B\u6E90\u7801\u3002" })] })] }), panel === 'object' && !selectedNode && !selectedEdge && !selectedPreviewEdge && !selectedAnnotation && !previewSelectedNodes.length && _jsxs(_Fragment, { children: [_jsxs("div", { className: "inspector-empty", children: [_jsx("div", { className: "empty-symbol", children: _jsx(Icon, { name: "arrow", size: 24 }) }), _jsx("h2", { children: "\u4ECE\u4E00\u4E2A\u5BF9\u8C61\u5F00\u59CB" }), _jsxs("p", { children: ["\u9009\u62E9\u6A21\u5757\u3001\u8FDE\u7EBF\u6216\u8BF4\u660E\u6587\u5B57\uFF0C", _jsx("br", {}), "\u8C03\u6574\u8BBA\u6587\u56FE\u7684\u5448\u73B0\u65B9\u5F0F\u3002"] }), _jsxs("div", { className: "shortcut-line", children: [_jsx("kbd", { children: "\u62D6\u52A8\u7A7A\u767D\u5904" }), " \u6846\u9009\u6A21\u5757"] }), _jsxs("div", { className: "shortcut-line", children: [_jsx("kbd", { children: "Shift / Ctrl" }), " \u591A\u9009\u5BF9\u8C61"] }), _jsxs("div", { className: "shortcut-line", children: [_jsx("kbd", { children: "\u53CC\u51FB" }), " \u5C55\u5F00 / \u6536\u8D77\u6A21\u5757"] })] }), _jsxs("div", { className: "document-summary", children: [_jsx("h3", { children: current?.title ?? 'ArchCanvas' }), _jsxs("div", { children: [_jsx("b", { children: summaryCounts?.nodes ?? architecture?.nodes.length ?? '—' }), _jsx("span", { children: previewSnapshot.current?.importedDocument ? '文档对象' : summaryCounts ? '源码对象' : '事实对象' }), _jsx("b", { children: summaryCounts?.edges ?? architecture?.edges.length ?? '—' }), _jsx("span", { children: summaryCounts ? '依赖关系' : '端口关系' })] })] }), !!architecture?.diagnostics.length && _jsxs("details", { className: "diagnostics", children: [_jsx("summary", { children: previewSnapshot.current?.importedDocument ? '文档导入边界' : summaryCounts ? '正式编辑分析边界' : '分析边界' }), architecture.diagnostics.slice(0, 4).map((d, i) => _jsx("p", { children: d.message }, i))] })] }), panel === 'legend' && current && _jsxs(_Fragment, { children: [_jsxs("div", { className: "panel-heading", children: [_jsx("h2", { children: "\u56FE\u4F8B\u7F16\u8F91" }), _jsx("p", { children: "\u56FE\u4F8B\u5C5E\u4E8E\u753B\u5E03\uFF0C\u968F\u5F53\u524D\u7248\u672C\u4FDD\u5B58\u548C\u5BFC\u51FA\u3002" }), current.pageSpec.preset === 'monochrome' && _jsx("p", { className: "field-help", children: "\u60AC\u6D6E\u56FE\u4F8B\u663E\u793A\u5F53\u524D\u53EF\u89C1\u8FDE\u7EBF\u7684\u89D2\u8272\u4E0E\u5B9E\u9645\u7EBF\u578B\uFF1B\u51FA\u7248\u56FE\u4F8B\u968F\u89C6\u56FE\u548C\u6837\u5F0F\u81EA\u52A8\u66F4\u65B0\u3002" })] }), _jsx("div", { className: "legend-list", children: current.legendItems.map((item, index) => _jsxs("div", { className: "legend-editor", children: [_jsxs("div", { className: "legend-row", children: [_jsx("input", { type: "color", "aria-label": `图例颜色 ${index + 1}`, value: item.color, onChange: e => apply([{ type: 'legend', items: current.legendItems.map(x => x.id === item.id ? { ...x, color: e.target.value } : x) }]) }), _jsx(TextField, { label: "", value: item.label, onCommit: label => apply([{ type: 'legend', items: current.legendItems.map(x => x.id === item.id ? { ...x, label } : x) }]) }), _jsx("button", { className: "tool", "aria-label": `删除图例 ${index + 1}`, onClick: () => apply([{ type: 'legend', items: current.legendItems.filter(x => x.id !== item.id) }]), children: _jsx(Icon, { name: "close", size: 13 }) })] }), _jsxs("div", { className: "legend-controls", children: [_jsx("select", { "aria-label": `图例符号 ${index + 1}`, value: item.glyph, onChange: e => apply([{ type: 'legend', items: current.legendItems.map(x => x.id === item.id ? { ...x, glyph: e.target.value } : x) }]), children: ['module', 'operator', 'tensor', 'attention', 'norm', 'add', 'opaque'].map(g => _jsx("option", { children: g }, g)) }), _jsx("button", { disabled: index === 0, onClick: () => { const items = [...current.legendItems]; [items[index - 1], items[index]] = [items[index], items[index - 1]]; apply([{ type: 'legend', items }]); }, title: "\u4E0A\u79FB", children: "\u2191" }), _jsx("button", { disabled: index === current.legendItems.length - 1, onClick: () => { const items = [...current.legendItems]; [items[index + 1], items[index]] = [items[index], items[index + 1]]; apply([{ type: 'legend', items }]); }, title: "\u4E0B\u79FB", children: "\u2193" })] })] }, item.id)) }), _jsxs("button", { className: "full-button", onClick: () => apply([{ type: 'legend', items: [...current.legendItems, { id: `legend-${crypto.randomUUID()}`, label: '自定义图例', color: '#dcebf6', glyph: 'module' }] }]), children: [_jsx(Icon, { name: "plus", size: 15 }), "\u6DFB\u52A0\u56FE\u4F8B\u6761\u76EE"] })] }), panel === 'page' && current && _jsxs(_Fragment, { children: [_jsxs("div", { className: "panel-heading", children: [_jsx("h2", { children: "\u51FA\u7248\u9875\u9762" }), _jsx("p", { children: "SVG\u3001PDF \u4E0E PNG \u5171\u7528\u5F53\u524D\u753B\u5E03\u573A\u666F\u3002" })] }), _jsxs("section", { className: "property-section", children: [_jsx("label", { className: "field-label", children: "\u7269\u7406\u9875\u5BBD" }), _jsx("div", { className: "segmented", children: [85, 180].map(widthMm => _jsxs("button", { className: current.pageSpec.widthMm === widthMm ? 'active' : '', onClick: () => apply([{ type: 'page', page: { widthMm } }]), children: [widthMm, " mm"] }, widthMm)) }), _jsx("label", { className: "field-label", children: "\u80CC\u666F" }), _jsxs("div", { className: "color-field", children: [_jsx("input", { "aria-label": "\u9875\u9762\u80CC\u666F", type: "color", value: current.pageSpec.background, onChange: e => apply([{ type: 'page', page: { background: e.target.value } }]) }), _jsx("code", { children: current.pageSpec.background })] }), _jsx("label", { className: "field-label", children: "\u914D\u8272" }), _jsxs("div", { className: "segmented", children: [_jsx("button", { className: current.pageSpec.preset === 'paper' ? 'active' : '', onClick: () => apply([{ type: 'page', page: { preset: 'paper' } }]), children: "\u8BBA\u6587\u5F69\u8272" }), _jsx("button", { className: current.pageSpec.preset === 'monochrome' ? 'active' : '', onClick: () => apply([{ type: 'page', page: { preset: 'monochrome' } }]), children: "\u9ED1\u767D" })] })] }), _jsxs("section", { className: "property-section", children: [_jsx("h3", { children: "\u8BF4\u660E\u6587\u5B57" }), _jsxs("button", { className: "full-button", onClick: addAnnotation, children: [_jsx(Icon, { name: "plus", size: 14 }), "\u6DFB\u52A0\u8BF4\u660E\u6587\u5B57"] }), _jsx("p", { className: "field-help", children: "\u4F7F\u7528\u53F3\u4E0A\u89D2\u201C\u5BFC\u51FA\u201D\u751F\u6210 SVG\u3001PDF\u3001PNG \u6216\u5B8C\u6574\u7F16\u8F91 JSON\u3002" })] })] })] }), _jsxs("div", { className: "inspector-footer", children: [_jsx(Icon, { name: "info", size: 14 }), _jsx("span", { children: "\u89C6\u89C9\u7F16\u8F91\u4E0D\u4FEE\u6539\u6A21\u578B\u6E90\u7801" })] })] })] }), _jsxs("footer", { className: `statusbar ${failure ? 'has-error' : ''}`, children: [_jsxs("span", { children: [_jsx("i", { className: busy ? 'busy-dot' : 'live-dot' }), failure || (runtimeCancel ? cancelling ? '正在取消运行验证…' : '正在隔离运行并核对前后结构…' : busy ? '正在处理…' : notice)] }), _jsxs("div", { children: [runtimeCancel && _jsx("button", { disabled: cancelling, onClick: () => void cancelRuntime(), children: cancelling ? '取消中…' : '取消运行验证' }), selection.ids.length > 0 && _jsxs("span", { children: [selection.ids.length, " \u4E2A\u5DF2\u9009"] }), _jsx("span", { children: "RECURSIVE PREVIEW" }), _jsxs("span", { children: ["rev ", current?.revision ?? 0] })] })] }), runtimeOpen && architecture && _jsx(RuntimeProfileDialog, { architecture: architecture, initial: inputSpec, example: exampleId === 'multi_input', onSave: saveInputSpec, onClose: () => setRuntimeOpen(false) }), connectionProposal && _jsx("div", { className: "modal-backdrop", children: _jsxs("div", { className: "runtime-modal connection-proposal", role: "dialog", "aria-modal": "true", "aria-labelledby": "proposal-title", children: [_jsxs("div", { className: "modal-heading", children: [_jsxs("div", { children: [_jsx("div", { className: "eyebrow", children: "CONNECTION PROPOSAL" }), _jsx("h2", { id: "proposal-title", children: connectionProposal.candidate ? '检查改接提案' : '保留未支持的连接提案' })] }), _jsx("button", { className: "tool", "aria-label": "\u5173\u95ED\u8FDE\u63A5\u63D0\u6848", onClick: () => setConnectionProposal(null), children: _jsx(Icon, { name: "close" }) })] }), connectionProposal.candidate ? _jsxs("p", { children: ["\u5C06\u9009\u5B9A\u8F93\u5165\u8FDE\u63A5\u5230 ", _jsx("b", { children: connectionProposal.candidate.variable }), "\u3002\u5F53\u524D\u53EA\u521B\u5EFA\u63D0\u6848\uFF1B\u8FD0\u884C\u9A8C\u8BC1\u540E\u4F1A\u5C55\u793A\u51C6\u786E\u6E90\u7801 diff \u548C\u524D\u540E\u5173\u7CFB\uFF0C\u6279\u51C6\u540E\u624D\u80FD\u63D0\u4EA4\u5DE5\u4F5C\u526F\u672C\u3002"] }) : connectionProposal.blockers.map((blocker, i) => _jsx("p", { children: blocker }, i)), _jsxs("div", { className: "modal-actions", children: [_jsx("button", { onClick: () => setConnectionProposal(null), children: "\u4FDD\u7559\u5F53\u524D\u8FDE\u63A5" }), !inputSpec && _jsx("button", { onClick: () => { setConnectionProposal(null); setRuntimeOpen(true); }, children: "\u8BBE\u7F6E\u8FD0\u884C\u8F93\u5165\u4E0E\u6A21\u5F0F" }), connectionProposal.candidate && _jsx("button", { className: "primary", disabled: busy, onClick: () => { const proposal = connectionProposal; setConnectionProposal(null); prepareRebind(proposal.nodeId, proposal.portId, proposal.candidate.binding); }, children: "\u8FD0\u884C\u9A8C\u8BC1\u5E76\u9884\u89C8\u6E90\u7801\u4FEE\u6539" })] })] }) }), review && _jsx(ReviewDialog, { base: review.base, transaction: review.transaction, busy: busy, error: reviewError, onApprove: () => void approveParameter(), onCommit: () => void commitParameter(), onClose: () => void closeReview() }), exportDocument && exportPreview && _jsx(ExportDialog, { document: exportDocument, capabilities: capabilities, selectedId: selection.kind === 'node' && selection.ids.length === 1 ? selection.ids[0] : undefined, previewExport: exportPreview, onClose: () => { setExportDocument(null); setExportPreview(null); } }), importOpen && _jsx(SourceImportDialog, { entry: entry, filename: filename, source: sourceText, busy: busy, error: failure, onEntry: setEntry, onFilename: setFilename, onSource: setSourceText, onJson: importCanvasJson, onError: setFailure, onAnalyze: () => void importSource(), onClose: () => setImportOpen(false), onProject: () => { setImportOpen(false); previewEngine.current?.command('show-import'); } })] }), authoringView] });
}
function TextField({ label, value, onCommit }) {
    const [draft, setDraft] = useState(value);
    const cancelled = useRef(false);
    useEffect(() => setDraft(value), [value]);
    return _jsxs("label", { className: "text-field", children: [label && _jsx("span", { className: "field-label", children: label }), _jsx("input", { "aria-label": label || '图例文字', value: draft, onChange: e => { cancelled.current = false; setDraft(e.target.value); }, onBlur: () => { if (!cancelled.current && draft !== value)
                    onCommit(draft); cancelled.current = false; }, onKeyDown: e => { if (e.nativeEvent.isComposing)
                    return; if (e.key === 'Enter')
                    e.currentTarget.blur(); if (e.key === 'Escape') {
                    cancelled.current = true;
                    setDraft(value);
                    e.currentTarget.blur();
                } } })] });
}
