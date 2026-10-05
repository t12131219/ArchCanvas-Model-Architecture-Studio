# AI 小白代理：真实 UI 探索记录

这是 AI 代理的探索式质量检查，不是真实研究使用者记录，不补齐 M4 真人席位或出版审看。代理已读正式 AGENTS、ArchCanvas Skill 和 runtime/source-review 约束。测试没有读取旧工程、安装依赖、执行生成模型、调用业务 API 或操纵隐藏应用状态；仅使用正式服务及浏览器支持的真实 UI 操作。

服务独立运行于 `http://127.0.0.1:8936/`，data-dir `.archcanvas/m4-proxy-exploration/novice`；启动 session `44643`，browser 2 / tab `1`。默认沙箱首次绑定 socket 被拒绝，原始 `service.log` 保留；授权范围内 permitted 启动的来源与能力在 `service-permitted.log`。没有操作 8765、8916、8917 或真人席位。没有改变共享 viewport；本次继承根代理矩阵协议的 1280 × 720。

实际加载 `index-CVO3JbfE.js`（SHA-256 `0516dc07309a95196c403fd822b3daf474ced88ec9c0ab7a8c0de85cfd0e26e9`）和 `index-DU5K7Xfa.css`（SHA-256 `37db77ae5f575917880af272c4011a5c8dda18b1444af180d4cca7ca58e2c401`）。每阶段 DOM 记录公开 scripts/styles 与 viewport，见 `build-binding.json`。产品源码未修改。

## 已观察到的实际闭环

1. 点击“搭建模型”进入真实空白工作区。加载完成后左侧显示 17 个模块、11 个分组：输入与输出、全连接、激活函数、基础算子、正则化、形状变换、卷积、池化、归一化、嵌入、合并与分支。模块为 Input、Output、Linear、ReLU、GELU、SiLU、Identity、Dropout、Flatten、Conv2d、MaxPool2d、AdaptiveAvgPool2d、BatchNorm2d、LayerNorm、Embedding、Add、Concat。该数量不等同完整 DL-Playground 或全部常用网络构件。
2. 用支持的 `Tab.drag` 真实拖入 Input、Linear、ReLU、Output，未合成 HTML5 事件。命名草稿 `AI小白代理_MLP`，依照可见提示点击输出/输入端口建立三条连接，点击“按连接排版”后再“适合画布”。
3. 选择 Linear，直接将 `in_features` 从 16 改为 12，点击生成，观察到输入末维 16 不匹配的错误。点击撤销恢复 16；重做恢复 12；在参数输入框最后输入 16，然后保存及生成，真实结果已使用 16。无需另找“应用参数”按钮，参数输入会生效。本测试没有推定所有参数控件同样行为。
4. 保存草稿；生成弹窗显示具体新 Python `nn.Linear(in_features=16, out_features=32, bias=True, dtype=torch.float32)`、`nn.ReLU()` 与 forward 调用。弹窗明确静态核对、模型未执行。点击“创建新工作副本并打开论文图”，看到五个事实对象（包含 AuthoredModel 容器）、四个端口关系；保存论文图。
5. 返回搭建，点击“重开已保存”，真实恢复四模块三连接。重开后 undo/redo 清空，未把历史恢复当作已实现。
6. 重复连接已有输入得到中文错误；按提示选择旧连线并删除，再真实从 ReLU 输出端拖到 Output 输入端，恢复三条连接。连线零高度 SVG path 的语义 locator 点击超时，记录原始限制后用公开坐标的可见连线中点点击成功；不是业务逻辑失败。
7. 选中 Linear，以 Right / Down / Left / Up 每次 16 单位移动；四步后的 x/y 回到 298/70，邻接箭头同步更新。以平移工具真实拖动四方向各 40 像素，camera 从 `(0.6402,172.0183)` 经 `(40.6402,172.0183)`、`(40.6402,212.0183)`、`(0.6402,212.0183)` 回原值，节点与连线几何不变。原始 DOM 与稳定截图记录均保留。

`movement-public-dom-summary.json` 是公开 SVG 几何提取，非独立正确性 oracle。实际检查了 `movement-contact-sheet.jpg` 及四张完整截图：这个四节点链在四方向小幅位移后未见节点重叠、箭头断开、相交或无须的回绕；有纵向错位时两条邻接边各产生两折以对齐端口。测试覆盖一个小链，不能推广到复杂网络、所有手势、当前全矩阵或出版像素审查。

## 发现与复现

| 优先级 | 观察与小白影响 | 真实复现与证据 |
| --- | --- | --- |
| P2 | “按连接排版”不会同时适合画布，四模块自动排成横链后，当前 100% 视窗外的 Output 消失。用户可能以为 Output 被删除，需要手动点适合画布。 | 拖入并连接四节点，保持 100%，点击按连接排版。稳定 `07-connected-layout-settled.jpg` 只见前三模块，DOM 显示 Output 位于 `(794,70)`；`08-invalid-shape-feedback.jpg` 在另点适合画布的 80% 下四节点均可见。 |
| P2 | 形状错误虽然有效拦截，但只在底部显示英文 `final input dimension…in_features`，没有同时定位/高亮出错节点或标记字段。中文小白需要自行理解 last dimension 与参数的关系。 | Linear in_features 改为 12 后生成：`08-invalid-shape-feedback.dom.txt/.public.json/.jpg`。节点绿框是此前的普通选中状态，不是错误高亮。 |
| P2 | 搜索 Attention 时左侧列表完全空白，没有“无结果”或“暂未支持”说明；17 总计仍在。用户难以知道关键词错误、加载失败，或模块不在支持范围。 | 搜索框输入 Attention：`22-search-attention.dom.txt/.public.json`；输入中文卷积能匹配 Conv2d：`23-search-convolution.*`。未把缺失 Attention/LSTM 记为实现承诺，只记为范围表达不足。 |
| P3 | 参数名和端口名多为原始英文（shape、in_features、out_features、input/output）；帮助描述是中文，但没有例子把“输入形状 1,16”与 Linear 的 16 联系起来。 | 空白引导、右侧控件及错误截图；已有中文一步步引导对找到 Input 与连接是有帮助的。 |

## 原始失败与局限

- 子代理不能请求 IAB visible=true；首次创建请求被工具拒绝，没有生成可见性 claim，随后不带 visible 创建自己的 tab。
- 初始目录异步加载瞬时为 0、生成及保存时瞬时禁用均有阶段记录；随后观察到了真实完成状态，不能把初始 0 当作永久缺失。
- AX 将平移呈现为 checkbox，但 DOM 实际是 button；一次 checkbox locator 无匹配，检查实际 DOM 后改用 button 点击成功。保留工具限制，不当作用户 UI 失败。
- 未验证所有 17 种模块构建、CNN/残差、多输入、复杂形状、数据集、训练、任意构造器、导出文件或物理出版尺寸。也未从零构建 Transformer；Attention/LSTM 不在当前目录。
- `journal.json` 与逐步原始 DOM/公开 SVG 是代理真实操作证据；AI 自己熟悉技术参数，因此仍不能代替小白真人认知与任务成功率。

最终 tab 保留在已保存的新模型论文图，`39-final-figure.jpg` 可审查；草稿另已保存，方便继续复现。该测试仅完成 AI 探索闭环，M4 真人验收不由此通过。
