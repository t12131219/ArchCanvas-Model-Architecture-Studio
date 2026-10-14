# Signed graph deep convolution：源码与图框对应

来源：`benedekrozemberczki/SGCN`，固定提交 `c01e930c02968ea5b0eb72f1fe93eaab99e46eea`。

静态审阅适配器；没有导入或执行模型。Notebook 的行号指派生 Python，原始 cell 索引见下表与证据 JSON。

| 证据 | 文件与符号 | 行号 | 原始 Notebook cell（0起） |
|---|---|---|---|
| E001 | [signed-gcn-modules/src/signedsageconvolution.py](sources/signed-gcn-modules/src/signedsageconvolution.py) · `SignedSAGEConvolution.__init__` | 65–84 | — |
| E002 | [signed-gcn-modules/src/signedsageconvolution.py](sources/signed-gcn-modules/src/signedsageconvolution.py) · `SignedSAGEConvolutionDeep.forward` | 131–162 | — |

| 稳定节点 ID | 图框 | 静态 shape | 证据 | 参数 / 实例族 |
|---|---|---|---|---|
| signed_graphconv.root | Signed graph deep convolution / module only | [N,4] | E002 | — |
| signed_graphconv.x1 | State x1 | [N,8] | E002 | — |
| signed_graphconv.x2 | Distinct state x2 | [N,8] | E002 | — |
| signed_graphconv.pos | Positive edge indices | [2,E+] | E002 | — |
| signed_graphconv.neg | Negative edge indices | [2,E-] | E002 | — |
| signed_graphconv.weight | Owned weight W | [24,4] | E001 | weight |
| signed_graphconv.bias | Owned bias b | [4] | E001 | bias |
| signed_graphconv.module | Signed graph deep convolution / operators | [N,4] | E002 | — |
| signed_graphconv.posloops | Remove then ADD self loops | [2,E_loop] | E002 | — |
| signed_graphconv.posmean | Mean of x1 neighbors | [N,8] | E002 | — |
| signed_graphconv.negloops | Remove then ADD self loops | [2,E_loop] | E002 | — |
| signed_graphconv.negmean | Mean of x2 neighbors | [N,8] | E002 | — |
| signed_graphconv.concat | Concat pos, neg, SELF x1 | [N,24] | E002 | — |
| signed_graphconv.project | Concatenated states @ W | [N,4] | E002 | — |
| signed_graphconv.biasadd | Add owned bias | [N,4] | E002 | — |
| signed_graphconv.normalize | L2 normalize each node | [N,4] | E002 | — |
| signed_graphconv.output | Selected module output | [N,4] | E002 | — |

## 与教科书/通用基础图的区别

- Do not draw positive and negative paths as copies of the same x or omit the explicitly retained x1.
- Do not apply the first-layer Base self-loop policy to this Deep implementation.

## 源码事实与边界

- Positive mean reads x1 while negative mean reads x2. The retained third concatenation operand is x1, not x2.
- Source removes existing self loops and then adds self loops to BOTH edge sets before scatter_mean. This includes self contribution inside both means as well as explicit retained x1.
- One owned W\[24,4\] and bias\[4\] follow three-operand concat; optional norm_embed selects final L2 normalization.
- Library self-loop/scatter helpers remain opaque. Balanced/unbalanced caller state swaps are outside this source module boundary.
- Graph ranks only allocate space. Explicit edges supply real operands; no upstream code is imported or executed.
