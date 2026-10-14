# Model Zoo 箭头源码语义审查（修正前）

本次检查读取 25 个模型的 75 个视图以及完整语义 IR，未执行上游 PyTorch 模型、Notebook 或训练代码，也没有把几何通过当作语义通过。独立检查的 234 条断言中，194 条通过、40 条失败；失败保存在 [before_endpoint_audit.json](before_endpoint_audit.json)，每条含源码行、表达式、原始箭头端点和应有可见端点。

| 来源与关系 | 修正前的问题 | 应有端点 |
|---|---|---|
| U-Net：`encN=self.encoderN(...)`；`cat((decN,encN),1)` | 8 条模块/详细视图跳连从展开 Encoder 外框中部出发，视觉上接近中间 Conv 层 | Encoder 最后一个 ReLU；内部折叠时接 double-conv 图元的输出 |
| AlexNet：`probas=F.softmax(logits,dim=1)` | 2 条边从展开 classifier 外框出发 | 最后的 `fc3` 输出 |
| GraphNet：`register_buffer('A',A)`；`self.A.expand(...)` | 详细视图把已经展开的 constructor panel 当作 A 的生产算子 | 注册 buffer 的图元输出 |
| ConvGAN / DCWGAN：调用 G 与三次 D | 每个模型 9 个展开调用端点停在外框 | G 的首个 Linear、真实图像 normalization、各 D call 前的 caller view |
| VAE / ConvVAE / CCVAE：`reparameterize(z_mean,z_log_var)` | 6 个 mean/logvar 绑定没有从各自 producer 连出；公共 bus 把两个独立值合并再 fork | `mu` → retain-mean；`logvar` → divide-by-two |
| VAE / ResNet18 | 1 个 VAE scope、3 个 projected-path scope 暗示源码先创建 tuple | 明确为独立操作数的显示分组，分别接下游算子 |
| VAE：`randn(z_mu.size(0),z_mu.size(1))` | 缺少 1 条 shape 来源关系 | `mu:shape` → random-source 的 shape 输入 |

15 条 residual / retained-input 身份检查通过；6 条 LSTMCell 跨折叠相邻单元的 hidden/cell 端口分离检查通过。这些通过项用于保护修复：输入残差不能被替换为变换后的输出，h/c 也不能因折叠而变为同一值。

修正合同位于 [endpoint_contracts.py](../../model_zoo_programmatic_guide/adapters/endpoint_contracts.py)，合同导出位于 [endpoint_contracts.json](endpoint_contracts.json)。共 361 个命名端口、384 个内部绑定引用，25 个适配器经过目标存在性和幂等检查。叶 Return 的输出别名使用 `direction: src`：输入箭头仍进入 Return 的真实消费端口，只有从 Return 选择字段时才追溯实际 producer。

GraphNet 的 `bmm(A,X)` 与 TextCNN 的 `positions>=valid_windows` 按源码操作数顺序绑定，不能从图元的左右排布猜顺序。LSTMCell 的 graph scope 明确声明输入、previous hidden、previous cell、output hidden 和 state fields；visual ranks 只负责位置。

修正前 PNG 的具体问题已目视确认： [U-Net 外框跳连](before_unet_endpoint_crop.png)、[ConvVAE 错误共享输入总线](before_convvae_endpoint_crop.png)。历史目录 `../before/model_zoo_programmatic_guide` 保留原始字节，属于已知有上述问题的旧原型，不能作为当前语义正确性的依据。

复现修正前审查：

```bash
python3 -B prototype/arrow_semantic_audit/modelzoo/audit_modelzoo.py \
  --guide prototype/arrow_semantic_audit/before/model_zoo_programmatic_guide \
  --output prototype/arrow_semantic_audit/modelzoo/before_endpoint_audit.json
```

重绘后用同一脚本省略 `--guide`，将 `--output` 指向新的报告。独立语义合同检查和全视图 endpoint inventory 不等于任意模型自动推断，也不声明运行时张量观测。
