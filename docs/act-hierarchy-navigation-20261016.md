# ACTPolicy 层级树导航修复（2026-10-16）

本次在 `http://127.0.0.1:8897/?documentId=canvas-architecture-policy.ACTPolicy-4c782cbfbe58-5ae609ca` 复现并修复。原 ACT 项目未修改、未执行，也未新增专用适配器。已有编辑草稿、适配模块及模型源码均保留。

## 原因

预览模式原来用正式解析器的 Architecture 构建左侧树，再要求每次操作都能唯一映射到预览引擎的图元。ACTPolicy 的 `ConditionalRegion` 对应多个源码检查容器，无法取得唯一映射，因此点击展开会报“当前源码对象未显示为独立图元”，树和画布都不展开。普通输入节点的选择可以工作，因此此前只测试输入多选未覆盖此失败路径。

## 修复

- 预览模式层级树直接使用预览引擎递归 authority 中的身份和父子关系，包含条件分支、模块和源码检查容器；隐藏路由连接点。
- 树中的选择、显示别名、固定标记和展开状态读取实际预览状态。展开及其撤销、重做不再依赖正式对象映射。
- 点击树节点定位实际图元；Ctrl / Shift / Command 点击切换多选。隐藏节点会先展开祖先，再选中定位。
- 搜索展示完整祖先路径；搜索期间的展开按钮根据实际画布展开状态操作。展开隐藏容器时，祖先和目标在同一个预览事务中处理。
- 根容器受递归引擎 mandatory 约束保持展开，其按钮明确禁用并提供提示，避免出现可点击却无效果的按钮。

此处的树是导航数据，不生成或替换正式 Architecture。当前实例显示 192 个预览图元，正式源码仍有 256 个事实对象；两种 IR 的计数不是同一个指标。源码编辑、项目身份、语义事实及原有双向映射约束保持独立。

## 验证

构建 `npm run build` 成功，仅有现有的大 bundle 提示。以下相关测试共 **55 项全部通过**：

```bash
node --experimental-strip-types --test --test-isolation=none \
  tests/previewHierarchy.test.ts tests/hierarchy-tree.test.ts \
  tests/previewApp.test.ts tests/previewRequestOrdering.test.ts \
  tests/previewInterop.test.ts tests/previewPanelDocument.test.ts \
  tests/previewSelection.test.ts
```

新增回归覆盖没有正式映射的检查容器、if/else 身份与顺序、隐藏搜索结果的祖先展开、节点别名与固定标记、实际 App 回调，以及实际引擎 focus 的多选切换。`git diff --check` 和预览 app 的 JavaScript 语法检查通过。

实际浏览器已验证：

1. 左侧展开条件容器后，if、else 及其内部对象可见，画布同步展开。
2. 点击 `else` 中的 `branch_review · nn.Identity`，树高亮、画布选中并定位、右侧属性及源码位置联动。
3. Ctrl 点击同级 `model · DETRVAE` 后，树与画布共同选中两个节点，对齐按钮启用。
4. 折叠条件容器，搜索 `branch_review` 后点击结果，祖先在画布中自动展开并定位到目标。
5. 撤销后内部树项及画布收起；重做后恢复展开，再次点击内部对象仍能定位。

截图见 [搜索内部节点并定位](evidence/act-hierarchy-navigation-20261016/search-focus.png) 和 [展开后内部节点选择](evidence/act-hierarchy-navigation-20261016/expanded-selection.png)。

本次不重新认证任意模型源码生成能力，也不声称解决此前报告的编辑草稿内部位置返回预览的映射限制。
