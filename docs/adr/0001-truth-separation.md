# ADR 0001: Separate Source Truth From Visual Truth

Status: accepted

Exact Architecture IR and CanvasDocument are separate persistence surfaces. This makes source-digest invariance testable for every visual edit and prevents canvas geometry from silently becoming model semantics.

