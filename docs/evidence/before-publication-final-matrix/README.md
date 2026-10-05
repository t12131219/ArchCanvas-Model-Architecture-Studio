# 出版最终构建：完整矩阵采集前的文档与收据归档

本目录由新的独占目录创建，拒绝覆盖已有归档。`files/` 保留更新前 11 份当前文档和 4 份收据的原始字节；原文件、原 manifest、原 current verification 及原始审计没有改写。

冻结状态为 `index-DPwoyNJW.js`：8886 的 11 条代表记录、两份输入与 3 份实际导出在其受限范围通过审计；当时新构建的完整 36＋3 矩阵仍未采集。175 个 current-verification 绑定及出版修正 manifest 的 80 个文件＋94 个链接在归档前全部逐项核对一致，11 份文档同时精确符合两份收据。上述数量是文件完整性与归档库存，不能视为新版矩阵覆盖或人工验收。

## 历史路径如何解析

原 manifest 的 `files[].path`、`linkedEvidence[].path` 与原 current-verification 的 `bindings` 键仍按正式工程根目录解释，不能相对本归档中复制的 JSON 文件目录解析。原 manifest 不做路径重写。

新完整矩阵阶段更新当前文档后，这些路径会指向新的当前字节；它们已不再代表旧收据冻结的文档版本。旧文档和这里复制的收据应按本归档 `manifest.json` 的 `archivedPath` 找到 `files/<原工程路径>`，用原 bytes/SHA256 核对。原收据里所列而未复制的源码、构建与历史证据仍按其原冻结范围阅读；本目录不是 175 个绑定或全部出版工件的递归副本，也不保证未来当前路径一直保留旧字节。

`files/docs/evidence/m4-current-verification.json` 是旧 175 绑定原件；`files/docs/evidence/m4-publication-refinement-work/manifest.json` 是旧 80＋94 清单原件；`root-final-recheck.json` 和 `verification-summary.json` 同样保持原字节，供恢复旧结论。若后续只读核对当前路径出现文档 hash 变化，应先查本归档解析映射，不将正常更新误判为原记录被改写。

旧 DWp 的 39 项矩阵继续属于历史。此次归档没有新增浏览器观察、build、测试、人工审看、原生性能/cancel 或研究者任务；M4 partial、参与者为 0 的边界不变。
