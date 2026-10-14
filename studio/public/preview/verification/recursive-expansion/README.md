# 递归展开回归修复

修复范围是 `prototype/Summary_Merge`。`Summary_Merge（复件）`只用于只读对照，未生成或写入其中任何文件。

## 修复

- 混合展开前沿必须一起选择图元及其所属文字。标题、变量名、说明行从该图元的原始视图恢复，使用稳定文字 ID、原始位置和尺寸计算跟随位移；伸长的容器还保留右对齐和底部对齐。
- 连线路径的平移基准使用实际原始端点，完成端口分配后再次绑定终点；不同 concat 操作数不能因复用一个概览箭头而共用输入槽。
- 边界入口按张量身份分配，避免不同张量被对齐到同一个嵌套入口。接口所属模块、方向、顺序和源码绑定继续接受验证。
- 可折叠模块的物理端口可在其矩形周边选择合法位置，容器边界及真实模型字段仍受约束。共享张量按同一批次布线；无效的旧路径不再提前占据同批分支的通道。
- 路由搜索在途经点之间延续进入方向，禁止在分支点或接口立即回走；画布边缘限制短引线长度，容器外侧的已有绕线提供平行候选通道。
- 不同导出视图中的同名 junction 可能属于不同模块。位置模板必须同时匹配节点 ID 和所属模块，分支点不参与模块间距扩张。
- 分支点依据源码中相邻模块的实际输入/输出接口重新定位，随模块尺寸和同级位置调整；只能在所属框的空闲通道中安置，避开模块、说明文字和其他分支点。零尺寸分支点允许四侧接入，保留输入、输出和不同张量的独立通道。
- 交互提交使用统一 `validateView`，同时验证源码、单条路径、同级模块重叠和跨张量共线覆盖。后台 worker、兼容模式、实时模式和回退执行共享这条规则；非法展开或移动恢复到操作前的图。
- 旧递归草稿升级到显示投影版本 5，保留展开树、局部位置、编辑和文字锚点。递归展开仍在后台 worker 中布线，图构建函数不启动昂贵搜索。

## 验证证据

最终通用回归 **69/69 通过**（`tests.log` / `test-summary.json`）；包含文字归属与跟随、Memory、分支合并、端口方向、边框避让、两种拖动模式、递归展开/收起/持久化和图级碰撞拒绝。`catalog-check.json` 的 **114 个活动案例、339 状态全部通过**，包括源码、单边与图级布局检查。

`catalog-check.json`记录所有活动模型的初始、单分支和完全展开状态。`branch-check-0.json`至`branch-check-3.json`分别记录逐模块深层展开检查；跨连线共线重叠和同级节点重叠由图级检查器检测，单边校验同时检查端口、边界顺序、字形说明和源码来源。

`repaired-branches.json`记录此前深层扫描发现的 27 个失败状态，最新复验全部通过。`final-differential.json`对中间修订前后的 799 个深层投影进行比较，筛出 378 个几何或路由契约变化状态；这 378 状态使用最终路由规则复验，源码、单边几何和跨张量共线覆盖均为 0 失败。其余 421 个未变化状态未在最终修订中重新布线，因此这里不声称最终版全量 799 状态重跑通过。历史 `branch-check-*.json`保留的是中间修订的发现记录，不能当作最终版全量通过报告。`readonly-reference.json`记录复件目录的 SHA256 核对。`ir-reference-check.json`核对 665 个图的 IR 摘要，与复件一致。`code-hashes.json`记录验证时的核心代码摘要。

`transformer-mixed.svg`、`highway-mixed.svg`及`timemixer-mixed.svg`使用当前图构建器、路由器、文字变换与箭头裁切函数生成；对应 PNG 是这些 SVG 的光栅化结果，**不是浏览器截图**。JSON 保存可检查的完整递归前沿。`http-assets.json`确认 8766 本地服务提供的四个核心脚本与工作区字节一致。

本轮早期浏览器检查确认了 Transformer 标题、展开 FFN、拖动 Q 时文字同步移动，以及所有可见边通过校验。之后桌面浏览器无法连接测试服务，最终修订使用程序回归与上述 SVG 验证；未将最后版本的浏览器交互或 worker 帧率标记为已验证。

## 复验与启动

```bash
cd ~/PycharmProjects/ArchCanvas
node --test --test-isolation=none prototype/Summary_Merge/tests/*.test.cjs
node prototype/Summary_Merge/tools/check_recursive_catalog.cjs
node prototype/Summary_Merge/tools/check_recursive_branches.cjs
node prototype/Summary_Merge/tools/render_recursive_evidence.cjs
python3 -m http.server 8766 --bind 127.0.0.1 --directory prototype/Summary_Merge
```

服务启动后访问：`http://127.0.0.1:8766/yworks_edge_router_lab/index.html?case=01093cc06a87b35a`。保留现有浏览器草稿，刷新时自动升级显示投影，无需清空存储。
