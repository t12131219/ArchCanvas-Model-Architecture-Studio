# 当前构建的真实输入诊断

本轮在隔离 `127.0.0.1:8888` 测量服务使用未修改的正式 DPwoy 构建。所有产品操作经实际 CUA 浏览器点击/原生拖动完成；外页只观察 DOM、可信事件、Event Timing 和 rAF，不发出产品输入、不读取产品隐藏状态。不使用失败原型，不占用五个人类研究席位，也不修改用户 8765 工作区。

三份收据各自保留分母，共九项请求成功、三项 pilot 请求未覆盖。三项失败是一个错误命中和两个未恢复请求目标的操作，不能抹除或计入 corrected 会话。独立审计见 [aggregate-current-audit.md](aggregate-current-audit.md) / [JSON](aggregate-current-audit.json)；第一份 stress 独立审计保留在 [原报告](stress300-independent-audit.md)。

| 会话 | 请求与覆盖 | eligible / matched / interactions | 离散匹配子集 p95 |
| --- | --- | --- | ---: |
| [stress300 raw](stress300-raw.json) / [validation](stress300-validation.json) | 展开 4→304、pan、Linear1 drag、undo、redo：5/5 | 14 / 10 / 4 | 2016 ms |
| [MLP pilot raw](mlp-pilot-raw.json) / [validation](mlp-pilot-validation.json) | pan 成功；drag 实际命中 Linear4、请求 Linear1 未覆盖；随后 undo/redo 对请求目标无变化：1/4 | 9 / 6 / 2 | 2008 ms |
| [MLP corrected raw](mlp-correct-target-raw.json) / [validation](mlp-correct-target-validation.json) | Linear1 drag、undo、redo：3/3 | 8 / 7 / 3 | 2016 ms |

stress pan 终点 +48/+32 CSSpx、MLP pan +32/+20，均不改变 revision；stress Linear1 +40/+24 canvaspx、MLP corrected +52/+36。两个全 SVG undo/redo 链仅规范两个实际 revision 标量后精确恢复。两个保存重开 SVG 完整字节相同；最终存储 envelope 已复制封存。刷新改变相机、重置会话选择/历史，不能称隐藏状态跨刷新恢复。无 pins，不能据此宣布无关固定对象保护。

stress pan 实际 down→up 8002.2 ms 内 16 次 rAF 回调、8 次 DOM 几何变化；drag 8084 ms 内 11 次回调、7 次几何变化。每次有 8 条可信 pointermove，连续输入数据仍是 DOM 代理。回调和几何变化都不是 presented FPS，八秒自动化输入也不是人类拖动任务耗时。工具自动滚动外页，iframe 位置变化明确记录；iframe client 坐标不能升级为宿主屏幕连续性。

Event Timing 缺失项保持 null，不填零。UA/DPR 来自这三份新的实际收据，区别于旧8887矩阵沿用8880的环境 provenance；加载字体状态不绑定实际解析字体文件。浏览器、宿主、CUA、系统与产品的调度因果尚未分离。当前性能目标仍未通过，活动手势取消、固定硬件/字体、持续呈现、39例人工出版审看和3–5真人任务仍待验收。旧39矩阵、独立末审和五个研究席位保留原字节及原范围。

原始传输第一次被截断，保留 [截断文件](stress300-transfer-truncated.txt)。之后按80000字符分段读取同一个页面中完整的readonly收据并校验JSON；分段读取没有修改或重新采集输入。DOM iframe读取错误、locator超时和AX大消息失败为工具限制，详细工具原日志不在本目录，不能据此判断产品成功或故障。

首次沙箱启动因 socket PermissionError 失败；其 pipeline 没有 pipefail，包装 exit0 不能证明服务成功，[原stderr](service-sandbox-failed.txt)保留。获准后以 pipefail 启动实际服务，启动 stdout 见 [service-raw.txt](service-raw.txt)。session41743后来实际 exit143，原因未知；本轮收据和两次保存重开在退出前已完成。不宣称服务仍在线，不从观察超时推定退出。过程记录见 [service-lifecycle.json](service-lifecycle.json)。

复现独立检查（不发浏览器输入）：

```bash
node scripts/validate_input_observation.mjs docs/evidence/m4-current-native-diagnostic/stress300-raw.json
node scripts/validate_input_observation.mjs docs/evidence/m4-current-native-diagnostic/mlp-pilot-raw.json
node scripts/validate_input_observation.mjs docs/evidence/m4-current-native-diagnostic/mlp-correct-target-raw.json
python3 docs/evidence/m4-current-native-diagnostic/audit_current_native.py
```

需要新采集时，以新的独立目录启动同一正式测量服务；保留旧收据，不覆盖本目录。先在实际 UI 载入模型，再 Start → Arm → 真实输入 → settled后 Finish → Stop。目标坐标必须同时核对 iframe 与截图的当时位置，错误命中如实保留。

[research-package-verification.json](research-package-verification.json)是本轮实际 verify exit0，58实施绑定、五席仍 pristine，0分配/收集/真人。产品测试、生产build和已完成出版Python测试本轮未重跑；实现和build字节核对不替代测试。

七份更新前文档与原1475绑定收据已[另存原字节](../before-current-native-diagnostic/README.md)。旧manifest和旧验证收据不回写；其中变更文档须经该归档路径解析旧hash。本轮新封存见 [manifest.json](manifest.json) 和 [追加验证](../m4-current-native-verification.json)。
