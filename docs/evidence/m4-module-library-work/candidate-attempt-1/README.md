# 模块库浏览候选（未合入）

文件仅在 /tmp。基础模块默认显示，普通 pressed buttons 组成命名 group；点击浏览选择仅 setPaletteView。非空规范化查询搜索基础模块与网络起点，显示两类结果数量，清空后返回选中的浏览视图。列表 key 只重新挂载 palette-list，以便切换从列表顶部开始；不触碰画布、草稿、选择、历史、连接或 camera。

建议补丁位置：state search 后、query 下 matches/presetMatches、左侧 palette-intro 和 palette-list；CSS 文件尾添加浏览选择与搜索结果提示样式。add/addPreset 函数和 drag payload 原样保留，未改 backend/API/catalog/preset。

尚无构建或浏览器认证。请 root 核对 manifest 中基础文件 SHA 后合入，再按实际浏览器验证。目标桌面首屏 Input/Output/Linear/激活可见须亲看截图，不能凭 CSS 断言；小视口可能仍需滚动。
