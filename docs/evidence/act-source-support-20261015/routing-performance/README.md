# 源码检查图的通用布线性能

本轮性能优化不改模型、适配 IR 或图的候选路线/代价。下列 8247 ms 等计时属于中间实现，不能作为最终字节的性能结果；计时之后已撤回小尺度下不保守的线段包围盒剪枝，另有源码范围角色签名与折叠标题修复。

四个运行时文件的性能修改范围：

- `source-contracts.js`、`recursive-graph.js` 可将不可变源合同检查与实际物理端口检查分开。
- `semantic-constraints.js` 的现有同步 `validationContext` 保存源码范围和每条边的检查结果。每次候选重新签名 ID、draft、端点、绑定、固定端口、策略、合同、投影；实际物理端口、当前 peer 占用和候选几何始终重检。完整 authority/variant 门、前沿与 receipt 在 context 建立时签名，依赖已有的单事务不可变源码约定；context 不能跨编辑复用，也不声称可检测同一 context 中 authority 的原地修改。
- `router.js` 对可见性网格的水平/垂直行列先筛选可能相交的矩形；留下的候选仍由原有 `inside`、`intersectsRect` 判定检查。线段接触完整保留原有含容差的判定，不再用固定 EPS 的包围盒提前排除。搜索候选与代价保持原有规则。

`before/` 保存此次优化前的四个文件。`reproduce.cjs` 每次在全新 Node VM 中加载运行时，创建同一真实 ACTPolicy 包，按相同顺序展开同一最深链，记录第一次访问各前沿的 `route + validateView`。`before.jsonl`、`after.jsonl` 是中间实现的历史顺序测量；`historical-timed/router.js` 留存该轮带有后被撤销剪枝的 router。`receipt.json` 将历史耗时、历史精确输出差分、先前记录的 SHA 与当前实现 SHA、当前检查明确分开。未把历史收据的哈希冒认为所有计时代码的完整冻结快照。

历史记录中，43 对象 / 26 边前沿从 11337 ms 降到 8247 ms（约 27%）；36 对象前沿从 4103 ms 降到 2771 ms。12–27 对象前沿从 104–198 ms 降到 70–155 ms。当时所有节点、连接（含合同、实际端口及路径）与完整校验结果逐项相同。计时受运行环境影响，只对应当时的输入和前沿；最终撤销包围盒剪枝后的耗时没有在本目录重新测量。

复审反例是两条长度分别为 `.005` 与 `.01`、垂直相隔 `.00001` 的平行线段。原接触谓词的叉积与距离和容差会承认该接触，而固定 EPS 包围盒会提前拒绝。最终直接删除该剪枝；详见 [独立谓词差分](predicate-audit/README.md)。确定性 30,288 线段例和 60,000 矩形行列例均与优化前相同。新增 `previewWireBroadphase.test.ts` 另含明确反例、任意角度/尺度、退化线段和端点的 30,288 例冻结参考差分。

撤销剪枝后的路由成本、线段接触、源合同缓存与 VAE/Transformer/ResNet 路线差分共 21 项测试通过，TypeScript 检查通过。这是最终实现的定向检查，不把历史 ACT 精确输出差分扩大到后续折叠标题变更。

`targeted-tests.log` 包含新增缓存正反例及 VAE、Transformer、ResNet 的缓存开关路线差分，还有陌生源码布局、路由成本和线段接触测试。`geometry-regression.log` 包含原有多模型完整/混合前沿、四方向门、Worker/fallback、手动折点、草稿来源和 wire identity 回归。

历史测量表明当时有限前沿减少重复工作且结果相同；最终检查保留完整源合同与几何规则，更深前沿仍可能花费数秒。这里没有最终延迟保证，也不证明所有模型和所有展开组合都达到即时响应。

在正式仓库根目录顺序重现，避免同时运行其他 CPU 密集检查：

```bash
ARCHCANVAS_BASELINE=1 ARCHCANVAS_OUTPUT=/tmp/act-routing-original.json node docs/evidence/act-source-support-20261015/routing-performance/reproduce.cjs source docs/evidence/act-adapters-20261015/ACTPolicy-preview.json
ARCHCANVAS_OUTPUT=/tmp/act-routing-optimized.json node docs/evidence/act-source-support-20261015/routing-performance/reproduce.cjs source docs/evidence/act-adapters-20261015/ACTPolicy-preview.json
```
