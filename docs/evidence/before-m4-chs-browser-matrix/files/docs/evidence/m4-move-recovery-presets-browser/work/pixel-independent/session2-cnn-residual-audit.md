# 第二轮 CNN 独立像素审核

实际查看 3 组共 6 张原 PNG：inserted、observed-later、generated 各自 primer 与正式图。15 个输入按读取字节绑定 SHA-256；结束复核全部未改变。残差材料另写报告。

| 截图 | 可见像素 | public / before / after 对照 |
|---|---|---|
| inserted primer | 空画布、100%、0 模块 0 连接、重开草稿底栏 | **不同**：公开字段/DOM 已是小型 CNN 8 模块 7 连接/已添加底栏 |
| inserted 正式图 | 40%、8 张卡、7 条连接、Input 检查器、添加 CNN 底栏 | 已知粗状态相符 |
| observed-later primer | 同上述正式图 | 已知粗状态相符 |
| observed-later 正式图 | 同上述正式图 | 已知粗状态相符 |
| generated primer | 已保存 CNN、8 卡 7 连接、无对话框 | public 已知字段相符；**与 DOM 的生成对话框存在状态不同** |
| generated 正式图 | 显示“模型已生成并静态核对”对话框、源码、两个后续按钮 | DOM 对话框粗状态相符；public modal 字段范围未知 |

共有 2 张图与 DOM 的已知状态不同，其中 inserted primer 也与 public 的已知字段不同。3 对 before/after DOM 字节相同。generated public 只有 footer/nodes/status；无 modal 字段不能当作缺少对话框的错误。正式生成截图下的背景模糊并被遮挡，不以它认证八个节点的细节。

40% 下能观察到 CNN 八卡之间连续的横向连接。箭头方向细节、逐端口触点和小型卡片/端口字样未认证可读。生成对话框标题与控件可读，源码有滚动溢出；未核验全部源码正确性、运行结果、性能或实际 presented paint。人工验收仍为 0。

完整绑定与每张实际观察见同名 JSON；未执行浏览器、产品、测试或构建修改。
