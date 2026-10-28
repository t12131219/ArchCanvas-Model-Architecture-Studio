# Summary 原生共享语义接入实际 Worker 通道

日期：2026-10-28。本阶段继续以 Summary 的原版语义实现替换 Studio 对应职责；菜单、层级树、对象/图例/页面面板及正式源码/CAS/事务边界沿用 Studio。

## 具体替换

此前 `app.js` 与 `routing-worker.js` 每次直接 structured clone 完整 graph。Summary 原版 `generic-semantic.js` 已有 `transport()`，但未用于实际 Worker。现在新增 `studio-worker-transport.js` 调用该原版实现，主线程和 Worker 各有一个端点，共享精确 ID 对应的不可变语义 core，单次消息传送独立几何 shell。

core 包含完整 IR、实际切面 state、receipts、navigation、authoring、migration、每个节点的 semantic 和每条边的 binding。连续几何操作只发 shell；精确对象引用、节点/边 ID 或顺序变化会触发新 core。初始构建仍发送完整 IR；Worker 构建完成后，主线程先接收完整 core，后续几何请求和回复可复用。没有按名称、摘要或相似内容借用另一来源的事实。

32 个原版 native JS 均未改动。改动只发生在适配层、实际消息边界和测试入口；来源与当前字节见 [本阶段清单](summary-worker-transport-manifest-20261028.json)。原版四项缓存容量没有提高。

## 面板和事务衔接

Studio 面板仍经现有同源 bridge 发出语义切面、F0/F1、物理端口和布线命令。唯一原生画布调用同一 `runGraphTask`，传输层对面板透明；没有新增第二 renderer、第二套 React 语义投影或传输设置面板。

成功回复先还原完整 graph，再交给原有完整 source/layout/edge validator 与事务提交路径；panel snapshot、撤销/重做、导出与保存均读取该实际图。传输包不进入公开编辑 JSON、正式 CanvasDocument 或源码事务。legacy graph 保持原消息形状，Worker 的未编码调用也保留，独立验证与正式旧功能不依赖新缓存。

## 失效和恢复

每个 Worker generation 使用独立端点和主线程 ID 前缀。发送 structured clone 失败、`error`、`messageerror`、输入/输出缓存缺失时，丢弃该 Worker、清空缓存，并让该代所有 pending 请求返回基础设施失败。调用方随后用完整原始输入的独立副本执行已有 fallback，并走相同语义和几何检查。下一次操作重建 Worker 并发送完整事实。

语义拒绝仍作为拒绝返回，不因失败自动改图。过期 Worker 的回调不能终止新 Worker；无关、重复或过期 requestId 不提交。切面超过四项或恢复老历史时可重发完整 core；若并发队列导致缓存被驱逐，则明确重建，不用当前 IR 填补缺失 core。

缓存是传输优化，不是认证。structured clone 不携带 WeakMap 中的可信校验标记；伪造 binding、改变 IR 事实或删除 canonical 输入仍需独立检查并被拒绝。

## 实测与范围

真实 Node Worker 线程加载正式 `routing-worker.js`，通过真正 structured clone 验证：连续 30 次几何校验只发一次完整 core，回复无需重复 core；30 份快照共享冻结事实而保留独立几何。另覆盖 Worker-origin 初始构建、七次切面/历史恢复、精确请求配对、发送失败、异常/反序列化错误、缓存驱逐与语义篡改。

Chromium 使用正式 Studio 和真正浏览器 Worker，通过受控发送失败和运行中错误测试恢复，再从现有面板检查 F0/F1、七次切面、撤销/重做、编辑 JSON、保存及刷新。异常注入仅在测试启动脚本中，产品不含测试后门。

三个大图仅做 300 ms F0 诊断，未开放：

| 模型 | 完整 graph 消息字节 | 同切面几何消息字节 | 减少 |
| --- | ---: | ---: | ---: |
| Transformer · 语义架构 | 17,584,930 | 1,592,053 | 90.95% |
| ForeignComposition | 1,264,719 | 182,138 | 85.60% |
| Transformer · CPU 运行证据 | 4,007,131 | 456,422 | 88.61% |

上述诊断逐字段往返一致，并检查 30 份几何快照共享完整 IR；各图仍有预算内未完成路由（27、16、15 条），这些数值不能作为全部边合法、交互流畅或内存压力合格的证据。首次 core 消息略大于原完整消息，收益来自后续同切面操作；切面频繁变化仍可能传完整 core。文字、导航等几何 shell 仍有重复，host snapshot 与便携 JSON 仍未整体精简。

自主测试先发现适配代码变量重名，已修复；另修正两项测试假设：validate 会按合同刷新 sourceControls，语义 patch 不接受内部 paperAuto。大图诊断脚本第一次把完整消息当 graph 读取，修正为显式 `.graph`；这些开发中失败不列为最终通过证据，最终日志仅记录修复后的执行。

最终验证与当前冻结输入另存 [本阶段验证目录](evidence/summary-worker-transport-20261028/)。不复写前阶段证据。

本阶段不提高 480 节点 / 3600 依赖 / 16 MB 限制。大图持久化、多切面历史内存、完整路由与取消压力、新 CPU 正式隔离执行及 receipt、D1 正式依赖拆分仍待继续；整体迁移未完成。


本阶段最终验证：完整前端 958 项（957 通过、0 失败、1 沙箱 Chromium 跳过）；新增传输专项 12 项（含真实 Worker 线程）、独立副本专项 145 项通过。真实 Chromium：传输/故障恢复 6、手势 5、原生 16、证据 9、组装 12、自适应 8，共 56 项通过。主/独立构建、111 HTTP 资源、32 原版模块与 45 目录资产字节核验通过；独立副本同步 141 项输入、核对 69 个 Python 文件、8 个模块来源及 5 个静态 fixture。详见[本阶段验证](evidence/summary-worker-transport-20261028/validation.json)。整体迁移仍未完成。
