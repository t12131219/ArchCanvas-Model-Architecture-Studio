初审的尺寸 metadata 错误已逐图纠正。我从 .png 后缀推断 PNG 结构并直接读取 byte16:24，未先检查编码；这导致三个初审报告里错误的 dimensions 数值。46 个原始文件均以 FF D8 / JFIF 开头，实际编码是 JPEG。

Pillow 解码/verify 与独立 JPEG SOF 宽高解析对全部46图一致：40图 1280×720；saved-mlp-reopened 和 compact-cnn-observed 共4图 1102×835；pinned-move-refused-final 两图 1102×905。

原初审报告、图像和其他原始记录全部保留；本记录覆盖其尺寸及“PNG编码”描述，实际原图查看及粗状态观察不因metadata纠正而替换。逐图路径、byte/SHA、旧metadata和新尺寸均在JSON中；46图末复核未改变。后缀与实际编码的差异仅记事实，不推断采集方法或成因。
