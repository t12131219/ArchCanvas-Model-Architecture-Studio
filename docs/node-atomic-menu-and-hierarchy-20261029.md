# 节点局部原子展开与模型层级标记

2026-10-29，开发源码 renderer `native-semantic/24`。

后续 renderer 25 将参数读取箭头改为节点详情，局部原子层和“全部展开”继续保持相同规则，见 [修订记录](parameter-dependency-presentation-20261030.md)。

## 交互

- 画布节点右键提供“展开稳定语义层”“折叠稳定语义层”“展开到原子层”“返回原语义视图”。原有加号、双击和稳定视图层行为保留。
- Shift / Ctrl / Command 点击可多选；对选区内节点右键保留完整选区，对选区外节点右键切换为该节点。菜单只对可以执行的动作启用按钮。
- 没有加号的语义叶子也可以暴露已被折叠或附注保存的源码单元，例如 Linear 的参数。真正的源码原子或没有源码实现的外部调用不会凭空生成内部实现，菜单会说明没有更深内容。
- “返回原语义视图”撤销对应局部范围的原子展示；支持多个范围分别还原、画布撤销、文档保存及重开。全局预设或展开全部操作会清除局部原子范围。
- 菜单限制在画布视口内；支持 Escape、上下方向键、Home / End、Shift+F10。局部展开保持当前缩放和所选节点的屏幕位置；返回已访问切面恢复其镜头。

## 数据边界

局部范围来自原始 IR 的父子包含关系，以及当前切面的 canonical representatives、canonical_members、local_pipeline 和 resource annotations。所选范围使用与“全部展开”相同的 canonical source 投影，保留对应源码节点、容器及内部连线，不在合并回外层语义视图时再次应用摘要连线策略。投影通过原生 mixed source cut 路径构建，以 `atomicCuts` 保存展示选择。选区之外的模块继续采用当前层级，未选择的语义兄弟保持身份；布局可随新增节点重新计算。

整个过程不执行模型，不修改 canonical IR、操作数、源码身份或代码生成权限。纯函数名语法继续保留在源码详情。实现不包含 TFB、模型或算子名称专项分支。

新增 bridge 命令 `atomic-selection`，参数为可选 `ids`（默认选区）和 `expanded`（默认 true，false 还原）。参见 `studio/public/preview/BRIDGE.md`。

## 层级色彩与符号

颜色依次采用用户展示覆盖、当前画布节点颜色、潜在层级节点的语义颜色。默认还原为彩色方块；在“视图 → 模型层级标记”中可切换“彩色方块 / 语义图标”，选择保存在本机。现有 SVG 图标实现保留。模块英文名称保持不变，图标说明跟随界面语言。

符号由本项目原创 SVG 绘制：变量用括号内 x，明确的二维形状用矩阵点阵，相加用圈加，普通乘法用 ×，已明确的逐元素相乘用 ⊙，矩阵乘法另用括号乘号。另提供注意力、线性映射、激活、归一化、形状变换和未知单元标记。分类读取语义字段，不依据用户可编辑名称推断运算。通用 mult 不被假定为矩阵乘法或 Hadamard 乘积；未提供二维 shape 的张量不被假定为矩阵。

联网查阅的记号依据：

- [Understanding LSTM Networks — Colah](https://colah.github.io/posts/2015-08-Understanding-LSTMs/)：向量沿箭头流动、点运算圆形符号、学习层框体的示例。
- [Hadamard product](https://en.wikipedia.org/wiki/Hadamard_product_(matrices))：逐元素乘积与矩阵乘法的区别。

这些是可辨认的阅读习惯，不代表所有论文采用同一套通用图标；没有下载或复制网站图片。

## 本轮修订验证

`canonical-revision-tests.log`：56 项检查通过；新增局部模块与“全部展开”对应范围的节点身份、名称、容器展开状态、语义展示字段和内部边逐项一致检查。renderer 23 含局部原子展开的旧布局重新计算，原 IR 和旧布局迁移证据保留；没有局部原子范围的 renderer 23 和兼容 renderer 22 布局继续保留。生产构建日志为 `canonical-revision-build.log`。

浏览器确认默认彩色方块，并验证切换至语义图标后再切回；3371 个层级条目均使用所选标记，模块英文名称保持不变。

本轮浏览器从 Transformer 稳定模块详图中，对 Feed-forward 标题右键执行“展开到原子层”：对应范围显示为 ffn 源码容器及 8 个子节点（4 个计算、2 个参数、输入和返回接口），全图仅从 82 增为 86 个可见节点，其他范围保留语义摘要。source / layout 为 true，无 invalid edge，storage 为 saved。证据为 `canonical-revision-browser.png`；菜单切换入口为 `canonical-revision-markers.png`。

曾打开的 3371 节点全量源码图有 114 条待布线、0 条冲突，这是此前全量视图的路由预算状态，本轮局部验收不能作为全量图布线完成证明。

## 先前 renderer 23 验证（历史证据）

`docs/evidence/node-atomic-menu-20261029/frontend-final.log`：55 项针对性检查通过，包含原生语义视图、局部多选展开与独立还原、源码 IR 不变、保存重开、进入编辑模式、层级颜色覆盖、运算图标、镜头连续性。相关原生模型样例的 F0 / F1 / source-unit 检查无待布线和失败连线。

浏览器在 8798 正式 runtime、独立测试数据目录下验证 Transformer：无加号 input projection 右键展开后出现 linear1.parameters；可还原；Shift 多选 input/output projection 后菜单显示两个选中节点，展开后显示两处参数。84 个可见节点的浏览器检查报告 source / layout 为 true，invalid edge 列表为空，storage 为 saved。

最终构建的局部操作还验证了镜头从 `-21 988 700 617` 到 `86.5 988 700 617`：宽高和 100% 缩放不变，仅跟随选中节点的布局平移。最终连线检查仍为 source / layout true、invalid 为空、storage saved。renderer 22 的兼容布局保留，不因为增加菜单而废弃其已有保存位置。

证据截图：`browser-menu.png`、`browser-atomic.png`、`browser-multiselect.png`、`browser-final.png`。生产构建与资产来源检查结果见同目录日志；421 项 integration manifest 文件摘要一致，preview authority audit 通过。验收不扩展为所有任意黑盒模型都有可解析内部源码的承诺，既有冻结发行包不自动包含本次开发改动。
