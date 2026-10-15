# Agent 生成新源码结构适配：实现与验证

本次补足了「只保存旧解析器事实」的缺口。Agent 可以依据实际源码编写 `archcanvas-source-rule/1` 声明式 AST 模板；独立解释器选取真实表达式、检查包含关系和依赖证明，生成 `archcanvas-source-adapter/2` 绑定实例。注册同时保存模板与实例。新源码通过保存的模板重新匹配和验证，不复用过期实例事实。

生成标准为 [adapter-generation-standard.md](adapter-generation-standard.md)，源码树 Skill 同步了相同规范与操作流程。开发实现与已安装的嵌入式 Skill 是独立版本；本次未更新 `~/.codex/skills/archcanvas` 的 beta.12 安装包。

## 实现范围

- 模板匹配有限 AST 类型/字段，选择真实子表达式，描述内部层级。`expression-input` 证明直接读取操作数；`comprehension-iteration` 检查 generator 变量在输出表达式中的真实词法读取。作用域遮蔽、未读取变量、互斥分支和短路条件均保留边界。
- 模板身份由内容确定，与模型名、文件名、变量名和当前源码 hash 分离。绑定实例记录完整源码集合与摘要、入口/方法/config、精确 AST 行列及原文。修改源码使旧实例失效，但模板可以重新绑定。
- 模板和实例通过 CLI/API 验证、注册、列出、加载；CLI/API 合并重复模板。注册普通失败回滚全部记录。一个模板匹配失败不抑制其他合法模板和原图。
- 同一入口的不同 config 或显式非默认方法实例不会阻止模板对当前配置和默认方法重新绑定；加入两项先失败、修复后通过的复用回归。
- 新结构接入原有 Summary_Merge 递归引擎。复用精确对应的旧源码卡片，保留原始节点、原始连接、语义绑定与源码摘要。新增箭头是有证据的源码依赖；同一依赖不重复绘制。分支卡片共享 If span 时，按真实 AST 分支体约束挂接。
- 规则显示名使用独立展示覆盖，不改写复用卡片的规范事实；新内部对象可选择、展开/收起、移动、撤销/重做、保存重开和导出。

## 真实项目与跨源码证据

测试根目录为 `Constraint relationship of architecture diagram/act`。原始 74 个文件的集合、字节数、SHA-256 和纳秒修改时间与上轮基线及本轮前后快照完全一致。读取 20 个 Python 文件；未 import、实例化或执行模型。发现结果仍为 15 个模型/模块类。

Agent 为真实 `_get_clones` helper 编写了通用 ListComp 操作数规则，没有修改共享解析器，也没有加入 act 或模型名称分支。

| 入口 | 新增内部卡片 | 新增源码依赖边 | 说明 |
| --- | ---: | ---: | --- |
| `policy:ACTPolicy` | 3 | 1 | 3 处应用，深层两处达到 12 层预算并在收据中标记截断 |
| `detr.models.detr_vae:DETRVAE` | 9 | 3 | 3 处克隆定义均补充 `range(N)`、`module`、`copy.deepcopy(module)` |
| `policy:CNNMLPPolicy` | 0 | 0 | 没有匹配的 helper；原图保持原样且无伪造补全 |

`_get_clones` 的循环变量 `i` 未被输出表达式读取，因此没有虚构 `range(N) → deepcopy(module)` 值依赖。新增的是源码实际读取的 `module → deepcopy(module)`。循环次数、运行路径和张量形状仍未知。

同一模板又在独立 `relocated:River` 源码中自动重新绑定；旧实例因源码不同被正确拒绝。另一位 Agent 只依据标准独立编写 DictComp 模板，成功补充 4 个内部节点及 3 条源码关系，跨文件/类名/变量名复用并拒绝不读取 generator 的反例。两份正例含顶层 RuntimeError 哨兵，静态流程均通过，证明没有执行模型。

收据、模板、绑定实例、原始/新预览和独立复测位于 [evidence/agent-source-rules-20261015](evidence/agent-source-rules-20261015)。

## 界面验收

在隔离状态目录 `/tmp/archcanvas-agent-source-rules-20261015` 启动正式服务，端口 8895；既有 8894 文档和历史保持原状。通过会话鉴权 API 注册真实规则，再通过 managed-project preview 自动应用。

陌生 River 模型在真实 Studio 中完成：展开内部节点及依赖箭头、选择属性面板、重命名为「变换集合」、撤销/重做、统一保存、刷新恢复、视图/编辑切换、按最终字号预检调整页宽并导出 SVG。前端测试另覆盖实际节点移动、收起再展开及 JSON 重开后的局部布局恢复和伪造绑定拒绝。

真实 DETRVAE 界面逐级展开到 Encoder 循环 → ModuleList → ListComp，显示 `range`、`module`、`copy.deepcopy` 和已证明的操作数依赖，选择新节点后可查看属性与精确源码位置；保存、下载编辑 JSON、刷新后均保留展开状态。下载图为 52 个可见节点、52 条边，源码、布局和全部连线校验通过。记录见 [studio-deep-expanded-receipt.json](evidence/agent-source-rules-20261015/studio-deep-expanded-receipt.json) 和 [界面截图](evidence/agent-source-rules-20261015/studio-act-rules.png)。

这次实测还发现并修复了应用加载器丢失分层布局数据的问题：导入包生成 12 个深度视图，但应用只按概览/细节两个菜单项重建 authority，使深层展开产生通道重叠并被正确拒绝。现在保留完整 12 个视图，展示版本升级到 8，旧缓存重建几何时保留展开选择、手动布局和显示名；没有放宽重叠约束。实际旧浏览器导出图迁移后，先前失败的循环展开及严格连线校验均通过。

验证视图：[River](http://127.0.0.1:8895/?documentId=canvas-architecture-relocated.River-73f85ac1b4d7-2a637c23)、[DETRVAE](http://127.0.0.1:8895/?documentId=canvas-architecture-detr.models.detr_vae.DETRVAE-f618087ae2e7-0c05186b)。

## 最终检查

| 检查 | 结果 |
| --- | --- |
| 规则解释器、v2 注册与原子写入回滚 | 58 / 58 通过 |
| v1 适配兼容 | 20 / 20 通过 |
| 实际本机 HTTP 适配流程 | 8 / 8 通过，无跳过 |
| 预览后端 | 13 / 13 通过，无跳过 |
| 模型发现 / 源码检查结构 | 17 / 17、4 / 4 通过 |
| Studio 全量前端 | 784 通过，0 失败，1 跳过 |
| 应用完整分层加载、旧缓存迁移、真实浏览器旧图展开 | 3 / 3 通过 |
| TypeScript / Vite 构建、Skill 格式、diff whitespace | 通过 |

前端唯一跳过项是需要启动 Chromium 的 DOM SVG 清理检查，当前命令沙箱禁止其启动；真实浏览器已另行完成当前规则场景的交互与 SVG 导出，不将其算作该项自动检查通过。全量回归首次因真实 AST fixture 的实现 hash 已过期失败；重新用正式非执行解析器生成 fixture 后，核对原图 IR、节点/边和来源身份未变，再运行全量回归通过。检查日志及当前实现 SHA-256 记录位于本次 evidence 目录。

## 边界

这是可积累的源码结构适配能力。它不为新节点授予张量端口或模型生成契约，不将未知运行关系转换成确定的计算流。超出有限规则语言/证明类型的语义仍需要单独扩展解释器合同。未知外部依赖的内部实现无法从未提供的源码恢复。任意结构修改后的 Python 生成与运行验证仍是独立能力；现有保留源码拓扑和已支持字面量参数修改流程继续保留。

本轮后端分析仍有秒级成本：本机 act 原始预览约 4–5 秒，新规则重新绑定约 0.3–1.7 秒。深层大图布线仍可能耗时十余秒，本次没有完成性能验收。规则新增的视图对象只在现有递归展开路径参与布线，不能据此宣称任意大型图性能已通过。
