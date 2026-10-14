# 证据索引与边界

日期：2026-10-12（Asia/Shanghai）。目标是用户指定的 Layout Styles URL；本地参考由用户指定为 `Source_Code_Project/yfiles-for-html-demos-master`，package version 31.0.3。

## 三类证据

1. **SOURCE**：`source-findings.md` 使用本地 JS/GraphML 的准确行号。商业 yFiles 实现不在该 demo 源码中。它能证明调用与配置，不能证明内部搜索算法。
2. **RUNTIME-CUA**：`runtime/` 中的浏览器 DOM、SVG 路径、节点矩形和 PNG；由 Codex CUA 浏览器读取及操作取得。这些不是 REA passive CDP Evidence。当前 IAB 没有向 CLI 提供已知 CDP endpoint，因此没有冒充 REA runtime capture。
3. **REA-STATIC**：使用已缓存 `rea-agents@6.4.0` CLI，对网页实际加载的公开 bundle 进行惰性解析。完整 JSON 和摘要均保留。

## REA Evidence

- `rea-bundle-analysis-4096.json` / `rea-summary-4096.json`：`ev_e8fd15b6141aff7b272fd1f1d218ece67ef7e2f43920d2825b6fd09156698074`。完整 bundle application 与 semantic coverage 均 partial（semantic worker heap limit）；33 findings 不能解释未收录模块。
- `feature-slice-provenance.json`：Babel AST 精确提取 `PolylineEdgeRouterConfig` CallExpression，保留 bundle SHA-256 与 UTF-16 `[146042,162887)` 范围；添加 `export default ` 前缀/`;` 后缀仅用于惰性模块解析。没有重命名，也没有执行代码。
- `rea-feature-analysis.json` / `rea-feature-summary.json`：`ev_1a31619286f805078d140b74d0de1fb07fd245eb9c4ad93d286a3cac5effc5a9`。片段 application syntax inventory complete，semantic graph **unknown**（外部 minified bindings 等 463 个 unknown）。包含 1261 semantic nodes / 725 relations，关系是静态保守候选。
- `rea-feature-anchors.json`：从上述 REA 输出选择 `write:/rerouting`、`write:/intermediateRoutingPoints`、两个 portCandidates 写入节点，附原 bundle 对应范围。锚点存在是观察；不意味着所有分支都执行过。
- `rea-bundle-analysis.json`：最初 sandbox worker startup failure 的 partial Evidence `ev_d510b5f507568728b152c2a2ff6c5052b701d87b5a67b0a06c9b4bfb05e8ea88`；已经恢复，不能作为完整分析。
- `rea-bundle-analysis-full.json`：默认 1 GB 堆下 partial Evidence `ev_d72fe62698bd1015f38e49edc612fd31a4b9c0b74b246fbb6ca71d2b6a5e292a`。提高 4 GB 后仍受限，所以缩小分析边界而没有继续盲重试。
- `rea-doctor.json`：当时 MCP 未注册；没有改用户 Codex 配置、安装分析引擎或执行 yWorks bundle。

## 运行时观察

- `original-orthogonal.png`：原始 Default 图；箭头与正交路径可见。
- `general-settings-dom.txt/png`：All/Selected/Incident scope、rerouting、Keep Bends、Always policy、Any port sides 的原 UI。
- `original-curved.png` / `curved-paths.json`：Curves 后平滑外观。SVG 最终采用 L 线段采样，而不是 C/Q 曲线指令；最初路径快照含箭头闭合 paths，所以条目为122=61 edges+61 arrows。
- `restored-orthogonal.json` 与 `curved-geometry.json`：严格过滤 stroke 与 fill 的61条边，分别保存16个 node rect。节点属性一致，45条路径改变，L 指令从111到732。
- `original-left-right-octilinear.png` / `left-right-octilinear.json`：左右端口预设和 Octilinear。
- `before-node-drag.json`、`after-node-drag-*`、`selected-node-moved-before-apply.*`、`node-keyboard-moved-before-apply.*`：**未成功改变节点几何的手势尝试**。这些文件的名字仅是操作意图，不能视为移动成功证据。端口预览/选择 transient paths 导致一度62条路径。原始 showcase 节点移动后的自动/显式 route 差异，本次结论来自本地事件注册源码；没有谎称该手势已被在线观测证明。

## 原型验证

`verification/` 是独立实现的浏览器操作快照，不用于证明 yWorks 行为。原型通过几何独立 oracle、端口侧/固定端口、自环、途经点、不变式测试（`tests/router.test.cjs`），以及创建/重接端点/折点/箭头/作用域/撤销等实际 UI 操作。曲线采用二次 Bézier 圆滑，八方向采用安全 chamfer，是复刻设计选择，不是对 yFiles 内部算法的还原。

`verification/checks.json` 记录11项通过的验证，当前几何测试为12项。SVG 下载等待超时；导出按钮和序列化实现存在，但未断言下载文件已成功交付。`verification/report.png` 为报告实际渲染截图，`verification/prototype-final.png` 为首次交付的实验页截图。

## 转角缺陷修复验证

用户截图指出拐角有突出的小线段。将 Source 移到约 (271,449) 后的旧算法能产生目标端口短线折返，例如 e10 的 `(161.2,492.88) → (161.2,490) → (161.2,518)`。搜索状态从无符号轴改为四方向，并检查两端 stub 方向后，禁止这类即时折返。`verification/turn-spur-fixed.json` 保存浏览器实际修复路径；其11条边均无共线反向折返。`turn-spur-fixed.png` 为完整页面，`turn-spur-fixed-detail.png` 为相同截图的局部裁剪。此验证属于原型，不用于证明 yWorks 行为。
