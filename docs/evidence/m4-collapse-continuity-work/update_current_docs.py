"""Record the bounded M4 result without rewriting historical evidence."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import os

ROOT = Path(__file__).resolve().parents[3]
WORK = Path(__file__).resolve().parent

def binding(path):
    path = Path(path)
    data = (ROOT / path).read_bytes()
    return {"path": path.as_posix(), "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}

def write_json(path, data):
    (ROOT / path).write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")

def link(current, label, target):
    return f"[{label}]({os.path.relpath(ROOT / target, (ROOT / current).parent)})"

current_docs = [
    'README.md', 'docs/m4-completion.md', 'docs/m4-exit-audit.md',
    'docs/m4-ai-usability-audit.md', 'docs/m4-human-review-handoff.md',
    'docs/m4-performance.md', 'docs/m4-authoring.md', 'docs/acceptance.md',
    'docs/capability-matrix.md', 'docs/evidence/README.md',
    'skills/archcanvas/references/formal-alpha.md',
    'skills/archcanvas/references/runtime-compatibility.md',
]
archive = json.loads((WORK / 'before-current-doc-update-attempt-1/manifest.json').read_text())
for rec in archive['records']:
    assert binding(rec['source'])['sha256'] == rec['sha256'], rec['source']
    assert binding(rec['copy'])['sha256'] == rec['sha256'], rec['copy']

# These two working narratives were not in the earlier fourteen-file archive.
extra = WORK / 'before-final-doc-repair-attempt-1'
extra.mkdir(exist_ok=False)
records = []
for path in ['docs/m4-collapse-continuity.md', 'docs/evidence/m4-collapse-continuity-work/README.md']:
    dest = extra / 'files' / path
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes((ROOT / path).read_bytes())
    rec = binding(path)
    rec['copy'] = dest.relative_to(ROOT).as_posix()
    rec['exact'] = binding(rec['copy'])['sha256'] == rec['sha256']
    records.append(rec)
write_json(extra.relative_to(ROOT) / 'manifest.json', {
    'protocol': 'm4-working-narratives-before-final-doc-update/1',
    'createdAt': datetime.now(timezone.utc).isoformat(), 'records': records,
})

cn = """当前（2026-10-06）为 `index-BKbgeBjI.js` / `index-B6WbMowt.css`。{stage}修复直接折叠祖先后查询错误布局快照的问题：实际 CNN 的 Repeat→pool 完整轮廓间距从1607恢复到31世界单位，保留隐藏展开记忆与局部坐标。最终独立专项13/13、Studio247/247、strict TypeScript/Vite退出0，计数单列；本轮未执行模型或安装依赖。

当前 build 的实际浏览器链已核对展开/折叠、pool右/左/上/下各40、undo/redo、保存重开及同revision导出。独立核对107输入、18 DOM观测、142对边端点；AI像素审查6张画布图。上移制造的重叠与阻塞提示保留，下移后恢复；不认证全局最少交叉或弯折。另完成从空白 Input→Linear(16→8)→GELU→Output 四节点三边、生成新源码并重开 managed 图，以及预制 CNN 原生拖入8节点7边、Identity重试拖入与撤销；独立搭建工件审查5/5、42输入精确，左库实际17模块（含SiLU）＋3透明起点。端口命中困难、草稿四弯回绕、Output副标题截断/内部ID仍待改善。

{role}冻结的 CG7A-7XR 九例单色/SVG/PDF证据属于其版本；宽度4的残差dash间隙被圆头填满、Transformer交叉/重叠和深层长页仍有问题。三个AI审查角色提供自动化操作/工件/像素证据，真人记录0。固定窗口性能工具只有旧上下文的三个简单控制页记录，无当前 Studio A/B或呈现帧认证。M4保持partial、M5未开始，研究包仍未针对当前build准备/核验。{status}记录当前边界；{archive}保留14份更新前原件。下方旧“当前/本轮/最终”仅指其明示旧版本与冻结时点。

"""
en = """Current configured checkout (2026-10-06): BKbgeBjI/B6WbMowt. The visible-frontier layout-cache repair is described in the checkout's docs/m4-collapse-continuity.md. Final independent target tests pass13/13, Studio tests247/247, strict TypeScript/Vite exit0; these counts are separate. The actual CNN Repeat-to-pool outline gap changes from1607 to31 world units while retaining latent child expansion/layout. Native final-build records cover expand/collapse, pool right/left/up/down40, undo/redo, save/reopen and same-revision SVG export. Independent readback checks107 inputs,18 DOM observations and142 edge endpoint pairs; AI review covers six canvas images. The deliberate up-move overlap remains diagnosed and clears after moving down. This is bounded continuity evidence, not global route aesthetics or a new full39 matrix.

The final build also reopens/regenerates a from-blank four-node/three-edge Input→Linear(16→8)→GELU→Output draft, opens a fresh managed figure and saves it. A native CNN starting-graph drag inserts8 nodes/7 edges and statically generates source; an Identity retry inserts one node and undo removes it. Independent artifact audit passes5/5 with42 exact inputs. The actual left library has17 modules, including SiLU, and three transparent starting graphs. The initial port-label clicks and first Identity drag fail and are retained. Draft routes repeatedly use four bends; managed Output subtitle clipping/internal-ID exposure remain product issues. This does not certify every module, actual execution, training or novice human usability.

CG7A-7XR monochrome-role evidence remains frozen separately in docs/m4-monochrome-role.md and its seal. Residual width4 dash gaps fill under round caps; Transformer crossings/overlaps and tall deep figures remain open. Three AI reviewer roles do not count as humans: human records0, M4partial, M5notstarted. The fixed-window performance helper has three simple-control records from an older build context, no current Studio A/B or presented-FPS certification. Current research preparation is pending. Consult docs/evidence/m4-human-review-handoff-status.json for current receipt bindings and limits. Fourteen prior documents were archived before this update; following historical paragraphs retain only their original build scope.

"""
for path in current_docs:
    text = (ROOT / path).read_text()
    if path.startswith('skills/'):
        marker = 'The configured formal checkout now uses Dzp9we5t/B6WbMowt'
        assert marker in text
        text = text.replace(marker, 'Historical Dzp scope: The configured formal checkout used Dzp9we5t/B6WbMowt', 1)
        insertion = en
        pos = text.index('Historical Dzp scope:')
        text = text[:pos] + insertion + text[pos:]
    else:
        lines = text.splitlines(keepends=True)
        assert lines[2].startswith('当前'), path
        lines[2] = '历史版本说明：' + lines[2]
        insertion = cn.format(
            stage=link(path, '空间连续性与当前验收', 'docs/m4-collapse-continuity.md'),
            role=link(path, '单色角色阶段', 'docs/m4-monochrome-role.md'),
            status=link(path, '机器可读状态', 'docs/evidence/m4-human-review-handoff-status.json'),
            archive=link(path, '更新前归档', 'docs/evidence/m4-collapse-continuity-work/before-current-doc-update-attempt-1/manifest.json'),
        )
        text = ''.join(lines[:2]) + insertion + ''.join(lines[2:])
    (ROOT / path).write_text(text)

completion = ROOT / 'docs/m4-completion.md'
text = completion.read_text()
start = text.index('## 当前 M4 状态')
end = text.index('## 历史 DPwoy 完整矩阵', start)
table = """## 当前 M4 状态

| 项目 | 状态 | 证据与边界 |
|---|---|---|
| M4-01–04 源码/holdout/shared/repeat/opaque | 静态子集有界 | 前端源码未由本次布局修复改变；历史证据只按原版本读取，不推广任意Python。 |
| M4-05 真浏览器性能 | 当前build未测Studio A/B，呈现门未认证 | 三个简单控制页记录只支持固定窗口记账；无三次重复矩阵、固定硬件/解析字体或presented FPS。 |
| M4-06 空间连续性与出版 | 当前CNN直接祖先折叠/四向/history/save/export有界通过 | 轮廓gap1607→31、18 DOM、6画布图与独立107输入；142是边端点对数。单色角色九例属于CG，宽线dash和TF排布仍有问题；物理出版/全局美学未认证。 |
| M4-07 研究者任务 | 0真人，当前包未prepare/verify | AI自动化操作和三个审查角色不计真实参与者；旧席位不可用于当前build。 |
| 新手搭建/模块库 | 四链、预制CNN、Identity重试有界核对 | 17实际模块＋3起点；独立5/5、42输入。点端口困难、草稿回绕与Output副标题保留；无逐模块/训练/真人认证。 |
| 产品回归 | 独立专项13/13、Studio247/247、strict/build0 | [当前收据与独立核对](m4-collapse-continuity.md)；计数不相加，Python全套/独立完整发行未重跑。 |

M4 partial，M5未开始。旧au3/Dzp/CG证据、失败、分母与封印均保留原范围；当前有限验证不继承旧完整矩阵或性能结论。

"""
completion.write_text(text[:start] + table + text[end:])

handoff = ROOT / 'docs/m4-human-review-handoff.md'
text = handoff.read_text().replace('# M4 当前交接：精确 memory 家族与开放体验门', '# M4 当前交接：空间连续性与搭建体验')
start = text.index('| 待完成门')
end = text.index('## 历史ChS交接补充', start)
handoff.write_text(text[:start] + """| 待完成门 | 当前状态 | 下一步 |
|---|---|---|
| 布局连续性 | CNN祖先折叠及四向/history/save/export有界通过 | 将手写独立坐标合同保留为回归；无可信旧快照时不静默重排。 |
| 新手操作与排布 | 四链/CNN/Identity有界通过，仍有明确失败 | 改善端口点击命中、侧端口重复回绕、Output截断与内部ID。 |
| 单色出版 | CG九例冻结，宽度4角色间隙失败 | 改善dash/round-cap可读性、Transformer交叉与深层长页；物理尺寸仍需实际审看。 |
| 性能/取消 | 当前Studio A/B未测，呈现门未认证 | 完成固定窗口三次匹配控制/Studio矩阵，保留所有缺失分母；实际帧/held-pointer取消另证。 |
| 真实研究任务 | 真人0，当前包未prepare/verify | 未来新包另准备/核验；AI不计researcher，无需以此暂停已授权开发。 |
| 回归/发行 | 专项13/13、Studio247/247、strict/build0 | 当前有限源码/build精确绑定；旧发行9项与Python9保留版本范围。 |

""" + text[end:])

# Make older section titles visibly historical, without altering their evidence.
for path, replacements in {
    'docs/m4-exit-audit.md': {'## 当前硬出口判断':'## 历史硬出口判断', '## 当前 ce7 原生输入诊断':'## 历史 ce7 原生输入诊断'},
    'docs/m4-performance.md': {'## 当前Bc：':'## 历史Bc：', '## Current pan and annotation evidence limits':'## Historical pan and annotation evidence limits', '## 当前 ce7':'## 历史 ce7', '## 当前 DenseStress300':'## 历史 DenseStress300'},
    'docs/m4-ai-usability-audit.md': {'当前正式构建为 `index-C7L6p5cl.js`':'该历史阶段正式构建为 `index-C7L6p5cl.js`', '## 最终版本的实际浏览器范围':'## 历史C7最终版本的实际浏览器范围', '## 当前待完成门':'## 历史C7待完成门'},
}.items():
    text = (ROOT / path).read_text()
    for old, new in replacements.items(): text = text.replace(old, new)
    (ROOT / path).write_text(text)

compat = ROOT / 'skills/archcanvas/references/runtime-compatibility.md'
text = compat.read_text().replace('The current local `au3IB_0Q` Studio retains three composite starting graphs:', 'The historical `au3IB_0Q` Studio introduced three composite starting graphs, still present in the currently observed BKbgeBjI library:')
text = text.replace('consult `docs/m4-ancestor-corridors.md` for current assets and bounded browser evidence;', 'consult `docs/m4-collapse-continuity.md` for current assets and bounded browser evidence;')
compat.write_text(text)

stage = """# M4：直接祖先折叠与新手搭建的有界验收

当前正式构建为 `index-BKbgeBjI.js`，JS SHA256 `d106d5525baf288f966a1e61ebd1a115c6f3190d0b2bf62594d11dba58be8b66`；CSS `index-B6WbMowt.css`，SHA256 `172a09a8c147e53c3bef426cf76b59b8cc4893e891eb6e920aa7b25a0bb024e0`。最终独立专项13/13、Studio247/247、strict TypeScript/Vite退出0。实际CNN直接收起Repeat后，Repeat完整轮廓至pool的间距从1607恢复到31世界单位；不是前body矩形的1614→38。M4仍partial、真人0、M5未开始。

CNN展开Repeat和两个ResidualBlock后直接收起Repeat，旧缓存仍以隐藏子层的expandedIds查键，使pool留在localY1938，而已保存root概览为362。修复仅改本阶段产品的 `studio/src/core/document.ts`，按有效可见展开集合存取带 `visible-frontier/1:` 前缀的排序JSON数组键；继续保留隐藏展开记忆和局部坐标。恢复只写目标可见节点，保护操作/祖先锚点和固定子树，手动move继续同步各快照。打开已坏旧文档不会静默重排，显式展开→折叠才利用可信紧凑快照恢复。

旧排序拼接键有界枚举合法完整分段，支持身份内部的`|`。恰好一种解释时才采用，组合歧义或20000步预算耗尽不采用该缓存；正常展开仍可新增节点并撑开邻居。多个旧隐藏状态投影到同一可见层级时，只有可见坐标一致才采用。Canonical刷新可读新键。没有可信快照、任意手写JSON冲突或固定布局冲突不承诺自动修复，不移动固定对象来隐藏诊断。实现从正式合同和真实失败证据编写，未读取/迁移失败Temp原型，本轮不执行模型、不安装依赖。

冻结[109文件前状态](evidence/m4-collapse-continuity-work/before-implementation-attempt-1/manifest.json)、[22输入诊断](evidence/m4-collapse-continuity-work/diagnosis-attempt-1/diagnosis.json)和[完整轮廓补充](evidence/m4-collapse-continuity-work/diagnosis-attempt-1/outline-supplement.json)。独立期望来自手写compact/deep坐标和冻结actualCNN，不用新产品输出生成expected。预修复8项为2通过/6失败，初次12项11通过/1失败；literal旧键、夹具undefined字段JSON往返和组合分段歧义修正均保留失败原件。组合歧义反例的output独立期望262，修复前实际700，第13项锁定该期望。

最终[专项13项收据](evidence/m4-collapse-continuity-work/checks/target-attempt-3/receipt.json)、[完整247项收据](evidence/m4-collapse-continuity-work/checks/suite-attempt-2/receipt.json)、[严格构建收据](evidence/m4-collapse-continuity-work/checks/build-attempt-2/receipt.json)均退出0且输入前后精确。专项与全套计数不相加。[独立末核](evidence/m4-collapse-continuity-work/acceptance/final-check-audit-attempt-2/report.json)复读251输入/基础设施/日志及90份最终源码/配置/测试/合同；未重跑Python全套或完整独立发行。

最终build实际浏览器从已存compact rev22开始：展开23、直接折叠24，随后pool右40 rev25、左40 rev26、上40 rev27、下40 rev28、undo29、redo30、保存重开30。上移故意产生重叠与阻塞提示，下移后消失。实际同revision SVG导出UUID `1367fc7fa1034519b3de845b083c566a`，180×287.39495798mm。公开SVG viewBox从坏状态595×2526缩到595×950；compact/deep与冻结L0/L2几何精确。

[31原始文件清单](evidence/m4-collapse-continuity-work/browser-final-manifest-attempt-1.json)保留操作声明；声明是事后整理，不是同步OS遥测。[独立原生链核对](evidence/m4-collapse-continuity-work/acceptance/final-native-audit-attempt-4/report.json)107输入不变、18 DOM观测、142对边端点（284个端点），保存文档保留4个旧缓存和16个隐藏局部坐标。移动链相机/受保护锚点有界保持；右移使root宽度由254增至294，随child边界派生，回移后恢复，不代表祖先尺寸不变。展开前缺即时camera匹配记录，不认证展开屏幕锚点。[AI像素复核](evidence/m4-collapse-continuity-work/acceptance/pixel-current-attempt-1/review-receipt.json)核31原件、6画布图及放大footer；缩略图误读已保留并纠正，无实际footer滞后结论。右移短折线、左/下直线恢复；右侧白区仍存在，不宣称全局最美排布。

从空白搭建Input→Linear(16→8)→GELU→Output四节点三边，初建属于中间Bf，最终BK重开/再生成相同草稿、打开managed图并保存rev0。第一次按端口标签bbox中心点击未连上，生成明确报未连接输入；改点实际圆点才成功。最终BK原生拖入CNN起点为8节点7边，保存/静态生成通过；未认证CNN managed打开。Identity首次拖入失败，随后undo移除了先前CNN插入，误导文件名原样保留；重开后点击成功，重试原生拖入9节点、两项重叠警告、undo回8。

[独立搭建核对5/5](evidence/m4-collapse-continuity-work/authoring-independent-audit/attempt-3/receipt.json)复读42输入及实际存储副本，手算声明shape并核AST/源码/公开端口；actual17模块包含SiLU，无Softmax，三透明起点为MLP/CNN/residualMLP。审查器两次错误假设及修正保留。[搭建像素复核](evidence/m4-collapse-continuity-work/acceptance/authoring-pixel-current-attempt-1/review-receipt.json)核36原件/3图：四链侧端口每条四弯反复回绕，CNN两排有一次长回线但未观察交叉，managed Output副标题截断并暴露内部ID。端口命中、连线简洁与标签是明确待修项；这不是逐模块生成、模型执行、训练或真人新手认证。

三个AI角色分别核独立合同/工件、像素、搭建/性能控制证据，root用CUA操作；不能充当真实研究者。[CG单色阶段](m4-monochrome-role.md)及原封印不改，不继承为BK完整矩阵。宽度3残差间隙保留1白像素，宽度4被round cap填满；12被UI拒绝且未测像素，原所谓local截图实际含导出modal。Transformer交叉/重叠、标题绕行和深层长页仍开放。性能只有旧上下文三条简单控制页记账，没有BK Studio A/B、三次匹配矩阵或presented FPS。物理出版、真实研究任务、held-pointer取消均未认证。

[当前schema11状态](evidence/m4-human-review-handoff-status.json)记录各自版本和具体收据；[14文件文档前状态](evidence/m4-collapse-continuity-work/before-current-doc-update-attempt-1/manifest.json)及[两工作说明前状态](evidence/m4-collapse-continuity-work/before-final-doc-repair-attempt-1/manifest.json)保留原字节。历史失败/中间build/原raw不回写。
"""
(ROOT / 'docs/m4-collapse-continuity.md').write_text(stage)
(WORK / 'README.md').write_text("""# M4 空间连续性与搭建审查证据

本目录包含真实失败诊断、冻结期望、修复尝试、最终BKbgeBjI的13/247/strict-build收据、原生CNN四向/history/save/export、从空白/预制CNN/Identity试用，以及独立工件和AI像素复核。当前结论及边界见[阶段记录](../../m4-collapse-continuity.md)和[schema11状态](../m4-human-review-handoff-status.json)。M4partial、真人0、M5未开始；不执行模型、不安装依赖、不使用失败Temp。

最终专项[13/13](checks/target-attempt-3/receipt.json)、全套[247/247](checks/suite-attempt-2/receipt.json)、[strict/build0](checks/build-attempt-2/receipt.json)计数单列。[独立检查末核](acceptance/final-check-audit-attempt-2/report.json)复读251输入并保存90最终源码/配置/测试/合同。[原生链末核](acceptance/final-native-audit-attempt-4/report.json)107输入、18DOM、142对边端点；[原生清单](browser-final-manifest-attempt-1.json)31文件。事后动作声明不等于同步OS记录，展开屏幕锚点未认证。

[像素复核](acceptance/pixel-current-attempt-1/review-receipt.json)保留6画布状态与放大读数，轮廓gap1607→31；上移重叠提示和右移短折线不掩盖。[搭建独立核对](authoring-independent-audit/attempt-3/receipt.json)5/5、42输入；[搭建像素核对](acceptance/authoring-pixel-current-attempt-1/review-receipt.json)36原件/3图。端口标签click失败、第一次Identity drag失败/undo0与错误文件名保留，retry9→undo8。草稿四弯回绕、Output截断/内部ID仍待修。

此前8项2通过/6失败、12项reader/夹具失败、组合legacy歧义output700而期望262、审查器假设修正以及中间Bf构建均留在各attempt。最终report只认证其scope。旧CG单色封印、宽线补充、旧控制页性能/人类出版和研究门分开；AI不可记为真人。
""")

# The status is built after the narrative bytes have settled; it never binds itself.
refs = [
    'docs/m4-collapse-continuity.md',
    'docs/evidence/m4-collapse-continuity-work/checks/target-attempt-3/receipt.json',
    'docs/evidence/m4-collapse-continuity-work/checks/suite-attempt-2/receipt.json',
    'docs/evidence/m4-collapse-continuity-work/checks/build-attempt-2/receipt.json',
    'docs/evidence/m4-collapse-continuity-work/acceptance/final-check-audit-attempt-2/report.json',
    'docs/evidence/m4-collapse-continuity-work/acceptance/final-native-audit-attempt-4/report.json',
    'docs/evidence/m4-collapse-continuity-work/acceptance/pixel-current-attempt-1/review-receipt.json',
    'docs/evidence/m4-collapse-continuity-work/acceptance/authoring-pixel-current-attempt-1/review-receipt.json',
    'docs/evidence/m4-collapse-continuity-work/authoring-independent-audit/attempt-3/receipt.json',
    'docs/evidence/m4-collapse-continuity-work/authoring-independent-audit/reviewer-final-readback.json',
    'docs/evidence/m4-collapse-continuity-work/browser-final-manifest-attempt-1.json',
    'docs/evidence/m4-collapse-continuity-work/core-current-attempt-2/receipt.json',
    'docs/evidence/m4-collapse-continuity-work/before-current-doc-update-attempt-1/manifest.json',
    'docs/evidence/m4-monochrome-role-verification-sealed.json',
    'docs/evidence/m4-monochrome-width-pixel-supplement-attempt-1/receipt.json',
    'docs/evidence/m4-performance-controls-work/analysis-attempt-3/receipt.json',
    'studio/src/core/document.ts', 'studio/dist/index.html',
    'studio/dist/assets/index-BKbgeBjI.js', 'studio/dist/assets/index-B6WbMowt.css',
]
status = {
    'schemaVersion': 11, 'generatedAt': datetime.now(timezone.utc).isoformat(),
    'scope': 'Current BK collapse continuity and bounded native CNN/authoring artifact and AI pixel review. No full39 matrix, human, global aesthetics, physical publication, model runtime or current Studio performance certification.',
    'productionBuild': 'index-BKbgeBjI.js',
    'productionJsSha256': binding('studio/dist/assets/index-BKbgeBjI.js')['sha256'],
    'productionCss': 'index-B6WbMowt.css',
    'productionCssSha256': binding('studio/dist/assets/index-B6WbMowt.css')['sha256'],
    'productionIndexSha256': binding('studio/dist/index.html')['sha256'],
    'phaseStatus': 'partial', 'nextPhaseStarted': False, 'humanAcceptanceCertified': False,
    'implementationDirection': {'formalProductBuiltFromScratch': True, 'failedPrototypeRuntimeUsed': False, 'failedPrototypeFallback': False, 'certifiedPrototypeReuseCandidates': 0, 'modelExecutionThisRound': 'not_run', 'dependenciesInstalledThisRound': False},
    'tests': {'studio': {'passed': 247, 'failed': 0, 'skipped': 0, 'exitCode': 0, 'receipt': refs[2], 'sourceBeforeAfterExact': True}, 'focusedSeparateRun': {'passed': 13, 'failed': 0, 'skipped': 0, 'exitCode': 0, 'receipt': refs[1]}, 'strictTypescriptExitCode': 0, 'buildExitCode': 0, 'buildReceipt': refs[3], 'suiteCountsCombined': False, 'pythonFullSuiteRerunThisRound': False, 'currentFullStandaloneReleaseCertified': False, 'independentCheckAudit': refs[4], 'independentCheckInputCount': 251, 'finalSourceConfigTestContractCount': 90},
    'collapseContinuity': {'source': binding('studio/src/core/document.ts'), 'keyFormat': 'visible-frontier/1: sorted JSON array', 'latentExpansionAndLayoutPreserved': True, 'oldDocumentSilentlyRepairedOnOpen': False, 'legacyParsingBudget': 20000, 'ambiguousLegacySnapshotApplied': False, 'outlineGapBefore': 1607, 'outlineGapAfter': 31, 'units': 'world', 'nativeSavedRevision': 30, 'exportUuid': '1367fc7fa1034519b3de845b083c566a', 'independentNativeAudit': refs[5], 'independentNativeInputs': 107, 'domObservations': 18, 'edgeEndpointPairs': 142, 'endpointPoints': 284, 'pixelReceipt': refs[6], 'canvasScreenshotBrackets': 6, 'rawNativeFiles': 31, 'cameraAndProtectedAnchorsWithinMovementChainPreserved': True, 'expansionScreenAnchorCertified': False, 'globalAestheticsCertified': False},
    'authoring': {'baseModules': 17, 'transparentStartingGraphs': 3, 'catalogIncludes': 'SiLU, not Softmax', 'fourNodeChain': 'Input→Linear(16→8)→GELU→Output', 'nodes': 4, 'edges': 3, 'chainInitiallyCreatedOn': 'index-Bf intermediate', 'chainReopenedRegeneratedAndManagedSavedOn': 'index-BKbgeBjI.js', 'managedSavedRevision': 0, 'cnnNativeDragNodes': 8, 'cnnNativeDragEdges': 7, 'cnnStaticGenerationVerified': True, 'cnnManagedOpenVerified': False, 'identityFirstDragFailed': True, 'identityFirstUndoRemovedPriorCnnInsertion': True, 'identityRetryNodes': 9, 'identityRetryUndoNodes': 8, 'identityRetryOverlapWarnings': 2, 'independentArtifactAudit': refs[8], 'independentArtifactCasesPassed': 5, 'independentArtifactInputs': 42, 'pixelReceipt': refs[7], 'pixelOriginalInputs': 36, 'pixelRawImages': 3, 'newPerModuleBrowserCertification': False, 'newRuntimeCertification': False, 'humanNoviceCertification': False, 'remainingIssues': ['Port-label center clicks did not create connections; actual circles succeeded', 'Authored vertical chain uses repeated four-bend side-return paths', 'Managed Output subtitle clips and exposes internal output ID']},
    'aiReview': {'roles': ['mono_acceptance: independent coordinate/artifact/check auditor', 'mono_pixels: AI pixel reviewer', 'performance_controls: independent static authoring/control-window auditor'], 'reviewerRoleCount': 3, 'nativeOperator': 'root through CUA', 'nativeActionDeclaration': 'retrospective, not synchronous OS telemetry', 'rolesAreHumanParticipants': False},
    'humanResearch': {'preparedForCurrentBuild': False, 'verifiedForCurrentBuild': False, 'assigned': 0, 'collected': 0, 'researchers': 0, 'aiCountedAsHuman': False},
    'performance': {'currentStudioAbMeasured': False, 'threeReplicateMatrixComplete': False, 'presentedFpsCertified': False, 'actualHostForegroundCertified': False, 'controlRecords': 3, 'controlContext': 'older Dzp build context, simple control page only', 'controlAccountingPassed': 3, 'controlAccountingReceipt': refs[15], 'scope': 'Fixed 2s warmup +20s capture +2s drain accounting. About2Hz rAF and1024ms matched control click do not certify current Studio performance or causation.'},
    'priorRoleStage': {'build': 'index-CG7A-7XR.js', 'targetPassed': 31, 'studioPassed': 234, 'publicationPythonPassed': 9, 'nativeCases': 9, 'seal': binding(refs[13]), 'scope': 'Frozen historical role-specific evidence. Does not certify current BK movement, authoring, full matrix or full release.'},
    'widthOverride': {'nativeUiRange': [1, 4], 'step': 0.5, 'contractRange': [0.25, 12], 'width12UiRejectedWithoutMutation': True, 'width12PixelsTested': False, 'width3ResidualGapRetainedWhitePixels': 1, 'width4ResidualGapFilledByRoundCaps': True, 'rawLocalScreenshotsShowExportModal': True, 'pixelSupplement': refs[14]},
    'openItems': ['current Studio matched A/B performance and presented frame evidence', 'held-pointer active gesture cancellation', 'actual physical85/180mm human publication review', '3–5 actual researcher tasks; current build research preparation pending', 'Transformer crossings/overlaps, expanded header detours and deep tall pages', 'width4 monochrome role dash gaps', 'authoring port hit regions, repeated side-return bends and Output subtitle', 'expansion screen anchor requires matched immediate-before camera evidence', 'no per-module authoring runtime/training or current full39 matrix certification'],
    'previousStatus': binding('docs/evidence/m4-collapse-continuity-work/before-current-doc-update-attempt-1/files/docs/evidence/m4-human-review-handoff-status.json'),
    'preservedFailures': ['initial collapse implementation/literal legacy reader', 'optional undefined fixture roundtrip correction', 'composite delimiter ambiguity before13th test', 'intermediate build/browser attempts', 'native port-label clicks and first Identity drag/undo filenames', 'authoring auditor Softmax inventory and expression-versus-assignment assumptions', 'native auditor serialization/schema assumptions', 'pixel thumbnail footer misreading corrected by magnified crops'],
    'evidenceRefs': [binding(p) for p in refs],
}
write_json('docs/evidence/m4-human-review-handoff-status.json', status)
print(json.dumps({'updatedCurrentDocs': current_docs, 'statusSchema': 11, 'preUpdateFilesVerified': 14}, ensure_ascii=False))
