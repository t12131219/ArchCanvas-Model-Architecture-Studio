# Independent authored-draft acceptance contract

This is an acceptance contract written before the implementation's test adapter.
It is not product capability evidence. The exact draft API is supplied by the
backend author; the expected networks, parameter outcomes and counterexamples
are authored separately from that implementation. No model execution, browser
operation, dependency installation, source writeback or old frozen-evidence
rewrite is performed by this review.

## Baseline evidence and scope

The current source-bound `CanvasDocument` embeds immutable analyzed Architecture.
`DocumentStore.put` rejects changed architecture/sourceBindingDigest after the
first save; visual undo does not change source bytes. `Workspace.register` accepts
exact source text/digests and writes a fresh managed copy, not a filesystem root.
Current Studio's empty state is a source-loading failure/reconnect state; it does
not establish blank model authoring. `ArchitecturePort` carries direction, role
and ordinal, with no tensor shape/dtype contract.

`baseline-investigation.json` binds the inspected formal source hashes and six
handwritten nonexecuting AST probes. The analyzer accepts negative Linear width,
boolean width, out-of-range Dropout probability, zero Conv2d kernel and negative
LayerNorm epsilon as recognized constructor facts. An unknown constructor is
retained opaque. Recognition and source roundtrip alone therefore cannot certify
parameter validity or executable tensor compatibility.

The proposed new API uses a separately identified `mode: authored-draft`
envelope. The initial 17 kinds are Input, Output, Linear, ReLU, GELU, SiLU,
Identity, Dropout, Flatten, Conv2d, MaxPool2d, AdaptiveAvgPool2d, BatchNorm2d,
LayerNorm, Embedding, Add and Concat. MHA/LSTM are outside this authoring scope.
The old analyzer registry is not a module-palette support matrix. Weighted
modules generate float32 state; their input contract requires float32, while
Embedding requires int64 indices. This is a declared dtype restriction, not a
runtime observation. Every supported node must reach an Output before code
generation. Incomplete drafts may be saved but cannot be presented as a complete
nn.Module or source-backed Architecture.

## Mandatory outcomes

1. **Mode and authority:** blank authoring creates a new identity and never
   accepts/relabels a source-bound CanvasDocument as editable model structure.
   A source-mode imported graph cannot bypass the registered reviewed source
   transaction path by passing its embedded graph to authoring operations.
2. **Stable identities and ports:** repeated equal labels/kinds create distinct
   instances/calls. Node IDs, not label text or array order, identify bindings.
   Connections resolve exact `(nodeId, portId)` direction/type contracts, and each
   input port has at most one producer. Input fanout retains one producer/tensor.
   Foreign same-named ports, reverse ports and arbitrary undeclared ports fail.
3. **Draft validity:** malformed fields, duplicate IDs, NaN/Infinity,
   booleans masquerading as numbers, unsupported kinds/parameters, cycles,
   self loops and multiple producers fail without mutation. Intentionally
   incomplete valid drafts remain incomplete. Generation rejects missing
   required inputs/outputs, unbound nodes and unreachable branches.
4. **Parameter and tensor validity:** constructor parameters enforce documented
   framework ranges before generating Python. Shapes are declared static
   contracts with explicit known/unknown scope, not measured execution. The
   independent cases use concrete hand-calculated outputs; they do not copy the
   implementation's propagation formulas. Add requires matching shapes/dtypes
   within the declared no-broadcast subset; Concat checks non-axis dimensions
   and the normalized axis, preserving ordered a/b inputs. Weighted dtype and
   Embedding index restrictions are honored.
5. **Generated source integrity:** a complete draft generates a fresh standalone
   Python source and exact entry with deterministic graph-node bindings. An
   independent restricted AST inspector checks the actual constructors,
   parameters, dtype literals, module uniqueness, call arguments, Add operands,
   Concat axis/order and outputs. It rejects extra executable code, silent
   Identity substitution, hidden modules, reused instances and ignored nodes.
   The source is parsed and analyzed, never imported or executed by this review.
6. **Independent roundtrip:** expected graph connections come from hand-authored
   case data. Fresh generated Python is re-analyzed through the formal frontend;
   every draft semantic node maps to exactly one appropriate canonical node.
   Exact ports, producer/tensor identities, call/instance distinctions,
   parameters, containment and output slots must match. Extra root-interface
   bindings are checked separately, not discarded indiscriminately. The
   frontend's inability to record functional Concat `dim` is covered by AST
   inspection rather than assumed to have been proved by IR equality.
7. **Persistence and freshness:** backend authoring CAS saves the whole draft,
   including semantic nodes/edges/parameters and authored positions. Reopening
   from a new store/service instance recovers the same values and identities.
   Stale revisions and forged modes fail while stored bytes remain unchanged.
   Generated source/Architecture receipts bind the exact saved draft revision;
   old generated artifacts cannot masquerade as output from an edited graph.
8. **Source separation:** generation writes no imported original, registered
   source copy or transaction files. Registering generated source produces a
   new managed project, independent of imported project IDs and sources.
   Before/after hashes cover the imported original, its managed copy and any
   existing pending review; a successful draft request is not source approval.
9. **UI and export boundary:** browser tests must separately establish visible
   creation/parameters/connections/deletion, undo/redo and reopen. The model
   draft and its visual operations must not use a stale compiled Scene for
   export. CPU/HTTP checks here cannot certify those interactions or publication
   readability, and AI observations do not count as real human tasks.

## Deliberate failures required of the oracle itself

The inspector must reject changed constructor width/bias/probability/dtype,
swapped fanout/binary operands, changed Concat dimension, shared two-module
instance, omitted node, extra hidden node, source with side effects, duplicate
canonical binding and inconsistent tensor identity. At least one accepted
positive source and each changed negative are saved as distinct artifacts. An
oracle that only echoes `verify_generated` or compares generated source with
another source generated by the same backend cannot establish independence.

Product limitations may reduce the advertised scope. They cannot be turned into
passed runtime, source-review, browser or human gates. M4 remains open.
