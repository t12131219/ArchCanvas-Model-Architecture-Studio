# 当前冻结实现与研究包独立完整性末审

审计时间：2026-10-04T22:25:08.236857+00:00。只读JSON／文件／SHA256核验；未重跑测试、构建、服务或浏览器，未调用正式verified_spec函数。只创建本JSON与本MD，未修改产品／raw／根任务正在整理的文档。

研究manifest：14104 bytes，SHA256 `4bf341d0c5848d8591ebec138a3723753c13315a57981a19e4676c07b2678d86`。

58个正式实现绑定、4个baseline工件和5个slot文档SHA／bytes全部一致；baseline canonical digest符合manifest。S01–S05端口8881–8885，未分配，参与者／审阅者为空；每slot只含同一baseline文档，storage revision1、visual revision0，25个任务条目均pending无证据。researcherCount0、researchGate=not_run。

原始studio-tests-final.txt包含79个通过条目，summary79pass／0fail／0skip；build-final.txt记录tsc --noEmit与vite成功输出DPwoyNJW。这里只核对既有记录，不重新声明运行。此子任务没有Python10测试的新运行或核验结论。

独立性详细report：915056 bytes，SHA256 `1131642db8242ed1b767df6fc80dca956d75d16da9d279db15af3edfa6d3b586`。9项checks与摘要一致；5个包来源在独立副本内，5份分析输出SHA一致，副本sourceManifest的4468项SHA一致。独立副本JS／CSS／index与正式dist逐字节一致。Python隔离记录为-I -S，仅添加standalone src；Studio构建使用拷贝的本项目已安装node_modules，不证明全新依赖安装。

| 当前dist | bytes | SHA256 |
|---|---:|---|
| `studio/dist/index.html` | 477 | `2ae814208ad18879724331ae17834d8d5921091248900b4863b3a0928cb4b63a` |
| `studio/dist/assets/index-DPwoyNJW.js` | 375594 | `c7189a047fbd29cba25779a9098d5b2c1265e21c827620834379d0e611af3bc4` |
| `studio/dist/assets/index-DK5lov-h.css` | 27591 | `d6d5f8f4d8824f28b313ffffe685678225486e5cf25966f0528d3846eb6a8a7f` |

矩阵spec：79016 bytes，SHA256 `847b40ea74b474c2853263abd9557971af9cf386ef1f51c8f3194e1ee1d45625`，与matrix-prepare.json逐字节相同。schema／protocol符合verified_spec读取要求；21implementation＋3build＋72core绑定及core report digest全部匹配。
core report：103735 bytes，SHA256 `1292030fc3634f5d34d5db570e3a6d55de43e1300a430d92225fd7144f0725b0`。

矩阵verify既有记录为frozenFilesUnchanged=true、visualAcceptance=not-evaluated；此审计用独立文件核验重证冻结条件，没有运行该产品函数。36个baseline候选／9个frontier的工件哈希一致不构成像素、出版可读性、性能或人工验收。

全部检查缺陷数：0。完整逐项绑定与检查结果见同名JSON。
