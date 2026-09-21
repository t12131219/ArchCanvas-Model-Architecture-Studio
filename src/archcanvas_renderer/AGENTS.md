# Renderer Rules

- Render only `PublicationIR` and `VisualScene`; do not derive source semantics or edit code.
- Keep SVG serialization deterministic and dependency-free unless a renderer ADR changes that rule.
- Validate scene-to-publication consistency before claiming an artifact is exportable.
- Visual previews, labels and routes must not imply additional Exact nodes or source operations.
- Update renderer tests and SVG goldens whenever geometry or serialization deliberately changes.
