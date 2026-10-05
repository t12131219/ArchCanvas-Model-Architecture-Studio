# 实际矩阵 SVG 的独立路由几何分析

`audit_cases.py` 从实际保存的 `canvas.json`、浏览器 `browser-scene.svg` 与服务 `figure.svg` 读取事实，复用已有独立 XML parser 与 TypeScript oracle。它不调用产品 `buildScene`、router、scorer，不操作浏览器，不执行用户模型；所有新输出限定在本目录内并拒绝覆盖。

输入是实际 captures 清单时，路径相对于清单目录；也可单独提供case目录。完整矩阵完成后直接对最终清单运行，新标签不能复用已经存在的out目录。

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python \
  docs/evidence/m4-bcf-browser-matrix-work/routing-quality/audit_cases.py \
  --captures docs/evidence/m4-bcf-browser-matrix-work/captures-001.json \
  --out docs/evidence/m4-bcf-browser-matrix-work/routing-quality/new-analysis
```

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python \
  docs/evidence/m4-bcf-browser-matrix-work/routing-quality/audit_cases.py \
  --case-dir docs/evidence/m4-bcf-browser-matrix-work/cases/transformer-level0-paper-180 \
  --out docs/evidence/m4-bcf-browser-matrix-work/routing-quality/new-single-case
```

独立算法已有15个污染反例。每次wrapper运行会重新执行并保存其真实stdout/exit。XML层核对document/revision/source/IR、公开node/port geometry、rendered metadata，并额外将每条渲染route的tensor/role/endpoints/聚合canonical edge IDs核对到实际保存的Architecture，而不是相信SVG自己声明的tensor分类。

新增adapter的8个独立污染控制（伪tensor/role/port/projected owner、空/重复/重用/缺失canonical edge）已全部拒绝，原始输入不修改，见 `adapter-controls.json`。wrapper exit0只说明输入解析、canonical binding和控制执行没有抛错；具体endpoint核对、browser/export几何是否一致必须读取各自字段，非零cross/overlap也会照实输出，不能把exit0当布局通过。

报告包括：

- strict-interior crossing edge pairs与每pair的唯一交点；区分不同tensor、无共同projected owner、相同tensor。
- positive collinear overlap pairs与每pair/lane的区间并集长度；相同tensor共享干线单列。
- collinear compaction之后的真实bends、U-turn reversals、route总长。
- endpoint Manhattan lower bound与超出量；超出量可能由obstacle/port/direction约束引起，不能直接称不必要绕行。
- route centerline穿入node body或endpoint ancestor header、canonical port锚定、viewBox边界。
- 每个交叉/重合pair的source-bound端点、tensor与canonical edge清单，便于独立定位到实际图，而不是只给总分。
- browser/export对应route与body geometry一致性；全部输入、算法和输出hash。

一个case的route数量不是canonical relation数量，frontier会聚合关系；比较不同层级时不能拿总bends直接判更差。85/180mm或彩色/黑白重复case可具有相同几何，但仅当完整输入字节/绑定证明相同时才归组。重展开布局恢复、四向拖动后的路由美观另需真实操作前后case，不继承baseline。

当前parser只支持完整document SVG，不支持detail proxy grammar；unsupported metadata、curve/relative path等明确失败。报告中端点误差容差是已有oracle的0.15画布单位，strict算法epsilon为1e−6；`.25` inset是centerline intrusion定义，不是出版安全距离。

没有覆盖stroke宽度、箭头头部、标签/文字框、glyph装饰、near-miss、自相交单条route、T-junction/端点接触、屏幕像素/字体或审美。`aestheticCertified`、`humanCertified`、`publicationCertified`、`presentedPerformanceCertified`始终false。几何0缺陷不能代替真人审看；非零统计也不能自动判所有相交或弯折不必要。

## 已执行的首个实际case

`first-case-analysis`绑定Bc构建采集的Transformer L0 / paper / 180mm实际工件，未新增浏览器操作。输入及算法执行期间稳定，1/1 case的两SVG解析成功，15/15 oracle污染控制被拒绝。浏览器与服务导出route/body几何一致：12nodes、12routes、25represented canonical edges；不同tensor严格交叉1pair/1point，重合7pairs/820.8units，无共同端点owner的重合3pairs/414.1units，20bends、0U-turn、0body/header intrusion，端点/viewBox核对通过。剩余crossing/overlap原样报告，不能称路由美观通过或完整矩阵分析完成。

详细首次执行范围和输入hash见 `first-case-analysis/audit.json`；wrapper源字节应与其sourceBindings核对。后续脚本如改变，请用新out目录另采，不覆盖本次结果。

## 模块库覆盖和产品下一步

见 `module-coverage.md` 与 `module-coverage.json`。它们是正式17模块和本地DL-Playground行为参考的只读比较，不是对参考项目执行正确性的认证；不从失败原型或DL-Playground复制实现。
