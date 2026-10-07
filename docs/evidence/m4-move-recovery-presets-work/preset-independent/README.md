# Independent composite-preset static audit

This AI subagent audit checks the actual new frontend `insertDraftPreset` API and the formal backend's generated Python. It is separate from the implementation agent's focused tests. No user model or generated Python was imported or executed, `torch` was absent from the audit processes, and no dependency was installed. It is not a browser, numerical, novice-user, or human-publication acceptance record.

The first primary attempt completed all three stages with exit 0. A later supplemental IR audit had one path-adapter failure before graph checks; that failed directory and script remain preserved. The corrected supplemental attempt uses a fresh directory and completed with exit 0.

## Results and denominator

| Check | Actual coverage | Result |
| --- | --- | --- |
| Frontend presets | 3 standalone programs, 3 twice-inserted programs, 6 insertions into separately identified existing handwritten programs, 1 mixed-three program, 1 mixed-six program with repeated default UUID allocation | 14 actual draft snapshots |
| Declared shape and dtype | All 170 node declarations across those 14 programs, including Inputs and Outputs | Exact match to handwritten shape calculations; all float32 |
| Frontend tensor graph | All 148 declared connections with ordered source/target ports | Exact match to handwritten graph inventory |
| Python source | Every constructor, type, literal parameter, explicit float32 constructor dtype, forward producer, ordered Add operand, named return key and producer | 14 complete AST audits passed |
| Identity and atomic/history behavior | Restarted deterministic allocation with collisions, independent existing draft IDs, preservation of old nodes/edges/header, one history entry with undo/redo, invalid or late colliding IDs, unavailable catalog and invalid position | 23 actual checks passed; snapshots preserved |
| AST oracle negative controls | Wrong type, parameter, dtype, forward producer, output key, return producer, extra assignment; additionally swapped residual operands | 22 defects rejected |
| Independent observed IR | 184 actual IR nodes, 178 edges (148 graph edges plus 30 Input→root bindings), 318 exact ports, 140 producer tensors | 14 complete IR audits passed |
| IR oracle negative controls | Lost residual edge role, wrong residual port ordinal, wrong named output path, split fan-out tensor identity | 4 defects rejected |

Counts above are observations across 14 separately saved programs. They are not a claim of 170 unique product operators or human test participants. The 23 frontend checks and 22/4 oracle controls are separate denominators and must not be added to the product's regression-test totals.

## Handwritten network contracts

| Program | Declared shapes in node order | Named result |
| --- | --- | --- |
| MLP | Input `[1,16]` → Linear `[1,32]` → ReLU `[1,32]` → Linear `[1,4]` → Output `[1,4]` | `[1,4]` |
| CNN | Input `[1,3,32,32]` → Conv2d `[1,8,32,32]` → ReLU `[1,8,32,32]` → MaxPool2d `[1,8,16,16]` → AdaptiveAvgPool2d `[1,8,1,1]` → Flatten `[1,8]` → Linear `[1,4]` → Output `[1,4]` | `[1,4]` |
| Residual MLP | Input `[1,16]` → Linear `[1,32]` → ReLU `[1,32]` → Linear `[1,16]` → Add `[1,16]` → Output `[1,16]` | Add left is the main projection; right is the original Input |
| Handwritten existing network | Input `[2,7]` → Identity `[2,7]` → Output `[2,7]` | Preserved when any preset is added |

The CNN spatial arithmetic is `floor((32 + 2×1 − (3−1) − 1)/1) + 1 = 32` for convolution, then `floor((32−2)/2) + 1 = 16` for pooling. Flattening dimensions 1 through -1 multiplies `8×1×1` to 8. ReLU, Identity, Add and Output preserve the specified shapes. These facts derive from declarations and operator contracts; they are not runtime observations.

`expected-contracts.json` was handwritten from the requested networks before sampling the product. The oracle does not import the backend's `_name`, `_infer`, `_source` or expected-graph functions. It obtains actual frontend drafts through the exported API, calls the formal backend as the system under test, and parses generated text with stdlib AST. The AST comparison starts at the actual named return dictionary and traverses expected producers, so it does not infer correctness merely from operation counts or generated symbol hashes. The supplemental IR audit recovers node identities from independently checked source expressions, Input symbols and named `outputPath` keys; it never uses the generation receipt's `nodeBindings`, `portBindings` or verifier result as its binding oracle.

All inserted graphs remain self-contained: no new edge binds an existing node, old graph objects remain exact, fresh identities do not collide within the draft, and a whole insertion can be undone/redone in one draft-history step. Those are direct function-call/history observations; the browser must separately establish that a palette click or drag invokes the same behavior and presents usable layout.

## Frozen evidence and commands

- `attempt-1/command-receipts.json` and the three `stage-*-output.txt` logs record the actual catalog → frontend → backend/AST commands and exit codes.
- `attempt-1/frontend-drafts.json` holds all actual drafts, insertion before/after snapshots, receipts and identity/history records.
- `attempt-1/backend-ast-audit/` holds all 14 validation receipts, generation receipts, exact generated source texts, independent AST mappings and negative-control source texts.
- `attempt-1/product-source-snapshots/` preserves the four exact audited product source files.
- `attempt-1/oracle-source-snapshots/` preserves the five primary oracle/command files immediately after the primary success.
- `attempt-1/ir-port-audit/` is the failed relative-path adapter attempt. No graph checks ran there. Its failed script and exit-1 receipt are preserved.
- `attempt-1/ir-port-audit-2/` is the corrected 14-program IR endpoint/role/tensor audit and its 4 negative controls.

From the formal project root, a fresh primary output directory can be generated with:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python docs/evidence/m4-move-recovery-presets-work/preset-independent/run-audit.py docs/evidence/m4-move-recovery-presets-work/preset-independent/<fresh-attempt>
```

The supplemental audit reads the saved frontend and generation receipts:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python docs/evidence/m4-move-recovery-presets-work/preset-independent/audit-ir.py --input docs/evidence/m4-move-recovery-presets-work/preset-independent/attempt-1/frontend-drafts.json --receipts docs/evidence/m4-move-recovery-presets-work/preset-independent/attempt-1/backend-ast-audit --output docs/evidence/m4-move-recovery-presets-work/preset-independent/<fresh-ir-attempt>
```

Every output directory/file uses create-exclusive writes. The top-level `evidence-manifest.json` binds this complete audit package and the actual product bytes. The failed attempt is included and is not relabeled as success.

## Limits

This verifies complete static declared networks and source/IR faithfulness. It does not establish numerical behavior, training/evaluation, memory allocation, torch-version compatibility, native pointer input, browser visibility, visual overlap at publication sizes, research-user task success, or M4 completion. No imported source project, generated runtime, or old prototype was modified. The audit wrote only this new evidence directory.
