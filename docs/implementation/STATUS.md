# Implementation Status

## Current State

The repository has completed fixture-backed implementations for Stages 1 through 4. It is not a
complete ArchCanvas product: Engine/RPC, persistence, desktop interaction, structural editing,
MCP transport and release hardening have not started.

## Completed In Current Worktree

- Stage 1: strict Source Identity, Exact Architecture IR and Patch Protocol schemas; a
  candidate-first, atomic, fixture-scoped `set_parameter` transaction with fail-closed negatives.
- Stage 2: bounded read-only PyTorch AST recovery, project discovery, source anchors, identity
  reconciliation, module containers, common flow patterns, capabilities and fixture goldens.
- Stage 3: explicit opt-in isolated FX/export workers, revision-bound runtime evidence, coverage
  gaps and shape validation. Runtime evidence cannot replace source anchors.
- Stage 4: Publication IR and VisualScene protocols, conservative Transformer repeat and residual
  stage reductions, node/edge omission ledger, deterministic SVG, preflight, and fixture goldens.
  A repeat group has a default collapsed scene and an explicit visual-only expanded scene; neither
  state changes Publication IR, Exact IR or source bytes.

## Scope Boundaries

- Static and runtime validation evidence currently cover repository fixtures. Article projects are
  read-only observations until separately approved A0-A6 evidence exists.
- Publication reduction supports declared Transformer repeat and residual-stage patterns. It does
  not claim a complete paper diagram for arbitrary Python or arbitrary PyTorch code.
- The current CLI is fixture-scoped. It is not an Engine API and must not be represented as a
  general project editing workflow.

## Next Entry Criteria

Before Stage 5 starts, commit the reviewed Stage 3/4 schemas, source, tests and goldens from a
clean worktree. Stage 5 then owns the only policy entrypoint: approved project manifests,
environment selection, cache/history, refresh orchestration and typed Engine RPC integration
tests. Desktop, MCP and visual persistence must remain clients of that Engine.
