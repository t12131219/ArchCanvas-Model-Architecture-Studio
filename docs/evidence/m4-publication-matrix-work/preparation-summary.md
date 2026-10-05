# Publication final matrix preparation

已只读复核上一轮封存清单：80本地文件、94链接的 bytes/SHA 全匹配；current-verification175个SHA绑定无漂移，root-final-recheck的count及两个文件摘要一致。生成后复核仍全部匹配。当前构建为 DPwoyNJW（JS SHA `c7189a047fbd29cba25779a9098d5b2c1265e21c827620834379d0e611af3bc4`），产品/文档/既有证据未改。

按现有CLI与协议执行三步，均exit0：生成 `docs/evidence/visual-golds-publication-final`；prepare `.archcanvas/browser-visual-matrix-publication-final`；verify同矩阵，`frozenFilesUnchanged=true`。命令、时间、stdout/stderr摘要见 `commands.json`；本目录保留三份实际输出日志。

候选报告有36variants，geometry/spatial core通过；生成117文件，未请求PNG。示例出版预设同时要求最小文字≥7pt、主线0.5–1pt，36项均未同时满足，报告如实保留。此推荐不是通用期刊门，core候选不是浏览器截图或人审。

| 模型 | 实际前沿 | 节点数 | 组合数 |
|---|---|---|---:|
| Transformer | L0/L1/L2/L3 | 12/23/41/49 |16|
| MLP | L0/L1 |4/8|8|
| Residual CNN | L0/L1/L2 |8/10/24|12|

9个真实前沿×paper/monochrome×85/180mm=36基础组合。spec冻结21implementation、3build、72core文件及候选报告摘要，完整expandedIds写在spec中。另要求每个模型至少一份独立edited-after样本，共3额外样本；不伪造浅模型层级，也不把基础图作为编辑证明。

当前实际浏览器采集0/36、edited models0/3；visualAcceptance仍pending-human-and-browser-review。没有打开浏览器、操作8886或启动/占用8881–8885服务。后续根任务实际采集36+3后再独立核验；本准备不继承旧39矩阵覆盖。
