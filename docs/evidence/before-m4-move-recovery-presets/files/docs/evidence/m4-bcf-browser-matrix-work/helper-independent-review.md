# Bc 矩阵 helper 的独立只读审查

对本报告绑定的当前 4 个脚本和 preparation guard 做静态审查，未运行 browser、helper、测试或完整 collect。预定的 root snapshot → bound-only processor package → separate stamp → fresh index 路径未发现阻断问题。

exact href 只读取对应 artifact；快照源自 saved store，保存与导出 Canvas 做完整 JSON 等价比较；没有 fallback 搜索。processor 只从 root bound 目录构造已冻结 DOM/envelope 与对应 raw Scene/JPEG。stamp 新建独立 receipt，仅增加两项 hash；index 比较其它字段不变，核对 copiedFiles/spec 并拒绝 case/baseline 重复。guard 绑定 Bc 构建、8968 store/origin 与 36/9 spec；formal collect 再独立渲染 Scene 与 normalize 出版 SVG。

边界：generic package CLI 本身允许调用者提供输入路径，bound-only 由本轮 processor 参数构造保证；直接 CLI 调用须审查 command/inputBindings。processor 脚本未列入 preparation guard，本报告单独绑定其当前字节，变更后需重新审查。以上不认证浏览器原生来源、像素、真实环境、真人或物理出版可读性。

细节和输入 SHA-256 见 helper-independent-review.json。
