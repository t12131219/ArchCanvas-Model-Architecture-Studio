当前修复把源码导入与预设目录分开：不在预设中的模型、算子和组合模块仍可显示、进行展示编辑并保存。模型名称不参与结构猜测，真正无法确定的源码仍显示为 opaque 边界。

源码分析新增直接辅助方法、模块变量、模块参数传递、单个 return 表达式的有界工厂、精确 `copy.deepcopy` 独立实例以及严格限定的标准参数初始化合同。带副作用、被替换或装饰的方法、未知模块突变和动态分支继续保守处理。增加正例、反例、实例共享、字典输出和不执行源码的测试。

纯展示编辑现在通过原始来源 ID 将显示名、样式、位置、尺寸及连接点投影回同一 CanvasDocument，使用相同类型操作和撤销历史。未知算子不再因改名或移动而被送入不支持的 Python 生成流程。隐藏子模块的位置保留到重新展开；语义修改仍进入独立验证流程，不能静默当成展示修改。

修复大模型保存容量阻断：真实原版 Transformer 的编辑草稿为 5,593,804 字节，旧 4 MB 草稿预算无法保存。源码编辑接口与草稿现在使用 16 MB 有界预算；画布保持 4 MB 存储预算，其撤销快照共享一份不可变架构事实，重开时恢复并校验完整事实。真实 Transformer 五个历史快照的保存文件为 1,148,857 字节。新增 800 余节点、陌生名称模型的真实 HTTP 导入→保存→重开测试。

补充真实 PatchTST 浏览器 JSON 往返检查发现 `attn_dropout=0.0` 会被 JavaScript 写为 `0`，旧源码证明哈希因此拒绝保存。现在源码证明按 JSON 数值一致性计算，原始源码和 IR 标识不变；真实数值变化、布尔值或字符串替换仍被拒绝。历史 Python 格式的证明仍可按原字节验证。新增陌生模型的实际 Node JSON 往返、保存重开与篡改反例，真实 PatchTST 的展示编辑、保存重开、撤销重做和 SVG 导出已通过。

真实源码检查结果：原 Transformer 为 804 节点/770 边，294 节点仍为未知边界；可识别 Encoder/Decoder 的层和重复实例，编辑导入、保存重开通过。PatchTST 为 4 节点/3 边，configs 未提供导致条件路径保持未知。不能据此声称任意 Python 的完整恢复、任意结构生成、形状推断或模型执行；未进行真人、出版尺寸和三宿主认证。

实际浏览器检查使用独立临时状态根打开 `UnseenSpectrum`：编辑未知 `mystery_transform` 为 `External operation`，将 X 从 80 改为 112，切回视图未创建新模型；保存、刷新后同一 documentId 仍保留名称、坐标和撤销记录。再次编辑→视图保持 X=112 与视觉版本1。PDF 导出完成，模型源码保持原字节。截图和产物位于 `docs/evidence/source-generality-20261010`。

补充 beta.7 内嵌运行时的实际 PatchTST 浏览器检查：将 `ConditionalRegion` 的显示名改为 `Configuration-dependent region`，X 从 80 改为 112，草稿保存成功，切回原 documentId 后保存画布成功。刷新后名称、X=112、视觉版本1和一次画布历史均保留，原始源码文件逐字节哈希不变。截图为 `docs/evidence/source-generality-20261010/patchtst-reopened.png`，完整保存文件和收据一并归档。临时服务与本轮页面已关闭。

标准 `candidate` 打包生成独立 staged manifest 并验证当前资产，冻结的 Beta.2 历史清单和归档保持原样。历史包测试与当前候选测试分别验证具体资产，未通过忽略 artifact 错误来伪造成功。已安装全局 Skill 为 `0.1.0-beta.7`，完整安装校验通过，doctor 为 `ready-local`、`releaseIntegrity=verified`；从安装入口独立分析原 Transformer 仍为 804/770/294。归档 SHA-256 为 `f297a698b00da99f5671785fec7a66c5ddafc9c73c67ee2b804ddfd1cab60735`。

最终当前实现的后端完整回归为 **451/451**（401.375 秒），前端为 **590/590**（219.614 秒），无失败、跳过或取消。TypeScript/Vite 构建通过。源码证明修复后，产品前端和构建资产未变；最终候选的 `src`、`studio/src`、`studio/dist` 和 Skill 共 126 个文件与当前 checkout 字节一致。336 个源码、测试、脚本、Skill、配置及 fixture 输入均已冻结哈希，完成回归后没有变化。完整日志、安装收据和证据清单见下方 summary。

`scripts/rollback_archcanvas_generality_20261010.sh` 只回滚全局 Skill，默认恢复本轮开始的 beta.3，并保留被替换版本。也可显式传入 `/tmp/archcanvas-global-beta4-before-beta6-20261010` 或 `/tmp/archcanvas-global-beta6-before-beta7-20261010`；已在独立临时路径验证恢复和候选保留。开发源码尚未提交；`/tmp/archcanvas-generality-before-20261010` 是部分原文件备份，`/tmp/archcanvas-source-import-before-json-number-fix.py` 保存最后的数值修复前文件，不能把这些描述为完整 checkout 自动回滚快照。

最终完整回归、候选版本、安装哈希和当前源码哈希以 `docs/evidence/source-generality-20261010/summary.json` 为准。此前审计和复核报告保留其历史时间点。
