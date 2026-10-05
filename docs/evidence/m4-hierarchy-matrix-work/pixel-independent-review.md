# Hierarchy 最终矩阵独立像素观察

复核时间：`2026-10-05T01:07:23.235596+00:00`。独立 AI 观察者逐张使用 `view_image(detail=original)` 实看 39 张最终 JPEG（36 baseline＋3 edited），另看 3 张 excluded；全部最终图为 **1102×905**，每张截图 SHA256 在观察前、观察后与最终复读保持一致。没有操作浏览器、修改 case、stamp/collect 或修改产品。

逐张事实与完整字节绑定见 [JSON](pixel-independent-review.json)，SHA256 `1add264f908aaffbd052ff44f88196f769f682bd8c8f75cec368ca8453641108`。关联 spec SHA256 `5a9e62a5448b273235b5345ac44ad231efacd0870ab828a386a7360f9b7e2354`；36 baseline variantId 集合精确等于 spec。这个集合比较只说明截图条目的配置覆盖，不替代 Canvas/DOM/导出工件校验。

39 张可见模型标题、展开轮廓、页头 PAPER COLOR/MONOCHROME、85/180 mm 与右侧 active page controls 均相符；均无 modal，整纸、图、图例位于 viewport。部分图的缩放控件轻微叠在右下空白纸边，没有遮挡可见图或图例内容。

Transformer L1 36%、L2 26%、L3 20% 和 CNN L2 25% fit 的文字/端点/图例词无法可靠逐项读；轮廓可见不认证完整 canonical 标签或连接正确性。其他图的主要标签可读，小字幕仍有限。窗口 fit 画面不等于校准的 85/180 mm 印样，也不能证明字体环境已锁定。

三份最终 edited 的说明分别为 “Presentation edits preserve model facts.”、“Memory enters decoder cross attention.” 和 “Each block retains its skip path.”；说明与图例均可见，CNN 最终说明紧随图例。截图本身不证明 undo/redo、保存或重开链。

| Case | SHA256 | px / fit | 可见观察 |
|---|---|---|---|
| mlp-level0-monochrome-180 | `db1c8c26b03e4673b8b6d3f384ef2c6c1fee734ad6e669950276468aec2cdcf6` | 1102×905 / 97% | MLP；180 mm · MONOCHROME；控件相符/全纸图例/无 modal；主要标签可读 |
| mlp-level0-monochrome-85 | `735f9f89ae22d8091e8dcf11df43df1d84b1f70fd71ffe3d0eb2c9747bec67c7` | 1102×905 / 97% | MLP；85 mm · MONOCHROME；控件相符/全纸图例/无 modal；主要标签可读 |
| mlp-level0-paper-180 | `ffeeeca40190b82762a3816406df6c16f1aacdd96701cbf6a4e6619111e0f963` | 1102×905 / 97% | MLP；180 mm · PAPER COLOR；控件相符/全纸图例/无 modal；主要标签可读 |
| mlp-level0-paper-85 | `bcaf3dcb23c1fe86821ab3b2caf55fb6ad79d3e46e0c8d84afd7b2b0f5a60875` | 1102×905 / 97% | MLP；85 mm · PAPER COLOR；控件相符/全纸图例/无 modal；主要标签可读 |
| mlp-level1-monochrome-180 | `f470f3918ef214a5e3a40f155b59356a1a03a3f5f631da7d9c1884f904070197` | 1102×905 / 66% | MLP；180 mm · MONOCHROME；控件相符/全纸图例/无 modal；主要标签可读 |
| mlp-level1-monochrome-85 | `432285617e1eab64aa2b40c8cf99c111d47716d0d22ba2a8a3a6fb8465e21307` | 1102×905 / 66% | MLP；85 mm · MONOCHROME；控件相符/全纸图例/无 modal；主要标签可读 |
| mlp-level1-paper-180 | `a82cb44e0c308ebcd2da26a043dc4650cb0cdb5cfd60088074591b357bcac43f` | 1102×905 / 66% | MLP；180 mm · PAPER COLOR；控件相符/全纸图例/无 modal；主要标签可读 |
| mlp-level1-paper-180-edited-reopened | `fced987a95226ae89df1a18ea7f1c5c6b89552b9995cfd8f8f3879a8b51b19ab` | 1102×905 / 62% | MLP；180 mm · PAPER COLOR；控件相符/全纸图例/无 modal；主要标签可读；说明可见 |
| mlp-level1-paper-85 | `c3dfe6723dfe3997f1900f74370e60a73482e7aa36c25ade29fedd8c8d260b49` | 1102×905 / 66% | MLP；85 mm · PAPER COLOR；控件相符/全纸图例/无 modal；主要标签可读 |
| residual_cnn-level0-monochrome-180 | `a3358357f8811282f1e118236dfdf0d43f7a602179421a33904943750672c042` | 1102×905 / 65% | ResidualCNN；180 mm · MONOCHROME；控件相符/全纸图例/无 modal；主要标签可读 |
| residual_cnn-level0-monochrome-85 | `817914cd2161312b3fea645541ee4823c1dd4c94efbdb92c494d829d70e94508` | 1102×905 / 65% | ResidualCNN；85 mm · MONOCHROME；控件相符/全纸图例/无 modal；主要标签可读 |
| residual_cnn-level0-paper-180 | `dece346c6f71367588e72c15210eda5102de172d32ae9a02729df880250192e0` | 1102×905 / 65% | ResidualCNN；180 mm · PAPER COLOR；控件相符/全纸图例/无 modal；主要标签可读 |
| residual_cnn-level0-paper-180-edited-repositioned-reopened | `8a024aba7dcf3a38e0c5e63543c8a3594513e8dfddbfcc6bd57d653de12495fa` | 1102×905 / 61% | ResidualCNN；180 mm · PAPER COLOR；控件相符/全纸图例/无 modal；主要标签可读；说明可见 |
| residual_cnn-level0-paper-85 | `e346c3642f4dbdc6ff14843e741d12f908c49e4410c51d6c8269b0ffe692ca92` | 1102×905 / 65% | ResidualCNN；85 mm · PAPER COLOR；控件相符/全纸图例/无 modal；主要标签可读 |
| residual_cnn-level1-monochrome-180 | `8875c679ad57217657b7eb5b60154689a0bf87944fa5d13dfae6956399981102` | 1102×905 / 54% | ResidualCNN；180 mm · MONOCHROME；控件相符/全纸图例/无 modal；主要标签可读 |
| residual_cnn-level1-monochrome-85 | `b300ffacd094b454c63a9ecfde325f2855933cdd7133729718df08de8c1bb12e` | 1102×905 / 54% | ResidualCNN；85 mm · MONOCHROME；控件相符/全纸图例/无 modal；主要标签可读 |
| residual_cnn-level1-paper-180 | `69c328306a73f1f404f4959f9ab68203dcb4c3fcbd7b5a934c2ed0df10ee7647` | 1102×905 / 54% | ResidualCNN；180 mm · PAPER COLOR；控件相符/全纸图例/无 modal；主要标签可读 |
| residual_cnn-level1-paper-85 | `474ad91632ad6a5d0e42ed352a6003b744996f98e51b6fdc4e47beb5934ab63f` | 1102×905 / 54% | ResidualCNN；85 mm · PAPER COLOR；控件相符/全纸图例/无 modal；主要标签可读 |
| residual_cnn-level2-monochrome-180 | `29d94212e664786fd654c81f52dffd6c7e9f9959b08b02134b33e294c84262f9` | 1102×905 / 25% | ResidualCNN；180 mm · MONOCHROME；控件相符/全纸图例/无 modal；逐字/端点不可可靠读 |
| residual_cnn-level2-monochrome-85 | `13945f386d916c4a4ce19546137e0f75b4814dc229b0a321525312e554ea9cc2` | 1102×905 / 25% | ResidualCNN；85 mm · MONOCHROME；控件相符/全纸图例/无 modal；逐字/端点不可可靠读 |
| residual_cnn-level2-paper-180 | `b6b0f197ce3bfeaab772fc2433ca25e231b4be484c45866abbd151cb961bbf92` | 1102×905 / 25% | ResidualCNN；180 mm · PAPER COLOR；控件相符/全纸图例/无 modal；逐字/端点不可可靠读 |
| residual_cnn-level2-paper-85 | `dcc6d369cc65434371ef282219c5b96a54ed012c149ab8d126d1b529d7bfe69a` | 1102×905 / 25% | ResidualCNN；85 mm · PAPER COLOR；控件相符/全纸图例/无 modal；逐字/端点不可可靠读 |
| transformer-level0-monochrome-180 | `6c71639bfbe7b5acd6117ead01af469992515b6a60cd846f4cdcdb9646ce09ea` | 1102×905 / 77% | Transformer；180 mm · MONOCHROME；控件相符/全纸图例/无 modal；主要标签可读 |
| transformer-level0-monochrome-85 | `8a2664d11247eb3aac210711b528376895ad9d70522a4b4f2759cf2b9df06de0` | 1102×905 / 77% | Transformer；85 mm · MONOCHROME；控件相符/全纸图例/无 modal；主要标签可读 |
| transformer-level0-paper-180 | `02b00176bac03f6e6acde39c954e9e9aed8b1c737f2b76ed6c65bc645b19fe84` | 1102×905 / 77% | Transformer；180 mm · PAPER COLOR；控件相符/全纸图例/无 modal；主要标签可读 |
| transformer-level0-paper-180-edited-reopened | `3c8c7698c64fb321f5b126013e1c85745760669e58af774b6fa4f86a89df2ff9` | 1102×905 / 72% | Transformer；180 mm · PAPER COLOR；控件相符/全纸图例/无 modal；主要标签可读；说明可见 |
| transformer-level0-paper-85 | `d2e8b8f092bddef2f018c1eeaace890102a5db9576b392280373804559bdfc68` | 1102×905 / 77% | Transformer；85 mm · PAPER COLOR；控件相符/全纸图例/无 modal；主要标签可读 |
| transformer-level1-monochrome-180 | `a4557c7a57ccb785944b8730159cc1a2229f4206c5cafa7a24eb148b465ec32d` | 1102×905 / 36% | Transformer；180 mm · MONOCHROME；控件相符/全纸图例/无 modal；逐字/端点不可可靠读 |
| transformer-level1-monochrome-85 | `fdb941d756b903e8c9f682f02df350844782fc01b83c5d79301337938979a227` | 1102×905 / 36% | Transformer；85 mm · MONOCHROME；控件相符/全纸图例/无 modal；逐字/端点不可可靠读 |
| transformer-level1-paper-180 | `88b4cb45b087d7d6636225be2967c5d26a71f48aa873c460ea300fbbc998e7b5` | 1102×905 / 36% | Transformer；180 mm · PAPER COLOR；控件相符/全纸图例/无 modal；逐字/端点不可可靠读 |
| transformer-level1-paper-85 | `51c151415aeefbdf401e64a49351191cea831c0dfab3de2b48cc3cff2c9ca9b8` | 1102×905 / 36% | Transformer；85 mm · PAPER COLOR；控件相符/全纸图例/无 modal；逐字/端点不可可靠读 |
| transformer-level2-monochrome-180 | `19470e683524e293a2a3534b5a8b01d8032465cd0da538ceb12fc5d694b1de42` | 1102×905 / 26% | Transformer；180 mm · MONOCHROME；控件相符/全纸图例/无 modal；逐字/端点不可可靠读 |
| transformer-level2-monochrome-85 | `88a62271034f0ce5c5f30ad6425026870ac1858d3563db7171bd1b0ce8c38e79` | 1102×905 / 26% | Transformer；85 mm · MONOCHROME；控件相符/全纸图例/无 modal；逐字/端点不可可靠读 |
| transformer-level2-paper-180 | `5f4b86766151698f8169fff43adbe7e1862d505457e1f30c20fe18070a6bb8ec` | 1102×905 / 26% | Transformer；180 mm · PAPER COLOR；控件相符/全纸图例/无 modal；逐字/端点不可可靠读 |
| transformer-level2-paper-85 | `7323d899329dbcb0a9a3c6db20e640df976d39426f8b62d012b7457f182fc128` | 1102×905 / 26% | Transformer；85 mm · PAPER COLOR；控件相符/全纸图例/无 modal；逐字/端点不可可靠读 |
| transformer-level3-monochrome-180 | `e8550febfbb62b0dd8333608dffb994b163c0d933596b70b79ebb037a544d957` | 1102×905 / 20% | Transformer；180 mm · MONOCHROME；控件相符/全纸图例/无 modal；逐字/端点不可可靠读 |
| transformer-level3-monochrome-85 | `252a68d0da6954637e3a8fcd77ff72148e276aba70bfc181e007fc901ca2a1b9` | 1102×905 / 20% | Transformer；85 mm · MONOCHROME；控件相符/全纸图例/无 modal；逐字/端点不可可靠读 |
| transformer-level3-paper-180 | `b6d7ad28b9877b8cc6052fe500eda146dd20e6d20d8816b49d86f5389bb01450` | 1102×905 / 20% | Transformer；180 mm · PAPER COLOR；控件相符/全纸图例/无 modal；逐字/端点不可可靠读 |
| transformer-level3-paper-85 | `e8866a6c2d24265beb8e6aec7b1429d833683248141c967e4164a9d03890ea41` | 1102×905 / 20% | Transformer；85 mm · PAPER COLOR；控件相符/全纸图例/无 modal；逐字/端点不可可靠读 |

excluded 三张不计覆盖。CNN 首次 edited 图为 24% fit，图/图例在上方、说明在页底，中间出现大段空白；最终独立审看的新 case 为 61% fit，说明已紧随图例。两张 Transformer excluded 的画面本身无模型/页宽/预设冲突；stale export 和 local asset path 属工件事实，不能从像素单独判定。85 mm excluded 截图与最终同配置截图字节相等，不额外计覆盖。

本报告保留 `visualAcceptance=pending-human-review` 与 `humanAcceptanceCertified=false`。不填写六维审美分、不认证字体/真实印样、性能或人类研究者任务；精确源码/IR/Canvas/导出一致性由独立字段与 collector 校验提供。
