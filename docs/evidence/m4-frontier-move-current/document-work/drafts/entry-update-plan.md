# Frontier move 正式入口更新计划（草稿）

仅在 root 最终 checks/browser/dist 收据落地后应用。此文件是入口文本和 gate 字段的拟稿，不修改正式入口。

## README.md 与 docs/m4-performance.md

在当前 memory continuity 第一节、历史 `##` 之前追加一段：

> 后续 M4 frontier-scoped movement（目标链接 `docs/m4-frontier-move.md`） 将普通视觉移动区分为 `all-frontiers`（默认，保持历史行为）与显式 `current-frontier`（仅当前视图，保留其他 frontier）。移动距离为画布世界单位；自然语言和拖动、对齐、位置修复共享同一范围。独立 core 18/18、workload preflight 48/48、受控 UI command 14/14 通过；root 最终 Studio/build/publication 和浏览器状态见新阶段 receipt。历史 all-frontiers `dy=-28590` 导致 collapsed world `y=-28236` 的旧反例保留，未被静默迁移；新 300 workload 来自 unbroken grid4 的 fresh typed current-frontier 操作。该阶段不认证 presented FPS、输入到 paint、全局美观、出版尺寸或真人使用。

`docs/m4-performance.md` 目标链接使用 `m4-frontier-move.md`；`README.md` 使用 `docs/m4-frontier-move.md`。应用时替换 `{{ROOT_FINAL_*}}` 为真实收据路径与 hash，不能引用旧 CU5 build 作为新 current build。

## docs/evidence/README.md

在第一节追加相同事实的证据索引，链接：

- `m4-frontier-move.md`
- `m4-frontier-move-current/independent/README.md`
- `m4-frontier-move-current/independent/workload-readback-report.json`
- `m4-frontier-move-current/ui-contract-review/summary-final.json`
- root 最终 checks/browser receipt

说明旧 300 bad arithmetic 与新 grid4 fresh candidate 的区分，保留 stale research package，不把旧 readiness 变成新参与者包。

## docs/evidence/m4-current-gate-audit.json

只追加一个根字段 `latestFrontierMove`；其他字段必须 JSON deep-equal 原 gate。拟稿结构如下，`{{ROOT_FINAL_*}}` 全部待替换：

```json
{
  "stage": "docs/m4-frontier-move.md",
  "scope": "Typed frontier-scoped visual movement; omission preserves all-frontiers default.",
  "moveScope": ["all-frontiers", "current-frontier"],
  "distanceUnit": "canvas-world-unit",
  "independentCore": {"passed": 18, "total": 18, "exitCode": 0},
  "workloadReadback": {"passed": 48, "total": 48, "exitCode": 0, "inputRevision": 4, "candidateRevision": 5, "collapsedRevision": 7, "reexpandedRevision": 8},
  "uiContract": {"passed": 14, "total": 14, "exitCode": 0, "inputsExact": 26, "inputTotal": 26, "mountedReact": false, "browserPaintCertified": false},
  "rootChecks": "{{ROOT_FINAL_CHECKS_RECEIPT}}",
  "rootBrowser": "{{ROOT_FINAL_BROWSER_RECEIPT}}",
  "oldBad300ArithmeticPreserved": true,
  "freshGrid4TypedCurrentCandidate": true,
  "oldResearchPackageStale": true,
  "modelExecuted": false,
  "humanParticipantsAdded": 0,
  "performanceGatePassed": false,
  "M4": "partial",
  "M5": "not_started"
}
```

## skills/archcanvas/SKILL.md

在 “Refine an existing figure” 或 “Preserve these contracts” 附近增加以下入口说明；应用前需由 root 确认最终 build/runtime capability：

> For a supported Studio with frontier caches, visual movement uses canvas-world units. The omitted move scope preserves `all-frontiers`; choose `current-frontier` explicitly when only the visible frontier should change. Resolve the actual operation and runtime capability before claiming support. Preview and commit must use the same scope, preserve stable source/IR/canonical identities, and retain pinned/ancestor protections. A current-frontier check is bounded visual evidence and does not establish presented FPS, global routing quality, publication acceptance, or human usability.

不要在 Skill 中写入未落地的 runtime command、旧 prototype fallback、模型执行或真人验收结论。
