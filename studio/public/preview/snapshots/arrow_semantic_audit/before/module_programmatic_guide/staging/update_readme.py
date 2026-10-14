from pathlib import Path
from collections import Counter
import json
HERE=Path(__file__).resolve().parents[1]
mods=json.loads((HERE/'module_catalog.json').read_text())['modules'];count=len(mods);families=Counter(m['family'] for m in mods)
lines=['# 模块程序化绘图原型','',
 '本专题针对两个目录指向的源码，补绘现有模型案例未展开过的模块子图，扩展统一 IR、图元、状态与连线机制。入口：[可搜索画廊](generated/index.html) · [新增覆盖差异](coverage.md) · [完整目录审计](index_audit.md)。',
 '',f'当前 **{count} 个模块案例**，其中原有 8 个，本轮新增 {count-8} 个；每例有概览、内部模块、算子详细三粒度，共 **{count*3} 张 SVG 与 {count*3} 张 PNG**。它们独立于已有 30 个完整模型案例统计；源码变体分别作为适配案例，不等于不同完整模型。',
 '', '沿用 Transformer 的 DejaVu Sans 字体、鲜明角色色和深色轮廓，整体与内部主流程均自底向上。同源独立分支并列、依赖调用顺序上下排列、tuple 返回值分别保留。颜色表示视觉角色；参数共享看实例身份和 IR。',
 '', '[新增模块详细图总览](generated/contact_pages.html) · [最终审阅](generated/module_review.json) · [实际导出核验](generated/export_checks.json) · [错误注入检查](generated/semantic_negative_checks.json) · [源码快照检查](generated/pinned_source_checks.json)。原8例的初始审阅报告保存在 [reviews/initial_eight](generated/reviews/initial_eight/module_review.json)，原8例的总览图片仍为 [detailed_contact.png](generated/detailed_contact.png)。',
 '', '## 模块适配目录','', '| 模块族 | 案例数 | 模块例子 |','| --- | ---: | --- |']
for family,n in families.items():
 entries=[m for m in mods if m['family']==family]
 lines.append('| '+family+' | '+str(n)+' | '+' · '.join('['+m['key']+']('+m['gallery']+')' for m in entries)+' |')
lines += ['', '完整清单、所选实现、源码 SHA 和逐模块范围在 [module_catalog.json](module_catalog.json)；每例说明位于 docs，对应关系也能从图中 E###、SVG tooltip 和 source_map.md 检查。',
 '', '## 本地生成与验证','',
 '保留本目录与同级 `model_zoo_programmatic_guide`。`bootstrap.py` 复用其静态 `spec/evidence/layout/theme/notebook_source` 引擎。本专题拥有独立 manifest、registry、适配器与产物，不接入 Studio 编辑会话。Python 3.10+ 即可生成 SVG；PNG 需要 `rsvg-convert`，检查 PNG 需要 Pillow。无需 PyTorch、GPU、权重或训练数据。',
 '', '```bash','cd "prototype/module_programmatic_guide"',
 'python3 fetch_sources.py --offline --report generated/pinned_source_checks.json', 'python3 generate.py --png','python3 verify.py generated --png','python3 checks/verify_semantics.py','python3 audit_coverage.py','python3 review_expansion.py','```',
 '', '从工作区根目录运行上例的 cd；已经在本目录时略过它。只修改一个模块时优先小范围生成：','',
 '```bash','python3 generate.py --module nonlocal_attention --png',
 'python3 verify.py generated --module nonlocal_attention --png',
 'python3 generate.py --module fpn --out /tmp/fpn-preview --png','python3 verify.py /tmp/fpn-preview --module fpn --png','```',
 '', '`fetch_sources.py --offline` 只核对固定 SHA256/Git blob 与 Notebook 单元映射，不联网、不写回。默认模式仅在文件缺失或被修改时恢复固定 commit。Notebook 派生 Python 保留单元/行映射，魔法命令被注释，从不执行。源码许可证缺失时 manifest 明确标记，不能用别的仓库 LICENSE 代替。',
 '', '## 目录与产物','', '```text',
 'module_adapters/     每例 build() + validate_ir()，以及局部共享声明 helper',
 'sources/             固定 commit 源码、原 Notebook、派生 Python 与许可证',
 'upstream/            两个 README 索引与固定 tree/revision',
 'source_manifest.json 来源、原始/派生哈希与 Notebook 单元映射',
 'module_catalog.json  索引条目→仓库→源码符号→所选模块边界',
 'existing_coverage.json 原30个主模型的逐节点覆盖盘点',
 'coverage.json/.md    模块覆盖差异、旧候选到实现的映射',
 'index_audit.json/.md 两目录全部条目、Notebook、已取源码符号的审计',
 'docs/                每例源码↔图元、端口/参数身份和布局理由',
 'checks/              独立 AST 合同、关键语义与错误注入检查',
 'generated/           SVG/PNG、搜索画廊、IR/证据/布局、最终报告',
 'staging/             此次分组获取/集成记录与合并前试绘工具','```',
 '', '每例生成目录含 `semantic_ir.json`、`source_evidence.json`、`profile.json`、`visual_style.json`、`source_map.md`、`layout_*.json`、`layout_checks.json` 以及 index.html。完整 IR 保留折叠节点，layout 只记录当前可见节点、bbox、端口和实际路径。形状是静态推导，不能当作数值执行观测。',
 '', '## 源码语义与视觉布局的分工','',
 '1. 固定实现与构造配置，先选模块输入/输出和排除项，核对 Parameter、buffer、普通属性及 train/eval 分支。不能用教科书默认替代源码。',
 '2. `build()` 显式声明节点、层次、实例身份和 typed edges。chain 只用于真实顺序；复杂多输入用 graph 和显式端口；状态/参数面板只表达来源或归属。图的 ranks 不自动创建数据依赖。',
 '3. 从完整 IR 投影三个粒度：折叠模块 → 内部分组 → 算子详细。measure 计算标签/形状/内容尺寸，再按底到顶 rank、并列列距与组间距分配 bbox。',
 '4. 连线器根据真实 bbox 和端口寻找正交通道，避开无关图元和边框；提前转弯，终段至少18px，显式端口预留24px。模型配置决定语义，布局约束决定展示。',
 '5. `validate_ir()` 核对所选语义，独立 AST 与负例检查关键源码合同；实际 SVG/PNG 检查核对 metadata、几何和源码副本，再目视复查。静态检查通过不等于数值运行正确。',
 '', '新增来源使用新的 source-project slug，保持旧 manifest 项的整个快照 digest 不变。只增加已有 slug 的文件也会改变其快照，造成旧图证据失配，需避免。旧模块三图与原模型产物的保留检查见 [existing_artifacts_check.json](generated/existing_artifacts_check.json)，本轮扩展前的输出哈希保存在 `staging/original_output_hashes.json`，便于离线重复核对。`review_expansion.py` 会刷新详细图总览、链接核验和最终报告；如果主动修改了原有案例，应另建新基线并说明变更，不能把旧图变化计为通过。',
 '', '## 完整性边界与后续扩展','',
 '本轮尽量合并可取得、可审阅、具有不同结构机制的模块，而不是再次分成小模型批次。目录审计覆盖全部832条记录，但外链仓库并未全部递归读取，不宣称它们的所有模块和动态配置都已绘制。未获取实现、普通 kernel、另一训练/反向配置、同构模块与整模型容器均保留明确边界。',
 '', '如 ROI Align / DeformConv 的底层 kernel 未冻结，图只能解释 Python 参数准备和真实库调用边界；GRU 门内部采用补充固定 PyTorch 实现时，说明区分 rasbt 的库调用与补充实现证据；CORN 解码来自 Notebook 调用段，不伪造一个 nn.Module 类。',
 '', '后续添加模块：先查 coverage 与 index_audit，冻结新实现和许可状态，编写显式适配器、来源记录与中文对应文档，添加独立源码合同及关键依赖负例，试绘三个粒度并完成导出/目视核验。可复用图元和布局引擎；当前仍需要源码审阅后写适配器，不能仅修改 --source 输入任意源码自动生成正确结构。','']
(HERE/'README.md').write_text('\n'.join(lines))
