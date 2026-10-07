# 第二轮残差 MLP 独立像素审核

实际查看 preset-native-dropped 与 generated 的 primer、正式图，共 4 张原 PNG。10 个输入按读取字节绑定 SHA-256；结束复核全部未改变。本次不继承到后续新截图或新构建。

| 截图 | 可见像素 | public / before / after 对照 |
|---|---|---|
| preset primer | 53%、6 卡 6 连接、Input 检查器、添加残差 MLP 底栏 | 已知粗状态相符 |
| preset 正式图 | 同 primer，PNG 字节也相同 | 已知粗状态相符 |
| generated primer | 53%、6 卡 6 连接、Input 仍选中、草稿已保存底栏、**无生成对话框** | public 底栏不同；DOM 底栏/检查器/对话框不同 |
| generated 正式图 | 53%、6 卡 6 连接、默认检查器、重开草稿底栏、**无生成对话框** | public 已知字段相符；DOM 有生成对话框，仍不同 |

2 张 generated 图都缺少 before/after DOM 明确包含的“生成的新模型”对话框、标题、源码和后续按钮。public 仅有 footer/nodes/status；modal 范围未知，不把缺少字段当错误。2 对 before/after DOM 字节相同。

预设图可见从 Input 经隐藏层、ReLU、投影层、Add 到 Output 的主链；另一路从 Input 输出向下绕过中间三卡，再进入 Add 的第二输入。53% 下可辨认这条跳连形状，未认证逐箭头方向细节、精确端口触点或全部小字可读性。

仅记录证据状态差异，未推断产品原因。未重跑原生拖放、模型运行、测试、构建、性能或 presented paint；人工验收仍为 0。完整绑定与逐图事实见同名 JSON。
