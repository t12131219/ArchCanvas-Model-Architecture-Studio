# Compact source-backed 300-leaf workload preparation

One existing typed `move` moves the frozen grid's source-backed output by `(0,-28590)` world units. Its absolute position becomes `(80,1756)`,60 units below the network. The root scene height naturally shrinks from30346 to1756; scene bounds shrink from4588×30542 to4588×1952. The network remains `(80,254)` and4396×1442, all300 source-backed leaf scene objects remain exact, and the304 node identities/302edge identities remain exact.

The whole CanvasDocument equals its frozen predecessor after allowing revision4→5 and the output's layout move in its active and two saved frontiers. Architecture,sourceBindingDigest,IR,sourceFacts and canonical ports remain exact. Only `edge:303` changes path, from `M 4349 1666 V 16006 H 177 V 30346` to `M 4349 1666 V 1711 H 177 V 1756`; total centreline length decreases142405→113815 world units. This is a source-backed visual workload rather than a generated/executed model.

| Candidate viewport CSSpx | Fully inside leaf bodies | Minimum body CSSpx | Nominal13-unit font CSSpx |
|---|---:|---:|---:|
|672×711|300|24.356×7.784|1.632|
|3400×1900|300|139.707×44.649|9.362|
|3800×2100|300|156.621×50.054|10.495|

These are literal projection calculations, with the formal fit margins96×92 and1.2 zoom cap. They are not measured fonts or proof of readable300objects. The default672×711 figure remains too small for useful nominal text. Larger candidates still require actual browser/hardware/font and complete timing/input/visibility checks.

[Independent readback attempt2](independent-report-attempt-2.json) passes658/658 document/hash/geometry relations. Before and after have zero centreline intrusions through unrelated leaf bodies and zero proper crossings/positive overlaps among edges with no common endpoint. Endpoint-related peer pairs, outer-frame contacts, visible stroke widths/markers and glyph envelopes are not certified by this finite audit. Scene diagnostics remain the single static-source info entry, with no warning/error. A clear centreline and an info-only diagnostic do not approve global aesthetics.

The first independent attempt passes655/656: it accidentally disallowed the output's derived `localY` move despite allowing absolute `y`. Its [report](independent-report-attempt-1.json),[script](independent_readback-attempt-1.py) and log remain exact; attempt2 adds explicit local/absolute/port-y delta checks. Product/core/preparer output was not changed to fix that oracle.

[Input manifest](input-manifest.json) freezes26 files:18 formal pre-caption core files,one camera projection and seven previous workload files. The old workload files remain unchanged. The new candidate's renderer is the named frozen formal core, not the live resize-stage build; this preparation does not certify future/live router output.

No App/router/core or current documentation entry was edited. No user model was imported or executed; no browser capture/timing, real-font measurement, physical publication review, human trial or presented FPS acceptance occurred. M4 remains partial, M5 not_started, humans0. This is finite workload preparation only.
