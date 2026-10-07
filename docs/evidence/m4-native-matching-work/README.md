# M4 原生 Event Timing 双向唯一匹配修复

本轮只修改 `studio/src/nativePerformance.ts`、独立 `scripts/validate_native_performance.mjs` 与既有 `studio/tests/native-performance.test.ts`。不改协议/schema、帧采样、界面、旧浏览器 raw/receipt、依赖或模型；没有重跑全套或 build，没有浏览器/服务操作。正式 dist 仍是修复前 `thbum3BQ`；整合 build 和当前浏览器诊断须由主代理单独完成。

旧 matcher 遍历 trial 并逐项消耗 entry。两条同类型/同目标试次在 0/6 ms，一条 entry 在 3 ms，虽然两条都可解释该 entry，首项仍取得 duration。旧独立 validator 使用相同的 used-set 规则并接受一项匹配。`before/manifest.json` 保存三份产品/测试原字节；额外不变的 `perf.ts` 副本只用于执行冻结反例。[冻结 before 重现](reproduce-before.json)明确复现该错误，不是实测浏览器数据。

现在产品 matcher 先建立完整 trial→entry 候选关系和 entry 的反向候选数；独立 validator 单独建立 entry→trial 关系，不导入产品函数。只有 trial 恰有一条 eligible entry 且该 entry 也恰能对应一条 eligible trial 才接受。任何共享候选或重叠候选集保持 null，不依靠列表顺序或逐项移除消歧。Event Timing 的 ±8 ms 窗口、可信事件、target/type/interactionId、processing 顺序和合法 duration 条件均保持既有规则。

手写反例在旧源下实际得到 **5 fail / 4 pass**，原失败日志 [`before-focused.txt`](before-focused.txt) 保留；修复后相同 focused 测试 **9/9**，无 skip/fail，见 [`after-focused.txt`](after-focused.txt)。两条旧 native JSON 用新独立 validator 只读复算仍 exit 0；这仅避免旧稳定独特匹配的回归，不把旧数据认证为当前构建性能。

新增预期覆盖两个 trial 竞争一 entry、重叠候选链、交换 trial/entry 顺序、不同 target/type 的唯一配对、非可信 trial 不制造竞争，以及独立 validator 拒绝把共享候选伪称单项匹配。测试和 matcher 结果都不证明呈现帧、连续 input-to-paint、全页 INP、字体/硬件锁定或真人参与；M4 性能门仍未认证。
