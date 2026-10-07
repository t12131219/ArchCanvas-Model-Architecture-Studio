# 草稿端口几何：独立 focused 检查

本次 formal implementation 与测试从正式 catalog/独立固定几何合同实现，不参考或复用 Temp 代码。7 个测试文件实际执行通过63/63，exit0。`result.json` 记录实际命令、计数和 exec chunk ID；完整成功 stdout 保留于本会话工具输出，本目录没有将人工概述伪装成完整 stdout。`manifest.json` 保存18份当时实际输入及各自 SHA256。root 另负责完整 Studio、strict/build 和当前浏览器证据，不在此目录宣称完成。

新 `draft-port-geometry-independent.test.ts` 的8个案例覆盖：真实17种 catalog 的固定尺寸与双向端点、53% side label8.1 CSSpx 的名义几何与命中分离、纵向外置文字、按端口合同增长的三输入示例与假 Add 名称反例、完整高卡片 fit、添加/排版碰撞、三种透明起点的 bounds/原有卡片保护、较高 obstacle 下的四向移动与历史恢复。expected 固定数字与 body 传感器没有调用产品几何/router作为 oracle；字体几何不等于浏览器真实字体塑形或像素审美。

纵向输入文字 baseline 为 portY−4，输出 baseline 为 portY+fontSize+4。名义一 em 文字框完全处于卡片外侧，不再与底部 kind caption争用空间。端点、dot hit、端口身份与顺序保持原合同；纵向透明 hit 按 peer midpoint限制，完整外置 text 本身由同一 port group接收事件，不声称一个透明矩形覆盖全部纵向文字 paint。

首次保留执行为61/62，失败与输入在 `../port-geometry-focused-attempt-1/`。原 clear-obstacle fixture 的 Add y160、obstacle y290，在新140高卡片下有10world重叠；这不是router缺失。clear fixture 调至y330，维持原本30world gap，独立碰撞/交叉检查不变。新增旧y290保留案例明确要求真实 overlap报告、完整五条 binding和原手排坐标不变，避免把合法历史位置静默改写。

单输入卡片仍176×100，当前双输入卡片176×140，水平输入y66/y98、输出y66；垂直输出使用实际高度。旧手排位置可能新重叠，低于50%文字仍受有界补偿限制；此 focused 证据不认证任意动态端口数量、浏览器操作、全球无交叉、出版尺寸、真人易用性或性能。M4仍partial，M5 not_started，真人0。
