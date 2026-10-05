#!/usr/bin/env python3
"""Independent UI evidence audit; writes only ui-independent-audit.json/.md.

Every parsed input and every frozen core module is read once before validation.
Fresh Node rendering uses copies of those same bytes in an ephemeral directory.
No browser interaction, product edits, service calls or dependency installation.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import struct
import subprocess
import tempfile
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[2]
NS = "{http://www.w3.org/2000/svg}"
TARGET = "call:instance:model.MLP.network.0"
ROOT = "call:instance:model.MLP"
NETWORK = "call:instance:model.MLP.network"
LABELS = ["mlp-before", "mlp-expanded", "mlp-selected", "mlp-alias", "mlp-pinned",
    "mlp-pin-undo", "mlp-pin-redo", "mlp-collapsed", "mlp-reexpanded", "mlp-saved",
    "mlp-reopened", "cnn-switched"]


def equal(actual, expected, message):
    if actual != expected:
        raise AssertionError(message)


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def sha(body):
    return hashlib.sha256(body).hexdigest()


def bind(path, body):
    return {"path": str(path.relative_to(PROJECT)), "bytes": len(body), "sha256": sha(body)}


def normalized_svg(markup):
    result, a = re.subn(r'\bdata-revision="[0-9]+"', 'data-revision="0"', markup)
    result, b = re.subn(r'"revision":[0-9]+', '"revision":0', result)
    equal((a, b), (1, 1), "normalize exactly one SVG attribute and one metadata revision scalar")
    return result


def svg_info(markup):
    root = ET.fromstring(markup)
    metadata = json.loads(root.find(NS + "metadata").text)
    groups = {item.attrib["data-node-id"]: item for item in root.iter() if "data-canonical-id" in item.attrib}
    bodies = {id: {key: float(body.attrib[key]) for key in ["x", "y", "width", "height"]}
        for id, group in groups.items()
        for body in [next(item for item in group if item.tag == NS + "rect" and "stroke-width" in item.attrib)]}
    return root, metadata, groups, bodies


def independent_facts(architecture):
    calls = {}
    for node in architecture["nodes"]:
        if node.get("instanceId") and node.get("callId"):
            calls.setdefault(node["instanceId"], set()).add(node["callId"])
    facts = []
    for node in architecture["nodes"]:
        fact = {"id": node["id"], "sourceLabel": node["label"], "kind": node["kind"],
            "category": node["category"], "evidence": node["evidence"]}
        if node.get("instanceId"):
            fact.update(instanceId=node["instanceId"], callCount=len(calls.get(node["instanceId"], set())))
        if node.get("callId"):
            fact["callId"] = node["callId"]
        for key in ["repeat", "outputPath"]:
            if key in node:
                fact[key] = node[key]
        if node.get("source"):
            fact["source"] = {key: node["source"][key] for key in ["path", "line", "endLine", "expression"]}
        facts.append(fact)
    return facts


def jpeg_dimensions(body):
    equal(body[:2], b"\xff\xd8", "original screenshot is JPEG")
    i = 2
    while i < len(body):
        require(body[i] == 0xFF, "JPEG marker boundary")
        while body[i] == 0xFF:
            i += 1
        marker = body[i]
        i += 1
        if marker in [0xD8, 0xD9, 0x01] or 0xD0 <= marker <= 0xD7:
            continue
        size = struct.unpack(">H", body[i:i + 2])[0]
        if marker in [0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF]:
            height, width = struct.unpack(">HH", body[i + 3:i + 7])
            return width, height
        i += size
    raise AssertionError("JPEG has no dimensions")


# Path enumeration does not parse content. Capture once, then hash and parse
# only these same byte objects. Include imports and actual isolated-store copy.
paths = {Path(__file__), HERE / "ui-journal.json", HERE / "ui-journal-final.json", HERE / "build-context.json",
    HERE / "mlp-reopened.jpg", PROJECT / "studio/src/App.tsx", PROJECT / "studio/src/HierarchyTree.tsx",
    PROJECT / "studio/dist/index.html"}
paths.update(HERE.glob("mlp-store-*.json"))
paths.update((PROJECT / ".archcanvas/m4-hierarchy-optimization/documents").glob("*.json"))
paths.update((PROJECT / "studio/dist/assets").glob("*"))
core_paths = sorted((PROJECT / "studio/src/core").glob("*.ts"))
paths.update(core_paths)
paths.update((PROJECT / "fixtures/mlp").glob("*.py"))
frozen = {path: path.read_bytes() for path in sorted(paths)}
before = [bind(path, body) for path, body in frozen.items()]
read_json = lambda path: json.loads(frozen[path])

journal = read_json(HERE / "ui-journal-final.json")
earlier = read_json(HERE / "ui-journal.json")
equal([item["label"] for item in journal], LABELS, "explicit journal labels and order")
equal(earlier, journal[:len(earlier)], "earlier raw journal remains exact prefix, not corrected")
equal(len(earlier), 11, "earlier journal prefix has eleven captures")
snapshots = {item["label"]: item for item in journal}
build = read_json(HERE / "build-context.json")
for binding in build["bindings"]:
    path = PROJECT / binding["path"]
    equal(bind(path, frozen[path]), binding, "actual production source/build binding " + binding["path"])
js_bindings = [item for item in build["bindings"] if item["path"].endswith(".js")]
equal(len(js_bindings), 1, "single bound production JS")
equal(js_bindings[0]["path"], "studio/dist/assets/index-oI5sT67U.js", "new oI5 build")
expected_script = "/assets/" + Path(js_bindings[0]["path"]).name
require(expected_script in frozen[PROJECT / "studio/dist/index.html"].decode(), "production HTML references same JS")
for item in journal:
    equal(item["scripts"], [expected_script], "observed production script reference " + item["label"])
    equal(item["url"], "http://127.0.0.1:8889/", "isolated observed URL")
    equal(item["viewport"], {"dpr": 1, "height": 720, "width": 1280}, "recorded viewport")

envelope_paths = sorted(HERE.glob("mlp-store-*.json"))
equal(len(envelope_paths), 1, "one sealed MLP store envelope")
envelope = read_json(envelope_paths[0])
document = envelope["document"]
store_path = PROJECT / ".archcanvas/m4-hierarchy-optimization/documents" / (document["id"] + ".json")
equal(frozen[store_path], frozen[envelope_paths[0]], "sealed envelope equals actual isolated-store bytes")
equal(envelope["revision"], 1, "storage CAS revision")
equal(document["revision"], 7, "visual document revision")
equal(document["pinnedObjects"], [TARGET], "only actual Linear1 is pinned")
equal(document["displayAliases"], {TARGET: "Projection α"}, "exact saved alias")
equal(document["expandedIds"], [ROOT, NETWORK], "exact saved expansions")
require("history" not in document and "selection" not in document and "camera" not in document,
    "saved CanvasDocument contains no history/selection/camera persistence")
architecture = document["architecture"]
for source in architecture["sources"]:
    equal(sha(source["content"].encode()), source["digest"], "included source content digest")
    source_path = PROJECT / "fixtures/mlp" / source["path"]
    equal(sha(frozen[source_path]), source["digest"], "formal MLP fixture byte digest")

parsed = {label: svg_info(item["svg"]) for label, item in snapshots.items()}
metadata = {label: values[1] for label, values in parsed.items()}
facts = independent_facts(architecture)
expected_revisions = [0, 1, 1, 2, 3, 4, 5, 6, 7, 7, 7]
for label, revision in zip(LABELS[:-1], expected_revisions):
    root, meta, groups, bodies = parsed[label]
    equal(meta["revision"], revision, "expected visual revision " + label)
    equal(root.attrib["data-revision"], str(revision), "root and metadata revision match")
    equal(meta["documentId"], document["id"], "same MLP document")
    equal(root.attrib["data-document-id"], document["id"], "root MLP identity")
    equal(meta["sourceDigest"], architecture["sourceDigest"], "unchanged sourceDigest")
    equal(meta["irDigest"], architecture["irDigest"], "unchanged irDigest")
    equal(meta["sourceFacts"], facts, "independent complete source-fact projection")
    equal(meta["sourceFactScope"], "whole-source-architecture", "whole source scope")
    equal(meta["renderer"], "archcanvas-svg/1.0", "actual SVG renderer")
    equal(set(groups), {row["id"] for row in snapshots[label]["tree"]}, "drawn frontier equals observed tree")
    equal(set(groups), {node["sceneNodeId"] for node in meta["renderedNodes"]}, "drawn frontier equals metadata")

row = lambda label, id: next(item for item in snapshots[label]["tree"] if item["id"] == id)
selected = lambda label: [item["id"] for item in snapshots[label]["tree"] if item["selected"] == "true"]
equal(selected("mlp-before"), [], "initial no selection")
equal(selected("mlp-selected"), [TARGET], "selection reached requested Linear1")
equal(row("mlp-selected", TARGET)["label"], "Linear 1", "source label before alias")
for label in ["mlp-alias", "mlp-pinned", "mlp-pin-undo", "mlp-pin-redo", "mlp-reexpanded", "mlp-saved", "mlp-reopened"]:
    equal(row(label, TARGET)["label"], "Projection α", "alias remains in hierarchy")
    equal(parsed[label][2][TARGET].attrib["aria-label"], "Projection α", "alias remains in canvas SVG")
    equal(row(label, TARGET)["toggle"], "展开 Linear 1", "toggle retains source label contract")

full_order = [ROOT, "input:model.MLP:features", NETWORK,
    *["call:instance:model.MLP.network." + str(i) for i in range(4)], "output:model.MLP:0"]
collapsed_order = [ROOT, "input:model.MLP:features", NETWORK, "output:model.MLP:0"]
for label in LABELS[:-1]:
    expected = collapsed_order if label in ["mlp-before", "mlp-collapsed"] else full_order
    equal([item["id"] for item in snapshots[label]["tree"]], expected, "authored MLP tree order " + label)
    equal([int(item["depth"]) for item in snapshots[label]["tree"]],
        [0, 1, 1, 1] if expected == collapsed_order else [0, 1, 1, 2, 2, 2, 2, 1], "MLP hierarchy depths")
    equal(row(label, NETWORK)["label"], "network×4", "repeat badge retained")
for label in LABELS[6:-1]:
    equal(snapshots[label]["captureVersion"], 2, "scope-correct V2 observation")
    equal(json.loads(snapshots[label]["pinnedIds"]), [TARGET], "V2 document pin membership")
    pins = [item["id"] for item in snapshots[label]["tree"] if item["pin"]]
    equal(pins, [] if label == "mlp-collapsed" else [TARGET], "direct-row V2 pin visibility")
    equal(json.loads(snapshots[label]["expandedIds"]), [ROOT] if label == "mlp-collapsed" else [ROOT, NETWORK], "V2 expansion membership")
equal([item["id"] for item in snapshots["mlp-pinned"]["tree"] if item["pin"]],
    [ROOT, NETWORK, TARGET], "retain exactly the known V1 recursive-pin false positives")
equal([item["id"] for item in snapshots["mlp-pin-undo"]["tree"] if item["pin"]], [], "undo removes observed pin")

pairs = [("mlp-expanded", "mlp-selected", "selection leaves exact SVG bytes"),
    ("mlp-alias", "mlp-pin-undo", "pin undo restores full alias SVG"),
    ("mlp-pinned", "mlp-pin-redo", "pin redo restores full pinned-stage SVG"),
    ("mlp-before", "mlp-collapsed", "collapse restores full original frontier SVG"),
    ("mlp-pin-redo", "mlp-reexpanded", "re-expansion restores full alias SVG and layout"),
    ("mlp-reexpanded", "mlp-saved", "save leaves exact SVG bytes"),
    ("mlp-saved", "mlp-reopened", "reopen restores exact full SVG bytes")]
restorations = []
for left, right, description in pairs:
    equal(normalized_svg(snapshots[left]["svg"]), normalized_svg(snapshots[right]["svg"]), description)
    restorations.append({"left": left, "right": right, "description": description,
        "fullSvgExactExceptTwoRevisionScalars": True,
        "rawSvgByteExact": snapshots[left]["svg"] == snapshots[right]["svg"],
        "leftRevision": metadata[left]["revision"], "rightRevision": metadata[right]["revision"]})
equal(snapshots["mlp-saved"]["saveState"], "已保存", "actual saved header")
equal(snapshots["mlp-reopened"]["saveState"], "已保存", "actual reopened header")
require("画布已保存" in snapshots["mlp-saved"]["footer"], "actual saved footer")
require("已重开保存的画布" in snapshots["mlp-reopened"]["footer"], "actual reopened footer")
equal(selected("mlp-saved"), [TARGET], "saved selection observed")
equal(selected("mlp-reopened"), [], "reload clears selection")
require(snapshots["mlp-saved"]["paper"] != snapshots["mlp-reopened"]["paper"], "reload changes camera")
equal(parsed["mlp-saved"][3], parsed["mlp-reopened"][3], "scene geometry does not change with camera")
cnn = snapshots["cnn-switched"]
equal(selected("cnn-switched"), [], "model switch clears selection")
equal(json.loads(cnn["pinnedIds"]), [], "model switch clears old pin membership")
equal(json.loads(cnn["expandedIds"]), ["call:instance:model.ResidualCNN"], "CNN expansion membership")
require(not any(item["id"] in set(full_order) or "model.MLP" in item["id"] for item in cnn["tree"]), "CNN tree contains no stale MLP IDs")
require(not any(item["label"] == "Projection α" for item in cnn["tree"]), "CNN tree contains no stale visual alias")
equal(metadata["cnn-switched"]["revision"], 0, "CNN new visual revision")
require(metadata["cnn-switched"]["documentId"] != document["id"], "CNN has new document identity")

# Fresh formal-core consistency is supplemental, not a second independently
# correct renderer. Copy all actual core bytes before import to close the
# parse-versus-import mutation window; stdin contains the frozen store object.
node_source = r'''import fs from 'node:fs';
import {pathToFileURL} from 'node:url';
const {createDocument,createHistory,reduceHistory,buildScene,renderSvg,validateDocument}=await import(pathToFileURL(process.argv[1]).href);
const saved=validateDocument(JSON.parse(fs.readFileSync(0,'utf8')));
let history=createHistory(createDocument(saved.architecture));const result={};
const capture=label=>{const document=history.document;const scene=buildScene(document);result[label]={document,svg:renderSvg(scene,{interactive:true})};};
const apply=operations=>{history=reduceHistory(history,{type:'apply',operations});};
capture('mlp-before');apply([{type:'expand',id:'call:instance:model.MLP.network',expanded:true}]);capture('mlp-expanded');capture('mlp-selected');
apply([{type:'alias',id:'call:instance:model.MLP.network.0',label:'Projection α'}]);capture('mlp-alias');
apply([{type:'pin',ids:['call:instance:model.MLP.network.0'],pinned:true}]);capture('mlp-pinned');
history=reduceHistory(history,{type:'undo'});capture('mlp-pin-undo');history=reduceHistory(history,{type:'redo'});capture('mlp-pin-redo');
apply([{type:'expand',id:'call:instance:model.MLP.network',expanded:false}]);capture('mlp-collapsed');
apply([{type:'expand',id:'call:instance:model.MLP.network',expanded:true}]);capture('mlp-reexpanded');capture('mlp-saved');
history=createHistory(saved);capture('mlp-reopened');
process.stdout.write(JSON.stringify({states:result,reopenedHistory:{past:history.past.length,future:history.future.length}}));'''
with tempfile.TemporaryDirectory(prefix="archcanvas-ui-audit-") as temporary:
    temporary_path = Path(temporary)
    (temporary_path / "package.json").write_text('{"type":"module"}')
    for path in core_paths:
        (temporary_path / path.name).write_bytes(frozen[path])
    rendered = subprocess.run(["node", "--experimental-strip-types", "--input-type=module", "-e", node_source,
        str(temporary_path / "index.ts")], input=json.dumps(document), text=True, capture_output=True, check=True)
fresh = json.loads(rendered.stdout)
for label, state in fresh["states"].items():
    equal(ET.canonicalize(state["svg"]), ET.canonicalize(snapshots[label]["svg"]), "fresh frozen formal core whole SVG XML " + label)
equal(fresh["states"]["mlp-saved"]["document"], document, "fresh visual-operation replay reconstructs full stored document")
equal(fresh["reopenedHistory"], {"past": 0, "future": 0}, "formal createHistory on reopen starts empty")
equal(jpeg_dimensions(frozen[HERE / "mlp-reopened.jpg"]), (1280, 720), "original screenshot dimensions")
app = frozen[PROJECT / "studio/src/App.tsx"].decode()
require("setHistory(createHistory(document))" in app and "setSelection({ kind: 'node', ids: [] })" in app,
    "current source explicitly resets history and selection on open")

after = [bind(path, path.read_bytes()) for path in frozen]
equal(after, before, "all scoped inputs stable after calculations")
result = {"schema": "archcanvas-hierarchy-ui-independent-audit/1", "status": "passed-with-retained-capture-scope-limit",
    "inputMethod": "Each original file read once into frozen bytes before parsing; all parsing and core copies use those same bytes; on-disk hashes checked again before and after writing only this audit.",
    "inputsBefore": before, "inputsAfter": after, "inputFiles": len(before), "inputsStable": True,
    "observedJournalSnapshots": len(journal), "earlierJournalUnmodifiedExactPrefix": True,
    "productionBuild": build, "productionJs": js_bindings[0],
    "buildScope": "DOM script URL references equal bound production HTML/JS; this audit did not refetch or hash original browser HTTP responses.",
    "sourceAndIr": {"allElevenMlpSnapshotsUnchanged": True, "sourceDigest": architecture["sourceDigest"],
        "irDigest": architecture["irDigest"], "wholeEightSourceFactsIndependentlyMapped": True,
        "includedSourceMatchesFormalFixture": True, "modelExecuted": False},
    "checks": {"expand": True, "selectRequestedLinear1": True, "aliasTreeAndCanvas": True, "pin": True,
        "undoPin": True, "redoPin": True, "collapse": True, "reexpandAliasPinLayout": True,
        "save": True, "reopen": True, "cnnModelSwitchClearsOldTree": True},
    "retainedPinCaptureError": {"labels": ["mlp-pinned"], "captureVersion": 1,
        "originalQuery": "treeitem.querySelector('.tree-row > svg')",
        "problem": "querySelector searches descendant rows recursively; a child pin icon falsely marks its ancestor treeitems as pinned.",
        "rawReportedPinnedIds": [ROOT, NETWORK, TARGET], "ancestorFalsePositiveIds": [ROOT, NETWORK],
        "rawUnmodified": True, "v2Method": "Scope the query to treeitem.firstElementChild (the direct .tree-row).",
        "v2Labels": LABELS[6:], "actualPinnedIdsInV2AndStoredDocument": [TARGET],
        "cnnPinnedIds": [], "notTreatedAsThreeActualPinnedObjects": True,
        "svgPinLimitation": "Pin state is not encoded as a publication SVG glyph; normalized pin-stage SVG equals alias-stage SVG. V2 direct-row observations and the stored document establish actual pin membership."},
    "fullSvgRestoration": restorations,
    "snapshots": [{"label": label, "revision": metadata[label]["revision"], "treeRows": len(snapshots[label]["tree"]),
        "svgBytesUtf8": len(snapshots[label]["svg"].encode()), "svgSha256": sha(snapshots[label]["svg"].encode()),
        "visibleNodes": len(parsed[label][2]), "visibleBindings": len(metadata[label]["renderedBindings"])} for label in LABELS],
    "persistence": {"documentId": document["id"], "visualRevision": 7, "storageRevision": 1,
        "sealedEnvelopeEqualsActualIsolatedStoreBytes": True, "savedAndReopenedFullSvgByteExact": True,
        "savedSvgSha256": sha(snapshots["mlp-saved"]["svg"].encode()),
        "savedSelection": selected("mlp-saved"), "reopenedSelection": selected("mlp-reopened"),
        "savedCameraStyle": snapshots["mlp-saved"]["paper"], "reopenedCameraStyle": snapshots["mlp-reopened"]["paper"],
        "cameraChanged": True, "sceneBodyGeometryExact": True, "historyResetByCurrentSourceAndFreshCore": True,
        "historyResetNativeJournalButtonStateRecorded": False, "cameraPersistenceCertified": False,
        "undoHistoryPersistenceCertified": False},
    "freshFrozenFormalCore": {"wholeSvgXmlAllElevenSnapshotsExact": True,
        "fullStoredDocumentReconstructedByOperationReplay": True, "sourceCopyMethod": "All frozen actual studio/src/core/*.ts copied into temporary directory, no live imports; directory removed.",
        "xmlNormalization": "ET.canonicalize normalizes browser empty-element serialization and attribute ordering; revision is not stripped for fresh replay checks. All complete XML content retained.",
        "replaySource": node_source, "executionExitCode": rendered.returncode,
        "independentRendererCorrectnessCertified": False},
    "actualScreenshotReview": {"file": bind(HERE / "mlp-reopened.jpg", frozen[HERE / "mlp-reopened.jpg"]),
        "tool": "tools.view_image", "detail": "high", "actuallyViewedByReviewer": True, "encodedWidth": 1280, "encodedHeight": 720,
        "observations": ["Header displays 已保存 and MLP.", "Hierarchy displays Projection α with only its direct-row pin icon; root and network have no pin icon.",
            "Expanded network contains four child labels in authored order.", "No highlighted selection; object inspector displays 从一个对象开始.",
            "Zoom displays 46%; toolbar undo and redo icons appear disabled.", "Footer displays 已重开保存的画布 and rev 7."],
        "acquisitionAuthenticityOrExactCaptureTimestampCertified": False,
        "pixelGeometryOrPublicationReadabilityCertified": False},
    "acceptance": {"agentAudit": True, "humanParticipants": 0, "humanPublicationApproval": False,
        "nativePerformanceCertified": False, "sustainedPresentedFpsCertified": False, "continuousInputToPaintCertified": False,
        "pinProtectionUnderMovementCertified": False, "historyPersistenceCertified": False},
    "limits": ["Journal contains DOM outcome snapshots, not independently replayed or authenticated native input event history.",
        "Original recursive V1 pin observations retained; only V2 direct-row observations and store count actual membership.",
        "Saved/reopened equality covers complete document SVG content; camera and selection reset and history persistence is not certified.",
        "Screenshot is actual viewed original JPEG bytes; image appearance does not authenticate original acquisition timing, physical print readability or exact CSS geometry.",
        "Fresh formal-core replay is consistency evidence using the same engine, not a separately correct renderer, fresh source analysis or model execution.",
        "Build bindings certify current on-disk bytes and observed asset URL references, not original HTTP response-body capture.",
        "No service lifecycle, native cancel, fixed fonts/hardware, sustained performance, human publication reviews or researcher tasks are accepted by this audit."]}

json_path = HERE / "ui-independent-audit.json"
md_path = HERE / "ui-independent-audit.md"
json_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
md_path.write_text(f'''# 层级树优化 UI 独立审计

12 个实际 DOM journal 观察已核对，{len(before)} 个输入从同一冻结 bytes 解析与哈希，审计前后 bytes / SHA256 均一致。早期 11 项 journal 仍是 final journal 的完全相同前缀。本审计只写自己的脚本和两个结果文件。

实际观察绑定新 `index-oI5sT67U.js`（SHA256 `{js_bindings[0]["sha256"]}`）；所有 journal 的 script URL 与当前 bound HTML/JS 一致。原始浏览器 HTTP 响应正文没有由本审计重新捕获或认证。

MLP 的展开、指定 Linear1 选择、`Projection α` 显示别名、pin、undo、redo、收起、再展开、保存与重开均通过。11 个 MLP 快照 source/IR digest 及完整 8 条 sourceFacts 一致；独立 Python 映射 metadata 与保存 architecture 相同，included source 与正式 fixture 字节相同。CNN 切换清除旧 MLP tree ID、alias、selection 与 pin。

保留采集限制：早期 `treeitem.querySelector('.tree-row > svg')` 递归扫描 descendant rows，把 Linear1 的 pin 误记到 MLP root 和 network。`mlp-pinned` 原始三个 true 原样保留；V2 改为 `firstElementChild` 直接行范围，真实 pinned IDs 及 store 均只有 Linear1。SVG 本身不显示 pin 状态，不能据 normalized pin-stage SVG 推断 pin 数量。

完整 SVG 比对只排除实际 SVG attribute / metadata 两个 revision 标量：undo 恢复 alias-stage、redo 恢复 pin-stage、collapse 恢复原始 frontier、re-expand 恢复布局及 alias 均精确。save/reopen 的完整 SVG 甚至原字节相同，SHA256 `{sha(snapshots["mlp-saved"]["svg"].encode())}`。封存 envelope 与当前隔离 store 字节相同，visual revision 7、storage revision 1。

Fresh formal core 从冻结模块 bytes 的临时副本导入，完整 visual-operation replay 重建保存 document 的所有字段；11 个完整 SVG 的 XML 内容与对应 journal 精确。只规范化 browser empty-element serialization 与 XML attribute 顺序，fresh replay 不去掉 revision。此项是相同引擎的一致性复核，不是第二个独立渲染算法正确性或新源码分析。

`mlp-reopened.jpg` 原文件已通过 `view_image(high)` 实际查看，编码 1280×720，与 journal viewport 相同。画面显示已保存、Projection α、该行 pin、无选择、46% 相机、重开 footer / rev7；undo / redo 图标看起来 disabled。图片不用来认证 CSS 几何、采集时间或物理出版可读性。

重开清空 selection 并改变相机，场景 body 几何不变。当前 App 明确 createHistory(document)，fresh core 检查返回空 past/future；journal 没有记录原生按钮 disabled 属性。历史与相机持久化均未认证。

本审计是 agent 验证，human participants 为 0，不替代人工 publication review、研究者任务、native cancel、固定字体/硬件或持续呈现 FPS / input-to-paint 性能验收。

复现：`python3 docs/evidence/m4-hierarchy-optimization/audit_ui.py`。需要已有 Node 24 和正式 core 文件，不安装依赖，不操作服务或浏览器。
''')
post = [bind(path, path.read_bytes()) for path in frozen]
equal(post, before, "all scoped original inputs stable after audit outputs written")
print(json.dumps({"status": result["status"], "inputFiles": len(before), "inputsStableAfterWrite": True,
    "json": bind(json_path, json_path.read_bytes()), "markdown": bind(md_path, md_path.read_bytes())}, ensure_ascii=False, indent=2))
