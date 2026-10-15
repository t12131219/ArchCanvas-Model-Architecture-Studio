# 源码模型目录与入口解析

`archcanvas_python.discovery` 对上传的 Python 文本或选定目录进行 AST 只读扫描，不 import、不执行构造器、模型或工厂。`discover_directory(root)` 返回 `archcanvas-model-discovery/1`；`discover_files({relative_path: text})` 使用相同规则。模型入口沿用 `module:Class`。

模型目录包含可由本地基类链证明继承 PyTorch `nn.Module` 或已登记的公开 `nn` 基类的类；同时保留其他顶层类和无法静态建立词法入口的嵌套类记录。导入别名、本地直接别名、相对导入及包内重新导出可解析。继承方法使用 Python C3 顺序；自定义 `__call__` 优先于 `forward`，包含继承的自定义 `__call__`。重新绑定、装饰器、冲突继承、未知外部 mixin 或异步方法不能取得安全入口合同。模块顶层及任意条件分支中的类方法赋值、删除、`setattr`/`delattr`、类字典修改会保守阻断相应旧方法；继承者也不能继续使用被替换的基类方法。条件别名/导入重绑定不能作为无条件合同。正式编辑与递归预览共享该方法选择，方法的来源位置仍指向实际声明文件。

`models` 给出模型名、入口、基类、`entryMethod`、`methodOwner`、源位置、`openable` 和具体限制。`candidates` 只含有可定位本地同步方法的入口；可选择入口不表示整个模型已消除待解析区域，也不保证源码生成。`roots` 表示没有被本次源码包含关系指向的局部模型，可能同时包含被外部框架使用的辅助模块，不等于可运行应用入口。

`relationships` 是有源位置的**可能包含关系**，不属于张量边：

- `owner`、`target`、`slot` 表示类与成员/容器槽位。
- `instanceId` 保留共享对象来源；`count: null` 明确表示数量依赖运行时。
- `evidence` 指向成员赋值，`targetEvidence` 指向目标构造表达式，`via` 保留工厂调用路径。
- `certainty: possible` 表示动态分支、未知数量或工厂上下文中的候选；多个候选并列，不会被连成执行顺序。
- `targetLocal` 区分本地类与外部 `nn` 合同。

扫描器追踪本地工厂的赋值、tuple 返回、参数传递、集合追加、静态/动态循环、构造器别名和继承初始化。它访问 AST 中可能建立结构的语句，**不会执行这些语句，也不会将跳过副作用后的结构当作可生成源码的纯工厂合同**。外部工厂、动态属性与无法证明的配置保留在 `unknowns`；`resolvedInSomeContexts` 说明其他工厂路径是否提供了该槽位的候选，并不取消原本未知的上下文。

位置/关键字重复、仅限位置参数被关键字传入、未知关键字、参数过多及展开的 `*args`/`**kwargs` 不会建立特定构造参数包含关系；`invalidBindings` 记录相应源位置。一个抽象构造上下文中的同槽位后续无条件赋值会退休旧包含关系，另一个共享别名槽位继续保留；条件覆盖的多个候选均保持 `possible`。`assignmentOverrides` 保存覆盖证据，不能将早已被 `None` 覆盖的构造器误当成当前模块。

`inventoryComplete` 表示在本轮文件、语法与预算范围内完成**本地已证明模型类的目录扫描**；它不表示外部依赖也有可用源码，也不表示类之间全部关系均可确定。`hierarchyComplete` 另外要求没有未解决槽位、无效参数绑定、动态数量或条件包含候选。`complete` 是 `inventoryComplete` 的兼容字段。调用方不能把 `complete` 当成完整运行架构或源码生成授权。

例如本次 `act` 的 20 个 Python 文件中，15 个本地模型类全部列出，包含两个自写 `__call__` 的 Policy；因此目录可以完整。其 Backbone 外部实现、摄像头/clone 动态数量和配置分支仍需保留 unknown/possible，因此包含层级不能宣称完整确定。对外展示应分别说明“已列出全部本地模型”和“部分层级仍待证明”，而不能仅用一个“完整支持”覆盖两者。

独立目录发现预算是 512 文件、16 MB、10 万解释步、深度 16；交给解析器的 `read_directory_files` 默认仍是 80 文件、2 MB。所有路径必须是相对 `.py`；目录读取拒绝源码符号链接并排除 `.git`、虚拟环境、缓存、构建目录。语法失败、嵌套类与预算终止均显式返回，不能静默遗漏后报告完整。

通用验证：`PYTHONPATH=src python3 -m unittest tests.test_model_discovery -v`。测试包括带顶层 `raise` 的工厂源码，确认分析只读取文本；另覆盖别名与继承、C3、`__call__`、工厂参数/共享实例、动态数量、分支候选、重绑定、伪 `torch`、文件预算与符号链接拒绝。`act` 的目录与不修改源码证据保存在 `docs/evidence/act-source-support-20261015/`，最终集成验收以同目录中最新运行收据为准。
