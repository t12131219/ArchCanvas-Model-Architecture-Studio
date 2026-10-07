# Measurement utility adaptation

This new diagnostic adapts the **current formal** `scripts/m4_input_observer.mjs` and loopback service design, not the failed Temp prototype. Frozen bytes and source SHA are in `input-manifest.json`. The observer depends on public DOM/SVG, native input/Event Timing/longtask/rAF APIs and no product hidden state. The service imports only the formal `archcanvas_cli.server` and stdlib and serves the independently frozen KAUB dist. No model is executed, no old evidence/script is modified, and no dist is built.

The original v2 operation trigger, target token and symmetric matching rules remain unchanged. New fields are an explicit input denominator (observed/trusted/untrusted/retained/dropped/failed/coalesced and per-type counters), all canonical-body boundary geometry/viewport coverage, capture-stop→fixed2000ms delivery drain, and timing membership/delivery phases. Full canonical body reads occur only at session/trial boundaries; rAF retains selected target/anchor/pin geometry. Each body read/capture/frame/performance callback reports own cost, with overlapping categories retained. This is limited reuse of a formal measurement utility whose dependencies and independent validator/tests are available, not a certified prototype reuse candidate.

First probe test attempt had2/7pass: the inherited nullable rectangle helper returned `undefined` without an iframe, but the independent v2 oracle requires `null`. That source and failed log remain in `failed-attempt-1-source` and `tests-attempt-1.*`; the new probe makes the no-frame value explicit null. Second probe test attempt7/7pass,27existing independent matching/terminal counterexamples pass against current validator bytes exactly equal to the frozen validator. These are measurement-tool tests, not Studio's product suite or browser performance certification.

`validate.mjs` imports the byte-frozen independent v2 validator and adds a separate denominator/window/coverage oracle. It does not import the new observer or Studio. Existing matching is unchanged, so old matching counterexamples are rerun against the frozen validator and new tests cover the extended event/drop/drain contracts. This is engineering consistency evidence, not acceptance pass.

The responsive iframe fills the actual outer viewport with no top strip. The control panel is an overlay; Start/Arm hide it without resizing the frame. A left-bottom toggle reopens it. Panel visibility times and the small toggle rect are logged. The small toggle and host may still affect presentation/occlusion; inspect actual pixels and record the environment separately. The harness reads its own context with GET but never dispatches input, writes documents or reads product window globals. Ordinary operator actions use the unmodified formal API/history. Capture ledger completeness refers to the declared supported input types while listeners are active, not all OS inputs or unformed native timing.

Run with the formal project environment and a separate data directory:

```bash
PYTHONPATH=src .venv/bin/python docs/evidence/m4-readable-grid-browser-next/continuous-observer-work/serve.py \
  --port 42940 --data-dir docs/evidence/m4-readable-grid-browser-next/continuous-observer-work/runtime-workspace/documents
```

Open `http://127.0.0.1:42940/__continuous/`. Select the Dense300 example in its ordinary UI and reopen the seeded document. Use “开始连续会话”, then show controls, choose operation/canonical IDs, “准备连续操作并隐藏面板”, perform a native pan/drag/wheel, show controls and “结束此连续操作”. Stop once all planned operations are complete; it waits exactly2000ms for delivery. Read the full “完整连续输入 JSON” textarea and use `node …/continuous-observer-work/validate.mjs <raw.json>`.

Pan uses the public hand tool or Space/middle button; drag requires selection tool and exact leaf target; a wrong hit is retained as no-input. Pins come from the actual public `data-pinned-ids`; nonempty pin protection must be prepared with ordinary UI. Arrow routing aesthetics, rendered300object legibility, medium processing and true presentation metrics remain separate requirements.

The frozen Dense300 candidate has a known collapsed-frontier defect: its output moves far above the visible page on network collapse. The initial runtime seed intentionally retains it and uses the already-expanded network for bounded pan/drag/wheel only. This probe does not repair the workload or certify that toggle, whole layout,300readable bodies or performance gates are complete. Keep the defect and any subsequent original trials in the evidence chain.
