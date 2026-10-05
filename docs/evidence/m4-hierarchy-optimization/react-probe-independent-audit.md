# Independent React hierarchy probe audit

Status: passed within the scope below. All 53 input files were parsed from the same bytes used for their first SHA256 binding and were unchanged on final re-read.

The raw browser receipt contains 18 rounds: one initial render, five stable parent-state updates, nine replacement/visual-state controls, and three actual tree callbacks. All 17 input receipts record trusted native clicks. Actual collected URL: `http://127.0.0.1:8890/react-probe-dist/`.

The independent Python expression model reproduces every recorded id/label/children count and every visible tree fact. Initial old/new reads are 49,401/3,043; each of five stable updates is 49,401/0. Selection and document replacement refresh the new tree with 2,739 reads. Same-ID label/repeat/topology replacements each refresh it with 3,042 reads. The property counts include Proxy overhead and have no timing meaning.

All 18 browser-reported exact DOM comparisons and paired hashes agree. The raw receipt stores hashes, lengths and visible facts, but omits full innerHTML strings; this audit therefore does not independently re-hash the DOM itself. The 18 rounds do not establish 18 complete Studio tasks.

Archived old function bytes, current component/type/icon copies, source-bound Stress300 fixture, product App and production build, generated legacy module, compiled outputs, browser embedded bindings and preparation snapshots all match. Current formal product JS is bound to SHA256 `2c769087f0765ba47892e9f26f12a19e4336ec12573dce5859ac636e310f446c`. Raw is 708,471 UTF-8 bytes, SHA256 `40f6608151b04fc57df6a2e3b3a6574caf65c5082ac28802b9080809aef8d98f`.

The controls simulate parent updates; they do not perform camera or node gestures. The same-ID architecture variants are synthetic inputs and preserve original source bytes/digest fields rather than claiming freshly analyzed IR. The later Linear 3 selection callback refreshes both trees, but Linear 3 is absent from the four retained target fact snapshots.

No FPS, paint, presented frames, latency, human participant, or publication approval follows from this evidence. The audit executes neither the browser nor a model.
