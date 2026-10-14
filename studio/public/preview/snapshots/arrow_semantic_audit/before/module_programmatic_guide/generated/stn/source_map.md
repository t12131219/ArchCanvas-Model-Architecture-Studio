# Spatial Transformer submodule：源码与图框对应

来源：`pytorch/tutorials`，固定提交 `ce8d551d11baebcf8064be3caba7b28a4d84a15d`。

静态审阅适配器；没有导入或执行模型。Notebook 的行号指派生 Python，原始 cell 索引见下表与证据 JSON。

| 证据 | 文件与符号 | 行号 | 原始 Notebook cell（0起） |
|---|---|---|---|
| E001 | [pytorch-tutorials-stn/intermediate_source/spatial_transformer_tutorial.py](sources/pytorch-tutorials-stn/intermediate_source/spatial_transformer_tutorial.py) · `Net.__init__` | 94–121 | — |
| E002 | [pytorch-tutorials-stn/intermediate_source/spatial_transformer_tutorial.py](sources/pytorch-tutorials-stn/intermediate_source/spatial_transformer_tutorial.py) · `Net.stn` | 124–133 | — |

| 稳定节点 ID | 图框 | 静态 shape | 证据 | 参数 / 实例族 |
|---|---|---|---|---|
| stn.root | STN submodule / MNIST image | [B,1,28,28] | E002 | — |
| stn.input | Input image / retained pixels | [B,1,28,28] | E002 | — |
| stn.module | Spatial transformer / Net.stn | [B,1,28,28] | E002 | — |
| stn.localization | Locate transform | [B,10,3,3] | E001,E002 | localization; instance=localization |
| stn.loc.conv1 | Conv7x7: 1 -> 8 | [B,8,22,22] | E001,E002 | instance=localization.0 |
| stn.loc.pool1 | MaxPool2x2 / stride2 | [B,8,11,11] | E001,E002 | instance=localization.1 |
| stn.loc.relu1 | ReLU / inplace | [B,8,11,11] | E001,E002 | instance=localization.2 |
| stn.loc.conv2 | Conv5x5: 8 -> 10 | [B,10,7,7] | E001,E002 | instance=localization.3 |
| stn.loc.pool2 | MaxPool2x2 / stride2 | [B,10,3,3] | E001,E002 | instance=localization.4 |
| stn.loc.relu2 | ReLU / inplace | [B,10,3,3] | E001,E002 | instance=localization.5 |
| stn.parameters | Affine parameter regressor | theta: [B,2,3] | E001,E002 | fc_loc |
| stn.flatten | View localization features | [B,90] | E002 | — |
| stn.fc1 | Linear 90 -> 32 | [B,32] | E001,E002 | instance=fc_loc.0 |
| stn.relu | ReLU / inplace | [B,32] | E001,E002 | instance=fc_loc.1 |
| stn.fc2 | Linear 32 -> 6 | [B,6] | E001,E002 | instance=fc_loc.2 |
| stn.theta | View affine matrix theta | [B,2,3] | E002 | — |
| stn.resampling | Grid + image resampling | [B,1,28,28] | E002 | — |
| stn.grid | F.affine_grid(theta, size) | [B,28,28,2] | E002 | — |
| stn.sample | F.grid_sample(image, grid) | [B,1,28,28] | E002 | — |
| stn.output | Warped image | [B,1,28,28] | E002 | — |

## 与教科书/通用基础图的区别

- Keep the original image value route to grid_sample distinct from the image-size route to affine_grid.
- Do not replace predicted theta with a permanently fixed identity matrix, a crop operator, or a classification head.
- Do not insert inverse(theta), pixel-coordinate normalization operators or interpolation-kernel internals absent from the frozen tutorial.

## 源码事实与边界

- The selected artifact is the Net.stn submodule; Net.forward classification convolutions, dropout and log_softmax are outside the scope.
- For a28x28 single-channel image the localization sequence is Conv7, Pool2, ReLU, Conv5, Pool2, ReLU; its last map is10x3x3.
- The regressor views90 features then executes Linear90->32, ReLU, Linear32->6, and view\[B,2,3\].
- fc_loc.2 has learnable weight and bias. The constructor sets its weight to zero and bias to identity affine coefficients; training may change both.
- affine_grid receives theta and x.size(), so its dependency on the original image is shape-only, not a second localization pixel path.
- grid_sample receives the original image pixel values and the generated normalized(x,y) grid. It does not resample the localization feature map.
- The source omits align_corners in both functional calls; the drawing preserves omission instead of claiming explicitTrue or an executed backend default.
- Modern PyTorch APIs document align_corners=False by default, grid_sample bilinear mode and zero padding; these are API context, not extra arguments present in this source.
- affine_grid and grid_sample are opaque functional library boundaries; normalized grid shape and meanings are API contracts, not a traced implementation.
- All tensor shapes are statically inferred from the chosen image shape; no tutorial, model, training loop, initialization or resampling was executed.
