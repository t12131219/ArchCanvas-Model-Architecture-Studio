# 本轮五项产品原生输入独立审核

状态：passed-scoped-diagnostic-with-visibility-false-and-performance-gates-open。本次未操作浏览器或改product/raw。23输入使用先hash后parse的同份冻结bytes，末尾重读一致；fresh离线validator exit0且完整parsed output exact。

实际服务是8897，当前JS oI5，raw 9,239,688bytes / SHA256 `d08725b9e8857f68bc5eae0c5702e92f60f144fe5588dc2aa09d0c3dfd9bc1bd`。131个read ranges连续覆盖9,133,326UTF16字符，UTF8 bytes不同正常；原getAXState/native frame limit按v2转录保留；v1误归因getAttribute仍保留且只修转录、不改raw，不认证原工具读取过程。

## 请求与公共场景恢复

| 请求 | 判定 | 原始事实 |
|---|---|---|
| network toggle | true | rev0→1，frontier4→304，camera不变 |
| viewport pan | true | 手工具/可信左键，+40/+24 CSSpx，rev1与完整SVG/frontier/pins/selection不变 |
| 指定Linear1 drag | true | first down确为network.0，client+30/+18经0.789091缩放和4px网格成为canvas+40/+24；rev1→2 |
| undo | true | rev2→3，完整SVG除恰好两个revision标量恢复pre-drag；对象/camera/selection/tool/frontier exact |
| redo | true | rev3→4，完整SVG除两个revision标量恢复moved状态；同字段exact |

全文11SVG snapshot的304 canonical sourceFacts、source/IR、XML对象body和frontier映射与冻结正式architecture精确；源码AST独立确认150 Linear/ReLU pairs，source aggregate和IR digest独立重算。Architecture参考是同source的既有正式分析工件；没有导入/执行模型或重新跑frontend。渲染frontier304不等于300对象同时在viewport可读。

## 原生匹配与实际手势窗口

全部双向唯一type/target/±8ms/positive interaction配对从raw独立重算：**14eligible /13matched /5interactions；matched subset p95=4008ms**。每interaction按最大duration仅计一次；drag pointerdown input-38缺失保持null，不能补0或当<50ms。不是整个页面INP、代表性任务p95或连续input-to-paint。

| 真实down→up事件窗 | duration ms | trusted moves | event窗口rAF | observed窗口rAF | observed几何变化 |
|---|---:|---:|---:|---:|---:|
| toggle | 2.8000 | 0 | 0 | 0 | 0 |
| pan | 7001.3000 | 8 | 9 | 9 | 7 |
| drag | 7095.1000 | 8 | 11 | 11 | 6 |
| undo | 6.9000 | 0 | 0 | 0 | 0 |
| redo | 6.8000 | 0 | 0 | 0 | 0 |

这些窗口严格使用真实trusted first down与同pointer up，不包括arm/finish外页等待；observedAt窗与eventAt窗分开。Pan/drag有8moves，各coalesced原始值与event→capture延迟列在JSON；输入约7秒是代理自动化事实，不是人类耗时。普通up之后lostcapture、后续blur原样保留，活动区间无Esc/cancel/blur/lostcapture，不计取消。

全session 642rAF /332992.3000ms；start→stop回调率1.927973Hz。完整trial cadence混入准备/等待，validator fps字段与本报告Hz都是回调节奏，不能当presented FPS、掉帧或持续性能通过。

## 实际可见性与边界

产品前后capability false，display request前false/后false；`visible`label是实验意图。冻结副本[product-audit-visibility-snapshot.json](product-audit-visibility-snapshot.json)保留读取时原bytes；root visibility原路径可能后续追加control-after，本报告不重绑定未来内容。Document观测visible、iframe focus true/false、top focus true，不能否定capability false或证明持续host呈现。

11首末snapshot frameRect有y−8/144外页滚动；几何screen为iframe client CSSpx，不能升级固定host屏幕。字体loaded/loadedFaces=[]不认证font文件；hardware未知，无pins/活动取消/保存重开/真人，截图未做像素审核。4条longtask与trial overlap保留，没观测到某条不证明系统无stall。

当前数值仍未达声明性能目标；现有工具不能取得presented-frame证据，simplecontrol另采另审，不把两个场景合并、解释成产品已排除或改旧raw。

[完整JSON](independent-product-audit.json)列所有sourceBindings、candidate graph、真实window/coordinates、scene恢复、changed bodies及fresh validator摘要。[脚本](independent-product-audit.py)可离线复核本scope；会重写本审计结果，不改输入/product。
