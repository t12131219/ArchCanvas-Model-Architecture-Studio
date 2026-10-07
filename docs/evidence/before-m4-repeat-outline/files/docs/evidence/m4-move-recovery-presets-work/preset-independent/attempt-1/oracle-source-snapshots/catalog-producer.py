"""Save the actual formal backend catalog without importing/running a model."""
import hashlib
import json
from pathlib import Path
import sys

root = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(root / "src"))
from archcanvas_authoring import module_catalog  # noqa: E402
import archcanvas_authoring.draft as module  # noqa: E402

origin = Path(module.__file__).resolve()
assert origin.is_relative_to(root / "src")
assert "torch" not in sys.modules
target = Path(sys.argv[1])
with target.open("x", encoding="utf-8") as handle:
    handle.write(json.dumps(module_catalog(), ensure_ascii=False, indent=2) + "\n")
with target.with_name("catalog-provenance.json").open("x", encoding="utf-8") as handle:
    json.dump({"pythonExecutable": sys.executable, "pythonVersion": sys.version, "packageOrigin": str(origin), "packageSha256": hashlib.sha256(origin.read_bytes()).hexdigest(), "catalogSha256": hashlib.sha256(target.read_bytes()).hexdigest(), "torchImported": False, "modelExecution": "not_run"}, handle, ensure_ascii=False, indent=2)
    handle.write("\n")
print(json.dumps({"status": "catalog-saved", "path": str(target), "modelExecution": "not_run"}))
