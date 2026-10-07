"""Update current entry points only; historical sealed stages remain unchanged."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json

ROOT=Path(__file__).resolve().parents[3]
WORK=Path(__file__).resolve().parent
entries=['README.md','docs/m4-completion.md','docs/m4-exit-audit.md','docs/m4-ai-usability-audit.md','docs/m4-human-review-handoff.md','docs/m4-performance.md','docs/m4-authoring.md','docs/acceptance.md','docs/capability-matrix.md','docs/evidence/README.md']
refs=['skills/archcanvas/references/formal-alpha.md','skills/archcanvas/references/runtime-compatibility.md']
before=json.loads((WORK/'before-implementation-attempt-1/manifest.json').read_text())
mapping={r['source']:r for r in before['records']}
out=WORK/'before-current-doc-update-attempt-1';out.mkdir(exist_ok=False)
records=[]
def bind(p):
    b=p.read_bytes();return dict(path=str(p.relative_to(ROOT)),bytes=len(b),sha256=hashlib.sha256(b).hexdigest())
for name in entries+refs+['docs/evidence/m4-human-review-handoff-status.json']:
    p=ROOT/name
    if name in mapping:
        rec=mapping[name];copy=ROOT/rec['copy'];assert p.read_bytes()==copy.read_bytes()
    else:
        copy=out/'files'/name;copy.parent.mkdir(parents=True,exist_ok=True);copy.write_bytes(p.read_bytes())
    records.append(dict(source=bind(p),copy=bind(copy),exact=True))
(out/'manifest.json').write_text(json.dumps(dict(createdAt=datetime.now(timezone.utc).isoformat(),scope='Before current entry-point/status update; existing226 copies reused without changing prior seals.',records=records),ensure_ascii=False,indent=2)+'\n')
for name in entries:
    p=ROOT/name;text=p.read_text();start=text.index('当前（2026-10-06）为 `index-BKbgeBjI.js`');end=text.index('\n\n历史版本说明',start)
    prefix='docs/' if name=='README.md' else '../' if name=='docs/evidence/README.md' else ''
    ep='docs/evidence/' if name=='README.md' else '' if name=='docs/evidence/README.md' else 'evidence/'
    note=f'''当前（2026-10-06）为 `index-ye7sAyyI.js` / `index-C769d2rm.css`。[端口命中与连线方向]({prefix}m4-authoring-interaction.md)新增圆点/间隙/文字统一命中区域和Enter/Space连接，按独立网络主轴放置端口，纵向四链现在三条直线；显式别名Output副标题显示`model output`并保留完整源码事实。最终专项28/28、Studio264/264、strict TypeScript/Vite退出0，计数单列；本轮未执行模型或安装依赖。

当前实际浏览器从空白四链点文字、拖圆点、键盘连接，核四向移动/平移、重复拒绝、history、保存重开、生成新managed并导出；双输入Add/Concat五边有界完成。17基础模块＋3透明起点可点击/拖入，MLP/residual点击和CNN拖入各自观察。合并草稿仍在(614,220)交叉，CNN长回线、多输入fit目标偏小、Escape后pending提示和部分截图时序差异均保留；不认证全局最美排布、逐模块执行或真人新手可用。

M4仍partial、M5未开始、真人0。三个AI独立角色分别核合同/原生工件、像素、实际源码工件，root用CUA操作；AI不计真人。当前Studio A/B、三次矩阵和呈现帧性能未认证。旧[空间连续性阶段]({prefix}m4-collapse-continuity.md)与单色证据保留原范围；[机器状态]({ep}m4-human-review-handoff-status.json)记录当前边界，[更新前归档]({ep}m4-authoring-interaction-work/before-current-doc-update-attempt-1/manifest.json)保留旧字节。下方旧“当前/本轮/最终”仅指其明示旧版本与冻结时点。'''
    text=text[:start]+note+text[end:]
    if name=='docs/m4-completion.md':
        text=text.replace('| 新手搭建/模块库 | 四链、预制CNN、Identity重试有界核对 | 17实际模块＋3起点；独立5/5、42输入。点端口困难、草稿回绕与Output副标题保留；无逐模块/训练/真人认证。 |','| 新手搭建/模块库 | 当前四链直线/四类端口输入/合并及三起点有界核对 | 17实际模块＋3起点；合并交叉、长回线和小目标保留；无逐模块/训练/真人认证。 |')
        text=text.replace('| 产品回归 | 独立专项13/13、Studio247/247、strict/build0 | [当前收据与独立核对](m4-collapse-continuity.md)；计数不相加，Python全套/独立完整发行未重跑。 |','| 产品回归 | 专项28/28、Studio264/264、strict/build0 | [当前收据与独立核对](m4-authoring-interaction.md)；计数不相加，Python全套/独立完整发行未重跑。 |')
        text=text.replace('| M4-06 空间连续性与出版 | 当前CNN直接祖先折叠/四向/history/save/export有界通过 |','| M4-06 空间连续性与出版 | 上一BK阶段CNN有界通过；当前四链新SVG有界 |')
    if name=='docs/m4-human-review-handoff.md':
        text=text.replace('| 新手操作与排布 | 四链/CNN/Identity有界通过，仍有明确失败 | 改善端口点击命中、侧端口重复回绕、Output截断与内部ID。 |','| 新手操作与排布 | 当前四链/合并/三起点有界通过，视觉问题保留 | 纵向直线、四类端口输入和别名Output已改善；合并交叉、CNN长回线和小目标待修。 |')
        text=text.replace('| 回归/发行 | 专项13/13、Studio247/247、strict/build0 |','| 回归/发行 | 专项28/28、Studio264/264、strict/build0 |')
    p.write_text(text)
english='''Current configured checkout (2026-10-06): ye7sAyyI/C769d2rm. See docs/m4-authoring-interaction.md. Final focused28/28, Studio264/264 and strict TypeScript/Vite exit0 are separately bound; no model execution or dependency installation this round. Draft ports have one dot/gap/label hit region and Enter/Space connections, with orientation determined per weakly connected network. The manually positioned vertical Input→Linear16→8→GELU→Output chain has three straight routes; Arrange still uses horizontal rank. Explicitly aliased Output subtitles use model output while preserving full source/output facts.

Bounded native trials cover four-chain label click/circle drag/keyboard, duplicate rejection, undo/redo, four node moves and four camera pans, save/reopen, a fresh managed figure and180mm SVG. Add/Concat distinct inputs and same-source fanout connect; MLP/residual starts are clicked and CNN is natively dragged. The library has17 modules including SiLU and3 transparent graphs. Current merge routes still cross at(614,220); CNN retains a long return, fit port targets are small, Escape leaves a pending notice, and some screenshot pixels do not match names/DOM brackets. Retained failed observers and stale/modal images are not passes. This does not certify arbitrary labels, globally optimal routes, every module, training, physical publication or human novice usability.

Previous BK collapse and CG monochrome records/seals retain their historical scopes; mutable prior paths resolve through the226 pre-implementation copies. Three independent AI roles are not humans: zero human records, M4partial, M5notstarted. Performance has only older simple-control records, no current Studio A/B or presented-FPS certification. Consult docs/evidence/m4-human-review-handoff-status.json for current bindings. Following historical paragraphs retain their original build scope.'''
for name in refs:
    p=ROOT/name;t=p.read_text();start=t.index('Current configured checkout');end=t.index('\n\nHistorical Dzp scope:',start);t=t[:start]+english+t[end:]
    t=t.replace('currently observed BKbgeBjI library','currently observed ye7sAyyI library').replace('consult `docs/m4-collapse-continuity.md` for current assets and bounded browser evidence','consult `docs/m4-authoring-interaction.md` for current assets and bounded browser evidence')
    p.write_text(t)
print(json.dumps(dict(entryPoints=len(entries),skillReferences=len(refs),priorDocuments=len(records)),ensure_ascii=False))
