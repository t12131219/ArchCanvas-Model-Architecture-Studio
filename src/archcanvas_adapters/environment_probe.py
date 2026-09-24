from __future__ import annotations

import json
import subprocess
import sys
from functools import lru_cache


@lru_cache(maxsize=1)
def pytorch_available_targets() -> tuple[str, ...]:
    """Probe Torch in an isolated interpreter so registry inspection stays side-effect free."""
    script = (
        "import json, torch; "
        "print(json.dumps(['cpu', 'cuda'] if torch.cuda.is_available() else ['cpu']))"
    )
    try:
        completed = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        if completed.returncode != 0:
            return ()
        targets = json.loads(completed.stdout)
    except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError):
        return ()
    if not isinstance(targets, list) or any(item not in {"cpu", "cuda"} for item in targets):
        return ()
    return tuple(targets)
