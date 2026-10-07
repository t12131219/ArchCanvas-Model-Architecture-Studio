# AI-only browser authoring smoke · BG build on 8986

本轮是 AI 浏览器体验审查，真人参与数为 **0**，不替代 M4 的真实研究使用者与物理出版审看。临时标签从 UI 新建空白草稿后操作，未点击保存草稿或创建工作副本，结束时已关闭；未重启服务、未执行模型、未修改历史封存证据。

17 个基础模块均从左栏点击加入，节点数量逐一从 1 增至 17。MLP、CNN、残差 MLP 三个网络起点分别产生 5/4、8/7、6/6 个模块/连接。Input 的实际库拖入和 CNN 网络起点拖入均成功。UI 搜索 Input 与 CNN 能定位对应控件。[逐模块记录](all-17-click-add.json)和[起点记录](preset-click-trials.json)保留具体对象与结果。

仅依赖视图从零加入 Input→Linear→ReLU→Output，通过圆点拖线建立 4 模块、3 连接，按连接排版后成为清晰直线链。两次点击端口的**圆点区域**也能连线，但整组端口 role-button 的中心点击会落在标签区域而未成功建立连接；失败的 [SVG](input-linear.svg)、[DOM](input-linear.dom.txt)及[成功圆点点击](exact-circle-click.json)均保留。这一旧版本缺口已经通知 root，新版本修复需另采证据。

同一 Linear 的上下左右方向键操作均产生 16 单位位移，路由跟随，反向移动回原坐标。[四向记录](four-way-moves.json)记录从零草稿；后续 MLP 的 [同步移动记录](preset-mlp-synchronized-moves.json)与 `preset-mlp-*-managed.jpg` 可核对最终像素。原 `move-up.jpg` 的截图时序不一致（SVG/AX Y54、图上 Y70），仅保留失败，不作为上移像素通过证据。

AI 审看链式排版、三个起点与同步 MLP 移动画面，未见不必要相交或穿卡。CNN 的两行布局有一条长正交回绕；残差跳连沿底部走廊。9 个公开 SVG 观察样本的简单名义矩形/中心线审查结果均为 0 穿卡、0 严格交叉、0 共线重叠，详见 [几何范围与结果](public-nominal-geometry.json)。它不覆盖圆角描边、箭头光栅间隙或真实论文尺寸。

残差 MLP 的生成入口显示实际新 Python 源码和“模型已生成并静态核对”弹窗，明确说明尚未执行模型；[弹窗 DOM](residual-generated.dom.txt)、[源码与资产](residual-generated-public.json)和[截图](residual-generated.jpg)提供证据。本轮未生成从零草稿、未逐模块验证所有参数/生成、未保存重开、未导出论文图，也未验证当前 source 的新修改。

完整范围、未测试项和工件 SHA-256 见 [report.json](report.json)。本轮只验证 8986 已有 BG 构建，不视为下一构建的回归通过。
