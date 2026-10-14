# GraphSAGE sampled mean：源码与图框对应

来源：`williamleif/graphsage-simple`，固定提交 `d3105e5223e9602ba3ef2dd27e343d044fe4bb5f`。

静态审阅适配器；没有导入或执行模型。Notebook 的行号指派生 Python，原始 cell 索引见下表与证据 JSON。

| 证据 | 文件与符号 | 行号 | 原始 Notebook cell（0起） |
|---|---|---|---|
| E001 | [graphsage-modules/graphsage/aggregators.py](sources/graphsage-modules/graphsage/aggregators.py) · `MeanAggregator.forward` | 30–63 | — |
| E002 | [graphsage-modules/graphsage/encoders.py](sources/graphsage-modules/graphsage/encoders.py) · `Encoder.__init__` | 10–31 | — |
| E003 | [graphsage-modules/graphsage/encoders.py](sources/graphsage-modules/graphsage/encoders.py) · `Encoder.forward` | 33–50 | — |

| 稳定节点 ID | 图框 | 静态 shape | 证据 | 参数 / 实例族 |
|---|---|---|---|---|
| graphsage_mean.root | GraphSAGE sampled mean / module only | [4,M] | E003 | — |
| graphsage_mean.nodes | Queried node IDs | [M] | E003 | — |
| graphsage_mean.adj | Supplied adjacency lists | neighbor sets | E003 | — |
| graphsage_mean.features | Shared feature callable | IDs -> [count,8] | E003 | instance=shared features callable |
| graphsage_mean.weight | Owned Encoder weight | [4,16] | E002 | Encoder.weight |
| graphsage_mean.module | GraphSAGE sampled mean / operators | [4,M] | E003 | — |
| graphsage_mean.neighbors | Read queried neighbor sets | M sets | E003 | — |
| graphsage_mean.sample | Sample up to10 neighbors | M sampled sets | E001 | — |
| graphsage_mean.unique | Union / unique node IDs | [U] | E001 | — |
| graphsage_mean.mask | Binary membership / row divide | [M,U] | E001 | — |
| graphsage_mean.lookup | Query features(unique IDs) | [U,8] | E001 | instance=shared features callable |
| graphsage_mean.selflookup | Query SAME features(nodes) | [M,8] | E003 | instance=shared features callable |
| graphsage_mean.mean | mask @ neighbor embeddings | [M,8] | E001 | — |
| graphsage_mean.concat | Concat SELF then NEIGHBOR | [M,16] | E003 | — |
| graphsage_mean.project | Projection / transposed node axis | [4,M] | E003 | — |
| graphsage_mean.project.transpose | Transpose combined | [16,M] | E003 | — |
| graphsage_mean.project.mm | W @ combined transpose | [4,M] | E003 | — |
| graphsage_mean.project.relu | ReLU / retain [embed_dim,M] | [4,M] | E003 | — |
| graphsage_mean.output | Selected module output | [4,M] | E003 | — |

## 与教科书/通用基础图的区别

- Do not include queried node itself in sampled neighbors under the selected gcn=False branch.
- Do not infer separate learned embedding tables from the two lookup glyphs or silently transpose the returned output.

## 源码事实与边界

- Neighbor sampling, membership-mask normalization and matrix multiplication are source operations; a textbook abstract mean glyph alone would hide these steps.
- Both self and neighbor lookups call the SAME externally supplied features callable. Its parameter ownership is unknown at this module boundary.
- Encoder owns weight\[4,16\], with no bias, and multiplies W by combined.t(); output is \[4,M\], not \[M,4\].
- Selected gcn=False bypasses the source gcn=True set-addition branch. Nonempty neighborhoods are assumed for static shape discussion; division has no epsilon.
- Frozen repository has no license file; README is retained and no license is invented.
- Graph ranks only allocate space. Explicit edges supply real operands; no upstream code is imported or executed.
