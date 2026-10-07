# 当前搭建工件的独立合同回读

[report.json](report.json) 为有界通过，同时保留操作失败。[audit.log](audit.log) 记录具体检查；[audit.py](audit.py) 仅使用标准库 JSON、哈希和 AST，不导入产品、不调用浏览器、不执行生成模型。

输入是本轮 43 帧的 129 份 DOM/public/JPEG 原件，以及额外一份 receipt（manifest 实际为 130 bindings）；另核对两份实际保存草稿、一份新 managed project metadata 和该项目的生成源码。共 142 份选取的文件在回读前后字节稳定，当前 build/package 的选取绑定也匹配。JPEG 在此只核哈希，像素审查由独立报告承担。

具体核对结果：

- 空白起点为 4 节点/3 连接：Input `[1,16]` float32 → Linear `16→32` → GELU `approximate='none'` → Output。保存/重开公开 node 与 route 字段精确相同，生成源码的 constructor、输入、顺序 producer 与 Output key 通过手写 AST 预期。实际 managed 源码逐字等于该 public source；metadata 为新 managed-copy，打开后的 AX 树显示 5 个事实对象/4 条关系。
- 残差起点为 6 节点/6 连接：Input → Linear `16→32` → ReLU → Linear `32→16` → Add → Output；Add left 来自投影、right 来自 Input。保存/重开公开字段精确；public source 与生成弹窗 AX 文本一致且手写 AST 通过。此流没有打开 residual managed project，不能据此补造实际 residual 文件证据。
- Add 四向键盘移动分别为 world ±16；其它节点与非 incident route 保持。route endpoints 对应 Input/Output 和 Add left/right 公开端口位置，四组 undo/redo 与最终 restored 精确恢复捕获的 node/route 字段。
- 相机四向操作的 public translate 分别为 CSS ±40，scale 与模型几何保持；最终返程对基线使用 `1e-9` 的小浮点容差。右向首次返程实际剩余 +30，补偿后实际 +10，直到单独最终恢复才回基线；两次失步保留，未称首次成功。

复核命令从正式工程根执行并使用新输出目录：

```bash
python docs/evidence/m4-native-matching-work/authoring-contract-independent/audit.py \
  --output /tmp/archcanvas-authoring-contract-independent-next
```

node 移动为键盘样本；camera drag 的输入模式来自绑定操作 receipt，本报告只直接验证 public transforms，没有原始 trusted-pointer traces、拖动中间帧或 input-to-paint。`four-managed.public.json` 查询的是 draft selectors，所以其 node/edge 数为空；本审计以实际 managed source/metadata 和 AX 事实核对，没有声称捕获 managed scene 几何。当前状态为 automation、真人 0，不认证全部 17 模块流程、像素同步、箭头美观、出版尺寸、实际 paint/FPS、数值等价或 M4 完成。busy/check 过渡、初次剪裁卡片 drag 无变与两次相机失败均沿用原件。
