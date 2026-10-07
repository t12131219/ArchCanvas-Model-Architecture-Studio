# 原生匹配的独立双向唯一合同审查

[report.json](report.json) 记录新写、手工指定预期的 9 项独立检查，全部通过，无 skip。该审查直接调用正式 `joinNativeTrials` 和独立 receipt validator；两者的输入源码、测试源码与原始 stdout/stderr 均已冻结于此目录。

同一个原始 Event Timing entry 被两个合格 trial 争用时，两者均为 `null`。2×2 完全重叠、`A={e1}, B={e1,e2}` 偏斜图和重复 entry 也保持歧义，不能通过依次分配/删除候选得到“唯一”匹配。测试还验证 ±8ms 的闭区间边界、不同 target/name、非 trusted 竞争者、独立连通分量，以及交换候选输入顺序。手写 `null`/pair 和 p95 预期不由产品 matcher 或 summary 生成；伪造先到先得结果即使同步重写 summary，仍被 verifier 拒绝。

复核命令从正式工程根执行，并使用新输出目录保留本次原件：

```bash
python docs/evidence/m4-native-matching-work/independent/audit.py \
  --output /tmp/archcanvas-native-matching-independent-next
```

此证据仅证明列出的源码匹配合同与收据一致性。测试没有浏览器、可信原生输入、实际 paint、FPS 或真人参与；它不认证 M4 性能或出版质量。严格 TypeScript 与生产 build 由 root 统一执行，不计入本报告。
