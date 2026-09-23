# ADR 0003: Keep One Engine Session Per Desktop Window

## Status

Accepted for the Stage 7 transport repair. Stage 7 acceptance remains gated by Stage 6.

## Context

The desktop bridge previously launched a Python Engine for every JSONL request. A planned
and validated candidate, including its one-time confirmation capability, lives only in
Engine memory; commit from a later Desktop RPC therefore had no candidate to confirm.

## Decision

- Tauri owns one bounded JSONL child and serializes requests through a mutex. It checks
  the response request ID, limits response bytes and rejects a changed host configuration.
- On I/O failure or invalid response, it discards the child and rejects that request.
  It never replays a source-changing request. The next request creates a new Engine,
  where any prior confirmation capability is absent.
- Window destruction terminates the child. Project analyzer/runtime profiles still require
  explicit Engine-side registration; process persistence alone does not enable source edits.

## Consequences

Desktop plan/validate/commit can share an Engine session when an approved project profile
is registered. Existing project-source and candidate validation gates remain authoritative.
