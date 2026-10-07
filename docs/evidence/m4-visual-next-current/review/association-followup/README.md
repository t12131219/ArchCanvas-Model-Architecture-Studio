# 标签与所属连线的距离复核

本次只读，没有产品修改，没有新构建，没有模型执行或真人参与。核对当前 BTw 的 103 个 implementation 输入与 3 个 dist 绑定，再独立枚举现有 helper 的 291 个位置；52 个位置的名义卡片、重复背板、标题与其他连线冲突均为 0。根 Agent 的 [`04-transformer-local-100-settled.jpg`](../../../m4-performance-next-current/final-browser/04-transformer-local-100-settled.jpg) 已由本 Agent 亲看：memory 可读，却位于三条 mask 路线之上，与真正的 Encoder→Decoder 水平 memory route 相距明显。它不能证明标签关联容易理解。

完整候选见 [`report.json`](report.json)，复核脚本为 [`inspect_association.py`](inspect_association.py)。每个候选使用独立的 6×9 字号名义文字宽与 padding，未调用生产 placement/intersection 函数，未假称 resolved-font metrics。

| 候选 | baseline | 距 own route y444.1 | 名义文字范围距 own route | 原锚点距离 |
|---|---|---:|---:|---:|
| 当前 BTw | (280.5,388.1) | 56 | 51 | 48 |
| 以 own route 距离为先 | (288.5,484.1) | 40 | 29 | 48.66 |

下方候选名义范围为 `[286.5,473.1,344.5,489.1]`，正文、标题和其他 route 冲突为 0。它比当前标签接近 16 单位，但仍浮在 Decoder 左下方，没有引导线时可能被误读为输出说明。因此不建议只更换排序、换一次 build，再宣称关联已解决。

原因是名义 label 宽 58，左右节点间有效空隙宽 35。当前 64 单位搜索范围内，标签不能完整放在与水平 route 同一高度的空隙中。向右移让文字范围避开 Encoder 的重复背板后，仍须位于 Decoder 前板的底部 y472 之下，连续位置的 baseline 至少约 y483，距离 route 约 38.9；严格正留白还要更远。上方则受 y397 的 mask route 约束，baseline 至多约392，距离至少52.1。

两个可继续推进的方案：

1. 给无引导线的 label 增加与所属 route 的关联距离上限。超过上限就保留旧位置，显示明确诊断。旧 memory 文字的实际 bbox 与两端卡片只有亚像素相交，而且原图可读；这会承认留白仍待处理，避免静默把标签移到另一组路线旁。
2. 为下方安全标签增加一般、派生的 caption guide。独立几何已核 `(298.5,444.1)→(298.5,473.1)` 的 29 单位竖线不穿卡片／标题，也不增加其他 route 的严格交叉、拐点接触或重合。它应无箭头、与 canonical tensor edge 分离，保留源事实和操作历史。此项没有实现，仍需 renderer/export 测试及真实浏览器像素核验。

保留 [`attempt-1-script.py`](attempt-1-script.py) 与 [`attempt-1-failure.txt`](attempt-1-failure.txt)：首次手算只检查 x 不变的下方位置，误以为最近 baseline 是492.1；独立枚举发现向右移8后的484.1更近。更正的是审查预期，没有改产品，也没有把这项审查错误包装成 UI bug。旧 172 工件 seal 未回写。
