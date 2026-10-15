# act 可持久化适配模块验证

本目录使用真实 `Constraint relationship of architecture diagram/act` 源码，按正式 JSON 适配标准生成、验证、注册、从磁盘重开并应用到预览。未导入或执行模型，未修改 act。`receipt.json` 逐文件记录全部 74 个文件的内容 SHA-256、集合、大小和 mtime，前后完全一致。

| 符号 | 适配源结构节点 | 源依赖 | 应用后预览总节点 | 截断边界 |
| --- | ---: | ---: | ---: | ---: |
| `policy:ACTPolicy` | 187 | 106 | 181 | 3 |
| `policy:CNNMLPPolicy` | 43 | 10 | 54 | 0 |
| `detr.models.detr_vae:DETRVAE` | 219 | 134 | 214 | 3 |
| `detr.models.detr_vae:reparametrize` | 7 | 6 | 独立 helper | — |

`registry/` 包含四个最终有效数据模块；`superseded-adapters/` 只保留中间解析规则下生成、当前明确拒绝的历史定义，不属于最终 registry。`*-preview.json` 保留应用结果；`unit-tests.log` 为 19 项正反例/无执行测试；`recheck.log` 为本次真实输出。`receipt.json.runtimeFiles` 绑定最终运行代码 hash。最终前端作用域修复后再次生成与复验，CNNMLPPolicy 适配标识更新，旧定义已经移入 superseded 目录。

ACTPolicy、CNNMLPPolicy 的 `__call__` 和 DETRVAE 均可静态打开。适配子树恢复 DETRVAE/CNNMLP、Transformer、Encoder/Decoder、两种 Layer、Joiner 的源码定义关系。大正文采用显式 `definitionReference` 避免重复展开耗尽预算；源引用只共享源码正文，不合并运行实例。预览中原始边逐项保持，源清单 digest 不变。

本结果验证源码结构和数据适配持久化。未知训练/推理条件、配置重复次数、外部 torchvision/IntermediateLayerGetter 实现、动态分支的真实张量路径和 shape 仍未证明。12 层实际包含预算触发时明确 `truncated`，不能称为完整运行架构恢复。Registry 不执行插件，不授予结构性源码生成；源码保留生成由独立流程验证。

`geometry/` 保存此次独立 Node VM 几何检查。陌生简单、条件、36 个并列语句，既有 VAE/Transformer 的折叠、混合、全部展开均通过 source/layout/edge/line-contact 检查。ACTPolicy 15 个可见对象时，修复前 10574×768，修复后 1199×974；每层折叠基准释放隐藏后代宽度，同依赖层仅按显示换行，不新增序列箭头。三项新增回归覆盖证据/绑定不变、独立语句限宽、手动偏移与折叠重开恢复。

上述几何轮次的历史性能：ACTPolicy 深入到 43 个可见对象时，当时同步 `route + validateView` 检查耗时约 11.4 秒；35 秒进程预算终止后续深链检查。浅层 12–27 对象约 118–216 ms。该轮次未改变既有八个布线/递归引擎文件；后续事务内源码合同缓存、矩形粗筛与线段包围盒剪枝修改了四个引擎文件，独立差分和更新后的耗时见 [routing-performance](../act-source-support-20261015/routing-performance/README.md)。不能把浅层改善或有限前沿的性能增益写成所有深层交互已流畅。

复验命令（从正式项目根目录）：

```bash
PYTHONPATH=src python3 -B -m unittest discover -s tests -p test_source_adapter_registry.py -v
PYTHONPATH=src python3 -B -m archcanvas_cli adapter list --root '../Constraint relationship of architecture diagram/act' --registry docs/evidence/act-adapters-20261015/registry
```
