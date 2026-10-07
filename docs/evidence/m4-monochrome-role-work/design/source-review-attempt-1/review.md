# 黑白角色实现的有界源码末查

这是实现作者的第二轮源码检查，不属于独立 expected oracle、浏览器像素或真人验收。产品专项测试、构建和新像素由 root / 独立验收代理负责；本审查未执行套件或构建。

已修的明确问题：

- projected grouping 曾只比较 monochrome effective appearance，可能合并旧版按存储颜色分开的 canonical 束。现 key 保留原 paper authored stroke / width / dashed 边界，再添加当前有效 pattern，避免无请求的分组改变。role 图例按实际样式归并，仍保留全部成员。
- pattern 检查曾用 Array.some，漏过 sparse holes。保存前文件与真实负探针后改为 Array.from(pattern).some。初探针 import 相对路径错误，已另存限制，不冒充产品失效；第二次真实观察到 Array(2) 被接受。独立验收仍需证实修复和 router fallback。
- 40-unit legend sample 在 width=12 时 marker 左翼超出项目矩形 2.9 units。用 SVG 固定 marker literal 几何证明旧缺陷，保存前文件后只改 sampleLength=max(40,5.5*width)；没有改模型边路径、箭头或线型。

目前有界源码结论：

1. footer 线样几何：SVG marker 默认 strokeWidth units，triangle x=[1,9]，viewBox=[0,10]，refX=8.5，markerWidth=5.5。新 sample 左 inset=.55w，长度>=5.5w，箭头左翼位于 inset+length−4.125w>=1.925w；右翼超出endpoint=.275w，低于标签预留间隔。垂直 marker ±2.2w，而行高>=5.5w，上下余量>=.55w。left round cap=.5w被.55w inset覆盖。几何覆盖到合法 width=12；真实字体与像素不由该数学检查证明。
2. no-edge / paper：buildEdgeLegend 对 paper 或 edges=[] 返回空数组，Scene 仅有非空项才挂派生字段。SVG原有节点图例照旧，空角色不生成。paper resolver返回原有三个字段；paper形状相同仍需独立字节比较证实。
3. detail：先完整场景再投影，仅从最终实际 detail edges 重建 role/style variants。incoming/outgoing boundary 与内部边使用同一有效 appearance；返回时删除 full edgeLegend/布局，空detail不能泄露外部角色。citation在派生band后。说明手动锚点不改；被投影的注释参与band避让。
4. annotation：band换行宽度不依赖手动注释宽度；重排suggestion忽略选定注释的几何，保留其ID reserved保护，避免自推反馈。图例rect参与findAnnotationBodyConflicts与建议位置；身份collision稳定追加:derived。
5. UI true/false：checkbox读当前真正Scene的dashed，写合法typed edgeStyle bool到选定canonical id。undefined时显示“角色默认”，明确勾选改为generic、关闭为solid；undo可恢复历史状态。当前typed op仅merge，没有安全删除override操作，因此没有伪装reset入口。black-and-white颜色picker禁用并说明paper恢复存储颜色；slider仍使用原1–4交互范围，文档合法范围0.25–12不被改写。
6. memory trunk：style-aware family前先validAppearance。非法array、非有限值、非正值、超过100、奇数/超过8项或dashed与pattern不一致均拒绝family和collapsed-residual特殊候选；缺字段按legacy bool grammar。generic obstacle routing仍独立可工作，不应把“拒绝共享family”扩大为整条边一律不走线。key含实际pattern，memory default点划与explicit generic不能共享。

待真实验证的可读风险：固定world-unit pattern + round caps在高线宽会关闭dash空隙（例如mask/memory gap3，width>=3；residual/generic gap4，width>=4）。属性正确不能推出像素可辨认。默认1.5仍有正gap；高宽variant需真实截图/导出审看。复杂expanded header detours没有在本轮路由修复；85 mm和真人出版门禁继续保留。
