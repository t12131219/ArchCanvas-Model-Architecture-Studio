# ADR 0002: Source-Mapped VisualSpec Foundation

## Status

Accepted for the V3 migration, without claiming Stage 4 or Stage 6 acceptance.

## Context

The existing Stage 4 layout inferred order and presentation directly from Publication IR.
V3 requires an independent, renderer-agnostic composition contract between Publication IR
and VisualScene. The existing fixture proves only a shallow encoder chain; it does not
prove the internal attention, residual or tensor graph required for L2-L4 expansion.

## Decision

- Add `VisualSpec` v1 as a strict, separately versioned protocol. It keeps integrated
  composition, canonical Publication IDs, semantic visual classes, source-backed ports,
  edge types and relative order constraints. It carries no renderer coordinates.
- Compile it only after validating Publication-to-Exact member and omission mappings.
  Ambiguous grouped edge ports remain unspecified instead of fabricating a stable port.
- The Engine layouts consume this contract and cache it beside the shared VisualScene.
  SVG and Desktop continue to consume that same scene.
- The initial contract has no source-mapped children. It rejects inline expansion and
  `direct_full_detail_supported=true`; the old repeat preview remains a visual-only
  compatibility behavior, not V3 canonical expansion. A future version must model and
  validate children and their edges before enabling full detail.

## Consequences

The new cache artifact is additive; existing RPC and CanvasDocument schemas do not
change. Consumers must not interpret the V3 foundation as Tier A completion. The
VisualSpec schema and its fixture goldens are committed with the producer/consumer tests.
