# 2026-10-15：主项目清除 Notebook

范围是正式项目 `ArchCanvas_Model_Architecture_Studio` 的整个工作树，包含隐藏文件、ignored 文件及 `studio/dist`，不包含 Git 历史。只静态读取源码、JSON、Python AST 和摘要，没有 import、实例化或执行参考模型。

## 结果

| 项目 | 结果 |
| --- | --- |
| 真实 `.ipynb` 文件 | 224 → 0：public 112 份、dist 112 份 |
| Notebook 检查点 | 0 |
| 移除体积 | 53,723,740 字节 |
| 原始来源记录 | 112 条，28 种内容，原始 SHA256 全部保留 |
| 规范 Python 转换资产 | 29 个，AST、哈希及 27,674 条来源行映射检查通过 |
| 既有 Python | public 中 1304 个文件全部字节不变 |
| 案例索引 | 230 个，223 个有源码，306 个源码引用、142 个去重资源，全部可用 |
| 图与证据 | 未因转换改写；全部非 Notebook 文件均保留 |
| Python 回归 | 26 项通过，无失败或跳过 |
| 前端相关回归 | 18 项通过，无失败或跳过 |
| 构建与 HTTP | TypeScript/Vite 构建通过，514 项 HTTP 内容及清单摘要核对通过 |

112 份来源原先已有精确对应的 Python 转换；本次重新校验后复用其字节，移除 Notebook 原件，不改变源码行号。`notebook-conversions.json` 仅将 `notebook_retained` 改为 `false` 并规范记录排序，转换 ID、Python 路径、摘要、cell/行映射保持不变。主入口仍使用 `sources/packages/`，历史 Notebook 的 Python 文件集中在 `sources/notebooks/`。

转换工具默认校验后移除原件，支持重复执行、新增文件、大写扩展及上游重新复制。转换或写出失败时不移除输入；删除范围只允许 `snapshots/` 下的 `.ipynb`，拒绝符号链接。vendor 刷新使用相同流程，不会把 Notebook 再次发布，资源清单同步更新摘要。

历史来源路径、上游 URL、哈希和 `pytorch_ipynb` 名称保留为证据身份。第三方依赖中名为 `jupyter.py` 的兼容代码不是 Notebook，不删除。12 个归档及 848 个 gzip 证据的静态解包盘点未发现 Notebook；没有伪扩展或真实嵌入 Notebook，测试中的静态 JSON fixture 用于转换回归。

## 证据

- [清理前全项目盘点](inventory-before.json)：含全部 224 个原件路径及 SHA256。
- [最终全项目盘点](inventory-after.json)：包括 public/dist 一致性和全项目零 Notebook 检查。
- [转换来源与行映射保全](conversion-preservation.json)。
- [public 全文件摘要比较](public-integrity.json)：相较清理前基线，预期之外的改写或丢失为零。
- [案例及 Python 资源检查](source-availability.json)：本次使用 `--skip-authoring`；未将未改动源码的重新解析纳入本轮验收。
- [Python 回归](python-tests.json)及[完整日志](python-tests.log)。
- [最终检查记录](checks.json)：含前端测试和构建结果。
- [514 项实际 HTTP 核对](http-source-assets.json)：临时服务仅监听 localhost，核对后关闭。

重跑转换及静态检查：

```bash
python3 -B studio/scripts/convert-preview-notebooks.py
python3 -B studio/scripts/convert-preview-notebooks.py --check
python3 -B -m unittest discover -s tests -p 'test_preview_notebook_conversion.py'
python3 -B -m unittest discover -s tests -p 'test_preview_vendor_notebooks.py'
python3 -B -m unittest discover -s tests -p 'test_preview_source_packages.py'
python3 -B studio/scripts/check-preview-sources.py --skip-authoring --output /tmp/archcanvas-source-check.json
npm --prefix studio run build
```
