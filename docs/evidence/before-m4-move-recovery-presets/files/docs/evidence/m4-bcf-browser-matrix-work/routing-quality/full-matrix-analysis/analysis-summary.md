# 当前Bc完整39例的独立路由几何摘要

39/39实际case的浏览器与服务导出共78份SVG已独立解析。78份canonical投影、端点及viewBox核对通过；39对browser/export routes和body几何相同。工作目录Canvas/browserSVG/exportSVG与封存矩阵117份文件逐hash/大小一致；124项输入、算法与captures清单绑定复核无变化。已有15个oracle污染控制全部拒绝。未操作浏览器、未执行模型、未改产品或既有证据。

MLP/CNN共22个case没有不同tensor的严格交叉或线段重合。Transformer全部17个case仍有交叉与重合；当前不能称路由审美通过。所有78份SVG为0U-turn、0body/header中心线穿越。

| 代表前沿 paper/180mm | 节点 / 路由 | 不同tensor交叉pair / pair点 | 不同tensor重合pair / 长度 | 弯折 |
| --- | --- | --- | --- | --- |
| mlp-level0-paper-180 | 4 / 2 | 0 / 0 | 0 / 0.00 | 0 |
| mlp-level1-paper-180 | 8 / 6 | 0 / 0 | 0 / 0.00 | 8 |
| residual_cnn-level0-paper-180 | 8 / 7 | 0 / 0 | 0 / 0.00 | 4 |
| residual_cnn-level1-paper-180 | 10 / 9 | 0 / 0 | 0 / 0.00 | 14 |
| residual_cnn-level2-paper-180 | 24 / 23 | 0 / 0 | 0 / 0.00 | 28 |
| transformer-level0-paper-180 | 12 / 12 | 1 / 1 | 7 / 820.80 | 20 |
| transformer-level1-paper-180 | 23 / 29 | 20 / 21 | 7 / 1052.80 | 72 |
| transformer-level2-paper-180 | 41 / 51 | 22 / 25 | 19 / 4185.21 | 116 |
| transformer-level3-paper-180 | 49 / 59 | 20 / 23 | 19 / 4314.21 | 124 |

39个case分别完成了几何核对，但body/port/route geometry排除页宽、style、annotation、bounds、revision后只有9种configuration；不能把这些分组宣称像素或出版尺寸等价。三个edited-after新增annotation而node/port/route geometry与对应baseline一致，不据此认证四向移动后的路由或美观。

具体问题可以直接定位到原图：TransformerL0的 `edge:7 × edge:43` 是source_mask到encoder与target_embedding到decoder的不同tensor路线，严格交点在 `(348.3,397)`；L3的 `edge:45 ↔ edge:46` 为target_mask与memory_mask在decoder入口的不同tensor路线，重合601.8单位；`edge:50 ↔ edge:57` 为target_mask到self_attention与memory_mask到cross_attention，无共同owner但重合499单位。完整端点/ports/tensor/canonical edge IDs及所有冲突pairs均见 `analysis-summary.json` / `transformerConflictDetails`。

下一步建议优先调查mask/memory角色的稳定外部走廊和独立lane；保持owner位置、pins、frontier、canonical port与所有语义完全不变，只在相同Canvas上比较route变化。改动应独立核对交叉/重合下降、没有新穿越/U-turn，再在当前真实截图与出版尺寸审看。不能为降低总分隐藏binding、合并不同tensor或移动固定节点。

Manhattan endpoint lower bound只提供几何下界，无法证明obstacle/方向约束下的多余绕行。当前bends和detour不直接标为“不必要”；sameTensor共享干线单列。centerline统计没有stroke宽度、arrowhead、text/glyph框、near miss、T-junction/端点接触或单route自相交。

全部结论为AI工程几何证据。真人、字体保真、物理出版美观、持续presented性能和活动取消仍未由本任务认证；M4保持partial。
