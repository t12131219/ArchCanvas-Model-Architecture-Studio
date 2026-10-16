# 通用源码发现、适配与 act 验证

> 本页保留 2026-10-15 的验收范围与历史收据。2026-10-16 的有限结构生成、自定义组合协议和新预览恢复修复见 [后续记录](generic-source-editing.md)；当前源码检查规则已升级为 `source-inspection/3`，旧版本收据不代表当前实现。

2026-10-15。本轮修复针对共享源码规则和持久化合同，不按 `act`、Policy、DETRVAE 或任何预设模型名称特判。目标是让 Agent 可以发现陌生模型、检查本地结构、保存可复验适配数据，在 Studio 交互后通过保留源码的独立副本继续预览。

本报告依据已保存的目录发现、15 类双解析器矩阵、数据适配、源码保留副本及路线差分证据。当前后端以[最终源码箭头与适配收据](evidence/act-source-support-20261015/final-arrow-support/receipt.json)、[重新生成的源码保留闭环](evidence/act-source-support-20261015/final-arrow-support/source-preservation/summary.json)和[只读返回槽审计](evidence/act-source-support-20261015/final-arrow-support/readonly-slot-review.json)绑定实现 SHA；中间收据仅用于追溯，不作为最终通过证明。

## 当前实现

| 原问题 | 通用修复 | 合同边界 |
| --- | --- | --- |
| 目录入口遗漏 Policy | 静态目录发现、局部继承及 Python C3 方法查找，自写 `__call__` 优先于 `forward` | 动态类、装饰器替换、类方法重绑和无法定位的外部实现保留限制，不根据名称认定模型 |
| 工厂/构造参数子模块缺层级 | 通过带源码证据的赋值、返回槽、工厂和参数注入恢复可能包含关系，显式记录未知配置与重复次数 | 源码定义关系不证明运行分支、实例数量或 tensor topology |
| 未知模块不能复用 | `archcanvas-source-adapter/1` 数据标准与 scaffold/validate/register/list/preview 实现；当前规则为 `source-inspection/2` | JSON 数据模块，不加载或执行 Python 插件；源码或检查规则变更使旧记录失效 |
| 草稿连接通过却无法生成原模型 | 保留已选源码 corpus 的独立副本；仅精确定位并有正式合同的构造字面量参数可修改，随后独立重分析 | 未证明的新增/删除/重接不能静默转成模型；原源码始终不改 |
| 当前预览与编辑覆盖不一致 | 预览保留原 opaque 端口/绑定并追加 source inspection；正式编辑继续使用其 canonical source facts | 视觉交互不更改源码计算绑定，source inspection 不授予源码事务权限 |

适配生成标准：[adapter-generation-standard.md](adapter-generation-standard.md)。机器 Schema 为 `schemas/source-adapter-v1.schema.json`；独立运行时验证还会从完整绑定源码重建所有事实，不能只通过 JSON Schema 就注册。

## Agent 与 Skill 操作

源码树 Skill 应先从其目录运行：

```bash
python3 -I -B scripts/archcanvas_runtime.py doctor
python3 -I -B scripts/archcanvas_runtime.py capabilities
```

读取真实 `runtimeRoot`、版本和 capabilities 后再调用 `discover`、`adapter` 或 Studio。源码树 launcher 绑定正式 checkout；已安装的 beta.12 Skill 本轮没有升级，冻结包不会随源码目录修改自动更新，旧服务进程也不会自动加载新的 Python 模块。重新打包安装或明确绑定正式源码运行时后，需要核对 doctor 和实际服务 capabilities。不能将开发树的新能力表述成已安装 beta.12 的既有能力。

Agent 遇到 `adaptationRequests` 时，按标准生成并核对源证据，再验证、注册和预览。默认已有本地定义时也可查看自动检查子树。注册只保存已验证事实与标签/说明；伪造源码片段、hash、端口、依赖、循环或插件字段会被拒绝。注册目录与服务 data-dir 保持一致；HTTP 只接收用户提交的相对路径源码文本，不能传磁盘 root。

源码树 Skill 的最终复核通过 `skill-creator` 的 `quick_validate.py`；适配标准按需从 Skill 的陌生模型章节进入。已核对实际 CLI 字段、HTTP session token、配置匹配及 helper 的使用范围，并明确 `adapter preview` 的直接入口是模型类。最终源码箭头收据绑定新的共享依赖检查规则和 4 个有效注册定义；此前 4 个记录均显式为 `stale`，不会自动沿用。20 项注册单元测试通过，包含检查规则升级后的过期检测。另次 CLI 集成复跑通过，受当前沙箱限制的三项 loopback HTTP 测试记为跳过，不计为通过；真实服务验证另见最终服务证据。已安装目录与旧 release 未修改，也未宣称它们自动获得新能力。

所有显示和交互沿用迁入的递归预览技术，保留 Studio 顶部和左右面板、编辑/预览互通与统一保存导出入口。此轮不以新模型适配替换先前的布线核心。

陌生模块的深层折叠布局增加了各层基准视图，隐藏后代不再把全展开宽度留在已折叠容器里。同一依赖层的并列语句按有限宽度换行，仅改变显示位置，不创造顺序连接。ACTPolicy 第一层条件展开时，同一包的画面范围从 10574×768 收紧为 1199×974，15 个可见对象的源证据与连接绑定保持不变。新增回归检查源码/绑定不变、36 个独立语句限宽、手动偏移及收起重开恢复；陌生简单/条件/并列语句和既有 VAE、Transformer 的折叠、混合、全展开检查均无 source/layout/edge/contact 违规。

几何正确不等于深层交互性能已经完整通过。布局修复轮次中，ACTPolicy 深入到 43 个可见对象时，同步 `route + validateView` 实测约 11.4 秒；35 秒进程预算结束后的更深层未完成验收。浅层 12–27 对象约 118–216 ms。这组历史测量保存在 `docs/evidence/act-adapters-20261015/geometry/`。

后续通用性能修复修改了 `router.js`、`source-contracts.js`、`semantic-constraints.js` 与 `recursive-graph.js`：在同步事务的不可变源码范围内缓存源合同检查，每次候选仍独立检查实际端口及几何；可见性网格先按行列筛选可能相交的矩形，随后运行原有精确判定。线段接触的包围盒优化因短尺度反例被撤除，保留原始判定。没有减少候选、修改布线代价、删除边或放宽语义/碰撞条件。每条边的 ID、绑定、固定端口、策略、合同与投影均重新签名；authority、所有 variant 门与前沿状态在建立 context 时绑定，context 不允许跨源码/层级编辑复用。后者是事务不可变假设，并不声称同一 context 能检测 authority 原地修改。独立 ACT 路线差分、VAE/Transformer/ResNet 缓存开关差分、负例和更新后的测量见 [性能证据](evidence/act-source-support-20261015/routing-performance/README.md)。较深前沿仍可能需要数秒，不能写成所有场景已无卡顿。

## 后端验收结果与证据

目录扫描覆盖 `act` 的全部 20 个 Python 文件，识别 15 个本地模型类、15 个候选入口和 78 条带证据的源码关系；预算没有耗尽，`inventoryComplete=true`。动态配置、构造数量及外部实现仍有未知项，因此 **`hierarchyComplete=false`**。这里完成的是已提供源码的模型清单与可证明关系，不能称为完整运行包含层级。

15 个类分别通过递归预览和正式编辑静态打开，共 30 次。两个 Policy 的实际入口是 `__call__`；DETRVAE 的工厂、参数注入及本地 Encoder/Decoder 定义可以检查。两套图承担不同合同，节点数量不要求相同：

| 入口 | 预览节点 / 边 | 正式编辑节点 / canonical 边 | 正式源码关系 |
| --- | ---: | ---: | ---: |
| `policy:ACTPolicy` | 181 / 139 | 247 / 10 | 206 |
| `policy:CNNMLPPolicy` | 54 / 24 | 48 / 9 | 26 |
| `detr.models.detr_vae:DETRVAE` | 214 / 164 | 232 / 21 | 187 |

预览新增边仍是 `syntaxOnly` 源码值依赖；三项原始图的 10、9、14 条连接逐项保留。未知调用 tuple/list 解包保留整体来源并保持分析值不完整，已有赋值、算术、别名和 return 卡可显示实际 RHS 的使用。部分未知的局部 return 保留已证明的 tuple 槽，不把兄弟槽 producer 混接。23 项现有依赖正反例与只读审计均通过：ACTPolicy 的 `kl_divergence` 只接收 `latent_proj` 的源值关系，`F.l1_loss` 只接收 `action_head` 的源值关系，没有互换槽的箭头。条件和互斥分支没有被添加为张量生产者。

DETRVAE 的源码保留生成在当前依赖规则下重新完成两个闭环，见[新 summary](evidence/act-source-support-20261015/final-arrow-support/source-preservation/summary.json)：未修改草稿生成后源码字节、摘要和 IR 完全相同；将有明确字面量来源的 `is_pad_head.out_features` 从 `1` 改为 `2` 后，仅 `detr/models/detr_vae.py` 对应位置变化。两个副本均保留全部 20 个选定 Python 文件；修改副本重新分析，并经正式 Workspace 注册，源码与 IR 摘要一致。该维度编辑只证明静态源码闭环，不证明 shape、训练配置或实际运行正确。

本轮没有开放这些陌生动态模型的结构增删或连接重接生成。测试中即使旁路重连通过草稿连接检查，源码保留生成仍以 `unsupported-source-preserving-edit` 明确拒绝，原始分支与循环没有被省略。适配模块本身固定 `generationContract=null`。

四个真实数据适配模块按 `source-inspection/2` 重新完成 scaffold、独立重建验证、注册、从磁盘重开和预览应用；4 个新定义有效、4 个旧定义明确过期，原始边与源清单摘要保持不变。20 项注册单元测试覆盖伪造 span/hash/端口、依赖环、插件、过期源码/规则以及幂等覆盖。最终 `test_source_*.py` 定向检查共 79 项，75 项通过、4 项因 loopback 限制跳过；23 项依赖检查包含在其中，跳过项不计为通过。此前目录规则的 89 项检查属于历史定向轮次，不与本次数量累加。全仓库与浏览器验收由各自独立证据记录，不能用这些定向结果代替。

目录发现、适配注册及源码生成的收据都记录原 `act` 全部 74 个文件的集合、内容 SHA-256、大小与纳秒修改时间不变；没有导入、实例化或运行模型。规则还用陌生名称、跨文件继承、局部工厂、共享实例、方法替换、无效签名、独立返回槽等正反例核对，避免为了覆盖而猜测结构。

证据目录：

| 证据 | 位置 | 当前用途 |
| --- | --- | --- |
| 目录发现、双解析器矩阵、只读清单 | [最终箭头收据](evidence/act-source-support-20261015/final-arrow-support/receipt.json) | 当前全部 30 次静态打开通过；绑定 7 个实现/Schema 文件与 74 文件只读清单；旧 `discovery-final-verification.json` 保留历史 |
| 保留源码与字面量编辑、managed copy 重新分析 | [当前生成 summary](evidence/act-source-support-20261015/final-arrow-support/source-preservation/summary.json) | 当前收据绑定 11 个实现文件；全部 20 个 Python 文件保留，精确字面量编辑和 Workspace 重分析一致；旧 source-preservation 目录不替代本次结果 |
| 数据适配与正反例 | `docs/evidence/act-source-support-20261015/final-arrow-support/registry/` | 当前 4 个定义已验证、保存、重开并应用；旧 `act-adapters-20261015/registry` 的 4 个记录明确 stale；中间目录不是有效 registry |
| 返回槽与未知值的只读复核 | [slot review](evidence/act-source-support-20261015/final-arrow-support/readonly-slot-review.json) | 现有 23 项依赖正反例复跑通过，已知槽和部分未知槽不跨接；当前 ACT 两项消费者的实际来源与源码一致；补充绑定 source_dependencies 与新生成 summary |
| 深层布局、陌生树与既有模型回归 | `docs/evidence/act-adapters-20261015/geometry/` | 三项新增前端回归通过；此目录的初始几何记录早于四个核心文件的后续性能修改，当前实现以 routing-performance 收据为准 |
| 四个核心文件的性能与精确路线差分 | `docs/evidence/act-source-support-20261015/routing-performance/` | 各次测量独立绑定 `router.js`、`source-contracts.js`、`semantic-constraints.js`、`recursive-graph.js`；撤除接触剪枝前的计时属于中间实现，最终绑定另列 |
| 前一轮后端只读与 SHA 核对 | `docs/evidence/act-source-support-20261015/final-readonly-backend-audit.json` | 历史检查早于最终源码箭头规则；本次以后端新收据和 slot review 为准，不沿用旧适配身份或依赖数量 |
| HTTP/CLI 与交互 | `tests/test_source_adaptation_http.py` 及最终保存输出 | 真实服务与代码 hash 必须一致，不沿用旧端口历史成功作为本次证明 |

## 最终 Studio 与真实界面复核

最终集成收据：[verification.json](evidence/act-source-support-20261015/final-integration/verification.json)。完整 Studio suite 为 783 项，782 通过、0 失败、1 项沙箱跳过；跳过的真实 Chromium 出版检查已在同一实现 SHA 下单独 3/3 通过。TypeScript 与 Vite 构建成功；真实 HTTP 检查 5/5、源码保留检查 7/7 通过。迁入预览的 19 项集成 manifest 与 public、dist 的 SHA 和大小一致。上述结果分别保留日志，不把不同轮次计数相加，也不把未完成的全仓库 Python suite 记作通过。

用户报告的“内部没有箭头”包含两类缺口：赋值、返回与不完整 tuple/list 的源码来源没有完整投影到检查子树；条件与互斥分支缺少解释关系。前者补充源码值依赖，后者采用独立的条件关联叠层，明确标注“非张量”。不添加仅按语句顺序排列的假数据边，也不把 if/else 串联成执行路径。

[最终 ACTPolicy 视图](http://127.0.0.1:8894/?documentId=canvas-architecture-policy.ACTPolicy-f618087ae2e7-880985a9)在保存刷新后仍有 **8 条紫色源码依赖、2 条棕色条件关联**，当前全部 18 条原有/投影边合法，源码与布局检查均通过，条件路由零诊断。独立返回槽核对保持 `latent_proj → kl_divergence`、`action_head → F.l1_loss`，不会把两个输出交叉连接。截图见 [training-arrows-reloaded.jpg](evidence/act-source-support-20261015/browser/training-arrows-reloaded.jpg)。这是最终规则重新分析后保存的新文档；旧规则下已保存的历史图不通过静默改写来迁移。

条件关联使用统一的路由与障碍检查，覆盖文字、附件与分叉；没有合法路线时显示诊断。路由仅在事务提交后刷新，渲染和图例读取不重新布线。源码依赖采用独立短虚线样式并保留用户覆盖。导出移除纯编辑属性、保留箭头与图例，通过原有后端校验。当前 ACTPolicy 真实 PDF 已生成：[文件](evidence/act-source-support-20261015/final-integration/act-training.pdf)、[收据](evidence/act-source-support-20261015/final-integration/act-training-export-receipt.json)。其 180 mm 整图预检最小文字约 2.39 pt，建议约 527 mm 或较小详情范围；没有宣称该整图已达到论文阅读尺寸要求。预览绑定摘要由浏览器声明，出版收据的 `sourceBindingVerified=false` 保留，不把导出几何校验解释成独立源码语义认证。

最终规则的 [DETRVAE 独立副本](http://127.0.0.1:8894/?documentId=canvas-architecture-detr.models.detr_vae.DETRVAE-b62d78c1447f-2daaf3d4)已真实完成 `is_pad_head.out_features` 1→2、源码审阅、正式注册、新预览、保存刷新、重进编辑，并显示参数 2。存储侧核对 20 个 Python 文件完整保留，仅 `self.is_pad_head = nn.Linear(hidden_dim, 1)` 对应字面量变为 2，见[存储核对](evidence/act-source-support-20261015/final-integration/generated-copy-storage-verification.json)。这项静态编辑不证明修改后的输出维度适合原任务。

原始导入草稿及生成后的完整编辑会话使用 IndexedDB，按文档、源码与 IR 身份隔离，恢复后保留选择、相机、历史与前沿；异步恢复前不写入空状态，损坏或失配缓存不覆盖原草稿。真实界面另验证了原始源码草稿参数 3 保存刷新后仍恢复，并随后还原为 2；只改变独立草稿。最终只读审计确认原 act 的 74 个文件集合、SHA、大小、纳秒修改时间全部不变。

## 必须保留的限制

这是一套不执行模型的静态工作流。已提供的本地源码可以检查和显示；动态训练/推理分支、shape、dtype、广播、数值行为和运行兼容仍未验证。`act` 的外部 torchvision/IntermediateLayerGetter 实现没有提供时继续保留未知边界，不能用预设猜补。ACTPolicy 和 DETRVAE 的源码检查各有三个包含深度预算截断；12 层/节点预算截断必须显示，不能把“类已列出”表述成“全部内部结构已恢复”。

宽泛来源不代表独立 tensor 返回槽。纯别名透明传播；下标赋值卡可显示 RHS 来源，但任意 dict mutation、别名副作用与变更后返回槽尚未恢复。ACTPolicy 的 `loss_dict['loss']` 和最终 dict 返回因此仍有未证明的内部关系，不能把增加源码箭头写成整个训练分支计算语义已恢复。

源码副本复制选中的 Python 文本；权重、数据、配置资源、环境依赖、许可证上下文以及其他非 Python 文件不因此自动迁移。生成后的静态核对和新预览不证明副本可以在没有原项目资源/环境的机器上运行。

来源模型有未知区域时，结构性编辑仍必须有独立生成合同。保存视觉草稿、调整样式和显示结构可以完成；它们不能代替计算语义证明，也不能为了让“生成”按钮通过而丢弃用户的拓扑修改。
