# Stress IR 来源标签更正前副本

这里保存了更正前的 stress audit、诊断 bundle manifest 与 current-verification 字节及各自摘要。原 audit 的 `irDigestMatchesHistoricalIndependentCPUFixture=true` 标签错误：新 raw IR `d01ce879…99220` 与历史原生 stress smoke receipt 相符，历史 CPU/core stress 的 IR 为 `63417bb3…1f17b`。相同源码摘要不能将这两个 IR等同。

当前 audit 已改为 `irDigestMatchesHistoricalNativeStressReceipt` 并绑定实际历史 native receipt 的路径、SHA256、大小及核对字段；其引用 manifest/current摘要同步更新。见 [更正记录](correction.json)和[当前审计](../input-observation/stress300-final-observer-audit.json)。此次只更正来源标签，原始 raw、validation、production、工具、测试日志均未改动，也没有重新执行模型、浏览器或测试。旧副本不作为当前来源标签结论。
