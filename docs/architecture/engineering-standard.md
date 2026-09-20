# ArchCanvas Engineering Standard

## Purpose

This document defines the delivery standard for ArchCanvas. It takes inspiration from
Tavotto's repository maturity: clear subsystem ownership, layered verification, bounded
agent instructions, and explicit integration contracts. It does not import Tavotto's
feature scope, product design, protocol semantics, or implementation.

## Sources Of Truth

| Concern | Authoritative location | Rule |
| --- | --- | --- |
| User model semantics | User project source plus re-analysis | A canvas, cached IR, or patch never replaces source. |
| Cross-language protocol | `schemas/*.schema.json` | Python and TypeScript consumers must validate the same document shapes. |
| Python runtime behavior | `src/` and focused tests | Models are strict; protocol behavior is covered by positive and negative tests. |
| Product behavior | `PRODUCT.md` | User promise, supported boundary, and product invariants. |
| Product-stage plan | `ArchCanvasV2_2.md` | Stages define scope, entry criteria, and gates. |
| Current delivery state | `docs/implementation/STATUS.md` | This is a factual status record, not a wishlist. |
| Architecture decisions | `docs/adr/` | Breaking or non-obvious decisions receive an ADR before dependent implementation. |
| Acceptance evidence | `docs/acceptance/` and `tests/` | A claim is complete only when its named evidence exists and passes. |
| Agent behavior | `AGENTS.md`, local `AGENTS.md`, and `skill/` | Root rules route; local rules constrain a subsystem. |

## Repository Shape

The target tree in `ArchCanvasV2_2.md` section 16 is deliberately separated into core,
source analysis, framework adapter, publication, renderer, engine, desktop, MCP, skill,
fixtures, tests, and release tooling. Create a subtree only when it owns executable code,
contracts, or evidence. Empty folders and speculative transports conceal unfinished work.

## Completion Levels

Each feature must identify its strongest proven level. Higher levels cannot be claimed from
lower-level evidence.

| Level | Evidence | Example |
| --- | --- | --- |
| Protocol | strict model and schema tests | an invalid patch envelope is rejected |
| Fixture | deterministic source/IR/golden test | Transformer `nhead` candidate equals the oracle |
| Integration | two owned subsystems exchange a typed contract | engine receives analyzer result and persists it |
| Acceptance | user workflow test in its host | desktop reopens a persisted visual layout |
| Release | platform, security, license, and regression gate | signed artifact passes the release matrix |

## Interface Discipline

The future engine is the only policy authority for project analysis, persistence, source
transactions, and exports. Desktop, CLI, MCP, and Skill are clients. A client may render
or request an operation, but cannot write user source directly or create a second revision
history.

Every interface change requires:

1. a contract update in `docs/architecture/interface-reservations.md` or a versioned schema;
2. an owner and a negative-path behavior;
3. at least one producer/consumer test before UI exposure;
4. an ADR when compatibility, trust, or source-write semantics change.

## Documentation Discipline

Keep product behavior, engineering contract, and implementation status separate. Put
large, conditional instructions in focused references and link to them from the shorter
entry document. Do not turn release records, generated test reports, or unresolved design
questions into permanent API documentation.
