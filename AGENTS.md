# ArchCanvas implementation direction

The user identified `ArchCanvas_Model Architecture Studio_Temp` as a failed version. The formal project should be written from scratch.

- Define the formal schemas, runtime, Studio, and tests independently from requirements, official framework contracts, and the licensed reference projects.
- Treat the failed prototype as low-confidence historical evidence and a source of failure cases. Do not migrate its complete pipelines, maintain its internal v1/v2 compatibility, or use it as the default runtime or fallback.
- Consult a small code candidate only when its purpose and dependencies are understood. Reuse requires independent evidence appropriate to its risk, a clear adaptation to the new contracts, and a recorded reason/source. Its own tests, README, or demo success are insufficient alone.
- Keep formal builds and execution independent of the prototype directory, its interpreter, artifacts, and source packages. Verify resolved runtime paths and package provenance; do not execute an installed entry that resolves to the failed prototype as though it were the formal product.
- No prototype code candidate is currently certified for reuse. Preserve that status until evidence is recorded; routine justified reuse does not introduce a separate user approval step.

The product is a portable Skill for Codex, Claude Code, and the official DeepSeek Harness, backed by one shared runtime and Studio. Publication quality, object/legend editing, in-place expansion, spatial continuity, and faithful export are early acceptance gates.

Visual gestures and language edits share the same CanvasDocument, typed operations, and undo history. Visual edits do not write model source. Semantic changes use supported intents, isolated preparation, independent verification, concrete human review, and guarded commit.

The source-tree `skills/archcanvas` launcher binds to this formal checkout; verified installations bind to their embedded runtime. Read the actual doctor/capabilities response before claiming a command, catalog size or editor function. Instruction-only copies without a binding cannot deliver a canvas. Historical package and host evidence do not certify current development bytes.
