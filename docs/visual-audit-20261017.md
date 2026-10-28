# 视图箭头与自动布局：首轮视觉审计（2026-10-17）

**结论：未通过完整验收。** 已在真实 Studio 中目视检查 7 类图结构，确认展开阻断、虚线近距离折返、展开后默认路径冗余，以及深层图总览可读性问题；另确认两个预设的 SVG 文件生成失败。本轮交付测试证据与可执行缺陷单，**未修改产品逻辑，也没有将已有“优化连线”按钮产生的改善记作本轮修复**。

依据：[用户指定规范](/home/fzg/Documents/Codex/2026-10-17/new-chat/outputs/视图系统箭头与自动布局通用优化测试规范.md)。本报告区分“浏览器目视检查”“引擎批量结构检查”和“尚未覆盖”，不把历史报告或测试进程正常退出作为视觉通过证据。

## 版本、环境与证据

- 正式开发目录：`/home/fzg/PycharmProjects/ArchCanvas/ArchCanvas_Model_Architecture_Studio`；HEAD `e293d8eb91f56d7800c7135a66049022a2de0d45`，**带已有未提交改动**，不能仅用提交号复现。文件哈希与工作树状态见 [manifest.json](evidence/visual-audit-20261017/manifest.json)。没有使用失败的 Temp 运行时。
- 本轮 `npm run build` 成功；有大于 500 KB 的打包体积警告。运行正式 Skill 的开发目录 launcher，版本 0.1.0，服务为 `127.0.0.1:8897`，独立测试状态目录 `/tmp/archcanvas-visual-audit-20261017`。
- 客户端为 Codex 内置浏览器，实际截图为 **1280×720**。浏览器内核版本、DPR、字体实际回退及硬件未独立测定。曾请求 960×640，但实际页面没有缩小；**小视口测试未完成**。
- 源码仅作静态分析，没有执行模型，没有添加 ACT 专用适配器，没有改写原 ACT 源码。测试输入位于证据目录；不会将 Agent 对源码的理解伪装成运行时张量事实。
- [截图索引](evidence/visual-audit-20261017/gallery.html)、[复现与批量结果](evidence/visual-audit-20261017/repro-results.json)、[DOM 几何测量](evidence/visual-audit-20261017/capture-metrics.json)。截图保存周边工具栏和警告，便于核对操作状态。

## 覆盖与结果

| 检查类型 | 覆盖 | 结果与边界 |
| --- | --- | --- |
| 浏览器目视：既有图 | Transformer、VAE、U-Net、iTransformer | 检查总览、局部/深层展开、缩放、部分 Apply layout、侧板折叠；不代表全部状态通过 |
| 浏览器目视：真实非预设图 | 原始 ACTPolicy；另有此前编辑副本的补充截图 | 验证条件结构与虚线；原始版和编辑副本分开记录 |
| 浏览器目视：固定种子生成 | SeededFanout，种子 20261017，7 个分支，3 层嵌套，残差及中英文长名称 | 展开成功；发现可避免的 U 形线路 |
| 浏览器目视：结构变换 | MLP 复制为两支，加入条件与汇合的 Wrapper | 初始 8 节点/7 边可显示；继续展开被拒绝 |
| 批量引擎结构检查 | 229 个非 builtin 案例，初始状态 + 全部展开 | 当前 114/114 通过；历史 99/115 通过、16 失败；**并非 229 张图的逐张视觉复核** |
| 导出实测 | Transformer、VAE，SVG | 对话框预览正常，生成文件均被摘要校验拒绝；最终文件尺寸视觉检查受阻 |

案例目录还有一个 builtin 布线沙盒，因此“当前 114”是本轮批量脚本排除沙盒后的数量。两种陌生输入分别来自固定种子生成和结构变换，均未据其结果修改或调参产品。ACT 在既往工作中已经使用，不将它冒充本轮全新的保留集。

### 指标的含义

路径长度与间距采用画布世界单位；交叉数为不同 `binding.wire_identity` 路径间的正交线段内部相交计数，排除端点相触和共线，可能重复计同一交点。弯折数按折线中间点计，**这些是诊断指标**。语义授权的公共干线可能有不同展示标识，不能只凭共线计数判定错误汇合；最终仍需核对完整 wire 合约。

`data-layout-constraint-valid=true` / `data-source-constraint-valid=true` 是应用自身校验声明，不是独立证明，也不代表虚线、文字或出版尺寸已通过。`data-frontier-ms`、引擎脚本耗时均不能当作呈现 FPS。

## 缺陷与工程任务

### VA-01 / P1：条件分支与跨层投影的图无法继续展开

- **状态：待修复。** 影响本次开发版本；来源：陌生结构变换。复现输入：[transformed_mlp.py](evidence/visual-audit-20261017/inputs/transformed_mlp.py)，入口 `transformed_mlp:Wrapper`。它是 MLP 双支 + 条件 + 分支内赋值/投影 + 汇合，默认显示 8 节点/7 边；源码树另有 46 个条目，不能混为可见节点数。
- 环境：1280×720，初始缩放 67%，默认两侧板。静态分析的条件区域明确保留为源码结构，不要求推断实际运行哪一支。
- 步骤：打开输入 → 点击“待解析 · Module”的 `＋` → 等待警告 → 点击“优化连线”后重试。也可打开本轮保留的 [测试文档](http://127.0.0.1:8897/?documentId=canvas-architecture-transformed_mlp.Wrapper-60eb610f84d7-af9d54b9)；服务与测试状态存在时有效。
- 预期：基于源码的子结构可以展开，并保持独立关系、正交路径和容器接口；执行路径仍标为未选择。
- 实际：出现 `unrelated tensor lane overlap`、`nonorthogonal canonical route`、`undeclared boundary` / `boundary crossing order changed`，展开不提交，旧紧凑图保留。优化后再试仍失败。纯引擎全展开也能重现不相关通道重叠，但不同 frontier 下边 ID 不同。
- 根因分类：**可见图投影 / 容器接口 / 边路由**。候选公共根因是源码适配图的独立输出及跨层端口投影，在展开后未得到合法可区分通道。现阶段没有证据把全部报错归为一个已证实的单一根因。
- 工程任务：沿 `source-adapter.js → recursive-graph.js → frontier-task.js → source-contracts.js` 追踪端口和边界证据，在公共投影/布线阶段修复；新增双分支条件合流、返回槽位、展开/折叠往返和输入重排用例。**不得通过关闭独立 wire/边界校验来放行**。
- 验证覆盖/指标：既有当前案例 114/114 结构通过，陌生变换图全展开失败，证明已有样本不能涵盖该类别。尚无修复后指标。
- 回归入口：`reproduce.mjs` 的 `transformed.expanded` 当前 `ok=false`，属于可复现失败记录，不是已通过断言。
- 证据：[32：展开被拒绝](evidence/visual-audit-20261017/32-transformed-branch-expand-rejected.png)、[33：优化后重试](evidence/visual-audit-20261017/33-transformed-after-apply-retry.png)，对应 DOM、SVG、geometry JSON 和输入 bundle 均已保存。

### VA-02 / P2：条件控制虚线出现仅隔 2 单位的反向折返

- **状态：待修复。** 来源：只读原始 ACTPolicy；不是此前增删改的副本。原源码入口 `policy:ACTPolicy`。
- 结构：19 可见节点/13 条张量边，另外 2 条源码条件关联虚线，可见包含深度 3。展开外层 `if actions is not None`，内部 true/else 保持收起。1280×720，细节截图 177%。
- 步骤：打开 ACTPolicy → 在层级树展开外层条件区域 → 定位其判定菱形和 true/else 两臂 → 放大查看虚线。
- 预期：从判定标记到两个分支的虚线可以清楚追踪，平行段留有可读间距。
- 实际：false 路径为 `(386,1154) → (386,1166) → (324,1166) → (324,1168) → (735.5,1168) → (735.5,1192)`；先向左 62，再沿仅隔 **2** 单位的相反方向段返回。视觉近似叠线，true 关系还共享起始区域。应用仍标记 `geometryValidated=true`。
- 根因分类：**边路由 / 虚线可读性**。公共代码 `source-controls.js` 的回退路径用 `candidates.find(safe)` 选择首个合法候选；几何合法判据不足以约束短折返、自身平行段间距与候选质量。这是条件关联边与张量边校验范围不同造成的可读性缺口，未证明张量关系被篡改。
- 工程任务：为控制关系统一候选评分和最短可读间距，对自折返、短段、文字及其他类型关系联合检查；保留控制关系身份及“执行路径未选择”语义。用左右并列/上下堆叠分支、混合展开和长条件名组合回归，不写 ACT 特例。
- 指标：false 虚线长度 511.5、4 弯、折返段间距 2；无修复后数据。
- 回归：`measure-captures.py` 输出 `15-act-original-if-detail.sourceControls[].turnbacks`；本轮仅测量，尚未设置质量通过阈值。
- 证据：[15：虚线细节](evidence/visual-audit-20261017/15-act-original-if-detail.png)、[14：总览](evidence/visual-audit-20261017/14-act-original-if-fit.png)。[18](evidence/visual-audit-20261017/18-act-original-dependencies-detail.png) 为继续展开内部后的补充，不是同一状态的修复后图。

### VA-03 / P2：展开后的默认走线与手动优化质量不一致

- **状态：待修复；现有按钮可临时改善。** 来源：固定种子生成，输入 [seeded_fanout.py](evidence/visual-audit-20261017/inputs/seeded_fanout.py)，入口 `seeded_fanout:SeededFanout`。
- 结构：初始 17 节点/21 边，全部展开 25/28，3 层嵌套，7 个并列分支、残差及中英文长名称。种子 20261017；分支种类为 ReLU、Sigmoid、GELU、ReLU、Sigmoid、Identity、Identity。
- 步骤：打开输入 → 画布选项“展开全部” → 在左树定位嵌套 residual cell 的 Linear，放大至约 92% → 查看 Linear→GELU → 点击“优化连线”。
- 预期：上下排列、直接通道空闲的两个算子优先采用清楚的向下直线；展开与手动优化采用一致的质量约束。
- 实际：展开后从两个右端口绕 U 形，点击优化后变为垂直直线。该边 **152 → 54** 单位，**2 → 0** 弯；全图长度 **8984 → 8530**、弯折 **34 → 32**，交叉计数 **5 → 5**。节点 transform 列表及语义绑定摘要均相同。仍有交叉，不宣称优化后完美。
- 根因分类：**端口分配 / 路由策略一致性**。`frontier-task.js:23` 将传入 options 交给 `F.route`；诊断入口默认 `{}`，而工具栏 `app.js:80` 提供 `optimizeReadability:true` 等选项。实际路径对比证明差异存在；需要继续追踪两条用户操作的完整选项来源，不应仅改一个默认值就宣称解决全部情况。
- 工程任务：统一展开、初始导入、重布线的公共终结质量阶段，同时尊重手动端口、固定节点、折点和局部范围。回归包含竖链、横链、侧边有障碍、容器边界、强制端口和不同输入顺序，防止直连优化破坏约束。
- 验证/回归：两次截图节点身份、位置和 edge binding 摘要一致；`reproduce.mjs` 保存同样的默认/优化路径。尚无本轮产品修复及回归结案。
- 证据：[29：默认折返](evidence/visual-audit-20261017/29-seeded-unary-detour-detail.png) → [30：点击优化后](evidence/visual-audit-20261017/30-seeded-unary-after-apply.png)。

### VA-04 / P2：深层展开总览缩得过小，难以追踪层级与箭头

- **状态：待设计与验证。** 来源：U-Net、iTransformer、VAE；不是单个模型 ID 的问题。
- 结构/环境：U-Net 全展开 54 节点/43 边，图高约 6842 世界单位，总览约 7%；iTransformer 混合展开 37/57，总览约 11%；VAE 混合展开 21/22，总览约 20%。1280×720。大图部分 DOM SVG 不完整，但截图和 geometry JSON 完整。
- 步骤：打开示例 → 全部或混合展开 → 点击“适合画布” → 折叠两侧板比较 → 放大到局部核查。
- 预期：总览保留方向和分区导航，且可以顺畅进入可读的细节；深图无需强行在单屏显示全部文字。
- 实际：深层纵向堆叠导致高度限制缩放，横向大量留白，文字和细线很难分辨。折叠侧板不能解决高度限制。U-Net 局部约 93% 时可辨，未确认该截图存在错误端点。
- 根因分类：**节点排布 / 相机与多尺度展示**。这是包含层级、纵向串行排布与 fit-all 共同作用；不能简单放大整图然后裁剪内容当作修复。
- 工程任务：评估语义缩放、详情聚焦与返回总览、长链分段或替代排布方向；保护用户局部布局和锁定位置。针对宽图、深图、宽深组合验证导航和导出，明确总体概览与细节图的不同目标。
- 指标/回归：以上缩放和图规模为基线；无修复后值。尚未完成可读字号/箭头尖端的最小缩放门槛。
- 证据：[20：U-Net 全展开](evidence/visual-audit-20261017/20-unet-all-expanded-fit.png)、[21：U-Net 局部](evidence/visual-audit-20261017/21-unet-skip-detail.png)、[24：iTransformer](evidence/visual-audit-20261017/24-itransformer-mixed-fit.png)、[08：VAE](evidence/visual-audit-20261017/08-vae-sampling-expanded-fit.png)。

### VA-05 / P1：预设预览能打开导出对话框，但无法生成 SVG 文件

- **状态：待修复；阻断最终尺寸验收。** 来源：内置 Transformer 和 VAE，分别实测。Transformer 初始 23 节点/25 边，展开 Attention 后 33/38；导出 UI 为 180 mm 页面宽。VAE 为独立复核案例。
- 步骤：在主 Studio 从折叠菜单选择预设 → 右上“导出” → SVG → “生成文件”。
- 预期：下载当前可见图的 SVG，并能按最终物理尺寸目视核查文字、线宽、端点与图例。
- 实际：预览可显示，但两者均出现 `ApiError: Preview sourceDigest must be an exact SHA256 hexadecimal digest.`，未成功生成可交付文件。
- 根因分类：**其他：预览/正式文档导出绑定契约**。`App.tsx` 的 `openPreviewExport` 直接将 `frozen.sourceBindingDigest` 传出；预设预览可以使用 `preview-only:<case>` 身份，而 `workspace.py:export_preview` 要求可选摘要一旦给出就必须为 64 位十六进制 SHA256。
- 工程任务：区分预览身份和真实来源摘要，按契约传递可核验字段；保留 caseId、实际 SVG 摘要和浏览器声明来源。不能伪造源码 SHA256，也不能任意放松摘要校验。回归覆盖内置预设、源码导入、保存重开、详情 SVG，以及切换模型导致快照失效。
- 验证：Transformer 和 VAE 均失败，修复后须分别导出真实文件并核对回执和图像，不能只测对话框打开。
- 证据：[39：对话框](evidence/visual-audit-20261017/39-transformer-export-dialog.png)、[40：Transformer 拒绝](evidence/visual-audit-20261017/40-transformer-export-rejected.png)、[41：VAE 拒绝](evidence/visual-audit-20261017/41-vae-export-rejected.png)。
- 限制：Transformer 的尺寸预检提示 180×150.8 mm、节点名字号 5.78 pt、最小字号 4.26 pt、主线 0.67 pt，并建议约 296×248 mm；这是合理的可读性提示，**不将提示本身记为缺陷**。最终文件检查仍未完成。

### VA-06 / P2：历史案例的全展开结构检查存在 16 个失败

- **状态：待分析；尚未逐个 UI 目视复核。** 来源：115 个历史案例中的 16 个，当前版本引擎初始 + 全展开序列。每例 ID、图名和错误见 [repro-results.json](evidence/visual-audit-20261017/repro-results.json)。失败时未提交新状态，因此不提供虚构的展开后规模或缩放。
- 复现：运行下方 `reproduce.mjs`；历史 bilinear attention、capsule routing、graph attention、graphsage、Autoformer、TimeMixer 等 10 例出现独立通道/边界错误；4 个 Transformer 历史图出现 `recursive child leaves owner junction-*`；2 个历史残差图出现 `source containment changed junction-2`。
- 预期：历史案例若可供用户打开，应可按声明范围展开；不支持的资料应有可理解的状态，而非与当前案例混成已通过。
- 根因分类：**可见图投影 / 包含关系 / 路由**，至少三个错误簇，不能当作一个已定位根因。
- 工程任务：先逐簇在真实 UI 对照源材料复核，再在 authority 归一化、junction owner/范围或路由阶段修复，保留来源关系。下一轮用当前案例和历史案例一起回归，不降低验证器标准。
- 指标：当前案例 114/114 结构通过；历史 99/115，通过数不等于视觉通过。无修复后数据，也不据此宣称“本轮引入退化”，因为没有改动前同输入基线。

## 待核实事项与非缺陷说明

- **VAE 跨层通道拥挤**：[07](evidence/visual-audit-20261017/07-vae-route-detail-105.png) 105% 细节可见多条线路贴近 Sampling 容器，19 节点/20 边，路径总长 11873.06、43 弯、12 次诊断交叉。本次未检测到不同 wire 的共线重叠，也未证明有错误汇合；保留为待核实可读性事项，不能把交叉一律记为错误。
- **长名称表达**：[29](evidence/visual-audit-20261017/29-seeded-unary-detour-detail.png) 的中英文类名以省略号显示；`source-adapter.js:49` 以字符数 29 截断。完整名称可通过源码/树查阅，没有证据称源码丢失。后续评估按实际字体测宽、自动换行和完整名称提示，优先级 P3。
- **Transformer 共线候选**：测量脚本能发现不同展示 wire 标识的共线片段，但可能是语义授权的共享干线，未独立逐个核对完整 contract 前不列为错误。
- 案例切换后有旧页脚错误残留；相关截图可能同时显示旧错误与新图。它影响反馈可信度，不能把残留错误归到新案例。以当次操作警告、图身份和复现脚本共同判定。

## 可重复运行方式

在正式项目根目录运行；不需要 PyTorch 模型执行，也不需要新增适配器：

```bash
python3 -B docs/evidence/visual-audit-20261017/inputs/generate.py
node docs/evidence/visual-audit-20261017/reproduce.mjs
python3 -B docs/evidence/visual-audit-20261017/measure-captures.py
```

生成器保存输入与种子；引擎脚本加载当前公共引擎和已保存的 AST bundle，批量案例使用与应用一致的全部 authority 输入。**脚本退出 0 表示诊断完成，失败保存在 JSON 的 `ok:false` 中，不代表测试通过。** 测量脚本处理完整 DOM SVG，不能替代浏览器视觉复核。

重新打开陌生输入进行 UI 检查：

```bash
python3 -B skills/archcanvas/scripts/archcanvas_runtime.py serve --host 127.0.0.1 --port 8897 --data-dir /tmp/archcanvas-visual-audit-20261017
```

在另一终端为每个入口创建正式文档，访问命令返回的精确 URL：

```bash
python3 -B skills/archcanvas/scripts/archcanvas_runtime.py open --root docs/evidence/visual-audit-20261017/inputs --entry seeded_fanout:SeededFanout --server http://127.0.0.1:8897
python3 -B skills/archcanvas/scripts/archcanvas_runtime.py open --root docs/evidence/visual-audit-20261017/inputs --entry transformed_mlp:Wrapper --server http://127.0.0.1:8897
```

浏览器持久化会恢复展开/局部布局。新一轮基线应使用独立浏览器状态或通过编辑 JSON 明确记录恢复状态，不应无说明清除用户数据。引擎脚本使用新建图，可作为稳定结构复现。

## 证据质量与验收边界

- 截图共 40 张；01–05 为早期浏览检查，06–38 中大部分另有 DOM/geometry；39–41 为导出对话框截图与 DOM。完整清单与 SHA256 在 manifest 中。
- **22 文件名错误**：切换未成功，实际仍为 U-Net；不计入 iTransformer 覆盖。**37 仍为 1280×720**，不计入小视口通过证据。
- 20、21、22、24、25 的初次 SVG DOM 读取达到输出上限，已改名为 `.svg.truncated.txt`，不得当作有效 SVG 或出版导出文件。原截图和 geometry JSON 完整，截断说明见 [incomplete-dom-artifacts.json](evidence/visual-audit-20261017/incomplete-dom-artifacts.json)。其余 SVG 是包含编辑层的实时 DOM 快照，同样不能称为最终出版导出。
- `catalog-full-expanded.json` 是早期只用 detailed 输入的补充压力诊断；与应用完整 authority 不同，不作为本报告 229 例统计的依据。
- 尚未覆盖完整矩阵：自环、反向/循环/并行边、空容器、多连通分量、全部编辑动作、手动折点/固定约束、反复展开后的稳定性、真实窗口变小、黑白打印和最终物理尺寸导出；也没有对全部既有案例逐张目视验收。
- 本轮未交付产品修复，所有缺陷均保持开放；没有修复前后版本对照，也没有“无退化”结论。下一轮先处理 VA-01 与 VA-05，再统一 VA-02/03 的公共路由质量约束，并补齐剩余组合矩阵与独立保留集。
