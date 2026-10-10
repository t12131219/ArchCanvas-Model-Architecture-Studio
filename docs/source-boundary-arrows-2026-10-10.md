# 展开源码模块的入口、出口连线修复

用户截图中的 UnknownFern 已有 projection → activation → head，但外部输入和输出仍连到 ConditionalRegion 容器。根因是源码依赖分析以空参数环境单独处理每个 forward，忽略调用参数与返回值，也丢失 opaque region 之后不同变量的来源。

本次在非执行 AST 分析中保留调用接口、Sequential 所属模块和条件区域的实际输入引用。参数按位置/关键字绑定，tuple/list/dict 值保留槽位，局部变量与别名、条件分支、提前返回和嵌套 helper/module 的依赖组成入口、出口。不同 opaque 赋值仍使用原有保守张量/端口，但另存变量槽位供源码恢复使用。未恢复的调用不被当作 identity 穿过。

新增 `boundary-dependency` 与原有 `value-dependency` 共存。跨区域依赖带原始 ConditionalRegion ID、canonical edge ID、源码 span 与完整性标识。schema 和 Studio 同时校验边界、真实绑定、源码后代和不同端点。静态依赖不是已执行的张量拓扑；不导入或执行用户模型，不新增 tensor ID、张量端口或执行路径结论。

UnknownFern 两侧都显示 `x → projection → activation → head → output`。源码箭头投影到折叠的子模块，完全收起 region 后恢复保守容器连线。完整且全部可见的源码路径代替重复容器笔画；原始 scene.edges/draft.edges 保留供导入、校验、保存和审查。缺失子模块、部分恢复或预算截断保留保守笔画。导出 metadata 保留原始绑定以及 `sourcePresentedBindings`。跨容器路线仍避让标题、子模块和无关容器，使用现有正交路由器的 6-unit 留白。

## 验证证据

证据目录：`docs/evidence/source-boundary-arrows-20261010/`。

- `tests/test_source_dependencies.py` 覆盖多输入、多返回值、关键字、tuple swap、nested helper、Sequential、独立调用、分支隔离、提前返回、两区域组合及结构化输入的准确 canonical edge 对应。
- `studio/tests/source-dependency-arrows.test.ts` 覆盖完整8条箭头、折叠/展开/JSON重开、移动后路由、编辑导入、canonical事实不变、详情范围、单色、SVG和边界缺失/伪造拒绝。
- `frontend-final.log`：597项通过，无跳过；`build.log`：构建通过。
- 最终 Python 全量结果见 `backend-final.log` 与 `backend-final-result.json`，包含正常退出证据。前一轮 `backend-full.log` 使用旧导出断言，已保留失败记录；受限沙箱的 `backend-regression.log` 另含 loopback/netlink 权限错误，不作为最终通过证据。
- `patchtst-summary.json`：484节点、108条源码依赖、原始3条张量边；视图/编辑源码连线及编辑张量路由均无阻挡。单次展开约0.77秒，编辑路由约0.72秒。仍触及480-node/12-level源码结构预算，不能据此声称完整恢复整个模型。
- `unknown-fern-saved-session.json`：真实浏览器已保存的画布，visual rev5、storage rev2。编辑→视图及新标签重开均完成，原始旧画布未修改。
- `unknown-fern-browser.png`、`unknown-fern-publication.png`：实际浏览器和同一保存画布的PNG导出。SVG/PDF/PNG转换另由publication用例验证。
- beta.11候选、安装与独立分析一致性见 `beta11-*.json`、`installed-analysis-equality.json`。
- `rollback-smoke.json`、`rollforward-smoke.json`、`rollback-behavior.json` 验证独立beta.11→beta.10→beta.11；源码依赖数量8→4→8，张量边始终3条。

## 使用与回滚

新版分析产生新IR，旧画布绑定的分析事实保持不可变。修复画布：
`http://127.0.0.1:8883/?documentId=canvas-architecture-unknown_fern.UnknownFern-a3cef22c1de0-064b2228`

`.archcanvas/source-boundary-beta10-rollback/.agents/skills/archcanvas` 是校验通过的完整beta.10。执行 `scripts/rollback_source_boundary_arrows_20261010.sh` 可恢复全局Skill并保留被替换版本。服务需重新启动；保存的新旧画布和源模型文件不受此脚本影响。

本次改动前的源码文件保存于证据目录 `before/`，不通过git reset回滚已有未提交工作。运行时发布包为 `.archcanvas/releases/archcanvas-0.1.0-beta.11.tar.gz`，仍是本地beta预览；三宿主E2E和完整人类/出版质量认证不由这些回归结果替代。
