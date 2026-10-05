# 正式 39 例出版矩阵独立末审

当前 DPwoy 构建的冻结矩阵：36 基线变体（9 个实际层级 frontier × 2 宽度 × 2 配色）和 3 份编辑后重开的画布，共 39 例。独立末审覆盖字段、实际截图、证据绑定链、文本编辑与持久化、当前构建及研究准备包。

| 核验 | 结果 |
| --- | --- |
| 原始文件 | 352 / 352 bytes、SHA256 保持冻结值 |
| 派生 stamped | 313 文件未变；39 receipt 仅增加两个 digest 字段 |
| 正式 CLI | 39 stamp exit 0；collect exit 0 |
| 封存矩阵 | 39 例、234 个六类工件；基线与编辑后覆盖完整 |
| 实际 interactive SVG / publication SVG | 39 XML 精确重建；39 converter bytes exact |
| 显式服务原件 | 39 个唯一 export ID；直接绑定复制 exact |
| 原始截图实际重看 | 20 + 19 = 39；未见明显状态不一致或 modal |
| 已提交 SVG 文本操作 | 3 undo + 3 redo，只排除 revision，其余整 XML exact |
| 保存后重开 / 重开后最终 raw | 各 3 对 SVG bytes exact |
| 研究包 | 58 实现绑定、4 基线、5 原始未分配槽位；0 研究员，not_run |
| 既有验证记录 | 79 Studio 测试、9 独立性检查；本审计未重跑 |

四处公开 DOM JSON 的 metadata.heightMm 与实际 SVG metadata 只差约2.84e−14或5.68e−14。本次只对该 JSON 数值字段采用1e−9窄容差，逐例记录实际 delta；实际 interactive XML 和其他 metadata 字段均精确一致。

19 条编辑 UI 记录的 38 份 SVG / AX 原件保留。5 条 AX 内容输入框值与已提交 SVG 不同（CNN redo；MLP undo / redo；Transformer undo / redo）；没有后续 DOM input value 或像素采样，原因未知，不认证输入框同步。CNN 的首条 added 是 L0 可见节点加 latent 子展开标记的过渡状态，不能称为完整 L2 frontier；后续显式恢复 root-only L0 并移说明，再进行文本对照。保存条目处理中 footer 不证明保存完成；证据来自随后重开结果与 SVG bytes exact。

临时编排 wrapper 在所有 stamp、collect 和 raw recheck 成功后，末行误用 Path.returncode 产生 AttributeError，wrapper exit1。正式 stamp / collect exit0与最终工件不受影响。该异常公开保留；仅修复临时 wrapper 变量，没有重复 stamp / collect 或改写原件。

UA / DPR 由先前同一个选定 IAB 的8880 observer 显式绑定，不是8887新测值；1280×720 viewport 来自当前8887 DOM。字体解析字节与硬件未知。独立 release 的三份构建 bytes exact，但依赖使用已安装 node_modules 的拷贝，不能证明全新安装。

这些结果只支持工件覆盖、AI 字段 / 画面状态一致性，以及三份已提交 SVG 编辑与持久化。视觉美感、人审、实尺寸印样、字体、原生性能和研究验收仍待完成。深层图在14–26%适配视图下不认证细字与端点；配置示例7pt并非通用期刊规则，36基线中10满足最小字≥7pt、0满足组合示例。19 UI 记录不等于19人类任务。

完整细项、原件与派生文件 SHA256、5 条 AX 观察、4 处 float delta、编排异常及最终输入复核见 `independent-final-audit.json` 和绑定的详细报告。Root 仍在更新的 README / verification summary / 当前声明文件不作为本报告输入。后续 input-draft 诊断、服务中断 / 重启 / 恢复记录也在本审计范围之外，本报告不认证这些后续过程。
