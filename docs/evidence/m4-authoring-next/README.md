# 从零搭建模型：本轮证据

本轮为 AI 工程与模拟使用测试，M4 继续 partial，真实研究使用者与出版审看记录均为 0。

- [独立后端与 HTTP 审查](independent/README.md)：8 个手算网络、50 个无效草稿、21 个 oracle 污染控制，实际 HTTP 与归档源码复跑各 7/7。
- [独立公开交互检查](interaction/README.md)：11 项检查，覆盖新增模块、缓存损坏、方向移动、平移末尾位移与指针归属；该组 HTTP 使用 stub，实际 HTTP 另见上一组。
- [实际浏览器与服务工件审查](browser-audit/README.md)：25 份当前构建 DOM、11 个工件、38 个污染控制，四向移动/平移、保存重开、生成新模型、PDF/SVG。限制见该报告。
- [操作记录](browser-journal.json)：保留端口点击失败、左向平移中断及后续成功范围。
- [当前交付截图](browser/reviewable-deliverable.jpg)：收尾时在同一页面读取可见状态并捕获 80% 适合画布画面，四个模块完整可见。这张补充截图由 root 保存，不增加独立审查的 25 份 DOM 或 52 个输入计数，也不替换此前截图。

Studio 113/113、Python 300/300（获准环境，零跳过）与构建/独立性日志均在本目录。Python 首次受限环境失败日志保留，不计为通过。生成模型未导入或执行。

先前 904 项绑定的原始字节保存在 [前轮归档](../before-m4-authoring-next/manifest.json)；旧 seal、独立审计 manifest 与失败记录不得覆盖。本轮总 seal 为 `../m4-authoring-current-verification-sealed.json`。分享证据不包含服务签名私钥。
