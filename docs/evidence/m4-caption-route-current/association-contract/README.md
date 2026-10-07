# 一般连线标签关联与派生引导线

本轮修复明确的体验缺口：先前 BTw memory 标签虽避开卡片，却从原 y436.1 移到 y388.1，与真正 Encoder→Decoder 的 y444.1 水平路线相距56 scene units，且没有引导线。根 Agent 的实际100%稳定图与独立只读审查确认文字可读、所属路线关联模糊；不是“原文字完全遮蔽”。旧172件 review 与9件 association follow-up继续冻结，见 [`../before-change/manifest.json`](../before-change/manifest.json) 的正式变更前存档。

本 Agent 实现一般策略，没有 special-case模型名或edge ID，没有扩路由budget。`placeEdgeLabels`始终读取最终Scene route：近旁、无碰撞、名义文字范围距所属route不超过18单位的标签保留原坐标。其他标签在原锚点±64单位的候选中，优先找近旁安全位置；只有能添加不超过48单位的清楚直法向guide时，才接受更远位置。Guide始端位于所属route一个线段的严格内部，末端抵达该标签名义范围边界；检查它不穿leaf卡片、repeat背板、expanded header、note、其他caption，并拒绝与任何其他route或已保留guide相交、接触或重合。共享tensor不赋予连接另一route的权限。找不到安全关联时保留原文字与位置，发出`layout-edge-label-blocked`或`layout-edge-label-association`；不会通过删除标签伪造清爽画面。

文字范围仍为确定性9字号每codepoint一em加padding的名义envelope，非浏览器resolved-font量测或校准印样。关联距离测的是nominal envelope至实际owner route的几何距离，不是baseline距route。直guide长上限48不是FPS或物理出版标准。

`Scene.captionGuides?`单独保存 `{id,kind:'caption-guide',sceneEdgeId,path,stroke,width}`。它是派生presentation，不新增`Scene.edges`、canonical edge、tensor、port、sourceFact或Document/history字段。SVG统一renderer以独立`data-caption-guide-id`与`data-caption-for-edge`绘制width0.8、opacity0.65、无marker、pointer-events none的线；publication和interactive使用同一逻辑。SVG metadata把它放在`presentationDecorations`，不放进`renderedBindings`。Whole export与buildScene相同；detail生成boundary/reroute后重新计算guide，并将完整caption/guide计入Scene bounds。正常无label场景不增加空captionGuides字段。

[`summary.json`](summary.json)和`scenes/`保存本轮未build current core的五组概览/whole/root-detail彩色与黑白结果。概览memory为 `(288.5,484.1)`，guide为 `(298.5,444.1)→(298.5,473.1)`、29单位；root detail同几何平移为 `(273.5,496.1)`与`(283.5,456.1)→(283.5,485.1)`。实际模型绑定及原水平memory route保持；root统一最终build与真实浏览器核对，本目录不继承这些source SVG为新build像素证据。

明确的确定性工作上限为128标签、1024节点、512route、1024额外body、262144累计path字符、4096route point、每caption320候选、全batch两百万body/segment/contact检查。前置越界保留每个caption并逐一diagnostic；耗尽检查后不能采用未验证候选，剩余caption保位置及内容并显式记录预算。这些是工作上限，不是wallclock/presented性能认证，不能声称所有密集图都完成关联。

真实源绑定 [`before-regression.txt`](before-regression.txt) **1/1修前失败**，断言远memory caption缺少owned-route guide。首次实现后现有8专项通过。扩充测试时[`focused-attempt-2.txt`](focused-attempt-2.txt)出现一项oracle错误：undo/redo合法递增revision，测试误要求旧revision完全相等；保留原日志，改成除revision外比较所有Document字段，没有把该错误记成产品问题。

独立审查另找到真实边界反例：先绘制的guide宽0.8，后来移动的caption虽不碰中心线，名义范围仍可进入它的stroke envelope约0.1单位。此前guide选址已将caption扩张±0.4，但反方向caption选址没有同样padding。新产品回归先失败，见[`reserved-guide-stroke-before.txt`](reserved-guide-stroke-before.txt)，随后补成两个方向相同的guideWidth/2名义clearance；审查原失败保留，不隐藏。

最终[`focused-attempt-6.txt`](focused-attempt-6.txt) **44/44、0skip**。其中10个新guide回归涵盖实际source memory、近标签保持、平移+CJK、共享route不误接、note/其他caption/route/reserveguide、多preset+alias+whole/detail+history+metadata分离、24caption一般stress、129caption前置上限、80caption支持域实际检查耗尽和latercaption避先前guide真实线宽；另外7个既有标签测试与routing/export/history回归一并通过。这些为重叠专项数量，不加到full suite上。`strict-noemit-attempt-3.txt` exit0，局部`git diff --check`exit0。子Agent没有运行全Studio/build/dist、没有模型执行、没有真人任务。旧`implementation-inputs.json`是修stroke前采样，最终`final-inputs.json`另列，不覆盖它。

本轮实现文件为`studio/src/core/edgeLabelPlacement.ts`、`types.ts`、`scene.ts`、`exportScene.ts`、`svg.ts`、`studio/src/layoutWarnings.ts`，新增`studio/tests/caption-guide-independent.test.ts`。没有修改old gold、旧证据或现有monochrome exact-gold test；route修复由另一Agent负责，只改实际canonical edge path，标签helper消费其最终结果。全套测试与新build若暴露旧gold受派生guide变化影响，由root窄调整当前兼容比较，不能回写历史baseline。

有限搜索和保守名义字框会产生可解释diagnostic；它不承诺全局最短或最美route/guide，不替代resolved-font、最终export尺寸、真人认知任务或300可见对象性能门。复杂Transformer交叉等既有缺口仍独立登记，M4不因本修复宣称完成。
