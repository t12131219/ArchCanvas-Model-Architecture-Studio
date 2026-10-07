# M4：独立草稿合并路由合同

这是 AI 验收角色的独立几何合同，不计作真人研究者。产品从正式要求与失败案例独立实现，没有读取、运行或采用失败 Temp 原型代码；本角色没有执行模型、安装依赖或改产品源码。

[最终11项合同](scope-boundary-extension-attempt-1/contract.json)绑定[实际测试](../../../../studio/tests/draft-merge-routing-independent.test.ts)。176×100 卡片及有序端口期望、有限草稿和正交段相交传感器均手写；不以产品的端口、路径、碰撞、评分、流向或 refinement helpers 当 oracle。不同 producer 的严格穿越、折点接触、正长度叠线均失败；只有同 source nodeId＋portId 的分支可以共线，每条边仍须完整独立保留。

实际五节点固定坐标为 A(50,80)、B(50,250)、Add(350,160)、Concat(620,160)、Output(890,160)。五边须保持 Add.left=A、Add.right=B、Concat.a=Add、Concat.b=A、Output=Concat。合同检查端点、外出/内入法向、无 body 穿透、无不同 producer 接触与叠线、四向移动16、history、JSON 重开、稳定重算、直链、障碍、逆向和垂直多输入布局。25 卡片范围边界须保留五条边、端点和全部草稿字节；它不强制具体 fallback 路径，也不强制保留或消除某个交叉。

冻结旧源码[最终基线](baseline-attempt-3/receipt.json)为11项7通过4失败，实际水平交叉为(614,220)，垂直布局在(218.67,454)存在不同 producer 折点接触。前两次10项6通过4失败收据保留；初始零长度 sensor 错用0.025端点容差，误拒了合法0.003333单位舍入接缝，已在[observer修正合同](observer-repair-attempt-1/contract.json)中记录，改为只拒绝严格相同两坐标，没有放松相交、body、身份或语义合同。[两类手写平面 witness](witness-planarity-attempt-2.json)独立验证这些固定图存在清晰解，不规定产品应输出哪条路径。首次 witness reader 相对 import 失败原件也保留。

[9项源边界审查](source-review-attempt-1/report.json)通过：47原件中仅 authoring.ts 变化，实际差异为新导入和 draft-only 调用；共享 router、Canvas scene/export、UI 和原正式文档精确。新增函数只写局部路由结果，不改坐标、schema、参数、绑定、源码或存储。conflict100000与clear几何250000分别约束新增搜索，另有节点、边、cell、state、search caps。耗尽保留所有原路由或已经安全接受的候选；不把较大草稿、非平面固定端口或搜索失败伪称为全局交叉已清除。

[6项最终检查复读](final-check-readback-attempt-1/report.json)通过，物理读取190去重绑定：正式[专项39/39](../checks/target-attempt-2/receipt.json)、[全套275/275](../checks/suite-attempt-1/receipt.json)无跳过，strict TypeScript/Vite[构建退出0](../checks/build-attempt-1/receipt.json)，before/after/current source、运行器、日志和 dist 精确。11项是最终新合同，先前10项与各次基线不叠加；本角色没有再运行这些测试。

产品候选按0.01舍入，独立端点容差0.025，故不声称端点浮点位级相同。证据只证明有限草稿几何及源边界；不认证任意固定布局全无交叉、最少弯折、出版尺寸可读性、浏览器性能、完整原生操作或真人体验。真实浏览器复采由主角色另行留证，M4其他门限仍需独立证据。
