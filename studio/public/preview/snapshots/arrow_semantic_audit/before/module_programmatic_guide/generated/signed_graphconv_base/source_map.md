# Signed graph first-layer convolution：源码与图框对应

来源：`benedekrozemberczki/SGCN`，固定提交 `c01e930c02968ea5b0eb72f1fe93eaab99e46eea`。

静态审阅适配器；没有导入或执行模型。Notebook 的行号指派生 Python，原始 cell 索引见下表与证据 JSON。

| 证据 | 文件与符号 | 行号 | 原始 Notebook cell（0起） |
|---|---|---|---|
| E001 | [signed-gcn-modules/src/signedsageconvolution.py](sources/signed-gcn-modules/src/signedsageconvolution.py) · `SignedSAGEConvolution.__init__` | 65–84 | — |
| E002 | [signed-gcn-modules/src/signedsageconvolution.py](sources/signed-gcn-modules/src/signedsageconvolution.py) · `SignedSAGEConvolutionBase.forward` | 104–125 | — |

| 稳定节点 ID | 图框 | 静态 shape | 证据 | 参数 / 实例族 |
|---|---|---|---|---|
| signed_graphconv_base.root | Signed graph first-layer convolution / module only | [N,4] | E002 | — |
| signed_graphconv_base.x | Node features x | [N,8] | E002 | — |
| signed_graphconv_base.edges | Supplied single edge set | [2,E] | E002 | — |
| signed_graphconv_base.weight | Owned weight W | [16,4] | E001 | weight |
| signed_graphconv_base.bias | Owned bias b | [4] | E001 | bias |
| signed_graphconv_base.module | Signed graph first-layer convolution / operators | [N,4] | E002 | — |
| signed_graphconv_base.remove | REMOVE self loops only | [2,E_without_self] | E002 | — |
| signed_graphconv_base.mean | Mean of neighbors without self | [N,8] | E002 | — |
| signed_graphconv_base.concat | Concat NEIGHBOR then SELF | [N,16] | E002 | — |
| signed_graphconv_base.project | Concatenated features @ W | [N,4] | E002 | — |
| signed_graphconv_base.biasadd | Add owned bias | [N,4] | E002 | — |
| signed_graphconv_base.normalize | L2 normalize each node | [N,4] | E002 | — |
| signed_graphconv_base.output | Selected module output | [N,4] | E002 | — |

## 与教科书/通用基础图的区别

- Do not copy the Deep two-state/three-operand structure or add self loops absent from this module.

## 源码事实与边界

- Base layer removes self loops, aggregates one feature state over one edge set, and concatenates neighbor mean then original x.
- There is no add_self_loops call in Base forward. This is a real semantic difference from the Deep signed layer.
- Owned weight\[16,4\], bias\[4\] and final L2 normalization are selected; outside caller may instantiate separate Base layers for different edge types.
- Graph ranks only allocate space. Explicit edges supply real operands; no upstream code is imported or executed.
