# 当前 native diagnostic 独立末审

三会话 raw / validator、aggregate 核心脚本与结果、两份保存重开 SVG / 当前 store、源 fixture 和四张实际 JPEG 已只读复核。54 个输入（含 fresh core 导入模块）在本审计前后 bytes / SHA256 一致；旧39矩阵、产品、dist、root 正在更新的文档与 manifest 没有作为新增定稿声明。

| 会话 | 请求试次 | eligible / matched / interaction 样本 | 匹配离散子集 p95 |
| --- | ---: | ---: | ---: |
| stress300 | 5 | 14 / 10 / 4 | 2016 ms |
| MLP pilot | 4 | 9 / 6 / 2 | 2008 ms |
| MLP corrected | 3 | 8 / 7 / 3 | 2016 ms |

各分母单列，缺失仍 null，未合并 p95。三份 validator 的所有字段重新计算后与原结果完全一致；aggregate 在内存禁用两处输出写入后全部断言通过，JSON 规范化后和 MD 均精确等于原输出。

Pilot 错误命中 Linear4，位置 +52/+36，root 宽 +52、network 宽 +52 / 高 +36；请求 Linear1 的 drag / undo / redo 三项失败保留。Corrected 三项成功。连续 DOM 几何和 rAF 回调只是代理，不认证 paint、呈现 FPS 或性能门槛。

两链 saved SVG = reopened SVG = final raw SVG，封存 envelope = 当前隔离 store 字节；visual rev4/8、storage rev1/1。Fresh 当前 formal core 渲染保存 document 的完整 interactive XML 也精确一致。304 / 8 条 SVG metadata sourceFacts 用独立 Python 映射保存 architecture 后一致；included source 内容 / digest 与正式 fixture 字节一致。这是存储与画布一致性补证，不是第二个独立渲染算法、fresh 源码分析或运行正确性证明。

四个 JPEG 原文件均通过 view_image(original) 实际查看，编码尺寸均1253×705。Raw测量是 iframe1280×720/DPR1，二者变换来源未知，不用图片坐标认证 CSS 几何。`mlp-saved.jpg` 显示未保存 header 与 redo footer，不能证明保存完成；结论由随后保存 DOM、重开 SVG 和 store 对照支撑。Stress saved 为79%上部裁切视图，reopened 为1%极细长条，不能认证细节像素一致或可读性。MLP reopen 清空选择并改变画面相机；不认证相机或 undo 历史持久化。

保留一个原审计脚本限制：raw / validator / envelope 先 parse，106行才首次绑定哈希，因此 parse 到 first-binding 的窗口尚未由脚本排除。本轮独立稳定 bytes 复核没有发现实际漂移；后续应从同一冻结 bytes 同时解析和计算 binding。本轮未修改原脚本与原输出。

补充核验由本轮 tool exec 执行；没有宣称已有独立 fresh-render / sourcefacts 原日志文件。详细 JSON 保存确切执行源码、Node 段、输入绑定和结果。执行脚本是临时 /tmp 文件，不是已封存 workspace 独立复现脚本；源码已嵌入 JSON，复制运行会只更新本 review 两文件。

人工视觉、物理印样、字体/硬件锁定、pin 保护、活动手势取消、持续宿主呈现和真人研究均未认证。原始采集过程与服务生命周期没有由本审查重演或认证。
