小型 CNN 的 inserted 与 redo 完整 SVG 字符串一致。reopened 的完整 SVG 字符串不一致：唯一 XML 差异是首个 Input 的 class 从 `draft-node selected ` 变为 `draft-node  `，表示重开后清空选择。仅移除这个已定位的选择 class 后，完整 XML 一致，图形几何、节点/边 ID、路径和文本均保留。

同目录 review.json 的 `reopenedFullSvgStringExact:false` 正确。README.md 此前“一致”措辞写错；本更正覆盖该句，保留原文件便于追溯。
