"""Finite source/fixture/history audit; no browser, model import or execution."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import re

ROOT = Path(__file__).resolve().parents[5]
OUT = Path(__file__).resolve().parent

def read(path):
    return (ROOT / path).read_text(encoding="utf-8")

def binding(path, kind):
    data = (ROOT / path).read_bytes()
    return {"path": path, "kind": kind, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}

def location(path, needle):
    rows = read(path).splitlines()
    matches = [i + 1 for i, line in enumerate(rows) if needle in line]
    if len(matches) != 1:
        raise ValueError((path, needle, matches))
    return {"path": path, "line": matches[0], "needle": needle}

own = OUT.relative_to(ROOT).as_posix()
catalog = json.loads((OUT / "formal-catalog.json").read_text())
stage = ROOT / "docs/evidence/m4-frontier-move-current"
receipt_files = sorted(stage.glob("checks-final-attempt-*/receipt.json"), key=lambda path: int(path.parent.name.rsplit("-", 1)[1]))
if not receipt_files:
    raise FileNotFoundError("no checks-final-attempt receipt")
receipt_file = receipt_files[-1]
receipt_path = receipt_file.relative_to(ROOT).as_posix()
receipt = json.loads(receipt_file.read_text(encoding="utf-8"))
current = {row["path"]: row for row in receipt["inputs"]}
historic_path = "docs/evidence/m4-ai-simulated-current/final-readback/catalog-independent/implementation-report.json"
historic = {row["path"]: row for row in json.loads(read(historic_path))["currentBindings"]}
authoring_files = [
    "studio/src/AuthoringStudio.tsx", "studio/src/AuthoringStudio.css", "studio/src/authoring.ts",
    "studio/src/authoringPresets.ts", "studio/src/draftParameterHelp.ts", "studio/src/draftNodeGeometry.ts",
    "studio/src/draftPortPresentation.ts", "studio/src/draftRouting.ts", "studio/src/authoringFeedback.ts",
    "studio/src/draftValidation.ts",
]
comparisons = []
for path in authoring_files:
    digest = binding(path, "current-authoring")["sha256"]
    comparisons.append({"path": path, "actualSha256": digest,
                        "matchesCurrentFinalReceipt": digest == current[path]["sha256"],
                        "matchesHistoricalBXHFiniteInput": digest == historic[path]["actualSha256"]})
receipt_drift = [row["path"] for row in comparisons if not row["matchesCurrentFinalReceipt"]]
source_receipt_status = {
    "receipt": receipt_path,
    "boundToCurrentSource": not receipt_drift,
    "driftedPaths": receipt_drift,
    "reason": "AuthoringStudio contains the post-P2 blank-draft guard; the parent must rerun final suite/build to issue a receipt bound to this byte." if receipt_drift else "Current source matches the parent final receipt.",
}

focused = []
for name, expected in [("focused-authoring.tap", 17), ("focused-geometry-feedback.tap", 19)]:
    txt = (OUT / name).read_text()
    stats = {key: int(re.search(rf"^ℹ {key} (\d+)$", txt, re.M).group(1))
             for key in ["tests", "pass", "fail", "cancelled", "skipped", "todo"]}
    if stats != {"tests": expected, "pass": expected, "fail": 0, "cancelled": 0, "skipped": 0, "todo": 0}:
        raise ValueError((name, stats))
    focused.append({"log": f"{own}/{name}", "exitCode": 0, **stats,
                    "existingTestsRepeated": True, "mountedBrowser": False, "modelExecution": "not_run",
                    "passedNames": [re.sub(r" \([^()]+ms\)$", "", row[2:])
                                    for row in txt.splitlines() if row.startswith("✔ ")]})

code = {
    "entry": location("studio/src/App.tsx", "setAuthoringOpen(true)"),
    "capability": location("src/archcanvas_cli/server.py", '"modelAuthoring":'),
    "libraryAndBlankAction": location("studio/src/AuthoringStudio.tsx", '<aside className="module-palette">'),
    "crossTabModuleSearch": location("studio/src/AuthoringStudio.tsx", "const matches ="),
    "crossTabPresetSearch": location("studio/src/AuthoringStudio.tsx", "const presetMatches ="),
    "moduleAddition": location("studio/src/AuthoringStudio.tsx", "function add(module:"),
    "presetAddition": location("studio/src/AuthoringStudio.tsx", "function addPreset("),
    "dragDrop": location("studio/src/AuthoringStudio.tsx", '<div className="draft-viewport"'),
    "blankResetHandler": location("studio/src/AuthoringStudio.tsx", "const next = draftHistory(createBlank());"),
    "fourDirections": location("studio/src/AuthoringStudio.tsx", "const move = { ArrowLeft:"),
    "undoKey": location("studio/src/AuthoringStudio.tsx", "travel(event.shiftKey ? 'redo' : 'undo')"),
    "blankDraftGuard": location("studio/src/AuthoringStudio.tsx", "function startBlankDraft()"),
    "historyReset": location("studio/src/authoring.ts", "export function draftHistory"),
    "cacheReplacement": location("studio/src/AuthoringStudio.tsx", "localStorage.setItem(CACHE"),
    "staticCheck": location("studio/src/AuthoringStudio.tsx", "async function check()"),
    "generationReview": location("studio/src/AuthoringStudio.tsx", 'aria-label="生成的新模型"'),
    "parameterFields": location("studio/src/AuthoringStudio.tsx", "function DraftField("),
    "boundedBackendCatalog": location("src/archcanvas_authoring/draft.py", "def module_catalog()"),
    "transparentPresetDefinition": location("studio/src/authoringPresets.ts", "export const draftPresets:"),
}

historical_paths = [
    "docs/evidence/m4-ai-simulated-current/catalog-visual/README.md",
    "docs/evidence/m4-ai-simulated-current/catalog-visual/01-empty.dom.txt",
    "docs/evidence/m4-ai-simulated-current/catalog-visual/01-empty.jpg",
    "docs/evidence/m4-ai-simulated-current/catalog-visual/05-network-starts.dom.txt",
    "docs/evidence/m4-ai-simulated-current/catalog-visual/05-network-starts.jpg",
    "docs/evidence/m4-ai-simulated-current/catalog-visual/08-cnn-dragged.dom.txt",
    "docs/evidence/m4-ai-simulated-current/catalog-visual/10-cnn-after-arrange.dom.txt",
    "docs/evidence/m4-ai-simulated-current/catalog-followup/README.md",
    "docs/evidence/m4-ai-simulated-current/catalog-followup/pixel-review.json",
    "docs/evidence/m4-ai-simulated-current/catalog-followup/public-geometry-audit.json",
    "docs/evidence/m4-ai-simulated-current/final-browser/receipt.json",
    "docs/evidence/m4-ai-simulated-current/final-browser/07-final-cnn-settled.dom.txt",
    "docs/evidence/m4-ai-simulated-current/final-browser/07-final-cnn-settled.json",
    "docs/evidence/m4-ai-simulated-current/final-browser/07-final-cnn-settled.jpg",
    historic_path,
]
tests = ["studio/tests/authoring-presets.test.ts", "studio/tests/authoring-interaction-independent.test.ts",
         "studio/tests/draft-port-geometry-independent.test.ts", "studio/tests/authoring-feedback-independent.test.ts",
         "studio/tests/ai-usability-regressions.test.ts"]
bindings = [binding(p, "current-authoring") for p in authoring_files]
bindings += [binding(p, "current-source") for p in ["studio/src/App.tsx", "src/archcanvas_authoring/draft.py",
    "src/archcanvas_authoring/__init__.py", "src/archcanvas_cli/server.py"]]
bindings += [binding(p, "current-test-source") for p in tests]
bindings += [binding(p, "current-final-checks") for p in [receipt_path,
    "docs/evidence/m4-frontier-move-current/checks-final-attempt-1/studio.txt",
    "docs/evidence/m4-frontier-move-current/checks-final-attempt-1/strict-build.txt"]]
bindings += [binding(p, "historical-evidence") for p in historical_paths]
bindings += [binding(p, "current-frontier-figure-only") for p in [
    "docs/evidence/m4-frontier-move-current/browser/receipt.json",
    "docs/evidence/m4-frontier-move-current/browser/13-reopened16.json",
    "docs/evidence/m4-frontier-move-current/browser/13-reopened16.png"]]
bindings += [binding(f"{own}/{p}", "this-audit") for p in ["README.md", "audit.py", "formal-catalog.json",
    "focused-authoring.tap", "focused-geometry-feedback.tap"]]

report = {
    "schema": "archcanvas-ai-catalog-code-fixture-trial/1", "createdUtc": datetime.now(timezone.utc).isoformat(),
    "reviewer": "/root/ai_catalog_frontier", "reviewerType": "AI simulated code/fixture/historical-image reviewer",
    "scope": "Formal implementation and current focused/full checks, plus explicitly historical bounded UI evidence. No current mounted authoring or native input claim.",
    "authorization": "User authorized 3–5 AI subagent simulations; AI simulations do not satisfy real researcher acceptance.",
    "humanParticipants": 0, "currentNativeAuthoringAttempts": 0, "modelExecution": "not_run",
    "productModifiedByThisAgent": False, "currentSourceContainsParentFix": True,
    "oldSealedEvidenceModified": False, "researchReadinessUsedForAcceptance": False,
    "m4": "partial", "m5": "not_started", "verdict": "bounded catalog and transparent starts present; P2 blank-draft replacement guard is present in current source; current native novice completion and human usability remain unverified",
    "formalOrigin": {"project": str(ROOT), "python": str(ROOT / ".venv/bin/python"),
        "catalogReadCommand": [".venv/bin/python", "-I", "-S", "-B", "-c", "formal module_catalog data only"],
        "prototypeDirectoryUsed": False, "legacyRuntimeFallback": False, "reusedPrototypeCodeCertified": False},
    "catalog": {"raw": f"{own}/formal-catalog.json", "moduleCount": len(catalog["modules"]),
        "categoryCount": len({m["category"] for m in catalog["modules"]}),
        "parameterFieldCount": sum(len(m["parameters"]) for m in catalog["modules"]),
        "parameterizedModuleCount": sum(bool(m["parameters"]) for m in catalog["modules"]),
        "kinds": [{"kind": m["kind"], "label": m["label"], "category": m["category"],
                   "parameters": [p["name"] for p in m["parameters"]], "ports": m["ports"]} for m in catalog["modules"]],
        "explicitlyUnsupported": catalog["unsupported"], "limits": catalog["limits"],
        "staticDeclaredTensorsOnly": True, "perKindIndependentGenerationOrExecutionCertified": False},
    "presets": [
        {"id": "mlp", "label": "最小 MLP", "nodes": 5, "edges": 4, "input": [1, 16], "output": [1, 4]},
        {"id": "cnn", "label": "小型 CNN", "nodes": 8, "edges": 7, "input": [1, 3, 32, 32], "output": [1, 4]},
        {"id": "residual-mlp", "label": "残差 MLP", "nodes": 6, "edges": 6, "input": [1, 16], "output": [1, 16]},
    ],
    "codeLocations": code, "finiteAuthoringByteComparisons": comparisons, "sourceReceiptStatus": source_receipt_status,
    "byteComparisonLimit": "Ten matching authoring files are not a transitive dependency/font/browser/environment proof and do not inherit historical pixel, timing or human acceptance.",
    "checks": {"parentFinalReceipt": receipt_path, "currentFullSuite": next(check for check in receipt["checks"] if check["label"] == "studio"),
               "strictBuildExit": next(check["exitCode"] for check in receipt["checks"] if check["label"] == "strict-build"),
               "receiptBoundToCurrentSource": source_receipt_status["boundToCurrentSource"],
               "focusedRepeatedExistingTests": focused,
               "countLimit": "Focused17+19 are repeated subsets inside the parent receipt; no additive product count, human count or mounted UI proof."},
    "fromZeroSimulation": [
        {"step": 1, "action": "Click 搭建模型; begin blank authored-draft", "currentEvidence": [code["entry"], code["libraryAndBlankAction"]],
         "status": "implemented source path; current native untested", "noviceJudgment": "Separate model-authoring workspace and central Input prompt provide a direct entry."},
        {"step": 2, "action": "Find Input, Linear, activation, Output and three network starts", "currentEvidence": [code["crossTabModuleSearch"], code["crossTabPresetSearch"], code["libraryAndBlankAction"]],
         "status": "17+3 inventory and cross-tab search present", "noviceJudgment": "Counts and Chinese/English search help discovery; lower modules/residual require scrolling in historical viewport."},
        {"step": 3, "action": "Click or drag cards to add, then edit right-side parameters", "currentEvidence": [code["moduleAddition"], code["dragDrop"], code["parameterFields"]],
         "status": "source implementation and current fixtures; historical native drag only", "noviceJudgment": "Click fallback and notices are clear; drag to occupied space intentionally may overlap and should show warning/arrange, not silently auto-move existing objects."},
        {"step": 4, "action": "Connect output to input; inspect missing bindings or shape mismatch", "currentEvidence": [code["staticCheck"], code["parameterFields"]],
         "status": "fixtures cover malformed ports, occupied inputs, cycles, field validation and structured identity diagnostics", "noviceJudgment": "Explicit port direction, keyboard Enter and Escape help, shape mismatch does not infer target from alias."},
        {"step": 5, "action": "Undo additions/preset; redo; arrange; save/reopen; review generated source", "currentEvidence": [code["presetAddition"], code["undoKey"], code["generationReview"]],
         "status": "current helper/transport fixtures and three static-generated preset round trips; no current native end-to-end", "noviceJudgment": "Preset notice explicitly explains one undo step; generation stays static and opens a fresh managed copy after review."},
    ],
    "historicalBoundedEvidence": [
        {"build": "index-DuFXKOwG.js", "evidence": "docs/evidence/m4-ai-simulated-current/catalog-visual/README.md",
         "reportedNativeScope": "17 kinds added/properties browsed then undone; clicked MLP; dragged CNN; residual deletion/reconnection; four-direction CNN/merge moves; configured CNN saved.",
         "retainFailures": ["CNN arrangement40percent unreadability", "parameter-bearing preset aliases become stale", "residual initial53percent small text"],
         "inheritance": "Historical only, no current native/mounted conclusion."},
        {"build": "index-CC91IvNz.js", "evidence": "docs/evidence/m4-ai-simulated-current/catalog-followup/README.md",
         "reportedNativeScope": "CNN arrangement into3columns3rows91percent, four-direction Conv moves with undo, channel mismatch repair, save/reopen.",
         "retainFailures": ["02/03/04/19 screenshot-state mismatch", "75percent text small", "no MLP/residual complete repeat"],
         "inheritance": "Historical bounded fix retest;154 route relations are DOM geometry, not154 product tests or universal synchrony."},
        {"build": "index-B_XHk-wz.js", "evidence": "docs/evidence/m4-ai-simulated-current/final-browser/receipt.json",
         "reportedNativeScope": "CNN2columns4rows84percent, AdaptiveAvgPool2d output_size2,2/static mismatch repair, saved/reopened; no full17kind/fourdirections.",
         "inheritance": "Finite ten authoring SHA matches noted separately; no current pixels/performance inherited."},
    ],
    "personalHistoricalImageReview": [
        {"path": "docs/evidence/m4-ai-simulated-current/catalog-visual/01-empty.jpg", "build": "DuFX", "observed": "Module count17, base/network tabs, cross-search hint, Input/Output/Linear visible, central Input prompt and right-side four-step instructions. Lower palette kinds are below fold.", "currentClaim": False},
        {"path": "docs/evidence/m4-ai-simulated-current/catalog-visual/05-network-starts.jpg", "build": "DuFX", "observed": "Network count3; MLP and CNN cards show editable start explanation, input/output and module counts. Residual card below fold; cannot claim all3 visible simultaneously.", "currentClaim": False},
        {"path": "docs/evidence/m4-ai-simulated-current/final-browser/07-final-cnn-settled.jpg", "build": "B_XH", "observed": "Eight complete cards at84percent2columns4rows; all three starts visible in palette. Straight adjacent arrows end at displayed ports; outer row-return bends provide a route around bodies. Nominal titles are identifiable in this stored image; small type and long returns are not human physical-size approval.", "currentClaim": False},
    ],
    "currentFrontierBrowserUse": {"receipt": "docs/evidence/m4-frontier-move-current/browser/receipt.json",
        "scope": "Thirteen source-bound figure states: scoped movement, undo, collapse/reexpand and save/reopen; no authoring palette evidence.",
        "usedToProveCurrentCatalogUI": False},
    "findings": [
        {"id": "AC-CATALOG-01", "priority": "P2", "kind": "fixed-in-current-source", "title": "新建空白模型现在保护未保存草稿",
         "trigger": "A user with unsaved authored edits clicks 新建空白模型.",
         "evidence": [code["blankDraftGuard"], code["blankResetHandler"], code["historyReset"], code["cacheReplacement"]],
         "result": "The current handler calls cancel(), then when dirty and revision/nodes exist it only shows ‘当前草稿有未保存编辑，请先保存或重开后再新建空白模型。’ and returns. Clean drafts may still install draftHistory(createBlank()) and reset storage/saved revisions; the sole CACHE effect then stores the new clean draft.",
         "previousIssue": "The prior report identified direct replacement of an unsaved draft and its undo history.",
         "confidence": "Direct current-source evidence after the P2 fix; current mounted/browser guard reproduction remains pending.",
         "recommendation": "Run one current native check: edit a node, click 新建空白模型, verify notice and preservation; then verify a clean draft can reset.", "productChangedByParent": True, "productModifiedByThisAgent": False},
        {"id": "AC-CATALOG-02", "priority": "P3", "kind": "scope-gap", "title": "常用库仍为有界17类型而非广泛模型积木库",
         "evidence": [code["boundedBackendCatalog"]], "absent": ["Sigmoid", "Tanh", "Softmax", "Conv1d", "AvgPool2d", "BatchNorm1d", "Reshape", "Permute", "ConvTranspose2d", "Upsample", "MultiheadAttention", "LSTM"],
         "confidence": "Absence from actual current catalog; list mixes explicitly unsupported kinds with unregistered follow-up candidates, not a claim that all are planned.",
         "recommendation": "Prioritize common simple activation/classification/1D/pooling operators with exact parameter, tensor-shape and generated-source contracts; complex attention/recurrent operators need separate scoped design and independent evidence."},
        {"id": "AC-CATALOG-03", "priority": "P3", "kind": "historical-discoverability", "title": "基础模块下部和残差起点需滚动",
         "evidence": ["docs/evidence/m4-ai-simulated-current/catalog-visual/01-empty.jpg", "docs/evidence/m4-ai-simulated-current/catalog-visual/05-network-starts.jpg"],
         "confidence": "Historical1280x720 stored images and current source; currentviewport not observed.",
         "recommendation": "Retain visible counts/cross-search and consider category navigation or a clearly visible palette-scroll cue; verify with real novices before calling discovery complete."},
    ],
    "notCovered": ["Current CW7 native pure-view authoring from blank", "Current native catalog drag/drop, click/undo and port interactions",
        "Current authoring keyboard/node/camera four-direction matrix", "Current authoring pixel/state synchronization", "Every17kind independently generated complete model",
        "Any model execution or numerical correctness", "Full keyboard/accessibility/touch workflow", "Other viewport/font/hardware conditions", "Global minimal crossings/bends or aesthetic approval",
        "Actual85/180mm publication readability", "Presented FPS or input-to-paint latency", "Real3–5researcher five-step tasks/timing/success rate"],
    "finiteBindings": bindings, "finiteBindingCount": len(bindings),
    "bindingLimit": "Finite explicitly selected evidence bytes; no complete transitive dependency, environment, old sealed directory or study-package audit.",
}
(OUT / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"catalog": len(catalog["modules"]), "focusedExistingSubsets": [x["tests"] for x in focused],
                  "currentBoundAuthoringFiles": len(comparisons), "finiteBindings": len(bindings), "humans": 0,
                  "currentNativeAuthoringAttempts": 0, "report": str(OUT / "report.json")}, ensure_ascii=False))
