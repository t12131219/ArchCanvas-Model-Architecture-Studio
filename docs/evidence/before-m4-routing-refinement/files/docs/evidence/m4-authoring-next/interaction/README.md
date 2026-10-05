# 第三个 AI 测试角色：独立交互契约审查

`studio/tests/authoring-interaction-independent.test.ts` 使用真正公开的 authored
draft/history/router/camera/API 接口，读取正式模块目录数据；不执行模型。
预期图、端口、位置和历史事实为手写 oracle，不把实现结果另存成预期快照。
源码审查发现的三个用户问题已经由根代理修改产品，本角色只添加独立测试。

最终 **11/11** 测试通过，strict TypeScript exit 0，`git diff --check` 通过：

- 四方向小幅及大幅移动共八种位移，保持完整参数/端口连接和无关节点，
  单次 history、递增 revision、undo/redo 完整恢复、重复渲染相等。
- Add 两个输入端口保持不同位置，保留 fan-out；错误方向、foreign node/port、
  同输入多 producer、闭环拒绝并保持原历史；删除仅影响 incident edges。
- 乱序插入的 DAG 按连接排布后保持语义、无 node overlap 和 body 穿越。
  人工覆盖保持位置，每条保留穿越都有准确 blockedBy。
- public transport 使用 HTTP response stub 检查 CAS revision、精确 payload、
  reopen 深拷贝、冲突不丢本地编辑。这不是实际服务/浏览器持久化证明。
- 点击新增原先每四个节点回到相同位置，第二个节点已重叠 154×78=12012
  单位面积。根代理新增 `nextDraftPosition`，独立十二次新增反例无重叠且
  旧节点不移动。组件还调整 camera 让新节点可见，实际可见性由浏览器记录验证。
- 原缓存只验 mode/schema/数组，`nodes:[{}]` 会进入组件并在读取 position 时
  崩溃。根代理新增 `parseDraftCache`；独立十五类节点形状、非法坐标、重复身份、
  非法 storage/revision 反例及基本坏 envelope 均拒绝，合法未保存草稿与深拷贝
  恢复通过。模块与参数语义仍由正式 server validator 处理，缓存 shape 验证不冒充
  完整语义验收。
- 原 authoring pan 在 pointerup 未收集终点，末次 move(+10)／release(+32)
  会只保留 +10。根代理改为共用公开 cameraGesture，源码确认 owner 校验及
  pointerup 终点。独立三个 zoom × 四方向终点、foreign pointer 和冻结 camera
  恢复通过。该测试不伪装成实际 held pointer 取消证明。

复现：

```bash
node --experimental-strip-types --test --test-isolation=none studio/tests/authoring-interaction-independent.test.ts
cd studio
./node_modules/.bin/tsc --noEmit
```

原始失败记录保留：`public-api-tests-first.txt` 是宿主 sync spawn 的 EPERM，
改为异步正式 Python 数据读取后消除；`public-api-tests-second.txt` 是测试把
220 单位人工覆盖误当无冲突路线，改为检查 anchors 与明确 diagnostics。
`public-api-tests-third.txt` 为最初八项通过，`public-api-tests-final.txt` 为新增
公共修复反例后的十一项通过。不是产品失败被隐去，也不继承旧冻结 scope。

本角色未操作浏览器，避免共享会话冲突。`review.json` 绑定实际读到的产品源码、
测试与原始输出；后续源码修改需要新证据。AI 测试角色不登记为真人，也不认证
出版、浏览器性能或 M4 完成。
