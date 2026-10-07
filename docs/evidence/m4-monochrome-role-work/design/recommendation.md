# 黑白连线角色辨识：只读设计审查

本文件是设计建议，不是实现、浏览器验收、性能或真人结论。审查只使用正式工程源文件；没有读取 Temp。已读取正式 AGENTS、archcanvas Skill 与 runtime contract，并通过 view_image 亲看当前冻结 CNN L0 与 L2 的黑白 local 原 JPEG。旧证据保持原件。

## 当前实际问题

- SceneEdge 只有 stroke、width 与 dashed:boolean。纸面彩图使用 EDGE_COLORS；黑白四种 role 均投影为 #56616b，默认仅 mask 是虚线。
- L0 黑白 local：stem 到 blocks 的两条短连接有独立端口和箭头，但 data / residual 同色、同线型且无可见角色标签。源事实准确不足以让新手从像素认出残差。
- L2 黑白 local：长 residual 走容器右侧，灰实线接近容器边框。路由本身是另一个问题；本轮可先改善辨识。
- 现有 legendItems 是可编辑的节点 glyph 图例，不支持线型角色。Residual 节点图例不能替代 residual 连线图例。
- scene.ts 的 projected bundle、canonicalSource proof、exportScene detail proof 与 router memory trunk identity 都依赖当前有效 appearance。新增线型必须同步，不能只改 SVG 绘制。

## 三个方案

| 方案 | 具体做法 | 收益与代价 |
| --- | --- | --- |
| A：线宽分层 | residual 更粗；memory 更细，mask 仍虚线 | 改动少，但缩小后差异有限，且用户 width override 会冲淡含义。不能单独解决四角色辨识。 |
| B：角色线型 + 实际样式图例（推荐） | data 实线；residual 长虚线；memory 点划线；mask 短虚线。黑白页底部展示当前可见 role / style variant 的真实线样。 | 不靠颜色，不加入模型事实或路由调整。必须增加派生 dashPattern、实际样式等价与图例排版；需要审看短线和出版缩放。 |
| C：角色文字标签 | 黑白 residual / memory / mask 自动显示角色标签，保留原线型 | 对新手语义最直接，但当前 label 位置未避让；短线与容器边易添文本碰撞，并改变 bounds。宜在独立文字避让合同之后实施。 |

B 能在现有正交路径上实施，清楚区分 residual 与 mask。它不能证明复杂绕线已美观，也不能替代真人理解测试。下列值是可实施的初始设计合同，最终像素审看可以拒绝这些值。

## 推荐合同

1. CanvasDocument / Architecture / EdgeStyle 的持久化字段保持当前形态。dashPattern 是 Scene 的派生呈现，不能写回架构或改变 role、canonicalEdgeIds、端口、tensorId、source / IR digest。
2. 默认角色线型仅作用于 monochrome；paper 保持当前颜色、width、dashed 与 5 4 通用虚线行为。black-and-white stroke 本轮继续使用当前 #56616b 投影，不引入新的颜色→灰度算法。已有 stroke override 保留在文档并在 paper 恢复；黑白 inspector 应明确统一灰投影，不能暗示颜色选择已经改变黑白像素。
3. 有效黑白线型：data []；residual [9,4]；memory [9,3,1,3]；mask [3,3]。保持默认 width=1.5，端点 marker、实际路径、端口和绘制顺序不变。
4. 显式用户 dashed 优先：undefined 使用 role default；true 保留旧通用 [5,4]；false 保留实线 []。width override 总是优先。三种情况不能用 truthiness 合并。开启虚线不能把自定义样式又默默改成 role default。
5. 单一 effective appearance resolver 被 scene 投影 grouping、route proof、SceneEdge construction、detail boundary edge、detail route proof 与 edgeAppearance fallback 共同使用；已有可见 inspector 仍读取真正 Scene。
6. SceneEdge 可增加可选 dashPattern。无该字段的既有手工 Scene 使用 dashed ? [5,4] : [] 的旧合同。SVG 只允许有限正数列表；不要把任意用户字符串直接写入 stroke-dasharray。
7. 有效 appearance equality 必须包括最终 dashPattern。RouteAppearance / memory shared-trunk key 也必须保留其差异；memory 自动点划与显式 true 通用虚线不能因为都 dashed=true 而合并。角色、stroke、width 与实际 pattern 都相同才可共享 trunk。
8. 黑白连线图例是 Scene 派生对象，与可编辑节点 legendItems 明确区分。只展示当前 Scene 的可见连线角色；每个 role 的实际 stroke / width / pattern variant 都展示真实样本。不要展示当前 detail 页面没画出的外部角色，也不要让用户 override 后仍把图例画成默认样式。可以在图例文字标“自定义”，但不能把样式改写为新的语义 role。
9. 推荐图例样本长度至少 36 world units，含箭头，文字用当前 10-unit 字体；角色名称保持四个 schema 名称与简明中文：Data / 数据流，Residual / 残差连接，Memory / Memory 连接，Mask / Mask 连接。不要把 memory 一律解释为循环状态。
10. role 图例置于现有节点图例之后的独立 band，按实际 textWidth / variant 数计算尺寸、换行与 Scene.bounds。保留模型所有坐标与已有说明的手动锚点。自动“移到图下方”与 annotation conflict 检查必须计入派生图例，不可只更新 SVG。导出 detail 重新从其实际 edges 生成图例，citation 应在两类图例之后。
11. UI 不应仅把 checked=true 称为通用“虚线”，而要展示当前有效样式来自“角色默认”还是显式覆盖。继承信息可读；恢复默认若没有受支持 typed operation，本轮不能承诺已有可点击功能。撤销能回到上一步并不是持久化的恢复默认能力。
12. 同一个 Scene 的 SVG interactive/publication 必须使用相同 edge path、stroke、width、pattern、role 图例文字/位置。交互控件差异仍按原合同处理；不能要求既有完整 node-subtree 跨模式 XML 相等。

## 独立验收必须覆盖

- 固定 literal role→pattern expectations，不能从产品 resolver 读 expected。4 roles × paper/mono × dashed absent/true/false，并含 width、stroke、空 override 与真实持久化 JSON 往返。
- 不变性：原始 document / architecture 字节不被 buildScene 改写；语义身份与 sourceFacts 不变。未带用户覆盖的九个历史 frontier，模型节点/端口/路径保持原样；新增页底图例和 bounds 差异单独解释。
- collapsed bundle：同 role + 同 effective pattern 可 bundle；同 role 默认 vs explicit true/false 必须按实际样式拆分。memory trunk 对不同 pattern 不共享；旧无 dashPattern RouteRequest 保留既有行为。
- hidden edge inspector fallback、visible bundled canonical selection、detail incoming/outgoing boundary、内部边与 full export 都显示同一 resolver 的实际结果。
- 图例来自实际可见 Scene。空 edge、单 role、多 role、多种用户 variant、长标签、宽线、极小 width、detail omission 均需检查；新增图例不遮节点/说明/citation且纳入 bounds、annotation suggestion 与冲突诊断。
- SVG 独立解析 stroke-dasharray、边路径、marker、role 图例样本与 render mode equality；PDF/PNG不能仅依据 SVG source 一致就称像素通过。
- 浏览器至少 CNN L0 与 L2（85/180 mm，局部能看完整 skip）及包含 memory/mask 的 Transformer；真实切换 paper→mono→paper、显式 dashed/width 修改、undo/redo/save/reopen、同 revision SVG 实际导出。亲看 fit/local 与导出成图，判断短线 pattern、点划线与容器边/opaque边框是否混淆。
- 85 mm 文字预检不达阅读尺寸的情况如实保留。该设计与 AI 图审不能计作真人、全局美观、物理出版或浏览器性能通过。

## 建议实施面

小型共享 appearance 模块；types.ts；scene.ts；exportScene.ts；svg.ts；edgeAppearance.ts；orthogonalRouter.ts 的 style key；annotationPlacement.ts 对新图例的几何覆盖；App 的只读样式来源解释。独立验收实现与 expected 应由另一代理拥有。不要改现有封存 baseline 或重写旧 receipt。
