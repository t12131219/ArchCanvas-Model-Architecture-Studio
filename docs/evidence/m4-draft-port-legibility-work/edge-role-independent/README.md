# 草稿连线角色独立核对

新 [手写独立测试](../../../../studio/tests/draft-edge-roles-independent.test.ts) 对 `draftEdgeRoles(draft, catalog)` 的 18 项具名测试通过，0 failed/skip；[枚举运行日志](test-enumerated.stdout.txt)与[进程收据](test-enumerated-process.json)记录实际命令、helper/test 字节。预期在第一次测试前冻结，见 [expectations-before-run.json](expectations-before-run.json)。

合同只把 Add 的直接输入跳连标为 residual：该输入 producer 须是另一个输入 producer 的严格祖先，且相关完整组件使用已注册、方向/类型正确的端口并无环。左右对称；主干和 Add 输出、x+x、独立输入、共享祖先的兄弟分支以及 Concat 都为 data。缺输入、重复绑定、错端口、未知/opaque 模块及相关环路不猜角色。独立未知/环路组件不影响另一已证明的残差组件。显示名称、标题、坐标和数组顺序不参与角色推导；冻结输入核对确保函数不修改草稿或目录。

[七份手写 DAG](source-role-handwritten-fixtures.json)另经过正式非执行生成器的静态角色回读，135/135 核对通过；[报告](source-role-readback-report.json)逐边保留预期/实际角色、目标端口及 Add 类别。生成源码仅保存为文本，未导入或执行，`torch` 始终未被导入。回读使用产品 nodeBindings/portBindings 定位观测对象，再用手写字面预期核角色，不声称独立证明全部源事实或参数。18 个测试与 135 个核对不同范围，不累加。

[总报告](report.json)包含合同及限制。首次默认隔离 Node 运行只显示文件级 1/1；其原日志保留，不代替明确 `--test-isolation=none` 的 18 个具名结果。新测试 whitespace 检查无诊断，git no-index 的退出 1 只表示新文件差异；另明确核无行尾空白与 EOF 换行。本角色未修改产品或既有测试，没有浏览器操作/像素或实体尺寸审看、模型执行或真人记录。结构残差样式不证明 shape/参数有效、最美路由或真人验收。
