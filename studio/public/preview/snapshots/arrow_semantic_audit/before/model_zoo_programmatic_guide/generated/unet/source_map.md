# U-Net：源码与图框对应

来源：`mateuszbuda/brain-segmentation-pytorch`，固定提交 `d45f8908ab2f0246ba204c702a6161c9eb25f902`。

静态审阅适配器；没有导入或执行模型。Notebook 的行号指派生 Python，原始 cell 索引见下表与证据 JSON。

| 证据 | 文件与符号 | 行号 | 原始 Notebook cell（0起） |
|---|---|---|---|
| E002 | [brain-segmentation-pytorch/train.py](sources/brain-segmentation-pytorch/train.py) · `main` | 19–109 | — |
| E001 | [brain-segmentation-pytorch/train.py](sources/brain-segmentation-pytorch/train.py) · `datasets` | 137–150 | — |
| E003 | [brain-segmentation-pytorch/unet.py](sources/brain-segmentation-pytorch/unet.py) · `UNet` | 7–98 | — |
| E004 | [brain-segmentation-pytorch/unet.py](sources/brain-segmentation-pytorch/unet.py) · `UNet.__init__` | 9–43 | — |
| E006 | [brain-segmentation-pytorch/unet.py](sources/brain-segmentation-pytorch/unet.py) · `UNet.forward` | 45–65 | — |
| E005 | [brain-segmentation-pytorch/unet.py](sources/brain-segmentation-pytorch/unet.py) · `UNet._block` | 68–98 | — |

| 稳定节点 ID | 图框 | 静态 shape | 证据 | 参数 / 实例族 |
|---|---|---|---|---|
| unet | U-Net / brain segmentation | [B,3,256,256] -> [B,1,256,256] | E006 | — |
| unet_input | Input image / MRI channels | [B,3,256,256] | E006 | — |
| unet_enc1 | Encoder 1 / retained skip | enc1: [B,32,256,256] | E004,E006,E005 | encoder1 |
| unet_enc1_block | Double Conv + BN + ReLU | [B,32,256,256] | E005 | encoder1 |
| unet_enc1_block_conv1 | Conv 3x3: 3 -> 32 | [B,32,256,256] | E005 | encoder1.enc1conv1 |
| unet_enc1_block_bn1 | BatchNorm 32 | [B,32,256,256] | E005 | encoder1.enc1norm1 |
| unet_enc1_block_relu1 | ReLU | [B,32,256,256] | E005 | — |
| unet_enc1_block_conv2 | Conv 3x3: 32 -> 32 | [B,32,256,256] | E005 | encoder1.enc1conv2 |
| unet_enc1_block_bn2 | BatchNorm 32 | [B,32,256,256] | E005 | encoder1.enc1norm2 |
| unet_enc1_block_relu2 | ReLU | [B,32,256,256] | E005 | — |
| unet_pool1 | MaxPool 1: 2x2 / 2 | [B,32,128,128] | E004,E006 | — |
| unet_enc2 | Encoder 2 / retained skip | enc2: [B,64,128,128] | E004,E006,E005 | encoder2 |
| unet_enc2_block | Double Conv + BN + ReLU | [B,64,128,128] | E005 | encoder2 |
| unet_enc2_block_conv1 | Conv 3x3: 32 -> 64 | [B,64,128,128] | E005 | encoder2.enc2conv1 |
| unet_enc2_block_bn1 | BatchNorm 64 | [B,64,128,128] | E005 | encoder2.enc2norm1 |
| unet_enc2_block_relu1 | ReLU | [B,64,128,128] | E005 | — |
| unet_enc2_block_conv2 | Conv 3x3: 64 -> 64 | [B,64,128,128] | E005 | encoder2.enc2conv2 |
| unet_enc2_block_bn2 | BatchNorm 64 | [B,64,128,128] | E005 | encoder2.enc2norm2 |
| unet_enc2_block_relu2 | ReLU | [B,64,128,128] | E005 | — |
| unet_pool2 | MaxPool 2: 2x2 / 2 | [B,64,64,64] | E004,E006 | — |
| unet_enc3 | Encoder 3 / retained skip | enc3: [B,128,64,64] | E004,E006,E005 | encoder3 |
| unet_enc3_block | Double Conv + BN + ReLU | [B,128,64,64] | E005 | encoder3 |
| unet_enc3_block_conv1 | Conv 3x3: 64 -> 128 | [B,128,64,64] | E005 | encoder3.enc3conv1 |
| unet_enc3_block_bn1 | BatchNorm 128 | [B,128,64,64] | E005 | encoder3.enc3norm1 |
| unet_enc3_block_relu1 | ReLU | [B,128,64,64] | E005 | — |
| unet_enc3_block_conv2 | Conv 3x3: 128 -> 128 | [B,128,64,64] | E005 | encoder3.enc3conv2 |
| unet_enc3_block_bn2 | BatchNorm 128 | [B,128,64,64] | E005 | encoder3.enc3norm2 |
| unet_enc3_block_relu2 | ReLU | [B,128,64,64] | E005 | — |
| unet_pool3 | MaxPool 3: 2x2 / 2 | [B,128,32,32] | E004,E006 | — |
| unet_enc4 | Encoder 4 / retained skip | enc4: [B,256,32,32] | E004,E006,E005 | encoder4 |
| unet_enc4_block | Double Conv + BN + ReLU | [B,256,32,32] | E005 | encoder4 |
| unet_enc4_block_conv1 | Conv 3x3: 128 -> 256 | [B,256,32,32] | E005 | encoder4.enc4conv1 |
| unet_enc4_block_bn1 | BatchNorm 256 | [B,256,32,32] | E005 | encoder4.enc4norm1 |
| unet_enc4_block_relu1 | ReLU | [B,256,32,32] | E005 | — |
| unet_enc4_block_conv2 | Conv 3x3: 256 -> 256 | [B,256,32,32] | E005 | encoder4.enc4conv2 |
| unet_enc4_block_bn2 | BatchNorm 256 | [B,256,32,32] | E005 | encoder4.enc4norm2 |
| unet_enc4_block_relu2 | ReLU | [B,256,32,32] | E005 | — |
| unet_pool4 | MaxPool 4: 2x2 / 2 | [B,256,16,16] | E004,E006 | — |
| unet_bottleneck | Bottleneck / lowest resolution | [B,512,16,16] | E004,E006,E005 | bottleneck |
| unet_bottleneck_block | Double Conv + BN + ReLU | [B,512,16,16] | E005 | bottleneck |
| unet_bottleneck_block_conv1 | Conv 3x3: 256 -> 512 | [B,512,16,16] | E005 | bottleneck.bottleneckconv1 |
| unet_bottleneck_block_bn1 | BatchNorm 512 | [B,512,16,16] | E005 | bottleneck.bottlenecknorm1 |
| unet_bottleneck_block_relu1 | ReLU | [B,512,16,16] | E005 | — |
| unet_bottleneck_block_conv2 | Conv 3x3: 512 -> 512 | [B,512,16,16] | E005 | bottleneck.bottleneckconv2 |
| unet_bottleneck_block_bn2 | BatchNorm 512 | [B,512,16,16] | E005 | bottleneck.bottlenecknorm2 |
| unet_bottleneck_block_relu2 | ReLU | [B,512,16,16] | E005 | — |
| unet_dec4 | Decoder 4 / upsample + skip fusion | [B,256,32,32] | E004,E006 | decoder4 |
| unet_dec4_upconv | ConvTranspose 2x2 / 2 | [B,256,32,32] | E004,E006 | upconv4 |
| unet_dec4_cat | Concat upsampled + encoder skip | [B,512,32,32] | E006 | — |
| unet_dec4_block | Double Conv + BN + ReLU | [B,256,32,32] | E005 | decoder4 |
| unet_dec4_block_conv1 | Conv 3x3: 512 -> 256 | [B,256,32,32] | E005 | decoder4.dec4conv1 |
| unet_dec4_block_bn1 | BatchNorm 256 | [B,256,32,32] | E005 | decoder4.dec4norm1 |
| unet_dec4_block_relu1 | ReLU | [B,256,32,32] | E005 | — |
| unet_dec4_block_conv2 | Conv 3x3: 256 -> 256 | [B,256,32,32] | E005 | decoder4.dec4conv2 |
| unet_dec4_block_bn2 | BatchNorm 256 | [B,256,32,32] | E005 | decoder4.dec4norm2 |
| unet_dec4_block_relu2 | ReLU | [B,256,32,32] | E005 | — |
| unet_dec3 | Decoder 3 / upsample + skip fusion | [B,128,64,64] | E004,E006 | decoder3 |
| unet_dec3_upconv | ConvTranspose 2x2 / 2 | [B,128,64,64] | E004,E006 | upconv3 |
| unet_dec3_cat | Concat upsampled + encoder skip | [B,256,64,64] | E006 | — |
| unet_dec3_block | Double Conv + BN + ReLU | [B,128,64,64] | E005 | decoder3 |
| unet_dec3_block_conv1 | Conv 3x3: 256 -> 128 | [B,128,64,64] | E005 | decoder3.dec3conv1 |
| unet_dec3_block_bn1 | BatchNorm 128 | [B,128,64,64] | E005 | decoder3.dec3norm1 |
| unet_dec3_block_relu1 | ReLU | [B,128,64,64] | E005 | — |
| unet_dec3_block_conv2 | Conv 3x3: 128 -> 128 | [B,128,64,64] | E005 | decoder3.dec3conv2 |
| unet_dec3_block_bn2 | BatchNorm 128 | [B,128,64,64] | E005 | decoder3.dec3norm2 |
| unet_dec3_block_relu2 | ReLU | [B,128,64,64] | E005 | — |
| unet_dec2 | Decoder 2 / upsample + skip fusion | [B,64,128,128] | E004,E006 | decoder2 |
| unet_dec2_upconv | ConvTranspose 2x2 / 2 | [B,64,128,128] | E004,E006 | upconv2 |
| unet_dec2_cat | Concat upsampled + encoder skip | [B,128,128,128] | E006 | — |
| unet_dec2_block | Double Conv + BN + ReLU | [B,64,128,128] | E005 | decoder2 |
| unet_dec2_block_conv1 | Conv 3x3: 128 -> 64 | [B,64,128,128] | E005 | decoder2.dec2conv1 |
| unet_dec2_block_bn1 | BatchNorm 64 | [B,64,128,128] | E005 | decoder2.dec2norm1 |
| unet_dec2_block_relu1 | ReLU | [B,64,128,128] | E005 | — |
| unet_dec2_block_conv2 | Conv 3x3: 64 -> 64 | [B,64,128,128] | E005 | decoder2.dec2conv2 |
| unet_dec2_block_bn2 | BatchNorm 64 | [B,64,128,128] | E005 | decoder2.dec2norm2 |
| unet_dec2_block_relu2 | ReLU | [B,64,128,128] | E005 | — |
| unet_dec1 | Decoder 1 / upsample + skip fusion | [B,32,256,256] | E004,E006 | decoder1 |
| unet_dec1_upconv | ConvTranspose 2x2 / 2 | [B,32,256,256] | E004,E006 | upconv1 |
| unet_dec1_cat | Concat upsampled + encoder skip | [B,64,256,256] | E006 | — |
| unet_dec1_block | Double Conv + BN + ReLU | [B,32,256,256] | E005 | decoder1 |
| unet_dec1_block_conv1 | Conv 3x3: 64 -> 32 | [B,32,256,256] | E005 | decoder1.dec1conv1 |
| unet_dec1_block_bn1 | BatchNorm 32 | [B,32,256,256] | E005 | decoder1.dec1norm1 |
| unet_dec1_block_relu1 | ReLU | [B,32,256,256] | E005 | — |
| unet_dec1_block_conv2 | Conv 3x3: 32 -> 32 | [B,32,256,256] | E005 | decoder1.dec1conv2 |
| unet_dec1_block_bn2 | BatchNorm 32 | [B,32,256,256] | E005 | decoder1.dec1norm2 |
| unet_dec1_block_relu2 | ReLU | [B,32,256,256] | E005 | — |
| unet_head | Pixel-wise segmentation head | [B,1,256,256] | E006 | — |
| unet_head_conv | Conv 1x1: 32 -> 1 | [B,1,256,256] | E004,E006 | conv |
| unet_sigmoid | Sigmoid per pixel | [B,1,256,256] | E006 | — |
| unet_output | Foreground probability mask | [B,1,256,256] | E006 | — |

## 与教科书/通用基础图的区别

- Follow this repository's BN-equipped same-padding U-Net, rather than the original paper's valid-convolution/crop variant.
- Draw ConvTranspose2d rather than interpolation or a generic upsample operator.
- Draw channel Concat rather than Add for all four long skip connections; route from the output before MaxPool.
- Use Sigmoid per pixel rather than Softmax; default output has a single foreground channel.
- Do not infer RGB semantics from in_channels=3: the selected repository targets MRI segmentation.

## 源码事实与边界

- UNet constructor defaults are in_channels=3,out_channels=1,init_features=32; train image-size defaults to 256.
- Encoder widths are 32,64,128,256; the bottleneck width is 512. Four MaxPool2d(2,2) steps reduce 256 to 16.
- Every _block is Conv3x3->BatchNorm2d->ReLU->Conv3x3->BatchNorm2d->ReLU, with padding=1 and bias=False.
- Each decoder uses learned ConvTranspose2d(kernel=2,stride=2), channel cat with the matching pre-pool encoder output, then _block.
- Skip sources are enc1..enc4 outputs before pooling; they concatenate along channels and are never residual additions.
- UNet.forward returns torch.sigmoid(self.conv(dec1)); the default 1x1 output convolution maps 32 to 1.
- No resizing, interpolation or center-cropping appears in forward; the selected 256x256 input keeps cat spatial sizes compatible.
- Separate encoder/decoder _block calls instantiate distinct parameters; same glyph type does not imply parameter sharing.
- Three representative double-conv blocks expand in the detailed view; all nine blocks retain their six operations in semantic IR.
