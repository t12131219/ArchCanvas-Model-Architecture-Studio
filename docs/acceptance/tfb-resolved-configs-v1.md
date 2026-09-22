# TFB Resolved Configs V1

This is a narrow, versioned input ledger for the D5 read-only census. It contains only the
read-only Stage 6 observations listed below; it is not a guessed default corpus and must not be
applied to another entrypoint merely because field names match.

| Entrypoint | Provenance | Approved config |
| --- | --- | --- |
| `baselines/duet/models/duet_model.py:DUETModel` | Stage 6 source-backed DUET semantic preflight | `CI=true`, `num_experts=4`, `k=1`, `e_layers=2`, `n_heads=2` |
| `baselines/time_series_library/models/Transformer.py:Transformer` | Stage 6 read-only Transformer forecast observation | `task_name=long_term_forecast`, `e_layers=2`, `d_layers=1` |
| `baselines/time_series_library/models/TimesNet.py:TimesNet` | Stage 6 read-only TimesNet forecast observation | `task_name=long_term_forecast`, `e_layers=2` |

Use the adjacent JSON only with `--resolved-config-file`. Any entrypoint lacking a row remains a
visible ArchCanvas configuration/recovery backlog item; it is not removed from the TFB census.
