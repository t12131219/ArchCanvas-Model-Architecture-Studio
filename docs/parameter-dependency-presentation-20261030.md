# 参数读取箭头改为节点详情（2026-10-30）

开发 renderer：`native-semantic/25`。既有冻结包不自动包含本次改动。

## 原因

截图中从 Multi-head attention 边框连到 query / key / value 和 w_o Linear 的灰色箭头属于 `parameter-read`，由 framework-contract 的权重读取证据产生，不是额外的 Q/K/V 激活输入。原投影把不可见参数映射到可见祖先模块，将参数依赖当成普通连接进行端口分配和布线，因此出现从模块边界返回内部 Linear 的箭头。

浏览器修复前当前切面共有 22 条这种参数箭头。并非根据灰色像素删除连接：常量、mask、buffer 的真实输入也可能是灰色，不能按颜色一并删除。

## 通用规则

原生 Studio 的 SemanticEngine 投影显式启用 `parameterReadsAsAnnotations`。在 canonical 边进入呈现合并、端口分配和路由之前，将所有 `kind === 'parameter-read'` 附着到当前可见消费节点，记为 `parameter-dependency`；不可见且不属于当前模式的端点继续按排除规则核算。完整原始边、源参数和操作数槽位保留在 annotations 与 canonical IR，详情可查看。

规则不依赖模型名、Q/K/V 名称、Linear 类型、路径、颜色或 TFB 项目。对概览、详图、源码全部展开、局部原子展开以及后续导入模型使用同一规则。参数节点仍可在源码原子层查看。data / interface-binding / control / effect 及 buffer 数据输入继续保留；参数本身作为显式 data 操作数使用时也保留其数据边。

renderer 24 及更早版本若 IR 含参数读取，则保存的旧切面与旧 JSON 布局重新编译，旧布局作为 migration provenance 保留。没有受影响依赖的兼容视图保留原布局。源码和代码生成权限不变。

## 验证

- `catalog-projection-tests.log`：43 个目录模型配置 × F0 / F1 / 完全源码展开，共 129 个视图。无可见参数读取箭头，876 次参数读取投影全部保留原始边证据，canonical 边核算无丢失或重复；未执行模型。
- 对照测试：在未命名通用模型中仅移除 parameter-read，mask、buffer、真实张量输入、控制依赖和同一参数的显式 data 操作数逐项保持一致。
- `final-tests.log`：114 项检查全部通过，涵盖局部原子展开、旧布局迁移、保存重开、编辑入口、混合层级及完整源码布局。原生五组源码样例继续验证实际路由。
- 正式 runtime `8798` 浏览器重载旧保存视图后：85 个节点、101 条连接、0 条 parameter-read 箭头，source / layout 为 true，invalid 为空，storage 为 saved。截图 `browser-after.png` 展示 Q/K/V 和输出 Linear。

证据目录：`docs/evidence/parameter-arrows-20261030/`。批量 129 视图验证的是语义呈现与核算，不等同于对全部大图运行完整布线性能验收。
