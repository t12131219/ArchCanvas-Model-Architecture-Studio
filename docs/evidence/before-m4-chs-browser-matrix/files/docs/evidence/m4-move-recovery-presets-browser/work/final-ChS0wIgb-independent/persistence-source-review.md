# final-ChS0wIgb 文件与来源独立复核

范围仅为新冻结目录的 rev17 保存/重开/SVG 导出、随后 rev18 单个已固定对象拒绝状态，以及紧凑 CNN 草稿/生成源码。未操作浏览器、服务、产品或原始证据；未查看 PNG。历史 session-2 未混入新 build。

- movement 冻结 envelope 与实际 `.archcanvas/m4-move-recovery-presets-browser-2` 保存文件字节完全一致：存储 revision=2、文档 revision=17。嵌入源码字节 SHA、source 集合 digest 与 IR digest 重新计算均对应。
- saved/reopened/export-dialog 的 public SVG 字符串完全一致，20687 字符；pins 为一个明确 ID，别名为“首层·可修复”。8 个 sourceFacts 与 6 个 renderedBindings 的逐字段来源对应成立，源标签仍为 Linear 1。
- 导出 document 全对象等于保存 document；导出三文件与 receipt 指向的实际存储文件字节相同，输出摘要和 bytes 对应。但 receipt 的 inputSvgDigest/sceneSvgDigest 为 `5dfa9535…`，captured public SVG UTF8 SHA 为 `58b0cb64…`，两项输入字节绑定不成立；没有原始 pre-export input SVG，未推断原因。导出 SVG 与画布 SVG 非字节/全 XML 完全相同：高度精度、交互属性/容器详情控件、×4 文本横坐标及端口包装变化完整保留在 JSON。metadata、节点主体 rect、别名、6 组连线及 11 个可见端口圆坐标/样式一致，透明 hitcircle 已删。
- pinned refusal 从 rev17 到 rev18，XML 只有 root data-revision 与 metadata revision 两处变化；其余树完全相同，DOM 保留别名及“取消固定位置”控件并有拒绝 footer。没有 rev18 envelope，public 不含 pinnedObjects，因此未认证完整 post-refusal pin 数组或历史内部状态。
- compact CNN 冻结 envelope 与实际 draft 保存文件字节完全一致，8 模块/7 连接、draft/storage revision=1。独立 AST 静态检查核对 6 个模块构造参数、输入/输出命名及 7 条源码连接；observed/generated 的 public SVG ID 和节点位置对应草稿。生成 modal 的 public 文本含完整源码。未提供独立 generated IR 或 compact CNN export copy；没有运行产品核验或模型执行。

绑定 33 个原始输入，末复核全部未变化。详细字段、完整 XML 差异、原始 bytes/SHA 和限定见同名 JSON；发现的 whole-export XML 差异与 post-refusal 完整 pin 缺口均未消除。

本复核只建立记录及文件内容对应，不认证采集方法/时序、保存操作链或重启/故障持久性、模型 runtime、全部固定压力、像素/字体/物理阅读效果或人类验收。此前 discovery 读取早于绑定；本脚本的 first hash 早于 audit parsing。
