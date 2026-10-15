# 最终源码值依赖复验

本目录替代旧 `act-adapters-20261015/receipt.json` 与旧双解析矩阵中的适配身份、源码依赖数量和后端实现 hash；旧记录保留为历史。`intermediate-before-slot-isolation/` 是本次已纠正的中间结果：部分未知 return 曾把已证明的 tuple 槽合并为宽泛来源，最终实现和当前收据保留已知槽隔离。

从正式项目根目录复现：

```bash
PYTHONPATH=src python3 -B docs/evidence/act-source-support-20261015/final-arrow-support/reproduce.py
PYTHONPATH=src python3 -B -m unittest discover -s tests -p 'test_source_*.py' -v
```

脚本只把 `act` 作为文本读取，重新 scaffold、校验、注册并重开四个适配，分别以正式编辑解析器和预览解析器静态打开全部 15 个入口。全部输出写入本目录；没有 import、实例化、执行模型或修改原始 `act`。`receipt.json` 记录全部 74 文件的字节摘要和修改时间、当前实现 hash、四个适配和 30 次静态打开结果。

修复包括未知调用解包后的整体源码 producer 保留、现有无调用赋值/return 卡对 RHS 的 def/use 箭头，以及部分未知的局部结构化 return 不污染其已证明的兄弟槽。未知 Value 保留 `complete=false`，没有升级成 tensor、shape、运行路径或生成权威。原始预览边逐项比较保持原样；新增边仍为 `syntaxOnly`。

纯别名透明传播，不添加语句顺序边。下标赋值可以显示 RHS 的来源，但当前不恢复任意 dict mutation、别名副作用或返回槽。条件容器和互斥分支的包含关系不添加张量箭头；单独的控制显示由前端负责。四个新定义使用 `generatorRevision: source-inspection/2`，规则升级前的旧定义显式为 `stale`，不会悄悄应用。

`ACTPolicy-training-branch-relations.json` 列出训练分支直接子节点和折叠 frontier 的源码关系；同一个模块内部的多个真实 producer 可以在折叠时投影为同一对容器，前端负责聚合显示。此目录的后端成功不单独证明所有布局、展开时延、路由或真实界面交互已通过，最终界面证据由总报告引用。

后续只读复核见 `readonly-slot-review.json` 和 `readonly-slot-review-tests.log`：复跑现有 23 项依赖用例，并检查当前 ACTPolicy 中 `latent_proj → kl_divergence`、`action_head → F.l1_loss` 的来源，未发现两者的返回槽互接。此次审计未修改实现，也没有扩大语法支持范围。`source-preservation/summary.json` 是最终依赖规则下重新生成的源码保留闭环；审计同时核对其 11 个实现 hash 与当前文件一致，并补充记录共享依赖模块的 hash。
