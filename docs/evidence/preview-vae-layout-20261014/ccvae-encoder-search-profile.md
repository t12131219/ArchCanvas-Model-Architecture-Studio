# CCVAE encoder search diagnostic

A single disposable VM call to `SummaryRecursive.route` used the raw mixed
encoder graph `v14-ccvae.encoder-before.json.gz`. Runtime model Python was
neither imported nor executed. The product files were read and instrumented
in memory only; no product file was changed by this diagnostic.

The instrumented call took 19.08 s. Edge `route-0039-38` accounted for 16.67 s
in the preferred lane attempt, which exhausted 224 searches and returned no
path; the same edge's stroke-safe retry took 0.70 s and succeeded after seven
searches. The completed graph passed source, layout and edge validation with
zero route failures.

There were 71,081,211 obstacle clipping calls. Duplicate gate coordinates
produced 66 zero-length searches (`491 → 491` and `475 → 475`, both at
`y = 1100.5`), consuming 2.69 s. Identical gate-to-gate legs repeated for
each candidate port pair, and several final legs repeated for four source
ports. This identifies a generic redundant-search opportunity: an exact
coincident-point shortcut and per-route-edge caching of identical search
inputs, including failed searches. Such caching must include obstacle
geometry, incoming/outgoing headings and any applicable terminal-stem
exception; it must remain local to one solve.

This is an instrumented diagnostic, not a browser latency result. The first
run did not record source hashes at load time, so its runtime bytes cannot
be attested retrospectively. Do not use later file hashes as the identity
of this run. The raw timing report is retained as
`ccvae-encoder-search-profile-unattested.json`; the script was subsequently
updated to record source and input hashes before loading the VM on any
future run.

The authorized follow-up run after the exact coincident-point shortcut and
bounded per-route-edge memo took 5.003 s. The dominant preferred attempt
took 2.635 s and performed 19 actual searches, followed by a 0.627 s successful
stroke-safe retry. Obstacle clipping fell to 8,784,261 calls. The final graph
again passed source, layout and all 24 edge checks, with zero routing
failures. `ccvae-encoder-search-profile-memo.json` records every runtime file
hash and compressed input hash captured before loading/evaluating those
bytes. The new memo key was checked for obstacle geometry, signed headings,
and terminal-stem exceptions for unmarked legacy peers; it caches failure
and stays bounded to 256 entries in one route solve.
