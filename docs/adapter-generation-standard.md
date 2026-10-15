# 源码适配模块与规则模板生成标准

本标准让 Agent 为待解析区域编写、验证并保存可复用的源码视图规则。规则能补足旧源码检查器尚未展开的 Python 句法结构：独立解释器直接匹配当前 AST、选择真实子结构、证明有限的源码关系，不调用旧 `SourceStructure` 来认可 Agent 写出的事实。预设案例可以作为表达方式与规则样本，实际事实始终来自当前源码。

生成分两层：不绑定模型路径和实例的规则模板 `archcanvas-source-rule/1`；从模板与完整当前源码重新生成的绑定实例 `archcanvas-source-adapter/2`。原有 `archcanvas-source-adapter/1` 仍用于保存通用检查器已经恢复的结构。新规则产生源码检查视图，支持展开、收起、移动、源码定位、保存和导出；它们不会自动成为带计算合同的搭建预设，也不授权模型执行或任意图到源码生成。

## Agent 遇到待解析区域时

1. 使用当前 Skill launcher 的 `doctor` 和 live capabilities 确认运行时，再运行目录发现，读取入口、继承、工厂、构造参数注入、包含关系与未知项。不要 import、实例化模型或执行工厂。缺失源文件、动态配置、规模截断与句法规则缺口应分别报告。
2. 阅读预览的 `adaptationRequests`、对应源码与 AST。请求包含边界 ID、证据、候选本地入口、`source-inspected` / `needs-source-adapter` 状态、截断状态及下一步工作流；`source-inspected` 只说明存在检查结构，不代表其中所有句法已经恢复或计算语义已证明。
3. 先用 `adapter rules` 查看已有模板。若模板适用，在当前完整 corpus 中重新实例化；不能复制另一模型的绑定子图。只有调整现有检查子树的名称与注释时，使用 v1 的 `scaffold → validate → register → preview` 即可。
4. 若缺少合适规则，按下述有限 DSL 编写 JSON。`match` 描述 AST 类型与必要结构；`nodes` 使用真实 AST 字段/列表索引路径；`relations` 仅使用独立解释器支持的证明方式。通用模板应避免绑定特定模型名、文件名或局部变量名；需要匹配真实 API 名或常量时，应说明适用范围。
5. 先 `rule-validate`，再 `scaffold --rules` 在真实源码中匹配并绑定。核对新增节点、包含关系、guard、依赖和覆盖差异。模板结构有效但没有匹配，并不意味着补足了解析；v2 注册至少需要一个实际匹配。
6. 验证正例、改类名/文件名/局部变量名后的迁移例，以及无证据关系的反例。`validate` 必须从源码与嵌入模板独立重建全部事实。`register` 保存验证通过的实例及其模板，之后 `preview` / Studio 重新分析。读取 `sourceRuleApplications`、`ruleDiagnostics` 和 `coverage`，确认规则实际应用且未截断。
7. 在新预览中检查展开/收起、源码定位、拖动、撤销、保存/重开和导出；保留原文档及 history。模板或实例被拒绝时，修正受支持的 pattern/path/proof，或保留具体未知区域。不得手改事实、hash、span、guard 或生成合同来迫使验证通过；不得安装可执行 Python 适配插件。

## 规则 DSL

顶层只允许 `schema`、`name`、`match`、`nodes`、`relations` 和可选 `id`。`rule-validate` 返回规范化模板及其内容 ID `rule-<24 位 SHA-256 前缀>`；若提供 `id`，必须与内容一致。模板不是 JSON Patch、Python 脚本或任意图定义。机器格式见正式项目的 `schemas/source-rule-v1.schema.json` 与 `schemas/source-adapter-v2.schema.json`；原实例格式见 `schemas/source-adapter-v1.schema.json`。

| 字段 | 合同 |
| --- | --- |
| `schema` / `name` | 固定 `archcanvas-source-rule/1`；名称为最多 120 字的纯文本 |
| `match` | `{ "type": "Python AST 类名", "fields": { ... } }`；根必须有源码位置。只能使用该 AST 类型真实存在的字段。字段值可以是嵌套 AST pattern、JSON 原始值或列表；省略字段为 wildcard，声明的列表精确匹配长度 |
| `nodes[].key` | 1–64 字符，以字母开头，后接字母/数字/`_`/`-`；每个 key 唯一 |
| `nodes[].at` | 从匹配根出发的 AST 字段名与非负列表索引数组；最终必须是真实、有行列位置的 AST 节点，路径唯一 |
| `nodes[].parent` | 另一 key 或 `null`；必须恰好有一个 `at: []`、`parent: null` 的根，父路径必须为子路径严格前缀；实例化后再次核对真实 AST 包含关系 |
| `nodes[].kind` | 仅 `SourceExpression`、`SourceCall`、`SourceLoop`、`SourceBranch`、`SourceStatement`；这些是检查视图类别，不是已验证张量算子 |
| `nodes[].label` | 可选的最多 120 字纯文本；省略时从实际源表达式生成 |
| `relations[]` | 仅 `{ "source": "node-key", "target": "node-key", "proof": "..." }`；端点必须存在且不同，不能重复或形成非法依赖环 |

当前关系证明只有两种：

- `expression-input`：producer 必须是 consumer 的直接、可读值操作数。支持调用的位置/关键字值参数及计算型 callable，算术/布尔/比较操作数，可读属性/下标，tuple/list/set/dict 元素，普通赋值/返回/表达式语句的 `.value`，以及受支持的星号与格式化表达式。不能跳过中间表达式，也不能仅凭包含关系、语句相邻、分支排列或 ModuleList 顺序连线；条件表达式、控制流、存储目标和增量更新不由此证明。
- `comprehension-iteration`：producer 必须恰为某个 comprehension generator 的 `iter`，consumer 必须恰为其元素表达式（dict 可为 key/value），且输出在实际词法作用域内读取该 generator 绑定的变量。后续 generator 遮蔽、lambda/嵌套 comprehension 遮蔽、无关输出、海象表达式状态变更不能冒充该关系。此箭头只表示句法上的迭代来源使用，不表示实际次数、张量逐项对应或执行顺序。

解释器保留真实 comprehension 的 `for ... in ...` 与 `if ...` 条件，以及外围 if/else/for/while、短路表达式的源码上下文，不求值、不选分支。guard 字符串保存在 `children[].parameters.guards` 与 `dependencies[].guards`，节点标明 `inspectionAuthority: "syntax only; runtime path and repetition unverified"`。节点类别与 guard 不能把未知控制流升级成运行事实。

## 完整示例：新增 comprehension 结构规则并跨模型复用

先在 `/tmp/archcanvas-rule-demo/source/` 保存下面两个文件。首次 scaffold 前就放入全部文件，避免添加第二个文件使第一个完整 corpus 绑定立即过期。模型只用于静态读取，不需要安装或运行 torch。

`models.py`：

```python
from torch import nn

class Harbor(nn.Module):
    def __init__(self):
        super().__init__()
        self.proj = nn.Linear(4, 4)

    def forward(self, items):
        return [self.proj(item) for item in items if item is not None]
```

`relocated.py`：

```python
from torch import nn

class Prairie(nn.Module):
    def __init__(self):
        super().__init__()
        self.project = nn.Linear(4, 4)

    def forward(self, tokens):
        return [self.project(token) for token in tokens if token is not None]
```

在 `/tmp/archcanvas-rule-demo/listcomp-rule.json` 保存：

```json
{
  "schema": "archcanvas-source-rule/1",
  "name": "Single list comprehension source template",
  "match": {
    "type": "ListComp",
    "fields": {
      "generators": [{"type": "comprehension", "fields": {"is_async": 0}}]
    }
  },
  "nodes": [
    {"key": "comp", "at": [], "parent": null, "kind": "SourceLoop"},
    {"key": "iterable", "at": ["generators", 0, "iter"], "parent": "comp", "kind": "SourceExpression"},
    {"key": "body", "at": ["elt"], "parent": "comp", "kind": "SourceExpression"}
  ],
  "relations": [
    {"source": "iterable", "target": "body", "proof": "comprehension-iteration"}
  ]
}
```

此 pattern 精确限制一个非 async generator，其他字段未约束。`at: []` 选中 ListComp，`generators/0/iter` 选中真实 iterable，`elt` 选中真实输出表达式。筛选条件保持源码原文。变量名、类名、文件名和子模块名均未写死。

从正式项目根目录运行；registry 放在 source root 之外：

```bash
export PYTHONPATH="$PWD/src"
python3 -B -m archcanvas_cli doctor
python3 -B -m archcanvas_cli discover --root /tmp/archcanvas-rule-demo/source --output /tmp/archcanvas-rule-demo/models.json
python3 -B -m archcanvas_cli adapter rule-validate --rule /tmp/archcanvas-rule-demo/listcomp-rule.json --output /tmp/archcanvas-rule-demo/checked-rule.json
python3 -B -m archcanvas_cli adapter scaffold --root /tmp/archcanvas-rule-demo/source --entry models:Harbor --rules /tmp/archcanvas-rule-demo/listcomp-rule.json --output /tmp/archcanvas-rule-demo/harbor.json
python3 -B -m archcanvas_cli adapter validate --root /tmp/archcanvas-rule-demo/source --definition /tmp/archcanvas-rule-demo/harbor.json
python3 -B -m archcanvas_cli adapter register --root /tmp/archcanvas-rule-demo/source --definition /tmp/archcanvas-rule-demo/harbor.json --registry /tmp/archcanvas-rule-demo/registry
python3 -B -m archcanvas_cli adapter rules --registry /tmp/archcanvas-rule-demo/registry
python3 -B -m archcanvas_cli adapter scaffold --root /tmp/archcanvas-rule-demo/source --entry relocated:Prairie --registry /tmp/archcanvas-rule-demo/registry --output /tmp/archcanvas-rule-demo/prairie.json
python3 -B -m archcanvas_cli adapter validate --root /tmp/archcanvas-rule-demo/source --definition /tmp/archcanvas-rule-demo/prairie.json
python3 -B -m archcanvas_cli adapter preview --root /tmp/archcanvas-rule-demo/source --entry relocated:Prairie --registry /tmp/archcanvas-rule-demo/registry --output /tmp/archcanvas-rule-demo/preview.json
```

两份绑定实例应使用同一个 rule ID，分别绑定真实入口、源位置和参数；每份包含一个匹配、三个检查节点和一条已证明依赖。预览通过 registry 自动对新入口实例化模板，无需先注册 Prairie 的绑定实例。检查预览的实际规则应用收据，而非仅检查 registry 中存在模板。

在另一个 source root 中把返回表达式改成 `[self.bias for token in tokens if token is not None]` 作为反例：同一模板可匹配 ListComp，但 output 不读取 generator 的绑定变量，scaffold 必须拒绝 `comprehension-iteration`。错误 selector、非法 parent、假 hash/span、伪造 generation contract 也必须拒绝。不能删除 proof 校验来使反例通过；若用途只是展示无依赖的源码包含，可明确移除该关系后重新验证其较弱含义。

`--rules` 接受单个模板对象或模板数组；`scaffold --registry PATH` 读取已保存模板并产生 v2 实例。两项同时使用会按验证后的 rule ID 合并并去重；单份实例最多包含 16 个不同模板。更大的模板库可分批 scaffold，preview 会逐模板独立验证和应用。两项均不提供时仍产生 v1；不要将 v1 的旧检查事实缓存误称为新句法规则。`--config FILE` 适用于 scaffold/preview，配置是最多 32 KB 的 JSON 对象，属于绑定身份；`scaffold --method METHOD` 可显式选择本地方法。

类入口按本地 Python C3 查找，优先自写 `__call__`，否则 `forward`，包括可解析的继承方法。顶层本地 helper 可用 `module:function` 独立 scaffold；preview 的主入口仍为可分析的模型类，helper 规则通过该模型的相应待解析调用应用。 自动重新绑定每轮最多扫描 16 个本地入口，并使用各入口的默认 callable；超限会记录截断诊断。模板本身不保存方法选择策略，迁移到另一模型的非默认方法时，Agent 需要再次指定 `scaffold --method METHOD` 并注册该绑定实例。

## 绑定实例、存储与失效

v1 的 `generatorRevision` 为 `source-inspection/2`，v2 为 `source-rules/1`。两者均记录完整相对文件集合与 SHA-256、精确入口/方法、符号与方法 AST 行列和原文、方法 hash、config、源码参数与独立 return 槽、真实 children/dependencies、`generationContract: null` 与纯展示 `presentation`。返回槽是源码槽位，不代表运行时张量接口。v2 另含规范化 `rules` 和 `applications`，后者记录 `ruleId`、`matchKey`、真实 `source`、`rootId`、`nodeIds`。适配实例的检查节点 `sourceStructure: true`、`ports: []`，关系均为语法证据。

实例校验从完整当前源码与嵌入模板重新构建并逐项比较；只允许修改已有 child ID 的 `presentation.labels` 和纯文本 `presentation.notes`。未知字段、无位置 AST、假证据、未知端点、非法包含/依赖环、插件字段或生成授权均拒绝。JSON Schema 仅检查数据形状，不能替代独立重建验证。

Registry 保存 `adapter-<digest>.json`，v2 注册同时保存 `rules/rule-<digest>.json`。规则模板独立于 source root，可跨模型复用；绑定实例不可跨 corpus 使用。文件内容、文件集合、入口/方法、配置或解释器版本变化后，应重新 scaffold、核对和注册。旧实例显式为 `stale`，不会错绑当前源码；模板仍可对当前源码重新匹配并生成新实例。坏 JSON、超限记录与符号链接不能当作有效记录加载。

预览与 managed-project preview 自动读取服务 registry、对当前 corpus 重新实例化可用模板。只有能定位到相应 opaque 区域的真实匹配才接入视图；找不到区域或某模板证明失败时记录诊断，保留原图。规则可复用精确匹配的已有检查卡，避免重复追加；原 opaque 节点及原始计算绑定仍保留。添加或注册模板不会回写旧 CanvasDocument 的 immutable IR；需要新分析/新文档，原布局与 history 应保留。

预算：源码最多 80 文件/2 MB；单模板最多 64 KB、1–64 nodes、128 relations、pattern 深度 12/512 items、selector 深度 16；单实例最多 16 模板、扫描 100000 个 AST 节点、480 matches/480 children/1440 relations、2 MB JSON。接入预览还受 480 总节点、3600 总边和 12 层包含预算约束。达到预算应暴露诊断/截断，不能宣称完整恢复。

## HTTP 与 Skill 调用

先读取同一服务 `GET /api/session`，请求携带 `X-ArchCanvas-Session`。HTTP 以相对路径 `files: {"relative.py": "source text"}` 接收源码，不接受任意磁盘 root。Registry 固定在服务 `data-dir/adapters`；模板在其 `rules/` 下。

| POST 接口 | 请求字段 / 返回 |
| --- | --- |
| `/api/adapters/rule-validate` | `{ "rule": 模板对象 }`；返回规范化模板及 ID，不需要 files |
| `/api/adapters/rules` | `{}`；返回 `{id,path,status:"valid",definition}` 或 `{id,path,status:"invalid",message}` 的数组，不需要 files |
| `/api/adapters/scaffold` | 必需 `files`, `entry`；可选 `method`, `config`, `rules`（单模板或数组）, `useRegistryRules`（布尔，默认 false）；返回 v1 或 v2 实例 |
| `/api/adapters/validate` | `files`, `definition`；返回重建验证后的实例 |
| `/api/adapters/register` | `files`, `definition`；返回注册收据；v2 同时保存模板，至少需要一个应用匹配 |
| `/api/adapters/list` | `files`；返回已保存实例的 valid/stale/invalid 等状态 |

预览用 `/api/preview/analyze` 的 `files`, `entry`, 可选 `config`；managed project 用 `/api/projects/{id}/preview`。它们自动使用本服务 registry；`useRegistryRules` 是 scaffold 的选项。CLI `adapter rules` 与 `rule-validate` 同样不需要 `--root`。

从源码树 Skill 目录运行时，用 `python3 -I -B scripts/archcanvas_runtime.py` 替换上述 `python3 -B -m archcanvas_cli`，先用同一 launcher 的 `doctor` 核对绑定。源码树的实现、已安装 Skill 与冻结 release 各自独立；开发树修改不会自动升级已安装的 beta.12。先检查实际 capabilities 中的 `sourceAdapters.agentRules`，不能根据本文件假定任意安装版本都支持新接口。

## 源码生成边界与验收证据

所有规则实例的 `generationContract` 固定 `null`。检查节点、候选分支、guard 和源码依赖不证明实际执行、tensor 端口、shape、dtype、广播或数值等价。模板不能恢复未提供的外部库实现；解释器尚无的证明类型应保留未知，并通过正式解释器开发与正反例扩展合同。

未修改拓扑的源码导入模型可使用独立的源码保留生成流程，复制原始 corpus 并重新分析；有精确 literal 来源和正式算子合同的参数才允许受支持修改。插入、删除、重接未证明计算语义的对象仍保留为草稿或源码修改提案，不能因视图规则验证成功而宣称任意 roundtrip 已支持。

每次新增模板应保存：规范化模板与 ID、正例和迁移例源码/绑定收据、反例拒绝原因、前后覆盖差异、实际规则应用/截断诊断，以及新预览的交互与保存导出记录。`act` 等真实项目演示应与通用无预设名称的正反例一起报告；不能只凭一个模型打开成功或旧 v1 测试宣称新 DSL 完整通过。
