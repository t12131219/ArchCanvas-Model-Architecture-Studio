# Third-Party Provenance

## ML Architecture Diagram Skill

- Location reviewed: sibling workspace `ml-architecture-diagram-skill/`.
- License: MIT, copyright 2026 ML Architecture Diagram Skill contributors.
- Reviewed material: `src/ml_architecture_diagram/parsers/pytorch_ast.py`, particularly its
  conservative AST treatment of residual additions and `torch.cat` inputs.
- ArchCanvas usage: design reference only. No source files or code fragments were copied.
- ArchCanvas-specific implementation: `src/archcanvas_pytorch/static/scanner.py`, which emits
  strict discovery records consumed by ArchCanvas Source Identity and Architecture IR adapters.
