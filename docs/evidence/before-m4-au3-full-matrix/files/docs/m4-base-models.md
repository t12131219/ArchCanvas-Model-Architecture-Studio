# M4 基础模型完整源码预期

MLP 与 Residual CNN 的完整静态图现在有独立手写预期，覆盖每个节点、声明端口、边、tensor producer、容器子项、repeat 和 instance/call 身份。预期来自正式 fixture 源码和公开算子调用合同，不由 analyzer snapshot 生成。此验收补齐了此前仅核对层顺序和算子数量的不足。

| 模型 | 完整节点 | 完整边 | 声明端口 | Tensor producer | Call / Instance |
| --- | ---: | ---: | ---: | ---: | ---: |
| MLP | 8 | 8 | 13 | 5 | 6 / 6 |
| Residual CNN | 24 | 24 | 43 | 19 | 19 / 17 |

`tests/m4_base_model_oracle.py` 手写全部节点、关系和有序子项。`tests/test_m4_base_models.py` 按 authored instance、调用 occurrence、源码表达式归一身份。绑定通过 `(nodeId, portId)` 精确查找，因此另一个节点上的同名端口不能蒙混过关；每个端口的名称、方向、角色、ordinal 都与预期比较。完整关系采用 Counter 比较，避免集合掩盖重复边。

MLP 的输入同时连接 root adapter、Sequential input 与第一层 Linear。末层 Linear 的同一 tensor 连接 Sequential result 与模型 Output；容器没有制造新的 producer。Sequential 内部顺序是 Linear(16, 32) → GELU → Dropout(0.1) → Linear(32, 4)。图输出的 `outputPath=[]` 表示源码的单 tensor return。

CNN 的两个 ResidualBlock 独立构造，每个块的两次 ReLU 调用共享一个 instance，但有不同 call。完整图保留 root、repeat 和 block 的 containment，主分支是 conv1 → norm1 → activation → conv2 → norm2。源码 `x + residual` 的 left producer 是 norm2，right producer 是块入口保存的旁路。手写预期要求 left=data、right=residual，暴露并推动修复了原分析器“固定 left 为 residual”的问题。修复依据 producer dependency 判断旁路，不根据变量名或左右位置猜测；其通用反例由单独的 `test_residual_roles.py` 负责。

校验还要求每个 producer 只对应一个 tensor identity，每个 tensor identity 只对应一个 producer，全部共享 consumer 精确保留。静态 tensor identity 不意味着具体 shape、dtype 或执行轨迹已经被验证。

九项故意破坏的负例验证 checker 能拒绝错 Add 端口、合法端口但错 producer、别的节点上的同名端口、容器 adapter 拆分 tensor、不同 producer 合并 tensor、未连接的额外端口、缺失子项、把共享 activation 伪造为独立 instance、错误 repeat count。每项先验证未修改图通过，再要求对应破坏触发明确错误，避免其他缺陷造成假阳性。

`scripts/check_m4_base_models.py` 使用正式发行独立检查器生成 `/tmp` source copy，再以 Python `-I -S`、只加入 copied `src` 与 copied tests 路径运行测试。11/11 通过，无 skip；MLP/CNN 都没有 opaque 节点。独立报告绑定 oracle、checker、发行脚本、frontend、源码、architecture 和完整归一 proof 的 SHA256，并保留实际 copied package provenance。已有 holdout 报告未被此脚本覆盖。

证据保存在 `docs/evidence/m4-base-model-report.json`、`m4-base-model-independent-suite.txt`、`m4-base-model-{mlp,cnn}.architecture.json` 和 `m4-base-model-{mlp,cnn}.oracle-proof.json`。这些文件是独立运行产物的逐字副本；报告内的 `/tmp` 路径保留了原始 provenance。可用以下命令重新检查：

```bash
python scripts/check_m4_base_models.py
```

这份证据仅证明这两个正式 fixture 的完整静态源码关系。它没有执行模型，不证明具体张量形状、数值等价、反向传播、浏览器性能、研究者评价或任意模型族支持；全部参数 origin 的独立认证也不在此报告范围内。
