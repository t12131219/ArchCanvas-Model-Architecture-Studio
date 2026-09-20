# ArchCanvas Engineering Rules

## Product Boundary

ArchCanvas is a source-aware model architecture studio. User source code remains the
semantic source of truth. Visual state is never a substitute for the Architecture IR,
and no source-changing workflow may bypass candidate generation, validation, and an
explicit commit.

## Environment And Baseline

Use `TFB_py311` for Python work:

```bash
conda run -n TFB_py311 python -m pip install -e '.[dev]'
conda run -n TFB_py311 python -m pytest
conda run -n TFB_py311 python -m compileall -q src tools tests
```

Before editing, inspect `git status --short` and run the narrowest relevant test.
Preserve unrelated worktree changes. Do not add a virtual environment, cache, generated
runtime output, or third-party source to version control.

## Non-Negotiable Invariants

- `archcanvas_core` is framework-neutral and must not import LibCST, PyTorch, UI, engine,
  desktop, or MCP packages.
- Exact Architecture IR, Publication IR, and CanvasDocument remain independent models.
- Default commands that prepare code changes are candidate-only. Commit paths re-check
  source revision immediately before atomic replacement.
- Schema, Pydantic model, fixture, and golden changes travel together. A protocol change
  requires a versioning or migration decision in `docs/adr/`.
- Unknown, ambiguous, stale, or unvalidated evidence fails closed; do not manufacture a
  confirmed architecture fact or an editable source anchor.

## Routing

| Work area | Read first | Owns |
| --- | --- | --- |
| Product behavior and non-goals | `PRODUCT.md` | user promise, supported boundary, source-of-truth rules |
| Protocols and models | `docs/architecture/engineering-standard.md` | schemas, core models, canonical JSON |
| Future boundaries | `docs/architecture/interface-reservations.md` | RPC, workers, desktop, MCP, Skill contracts |
| Source recovery and transforms | `ArchCanvasV2_2.md` sections 0-14 | anchors, identity, candidate transforms |
| Stage planning | `docs/implementation/STATUS.md` | current scope and next entry criteria |
| Tests and release evidence | `docs/acceptance/README.md` | corpus, golden, integration, release gates |
| Local rule additions | `docs/rules/README.md` | scoped rules and future subsystem `AGENTS.md` |
| User-facing agent workflow | `skill/SKILL.md` | source-aware analysis and safe edit behavior |

When a subsystem becomes real, add a concise local `AGENTS.md` in that subtree. It should
link to focused rules rather than repeat these repository-wide invariants.
