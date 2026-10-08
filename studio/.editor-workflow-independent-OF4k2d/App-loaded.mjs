import { jsx as _jsx, jsxs as _jsxs, Fragment as _Fragment } from "react/jsx-runtime";
import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import { flushSync } from 'react-dom';
import { buildScene, createDocument, createHistory, reconcileDocument, reduceHistory, renderSvg, validateArchitecture, presentEditorScene, editorSceneBounds, implicitRootIds } from 'file:///home/fzg/PycharmProjects/ArchCanvas/ArchCanvas_Model_Architecture_Studio/studio/src/core/index.ts';
import { api } from 'file:///home/fzg/PycharmProjects/ArchCanvas/ArchCanvas_Model_Architecture_Studio/studio/src/api.ts';
import { Icon } from 'file:///home/fzg/PycharmProjects/ArchCanvas/ArchCanvas_Model_Architecture_Studio/studio/.editor-workflow-independent-OF4k2d/icons.mjs';
import { ParameterEditor } from 'file:///home/fzg/PycharmProjects/ArchCanvas/ArchCanvas_Model_Architecture_Studio/studio/.editor-workflow-independent-OF4k2d/ParameterEditor.mjs';
import { ActivationEditor } from 'file:///home/fzg/PycharmProjects/ArchCanvas/ArchCanvas_Model_Architecture_Studio/studio/.editor-workflow-independent-OF4k2d/ActivationEditor.mjs';
import { ConnectionEditor } from 'file:///home/fzg/PycharmProjects/ArchCanvas/ArchCanvas_Model_Architecture_Studio/studio/.editor-workflow-independent-OF4k2d/ConnectionEditor.mjs';
import { RuntimeProfileDialog } from 'file:///home/fzg/PycharmProjects/ArchCanvas/ArchCanvas_Model_Architecture_Studio/studio/.editor-workflow-independent-OF4k2d/RuntimeProfileDialog.mjs';
import { ReviewDialog } from 'file:///home/fzg/PycharmProjects/ArchCanvas/ArchCanvas_Model_Architecture_Studio/studio/.editor-workflow-independent-OF4k2d/ReviewDialog.mjs';
import { ExportDialog } from 'file:///home/fzg/PycharmProjects/ArchCanvas/ArchCanvas_Model_Architecture_Studio/studio/.editor-workflow-independent-OF4k2d/ExportDialog.mjs';
import { ObjectFacts } from 'file:///home/fzg/PycharmProjects/ArchCanvas/ArchCanvas_Model_Architecture_Studio/studio/.editor-workflow-independent-OF4k2d/ObjectFacts.mjs';
import { HierarchyTree } from 'file:///home/fzg/PycharmProjects/ArchCanvas/ArchCanvas_Model_Architecture_Studio/studio/.editor-workflow-independent-OF4k2d/HierarchyTree.mjs';
import { studioTelemetry } from 'file:///home/fzg/PycharmProjects/ArchCanvas/ArchCanvas_Model_Architecture_Studio/studio/src/perf.ts';
import { prepareMovePreview, previewMoveScene } from 'file:///home/fzg/PycharmProjects/ArchCanvas/ArchCanvas_Model_Architecture_Studio/studio/src/core/movePreview.ts';
import { beginCameraPan, cameraAtPanInput } from 'file:///home/fzg/PycharmProjects/ArchCanvas/ArchCanvas_Model_Architecture_Studio/studio/src/cameraGesture.ts';
import { canvasDotGrid, clampCanvasZoom, fitCameraToBounds, focusCameraOnPoint, paperTranslation, viewportToWorld, zoomCameraAtPoint } from 'file:///home/fzg/PycharmProjects/ArchCanvas/ArchCanvas_Model_Architecture_Studio/studio/src/cameraProjection.ts';
import { canApplyCameraViewTicket, readCameraView, sameCameraViewDocument, writeCameraView } from 'file:///home/fzg/PycharmProjects/ArchCanvas/ArchCanvas_Model_Architecture_Studio/studio/src/cameraViewState.ts';
import { cameraViewportSize, resizeCameraViewport } from 'file:///home/fzg/PycharmProjects/ArchCanvas/ArchCanvas_Model_Architecture_Studio/studio/src/cameraViewport.ts';
import { edgeAppearance } from 'file:///home/fzg/PycharmProjects/ArchCanvas/ArchCanvas_Model_Architecture_Studio/studio/src/edgeAppearance.ts';
import { edgePatternLabel } from 'file:///home/fzg/PycharmProjects/ArchCanvas/ArchCanvas_Model_Architecture_Studio/studio/src/core/edgePresentation.ts';
import { findAnnotationBodyConflicts, suggestAnnotationPosition } from 'file:///home/fzg/PycharmProjects/ArchCanvas/ArchCanvas_Model_Architecture_Studio/studio/src/core/annotationPlacement.ts';
import { layoutWarnings } from 'file:///home/fzg/PycharmProjects/ArchCanvas/ArchCanvas_Model_Architecture_Studio/studio/src/layoutWarnings.ts';
import { planLayoutRecovery } from 'file:///home/fzg/PycharmProjects/ArchCanvas/ArchCanvas_Model_Architecture_Studio/studio/src/core/layoutRecovery.ts';
import { parseMoveCommand } from 'file:///home/fzg/PycharmProjects/ArchCanvas/ArchCanvas_Model_Architecture_Studio/studio/src/moveCommand.ts';
import { AuthoringStudio } from 'file:///home/fzg/PycharmProjects/ArchCanvas/ArchCanvas_Model_Architecture_Studio/studio/.editor-workflow-independent-OF4k2d/AuthoringStudio.mjs';
import { createGeneratedCanvas } from 'file:///home/fzg/PycharmProjects/ArchCanvas/ArchCanvas_Model_Architecture_Studio/studio/src/generatedCanvas.ts';
import { followSourceView, resumeSourceAuthoring, sourceAuthoringKey } from 'file:///home/fzg/PycharmProjects/ArchCanvas/ArchCanvas_Model_Architecture_Studio/studio/src/sourceAuthoringSession.ts';
import { WorkspaceModeSwitch } from 'file:///home/fzg/PycharmProjects/ArchCanvas/ArchCanvas_Model_Architecture_Studio/studio/.editor-workflow-independent-OF4k2d/WorkspaceModeSwitch.mjs';
import { FloatingLegend } from 'file:///home/fzg/PycharmProjects/ArchCanvas/ArchCanvas_Model_Architecture_Studio/studio/.editor-workflow-independent-OF4k2d/FloatingLegend.mjs';
import { resumeGeneratedWorkspace, generatedSourceView, sameGeneratedDraft, readGeneratedWorkspace, writeGeneratedWorkspace, authoringViewSelection } from 'file:///home/fzg/PycharmProjects/ArchCanvas/ArchCanvas_Model_Architecture_Studio/studio/src/generatedWorkspace.ts';
import { blankDraft } from 'file:///home/fzg/PycharmProjects/ArchCanvas/ArchCanvas_Model_Architecture_Studio/studio/src/authoring.ts';
const PALETTE = ['#dcebf6', '#deeee6', '#f4e6d0', '#ece3f4', '#f5dfe3', '#e8ecf0'];
const KEY = 'archcanvas.active-document.v1';
const ACTIVE = 'archcanvas.active-canvas.v2';
const REVIEW = 'archcanvas.source-review.v1';
function cameraViewIdentity(document) {
    return { documentId: document.id, sourceBindingDigest: document.sourceBindingDigest,
        irDigest: document.architecture.irDigest, visualRevision: document.revision };
}
function cameraSessionStorage() {
    try {
        return sessionStorage;
    }
    catch {
        return null;
    }
}
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
    const [authoringOpen, setAuthoringOpen] = useState(false);
    const [authoringWorkspace, setAuthoringWorkspace] = useState();
    const authoringSessions = useRef(new Map());
    const authoringSessionKey = useRef(null);
    const generatedWorkspaces = useRef(new Map());
    const [browseBaseline, setBrowseBaseline] = useState();
    const [history, setHistory] = useState({ "document": { "schemaVersion": 1, "id": "canvas-architecture-model.AuthoredModel-ace9d329992d-1cd31276", "title": "独立连续工作流", "revision": 0, "sourceBindingDigest": "ace9d329992d50543f1614d535ff23dffd7005d25b1119934ed9bbfc1ddc7e37", "architecture": { "schemaVersion": 1, "id": "architecture:model.AuthoredModel", "label": "AuthoredModel", "sourceDigest": "ace9d329992d50543f1614d535ff23dffd7005d25b1119934ed9bbfc1ddc7e37", "irDigest": "1cd3127635084258c9c82c20a5e56532cc97ba0ec44a196f2df13fe7dec0e42b", "entry": "model:AuthoredModel", "nodes": [{ "id": "input:model.AuthoredModel:node_c96c6d5be8d08a12", "label": "node_c96c6d5be8d08a12", "kind": "Input", "category": "input", "children": [], "ports": [{ "id": "input:model.AuthoredModel:node_c96c6d5be8d08a12:out:node_c96c6d5be8d08a12", "name": "node_c96c6d5be8d08a12", "direction": "out", "role": "data", "ordinal": 0 }], "parameters": {}, "source": { "path": "model.py", "line": 11, "endLine": 13, "expression": "def forward(self, node_c96c6d5be8d08a12):\n        node_7f2fe580edb35154 = self.node_7f2fe580edb35154(node_c96c6d5be8d08a12)\n        return {'output': node_7f2fe580edb35154}" }, "evidence": "source", "parentId": "call:instance:model.AuthoredModel" }, { "id": "call:instance:model.AuthoredModel", "label": "AuthoredModel", "kind": "Module", "category": "container", "children": ["input:model.AuthoredModel:node_c96c6d5be8d08a12", "call:instance:model.AuthoredModel.node_7f2fe580edb35154", "output:model.AuthoredModel:0"], "ports": [{ "id": "call:instance:model.AuthoredModel:in:node_c96c6d5be8d08a12", "name": "node_c96c6d5be8d08a12", "direction": "in", "role": "data", "ordinal": 0 }], "parameters": {}, "source": { "path": "model.py", "line": 6, "endLine": 13, "expression": "class AuthoredModel(nn.Module):\n    def __init__(self):\n        super().__init__()\n        self.node_7f2fe580edb35154 = nn.Linear(in_features=4, out_features=4, bias=True, dtype=torch.float32)\n\n    def forward(self, node_c96c6d5be8d08a12):\n        node_7f2fe580edb35154 = self.node_7f2fe580edb35154(node_c96c6d5be8d08a12)\n        return {'output': node_7f2fe580edb35154}" }, "evidence": "source", "instanceId": "instance:model.AuthoredModel", "callId": "call:instance:model.AuthoredModel" }, { "id": "call:instance:model.AuthoredModel.node_7f2fe580edb35154", "label": "node 7f2fe580edb35154", "kind": "Linear", "category": "linear", "children": [], "ports": [{ "id": "call:instance:model.AuthoredModel.node_7f2fe580edb35154:in:input", "name": "input", "direction": "in", "role": "data", "ordinal": 0 }, { "id": "call:instance:model.AuthoredModel.node_7f2fe580edb35154:out:output", "name": "output", "direction": "out", "role": "data", "ordinal": 0 }], "parameters": { "in_features": 4, "out_features": 4, "bias": true, "dtype": { "expression": "torch.float32", "origin": "unknown" } }, "source": { "path": "model.py", "line": 12, "endLine": 12, "expression": "self.node_7f2fe580edb35154(node_c96c6d5be8d08a12)" }, "evidence": "contract", "parentId": "call:instance:model.AuthoredModel", "instanceId": "instance:model.AuthoredModel.node_7f2fe580edb35154", "callId": "call:instance:model.AuthoredModel.node_7f2fe580edb35154", "parameterOrigins": { "in_features": { "kind": "literal", "path": "model.py", "line": 9, "endLine": 9, "expression": "4", "column": 59, "endColumn": 60 }, "out_features": { "kind": "literal", "path": "model.py", "line": 9, "endLine": 9, "expression": "4", "column": 75, "endColumn": 76 }, "bias": { "kind": "literal", "path": "model.py", "line": 9, "endLine": 9, "expression": "True", "column": 83, "endColumn": 87 }, "dtype": { "kind": "unknown", "path": "model.py", "line": 9, "endLine": 9, "expression": "torch.float32", "column": 95, "endColumn": 108 } } }, { "id": "output:model.AuthoredModel:0", "label": "output", "kind": "Output", "category": "output", "children": [], "ports": [{ "id": "output:model.AuthoredModel:0:in:value", "name": "value", "direction": "in", "role": "data", "ordinal": 0 }], "parameters": {}, "source": { "path": "model.py", "line": 11, "endLine": 13, "expression": "def forward(self, node_c96c6d5be8d08a12):\n        node_7f2fe580edb35154 = self.node_7f2fe580edb35154(node_c96c6d5be8d08a12)\n        return {'output': node_7f2fe580edb35154}" }, "evidence": "source", "parentId": "call:instance:model.AuthoredModel", "outputPath": [{ "kind": "key", "key": "output" }] }], "edges": [{ "id": "edge:0", "source": { "nodeId": "input:model.AuthoredModel:node_c96c6d5be8d08a12", "portId": "input:model.AuthoredModel:node_c96c6d5be8d08a12:out:node_c96c6d5be8d08a12" }, "target": { "nodeId": "call:instance:model.AuthoredModel", "portId": "call:instance:model.AuthoredModel:in:node_c96c6d5be8d08a12" }, "tensorId": "tensor:input:model.AuthoredModel:node_c96c6d5be8d08a12:node_c96c6d5be8d08a12", "role": "data" }, { "id": "edge:1", "source": { "nodeId": "input:model.AuthoredModel:node_c96c6d5be8d08a12", "portId": "input:model.AuthoredModel:node_c96c6d5be8d08a12:out:node_c96c6d5be8d08a12" }, "target": { "nodeId": "call:instance:model.AuthoredModel.node_7f2fe580edb35154", "portId": "call:instance:model.AuthoredModel.node_7f2fe580edb35154:in:input" }, "tensorId": "tensor:input:model.AuthoredModel:node_c96c6d5be8d08a12:node_c96c6d5be8d08a12", "role": "data" }, { "id": "edge:2", "source": { "nodeId": "call:instance:model.AuthoredModel.node_7f2fe580edb35154", "portId": "call:instance:model.AuthoredModel.node_7f2fe580edb35154:out:output" }, "target": { "nodeId": "output:model.AuthoredModel:0", "portId": "output:model.AuthoredModel:0:in:value" }, "tensorId": "tensor:call:instance:model.AuthoredModel.node_7f2fe580edb35154:output", "role": "data" }], "diagnostics": [{ "level": "info", "message": "Static AST subset only. User code was not imported or executed; no inferred shapes or runtime verification. Source editing uses separately reviewed registered transactions." }], "sources": [{ "path": "model.py", "content": "\"\"\"Fresh ArchCanvas authored model; static declarations are not runtime verification.\"\"\"\nimport torch\nfrom torch import nn\n\n\nclass AuthoredModel(nn.Module):\n    def __init__(self):\n        super().__init__()\n        self.node_7f2fe580edb35154 = nn.Linear(in_features=4, out_features=4, bias=True, dtype=torch.float32)\n\n    def forward(self, node_c96c6d5be8d08a12):\n        node_7f2fe580edb35154 = self.node_7f2fe580edb35154(node_c96c6d5be8d08a12)\n        return {'output': node_7f2fe580edb35154}\n", "digest": "e34b58605d64958ea31a4e28b01bb20b939fc94cabdbc6ea5450cdab60ba2113" }] }, "displayAliases": { "input:model.AuthoredModel:node_c96c6d5be8d08a12": "输入", "call:instance:model.AuthoredModel.node_7f2fe580edb35154": "我的投影", "output:model.AuthoredModel:0": "输出" }, "nodeStyleOverrides": {}, "edgeStyleOverrides": {}, "legendItems": [{ "id": "legend:input", "label": "Input", "color": "#eef2f5", "glyph": "tensor" }, { "id": "legend:container", "label": "Container", "color": "#f5f8fc", "glyph": "module" }, { "id": "legend:linear", "label": "Linear", "color": "#e5f1ed", "glyph": "operator" }, { "id": "legend:output", "label": "Output", "color": "#eef2f5", "glyph": "tensor" }], "annotations": [], "pageSpec": { "widthMm": 180, "background": "#ffffff", "preset": "paper" }, "expandedIds": ["call:instance:model.AuthoredModel"], "layout": { "call:instance:model.AuthoredModel": { "x": -558, "y": -322, "width": 1010, "height": 762 }, "input:model.AuthoredModel:node_c96c6d5be8d08a12": { "x": 28, "y": 62, "width": 194, "height": 62 }, "call:instance:model.AuthoredModel.node_7f2fe580edb35154": { "x": 398, "y": 362, "width": 194, "height": 62 }, "output:model.AuthoredModel:0": { "x": 788, "y": 672, "width": 194, "height": 62 } }, "layoutByFrontier": {}, "pinnedObjects": [] }, "past": [], "future": [] });
    const [examples, setExamples] = useState([]);
    const [exampleId, setExampleId] = useState('');
    const [selection, setSelection] = useState({ kind: 'node', ids: [] });
    const [camera, setCamera] = useState({ x: 35, y: 35, zoom: 0.9 });
    const [tool, setTool] = useState('select');
    const [layoutMoveScope, setLayoutMoveScope] = useState('all-frontiers');
    const [isPanning, setIsPanning] = useState(false);
    const [preview, setPreview] = useState(null);
    const [recoveryPreview, setRecoveryPreview] = useState(null);
    const [box, setBox] = useState(null);
    const [panel, setPanel] = useState('object');
    const [sourceOpen, setSourceOpen] = useState(false);
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
    const [inline, setInline] = useState(null);
    const [capabilities, setCapabilities] = useState(null);
    const [projectId, setProjectId] = useState(null);
    const [review, setReview] = useState(null);
    const [reviewError, setReviewError] = useState('');
    const [exportDocument, setExportDocument] = useState(null);
    const [inputSpec, setInputSpec] = useState(null);
    const [runtimeOpen, setRuntimeOpen] = useState(false);
    const [runtimeCancel, setRuntimeCancel] = useState(null);
    const [cancelling, setCancelling] = useState(false);
    const [portDraft, setPortDraft] = useState(null);
    const portRequest = useRef(0);
    const portGesture = useRef(null);
    const [connectionProposal, setConnectionProposal] = useState(null);
    const viewportRef = useRef(null);
    const gesture = useRef(null);
    const space = useRef(false);
    const fileRef = useRef(null);
    const inlineCancelled = useRef(false);
    const historyRef = useRef(history);
    historyRef.current = history;
    const cameraRef = useRef(camera);
    cameraRef.current = camera;
    const loadSequence = useRef(0);
    const saving = useRef(false);
    const frame = useRef(0);
    const cameraOwner = useRef(null);
    const cameraIntent = useRef(0);
    const cameraInitializationFrame = useRef(0);
    const pendingCameraInitialization = useRef(null);
    // The size against which cameraRef's translation is defined. DOM dimensions
    // can change before an observer or terminal gesture has coordinated them.
    const cameraViewport = useRef(null);
    const current = history?.document;
    const committedScene = useMemo(() => current ? buildScene(current) : null, [current]);
    const activeRecovery = recoveryPreview && recoveryPreview.document === current && selection.kind === 'node' && selection.ids.length === 1 && selection.ids[0] === recoveryPreview.plan.id ? recoveryPreview : null;
    const scene = useMemo(() => { const result = activeRecovery ? activeRecovery.plan.scene : preview && preview.document === current ? previewMoveScene(preview.session, preview.dx, preview.dy) : committedScene; return result ? presentEditorScene(result) : null; }, [current, committedScene, preview, activeRecovery]);
    const markup = useMemo(() => scene ? renderSvg(scene, { interactive: true, background: false, presentation: 'editor' }) : '', [scene]);
    const implicitRoots = useMemo(() => scene ? implicitRootIds(scene) : new Set(), [scene]);
    const architecture = current?.architecture;
    const selectedNode = selection.kind === 'node' ? architecture?.nodes.find(n => n.id === selection.ids[0]) : undefined;
    const selectedEdge = selection.kind === 'edge' ? architecture?.edges.find(n => n.id === selection.ids[0]) : undefined;
    const selectedEdgeAppearance = selectedEdge && current && scene ? edgeAppearance(current, selectedEdge.id, scene) : undefined;
    const selectedAnnotation = selection.kind === 'annotation' ? current?.annotations.find(n => n.id === selection.ids[0]) : undefined;
    const selectedSceneNode = scene?.nodes.find(n => n.id === selectedNode?.id);
    const selectedSceneAnnotation = scene?.annotations.find(n => n.id === selectedAnnotation?.id);
    const annotationConflicts = scene && selectedSceneAnnotation ? findAnnotationBodyConflicts(scene, selectedSceneAnnotation) : [];
    const paperPosition = scene ? paperTranslation(camera, scene.bounds) : null;
    const dotGrid = canvasDotGrid(camera);
    const dirty = !!current && current.revision !== savedVisualRevision;
    const layoutGuidance = layoutWarnings(scene);
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
    useEffect(() => { document.querySelector('file:///home/fzg/PycharmProjects/ArchCanvas/ArchCanvas_Model_Architecture_Studio/studio/src/.inspector-content/index.ts')?.scrollTo({ top: 0 }); }, [selection.ids[0], panel]);
    useEffect(() => { setRecoveryPreview(null); }, [selection]);
    function readCameraViewport() {
        return cameraViewportSize(viewportRef.current?.getBoundingClientRect());
    }
    function persistCamera(document = historyRef.current?.document, view = cameraRef.current) {
        if (gesture.current?.type === 'pan')
            return;
        const viewport = cameraViewport.current;
        if (!document || !viewport || !sameCameraViewDocument(cameraOwner.current, cameraViewIdentity(document)))
            return;
        writeCameraView(cameraSessionStorage(), cameraViewIdentity(document), view, viewport);
    }
    function claimCamera(document = historyRef.current?.document) {
        cancelAnimationFrame(cameraInitializationFrame.current);
        cameraInitializationFrame.current = 0;
        pendingCameraInitialization.current = null;
        cameraIntent.current++;
        cameraOwner.current = document ? cameraViewIdentity(document) : null;
    }
    function claimGestureCamera() {
        const document = historyRef.current?.document;
        if (!document || sameCameraViewDocument(cameraOwner.current, cameraViewIdentity(document)))
            return;
        // An early spatial gesture adopts the view actually under the pointer.
        // A delayed load restore must not move that mapping after its commit.
        claimCamera(document);
        cameraViewport.current = readCameraViewport();
        persistCamera(document);
    }
    const commitCamera = useCallback((view, document = historyRef.current?.document) => {
        if (!document)
            return;
        claimCamera(document);
        cameraViewport.current = readCameraViewport();
        cameraRef.current = view;
        setCamera(view);
        persistCamera(document, view);
    }, []);
    function synchronizeCameraViewport() {
        // Freeze the original pointer mapping until its final sample or rollback.
        if (gesture.current || portGesture.current)
            return;
        const document = historyRef.current?.document, viewport = readCameraViewport();
        if (!document || !viewport)
            return;
        if (!sameCameraViewDocument(cameraOwner.current, cameraViewIdentity(document))) {
            const pending = pendingCameraInitialization.current;
            if (pending && !canApplyCameraViewTicket(pending.ticket, cameraViewIdentity(document), loadSequence.current, cameraIntent.current)) {
                pendingCameraInitialization.current = null;
            }
            else if (pending && !cameraInitializationFrame.current && viewport.width > 96 && viewport.height > 92) {
                // A previously hidden/unmounted viewport can recover when it becomes
                // usable. Keep retries bounded while preserving the original intent.
                initializeCamera(document, pending.ticket.loadSequence, pending.restore);
            }
            return;
        }
        const previous = cameraViewport.current;
        if (!previous) {
            cameraViewport.current = viewport;
            return;
        }
        const view = resizeCameraViewport(cameraRef.current, previous, viewport);
        if (!view || view === cameraRef.current)
            return;
        cameraViewport.current = viewport;
        cameraRef.current = view;
        setCamera(view);
        persistCamera(document, view);
    }
    useLayoutEffect(() => {
        const viewport = viewportRef.current;
        if (!viewport)
            return;
        synchronizeCameraViewport();
        let active = true;
        const resized = () => {
            if (!active || viewport !== viewportRef.current)
                return;
            // ResizeObserver runs before paint. Commit the matching translation in
            // this delivery, rather than leaving one frame at the old viewport size.
            flushSync(() => synchronizeCameraViewport());
        };
        if (typeof ResizeObserver !== 'undefined') {
            const observer = new ResizeObserver(resized);
            observer.observe(viewport);
            return () => { active = false; observer.disconnect(); };
        }
        window.addEventListener('resize', resized);
        return () => { active = false; window.removeEventListener('resize', resized); };
    }, [authoringOpen]);
    useEffect(() => { persistCamera(); }, [current?.id, current?.revision, current?.sourceBindingDigest, current?.architecture.irDigest]);
    const cancelGesture = useCallback(() => {
        const active = gesture.current;
        const pointerId = active?.pointerId ?? portGesture.current?.pointerId;
        // Clear ownership before releasing capture: lostpointercapture is synchronous.
        gesture.current = null;
        portGesture.current = null;
        portRequest.current++;
        cancelAnimationFrame(frame.current);
        frame.current = 0;
        setPreview(null);
        setRecoveryPreview(null);
        setBox(null);
        setPortDraft(null);
        setIsPanning(false);
        if (active?.type === 'pan') {
            cameraRef.current = active.camera;
            setCamera(active.camera);
        }
        synchronizeCameraViewport();
        if (active?.type === 'pan')
            persistCamera();
        const viewport = viewportRef.current;
        if (pointerId !== undefined && viewport?.hasPointerCapture(pointerId))
            viewport.releasePointerCapture(pointerId);
    }, []);
    function chooseTool(next) { cancelGesture(); setTool(next); }
    function chooseMoveScope(next) { cancelGesture(); setLayoutMoveScope(next); }
    useEffect(() => {
        const blur = () => { space.current = false; cancelGesture(); };
        window.addEventListener('blur', blur);
        return () => { window.removeEventListener('blur', blur); cancelAnimationFrame(frame.current); cancelAnimationFrame(cameraInitializationFrame.current); };
    }, [cancelGesture]);
    useEffect(() => { if (review || exportDocument || importOpen || connectionProposal || runtimeOpen)
        cancelGesture(); }, [review, exportDocument, importOpen, connectionProposal, runtimeOpen, cancelGesture]);
    const apply = useCallback((operations, message) => {
        cancelGesture();
        const interaction = studioTelemetry.beginInteraction(`visual:${operations.map(operation => operation.type === 'expand' && !operation.expanded ? 'collapse' : operation.type).join('+') || 'noop'}`);
        try {
            const previous = historyRef.current;
            if (!previous)
                return;
            const next = reduceHistory(previous, { type: 'apply', baseRevision: previous.document.revision, operations });
            historyRef.current = next;
            setHistory(next);
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
    const selectHierarchyNode = useCallback((id) => { setSelection({ kind: 'node', ids: [id] }); setPanel('object'); }, []);
    const expandHierarchyNode = useCallback((id, expanded) => apply([{ type: 'expand', id, expanded }]), [apply]);
    const undo = useCallback(() => { cancelGesture(); setHistory(p => p ? reduceHistory(p, { type: 'undo' }) : p); setNotice('已撤销一次画布操作'); }, [cancelGesture]);
    const redo = useCallback(() => { cancelGesture(); setHistory(p => p ? reduceHistory(p, { type: 'redo' }) : p); setNotice('已重做一次画布操作'); }, [cancelGesture]);
    function previewPositionRecovery() {
        cancelGesture();
        const document = historyRef.current?.document;
        if (!document || selection.kind !== 'node' || selection.ids.length !== 1)
            return;
        try {
            const plan = planLayoutRecovery(document, selection.ids[0], layoutMoveScope);
            if (plan.status !== 'ready') {
                setNotice(plan.reason);
                return;
            }
            setRecoveryPreview({ document, plan });
            setNotice('正在预览位置修复；应用后才会写入画布，可一次撤销。');
        }
        catch (error) {
            setFailure(String(error));
        }
    }
    function applyPositionRecovery() {
        const value = activeRecovery;
        if (!value || value.document !== historyRef.current?.document) {
            cancelGesture();
            return;
        }
        apply([value.plan.operation], '位置修复已应用；Ctrl+Z 可一次撤销。');
    }
    const initializeCamera = useCallback((document, sequence, restore = true) => {
        cancelAnimationFrame(cameraInitializationFrame.current);
        cameraOwner.current = null;
        const ticket = { identity: cameraViewIdentity(document), loadSequence: sequence, intentSequence: cameraIntent.current };
        const request = { ticket, restore };
        pendingCameraInitialization.current = request;
        const schedule = (attempt) => {
            cameraInitializationFrame.current = requestAnimationFrame(() => {
                cameraInitializationFrame.current = 0;
                const active = historyRef.current?.document;
                // createHistory clones its input; the load/revision/identity ticket is
                // the ownership contract, not the raw loader object's reference.
                if (!active || !canApplyCameraViewTicket(ticket, cameraViewIdentity(active), loadSequence.current, cameraIntent.current)) {
                    if (pendingCameraInitialization.current === request)
                        pendingCameraInitialization.current = null;
                    return;
                }
                if (gesture.current || portGesture.current)
                    return;
                const rect = viewportRef.current?.getBoundingClientRect();
                if (!rect || rect.width <= 96 || rect.height <= 92) {
                    if (attempt < 3)
                        schedule(attempt + 1);
                    return;
                }
                const viewport = { width: rect.width, height: rect.height };
                const recovered = restore ? readCameraView(cameraSessionStorage(), ticket.identity, viewport) : null;
                const view = recovered ?? fitCameraToBounds(editorSceneBounds(buildScene(active)), viewport);
                pendingCameraInitialization.current = null;
                cameraOwner.current = ticket.identity;
                cameraViewport.current = viewport;
                cameraRef.current = view;
                setCamera(view);
                persistCamera(active, view);
            });
        };
        schedule(0);
    }, []);
    const fit = useCallback((documentToFit) => {
        cancelGesture();
        const doc = documentToFit ?? historyRef.current?.document;
        if (!doc || !viewportRef.current)
            return;
        const interaction = studioTelemetry.beginInteraction('fit-canvas');
        try {
            const bounds = editorSceneBounds(buildScene(doc));
            const { width, height } = viewportRef.current.getBoundingClientRect();
            if (width <= 96 || height <= 92)
                return;
            commitCamera(fitCameraToBounds(bounds, { width, height }), doc);
        }
        finally {
            studioTelemetry.endInteraction(interaction);
        }
    }, [cancelGesture, commitCamera]);
    const openArchitecture = useCallback(async (arch, restore = true, requestSequence, initializeView = true) => {
        const sequence = requestSequence ?? ++loadSequence.current;
        if (sequence !== loadSequence.current)
            return;
        cameraOwner.current = null;
        cameraIntent.current++;
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
        setPreview(null);
        setSourceOpen(false);
        setNotice(saved >= 0 ? '已重开保存的画布' : '静态源码已导入；模型未被执行');
        setFailure('');
        if (initializeView)
            initializeCamera(document, sequence, restore);
    }, [initializeCamera]);
    const loadExample = useCallback(async (id) => {
        cancelGesture();
        const sequence = ++loadSequence.current;
        cameraOwner.current = null;
        cameraIntent.current++;
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
        cameraOwner.current = null;
        cameraIntent.current++;
        api.capabilities().then(result => { if (alive)
            setCapabilities(result); }).catch(() => { });
        api.examples().then(async (items) => {
            if (!alive || sequence !== loadSequence.current)
                return;
            setExamples(items);
            try {
                const active = JSON.parse(localStorage.getItem(ACTIVE) ?? 'null');
                if (active) {
                    const stored = await api.document(active.documentId);
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
                    historyRef.current = createHistory(doc);
                    setHistory(historyRef.current);
                    setStorageRevision(version);
                    setSavedVisualRevision(saved);
                    setProjectId(active.projectId);
                    setNotice(active.projectId ? '已重开工作副本及保存的画布' : '已重开保存的画布');
                    initializeCamera(doc, sequence);
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
            void loadExample(items.find(x => x.id === prior)?.id ?? items[0]?.id ?? 'transformer');
        }).catch(error => { if (alive) {
            setFailure(`Runtime 未连接：${String(error)}`);
            setNotice('请按 README 启动正式服务');
        } });
        return () => { alive = false; };
    }, [loadExample, initializeCamera]);
    useEffect(() => { if (exampleId)
        localStorage.setItem(KEY, exampleId); }, [exampleId]);
    useEffect(() => { if (current)
        localStorage.setItem(ACTIVE, JSON.stringify({ documentId: current.id, projectId })); }, [current?.id, projectId]);
    const save = useCallback(async () => {
        if (activeRecovery) {
            setNotice('请先应用或取消位置修复预览，再保存画布。');
            return;
        }
        if (!historyRef.current || saving.current)
            return;
        saving.current = true;
        const frozen = historyRef.current.document;
        const sequence = loadSequence.current;
        setBusy(true);
        try {
            const result = await api.save(frozen, storageRevision);
            if (sequence !== loadSequence.current || historyRef.current?.document.id !== frozen.id)
                return;
            setStorageRevision(result.revision);
            setSavedVisualRevision(frozen.revision);
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
    }, [storageRevision, activeRecovery]);
    useEffect(() => {
        const down = (event) => {
            if (authoringOpen || editingTarget(event.target) || review || exportDocument || connectionProposal || runtimeOpen || importOpen)
                return;
            if (event.code === 'Space') {
                space.current = true;
                event.preventDefault();
            }
            if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'z') {
                event.preventDefault();
                event.shiftKey ? redo() : undo();
            }
            if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 's') {
                event.preventDefault();
                void save();
            }
            if (event.key === 'Escape') {
                cancelGesture();
                setSelection({ kind: 'node', ids: [] });
                setInline(null);
            }
            if (!event.ctrlKey && !event.metaKey && !event.altKey) {
                if (event.key.toLowerCase() === 'f')
                    fit();
                if (event.key.toLowerCase() === 'h') {
                    cancelGesture();
                    setTool('pan');
                }
                if (event.key.toLowerCase() === 'v') {
                    cancelGesture();
                    setTool('select');
                }
            }
        };
        const up = (event) => { if (event.code === 'Space')
            space.current = false; };
        window.addEventListener('keydown', down);
        window.addEventListener('keyup', up);
        return () => { window.removeEventListener('keydown', down); window.removeEventListener('keyup', up); };
    }, [fit, redo, save, undo, review, exportDocument, connectionProposal, runtimeOpen, importOpen, cancelGesture, authoringOpen]);
    useEffect(() => {
        const viewport = viewportRef.current;
        if (!viewport)
            return;
        const wheel = (event) => {
            if (editingTarget(event.target))
                return;
            event.preventDefault();
            if (gesture.current || portGesture.current)
                return;
            synchronizeCameraViewport();
            const rect = viewport.getBoundingClientRect();
            const px = event.clientX - rect.left, py = event.clientY - rect.top;
            const old = cameraRef.current, zoom = clampCanvasZoom(old.zoom * Math.exp(-Math.max(-2000, Math.min(2000, event.deltaY)) * 0.0015));
            commitCamera({ x: px - (px - old.x) * zoom / old.zoom, y: py - (py - old.y) * zoom / old.zoom, zoom });
        };
        viewport.addEventListener('wheel', wheel, { passive: false });
        return () => viewport.removeEventListener('wheel', wheel);
    }, [authoringOpen, commitCamera]);
    function panInput(event) {
        const rect = event.currentTarget.getBoundingClientRect();
        return { pointerId: event.pointerId, clientX: event.clientX, clientY: event.clientY, viewportX: rect.left, viewportY: rect.top };
    }
    function pointerDown(event) {
        if (activeRecovery) {
            cancelGesture();
            return;
        }
        if (editingTarget(event.target) || !scene || gesture.current || portGesture.current)
            return;
        synchronizeCameraViewport();
        portRequest.current++;
        const input = panInput(event);
        const x = input.clientX - input.viewportX, y = input.clientY - input.viewportY;
        const view = cameraRef.current;
        // Navigation takes priority even over expand handles and input ports.
        if (event.button === 1 || (event.button === 0 && (tool === 'pan' || space.current))) {
            claimCamera();
            cameraViewport.current = readCameraViewport();
            gesture.current = { type: 'pan', pointerId: event.pointerId, x, y, camera: view, pan: beginCameraPan(view, input), ids: [], dx: 0, dy: 0 };
            setIsPanning(true);
            event.currentTarget.setPointerCapture(event.pointerId);
            event.preventDefault();
            return;
        }
        if (event.button !== 0)
            return;
        const target = event.target;
        const portId = target.closest('[data-port-id]')?.getAttribute('data-port-id');
        const port = scene.nodes.flatMap(node => node.ports).find(p => p.id === portId);
        if (port?.direction === 'in' && !busy && current) {
            event.preventDefault();
            if (port.proxy || !inputSpec) {
                setConnectionProposal({ nodeId: port.canonicalNodeId, portId: port.canonicalPortId, candidate: null, blockers: [!inputSpec ? '先设置运行输入与模式，再检查可用来源。' : '这是折叠层级的投影端口；请展开至准确调用端口。'] });
                return;
            }
            const sequence = loadSequence.current;
            const promise = inspectRebind(port.canonicalNodeId, port.canonicalPortId);
            claimGestureCamera();
            portGesture.current = { request: portRequest.current, document: current, pointerId: event.pointerId, port, sequence, promise };
            setPortDraft({ port, x: port.x, y: port.y, options: null });
            void promise.then(options => { if (portGesture.current?.promise === promise)
                setPortDraft(draft => draft && ({ ...draft, options })); }).catch(() => { });
            event.currentTarget.setPointerCapture(event.pointerId);
            return;
        }
        const expandId = target.closest('[data-expand-id]')?.getAttribute('data-expand-id');
        if (expandId) {
            const n = scene.nodes.find(x => x.id === expandId);
            if (n)
                apply([{ type: 'expand', id: expandId, expanded: !n.expanded }], n.expanded ? '已原位收起' : '已原位展开，保留画布位置');
            return;
        }
        const nodeId = target.closest('[data-node-id]')?.getAttribute('data-node-id');
        const edgeId = target.closest('[data-edge-id]')?.getAttribute('data-edge-id');
        const legendId = target.closest('[data-legend-id]')?.getAttribute('data-legend-id');
        const annotationId = target.closest('[data-annotation-id]')?.getAttribute('data-annotation-id');
        if (nodeId) {
            const ids = event.shiftKey ? selection.ids.includes(nodeId) ? selection.ids.filter(id => id !== nodeId) : [...(selection.kind === 'node' ? selection.ids : []), nodeId] : selection.kind === 'node' && selection.ids.includes(nodeId) ? selection.ids : [nodeId];
            setSelection({ kind: 'node', ids });
            setPanel('object');
            if (!current)
                return;
            try {
                claimGestureCamera();
                gesture.current = { type: 'move', pointerId: event.pointerId, x, y, camera: view, ids, dx: 0, dy: 0, document: current, preview: prepareMovePreview(current, ids, layoutMoveScope), moveScope: layoutMoveScope };
            }
            catch (error) {
                setFailure(String(error));
                return;
            }
        }
        else if (edgeId) {
            setSelection({ kind: 'edge', ids: [edgeId] });
            setPanel('object');
            return;
        }
        else if (legendId) {
            setSelection({ kind: 'legend', ids: [legendId] });
            setPanel('legend');
            return;
        }
        else if (annotationId) {
            setSelection({ kind: 'annotation', ids: [annotationId] });
            setPanel('object');
            return;
        }
        else {
            if (!event.shiftKey)
                setSelection({ kind: 'node', ids: [] });
            claimGestureCamera();
            gesture.current = { type: 'box', pointerId: event.pointerId, x, y, camera: view, ids: event.shiftKey ? selection.ids : [], dx: 0, dy: 0 };
        }
        event.currentTarget.setPointerCapture(event.pointerId);
        event.preventDefault();
    }
    function pointerMove(event) {
        if (portGesture.current?.pointerId === event.pointerId && scene) {
            const input = panInput(event), view = cameraRef.current;
            const point = viewportToWorld(view, { x: input.clientX - input.viewportX, y: input.clientY - input.viewportY });
            setPortDraft(draft => draft && ({ ...draft, ...point }));
            return;
        }
        const active = gesture.current;
        if (!active || active.pointerId !== event.pointerId)
            return;
        const input = panInput(event);
        active.dx = input.clientX - input.viewportX - active.x;
        active.dy = input.clientY - input.viewportY - active.y;
        const panCamera = active.pan ? cameraAtPanInput(active.pan, input) : null;
        cancelAnimationFrame(frame.current);
        frame.current = requestAnimationFrame(() => {
            if (gesture.current !== active)
                return;
            frame.current = 0;
            if (panCamera) {
                cameraRef.current = panCamera;
                setCamera(panCamera);
            }
            else if (active.type === 'move') {
                if (historyRef.current?.document !== active.document || !active.preview || !active.document) {
                    cancelGesture();
                    return;
                }
                const dx = Math.round(active.dx / active.camera.zoom / 4) * 4, dy = Math.round(active.dy / active.camera.zoom / 4) * 4;
                const document = active.document, session = active.preview;
                setPreview(previous => previous && previous.session === session && previous.dx === dx && previous.dy === dy ? previous : { document, session, dx, dy });
            }
            else
                setBox({ x: Math.min(active.x, active.x + active.dx), y: Math.min(active.y, active.y + active.dy), width: Math.abs(active.dx), height: Math.abs(active.dy) });
        });
    }
    function pointerUp(event) {
        const connecting = portGesture.current;
        if (connecting) {
            if (connecting.pointerId !== event.pointerId || !scene)
                return;
            portGesture.current = null;
            setPortDraft(null);
            if (event.currentTarget.hasPointerCapture(event.pointerId))
                event.currentTarget.releasePointerCapture(event.pointerId);
            const input = panInput(event), view = cameraRef.current;
            const { x, y } = viewportToWorld(view, { x: input.clientX - input.viewportX, y: input.clientY - input.viewportY });
            void connecting.promise.then(options => {
                if (connecting.sequence !== loadSequence.current || connecting.request !== portRequest.current || connecting.document !== historyRef.current?.document)
                    return;
                const producer = candidatePorts(options).find(p => Math.hypot(p.x - x, p.y - y) < 14 / view.zoom);
                const candidate = options.candidates.find(c => c.binding.nodeId === producer?.canonicalNodeId && c.binding.portId === producer?.canonicalPortId) ?? null;
                setConnectionProposal({ nodeId: connecting.port.canonicalNodeId, portId: connecting.port.canonicalPortId, candidate, blockers: candidate ? [] : options.blockers.length ? options.blockers : ['拖线终点不是已证明可用的来源输出端口；原连接保持不变。'] });
            }).catch(error => { if (connecting.sequence === loadSequence.current && connecting.request === portRequest.current && connecting.document === historyRef.current?.document)
                setConnectionProposal({ nodeId: connecting.port.canonicalNodeId, portId: connecting.port.canonicalPortId, candidate: null, blockers: [String(error)] }); });
            synchronizeCameraViewport();
            return;
        }
        const active = gesture.current;
        if (!active || active.pointerId !== event.pointerId)
            return;
        const input = panInput(event);
        active.dx = input.clientX - input.viewportX - active.x;
        active.dy = input.clientY - input.viewportY - active.y;
        cancelAnimationFrame(frame.current);
        frame.current = 0;
        gesture.current = null;
        setPreview(null);
        setBox(null);
        setIsPanning(false);
        if (active.pan) {
            const finalCamera = cameraAtPanInput(active.pan, input);
            if (finalCamera) {
                cameraRef.current = finalCamera;
                setCamera(finalCamera);
                synchronizeCameraViewport();
                commitCamera(cameraRef.current);
            }
        }
        if (event.currentTarget.hasPointerCapture(event.pointerId))
            event.currentTarget.releasePointerCapture(event.pointerId);
        if (active.type === 'move' && historyRef.current?.document === active.document && Math.hypot(active.dx, active.dy) > 3)
            apply([{ type: 'move', ids: active.ids, dx: Math.round(active.dx / active.camera.zoom / 4) * 4, dy: Math.round(active.dy / active.camera.zoom / 4) * 4, ...(active.moveScope === undefined ? {} : { scope: active.moveScope }) }], '位置已调整；一次拖动对应一次撤销');
        if (active.type === 'box' && scene && Math.hypot(active.dx, active.dy) > 4) {
            const { x, y } = viewportToWorld(active.camera, { x: Math.min(active.x, active.x + active.dx), y: Math.min(active.y, active.y + active.dy) });
            const right = x + Math.abs(active.dx) / active.camera.zoom, bottom = y + Math.abs(active.dy) / active.camera.zoom;
            const ids = scene.nodes.filter(n => !implicitRoots.has(n.id) && n.x >= x && n.y >= y && n.x + n.width <= right && n.y + n.height <= bottom).map(n => n.id);
            setSelection({ kind: 'node', ids: [...new Set([...active.ids, ...ids])] });
        }
        synchronizeCameraViewport();
    }
    function pointerCancelled(event) {
        if (gesture.current?.pointerId === event.pointerId || portGesture.current?.pointerId === event.pointerId)
            cancelGesture();
    }
    function candidatePorts(options) {
        return (options?.candidates ?? []).flatMap(candidate => {
            const node = scene?.nodes.find(n => n.id === candidate.binding.nodeId && !n.expanded);
            if (!node)
                return [];
            const port = node.ports.find(p => p.direction === 'out' && p.canonicalPortId === candidate.binding.portId);
            return [{ id: `${candidate.binding.nodeId}:${candidate.binding.portId}`, canonicalNodeId: candidate.binding.nodeId, canonicalPortId: candidate.binding.portId, x: port?.x ?? node.x + node.width / 2, y: port?.y ?? node.y + node.height }];
        });
    }
    async function semanticProject(base, sequence) {
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
            claimCamera(next.document);
            persistCamera(next.document);
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
    function align() {
        if (!scene || selection.kind !== 'node' || selection.ids.length < 2)
            return;
        const selected = scene.nodes.filter(n => !implicitRoots.has(n.id) && selection.ids.includes(n.id));
        const left = Math.min(...selected.map(n => n.x));
        apply(selected.map(n => ({ type: 'move', ids: [n.id], dx: left - n.x, dy: 0, scope: layoutMoveScope })), '已左对齐所选对象');
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
            ops.push({ type: 'nodeStyle', id: selectedNode.id, style: { fill: colors[color] } });
        if (alias)
            ops.push({ type: 'alias', id: selectedNode.id, label: alias[1] });
        if (text.includes('展开') && selectedSceneNode?.expandable)
            ops.push({ type: 'expand', id: selectedNode.id, expanded: true });
        if (text.includes('收起') && selectedSceneNode?.expandable)
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
        cancelGesture();
        const sequence = ++loadSequence.current;
        setBusy(true);
        try {
            const arch = await api.analyze(sourceText, entry, filename);
            if (sequence !== loadSequence.current)
                return;
            await openArchitecture(arch, true, sequence);
            setExampleId('');
            setImportOpen(false);
        }
        catch (error) {
            if (sequence === loadSequence.current)
                setFailure(String(error));
        }
        finally {
            if (sequence === loadSequence.current)
                setBusy(false);
        }
    }
    function focusNode(id) {
        cancelGesture();
        setSelection({ kind: 'node', ids: [id] });
        setPanel('object');
        const node = scene?.nodes.find(n => n.id === id);
        if (!node || !viewportRef.current || !scene)
            return;
        const { width, height } = viewportRef.current.getBoundingClientRect();
        commitCamera(focusCameraOnPoint(cameraRef.current, { x: node.x + node.width / 2, y: node.y + node.height / 2 }, { width, height }));
    }
    function focusAnnotation(id) {
        cancelGesture();
        const document = historyRef.current?.document, viewport = viewportRef.current;
        if (!document || !viewport)
            return;
        const updated = buildScene(document), annotation = updated.annotations.find(item => item.id === id);
        if (!annotation)
            return;
        const { width, height } = viewport.getBoundingClientRect();
        commitCamera(focusCameraOnPoint(cameraRef.current, { x: annotation.x + annotation.width / 2, y: annotation.y + annotation.height / 2 }, { width, height }));
    }
    function addAnnotation() {
        if (!scene)
            return;
        const id = `annotation-${crypto.randomUUID()}`;
        apply([{ type: 'annotation', annotation: { id, text: '双击节点编辑显示名；说明不改变计算。', ...suggestAnnotationPosition(scene), width: 380 } }]);
        setSelection({ kind: 'annotation', ids: [id] });
        setPanel('object');
        focusAnnotation(id);
    }
    function moveAnnotationBelow() {
        if (!scene || !selectedAnnotation)
            return;
        const position = suggestAnnotationPosition(scene, selectedAnnotation.id);
        if (position.x !== selectedAnnotation.x || position.y !== selectedAnnotation.y)
            apply([{ type: 'annotation', annotation: { ...selectedAnnotation, ...position } }], '说明已移到图下方；可撤销恢复原位置');
        focusAnnotation(selectedAnnotation.id);
    }
    function zoomCamera(factor) {
        cancelGesture();
        const rect = viewportRef.current?.getBoundingClientRect();
        if (!rect)
            return;
        const old = cameraRef.current;
        commitCamera(zoomCameraAtPoint(old, factor === 'reset' ? 1 : clampCanvasZoom(old.zoom * factor), { x: rect.width / 2, y: rect.height / 2 }));
    }
    function sourceDraftKey(document) { return sourceAuthoringKey(document); }
    function cacheGeneratedWorkspace(workspace, binding) {
        try {
            writeGeneratedWorkspace(localStorage, workspace, binding);
        }
        catch {
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
        if (!frozen || busy || activeRecovery)
            return;
        const sequence = loadSequence.current, key = sourceDraftKey(frozen);
        let generatedBinding = generatedWorkspaces.current.get(key);
        if (!generatedBinding) {
            const recovered = readGeneratedWorkspace(localStorage, frozen);
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
                    const rebased = translated ? await resumeSourceAuthoring(workspace, translated, view, (draft, document, scene) => api.sourceDraftFrontier(draft, document, scene)) : workspace;
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
        const retained = authoringSessions.current.get(key);
        if (retained) {
            const retainedRevision = retained.draft.sourceProvenance?.visualRevision;
            if (retainedRevision === frozen.revision) {
                const workspace = followSourceView(retained, { selection: selection.kind === 'node' ? selection.ids : [], camera: { ...cameraRef.current }, viewport: readCameraViewport() ?? undefined, tool,
                    sourceHistory: { past: historyRef.current?.past.length ?? 0, future: historyRef.current?.future.length ?? 0 } });
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
                const workspace = await resumeSourceAuthoring(retained, frozen, { selection: selection.kind === 'node' ? selection.ids : [], camera: { ...cameraRef.current }, viewport: readCameraViewport() ?? undefined, tool,
                    sourceHistory: { past: historyRef.current?.past.length ?? 0, future: historyRef.current?.future.length ?? 0 } }, (draft, document, scene) => api.sourceDraftFrontier(draft, document, scene));
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
                camera: { ...cameraRef.current }, viewport: readCameraViewport() ?? undefined, tool,
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
    async function openGeneratedModel(generated) {
        cancelGesture();
        const workspace = authoringSessionKey.current ? authoringSessions.current.get(authoringSessionKey.current) : undefined;
        const sequence = ++loadSequence.current;
        cameraOwner.current = null;
        cameraIntent.current++;
        const project = await api.register(generated.architecture);
        if (sequence !== loadSequence.current)
            return;
        await openArchitecture(project.architecture, false, sequence, false);
        if (sequence !== loadSequence.current)
            return;
        const retained = createGeneratedCanvas(project.architecture, generated.draft, generated, generated.presentationDraft);
        const document = retained.document;
        if (workspace && authoringSessionKey.current) {
            const binding = { workspaceKey: authoringSessionKey.current,
                documentId: document.id, sourceDigest: document.sourceBindingDigest, irDigest: document.architecture.irDigest,
                draft: structuredClone(workspace.draft), nodeBindings: { ...generated.nodeBindings, ...generated.containerBindings }, visualRevision: document.revision };
            generatedWorkspaces.current.set(sourceDraftKey(document), binding);
            cacheGeneratedWorkspace(workspace, binding);
        }
        historyRef.current = createHistory(document);
        setHistory(historyRef.current);
        setSelection({ kind: 'node', ids: (workspace?.selection ?? []).flatMap(id => retained.nodeBindings[id] ? [retained.nodeBindings[id]] : []) });
        setProjectId(project.id);
        setExampleId('');
        setAuthoringOpen(false);
        if (workspace?.camera) {
            commitCamera(workspace.camera, document);
            setTool(workspace.tool ?? 'select');
        }
        else
            initializeCamera(document, sequence, false);
        setNotice(`已打开新模型工作副本，并保留搭建位置与视角。模型未执行。${retained.unmappedNodeIds.length ? ` ${retained.unmappedNodeIds.length} 个展示框没有对应的新源码节点。` : ''}${retained.unresolvedEdgeStyles.length ? ` ${retained.unresolvedEdgeStyles.length} 条连线样式待核对。` : ''}`);
    }
    if (authoringOpen)
        return _jsx(AuthoringStudio, { initialWorkspace: authoringWorkspace, browseBaseline: browseBaseline, onViewState: retainAuthoringWorkspace, onClose: () => setAuthoringOpen(false), onOpen: openGeneratedModel, onNewBlank: workspace => { retainAuthoringWorkspace(workspace); openBlankAuthoring(); }, onReuseView: workspace => {
                retainAuthoringWorkspace(workspace);
                if (!browseBaseline || !sameGeneratedDraft(workspace.draft, browseBaseline))
                    throw new Error('编辑内容已变化，需要重新生成视图。');
                if (workspace.camera)
                    commitCamera(workspace.camera);
                setSelection({ kind: 'node', ids: authoringViewSelection(workspace, current ? generatedWorkspaces.current.get(sourceDraftKey(current)) : undefined) });
                setTool(workspace.tool ?? 'select');
                setAuthoringOpen(false);
            } }, authoringSessionKey.current);
    return _jsxs("div", { className: "studio", children: [_jsxs("header", { className: "topbar", children: [_jsxs("div", { className: "brand", children: [_jsxs("span", { className: "brand-mark", children: [_jsx("i", {}), _jsx("i", {}), _jsx("i", {})] }), _jsxs("span", { children: ["ArchCanvas", _jsx("small", { children: "MODEL ARCHITECTURE STUDIO" })] })] }), _jsxs("div", { className: "project-breadcrumb", children: [_jsx("span", { className: "slash", children: "/" }), _jsx(Icon, { name: "file", size: 15 }), _jsx("span", { children: current?.title ?? '模型工作台' }), _jsx("span", { className: "alpha-tag", children: "ALPHA" })] }), _jsxs("div", { className: "header-actions", children: [_jsxs("details", { className: "workspace-menu", children: [_jsxs("summary", { children: ["\u6A21\u578B ", _jsx("span", { children: "\u2304" })] }), _jsxs("div", { children: [_jsxs("button", { disabled: busy || !!review || !!activeRecovery, onClick: openBlankAuthoring, children: [_jsx(Icon, { name: "plus", size: 15 }), "\u65B0\u5EFA\u7A7A\u767D\u6A21\u578B"] }), _jsxs("button", { disabled: busy || !!review, onClick: () => setImportOpen(true), children: [_jsx(Icon, { name: "file", size: 15 }), "\u5BFC\u5165 Python \u6E90\u7801"] }), _jsxs("button", { disabled: !current, onClick: () => setSourceOpen(true), children: [_jsx(Icon, { name: "code", size: 15 }), "\u67E5\u770B\u6E90\u7801"] })] })] }), _jsx(WorkspaceModeSwitch, { mode: "view", disabled: !current || busy || !!review || !!activeRecovery, onView: () => { }, onEdit: () => void continueModelAuthoring() }), _jsxs("span", { className: `save-state ${dirty ? 'dirty' : ''}`, children: [_jsx("i", {}), current ? dirty ? '有未保存编辑' : '已保存' : '等待文档'] }), _jsxs("button", { onClick: save, disabled: !current || busy || !!activeRecovery, children: [_jsx(Icon, { name: "save", size: 15 }), "\u4FDD\u5B58"] }), _jsxs("button", { className: "primary", onClick: () => current && setExportDocument(structuredClone(current)), disabled: !current || busy || !!activeRecovery, children: [_jsx(Icon, { name: "export", size: 16 }), "\u5BFC\u51FA"] })] })] }), _jsxs("div", { className: "workspace", children: [_jsxs("aside", { className: "navigator", children: [_jsxs("div", { className: "navigator-top", children: [_jsx("div", { className: "eyebrow", children: "SOURCE WORKSPACE" }), _jsxs("div", { className: "model-switch", children: [_jsx(Icon, { name: "layers" }), _jsxs("select", { "aria-label": "\u793A\u4F8B\u6A21\u578B", value: exampleId, onChange: e => void loadExample(e.target.value), disabled: busy, children: [_jsx("option", { value: "", disabled: true, children: "\u5BFC\u5165\u7684\u6A21\u578B" }), examples.map(e => _jsx("option", { value: e.id, children: e.name }, e.id))] })] }), _jsxs("button", { className: "import-button", disabled: busy, onClick: () => setImportOpen(true), children: [_jsx(Icon, { name: "plus", size: 15 }), "\u5BFC\u5165 Python \u6E90\u7801"] })] }), _jsxs("div", { className: "nav-section-title", children: ["\u6A21\u578B\u5C42\u7EA7", _jsx("span", { children: architecture?.nodes.length ?? 0 })] }), _jsx("div", { className: "tree", role: "tree", "aria-label": "\u6A21\u578B\u5C42\u7EA7", children: architecture && current && _jsx(HierarchyTree, { architecture: architecture, document: current, selected: selection.ids, onSelect: selectHierarchyNode, onExpand: expandHierarchyNode }) }), _jsxs("div", { className: "navigator-bottom", children: [_jsxs("button", { className: sourceOpen ? 'active' : '', onClick: () => setSourceOpen(x => !x), disabled: !current, children: [_jsx(Icon, { name: "code", size: 16 }), "\u67E5\u770B\u6E90\u7801\u8BC1\u636E", _jsx(Icon, { name: "chevron", size: 13 })] }), _jsxs("div", { className: "source-note", children: [_jsx("span", { className: "live-dot" }), "\u9759\u6001\u5206\u6790 \u00B7 \u672A\u6267\u884C\u6A21\u578B", _jsx("p", { children: projectId ? '当前为 Studio 工作副本。' : '样式和显示名仅修改画布。' })] })] })] }), _jsxs("main", { className: "main", children: [_jsxs("div", { className: "workspace-caption", children: [_jsx("b", { children: current?.title ?? '模型工作台' }), _jsx("span", { children: "MODEL ARCHITECTURE \u00B7 \u9759\u6001\u6E90\u7801\u89C6\u56FE" })] }), _jsxs("div", { className: "canvas-toolbar", children: [_jsxs("div", { className: "tool-group", children: [_jsx("button", { title: "\u9009\u62E9 / Shift \u591A\u9009 \u00B7 V", "aria-label": "\u9009\u62E9\u5BF9\u8C61", "aria-pressed": tool === 'select', className: `tool ${tool === 'select' ? 'selected' : ''}`, onClick: () => chooseTool('select'), children: _jsx(Icon, { name: "arrow" }) }), _jsx("button", { title: "\u62D6\u52A8\u753B\u5E03 \u00B7 H", "aria-label": "\u5E73\u79FB\u753B\u5E03", "aria-pressed": tool === 'pan', className: `tool ${tool === 'pan' ? 'selected' : ''}`, onClick: () => chooseTool('pan'), children: _jsx(Icon, { name: "hand" }) }), _jsx("span", { className: "tool-divider" }), _jsx("button", { className: "tool", onClick: undo, disabled: !history?.past.length, title: "\u64A4\u9500 Ctrl+Z", children: _jsx(Icon, { name: "undo" }) }), _jsx("button", { className: "tool", onClick: redo, disabled: !history?.future.length, title: "\u91CD\u505A Ctrl+Shift+Z", children: _jsx(Icon, { name: "redo" }) }), _jsx("span", { className: "tool-divider" }), _jsx("button", { className: "tool", onClick: align, disabled: selection.ids.length < 2, title: "\u5DE6\u5BF9\u9F50", children: _jsx(Icon, { name: "align" }) }), _jsx("button", { className: "tool", onClick: () => apply([{ type: 'pin', ids: selection.ids, pinned: !current?.pinnedObjects.includes(selection.ids[0]) }]), disabled: !selection.ids.length || selection.kind !== 'node', title: "\u56FA\u5B9A / \u89E3\u9501", children: _jsx(Icon, { name: "pin" }) })] }), _jsxs("div", { className: "paper-preset", children: [_jsx("span", { className: "mini-paper" }), _jsxs("select", { "aria-label": "\u9875\u9762\u9884\u8BBE", value: current?.pageSpec.preset ?? 'paper', disabled: !current, onChange: e => apply([{ type: 'page', page: { preset: e.target.value } }]), children: [_jsx("option", { value: "paper", children: "\u8BBA\u6587 \u00B7 \u5F69\u8272" }), _jsx("option", { value: "monochrome", children: "\u8BBA\u6587 \u00B7 \u9ED1\u767D" })] })] }), _jsxs("div", { className: "tool-group", children: [_jsx("button", { className: `tool ${grid ? 'selected' : ''}`, title: "\u663E\u793A\u70B9\u9635\u7F51\u683C", "aria-label": "\u663E\u793A\u70B9\u9635\u7F51\u683C", "aria-pressed": grid, onClick: () => setGrid(x => !x), children: _jsx(Icon, { name: "grid", size: 16 }) }), _jsx("button", { className: "tool", onClick: () => fit(), title: "\u9002\u5408\u753B\u5E03 F", children: _jsx(Icon, { name: "fit" }) })] })] }), _jsxs("div", { ref: viewportRef, className: `canvas-viewport ${grid ? 'with-grid' : ''} ${tool === 'pan' ? 'pan-tool' : ''} ${isPanning ? 'is-panning' : ''}`, "data-canvas-tool": tool, "data-canvas-surface": "infinite", "data-camera": JSON.stringify(camera), style: grid ? { backgroundSize: `${dotGrid.spacing}px ${dotGrid.spacing}px`, backgroundPosition: `${dotGrid.x - dotGrid.spacing / 2}px ${dotGrid.y - dotGrid.spacing / 2}px` } : undefined, onPointerDown: pointerDown, onPointerMove: pointerMove, onPointerUp: pointerUp, onPointerCancel: pointerCancelled, onLostPointerCapture: pointerCancelled, onDoubleClick: event => { if (tool === 'pan' || space.current || event.button !== 0 || editingTarget(event.target) || event.target.closest('[data-port-id],[data-expand-id]'))
                                    return; const id = event.target.closest('[data-node-id]')?.getAttribute('data-node-id'); const n = architecture?.nodes.find(n => n.id === id); if (n) {
                                    inlineCancelled.current = false;
                                    setInline({ id: n.id, label: current?.displayAliases[n.id] ?? n.label });
                                    setSelection({ kind: 'node', ids: [n.id] });
                                } }, children: [_jsxs("div", { className: "canvas-heading", children: [_jsx("span", { children: "INFINITE CANVAS" }), _jsxs("div", { children: [current?.pageSpec.widthMm ?? 180, " mm ", _jsx("i", {}), " ", current?.pageSpec.preset === 'monochrome' ? 'MONOCHROME' : 'PAPER COLOR'] })] }), scene && paperPosition && _jsxs("div", { className: "paper infinite-scene", style: { width: scene.bounds.width, height: scene.bounds.height, transform: `translate(${paperPosition.x}px, ${paperPosition.y}px) scale(${camera.zoom})` }, children: [_jsx("div", { className: "publication-scene", "data-scene-kind": activeRecovery ? 'recovery-preview' : preview && preview.document === current ? 'move-preview' : 'committed', "data-committed-revision": current?.revision, "data-pinned-ids": JSON.stringify(current?.pinnedObjects ?? []), "data-expanded-ids": JSON.stringify(current?.expandedIds ?? []), dangerouslySetInnerHTML: { __html: markup } }), portDraft && _jsxs("svg", { className: "connection-draft", width: scene.bounds.width, height: scene.bounds.height, viewBox: `${scene.bounds.x} ${scene.bounds.y} ${scene.bounds.width} ${scene.bounds.height}`, "aria-label": "\u6539\u63A5\u8349\u7A3F\u4E0E\u53EF\u7528\u6765\u6E90", children: [_jsx("path", { d: `M ${portDraft.port.x} ${portDraft.port.y} L ${portDraft.x} ${portDraft.y}`, stroke: "#bd7533", strokeWidth: "2", strokeDasharray: "5 4", fill: "none" }), candidatePorts(portDraft.options).map(p => _jsx("circle", { cx: p.x, cy: p.y, r: "9", stroke: "#35876b", strokeWidth: "2", fill: "#deeee6", opacity: 'file:///home/fzg/PycharmProjects/ArchCanvas/ArchCanvas_Model_Architecture_Studio/studio/src/.8/index.ts' }, p.id))] }), selection.kind === 'node' && scene.nodes.filter(n => !implicitRoots.has(n.id) && selection.ids.includes(n.id)).map(n => _jsxs("div", { className: "selection-outline", style: { left: n.x - scene.bounds.x - 3, top: n.y - scene.bounds.y - 3, width: n.width + 6, height: n.height + 6 }, children: [_jsx("span", {}), _jsx("span", {}), _jsx("span", {}), _jsx("span", {}), current?.pinnedObjects.includes(n.id) && _jsx("b", { children: "\u56FA\u5B9A" })] }, n.id)), inline && (() => { const n = scene.nodes.find(n => n.id === inline.id); return n ? _jsx("input", { autoFocus: true, className: "inline-editor", "aria-label": "\u539F\u4F4D\u7F16\u8F91\u663E\u793A\u540D", style: { left: n.x - scene.bounds.x + 4, top: n.y - scene.bounds.y + 8, width: n.width - 8 }, value: inline.label, onChange: e => setInline({ ...inline, label: e.target.value }), onKeyDown: e => { if (e.nativeEvent.isComposing)
                                                    return; if (e.key === 'Enter') {
                                                    inlineCancelled.current = true;
                                                    apply([{ type: 'alias', id: inline.id, label: inline.label }]);
                                                    setInline(null);
                                                } if (e.key === 'Escape') {
                                                    inlineCancelled.current = true;
                                                    setInline(null);
                                                } }, onBlur: () => { if (!inlineCancelled.current)
                                                    apply([{ type: 'alias', id: inline.id, label: inline.label }]); setInline(null); } }) : null; })()] }), !scene && _jsxs("div", { className: "empty-state", children: [_jsx(Icon, { name: "layers", size: 40 }), _jsx("h2", { children: "\u8BA9\u6A21\u578B\u7ED3\u6784\u6210\u4E3A\u53EF\u7F16\u8F91\u7684\u8BBA\u6587\u56FE" }), _jsx("p", { children: failure || '正在从源码构建第一张画布…' }), _jsx("button", { onClick: () => void loadExample(examples[0]?.id ?? 'transformer'), children: "\u91CD\u65B0\u8FDE\u63A5" })] }), box && _jsx("div", { className: "marquee", style: { left: box.x, top: box.y, width: box.width, height: box.height } }), scene && _jsx(FloatingLegend, { scene: scene, onEdit: () => setPanel('legend') }), _jsxs("div", { className: "zoom-control", onPointerDown: event => event.stopPropagation(), children: [_jsx("button", { onClick: () => zoomCamera(1 / 1.2), "aria-label": "\u7F29\u5C0F", children: _jsx(Icon, { name: "minus", size: 15 }) }), _jsxs("button", { className: "zoom-value", onClick: () => zoomCamera('reset'), title: "100%", children: [Math.round(camera.zoom * 100), "%"] }), _jsx("button", { onClick: () => zoomCamera(1.2), "aria-label": "\u653E\u5927", children: _jsx(Icon, { name: "plus", size: 15 }) }), _jsx("span", {}), _jsx("button", { onClick: () => fit(), "aria-label": "\u9002\u5408\u753B\u5E03", children: _jsx(Icon, { name: "fit", size: 15 }) })] }), _jsx("div", { className: "canvas-hint", children: portDraft ? '拖向绿色来源端口；松开只创建提案' : tool === 'pan' ? _jsxs(_Fragment, { children: ["\u62D6\u52A8\u5E73\u79FB", _jsx("span", { children: "\u00B7" }), "V \u8FD4\u56DE\u9009\u62E9", _jsx("span", { children: "\u00B7" }), "\u6EDA\u8F6E\u7F29\u653E"] }) : _jsxs(_Fragment, { children: ["\u6EDA\u8F6E\u7F29\u653E", _jsx("span", { children: "\u00B7" }), "H / \u7A7A\u683C\u5E73\u79FB", _jsx("span", { children: "\u00B7" }), "\u8F93\u5165\u7AEF\u53E3\u62D6\u5411\u6765\u6E90\u521B\u5EFA\u63D0\u6848"] }) })] }), !!layoutGuidance.length && _jsxs("div", { className: "layout-warning", role: "status", "aria-label": "\u5E03\u5C40\u63D0\u793A", children: [layoutGuidance.slice(0, 3).map(message => _jsx("p", { children: message }, message)), layoutGuidance.length > 3 && _jsxs("p", { children: ["\u53E6\u6709 ", layoutGuidance.length - 3, " \u5904\u5E03\u5C40\u51B2\u7A81\uFF1B\u8C03\u6574\u540E\u4F1A\u91CD\u65B0\u68C0\u67E5\u3002"] })] }), activeRecovery && _jsxs("div", { className: "layout-recovery-preview", role: "status", "aria-label": "\u4F4D\u7F6E\u4FEE\u590D\u9884\u89C8", children: [_jsxs("p", { children: ["\u4F4D\u7F6E\u4FEE\u590D\u9884\u89C8 \u00B7 ", activeRecovery.plan.operation.scope === 'current-frontier' ? '仅当前视图' : '所有视图', " \u00B7 \u5E94\u7528\u540E\u624D\u8C03\u6574\u9009\u4E2D\u5BF9\u8C61\u3002"] }), _jsxs("div", { children: [_jsx("button", { className: "primary", onClick: applyPositionRecovery, children: "\u5E94\u7528\u4F4D\u7F6E\u4FEE\u590D" }), _jsx("button", { onClick: cancelGesture, children: "\u53D6\u6D88\u9884\u89C8" })] })] }), _jsxs("div", { className: "command-bar", children: [_jsx("span", { className: "command-icon", children: _jsx(Icon, { name: "message", size: 17 }) }), _jsx("input", { "aria-label": "\u753B\u5E03\u6587\u5B57\u6307\u4EE4", placeholder: selectedNode ? '向右移动 24，或设为蓝色、命名为…' : '选择一个节点，用文字修改画布…', value: command, onChange: e => setCommand(e.target.value), onKeyDown: e => { if (e.key === 'Enter' && !e.nativeEvent.isComposing)
                                            runCommand(); } }), _jsx("span", { className: "local-label", children: "\u672C\u5730\u89C6\u89C9\u6307\u4EE4" }), _jsxs("button", { onClick: runCommand, disabled: !command.trim(), children: ["\u5E94\u7528 ", _jsx("span", { children: "\u21B5" })] })] }), sourceOpen && architecture && _jsxs("div", { className: "source-drawer", children: [_jsxs("div", { className: "drawer-header", children: [_jsx(Icon, { name: "code", size: 16 }), _jsx("b", { children: "\u6E90\u7801\u8BC1\u636E" }), _jsx("span", { children: selectedNode?.source ? `${selectedNode.source.path}:${selectedNode.source.line}` : '只读 · 未执行' }), _jsx("button", { className: "tool", onClick: () => setSourceOpen(false), "aria-label": "\u5173\u95ED\u6E90\u7801", children: _jsx(Icon, { name: "close", size: 16 }) })] }), _jsx("div", { className: "source-content", children: architecture.sources.map(source => _jsxs("div", { children: [_jsx("div", { className: "source-filename", children: source.path }), _jsx("pre", { children: source.content.split('\n').map((line, i) => _jsxs("div", { className: selectedNode?.source?.path === source.path && i + 1 >= selectedNode.source.line && i + 1 <= selectedNode.source.endLine ? 'source-highlight' : '', children: [_jsx("span", { children: i + 1 }), line || ' '] }, i)) })] }, source.path)) })] })] }), _jsxs("aside", { className: "inspector", children: [_jsxs("div", { className: "inspector-tabs", children: [_jsx("button", { className: panel === 'object' ? 'active' : '', onClick: () => setPanel('object'), children: "\u5BF9\u8C61" }), _jsx("button", { className: panel === 'legend' ? 'active' : '', onClick: () => setPanel('legend'), children: "\u56FE\u4F8B" }), _jsx("button", { className: panel === 'page' ? 'active' : '', onClick: () => setPanel('page'), children: "\u9875\u9762" })] }), _jsxs("div", { className: "inspector-content", children: [panel === 'object' && selectedNode && current && _jsxs(_Fragment, { children: [_jsxs("div", { className: "object-heading", children: [_jsx("span", { className: "object-icon", style: { background: selectedSceneNode?.fill }, children: _jsx(Icon, { name: "layers", size: 20 }) }), _jsxs("div", { children: [_jsx("h2", { children: current.displayAliases[selectedNode.id] ?? selectedNode.label }), _jsx("span", { children: selectedNode.kind })] })] }), _jsxs("div", { className: `evidence-tag ${selectedNode.evidence}`, children: [_jsx(Icon, { name: "check", size: 12 }), statusText(selectedNode.evidence)] }), _jsxs("section", { className: "property-section", children: [_jsx("h3", { children: "\u663E\u793A" }), _jsx(TextField, { label: "\u663E\u793A\u540D\u79F0", value: current.displayAliases[selectedNode.id] ?? selectedNode.label, onCommit: label => apply([{ type: 'alias', id: selectedNode.id, label }]) }), _jsxs("p", { className: "field-help", children: ["\u6E90\u540D\u79F0\uFF1A", selectedNode.label] }), _jsx("label", { className: "field-label", children: "\u56FE\u5143\u6837\u5F0F" }), _jsx("select", { className: "field-select", "aria-label": "\u56FE\u5143\u6837\u5F0F", value: current.nodeStyleOverrides[selectedNode.id]?.glyph ?? selectedSceneNode?.glyph ?? 'module', onChange: e => apply([{ type: 'nodeStyle', id: selectedNode.id, style: { glyph: e.target.value } }]), children: ['module', 'operator', 'tensor', 'attention', 'norm', 'add', 'opaque'].map(g => _jsx("option", { value: g, children: { module: '模块框', operator: '紧凑算子', tensor: '张量条带', attention: 'Attention 图元', norm: '归一化图元', add: '加法图元', opaque: '未知边界' }[g] }, g)) }), _jsx("label", { className: "field-label", children: "\u586B\u5145\u989C\u8272" }), _jsxs("div", { className: "color-palette", children: [PALETTE.map(color => _jsx("button", { "aria-label": `填充 ${color}`, className: selectedSceneNode?.fill === color ? 'picked' : '', style: { background: color }, onClick: () => apply(selection.ids.map(id => ({ type: 'nodeStyle', id, style: { fill: color } }))) }, color)), _jsx("input", { type: "color", "aria-label": "\u81EA\u5B9A\u4E49\u586B\u5145\u989C\u8272", value: selectedSceneNode?.fill ?? '#dcebf6', onChange: e => apply(selection.ids.map(id => ({ type: 'nodeStyle', id, style: { fill: e.target.value } }))) })] }), _jsx("label", { className: "field-label", children: "\u8FB9\u6846\u989C\u8272" }), _jsxs("div", { className: "color-field", children: [_jsx("input", { type: "color", "aria-label": "\u8FB9\u6846\u989C\u8272", value: selectedSceneNode?.stroke ?? '#607d91', onChange: e => apply([{ type: 'nodeStyle', id: selectedNode.id, style: { stroke: e.target.value } }]) }), _jsx("code", { children: selectedSceneNode?.stroke })] })] }), _jsxs("section", { className: "property-section", children: [_jsx("h3", { children: "\u6392\u5217\u4E0E\u5C42\u7EA7" }), _jsxs("div", { className: "coordinate-row", children: [_jsxs("label", { children: ["X ", _jsx("output", { children: Math.round(selectedSceneNode?.x ?? 0) })] }), _jsxs("label", { children: ["Y ", _jsx("output", { children: Math.round(selectedSceneNode?.y ?? 0) })] })] }), _jsx("label", { className: "field-label", htmlFor: "layout-move-scope", children: "\u79FB\u52A8\u8303\u56F4" }), _jsxs("select", { id: "layout-move-scope", className: "field-select", "aria-label": "\u79FB\u52A8\u8303\u56F4", value: layoutMoveScope, onChange: e => chooseMoveScope(e.target.value), children: [_jsx("option", { value: "all-frontiers", children: "\u6240\u6709\u89C6\u56FE" }), _jsx("option", { value: "current-frontier", children: "\u4EC5\u5F53\u524D\u89C6\u56FE" })] }), _jsxs("p", { className: "field-help", children: ["\u62D6\u52A8\u3001\u5BF9\u9F50\u3001\u4F4D\u7F6E\u4FEE\u590D\u548C\u6587\u5B57\u79FB\u52A8\u4F7F\u7528\u6B64\u8303\u56F4\u3002", layoutMoveScope === 'current-frontier' ? '保留其他层级的排列；展开或收起时，操作容器及祖先、固定对象保持位置。' : '同步调整已保存的展开层级布局。'] }), _jsxs("button", { className: "full-button", onClick: () => apply([{ type: 'pin', ids: selection.ids, pinned: !current.pinnedObjects.includes(selectedNode.id) }]), children: [_jsx(Icon, { name: "pin", size: 14 }), current.pinnedObjects.includes(selectedNode.id) ? '取消固定位置' : '固定位置'] }), selectedSceneNode?.expandable && _jsxs("button", { className: "full-button", onClick: () => apply([{ type: 'expand', id: selectedNode.id, expanded: !selectedSceneNode.expanded }]), children: [_jsx(Icon, { name: "layers", size: 14 }), selectedSceneNode.expanded ? '原位收起' : '原位展开'] }), _jsxs("button", { className: "full-button", onClick: previewPositionRecovery, disabled: busy || selection.ids.length !== 1, children: [_jsx(Icon, { name: "align", size: 14 }), "\u9884\u89C8\u4F4D\u7F6E\u4FEE\u590D"] }), _jsx("button", { className: "text-button", onClick: () => focusNode(selectedNode.id), children: "\u805A\u7126\u8FD9\u4E2A\u5BF9\u8C61" })] }), _jsx(ParameterEditor, { node: selectedNode, busy: busy, enabled: !!capabilities?.semanticWriteback, onPrepare: prepareParameter, onInspectConfiguration: inspectConfiguration }), _jsx(ActivationEditor, { node: selectedNode, busy: busy, enabled: !!capabilities?.supportedIntents?.includes('replace_activation'), inputSpec: inputSpec, onSetup: () => setRuntimeOpen(true), onPrepare: prepareActivation }), _jsx(ObjectFacts, { architecture: current.architecture, node: selectedNode, onSelect: id => { setSelection({ kind: 'node', ids: [id] }); setPanel('object'); } }), selectedNode.ports.some(p => p.direction === 'in') && _jsx(ConnectionEditor, { document: current, nodeId: selectedNode.id, portId: selectedNode.ports.find(p => p.direction === 'in').id, busy: busy, inputSpec: inputSpec, onSetup: () => setRuntimeOpen(true), enabled: !!capabilities?.supportedIntents?.includes('rebind_input'), onInspect: inspectRebind, onPrepare: prepareRebind }, `${architecture?.sourceDigest}:${selectedNode.id}:${JSON.stringify(inputSpec)}`), _jsxs("section", { className: "property-section", children: [_jsxs("h3", { children: ["\u6A21\u578B\u4E8B\u5B9E", _jsx("span", { className: "read-only", children: "\u53EA\u8BFB" })] }), Object.entries(selectedNode.parameters).length ? _jsx("dl", { className: "parameters", children: Object.entries(selectedNode.parameters).map(([name, value]) => _jsxs("div", { children: [_jsx("dt", { children: name }), _jsx("dd", { children: typeof value === 'string' ? value : JSON.stringify(value) })] }, name)) }) : _jsx("p", { className: "field-help", children: "\u6CA1\u6709\u5DF2\u89E3\u6790\u7684\u6784\u9020\u53C2\u6570\u3002" }), _jsxs("button", { className: "full-button", onClick: () => setSourceOpen(true), children: [_jsx(Icon, { name: "code", size: 14 }), "\u67E5\u770B\u6E90\u7801\u4F4D\u7F6E"] })] })] }), panel === 'object' && selectedEdge && current && _jsxs(_Fragment, { children: [_jsxs("div", { className: "object-heading", children: [_jsx(Icon, { name: "arrow" }), _jsxs("div", { children: [_jsx("h2", { children: selectedEdge.label || selectedEdge.role }), _jsxs("span", { children: ["\u5F20\u91CF\u5173\u7CFB \u00B7 ", selectedEdge.role] })] })] }), _jsxs("section", { className: "property-section", children: [_jsx("h3", { children: "\u8FDE\u7EBF\u6837\u5F0F" }), _jsx("label", { className: "field-label", children: "\u989C\u8272" }), _jsx("input", { type: "color", "aria-label": "\u8FDE\u7EBF\u989C\u8272", disabled: current.pageSpec.preset === 'monochrome', value: selectedEdgeAppearance?.stroke ?? '#64748b', onChange: e => apply([{ type: 'edgeStyle', id: selectedEdge.id, style: { stroke: e.target.value } }]) }), current.pageSpec.preset === 'monochrome' && _jsx("p", { className: "field-help", children: "\u9ED1\u767D\u6A21\u5F0F\u7EDF\u4E00\u4F7F\u7528\u7070\u8272\uFF1B\u5DF2\u8BBE\u7F6E\u7684\u989C\u8272\u5728\u8BBA\u6587\u5F69\u8272\u6A21\u5F0F\u751F\u6548\u3002" }), _jsx("label", { className: "field-label", children: "\u7EBF\u5BBD" }), _jsx("input", { "aria-label": "\u8FDE\u7EBF\u5BBD\u5EA6", type: "range", min: "1", max: "4", step: "0.5", value: selectedEdgeAppearance?.width ?? 1.5, onChange: e => apply([{ type: 'edgeStyle', id: selectedEdge.id, style: { width: Number(e.target.value) } }]) }), _jsxs("label", { className: "check-field", children: [_jsx("input", { type: "checkbox", checked: selectedEdgeAppearance?.dashed ?? false, onChange: e => apply([{ type: 'edgeStyle', id: selectedEdge.id, style: { dashed: e.target.checked } }]) }), "\u4F7F\u7528\u865A\u7EBF"] }), selectedEdgeAppearance && _jsxs("p", { className: "field-help", children: ["\u5F53\u524D\u7EBF\u578B\uFF1A", edgePatternLabel(selectedEdgeAppearance), " \u00B7 ", current.edgeStyleOverrides[selectedEdge.id]?.dashed === undefined ? '角色默认' : '用户覆盖', "\u3002\u66F4\u6539\u590D\u9009\u6846\u540E\u4F7F\u7528\u663E\u5F0F\u5B9E\u7EBF\u6216\u901A\u7528\u865A\u7EBF\uFF1B\u53EF\u64A4\u9500\u6700\u8FD1\u7F16\u8F91\u3002"] })] }), _jsxs("section", { className: "property-section", children: [_jsx("h3", { children: "\u5F53\u524D\u7AEF\u53E3\u7ED1\u5B9A" }), _jsxs("p", { className: "field-help", children: [selectedEdge.source.portId, " \u2192 ", selectedEdge.target.portId] }), _jsx("p", { className: "field-help", children: "\u6539\u8D70\u7EBF\u6837\u5F0F\u4E0D\u4F1A\u6539\u53D8\u6A21\u578B\u8BA1\u7B97\u5173\u7CFB\u3002" })] }), _jsx(ConnectionEditor, { document: current, nodeId: selectedEdge.target.nodeId, portId: selectedEdge.target.portId, busy: busy, inputSpec: inputSpec, onSetup: () => setRuntimeOpen(true), enabled: !!capabilities?.supportedIntents?.includes('rebind_input'), onInspect: inspectRebind, onPrepare: prepareRebind }, `${architecture?.sourceDigest}:${selectedEdge.id}:${JSON.stringify(inputSpec)}`)] }), panel === 'object' && selectedAnnotation && _jsxs(_Fragment, { children: [_jsx("h2", { children: "\u8BF4\u660E\u6587\u5B57" }), _jsx(TextField, { label: "\u5185\u5BB9", value: selectedAnnotation.text, onCommit: text => apply([{ type: 'annotation', annotation: { ...selectedAnnotation, text } }]) }), annotationConflicts.length > 0 && _jsxs("p", { className: "annotation-overlap", role: "status", children: ["\u8BF4\u660E\u6B63\u6587\u4E0E ", annotationConflicts.length, " \u4E2A\u5BF9\u8C61\u91CD\u53E0\u3002\u53EF\u79FB\u5230\u56FE\u4E0B\u65B9\uFF0C\u518D\u68C0\u67E5\u5BFC\u51FA\u3002"] }), _jsxs("button", { className: "full-button", onClick: moveAnnotationBelow, children: [_jsx(Icon, { name: "align", size: 14 }), "\u79FB\u5230\u56FE\u4E0B\u65B9"] }), _jsx("button", { className: "text-button", onClick: () => focusAnnotation(selectedAnnotation.id), children: "\u805A\u7126\u8FD9\u6BB5\u8BF4\u660E" }), _jsx("button", { className: "full-button", onClick: () => { apply([{ type: 'removeAnnotation', id: selectedAnnotation.id }]); setSelection({ kind: 'node', ids: [] }); }, children: "\u79FB\u9664\u8BF4\u660E" })] }), panel === 'object' && !selectedNode && !selectedEdge && !selectedAnnotation && _jsxs(_Fragment, { children: [_jsxs("div", { className: "inspector-empty", children: [_jsx("div", { className: "empty-symbol", children: _jsx(Icon, { name: "arrow", size: 24 }) }), _jsx("h2", { children: "\u4ECE\u4E00\u4E2A\u5BF9\u8C61\u5F00\u59CB" }), _jsxs("p", { children: ["\u9009\u62E9\u6A21\u5757\u3001\u8FDE\u7EBF\u6216\u8BF4\u660E\u6587\u5B57\uFF0C", _jsx("br", {}), "\u8C03\u6574\u8BBA\u6587\u56FE\u7684\u5448\u73B0\u65B9\u5F0F\u3002"] }), _jsxs("div", { className: "shortcut-line", children: [_jsx("kbd", { children: "Shift" }), " \u591A\u9009\u5BF9\u8C61"] }), _jsxs("div", { className: "shortcut-line", children: [_jsx("kbd", { children: "\u53CC\u51FB" }), " \u7F16\u8F91\u663E\u793A\u540D"] })] }), _jsxs("div", { className: "document-summary", children: [_jsx("div", { className: "eyebrow", children: "SOURCE-GROUNDED CANVAS" }), _jsx("h3", { children: current?.title ?? 'ArchCanvas' }), _jsx("p", { children: "\u4E00\u4EFD\u6A21\u578B\u4E8B\u5B9E\uFF0C\u4E00\u4EFD\u53EF\u6301\u7EED\u7F16\u8F91\u7684\u753B\u5E03\u3002" }), _jsxs("div", { children: [_jsx("b", { children: architecture?.nodes.length ?? '—' }), _jsx("span", { children: "\u4E8B\u5B9E\u5BF9\u8C61" }), _jsx("b", { children: architecture?.edges.length ?? '—' }), _jsx("span", { children: "\u7AEF\u53E3\u5173\u7CFB" })] })] }), !!architecture?.diagnostics.length && _jsxs("div", { className: "diagnostics", children: [_jsx("h3", { children: "\u5206\u6790\u8FB9\u754C" }), architecture.diagnostics.slice(0, 4).map((d, i) => _jsx("p", { children: d.message }, i))] })] }), panel === 'legend' && current && _jsxs(_Fragment, { children: [_jsxs("div", { className: "panel-heading", children: [_jsx("h2", { children: "\u56FE\u4F8B\u7F16\u8F91" }), _jsx("p", { children: "\u56FE\u4F8B\u5C5E\u4E8E\u753B\u5E03\uFF0C\u968F\u5F53\u524D\u7248\u672C\u4FDD\u5B58\u548C\u5BFC\u51FA\u3002" }), current.pageSpec.preset === 'monochrome' && _jsx("p", { className: "field-help", children: "\u60AC\u6D6E\u56FE\u4F8B\u663E\u793A\u5F53\u524D\u53EF\u89C1\u8FDE\u7EBF\u7684\u89D2\u8272\u4E0E\u5B9E\u9645\u7EBF\u578B\uFF1B\u51FA\u7248\u56FE\u4F8B\u968F\u89C6\u56FE\u548C\u6837\u5F0F\u81EA\u52A8\u66F4\u65B0\u3002" })] }), _jsx("div", { className: "legend-list", children: current.legendItems.map((item, index) => _jsxs("div", { className: "legend-editor", children: [_jsxs("div", { className: "legend-row", children: [_jsx("input", { type: "color", "aria-label": `图例颜色 ${index + 1}`, value: item.color, onChange: e => apply([{ type: 'legend', items: current.legendItems.map(x => x.id === item.id ? { ...x, color: e.target.value } : x) }]) }), _jsx(TextField, { label: "", value: item.label, onCommit: label => apply([{ type: 'legend', items: current.legendItems.map(x => x.id === item.id ? { ...x, label } : x) }]) }), _jsx("button", { className: "tool", "aria-label": `删除图例 ${index + 1}`, onClick: () => apply([{ type: 'legend', items: current.legendItems.filter(x => x.id !== item.id) }]), children: _jsx(Icon, { name: "close", size: 13 }) })] }), _jsxs("div", { className: "legend-controls", children: [_jsx("select", { "aria-label": `图例符号 ${index + 1}`, value: item.glyph, onChange: e => apply([{ type: 'legend', items: current.legendItems.map(x => x.id === item.id ? { ...x, glyph: e.target.value } : x) }]), children: ['module', 'operator', 'tensor', 'attention', 'norm', 'add', 'opaque'].map(g => _jsx("option", { children: g }, g)) }), _jsx("button", { disabled: index === 0, onClick: () => { const items = [...current.legendItems]; [items[index - 1], items[index]] = [items[index], items[index - 1]]; apply([{ type: 'legend', items }]); }, title: "\u4E0A\u79FB", children: "\u2191" }), _jsx("button", { disabled: index === current.legendItems.length - 1, onClick: () => { const items = [...current.legendItems]; [items[index + 1], items[index]] = [items[index], items[index + 1]]; apply([{ type: 'legend', items }]); }, title: "\u4E0B\u79FB", children: "\u2193" })] })] }, item.id)) }), _jsxs("button", { className: "full-button", onClick: () => apply([{ type: 'legend', items: [...current.legendItems, { id: `legend-${crypto.randomUUID()}`, label: '自定义图例', color: '#dcebf6', glyph: 'module' }] }]), children: [_jsx(Icon, { name: "plus", size: 15 }), "\u6DFB\u52A0\u56FE\u4F8B\u6761\u76EE"] })] }), panel === 'page' && current && _jsxs(_Fragment, { children: [_jsxs("div", { className: "panel-heading", children: [_jsx("h2", { children: "\u51FA\u7248\u9875\u9762" }), _jsx("p", { children: "SVG\u3001PDF \u4E0E PNG \u5171\u7528\u5F53\u524D\u753B\u5E03\u573A\u666F\u3002" })] }), _jsxs("section", { className: "property-section", children: [_jsx("label", { className: "field-label", children: "\u7269\u7406\u9875\u5BBD" }), _jsx("div", { className: "segmented", children: [85, 180].map(widthMm => _jsxs("button", { className: current.pageSpec.widthMm === widthMm ? 'active' : '', onClick: () => apply([{ type: 'page', page: { widthMm } }]), children: [widthMm, " mm"] }, widthMm)) }), _jsx("label", { className: "field-label", children: "\u80CC\u666F" }), _jsxs("div", { className: "color-field", children: [_jsx("input", { "aria-label": "\u9875\u9762\u80CC\u666F", type: "color", value: current.pageSpec.background, onChange: e => apply([{ type: 'page', page: { background: e.target.value } }]) }), _jsx("code", { children: current.pageSpec.background })] }), _jsx("label", { className: "field-label", children: "\u914D\u8272" }), _jsxs("div", { className: "segmented", children: [_jsx("button", { className: current.pageSpec.preset === 'paper' ? 'active' : '', onClick: () => apply([{ type: 'page', page: { preset: 'paper' } }]), children: "\u8BBA\u6587\u5F69\u8272" }), _jsx("button", { className: current.pageSpec.preset === 'monochrome' ? 'active' : '', onClick: () => apply([{ type: 'page', page: { preset: 'monochrome' } }]), children: "\u9ED1\u767D" })] })] }), _jsxs("section", { className: "property-section", children: [_jsx("h3", { children: "\u8BF4\u660E\u4E0E\u5DE5\u4EF6" }), _jsxs("button", { className: "full-button", onClick: addAnnotation, children: [_jsx(Icon, { name: "plus", size: 14 }), "\u6DFB\u52A0\u8BF4\u660E\u6587\u5B57"] }), _jsxs("button", { className: "full-button", onClick: () => download(`${current.id}.archcanvas.json`, JSON.stringify(current, null, 2), 'application/json'), children: [_jsx(Icon, { name: "save", size: 14 }), "\u4E0B\u8F7D\u753B\u5E03\u6587\u6863"] }), _jsx("p", { className: "field-help", children: "\u5BFC\u51FA\u8BBA\u6587\u56FE\u53EF\u751F\u6210 SVG\u3001PDF \u6216 PNG\uFF0C\u5E76\u4FDD\u7559\u53EF\u91CD\u5F00\u7684\u6587\u4EF6\u94FE\u63A5\u4E0E\u5BFC\u51FA\u6536\u636E\u3002" })] })] })] }), _jsxs("div", { className: "inspector-footer", children: [_jsx(Icon, { name: "info", size: 14 }), _jsx("span", { children: "\u89C6\u89C9\u7F16\u8F91\u4E0D\u4FEE\u6539\u6A21\u578B\u6E90\u7801" })] })] })] }), _jsxs("footer", { className: `statusbar ${failure ? 'has-error' : ''}`, children: [_jsxs("span", { children: [_jsx("i", { className: busy ? 'busy-dot' : 'live-dot' }), failure || (runtimeCancel ? cancelling ? '正在取消运行验证…' : '正在隔离运行并核对前后结构…' : busy ? '正在处理…' : notice)] }), _jsxs("div", { children: [runtimeCancel && _jsx("button", { disabled: cancelling, onClick: () => void cancelRuntime(), children: cancelling ? '取消中…' : '取消运行验证' }), selection.ids.length > 0 && _jsxs("span", { children: [selection.ids.length, " \u4E2A\u5DF2\u9009"] }), _jsx("span", { children: "SVG SCENE v1" }), _jsxs("span", { children: ["rev ", current?.revision ?? 0] })] })] }), runtimeOpen && architecture && _jsx(RuntimeProfileDialog, { architecture: architecture, initial: inputSpec, example: exampleId === 'multi_input', onSave: saveInputSpec, onClose: () => setRuntimeOpen(false) }), connectionProposal && _jsx("div", { className: "modal-backdrop", children: _jsxs("div", { className: "runtime-modal connection-proposal", role: "dialog", "aria-modal": "true", "aria-labelledby": "proposal-title", children: [_jsxs("div", { className: "modal-heading", children: [_jsxs("div", { children: [_jsx("div", { className: "eyebrow", children: "CONNECTION PROPOSAL" }), _jsx("h2", { id: "proposal-title", children: connectionProposal.candidate ? '检查改接提案' : '保留未支持的连接提案' })] }), _jsx("button", { className: "tool", "aria-label": "\u5173\u95ED\u8FDE\u63A5\u63D0\u6848", onClick: () => setConnectionProposal(null), children: _jsx(Icon, { name: "close" }) })] }), connectionProposal.candidate ? _jsxs("p", { children: ["\u5C06\u9009\u5B9A\u8F93\u5165\u8FDE\u63A5\u5230 ", _jsx("b", { children: connectionProposal.candidate.variable }), "\u3002\u5F53\u524D\u53EA\u521B\u5EFA\u63D0\u6848\uFF1B\u8FD0\u884C\u9A8C\u8BC1\u540E\u4F1A\u5C55\u793A\u51C6\u786E\u6E90\u7801 diff \u548C\u524D\u540E\u5173\u7CFB\uFF0C\u6279\u51C6\u540E\u624D\u80FD\u63D0\u4EA4\u5DE5\u4F5C\u526F\u672C\u3002"] }) : connectionProposal.blockers.map((blocker, i) => _jsx("p", { children: blocker }, i)), _jsxs("div", { className: "modal-actions", children: [_jsx("button", { onClick: () => setConnectionProposal(null), children: "\u4FDD\u7559\u5F53\u524D\u8FDE\u63A5" }), !inputSpec && _jsx("button", { onClick: () => { setConnectionProposal(null); setRuntimeOpen(true); }, children: "\u8BBE\u7F6E\u8FD0\u884C\u8F93\u5165\u4E0E\u6A21\u5F0F" }), connectionProposal.candidate && _jsx("button", { className: "primary", disabled: busy, onClick: () => { const proposal = connectionProposal; setConnectionProposal(null); prepareRebind(proposal.nodeId, proposal.portId, proposal.candidate.binding); }, children: "\u8FD0\u884C\u9A8C\u8BC1\u5E76\u9884\u89C8\u6E90\u7801\u4FEE\u6539" })] })] }) }), review && _jsx(ReviewDialog, { base: review.base, transaction: review.transaction, busy: busy, error: reviewError, onApprove: () => void approveParameter(), onCommit: () => void commitParameter(), onClose: () => void closeReview() }), exportDocument && _jsx(ExportDialog, { document: exportDocument, capabilities: capabilities, selectedId: selection.kind === 'node' && selection.ids.length === 1 ? selection.ids[0] : undefined, onClose: () => setExportDocument(null) }), importOpen && _jsx("div", { className: "modal-backdrop", children: _jsxs("div", { className: "import-modal", role: "dialog", "aria-modal": "true", "aria-labelledby": "import-title", children: [_jsxs("div", { className: "modal-heading", children: [_jsxs("div", { children: [_jsx("div", { className: "eyebrow", children: "STATIC SOURCE IMPORT" }), _jsx("h2", { id: "import-title", children: "\u4ECE Python \u6E90\u7801\u5F00\u59CB" })] }), _jsx("button", { className: "tool", onClick: () => setImportOpen(false), "aria-label": "\u5173\u95ED\u5BFC\u5165", children: _jsx(Icon, { name: "close" }) })] }), _jsx("p", { children: "\u5BFC\u5165\u5355\u6587\u4EF6 nn.Module\u3002\u5206\u6790\u5668\u53EA\u89E3\u6790\u6E90\u7801\uFF1B\u4E0D\u5BFC\u5165\u6A21\u5757\u3001\u4E0D\u8FD0\u884C forward\u3002\u591A\u6587\u4EF6\u5DE5\u7A0B\u53EF\u901A\u8FC7 CLI \u5206\u6790\u540E\uFF0C\u8BFB\u53D6\u751F\u6210\u7684\u67B6\u6784 JSON\u3002" }), _jsxs("div", { className: "import-fields", children: [_jsxs("label", { children: ["\u6A21\u578B\u7C7B\u540D", _jsx("input", { value: entry, onChange: e => setEntry(e.target.value) })] }), _jsxs("label", { children: ["\u6587\u4EF6\u540D", _jsx("input", { value: filename, onChange: e => setFilename(e.target.value) })] }), _jsxs("button", { onClick: () => fileRef.current?.click(), children: [_jsx(Icon, { name: "file", size: 15 }), "\u8BFB\u53D6 .py / \u67B6\u6784 JSON"] }), _jsx("input", { ref: fileRef, hidden: true, type: "file", accept: 'file:///home/fzg/PycharmProjects/ArchCanvas/ArchCanvas_Model_Architecture_Studio/studio/src/.py,.json/index.ts', onChange: async (e) => { const file = e.target.files?.[0]; if (!file)
                                        return; try {
                                        if (file.size > 4_000_000)
                                            throw new Error('文件超过 4 MB 导入预算');
                                        const text = await file.text();
                                        if (file.name.endsWith('file:///home/fzg/PycharmProjects/ArchCanvas/ArchCanvas_Model_Architecture_Studio/studio/src/.json/index.ts')) {
                                            const architecture = validateArchitecture(JSON.parse(text));
                                            await openArchitecture(architecture);
                                            setExampleId('');
                                            setImportOpen(false);
                                        }
                                        else {
                                            setSourceText(text);
                                            setFilename(file.name);
                                        }
                                    }
                                    catch (error) {
                                        setFailure(`导入失败：${String(error)}`);
                                    } e.target.value = ''; } })] }), _jsx("textarea", { "aria-label": "Python \u6E90\u7801", spellCheck: false, placeholder: "import torch\\nfrom torch import nn\\n\\nclass Model(nn.Module):\\n    ...", value: sourceText, onChange: e => setSourceText(e.target.value) }), failure && _jsx("p", { className: "error-text", children: failure }), _jsxs("div", { className: "modal-actions", children: [_jsx("button", { onClick: () => setImportOpen(false), children: "\u53D6\u6D88" }), _jsx("button", { className: "primary", onClick: () => void importSource(), disabled: busy || !sourceText.trim(), children: "\u9759\u6001\u5206\u6790\u5E76\u6253\u5F00\u753B\u5E03" })] })] }) })] });
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
