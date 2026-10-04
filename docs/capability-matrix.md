# 首批真实能力矩阵

状态以 2026-10-04 正式目录代码和已记录命令为准。`通过` 表示有独立实现和可复核检查；`未认证` 表示不能作为支持承诺。

| 能力面 | 当前状态 | 真实边界与证据 |
|---|---|---|
| 运行入口与来源 | 通过 | `archcanvas_cli` / `archcanvas_python` 从正式目录 `src` 解析；`check_independence.py --build` 的 `/tmp` 报告检查 module origin、capability receipt 和发行源字节 |
| 静态源码分析 | Alpha 通过 | stdlib AST 子集；显式本地模块、字面量构造、模块层级、producer/consumer、具名 MHA 端口、tuple 输出、残差、bounded repeat/shared identity |
| Transformer gold | 通过 | 独立人工 oracle；多输入、self/cross attention、mask、7 个残差、2 个独立 Encoder layer、无源码 Softmax |
| MLP / Residual CNN gold | 通过 | fixture 源码与关系测试通过；没有把 fixture 快照当作泛化保证 |
| 未知与动态结构 | 有界 | 动态控制、反射、未知 constructor、继承 forward、预算截断保留 opaque/diagnostic；不伪造 proven 关系 |
| Runtime execution / shape | 未实现 | 不 import 或执行用户模型；没有运行 shape、dtype、参数值或训练状态证明 |
| CanvasDocument | 通过 | source/IR digest、canonical identity、display alias、节点/边样式、图例、注释、页规格、layout、pin、expanded frontier |
| Visual history | 通过 | 手势和当前局部确定性视觉指令共用 VisualOperation、undo/redo 和 document revision；没有通用 LLM 语言解析 |
| 层级展开 | Alpha 通过 | 同一 scene projection、proxy ports、局部布局和 pinned 保护有 core tests；真实浏览器 Encoder 展开保持原位，完整三级/任意模型空间连续性仍待验收 |
| 保存与冲突 | 通过 | loopback server JSON CAS；storage revision 与 document revision 分离；immutable architecture/source binding；root 允许 loopback 环境 HTTP tests 通过，浏览器 alias 保存与刷新重开已实测 |
| SVG | 通过 | 当前 scene 的单一 SVG renderer，转义用户文本，publication 默认不含 editor controls；保存后本地导出及 XML/编辑内容验证通过。内置浏览器下载事件未认证，85/180 mm、字体与黑白人工审看待完成 |
| PNG / PDF | 未实现 | 不提供入口，也不以 SVG 成功冒充位图/PDF 能力 |
| 参数 / 连接写回 | 未实现 | 无 semantic transaction、CST diff、独立再分析、approval/stale/journal 提交接口 |
| MCP adapter | 未实现 | Skill 文档描述合同，不存在可调用 MCP 工具 |
| Codex / Claude Code / DeepSeek Harness | 未认证 | Skill 指令包与引用已整理；三宿主 discovery/open/edit/save/export E2E 尚未实测 |
| Publication quality / performance | 未认证 | 没有固定浏览器/字体/DPR/研究者任务的视觉或 p95 性能证据 |

静态分析通过只说明支持子集的源码事实可恢复；它不把“节点显示出来”提升为任意模型支持，也不把 opaque 区域变成可编辑源码。参见 [source oracle](source-oracle.md) 和 [acceptance ledger](acceptance.md)。
