"""Nonexecuting bridge to the formal Studio document and history contracts."""
import json
import shutil
import subprocess
from pathlib import Path


def canvas_operation(root: Path | None, payload: dict) -> dict:
    if root is None or not (root / "scripts/canvas_bridge.mjs").is_file() or not shutil.which("node"):
        raise ValueError("Canvas operations require the complete formal runtime and Node.js 24+; run doctor.")
    try:
        result = subprocess.run([shutil.which("node"), "--experimental-strip-types", str(root / "scripts/canvas_bridge.mjs")],
                                input=json.dumps(payload, ensure_ascii=False, allow_nan=False), cwd=root,
                                capture_output=True, text=True, timeout=45)
    except subprocess.TimeoutExpired as exc:
        raise ValueError("Canvas projection exceeded its 45 second budget; saved state is unchanged.") from exc
    if result.returncode:
        raise ValueError(result.stderr[-2000:] or "Canvas projection failed; saved state is unchanged.")
    return json.loads(result.stdout)
