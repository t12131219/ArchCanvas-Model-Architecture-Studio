"""Serialize direct AI pixel observations and read only frozen public evidence.

No browser calls, renderer/model/product execution, tests or source edits. The
observations were personally made via tools.view_image before serialization.
"""
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import math
import re

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
RAW = ROOT / "docs/evidence/m4-native-matching-work/authoring-smoke"
STAMP = datetime.now(timezone.utc).isoformat()


def read(p):
    return json.loads(p.read_text())


def bind(p):
    data = p.read_bytes()
    return {"path": str(p.relative_to(ROOT)), "bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest()}


def put(name, data):
    p = OUT / name
    if p.exists():
        raise RuntimeError("Preserve earlier evidence: " + str(p))
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    return bind(p)


def public(name):
    return read(RAW / (name + ".public.json"))


def camera(text):
    return tuple(float(x) for x in re.fullmatch(
        r"translate\(([-\d.e]+) ([-\d.e]+)\) scale\(([-\d.e]+)\)", text).groups())


def position(text):
    return tuple(float(x) for x in re.fullmatch(r"translate\(([-\d.e]+) ([-\d.e]+)\)", text).groups())


def close(a, b):
    return all(abs(x-y) <= 1e-9 for x, y in zip(a, b))


frozen = read(OUT / "final-inputs-before.json")
roster = frozen["personalOriginalJpegRoster"]
assert len(roster) == 19
manifest = read(RAW / "manifest.json")
collection = read(RAW / "receipt.json")
changed = [dict(before=row, after=bind(ROOT / row["path"]))
           for row in frozen["rawFiles"] if bind(ROOT / row["path"]) != row]
assert not changed
assert bind(RAW / "manifest.json") == frozen["manifest"]
assert bind(RAW / "receipt.json") == frozen["browserReceipt"]
assert len(manifest["rawFiles"]) == 130
raw_frame_files = [row for row in manifest["rawFiles"] if row["path"].endswith((".jpg", ".public.json", ".dom.txt"))]
assert len(raw_frame_files) == 129

OBS = {
    "four-check-settled": ("matched-bounded", [
        "At80%, complete Input→Linear→GELU→Output row; Output selected, propertiesX794/Y70,4modules/3connections and static-check success agree with public/DOM.",
        "Three horizontal straight arrow spans enter separate ports. No unnecessary visible bend, crossing, card-body penetration or row clipping. Labels and declared shapes are readable."], [
        "Shapes are static declarations. This image does not prove the recorded connection gestures or actual model execution."]),
    "four-reopened": ("matched-bounded", [
        "At80%, same complete four-card row and three straight links. Saved header, no selection, neutral four-step help and footer已重开保存的模型草稿 matchDOM/public.",
        "No apparent new card overlap, detached arrow or layout disruption after the recorded reopen state."], [
        "Read screenshot/public artifacts only; did not operate persistence or inspect backend/network behavior."]),
    "four-generated": ("matched-bounded", [
        "Visible generation dialog模型已生成并静态核对 and source preview agree with DOM and public.source:AuthoredModel,nn.Linear16→32,nn.GELU(approximate='none'),forwardreturn.",
        "Dialog and source text are readable; continue/build-managed buttons visible. Dialog explicitly states model not executed."], [
        "Background is intentionally blurred. Do not certify the obscured canvas pixels or Python execution/independent source correctness from a modal screenshot."]),
    "four-managed": ("managed-selector-limited", [
        "Managed figure UI shows我的模型,AuthoredModel frame and input/Linear/GELU/output vertically, hierarchy5,67%,180mm papercolor,footerrev0. Matches managed DOM.",
        "Whole paper, title and legend fit. No obvious card overlap. GELU→Output has a small offset elbow matching the visible offset Output card; no claim of globally minimum bends."], [
        "public.nodes/public.edges are empty because the authoring selector does not cover this managed scene. Do not interpret that artifact as an empty product diagram or claim full geometry/public agreement.",
        "67%screen preview is not physical publication acceptance or print/font certification."]),
    "preset-palette": ("mismatch-retained", [
        "Original pixels show基础模块17 tabselected andInput/Output/Linear palette cards. The0module empty canvas/instructions/footer agree with public.",
        "DOM already has网络起点3selected and三complete-start cards. JPEG does not show that final palette tab state."], [
        "Do not certify that this named palette screenshot personally shows all3presets. Preserve original mismatch; no replacement."]),
    "residual-search": ("mismatch-retained", [
        "Original pixels show网络起点3selected, empty focused search placeholder,最小MLP and小型CNN cards with third card clipped below viewport;0module canvas.",
        "DOM already hasquery残差,1network start残差MLP and1baseAdd searchresult. JPEG precedes filtered state; public only covers graph and cannot resolve sidebar mismatch."], [
        "Do not claim search-result pixels agree or that residual-card visibility is established by this frame. Later residual-base independently shows its actual visible card."]),
    "residual-base": ("matched-bounded", [
        "At53%, all6cards and6connections visible; Add selectedX1064/Y172;query残差 andvisible residualMLP card;static success/declared shapes agree withDOM/public.",
        "MainInput→Linear16→32→ReLU→Linear32→16→Add→Output chain stays horizontal. Complete input→Add skip descends to lower corridor and rises into lower/right operand, avoiding intermediate card bodies.",
        "No visible free-space branch crossing. All arrows use same green appearance. Both Add inputs are close, labels left/right tiny, and two Linear titles truncate with ellipses."], [
        "Fit53% gives Add input spacing12world×0.5304≈6.365CSSpx; very small targets/labels are a novice usability concern, not a certified comprehension pass.",
        "Input main/skip share the first6world horizontal segment; unavoidable-looking common source stem is not proof of tensor identity. No global no-overlap claim."]),
    "residual-node-left": ("matched-bounded", [
        "Add card shifts left with propertiesX1048/Y172 while other five cards/camera remain stable; matchDOM/public.",
        "Incoming projection/skip and outgoing arrow attach to moved Add. Complete lower skip remains; no apparent new unrelated card overlap or crossing in personally viewed frame."], [
        "Only16world keyboard move. At53%, dense Add inputs remain small. This is not a mouse-drag or all-distance test."]),
    "residual-node-right": ("matched-bounded", [
        "Add card shifts right with propertiesX1080/Y172 while other five cards/camera stay stable; matchDOM/public.",
        "Incoming paths shorten/lengthen around moved Add and output link stays attached; lower skip retained without obvious new crossing or card disruption."], [
        "Only16world keyboard move; port readability remains fit53%limited."]),
    "residual-node-up": ("mismatch-retained", [
        "Original pixels retain baseline AddY172 andproperties1064/172; Add sits on baseline row.",
        "Bound public/DOM already moved Add toY156 and rerouted its3incident paths. This JPEG does not certify the up-move visual result."], [
        "Public movement/undo/redo evidence is separate. Preserve original mismatch without substituting unseen redo JPEG."]),
    "residual-node-down": ("mismatch-retained", [
        "Original pixels retain baseline AddY172 andproperties1064/172; Add sits on baseline row.",
        "Bound public/DOM already moved Add toY188 and rerouted3incident paths. This JPEG does not certify down-move visual result."], [
        "Public movement/undo/redo evidence is separate. Preserve original mismatch without claiming its visual settling."]),
    "residual-camera-left": ("matched-bounded", [
        "53%graph shifted left relative to residual-base; Addproperties1064/172andPanselected agreeDOM/public. Card/line arrangement stays coherent.",
        "Input's left edge/title is partly clipped by canvas viewport after40CSSpxpan. No visible cardbody tangle or new line crossing in remaining view."], [
        "Viewport clipping is expected from pan and is not model-node deletion. Complete Input body cannot be judged here."]),
    "residual-camera-right": ("matched-bounded", [
        "53%graph shifted right; Addproperties1064/172andPanselected agreeDOM/public. Whole row geometry moves together.",
        "Output right side is clipped at canvas/rightpanel boundary. Visible skip/main connections do not become tangled."], [
        "Only rightward pose observed in pixels. Timeout/incomplete return and recovery are retained as public-record failures, not silently repaired pixel pass."]),
    "residual-camera-up": ("matched-bounded", [
        "53%row and lower skip appear40CSSpxabovebase,Panselected andAddproperties1064/172matchDOM/public. All6cards visible.",
        "No visible internal arrangement disruption, new crossing or overlap from moving camera upward."], [
        "Screen pose snapshot only; no presented latency certification."]),
    "residual-camera-down": ("matched-bounded", [
        "53%row/skip appear40CSSpxbelowbase,Panselected andAddproperties1064/172matchDOM/public. All6cards visible.",
        "No visible new internal card overlap or free-space arrow crossing; dense tinyAddinputs remain."], [
        "Screen pose snapshot only; no presented latency certification."]),
    "residual-local100": ("matched-bounded", [
        "100%local showsReLU,projectionLinear32→16andleftportionofAdd; lower skip extends fromoffscreenleft andrises intoAddrightinput;main entersleftinput.",
        "Addinput circles/arrowheads andleft/rightlabels are independently visible12world/CSSpxapart. Mainprojection pathhas a6pxupwardstep toleftinput. Skip approaches6pxbeforeAdd thenrises andentersrightinput. Paths do not visiblycrossatmerge.",
        "Projection/ReLUlabels andshapes readable; saved/reopenedfooter andneutral help agreeDOM/public."], [
        "Input,partofhiddenLinear,AddrightedgeandOutputoutsideviewport. This localdoesnot independentlyshowthecompleteinput-toAddskiporwholemodel;usebaseforwholebypass.",
        "Twoarrowheads/porthitregionsareclose;smalladjacentleft/rightoperandsmayremainhardfornovices. Noactualnovicehit-rateorcomprehensiontest."]),
    "residual-port-tooltip": ("mismatch-retained", [
        "Originalpixels show53%residualrow,neutralhelp,saved/reopenedstate;graphmatchespublic.",
        "No tooltip rectangle/text visible. DOM hasactiverightport andtooltip残差相加·right/来自输入/声明float32·1×16. Do not certify tooltip appearance/readability from this original."], [
        "DOM existence/focus is not pixel visibility. Preserve mismatch, no recapture."]),
    "residual-final-preview": ("mismatch-retained", [
        "Originalgraph remainscoherent53%baseline6cards/6links withsaved/reopenedfooter;matchespublicgraph.",
        "JPEGstillshowquery残差,filtered1networkcardand选择modepressed. DOMsearchisempty,networkstart3and平移modepressed. Sidebarandmodeareoutofsync."], [
        "Do not claim full UI synchronized final preview. Baseline graph consistency is a bounded separate observation."]),
    "four-added": ("mismatch-retained", [
        "Previously personally viewed original JPEG and retained six-input partial report: pixelsGELUselectedproperties290/444andfooter已添加GELU激活;DOM/publicalreadyOutputat290/572and已添加输出.",
        "Inputtopcropped,Linear/GELUvisible,edgesabsent. This is precedingGELUstate,not final4-moduleadded capture."], [
        "Original failure preserved. No fullfourmodule visibility/routing acceptance from this image."]),
}
assert set(OBS) == set(roster)
views = []
for name in roster:
    status, observations, limits = OBS[name]
    dom = (RAW / (name + ".dom.txt")).read_text()
    state = public(name)
    views.append({"frame": name, "reviewStatus": status, "personallyViewedOriginal": True,
                  "tool": "tools.view_image", "viewTimestamp": None,
                  "timestampNote": "Direct original view occurred in this same audit session; no per-view timestamp was recorded. four-check-settled/four-added already viewed in preserved partial phase;17other originals viewed during final phase.",
                  "jpeg": bind(RAW / (name + ".jpg")), "public": bind(RAW / (name + ".public.json")),
                  "dom": bind(RAW / (name + ".dom.txt")), "observations": observations,
                  "limits": limits, "publicCamera": state.get("camera"),
                  "publicNodes": len(state["nodes"]), "publicEdges": len(state["edges"]),
                  "publicStatus": state["status"],
                  "domPropertyCoordinates": re.findall(r'spinbutton "模块 ([XY]) 坐标": "([-.\d]+)"', dom),
                  "domPressedModes": re.findall(r'button "(选择|平移)"[^\n]*\[pressed\]', dom),
                  "domTooltipPresent": 'tooltip "' in dom,
                  "scope": "Personal original JPEG observations; DOM/public parsed independently, not substitutes for pixels."})

base = public("residual-base")
add = next(n for n in base["nodes"] if n["kind"] == "Add")
base_position = position(add["transform"])
base_camera = camera(base["camera"])
node_rows = []
for direction, delta in {"left": (-16, 0), "right": (16, 0), "up": (0, -16), "down": (0, 16)}.items():
    name = "residual-node-" + direction
    state, undo, redo = public(name), public(name + "-undo"), public(name + "-redo")
    moved = next(n for n in state["nodes"] if n["id"] == add["id"])
    actual_delta = tuple(a-b for a, b in zip(position(moved["transform"]), base_position))
    row = {"direction": direction, "baselinePositionWorld": base_position,
           "movedPositionWorld": position(moved["transform"]), "deltaWorld": actual_delta,
           "expectedDeltaWorld": delta, "deltaVerified": close(actual_delta, delta),
           "otherNodesExact": [n for n in state["nodes"] if n["id"] != add["id"]] == [n for n in base["nodes"] if n["id"] != add["id"]],
           "cameraExact": state["camera"] == base["camera"],
           "edgeIdsExact": [e["id"] for e in state["edges"]] == [e["id"] for e in base["edges"]],
           "undoPublicExactBaseline": undo == base, "redoPublicExactMoved": redo == state,
           "ownMovedJpegStatus": OBS[name][0], "undoRedoJpegsPersonallyViewed": False,
           "bindings": [bind(RAW / (n + ".public.json")) for n in (name, name+"-undo", name+"-redo")],
           "scope": "Public state comparisons only; up/down own JPEGs are stale and undo/redo JPEGs were not personally viewed."}
    assert all(row[k] for k in ("deltaVerified", "otherNodesExact", "cameraExact", "edgeIdsExact", "undoPublicExactBaseline", "redoPublicExactMoved"))
    node_rows.append(row)

camera_rows = []
for direction, delta in {"left": (-40, 0), "right": (40, 0), "up": (0, -40), "down": (0, 40)}.items():
    name = "residual-camera-" + direction
    state = public(name)
    actual_camera = camera(state["camera"])
    actual_delta = tuple(a-b for a, b in zip(actual_camera[:2], base_camera[:2]))
    row = {"direction": direction, "deltaCssPx": actual_delta, "expectedDeltaCssPx": delta,
           "deltaVerified": close(actual_delta, delta), "scaleUnchanged": actual_camera[2] == base_camera[2],
           "nodesExactBaseline": state["nodes"] == base["nodes"], "edgesExactBaseline": state["edges"] == base["edges"],
           "binding": bind(RAW / (name + ".public.json")), "ownJpegPersonallyViewed": True}
    assert all(row[k] for k in ("deltaVerified", "scaleUnchanged", "nodesExactBaseline", "edgesExactBaseline"))
    camera_rows.append(row)
return_rows = []
for name in ("residual-camera-left-return", "residual-camera-right-return", "residual-camera-right-return-recovered", "residual-camera-right-return-settled", "residual-camera-up-return", "residual-camera-down-return"):
    state = public(name)
    current = camera(state["camera"])
    offset = tuple(a-b for a, b in zip(current[:2], base_camera[:2]))
    return_rows.append({"frame": name, "cameraOffsetFromBaselineCssPx": offset,
                        "restoredWithin1e-9": close(offset, (0, 0)),
                        "nodesExactBaseline": state["nodes"] == base["nodes"],
                        "edgesExactBaseline": state["edges"] == base["edges"],
                        "jpegPersonallyViewed": False, "public": bind(RAW / (name + ".public.json"))})
movement_binding = put("public-movement-readback.json", {
    "protocol": "archcanvas-authoring-ai-public-movement-readback/1", "createdAt": STAMP,
    "method": "Read-only frozen public JSON. All4Addkeyboard16world deltas/undo/redo states and4camera40CSSpxposes match; no gesture execution by this auditor.",
    "base": bind(RAW / "residual-base.public.json"), "nodes": node_rows, "cameraPoses": camera_rows,
    "cameraReturnStates": return_rows,
    "failuresRetained": "Right return batch timed out; observed+30CSSpx remains. Additional requested-30delivered-20so+10remains;separate-10thenrestores. These failures remain independent of the four passing baseline-relative poses.",
    "rootReportedGestureActor": "automation", "humanParticipantsAdded": 0,
    "limits": "Public-state success does not make mismatched up/down JPEGs synchronized or certify all43frames/presented gesture performance."})

per_image = put("per-image-review.json", {
    "protocol": "archcanvas-current-authoring-independent-ai-pixels/1", "createdAt": STAMP,
    "auditor": "AI subagent /root/au3_pixel_audit", "AIOnly": True, "humanParticipantsAdded": 0,
    "personallyViewedOriginalCount": 19, "newFinalPhaseOriginalCount": 17,
    "originalViewTool": "tools.view_image", "originalWholeJpegsViewed": True,
    "notWholeCollectionPixelAudit": True, "collectionFrameCount": 43,
    "statuses": {status: sum(1 for v in views if v["reviewStatus"] == status)
                 for status in ("matched-bounded", "managed-selector-limited", "mismatch-retained")},
    "views": views, "publicMovementReadback": movement_binding,
    "previousPartialEvidencePreserved": [bind(OUT / n) for n in ("two-image-inputs-before.json", "two-image-partial-review.json")],
    "additionalKnownCollectionFailuresNotPixelAudited": collection["failures"],
    "noClaimOfAllDirectionsPixelSuccess": "Public4directionspass; ownup/downAddJPEGsarebaseline. Camera4directionJPEGsviewed, withleftInput/rightOutputviewportclipping."})

# Read back every frozen byte after the final report serialization.
final_changed = [dict(before=row, after=bind(ROOT / row["path"])) for row in frozen["rawFiles"] if bind(ROOT / row["path"]) != row]
assert not final_changed
readback = put("final-readback.json", {
    "protocol": "archcanvas-authoring-independent-ai-pixel-final-readback/1", "createdAt": datetime.now(timezone.utc).isoformat(),
    "frameCount": 43, "rawFrameTriples": 129, "manifestBindingsIncludingBrowserReceipt": 130,
    "all130BindingsUnchanged": not final_changed, "changedInputs": final_changed,
    "collectionManifestUnchanged": bind(RAW / "manifest.json") == frozen["manifest"],
    "collectionReceiptUnchanged": bind(RAW / "receipt.json") == frozen["browserReceipt"],
    "frozenInputManifest": bind(OUT / "final-inputs-before.json"),
    "manifestCountExplanation": "Collection receipt.rawFileCount129 counts43JPEG/DOM/publictriples. Collection manifest.rawFiles130 also includesreceipt.json. The historical final-inputs-before key'all129RawInputBindingsMatch'checked all130listedbindings;itsoriginalbytesremainpreserved.",
    "personallyViewedRoster": roster, "personallyViewedOriginals": 19,
    "reportsReadback": [bind(OUT / "finalize_review.py"), per_image, movement_binding]})
receipt = put("receipt.json", {
    "protocol": "archcanvas-authoring-independent-ai-pixel-receipt/1", "createdAt": STAMP,
    "status": "bounded-review-complete-with-retained-mismatches", "auditor": "AI subagent /root/au3_pixel_audit",
    "AIOnly": True, "humanParticipantsAdded": 0, "productModified": False, "browserActionsByAuditor": False,
    "personallyViewedOriginalJpegs": 19, "collectionOriginalJpegs": 43,
    "matchedBoundedViews": 11, "managedSelectorLimitedViews": 1, "retainedMismatchedViews": 7,
    "mismatchFrames": [v["frame"] for v in views if v["reviewStatus"] == "mismatch-retained"],
    "conclusion": "Four-card completed/reopenedrow andgenerated-source modal are coherent;managedfigureDOM/pixelsagreewithinselectorlimits. Residualbase,left/rightAddposesandcamera4poses retain clearcompletebypasswithoutobviousfree-spacecrossings. 100%merge showsseparateAddoperands;53%inputs≈6.365CSSpxandtruncatedlabelsremainnoviceissues. Palette/search,Addverticalposes,tooltip,andfinalsidebar/modestatearenotfullysynchronizedinoriginalJPEGs;preserveallfailures.",
    "routingLimits": {"fullGlobalOptimality": False, "noOverlapCertified": False,
                      "sharedInputStemWorld": 6, "AddPortGapWorld": 12,
                      "AddPortGapCssPxAtFit": 12 * base_camera[2],
                      "mergeLocal100HasFullSkipSource": False,
                      "sameGreenDataAndSkip": True,
                      "finePortNoviceUsabilityCertified": False},
    "catalogLimits": "17kindand3presetinventoryinDOMdoesnotcertifyeachkind/presetworkflow. ActualownbasepixelsshowonevisibleResidualMLPstart;namedpalette/searchcapturesareoutofsync.",
    "publicMovementScope": "FourAddkeyboard16worldposes+undo/redoandfourcamera40CSSpxposesverifiedfrompublicJSON. Noauditorbrowsergesture. VerticalAddownJPEGsarebaseline,sofull4directionpixelacceptancefails.",
    "retainedCameraReturnFailures": "+30aftertimeout;additionalrequested-30delivered-20;+10then-10restored. ReturnJPEGsnotpersonallyviewedbythisaudit.",
    "inputIntegrity": {"rawFrameFilesUnchanged": 129, "manifestBindingsUnchangedIncludingReceipt": 130},
    "limits": {"all43PixelCertified": False, "humanNoviceTaskAcceptance": False,
               "humanPublicationAcceptance": False, "physicalPublicationCertified": False,
               "modelExecutionCertified": False, "performanceCertified": False,
               "saveBackendBehaviorIndependentlyTested": False,
               "all17KindsOr3PresetsEndToEndCertified": False},
    "artifacts": [bind(OUT / "final-inputs-before.json"), per_image, movement_binding, readback]})
print(json.dumps({"receipt": receipt, "readback": readback, "perImage": per_image,
                  "movement": movement_binding, "personallyViewed": 19,
                  "mismatchFrames": [v["frame"] for v in views if v["reviewStatus"] == "mismatch-retained"]}, indent=2))
