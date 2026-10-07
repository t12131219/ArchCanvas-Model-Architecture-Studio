# M4：密集图局部路由与搭建页恢复

当前构建为 `index-B32ccWRJ.js` / `index-BOWsNy5e.css`，JS SHA256 `1ba52af85bc7df646d488e4ba55170fc05403ee4d06b658b551ddcfd3cac01b0`。本轮继续 M4；M4 `partial`、M5 `not_started`、真人 0。

正式工程独立实现密集图的晚期局部组件 pass：只处理不少于 128 条路线的 ordinary data 批次、最多 8 条路线的冲突组件和多弯路线。它有独立公开的 2048 candidate / 400000 segment / 150000 obstacle work allowance，不扩大旧 384 candidate 预算。每个采用候选保护端点法向、名义 body/header 间距和每个 peer/self 的已有交叉、接触与重叠几何，包括同 tensor。小图继续使用原有合同，九个历史前沿及详情保持原有回归。

[独立读回](evidence/m4-routing-components-current/independent-review/after-readback-attempt-1/comparison.json)显示 DenseStress300 基线交点 **71→38**，正长度重叠 **4→1**；向下移动交点 **75→44**、重叠 **5→2**。四向移动、预览=提交、undo/redo、端点/法向及只移动选定 leaf 均通过。下移仍有 **6 对唯一 edge–leaf 入侵**，来自两个模块之间仅 6 world units 的间隙；当前 6-unit 引出策略仍返回诚实 blocked。旧 AI 的 9 条 segment rows 与此分母不同。286/302 条四弯路线和整体美观仍未通过。

搭建页恢复了当前构建中缺失的右侧参数、静态检查、定位和步骤面板，并添加模块/网络起点的拖入边界与“松开添加”反馈。SSR 真实组件回归能拒绝仅移除 inspector 的仍可编译变体。左侧仍为 **17 基础模块、3 透明网络起点**，没有扩大算子或执行合同。

[统一检查](evidence/m4-routing-components-v1/checks-final/receipt.json)：Studio **470/470**、strict TypeScript/Vite exit 0、publication **11/11**。119 source/test/config bindings 和 3 dist 绑定；这是有限测试清单，不是完整依赖清单。新浏览器试用从空白点击建立 Input→Linear→ReLU→Output，3 条连接、静态检查、保存、重开、生成源码、打开新工作副本并保存画布；见 [浏览器收据](evidence/m4-routing-components-v1/browser/receipt.json)。这是 AI 工程试用，非真人新手验收；尚未补全当前 build 的原生拖入取消和出版像素矩阵。

新五席包 `.archcanvas/m4-research-trial-routing-components-v1` 已 prepare/verify，独立 readiness **127/127**，88 implementation / 4 baseline，五 pristine 端口 **43831–43835**，0 assignment/collection/humans。旧 frontier status v2 包保持原字节，产品变动后 stale，不可继续分配。固定字体/硬件、presented FPS、input-to-paint、85/180 mm 真人出版审看及 3–5 真实使用者五步任务仍开放。
