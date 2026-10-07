# M4 位置修复与组合网络起点：文档更新计划

本页是本轮只读审查后的最小更新计划，不是最终验收或构建声明。尚未修改旧正文、status、seal、manifest、raw 或研究包；最终 build、测试和浏览器范围等待 root 给出。本轮仍为 M4 partial，不进入 M5。

## 已核对的冻结基线

- [切换前归档](../before-m4-move-recovery-presets/manifest.json) 保存旧 Bc 的 2894 个绑定；全部 archivePath 的 SHA256 与 bytes 精确一致。
- [原 seal](../m4-bcf-browser-matrix-current-verification-sealed.json) SHA256 为 `170be658b4b76e2217bb0d58397f586fc1f8fdccd66278961d657116952a5551`，与归档记录一致。
- 当前 [status](../m4-human-review-handoff-status.json) 仍是 schemaVersion 6，28598 bytes，SHA256 `5d1ce4f35d18275cd26ab153bc4d9b373120e99a96f885bdfbf5659e48212c13`，与原 seal 一致。冻结原件已在归档中的 `files/docs/evidence/m4-human-review-handoff-status.json` 保存。
- 原实现是 `index-BcFxpKDY.js` / `index-NmgHfiF5.css`：39 例/234 工件的矩阵、四份原生诊断、17 单模块库、无组合预制、五席 8961–8965 和 0 真人均属于该版本。旧失败、分母、问题记录继续保留。

## 当前源码可以怎样描述

只读审查了新增 `core/layoutRecovery.ts`、`authoringPresets.ts` 和相关 App/AuthoringStudio/Scene/diagnostic 改动。以下是实现合同，是否得到最终测试、实际浏览器覆盖须另绑定证据。

- 位置修复是显式 preview → apply/cancel；预览不写 CanvasDocument，应用提交一次现有 move operation。预览期间阻止保存/导出；选中身份或文档变化使旧预览失效。不是隐式限制用户拖动，也不是全图自动美化。
- 规划最多检查 64 个候选。选中对象或其后代有 pin 时拒绝；容器内部冲突要求选择具体内部对象；无可行方案时保留现状并解释。候选保护其他对象位置/尺寸，祖先容器可能随布局 resize；不承诺所有交叉、折点或碰撞可消除。
- Scene 新增 `layout-outside-parent` 提示，覆盖之前左移越界没有 warning 的缺口。旧 Bc 的左越界 22、上标题侵入 32、下重叠 14 仍是历史观察，不能删成“从未发生”。
- 三个透明网络起点为最小 MLP、小型 CNN、残差 MLP，使用现有普通节点/typed tensor ports。分别是 5/4、8/7、6/6 个节点/连接；输入输出声明为 `[1,16]→[1,4]`、`[1,3,32,32]→[1,4]`、`[1,16]→[1,16]`。它们不是三个新单模块，也不是 opaque 复合算子；17 种基础模块数不增加。
- 插入整体作为一次 draft history 变化，生成独立身份，保留旧节点和连线，避开已有卡片；注册参数、端口、容量和身份分配失败保持原草稿。可在草稿中继续逐节点编辑。源码生成仍是受管理新副本的静态 source/IR 合同；运行/数值验证、导入源任意写回、Attention/LSTM/训练不因预制而新增。
- 新 work 中 attempt-1 的 AST/IR 审查是静态样本，不是原生 UI、模型执行或真人任务。初始 shell wrapper 未开始产品测试、strict-1 type failure、IR adapter 失败均保留，最终计数只引用最后冻结命令，不与 attempt 相加。

## 最少需要更新的文档

以下 14 个已有入口均已包含在 2894 绑定归档中，不需改历史原始证据。

| 文档 | 必要更新 |
|---|---|
| `README.md`、`docs/acceptance.md`、`docs/evidence/README.md` | 替换首段“当前 Bc/本轮产品未改/当前完整39矩阵/缺组合预制”的声明，链接本轮说明、新 work 与新封存；加旧 Bc 2894 绑定归档范围。 |
| `docs/capability-matrix.md` | 同步首段；更新从零建模、连线/布局提示、复合预制、层级/拖动/手势、SVG与publication/performance相关行。17 单模块＋3 网络起点单列，实际浏览器覆盖逐项说明；旧39例不写为新构建矩阵。 |
| `docs/m4-completion.md` | 更新当前状态表：显式位置修复和预制的最终范围、当前矩阵/研究包/性能门；移除“组合预制未支持”和“13core不变”的当前声明。 |
| `docs/m4-exit-audit.md` | 更新首段和当前硬出口段；保持真人、物理尺寸/字体/硬件、presented性能、活动held-pointer取消等未认证门。 |
| `docs/m4-human-review-handoff.md` | 更新短交接、当前门表、版本/包与实际服务生命周期；旧8968/8947“可继续在线”不作为新轮在线承诺。 |
| `docs/browser-visual-matrix-protocol.md` | 当前入口指向新版本实际准备/采集事实；下方旧矩阵命令和事实明确按历史版本阅读，不覆盖旧spec或manifest。 |
| `docs/m4-ai-usability-audit.md`、`docs/m4-authoring.md`、`docs/m4-authoring-feedback.md`、`docs/m4-bcf-browser-matrix.md`、`docs/m4-performance.md`、`docs/m4-routing-refinement.md` | 加简短新当前入口与旧 Bc/更早冻结范围说明；旧诊断表、问题、attempt、原生分母、像素/几何和CPU结论保留。Bc专页本体不改成新构建采集报告。 |

新增 `docs/m4-move-recovery-presets.md` 作为本轮唯一详细说明，新增本 work 的 `README.md` 为证据入口；不复制所有旧历史段。`docs/m4-research-protocol.md` 本身仍是更早 Cr 入口，未在本轮 2894 归档名单；最小方案不改它。若 root 要同步该协议的当前命令，先另行保存原字节，再使用新目录和实际包，不覆盖旧包。

## schema 6 状态更新方向

保持现有 schema 6 结构，未有消费者合同变更就不单凭新版本递增 schema。最终字段须使用实际 root 收据：

- 更新 generatedAt/scope/build/CSS/frontend 与 tests。区分新全套或专项、沿用但字节核对的 Python319、原 Studio136，以及本轮独立静态 oracle；不要合并计数。旧“productSuitesRerunThisCollectionRound=false”按实际命令修订。
- authoring 保持 modules=17，新增三预制及 topology/declared input/output/static-generation scope，移除 unsupported 中的 composite-presets；保留运行/Attention/LSTM/训练未支持和实际 module/preset 浏览器覆盖限制。
- 当前 currentMatrix、currentBrowserRepresentative、performance、currentRoutingObservations、currentNativeMovementObservations 只能装本轮实际范围。旧39/234、四份原生及运动问题转入 `historicalBcSnapshot` 的归档原件指针，或明确 historical 子字段，不合并新旧分母。
- Scene 已改，旧“13 exact core unchanged”不再作当前 inheritance 依据；73场景CPU/geometry可保留历史标签。即使某个指标重算相同，也不能由旧build哈希替代新检查。
- research 的旧70 implementation/five-slot包因源码/build变化为 stale，不能分配；若 root fresh prepare/verify，就只写实际新包/哈希/端口/绑定数。否则当前准备 pending，0人保持。
- references 更新到新收据与冻结文档哈希；旧 references 可由归档旧status恢复。previousFrozenScope 指向本次2894归档/旧Bc seal；不改旧 seal 内嵌 currentStatus 哈希，不反向修改旧manifest。
- phaseStatus=partial、nextPhaseStarted=false、human数=0、publication/performance/cancel等 false 保持，除非本轮取得相应独立证据。AI operator/audit不改真人分母。

## 最后写入与冻结次序

root先提供最终源码/build哈希、最后测试/独立oracle、browser真实范围、服务生命周期、新spec/研究包准备事实及拟定新seal路径。随后写上述最小正文/status和新入口，核本地链接及2894旧archive原字节，立即冻结。root创建独立新seal，最后审计只读；不给旧seal重新计算哈希，不运行全suite/build/browser补证。
