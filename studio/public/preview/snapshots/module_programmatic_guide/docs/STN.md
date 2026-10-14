# STN：图像定位、仿射网格与原图采样

本例只绘制官方教程的 **`Net.stn(x)` 子模块**，并取证构造器中它实际调用的 `localization` 和 `fc_loc`。输入与输出均为 `[B,1,28,28]`。`Net.forward` 中后续分类卷积、Dropout、全连接层和 `log_softmax` 不在本图范围内。

来源入口是固定 Awesome-pytorch-list 中的 [pytorch tutorials 条目](../upstream/Awesome-pytorch-list/README.md)。实际实现冻结为 `pytorch/tutorials` 提交 `ce8d551d11baebcf8064be3caba7b28a4d84a15d`；[源码副本](../sources/pytorch-tutorials-stn/intermediate_source/spatial_transformer_tutorial.py) 和 [许可证](../sources/pytorch-tutorials-stn/LICENSE) 一并保存。适配器为 [stn.py](../module_adapters/stn.py)，源码与版本摘要由 [source_manifest.json](../source_manifest.json) 绑定。

## 每个图框对应什么

| 图框 / 稳定 ID | 源码位置 | 对应理由 |
|---|---|---|
| `stn.localization` / Locate transform | `Net.__init__` 第103–110行；`Net.stn` 第125行 | 一个真实 `nn.Sequential` 实例；内部顺序是 Conv、Pool、ReLU、Conv、Pool、ReLU，不把两层卷积画成并行分支 |
| `stn.flatten` | `Net.stn` 第126行 | 对10×3×3的定位特征作 `view`，得到90维特征；不是对原始28×28图像作 Flatten |
| `stn.fc1`、`stn.relu`、`stn.fc2` | `Net.__init__` 第113–117行；`Net.stn` 第127行 | `fc_loc` 的三个真实子模块，对应90→32→6的仿射系数回归器 |
| `stn.theta` | `Net.stn` 第128行 | 把每张图的六个系数解释为2×3仿射矩阵，得到 `[B,2,3]` |
| `stn.grid` | `Net.stn` 第130行 | 对应一次真实 `F.affine_grid(theta, x.size())` 库调用；输入包括 theta 数值和原图 shape |
| `stn.sample` | `Net.stn` 第131行 | 对应一次真实 `F.grid_sample(x, grid)`；第一项是原始图像，不是定位特征、theta或网格本身 |
| `stn.output` | `Net.stn` 第133行 | 返回采样后的图像张量；没有分类 logits、概率或 tuple |

`Net.__init__` 还定义了分类器成员 `conv1`、`conv2`、`conv2_drop`、`fc1`、`fc2`。它们与 `localization.0/.3`、`fc_loc.0/.2` 是不同参数身份；不能因为同在一个构造器内就全部纳入 STN 图。

## 静态形状与参数身份

所选28×28输入经过以下顺序。卷积默认 stride=1、padding=0；MaxPool 的 kernel和stride均为2。

```text
[B,1,28,28]
  → Conv7×7 1→8       [B,8,22,22]
  → MaxPool2 + ReLU   [B,8,11,11]
  → Conv5×5 8→10      [B,10,7,7]
  → MaxPool2 + ReLU   [B,10,3,3]
  → view             [B,90]
  → Linear90→32 → ReLU → Linear32→6
  → view theta       [B,2,3]
  → affine_grid      [B,28,28,2]
  → grid_sample      [B,1,28,28]
```

四个含可学习参数的实例是 `localization.0`、`localization.3`、`fc_loc.0`、`fc_loc.2`，各有 weight与bias，共八个参数张量。两个池化、三个 ReLU、两个 view以及两个网格函数不引入可学习参数。

构造器将 `fc_loc.2.weight` 置零，将 bias设置为 `[1,0,0,0,1,0]`，因此刚初始化的仿射回归器输出恒为单位矩阵。这是**初始化状态**，训练可以改变其 weight和bias。图中仍保留真实 Linear参数，不能把它替换为永远不变的 Identity算子。绘图过程没有运行这个初始化。

## 为什么必须有两条不同的旁路

主链传递定位结果，按源码顺序自底向上排布。旁路分别携带原图的不同信息：

| 边 | 语义 IR | 实际用途 |
|---|---|---|
| 原图 → `affine_grid` | `role=shape_dependency`，`shape→size`；虚线 | `x.size()` 提供输出网格的 batch、通道和空间大小；不向网格生成器传递图像灰度值 |
| 原图 → `grid_sample` | `role=retained_image`，`image→image`；实线 | 保留原始像素，按新网格采样；必须绕过定位网络、参数回归和网格生成 |
| `affine_grid` → `grid_sample` | 主链 tensor边；`sample.main_input=grid` | 主链到达采样器的张量是网格，采样器的另一个数值操作数来自原图旁路 |

这三项依赖对应 `F.grid_sample(x, grid)` 的两个数值操作数，以及 `F.affine_grid(theta, x.size())` 的 shape参数。两条旁路放在不同侧的留白通道内，进入算子前提前转弯；不能把虚线和实线都解释成图像复制，也不能把形状信息误当作一条新的特征分支。

## 网格说明与库边界

`grid` 最后一维是 `(x,y)` 输入采样坐标。它采用归一化坐标约定；坐标可以落到图像范围之外。概念上的标准API关系是：

```text
[x_input, y_input] = theta @ [x_output, y_output, 1]
```

这是对 `affine_grid` 含义的辅助说明，图中没有伪造源码未写出的矩阵乘法、inverse(theta)、坐标归一化或插值内核节点。`F.affine_grid` 与 `F.grid_sample` 均标记为 `opaque_runtime_boundary=True`：本例冻结了教程调用方，没有冻结或展开 PyTorch functional内核。

**源码没有指定 `align_corners`。** 两个调用都保留 `align_corners_argument='omitted'`。现代 PyTorch API文档的默认值是False；`grid_sample` 的现代默认 mode为bilinear、padding_mode为zeros。这些属于API上下文，不是本文件显式传入的参数，也不是本次运行观察到的结果。本例没有执行教程，不能声称确认了某个实际运行环境的采样结果或旧版本默认行为。

## 三种粒度怎样分配布局

概览保留原图、整个 `Net.stn` 模块与变换图像。模块视图展开 Localization、Affine regressor、Grid + image resampling三个阶段。详细视图展开定位网络六个真实子模块、view和回归器，以及两个独立 functional调用。

所有链按源码输入→输出声明，绘图引擎把后续节点放到更高位置。宽度由标题、shape和最宽子项计算；高度累加子项、标题留白与间距。两条跨层旁路通过命名语义端口路由，折叠时投影到最近可见祖先，保留其原始依赖身份。

`validate_ir()` 核对模块范围、Conv/Pool/ReLU顺序、空间shape、90→32→6、单位仿射初始化、原图像素与shape两种来源，以及未显式指定的API参数。布局与实际SVG核验另检查框包含、文字、正交边、末段和边框间距。所有核验只运行绘图原型，不执行上游模型。

独立源码契约与错误注入检查持久保存在 [checks/spatial_modules.py](../checks/spatial_modules.py)。它直接从冻结源码AST计算卷积/池化尺寸、核对参数身份和两个原图旁路，并检查错误像素来源、伪造 `align_corners=True`、错误初始化等负例；改变冻结源文件也必须被SHA检查拒绝。在本原型目录内运行：

```bash
PYTHONDONTWRITEBYTECODE=1 python3 checks/spatial_modules.py
```

该命令同时验证STN与PixelShuffle，不依赖已有的生成图或临时预览；取证副本和故意改错的源文件副本位于自动清理的临时目录，上游教程与模型不会执行。
