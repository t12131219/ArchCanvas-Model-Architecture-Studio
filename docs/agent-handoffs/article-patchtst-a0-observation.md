# PatchTST Article Input Observation

## Scope and Authorization

- Input category: external read-only development observation.
- Approved local root for this observation: `Article/PatchTST/PatchTST_supervised` relative to
  the user-provided ArchCanvas workspace.
- Selected entrypoint: `models/PatchTST.py:Model`.
- Execution and mutation: none. Stage 2 used AST parsing and byte reads only; no import, install,
  `sys.path` change, trace, or source write occurred.

## Reproducible Source Identity

The direct-binding snapshot on 2026-09-21 is
`sha256:29a21da6a010632a98c84799fb888c016224376dad4bba0ba19626b9a6d82706`.

| Relative file | Revision |
| --- | --- |
| `models/PatchTST.py` | `sha256:49d8bb865e1226d6338842f4b33c4bc6992cefb048dc2a4a5a8c410ca708586b` |
| `layers/PatchTST_backbone.py` | `sha256:df67173153787c2356bdfb6491159cd754332ef7382986efe879e1fbea8ebf26` |
| `layers/PatchTST_layers.py` | `sha256:21c06c70a90c60ee2a269b5c600c702834dea22cdfd72915e6b0f8b4a28db3f6` |

The symbol table resolves `PatchTST_backbone` and `series_decomp` from the selected entrypoint to
the two listed files. No transitive implementation topology is asserted.

## Provenance and Acceptance

`Article/PatchTST/README.md` identifies the upstream as
`https://github.com/yuqinie98/PatchTST` and identifies the ICLR 2023 paper. The archived project
root contains `requirements.txt` (`torch==1.11.0` among its declared dependencies), but no
root-level PatchTST `LICENSE`, `NOTICE`, commit hash, or tag was present in the checked local
archive. Third-party subdirectories have their own license files and do not establish the
provenance of the selected PatchTST sources.

Therefore this record is **not an A0 pass and not an A2 acceptance artifact**: it is a reproducible
development observation with incomplete license/revision provenance. It must not be copied into
fixtures or release artifacts until an upstream revision and license are explicitly registered.

The current static result is intentionally fail-closed: `Model.__init__` and `Model.forward` each
contain a condition on `self.decomposition`, so analysis reports
`DYNAMIC_CONSTRUCTOR_CONTROL_FLOW` and `DYNAMIC_CONTROL_FLOW`, with only input/output nodes. No
backbone, decomposition, or inferred branch topology is confirmed. This is an A1 capability-boundary
observation, not a visualization or code-editing claim.
