# 本轮一次20秒simple control独立审核

状态：**passed-scoped-control-with-visibility-false-and-no-studio-exoneration**。本审计未操作浏览器、重采窗口或改product/raw；16个输入先hash后parse同份冻结bytes，末读全部稳定。新的离线validator exit0、全部semantic字段exact；fresh inputBinding/validatorBinding/runtime反映临时路径/新时刻，三类metadata明确排除对等，原saved绑定另独立核准确。

Raw 8574bytes，SHA256 `a1fa05d03f0500c25e1e251c641f7796f41274c5a70629300d155db39b0140d3`。实际自动`timer-20-seconds`窗为20000.4000ms。

| 事实 | 独立重算 |
|---|---:|
| rAF timestamps/intervals | 38 /37 |
| interval p50/p95/max | 983.2 /999.9 /1000.0ms |
| ≤20ms / >500ms间隔 | 18 /19 |
| exact start→stop callback rate | 1.899962Hz |
| first→last interval cadence | 1.94574Hz |
| 一秒桶 | 前2秒各1；之后18秒各2；0.4ms尾桶0 |
| trusted target inputs/matched | 3 /3 |
| matched interactions | 1 |
| native interaction maximum duration | 2008ms |
| target真实down→up | 1ms |

三个pointerdown/up/click共interaction5202，duration均2008ms。native双向唯一type/target/±8ms匹配和queue/processing独立精确；start按钮2条PO记录没有captured start input，不填目标分母。单interaction的p95=2008仅是本有界样本，不是代表性p95或整个页面INP。rAF按每秒桶保留长期低频，不用均值/某个16.6ms间隔掩盖stall；presentedFrameRate/掉帧/continuousInputToPaint均null。

实际viewport1280×720/DPR1、Chrome154/Linux、hardwareConcurrency16；这些不锁定真实硬件/字体。document start/end visible/focused、changes空，宿主capability control-before/control-after均**false**。root display request仍false，实验label或document visible不能证明向用户持续呈现。saved validator没摄入另存capability文件，hostPresentation仍unconfirmed；本报告新增其原bytes绑定和精确读数，不改原validator/raw。

simple页面没有React/SVG/model/Studio telemetry，但它是top-level、产品是iframe，采样非同时、非随机；相同名义viewport与两者低频只能支持环境/调度疑点。**不能因此排除产品SVG替换、React、telemetry或renderer成本，不能定位CUA/宿主/系统/产品因果，也不能用control清除失败性能门。** 产品另保持14/13/5、p95=4008ms与精确公共SVGundo/redo恢复；两个分母不合并。

control没有longtask订阅/字段，不当0长任务。局部callback成本不含浏览器delivery、rescheduling、rendering、timer、target handler或系统总成本，量化0不是零开销。截图未做像素审核，无真人、字体/硬件认证或持续presented FPS。此次独立报告和本轮一窗已足够记录该诊断，不建议在条件未变时重复直到出现较快结果。

[完整JSON](independent-control-audit.json)保留全部frames/native配对、秒桶、bindings、vis读数与fresh差异范围；[脚本](independent-control-audit.py)离线复核本scope，不改输入或产品。
