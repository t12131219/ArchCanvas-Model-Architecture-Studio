# 本轮矩阵收尾前的原件归档

这里保存本轮可能更新的当前文档与 `m4-hierarchy-verification.json` 的原始字节。原凭据、旧 manifest、原始采样、源码、构建与截图均未改写；归档不增加矩阵覆盖、性能通过或真人验收。

`manifest.json` 对每份原件记录原路径、归档路径、字节数和 SHA-256。`historical-resolution.json` 保留原凭据的全部 1872 个绑定，并明确每项核对所用的实际路径：只有“原路径＋该项原哈希”精确匹配本归档原件时才使用新归档路径；其他绑定路径原样保留。这包括上一轮 `before-hierarchy-optimization` 已解析的历史路径，不会重新指向已更新的当前文档，也不扫描候选文件修补不匹配。

在正式工程目录执行只读核对：

```bash
python docs/evidence/before-hierarchy-final-matrix/verify_archive.py
```

归档刚完成时可加 `--compare-current` 确认当前原件仍逐字节相同；当前文档更新后只使用默认核对。核对程序不会写入文件、更新哈希或重封旧证据。本轮若另建验证凭据，应绑定本归档 manifest、原 verification 归档副本、完整路径解析及新工件，而不是覆盖原 seal 或继承旧矩阵覆盖。
