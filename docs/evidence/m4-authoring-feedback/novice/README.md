# 模型搭建反馈：独立 AI 只读复核

当前最终 `index-BcFxpKDY.js` 范围内，三项原 P2 在实际浏览器样本中均已有可审查修复：自动排版后四模块全见、重复显示名错误准确定位下游 Linear 并显示中文字段/端口提示、缺失模块搜索显示说明。无效输入防护与保存、重开、生成、打开新模型论文图也有真实 UI 记录。

采集者是根代理，实际服务是 `http://127.0.0.1:8947/` / tab 43；本子代理只读审看。子代理自己的 CUA 两次返回 Browser 2 unavailable，inventory 为 browsers=[]，没有完成本轮独立 UI 操作。独立 8946 服务仅启动，session 18048 已正常停止，exit 0。详见 `proxy-browser-limitation.json`。不能把代理审看充作独立参与者、真人或 M4 验收。

最终公开 DOM 30 份绑定 `index-BcFxpKDY.js`（SHA-256 `98eae2934004ecaec4036f7b0746fb8304b3412c467b2417b68988dd4e4afe3a`），CSS `index-NmgHfiF5.css`（`0026e211728f2ae0aec210a2b2da0df06a46f068f0e26cbef5752ed3137dff2b`）。另有 19 份 obx 构建 DOM 是本轮初始历史样本，单独保留 `historical-obx-readonly-review.json`；不混成当前 30 份。原上轮 CVO 证据完全未改。产品代码未由本代理修改，没有业务 API 绕过、hidden state 注入、安装或模型执行。

## 最终样本结论

| 检查 | 证据与结果 |
| --- | --- |
| 自动排版可见性 | `root-browser/49-final-autofit.dom.json/.png`：四节点全界限在 canvas x220–857、y118–768.5 内，Output 可见，三边均为水平直路。实际截图没有节点重叠或交叉。没有再点额外 fit 来补救。 |
| 同名 Linear 稳定定位 | `51-final-duplicate-error.*`：两 Linear 均显示“全连接”，只标记下游 `n_e1ffd287dd6943ff8be415aac5b11046`；上游 `n_7a581a00dcd342d58fdde0f6811f65e3` 无错误标记。下游节点徽标、input 端口、`in_features` 的 aria-invalid、中文说明和定位入口均可见。technical 英文藏在 details。错误视图是目标聚焦，Input 可在左边被裁，不应声称该聚焦状态全图可见。 |
| 初次重挂无效草稿 | `20-final-build-initial-cached-error.*`：由 UI 编辑保留的语义无效草稿重新挂载后，仍定位上述稳定 ID、参数与端口。没有直接写 localStorage 制造样本。 |
| 无效数值文本 | `21-final-invalid-text.dom.json`：hello 无效，保存/生成同时禁用。`22-final-escape-with-error.*` 恢复 12 并明确显示“未提交的无效输入已放弃”，继续保留原后端形状错误是合理的；32 被有效提交后，`23` 节点/字段错误解除。当前空值回归来自历史 obx16，不虚构当前 Bc 空值重跑。 |
| 无效数组与视觉修改 | `30` shape `1,` 无效；`31` 改同一 Input 显示名、`32` 改 x50→66 后 raw文本仍为 `1,`、字段无效、两按钮禁用。`33` Escape 恢复 `1, 16` 并显示放弃无效输入提示。它实际覆盖了数组 structuredClone 曾可能重置 raw文本的边界。 |
| 搜索无结果说明 | `34-final-search-attention.text.json/.png` 与 `50-final-random-search.text.json`：显示“没有找到匹配的模块”，介绍中文/英文搜索，并明确当前不支持 Attention、LSTM、组合网络预制。`35` 清空后 17 模块恢复。17 是目录实际数量，不等同完整 DL-Playground。中文卷积匹配 1 个 Conv2d 仅来自历史 obx13。 |
| 最新参数直接生成 | `36-direct-generate-final-typed-value.text.json`：最后输入下游 out_features=8 后直接生成，具体源码是 Linear16→32、Linear32→8，无旧宽度误用。代理另以 ast.parse/literal_eval 读取生成的源码副本，再次确认两组字面参数；没有 import/exec 模型。 |
| 保存与重开 | `37` 显示草稿已保存；`38` 重开四节点三边；`43` 重开后再次生成；`44` 打开新工作副本论文图；`45` 明确显示画布已保存。草稿重开已验证，论文图未做 UI 重开。 |
| 平移不改模型几何 | `39–42`：左右各 50 像素、上下各 40 像素，相机复原，公开节点本地坐标与路径一致。没有把这组样本扩展成所有手势/原生 FPS/活动取消认证。 |
| 导出可见完成 | `47` 显示 PDF 已生成，`48` 显示 SVG 已生成。只读核验根代理复制的 10 项 server artifact 的字节/SHA，与根代理记录一致。收据含义、世界坐标 SVG 精确相等与物理数值由根代理独立 artifact audit 提供，本代理没有另一次几何实现验证。 |

实际审看了当前 `34` 搜索截图、`44` 论文图截图、`49` 自动排版截图、`51` 诊断截图，以及历史 `07/14` 对应截图。论文图当前呈现四个模型节点与容器共五事实对象，三条可见边；UI 的四端口关系包含 return 内部 binding，不代表四条可见箭头。源图仍有中心微偏移带来的四个弯折，本次没有把它认作所有路由都已无多余弯折；没有明显相交或节点重叠不能代替物理出版审看。

## 可核验范围

`final-readonly-review.json` 记录了 118 项根代理浏览器原始文件哈希、当前/历史 DOM 分类、逐项检查值、截图名单和根代理 artifact audit 引用。`historical-obx-readonly-review.json` 保留 Escape 提示被旧错误遮住的失败，随后 Bc22 的修复证明另记；没有抹去早期批量连接结果为零或工具 locator 失败，也没有推定其原因。

空白构建最初发生在 obx，最终 Bc 从该缓存草稿继续并重新执行反馈、有效参数生成和持久化闭环；不是在 Bc 又做一遍从空白创建。自动排版撤销/重做的真实操作样本为历史 obx08/09；当前公开函数与构建测试不能冒称当前 UI 已重做该手势。

未验证人为网络延迟的 React 陈旧响应、完整模块覆盖、全 visual matrix、原生 FPS、活动取消、字体/物理阅读、论文图重开或真人任务成功率。函数层 deferred transport 测试能证明 missing 旧 ID 不会猜同名新对象，不能单独证明 React 异步 lifecycle 在真实 UI 下已通过。当前闭环属于 AI 探索回归，M4 真人门禁保持开放。
