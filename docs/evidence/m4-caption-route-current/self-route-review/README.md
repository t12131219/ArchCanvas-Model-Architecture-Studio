# 最终捷径的自身几何审查与修复

此次审查只改 `studio/src/core/orthogonalRouter.ts` 和 `studio/tests/route-shortcut-independent.test.ts`；没有改历史 gold、现有 router-work 证据、其他产品、入口文档或 dist。正式项目独立实现，没有旧原型代码。

冻结修复前 router 的 SHA-256 为 `d735e2a718610c8ce118847d34e5cd241ecab10fb7696b38e34e48f800d83185`。它已经逐对保护其他路由，但 `validDirections` 的相邻 U-turn 检查不能保护非相邻自身段。确定性 seed `1129976764` 的有限探索执行 100000 次尝试，其中 85082 条原路径通过独立简单几何和正文过滤，82046 次发生实际缩短；捕获 1 次新增自身接触，0 次重叠。随机探索是发现工具，不是全域证明，所有原始输入和输出在 [exploration-before.json](exploration-before.json)。

已确认反例：原路径 `M 0 0 V -24 H -16 V -64 H 56 V -104 H 40 V -128 H -48 V -104 H 0` 没有非相邻自身接触或重叠，旧 batch 却接受 `M 0 0 V -114 H -6 V -104 H 0`。首段穿过终点 `(0,-104)`，与第四段形成新增自身接触。对四个无关障碍的 16 子集重放确认，只有 `(-16,-96,8,24)` 的一个障碍就能复现。新路径是 `M 0 0 V -6 H -22 V -104 H 0`，保留端点、方向和至少六单位逃逸，并消除新增接触、仍严格缩短。[实际子集输出](counterexample-subsets.json) 保留这两个版本的 batch 结果。

新 guard 将 `shortcutPair` 用于同一路由的非相邻 segments，忽略相邻段共有的正常转角；每个无序段对只检查一次。原路由的 contacts/crossings/occupied overlap 区间只计算一次，新候选必须是其子集，因此不要求旧输入都简单，不能把旧已有交点的删除换成新位置的交点。原已有 crossing/contact 的另一固定案例仍能缩短，并保留原来的 endpoint contact。端点 contact 同样受保护；crossing 分类排除 whole-edge endpoint 并不删除 contacts。

自身比较与 peer 比较共享既有 `ROUTE_SHORTCUT_BUDGET` 的 pair 和 segment allowance，采用 `1e-7` 容差；没有新增无预算的几何扫描。预算不足时返回 undefined，不接受未验证候选，保留前面已验证的路由。旧 router 的 `0.01` 全局容差未修改。这个结论只针对 final shortcut pass，不把它扩展为旧 generic/family/refinement 所有任意输入的全域安全证明。

独立 focused **19/19**、严格 TypeScript exit **0**。相同测试替换成冻结修复前 router 重放 **18/19**，唯一失败明确是 `new contact 0:-104`；oracle 独立手写，没有调用生产几何函数。[修复前失败](before-fail-attempt-2.txt)、[修复后通过](new-focused-attempt-2.txt)。sensor test 单独确认普通转角不计、自交/终点接触/正长 retracing 都能检出。固定小案例和九个 source frontiers 均执行自身 subset、peer subset、端点方向、escape、长度/弯数、确定性和 input 纯读断言。

源模型的九个前沿共 **198** 次 route 出现，仍实际改变 **3** 次、减少 **161** 世界单位和 **4** 个弯，与修复前最终捷径的变化完全一致。[新量化](source-frontier-measurement.json) 不计新增独特 tensor、不证明全局交点最少、浏览器像素、呈现 FPS 或真人体验。本子任务没有 full build、模型执行或浏览器操作。

首次抽取反例测试漏掉必要障碍，冻结前版也能通过；原 [attempt 1](before-fail-attempt-1.txt) 和 [replay source](before-replay.test.ts) 完整保留，没有计为正确性证据。第二次用 16 个障碍子集缩减后保留必要障碍，才得到真实旧失败。最终 product 源码和测试 bytes、所有本目录 artifacts 由 [manifest.json](manifest.json) 精确绑定。
