# AI 代理探索：移动、平移、缩放与适合画布

这是独立 AI 探索记录，不是真人研究使用者或出版审看记录。仅操作独立服务 `http://127.0.0.1:8937/`，正式 `.venv`、`PYTHONPATH=src`，数据目录 `.archcanvas/m4-proxy-exploration/movement`。没有操作 8765/8916/8917、真人席位或旧工程；没有安装依赖、执行模型或修改产品源。浏览器 2、tab 1（子 Agent 视角），服务 session 74765。普通 sandbox bind 失败的原始 `service.log` 保留；允许的本地主机启动记录另存 `service-permitted-host.log`。

实际 viewport 始终为 1280×720。没有修改共享 viewport。它与主 Agent 1102×835 或 1102×905 的观察不同，不能合并为一次尺寸试验。当前 build、关键产品源、示例源 hash 见 `dom-audit.json`；实际 script src 同时记录在每份公共 DOM JSON 中。

## 结果

| 操作 | 实际结果及证据 |
| --- | --- |
| 选择 source embedding | 画布 SVG 点选成功；右侧显示名称、X=80、Y=310、源码只读事实出现。 |
| 上移 | 真实指针屏幕 (529.423,344.615)→(529.423,320.615)，-24px；zoom 0.538462 后按 4 world 单位取整，实际 Y=266，-44 world。节点与 source_tokens 重叠，UI 明确显示重叠和连线缺少畅通路径警告。图不美观，不能计为 tidy 通过。 |
| 下移 | 同一原点→(529.423,356.615)，+12px，实际 Y=334，+24 world；端点跟随，无该样本重叠警告，间距缩小。 |
| 左移 | 同一原点→(505.423,344.615)，-24px，实际 X=36，-44 world；端点跟随，离开原父框内侧边界，视觉不再齐列。 |
| 右移 | 同一原点→(553.423,344.615)，+24px，实际 X=124，+44 world；与 target embedding 重叠，UI 显示重叠警告，不能计为 tidy 通过。 |
| undo/redo | 每个方向后独立撤销，公共 SVG nodes/edges/ports 几何逐字恢复基线；上移还真实重做，几何逐字恢复上移场景。画布 revision 递增。 |
| 四向平移 | 平移工具真实拖动 (850,410) 至上下左右各40屏幕px。纸张对应 y121/161、x394.115/434.115，往返恢复；所有节点/端口/边公共几何逐字不变，revision 保持10。 |
| 小/大缩放 | 三次缩小为31%，百分比按钮重置100%，三次放大173%；公共几何不变。大倍率局部可读但完整图超出viewport是缩放预期，不是 fit 裁切证据。按钮放大锚点在纸张左上方，选择对象不会自动维持在视口中间。 |
| 概览fit | UI54%，纸张 x434.115..808.885,y161..595，canvas x230..1013,y115..641；整纸完整。 |
| 全展开fit | 编码器两层、解码器及三份FFN全部通过树按钮展开，49 nodes/59 edges/106 ports、rev17。UI15%，实际 scale0.146325；整纸 x551.849..691.151,y161..595 完整。 |
| 保存 | rev17保存成功，后续相机操作没有增加文档revision。未进行重开验证，因此不声称本角色独立认证 save/reopen。 |
| 聚焦 | 15%聚焦只平移不会放大，长图随后超出视口；100%聚焦给出可读局部。再次fit恢复完整纸张。 |

4个移动均只改变与该节点相关的 edge:5/6/13；稳定 node/edge/port IDs、SVG sourceDigest、irDigest、sourceFacts 不变。几何审计脚本仅离线读取捕获的公共 SVG，并非用 API 代替 UI。`dom-audit.txt` 是脚本真实退出0输出。

## 视觉审看与开放问题

实际查看了全部15张保存截图：概览、四向节点移动、四向平移、小/大缩放、展开fit、15%聚焦、100%聚焦、再次fit。上移/右移主动碰撞留下警告和不美观布局；软件未自动重新排布全部节点。左移失去齐列并接近容器边缘，也不能称自动维持出版布局。下移/平移/缩放未观察到本样本箭头脱离或随机图元错位，但概览仍有多条长 mask/残差/记忆线，不能据此声称无不必要交叉或弯折。

全展开15%图完整但文字很小，整体截图只能审看宏观布局。100%局部截图显示 top mask 走线仍密集，绕线路径仍可改进。本角色没有认证全局零交叉、出版物理尺寸、真实用户理解能力、FPS 或性能验收。

100%聚焦时公共 DOM 观察到 `.canvas-viewport` 在 `overflow:hidden` 下 `scrollTop=121`，纸张实际位置相比 camera transform 另含该偏移；再次fit后 `scrollTop=0`。Playwright locator click 可能因自动把 SVG目标/侧栏按钮滚入视口而改变隐藏容器滚动，本角色没有用纯坐标复现以分离来源，因此只保留观察，不能直接认定产品 bug。`final-scroll-css.json` 为修复前只读CSS/滚动状态。产品 CSS `.canvas-viewport` 为 overflow:hidden、纸张 absolute，App.fit按当次viewport bounds计算，没有发现窗口变化后自动保持fit的 resize绑定。主Agent曾在另一窗口尺寸记录的底部裁切应继续保留原始记录；本1280×720样本未重现。

原始操作失败也保留在journal：AX把工具显示为checkbox而实际DOM为button，首次checkbox locator未命中；首次FFN ancestor筛选同时匹配外层树行，严格匹配拒绝点击。后续依据刷新DOM用button/精确树行成功操作，这些定位失败不视为产品错误。

`journal.json` 是操作和真实尺寸记录。各 `*.json` 保留公共交互SVG、screen bounds、inline camera style、revision文本；`*.ax.txt` 保留AX状态。所有原始文件由最终 manifest 绑定。未来修改 build 应保留本记录为历史，不改写其结果。
