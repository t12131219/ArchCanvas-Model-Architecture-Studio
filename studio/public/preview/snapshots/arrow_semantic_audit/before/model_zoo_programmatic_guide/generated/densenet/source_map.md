# DenseNet-BC-100：源码与图框对应

来源：`bamos/densenet.pytorch`，固定提交 `d1cd5e1957975628286e516512c6d1c14430f810`。

静态审阅适配器；没有导入或执行模型。Notebook 的行号指派生 Python，原始 cell 索引见下表与证据 JSON。

| 证据 | 文件与符号 | 行号 | 原始 Notebook cell（0起） |
|---|---|---|---|
| E001 | [densenet.pytorch/densenet.py](sources/densenet.pytorch/densenet.py) · `Bottleneck` | 18–33 | — |
| E002 | [densenet.pytorch/densenet.py](sources/densenet.pytorch/densenet.py) · `Bottleneck.__init__` | 19–27 | — |
| E003 | [densenet.pytorch/densenet.py](sources/densenet.pytorch/densenet.py) · `Bottleneck.forward` | 29–33 | — |
| E008 | [densenet.pytorch/densenet.py](sources/densenet.pytorch/densenet.py) · `Transition` | 47–57 | — |
| E009 | [densenet.pytorch/densenet.py](sources/densenet.pytorch/densenet.py) · `Transition.__init__` | 48–52 | — |
| E010 | [densenet.pytorch/densenet.py](sources/densenet.pytorch/densenet.py) · `Transition.forward` | 54–57 | — |
| E004 | [densenet.pytorch/densenet.py](sources/densenet.pytorch/densenet.py) · `DenseNet` | 60–116 | — |
| E005 | [densenet.pytorch/densenet.py](sources/densenet.pytorch/densenet.py) · `DenseNet.__init__` | 61–97 | — |
| E006 | [densenet.pytorch/densenet.py](sources/densenet.pytorch/densenet.py) · `DenseNet._make_dense` | 99–107 | — |
| E007 | [densenet.pytorch/densenet.py](sources/densenet.pytorch/densenet.py) · `DenseNet.forward` | 109–116 | — |
| E011 | [densenet.pytorch/train.py](sources/densenet.pytorch/train.py) · `main` | 29–104 | — |

| 稳定节点 ID | 图框 | 静态 shape | 证据 | 参数 / 实例族 |
|---|---|---|---|---|
| densenet | DenseNet-BC-100 / CIFAR-10 | [B,3,32,32] -> [B,10] | E007 | — |
| dense_input | CIFAR-10 image | [B,3,32,32] | E011 | — |
| dense_stem | Stem Conv 3x3: 3 -> 24 | [B,24,32,32] | E005,E007 | conv1 |
| dense_b1 | Dense block 1 x 16 | [B,24,32,32] -> [B,216,32,32] | E006,E007 | dense1; {'count': 16, 'index': 'j', 'template': 'dense_b1_layer', 'independent_parameters': True} |
| dense_b1_layer | Bottleneck template j=0...15 | Cj=24+12j; growth k=12 | E002,E003,E006 | dense1[j] |
| dense_b1_input | Retain dense input x | [B,Cj,32,32] | E003 | — |
| dense_b1_bn1 | BatchNorm Cj | [B,Cj,32,32] | E002,E003 | dense1[j].bn1 |
| dense_b1_relu1 | ReLU | [B,Cj,32,32] | E003 | — |
| dense_b1_conv1 | Conv 1x1: Cj -> 4k | [B,48,32,32] | E002,E003 | dense1[j].conv1 |
| dense_b1_bn2 | BatchNorm 4k | [B,48,32,32] | E002,E003 | dense1[j].bn2 |
| dense_b1_relu2 | ReLU | [B,48,32,32] | E003 | — |
| dense_b1_conv2 | Conv 3x3: 4k -> k | [B,12,32,32] | E002,E003 | dense1[j].conv2 |
| dense_b1_cat | Concat x and new features | [B,Cj+12,32,32] | E003 | — |
| dense_t1 | Transition 1: compression + pooling | [B,108,16,16] | E009,E010 | trans1 |
| dense_t1_bn | BatchNorm | [B,216,32,32] | E009,E010 | trans1.bn1 |
| dense_t1_relu | ReLU | [B,216,32,32] | E010 | — |
| dense_t1_conv | Conv 1x1: 216 -> 108 | [B,108,32,32] | E009,E010 | trans1.conv1 |
| dense_t1_pool | Average pool 2x2 / 2 | [B,108,16,16] | E010 | — |
| dense_b2 | Dense block 2 x 16 | [B,108,16,16] -> [B,300,16,16] | E006,E007 | dense2; {'count': 16, 'index': 'j', 'template': 'dense_b2_layer', 'independent_parameters': True} |
| dense_b2_layer | Bottleneck template j=0...15 | Cj=108+12j; growth k=12 | E002,E003,E006 | dense2[j] |
| dense_b2_input | Retain dense input x | [B,Cj,16,16] | E003 | — |
| dense_b2_bn1 | BatchNorm Cj | [B,Cj,16,16] | E002,E003 | dense2[j].bn1 |
| dense_b2_relu1 | ReLU | [B,Cj,16,16] | E003 | — |
| dense_b2_conv1 | Conv 1x1: Cj -> 4k | [B,48,16,16] | E002,E003 | dense2[j].conv1 |
| dense_b2_bn2 | BatchNorm 4k | [B,48,16,16] | E002,E003 | dense2[j].bn2 |
| dense_b2_relu2 | ReLU | [B,48,16,16] | E003 | — |
| dense_b2_conv2 | Conv 3x3: 4k -> k | [B,12,16,16] | E002,E003 | dense2[j].conv2 |
| dense_b2_cat | Concat x and new features | [B,Cj+12,16,16] | E003 | — |
| dense_t2 | Transition 2: compression + pooling | [B,150,8,8] | E009,E010 | trans2 |
| dense_t2_bn | BatchNorm | [B,300,16,16] | E009,E010 | trans2.bn1 |
| dense_t2_relu | ReLU | [B,300,16,16] | E010 | — |
| dense_t2_conv | Conv 1x1: 300 -> 150 | [B,150,16,16] | E009,E010 | trans2.conv1 |
| dense_t2_pool | Average pool 2x2 / 2 | [B,150,8,8] | E010 | — |
| dense_b3 | Dense block 3 x 16 | [B,150,8,8] -> [B,342,8,8] | E006,E007 | dense3; {'count': 16, 'index': 'j', 'template': 'dense_b3_layer', 'independent_parameters': True} |
| dense_b3_layer | Bottleneck template j=0...15 | Cj=150+12j; growth k=12 | E002,E003,E006 | dense3[j] |
| dense_b3_input | Retain dense input x | [B,Cj,8,8] | E003 | — |
| dense_b3_bn1 | BatchNorm Cj | [B,Cj,8,8] | E002,E003 | dense3[j].bn1 |
| dense_b3_relu1 | ReLU | [B,Cj,8,8] | E003 | — |
| dense_b3_conv1 | Conv 1x1: Cj -> 4k | [B,48,8,8] | E002,E003 | dense3[j].conv1 |
| dense_b3_bn2 | BatchNorm 4k | [B,48,8,8] | E002,E003 | dense3[j].bn2 |
| dense_b3_relu2 | ReLU | [B,48,8,8] | E003 | — |
| dense_b3_conv2 | Conv 3x3: 4k -> k | [B,12,8,8] | E002,E003 | dense3[j].conv2 |
| dense_b3_cat | Concat x and new features | [B,Cj+12,8,8] | E003 | — |
| dense_head | Final normalization + classifier | 342 features -> 10 classes | E007 | — |
| dense_final_bn | BatchNorm 342 | [B,342,8,8] | E005,E007 | bn1 |
| dense_final_relu | ReLU | [B,342,8,8] | E007 | — |
| dense_global_pool | Average pool 8x8 | [B,342,1,1] | E007 | — |
| dense_squeeze | Squeeze singleton axes | [B,342] for B>1 | E007 | — |
| dense_fc | Linear 342 -> 10 | [B,10] for B>1 | E005,E007 | fc |
| dense_log_softmax | LogSoftmax over classes | [B,10] log probabilities | E007 | — |
| dense_output | Class log probabilities | [B,10] for B>1 | E007 | — |

## 与教科书/通用基础图的区别

- Use the repository's CIFAR-10 BC-100 variant, not an ImageNet DenseNet-121 stem or four dense stages.
- Draw explicit channel Concat and retained-input dependency; do not replace dense connections by Add.
- Transition pooling is average pooling and compression is floor(C*0.5).
- The returned output is log probability, not logits or ordinary Softmax probability.
- Preserve the actual fixed pooling and all-axis squeeze, including their input-size/batch-size limitation.

## 源码事实与边界

- train.main constructs DenseNet(growthRate=12,depth=100,reduction=0.5,bottleneck=True,nClasses=10).
- (100-4)//3//2 = 16 Bottleneck layers per dense block; 48 distinct bottleneck instances in total.
- Feature channels are 3->24->216->108->300->150->342->10; spatial sizes are 32->16->8->1.
- Every Bottleneck performs BN->ReLU->Conv1x1->BN->ReLU->Conv3x3->channel cat(x,out).
- Dense reuse means channel concatenation, not a residual Add; retained x bypasses both convolutions.
- Repeated blocks/layers have independently created parameters; a representative symbolic template is drawn.
- The source uses fixed avg_pool2d(kernel=8), torch.squeeze without axis, and legacy log_softmax without dim.
- The diagrams use a selected B>1 static profile; no claim of modern PyTorch runtime compatibility is made.
