# 正式证据包独立复核

39 个有效 capture（36 基线＋3 编辑）、39 个唯一 variant/state、39 个唯一真实导出 UUID 均对应独立图片汇总中的案例；两失败原例与 primer 没有进入正式成功覆盖。

234 个 bound→collected 文件映射均逐一字节相等，截图和 browser SVG 与已审 raw 相等。每个完整 CanvasDocument（包含 layoutByFrontier）与保存 envelope 和该 UUID 的 document.json 相等；Canvas canonical digest、完整 browser/publication metadata、源事实、817 条 rendered binding 的全部 canonical members/roles/declared ports 均已核对。

公开 href、screen receipt 的 UUID、service 目录、figure/receipt 字节、输入 publication SVG 和输出哈希一致。包审计的 1,060 个输入重新哈希相符，本次共 1376 个去重输入前后哈希不变。

这些是本地字节、关联和完整声明一致性证据，不认证首次采集不可变、实时存储、原生出处、截图同步、运行时语义或人工验收；未重新执行 renderer/export normalizer，未新增图片查看。原有像素与路线问题保持有效。
