# Terminal cleanup order regression

The v17 terminal-band follow-up ran between a parallel-lane displacement and
the original short-step simplification. In two source-backed LayerNorm LSTM
outputs it accepted a legal terminal band before the original simplification
could remove two short bends. The resulting final graph added four bends and
a 10 px near-parallel run without reducing length, contacts or crossings.

This was actual candidate acceptance, not budget exhaustion. The instrumented
LSTM initial stage ended with 216 validation and 443 quality-budget units;
the MI-LSTM expanded stage ended with 147/177. Their individual accepted
routes and remaining budgets are preserved in
`accepted-followup-causality.json`. Simply disabling the follow-up reproduces
all nine v16 metrics for both cases (`no-followup-standard-report.json`).
Requiring a prior accepted displacement would not fix this: both LSTM
displacements were accepted and still had close peer runs.

The isolated change moves the bounded follow-up into a second pass after all
original lane shifts and shortening finish. It reuses the remaining shared
budgets. Every accepted follow-up must retain the existing contacts/crossings/
weighted-crowding guards, length and point count, and additionally avoid
increasing close parallel run count/length or reducing the minimum close gap.
The old `qualityDoesNotRegress` policy remains unchanged; the added measurements
guard only this terminal pass. All source, gate, port, manual-knot and junction
validators still run. There are no model or case branches in the product patch.

All 32 actual routed stages pass. LSTM's four stages reproduce all nine v16
metrics. MI-LSTM's expanded/reopened stages shorten by 28 px with unchanged
bends, contacts and crossings, three fewer close parallel runs and 28 px less
close length. TimeMixer's original three depth-3 stages retain the 12 px
close-length improvement; the second pass also removes 14 px of close length
in three depth-2 stages relative to v17, with all other metrics unchanged.
`comparison.json` records the complete matched nine-metric comparison against
both frozen v16 and v17 reports. The actual standard/mixed reports preserve
input and loaded runtime hashes. Relative to v17, MI-LSTM has 28 px more close
length but two fewer bends; relative to v16 every measured metric is no worse.

The new `previewCleanupOrder.test.ts` reads the actual catalog's original LSTM
source-backed views and exercises the full `F.build`/`F.route` pipeline. It
checks that both original output bindings retain the simpler path, source
fields remain exact, all validators pass, and folding restores the geometry
and paths. It fails against the actual frozen v17 runtime and passes against
the isolated second pass. Together with the nine terminal-band, eight wire-
contact and nine spine tests, all 27 tests pass. The negative output, positive
test log and exact runtime/test hashes are retained here.

The isolated recursive overlay is SHA-256
`7f350b1ef7c04cab02212844667e414c75f0b6636b0aef55fa241bdc886f72fc`.
Other unchanged engine bytes are referenced individually from existing frozen
evidence in `runtime-tests-receipt.json`; the runner checks every hash. This
isolation precedes the final v18 cache-version update and does not attest later
product bytes. The formal product was not edited by this isolation task.

From this directory:

```bash
node run-regression.cjs
node run-regression.cjs --baseline  # Expected failure in the old cleanup order.
node run-regression.cjs --matrix --output /tmp/terminal-post-loop-standard
node run-regression.cjs --matrix --mixed --output /tmp/terminal-post-loop-mixed
```

No Python model source was imported or executed. The change adds no visibility
searches; candidate generation remains bounded to sixteen terminal-band
alternatives per eligible edge and shares the original cleanup budgets.
