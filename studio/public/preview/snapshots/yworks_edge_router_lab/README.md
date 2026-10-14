# Edge Router Lab

2026-10-12 交汇点跟随：分支圆点通过源码张量与注册连线确定归属，按实际共享路径计算位置；移动、Apply、撤销和重做使用同一关系。旧 SVG 中误挂在其他模块里的静态圆点会迁移，普通交叉不会成为语义分支。

2026-10-12 短路径与容器接口跟随：语义字段和物理连接位置分离，普通图元自动选择合法连接侧；短间距优先直线，移动后也优化仍然合法的绕行路径。LayerNorm 等内部算子的原始直通出口可随所属端口移动，保留容器边、层级与穿越次序。Memory 上入下出、分支干线和多字段插槽继续受保护。共享路由器已同步，全部当前示例由 Summary_Merge 的 index 展示。实现、浏览器截图和验证见 [专项证据](../Summary_Merge/verification/shortest-routing/README.md)。

这是对 yWorks Layout Styles 的 Edge Router 行为复刻实验，不使用 yFiles 运行库。打开 `index.html` 查看：节点拖动、端口连接、端点重接、手动折点、箭头样式、Orthogonal / Octilinear / Curved 近似路径、All / Selected / Incident scope、Path As Needed / Never 策略、保留途经点、网格候选通道、撤销/重做和 SVG 导出。

- [复刻实验](index.html)
- [解析证据](report.html)
- [源码证据](evidence/source-findings.md)
- [REA 静态摘要](evidence/rea-feature-summary.json)
- [运行时截图与 DOM/路径快照](evidence/runtime/)

服务本目录：`python3 -m http.server 8765 --directory prototype/yworks_edge_router_lab`。

## 工作方式

箭头由独立绘制层沿路径末段方向旋转并裁短线尾；端点保存节点、侧与比例。显式 Apply 把节点扩成安全边界，在候选通道图中做带方向状态的最短路搜索，价格包含长度、折点、交叉和共线重叠。Octilinear 将安全转角削为 45°，Curved 用二次 Bézier 圆滑转角。原型路径不会与商业 yFiles 求解器逐点相同。

## 证据与验证

- 原图正交/曲线对比：16 个节点矩形属性一致；61 条边里45条改变；最终曲线外观的 SVG 采用直线采样（111→732 个 L 指令），无 C/Q。
- REA 完整 bundle 分析受语义图堆限制。精确 AST 提取配置片段后 application inventory complete，semantic graph 保持 unknown。详见 `evidence/README.md` 和 `rea-feature-anchors.json`。
- `node tests/router.test.cjs`：13 个具名几何测试，0 失败，包含源/目标端口短线折返的回归案例。`evidence/verification/checks.json` 保存12项通过的 UI/几何验证。SVG 导出按钮已实现，但浏览器下载等待超时，下载交付未验证。
- 默认本地预览：`http://127.0.0.1:8765/`。无需 npm install；也可直接用浏览器打开 `index.html`。预览 server PID 存在 `evidence/verification/server.pid`。

## 转角小尾巴修复

原先搜索只记录水平/垂直轴，拼接端口短线时可能先越过转角再原路返回。现在搜索记录四个有符号方向，并检查源端离开方向和目标端进入方向，禁止即时折返。手动途经点仍保留。浏览器复现布局与修复截图见 `evidence/verification/turn-spur-fixed.json/png`；刷新页面后点击 Apply Layout 即可重算旧路径。

## 多边重叠修复

启用惩罚交叉与共线重叠时，为已有路径提供12 px平行候选通道，并禁止搜索中间线段共线复用。端口短线也参与冲突检查，第二轮优化包含重叠代价。用户当前13边布局的回归页为 `evidence/verification/overlap-regression.html`，原始/修复SVG几何均保存。交叉仍可存在；显式固定在同一物理端口的多条连接允许共享必要端口短线。
