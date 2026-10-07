# 新增输入诊断独立审查

只读新增 `work/input-diagnostic`、当前上下文与必要源码；未执行产品测试、validator、模型、构建或浏览器动作。旧 39 例矩阵 receipt、历史环境出处与 `final-readback-attempt-2` 未修改。

通过报告为 `reviewer-repair-attempt-3/report.json`，42 个输入 before/after 精确不变。独立重算整个双侧 event matcher 候选图，未分配 trial 的输入也参与竞争；14 个 assigned eligible discrete inputs 中 10 个唯一匹配、4 个缺失，合并 interaction 的最大 duration 得 4 个 interaction，nearest-rank P95=3000 ms。该分母是离散子集，不是全部输入或全页 INP。342 个 rAF 的 callback cadence=1.8838800636873003 fps；314 个 idle intervals=2.0254510176278746 fps；这是回调频率，不是 presented frame rate，也不指认慢速原因。

实际 6 个 trial 中，错误目标 `repeat:instance:model.DenseStress.layers` 的首个 toggle 无输入、无 frame，不计成功；后续 toggle/pan/drag/undo/redo 共 5 个成功。独立核 same-pointer release、held interval 无 cancel、source/IR binding、pan 终点 camera 与公开 SVG/frontier/selection 连续性，drag/undo/redo 位移 +32/−32/+32、相机不变，以及全 SVG 仅去 revision 后的恢复精确。两级 ancestor container 的 width 随 drag 增32、undo减32、redo增32；该自动包围尺寸变化明确保留，无关 body 不变。末尾 focus/control blur 与 release 后 lostpointercapture 不计 held input cancellation。

上下文 3 个正式 assets、6 个 probe source 的当前 bytes/hash 全精确。fixture `stress_300/model.py` 的 source descriptor 独立重算 sourceDigest，304 个 sourceFact 表达式独立匹配 AST 源片段。IR digest 只检查在记录中保持一致，没有重建语义 IR。context 没有独立 capture timestamp，不能称其为 session 前后响应字节快照。

UA 与 DPR 来自 observer 本次 start() 对 iframe navigator 与 viewport 的实际读取，Linux Chrome/154、1280×720、DPR1；其范围仅此次 same-origin iframe harness，不能回改旧 39 receipt 的历史 UA/DPR 出处。`fonts={status:loaded,loadedFaces:[]}` 不认证 resolved fallback font 或字体 bytes。22 条 visibility 为 visible 仅代表这些观察点，不能认证持续无调度干扰；304 是完整 SVG rendered membership，不代表所有 body 均在 viewport 内。

原整段读的截断 JSON 精确保留：200099 B / 200011 UTF-16 units，不能解析，不计成功。分块新原件 9283722 B / 9177272 UTF-16 units，92×100000 以内 chunks 的收据 hash、长度、解析一致；所有记录 buffer dropped=0。buffer 未丢弃不能证明 Event Timing API 覆盖全部输入，4 个缺失项仍保持未测量。

前两份独立 reviewer 失败保留：根目录 `report.json` 错把 pointerup 后的 blur 当 active cancel；`reviewer-repair-attempt-2/report.json` 错把 ancestor 自动 width 改变当无关 body 改变。精确源码快照均保留，修正的是审查辅助断言，不是产品/raw/validator。第三份通过没有覆盖失败回执。

observer 记录 trusted=true 是浏览器事实，atomicNativeDrag=true 是 root 操作回执，不等于独立 OS 来源、人类参与或 presented paint 证据。连续输入只给非因果 DOM change proxy。当前数据不认证 paint 延迟、全页 INP、硬件/字体锁、性能阈值通过、持久化或美学。
