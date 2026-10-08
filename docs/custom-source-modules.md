# 源码自定义模块合同

2026-10-07。编辑模式中的源码窗口通过 `POST /api/authoring/custom-modules/preview` 检查一个 Python `nn.Module` 类，随后将可重复使用的定义写入当前草稿的 `customModules`。预览、检查、生成和重新打开均不 import/exec 用户源码，不执行模型，也不修改原始源码目录。

## 预览请求

```json
{
  "source": "from torch import nn\nclass MyBlock(nn.Module):\n    def forward(self, x, memory):\n        return {\"features\": x + memory, \"memory\": memory}\n",
  "entry": "MyBlock",
  "label": "我的模块",
  "constructorValues": {}
}
```

`entry` 选择源码中唯一的顶层类。类须被静态证明继承 `torch.nn.Module`，且直接编写同步 `forward`。普通具名参数和 keyword-only 参数成为连接端口，包含有默认值的参数；这些端口在搭建图中均须连接。当前前端不支持 positional-only、`*args`、`**kwargs` 或继承的 `forward`，预览会具体报错。所选类依赖的本地辅助类应写在同一份源码中，未解析的外部调用保留为未知内部。

构造参数是 JSON 对象，接受有限 JSON 字面量；不能填写可执行表达式。遗漏的参数仅在其默认值也是可恢复字面量时补齐，必填参数和未知字段会报错。构造合同固定在定义内，修改源码或构造值后重新预览会产生新的定义身份。

输入、返回槽和定义限制分别为 16 个端口、16 个静态可恢复张量返回槽、每份草稿 24 个自定义定义、每份源码 128 KB。标量、tuple、list、dict 和嵌套返回中的可恢复张量槽由真实 AST 返回路径确定；非张量常量不作为可连接输出。未知控制/调用可以保留为显式 opaque 内部，输出的形状与 dtype 不被推测。

## 保存与生成

预览返回 `definition`、可加入模块目录的 `module`、静态分析 `architecture` 和 `verification`。定义保存原始源码、类名、构造值、SHA-256、稳定 `Custom_…` 身份，以及输入和输出路径合同。后端保存/重开/生成都会重新核对定义；篡改端口、源码或哈希会拒绝。

同一模块可以重复插入，不同源码即使使用同一个 Python 类名也进入不同的生成文件命名空间。生成文件保留完整用户源码，并追加确定的适配器。适配器为每个张量输出添加真实的 `nn.Identity` 锚点，保证 passthrough 与多输出在折叠视图仍有可辨识的 canonical producer；这些锚点属于生成源码，未伪造 IR 连线。新包装模型只传递具名输入，并按已核对的返回槽选取输出。

生成后重新静态分析整个源码 corpus，核对原始源码字节、构造事实、实例身份、输入名称、输出锚点和与其他模块连接的精确端口。已生成模型即使在新会话中重新导入，也通过独立的源码调用/返回重放恢复折叠源码模块合同；新包装文件不覆盖保留的源码。

包含自定义模块的草稿中，`complete` 仅说明连接、拓扑和输出可达性满足生成合同。验证字符串为 `static-topology; custom output shapes unknown; no model execution`；`unknownTensorNodeIds` 明确列出无法推导形状的节点。形状可推导的上游原子模块继续静态检查，自定义输出及其下游的未知形状不会被冒充成功推导。`verification.modelExecution` 始终为 `not_run`；静态生成不证明运行兼容、数值正确或数值等价。

`nodes[].visual` 独立保存卡片尺寸和十六进制填充/描边色。它可用于空白模型和源码模型，不创建语义分组，不改变生成源码；草稿 CAS 保存、重开与源码 frontier rebase 均保留此字段。

## 验证证据

专项测试在 `tests/test_custom_modules.py` 和 `tests/test_custom_modules_http.py`，覆盖多输入/嵌套多输出、同类名隔离、重复实例、原子模块连接、未知形状、源码/端口篡改拒绝、原始源码副作用未执行、CAS 保存重开、新副本注册、源码 frontier rebase、无会话元数据的再次导入以及视觉样式保留。
