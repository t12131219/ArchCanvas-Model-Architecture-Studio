# 当前构建 stress300 原生输入独立审计

状态：passed-with-explicit-limits。仅新增诊断；不认证 M4 性能目标、持续呈现或真人任务。

复现：`python3 docs/evidence/m4-current-native-diagnostic/audit_stress300.py`。脚本不导入产品、observer 或 validator；独立计算与另存 validator 输出逐字段核对。

原始收据 9,291,956 bytes / SHA256 `1ec9e57e44958464095083abc3e3189e6d2b87aeefe41195a5341d6bca307cd3`。19 个 scoped 输入在审计前后 hash 完全一致；生产3文件和probe6文件均与当前磁盘原字节匹配。未另捕获HTTP响应正文。

五试次为4→304对象展开、手工具pan、Linear 1拖动、undo、redo。pan终点+48/+32 CSSpx，完整SVG/frontier/revision/public selection不变；drag节点+40/+24 canvas px。去掉SVG attribute和metadata两个revision数值后，undo恢复全部SVG字节到drag前，redo恢复全部SVG字节到drag后；已保存浏览器SVG与最终raw逐字相同。无pins，因此没有pin保护结果。

离散事件14 eligible /10 matched /4 interactions；matched子集p95 2016 ms。drag pointerdown与redo的down/up/click缺失，共4项保持null，不是零延迟。

| 操作 | 实际 down→up 窗口 | 可信moves | 窗口内rAF回调 | 最大回调间隔 | observed时间窗口内几何变更 |
| --- | ---: | ---: | ---: | ---: | ---: |
| pan | 8002.2 ms | 8 | 16 | 983.3 ms | 8 |
| drag | 8084.0 ms | 8 | 11 | 1016.5 ms | 7 |

窗口使用实际输入event时间戳，不含Arm后等待；几何变更另用实际observedAt窗口。JSON保留两种分母和完整回调时刻，不把回调或几何变化写成presented FPS。八秒代理输入不是人工任务耗时。

文档始终观测为visible，iframe focus有true/false，top focus为true；没有持续宿主呈现证明，调度原因仍未知。fonts loaded/loadedFaces=[]不绑定实际解析字体。

首轮传输截断记录保留；工具DOM读取失败与AX大frame限制不在此脚本的完整原始工具日志范围中，不能据缺失判零或成功。saved重开链、机器/字体锁定、人审与研究者任务未纳入本审计。

详细结果：[stress300-independent-audit.json](stress300-independent-audit.json)。
