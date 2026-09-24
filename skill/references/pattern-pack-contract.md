# Pattern Pack Contract

Pattern Packs interpret completed Exact IR; they do not build or repair it. Apply predicates in
this order: structure, dataflow and ports, shape and axes, sharing and control flow, then weak name
hints. A name hint cannot rescue any failed hard predicate.

Use builtin packs by default. Enable a workspace pack only with its explicit path and locked SHA-256
digest. Treat session candidates as preview-only: review their match basis, unproven predicates,
counterexample risk, annotations, and Exact IR digest invariance before any separate approval or
installation step. Executable third-party matchers are unsupported.

On multiple unresolved matches or conflicting interpretations, retain the generic graph and record
`ambiguous_pattern`. Pattern recognition never grants source-edit permission; source changes still
require a registered transform and the full transaction gates.
