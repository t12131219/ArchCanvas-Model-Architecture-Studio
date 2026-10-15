# ASPP shared-spine tradeoff (v14 to v17)

This capture replays the actual `single-0-depth-2` frontier with the frozen v14 runtime and formal v17 runtime. Both pass all source, geometry, routing, gate and junction checks. The source authority is identical. The three changed matrix stages (`single-0-depth-2`, `mixed-0-depth-2`, `single-0-reopen`) have the same quality values and the same tradeoff.

The real external producer `aspp.input` feeds five independent branch modules using one source value. The central `rate12` input and the final `project → output` now follow their shared vertical axes. They each remove two bends; the `rate12` input also removes two crossings with licensed same-value input branches. These are presentation changes within existing source bindings, not newly combined values.

The frame grows 16px and its branch group shifts 16px to align that shared spine. Across the six `input → branch/resize` routes, three shorten 27px and three grow 27px, for net zero. Five independent branch/resize → concat approaches each grow 19px, while `project → output` shortens 8px. Net total length is therefore +87px. Total bends fall 46→42. Total strict crossings fall 12→10; the remaining 10 are all between independent concat inputs, so unrelated crossings and contacts stay 10. No new independent contact, touch or near-parallel run is introduced; both versions have zero near-parallel runs in this frontier.

This is a local length-versus-straightness tradeoff from a licensed real-producer spine. It is retained for explicit review, rather than represented as an across-the-board improvement. Actual routes, node changes, bindings, runtime hashes, capture hashes and contact pairs are retained in `aspp-v14-v17-route-diff.json` and the two capture folders.

Final v18 confirmation: `aspp-v17-v18-route-diff.json` compares the actual v17 and v18 frontier. All nodes, source authority, edge routes, bindings, ports and gates are byte-identical, with no added or removed contact. The exact +87px / −4-bend tradeoff therefore remains the final behavior.
