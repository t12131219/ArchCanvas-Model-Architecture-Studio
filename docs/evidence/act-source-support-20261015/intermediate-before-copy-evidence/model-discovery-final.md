# act 模型发现与入口最终静态复验

本轮识别 15 个本地模型/模块类、21 条本地可能包含关系。74 个原始文件的内容、集合和修改时间完整比较；未 import、未实例化、未执行模型或工厂。

| 入口 | 实际入口方法 | 预览打开 | 正式编辑打开 |
| --- | --- | --- | --- |
| `detr.models.backbone:Backbone` | `forward` | 通过 | 通过 |
| `detr.models.backbone:BackboneBase` | `forward` | 通过 | 通过 |
| `detr.models.backbone:FrozenBatchNorm2d` | `forward` | 通过 | 通过 |
| `detr.models.backbone:Joiner` | `forward` | 通过 | 通过 |
| `detr.models.detr_vae:CNNMLP` | `forward` | 通过 | 通过 |
| `detr.models.detr_vae:DETRVAE` | `forward` | 通过 | 通过 |
| `detr.models.position_encoding:PositionEmbeddingLearned` | `forward` | 通过 | 通过 |
| `detr.models.position_encoding:PositionEmbeddingSine` | `forward` | 通过 | 通过 |
| `detr.models.transformer:Transformer` | `forward` | 通过 | 通过 |
| `detr.models.transformer:TransformerDecoder` | `forward` | 通过 | 通过 |
| `detr.models.transformer:TransformerDecoderLayer` | `forward` | 通过 | 通过 |
| `detr.models.transformer:TransformerEncoder` | `forward` | 通过 | 通过 |
| `detr.models.transformer:TransformerEncoderLayer` | `forward` | 通过 | 通过 |
| `policy:ACTPolicy` | `__call__` | 通过 | 通过 |
| `policy:CNNMLPPolicy` | `__call__` | 通过 | 通过 |

## 有来源证据的局部包含关系

| 所属模型 | 槽位 | 候选模块 | 数量 | 确定性 |
| --- | --- | --- | --- | --- |
| `detr.models.backbone:Joiner` | `items[0]` | `detr.models.backbone:Backbone` | 1 | source |
| `detr.models.backbone:Joiner` | `items[1]` | `detr.models.position_encoding:PositionEmbeddingLearned` | 1 | possible |
| `detr.models.backbone:Joiner` | `items[1]` | `detr.models.position_encoding:PositionEmbeddingSine` | 1 | possible |
| `detr.models.detr_vae:CNNMLP` | `backbones[*]` | `detr.models.backbone:Joiner` | unknown | possible |
| `detr.models.detr_vae:DETRVAE` | `backbones[0]` | `detr.models.backbone:Joiner` | 1 | possible |
| `detr.models.detr_vae:DETRVAE` | `encoder` | `detr.models.transformer:TransformerEncoder` | 1 | source |
| `detr.models.detr_vae:DETRVAE` | `transformer` | `detr.models.transformer:Transformer` | 1 | source |
| `detr.models.transformer:Transformer` | `decoder` | `detr.models.transformer:TransformerDecoder` | 1 | source |
| `detr.models.transformer:Transformer` | `encoder` | `detr.models.transformer:TransformerEncoder` | 1 | source |
| `detr.models.transformer:TransformerDecoder` | `layers[*]` | `detr.models.transformer:TransformerDecoderLayer` | unknown | possible |
| `detr.models.transformer:TransformerDecoder` | `layers[0]` | `detr.models.transformer:TransformerDecoderLayer` | 6 | source |
| `detr.models.transformer:TransformerEncoder` | `layers[*]` | `detr.models.transformer:TransformerEncoderLayer` | unknown | possible |
| `detr.models.transformer:TransformerEncoder` | `layers[0]` | `detr.models.transformer:TransformerEncoderLayer` | 6 | source |
| `policy:ACTPolicy` | `model` | `detr.models.detr_vae:DETRVAE` | 1 | source |
| `policy:CNNMLPPolicy` | `model` | `detr.models.detr_vae:CNNMLP` | 1 | source |
| `torch.nn.ModuleList` | `items[*]` | `detr.models.backbone:Joiner` | unknown | possible |
| `torch.nn.ModuleList` | `items[*]` | `detr.models.transformer:TransformerDecoderLayer` | unknown | possible |
| `torch.nn.ModuleList` | `items[*]` | `detr.models.transformer:TransformerEncoderLayer` | unknown | possible |
| `torch.nn.ModuleList` | `items[0]` | `detr.models.backbone:Joiner` | 1 | source |
| `torch.nn.ModuleList` | `items[0]` | `detr.models.transformer:TransformerDecoderLayer` | 6 | possible |
| `torch.nn.ModuleList` | `items[0]` | `detr.models.transformer:TransformerEncoderLayer` | 6 | possible |

`inventoryComplete` 仅表示本轮源码类目录扫描完成；`hierarchyComplete` 为 false 时，动态数量、配置选择和外部模块仍明确未知。包含候选不是实际执行路径或张量连接，打开与交互成功不等于任意结构改写可以生成源码。详细原始结果见相邻 JSON。

源码不变：True；验收期间实现不变：False；全部入口双后端打开：True。
