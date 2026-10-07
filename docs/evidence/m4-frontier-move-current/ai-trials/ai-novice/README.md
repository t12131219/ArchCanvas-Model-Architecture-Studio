# AI 模拟新手试用（不是真人）

本记录以“第一次接触 ArchCanvas 的新手”视角完成五步叙述：理解画布、寻找左侧预制模块、选择对象、四向移动并撤销、折叠/展开以及保存重开。**这是 AI 证据复核，不是研究参与者数据；真人参与者数为 0。**完整结构见 [report.json](report.json)。

作者工作台的模块库来自正式源代码旁证：左侧显示 **17 个基础模块**，并提供 **3 个透明网络起点**（最小 MLP、小型 CNN、残差 MLP）。卡片同时支持点击添加和拖入画布，插入后的节点与连线仍可编辑。该 frontier 浏览器序列从已种入的 DenseStress300 画布开始，没有新建空白草稿的挂载浏览器帧，所以本报告把这两步标作 source-grounded，而没有冒充已完成 fresh authoring。Attention/LSTM 在 UI 中明确提示不支持，目录还不含 Sigmoid/Tanh/Conv1d/AvgPool2d/BatchNorm1d 等常见选择；对小白用户而言，MLP/CNN/残差覆盖够用，但 transformer/RNN 方向会遇到空结果。

四向操作由完整分段 SVG/JSON 读回确认：Linear 1 在当前视图下右移 `x 110→134`、上移 `y 316→292`、下移 `y 316→340`、左移 `x 110→86`，每次 Ctrl+Z 都恢复原坐标。对应证据是 `browser/02–09` 的 JSON/SVG；移动距离是画布单位。部分同名 PNG 在采集时落后于 JSON/SVG（例如 `02/04/06/08` 仍显示旧坐标），因此保留但排除为像素状态证明。

折叠后的 corrected fit 帧 [14-collapsed17-fit.png](../../browser/14-collapsed17-fit.png) 在 97% 下显示 DenseStress300、features、network、output 四个对象和两条清晰竖直箭头，没有可见交叉或多余弯折。重展开后的 [15-reexpanded18-fit.png](../../browser/15-reexpanded18-fit.png) 在 13% 下显示 304 个对象组成的整齐网格，但单个标签和箭头已经太小，不能据此通过出版尺寸可读性或全局连线美观。保存/重开 SVG 字节完全相同，revision 16 与 pinned features 保持。

旧的 `10-collapsed-current.png`、`11-reexpanded-current.png`、`13-reopened16.png` 与其 JSON 命名状态错帧，另有四张移动 PNG 仍显示旧坐标；这些原始文件没有删除，报告中逐项列为排除。当前阶段仍是 M4 partial、M5 not started；没有模型执行、语义写回、真实研究者、180 秒任务率、出版人工审看或 presented FPS 认证。
