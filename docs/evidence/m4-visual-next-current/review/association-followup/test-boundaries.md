# 测试与像素观察的边界

本 Agent 独立亲看当前 `index-BTw7OHsD.js` 的 `04-transformer-local-100-settled.jpg`。这是实际 100% 局部画面，不是整页 publication fit：memory 清楚可读，处于两列 embedding 下方、mask 路线之上；实际 Encoder→Decoder memory 水平线在它下方 56 个 scene units。图中没有 caption guide。由此可以确认当前文字与卡片留白改善，却不能推出用户容易找到文字所属连线。根 Agent 保留的 03 动画滞后图不计稳定结果；本 Agent 没有创建新截图或把旧 B_XH 像素用于当前 BTw 认证。

[`label-after-focused-attempt-3.txt`](../label-after-focused-attempt-3.txt) 是标签修复轮的 34/34 专项，其中 7 个新测试分别核对：实际源绑定 memory 名义 envelope；已有安全 caption 保持；repeat/header/note 阻挡；不同 caption 与其他 route；局部空间不足的诊断；whole/detail 与 visual history；长 caption 的画布范围。其余是既有路由、导出分区和 history 核验。34 不是 34 个新 Studio 测试，7/34 也不与根 Agent 后续 358/358 相加。

这些回归证明节点／端口／源事实／canonical binding／路径和持久化 layout 未被标签避让改写、名义碰撞检查与诊断工作、长标签未被名义 Scene bounds 裁切。它们不证明 resolved-font 宽度、所有真实浏览器字体、所有 detail 页像素、物理出版可读性或真人任务表现。尤其没有任何测试证明“没有卡片碰撞”必然意味着“与所属 route 关联清楚”；当前 settled 截图揭示了这项区别。

下一项约束应直接保护 owned-route association：为没有 guide 的 caption 设定与所属 route 的最大距离，超出时给可理解诊断，并保留既有位置及标签内容；或实现一般派生 caption guide。独立枚举已经证明仅换排序会把距离从56降至40单位，仍不是邻近标签。为下方安全位置建立29单位 guide 的具体几何见 [`report.json`](report.json)，目前没有产品实现。此问题继续登记为视觉体验未完成项，不能因为专项／full suite 通过就关闭。

当前 follow-up 原六文件 [`manifest.json`](manifest.json) 和旧 review 172-file manifest 保持原字节；新增本说明、boundary receipt 和扩展 final manifest 单独封存。
