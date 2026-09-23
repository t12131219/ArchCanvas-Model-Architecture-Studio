# Stage 2 Checkpoint: Generic Fallback

Status: generic source recovery and the opaque boundary contract are implemented. See `stage-2.md`
for the completed stage gate.

`archcanvas analyze --no-pattern-packs` bypasses all model-specific adapters and semantic gates. It
parses the selected entrypoint without importing the project and emits a semantically closed Exact
IR using generic calls, operators, tensors, and explicit opaque boundaries.

An opaque boundary records three independent states:

- `implementation_status`: `boundary-only` when static expansion stops;
- `semantic_status`: `unnamed` when no verified semantic pattern is active;
- `execution_status`: `unresolved` when static control flow cannot choose a realized branch.

It also preserves source evidence, input/output ports, symbolic unknown shapes, the unresolved
reason, and the remaining visual inspection capability. The pattern receipt reports `disabled`,
the annotation overlay is empty, and profile-specific validation is not run.

Automated acceptance covers both current Tier A fixtures: Transformer retains its recovered generic
operator graph, while Autoformer's conditional return is represented by an honest opaque boundary.
Both pass source identity and semantic closure with pattern packs disabled.
