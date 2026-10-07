# Unified editor requirements audit (v2, staged)

The preparation run reads the current formal worktree, checks all successful
recorded online research snapshots against their bytes and SHA256, reads the
actual DL-Playground reference checkout identity, and runs fresh tests for
requirements 1–3. It does not reuse the v1 source-binding receipt or overwrite
historical evidence. `checks-prepare.json` is provisional; the accepted
current-code binding is `report.json` together with `checks-final.json`, after
the final code, browser generation check, and current routing receipt settled.

| Requirement | Final bounded evidence |
| --- | --- |
| Source view → authoring continuity | 14/14 current callback/session/compact card/generated-canvas tests; actual parameter edits, additions, deletion/rewire and collapsed-frontier generation also covered in the Python subset |
| Atomic modules and transparent presets | Actual runtime catalog matches 74 atoms / 13 categories; all 23 presets exercised through real insertion and static generation; 12/12 palette/preset tests |
| Infinite dot canvas | 3/3 tests for world-anchored grid, all pan quadrants, unrestricted translation, pointer-centred zoom and grid-free publication SVG |
| Python source bridge / grouped generation / atomic catalog | 22/22 current tests; no model execution |
| Atomic frontier and routing | Current v3 receipt: 41/41 cases, 19 changed pair geometries, 0 new pair violations; canonical/source/identity/parent-child/scene-SVG invariants clean; full Studio 525/525 and build pass |

Preparation inputs stayed unchanged throughout the run. The 16 successful
network snapshots match their recorded byte sizes and hashes. DL-Playground
checkout HEAD is the recorded `c07a79b60bcb67be0bec2276002bd21f92a616de`;
its public categories inform discovery, and no implementation or assets are
copied. The two small PyTorch stable-address redirect pages are not counted as
API content, and 403 requests remain explicitly recorded as failed requests.
The full PyTorch 2.9 pages and pinned API-source documentation are available in
the successful snapshots.

Run `./.venv/bin/python docs/evidence/unified-editor-review-v2/requirements-audit/run_checks.py --label final`
after the coordinated code changes settle. The first final attempt was captured
under `unstable-final-attempt-1/` and is explicitly unbound because
`readableRouting.ts` changed during its test window; passing tests from that
attempt are historical diagnostics, not current-code proof. Each accepted run records before/after input
bindings, exact commands, timestamps, log hashes and formal runtime provenance.

These checks establish bounded engineering behavior and static contracts.
Model execution/numerical equivalence, human usability, global routing
optimality and physical publication review are outside this evidence. M4 stays
partial with zero human participants, as explicitly authorized by the user.
