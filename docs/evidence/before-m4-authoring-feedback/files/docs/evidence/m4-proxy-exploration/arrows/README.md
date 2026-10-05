# 箭头与出版图视觉探索（AI代理）

本角色参与过批路由实现，因此不是独立正确性审查者，也不是实际研究使用者或真人出版审看者。子Agent的CUA环境没有可用浏览器，`getState`返回空inventory，创建浏览器2标签页被拒绝；没有以隐藏状态或HTTP代替真实交互。root将代操作独立8938页面，本角色审看真实截图与公开DOM。

目前独立服务已启动，session84839，端口8938，数据目录`.archcanvas/m4-proxy-exploration/arrows`。sandbox启动失败日志和许可启动日志都保留。未触碰8765/8916/8917、真人包或共享viewport，未安装依赖、未执行模型、未修改产品源码。

已实际审看当前CVO构建的三张真实浏览器截图（见`review-manifest-initial.json`）。L3整图在fit20%和14%时是一条细长页面，层级框可辨认，但标签及箭头细节不可阅读，因此不能用此截图证明没有交叉/折弯。encoder第二层以下与decoder下沿之间有长距离memory corridor和明显空白，整图高度降低可读性。公开导出DOM和真实收据显示180×598.6mm、最小文字5.36pt、节点名6.97pt、主线0.80pt；建议236×784.8mm仍很长。整图不能仅通过扩大页宽解决普通论文版面问题，需显式选择更小详情范围。

尚待root代操作：collapsed overview、局部大倍率L3/四向移动后截图、decoder详情180mm/85mm、保存/重开或导出。当前只能给出上述有限照片/尺寸观察，未完成直接UI参与者任务，不继承独立几何oracle的数字为自身眼见结果。


随后用正式现有CairoSVG把上述真实SVG只读栅格化，生成原尺度952×3166px整图及两处crop，实际`view_image`审看。来源、crop box与哈希见`actual-export-raster-review.json`。这三张PNG是导出文件的审看派生图，不是新的浏览器截图，不是实际打印尺寸验收。

局部能看见多个mask虚线靠近上沿并绕decoder右侧，长memory线回入cross attention；顶部多颜色正交lane相交或相接时缺乏明显跨线/汇合视觉区别。相邻纵向self/cross attention→Add的主路径仍有小横向折点。审看的top/decoder crop中没有眼见文字被route贯穿，也没有眼见框内文字裁剪，但不能据此排除其余区域问题。建议提供可追踪的tensor边高亮、明确trunk/junction和跨线视觉语法，以及显式对齐/边引导操作；这些是改进建议，不是已实现功能。


root随后已在8938/tab42真实UI采集overview、L3fit、100%top、100%memory，放在`root-ui`。本角色已实际`view_image`全部截图，并对另一移动角色的4方向照片只读审看。最终有限结论见`report.md`/`report.json`；以它们覆盖上面“尚待root”这一过程记录，初始失败与中间文档保留。
