# Collapsed residual 独立验收

本目录与新 `studio/tests/collapsed-residual-independent.test.ts` 为本轮独立验收；旧 au3 matrix、work、seal、产品代码与旧 tests 未修改。验收作者未运行产品 tests、全套、build、browser 或 models；正式执行由 root 单独记录。

`baseline/capture.json` 先从冻结 au3 core 与 actual bound 原件生成，不调用 renderer/model/helper。9 个 authored frontier 各保存 core Canvas、Scene、SVG、actual Canvas 与 public SVG 的精确副本；45 个证据原件与 freezer 自身的 46 个读取输入 before/after 不变。实际 Canvas 与 core 仅 revision 差，SVG metadata 除 revision 外完全一致，所有 Scene/core/public path 字节一致。CNN L0 edge9 原 `M 209.3 316 V 329 H 326 V 341 H 209.3 V 354` 长271.4、4弯；固定 straight 候选 `M 209.3 316 V 354` 长38、0弯。保留 hidden Add canonical target、proxy owner、原 ports、角色、样式与独立 data lane，不把 sameTensor 当可合并证据。

`oracle.ts` 完全独立解析 M/L/H/V 路径与 SVG。非法/未解析字节、非有限、对角线、多子路径均拒绝；路由长度与弯折从独立 segment 求得。pair guard 使用整条 polyline 的内部交点：合并 forward collinear split vertices，并包括实际弯折处的接触交点；排除 whole-edge start/end attachment。每条 protected edge pair 分别保护 point count 与几何 overlap union length，sameTensor/同 owner/不同 role/style 不被跳过，不能以总数改善交换另一对新交叉或重叠。所有 front bodies、repeat +3.5/+7 backplates 与 ancestor headers 均独立检查，不用产品 outline/router/intersection helper 作 expected。

`fixtures.ts` 是纯字面 generic graph/Scene/ports/请求，不调用 createDocument、layout 或 routing factory。测试包含 renamed collapsed Module/Repeat、pinned/manual geometry、repeated source exposed outputs、单条无 pressure residual、misaligned Manhattan 最短路，以及 expanded/actual-visible target、upward、memory/mask、缺失/混合/错 canonical proof 的反例。障碍反例覆盖 unrelated body、ancestor header、repeat backplate；protected route 反例覆盖 distinct/same tensor × data/memory/mask/residual 不同样式、严格交叉、重叠、collinear split vertex 与真实 bend vertex。control candidate 是先写明的独立几何，不借产品 candidate generator 得 expected。

9 个冻结 frontier 每个都核 canonical 全覆盖、hiddenEdges、source/IR/facts、完整 nodes/ports、role/style 及 pair-local 不新增 interference。允许其他 collapsed forward residual 取得同类安全缩短；不要求为了保持旧路径而拒绝合理同类优化。任何实际 route 改动都必须 residual、真实 hidden canonical target 的 collapsed visible owner、length 严格缩短且 bends 不增。全导出与 Canvas SVG、重复 render、interactive circle 位置与输入文档不变另行检查。超出 literal work size 的 fallback 必须保旧路由。

该 suite 验证路由与导出几何合同，不认证浏览器像素美学、字体/物理可读性、当前 UA/DPR、真人参与、paint timing 或性能阈值通过。

正式 `target-attempt-1` 的3项失败作为 reviewer 问题保留：2项 generic fixture 的 document.id 含 slash，不满足持久ID合同；1项 overlap 反例同时引入中间 bend point contact，oracle 先以 crossing 正确拒绝，而测试误要求拒绝文字只能为 overlap。`reviewer-repair-attempt-1` 保存旧 test/oracle/fixtures/contract 字节与修复对照；只将 document.id 改成合法持久ID（任意 canonical IDs 不变），并独立断言负例 overlapLength>0 后接受任一种 protected interference 拒绝，安全合同未放宽。oracle 没有修改。root 的首次 runner 另缺 fixtures 输入绑定，其 snapshot supplement 只能补披露当前副本，不能 retro-certify 首次执行时的该文件；后续 runner 已扩大显式输入。
