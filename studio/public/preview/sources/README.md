# 预设案例 Python 源码

Studio 的案例编辑、源码查看和静态解析统一使用此目录的 `.py` 文件，不需要 Jupyter、原型目录或模型运行环境。

- `packages/<案例名>_<包摘要>/`：当前及历史案例实际绑定的 Python 源码包。多文件保留导入所需的相对结构；相同源码包供多个案例共用，许可证放在包内 `licenses/`。
- `notebooks/`：历史 Notebook 的代码单元静态转换结果，全部为 `.py`。去除了名称中的空格、连字符等非法模块字符；Notebook magic 仅作为注释保留。
- `../data/catalog-sources.json`：案例 ID → 入口、Python 文件、源码证据和许可证。
- `../data/source-packages.json`：去重包、案例关联、原始路径和 SHA256 台账。
- `../data/notebook-conversions.json`：112 份 Notebook 的来源摘要及 cell → Python 行号映射。

案例名和文件名仅用于参考展示，已规范为合法 Python 名称。每个 `originalPath` / `originalAsset` 保留原始位置；源码正文与绑定的行号未改变。`snapshots/` 保留 Python、图、来源材料和历史验证证据，Notebook 原件已全部移除。台账保留原始摘要及行映射，历史证据中的 `.ipynb` 路径和上游 URL 仅用于追溯；日常查看源码请从这里开始。

这些文件包含第三方参考模型及训练示例。Studio 只静态读取文本，不 import、不实例化、不执行模型。路由实验及没有模型源码的教学 SVG 会明确显示无源码；没有逐节点证据的图元仍可独立进行视觉编辑。

重新生成（从正式项目根目录运行，不需要原型目录）：

```bash
python3 -B studio/scripts/organize-preview-sources.py
python3 -B studio/scripts/convert-preview-notebooks.py
python3 -B studio/scripts/convert-preview-notebooks.py --check
PYTHONPATH=src python3 -B studio/scripts/check-preview-sources.py
```

转换命令默认在校验 Python 后移除 Notebook，支持重复运行及新增文件的增量转换。刷新原型材料同样遵守此规则。
