# 多输入草稿卡片的几何决策

原 Add/Concat 横向双输入锚点为 y60/y72，只有 12 world 的间距。在残差实际 fit 53% 样本里，这成为约 6.36 CSS px 的分隔；16.2 world 字号补偿被 slot clamp 回 9 world，实际端口文字仍约 4.8 CSS px。将文字直接放大无法解决两行的物理拥挤和命中竞争。

本次保持单端口模块为 176×100、水平锚点 y66。按正式 catalog 声明的同侧端口数统一计算卡片高度和端口锚点；多同侧端口的首槽为 y66，后续槽间距32。当前 Add/Concat 两输入卡片为176×140，输入 y66/y98，输出仍 y66，因此主链可保持直线，跳连有独立到达位置。垂直方向保持有序 x 槽，输出锚点使用真实 body bottom；端口身份/方向/参数、模型声明、schema、源码和历史位置都不变。

统一纯 helper 为实际 body bounds、routing obstacle、端点、slot spacing 提供同一 catalog 合同。fit、添加/网络起点碰撞、按连接排版和组件 tooltip/focus/body 都必须读取它；不使用 Add/Concat kind 名称硬编码假 metadata。组件由 root 集成，旧 renderer/browser 工件保持原字节。9份将改正式源码和 focused 测试已归档至 `before/port-geometry/manifest.json`；没有参考或复用 Temp 实现。

风险与限制：较高的卡片可能使既有手排位置出现原来没有的几何重叠，不能自动移动历史位置；应按真实新 bounds 显示重叠提示。完整图片、保存后的路由和纵向图的 body/tooltip/fit 必须重新采当前构建验证。低于50%的屏幕文字仍受有界补偿限制，不声称任意缩放可读；字体宽度模型也不等于真实浏览器塑形。此次只改善当前双输入卡片，不能据此认证所有动态端口数量或出版审美。

实际几何 focused 最终通过63/63（7文件），见 `port-geometry-focused-pass/` 的18份输入绑定与实际命令记录。保留第一次61/62失败：旧clear-obstacle fixture 与变高的Add实际重叠10world。新的clear fixture保持原30world gap，另加原旧位置的真实overlap/不静默移动回归。纵向文字改为卡片外侧：输入 baseline portY−4、输出 baseline portY+fontSize+4，避开底部kind caption，dot端点/hit不变。这些固定几何检查并不替代当前浏览器或真人验收。
