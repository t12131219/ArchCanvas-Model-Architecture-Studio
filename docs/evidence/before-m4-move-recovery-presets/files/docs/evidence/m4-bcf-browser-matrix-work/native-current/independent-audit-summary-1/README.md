# 当前原生与四向操作的独立审计

审计者为 Codex 子 Agent `/root/authoring_error_contract`，仅读取原始文件、公开 SVG 和正式源码；浏览器由 root 操作。本报告不计入真人研究参与者、出版审看者或呈现帧率验收。M4 仍为 partial。

新增证据由两份独立清单封存，原始失败、39 案例矩阵及旧 seals 均保持原样：

- `../independent-observation-audit-3/manifest.json`：SHA256 `49d9374c61809f90a49db942eaa3ef4e6adedae4ba30cd63edc59a9d8c3bf4d0`。
- `../independent-supplement-audit-2/manifest.json`：SHA256 `bc6d02bd4cbb9a9797f5bf0476f2e73d54223abb423efda7b1d1d8ca783b4464`。

第一份审计绑定长 16 操作记录、70 个原始 chunks、旧 top-level MLP 五次点击 pilot、9 个正式资源/探针与独立分析源码。第二份绑定新的短四向平移、top-level DenseStress300 三次独立点击、公开资源 URL、正式 native sampler 源码及原始 UI read receipts。输入字节在各次审计前后相等。报告不会把静态 canonical 架构参考当成当前交互的实际保存 Canvas。

| 记录 | 独立结果 | 保留的范围限制 |
| --- | --- | --- |
| 长 MLP 16 操作，同源 iframe | 完整 JSON 与 70 chunks 逐片 hash、连续字符 offset、UTF-8 重组完全一致；32 个 before/after 公开 SVG 快照完成 XML/source/projection 核对；四次节点 drag 均有可信 down、8 moves、同指针 up、revision +1 | frames 与 frameCallbacks 各 dropped 4102；既有 validator 的 completeBuffers=false，四次 pan 的成功判定仍为 false；丢失的 root 操作 journal 未重造 |
| 短 MLP 四向 pan，同源 iframe | 全 buffer dropped 0；4/4 通过既有 validator；52 inputs、273 callbacks、114 Event Timing entries；相机终点与同指针释放相符，公开 SVG/selection/frontier/pins 完全相等 | 仅完成手势，不覆盖按住期间的 Escape/blur/cancel；所有 pin specs 为空，无隐藏 Canvas/history 或保存持久性证据 |
| top-level MLP 五次点击 pilot | 既有 validator 的 2/5 valid 保留；唯一 matched interaction 8582 为 4008ms | 两个 after 跨 revision +2，第五 after=null；不能计 5/5。raw 视口 1280×720，后来 public read 为 1102×835；约 1Hz 的回调原因未知 |
| top-level DenseStress300 三次分开的点击 | 3/3 可信 expand/collapse/expand；revision 0→1→2→3，frontier 4→304→4→304；3 个双侧唯一 interactions；公开 SVG 为 304 nodes、302 routes，source/projection/端点合法 | 不是 20 组 synthetic benchmark 或全性能总体；9.24 米高的单幅导出没有出版可用性认证；没有 pin 保护与真实模型执行证据 |

短 pan 的浏览器 `performance.now` 采样窗口是 **4547ms**（76876.1→81423.1），不是 41.6 秒。journal UTC、后续读取 UTC 与浏览器原始时钟分别保留。每次终点位移为右 +40、左 −40 CSS px，上 −32、下 +32 CSS px，camera scale 不变，document revision 为 1。8 个公开 XML 快照与独立冻结的 MLP canonical 架构一致；逐方向 journal 的 SVG/camera/revision 与 raw 对应值相符。root 将 9 次 UI 切片拼成完整文件，但没有保留每片，所以此新文件仅能核对有效 JSON、全文字符数及 read receipt，不能独立逐片重组。

Event Timing 的 p95 只使用双侧唯一匹配，并将同一 interaction 的最大 duration 计算一次：

| 记录 | 匹配离散 inputs / eligible | 去重 interaction 数 | matched subset p95 |
| --- | --- | --- | --- |
| 长 16 操作 | 35 / 44 | 15 | 3008ms |
| 短四向 pan | 8 / 12 | 4 | 24ms |
| MLP pilot | 1 个有效点击 | 1 | 4008ms |
| DenseStress300 | 3 / 3 toggle inputs | 3 | 176ms（原值 176、72、144ms） |

长记录的所有可信离散事件（包括未分配 trial 的 undo/tool 点击）均参与候选图竞争；每个 input 和每个 Event Timing entry 都要求唯一。该结果与既有 input validator 的逐项匹配完全相符。旧 native sampler 源码使用顺序 unused-entry 匹配并按 trial 统计 duration；本审计另外执行双侧唯一、interaction max 去重，两批真实数据恰好一致，不将此结果推广成该旧实现已覆盖全部歧义输入。300 层三次 target 屏幕锚点位移均为 0；无 pin 记录，不能写成 pin drift 为 0。

四次节点移动实际位移均为 52 个画布单位。24 CSS px 经过当前约 0.460722 scale 后，与记录的该位移相符。独立 XML 解析直接读取真实 body、公开端口和 path；同源 canonical edges/tensors/role/ports 来自已经封存的 MLP 架构。全部四次端点与 viewBox 检查通过，但出现以下几何问题，不能将“成功提交位移”写成“视觉合格”：

| 节点操作 | 几何问题 | 路由统计 |
| --- | --- | --- |
| 右移 | 没有新增非祖先 body 重叠、标题侵入或子节点越界；父容器和端口随场景更新 | 总 bends 8→10 |
| 左移 | Linear1 x=58，network body 左界=80，越界 22 | bends 8→10；无中心线 body/header 穿入 |
| 上移 | Linear1 y=264，进入 network 标题区域；edge2 穿过该父 header | bends 8→6；同 tensor overlap 长度 6→33 |
| 下移 | Linear1 y=368，与 GELU2 body 重叠高度 14；edge3 中心线穿入两个 body | bends 8→12 |

几何 oracle 的 header 障碍包含 SVG divider 之后的 4 单位 padding；像素复核的可见标题区截至 divider，二者范围明确。四次移动中不同 tensor 的严格内部交叉/共线重叠均为 0，无 U-turn；这些数值不覆盖 stroke、arrowhead、text、端点接触、T 接触、近距离遮挡，也不证明所有弯折必要或箭头美观。oracle 的 15 个故意污染控制全部拒绝，属于该独立几何 oracle 的控制证据，不是真人审美或直接 XML adapter 的完整测试。

四次 undo 后的公开 SVG 与移动前一致，比较只移除 SVG `data-revision` 及 metadata `revision`。首次右移前未选中，undo 后保留选中，所以第一次 selectionMarkup 不相等；其余三次相等。right redo 恢复右移 SVG，collapse/reexpand 恢复展开 SVG。没有据此认证隐藏 undo history 或已保存 CanvasDocument 相等。长记录另有未分配 trial 的可信 undo input-24/25/26，raw 事件明确保存，未把它补造为新的原始操作 journal。

长记录最后一个已存 callback timestamp 为 298615.7（observedAt=298617），所以 later pan up/down、zoom、collapse/reexpand 的帧数为 0，代理时延为 null。四次节点 drag 的 down→up 分别为 158.5、150.1、136.2、150.6ms，active callbacks 为 9、9、8、9。前两个 long-session pan 有已存 callback，但全 buffer 完整门槛仍失败；其相机和完整事件流的独立终点事实只在记录范围成立，不覆盖完整性能。新短 pan 的 active callbacks 分别为 8、9、9、8，continuous change proxy 仍只是“首次后续采样几何变化”，不标成 causal input response 或 paint。

DenseStress300 完整 SVG 标准 XML 有效，公开 projection 与封存 canonical source facts/edges/tensors/ports 相符；viewBox 为 0 0 595 30542，width=180mm、height=9239.6mm，后续 fit transform scale≈0.0179752。不同 tensor strict crossing/overlap 为 0、总 bends=8、无 U-turn、无 centerline body/header intrusion，只有同 tensor trunk overlap 6。缩放后的图极窄和单幅高度是实际可用性问题，不由路由计数消除。rAF 6547 次、interval p95≈16.7ms、max≈133.4ms；原始 longTasks 两次为 138、112ms。全部属于采样事实，不能称呈现 FPS 或绘制流畅合格。

300 层 raw-single-read 与 final-public-dom.svg 都保留了工具截断：前者 JSON 无效，后者只有 200011 字符。`raw-full.json` 为 503244 字符，`final-browser-scene-full.svg` 为 859169 字符，分别与实际 UI read receipt 相符；root 声明使用 11 与 18 个连续切片，但这些单片没有留下，本审计不能逐片 hash/reassemble，只核对留下的 full artifact/read receipt/parse/source coherence。

输入资源实际磁盘 hashes 与声明相符，UI 公共加载 script/style URLs 指向 Bc JS/CSS。该证据没有读取 HTTP response bytes，也没有据 URL 声称所有源码的编译 provenance；正式 sampler、telemetry 与 panel 的当前源码 hashes 单独绑定。document.fonts loadedFaces 为空不能锁定 fallback 字体、系统或硬件。旧 sampler telemetry 的 Event Timing/long task 使用 200 条滚动上限但没有 dropped 计数；这批 60 ET/2 long tasks 未达到上限，仍如实记录该契约缺口。

独立审计脚本自身的失败尝试也保留：`independent-observation-audit-1/2` 分别遇到错误的 chunk 索引 key 与错误的 callCount 字段比较，`independent-supplement-audit-1` 遇到 DOM revision 字符串与整数比较。修正仅发生在新审计 adapter，随后使用新输出目录；这些失败目录不是完成报告。没有修改 raw、chunks、product、既有 seals，也没有导入/执行用户模型或旧 runtime。

逐像素观察另见 `../pixel-audit/README.md`。模块覆盖另见 `../../routing-quality/module-coverage.md`：17 个基础模块、11 类、点击/拖入与搜索已存在；组合模板、新手引导与连续 shape/dtype 可见性仍为缺口，不能按 AI 测试代替真实小白参与者。后续优先解决移动后的父边界/标题/兄弟冲突、受语义约束的外部通路布局及大模型的可读概览，再进行实际研究者与出版尺寸审看。
