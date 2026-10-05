# Current-build native input diagnostic

This isolated observation uses the formal `ce7f7f733da28cb31ecff80ca029a53094e88f8451bffc3874f8167f80a07d00` frontend through `scripts/m4_input_harness.py` on loopback port 8907. It does not modify the product build or the user service at port 8765.

The raw textarea receipt records six ordinary browser operations on DenseStress300: a successful toggle, pan, one no-input drag, a successful drag, undo, and redo. `validator-process.json` records the validator exit and hashes. It reports 14 eligible discrete inputs, 10 matches and four matched interactions with a 2000 ms matched-subset p95. rAF cadence is approximately 1.98 fps, with idle cadence approximately 2.01 fps. These are Event Timing and DOM/rAF engineering observations. They do not certify presented paint, continuous input-to-paint, overall INP, fixed fonts/hardware, active held-input cancellation, or human acceptance.

The no-input attempt remains in the receipt and was not repaired. The successful drag, undo, redo, save, reopen, and direct document-store snapshot are retained separately. The service was stopped after capture; the browser tab was closed and the temporary viewport override was reset.
