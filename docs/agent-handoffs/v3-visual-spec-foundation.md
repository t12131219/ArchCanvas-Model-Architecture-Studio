# V3 VisualSpec Foundation Checkpoint

## Implemented locally

- Strict VisualSpec v1 with committed schema and Transformer/ResNet fixture goldens.
- Source-mapped publication nodes, edge semantics, unambiguous Exact port references,
  integrated composition and relative order constraints; invalid references fail closed.
- Engine analysis compiles and caches VisualSpec before producing the shared scene.
  Rollback restores its prior cache state with the other analysis artifacts.
- SVG repeat previews are explicitly non-executable schematic duplicates and no longer
  claim that every repeated block is an encoder layer.

## Not implemented or accepted

The existing fixtures do not prove a canonical L2-L4 child topology. Their repeat
expansion is still a visual preview, not inline model detail; direct full detail is
explicitly unsupported. Tier A approved configurations, four source ledgers, reference
discrepancy review, five model goldens, desktop direct-full E2E and Stage 6 external
acceptance are still required. Do not mark Stages 4 or 6 as V3 accepted from this work.

## Next implementation boundary

Build the Tier A module/tensor/edge/evidence/discrepancy ledgers from approved source
and selected configs. Only then add source-mapped child nodes and stable semantic ports
to the next VisualSpec version, followed by true inline layout and desktop controls.
