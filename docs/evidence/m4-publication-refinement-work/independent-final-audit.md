# Publication final independent audit

末审绑定实际最终构建 `index-DPwoyNJW.js`，SHA-256 `c7189a047fbd29cba25779a9098d5b2c1265e21c827620834379d0e611af3bc4`。旧 Qpo 审计文件保持字节不变；本报告重新核验最终 journal、截图、新服务链接及真实文件，未继承旧矩阵或以旧截图替代。

## 核验结果

- `browser-journal-final.json` 11/11 条 scripts 精确指向 DPwoyNJW；11 个主 Canvas XML、9 个有效预览与对应输入文档、范围、页宽的独立重建结果精确匹配，5 份详情选项的 nodeId、ordinal、路径、字号及页高精确相符。24 mm 记录明确保存验证提示、无预览/链接和生成按钮 `disabled=true`。
- 3 份本轮真实导出为 feedforward 86 mm SVG、同范围 PDF、CNN 180 mm SVG。每个服务 id 来自相应 journal 实际链接，与 `final-export-bindings.json` 精确一致；9 个服务/复制文件 bytes/SHA 全匹配，不使用推断 id、最新文件搜索或内容匹配关联。6 份实际 preview/interactive XML 副本也精确匹配同条记录及重建 XML。
- 3 个输入文档与准备基线精确相等；2 个模型重新正式 AST 分析所得 architecture 精确相等，源码内容/digest 与 source/IR 保持一致。11 个主 Canvas 保持基线可见 frontier/geometry/元数据。8 份几何核心源码 bytes/SHA 与 Qpo 审计一致。
- 2 个 SVG 精确等于正式发布转换器处理当前公共 SVG 的字节。feedforward 86 mm 最小文字 `7.02534661553473 pt`、场景页高 `263.700288184438 mm`；PDF 与同 86 mm SVG 的 scene digest 一致，真实单页 MediaBox `243.779528 × 747.496885 pt` 与独立毫米转点公式误差小于 `0.05 pt`。
- CNN 说明仍为宽 `380`、场景高 `50`，真实 SVG 两个 tspan 为 `Each residual block combines transformed features with its skip` 和 `path.`。
- 11 张 `final-*.jpg` 已逐张通过 `view_image` 实际审看，可见目标状态与记录一致，没有复现 Qpo 的3张滞后截图。截图可见切片未覆盖的完整文本/链接/结果缺失状态由 DOM 和实际文件验证，不夸大像素证明范围。

## 缓存与记录范围

第9条（零基 index8）当前 CNN 面板没有旧 v1-era artifact 链接/生成结果。先前 Qpo 的 CNN 服务导出实物仍存在；最终面板使用 v2 key 与 exact scene SVG 校验。第11条 reopening 的3个链接精确等于第10条新生成当前 SVG 的链接，preview/Canvas XML 亦完全相同；恢复旧结果不计第4个新生成文件。浏览器缓存 envelope 原始内容未另行记录。

同 revision/source/IR 下渲染内容改变的拒绝反例属于新增2项纯函数测试及源码契约，不宣称做过实际浏览器 renderer 升级实验。已有最终完整日志为 Studio `79/79`（原77+新增2），TypeScript/Vite 构建成功；末审没有重跑完整套件。Python publication `10/10` 仍是先前范围记录，发布 runtime/core 未变，未重标成新版重跑。

独立副本已有报告9项通过；4468 source manifest 项、5分析文件及3构建文件经只读子审核验，包来源在副本。Studio 使用拷贝的已安装 node_modules，不证明 clean install。最终研究包 manifest SHA `4bf341d0c5848d8591ebec138a3723753c13315a57981a19e4676c07b2678d86`，58实施绑定、4基线及5slot文件全匹配；ports8881–8885，全部unassigned，storage revision1/visual revision0，0参与者、researchGate `not_run`。prepare/verify 支持冻结包准备与完整性，不构成人工研究结果。

## 服务证据边界

保存的 `service-restart.txt` 及3个随后实际成功文件支持端口8886上的恢复成功；失败请求未计入成功样本。旧session90378退出143、failed fetch、restart session64384来自根任务事后转录的原工具响应（chunks `e36654`/`7dd742`），没有独立同期落盘的原过程收据；本审计不认证退出原因或将这段历史转录当作独立原始过程证明。

本轮没有发现 scene/document、转换几何或最终截图状态缺陷。覆盖仅限两份输入、11条最终观察及3份实际导出；不继承历史39项矩阵，也不构成人工美学、原生性能、字形/字体嵌入、参与者研究或投稿出版质量验收。详细绑定、每项结果及限制见 `independent-final-audit.json`。
