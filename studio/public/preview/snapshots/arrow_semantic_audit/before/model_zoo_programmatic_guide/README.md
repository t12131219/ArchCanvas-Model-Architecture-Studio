# 模型目录与跨模型程序化架构图原型

本目录把 Transformer 的程序化绘图方法扩展到四个批次，并补充 **显式四门 LSTM 的循环单元专题**。第一批为 **CNN（LeNet5）、ResNet18、DenseNet、U-Net、VAE、LSTM**，第二批为 **分组 AlexNet、MobileNetV2、NiN、TextCNN、卷积自编码器、DCGAN**，第三批为 **VGG16、ResNet50、卷积 VAE、条件卷积 VAE、Packed GRU、多层双向 LSTM**。第四批为 **MobileNetV3-Large、ResNet101、VGG19 型、卷积 GAN、卷积 WGAN、固定邻接 GraphNet**。目前共 25 个实现，每个有概览、模块、详细三个粒度，共 75 张 SVG，以及对应的 PNG、源码证据、语义 IR 和布局记录。

这是一个可离线复现、可继续扩展的原型：**源码取证和图像生成由程序完成；模型语义由逐份审阅源码后编写的适配器明确描述。** 当前没有实现输入任意源码便自动恢复正确模型结构的功能，也没有接入 ArchCanvas Studio 的可编辑画布或历史系统。

[全部模型图像总览](generated/index.html) · [循环单元专题](generated/index_cell_examples.html) · [第四批预览](generated/index_batch4.html) · [第三批预览](generated/index_batch3.html) · [第二批预览](generated/index_batch2.html) · [第一批预览](generated/index_batch1.html) · [可搜索模型与资源清单](catalog/index.html) · [全部 Notebook 路径](catalog/notebooks.html) · [导出核验报告](generated/export_checks.json)

## 显式四门 LSTM：从参考框架图到真实源码

新增 [LSTM 门级三粒度预览](generated/lstmcell/index.html)、[详细 SVG](generated/lstmcell/figure3_detailed.svg) 和 [逐项对应说明](docs/LSTMCell.md)。来源是官方 `pytorch/pytorch` 的 `benchmarks/fastrnns/custom_lstms.py`，固定 v2.5.1 提交 `a8d6afb511a69687bbb2b7e88a3cf67917e1697e`。它在 Python 中显式定义标准 `LSTMCell` 的四门公式与 `LSTMLayer` 的时间循环，适合绘制用户提供的门级参考图；原有 Packed LSTM 和 BiLSTM 仍保留各自的模型/调用方图。

这里选定 `LSTMLayer(LSTMCell, input_size=8, hidden_size=16)` 和 `T=3` 作为可读的静态例子，B 保持符号维。8/16/3 是明确指定的绘图配置，不是从参考图或上游默认值猜出的配置。初始 h/c 由调用方提供，不虚构隐式零初态。

外层三个时间步从左到右排列，仅展开中间一个 Cell；内部算子依赖仍自底向上。两条跨时间线分别传递 h 和 c，所有 Cell 使用同一 `self.cell` 实例及四份参数。详细图展示源代码实际的两次 MatMul、两项 bias、`chunk(4,1)`、三次 Sigmoid、候选 Tanh、两项 cell 乘法/相加、cell Tanh 与输出乘法。没有把参考图中的教学式 `[x,h]` 拼接画成源码存在的 Concat，也没有把四个门画成四个独立 Linear 模块。

该源码不在原两个目录的已选绘图路径中，因此清单用独立 `supplementary_examples` 记录它：原始 832 个条目与 183 个 Notebook 的范围保持不变，25 个绘图实现由原目录适配 24 个加专题 1 个组成。

仅重建本例：

```bash
python3 generate.py --model lstmcell --png
python3 verify.py generated --model lstmcell --png
python3 checks/lstmcell_semantics.py --out generated/lstmcell_semantic_review.json
python3 checks/lstmcell_geometry.py --out generated/lstmcell_geometry_review.json
```

[审阅记录](generated/lstmcell_review.json) 保存官方来源核对、逐条边审阅、语义/几何负例和旧文件保留结果；[语义复查脚本](checks/lstmcell_semantics.py) 用独立的公式绑定表核对 88 条真实边，并检查 12 个故意改错的负例。[几何复查脚本](checks/lstmcell_geometry.py) 核对实际 SVG、三层投影、x/Cell 列对齐、独立 h/c 端口、24px 起止直段和 8px 平行边框间距。检查只运行本原型的适配器和验证器，不执行上游模型。

## 第四批模型

本批扩展精确版本的 SE/深度卷积、长重复瓶颈、无统一 forward 的 GAN 调用方 DAG，以及固定邻接矩阵的图计算。新来源使用独立 `deeplearning-models-batch4` 和 `torchvision-v0.9.0-mobilev3` 快照键；旧19个模型目录保留原字节内容，循环单元专题也完整保留。

| 实现 | 必须保留的源码事实 | 预览 | 详细 SVG | 对应关系说明 |
| --- | --- | --- | --- | --- |
| MobileNetV3-Large | v0.9.0；15个IR/8个SE/10个identity Add；SE为Hardsigmoid，project为Identity；64-crop，960→1280→10头 | [预览](generated/mobilenetv3/index.html) | [详细图](generated/mobilenetv3/figure3_detailed.svg) | [说明](docs/MobileNetV3.md) |
| ResNet101 | CIFAR-10 32×32；Bottleneck ×[3,4,23,3]；4个首块投影/29个identity；原Notebook无eval，BN使用训练batch统计；AvgPool未调用 | [预览](generated/resnet101/index.html) | [详细图](generated/resnet101/figure3_detailed.svg) | [说明](docs/ResNet101.md) |
| VGG19 型 | 源类名仍VGG16；实际16Conv+3Linear，深度[2,2,4,4,4]；CIFAR32；无生效Dropout/AvgPool | [预览](generated/vgg19/index.html) | [详细图](generated/vgg19/figure3_detailed.svg) | [说明](docs/VGG19.md) |
| 卷积 GAN | MNIST28；G有4次转置卷积7→13→25→27→28；D有2Conv；三次调用点共用D参数，只有D训练fake路径detach；raw logits进入BCEWithLogits | [预览](generated/convgan/index.html) | [详细图](generated/convgan/figure3_detailed.svg) | [说明](docs/ConvGAN.md) |
| 卷积 WGAN | 相同G，D有3Conv、Flatten512→Linear1；Uniform[0,1]；原Wloss符号/5critic更新/RMSprop/clamp保留；无Sigmoid | [预览](generated/dcwgan/index.html) | [详细图](generated/dcwgan/figure3_detailed.svg) | [说明](docs/DCWGAN.md) |
| 固定邻接 GraphNet | MNIST784像素图；`exp(-dist/sigma²)`不是距离平方；阈值/degree归一化后的A为buffer；一次bmm→无bias Linear784→10→logits/probas | [预览](generated/graphnet/index.html) | [详细图](generated/graphnet/figure3_detailed.svg) | [说明](docs/GraphNet.md) |

GAN 图将 caller 的数据依赖与模型容器分开：并列的三个 D 图框表示三种真实调用点，参数身份相同；不是三个独立判别器或共同返回 tuple。WGAN 的重复训练循环没有展开为逐次执行轨迹。GraphNet 的 A 构造放在独立配置面板，通过 buffer 来源线进入 forward；不把一次构造误画为每次图像输入都会计算的层。

本批的 [导出核验报告](generated/export_checks_batch4.json) 覆盖18个新视图；[源码交叉审阅、负例与旧文件保留记录](generated/batch4_review.json) 保存独立审阅结论与语义/取证负例。形状和依赖来自静态审阅，没有执行或训练任何上游模型。

可复查 [14个语义与顶层 caller 取证负例](generated/batch4_semantic_review.json)：

```bash
python3 checks/batch4_semantics.py
```

## 第三批模型

本批保持前两批模型产物，并扩展瓶颈残差、图像条件通道、随机潜变量和循环层/方向的结构表达。来源仍是同一固定 rasbt 提交，但使用独立 `deeplearning-models-batch3` 快照，避免改变旧图的源码摘要。所有形状均为所选配置下的静态推导。

| 实现 | 必须保留的源码事实 | 预览 | 详细 SVG | 对应关系说明 |
| --- | --- | --- | --- | --- |
| VGG16 | CIFAR-10 32×32；13 个 Conv，block 深度 [2,2,3,3,3]；512→4096→4096→10；注释中的 Dropout/AvgPool 未执行 | [预览](generated/vgg16/index.html) | [详细图](generated/vgg16/figure3_detailed.svg) | [说明](docs/VGG16.md) |
| ResNet50 | MNIST 28×28；Bottleneck expansion=4，[3,4,6,3]；实际 factory 名为 resnet34；四个 stage 首块均投影，AvgPool 未调用 | [预览](generated/resnet50/index.html) | [详细图](generated/resnet50/figure3_detailed.svg) | [说明](docs/ResNet50.md) |
| 卷积 VAE | latent=15；encoder 28→12→5→2；转置卷积 decoder 2→4→11→28；eval 仍随机采样；返回 μ/logvar/z/decoded | [预览](generated/convvae/index.html) | [详细图](generated/convvae/figure3_detailed.svg) | [说明](docs/ConvVAE.md) |
| 条件卷积 VAE | latent=50；标签注入 encoder 的 11 通道图像和 decoder 的 60 维输入；forward 重建 11 通道，不仅一张灰度图 | [预览](generated/ccvae/index.html) | [详细图](generated/ccvae/figure3_detailed.svg) | [说明](docs/CCVAE.md) |
| Packed GRU | 单层单向 128→256；外部 lengths 驱动 packing；只取 hidden 分类；无 LSTM cell；Sigmoid 属于调用方 | [预览](generated/gru/index.html) | [详细图](generated/gru/figure3_detailed.svg) | [说明](docs/GRU.md) |
| 多层双向 LSTM | AG News；两层双向；拼接最后层 hidden[-2]/[-1] 为 512；同一 Dropout 实例调用三次；词表 vectors 未复制到 Embedding | [预览](generated/bilstm/index.html) | [详细图](generated/bilstm/figure3_detailed.svg) | [说明](docs/BiLSTM.md) |

本批的 [导出核验报告](generated/export_checks_batch3.json) 覆盖 18 个新视图；[交叉审阅、负例与旧文件保留记录](generated/batch3_review.json) 保存六个被拒绝的关键语义错误，以及前两批 230 个模型文件逐字节一致的核对结果。

## 第二批模型

本批增加新的算子和拓扑类型，并保留第一批各模型文件的原始内容。两批共享绘图引擎，但源码清单使用独立快照键；新增文件不会改变第一批的取证摘要。

| 实现 | 新增的结构覆盖与所选源码事实 | 预览 | 详细 SVG | 对应关系说明 |
| --- | --- | --- | --- | --- |
| 分组 AlexNet | CIFAR-10 64×64；Conv2–5 为 groups=2；AdaptiveAvgPool 输出 6×6；Softmax 已计算但未返回 | [预览](generated/alexnet/index.html) | [详细图](generated/alexnet/figure3_detailed.svg) | [说明](docs/AlexNet.md) |
| MobileNetV2 | Notebook 指定 torchvision v0.9.0；深度卷积、线性瓶颈与条件 residual；替换分类层 1280→10 | [预览](generated/mobilenetv2/index.html) | [详细图](generated/mobilenetv2/figure3_detailed.svg) | [说明](docs/MobileNetV2.md) |
| Network in Network | 三组空间卷积与 1×1 卷积；末端类别通道仍有 ReLU；固定 AvgPool8，返回 logits/probas | [预览](generated/nin/index.html) | [详细图](generated/nin/figure3_detailed.svg) | [说明](docs/NiN.md) |
| TextCNN | k=3/4/5 三条独立 Conv1d 分支；真实 lengths mask 后全局最大值；Concat384→Linear2 | [预览](generated/textcnn/index.html) | [详细图](generated/textcnn/figure3_detailed.svg) | [说明](docs/TextCNN.md) |
| 卷积自编码器 | MNIST 28×28；两次 nearest 插值重建，非转置卷积；末端 LeakyReLU→Sigmoid | [预览](generated/convae/index.html) | [详细图](generated/convae/figure3_detailed.svg) | [说明](docs/ConvAE.md) |
| DCGAN | CelebA 64×64；两独立入口 G/D；显示调用方 z→G→D 组合，不虚构 DCGAN.forward | [预览](generated/dcgan/index.html) | [详细图](generated/dcgan/figure3_detailed.svg) | [说明](docs/DCGAN.md) |

## 第一批模型

以下名称指所选实现与配置，不泛指同名模型的所有变体。形状来自静态推导，`B` 为符号化 batch 维度。

| 类别 / 实现 | 所选配置及必须保留的源码差异 | 三粒度预览 | 详细 SVG | 对应关系说明 |
| --- | --- | --- | --- | --- |
| CNN / LeNet5 | MNIST 调用方 resize 到 32×32；Tanh、MaxPool；400→120→84→10；返回 logits 和概率 | [预览](generated/lenet/index.html) | [详细图](generated/lenet/figure3_detailed.svg) | [说明](docs/LeNet.md) |
| ResNet18 | MNIST 28×28；BasicBlock ×[2,2,2,2]；stage 2–4 首块为投影 shortcut；forward 没有调用已声明的 AvgPool | [预览](generated/resnet/index.html) | [详细图](generated/resnet/figure3_detailed.svg) | [说明](docs/ResNet.md) |
| DenseNet-BC-100 | CIFAR-10；k=12、压缩率 0.5；每块 16 个独立 Bottleneck；Concat 累积通道；选定 B>1 | [预览](generated/densenet/index.html) | [详细图](generated/densenet/figure3_detailed.svg) | [说明](docs/DenseNet.md) |
| U-Net | 默认 in=3 / out=1 / f=32，256×256 例子；BN 双卷积、转置卷积；pool 前特征经 Concat；最终 Sigmoid | [预览](generated/unet/index.html) | [详细图](generated/unet/figure3_detailed.svg) | [说明](docs/UNet.md) |
| 全连接 VAE | MNIST 784→500；独立 μ/logvar 头，latent=15；内部随机采样；返回 μ、logvar、z、decoded | [预览](generated/vae/index.html) | [详细图](generated/vae/figure3_detailed.svg) | [说明](docs/VAE.md) |
| Packed LSTM | IMDB；Embedding 128、单层单向 LSTM 256；lengths 驱动 packing；最终 hidden 分类；Sigmoid 在调用方 | [预览](generated/lstm/index.html) | [详细图](generated/lstm/figure3_detailed.svg) | [说明](docs/LSTM.md) |

这四批没有新增各模型专用的基础 PNG。图像由所选源码构造；说明文件逐项列出与常见论文图、教材图的差异。此前的 [Transformer 原型](../transformer_programmatic_guide/README.md) 和 [四个时间序列模型原型](../timeseries_programmatic_guide/README.md) 保留在各自目录。

## 目录收录范围与来源

从用户指定的两个仓库提取固定版本目录，保留原始分类与出处：

| 上游 | 固定提交 | 本目录的处理 |
| --- | --- | --- |
| [Awesome-pytorch-list](https://github.com/bharathgs/Awesome-pytorch-list) | `06e9786eb64392cbe233d1a9ab7489256c0ac521` | README 中 706 个带链接的编号资源，含库、教程、工具、论文实现 |
| [deeplearning-models](https://github.com/rasbt/deeplearning-models) | `59beda3aa25337e576564f1c18c6edd26f9f30e3` | README 中 126 个 Notebook 表行；Git tree 中全部 183 个 Notebook 路径 |
| [densenet.pytorch](https://github.com/bamos/densenet.pytorch) | `d1cd5e1957975628286e516512c6d1c14430f810` | Awesome 所列项目；取证 `densenet.py`、`train.py` |
| [brain-segmentation-pytorch](https://github.com/mateuszbuda/brain-segmentation-pytorch) | `d45f8908ab2f0246ba204c702a6161c9eb25f902` | Awesome 所列项目；取证 `unet.py`、`train.py` |

MobileNetV2 与 MobileNetV3-Large 还固定了 [pytorch/vision](https://github.com/pytorch/vision) 的 `v0.9.0` 实现，确切提交 `01dfa8ea81972bb74b52dc01e6a1b43b26b62020`。Notebook 配置与外部实现的证据分别保留，不把 torchvision 代码的出处写成 rasbt。

**832 个目录条目不等于 832 个独立模型。** 同一模型的不同框架、数据集、训练方式按上游目录保留；“仅收录”条目尚未有源码适配器。外部项目未递归枚举其全部实现。183 个 Notebook 中有 21 个没有出现在 README 表行中，另有 5 个 README Notebook 链接不在固定 Git tree 中，清单保留并标记这类上游错链；第二批分组 AlexNet 已审阅实际存在的路径，单独记录修正关系。

可下载 [条目 CSV](catalog/models.csv)、[Notebook CSV](catalog/notebooks.csv)，或者读取 [models.json](catalog/models.json)。JSON 同时保存原始条目、分类、行号、Notebook 路径及 Git blob SHA；固定 README、Git tree 与提交记录在 [catalog/upstream](catalog/upstream)。这些索引并不表示已经下载、执行或适配全部列出的模型。

实际绘图源码及许可证保存在 [sources](sources)，其文件 SHA-256、固定 URL 和 Notebook 派生映射由 [source_manifest.json](source_manifest.json) 管理。

## 快速使用

只查看结果时直接打开 [generated/index.html](generated/index.html)。总览可以在三个粒度之间切换；每个模型页面提供 SVG、布局记录、逐节点源码映射和证据 JSON。图框悬停提示包含文件、符号、起始行号和参数路径。

生成 SVG 与目录只需要 Python 3.10+ 标准库。PNG 导出另外需要 `rsvg-convert`，并建议安装 DejaVu Sans 字体以保持外观一致。本批不依赖 PyTorch、训练环境或预训练权重。

在本目录运行：

```bash
# 所有源码已随原型保存；此命令不需要联网
python3 generate.py

# 同时生成 PNG
python3 generate.py --png

# 核对 25 个模型、三粒度导出；--png 额外检查 PNG 文件与尺寸
python3 verify.py generated --png

# 从已保存的 README 与 tree 快照重新生成目录
python3 catalog.py
```

继续迭代第四批时可只重新生成该批，保留其他模型文件：

```bash
python3 generate.py --batch batch4 --png
python3 verify.py generated --batch batch4 --png
```

总览与验证记录自动合并已有产物；不重新渲染其他批次。只迭代一个模型时，也可以使用独立输出目录：

```bash
python3 generate.py --model unet --out scratch/unet --png
```

`--model` 接受 `all` 和 [models.py](models.py) 中注册的 25 个键；`--batch` 接受 `all / batch1 / batch2 / batch3 / batch4 / cell_examples`。`--out` 指定产物目录，`--source-root` 指定保存源码的根目录。`verify.py` 同样支持 `--batch`、`--model`；选定范围的报告保存为 `export_checks_<batch或model>.json`，全量核验保存为 `export_checks.json`。例如单模型可运行 `python3 verify.py scratch/unet --model unet --png`。

如果来源文件丢失，可以恢复固定快照：

```bash
python3 fetch_sources.py
```

该命令验证现有文件，缺失或哈希不匹配时才从 manifest 的固定 URL 获取源码，并复现 Notebook 的派生 `.py` 与 cell 行号映射。它不会更新到上游最新版本，也不会执行 Notebook。更换源码版本需要先审阅适配器与配置，不能只更改 `--source-root`；哈希不同会阻止生成。

## 文件与流水线

```text
固定源码 / 原始 Notebook / 配置 / 必要的外部实现
          ↓ AST 符号、片段、原 cell 行号与哈希
adapters/<model>.py 的审阅语义
          ↓ 模块树、算子、端口、边、参数身份与来源证据
semantic_ir.json
          ↓ 粒度投影、递归测量、自底向上放置、正交路由
SVG + layout_<view>.json
          ↓ 导出一致性与几何检查；人工视觉核对
PNG / HTML / source_map.md / export_checks.json
```

| 文件 / 目录 | 用途 |
| --- | --- |
| [spec.py](spec.py) | `op / chain / parallel / graph / ref` 的显式适配器契约 |
| [models.py](models.py) | 批次与模型注册表；生成和验证共享同一范围 |
| [adapters](adapters) | 25 个模型的源码语义、选定 profile、参数身份、分支和展开策略；第三、四批与循环单元专题另含 `validate_ir` 关键事实校验 |
| [evidence.py](evidence.py) | 固定源码验证、AST 定位、来源副本、语义 IR 输出 |
| [notebook_source.py](notebook_source.py) | 顺序提取 code cell；保留 cell / cell_line / derived_line 映射 |
| [theme.py](theme.py) | 字体、字号、颜色、边框和视觉角色；不决定数学语义 |
| [layout.py](layout.py) | 粒度投影、文字测量、模块尺寸、位置、端口、路线及几何约束 |
| [generate.py](generate.py) | 按模型或批次生成三粒度、映射表和预览页面；区分参数路径与无权重模块的实例身份 |
| [verify.py](verify.py) | 对最终 SVG 原语、来源证据、IR 与 PNG 进行一致性核验 |
| [catalog.py](catalog.py) | 离线解析已固定的 README / Git tree，生成目录输出 |
| [fetch_sources.py](fetch_sources.py) | 可选恢复 manifest 内的固定模型源码 |
| [docs](docs) | 每个模型的配置、源码对应、排布与边界解释 |
| [checks/lstmcell_semantics.py](checks/lstmcell_semantics.py) | 独立门级绑定表与 12 个语义负例；读取已生成 IR，不执行上游模型 |
| [checks/lstmcell_geometry.py](checks/lstmcell_geometry.py) | 实际导出、显式投影、端口、边框间距与几何负例 |
| [checks/batch4_semantics.py](checks/batch4_semantics.py) | 第四批六模型关键事实与14个故意改错的语义/模块范围证据负例 |

每个 `generated/<model>/` 有以下记录：

- `figure1_overview.svg`、`figure2_modules.svg`、`figure3_detailed.svg`，可选对应 PNG。
- `semantic_ir.json`：稳定节点 ID、层级、语义端口、数据边、选定配置、参数路径及证据编号。
- `source_evidence.json` 与 `sources/`：使用的固定文件、AST 范围、片段、Notebook 原 cell 映射、许可证。
- `source_map.md`：人可读的逐节点对应关系；`profile.json`：静态配置。
- `layout_<view>.json`：实际边框、文字估计范围、几何端口与路线；`visual_style.json`：实际绘图主题。
- `layout_checks.json`：生成时检查；总目录的 `export_checks.json`：最终文件核验。

## 源码结构如何对应到图框

源码不能仅靠 `__init__` 的声明顺序转成架构图。适配器同时审阅构造函数、`forward`、辅助函数及调用方配置，区分实际执行、未执行声明、保留张量和调用方操作。

| 源码事实 | IR / 图像表达 | 原因 |
| --- | --- | --- |
| 连续调用 A→B→C | `chain(items=[A,B,C])` | 按真实依赖顺序画；几何坐标把列表首项放在最下方 |
| 同一个 x 送给两条分支 | `parallel(..., dispatch=False)` | 这是输入复制；两条分支接收同一张量 |
| 多操作数 DAG / 时间单元 | `graph(..., ranks=...)` + `extra_edges` | ranks 只分配自底向上的层级位置；graph 不自动添加串联、分发、收集或容器边界的数据边 |
| tuple 中不同字段送给分支 | `dispatch=True` + `input_selector` | 字段选择与输入复制不同，不能混为一谈 |
| 张量值、shape 引用和外部参数共同构造操作数 | `semantic_mode='operand_bundle'` + `child_inputs` | 逻辑操作数分组不等于源码 tuple；TextCNN 的 count 只吃 lengths，positions 只引用 features.shape |
| 分支返回 tuple/list | `tuple_collection` | 汇集总线不表示 Add 或 Concat；算术合并必须有显式节点 |
| 残差相加 / 通道拼接 | 独立 Add / Concat 节点 + 指定侧输入 | ResNet 和 U-Net/DenseNet 的数学操作不同 |
| 同类层多次独立构造 | 不同参数路径；`repeat.independent_parameters=True` | 结构相同不代表共享权重 |
| 同一无权重模块被多次调用 | 不同节点 ID 与同一 `instance_identity` | BiLSTM 的三次 Dropout 使用同一实例；训练时不共享同一随机 mask，eval 时都不生效 |
| nn.LSTM 库调用 | 明确库边界；记录时间上的参数复用 | 本 Notebook 没有定义门级实现，不能声称四门是从本源码提取 |
| 显式 LSTMCell 四门实现 | 两份 4H 矩阵与 bias + chunk 字段 + 门激活 + 状态运算 | 四门的不同参数行切片与同一 Cell 的时间复用是两种不同关系 |
| 训练 loop / caller 操作 | 单独调用方边界或另图范围 | LSTM caller Sigmoid 可展示；VAE 的 KL/BCE 不属于 forward |

例如 U-Net 的 skip 对应真正的 `enc1`，而不是其后 `pool1(enc1)`：

```python
# 摘自 sources/brain-segmentation-pytorch/unet.py 的 forward
enc1 = self.encoder1(x)
enc2 = self.encoder2(self.pool1(enc1))
# ... enc3 / enc4 / bottleneck / decoder4 / decoder3 / decoder2 ...
dec1 = self.upconv1(dec2)
dec1 = torch.cat((dec1, enc1), dim=1)
dec1 = self.decoder1(dec1)
```

适配器将 pooling 保持为独立主链节点，并明确保留旁路：

```python
# adapters/unet.py 使用的边契约；这里只展示一条
edge = dict(
    src="unet_enc1", dst="unet_dec1_cat", role="skip_concat",
    label="enc1: 32 channels", src_port="skip", dst_port="side",
)
```

`src_port / dst_port` 是语义端口。绘图再分配实际几何端口，例如右侧的 `right.aux0`；布局记录同时保留原端口及折叠后的可见节点，避免为避障移动路线时悄悄改变数据来源。

LSTMCell 的 `graph` 容器只声明层级归属，全部真实数据流由 `extra_edges` 明确绑定。`ranks` 从底到顶列出每个直接子节点，且必须各出现一次；同一层内从左到右排列。`align_x` 用子节点 ID 对齐另一层的子节点，例如让每个 x_t 位于对应 Cell 的正下方；测量阶段预留列宽，未知目标或循环对齐会被拒绝。`src_side / dst_side` 选择上、下、左、右几何入口，`in.auxN / out.auxN / left.auxN / right.auxN` 将多条线错开。几何槽与 `item[0]`、`state_cell` 等语义字段独立，不改变字段绑定。显式门级计算和 h/c 时间递推使用实线；不能根据实线或虚线决定张量是否参与计算。

第二批还补充了 `shape_dependency / value_operand / operand_collection`。TextCNN 的三个实际 Conv 分支仍由同一 embedding 值分发，结果形成源码中的 pooled list；每条分支内部的 features / mask、有效窗口数 / positions 只是逻辑操作数分组。`child_inputs` 记录真实 producer、value/shape/external 角色和来源端口。对于只由外部 lengths 产生的计数，`suppress_input_boundary=True` 抑制不存在的主输入箭头；shape 引用画虚线并在悬停提示中注明。相应布局中的本地接入线是容器内的显示投影，真实 producer 仍由 IR 和 `operand_binding` 记录。

可用以下脚本查看已生成的对应关系，完全不执行模型：

```python
import json
from pathlib import Path

root = Path("generated/unet")
ir = json.loads((root / "semantic_ir.json").read_text())
nodes = {n["id"]: n for n in ir["nodes"]}
for e in ir["edges"]:
    if e["role"] == "skip_concat":
        src, dst = nodes[e["src"]], nodes[e["dst"]]
        print(src["label"], "->", dst["label"], src["source_evidence"])
```

## 三粒度、紧凑程度与箭头排布

三个视图投影自同一份 IR。`expand` 和 `view_overrides` 控制容器何时展开；折叠不会改变源码事实。端点在当前粒度不可见时，辅助边投影到最近的可见祖先；已经封装在同一边界内部的边不重复绘制。

详细图也不强制穷举所有重复算子。DenseNet 用 `j=0…15` 的符号化 Bottleneck 模板表达 16 次顺序应用及独立权重；U-Net 的完整 IR 有九个双卷积块，详细视图代表性展开 encoder1、bottleneck、decoder1，其他块保留形状、参数身份和容器。第二批中，MobileNetV2 代表展开无 expansion、带 expansion、带 identity shortcut 的三类块；DCGAN 代表展开 G/D 两端 stage。TextCNN 完整展开 k=3 的 mask，折叠 k=4/5 的同型操作数容器，详细图宽度由 5354 px 减至 3330 px；全部 54 个语义节点及三个独立 lengths 依赖仍保留在 IR。第四批 MobileNetV3 的全部15份 block 都保留完整算子 IR，详细图只展开IR1/4/12；ResNet101将第三stage的22个identity表达为独立参数重复模板；GAN三次D调用共用参数，仅代表性调用展开。各模型说明列出折叠策略。这些都是控制图面大小的明确显示策略，详见各模型说明。

当前布局规则为：

1. **先测量，再放置。** 估计标题、shape、详情与证据行所需空间；叶子框高度随内容增加。容器根据子节点大小递归计算，而非使用每个模型的一组固定坐标。
2. **主链自底向上。** `chain` 顺序来自适配器；容器与内部算子遵守相同方向。并列分支各自向上，并保留独立列和分发/收集总线。
3. **按分组统一宽度。** 主要阶段通过 `fill_width` 填满容器有效宽度，标题更整齐；算子保留紧凑本征宽度。基础间距 `GAP=24`、内边距 `PAD=32`，顶部空间根据标题动态增加。
4. **长依赖使用侧边走廊。** U-Net skip、VAE 保留统计量、LSTM lengths 有独立辅助边；正交 A* 依据障碍边界选择路线，同端口侧面有多条边时分配错开的接入点。
5. **提前转弯。** 原有侧边辅助线起止各留 24 px 水平直段；LSTMCell 的上下/左右显式端口起止各留 24 px 法向直段，其平行于边框的线段与边框至少相隔 8 px。所有有箭头路线末段至少 18 px。路线不得沿框边重叠，也不得穿过无关叶子节点。
6. **长旁路分开走廊。** `skip_concat` 与 `retained_value` 给不同边配置不同的优先纵向通道；路由器禁止不同来源张量的辅助边共用线段。标签在路线规划完成后放到走廊外，悬停依赖线可查看真实来源与端口。依赖线的正交交叉仍可能存在，尤其是多字段 VAE；不宣称全图无交叉。

原有链式/分支例子中，虚线表示主链外的显式依赖，包括真实 skip、保留返回值、随机源、辅助输入及 shape 引用；它不表示“这条边不参与计算”。LSTMCell 的显式 DAG 另用实线表达算子操作数和时间状态，并由标签区分字段。并列总线根据 IR 角色表达值分发、tuple/list 收集或逻辑操作数收集，不自动执行求和、拼接。每种数学融合仍由标签和 IR 区分。

字体采用 DejaVu Sans；主标题 30 px、主要模块标题约 22–24 px、算子 20 px、shape 16 px。深色边框配合浅蓝 Conv/MLP、黄色 Norm/Add/Concat、紫色 Linear/Output、粉色 Input/Embed、绿色概率/采样和橙色 Recurrent。Encoder/Decoder 采用浅蓝/浅粉容器，接近已有 Transformer 的风格。

**颜色编码视觉角色，标签与参数路径编码具体结构和身份。** Add、Norm、Concat 可以属于同一黄色图例，但不能因此推断它们是同一算子。相同模块样式也不能用于推断权重共享；参数独立性或时间复用必须看 IR。

## 核验覆盖与原型边界

最终全量核验覆盖 75 个视图：固定源码 SHA、提交及快照绑定、Notebook 派生行与原 cell 对应、AST 片段、IR 父子/端口关系、各模型关键语义、SVG 实际矩形与路线、主题配色与边框、PNG 存在及尺寸。第三、四批与循环单元专题的关键事实由 `verify.model_facts` 调用各适配器的 `validate_ir`，针对条件端点、隐藏状态选择、采样与残差顺序进行检查；这些审阅断言不能代替完整数值等价验证。

几何检查包括画布范围、子节点包含、同级框不重叠、端点注册、正交线、末段长度、主链方向、避免沿框边走线、无关叶子框避障、文字估计范围，以及不同来源辅助张量不共用线段。导出一致性检查读取实际 SVG；几何规则复用 `layout.validate`，不是第二套独立几何算法。

这些检查不能证明完整模型数值等价，也不能代替语义审阅和最终视觉检查。当前没有运行模型、训练、加载权重或验证现代运行环境兼容性。特别是 DenseNet 快照的全轴 `squeeze` 与缺少 `dim` 的旧 `log_softmax`，图与说明保留了选定 B>1 路径和兼容性边界。

文字测量使用保守的确定性字符宽度估计，未做字体引擎的真实 glyph 测量。跨平台字体变化、超长标题、更多辅助依赖都可能需要调整布局。当前长链模型采用纵向展开，适合 SVG 缩放阅读；若需要单页论文插图，可降低展开粒度或新增专门的显示模板。

## 后续接入新模型

1. 固定源码、入口、构造配置和模式，保存原始文件、许可证与哈希；Notebook 同时保存原始 cell 对应。
2. 从真实 `forward`、独立入口和辅助函数审阅数据路径、条件分支、张量保留、共享/独立参数及调用方边界。
3. 新增 `adapters/<key>.py` 的 `build()`，使用 `op / chain / parallel / graph`，为所有节点给出稳定 ID、来源符号和必要端口。对于库内细节，保留明确边界或另取该库版本源码。顶层 caller 可以引用 `__module__`，它表示 AST 模块的完整范围，不是虚构函数；具体调用和语义仍由适配器审阅。
4. 为三粒度设置展开策略、重复模板、视觉角色和主要模块等宽组；复用 `layout.py`，仅在结构确实需要时增加图元或布局规则。
5. 在 `models.py` 注册模型与批次，并为该模型的关键事实增加验证；第三批使用适配器 `validate_ir` 返回非空检查标签，语义不符时抛出 `ValueError`。新批次应同步扩展 `verify.model_facts` 的受控分派。编写源码对应与修正说明，查看实际导出。

适配器中的来源引用最小形式为：

```python
from spec import chain, op, ref

source = "deeplearning-models/pytorch_ipynb/cnn/cnn-lenet5-mnist.py"
evidence = [ref(source, "LeNet5.__init__"), ref(source, "LeNet5.forward")]
conv = op("lenet.conv1", "Conv2d 1 -> 6", "conv2d", evidence,
          shape="[B,6,28,28]", parameter="features.0")
```

这个调用建立可追溯的声明，并不会自动理解函数体中的所有运算。未来若接入 AST 规则、FX、`torch.export` 或运行时 shape tracing，它们应负责产生候选结构与证据，再进入同一 IR；控制流、packed sequence、随机采样和重复参数仍需要明确处理。当前可复用的核心是 **取证契约、语义 IR、三粒度投影、主题与布局/路由引擎**。
