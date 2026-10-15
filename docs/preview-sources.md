# 预设案例源码整理与互通

按用户要求，参考案例统一使用 Python 文件，并允许重新命名。日常源码入口是 `studio/public/preview/sources/`，不再需要在庞大的快照目录中寻找对应版本。

## 目录和来源

| 位置 | 内容 |
| --- | --- |
| `sources/packages/<案例名>_<摘要>/` | 案例实际绑定的多文件 Python 包、许可证；相同内容供当前/历史案例共享 |
| `sources/notebooks/` | 全部 Notebook 的合法 Python 路径转换版 |
| `data/catalog-sources.json` | 每个案例的入口、Python 资源、原始路径别名、证据和许可证 |
| `data/source-packages.json` | 110 个源码包、142 个 Python 文件及来源台账 |
| `data/notebook-conversions.json` | 112 份 Notebook、28 种内容、29 个 Python 资产及完整 cell/行映射 |
| `snapshots/` | 原始来源、Notebook、图、许可证和历史证据，继续保留用于追溯 |

源码整理不需要访问原型目录，也不 import、实例化或执行模型。112 份 Notebook 都有与代码单元逐字一致的既有 Python 转换；本次验证转换后将精确字节集中发布。Notebook magic 作为注释保留。案例目录、文件名中的连字符及版本号点改为合法 Python 标识符；多文件包移除共同的仓库目录前缀，使 `layers.*` 等本地导入可被静态解析。入口和源码位置同步转换，正文及证据行号不变，`originalPath` / `originalAsset` 保留原名称。

盘点确认原型 `snapshots` 的 5731 个文件在正式工程中均已存在，报错并非普遍漏拷贝。此前 223 个有源码案例的 304 个 Python 资源引用都能读取；这次补入同一源码快照中原已保存、但未进案例索引的 MobileNetV3 `utils.py`，最终为 306 个引用、142 个去重资源。没有网络下载或替换成不同版本的依赖。

## 预览对象与源码编辑

规范入口后，112 个当前有源码案例中，96 个可以进入正式静态模型解析（此前仅 7 个）。其余 16 个涉及函数入口、自定义执行方法、没有 `forward` 或不受支持的继承等，仍提供完整 Python 文本和视图编辑；不会伪造一个 `forward` 来宣称支持。新源码重新生成预览的适配器支持范围另计，当前为 103/112；原有离线案例图仍可查看和编辑。

手工审核过的原型图包含聚合模块、共享值及展示节点，不能与另一套解析器的 AST 节点简单一一对应。预览模式因此保留原型 ID 的完整面板投影，让所有图元均可进行显示名、颜色、布局、图例和连线样式等视觉编辑。229 个静态案例中 6360 个非 junction 展示图元均可精确寻址；路由实验由内置图提供。进入“编辑”时，按当前 Python 文本重新建立正式 Architecture，再进入既有模型编辑流程。

源码证据通过原始路径别名、多条文件/行证据与实例身份匹配，不按图元显示名猜测。没有独立行证据的对象仍可查看完整源码；源码不支持正式解析时显示明确边界。`preview-only` 投影保留 opaque 标记，不能提交模型参数、激活或结构事务。图的视觉编辑不会修改参考源码。

7 个案例本来没有模型源码：路由实验和残差教学 SVG。它们仍可进行视觉编辑，并明确显示无模型源码，不绑定不相关的 Transformer 文件。

## 重建与验证

```bash
python3 -B studio/scripts/organize-preview-sources.py
python3 -B studio/scripts/convert-preview-notebooks.py
python3 -B studio/scripts/convert-preview-notebooks.py --check
PYTHONPATH=src python3 -B studio/scripts/check-preview-sources.py
node --experimental-strip-types studio/scripts/check-preview-source-mapping.ts
```

开发用 `vendor-summary-preview.py` 在刷新原型材料后也会执行两项整理，正式启动不执行这些脚本。

本次静态结果见 [source-availability.json](evidence/preview-sources-20261014/source-availability.json)：230 个案例索引，223 个有源码，全部资源 SHA256、AST、入口符号和预算检查通过；112 份 Notebook 共验证 27674 个原始单元行映射。图与正式源码节点的实际映射覆盖、完整展示投影覆盖见 [source-mapping.json](evidence/preview-sources-20261014/source-mapping.json)。这不证明任意 Python 实现、动态控制流或训练执行均受支持。

当前构建 `index-CHFG_21J.js` 的 507 项源码、证据、许可证、台账与集成资源均通过实际 HTTP 内容核对，dist/public 字节一致，见 [http-source-assets.json](evidence/preview-sources-20261014/http-source-assets.json)。

真实 Studio 浏览器验证覆盖 AlexNet、ActNorm、MobileNetV3、PyTorch 原图和 DCGAN，14 项检查通过、浏览器错误 0。验证规范源码与摘要、对象与图例面板、撤销/重做、保存及编辑 JSON；AlexNet 能进入现有正式源码编辑，DCGAN 明确保留只读源码，PyTorch 原图不编造逐节点证据。见 [browser-sources.json](evidence/preview-sources-20261014/browser-sources.json)，可用 `studio/scripts/test-preview-sources.mjs` 重跑。

转换/包整理单元测试 15 项、发布包预算 4 项全部通过；相关前端测试 34 项中 33 通过，既有 publication DOM 测试在命令 sandbox 内无法启动 Chromium 而跳过，未计作成功。构建成功，12 项集成资源摘要与 public/dist 一致。命令及结果见 [checks.json](evidence/preview-sources-20261014/checks.json)。
