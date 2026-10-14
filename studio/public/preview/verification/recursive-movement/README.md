# 递归展开后无法移动：修复与验证

## 问题与根因

在现有浏览器中，Transformer 的 83 节点完全展开图拖动 LayerNorm 后出现“此位置无法保留合法连接，已限制移动”。相同初始图中的小幅移动可以通过。

`recursive-graph.js` 用 canonical binding 的语义键查找分支标记对应的连线。Memory 的输入别名段与输出 K/V 段可以拥有相同语义键，查找结果错误地指向输入段。因此 `tensor-junction-6` 已在加载时断开；`E.move()` 最后的全图分支检查使任一节点的移动都回退。

`diagnosis.json` 保存了具体标记的错误/正确边 ID。修复后 Memory 分支对应 `encoder-memory-to-cross-040-40` 和 `encoder-memory-to-cross-042-42`。

## 修复范围

- 共享投影映射同时核对可见 source/target，优先使用 recorded visual edge ID / original edge ID。分支点与连线文字都使用此规则。
- `validateView()` 同时检查节点、边界/端口、无关线重叠和分支拓扑。已布线图的 `F.route()` 也检查拓扑，避免等到拖动才发现错误。
- 展示文档升级到版本 6，重建版本 5 的缺陷投影缓存，保留展开选择、局部位置偏移、边样式、草稿和连线文字锚点。
- 沿用上一版的移动、回退和边界保护机制；未通过放宽约束让错误连接通行。

修改目标为 `prototype/Summary_Merge`。`Summary_Merge（复件）` 仅只读对照；`readonly-reference.json` 核对其 12,533 个文件，全部未改。

## 验证材料

- `tests.log`：72/72 项完整自动化测试通过，使用 `node --test --test-isolation=none --test-reporter=spec prototype/Summary_Merge/tests/*.test.cjs`。
- `movement-tests.log`：补强连线文字归属及合法锚点迁移断言后，3/3 项修复专用回归再次通过。实现与完整测试时一致。
- `catalog.log` / `catalog-check.json`：114 个活动案例、339 个初始/局部/完整展开状态检查，零失败。
- `representative-moves.json`：Highway、TimeMixer、GraphNet、TextCNN 各 12 个完全展开节点的小幅移动，48/48 次成功，记录实际位移、阻塞状态与全图合法性。
- `compat-drag.png`：实际浏览器兼容模式，`enc.norm1.layernorm` 从 x=282 移至 x≈332，提交成功。
- `realtime-drag.png`：同一节点实时模式移回 x≈281，提交成功。

浏览器测试在用户的当前页面完成，随后撤销两次验证位移并恢复兼容模式。原有展开选择和布局保留，截图展示验证时的状态。

检查覆盖上述展开状态和代表移动；不声称任意坐标均可移动。模块边界、兄弟图元占用与真实不可达连接仍限制非法位置。
