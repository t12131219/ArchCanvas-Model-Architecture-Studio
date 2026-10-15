# 参考案例快照

本目录保存参考模型的 Python 源码、图、许可证和历史验证证据。Notebook 原件已全部转换并移除；Studio 不依赖 Jupyter。

日常使用请从以下入口查找源码：

- `../sources/packages/`：案例实际绑定的 Python 包，保留本地导入关系与许可证。
- `../sources/notebooks/`：历史 Notebook 转换的 Python 文件，使用合法模块路径。
- `../data/catalog-sources.json`：案例入口、Python 文件、来源别名及证据。
- `../data/notebook-conversions.json`：原始 Notebook 的路径、SHA256、转换策略和代码单元行映射；`notebook_retained: false` 表示原件已移除。

快照中的 `pytorch_ipynb` 目录名、历史 JSON / SVG / CSV 中的 `.ipynb` 路径、上游 URL 和采集脚本保留原始来源身份。它们不是本地 Notebook 入口；历史脚本的采集记录应按当时状态理解，当前文件完整性使用正式项目的 `studio/scripts/check-preview-sources.py` 检查。源码字节、证据行号和图语义未因本次清理而改写。
