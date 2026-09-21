# Engine Rules

- Engine is the only owner of project sessions, cache/history and future source transactions.
- Persist only under the configured cache root; never create engine state inside an analyzed project.
- Every external request uses `EngineRequest`/`EngineResponse` and returns a structured rejection.
- Detect stale source and orphan visual state; do not replay it automatically across revisions.
- Desktop, CLI and MCP are future Engine clients and must not bypass these rules.
