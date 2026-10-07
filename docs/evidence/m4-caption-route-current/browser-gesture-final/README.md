# 当前浏览器的离散手势与保存独立核对

此目录独立只读核对真实 CUA 浏览器观察 04–25 的 JSON 与完整 SVG，**515/515** 关系通过；这些是观察关系，不是额外产品测试、模拟使用者或真人验收。脚本只导入 Python 标准库，没有浏览器输入、模型执行或产品 helper。来源是实际公开 DOM 与已经捕获的 SVG，不将截图哈希当内容证明。

04→08 的相机分别右、下、左、上 **32 px**：所有卡片屏幕矩形严格同方向刚性平移，完整 SVG 几何与 metadata 不变，最后回到原 transform。09–20 的 output projection 分别右、下、左、上 **32 世界单位**：每次只有一个 front card 变化、相机不变；撤销后整个 SVG 场景回到 04，重做后整个 SVG 场景回到编辑状态，实际 visual revisions 持续前进。移动可能合法重新放置派生标签/guide，未要求其坐标冻结。

每份观察的 49 条 source facts 由冻结 static architecture 的 node facts 和 independently counted call instances 对比，document/source/IR identity、canonical source/target/tensor/role 与 rendered edge bindings 保持正确。guide 必须只有一个已存在 tensor edge 归属，metadata decoration 一致，起点实际位于自己的 canonical route，guide 与其父级无 marker 属性，不被算作 tensor binding。

**22 暴露真实体验缺口**：Encoder 下移 **24 世界单位**后，canonical memory edge44、source facts 和 IR 仍在，但 `memory` 文字和 guide 消失，不能宣称所有移动后的标签稳定性通过。该捕获直接证明消失，具体旧 `abs(sourceBox.y-targetBox.y)<15` policy 的根因由另一个独立审查记录。23 撤销恢复整个 04 场景以及 memory 文字和 guide。

24 保存、25 重开后的完整 SVG 几何和 metadata 均一致，visual revision **18**。实际 before/after 存储 envelope 的 counter **1→2**，文档 revision **0→18**，其余字段逐一 exact：architecture、sourceBindingDigest、layout/layoutByFrontier、pins、pageSpec、aliases、styles、annotations 等全部一致。两份 fixture Python 文件与冻结 package 的源码字节相同。存储文档没有 history 字段，不能把浏览器撤销/重做证明延伸为持久化 history 证明。[逐字段摘要与源字节](stored-invariants.json)。

重开相机从 scale **1** 变为 **0.681141**，重新适配视图，未保存原相机。离散输入不能证明连续拖动顺滑、input latency、native denominator、真实 presented FPS 或 300 个对象实际可见。JPEG 与同名 DOM 可能处于不同绘制时刻；本脚本不审看图片、不据文件名宣称同步像素。出版尺寸、字体与真人任务不在本报告范围内。

首次审查错误假定没有 guide 时 metadata 仍有 `presentationDecorations`，在 22 得到 KeyError；原 script/error 完整保留。第二次 **510/510**，第三次加入真实存储快照得到 **515/515**；失败属于审查脚本缺口，不是产品 crash。[最终报告](report.json)、[精确字节清单](manifest.json)。本目录封存后不覆写，后续 publication 修复和新 captures 属于新证据。
