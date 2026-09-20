# Interface Reservations

This is a contract reservation, not an implementation inventory. An interface listed here
becomes callable only after its stage has a versioned request/response schema, owner,
negative-path tests, and implementation. Clients must treat unimplemented interfaces as
unavailable rather than emulating success.

## Engine RPC v1

**Owner:** `archcanvas_engine` (Stage 5)

All clients use typed RPC envelopes with `request_id`, `protocol_version`, `project_id`,
`source_revision`, and structured error codes. The reserved operations are:

| Operation | Input | Output | Commit authority |
| --- | --- | --- | --- |
| `health` | host capability query | engine readiness and capability set | none |
| `open_project` | approved project root | manifest and project session | none |
| `analyze_project` | session plus analysis options | Source Identity and Exact Architecture IR | none |
| `render_publication` | Architecture IR revision and view options | Publication IR and VisualScene/SVG reference | none |
| `save_visual_patch` | CanvasDocument or VisualPatch | persisted visual revision | visual state only |
| `plan_patch` | ArchitecturePatch | candidate diff and validation plan | none |
| `validate_patch` | candidate reference | validation reports and observed delta | none |
| `commit_patch` | validated candidate plus explicit confirmation | new source revision and refreshed IR | engine only |
| `export_artifact` | scene or publication revision and format | artifact reference and preflight report | none |

`commit_patch` is unavailable until Stage 7. It must reject an absent explicit confirmation,
stale revision, missing validation report, or non-zero blocking report.

## Runtime Worker v1

**Owner:** `archcanvas_pytorch.runtime` (Stage 3)

The engine starts isolated workers using a versioned `TraceRequest`/`TraceResponse` contract.
A request names an approved project root, entrypoint, controlled inputs, timeout, and provider
preference. A response contains only trace evidence, coverage, resource summary, diagnostics,
and a structured failure code. Workers do not receive source-write authority and do not mutate
the engine process state.

## Desktop Sidecar v1

**Owner:** `desktop` plus `archcanvas_engine` (Stages 5-7)

Tauri is a client of Engine RPC. It may store UI session state and CanvasDocument revisions,
but it must not import Python core models through ad hoc serialization or access source paths
outside an engine-approved project session. The UI renders validation reports returned by the
engine; it does not recompute commit eligibility.

## MCP v1

**Owner:** `archcanvas_mcp` (Stage 9)

MCP exposes a subset of Engine RPC with the same names and outcome semantics. The minimum
reserved tool set is `archcanvas_health`, `archcanvas_open_project`, `archcanvas_analyze`,
`archcanvas_render_publication`, `archcanvas_plan_patch`, `archcanvas_validate_patch`,
`archcanvas_commit_patch`, and `archcanvas_export`.

The server must advertise only tools whose backing engine capability is ready. Project roots
are user-approved authority, not model-supplied permission. `archcanvas_commit_patch` remains
an explicit, separately authorized operation and cannot be folded into plan or validate.

## Skill v1

**Owner:** `skill/` (Stage 9)

The Skill teaches the source-aware workflow and routes to references; it does not implement
analysis or mutate source. It probes availability once per conversation when MCP is present.
If the server or required capability is unavailable, it reports the missing capability and
stops rather than inventing a diagram, a validation result, or a code commit.

## Canvas Contract v1

**Owner:** `desktop` and `archcanvas_core` (Stage 6)

`CanvasDocument` is a visual document keyed by a Publication IR revision. It owns viewport,
node placement, size, visual style, annotations, lock, and collapse state. It never owns
model parameters, ports, source anchors, source revisions, or patch payloads. Semantic edits
are represented only by ArchitecturePatch and enter the engine transaction path.
