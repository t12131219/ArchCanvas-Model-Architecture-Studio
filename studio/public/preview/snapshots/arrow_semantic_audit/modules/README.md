# 模块实际箭头端点审计与修订

最终 **76 个模块 × 3 视图全部通过**；独立核对 2723 个真实 SVG 图框和 2407 条实际箭头。

审计不调用共享绘图引擎的 resolver。它读取固定源码哈希/AST 证据、typed IR、接口合同、布局端口和实际 SVG XML，并独立推导正确的可见计算节点与字段。SVG tooltip 不作为端点正确性的证明。

## 修订前发现的问题

基线228视图的图框与路径几何均和布局记录一致，但存在 110 个展开端点缺少接口或真实续线。容器 in.auxN/out.auxN 的错位、named输出与graph helper的边界跳过都可能导致这个问题。
另外删除展开parallel scope入口的冗余箭头：它们没有实际内部续接，而每条真实分支输入已独立连到子算子。

## 源码对应的修复

- 68个特殊接口合同覆盖20个模块；普通chain入口/出口由真实IR boundary递归解析，rank仅决定位置。
- BatchNormFlow把mean和var分别送入标准化/EMA；manual BN保留mean的来源，不从variance发出；gain送到真实乘法。
- FlowSequential保持features/logdet字段独立；Glow各chunk字段及保留首项保持独立。
- ActNorm正常计算从原loc/scale状态读取；初始化Copy只更新状态，不能替代正常输入。
- Transformer-XL relative shift从shift_slice真实返回结果发出；固定buffer的constructor来源也来自真实注册算子。
- 每条实际SVG箭头保留data-endpoint-binding；layout保留物理port_fields及每条IR edge的endpoint_projections。

## 验证证据

- [最终完整审计](after_endpoint_audit.json)：228视图、2407实际箭头，0错误。
- [实际SVG错误注入](actual_svg_negative_checks.json)：8类全部拒绝，包括实际leaf换兄弟节点、var换mean、logdet换features、折叠field替换、retained x换square、shape换value。测试保持源码和图框几何不变。
- [接口语义负例](flow_interface_negative_checks.json)：22个源码case、119个变异全部拒绝，其中7个新增接口混淆反例。
- 全部模块的AST与语义测试通过，399个错误变体拒绝；见 module_programmatic_guide/generated/semantic_negative_checks.json。
- [来源接口库存](source_interface_inventory.json) 和 [逐接口解释](source_interface_review.md) 保留实际AST符号与行号。
- [代表性目视记录](final_visual_review.json)：最终12例详细图的2页contact及4例真实像素局部；并不宣称人工逐像素检查全部228图。

## 离线复现

```bash
python3 prototype/arrow_semantic_audit/modules/audit.py --report prototype/arrow_semantic_audit/modules/after_endpoint_audit.json
python3 prototype/arrow_semantic_audit/modules/negative_checks.py
python3 prototype/module_programmatic_guide/checks/verify_semantics.py
```

源模型未导入或执行。这证明所选静态接口与实际导出一致，不证明任意新模型/任意运行时分支，也不等于数值正确性或全局最优布局。历史输出基线保留，本次箭头/IR接口授权更新列出前后哈希，不宣称旧8例仍逐字节相同。
