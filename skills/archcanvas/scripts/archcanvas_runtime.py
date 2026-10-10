#!/usr/bin/env python3
"""Explicit development binding; installed releases replace this launcher."""
import json
import sys
from pathlib import Path

sys.dont_write_bytecode = True
skill = Path(__file__).resolve().parents[1]
binding = skill / "archcanvas-runtime.json"
root = Path(json.loads(binding.read_text())["runtimeRoot"]).expanduser().resolve() if binding.is_file() else skill.parents[1]
if "ArchCanvas_Model Architecture Studio_Temp" in str(root) or not (root / "src/archcanvas_cli/__main__.py").is_file() or not (root / "pyproject.toml").is_file():
    raise SystemExit("No formal ArchCanvas runtime is bound. Install the complete verified bundle, or explicitly configure archcanvas-runtime.json with runtimeRoot. Copying SKILL.md alone cannot open a canvas.")
sys.path.insert(0, str(root / "src"))
from archcanvas_cli.__main__ import main
raise SystemExit(main())
