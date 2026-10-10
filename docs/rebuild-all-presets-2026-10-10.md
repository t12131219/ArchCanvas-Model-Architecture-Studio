# 全案例删空重建回归（2026-10-10）

本次验证覆盖正式服务暴露的 7 个源码示例和编辑器左侧 23 个透明网络起点。测试均在独立草稿/独立数据目录中完成，未修改用户当前画布。

## 结果

- 7/7 源码示例均可在编辑模式中逐个删除到 `0 模块 / 0 连接`：Encoder–Decoder Transformer、Multilayer Perceptron、Residual CNN、Vision Transformer holdout、Dense 300-layer stress、Input Rebinding Lab、Multi-input Attention。
- 7/7 均可从空白逐个添加原子模块；Transformer 和 Multi-input Attention 的 mask 注意力使用源码自定义模块补充具名 mask 端口。
- 7/7 均可逐条建立连接，静态生成和精确端口/边绑定核对通过。
- 7/7 均可保存、重开并重新建立画布；原始源码视图保持不变。
- 23/23 左侧网络起点均可删空后按原节点、参数、连接逐个搭回并生成。
- 前端完整回归：599 项通过，0 失败，0 跳过；最后缓存键调整后定向 11 项通过。
- 后端完整回归：469 项通过，0 失败；运行隔离检查在授权环境中正常完成。

详细逐例结果见 [`source-example-matrix.json`](evidence/rebuild-all-presets-20261010/source-example-matrix.json) 和 [`library-preset-matrix.json`](evidence/rebuild-all-presets-20261010/library-preset-matrix.json)。浏览器视图/编辑入口计数见 [`browser-view-matrix.json`](evidence/rebuild-all-presets-20261010/browser-view-matrix.json)，截图见 [`rebuild-checked-chain.png`](evidence/rebuild-all-presets-20261010/rebuild-checked-chain.png) 和 [`browser-transformer-rebuilt.png`](evidence/rebuild-all-presets-20261010/browser-transformer-rebuilt.png)。

## 修复

- 普通编辑草稿容量从 128/384 提升到 1200 模块/3600 连接，覆盖 300-layer stress 案例，并同步前后端缓存校验和网络起点插入检查。
- 删除展开源码区域的最后一个子对象时递归移除空容器；删至空白后清除 source provenance/cache，避免旧源码边界阻止新建。
- 编辑器 Ctrl+A 现在包含源码容器，Delete 后可真实得到空草稿；增加“保留未使用分支”选项，支持源码中的独立分支按原样重建。
- 自定义模块预览可提供 Q/K/V、`attn_mask`、`key_padding_mask` 等具名端口，用于重建带 mask 的注意力。
- 静态分析保留 `flatten`、`transpose`、`mean` 等 tensor 方法的字面量轴参数，防止 Vision Transformer 重建丢失计算语义。
- 分组生成器按实际功能运算发射顺序绑定重复 Add/算子，避免残差图绑定到错误的同类运算。

保存前快照在 [`before/`](evidence/rebuild-all-presets-20261010/before/)；本轮变更保持可回滚。

## 安装与回滚

当前全局 ArchCanvas Skill 已更新到 `0.1.0-beta.12`，doctor 为 `ready-local / verified`，安装哈希验证通过。`scripts/rollback_rebuild_presets_20261010.sh` 可恢复 beta.11 并存档被替换的版本。本轮源码差异为 `evidence/rebuild-all-presets-20261010/this-turn.diff`，可以按 before 快照恢复本轮修改，保留前轮未提交工作。

全部案例的完整操作矩阵使用实际编辑器 reducer、正式 backend 与真实保存仓库完成；浏览器又逐例打开 7 个已保存画布并核验视图节点/边、编辑入口和草稿计数。Transformer、Residual CNN、ViT、MLP、输入重绑定和多输入注意力均完成编辑进入/返回视图；300 层案例在编辑器显示 `303 模块 / 301 连接`，加载后检查通过且保持响应，因大图渲染成本未重复做视图返回。未声称每个案例的数值或训练行为等价；本轮模型重建验证均为非执行静态验证。

实际 HTTP 矩阵另覆盖全部 7 例的校验、生成、草稿保存重开、源码注册及画布保存重开（`http-matrix.json`）。浏览器另确认自定义 MaskedAttention 的 query/key/value/attn_mask/output[0] 端口预览。隔离副本 beta.12 → beta.11 → beta.12 回滚验收通过。
