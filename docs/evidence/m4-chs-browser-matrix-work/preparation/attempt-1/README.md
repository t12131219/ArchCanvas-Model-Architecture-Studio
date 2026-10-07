# ChS current browser matrix preparation — attempt 1

本目录只保存新构建的静态候选、准备与校验，真实浏览器截图为 0，edited 为 0，真人为 0。旧 Bc/Cr/oI5 等任何 raw、矩阵和封印均没有被计入新 coverage。当前 799 个 seal 绑定和 seal 原字节逐项在准备前后保持一致；没有修改产品、既有文档或 status。

正式环境：项目 `.venv/bin/python` 为 Python 3.11.5；实际 Node 为 `/home/fzg/.nvm/versions/node/v24.19.0/bin/node` (v24.19.0)。静态候选仅用 analyze_project AST、正式 TypeScript core，模型未 import/执行，没有安装依赖，没有 PNG。

实际成功执行的入口（完整 argv、开始/结束时间和 exit code 分别在 `*-command.json`，stdout/stderr 为独立文件）：

```bash
.venv/bin/python -B scripts/check_visual_golds.py --project /home/fzg/PycharmProjects/ArchCanvas/ArchCanvas_Model_Architecture_Studio --python /home/fzg/PycharmProjects/ArchCanvas/ArchCanvas_Model_Architecture_Studio/.venv/bin/python --output docs/evidence/m4-chs-browser-matrix-work/preparation/attempt-1/core
.venv/bin/python -B scripts/browser_visual_matrix.py prepare --core-dir docs/evidence/m4-chs-browser-matrix-work/preparation/attempt-1/core --output .archcanvas/browser-visual-matrix-chs-current
.venv/bin/python -B scripts/browser_visual_matrix.py verify --matrix .archcanvas/browser-visual-matrix-chs-current
.venv/bin/python -B scripts/check_browser_visual_matrix.py --output docs/evidence/m4-chs-browser-matrix-work/preparation/attempt-1/independent-artifact-contracts
/home/fzg/.nvm/versions/node/v24.19.0/bin/node scripts/browser_visual_core.mjs docs/evidence/m4-chs-browser-matrix-work/preparation/attempt-1/core-replay-input.json docs/evidence/m4-chs-browser-matrix-work/preparation/attempt-1/core-replay
```

`core/visual-gold-report.json` 给出36候选，geometryPassed/spatialCorePassed=true。core-replay再次validate全部Canvas，并由同一正式renderer重建36个interactive与publicationSVG，publication与静态候选逐字节相同；它不是独立语义/像素oracle。`independent-artifact-contracts/report.json` 为独立发行副本中的8个明确automation反例，不能冒充浏览器或模型运行证据。

新 `spec.json` 冻结 core文件、分析器/renderer/publication实现、完整3件dist与source/IR/expandedIds/page。`capture-tasks.md` 有全量canonical展开目标，不能只展开一个代表层。分母为Transformer L0–L3（12/23/41/49可见对象）、MLP L0–L1（4/8）、ResidualCNN L0–L2（8/10/24），9真实frontiers×paper/monochrome×85/180mm=36baseline，另三模型各至少一份独立edited证据；MLP/CNN不存在的层级不能补造。

## 实际UI加载与后续采集

这里只准备，没有启动/控制服务或浏览器。根操作者使用正式CLI，在一个新的未占用loopback端口启动独立服务；8765不修改。`--data-dir` 必须指向全新工作区下的 `documents` 目录（例如 `/tmp/archcanvas-m4-chs-browser-matrix/documents`），因为server把其父目录作为workspace，实际exports放在该父目录下的 `exports/<artifactId>`。不要把data-dir直接指向工作区根而将exports落到共享 `/tmp/exports`。

在真实Studio的 `示例模型` select中切换 `Encoder–Decoder Transformer`、`Multilayer Perceptron`、`Residual CNN`；服务 `/api/examples/<id>` 静态分析正式 fixtures，然后App.createDocument并按同source/IR恢复保存Canvas。新origin＋新的documents避免继承此前已编辑画布。不要把静态core候选或生成草稿冒充实际UI document。若例子恢复已有记录，先核对应source/IR/frontier/visual字段是否真baseline。

通过真实UI逐层展开capture-tasks所列全部容器，切论文彩色/黑白和85/180mm；保存当前Canvas后从UI整图SVG导出，不选择详情范围。关闭导出modal、fit，先读取可见AX/DOM，先丢弃一次截图，再独立tool call保存第二次实际CUA截图；该顺序仍需每图实看验证可见模型、frontier、页头、整纸/legend与无modal，不能以DOM/helper通过代替像素。

每例原样保存真实store `<documentId>.json` envelope和其复制时间/字节SHA sidecar，在下一case改变store前冻结。只按本例浏览器实际exportUrl对应artifactId复制实际SVG、receipt和exportCanvas，不搜索替代export，不用core SVG代替服务导出。保存 `.publication-scene svg.outerHTML`、实际wrapper expandedIds、documentId/revision/source/IR/page、camera transform/scene屏幕bounds、当前viewport/DPR、实际loadedJS/CSS URL并绑定本spec中的SHA。UA/字体/硬件不可观察时明确来源/缺口，不能继承旧1102×835环境或伪称当前读取。caseId为全新且拒覆盖；失败保留excluded并另case重采。

真实capture后使用正式 `stamp-hashes` 与 `collect`，输出全新目录，并独立看像素/字段。`artifactCoverage=complete`仍不代表人审、物理出版或呈现性能合格；此preparation当前仍0/36+0/3，不改M4 partial。
