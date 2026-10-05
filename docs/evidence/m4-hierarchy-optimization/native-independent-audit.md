# 层级优化构建：两试次原生输入独立审计

状态：passed-with-explicit-limits；M4 完整性能与人类门仍未认证。

复现：`python3 docs/evidence/m4-hierarchy-optimization/audit_native.py`。脚本不导入产品或 observer，不操作浏览器；独立重算 source/IR/DOM/匹配，另外运行离线 validator 并核完整 parsed output exact。

Raw 3,335,243 bytes / SHA256 `8ad2e110e445d36b091025f98eac8215453dec05c3db78f3a0f21c386399bc5d`。23 个 scoped 输入全部使用同一份先hash后parse的冻结bytes，审计后磁盘重读全部相同。生产3/probe6及build-context exact；不声称另捕获HTTP正文。

正式 fixture 300 个显式 Linear/ReLU 声明、304 canonical nodes/304 edges、source aggregate 与 semantic IR digest 独立重算相符。5 个完整 SVG snapshot 的 canonical sourceFacts 全字段相符；未重执行 frontend 或模型。

| 请求 | 结果 | DOM事实 |
| --- | --- | --- |
| toggle network | true | 4→304，可见源码身份，rev0→1，相机不变 |
| viewport hand-tool pan | true | 可信左键down/up＋8moves，+40/+24 CSSpx，rev1不变 |

Pan 全 SVG、frontier、空pin/selection markup逐字相同，目标Linear1 canvas body不变；实际输入开始于viewport，Linear1仅是几何观测对象。无pins，因此没有固定对象保护认证。

离散 eligible 6 / matched 3 / interactions 1，matched subset p95 2016 ms，全部来自toggle一个interaction。Pan down/up/click三项未匹配，保持null，不以0填充或借用其他输入。

| 实际down→up窗口 | duration | trusted moves | event时间窗口rAF | observed时间窗口rAF | observed几何变化 |
| --- | ---: | ---: | ---: | ---: | ---: |
| toggle | 2.7000 ms | 0 | 0 | 0 | 0 |
| pan | 8003.8000 ms | 8 | 16 | 17 | 8 |

全session 132 rAF / 69999.1000 ms；first→last callback cadence 1.89862667 callbacks/s，start→stop分母 1.88573853 callbacks/s。二者均不是 presented FPS；完整trial包含外页准备/等待，不能当持续交互速率。

toggle实际down/up窗口零回调；pan八秒是可信自动化输入的实际时间，不是人类任务耗时。toggle有90ms longtask，pan无观测longtask；不证明长期或完整产品CPU耗时。

iframe1280×720/DPR1，frameRect y−8↔144；公开对象screen记录使用iframe client CSSpx，不是固定宿主屏幕。document观测visible，iframe focus true/false，top focus true，没有连续host呈现认证。

活动cancel未执行；post-up blur/lostcapture保留原事件。字体loaded且loadedFaces空，不绑定解析font文件；hardware未知。native截图文件未保存，瞬时工具image不纳入像素审计。真人0，研究任务/人审/保存重开均不由本轮认证。

wrong stress300 option的selector deadline及contentDocument TypeError见tool-observations.json，仅root工具响应转录，原完整失败工具日志未捕获；不抹除、不算请求试次成功。

审计首跑（tool chunk5b4a70）误把nn.Sequential源码构造当成IR kind，‘source-recovered network’断言失败；实际正式IR为Module/container、repeat300 independent。修正仅审计假设，源码与raw未改，失败不计成功；记录为工具响应转录。

[完整JSON](native-independent-audit.json) 保留独立计算、全部绑定、fresh validator stdout hash、缺失项与限制。
