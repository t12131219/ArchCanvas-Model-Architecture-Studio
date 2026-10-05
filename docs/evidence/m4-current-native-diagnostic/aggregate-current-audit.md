# 当前构建三会话独立审计

状态：passed-with-retained-pilot-and-explicit-limits。M4 性能、人审与真人任务均未认证。

复现：`python3 docs/evidence/m4-current-native-diagnostic/audit_current_native.py`。脚本不导入产品、observer、validator；独立计算与单列validator结果比对。初版stress300脚本/JSON/MD原字节保持。

41 个scoped输入在审计前后hash完全一致；三份raw的各生产3/probe6绑定均与实际磁盘一致。两模型正式source内容/fixture和保存source/IR一致。

| 会话 | 请求试次结果 | Eligible / matched / interactions | matched子集p95 |
| --- | --- | ---: | ---: |
| stress300 | toggle:true, pan:true, drag:true, undo:true, redo:true | 14 / 10 / 4 | 2016 ms |
| mlp-pilot | pan:true, drag:false, undo:false, redo:false | 9 / 6 / 2 | 2008 ms |
| mlp-correct-target | drag:true, undo:true, redo:true | 8 / 7 / 3 | 2016 ms |

三个分母不合并；未匹配输入仍null。Pilot drag请求Linear1，实际命中Linear4，记录为no-input、没有请求before/active geometry；该次实际Linear4+52/+36保留。随后undo/redo对请求Linear1无变化，false；完整SVG证明其恢复的是意外Linear4移动，不计请求成功。

| 会话/手势 | down→up实际窗口 | moves | event窗口回调 | 最大间隔 | observed窗口几何变化 |
| --- | ---: | ---: | ---: | ---: | ---: |
| stress300/pan | 8002.2 ms | 8 | 16 | 983.3 ms | 8 |
| stress300/drag | 8084.0 ms | 8 | 11 | 1016.5 ms | 7 |
| mlp-pilot/pan | 7999.7 ms | 8 | 16 | 983.4 ms | 8 |
| mlp-pilot/drag | 7010.3 ms | 8 | 9 | 1000.0 ms | null（未绑定请求） |
| mlp-correct-target/drag | 8005.5 ms | 8 | 9 | 1000.0 ms | 7 |

此表按实际event down/up去掉外页准备等待；几何另按observedAt窗口。回调与DOM变化不认证呈现FPS。

Stress300目标+40/+24，MLP corrected目标+52/+36；两链全SVG除attribute/metadata两个revision标量外逐字undo/redo恢复。两模型保存→真实重开SVG和finalraw完全相同，封存envelope→当前隔离store原字节相同（visual rev4/8，storage rev1/1）。这些结果不认证相机或undo历史持久化。

iframe实际1280×720/DPR1；文档观测visible，iframe focus true/false，top focus true。三个会话外页frameRect均有y−8↔144滚动，iframe-client对象screen坐标与outer页面坐标不混用；不证明固定连续宿主呈现。无pins/真人，解析font/hardware未知。

Pilot意外Linear4移动还使root body宽+52、network body宽+52/高+36；完整恢复核对包括这些祖先变化。首跑审计的过窄‘仅一个body变化’断言失败记录保留，不计成功。

服务启动sandbox失败、首raw transfer截断和初版stress审计原bytes均保留。工具DOM读取失败与AX frame限制缺完整工具日志范围，不据缺失判0；脚本绑定截图bytes但不声称像素或物理尺寸审看。

详细结果：[aggregate-current-audit.json](aggregate-current-audit.json)。
