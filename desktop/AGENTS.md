# Desktop Rules

- The desktop is an Engine RPC client. It does not read or write project source paths.
- `CanvasDocument` is visual-only: viewport, placement, sizing, style, annotation, collapse,
  lock and layout mode. Do not add model parameters, ports, edges or source-patch fields.
- Browser fixture mode is explicitly read-only and may only persist fixture visual state locally.
- Tauri commands return typed Engine outcomes; Python analysis and all future source transactions
  remain owned by `archcanvas_engine`.
