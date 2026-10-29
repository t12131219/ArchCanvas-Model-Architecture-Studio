# “优化连线 / Apply Layout”响应性能修复（2026-10-29）

## 范围与结论

本轮针对正式 Studio 中“优化连线”对应的原生 `apply-layout`，修改正式项目内已经迁入的 Summary 运行时，不依赖 `prototype/Summary_Merge` 的运行环境。面板、源码事务和模型入口继续使用当前正式程序。

当前浏览器中的 Transformer 工作副本有 89 个可见节点、94 条连线。实际按钮测试记录到 **518 ms 的 Worker 调用及结果提交耗时**，其中 Worker 为 483.2 ms，27 条路径改变，节点位置、尺寸和源码绑定不变。取消操作保留提交前图形；随后一次撤销完整恢复测试前全部路径。测试结束后保留用户原来的图形与相机。

该数值不是点击至最终屏幕绘制的完整延迟：计时从首次反馈的 rAF 之后开始，到结果安装完成结束，不含最后的宿主面板更新、持久化及绘制。也不能据此保证所有展开层级均在一秒内完成。

## 卡顿原因

1. 原 `apply()` 在设置 busy、显示反馈前，同步进行完整源码校验；`needed` 策略还会反复构建约束上下文。
2. 显式 Apply 的路由参数未接入原生模块移动已有的 A*、空间索引等配置。物理端口组合和候选路径枚举缺少统一时间边界。
3. 批量布线为每条边重复验证其他边，并重复查找重叠。大型源码图在这个路径上放大了重复工作。
4. Apply 完成后，原桥接可能在 finalizer、`applied` 回复和 `state` 通知中连续生成三份完整状态，重复复制源码与文档。

## 实现

| 文件 | 改动 |
| --- | --- |
| `studio/public/preview/yworks_edge_router_lab/app.js` | 先发送轻量 busy 状态并让出一帧；将预检、冲突判断、布线、整图验证交给 Worker 的 `optimize` 任务。验证通过后只保存一次撤销记录、提交一次结果；失败或取消保留原图。 |
| `graph-engine.js` | 增加 `optimizeRoutes`；显式优化复用原生路由配置、批内合法性上下文及重叠集合；保留合法旧路径和不可变源码绑定。每批完成后再次验证源码、布局和所有连线。 |
| `router.js` | 端口对及简单路径候选枚举也检查搜索截止时间，避免搜索主循环停止后候选枚举仍持续运行。 |
| `recursive-graph.js` | 可读性整理的候选循环遵守同一搜索截止时间。 |
| `routing-worker.js` | 接入显式 `optimize` 任务，沿用已有源码共享传输和取消机制。 |
| `studio-bridge.js` | Apply 期间保留轻量交互通知，完成时仅返回一份包含完整文档的 `applied`；快照和导出接口不变。 |
| `studio/src/PreviewStudio.tsx` | 将 `apply-layout` 的最终 `applied` 作为宿主状态更新，避免再索取重复快照。 |
| `studio/public/preview/BRIDGE.md`、`integration-manifest.json` | 记录接口行为并更新正式集成资产哈希。 |

路由仍比较路径成本、交叉等因素，没有改为“找到第一条路径便结束”的展开策略。成功提交不会移动或缩放模块；手工折点是否保留继续遵守现有设置，源码操作数、端点身份和端口约束仍参与验证。

## 时间预算与继续优化

- 默认每批路由搜索预算 1000 ms，每条边搜索预算 24 ms；边级截止时间同时受剩余批预算限制。
- 未开始处理的目标边保留原路径，写入 `routeOptimization.pendingIds`，界面提示再次点击继续。
- 再次点击时，只有目标范围、设置和图形调度签名匹配才继续剩余边；范围或几何改变后重新开始一轮。已尝试但在预算内未找到替代路径的边可以保留合法旧路径，不属于“尚未开始”的剩余队列。
- 调度记录只用于分批，不是源码或布局的有效性凭证。每批提交仍进行完整约束验证。
- **一秒是搜索预算，不是整次操作的硬性上限。** 源码首次认证、整图验证、传输、候选前处理、保存和绘制仍有额外耗时。
- Worker 不可用时沿用既有独立回退路径，此时不能承诺后台计算或同样的取消响应。

## 性能证据

### 浏览器当前工作副本

证据：[`browser-check.json`](evidence/summary-apply-layout-performance-20261029/browser-check.json)。

| 检查 | 结果 |
| --- | --- |
| 可见图形 | 89 节点、94 连线 |
| Worker 调用与结果提交 | 518 ms |
| Worker 内总耗时 | 483.2 ms |
| Worker 预检 / 布线 / 最终验证 | 8.4 / 465.3 / 5.2 ms |
| 改变路径 / 剩余未处理边 | 27 / 0 |
| 源码、布局 | 通过 |
| 模块位置尺寸、连线源码绑定 | 不变 |
| 操作中取消 | 可点击，原节点与所有路径不变 |
| 一次撤销 | 节点、绑定、全部路径精确恢复测试前状态 |
| 相机 | 测试前后 viewBox 完全一致 |

测试结束截图：[`studio-after-undo.png`](evidence/summary-apply-layout-performance-20261029/studio-after-undo.png)。底部的取消提示来自取消回归测试，不代表第一次优化失败。

### 可复现的引擎基准

脚本 [`scripts/benchmark_summary_apply_layout.mjs`](../scripts/benchmark_summary_apply_layout.mjs) 从正式 catalog 构建 Transformer 默认图（82 节点、80 连线），使用与浏览器一致的显式路由设置。每批检查所有源码/布局/连线约束，并比较节点及源码绑定是否变化。构建初始图不计入以下耗时。

| 场景 | 第一批 | 第二批 | 最终状态 |
| --- | --- | --- | --- |
| 已准备、已验证图 | 1034.5 ms，检查 66 条，剩余 14 条 | 238.2 ms，检查剩余 14 条 | 全部完成、验证通过 |
| 准备后经 JSON 往返的图 | 1401.4 ms，检查 60 条，剩余 20 条 | 321.0 ms，检查剩余 20 条 | 全部完成、验证通过 |

对应 [`benchmark-warm.json`](evidence/summary-apply-layout-performance-20261029/benchmark-warm.json) 与 [`benchmark-cold.json`](evidence/summary-apply-layout-performance-20261029/benchmark-cold.json)。时间预算会使每批数量随机器负载变化，不能要求固定处理条数。

另一个独立加载的未缓存 JSON fixture 首批为 5909.2 ms，其中源码预检 4886.1 ms、路由 998.3 ms；下一批为 333.4 ms，见 [`uncached-json-fixture.log`](evidence/summary-apply-layout-performance-20261029/uncached-json-fixture.log)。这保留了首次完整认证仍可能较慢的证据；它已从 Apply 主线程输入路径移入 Worker，没有跳过校验。

复现命令（在正式项目目录）：

```sh
node scripts/benchmark_summary_apply_layout.mjs . optimized warm /tmp/apply-warm.json
node scripts/benchmark_summary_apply_layout.mjs . optimized cold /tmp/apply-cold.json
timeout 45s node scripts/benchmark_summary_apply_layout.mjs . baseline warm /tmp/apply-baseline.json
```

`baseline` 使用原先显式 Apply 的非交互 `routeBatch` 路径和相同设置，用于观察未采用批预算/原生参数组合的行为；它不是整个旧版本浏览器的端到端测试。

该基准在 45 秒进程时限内未完成（退出码 124，已经输出 82 节点/80 连线的开始记录）。见 [`benchmark-baseline-status.json`](evidence/summary-apply-layout-performance-20261029/benchmark-baseline-status.json) 和对应日志。进程时限包含初始图准备，因此不能将 45 秒视为准确的旧路由耗时，也不据此计算端到端加速倍数。

## 验证与限制

- 相关 61 项回归测试全部通过，覆盖手势、交互性能、预览退役、源码控件、递归通道修复、传输等。见 [`regression-tests.log`](evidence/summary-apply-layout-performance-20261029/regression-tests.log)。
- 最终定向检查 8 项全部通过，覆盖 MLP/Transformer 分批优化、剩余范围续算、零预算、范围变化、源码伪造拒绝、手工折点、未选中边、Apply 撤销/取消、单次完整桥接回复及真实 Worker。见 [`final-apply-tests.log`](evidence/summary-apply-layout-performance-20261029/final-apply-tests.log)。这些与前述回归有重叠，不相加称为独立测试总数。
- 真实 Worker 新增用例另行通过，验证源码核心复用、分批回执及最终约束，见 [`worker-apply-test.log`](evidence/summary-apply-layout-performance-20261029/worker-apply-test.log)。
- `npm run build` 通过；仍有既有大 chunk 提示，见 [`build.log`](evidence/summary-apply-layout-performance-20261029/build.log)。
- 正式 vendor 与 integration 清单合并审计 7378 项资产全部匹配；改动的 6 个 JavaScript 文件语法检查及 `git diff --check` 通过，见 [`asset-audit.json`](evidence/summary-apply-layout-performance-20261029/asset-audit.json)。

本轮代表性性能证据为当前 Transformer 工作副本、标准 Transformer 和 MLP 约束回归，不等于对所有模型、所有 3000+ 可见节点展开状态完成浏览器压力认证。大图首次认证、完整状态回传与持久化仍可能占主要耗时，后续优化应分别测量这些环节，不能删减语义校验来满足延迟指标。
