# ArchCanvas User Workflow Contract

## Capability Check

Call `archcanvas_health` once only when the tool is available. Use the returned capability set
to select the workflow. A missing tool means the current host has not loaded the ArchCanvas
plugin; a reported unavailable capability means that the installed engine does not support that
operation. Neither condition permits a substitute source write or invented result.

## Read-Only Analysis And Rendering

For an approved project root, use `archcanvas_open_project` followed by
`archcanvas_analyze`. Present unresolved facts, confidence, and the distinction between Exact
Architecture and Publication View when that distinction affects the user's request. Use
`archcanvas_render_publication` or `archcanvas_export` only after their inputs reference the
current analyzed revision.

Analysis and export do not modify user source. A visual move, annotation, or layout adjustment
uses the visual-state capability and cannot change an ArchitecturePatch.

## Architecture Edit

For a parameter or structure edit, use this exact order:

1. analyze the current source revision;
2. request `archcanvas_plan_patch` and inspect provenance, risk, and candidate diff;
3. request `archcanvas_validate_patch` and report blocking issues, shape/runtime evidence, and
   observed Graph Delta;
4. call `archcanvas_commit_patch` only after the user explicitly asks to commit the validated
   candidate;
5. re-analyze and report the new source revision and refreshed architecture state.

Do not commit on a stale source revision, ambiguous identity, missing evidence, a blocking
report, or a user request that only asks to preview, plan, validate, render, or export.

## Failure Handling

Use the engine's structured code and message. Do not retry a failed commit without a new
analysis when the failure is stale source, stale anchor, fingerprint mismatch, ambiguous
identity, unexpected Graph Delta, or failed runtime/shape validation. Do not auto-authorize a
project root or weaken validation in response to a failure.
