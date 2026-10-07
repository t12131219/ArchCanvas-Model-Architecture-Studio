# 独立 AI 像素审查

本轮亲看 19 张原始 JPEG：18 张指定当前视图，以及此前已发现不同步的 `four-added`。原采集有 43 帧；本报告不认证其他 24 张未亲看的原图。AI 审查增加的真人人数为 0。未操作浏览器、执行模型、运行产品测试或修改产品代码。

19 张记录中，11 张在观察范围内与 DOM/public 一致，1 张 managed 视图只能与 DOM 作有限核对，7 张存在原图不同步，均保留：

- `four-added`：原图仍为添加 GELU，记录已是添加 Output。
- `preset-palette`：原图仍选基础模块，DOM 已选网络起点。
- `residual-search`：原图搜索框为空，显示未过滤的起点；DOM 已过滤“残差”。
- `residual-node-up`、`residual-node-down`：原图 Add 及右栏 Y 仍为 172，记录分别为 156、188。
- `residual-port-tooltip`：DOM 有 right 输入端口的提示框，原图未见提示框。
- `residual-final-preview`：图形及保存状态一致，但原图仍有“残差”搜索及选择模式；DOM 已清空搜索并切换平移。

四模块完成及重开视图的三条直箭头未见多余弯折或交叉，生成源码对话框清楚标注静态核对及未执行模型。Managed 视图可见完整论文页、标题和图例；authoring public 选择器没有覆盖 managed scene，其空 nodes/edges 不能解释成产品空图，也不能用来认证 managed 几何完全一致。

残差 MLP 总览中的完整输入跳连绕过中间操作进入 Add，未见自由空间交叉或卡片内穿线。100% 局部能分开两个 Add 输入及箭头，但输入和输出位于视口外，不能仅用局部图认证整条跳连。53% 总览下两个输入仅相距约 6.365 CSS px，标签紧密，两个 Linear 标题截断，普通分支及残差使用同样的绿色。此处仍有小白用户辨识及准确点击风险。输入主链和跳连共享首段 6 world units；没有“全部连线无重叠”或“全局最美路径”的认证。

公开 JSON 独立核对了 Add 四向键盘移动 16 world units、每次撤销恢复基线和重做恢复移动状态，以及相机四向相对基线平移 40 CSS px。左右 Add 原图同步，上下原图未同步，不能宣布四向像素均通过。相机四向原图均亲看；左移切掉 Input 左缘，右移切掉 Output 右缘，剩余图形内部排列保持一致。右向回程的超时和恢复失败仍保留：先剩余 +30 px，再请求 -30 仅送达 -20，剩余 +10；最后独立 -10 恢复。回程原图未由本审查亲看。

输入读回验证 129 份帧文件（43 组 JPEG/DOM/public）全部不变；采集 manifest 另外绑定了 receipt，共 130 份。此前 `final-inputs-before.json` 的键名 `all129RawInputBindingsMatch` 实际遍历了全部 130 项；原文件保持不变，计数解释写入最终读回。

正式文件为 `receipt.json`、`per-image-review.json`、`public-movement-readback.json` 和 `final-readback.json`。这些屏幕和公开状态证据不证明真人任务通过、全部 17 种模块或 3 种预制网络完成流程、物理出版质量、模型执行、性能或后端保存行为。
