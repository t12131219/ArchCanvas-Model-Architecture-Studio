import { jsx as _jsx, jsxs as _jsxs, Fragment as _Fragment } from "react/jsx-runtime";
import { useEffect, useId, useLayoutEffect, useMemo, useRef, useState } from 'react';
import { api, ApiError } from 'file:///home/fzg/PycharmProjects/ArchCanvas/ArchCanvas_Model_Architecture_Studio/studio/src/api.ts';
import { Icon } from './icons.mjs';
import { addDraftNode, arrangeDraft, blankDraft, changeDraft, connectDraft, DRAFT_WIDTH, draftModuleSize, draftNodeSize, draftPortSpacing, draftHistory, draftRoutes, nextDraftPosition, portPoint, removeDraftNode, travelDraft, sourceDraftCatalog, draftSourceKind, moveDraftNodes, selectDraftNode } from 'file:///home/fzg/PycharmProjects/ArchCanvas/ArchCanvas_Model_Architecture_Studio/studio/src/authoring.ts';

import { beginCameraPan, cameraAtPanInput } from 'file:///home/fzg/PycharmProjects/ArchCanvas/ArchCanvas_Model_Architecture_Studio/studio/src/cameraGesture.ts';
import { fitDraftCamera, parseDraftField, resolveDraftFeedback } from 'file:///home/fzg/PycharmProjects/ArchCanvas/ArchCanvas_Model_Architecture_Studio/studio/src/authoringFeedback.ts';
import { draftPresets, draftPresetSize, draftPresetUnavailable, insertDraftPreset } from 'file:///home/fzg/PycharmProjects/ArchCanvas/ArchCanvas_Model_Architecture_Studio/studio/src/authoringPresets.ts';
import { draftPortPresentation } from 'file:///home/fzg/PycharmProjects/ArchCanvas/ArchCanvas_Model_Architecture_Studio/studio/src/draftPortPresentation.ts';
import { draftParameterHelp } from 'file:///home/fzg/PycharmProjects/ArchCanvas/ArchCanvas_Model_Architecture_Studio/studio/src/draftParameterHelp.ts';
import { draftValidationKey, draftTensorLabel, readDraftValidation } from 'file:///home/fzg/PycharmProjects/ArchCanvas/ArchCanvas_Model_Architecture_Studio/studio/src/draftValidation.ts';
import { draftCanvasTextScale, draftFittedText } from 'file:///home/fzg/PycharmProjects/ArchCanvas/ArchCanvas_Model_Architecture_Studio/studio/src/draftTextReadability.ts';
import { placeDraftTooltip } from 'file:///home/fzg/PycharmProjects/ArchCanvas/ArchCanvas_Model_Architecture_Studio/studio/src/draftTooltipPlacement.ts';
import { draftEdgeRoles } from 'file:///home/fzg/PycharmProjects/ArchCanvas/ArchCanvas_Model_Architecture_Studio/studio/src/draftEdgeRoles.ts';
import { reprojectSourceDraft } from 'file:///home/fzg/PycharmProjects/ArchCanvas/ArchCanvas_Model_Architecture_Studio/studio/src/sourceDraftFrontier.ts';
import { canvasDotGrid, clampCanvasZoom } from 'file:///home/fzg/PycharmProjects/ArchCanvas/ArchCanvas_Model_Architecture_Studio/studio/src/cameraProjection.ts';
import { draftPaletteCategories, draftPaletteCategoryLabel, draftPresetMatches, filterDraftModules } from 'file:///home/fzg/PycharmProjects/ArchCanvas/ArchCanvas_Model_Architecture_Studio/studio/src/draftPalette.ts';
import { authoringCameraAtViewport, parseAuthoringWorkspace, reopenAuthoringWorkspace } from 'file:///home/fzg/PycharmProjects/ArchCanvas/ArchCanvas_Model_Architecture_Studio/studio/src/sourceAuthoringSession.ts';
const CACHE = 'archcanvas.authored-workspace.v1';
import { cameraViewportSize } from 'file:///home/fzg/PycharmProjects/ArchCanvas/ArchCanvas_Model_Architecture_Studio/studio/src/cameraViewport.ts';
import { WorkspaceModeSwitch } from './WorkspaceModeSwitch.mjs';
import { sameGeneratedDraft } from 'file:///home/fzg/PycharmProjects/ArchCanvas/ArchCanvas_Model_Architecture_Studio/studio/src/generatedWorkspace.ts';
import { CustomModuleDialog } from './CustomModuleDialog.mjs';
import { customModuleCatalog } from 'file:///home/fzg/PycharmProjects/ArchCanvas/ArchCanvas_Model_Architecture_Studio/studio/src/customModules.ts';
import { implicitDraftRootIds } from 'file:///home/fzg/PycharmProjects/ArchCanvas/ArchCanvas_Model_Architecture_Studio/studio/src/authoring.ts';
import { FloatingLegend } from './FloatingLegend.mjs';
const UNSUPPORTED_SEARCH_HINTS = [
    { aliases: ['sigmoid'], label: 'Sigmoid', alternative: 'ReLU、GELU 或 SiLU，激活行为不同' },
    { aliases: ['softmax'], label: 'Softmax', alternative: 'ReLU、GELU 或 SiLU，但它们不提供概率归一化' },
    { aliases: ['tanh'], label: 'Tanh', alternative: 'ReLU、GELU 或 SiLU，输出范围与激活行为不同' },
    { aliases: ['conv1d'], label: 'Conv1d', alternative: 'Conv2d，仅用于二维空间输入' },
    { aliases: ['avgpool2d'], label: 'AvgPool2d', alternative: 'MaxPool2d 或 AdaptiveAvgPool2d，池化方式或输出尺寸设置不同' },
    { aliases: ['batchnorm1d'], label: 'BatchNorm1d', alternative: 'BatchNorm2d，仅用于四维图像张量' },
    { aliases: ['multiheadattention', 'attention', '注意力'], label: 'MultiheadAttention / Attention', alternative: 'Embedding、LayerNorm、Linear 或 MLP 网络起点；这些模块不提供注意力计算' },
    { aliases: ['lstm'], label: 'LSTM', alternative: 'Embedding、Linear 或 MLP 网络起点；这些模块不提供循环状态' },
    { aliases: ['gru'], label: 'GRU', alternative: 'Embedding、Linear 或 MLP 网络起点；这些模块不提供循环状态' },
];
export function unsupportedPaletteMessage(value) {
    const query = value.trim().toLowerCase();
    const match = UNSUPPORTED_SEARCH_HINTS.find(item => item.aliases.some(alias => query.includes(alias)));
    return match ? `暂不支持 ${match.label}。当前可用选项：${match.alternative}。` : null;
}
function createBlank() { return blankDraft(`draft-${crypto.randomUUID()}`); }
function restored() {
    try {
        const stored = parseAuthoringWorkspace(JSON.parse(localStorage.getItem(CACHE) ?? 'null'));
        if (stored)
            return stored;
    }
    catch { /* A damaged browser cache is never used as a source document. */ }
    return { draft: createBlank(), storageRevision: 0, savedRevision: -1 };
}
export function AuthoringStudio({ onClose, onOpen, initialWorkspace, onViewState, browseBaseline, onReuseView, onNewBlank }) {
    const [initial] = useState(() => initialWorkspace ?? restored());
    const [history, setHistory] = useState(() => initial.history ?? draftHistory(initial.draft));
    const [baseCatalog, setBaseCatalog] = useState({ "schemaVersion": 1, "mode": "authored-draft", "modules": [{ "kind": "Input", "category": "io", "label": "\u8f93\u5165", "description": "\u58f0\u660e\u8f93\u5165\u5f62\u72b6\u4e0e\u7c7b\u578b\uff1b\u58f0\u660e\u4e0d\u662f\u5b9e\u6d4b\u6570\u636e\u3002", "defaults": { "shape": [1, 16], "dtype": "float32" }, "parameters": [{ "name": "shape", "type": "integer-array", "default": [1, 16], "min": 1, "max": 1000000, "minLength": 1, "maxLength": 8 }, { "name": "dtype", "type": "choice", "default": "float32", "options": ["float32", "float64", "int64"] }], "ports": [{ "id": "output", "name": "output", "direction": "out", "type": "tensor" }] }, { "kind": "Output", "category": "io", "label": "\u8f93\u51fa", "description": "\u5c06\u4e00\u6761\u5f20\u91cf\u8fde\u63a5\u4e3a\u547d\u540d\u8f93\u51fa\u3002", "defaults": {}, "parameters": [], "ports": [{ "id": "input", "name": "input", "direction": "in", "type": "tensor" }] }, { "kind": "Linear", "category": "dense", "label": "\u5168\u8fde\u63a5", "description": "\u53d8\u6362\u8f93\u5165\u7684\u6700\u540e\u4e00\u7ef4\uff0c\u9700\u8981 float32\u3002", "defaults": { "in_features": 16, "out_features": 32, "bias": true }, "parameters": [{ "name": "in_features", "type": "integer", "default": 16, "min": 1, "max": 1000000 }, { "name": "out_features", "type": "integer", "default": 32, "min": 1, "max": 1000000 }, { "name": "bias", "type": "boolean", "default": true }], "ports": [{ "id": "input", "name": "input", "direction": "in", "type": "tensor" }, { "id": "output", "name": "output", "direction": "out", "type": "tensor" }] }, { "kind": "Identity", "category": "operator", "label": "\u6052\u7b49\u6620\u5c04", "description": "\u4fdd\u7559\u5f20\u91cf\u5f62\u72b6\u4e0e\u7c7b\u578b\u3002", "defaults": {}, "parameters": [], "ports": [{ "id": "input", "name": "input", "direction": "in", "type": "tensor" }, { "id": "output", "name": "output", "direction": "out", "type": "tensor" }] }, { "kind": "Flatten", "category": "reshape", "label": "\u5c55\u5e73", "description": "\u5c06\u8d77\u6b62\u7ef4\u5ea6\u4e4b\u95f4\u7684\u8f74\u5408\u5e76\uff0c\u9ed8\u8ba4\u4fdd\u7559\u6279\u6b21\u8f74\u3002", "defaults": { "start_dim": 1, "end_dim": -1 }, "parameters": [{ "name": "start_dim", "type": "integer", "default": 1, "min": -8, "max": 7 }, { "name": "end_dim", "type": "integer", "default": -1, "min": -8, "max": 7 }], "ports": [{ "id": "input", "name": "input", "direction": "in", "type": "tensor" }, { "id": "output", "name": "output", "direction": "out", "type": "tensor" }] }, { "kind": "Unflatten", "category": "reshape", "label": "\u6062\u590d\u591a\u7ef4", "description": "\u628a\u4e00\u4e2a\u8f74\u6062\u590d\u4e3a\u6307\u5b9a\u7684\u591a\u4e2a\u5c3a\u5bf8\uff0c\u5143\u7d20\u603b\u6570\u5fc5\u987b\u4e00\u81f4\u3002", "defaults": { "dim": -1, "unflattened_size": [4, 4] }, "parameters": [{ "name": "dim", "type": "integer", "default": -1, "min": -8, "max": 7 }, { "name": "unflattened_size", "type": "integer-array", "default": [4, 4], "min": 1, "max": 1000000, "minLength": 1, "maxLength": 8 }], "ports": [{ "id": "input", "name": "input", "direction": "in", "type": "tensor" }, { "id": "output", "name": "output", "direction": "out", "type": "tensor" }] }, { "kind": "Reshape", "category": "reshape", "label": "\u91cd\u5851\u5f62\u72b6", "description": "\u663e\u5f0f\u58f0\u660e\u6574\u4e2a\u8f93\u51fa\u5f62\u72b6\uff1b\u5141\u8bb8\u4e00\u4e2a -1 \u63a8\u5bfc\u8f74\uff0c\u5143\u7d20\u603b\u6570\u4e0d\u53d8\u3002", "defaults": { "shape": [1, -1] }, "parameters": [{ "name": "shape", "type": "integer-array", "default": [1, -1], "min": -1, "max": 1000000, "minLength": 1, "maxLength": 8 }], "ports": [{ "id": "input", "name": "input", "direction": "in", "type": "tensor" }, { "id": "output", "name": "output", "direction": "out", "type": "tensor" }] }, { "kind": "Transpose", "category": "reshape", "label": "\u4ea4\u6362\u4e24\u8f74", "description": "\u4ea4\u6362\u4e24\u4e2a\u6307\u5b9a\u7ef4\u5ea6\uff0c\u4fdd\u7559\u5143\u7d20\u4e0e\u7c7b\u578b\u3002", "defaults": { "dim0": -2, "dim1": -1 }, "parameters": [{ "name": "dim0", "type": "integer", "default": -2, "min": -8, "max": 7 }, { "name": "dim1", "type": "integer", "default": -1, "min": -8, "max": 7 }], "ports": [{ "id": "input", "name": "input", "direction": "in", "type": "tensor" }, { "id": "output", "name": "output", "direction": "out", "type": "tensor" }] }, { "kind": "Permute", "category": "reshape", "label": "\u91cd\u6392\u7ef4\u5ea6", "description": "\u5b8c\u6574\u5217\u51fa\u7ef4\u5ea6\u987a\u5e8f\uff0c\u6bcf\u4e2a\u8f74\u5fc5\u987b\u6070\u597d\u51fa\u73b0\u4e00\u6b21\u3002", "defaults": { "dims": [0, 2, 1] }, "parameters": [{ "name": "dims", "type": "integer-array", "default": [0, 2, 1], "min": 0, "max": 7, "minLength": 1, "maxLength": 8 }], "ports": [{ "id": "input", "name": "input", "direction": "in", "type": "tensor" }, { "id": "output", "name": "output", "direction": "out", "type": "tensor" }] }, { "kind": "Unsqueeze", "category": "reshape", "label": "\u65b0\u589e\u5355\u4f4d\u8f74", "description": "\u5728\u6307\u5b9a\u4f4d\u7f6e\u63d2\u5165\u5927\u5c0f\u4e3a 1 \u7684\u8f74\u3002", "defaults": { "dim": 1 }, "parameters": [{ "name": "dim", "type": "integer", "default": 1, "min": -9, "max": 8 }], "ports": [{ "id": "input", "name": "input", "direction": "in", "type": "tensor" }, { "id": "output", "name": "output", "direction": "out", "type": "tensor" }] }, { "kind": "Squeeze", "category": "reshape", "label": "\u79fb\u9664\u5355\u4f4d\u8f74", "description": "\u4ec5\u79fb\u9664\u6307\u5b9a\u5927\u5c0f\u4e3a 1 \u7684\u8f74\uff0c\u907f\u514d\u9690\u5f0f\u4e22\u5931\u6279\u6b21\u3002", "defaults": { "dim": 1 }, "parameters": [{ "name": "dim", "type": "integer", "default": 1, "min": -8, "max": 7 }], "ports": [{ "id": "input", "name": "input", "direction": "in", "type": "tensor" }, { "id": "output", "name": "output", "direction": "out", "type": "tensor" }] }, { "kind": "ReLU", "category": "activation", "label": "ReLU \u6fc0\u6d3b", "description": "\u9010\u5143\u7d20\u6d6e\u70b9\u6fc0\u6d3b\uff0c\u4fdd\u7559\u5f62\u72b6\uff1bSoftmax \u6309\u6307\u5b9a\u8f74\u5f52\u4e00\u5316\u3002", "defaults": {}, "parameters": [], "ports": [{ "id": "input", "name": "input", "direction": "in", "type": "tensor" }, { "id": "output", "name": "output", "direction": "out", "type": "tensor" }] }, { "kind": "GELU", "category": "activation", "label": "GELU \u6fc0\u6d3b", "description": "\u9010\u5143\u7d20\u6d6e\u70b9\u6fc0\u6d3b\uff0c\u4fdd\u7559\u5f62\u72b6\uff1bSoftmax \u6309\u6307\u5b9a\u8f74\u5f52\u4e00\u5316\u3002", "defaults": { "approximate": "none" }, "parameters": [{ "name": "approximate", "type": "choice", "default": "none", "options": ["none", "tanh"] }], "ports": [{ "id": "input", "name": "input", "direction": "in", "type": "tensor" }, { "id": "output", "name": "output", "direction": "out", "type": "tensor" }] }, { "kind": "SiLU", "category": "activation", "label": "SiLU / Swish \u6fc0\u6d3b", "description": "\u9010\u5143\u7d20\u6d6e\u70b9\u6fc0\u6d3b\uff0c\u4fdd\u7559\u5f62\u72b6\uff1bSoftmax \u6309\u6307\u5b9a\u8f74\u5f52\u4e00\u5316\u3002", "defaults": {}, "parameters": [], "ports": [{ "id": "input", "name": "input", "direction": "in", "type": "tensor" }, { "id": "output", "name": "output", "direction": "out", "type": "tensor" }] }, { "kind": "Sigmoid", "category": "activation", "label": "Sigmoid \u6fc0\u6d3b", "description": "\u9010\u5143\u7d20\u6d6e\u70b9\u6fc0\u6d3b\uff0c\u4fdd\u7559\u5f62\u72b6\uff1bSoftmax \u6309\u6307\u5b9a\u8f74\u5f52\u4e00\u5316\u3002", "defaults": {}, "parameters": [], "ports": [{ "id": "input", "name": "input", "direction": "in", "type": "tensor" }, { "id": "output", "name": "output", "direction": "out", "type": "tensor" }] }, { "kind": "Tanh", "category": "activation", "label": "Tanh \u6fc0\u6d3b", "description": "\u9010\u5143\u7d20\u6d6e\u70b9\u6fc0\u6d3b\uff0c\u4fdd\u7559\u5f62\u72b6\uff1bSoftmax \u6309\u6307\u5b9a\u8f74\u5f52\u4e00\u5316\u3002", "defaults": {}, "parameters": [], "ports": [{ "id": "input", "name": "input", "direction": "in", "type": "tensor" }, { "id": "output", "name": "output", "direction": "out", "type": "tensor" }] }, { "kind": "ReLU6", "category": "activation", "label": "ReLU6 \u6fc0\u6d3b", "description": "\u9010\u5143\u7d20\u6d6e\u70b9\u6fc0\u6d3b\uff0c\u4fdd\u7559\u5f62\u72b6\uff1bSoftmax \u6309\u6307\u5b9a\u8f74\u5f52\u4e00\u5316\u3002", "defaults": {}, "parameters": [], "ports": [{ "id": "input", "name": "input", "direction": "in", "type": "tensor" }, { "id": "output", "name": "output", "direction": "out", "type": "tensor" }] }, { "kind": "LeakyReLU", "category": "activation", "label": "Leaky ReLU \u6fc0\u6d3b", "description": "\u9010\u5143\u7d20\u6d6e\u70b9\u6fc0\u6d3b\uff0c\u4fdd\u7559\u5f62\u72b6\uff1bSoftmax \u6309\u6307\u5b9a\u8f74\u5f52\u4e00\u5316\u3002", "defaults": { "negative_slope": 0.01 }, "parameters": [{ "name": "negative_slope", "type": "number", "default": 0.01, "min": 0, "max": 100 }], "ports": [{ "id": "input", "name": "input", "direction": "in", "type": "tensor" }, { "id": "output", "name": "output", "direction": "out", "type": "tensor" }] }, { "kind": "ELU", "category": "activation", "label": "ELU \u6fc0\u6d3b", "description": "\u9010\u5143\u7d20\u6d6e\u70b9\u6fc0\u6d3b\uff0c\u4fdd\u7559\u5f62\u72b6\uff1bSoftmax \u6309\u6307\u5b9a\u8f74\u5f52\u4e00\u5316\u3002", "defaults": { "alpha": 1.0 }, "parameters": [{ "name": "alpha", "type": "number", "default": 1.0, "min": 0, "max": 100 }], "ports": [{ "id": "input", "name": "input", "direction": "in", "type": "tensor" }, { "id": "output", "name": "output", "direction": "out", "type": "tensor" }] }, { "kind": "SELU", "category": "activation", "label": "SELU \u6fc0\u6d3b", "description": "\u9010\u5143\u7d20\u6d6e\u70b9\u6fc0\u6d3b\uff0c\u4fdd\u7559\u5f62\u72b6\uff1bSoftmax \u6309\u6307\u5b9a\u8f74\u5f52\u4e00\u5316\u3002", "defaults": {}, "parameters": [], "ports": [{ "id": "input", "name": "input", "direction": "in", "type": "tensor" }, { "id": "output", "name": "output", "direction": "out", "type": "tensor" }] }, { "kind": "Softplus", "category": "activation", "label": "Softplus \u6fc0\u6d3b", "description": "\u9010\u5143\u7d20\u6d6e\u70b9\u6fc0\u6d3b\uff0c\u4fdd\u7559\u5f62\u72b6\uff1bSoftmax \u6309\u6307\u5b9a\u8f74\u5f52\u4e00\u5316\u3002", "defaults": { "beta": 1.0, "threshold": 20.0 }, "parameters": [{ "name": "beta", "type": "number", "default": 1.0, "min": 1e-06, "max": 100 }, { "name": "threshold", "type": "number", "default": 20.0, "min": 1e-06, "max": 1000 }], "ports": [{ "id": "input", "name": "input", "direction": "in", "type": "tensor" }, { "id": "output", "name": "output", "direction": "out", "type": "tensor" }] }, { "kind": "Softsign", "category": "activation", "label": "Softsign \u6fc0\u6d3b", "description": "\u9010\u5143\u7d20\u6d6e\u70b9\u6fc0\u6d3b\uff0c\u4fdd\u7559\u5f62\u72b6\uff1bSoftmax \u6309\u6307\u5b9a\u8f74\u5f52\u4e00\u5316\u3002", "defaults": {}, "parameters": [], "ports": [{ "id": "input", "name": "input", "direction": "in", "type": "tensor" }, { "id": "output", "name": "output", "direction": "out", "type": "tensor" }] }, { "kind": "Hardsigmoid", "category": "activation", "label": "Hard Sigmoid \u6fc0\u6d3b", "description": "\u9010\u5143\u7d20\u6d6e\u70b9\u6fc0\u6d3b\uff0c\u4fdd\u7559\u5f62\u72b6\uff1bSoftmax \u6309\u6307\u5b9a\u8f74\u5f52\u4e00\u5316\u3002", "defaults": {}, "parameters": [], "ports": [{ "id": "input", "name": "input", "direction": "in", "type": "tensor" }, { "id": "output", "name": "output", "direction": "out", "type": "tensor" }] }, { "kind": "Hardswish", "category": "activation", "label": "Hard Swish \u6fc0\u6d3b", "description": "\u9010\u5143\u7d20\u6d6e\u70b9\u6fc0\u6d3b\uff0c\u4fdd\u7559\u5f62\u72b6\uff1bSoftmax \u6309\u6307\u5b9a\u8f74\u5f52\u4e00\u5316\u3002", "defaults": {}, "parameters": [], "ports": [{ "id": "input", "name": "input", "direction": "in", "type": "tensor" }, { "id": "output", "name": "output", "direction": "out", "type": "tensor" }] }, { "kind": "PReLU", "category": "activation", "label": "\u53ef\u5b66\u4e60 PReLU", "description": "\u9010\u5143\u7d20\u6d6e\u70b9\u6fc0\u6d3b\uff0c\u4fdd\u7559\u5f62\u72b6\uff1bSoftmax \u6309\u6307\u5b9a\u8f74\u5f52\u4e00\u5316\u3002", "defaults": { "num_parameters": 1, "init": 0.25 }, "parameters": [{ "name": "num_parameters", "type": "integer", "default": 1, "min": 1, "max": 1000000 }, { "name": "init", "type": "number", "default": 0.25, "min": -100, "max": 100 }], "ports": [{ "id": "input", "name": "input", "direction": "in", "type": "tensor" }, { "id": "output", "name": "output", "direction": "out", "type": "tensor" }] }, { "kind": "Softmax", "category": "activation", "label": "Softmax \u6982\u7387", "description": "\u9010\u5143\u7d20\u6d6e\u70b9\u6fc0\u6d3b\uff0c\u4fdd\u7559\u5f62\u72b6\uff1bSoftmax \u6309\u6307\u5b9a\u8f74\u5f52\u4e00\u5316\u3002", "defaults": { "dim": -1 }, "parameters": [{ "name": "dim", "type": "integer", "default": -1, "min": -8, "max": 7 }], "ports": [{ "id": "input", "name": "input", "direction": "in", "type": "tensor" }, { "id": "output", "name": "output", "direction": "out", "type": "tensor" }] }, { "kind": "LogSoftmax", "category": "activation", "label": "Log Softmax", "description": "\u9010\u5143\u7d20\u6d6e\u70b9\u6fc0\u6d3b\uff0c\u4fdd\u7559\u5f62\u72b6\uff1bSoftmax \u6309\u6307\u5b9a\u8f74\u5f52\u4e00\u5316\u3002", "defaults": { "dim": -1 }, "parameters": [{ "name": "dim", "type": "integer", "default": -1, "min": -8, "max": 7 }], "ports": [{ "id": "input", "name": "input", "direction": "in", "type": "tensor" }, { "id": "output", "name": "output", "direction": "out", "type": "tensor" }] }, { "kind": "Dropout", "category": "regularization", "label": "Dropout \u968f\u673a\u5931\u6d3b", "description": "\u975e\u539f\u5730\u968f\u673a\u5931\u6d3b\uff1b\u8bad\u7ec3\u4e0e\u8bc4\u4f30\u884c\u4e3a\u4e0d\u540c\uff0c\u4e0d\u8bc1\u660e\u6570\u503c\u6548\u679c\u3002", "defaults": { "p": 0.1 }, "parameters": [{ "name": "p", "type": "number", "default": 0.1, "min": 0, "max": 1 }], "ports": [{ "id": "input", "name": "input", "direction": "in", "type": "tensor" }, { "id": "output", "name": "output", "direction": "out", "type": "tensor" }] }, { "kind": "Dropout1d", "category": "regularization", "label": "Dropout1d \u968f\u673a\u5931\u6d3b", "description": "\u975e\u539f\u5730\u968f\u673a\u5931\u6d3b\uff1b\u8bad\u7ec3\u4e0e\u8bc4\u4f30\u884c\u4e3a\u4e0d\u540c\uff0c\u4e0d\u8bc1\u660e\u6570\u503c\u6548\u679c\u3002", "defaults": { "p": 0.1 }, "parameters": [{ "name": "p", "type": "number", "default": 0.1, "min": 0, "max": 1 }], "ports": [{ "id": "input", "name": "input", "direction": "in", "type": "tensor" }, { "id": "output", "name": "output", "direction": "out", "type": "tensor" }] }, { "kind": "Dropout2d", "category": "regularization", "label": "Dropout2d \u968f\u673a\u5931\u6d3b", "description": "\u975e\u539f\u5730\u968f\u673a\u5931\u6d3b\uff1b\u8bad\u7ec3\u4e0e\u8bc4\u4f30\u884c\u4e3a\u4e0d\u540c\uff0c\u4e0d\u8bc1\u660e\u6570\u503c\u6548\u679c\u3002", "defaults": { "p": 0.1 }, "parameters": [{ "name": "p", "type": "number", "default": 0.1, "min": 0, "max": 1 }], "ports": [{ "id": "input", "name": "input", "direction": "in", "type": "tensor" }, { "id": "output", "name": "output", "direction": "out", "type": "tensor" }] }, { "kind": "Dropout3d", "category": "regularization", "label": "Dropout3d \u968f\u673a\u5931\u6d3b", "description": "\u975e\u539f\u5730\u968f\u673a\u5931\u6d3b\uff1b\u8bad\u7ec3\u4e0e\u8bc4\u4f30\u884c\u4e3a\u4e0d\u540c\uff0c\u4e0d\u8bc1\u660e\u6570\u503c\u6548\u679c\u3002", "defaults": { "p": 0.1 }, "parameters": [{ "name": "p", "type": "number", "default": 0.1, "min": 0, "max": 1 }], "ports": [{ "id": "input", "name": "input", "direction": "in", "type": "tensor" }, { "id": "output", "name": "output", "direction": "out", "type": "tensor" }] }, { "kind": "AlphaDropout", "category": "regularization", "label": "AlphaDropout \u968f\u673a\u5931\u6d3b", "description": "\u975e\u539f\u5730\u968f\u673a\u5931\u6d3b\uff1b\u8bad\u7ec3\u4e0e\u8bc4\u4f30\u884c\u4e3a\u4e0d\u540c\uff0c\u4e0d\u8bc1\u660e\u6570\u503c\u6548\u679c\u3002", "defaults": { "p": 0.1 }, "parameters": [{ "name": "p", "type": "number", "default": 0.1, "min": 0, "max": 1 }], "ports": [{ "id": "input", "name": "input", "direction": "in", "type": "tensor" }, { "id": "output", "name": "output", "direction": "out", "type": "tensor" }] }, { "kind": "FeatureAlphaDropout", "category": "regularization", "label": "FeatureAlphaDropout \u968f\u673a\u5931\u6d3b", "description": "\u975e\u539f\u5730\u968f\u673a\u5931\u6d3b\uff1b\u8bad\u7ec3\u4e0e\u8bc4\u4f30\u884c\u4e3a\u4e0d\u540c\uff0c\u4e0d\u8bc1\u660e\u6570\u503c\u6548\u679c\u3002", "defaults": { "p": 0.1 }, "parameters": [{ "name": "p", "type": "number", "default": 0.1, "min": 0, "max": 1 }], "ports": [{ "id": "input", "name": "input", "direction": "in", "type": "tensor" }, { "id": "output", "name": "output", "direction": "out", "type": "tensor" }] }, { "kind": "Conv1d", "category": "convolution", "label": "1\u7ef4\u5377\u79ef", "description": "float32 \u901a\u9053\u4f18\u5148\u5f20\u91cf\uff0c\u652f\u6301\u6279\u6b21\u6216\u65e0\u6279\u6b21\uff1b\u5206\u7ec4\u987b\u6574\u9664\u8f93\u5165\u8f93\u51fa\u901a\u9053\u3002", "defaults": { "in_channels": 3, "out_channels": 16, "kernel_size": [3], "stride": [1], "padding": [0], "dilation": [1], "groups": 1, "bias": true }, "parameters": [{ "name": "in_channels", "type": "integer", "default": 3, "min": 1, "max": 1000000 }, { "name": "out_channels", "type": "integer", "default": 16, "min": 1, "max": 1000000 }, { "name": "kernel_size", "type": "integer-array", "default": [3], "min": 1, "max": 10000, "length": 1 }, { "name": "stride", "type": "integer-array", "default": [1], "min": 1, "max": 10000, "length": 1 }, { "name": "padding", "type": "integer-array", "default": [0], "min": 0, "max": 10000, "length": 1 }, { "name": "dilation", "type": "integer-array", "default": [1], "min": 1, "max": 10000, "length": 1 }, { "name": "groups", "type": "integer", "default": 1, "min": 1, "max": 1000000 }, { "name": "bias", "type": "boolean", "default": true }], "ports": [{ "id": "input", "name": "input", "direction": "in", "type": "tensor" }, { "id": "output", "name": "output", "direction": "out", "type": "tensor" }] }, { "kind": "ConvTranspose1d", "category": "convolution", "label": "1\u7ef4\u8f6c\u7f6e\u5377\u79ef", "description": "float32 \u901a\u9053\u4f18\u5148\u5f20\u91cf\uff0c\u652f\u6301\u6279\u6b21\u6216\u65e0\u6279\u6b21\uff1b\u5206\u7ec4\u987b\u6574\u9664\u8f93\u5165\u8f93\u51fa\u901a\u9053\u3002", "defaults": { "in_channels": 3, "out_channels": 16, "kernel_size": [3], "stride": [1], "padding": [0], "output_padding": [0], "dilation": [1], "groups": 1, "bias": true }, "parameters": [{ "name": "in_channels", "type": "integer", "default": 3, "min": 1, "max": 1000000 }, { "name": "out_channels", "type": "integer", "default": 16, "min": 1, "max": 1000000 }, { "name": "kernel_size", "type": "integer-array", "default": [3], "min": 1, "max": 10000, "length": 1 }, { "name": "stride", "type": "integer-array", "default": [1], "min": 1, "max": 10000, "length": 1 }, { "name": "padding", "type": "integer-array", "default": [0], "min": 0, "max": 10000, "length": 1 }, { "name": "output_padding", "type": "integer-array", "default": [0], "min": 0, "max": 10000, "length": 1 }, { "name": "dilation", "type": "integer-array", "default": [1], "min": 1, "max": 10000, "length": 1 }, { "name": "groups", "type": "integer", "default": 1, "min": 1, "max": 1000000 }, { "name": "bias", "type": "boolean", "default": true }], "ports": [{ "id": "input", "name": "input", "direction": "in", "type": "tensor" }, { "id": "output", "name": "output", "direction": "out", "type": "tensor" }] }, { "kind": "MaxPool1d", "category": "pooling", "label": "1\u7ef4\u6700\u5927\u6c60\u5316", "description": "\u6d6e\u70b9\u901a\u9053\u4f18\u5148\u5f20\u91cf\uff0c\u663e\u5f0f\u7a97\u53e3\u4e0e\u6b65\u957f\uff1b\u6700\u5927\u6c60\u5316\u4ec5\u8fd4\u56de\u7ed3\u679c\u5f20\u91cf\u3002", "defaults": { "kernel_size": [2], "stride": [2], "padding": [0], "dilation": [1], "ceil_mode": false }, "parameters": [{ "name": "kernel_size", "type": "integer-array", "default": [2], "min": 1, "max": 10000, "length": 1 }, { "name": "stride", "type": "integer-array", "default": [2], "min": 1, "max": 10000, "length": 1 }, { "name": "padding", "type": "integer-array", "default": [0], "min": 0, "max": 10000, "length": 1 }, { "name": "dilation", "type": "integer-array", "default": [1], "min": 1, "max": 10000, "length": 1 }, { "name": "ceil_mode", "type": "boolean", "default": false }], "ports": [{ "id": "input", "name": "input", "direction": "in", "type": "tensor" }, { "id": "output", "name": "output", "direction": "out", "type": "tensor" }] }, { "kind": "AdaptiveMaxPool1d", "category": "pooling", "label": "1\u7ef4\u81ea\u9002\u5e94\u6700\u5927\u6c60\u5316", "description": "\u56fa\u5b9a\u8f93\u51fa\u7a7a\u95f4\u5c3a\u5bf8\uff1b\u4ec5\u8fd4\u56de\u7ed3\u679c\u5f20\u91cf\uff0c\u4e0d\u8fd4\u56de\u6700\u5927\u503c\u7d22\u5f15\u3002", "defaults": { "output_size": [1] }, "parameters": [{ "name": "output_size", "type": "integer-array", "default": [1], "min": 1, "max": 10000, "length": 1 }], "ports": [{ "id": "input", "name": "input", "direction": "in", "type": "tensor" }, { "id": "output", "name": "output", "direction": "out", "type": "tensor" }] }, { "kind": "AvgPool1d", "category": "pooling", "label": "1\u7ef4\u5e73\u5747\u6c60\u5316", "description": "\u6d6e\u70b9\u901a\u9053\u4f18\u5148\u5f20\u91cf\uff0c\u663e\u5f0f\u7a97\u53e3\u4e0e\u6b65\u957f\uff1b\u6700\u5927\u6c60\u5316\u4ec5\u8fd4\u56de\u7ed3\u679c\u5f20\u91cf\u3002", "defaults": { "kernel_size": [2], "stride": [2], "padding": [0], "ceil_mode": false, "count_include_pad": true }, "parameters": [{ "name": "kernel_size", "type": "integer-array", "default": [2], "min": 1, "max": 10000, "length": 1 }, { "name": "stride", "type": "integer-array", "default": [2], "min": 1, "max": 10000, "length": 1 }, { "name": "padding", "type": "integer-array", "default": [0], "min": 0, "max": 10000, "length": 1 }, { "name": "ceil_mode", "type": "boolean", "default": false }, { "name": "count_include_pad", "type": "boolean", "default": true }], "ports": [{ "id": "input", "name": "input", "direction": "in", "type": "tensor" }, { "id": "output", "name": "output", "direction": "out", "type": "tensor" }] }, { "kind": "AdaptiveAvgPool1d", "category": "pooling", "label": "1\u7ef4\u81ea\u9002\u5e94\u5e73\u5747\u6c60\u5316", "description": "\u56fa\u5b9a\u8f93\u51fa\u7a7a\u95f4\u5c3a\u5bf8\uff1b\u4ec5\u8fd4\u56de\u7ed3\u679c\u5f20\u91cf\uff0c\u4e0d\u8fd4\u56de\u6700\u5927\u503c\u7d22\u5f15\u3002", "defaults": { "output_size": [1] }, "parameters": [{ "name": "output_size", "type": "integer-array", "default": [1], "min": 1, "max": 10000, "length": 1 }], "ports": [{ "id": "input", "name": "input", "direction": "in", "type": "tensor" }, { "id": "output", "name": "output", "direction": "out", "type": "tensor" }] }, { "kind": "BatchNorm1d", "category": "normalization", "label": "1\u7ef4\u6279\u5f52\u4e00\u5316", "description": "float32 \u901a\u9053\u5f52\u4e00\u5316\uff1b\u8bad\u7ec3\u517c\u5bb9\u9759\u6001\u68c0\u67e5\u8981\u6c42\u8db3\u591f\u7684\u901a\u9053\u91c7\u6837\u3002", "defaults": { "num_features": 16, "eps": 1e-05, "momentum": 0.1, "affine": true, "track_running_stats": true }, "parameters": [{ "name": "num_features", "type": "integer", "default": 16, "min": 1, "max": 1000000 }, { "name": "eps", "type": "number", "default": 1e-05, "min": 1e-12, "max": 1 }, { "name": "momentum", "type": "number", "default": 0.1, "min": 0, "max": 1 }, { "name": "affine", "type": "boolean", "default": true }, { "name": "track_running_stats", "type": "boolean", "default": true }], "ports": [{ "id": "input", "name": "input", "direction": "in", "type": "tensor" }, { "id": "output", "name": "output", "direction": "out", "type": "tensor" }] }, { "kind": "InstanceNorm1d", "category": "normalization", "label": "1\u7ef4\u5b9e\u4f8b\u5f52\u4e00\u5316", "description": "float32 \u901a\u9053\u5f52\u4e00\u5316\uff1b\u8bad\u7ec3\u517c\u5bb9\u9759\u6001\u68c0\u67e5\u8981\u6c42\u8db3\u591f\u7684\u901a\u9053\u91c7\u6837\u3002", "defaults": { "num_features": 16, "eps": 1e-05, "momentum": 0.1, "affine": false, "track_running_stats": false }, "parameters": [{ "name": "num_features", "type": "integer", "default": 16, "min": 1, "max": 1000000 }, { "name": "eps", "type": "number", "default": 1e-05, "min": 1e-12, "max": 1 }, { "name": "momentum", "type": "number", "default": 0.1, "min": 0, "max": 1 }, { "name": "affine", "type": "boolean", "default": false }, { "name": "track_running_stats", "type": "boolean", "default": false }], "ports": [{ "id": "input", "name": "input", "direction": "in", "type": "tensor" }, { "id": "output", "name": "output", "direction": "out", "type": "tensor" }] }, { "kind": "Conv2d", "category": "convolution", "label": "2\u7ef4\u5377\u79ef", "description": "float32 \u901a\u9053\u4f18\u5148\u5f20\u91cf\uff0c\u652f\u6301\u6279\u6b21\u6216\u65e0\u6279\u6b21\uff1b\u5206\u7ec4\u987b\u6574\u9664\u8f93\u5165\u8f93\u51fa\u901a\u9053\u3002", "defaults": { "in_channels": 3, "out_channels": 16, "kernel_size": [3, 3], "stride": [1, 1], "padding": [0, 0], "dilation": [1, 1], "groups": 1, "bias": true }, "parameters": [{ "name": "in_channels", "type": "integer", "default": 3, "min": 1, "max": 1000000 }, { "name": "out_channels", "type": "integer", "default": 16, "min": 1, "max": 1000000 }, { "name": "kernel_size", "type": "integer-array", "default": [3, 3], "min": 1, "max": 10000, "length": 2 }, { "name": "stride", "type": "integer-array", "default": [1, 1], "min": 1, "max": 10000, "length": 2 }, { "name": "padding", "type": "integer-array", "default": [0, 0], "min": 0, "max": 10000, "length": 2 }, { "name": "dilation", "type": "integer-array", "default": [1, 1], "min": 1, "max": 10000, "length": 2 }, { "name": "groups", "type": "integer", "default": 1, "min": 1, "max": 1000000 }, { "name": "bias", "type": "boolean", "default": true }], "ports": [{ "id": "input", "name": "input", "direction": "in", "type": "tensor" }, { "id": "output", "name": "output", "direction": "out", "type": "tensor" }] }, { "kind": "ConvTranspose2d", "category": "convolution", "label": "2\u7ef4\u8f6c\u7f6e\u5377\u79ef", "description": "float32 \u901a\u9053\u4f18\u5148\u5f20\u91cf\uff0c\u652f\u6301\u6279\u6b21\u6216\u65e0\u6279\u6b21\uff1b\u5206\u7ec4\u987b\u6574\u9664\u8f93\u5165\u8f93\u51fa\u901a\u9053\u3002", "defaults": { "in_channels": 3, "out_channels": 16, "kernel_size": [3, 3], "stride": [1, 1], "padding": [0, 0], "output_padding": [0, 0], "dilation": [1, 1], "groups": 1, "bias": true }, "parameters": [{ "name": "in_channels", "type": "integer", "default": 3, "min": 1, "max": 1000000 }, { "name": "out_channels", "type": "integer", "default": 16, "min": 1, "max": 1000000 }, { "name": "kernel_size", "type": "integer-array", "default": [3, 3], "min": 1, "max": 10000, "length": 2 }, { "name": "stride", "type": "integer-array", "default": [1, 1], "min": 1, "max": 10000, "length": 2 }, { "name": "padding", "type": "integer-array", "default": [0, 0], "min": 0, "max": 10000, "length": 2 }, { "name": "output_padding", "type": "integer-array", "default": [0, 0], "min": 0, "max": 10000, "length": 2 }, { "name": "dilation", "type": "integer-array", "default": [1, 1], "min": 1, "max": 10000, "length": 2 }, { "name": "groups", "type": "integer", "default": 1, "min": 1, "max": 1000000 }, { "name": "bias", "type": "boolean", "default": true }], "ports": [{ "id": "input", "name": "input", "direction": "in", "type": "tensor" }, { "id": "output", "name": "output", "direction": "out", "type": "tensor" }] }, { "kind": "MaxPool2d", "category": "pooling", "label": "2\u7ef4\u6700\u5927\u6c60\u5316", "description": "\u6d6e\u70b9\u901a\u9053\u4f18\u5148\u5f20\u91cf\uff0c\u663e\u5f0f\u7a97\u53e3\u4e0e\u6b65\u957f\uff1b\u6700\u5927\u6c60\u5316\u4ec5\u8fd4\u56de\u7ed3\u679c\u5f20\u91cf\u3002", "defaults": { "kernel_size": [2, 2], "stride": [2, 2], "padding": [0, 0], "dilation": [1, 1], "ceil_mode": false }, "parameters": [{ "name": "kernel_size", "type": "integer-array", "default": [2, 2], "min": 1, "max": 10000, "length": 2 }, { "name": "stride", "type": "integer-array", "default": [2, 2], "min": 1, "max": 10000, "length": 2 }, { "name": "padding", "type": "integer-array", "default": [0, 0], "min": 0, "max": 10000, "length": 2 }, { "name": "dilation", "type": "integer-array", "default": [1, 1], "min": 1, "max": 10000, "length": 2 }, { "name": "ceil_mode", "type": "boolean", "default": false }], "ports": [{ "id": "input", "name": "input", "direction": "in", "type": "tensor" }, { "id": "output", "name": "output", "direction": "out", "type": "tensor" }] }, { "kind": "AdaptiveMaxPool2d", "category": "pooling", "label": "2\u7ef4\u81ea\u9002\u5e94\u6700\u5927\u6c60\u5316", "description": "\u56fa\u5b9a\u8f93\u51fa\u7a7a\u95f4\u5c3a\u5bf8\uff1b\u4ec5\u8fd4\u56de\u7ed3\u679c\u5f20\u91cf\uff0c\u4e0d\u8fd4\u56de\u6700\u5927\u503c\u7d22\u5f15\u3002", "defaults": { "output_size": [1, 1] }, "parameters": [{ "name": "output_size", "type": "integer-array", "default": [1, 1], "min": 1, "max": 10000, "length": 2 }], "ports": [{ "id": "input", "name": "input", "direction": "in", "type": "tensor" }, { "id": "output", "name": "output", "direction": "out", "type": "tensor" }] }, { "kind": "AvgPool2d", "category": "pooling", "label": "2\u7ef4\u5e73\u5747\u6c60\u5316", "description": "\u6d6e\u70b9\u901a\u9053\u4f18\u5148\u5f20\u91cf\uff0c\u663e\u5f0f\u7a97\u53e3\u4e0e\u6b65\u957f\uff1b\u6700\u5927\u6c60\u5316\u4ec5\u8fd4\u56de\u7ed3\u679c\u5f20\u91cf\u3002", "defaults": { "kernel_size": [2, 2], "stride": [2, 2], "padding": [0, 0], "ceil_mode": false, "count_include_pad": true }, "parameters": [{ "name": "kernel_size", "type": "integer-array", "default": [2, 2], "min": 1, "max": 10000, "length": 2 }, { "name": "stride", "type": "integer-array", "default": [2, 2], "min": 1, "max": 10000, "length": 2 }, { "name": "padding", "type": "integer-array", "default": [0, 0], "min": 0, "max": 10000, "length": 2 }, { "name": "ceil_mode", "type": "boolean", "default": false }, { "name": "count_include_pad", "type": "boolean", "default": true }], "ports": [{ "id": "input", "name": "input", "direction": "in", "type": "tensor" }, { "id": "output", "name": "output", "direction": "out", "type": "tensor" }] }, { "kind": "AdaptiveAvgPool2d", "category": "pooling", "label": "2\u7ef4\u81ea\u9002\u5e94\u5e73\u5747\u6c60\u5316", "description": "\u56fa\u5b9a\u8f93\u51fa\u7a7a\u95f4\u5c3a\u5bf8\uff1b\u4ec5\u8fd4\u56de\u7ed3\u679c\u5f20\u91cf\uff0c\u4e0d\u8fd4\u56de\u6700\u5927\u503c\u7d22\u5f15\u3002", "defaults": { "output_size": [1, 1] }, "parameters": [{ "name": "output_size", "type": "integer-array", "default": [1, 1], "min": 1, "max": 10000, "length": 2 }], "ports": [{ "id": "input", "name": "input", "direction": "in", "type": "tensor" }, { "id": "output", "name": "output", "direction": "out", "type": "tensor" }] }, { "kind": "BatchNorm2d", "category": "normalization", "label": "2\u7ef4\u6279\u5f52\u4e00\u5316", "description": "float32 \u901a\u9053\u5f52\u4e00\u5316\uff1b\u8bad\u7ec3\u517c\u5bb9\u9759\u6001\u68c0\u67e5\u8981\u6c42\u8db3\u591f\u7684\u901a\u9053\u91c7\u6837\u3002", "defaults": { "num_features": 16, "eps": 1e-05, "momentum": 0.1, "affine": true, "track_running_stats": true }, "parameters": [{ "name": "num_features", "type": "integer", "default": 16, "min": 1, "max": 1000000 }, { "name": "eps", "type": "number", "default": 1e-05, "min": 1e-12, "max": 1 }, { "name": "momentum", "type": "number", "default": 0.1, "min": 0, "max": 1 }, { "name": "affine", "type": "boolean", "default": true }, { "name": "track_running_stats", "type": "boolean", "default": true }], "ports": [{ "id": "input", "name": "input", "direction": "in", "type": "tensor" }, { "id": "output", "name": "output", "direction": "out", "type": "tensor" }] }, { "kind": "InstanceNorm2d", "category": "normalization", "label": "2\u7ef4\u5b9e\u4f8b\u5f52\u4e00\u5316", "description": "float32 \u901a\u9053\u5f52\u4e00\u5316\uff1b\u8bad\u7ec3\u517c\u5bb9\u9759\u6001\u68c0\u67e5\u8981\u6c42\u8db3\u591f\u7684\u901a\u9053\u91c7\u6837\u3002", "defaults": { "num_features": 16, "eps": 1e-05, "momentum": 0.1, "affine": false, "track_running_stats": false }, "parameters": [{ "name": "num_features", "type": "integer", "default": 16, "min": 1, "max": 1000000 }, { "name": "eps", "type": "number", "default": 1e-05, "min": 1e-12, "max": 1 }, { "name": "momentum", "type": "number", "default": 0.1, "min": 0, "max": 1 }, { "name": "affine", "type": "boolean", "default": false }, { "name": "track_running_stats", "type": "boolean", "default": false }], "ports": [{ "id": "input", "name": "input", "direction": "in", "type": "tensor" }, { "id": "output", "name": "output", "direction": "out", "type": "tensor" }] }, { "kind": "Conv3d", "category": "convolution", "label": "3\u7ef4\u5377\u79ef", "description": "float32 \u901a\u9053\u4f18\u5148\u5f20\u91cf\uff0c\u652f\u6301\u6279\u6b21\u6216\u65e0\u6279\u6b21\uff1b\u5206\u7ec4\u987b\u6574\u9664\u8f93\u5165\u8f93\u51fa\u901a\u9053\u3002", "defaults": { "in_channels": 3, "out_channels": 16, "kernel_size": [3, 3, 3], "stride": [1, 1, 1], "padding": [0, 0, 0], "dilation": [1, 1, 1], "groups": 1, "bias": true }, "parameters": [{ "name": "in_channels", "type": "integer", "default": 3, "min": 1, "max": 1000000 }, { "name": "out_channels", "type": "integer", "default": 16, "min": 1, "max": 1000000 }, { "name": "kernel_size", "type": "integer-array", "default": [3, 3, 3], "min": 1, "max": 10000, "length": 3 }, { "name": "stride", "type": "integer-array", "default": [1, 1, 1], "min": 1, "max": 10000, "length": 3 }, { "name": "padding", "type": "integer-array", "default": [0, 0, 0], "min": 0, "max": 10000, "length": 3 }, { "name": "dilation", "type": "integer-array", "default": [1, 1, 1], "min": 1, "max": 10000, "length": 3 }, { "name": "groups", "type": "integer", "default": 1, "min": 1, "max": 1000000 }, { "name": "bias", "type": "boolean", "default": true }], "ports": [{ "id": "input", "name": "input", "direction": "in", "type": "tensor" }, { "id": "output", "name": "output", "direction": "out", "type": "tensor" }] }, { "kind": "ConvTranspose3d", "category": "convolution", "label": "3\u7ef4\u8f6c\u7f6e\u5377\u79ef", "description": "float32 \u901a\u9053\u4f18\u5148\u5f20\u91cf\uff0c\u652f\u6301\u6279\u6b21\u6216\u65e0\u6279\u6b21\uff1b\u5206\u7ec4\u987b\u6574\u9664\u8f93\u5165\u8f93\u51fa\u901a\u9053\u3002", "defaults": { "in_channels": 3, "out_channels": 16, "kernel_size": [3, 3, 3], "stride": [1, 1, 1], "padding": [0, 0, 0], "output_padding": [0, 0, 0], "dilation": [1, 1, 1], "groups": 1, "bias": true }, "parameters": [{ "name": "in_channels", "type": "integer", "default": 3, "min": 1, "max": 1000000 }, { "name": "out_channels", "type": "integer", "default": 16, "min": 1, "max": 1000000 }, { "name": "kernel_size", "type": "integer-array", "default": [3, 3, 3], "min": 1, "max": 10000, "length": 3 }, { "name": "stride", "type": "integer-array", "default": [1, 1, 1], "min": 1, "max": 10000, "length": 3 }, { "name": "padding", "type": "integer-array", "default": [0, 0, 0], "min": 0, "max": 10000, "length": 3 }, { "name": "output_padding", "type": "integer-array", "default": [0, 0, 0], "min": 0, "max": 10000, "length": 3 }, { "name": "dilation", "type": "integer-array", "default": [1, 1, 1], "min": 1, "max": 10000, "length": 3 }, { "name": "groups", "type": "integer", "default": 1, "min": 1, "max": 1000000 }, { "name": "bias", "type": "boolean", "default": true }], "ports": [{ "id": "input", "name": "input", "direction": "in", "type": "tensor" }, { "id": "output", "name": "output", "direction": "out", "type": "tensor" }] }, { "kind": "MaxPool3d", "category": "pooling", "label": "3\u7ef4\u6700\u5927\u6c60\u5316", "description": "\u6d6e\u70b9\u901a\u9053\u4f18\u5148\u5f20\u91cf\uff0c\u663e\u5f0f\u7a97\u53e3\u4e0e\u6b65\u957f\uff1b\u6700\u5927\u6c60\u5316\u4ec5\u8fd4\u56de\u7ed3\u679c\u5f20\u91cf\u3002", "defaults": { "kernel_size": [2, 2, 2], "stride": [2, 2, 2], "padding": [0, 0, 0], "dilation": [1, 1, 1], "ceil_mode": false }, "parameters": [{ "name": "kernel_size", "type": "integer-array", "default": [2, 2, 2], "min": 1, "max": 10000, "length": 3 }, { "name": "stride", "type": "integer-array", "default": [2, 2, 2], "min": 1, "max": 10000, "length": 3 }, { "name": "padding", "type": "integer-array", "default": [0, 0, 0], "min": 0, "max": 10000, "length": 3 }, { "name": "dilation", "type": "integer-array", "default": [1, 1, 1], "min": 1, "max": 10000, "length": 3 }, { "name": "ceil_mode", "type": "boolean", "default": false }], "ports": [{ "id": "input", "name": "input", "direction": "in", "type": "tensor" }, { "id": "output", "name": "output", "direction": "out", "type": "tensor" }] }, { "kind": "AdaptiveMaxPool3d", "category": "pooling", "label": "3\u7ef4\u81ea\u9002\u5e94\u6700\u5927\u6c60\u5316", "description": "\u56fa\u5b9a\u8f93\u51fa\u7a7a\u95f4\u5c3a\u5bf8\uff1b\u4ec5\u8fd4\u56de\u7ed3\u679c\u5f20\u91cf\uff0c\u4e0d\u8fd4\u56de\u6700\u5927\u503c\u7d22\u5f15\u3002", "defaults": { "output_size": [1, 1, 1] }, "parameters": [{ "name": "output_size", "type": "integer-array", "default": [1, 1, 1], "min": 1, "max": 10000, "length": 3 }], "ports": [{ "id": "input", "name": "input", "direction": "in", "type": "tensor" }, { "id": "output", "name": "output", "direction": "out", "type": "tensor" }] }, { "kind": "AvgPool3d", "category": "pooling", "label": "3\u7ef4\u5e73\u5747\u6c60\u5316", "description": "\u6d6e\u70b9\u901a\u9053\u4f18\u5148\u5f20\u91cf\uff0c\u663e\u5f0f\u7a97\u53e3\u4e0e\u6b65\u957f\uff1b\u6700\u5927\u6c60\u5316\u4ec5\u8fd4\u56de\u7ed3\u679c\u5f20\u91cf\u3002", "defaults": { "kernel_size": [2, 2, 2], "stride": [2, 2, 2], "padding": [0, 0, 0], "ceil_mode": false, "count_include_pad": true }, "parameters": [{ "name": "kernel_size", "type": "integer-array", "default": [2, 2, 2], "min": 1, "max": 10000, "length": 3 }, { "name": "stride", "type": "integer-array", "default": [2, 2, 2], "min": 1, "max": 10000, "length": 3 }, { "name": "padding", "type": "integer-array", "default": [0, 0, 0], "min": 0, "max": 10000, "length": 3 }, { "name": "ceil_mode", "type": "boolean", "default": false }, { "name": "count_include_pad", "type": "boolean", "default": true }], "ports": [{ "id": "input", "name": "input", "direction": "in", "type": "tensor" }, { "id": "output", "name": "output", "direction": "out", "type": "tensor" }] }, { "kind": "AdaptiveAvgPool3d", "category": "pooling", "label": "3\u7ef4\u81ea\u9002\u5e94\u5e73\u5747\u6c60\u5316", "description": "\u56fa\u5b9a\u8f93\u51fa\u7a7a\u95f4\u5c3a\u5bf8\uff1b\u4ec5\u8fd4\u56de\u7ed3\u679c\u5f20\u91cf\uff0c\u4e0d\u8fd4\u56de\u6700\u5927\u503c\u7d22\u5f15\u3002", "defaults": { "output_size": [1, 1, 1] }, "parameters": [{ "name": "output_size", "type": "integer-array", "default": [1, 1, 1], "min": 1, "max": 10000, "length": 3 }], "ports": [{ "id": "input", "name": "input", "direction": "in", "type": "tensor" }, { "id": "output", "name": "output", "direction": "out", "type": "tensor" }] }, { "kind": "BatchNorm3d", "category": "normalization", "label": "3\u7ef4\u6279\u5f52\u4e00\u5316", "description": "float32 \u901a\u9053\u5f52\u4e00\u5316\uff1b\u8bad\u7ec3\u517c\u5bb9\u9759\u6001\u68c0\u67e5\u8981\u6c42\u8db3\u591f\u7684\u901a\u9053\u91c7\u6837\u3002", "defaults": { "num_features": 16, "eps": 1e-05, "momentum": 0.1, "affine": true, "track_running_stats": true }, "parameters": [{ "name": "num_features", "type": "integer", "default": 16, "min": 1, "max": 1000000 }, { "name": "eps", "type": "number", "default": 1e-05, "min": 1e-12, "max": 1 }, { "name": "momentum", "type": "number", "default": 0.1, "min": 0, "max": 1 }, { "name": "affine", "type": "boolean", "default": true }, { "name": "track_running_stats", "type": "boolean", "default": true }], "ports": [{ "id": "input", "name": "input", "direction": "in", "type": "tensor" }, { "id": "output", "name": "output", "direction": "out", "type": "tensor" }] }, { "kind": "InstanceNorm3d", "category": "normalization", "label": "3\u7ef4\u5b9e\u4f8b\u5f52\u4e00\u5316", "description": "float32 \u901a\u9053\u5f52\u4e00\u5316\uff1b\u8bad\u7ec3\u517c\u5bb9\u9759\u6001\u68c0\u67e5\u8981\u6c42\u8db3\u591f\u7684\u901a\u9053\u91c7\u6837\u3002", "defaults": { "num_features": 16, "eps": 1e-05, "momentum": 0.1, "affine": false, "track_running_stats": false }, "parameters": [{ "name": "num_features", "type": "integer", "default": 16, "min": 1, "max": 1000000 }, { "name": "eps", "type": "number", "default": 1e-05, "min": 1e-12, "max": 1 }, { "name": "momentum", "type": "number", "default": 0.1, "min": 0, "max": 1 }, { "name": "affine", "type": "boolean", "default": false }, { "name": "track_running_stats", "type": "boolean", "default": false }], "ports": [{ "id": "input", "name": "input", "direction": "in", "type": "tensor" }, { "id": "output", "name": "output", "direction": "out", "type": "tensor" }] }, { "kind": "LayerNorm", "category": "normalization", "label": "\u5c42\u5f52\u4e00\u5316", "description": "\u5f52\u4e00\u5316\u5339\u914d\u7684\u672b\u5c3e\u7ef4\u5ea6\u3002", "defaults": { "normalized_shape": [16], "eps": 1e-05, "elementwise_affine": true }, "parameters": [{ "name": "normalized_shape", "type": "integer-array", "default": [16], "min": 1, "max": 1000000, "minLength": 1, "maxLength": 8 }, { "name": "eps", "type": "number", "default": 1e-05, "min": 1e-12, "max": 1 }, { "name": "elementwise_affine", "type": "boolean", "default": true }], "ports": [{ "id": "input", "name": "input", "direction": "in", "type": "tensor" }, { "id": "output", "name": "output", "direction": "out", "type": "tensor" }] }, { "kind": "RMSNorm", "category": "normalization", "label": "RMS \u5f52\u4e00\u5316", "description": "\u6309\u672b\u5c3e\u7ef4\u5ea6\u5747\u65b9\u6839\u5f52\u4e00\u5316\uff1b\u9700\u8981\u652f\u6301 RMSNorm \u7684 PyTorch \u7248\u672c\u3002", "defaults": { "normalized_shape": [16], "eps": 1e-05, "elementwise_affine": true }, "parameters": [{ "name": "normalized_shape", "type": "integer-array", "default": [16], "min": 1, "max": 1000000, "minLength": 1, "maxLength": 8 }, { "name": "eps", "type": "number", "default": 1e-05, "min": 1e-12, "max": 1 }, { "name": "elementwise_affine", "type": "boolean", "default": true }], "ports": [{ "id": "input", "name": "input", "direction": "in", "type": "tensor" }, { "id": "output", "name": "output", "direction": "out", "type": "tensor" }] }, { "kind": "GroupNorm", "category": "normalization", "label": "\u5206\u7ec4\u5f52\u4e00\u5316", "description": "N,C,... \u5e03\u5c40\uff0c\u5206\u7ec4\u5fc5\u987b\u6574\u9664\u901a\u9053\u6570\u3002", "defaults": { "num_groups": 4, "num_channels": 16, "eps": 1e-05, "affine": true }, "parameters": [{ "name": "num_groups", "type": "integer", "default": 4, "min": 1, "max": 1000000 }, { "name": "num_channels", "type": "integer", "default": 16, "min": 1, "max": 1000000 }, { "name": "eps", "type": "number", "default": 1e-05, "min": 1e-12, "max": 1 }, { "name": "affine", "type": "boolean", "default": true }], "ports": [{ "id": "input", "name": "input", "direction": "in", "type": "tensor" }, { "id": "output", "name": "output", "direction": "out", "type": "tensor" }] }, { "kind": "Embedding", "category": "embedding", "label": "\u8bcd\u5d4c\u5165", "description": "int64 \u7d22\u5f15\u8f6c float32 \u5411\u91cf\uff1b\u5b9e\u9645\u7d22\u5f15\u8303\u56f4\u9700\u8981\u6570\u636e\u9a8c\u8bc1\u3002", "defaults": { "num_embeddings": 1000, "embedding_dim": 16 }, "parameters": [{ "name": "num_embeddings", "type": "integer", "default": 1000, "min": 1, "max": 1000000 }, { "name": "embedding_dim", "type": "integer", "default": 16, "min": 1, "max": 1000000 }], "ports": [{ "id": "input", "name": "input", "direction": "in", "type": "tensor" }, { "id": "output", "name": "output", "direction": "out", "type": "tensor" }] }, { "kind": "MultiheadAttention", "category": "attention", "label": "\u591a\u5934\u6ce8\u610f\u529b", "description": "\u4e09\u8def float32 Q/K/V\uff1b\u56fa\u5b9a\u8fd4\u56de\u6ce8\u610f\u529b\u7ed3\u679c\u4e0e\u5e73\u5747\u6743\u91cd\uff0c\u65e0\u63a9\u7801\uff0c\u65e0\u7f13\u5b58\u3002", "defaults": { "embed_dim": 16, "num_heads": 4, "dropout": 0.1, "bias": true, "batch_first": true }, "parameters": [{ "name": "embed_dim", "type": "integer", "default": 16, "min": 1, "max": 1000000 }, { "name": "num_heads", "type": "integer", "default": 4, "min": 1, "max": 1000000 }, { "name": "dropout", "type": "number", "default": 0.1, "min": 0, "max": 1 }, { "name": "bias", "type": "boolean", "default": true }, { "name": "batch_first", "type": "boolean", "default": true }], "ports": [{ "id": "query", "name": "query", "direction": "in", "type": "tensor" }, { "id": "key", "name": "key", "direction": "in", "type": "tensor" }, { "id": "value", "name": "value", "direction": "in", "type": "tensor" }, { "id": "output", "name": "output", "direction": "out", "type": "tensor" }, { "id": "weights", "name": "weights", "direction": "out", "type": "tensor" }] }, { "kind": "RNN", "category": "recurrent", "label": "RNN \u5faa\u73af\u5c42", "description": "\u6279\u6b21\u4e09\u7ef4\u5e8f\u5217\uff0c\u9ed8\u8ba4\u96f6\u521d\u6001\uff1b\u8fd4\u56de\u5e8f\u5217\u4e0e\u672b\u6001\uff0c\u4e0d\u652f\u6301 PackedSequence \u6216 LSTM \u6295\u5f71\u3002", "defaults": { "input_size": 16, "hidden_size": 32, "num_layers": 1, "bias": true, "batch_first": true, "dropout": 0.0, "bidirectional": false, "nonlinearity": "tanh" }, "parameters": [{ "name": "input_size", "type": "integer", "default": 16, "min": 1, "max": 1000000 }, { "name": "hidden_size", "type": "integer", "default": 32, "min": 1, "max": 1000000 }, { "name": "num_layers", "type": "integer", "default": 1, "min": 1, "max": 128 }, { "name": "bias", "type": "boolean", "default": true }, { "name": "batch_first", "type": "boolean", "default": true }, { "name": "dropout", "type": "number", "default": 0.0, "min": 0, "max": 1 }, { "name": "bidirectional", "type": "boolean", "default": false }, { "name": "nonlinearity", "type": "choice", "default": "tanh", "options": ["tanh", "relu"] }], "ports": [{ "id": "input", "name": "input", "direction": "in", "type": "tensor" }, { "id": "output", "name": "output", "direction": "out", "type": "tensor" }, { "id": "h_n", "name": "h_n", "direction": "out", "type": "tensor" }] }, { "kind": "GRU", "category": "recurrent", "label": "GRU \u5faa\u73af\u5c42", "description": "\u6279\u6b21\u4e09\u7ef4\u5e8f\u5217\uff0c\u9ed8\u8ba4\u96f6\u521d\u6001\uff1b\u8fd4\u56de\u5e8f\u5217\u4e0e\u672b\u6001\uff0c\u4e0d\u652f\u6301 PackedSequence \u6216 LSTM \u6295\u5f71\u3002", "defaults": { "input_size": 16, "hidden_size": 32, "num_layers": 1, "bias": true, "batch_first": true, "dropout": 0.0, "bidirectional": false }, "parameters": [{ "name": "input_size", "type": "integer", "default": 16, "min": 1, "max": 1000000 }, { "name": "hidden_size", "type": "integer", "default": 32, "min": 1, "max": 1000000 }, { "name": "num_layers", "type": "integer", "default": 1, "min": 1, "max": 128 }, { "name": "bias", "type": "boolean", "default": true }, { "name": "batch_first", "type": "boolean", "default": true }, { "name": "dropout", "type": "number", "default": 0.0, "min": 0, "max": 1 }, { "name": "bidirectional", "type": "boolean", "default": false }], "ports": [{ "id": "input", "name": "input", "direction": "in", "type": "tensor" }, { "id": "output", "name": "output", "direction": "out", "type": "tensor" }, { "id": "h_n", "name": "h_n", "direction": "out", "type": "tensor" }] }, { "kind": "LSTM", "category": "recurrent", "label": "LSTM \u5faa\u73af\u5c42", "description": "\u6279\u6b21\u4e09\u7ef4\u5e8f\u5217\uff0c\u9ed8\u8ba4\u96f6\u521d\u6001\uff1b\u8fd4\u56de\u5e8f\u5217\u4e0e\u672b\u6001\uff0c\u4e0d\u652f\u6301 PackedSequence \u6216 LSTM \u6295\u5f71\u3002", "defaults": { "input_size": 16, "hidden_size": 32, "num_layers": 1, "bias": true, "batch_first": true, "dropout": 0.0, "bidirectional": false }, "parameters": [{ "name": "input_size", "type": "integer", "default": 16, "min": 1, "max": 1000000 }, { "name": "hidden_size", "type": "integer", "default": 32, "min": 1, "max": 1000000 }, { "name": "num_layers", "type": "integer", "default": 1, "min": 1, "max": 128 }, { "name": "bias", "type": "boolean", "default": true }, { "name": "batch_first", "type": "boolean", "default": true }, { "name": "dropout", "type": "number", "default": 0.0, "min": 0, "max": 1 }, { "name": "bidirectional", "type": "boolean", "default": false }], "ports": [{ "id": "input", "name": "input", "direction": "in", "type": "tensor" }, { "id": "output", "name": "output", "direction": "out", "type": "tensor" }, { "id": "h_n", "name": "h_n", "direction": "out", "type": "tensor" }, { "id": "c_n", "name": "c_n", "direction": "out", "type": "tensor" }] }, { "kind": "Add", "category": "merge", "label": "\u5f20\u91cf\u76f8\u52a0", "description": "\u4e24\u8def\u5f62\u72b6\u4e0e\u7c7b\u578b\u5fc5\u987b\u5b8c\u5168\u76f8\u540c\uff1b\u4e0d\u9690\u5f0f\u5e7f\u64ad\uff0c\u6570\u503c\u57df\u672a\u9a8c\u8bc1\u3002", "defaults": {}, "parameters": [], "ports": [{ "id": "left", "name": "left", "direction": "in", "type": "tensor" }, { "id": "right", "name": "right", "direction": "in", "type": "tensor" }, { "id": "output", "name": "output", "direction": "out", "type": "tensor" }] }, { "kind": "Subtract", "category": "merge", "label": "\u5f20\u91cf\u76f8\u51cf", "description": "\u4e24\u8def\u5f62\u72b6\u4e0e\u7c7b\u578b\u5fc5\u987b\u5b8c\u5168\u76f8\u540c\uff1b\u4e0d\u9690\u5f0f\u5e7f\u64ad\uff0c\u6570\u503c\u57df\u672a\u9a8c\u8bc1\u3002", "defaults": {}, "parameters": [], "ports": [{ "id": "left", "name": "left", "direction": "in", "type": "tensor" }, { "id": "right", "name": "right", "direction": "in", "type": "tensor" }, { "id": "output", "name": "output", "direction": "out", "type": "tensor" }] }, { "kind": "Multiply", "category": "merge", "label": "\u5f20\u91cf\u76f8\u4e58", "description": "\u4e24\u8def\u5f62\u72b6\u4e0e\u7c7b\u578b\u5fc5\u987b\u5b8c\u5168\u76f8\u540c\uff1b\u4e0d\u9690\u5f0f\u5e7f\u64ad\uff0c\u6570\u503c\u57df\u672a\u9a8c\u8bc1\u3002", "defaults": {}, "parameters": [], "ports": [{ "id": "left", "name": "left", "direction": "in", "type": "tensor" }, { "id": "right", "name": "right", "direction": "in", "type": "tensor" }, { "id": "output", "name": "output", "direction": "out", "type": "tensor" }] }, { "kind": "Divide", "category": "merge", "label": "\u5f20\u91cf\u76f8\u9664", "description": "\u4e24\u8def\u5f62\u72b6\u4e0e\u7c7b\u578b\u5fc5\u987b\u5b8c\u5168\u76f8\u540c\uff1b\u4e0d\u9690\u5f0f\u5e7f\u64ad\uff0c\u6570\u503c\u57df\u672a\u9a8c\u8bc1\u3002", "defaults": {}, "parameters": [], "ports": [{ "id": "left", "name": "left", "direction": "in", "type": "tensor" }, { "id": "right", "name": "right", "direction": "in", "type": "tensor" }, { "id": "output", "name": "output", "direction": "out", "type": "tensor" }] }, { "kind": "Concat", "category": "merge", "label": "\u5f20\u91cf\u62fc\u63a5", "description": "\u6cbf\u4e00\u4e2a\u8f74\u62fc\u63a5\u4e24\u8def\u76f8\u540c\u7c7b\u578b\u5f20\u91cf\uff0c\u5176\u4ed6\u8f74\u76f8\u540c\u3002", "defaults": { "dim": 1 }, "parameters": [{ "name": "dim", "type": "integer", "default": 1, "min": -8, "max": 7 }], "ports": [{ "id": "a", "name": "a", "direction": "in", "type": "tensor" }, { "id": "b", "name": "b", "direction": "in", "type": "tensor" }, { "id": "output", "name": "output", "direction": "out", "type": "tensor" }] }, { "kind": "MatMul", "category": "operator", "label": "\u77e9\u9635\u4e58\u6cd5", "description": "\u76f8\u540c\u7c7b\u578b\u7684\u4e8c\u7ef4\u6216\u6279\u6b21\u77e9\u9635\uff1b\u6279\u6b21\u8f74\u4e25\u683c\u76f8\u540c\uff0c\u4e0d\u9690\u5f0f\u5e7f\u64ad\u3002", "defaults": {}, "parameters": [], "ports": [{ "id": "left", "name": "left", "direction": "in", "type": "tensor" }, { "id": "right", "name": "right", "direction": "in", "type": "tensor" }, { "id": "output", "name": "output", "direction": "out", "type": "tensor" }] }, { "kind": "Mean", "category": "operator", "label": "\u6309\u8f74\u5e73\u5747", "description": "\u6cbf\u4e00\u4e2a\u6307\u5b9a\u8f74\u6c42\u6d6e\u70b9\u5747\u503c\u3002", "defaults": { "dim": 1, "keepdim": true }, "parameters": [{ "name": "dim", "type": "integer", "default": 1, "min": -8, "max": 7 }, { "name": "keepdim", "type": "boolean", "default": true }], "ports": [{ "id": "input", "name": "input", "direction": "in", "type": "tensor" }, { "id": "output", "name": "output", "direction": "out", "type": "tensor" }] }, { "kind": "Sum", "category": "operator", "label": "\u6309\u8f74\u6c42\u548c", "description": "\u6cbf\u4e00\u4e2a\u6307\u5b9a\u8f74\u6c42\u548c\uff0c\u4fdd\u7559\u58f0\u660e\u7c7b\u578b\u3002", "defaults": { "dim": 1, "keepdim": true }, "parameters": [{ "name": "dim", "type": "integer", "default": 1, "min": -8, "max": 7 }, { "name": "keepdim", "type": "boolean", "default": true }], "ports": [{ "id": "input", "name": "input", "direction": "in", "type": "tensor" }, { "id": "output", "name": "output", "direction": "out", "type": "tensor" }] }, { "kind": "Upsample", "category": "reshape", "label": "\u56fa\u5b9a\u5c3a\u5bf8\u4e0a\u91c7\u6837", "description": "\u6309\u663e\u5f0f\u76ee\u6807\u7a7a\u95f4\u5c3a\u5bf8\u6700\u8fd1\u90bb\u63d2\u503c\uff1b\u652f\u6301 1\u20133 \u7ef4\u7a7a\u95f4\u3002", "defaults": { "size": [64, 64], "mode": "nearest" }, "parameters": [{ "name": "size", "type": "integer-array", "default": [64, 64], "min": 1, "max": 10000, "minLength": 1, "maxLength": 3 }, { "name": "mode", "type": "choice", "default": "nearest", "options": ["nearest", "nearest-exact"] }], "ports": [{ "id": "input", "name": "input", "direction": "in", "type": "tensor" }, { "id": "output", "name": "output", "direction": "out", "type": "tensor" }] }], "unsupported": ["PackedSequence", "AttentionMask", "DynamicControlFlow", "LossAndOptimizer", "CustomPythonExecution"], "limits": { "nodes": 128, "edges": 384 }, "verification": "static-declared-tensors; no model import or execution" });
    const [storageRevision, setStorageRevision] = useState(initial.storageRevision ?? 0);
    const [savedRevision, setSavedRevision] = useState(initial.savedRevision ?? -1);
    const [selection, setSelection] = useState(() => ({ node: initial.selection?.at(-1), nodes: initial.selection ?? [] }));
    const [camera, setCamera] = useState(initial.camera ?? { x: 30, y: 30, zoom: 1 });
    const [preview, setPreview] = useState(null);
    const [connection, setConnection] = useState(null);
    const [tool, setTool] = useState(initial.tool ?? 'select');
    const [marquee, setMarquee] = useState(null);
    const [search, setSearch] = useState('FC');
    const [paletteView, setPaletteView] = useState('modules');
    const [paletteCategory, setPaletteCategory] = useState('');
    const [paletteDrag, setPaletteDrag] = useState(null);
    const [dropActive, setDropActive] = useState(false);
    const [busy, setBusy] = useState(false);
    const [busyOperation, setBusyOperation] = useState(null);
    const [notice, storeNotice] = useState('从左侧拖入输入、模块和输出；点击输出端口，再点击输入端口连接。');
    const [error, setError] = useState('');
    const [checkNoticeKey, setCheckNoticeKey] = useState(null);
    const [feedback, setFeedback] = useState(null);
    const [invalidFields, setInvalidFields] = useState([]);
    const [generated, setGenerated] = useState(null);
    const [customModuleOpen, setCustomModuleOpen] = useState(false);
    const [validation, setValidation] = useState(null);
    const [hoveredPort, setHoveredPort] = useState(null);
    const [focusedPort, setFocusedPort] = useState(null);
    const portHint = hoveredPort ?? focusedPort;
    const hintRef = useRef(null);
    const [measuredHint, setMeasuredHint] = useState(null);
    const svgRef = useRef(null);
    const [viewportSize, setViewportSize] = useState({ width: 254, height: 150 });
    const cameraViewport = useRef(initial.viewport);
    const gesture = useRef(null);
    const currentRef = useRef(history);
    currentRef.current = history;
    const saving = useRef(false);
    const browsing = useRef(false);
    const invalidFieldsRef = useRef([]);
    const draft = preview ?? history.draft;
    const implicitRoots = useMemo(() => implicitDraftRootIds(draft), [draft]);
    const catalog = useMemo(() => sourceDraftCatalog(history.draft, baseCatalog), [history.draft.sourceProvenance, history.draft.customModules, baseCatalog]);
    const paletteCatalog = useMemo(() => baseCatalog ? { ...baseCatalog, modules: [...baseCatalog.modules, ...(history.draft.customModules ?? []).map(customModuleCatalog)] } : null, [baseCatalog, history.draft.customModules]);
    const catalogRef = useRef(catalog);
    catalogRef.current = catalog;
    const selectedIds = selection.nodes ?? (selection.node ? [selection.node] : []);
    const grid = canvasDotGrid(camera);
    const viewStateRef = useRef(onViewState);
    viewStateRef.current = onViewState;
    const selected = draft.nodes.find(node => node.id === selection.node);
    const selectedModule = catalog?.modules.find(module => module.kind === selected?.kind);
    const geometry = useMemo(() => catalog ? draftRoutes(draft, catalog) : { routes: [], overlaps: [], flow: 'horizontal', nodeFlows: {} }, [draft, catalog]);
    const edgeRoles = useMemo(() => catalog ? draftEdgeRoles(draft, catalog) : new Map(), [draft, catalog]);
    const dirty = history.draft.revision !== savedRevision;
    const validationKey = useMemo(() => draftValidationKey(history.draft), [history.draft]);
    const checked = validation?.key === validationKey && !invalidFields.length ? validation.result : null;
    const currentNotice = checkNoticeKey && (checkNoticeKey !== validationKey || !checked) ? '草稿结构已改变；请重新检查声明形状与连接，模型尚未执行。' : notice;
    const labelScale = draftCanvasTextScale(camera.zoom);
    useEffect(() => { viewStateRef.current?.({ draft: history.draft, history, storageRevision, savedRevision, selection: selectedIds, camera, viewport: cameraViewport.current, tool, sourceHistory: initial.sourceHistory, viewBaseline: initial.viewBaseline }); }, [history, storageRevision, savedRevision, selection, camera, tool]);
    useEffect(() => {
        let alive = true;
        api.authoringCatalog().then(async (value) => {
            if (!alive)
                return;
            catalogRef.current = sourceDraftCatalog(currentRef.current.draft, value);
            setBaseCatalog(value);
            try {
                const result = readDraftValidation(await api.validateDraft(initial.draft));
                if (alive && initial.draft === currentRef.current.draft)
                    receiveValidation(initial.draft, result);
            }
            catch (reason) {
                if (alive && initial.draft === currentRef.current.draft)
                    reportError(reason, '先前草稿尚未通过检查，编辑已保留：');
            }
        }).catch(reason => { if (alive)
            setError(String(reason)); });
        return () => { alive = false; };
    }, [initial.draft]);
    useEffect(() => {
        try {
            localStorage.setItem(CACHE, JSON.stringify({ draft: history.draft, history, storageRevision, savedRevision, selection: selectedIds, camera, viewport: cameraViewport.current, tool, viewBaseline: initial.viewBaseline }));
        }
        catch {
            setError('浏览器未能保留草稿；请使用“保存草稿”。');
        }
    }, [history, storageRevision, savedRevision, selectedIds, camera, tool]);
    useLayoutEffect(() => {
        const viewport = svgRef.current;
        if (!viewport)
            return;
        const resize = () => {
            const size = cameraViewportSize({ width: viewport.clientWidth, height: viewport.clientHeight });
            if (!size)
                return;
            const previous = cameraViewport.current;
            cameraViewport.current = size;
            setCamera(camera => authoringCameraAtViewport(camera, previous, size));
            setViewportSize(size);
        };
        resize();
        const observer = new ResizeObserver(resize);
        observer.observe(viewport);
        return () => observer.disconnect();
    }, []);
    function cancel() {
        const active = gesture.current;
        gesture.current = null;
        setPreview(null);
        setConnection(null);
        setHoveredPort(null);
        setFocusedPort(null);
        clearPaletteDrag();
        setMarquee(null);
        if (active?.type === 'pan')
            setCamera(active.camera);
        if (active && svgRef.current?.hasPointerCapture(active.pointer))
            svgRef.current.releasePointerCapture(active.pointer);
    }
    function setNotice(value) { storeNotice(value); setCheckNoticeKey(null); }
    function clearError() { setError(''); setFeedback(null); }
    function startBlankDraft() {
        if (busy)
            return;
        cancel();
        if (onNewBlank) {
            onNewBlank({ draft: currentRef.current.draft, history: currentRef.current, storageRevision, savedRevision,
                selection: selectedIds, camera, viewport: cameraViewport.current, tool,
                sourceHistory: initial.sourceHistory, viewBaseline: initial.viewBaseline });
            return;
        }
        if (dirty && (history.draft.revision > 0 || history.draft.nodes.length > 0)) {
            setNotice('当前草稿有未保存编辑，请先保存或重开后再新建空白模型。');
            return;
        }
        const next = draftHistory(createBlank());
        currentRef.current = next;
        setHistory(next);
        setStorageRevision(0);
        setSavedRevision(-1);
        setSelection({});
        setGenerated(null);
        setCamera({ x: 30, y: 30, zoom: 1 });
        clearError();
    }
    function discardInvalidInput() {
        const message = '未提交的无效输入已放弃；草稿仍保留上次有效参数。';
        setNotice(message);
        setError(previous => previous && !previous.includes(message) ? `${previous} ${message}` : previous);
    }
    function focusDraftNode(id) {
        cancel();
        const node = currentRef.current.draft.nodes.find(item => item.id === id), rect = svgRef.current?.getBoundingClientRect(), currentCatalog = catalogRef.current;
        if (!node || !rect || !currentCatalog)
            return;
        setSelection({ node: id, nodes: [id] });
        setCamera(old => { const zoom = Math.max(.7, Math.min(1, old.zoom)); return { zoom, x: rect.width / 2 - (node.position.x + DRAFT_WIDTH / 2) * zoom, y: rect.height / 2 - (node.position.y + draftNodeSize(node, currentCatalog).height / 2) * zoom }; });
    }
    function reportError(reason, prefix = '') {
        const value = resolveDraftFeedback(reason, currentRef.current.draft, catalogRef.current);
        setError(prefix + value.message);
        setFeedback(value);
        if (value.target)
            focusDraftNode(value.target.nodeId);
    }
    function fieldValidity(nodeId, parameter, invalid) {
        const key = `${nodeId}:${parameter}`, previous = invalidFieldsRef.current;
        if (previous.includes(key) === invalid)
            return;
        const next = invalid ? [...previous, key] : previous.filter(item => item !== key);
        invalidFieldsRef.current = next;
        setInvalidFields(next);
    }
    function apply(update) {
        if (busy)
            return;
        cancel();
        try {
            const next = changeDraft(currentRef.current, update);
            currentRef.current = next;
            setHistory(next);
            setGenerated(null);
            clearError();
            return next.draft;
        }
        catch (reason) {
            reportError(reason);
        }
    }
    function travel(action) { cancel(); const next = travelDraft(currentRef.current, action); currentRef.current = next; setHistory(next); setGenerated(null); clearError(); }
    function point(clientX, clientY) {
        const rect = svgRef.current.getBoundingClientRect();
        return { x: (clientX - rect.left - camera.x) / camera.zoom, y: (clientY - rect.top - camera.y) / camera.zoom };
    }
    function clearPaletteDrag() { setPaletteDrag(null); setDropActive(false); }
    function startPaletteDrag(event, entry) {
        if (busy || !catalog) {
            event.preventDefault();
            return;
        }
        event.dataTransfer.setData(`application/x-archcanvas-${entry.type}`, entry.id);
        event.dataTransfer.effectAllowed = 'copy';
        setPaletteDrag(entry);
        setDropActive(false);
    }
    function acceptsPaletteDrag(event) {
        return !busy && !!catalog && Array.from(event.dataTransfer.types).some(type => type === 'application/x-archcanvas-module' || type === 'application/x-archcanvas-preset');
    }
    function paletteDragOver(event) {
        if (!acceptsPaletteDrag(event))
            return;
        event.preventDefault();
        event.dataTransfer.dropEffect = 'copy';
        setDropActive(true);
    }
    function paletteDragLeave(event) {
        if (!event.currentTarget.contains(event.relatedTarget))
            setDropActive(false);
    }
    function paletteDrop(event) {
        const accepts = acceptsPaletteDrag(event);
        clearPaletteDrag();
        if (!accepts)
            return;
        event.preventDefault();
        const preset = draftPresets.find(item => item.id === event.dataTransfer.getData('application/x-archcanvas-preset'));
        if (preset) {
            const at = point(event.clientX, event.clientY);
            addPreset(preset, { x: at.x - DRAFT_WIDTH / 2, y: at.y - 30 });
            return;
        }
        const module = catalog?.modules.find(item => item.kind === event.dataTransfer.getData('application/x-archcanvas-module'));
        if (module) {
            const at = point(event.clientX, event.clientY);
            add(module, { x: at.x - DRAFT_WIDTH / 2, y: at.y - 30 });
        }
    }
    function add(module, position) {
        if (busy || !catalog)
            return;
        const size = draftModuleSize(module);
        const rect = svgRef.current?.getBoundingClientRect();
        const center = rect ? point(rect.left + rect.width / 2, rect.top + rect.height / 2) : { x: 80, y: 80 };
        const at = position ?? nextDraftPosition(draft, { x: center.x - DRAFT_WIDTH / 2, y: center.y - size.height / 2 }, module, catalog);
        const id = `n_${crypto.randomUUID().replaceAll('-', '')}`;
        const next = apply(value => addDraftNode(value, module, id, { x: Math.round(at.x), y: Math.round(at.y) }));
        if (!next)
            return;
        setSelection({ node: id, nodes: [id] });
        setNotice(`已添加 ${module.label}；在右侧编辑参数。`);
        if (rect && !position && (at.y * camera.zoom + camera.y + size.height * camera.zoom > rect.height - 20))
            setCamera(old => ({ ...old, y: rect.height / 2 - (at.y + size.height / 2) * old.zoom }));
    }
    function insertCustomModule(preview) {
        if (busy || !catalog)
            return;
        const definition = preview.definition, module = preview.module;
        const nextCatalog = { ...catalog, modules: [...catalog.modules.filter(item => item.kind !== module.kind), module] };
        const rect = svgRef.current?.getBoundingClientRect(), size = draftModuleSize(module);
        const center = rect ? point(rect.left + rect.width / 2, rect.top + rect.height / 2) : { x: 180, y: 150 };
        const position = nextDraftPosition(currentRef.current.draft, { x: center.x - size.width / 2, y: center.y - size.height / 2 }, module, nextCatalog);
        const id = `n_${crypto.randomUUID().replaceAll('-', '')}`;
        const next = apply(value => {
            value.customModules ??= [];
            if (!value.customModules.some(item => item.kind === definition.kind))
                value.customModules.push(structuredClone(definition));
            addDraftNode(value, module, id, position);
        });
        if (!next)
            return;
        setSelection({ node: id, nodes: [id] });
        setPaletteView('modules');
        setPaletteCategory('custom');
        setSearch('');
        setCustomModuleOpen(false);
        setNotice(`已添加 ${module.label}；可连接输入与输出，也可从左侧重复插入。输出形状未推测。`);
    }
    function addPreset(preset, position) {
        if (busy || !catalog)
            return;
        const rect = svgRef.current?.getBoundingClientRect(), size = draftPresetSize(preset, catalog);
        const center = rect ? point(rect.left + rect.width / 2, rect.top + rect.height / 2) : { x: 80 + size.width / 2, y: 130 };
        const at = position ?? { x: center.x - size.width / 2, y: center.y - size.height / 2 };
        try {
            const candidate = structuredClone(currentRef.current.draft), existing = candidate.nodes.length;
            const inserted = insertDraftPreset(candidate, catalog, preset.id, at);
            const next = apply(value => { value.nodes = candidate.nodes; value.edges = candidate.edges; });
            if (!next)
                return;
            setSelection({ node: inserted.inputNodeId, nodes: [inserted.inputNodeId] });
            fit(next);
            setNotice(`已${existing ? '添加一个独立网络' : '添加'}：${preset.label}。可在右侧修改输入形状，逐个选择模块编辑；一次撤销即可移除本次添加。`);
        }
        catch (reason) {
            reportError(reason);
        }
    }
    function connect(source, target) {
        if (!catalog)
            return;
        // Validate against a copy first: errors are reported outside React's updater.
        try {
            const value = structuredClone(currentRef.current.draft);
            const id = `e_${crypto.randomUUID().replaceAll('-', '')}`;
            connectDraft(value, catalog, source, target, id);
            apply(next => { next.edges = value.edges; });
            setNotice('已建立张量连接；可选择连线删除。');
        }
        catch (reason) {
            cancel();
            reportError(reason);
        }
    }
    function deleteSelection() {
        if (busy)
            return;
        if (selectedIds.length) {
            if (apply(value => { for (const id of selectedIds)
                removeDraftNode(value, id); }))
                setNotice('已删除模块及相连连线；请重新检查当前结构。');
        }
        else if (selection.edge) {
            if (apply(value => { value.edges = value.edges.filter(edge => edge.id !== selection.edge); }))
                setNotice('已删除连线；请重新检查当前结构。');
        }
        setSelection({});
    }
    function receiveValidation(snapshot, result) {
        const key = draftValidationKey(snapshot);
        if (draftValidationKey(result.draft) !== key)
            throw new Error('检查结果与当前草稿声明不一致，请重新检查。');
        if (key !== draftValidationKey(currentRef.current.draft))
            return false;
        setValidation({ key, result });
        return true;
    }
    async function check() {
        if (busy || !catalog || invalidFieldsRef.current.length)
            return;
        cancel();
        setBusy(true);
        setBusyOperation('check');
        clearError();
        const snapshot = currentRef.current.draft;
        try {
            const result = readDraftValidation(await api.validateDraft(snapshot));
            if (receiveValidation(snapshot, result)) {
                setNotice(result.complete ? result.draft.sourceProvenance ? '连接检查通过；源码来源已保留，形状与模型执行尚未验证。' : '静态检查通过；声明形状与连接相容，模型尚未执行。' : `还有 ${result.issues.length} 项需要完成；可在右侧定位并继续搭建。`);
                setCheckNoticeKey(draftValidationKey(snapshot));
            }
        }
        catch (reason) {
            if (draftValidationKey(snapshot) === draftValidationKey(currentRef.current.draft)) {
                setValidation(null);
                reportError(reason, '检查未通过：');
            }
        }
        finally {
            setBusyOperation(null);
            setBusy(false);
        }
    }
    async function save() {
        if (saving.current || busy || invalidFieldsRef.current.length)
            return;
        cancel();
        saving.current = true;
        setBusy(true);
        setBusyOperation('save');
        const snapshot = currentRef.current.draft;
        try {
            const result = await api.saveDraft(snapshot, storageRevision);
            if (snapshot === currentRef.current.draft) {
                setStorageRevision(result.revision);
                setSavedRevision(snapshot.revision);
                setNotice('模型草稿已保存；可重开继续搭建。');
                clearError();
            }
        }
        catch (reason) {
            if (snapshot === currentRef.current.draft)
                reportError(reason, '保存失败，草稿已保留：');
        }
        finally {
            saving.current = false;
            setBusyOperation(null);
            setBusy(false);
        }
    }
    async function reopen() {
        if (busy)
            return;
        const snapshot = currentRef.current.draft;
        cancel();
        setBusy(true);
        setBusyOperation('reopen');
        try {
            const result = await api.draft(history.draft.id);
            if (snapshot === currentRef.current.draft) {
                const restored = reopenAuthoringWorkspace({ draft: snapshot, history: currentRef.current, storageRevision, savedRevision, selection: selectedIds, camera, tool }, result.draft, result.revision);
                const next = restored.history;
                currentRef.current = next;
                setHistory(next);
                setStorageRevision(result.revision);
                setSavedRevision(restored.savedRevision);
                setSelection({ node: restored.selection?.at(-1), nodes: restored.selection });
                setGenerated(null);
                clearError();
                setNotice('已重开保存的模型草稿，视角与已有撤销记录保留；可撤销本次重开。');
            }
        }
        catch (reason) {
            if (snapshot === currentRef.current.draft)
                reportError(reason);
        }
        finally {
            setBusyOperation(null);
            setBusy(false);
        }
    }
    async function generate() {
        if (busy || invalidFieldsRef.current.length)
            return;
        cancel();
        setBusy(true);
        setBusyOperation('generate');
        clearError();
        const snapshot = currentRef.current.draft;
        try {
            const materialized = snapshot.sourceProvenance ? await reprojectSourceDraft(snapshot) : snapshot;
            const result = await api.generateDraft(materialized);
            if (snapshot === currentRef.current.draft)
                setGenerated({ ...result, presentationDraft: snapshot });
        }
        catch (reason) {
            if (snapshot === currentRef.current.draft)
                reportError(reason);
        }
        finally {
            setBusyOperation(null);
            setBusy(false);
        }
    }
    async function browse() {
        if (busy || browsing.current || invalidFieldsRef.current.length)
            return;
        cancel();
        clearError();
        const snapshot = currentRef.current.draft;
        const workspace = { draft: snapshot, history: currentRef.current, storageRevision, savedRevision,
            selection: selectedIds, camera, viewport: cameraViewport.current, tool, sourceHistory: initial.sourceHistory, viewBaseline: initial.viewBaseline };
        if (browseBaseline && onReuseView && sameGeneratedDraft(snapshot, browseBaseline)) {
            try {
                onReuseView(workspace);
            }
            catch (reason) {
                reportError(reason);
            }
            return;
        }
        browsing.current = true;
        setBusy(true);
        setBusyOperation('generate');
        try {
            const materialized = snapshot.sourceProvenance ? await reprojectSourceDraft(snapshot) : snapshot;
            const result = await api.generateDraft(materialized);
            if (snapshot !== currentRef.current.draft)
                return;
            viewStateRef.current?.(workspace);
            setBusyOperation('open');
            await onOpen({ ...result, presentationDraft: snapshot });
        }
        catch (reason) {
            if (snapshot === currentRef.current.draft)
                reportError(reason, '无法切换到视图，编辑已保留：');
        }
        finally {
            browsing.current = false;
            setBusyOperation(null);
            setBusy(false);
        }
    }
    async function toggleSourceHierarchy(nodeId) {
        const snapshot = currentRef.current.draft;
        if (!snapshot.sourceProvenance || busy)
            return;
        const node = snapshot.nodes.find(item => item.id === nodeId);
        if (!node)
            return;
        cancel();
        setBusy(true);
        setBusyOperation('frontier');
        clearError();
        try {
            const result = await reprojectSourceDraft(snapshot, nodeId, !node.presentation?.group);
            if (snapshot !== currentRef.current.draft)
                return;
            const next = changeDraft(currentRef.current, draft => { Object.assign(draft, result); });
            currentRef.current = next;
            setHistory(next);
            setGenerated(null);
            setSelection({ node: nodeId, nodes: [nodeId] });
            setNotice(node.presentation?.group ? '已折叠源码区域；内部编辑仍保留，展开后继续。' : '已展开源码区域；已有参数、连接与新增部件保留。');
        }
        catch (reason) {
            if (snapshot === currentRef.current.draft)
                reportError(reason);
        }
        finally {
            setBusy(false);
            setBusyOperation(null);
        }
    }
    function fit(documentToFit = currentRef.current.draft) {
        cancel();
        const rect = svgRef.current?.getBoundingClientRect();
        if (!rect)
            return;
        const currentCatalog = catalogRef.current;
        const routePoints = currentCatalog ? draftRoutes(documentToFit, currentCatalog).routes.flatMap(route => route.points) : [];
        const implicit = implicitDraftRootIds(documentToFit);
        if (currentCatalog)
            setCamera(fitDraftCamera({ ...documentToFit, nodes: documentToFit.nodes.filter(node => !implicit.has(node.id)) }, rect, currentCatalog, routePoints));
    }
    function arrange() { if (!catalogRef.current)
        return; const rect = svgRef.current?.getBoundingClientRect(); const next = apply(value => arrangeDraft(value, catalogRef.current, rect)); if (next) {
        fit(next);
        setNotice('已按连接排版并适合画布；Ctrl+Z 可撤销排版。');
    } }
    function zoom(factor) {
        cancel();
        const rect = svgRef.current?.getBoundingClientRect();
        if (!rect)
            return;
        setCamera(old => { const next = clampCanvasZoom(old.zoom * factor); return { zoom: next, x: rect.width / 2 - (rect.width / 2 - old.x) * next / old.zoom, y: rect.height / 2 - (rect.height / 2 - old.y) * next / old.zoom }; });
    }
    useEffect(() => {
        const key = (event) => {
            if (event.target?.closest('input,textarea,select') || busy || generated)
                return;
            if (event.key === 'Escape') {
                const pending = !!connection || gesture.current?.type === 'port';
                cancel();
                setSelection({});
                if (pending) {
                    clearError();
                    setNotice('已取消连线；选择输出端口即可重新连接。');
                }
            }
            if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'z') {
                event.preventDefault();
                travel(event.shiftKey ? 'redo' : 'undo');
            }
            if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 's') {
                event.preventDefault();
                void save();
            }
            if (event.key === 'Delete' || event.key === 'Backspace') {
                event.preventDefault();
                deleteSelection();
            }
            const move = { ArrowLeft: [-16, 0], ArrowRight: [16, 0], ArrowUp: [0, -16], ArrowDown: [0, 16] }[event.key];
            if (move && selectedIds.length) {
                event.preventDefault();
                apply(value => moveDraftNodes(value, selectedIds, move[0], move[1]));
            }
            if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'a') {
                event.preventDefault();
                const ids = draft.nodes.filter(node => !node.presentation?.group).map(node => node.id);
                setSelection({ node: ids.at(-1), nodes: ids });
            }
        };
        const blur = () => cancel();
        window.addEventListener('keydown', key);
        window.addEventListener('blur', blur);
        return () => { window.removeEventListener('keydown', key); window.removeEventListener('blur', blur); };
    });
    function pointerDown(event) {
        if (busy || gesture.current || ![0, 1].includes(event.button))
            return;
        const target = event.target, port = target.closest('[data-draft-port]'), node = target.closest('[data-draft-node]'), edge = target.closest('[data-draft-edge]');
        const base = currentRef.current.draft;
        if (tool === 'pan' || event.button === 1 || event.altKey) {
            setConnection(null);
            gesture.current = { type: 'pan', pointer: event.pointerId, clientX: event.clientX, clientY: event.clientY, camera, base, pan: beginCameraPan(camera, panInput(event)) };
        }
        else if (port) {
            const endpoint = { nodeId: port.getAttribute('data-node'), portId: port.getAttribute('data-draft-port') };
            const module = catalog?.modules.find(item => item.kind === base.nodes.find(item => item.id === endpoint.nodeId)?.kind);
            if (module?.ports.find(item => item.id === endpoint.portId)?.direction === 'in') {
                if (connection)
                    connect(connection.endpoint, endpoint);
                else
                    setNotice('先点击一个输出端口，再选择此输入端口。');
                return;
            }
            const p = point(event.clientX, event.clientY);
            clearError();
            setConnection({ endpoint, ...p });
            gesture.current = { type: 'port', pointer: event.pointerId, clientX: event.clientX, clientY: event.clientY, camera, base, endpoint };
        }
        else if (node) {
            setConnection(null);
            const nodeId = node.getAttribute('data-draft-node');
            const ids = selectDraftNode(selectedIds, nodeId, event.shiftKey || event.ctrlKey || event.metaKey);
            setSelection({ node: ids.at(-1), nodes: ids });
            gesture.current = { type: 'node', pointer: event.pointerId, clientX: event.clientX, clientY: event.clientY, camera, base, nodeId, nodeIds: ids };
        }
        else if (edge) {
            setSelection({ edge: edge.getAttribute('data-draft-edge') });
            setConnection(null);
            return;
        }
        else {
            setConnection(null);
            const additive = event.shiftKey || event.ctrlKey || event.metaKey;
            if (!additive)
                setSelection({});
            const start = point(event.clientX, event.clientY);
            setMarquee({ ...start, width: 0, height: 0 });
            gesture.current = { type: 'marquee', pointer: event.pointerId, clientX: event.clientX, clientY: event.clientY, camera, base, selection: selectedIds, additive };
        }
        event.preventDefault();
        event.currentTarget.setPointerCapture(event.pointerId);
    }
    function pointerMove(event) {
        const active = gesture.current;
        if (!active) {
            if (connection)
                setConnection(previous => previous && ({ ...previous, ...point(event.clientX, event.clientY) }));
            return;
        }
        if (active.pointer !== event.pointerId)
            return;
        const dx = event.clientX - active.clientX, dy = event.clientY - active.clientY;
        if (active.type === 'pan') {
            const next = cameraAtPanInput(active.pan, panInput(event));
            if (next)
                setCamera(next);
        }
        if (active.type === 'node') {
            const next = structuredClone(active.base);
            moveDraftNodes(next, active.nodeIds ?? [active.nodeId], Math.round(dx / active.camera.zoom), Math.round(dy / active.camera.zoom));
            setPreview(next);
        }
        if (active.type === 'marquee') {
            const start = point(active.clientX, active.clientY), end = point(event.clientX, event.clientY);
            const box = { x: Math.min(start.x, end.x), y: Math.min(start.y, end.y), width: Math.abs(end.x - start.x), height: Math.abs(end.y - start.y) };
            setMarquee(box);
            const ids = active.base.nodes.filter(node => { const size = catalog ? draftNodeSize(node, catalog) : { width: 176, height: 100 }; return !node.presentation?.group && node.position.x < box.x + box.width && node.position.x + size.width > box.x && node.position.y < box.y + box.height && node.position.y + size.height > box.y; }).map(node => node.id);
            const merged = [...new Set([...(active.additive ? active.selection ?? [] : []), ...ids])];
            setSelection({ node: merged.at(-1), nodes: merged });
        }
        if (active.type === 'port')
            setConnection(previous => previous && ({ ...previous, ...point(event.clientX, event.clientY) }));
    }
    function pointerUp(event) {
        const active = gesture.current;
        if (!active || active.pointer !== event.pointerId)
            return;
        gesture.current = null;
        if (event.currentTarget.hasPointerCapture(event.pointerId))
            event.currentTarget.releasePointerCapture(event.pointerId);
        if (active.type === 'node') {
            const dx = Math.round((event.clientX - active.clientX) / active.camera.zoom), dy = Math.round((event.clientY - active.clientY) / active.camera.zoom);
            apply(value => moveDraftNodes(value, active.nodeIds ?? [active.nodeId], dx, dy));
        }
        else if (active.type === 'marquee') {
            setMarquee(null);
        }
        else if (active.type === 'pan') {
            const next = cameraAtPanInput(active.pan, panInput(event));
            if (next)
                setCamera(next);
        }
        else if (active.type === 'port') {
            const port = document.elementFromPoint(event.clientX, event.clientY)?.closest('[data-draft-port]');
            if (port && port.getAttribute('data-node') !== active.endpoint.nodeId)
                connect(active.endpoint, { nodeId: port.getAttribute('data-node'), portId: port.getAttribute('data-draft-port') });
            else
                setNotice('连接起点已选中；点击目标输入端口，Escape 取消。');
        }
    }
    function panInput(event) {
        const rect = event.currentTarget.getBoundingClientRect();
        return { pointerId: event.pointerId, clientX: event.clientX, clientY: event.clientY, viewportX: rect.left, viewportY: rect.top };
    }
    const query = search.trim().toLowerCase();
    const paletteCategories = draftPaletteCategories(paletteCatalog);
    const activePaletteCategory = paletteCategories.some(category => category.id === paletteCategory) ? paletteCategory : '';
    const matches = query || paletteView === 'modules' ? filterDraftModules(paletteCatalog, query, activePaletteCategory) : [];
    const presetMatches = draftPresets.filter(preset => (!!query || paletteView === 'presets') && draftPresetMatches(preset, catalog, query));
    const groups = [...new Set(matches.map(module => module.category))];
    const connectionNode = draft.nodes.find(node => node.id === connection?.endpoint.nodeId), connectionModule = catalog?.modules.find(module => module.kind === connectionNode?.kind);
    const start = connection && connectionNode && connectionModule ? portPoint(connectionNode, connectionModule, connection.endpoint.portId, geometry.nodeFlows[connectionNode.id] ?? 'horizontal') : null;
    const blocked = geometry.routes.filter(route => route.blockedBy.length);
    const hintNode = draft.nodes.find(node => node.id === portHint?.nodeId);
    const hintModule = catalog?.modules.find(module => module.kind === hintNode?.kind);
    const hintPort = hintModule?.ports.find(port => port.id === portHint?.portId);
    const hintBinding = hintPort?.direction === 'in' ? draft.edges.find(edge => edge.target.nodeId === hintNode?.id && edge.target.portId === hintPort.id) : undefined;
    const hintProducer = draft.nodes.find(node => node.id === hintBinding?.source.nodeId);
    const hintTensorNode = hintPort?.direction === 'in' ? hintBinding?.source.nodeId ?? '' : hintNode?.id ?? '';
    const hintTensorPort = hintPort?.direction === 'in' ? hintBinding?.source.portId ?? '' : hintPort?.id ?? '';
    const hintTensor = checked?.portTensors?.[hintTensorNode]?.[hintTensorPort] ?? checked?.tensors[hintTensorNode];
    const hintAnchor = hintNode && hintModule && hintPort ? portPoint(hintNode, hintModule, hintPort.id, geometry.nodeFlows[hintNode.id] ?? 'horizontal') : null;
    const hintFlow = hintNode ? geometry.nodeFlows[hintNode.id] ?? 'horizontal' : 'horizontal';
    const hintScreenX = hintAnchor ? camera.x + hintAnchor.x * camera.zoom : 0;
    const hintScreenY = hintAnchor ? camera.y + hintAnchor.y * camera.zoom : 0;
    const hintNodeRect = hintNode && catalog ? { x: camera.x + hintNode.position.x * camera.zoom, y: camera.y + hintNode.position.y * camera.zoom, width: DRAFT_WIDTH * camera.zoom, height: draftNodeSize(hintNode, catalog).height * camera.zoom } : null;
    const hintNodeObstacles = catalog ? draft.nodes.map(node => ({ x: camera.x + node.position.x * camera.zoom, y: camera.y + node.position.y * camera.zoom, width: DRAFT_WIDTH * camera.zoom, height: draftNodeSize(node, catalog).height * camera.zoom })) : [];
    const hintPlacement = hintAnchor && hintNodeRect ? placeDraftTooltip({ port: { x: hintScreenX, y: hintScreenY }, node: hintNodeRect, direction: hintPort?.direction ?? 'out', flow: hintFlow }, { width: 230, height: 114 }, { width: viewportSize.width, height: viewportSize.height }, hintNodeObstacles) : undefined;
    const hintPosition = hintPlacement ? { left: hintPlacement.left, top: hintPlacement.top } : undefined;
    const hintLayoutKey = JSON.stringify([tool, portHint, hintNode?.label, hintProducer?.label, hintTensor, hintScreenX, hintScreenY, hintNodeRect, hintPosition, hintNodeObstacles, viewportSize.width, viewportSize.height]);
    useLayoutEffect(() => {
        const tooltip = hintRef.current, viewport = svgRef.current;
        if (!tooltip || !viewport || !hintNodeRect || !hintPort)
            return;
        const bounds = tooltip.getBoundingClientRect();
        const position = placeDraftTooltip({ port: { x: hintScreenX, y: hintScreenY }, node: hintNodeRect, direction: hintPort.direction, flow: hintFlow }, { width: bounds.width, height: bounds.height }, { width: viewport.clientWidth, height: viewport.clientHeight }, hintNodeObstacles);
        setMeasuredHint(previous => previous?.key === hintLayoutKey && previous.left === position.left && previous.top === position.top ? previous : { key: hintLayoutKey, left: position.left, top: position.top });
    }, [hintLayoutKey]);
    return _jsxs("div", { className: "authoring-studio", children: [_jsxs("header", { className: "authoring-header", children: [_jsxs("div", { className: "authoring-brand", children: [_jsx("b", { children: "ArchCanvas" }), _jsx("span", { children: "MODEL ARCHITECTURE STUDIO" })] }), _jsx(DraftTextInput, { ariaLabel: "\u6A21\u578B\u8349\u7A3F\u540D\u79F0", value: history.draft.title, disabled: busy, onCommit: title => apply(value => { value.title = title; }) }), _jsxs("div", { className: "header-actions", children: [_jsxs("details", { className: "workspace-menu", children: [_jsxs("summary", { children: ["\u6A21\u578B ", _jsx("span", { children: "\u2304" })] }), _jsxs("div", { children: [_jsx("button", { disabled: busy, onClick: startBlankDraft, children: "\u65B0\u5EFA\u7A7A\u767D\u6A21\u578B" }), _jsx("button", { disabled: busy || !storageRevision, onClick: () => void reopen(), children: "\u91CD\u5F00\u5DF2\u4FDD\u5B58\u8349\u7A3F" }), _jsxs("button", { disabled: busy || !draft.nodes.length || !!invalidFields.length, onClick: () => void generate(), children: [_jsx(Icon, { name: "code", size: 15 }), "\u9884\u89C8\u751F\u6210\u6E90\u7801"] }), _jsx("button", { disabled: busy, onClick: onClose, children: "\u67E5\u770B\u539F\u59CB\u89C6\u56FE" })] })] }), _jsx(WorkspaceModeSwitch, { mode: "edit", disabled: busy || !catalog || !!invalidFields.length, onView: () => void browse(), onEdit: () => { } }), _jsx("span", { className: "authoring-save-state", children: dirty ? '有未保存编辑' : '草稿已保存' }), _jsxs("button", { disabled: busy || !catalog || !!invalidFields.length, onClick: () => void save(), children: [_jsx(Icon, { name: "save", size: 15 }), "\u4FDD\u5B58"] })] })] }), _jsxs("div", { className: "authoring-body", children: [_jsxs("aside", { className: "module-palette", children: [_jsxs("div", { className: "palette-intro", children: [_jsx("span", { className: "eyebrow", children: "MODULE LIBRARY" }), _jsxs("h2", { children: ["\u5E38\u7528\u6A21\u5757 ", _jsx("small", { children: baseCatalog?.modules.length ?? 0 })] }), _jsxs("p", { children: ["\u62D6\u5165\u753B\u5E03\uFF0C\u6216\u70B9\u51FB\u6DFB\u52A0\u3002", _jsx("br", {}), "\u8F93\u5165 \u2192 \u8BA1\u7B97\u6A21\u5757 \u2192 \u8F93\u51FA"] }), _jsxs("div", { className: "palette-browse", role: "group", "aria-label": "\u6A21\u5757\u5E93\u6D4F\u89C8\u65B9\u5F0F", children: [_jsxs("button", { "aria-pressed": paletteView === 'modules', onClick: () => { setPaletteView('modules'); setPaletteCategory(''); }, children: ["\u57FA\u7840\u6A21\u5757 ", _jsx("span", { children: baseCatalog?.modules.length ?? 0 })] }), _jsxs("button", { "aria-pressed": paletteView === 'presets', onClick: () => { setPaletteView('presets'); setPaletteCategory(''); }, children: ["\u7F51\u7EDC\u8D77\u70B9 ", _jsx("span", { children: draftPresets.length })] })] }), _jsx("input", { "aria-label": "\u641C\u7D22\u6A21\u5757", placeholder: "\u540D\u79F0\u3001\u522B\u540D\u6216\u53C2\u6570\uFF0C\u5982 FC / padding", value: search, onChange: event => setSearch(event.target.value) }), paletteView === 'modules' && _jsxs("label", { className: "palette-category", children: ["\u6A21\u5757\u5206\u7C7B", _jsxs("select", { "aria-label": "\u7B5B\u9009\u6A21\u5757\u5206\u7C7B", disabled: !catalog, value: activePaletteCategory, onChange: event => setPaletteCategory(event.target.value), children: [_jsxs("option", { value: "", children: ["\u5168\u90E8\u5206\u7C7B \u00B7 ", baseCatalog?.modules.length ?? 0] }), paletteCategories.map(category => _jsxs("option", { value: category.id, children: [category.label, " \u00B7 ", category.count] }, category.id))] })] }), _jsx("small", { className: "palette-search-help", children: "\u53EF\u6309\u7C7B\u522B\u3001\u82F1\u6587\u522B\u540D\u6216\u53C2\u6570\u641C\u7D22\uFF1B\u7F51\u7EDC\u8D77\u70B9\u4E5F\u6309\u7EC4\u6210\u6A21\u5757\u5339\u914D\u3002" }), _jsxs("button", { className: "custom-module-launch", disabled: busy || !catalog, onClick: () => setCustomModuleOpen(true), children: [_jsx(Icon, { name: "code", size: 14 }), "\u6E90\u7801\u81EA\u5B9A\u4E49\u6A21\u5757"] })] }), _jsxs("div", { className: "palette-list", children: [(!!query || !!activePaletteCategory) && _jsxs("div", { className: "palette-search-summary", children: [_jsxs("p", { role: "status", children: [query ? '搜索结果' : '分类结果', "\uFF1A\u57FA\u7840\u6A21\u5757 ", matches.length, activePaletteCategory && `（${draftPaletteCategoryLabel(activePaletteCategory)}）`, query && ` · 网络起点 ${presetMatches.length}`, "\u3002"] }), _jsx("button", { onClick: () => { setSearch(''); setPaletteCategory(''); }, children: "\u91CD\u7F6E\u7B5B\u9009" })] }), !catalog ? _jsx("p", { role: "status", className: "palette-empty", children: "\u6B63\u5728\u52A0\u8F7D\u6A21\u5757\u5E93\u2026" }) : !matches.length && !presetMatches.length && _jsxs("div", { role: "status", className: "palette-empty", children: [_jsx("b", { children: "\u6CA1\u6709\u627E\u5230\u5339\u914D\u7684\u6A21\u5757\u6216\u7F51\u7EDC" }), _jsx("p", { children: unsupportedPaletteMessage(query) ?? '尝试中文名称、英文别名或参数，如“卷积”、FC、padding 或 MLP；也可重置筛选。' })] }), !!presetMatches.length && _jsxs("section", { className: "preset-section", "aria-label": "\u7F51\u7EDC\u8D77\u70B9", children: [_jsxs("h3", { children: ["\u7F51\u7EDC\u8D77\u70B9 ", _jsx("span", { children: presetMatches.length })] }), _jsxs("p", { className: "preset-intro", children: [draft.nodes.length ? '添加一个独立网络。' : '从完整网络开始搭建。', "\u6240\u6709\u57FA\u7840\u6A21\u5757\u4E0E\u8FDE\u7EBF\u90FD\u53EF\u4FEE\u6539\u3002"] }), presetMatches.map(preset => { const unavailable = draftPresetUnavailable(preset, catalog); return _jsxs("button", { "aria-label": `添加 ${preset.label}`, className: `preset-card ${paletteDrag?.type === 'preset' && paletteDrag.id === preset.id ? 'dragging' : ''}`, disabled: busy || !!unavailable, draggable: !busy && !unavailable, onDragStart: event => startPaletteDrag(event, { type: 'preset', id: preset.id, label: preset.label }), onDragEnd: clearPaletteDrag, onClick: () => addPreset(preset), title: unavailable ?? `${preset.description}；输入 ${preset.input}，输出 ${preset.output}`, children: [_jsxs("span", { className: "preset-heading", children: [_jsx("b", { children: preset.label }), _jsx(Icon, { name: "plus", size: 13 })] }), _jsxs("span", { className: "preset-description", children: [preset.description, " \u00B7 ", preset.nodes.length, " \u6A21\u5757"] }), _jsxs("small", { children: ["\u8F93\u5165 ", preset.input, _jsx("br", {}), "\u8F93\u51FA ", preset.output] }), _jsxs("small", { className: "preset-components", children: ["\u6A21\u5757\u7C7B\u578B\uFF1A", [...new Set(preset.nodes.map(node => node.kind))].join(' · ')] }), unavailable && _jsx("span", { className: "preset-unavailable", children: unavailable })] }, preset.id); }), _jsx("p", { className: "preset-note", children: "\u5F62\u72B6\u662F\u53EF\u7F16\u8F91\u7684\u58F0\u660E\uFF1B\u751F\u6210\u524D\u4F1A\u9759\u6001\u68C0\u67E5\uFF0C\u6A21\u578B\u5C1A\u672A\u6267\u884C\u3002" })] }), !!query && !!matches.length && _jsxs("h3", { className: "palette-results-heading", children: ["\u57FA\u7840\u6A21\u5757 \u00B7 ", matches.length] }), groups.map(group => _jsxs("section", { children: [_jsx("h3", { children: draftPaletteCategoryLabel(group) }), matches.filter(module => module.category === group).map(module => _jsxs("button", { "aria-label": `添加 ${module.kind}`, className: `module-card ${paletteDrag?.type === 'module' && paletteDrag.id === module.kind ? 'dragging' : ''}`, disabled: busy, draggable: !busy, onDragStart: event => startPaletteDrag(event, { type: 'module', id: module.kind, label: `${module.kind} · ${module.label}` }), onDragEnd: clearPaletteDrag, onClick: () => add(module), title: module.description, children: [_jsx("span", { className: `module-dot kind-${module.category}` }), _jsxs("span", { children: [_jsx("b", { children: module.kind }), _jsx("small", { children: module.label })] }), _jsx(Icon, { name: "plus", size: 13 })] }, module.kind))] }, group))] }, query ? 'search' : paletteView), _jsx("div", { className: "palette-note", children: "\u5E38\u7528\u6A21\u578B\u7684\u65E0\u73AF\u8349\u7A3F\u3002\u53C2\u6570\u548C\u8FDE\u7EBF\u901A\u8FC7\u9759\u6001\u68C0\u67E5\u540E\uFF0C\u751F\u6210\u65B0\u6A21\u578B\u3002" })] }), _jsxs("main", { className: "authoring-main", children: [_jsxs("div", { className: "workspace-caption", children: [_jsx("b", { children: history.draft.title }), _jsx("span", { children: "MODEL ARCHITECTURE \u00B7 \u6A21\u578B\u7F16\u8F91" }), !!implicitRoots.size && _jsx("button", { disabled: busy, onClick: () => { const id = [...implicitRoots][0]; setSelection({ node: id, nodes: [id] }); }, children: "\u6A21\u578B\u5C42\u7EA7" })] }), draft.sourceProvenance && _jsxs("div", { className: "draft-help", role: "status", children: ["\u642D\u5EFA\u64A4\u9500 ", history.past.length, " \u00B7 \u91CD\u505A ", history.future.length, "\uFF1B\u5236\u56FE\u5386\u53F2 ", initial.sourceHistory?.past ?? 0, " / ", initial.sourceHistory?.future ?? 0, " \u5728\u201C\u89C6\u56FE\u201D\u4E2D\u7EE7\u7EED\u3002\u4E24\u5904\u5386\u53F2\u5206\u522B\u4FDD\u7559\uFF0C\u64A4\u9500\u4E0D\u4F1A\u6539\u5199\u539F\u59CB\u6E90\u7801\u3002"] }), _jsxs("div", { className: "authoring-toolbar", children: [_jsxs("button", { "aria-pressed": tool === 'select', onClick: () => { cancel(); setTool('select'); }, children: [_jsx(Icon, { name: "arrow", size: 16 }), "\u9009\u62E9"] }), _jsxs("button", { "aria-pressed": tool === 'pan', onClick: () => { cancel(); setTool('pan'); }, children: [_jsx(Icon, { name: "hand", size: 16 }), "\u5E73\u79FB"] }), _jsx("button", { "aria-label": "\u64A4\u9500\u8349\u7A3F", disabled: busy || !history.past.length, onClick: () => travel('undo'), children: _jsx(Icon, { name: "undo", size: 16 }) }), _jsx("button", { "aria-label": "\u91CD\u505A\u8349\u7A3F", disabled: busy || !history.future.length, onClick: () => travel('redo'), children: _jsx(Icon, { name: "redo", size: 16 }) }), _jsx("button", { disabled: busy || !draft.nodes.length, onClick: arrange, children: "\u6309\u8FDE\u63A5\u6392\u7248" }), _jsx("button", { disabled: busy || !catalog || !!invalidFields.length, onClick: () => void check(), children: "\u68C0\u67E5\u6A21\u578B" }), _jsxs("button", { onClick: () => fit(), children: [_jsx(Icon, { name: "fit", size: 16 }), "\u9002\u5408\u753B\u5E03"] }), _jsxs("div", { className: "authoring-zoom", children: [_jsx("button", { "aria-label": "\u8349\u7A3F\u7F29\u5C0F", onClick: () => zoom(1 / 1.2), children: "\u2212" }), _jsxs("button", { "aria-label": "\u8349\u7A3F\u7F29\u653E\u767E\u5206\u6BD4", onClick: () => zoom(1 / camera.zoom), children: [Math.round(camera.zoom * 100), "%"] }), _jsx("button", { "aria-label": "\u8349\u7A3F\u653E\u5927", onClick: () => zoom(1.2), children: "+" })] })] }), (geometry.overlaps.length > 0 || blocked.length > 0) && _jsxs("div", { className: "draft-layout-warning", role: "status", children: [geometry.overlaps.length ? `${geometry.overlaps.length} 组模块重叠。` : '', blocked.length ? `${blocked.length} 条连线无法避开模块。` : '', "\u53EF\u79FB\u52A8\u6A21\u5757\u6216\u4F7F\u7528\u201C\u6309\u8FDE\u63A5\u6392\u7248\u201D\u3002"] }), _jsxs("div", { className: `draft-viewport ${dropActive ? 'palette-drop-active' : ''}`, "data-palette-drop-active": dropActive, onDragEnter: paletteDragOver, onDragOver: paletteDragOver, onDragLeave: paletteDragLeave, onDrop: paletteDrop, children: [dropActive && _jsxs("div", { className: "draft-drop-hint", role: "status", children: [_jsxs("b", { children: ["\u677E\u5F00\u6DFB\u52A0 ", paletteDrag?.label ?? '模块或网络起点'] }), _jsx("span", { children: "\u6DFB\u52A0\u540E\u53EF\u7F16\u8F91\u53C2\u6570\u548C\u8FDE\u7EBF \u00B7 Ctrl+Z \u64A4\u9500" })] }), _jsxs("svg", { ref: svgRef, "aria-label": "\u6A21\u578B\u642D\u5EFA\u753B\u5E03", "data-draft-camera": JSON.stringify(camera), "data-draft-selected": selectedIds.join(","), "data-draft-flow": geometry.flow, "data-draft-text-scale": labelScale.toFixed(2), className: tool === 'pan' ? 'draft-pan' : '', onWheel: event => { event.preventDefault(); cancel(); const rect = event.currentTarget.getBoundingClientRect(), x = event.clientX - rect.left, y = event.clientY - rect.top; setCamera(old => { const zoom = clampCanvasZoom(old.zoom * Math.exp(-event.deltaY * .001)); return { zoom, x: x - (x - old.x) * zoom / old.zoom, y: y - (y - old.y) * zoom / old.zoom }; }); }, onPointerDown: pointerDown, onPointerMove: pointerMove, onPointerUp: pointerUp, onPointerCancel: cancel, onLostPointerCapture: () => { if (gesture.current)
                                            cancel(); }, children: [_jsxs("defs", { children: [_jsx("pattern", { id: "draft-grid", width: grid.spacing, height: grid.spacing, patternUnits: "userSpaceOnUse", x: grid.x, y: grid.y, children: _jsx("circle", { cx: "1", cy: "1", r: ".8", fill: "#cedbd2" }) }), _jsx("marker", { id: "draft-arrow", viewBox: "0 0 10 10", refX: "9", refY: "5", markerWidth: "6", markerHeight: "6", orient: "auto-start-reverse", children: _jsx("path", { d: "M 0 0 L 10 5 L 0 10 z", fill: "#628572" }) }), _jsx("marker", { id: "draft-skip-arrow", viewBox: "0 0 10 10", refX: "9", refY: "5", markerWidth: "6", markerHeight: "6", orient: "auto-start-reverse", children: _jsx("path", { d: "M 0 0 L 10 5 L 0 10 z", fill: "#a76d35" }) }), _jsx("marker", { id: "draft-selected-arrow", viewBox: "0 0 10 10", refX: "9", refY: "5", markerWidth: "6", markerHeight: "6", orient: "auto-start-reverse", children: _jsx("path", { d: "M 0 0 L 10 5 L 0 10 z", fill: "#c18543" }) })] }), _jsx("rect", { width: "100%", height: "100%", fill: "url(#draft-grid)" }), _jsxs("g", { transform: `translate(${camera.x} ${camera.y}) scale(${camera.zoom})`, children: [geometry.routes.map(route => _jsxs("g", { "data-draft-edge": route.id, "data-draft-role": edgeRoles.get(route.id) ?? 'data', className: `draft-edge ${edgeRoles.get(route.id) === 'residual' ? 'residual' : ''} ${selection.edge === route.id ? 'selected' : ''}`, children: [_jsx("title", { children: edgeRoles.get(route.id) === 'residual' ? '跳连：跳过中间模块后相加' : '数据流' }), _jsx("path", { d: route.path, fill: "none", stroke: "transparent", strokeWidth: "14" }), _jsx("path", { d: route.path, fill: "none", strokeWidth: "1.8", markerEnd: selection.edge === route.id ? 'url(#draft-selected-arrow)' : edgeRoles.get(route.id) === 'residual' ? 'url(#draft-skip-arrow)' : 'url(#draft-arrow)' })] }, route.id)), draft.nodes.filter(node => !implicitRoots.has(node.id)).map(node => {
                                                        const module = catalog?.modules.find(item => item.kind === node.kind);
                                                        if (!module)
                                                            return null;
                                                        const size = draftNodeSize(node, catalog);
                                                        const compact = !!(node.presentation || node.visual) && size.height < 76;
                                                        const capHeight = Math.min(36, Math.max(24, size.height - 2));
                                                        const titleWidth = Math.max(40, size.width - 26);
                                                        return _jsxs("g", { "data-draft-node": node.id, transform: `translate(${node.position.x} ${node.position.y})`, className: `draft-node ${compact ? 'compact' : ''} ${selectedIds.includes(node.id) ? 'selected' : ''} ${node.presentation?.group ? 'source-group' : ''} ${feedback?.target?.nodeId === node.id ? 'has-error' : ''}`, "data-draft-error": feedback?.target?.nodeId === node.id ? 'true' : undefined, children: [_jsx("rect", { width: size.width, height: size.height, rx: "9", style: { fill: node.presentation?.group ? 'transparent' : node.visual?.fill ?? node.presentation?.fill, stroke: node.visual?.stroke ?? node.presentation?.stroke } }), _jsx("rect", { className: "draft-node-cap", x: "1", y: "1", width: size.width - 2, height: capHeight, rx: "8" }), _jsxs("text", { x: "13", y: "23", className: "draft-node-title", style: { fontSize: 13 * labelScale }, children: [_jsx("title", { children: node.label }), draftFittedText(node.label, 13 * labelScale, titleWidth)] }), (!compact || size.height >= 56) && _jsxs("text", { x: "13", y: Math.max(45, size.height - 8), className: "draft-node-kind", style: { fontSize: compact ? 8.5 * labelScale : 10 * labelScale }, children: [_jsx("title", { children: draftSourceKind(draft, node) }), draftFittedText(draftSourceKind(draft, node), compact ? 9 * labelScale : 10 * labelScale, titleWidth, true)] }), !compact && checked?.tensors[node.id] && _jsxs("text", { x: "13", y: "49", className: "draft-node-tensor", style: { fontSize: 10 * labelScale }, children: [_jsx("title", { children: draftTensorLabel(checked.tensors[node.id]) }), draftFittedText(`声明 [${checked.tensors[node.id].shape.join(",")}]`, 10 * labelScale, titleWidth, true)] }), feedback?.target?.nodeId === node.id && _jsxs("g", { className: "draft-error-badge", children: [_jsx("circle", { cx: Math.min(size.width - 16, 160), cy: "21", r: "9" }), _jsx("text", { x: Math.min(size.width - 16, 160), y: "25", textAnchor: "middle", children: "!" })] }), module.ports.map(port => {
                                                                    const flow = geometry.nodeFlows[node.id] ?? 'horizontal';
                                                                    const p = portPoint(node, module, port.id, flow), x = p.x - node.position.x, y = p.y - node.position.y;
                                                                    const presentation = draftPortPresentation(port, x, y, flow, draftPortSpacing(module, port.direction, flow), 9 * labelScale, compact);
                                                                    const active = connection?.endpoint.nodeId === node.id && connection.endpoint.portId === port.id;
                                                                    return _jsxs("g", { "data-node": node.id, "data-draft-port": port.id, "data-draft-port-flow": flow, className: `draft-port ${port.direction} ${active ? 'active' : ''} ${feedback?.target?.nodeId === node.id && feedback.target.portId === port.id ? 'has-error' : ''}`, role: "button", tabIndex: 0, "aria-pressed": active, "aria-describedby": portHint?.nodeId === node.id && portHint.portId === port.id && tool !== 'pan' ? 'draft-port-tooltip' : undefined, "aria-label": `${node.label} ${port.name} ${port.direction === 'in' ? '输入端口' : '输出端口'}`, onPointerEnter: () => setHoveredPort({ nodeId: node.id, portId: port.id }), onPointerLeave: () => setHoveredPort(null), onFocus: () => { setHoveredPort(null); setFocusedPort({ nodeId: node.id, portId: port.id }); }, onBlur: () => setFocusedPort(null), onKeyDown: event => {
                                                                            if (event.key !== 'Enter' && event.key !== ' ')
                                                                                return;
                                                                            event.preventDefault();
                                                                            event.stopPropagation();
                                                                            if (busy || tool === 'pan')
                                                                                return;
                                                                            if (port.direction === 'out') {
                                                                                cancel();
                                                                                clearError();
                                                                                setFocusedPort({ nodeId: node.id, portId: port.id });
                                                                                setConnection({ endpoint: { nodeId: node.id, portId: port.id }, ...p });
                                                                                setNotice('连接起点已选中；点击目标输入端口，Escape 取消。');
                                                                            }
                                                                            else if (connection)
                                                                                connect(connection.endpoint, { nodeId: node.id, portId: port.id });
                                                                            else
                                                                                setNotice('先点击一个输出端口，再选择此输入端口。');
                                                                        }, children: [_jsx("rect", { className: "draft-port-hit", x: presentation.hit.x, y: presentation.hit.y, width: presentation.hit.width, height: presentation.hit.height, rx: "4", fill: "transparent", stroke: "none", pointerEvents: "all", style: { fill: 'transparent', stroke: 'none', filter: 'none' } }), _jsx("circle", { className: "draft-port-dot", cx: x, cy: y, r: "5" }), _jsx("text", { x: presentation.labelX, y: presentation.labelY, textAnchor: presentation.textAnchor, pointerEvents: compact ? 'none' : undefined, style: { fontSize: presentation.labelFontSize }, children: port.name })] }, port.id);
                                                                }), _jsx("rect", { "data-draft-drag-handle": node.id, "aria-label": `${node.label} 选择并拖动`, x: "12", y: "2", width: Math.max(1, size.width - 24), height: Math.min(capHeight - 2, Math.max(16, size.height / 2)), fill: "transparent", stroke: "none", pointerEvents: "all", style: { fill: 'transparent', stroke: 'none', filter: 'none' } })] }, node.id);
                                                    }), marquee && _jsx("rect", { className: "draft-marquee", ...marquee, fill: "#6e997b18", stroke: "#608e6e", strokeWidth: 1 / camera.zoom, pointerEvents: "none" }), start && connection && _jsx("path", { d: `M ${start.x} ${start.y} L ${connection.x} ${connection.y}`, stroke: "#b8864e", strokeWidth: "2", strokeDasharray: "6 4", fill: "none", pointerEvents: "none" })] })] }), !!geometry.routes.length && _jsx(FloatingLegend, { scene: { legend: draft.sourceProvenance?.canvas.legendItems ?? [], edges: geometry.routes.map(route => ({ id: route.id, role: edgeRoles.get(route.id) ?? 'data', stroke: edgeRoles.get(route.id) === 'residual' ? '#a76d35' : '#628572', width: 1.8, dashed: edgeRoles.get(route.id) === 'residual' })) } }), tool !== 'pan' && hintNode && hintPort && hintPosition && _jsxs("div", { id: "draft-port-tooltip", ref: hintRef, className: "draft-port-tooltip", role: "tooltip", style: { ...(measuredHint?.key === hintLayoutKey ? { left: measuredHint.left, top: measuredHint.top } : hintPosition), maxHeight: Math.max(1, viewportSize.height - 24) }, children: [_jsxs("b", { children: [hintNode.label, " \u00B7 ", hintPort.name] }), _jsxs("span", { children: [hintPort.direction === 'in' ? '输入端口' : '输出端口', hintBinding && hintProducer ? ` · 来自 ${hintProducer.label}` : hintPort.direction === 'in' ? ' · 尚未连接' : ' · 可连接多个下游'] }), hintTensor ? _jsx("span", { children: draftTensorLabel(hintTensor) }) : _jsx("span", { children: "\u5F62\u72B6\u5F85\u68C0\u67E5 \u00B7 \u6A21\u578B\u5C1A\u672A\u6267\u884C" }), _jsx("small", { children: hintPort.direction === 'out' ? '点击或按 Enter 选择，再连接输入端口。' : connection ? '点击或按 Enter 连接；形状以静态检查为准。' : '先选择输出端口，再连接到这里。' })] }), !draft.nodes.length && _jsxs("div", { className: "draft-empty", children: [_jsx("span", { children: "\u4ECE\u96F6\u642D\u5EFA\u4E00\u4E2A\u6A21\u578B" }), _jsx("h2", { children: "\u628A\u7B2C\u4E00\u4E2A Input \u62D6\u5230\u8FD9\u91CC" }), _jsxs("p", { children: ["\u518D\u52A0\u5165 Linear\u3001\u6FC0\u6D3B\u51FD\u6570\u4E0E Output\u3002", _jsx("br", {}), "\u4E5F\u53EF\u4EE5\u4ECE\u5DE6\u4FA7\u201C\u7F51\u7EDC\u8D77\u70B9\u201D\u52A0\u5165\u5B8C\u6574 MLP\u3001CNN \u6216\u6B8B\u5DEE\u7F51\u7EDC\u3002"] }), _jsx("button", { disabled: !catalog, onClick: () => { const input = catalog?.modules.find(module => module.kind === 'Input'); if (input)
                                                    add(input, { x: 80, y: 120 }); }, children: "\u6DFB\u52A0\u8F93\u5165" })] })] }), _jsx("div", { className: "draft-help", children: "Shift \u8FDE\u7EED\u9009\u62E9 \u00B7 \u6846\u9009 / Ctrl+A \u591A\u9009 \u00B7 \u62D6\u52A8\u6574\u4F53 \u00B7 \u6EDA\u8F6E\u7F29\u653E \u00B7 \u4E2D\u952E/Alt \u5E73\u79FB \u00B7 \u8F93\u51FA\u7AEF\u53E3 \u2192 \u8F93\u5165\u7AEF\u53E3 \u00B7 \u65B9\u5411\u952E\u79FB\u52A8 16 \u00B7 Delete \u5220\u9664 \u00B7 Escape \u53D6\u6D88 \u00B7 Ctrl+Z \u64A4\u9500" })] }), _jsxs("aside", { className: "draft-inspector", children: [_jsx("span", { className: "eyebrow", children: "MODEL PROPERTIES" }), selected && selectedModule ? _jsxs(_Fragment, { children: [_jsx("h2", { children: draftSourceKind(draft, selected) }), selectedIds.length > 1 && _jsxs("p", { children: ["\u5DF2\u9009\u62E9 ", selectedIds.length, " \u4E2A\u90E8\u4EF6\uFF1B\u62D6\u52A8\u6216\u65B9\u5411\u952E\u53EF\u6574\u4F53\u79FB\u52A8\u3002"] }), draft.sourceProvenance?.nodeRefs[selected.id] && _jsxs("div", { className: "draft-source-evidence", children: [_jsx("b", { children: "\u6E90\u7801\u7F16\u8F91\u526F\u672C" }), _jsx("p", { children: "\u4FDD\u7559\u5B8C\u6574\u6E90\u7801\u3001\u5C42\u7EA7\u3001\u5171\u4EAB\u548C\u672A\u77E5\u4E8B\u5B9E\u3002\u6B64\u5904\u7ED3\u6784\u7F16\u8F91\u53EA\u5F71\u54CD\u72EC\u7ACB\u8349\u7A3F\u3002" }), _jsx("code", { children: draft.sourceProvenance.nodeRefs[selected.id].nodeId }), _jsxs("details", { children: [_jsx("summary", { children: "\u539F\u59CB\u53C2\u6570\u4E0E\u4E8B\u5B9E" }), _jsx("pre", { children: JSON.stringify(draft.sourceProvenance.architecture.nodes.find(node => node.id === draft.sourceProvenance?.nodeRefs[selected.id]?.nodeId)?.parameters, null, 2) })] }), _jsxs("p", { children: [draft.sourceProvenance.nodeRefs[selected.id].repeat && `重复 ${draft.sourceProvenance.nodeRefs[selected.id].repeat.count} 次 · ${draft.sourceProvenance.nodeRefs[selected.id].repeat.sharing}`, " ", draft.sourceProvenance.nodeRefs[selected.id].evidence === 'opaque' && '未知区域：可移动、重连或替换；生成需明确表达式。'] })] }), draft.sourceProvenance?.architecture.nodes.find(node => node.id === draft.sourceProvenance?.nodeRefs[selected.id]?.nodeId)?.children.length ? _jsx("button", { disabled: busy, onClick: () => void toggleSourceHierarchy(selected.id), children: selected.presentation?.group ? '折叠此源码区域' : '展开此源码区域' }) : null, _jsxs("label", { className: "draft-field", children: ["\u663E\u793A\u540D\u79F0", _jsx(DraftTextInput, { ariaLabel: "\u6A21\u5757\u663E\u793A\u540D\u79F0", value: selected.label, disabled: busy, onCommit: label => apply(value => { value.nodes.find(node => node.id === selected.id).label = label; }) })] }), _jsx("div", { className: "draft-param-fields", children: selectedModule.parameters.map(parameter => _jsx(DraftField, { kind: selected.kind, parameter: parameter, value: selected.parameters[parameter.name], disabled: busy, error: feedback?.target?.nodeId === selected.id && feedback.target.parameter === parameter.name ? feedback.message : undefined, onValidity: invalid => fieldValidity(selected.id, parameter.name, invalid), onDiscardInvalid: discardInvalidInput, onCommit: value => apply(next => { next.nodes.find(node => node.id === selected.id).parameters[parameter.name] = value; }) }, `${selected.id}:${parameter.name}`)) }), _jsx("p", { className: "draft-description", children: selectedModule.description }), selected.kind === 'Linear' && _jsx("p", { className: "draft-parameter-help", children: "\u4F8B\u5982\u8F93\u5165\u5F62\u72B6\u4E3A [1, 16] \u65F6\uFF0Cin_features \u5E94\u4E3A 16\uFF1Bout_features \u51B3\u5B9A\u8F93\u51FA\u6700\u540E\u4E00\u7EF4\u3002" }), _jsx("div", { className: "draft-coordinate", children: ['x', 'y'].map(axis => _jsxs("label", { children: [axis.toUpperCase(), _jsx("input", { "aria-label": `模块 ${axis.toUpperCase()} 坐标`, type: "number", value: selected.position[axis], disabled: busy, onChange: event => { if (event.target.value && Number.isFinite(Number(event.target.value)))
                                                        apply(value => { value.nodes.find(node => node.id === selected.id).position[axis] = Number(event.target.value); }); } })] }, axis)) }), _jsx("button", { disabled: busy, onClick: deleteSelection, children: "\u5220\u9664\u6A21\u5757\u53CA\u76F8\u8FDE\u8FDE\u7EBF" })] }) : selection.edge ? _jsxs(_Fragment, { children: [_jsx("h2", { children: "\u5F20\u91CF\u8FDE\u7EBF" }), _jsx("p", { children: "\u6B64\u8FDE\u7EBF\u5B9A\u4E49\u6A21\u5757\u7684\u8F93\u5165\u6765\u6E90\u3002" }), _jsx("button", { disabled: busy, onClick: deleteSelection, children: "\u5220\u9664\u8FDE\u7EBF" })] }) : _jsxs(_Fragment, { children: [_jsx("h2", { children: "\u6BCF\u4E00\u6B65\u90FD\u5728\u56FE\u4E0A\u5B8C\u6210" }), _jsxs("ol", { children: [_jsx("li", { children: "\u62D6\u5165 Input\uFF0C\u8BBE\u7F6E\u8F93\u5165\u5F62\u72B6\u3002" }), _jsx("li", { children: "\u62D6\u5165\u5E38\u7528\u6A21\u5757\uFF0C\u7F16\u8F91\u53C2\u6570\u3002" }), _jsx("li", { children: "\u8FDE\u63A5\u7AEF\u53E3\uFF0C\u52A0\u5165 Output\u3002" }), _jsx("li", { children: "\u4FDD\u5B58\u8349\u7A3F\uFF0C\u751F\u6210\u6A21\u578B\u4E0E\u8BBA\u6587\u56FE\u3002" })] }), _jsx("p", { children: "\u968F\u65F6\u70B9\u51FB\u201C\u68C0\u67E5\u6A21\u578B\u201D\uFF0C\u67E5\u770B\u7F3A\u5C11\u7684\u8FDE\u63A5\u4E0E\u58F0\u660E\u5F62\u72B6\uFF1B\u5B8C\u6210\u540E\u518D\u751F\u6210\u3002\u5F53\u524D\u662F\u9759\u6001\u5EFA\u6A21\uFF0C\u6A21\u578B\u5C1A\u672A\u6267\u884C\u3002" })] }), _jsxs("section", { className: "draft-check", "aria-label": "\u6A21\u578B\u9759\u6001\u68C0\u67E5", children: [_jsx("h3", { children: checked ? checked.complete ? draft.customModules?.length ? '连接检查通过 · 自定义形状未知' : draft.sourceProvenance ? '连接检查通过' : '静态检查通过' : `${checked.issues.length} 项待完成` : '检查当前结构' }), _jsx("p", { children: checked ? draft.customModules?.length ? '仅检查静态连接；自定义模块及下游输出形状未推测，模型尚未执行。' : draft.sourceProvenance ? '保留源码事实；当前连接检查不推测未知形状，模型尚未执行。' : '以下形状来自静态声明，模型尚未执行。' : '参数、模块或连接改变后需重新检查；移动和显示名称不影响声明形状。' }), selected && checked?.tensors[selected.id] && _jsx("div", { className: "draft-checked-tensor", children: draftTensorLabel(checked.tensors[selected.id]) }), checked?.issues.map((issue, index) => { const targets = (issue.nodeId ? [issue.nodeId] : issue.nodeIds ?? []).filter(id => draft.nodes.filter(node => node.id === id).length === 1); return _jsxs("div", { className: "draft-check-issue", children: [_jsx("span", { children: issue.message }), targets.map(id => _jsx("button", { onClick: () => { reportError(new ApiError(issue.technical ?? issue.message, 400, [{ ...issue, nodeId: id }])); }, children: `定位 ${draft.nodes.find(node => node.id === id).label}` }, id))] }, `${issue.code}:${index}`); }), _jsx("button", { disabled: busy || !catalog || !!invalidFields.length, onClick: () => void check(), children: checked ? '重新检查' : '检查模型' })] }), _jsxs("div", { className: "draft-summary", children: [_jsx("b", { children: draft.nodes.length }), " \u6A21\u5757 ", _jsx("b", { children: draft.edges.length }), " \u8FDE\u63A5"] })] })] }), _jsxs("footer", { className: `authoring-status ${error ? 'error' : ''}`, role: error || invalidFields.length ? 'alert' : 'status', children: [busy ? ({ check: '正在检查模型…', save: '正在保存草稿…', reopen: '正在重开保存的草稿…', generate: '正在生成并核对模型…', open: '正在打开新工作副本…', frontier: '正在展开源码层级并保留草稿编辑…' }[busyOperation ?? 'check']) : invalidFields.length ? '参数输入尚未有效：请修正标记字段，或按 Escape 恢复上次有效值，再保存或生成。' : error || currentNotice, !busy && error && feedback?.target && _jsx("button", { onClick: () => focusDraftNode(feedback.target.nodeId), children: "\u5B9A\u4F4D\u51FA\u9519\u6A21\u5757" }), !busy && error && feedback?.technical && _jsxs("details", { children: [_jsx("summary", { children: "\u6280\u672F\u8BE6\u60C5" }), _jsx("span", { children: feedback.technical })] })] }), customModuleOpen && _jsx(CustomModuleDialog, { onClose: () => setCustomModuleOpen(false), onInsert: insertCustomModule }), generated && _jsx("div", { className: "modal-backdrop", children: _jsxs("section", { className: "authoring-review", role: "dialog", "aria-modal": "true", "aria-label": "\u751F\u6210\u7684\u65B0\u6A21\u578B", children: [_jsxs("div", { className: "modal-heading", children: [_jsxs("div", { children: [_jsx("span", { className: "eyebrow", children: "NEW MODEL" }), _jsx("h2", { children: "\u6A21\u578B\u5DF2\u751F\u6210\u5E76\u9759\u6001\u6838\u5BF9" })] }), _jsx("button", { onClick: () => setGenerated(null), disabled: busy, children: _jsx(Icon, { name: "close" }) })] }), _jsxs("p", { children: [generated.draft.sourceProvenance ? '原源码已保留在独立新副本，生成源码通过语法与静态分析检查；不声明数值等价或执行验证。' : '节点、端口、参数和连接已与新源码的分析结果核对。', "\u63A5\u4E0B\u6765\u53EF\u6253\u5F00\u8BBA\u6587\u56FE\u3001\u7F16\u8F91\u6837\u5F0F\u5E76\u5BFC\u51FA\uFF1B\u6A21\u578B\u5C1A\u672A\u6267\u884C\u3002"] }), _jsx("pre", { children: generated.source }), _jsxs("div", { className: "modal-actions", children: [_jsx("button", { disabled: busy, onClick: () => setGenerated(null), children: "\u7EE7\u7EED\u642D\u5EFA" }), _jsx("button", { className: "primary", disabled: busy, onClick: async () => { setBusy(true); setBusyOperation('open'); try {
                                        await onOpen(generated);
                                    }
                                    catch (reason) {
                                        reportError(reason);
                                        setBusyOperation(null);
                                        setBusy(false);
                                    } }, children: "\u521B\u5EFA\u65B0\u5DE5\u4F5C\u526F\u672C\u5E76\u6253\u5F00\u8BBA\u6587\u56FE" })] })] }) })] });
}
function DraftTextInput({ ariaLabel, value, disabled, onCommit }) {
    const [text, setText] = useState(value);
    const [invalid, setInvalid] = useState(false);
    const errorId = useId();
    useEffect(() => { setText(value); setInvalid(false); }, [value]);
    function commit() {
        const next = text.trim();
        if (!next || next.length > 120 || /[\x00-\x1f]/.test(next)) {
            setInvalid(true);
            return;
        }
        setInvalid(false);
        if (next !== value)
            onCommit(next);
    }
    function restore() { setText(value); setInvalid(false); }
    return _jsxs(_Fragment, { children: [_jsx("input", { "aria-label": ariaLabel, "aria-invalid": invalid, "aria-describedby": invalid ? errorId : undefined, maxLength: 120, value: text, disabled: disabled, onChange: event => { setText(event.target.value); }, onBlur: commit, onKeyDown: event => { if (event.key === 'Enter')
                    event.currentTarget.blur(); if (event.key === 'Escape')
                    restore(); } }), invalid && _jsx("small", { id: errorId, role: "alert", children: "\u540D\u79F0\u987B\u4E3A 1\u2013120 \u4E2A\u5B57\u7B26\uFF0C\u4E0D\u80FD\u542B\u63A7\u5236\u5B57\u7B26\uFF1B\u6309 Escape \u6062\u590D\u4E0A\u6B21\u6709\u6548\u540D\u79F0\u3002" })] });
}
function DraftField({ kind, parameter, value, disabled, error, onCommit, onValidity, onDiscardInvalid }) {
    const display = () => Array.isArray(value) ? value.join(', ') : String(value);
    const [text, setText] = useState(display);
    const [invalid, setInvalid] = useState('');
    const effectiveValue = JSON.stringify(value);
    const invalidRef = useRef(false);
    const callbacks = useRef({ onValidity, onDiscardInvalid });
    callbacks.current = { onValidity, onDiscardInvalid };
    const message = '请输入范围内的有效数值；数组用逗号分隔且不能留空。';
    function validity(bad) { invalidRef.current = bad; callbacks.current.onValidity(bad); setInvalid(bad ? message : ''); }
    useEffect(() => { if (invalidRef.current)
        callbacks.current.onDiscardInvalid(); setText(display()); validity(false); }, [effectiveValue]);
    useEffect(() => () => { callbacks.current.onValidity(false); if (invalidRef.current)
        callbacks.current.onDiscardInvalid(); }, []);
    function commit() {
        const next = parseDraftField(text, parameter);
        validity(next === null);
        if (next !== null && JSON.stringify(next) !== JSON.stringify(value))
            onCommit(next);
    }
    function restore() { if (invalidRef.current)
        callbacks.current.onDiscardInvalid(); setText(display()); validity(false); }
    const errorId = `draft-parameter-${parameter.name}-error`, helpId = `draft-parameter-${parameter.name}-help`, help = invalid || error;
    const guidance = draftParameterHelp(kind, parameter.name);
    const describedBy = [guidance && helpId, help && errorId].filter(Boolean).join(' ') || undefined;
    return _jsxs("label", { className: `draft-field ${help ? 'has-error' : ''}`, "data-draft-parameter": parameter.name, children: [_jsxs("span", { children: [guidance?.label ?? parameter.name, guidance && _jsx("code", { className: "draft-parameter-name", children: parameter.name })] }), parameter.type === 'boolean' ? _jsx("input", { type: "checkbox", "aria-label": parameter.name, "aria-describedby": describedBy, checked: value === true, disabled: disabled, onChange: event => onCommit(event.target.checked) }) : parameter.type === 'choice' ? _jsx("select", { "aria-label": parameter.name, "aria-describedby": describedBy, value: String(value), disabled: disabled, onChange: event => onCommit(event.target.value), children: parameter.options?.map(option => _jsx("option", { value: option, children: option }, option)) }) : _jsx("input", { "aria-label": parameter.name, "aria-invalid": !!help, "aria-describedby": describedBy, inputMode: parameter.type === 'integer-array' ? 'text' : 'decimal', value: text, disabled: disabled, onChange: event => { setText(event.target.value); validity(parseDraftField(event.target.value, parameter) === null); }, onBlur: commit, onKeyDown: event => { if (event.key === 'Enter')
                    event.currentTarget.blur(); if (event.key === 'Escape')
                    restore(); } }), guidance && _jsxs("small", { id: helpId, className: "draft-field-help", children: [guidance.description, parameter.type === 'integer-array' && ' 填写逗号分隔的数字（如 1, 3），无需输入方括号。'] }), help && _jsx("small", { id: errorId, role: "alert", children: help })] });
}
