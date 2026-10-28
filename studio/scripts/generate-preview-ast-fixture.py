#!/usr/bin/env python3
"""Record a real formal AST fixture without importing or running model text."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

PROJECT = Path(__file__).resolve().parents[2]
SOURCE = PROJECT / "src"
sys.path.insert(0, str(SOURCE))
import archcanvas_preview
from archcanvas_preview import analyze, analyze_for_authoring

FILES = {
    "net/__init__.py": "",
    "net/ops.py": 'from torch import nn\nraise RuntimeError("Source text must never execute")\nclass Branch(nn.Module):\n def __init__(self):\n  super().__init__()\n  self.proj = nn.Linear(4,4)\n  self.act = nn.ReLU()\n def forward(self,x):\n  return self.act(self.proj(x))\n',
    "net/model.py": 'from torch import nn\nfrom .ops import Branch\nclass Model(nn.Module):\n def __init__(self):\n  super().__init__()\n  self.shared = Branch()\n def forward(self,x):\n  a = self.shared(x)\n  b = self.shared(x)\n  return a,b\n',
}
ENTRY = "net.model:Model"
bundle = analyze(FILES, ENTRY)
architecture = analyze_for_authoring(FILES, ENTRY)
assert not bundle["ir"]["modelExecuted"] and "torch" not in sys.modules
parser = Path(archcanvas_preview.__file__).resolve()
assert parser.is_relative_to(SOURCE)
modules = {
    str(Path(module.__file__).resolve().relative_to(PROJECT)): hashlib.sha256(Path(module.__file__).resolve().read_bytes()).hexdigest()
    for module in list(sys.modules.values())
    if getattr(module, "__file__", None) and Path(module.__file__).resolve().is_relative_to(SOURCE)
}
producer = Path(__file__).resolve()
modules[str(producer.relative_to(PROJECT))] = hashlib.sha256(producer.read_bytes()).hexdigest()
report = {
    "schema": "archcanvas-preview-formal-ast-fixture/1",
    "generatedAt": datetime.now(timezone.utc).isoformat(),
    "inputs": {"files": FILES, "entry": ENTRY},
    "parser": str(parser), "implementation": dict(sorted(modules.items())),
    "modelExecuted": False, "torchLoaded": False,
    "bundle": bundle, "architecture": architecture,
}
# This is a generated current test input. Historical migration evidence must
# remain immutable when a later backend capability changes implementation bytes.
output = PROJECT / "studio/tests/fixtures/preview-formal-ast.json"
output.parent.mkdir(parents=True, exist_ok=True)
output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf8")
print(json.dumps({"output": str(output), "nodes": len(bundle["ir"]["nodes"]), "edges": len(bundle["ir"]["edges"]), "modules": len(modules), "modelExecuted": False}))
