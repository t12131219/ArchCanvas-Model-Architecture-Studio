# TFB Resolved Configs V1

This is a narrow, versioned input ledger for the D5 read-only census. It contains only the two
forecast configurations already recorded in `stage-6-tfb-observation.json`; it is not a guessed
default corpus and must not be applied to another entrypoint merely because field names match.

| Entrypoint | Provenance | Approved config |
| --- | --- | --- |
| `baselines/time_series_library/models/Transformer.py:Transformer` | Stage 6 read-only Transformer forecast observation | `task_name=long_term_forecast`, `e_layers=2`, `d_layers=1` |
| `baselines/time_series_library/models/TimesNet.py:TimesNet` | Stage 6 read-only TimesNet forecast observation | `task_name=long_term_forecast`, `e_layers=2` |

Use the adjacent JSON only with `--resolved-config-file`. Any entrypoint lacking a row remains a
visible ArchCanvas configuration/recovery backlog item; it is not removed from the TFB census.
