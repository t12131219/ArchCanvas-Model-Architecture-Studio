# 新建模型本轮浏览器与服务文件独立核查

这是一份 AI 工程核查，不是研究使用者或出版审看者的真人记录。审查者未操作 root 的浏览器、未重写原始截图/DOM、未导入或执行生成模型，也未导入产品的渲染器、生成器或路由算法。新检查器只使用 Python 标准库和同目录的独立几何工具；旧封存证据不继承到本轮。

## 新建模型的公开 DOM

`check_v2.py` 读取本轮 **25 份**原始 JSON，验证实际完整 SVG，绑定构建 `index-CIVB6v-J.js`。节点/边概要必须与实际 XML 一致；然后独立核验真实 176×100 模块、端口所有者与方向、可见路径和点击路径、箭头标记、端点、模块重叠、路径穿框、交叉、重合、回头与多余绕行。

- Input → Linear → ReLU → Output 的四个节点和三条连接保持同一身份。
- Linear 左、右、上、下各 ±16 模型坐标的移动通过。只有左移有单独的撤销、重做原始状态；其他三向只认证各移动状态和最后的整体恢复。
- 摄像机四向 ±40 CSS 像素平移和恢复通过，平移未改动图形。第一次左移操作中断后恢复状态仍偏 −15 CSS 像素，这条不完整输入链保留并排除。左向成功范围为第二轮完整记录。
- 保存基线、重开草稿和重启服务后的公开节点几何相同。基线及左右移动没有真实弯折；上下移动的两条受影响连接各有两次真实弯折，保持当前端点下的最短曼哈顿路径。25 份状态均为零模块重叠、零路径穿框、零严格交叉、零线段重合。
- **21 个**故意损坏的反例全部被拒绝，其中 7 个同时修改实际 SVG 与概要，或在输入概要仍一致时破坏端点、穿框、自由空间绕行/回头、增删节点/边，避免只靠“概要不一致”取得通过。

`audit.json` 与 `process-first.txt` 保留第一轮中间结果；最终结果为 `audit-v2.json` 与 `process-v2.txt`。

## 实际服务文件与出版工件

`service_check.py` 校验 root 从实际 UI/API 会话服务目录只读复制的 **11 个文件**。每个副本必须与当前服务原文件逐字节相同，并独立重算长度与 SHA-256；不读取或归档服务签名 key。以下结果单列为服务文件证据，不能称为浏览器隐藏状态或原始 HTTP receipt。

- DraftStore 保存版本为 **2**，内层草稿历史版本为 **19**；两者含义不同。保存稿的 Input 参数是 shape `[1,16]`、dtype `float32`，Linear 参数是 `in_features=16`、`out_features=48`、`bias=true`。
- 独立 AST 检查确认生成代码声明 `nn.Linear(16,48,bias=True,dtype=torch.float32)` 和 `nn.ReLU()`，实际 forward 数据依次通过这两个模块，并以保存稿 Output 的身份返回。新工程 managed project 身份、源码字节摘要、CanvasArchitecture 节点/端口/连接、显示名称、参数与该链一致。
- CanvasStore 保存版本为 **1**，CanvasDocument 内层版本为 **0**。SVG、PDF 的 export document 相同，其 receipt 绑定同一 document/source/IR 标识；源码文件 SHA-256 为 `a912b1e6c0c7a8313170ae6dadac97e411daa1108d9f3e72effce07f15b1ef41`。
- 浏览器 `source-saved-svg.xml` 和 `source-reopened-svg.xml` **逐字节相同**。浏览器论文 SVG 与服务导出 SVG 的实际节点矩形、路径、端口、绑定及元数据一致；二者不是相同字节。浏览器 XML 尺寸为 `180×196.64 mm`，服务 SVG 为 `180×196.63866 mm`。
- 论文图实际有 **4 个弯折**、零严格交叉、零线段重合和零叶节点穿框。Input→Linear 的中心差为 `1.56 SVG unit`，ReLU→Output 的中心差为 `11.88 SVG unit`，各产生两个折点；当前位置下路径为最短，但节点进一步对齐可作为视觉改进。端点序列化的最大坐标偏差为约 `0.04 SVG unit`，没有宣称严格零误差。
- PDF 字节摘要和长度与实际 receipt 一致。直接从 PDF `/MediaBox` 量得页面 `179.99999983333333×196.63866000555555 mm`；仅认证实际页面尺寸与文件绑定，不据此认证渲染效果、字体保真或真人出版审看。
- 服务检查器另有 **17 个**故意损坏的反例，覆盖保存版本、参数/端口、managed project、生成代码数据路径/返回键、同时修改 document 和 export 的源码/参数/端口/显示名称、出版端点/摘要，以及同时更新 PDF digest 的错误物理尺寸。全部被拒绝。

结果为 `service-audit.json` 与 `process-service.txt`。

## 重放与边界

两条命令最终均以 exit 0 完成：

```bash
./.venv/bin/python docs/evidence/m4-authoring-next/browser-audit/check_v2.py
./.venv/bin/python docs/evidence/m4-authoring-next/browser-audit/service_check.py
```

原始 DraftStore 保存版本 1 的字节未保留，因此不独立认证其参数。生成预览有公开 DOM，实际 HTTP 生成 response/receipt 未捕获，因此不认证浏览器原始生成 receipt 或 correspondence digest。source/IR digest 字段在工件之间一致，但本检查器只独立重算单个源码 SHA-256，未重算产品的 source bundle/IR digest 算法。参数是静态声明；未运行模型、训练或推理。原始 JSON 不构成完整可信输入事件日志，故不推断所有按键时序、持续按住中断、FPS、INP、视口可见性或真人易用性。真人研究参与和出版审看记录仍为 0。

本目录最终文件由 `manifest.json` 绑定；完成后应由 root 纳入本轮总封存，原始失败记录不可用成功状态替换。
