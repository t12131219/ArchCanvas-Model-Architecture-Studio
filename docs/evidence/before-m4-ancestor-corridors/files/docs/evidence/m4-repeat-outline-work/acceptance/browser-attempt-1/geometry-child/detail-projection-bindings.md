# Exact detail projection bindings

All ten records (five in each detail preview/export) retain their canonical edge/source/target/tensor/role metadata and match the saved architecture. The visible circles belong to the captured hidden targets’ direct collapsed parent; typed input role/direction matches.

| Canonical edge | Hidden target port | Visible parent input | Actual public circle / route endpoint |
| --- | --- | --- | --- |
| edge:8 | query (data) | 0:x | [113.5, 412.0] |
| edge:9 | key (data) | 0:x | [113.5, 412.0] |
| edge:10 | value (data) | 0:x | [113.5, 412.0] |
| edge:11 | attn_mask (mask) | 0:mask | [162.0, 412.0] |
| edge:29 | attn_mask (mask) | 1:mask | [162.0, 512.0] |

Per-record exact public circle IDs, captured saved parent IDs, hidden and representative typed canonical ports, metadata checks, and five unchanged input bindings are in detail-projection-bindings.json. Actual replay ScenePort canonicalBindings and canonicalEdgeIds contain each specific hidden canonical target and edge; replay is observed output, not the expected oracle. Removing the hidden binding or canonical edge ID is rejected by negative controls. These facts establish the nominal projection binding only; the blocked up-move route remains a separate observed failure state.
