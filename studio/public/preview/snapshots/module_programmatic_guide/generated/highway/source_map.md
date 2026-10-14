# Highway gated fusion：源码与图框对应

来源：`analvikingur/pytorch_Highway`，固定提交 `70b75db7a2d029f4bbe08fd4c7d69e36bf7b6d3a`。

静态审阅适配器；没有导入或执行模型。Notebook 的行号指派生 Python，原始 cell 索引见下表与证据 JSON。

| 证据 | 文件与符号 | 行号 | 原始 Notebook cell（0起） |
|---|---|---|---|
| E001 | [pytorch-highway/highway/highway.py](sources/pytorch-highway/highway/highway.py) · `Highway` | 5–37 | — |
| E002 | [pytorch-highway/highway/highway.py](sources/pytorch-highway/highway/highway.py) · `Highway.__init__` | 6–18 | — |
| E003 | [pytorch-highway/highway/highway.py](sources/pytorch-highway/highway/highway.py) · `Highway.forward` | 20–37 | — |

| 稳定节点 ID | 图框 | 静态 shape | 证据 | 参数 / 实例族 |
|---|---|---|---|---|
| highway.root | Highway module / two layers | [B,16] | E002,E003 | — |
| highway.input | Input features x | [B,16] | E003 | — |
| highway.layer0 | Highway layer 0 / independent weights | [B,16] | E002,E003 | — |
| highway.layer0.gate | Transform gate | [B,16] | E002,E003 | — |
| highway.layer0.gate_linear | Linear 16 -> 16 | [B,16] | E002 | gate.0 |
| highway.layer0.sigmoid | Sigmoid gate g | [B,16] | E003 | — |
| highway.layer0.nonlinear | Nonlinear transform | [B,16] | E002,E003 | — |
| highway.layer0.nonlinear_linear | Linear 16 -> 16 | [B,16] | E002 | nonlinear.0 |
| highway.layer0.relu | Selected f = ReLU | [B,16] | E003 | — |
| highway.layer0.carry | Learned linear carry | [B,16] | E002,E003 | — |
| highway.layer0.carry_linear | Linear 16 -> 16 | [B,16] | E002,E003 | linear.0 |
| highway.layer0.complement | 1 - g | [B,16] | E003 | — |
| highway.layer0.nonlinear_product | g * nonlinear | [B,16] | E003 | — |
| highway.layer0.carry_product | (1-g) * linear | [B,16] | E003 | — |
| highway.layer0.add | Add gated branches | [B,16] | E003 | — |
| highway.layer1 | Highway layer 1 / independent weights | [B,16] | E002,E003 | — |
| highway.layer1.gate | Transform gate | [B,16] | E002,E003 | — |
| highway.layer1.gate_linear | Linear 16 -> 16 | [B,16] | E002 | gate.1 |
| highway.layer1.sigmoid | Sigmoid gate g | [B,16] | E003 | — |
| highway.layer1.nonlinear | Nonlinear transform | [B,16] | E002,E003 | — |
| highway.layer1.nonlinear_linear | Linear 16 -> 16 | [B,16] | E002 | nonlinear.1 |
| highway.layer1.relu | Selected f = ReLU | [B,16] | E003 | — |
| highway.layer1.carry | Learned linear carry | [B,16] | E002,E003 | — |
| highway.layer1.carry_linear | Linear 16 -> 16 | [B,16] | E002,E003 | linear.1 |
| highway.layer1.complement | 1 - g | [B,16] | E003 | — |
| highway.layer1.nonlinear_product | g * nonlinear | [B,16] | E003 | — |
| highway.layer1.carry_product | (1-g) * linear | [B,16] | E003 | — |
| highway.layer1.add | Add gated branches | [B,16] | E003 | — |
| highway.output | Highway output x | [B,16] | E003 | — |

## 与教科书/通用基础图的区别

- Do not substitute textbook identity carry: source includes a learned linear branch.
- Do not use three independent gates: the complement uses exactly1-g from the same gate tensor.
- Do not share weights across Highway layers: the ModuleLists construct distinct Linear modules.
- Do not claim activation was recovered asReLU from source; it is the selected f callable.

## 源码事实与边界

- Three separate ModuleLists independently construct gate, nonlinear and linear transforms for each layer; six Linear modules for this2layer example.
- All3 paths consume the same current layer input; nonlinear is f(self.nonlinear\[layer\](x)); gate is F.sigmoid(self.gate\[layer\](x)).
- Source carry path is self.linear\[layer\](x), a learned affine transform, not original x.
- Two gated products use complementary g and1-g, then Add; next layer reads updated x and uses its own weights.
- Source accepts callable f without fixing it; f=F.relu,size16,layers2 are explicitly selected module example values.
- Graph ranks allocate space only; every branch input, product operand and inter-layer dependency is an explicit edge, no fake tuple.
