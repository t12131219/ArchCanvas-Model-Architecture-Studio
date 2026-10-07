# Repeat outline 五文件独立代码复核

未发现本次五文件改动中可证实的实质问题。检查了真实 nominal union 的端口投影、按 side 分离的 canonical 关系、detail fallback 与平移，以及 router 对自身叠片和其他节点的完整避让。五个源码文件与 implementation-ready 的字节和哈希相符，15 个复核输入结束时重哈希不变。

自建 6 个定向探针结果通过：同一 canonical memory 输出的 bottom/right 端口在两种 authored 顺序和 full/detail 中保持独立显示 ID 与正确 edge membership；空外接框角区不产生假重叠；隐藏祖先适配边的 detail 输入/输出 fallback 保留原 canonical endpoint 并投影到露出的轮廓。探针按字面卡片矩形检查几何，没有调用产品 outline/side/intersection 辅助函数来定义预期。

该结论是有限代码与定向探针复核，不是无缺陷证明。圆角、字形、描边和箭头实际范围、残留路线交叉、小字和物理尺寸可读性尚未在此认证。未操作 UI、运行模型或改产品；新 BG 浏览图、保存关联与 seal 需另行复核。
