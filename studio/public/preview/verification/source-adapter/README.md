# 未知源码适配验证

验证对象是源码适配层和 8767 预览服务，不修改既有 catalog 或 `Summary_Merge（复件）`。

## 结果

- Python AST 单测：9 项通过，记录在 [python-tests.log](python-tests.log)。包括无执行 sentinel、跨文件/关键字/结构返回、共享实例、Unicode UTF-8 证据列、动态分支、装饰/继承/原位/输出缓冲区/构造 helper 保护和预算拒绝。
- Node 编辑器测试：4 项通过，记录在 [editor-tests.log](editor-tests.log)。RiverNet 完成导入 → 混合/全量展开 → 移动 → 折叠/重开 → JSON 保存恢复 → 源码篡改拒绝；所有跨层 input 接口均检查无反向绕行、最多一个转折；WeatherCell 动态分支保持一个待解析区域。
- 既有递归与交互回归：8 项通过，见 [existing-regressions.log](existing-regressions.log)。
- CLI 包：[river-net.json](river-net.json) 为 18 节点/17 条依赖/0 个待解析区域；[weather-cell.json](weather-cell.json) 为 4 节点/2 条依赖/1 个待解析区域。
- 浏览器实际导入截图：[browser-source-import.png](browser-source-import.png)；完整展开截图：[browser-source-expanded.png](browser-source-expanded.png)。页面 DOM 在展开后报告 `18 nodes / 17 edges`、`data-source-constraint-valid=true`、`data-layout-constraint-valid=true`；小幅节点移动后标题跟随，箭头重新计算并通过约束。
- 陌生模型通用布线回归：[routing-layout.json](routing-layout.json)。二元算子的标题侧按邻接流向和容器空间自动选择，输入端口按距离和朝向代价联合分配，再由共享路由器优化路径与折点；RiverNet 概览为 `628×782`，7 条边无交叉，源码约束、布局约束和边约束均通过。二元标题障碍使用实际文字包围盒，逐级展开时不再把隐藏层的预留空间当作当前画布空间。
- 本次浏览器复核：[直接输入路线](browser-routing-input.jpg)、[紧凑概览](browser-routing-compact.jpg)。`x → Sequential input` 从右侧向下进入输入，外层加法标题位于左侧；收起后 `8 nodes / 7 edges`、4 个折点、0 个交叉。浏览器保留了原手动移动，因此总长为 848 px；无手动位移的 fixture 为 866 px。完全展开 fixture 仍有 1 处不同值依赖的交叉，合法性校验全部通过，未声称任意图都无交叉。
- 完整 catalog 检查通过：115 个当前案例、665 个导入视图；原始源文件哈希、标签和语义 IR 保持一致。本次也重新运行了 graph-engine、recursive-expansion、interaction-mode 和 source-glyphs 四个既有测试文件，均通过。

![RiverNet 导入后的 Summary_Merge 编辑器](/home/fzg/PycharmProjects/ArchCanvas/prototype/Summary_Merge/verification/source-adapter/browser-source-import.png)

研究资料均为可复核的页面文本提取：[FX](research-fx.json)、[torch.export](research-export.json)、[Netron](research-netron.json)、[torchview](research-torchview.json)。

## 可复核命令

```bash
cd ~/PycharmProjects/ArchCanvas/prototype/Summary_Merge
python3 -B -m unittest discover -s source_adapter -p test_analyze.py -v
node --test --test-isolation=none --test-reporter=spec tests/source-adapter.test.cjs
```

服务运行期间可打开 `http://127.0.0.1:8767/yworks_edge_router_lab/index.html`，在“导入模型源码”中选择 `source_adapter/examples/novel_model.py`，入口填 `RiverNet`。

## 边界

页面导入验证的是源码内容、证据片段、IR canonical digest、连接身份和初始布局；它不能证明源码运行正确、张量 shape/dtype 正确或未知动态分支的实际执行路径。无法静态绑定的代码保留为 opaque，并仍可移动、保存和导出。
