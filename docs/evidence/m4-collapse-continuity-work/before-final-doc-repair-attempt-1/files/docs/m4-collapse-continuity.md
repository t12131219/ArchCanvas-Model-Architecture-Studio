# M4：直接折叠祖先后的空间连续性

当前为**源码实现完成、验收进行中**。本轮只修改正式工程的 `studio/src/core/document.ts`；统一 target、完整套件、构建与实际浏览器证据尚待 root 补齐。M4仍partial、真人0、M5未开始。

CNN 在展开 Repeat 和两个 ResidualBlock 后，直接收起 Repeat 会回到概览，但 pool 仍停留在详细视图的位置，留下1607世界单位的可见轮廓空隙。原因是布局缓存使用全部 `expandedIds`，其中包括已隐藏子层；实际画布只沿展开祖先显示后代，因此相同可见概览查询了一个新的、从未保存过的缓存键。

实际旧文档为 rev14：pool localY1938，已有 root-only 快照 localY362。公开 SVG 的 Repeat 完整轮廓（含两层背板）bottom423、pooltop2030，gap1607；前 body rectangle 单独 bottom416，body gap1614。根据已有快照的坐标差，恢复后预期pooltop454、轮廓gap31；这是冻结旧快照的独立期望，目前不代表已完成浏览器恢复。

实现按**有效可见展开集合**存取布局：容器只有在所有祖先展开时才进入缓存键。所有隐藏子层的展开标记和局部布局继续保留；直接重新展开祖先可恢复原详细层级。新键使用带前缀的JSON数组，避免新缓存以`|`分隔任意节点身份，CanvasDocument字段与schemaVersion保持原合同。

新快照只保存当时可见节点的坐标，恢复只触及目标可见节点，并保护操作节点、其祖先锚点和固定子树。隐藏层级的局部坐标不会被概览快照覆写。已有手动move仍同步到各旧/新快照，所以展开和折叠保留用户的平移调整。只切换隐藏后代的展开记忆时，可见位置保持原样。

旧键仍可读取，优先精确有效键；多个旧隐藏状态键投影到同一可见层级时，只有可见坐标一致才采用，冲突时保留当前布局。读取器枚举符合旧排序拼接规则的合法完整分段，包括节点身份内部的`|`；只有恰好一种解释才采用。`root|Ω`若只有完整身份合法则可读取，`a|b|root`若同时表示`{a|b,root}`和`{a,b,root}`则不可用于恢复。解析预算为20000步，预算耗尽保持当前布局。Canonical刷新也能读取新JSON键，并按既有身份保留规则处理快照。

已经伸长的旧collapsed文档不会在打开时静默修改。其已有紧凑概览快照不会被当前伸长布局覆写，后续显式展开→折叠可利用该快照恢复。任意手写JSON若把当前坐标和缓存改成彼此冲突，缺少更新顺序证据，不能承诺自动修复；没有可信快照时也不会清空布局或全图重排。固定造成的冲突须保留并显示既有诊断，不移动固定对象来隐藏问题。

此修复从正式工程现有独立合同与实际失败证据编写，未读取、迁移、导入或调用失败原型Temp。前状态 [109文件快照](evidence/m4-collapse-continuity-work/before-implementation-attempt-1/manifest.json) 保存正式源码、Studio源码/测试、当时dist/config及修复合同；输入前后与副本 exact。诊断的 [22个输入副本](evidence/m4-collapse-continuity-work/diagnosis-attempt-1/diagnosis.json) 与 [公开轮廓补充](evidence/m4-collapse-continuity-work/diagnosis-attempt-1/outline-supplement.json) 另行冻结。

源码初次实现、合法literal旧键修正和组合分段歧义修正的before/after均保留。[实现说明](evidence/m4-collapse-continuity-work/implementation-review.json) 对应第一次实现；[首个reader修正收据](evidence/m4-collapse-continuity-work/reader-repair-attempt-1/receipt.json) 对应后来Bf版本；[组合分段修正收据](evidence/m4-collapse-continuity-work/reader-composite-repair-attempt-1/receipt.json) 对应当前源码20013bytes、SHA256 `c3fa2e7a0410a4ab15ea01b97280429558f5309e36e7e88992045f2776d484e1`。28个关键Bf source/dist/check/witness输入另行冻结，历史失败记录不被新结果覆写。

独立验收由另一Agent编写，期望来自手写compact/deep局部坐标与冻结actualCNN，未用新产品输出生成expected。预修复8项中2通过/6失败，覆盖旧版遗漏的直接祖先折叠链；后续12项包含隐藏记忆、手动移动、固定、undo/redo、JSON往返、旧快照与身份分隔碰撞。初实现12项为11通过/1失败（literal旧键），随后root目标运行还有一项夹具可选字段在JSON往返后的差异，修夹具保留失败原件。组合旧键歧义由独立审查另行复现：旧缓存将output从独立期望262错移到700；第13项固定该literal期望，当前reader修复待root统一重跑。**最终target、完整套件和严格构建尚未在此文档认证通过。**

实际浏览器仍需在新build上通过普通操作复现直接Repeat折叠、重新展开、局部移动、undo/redo、save/reopen以及同revision导出，并检查完整轮廓、文字与连线。旧单色矩阵仍属于旧build，不能继承为新布局验收。该功能也不认证出版物理尺寸、实际呈现性能或真人研究任务。
