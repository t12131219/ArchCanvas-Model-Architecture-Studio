# 箭头审查：独立文件完整性与交付范围核对

本检查只读取现有文件。默认运行不写入结果；显式 `--write-report` 仅刷新本页、`integrity_checks.json` 和 `shared_before_after.json`，不修改源码、SVG、before 或历史基线，也不导入或执行上游模型。

| 核对对象 | 文件数量 | 结果 |
|---|---:|---|
| 修改前 before 备份 | 2,775 | 通过，逐文件 SHA-256 一致 |
| 四专题 source 副本 | 608 | 通过，逐文件 SHA-256 一致 |
| Transformer 历史 snapshots | 37 | 通过，逐文件 SHA-256 一致 |
| 固定 upstream 索引 | 34 | 通过，逐文件 SHA-256 一致 |
| 原始压缩包与 prototype 携带副本 | 6 | 通过，逐文件 SHA-256 一致 |
| 随附原始参考 SVG | 1 | 通过，逐文件 SHA-256 一致 |

source 数量按专题为：model_zoo_programmatic_guide 144、module_programmatic_guide 255、timeseries_programmatic_guide 25、transformer_programmatic_guide 184；文件无增删，所有修改前/后摘要见机器记录。`sources` 与 `snapshots` 范围可能包含同一文件，各项不能直接相加。

当前图像、适配器和说明允许有意更新，其旧内容均在 before 保留。current / compact / mini 图像不按旧字节相同判定；历史 snapshots 的原文件则逐一要求原字节不变。

另核对 module 与 model-zoo 已保存审计记录的 303 个视图，逐项比较 SVG、IR 与布局文件共 **909 个摘要**，结果：**通过**。此项检查收据对应当前产物，不重复执行语义验收。

Transformer 当前/compact 六视图与两个 mini 的审计产物再核对 **34 个摘要**（SVG、PNG、IR、布局、evidence，以及 mini 的 SVG/布局），结果：**通过**。

## SVG 范围

排除审计 before 备份和额外展开 fixture 后，共 **331 个 SVG**。

| 范围 | SVG 数量 |
|---|---:|
| model_zoo_programmatic_guide 正式主视图 | 75 |
| module_programmatic_guide 正式主视图 | 228 |
| timeseries_programmatic_guide 正式主视图 | 12 |
| transformer_programmatic_guide 正式主视图 | 3 |
| 活跃 compact 版 | 3 |
| 活跃 mini 示例 | 2 |
| 历史 snapshots | 7 |
| 随附源码参考图 | 1 |

主视图 **318** 张；加活跃 compact / mini 后 **323** 张。历史与随附原图文件保留不代表本轮真实端点认证。逐 SVG 路径列表在 JSON 中。

独立读取 **323 张活跃 SVG** 的实际 XML，计 **4,761 条 `data-route-id` 路径**。逐文件检查无重复 ID、无匿名绘制路径，并有显式语义绑定或教学 annotation 字段；不以 layout 自报路径数代替实际 XML。分组统计见机器记录。

## 导航与复现

四专题与迁移入口 347 份活跃 Markdown/HTML，核对 3,770 个本地引用，断链 **0**。另扫描 11 份活跃审计说明中的 51 个本地引用，断链 **0**。

排除 before 备份、历史 snapshots、上游/source README；忽略代码块与正确转义的方括号。此次只检查文件/目录存在性，不检查远端 URL、fragment anchor 或运行时 JavaScript 动态目标。源码完整性与导航就绪分别记录，缺失路径会逐项列出。

从 ArchCanvas 工作区根目录运行：

```bash
python3 prototype/arrow_semantic_audit/check_integrity.py
python3 prototype/arrow_semantic_audit/check_integrity.py --write-report
```

第一条仅检查并打印，不写文件；第二条只更新审计结果，并为共享专题清单保留原始 2,387 条 before 记录、验证每份备份、重算当前摘要，另列新增文件（不计 __pycache__）。脚本按自身位置解析 prototype，不依赖当前工作目录；也可通过 `--root` 显式指定副本目录。

检查时间：`2026-10-11T13:23:10.749321+00:00`。完整性：**通过**；导航：**通过**。逐文件结果见 [integrity_checks.json](integrity_checks.json)，复现脚本为 [check_integrity.py](check_integrity.py)。
