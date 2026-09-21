# ADR 0001: Keep Publication And Scene State Separate From Exact IR

## Status

Accepted for Stage 4.

## Context

The source-backed Exact Architecture IR is the semantic record used for source navigation,
runtime evidence and transactions. A publication diagram needs pattern reduction, omission of
implementation details and visual controls such as repeat expansion. Adding those concerns to
Exact IR would let a presentation choice look like a source fact or a code-edit request.

## Decision

- `PublicationIR` is a separate, read-only reduction of Exact IR. Every Exact node and edge is
  represented by a member mapping or recorded in an explicit omission ledger.
- `VisualScene` is a separate layout document that maps each publication node and edge once.
- A repeat group's default publication form is collapsed. `StageLayout` accepts explicit expanded
  repeat group IDs and stores that choice only as `SceneNode.expanded`.
- Expanded SVG layer previews are visual grammar. They do not create Exact nodes, alter member
  mappings, change Publication IR, create a patch, or write user source.
- Unknown/non-repeat expansion requests and expanded non-repeat scene nodes fail closed.

## Consequences

Publication scenes are deterministic and can be exported without gaining source-write authority.
Stage 6 may persist the same visual state in `CanvasDocument`; it must retain the same separation.
The initial Publication/VisualScene v1 schemas are not yet released outside this repository, so no
migration document is required. Any future externally persisted or cross-host schema change needs
an explicit version and migration decision.
