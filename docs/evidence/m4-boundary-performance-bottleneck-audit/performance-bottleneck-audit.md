# M4 性能瓶颈审计（只读）

审计时间：2026-10-05T04:34:29.950353+00:00。本报告只读取正式源码、当前构建和既有冻结收据；没有启动浏览器或服务，没有执行模型，没有修改源码/build，也没有改写既有 evidence/seal。当前构建 JS SHA256：`1f4f51f9818e523916dacea184a7005fa7459bd3f2c4c8bfe6bfc83006e5be29`；Python frontend SHA256：`ce7f7f733da28cb31ecff80ca029a53094e88f8451bffc3874f8167f80a07d00`。

## 结论

DenseStress300 收据的约 2 Hz、约 983–1000 ms rAF 间隔，当前证据更支持**浏览器/宿主调度或 surface throttling 的外部混杂**，不能归因给产品渲染。独立简单控制页没有 React、SVG、模型或产品遥测，却在可见/聚焦窗口记录约 1.95 Hz、间隔 p95 983.4 ms，并出现 1000 ms Event Timing；另一简单控制窗口达到约 19.18 Hz。这与产品 iframe 的约 1.98 Hz 和 992–2024 ms Event Timing 形状相近，说明一秒量级更像会话调度模式。`visibility=true` 是离散读数，不能证明持续 presented。

产品侧仍存在真实性能风险：展开 304 个对象时，完整 SVG 收据约 625 KB；`App.tsx:90–92` 每次 `preview` 变化都会重新 `buildScene` / `renderSvg`，`movePreview.ts:52–64` 的每个拖动预览都会重建 Scene；`App.tsx:587–588` 通过 `dangerouslySetInnerHTML` 整体替换 SVG。独立 Node 证据中 expanded drag 路径 p95 约 5.75 ms Scene、5.54 ms SVG，浏览器 stress 长任务最高 101 ms。这足以在真正 60 Hz 的 presented 环境造成掉帧风险，但现有证据不足以解释全部一秒间隔，也不能把 rAF 当 presented FPS。

观察器不是已证实的唯一原因。full observer 的 scene-read/frame callback 自身最高约 12.4 ms，缓冲无丢失；它增加 DOM 读取和 iframe 开销，但无产品的简单控制页仍复现慢调度。Event Timing 只覆盖匹配的离散事件；pointermove/wheel 和 compositor presented frame 未测量。

## 最小可验证工程动作

先不要因为 2 Hz 收据直接改产品。下一次在同一固定可见浏览器 session 同时保留产品窗口与无 React/SVG/model 控制窗口，并连续记录 visibility/focus；若能力存在，再加入 presented-frame trace。诊断副本可在 `prepareMovePreview → buildScene → renderSvg → React/DOM commit` 分段打点，不能读取隐藏状态或改写正式收据。

若真实 60 Hz 环境仍显示 Scene CPU 占比，最低风险候选是用 `WeakMap<Architecture, …>` 缓存 `buildScene` 的不变量索引（`byId`、roots、sourceFacts、parent chains、canonical edge index 等）。它只减少重复索引构建，预期不改变 Scene/SVG 字节；必须先用 DenseStress300 展开/收起、拖动预览、页面 preset、样式、别名、annotation、frontier、undo/redo 做字节级回归，再跑可见浏览器 stress。该候选**不能**消除整棵 SVG 的 DOM 解析，也不能证明调度原因。

更有效但高风险的方向是拖动预览时使用 overlay/keyed incremental SVG，避免每帧 `dangerouslySetInnerHTML`；它可能改变 edge routing、ports、命中测试、无障碍和导出字节，应单独版本化并经过完整矩阵回归，本轮不实施。

## 当前门状态

`presentedPaintCertified=false`、持续 FPS 未认证、活动 held-down→Escape 取消未认证；真实研究者任务与出版复核仍是外部门。此审计不把任何工程或 agent 操作计入真人验收。

完整机器可读证据、输入 hash、行号和验证门见同目录 `performance-bottleneck-audit.json`。
