# Current-build atomic drag / Escape capability attempt

This bounded, AI-operated diagnostic used the unchanged formal `index-Cr_xKW9U.js` build on isolated loopback port 8910, with the new data directory `.archcanvas/m4-current-native-cancellation/documents`. It did not touch the user service at 8765, execute a model, modify product/probe source or a build, or rewrite a prior seal.

The CUA surface exposes one complete `drag(from,to)` and one complete `pressKey` operation, with no documented separate pointer-down, held move or pointer-up control. One MLP attempt ran atomic drag `[510,383]→[590,431]` concurrently with a 1500ms delayed `Escape`. Both API calls returned successfully. That is not delivery proof: the product observer recorded no Escape event. Its trusted pointerdown→pointerup interval was only 165.6ms, with eight held pointermoves, ten geometry frames and seven changed preview frames. The drag committed revision 0→1 and canvas delta `+100,+60`; two anchor bodies and camera stayed unchanged. Normal lostpointercapture followed pointerup. **Active cancellation remains unobserved and uncertified.** No additional rollback, persistence or history claim is made.

The complete 3,704,764-character textarea receipt was copied in 120,000-character read-only chunks after a direct copy was truncated to 200,011 characters. The invalid first copy remains as `atomic-drag-escape-truncated-copy.txt`; it is not validation input. `atomic-drag-escape-raw.json` parses successfully and the independent formal validator exited 0. The independent local audit recomputes trusted ordering, active-preview samples, committed geometry, two-sided unique matching, cadence, public final SVG equality and current asset/probe bindings without importing product/observer/validator code.

This new MLP session recorded 3,565 rAF callbacks over 59,411.6ms, interval cadence 60.0025Hz and p95 16.8ms. The actual held interval contained ten rAF observations at 60Hz. These are callback/DOM facts, not presented FPS or continuous input-to-paint. Document visibility stayed `visible`, iframe focus was false at both recorded endpoints, top focus true, while browser visibility capability returned false. Resolved font bytes and hardware remain unknown. It is a nonrandom new session and does not identify why earlier same-build observations were around 2Hz.

Only one of two eligible discrete inputs uniquely matched Event Timing: pointerup duration 24ms. The pointerdown native entry had duration 40ms and a null target token, so it cannot be borrowed into that matched subset. Thus 24ms is neither a complete interaction maximum nor representative latency/overall INP. No human participation, physical publication review, DenseStress300 performance certification or full performance acceptance is established.

The temporary tab was closed. No viewport override was applied. The measurement server was stopped with Ctrl-C and returned exit 130; the direct shell output contained `KeyboardInterrupt`. A capped AX read timed out after stop controls, but the completed textarea was subsequently read and preserved without restarting the session.

Artifacts: `atomic-drag-escape-raw.json`, `cua-operation-attempt.json`, `after-dom.json`, `atomic-drag-after.png`, `validator.stdout.json`, `independent-audit.json`, `environment-end.json`, and `session-process.json`. Reproduce the independent offline check with:

```bash
python docs/evidence/m4-current-native-cancellation-work/audit.py
node scripts/validate_input_observation.mjs docs/evidence/m4-current-native-cancellation-work/atomic-drag-escape-raw.json
```
