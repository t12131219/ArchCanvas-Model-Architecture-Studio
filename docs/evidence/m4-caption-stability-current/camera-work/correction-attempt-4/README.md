# Camera initialization: formal history clone correction

这是上一份相机证据之后的修正包。之前24/24使用原引用mock，遗漏正式createHistory会克隆document；该结果不能认证App初始化。原目录、原测试日志和manifest保持字节，不回写。

主任务实际CUA先显示保存rev23的Transformer，经100%与32,16pan后刷新回默认35,35,.9，而同identity/revision/source/IR及整publicSVG保持一致。[实际失败摘要](actual-before-fix-browser-summary.json)绑定原06/07/08JSON。随后本任务改用正式createHistory：未改旧App时[before-fix](before-fix.process.json)为22/24、2fail，复现所有initial restore/fit被raw引用比较拒绝。

修复删除raw对象引用相等要求，继续匹配id/source/IR/revision/load/intent；fit与persist取实际active history document。[最小修复diff](clone-guard-correction.diff)和[从原件至当前总diff](camera-total-vs-before-change.diff)保留。core/history/source/model执行均未修改。

[focused final2](focused-final-2.process.json)24/24、fail/skip/cancel0；[strict final2](strict-final-2.process.json)退出0；[root scoped diff](diff-check-final.process.json)退出0，另对三个owned文件全文查空白。测试实际调用createHistory，断言doc已克隆、初始化读先于写、两viewport世界中心、active pan拒写、终端/回滚写入、六种stale拒绝，以及fit接收active clone。中间final1的23/24也保留：负控sourceBindingDigest未同步architecture.sourceDigest，先被正式validate拒绝；修正夹具后才计final2。

[report.json](report.json)给出准确分母和限制；[final-source](final-source/)绑定当前源文件。仍未挂载React，正式build及修复后实际CUA由主任务继续。实际before-fix失败不改称通过；真人0、M4partial、M5未开始。
