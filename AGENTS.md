# ArchCanvas Engineering Contract

## Invariants

- Source evidence and Exact Architecture IR are authoritative; canvas geometry is not.
- Static analysis is the default. Never import or execute a user's project during analysis.
- Visual patches may only change `CanvasDocument` state and must not write model source.
- Semantic source edits must use prepare, verify, review, and explicit commit phases.
- Unsupported capabilities return a structured non-zero receipt. Never report a skipped gate as passed.
- Stdout from CLI commands is reserved for a single machine-readable JSON receipt; diagnostics go to stderr.

## Task Routing

- Protocol and validation work belongs in `src/archcanvas_core` and `schemas`.
- Python source discovery and recovery belongs in `src/archcanvas_python`.
- Command orchestration and receipts belong in `src/archcanvas_engine`.
- Skill routing stays concise in `skill/SKILL.md`; detailed contracts belong in `skill/references`.

## Validation

Run from the repository root:

```bash
python -m pytest
python -m compileall -q src tools tests
python tools/export_schemas.py --check
```
