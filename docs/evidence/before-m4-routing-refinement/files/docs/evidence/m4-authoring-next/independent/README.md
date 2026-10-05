# Independent authored-draft acceptance

The independent nonexecuting graph/source/IR audit passed **8 positive networks,
50 invalid drafts, and 21 deliberately corrupted source/IR oracle controls**.
The actual random-port HTTP suite passed **7/7**, with no skips, against a durable
24-file formal Python source/test copy. These checks do not establish browser,
runtime, numerical, publication or human acceptance. M4 remains open.

`contract.md` was written before the implementation adapter. `casebook.py` supplies
concrete hand-calculated tensor shapes and original graph relations, covering all
17 enabled authoring kinds. `oracle.py` imports no product authoring registry,
shape propagator, generator, verifier or expected delta. It parses actual Python
constructors and straight-line dataflow, then checks separately re-analyzed
canonical inventories, parameters, port identity/direction/role/ordinal,
containment, instance/call distinctions, exact tensor bindings and fanout tensor
bijection. It checks SourceFacts category/evidence and named return slots.

The worked examples cover distinct Linear instances with equal Chinese labels,
MLP activations, Conv/BatchNorm/pool/Flatten, Embedding→LayerNorm, residual bypass,
negative and zero Concat axes, grouped/dilated convolution plus ceil pooling,
and two identical Add expressions producing separate canonical calls and outputs.
The 50 invalid drafts cover mode/envelope forgery, ports, duplicates, cycles,
boolean/fractional/nonfinite parameters, width/channel/shape/dtype conflicts,
constructor constraints, element/revision budgets and incomplete/disconnected
generation. Each base graph succeeds before its mutation is counted as rejected.

The 21 oracle controls are saved under `oracle-counterexamples/`. Some mutations
re-analyze changed source and remap occurrence IDs by source line/kind, so changed
Concat axes and operand order cannot be rejected merely because a fingerprint
became stale. Others alter exact parameters, ports, output slots, node inventory,
tensor identities or mapped typed shapes. Extra executable statements/imports
and hidden constructors are rejected by the syntax boundary. The controls do not
call product `verify_generated`; their failures show that this external oracle
detects actual corrupted facts.

An early valid Concat draft with declared `dim=-1` exposed a real extra Unary node
in its generated static IR. The backend fixed generation by normalizing the
proved rank-2 axis to equivalent source `dim=1`, while retaining the draft's -1
and recording `scalarNormalizations`. The independent AST check expects that
concrete equivalent axis. No frontend or failed prototype code was used for the
repair. Initial `inplace:false` and scalar spatial-parameter examples were adapted
to the public draft schema: ReLU/SiLU permit no parameter, Dropout permits p only,
and spatial fields use two-element arrays. Those packaging failures were not
counted as product bugs or negative coverage.

The separate HTTP tests are in
`tests/test_authoring_http_independent.py`. They verify missing/invalid mutation
sessions and foreign origins fail without writes; draft CAS and concurrent
clients have exactly one winner; incomplete drafts save but cannot generate;
source documents/drafts cannot be substituted and source facts remain immutable;
a new service instance reopens the exact draft and rejects the old session token;
generation is text-only, and registering it creates a fresh managed project.
Original imported source, its registered copy and a pending-review sentinel retain
their hashes. Editing the draft changes generated source and source/IR/draft
digests without changing imported artifacts. The pending sentinel verifies byte
preservation only; it is not a real verified/approved source transaction.

`http-tests-sandbox.txt` records the initial restricted-socket skips and is not
counted as passing HTTP coverage. `http-tests-permitted-final.txt` records the live
7/7 run; `http-tests-frozen.txt` repeats the suite from `source-snapshots/` in a
permitted host. `http-source-context.json` binds the snapshot, log and before/after
24 current/archive hashes. All service data and ports are temporary and isolated;
no existing service or browser is operated.

`baseline-investigation.json` records the read-only initial source contracts and
nonexecuting handwritten constructor counterexamples. The static frontend can
recognize invalid constructor arguments, so source roundtrip cannot alone prove
parameter/type correctness. The real analyzer's source recognition is not a
runtime constructor test. Embedding index values, numerical stability, training,
checkpoint compatibility and arbitrary symbolic shape cases remain outside this
audit. No model import or model execution occurs.

Run the independent static audit from the formal project:

```bash
PYTHONPATH=src .venv/bin/python docs/evidence/m4-authoring-next/independent/audit.py
```

Run the HTTP suite on a host permitting loopback sockets:

```bash
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -p test_authoring_http_independent.py -v
```

`audit.json` and the final `manifest.json` bind concrete source/tests/expected-case
bytes and generated/control artifacts. Old routing/UI seals are untouched and no
browser coverage is inherited.
