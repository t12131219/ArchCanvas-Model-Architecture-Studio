# ACT 源码保留生成验证

当前源码解析结果为 DETRVAE 232 个对象、21 条张量连接；全部 20 个选定 Python 文件保存在副本，包含方法内部 import 或未直接调用的源码。`initial-draft.json` 使用普通紧凑前沿，不强制路由全部源码检查节点。

- 未修改草稿生成：源码字节、源码摘要及全部 IR 完全相同。
- 编辑 `is_pad_head.out_features`：从源码显式整数 `1` 改为 `2`，仅 `detr/models/detr_vae.py` 该位置变化；分支、循环、其余语句保留。
- `managed-copy/` 是生成后的独立源码副本；用相同入口重新分析与生成 IR 完全一致。`workspace-replay.json` 另外核对正式 Workspace.register 的 managed-copy 注册。
- 连接检查通过的旁路重连仍被 `unsupported-source-preserving-edit` 拒绝；源码检查图没有结构生成权限。
- `source-before.json` 与 `source-after.json` 包含原始 act 全部 74 个文件的集合、SHA-256、大小及 mtime，且与之前只读评估一致。

没有 import、实例化或执行模型。输出维度修改仅证明静态源码编辑闭环，不证明训练配置或张量 shape 正确。

重现：在正式项目根目录运行 `PYTHONPATH=src python3 -B docs/evidence/act-source-support-20261015/source-preservation/reproduce.py`。这会更新本目录验证结果，不写原始 act。
