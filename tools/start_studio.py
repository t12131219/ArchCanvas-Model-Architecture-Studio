"""Start the local Studio API and Vite development server together."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

REPOSITORY = Path(__file__).resolve().parents[1]
STUDIO = REPOSITORY / "studio"


def _default_artifact() -> Path:
    candidates = sorted(
        (path for path in (REPOSITORY / "build").rglob("architecture.json") if path.is_file()),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    for artifact in candidates:
        overlay = artifact.parent / "semantic-annotation-overlay.json"
        if not overlay.is_file():
            return artifact
        try:
            payload = json.loads(overlay.read_text(encoding="utf-8"))
            annotations = payload.get("annotations", [])
            if all("recommended_depth" in annotation for annotation in annotations):
                return artifact
        except (OSError, TypeError, ValueError, json.JSONDecodeError):
            continue
    raise FileNotFoundError(
        "No compatible build/*/architecture.json found. "
        "Run archcanvas analyze first or pass --artifact."
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Start the ArchCanvas backend and Vite Studio frontend together."
    )
    parser.add_argument(
        "--artifact",
        type=Path,
        help="Path to architecture.json (defaults to the latest local build).",
    )
    parser.add_argument("--workspace", type=Path, help="CanvasDocument workspace directory.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--backend-port", type=int, default=4310)
    parser.add_argument("--frontend-port", type=int, default=4323)
    return parser


def _wait_for_backend(process: subprocess.Popen[bytes], url: str) -> None:
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"Studio backend exited with code {process.returncode}.")
        try:
            with urlopen(url, timeout=0.5) as response:
                if response.status == 200:
                    return
        except (OSError, URLError):
            time.sleep(0.15)
    raise TimeoutError(f"Studio backend did not become ready at {url}.")


def _terminate(process: subprocess.Popen[bytes] | None) -> None:
    if process is None or process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    artifact = (args.artifact or _default_artifact()).resolve()
    if not artifact.is_file():
        raise FileNotFoundError(f"Architecture artifact not found: {artifact}")
    if not (STUDIO / "node_modules" / ".bin" / "vite").exists():
        raise RuntimeError("studio/node_modules is missing; run 'npm install' in studio first.")

    workspace = (args.workspace or artifact.parent / ".archcanvas").resolve()
    python = Path(sys.executable)
    npm = "npm.cmd" if os.name == "nt" else "npm"
    backend = subprocess.Popen(
        [
            str(python),
            "-m",
            "archcanvas_engine.cli",
            "studio",
            str(artifact),
            "--workspace",
            str(workspace),
            "--serve",
            "--host",
            args.host,
            "--port",
            str(args.backend_port),
            "--json",
        ],
        cwd=REPOSITORY,
    )
    frontend: subprocess.Popen[bytes] | None = None
    try:
        backend_url = f"http://{args.host}:{args.backend_port}/api/state"
        _wait_for_backend(backend, backend_url)
        print(f"Studio backend: {backend_url}")
        frontend = subprocess.Popen(
            [npm, "run", "dev", "--", "--host", args.host, "--port", str(args.frontend_port)],
            cwd=STUDIO,
        )
        print(f"Studio frontend: http://{args.host}:{args.frontend_port}/")
        return frontend.wait()
    except KeyboardInterrupt:
        return 130
    finally:
        _terminate(frontend)
        _terminate(backend)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (FileNotFoundError, RuntimeError, TimeoutError) as error:
        print(f"start_studio: {error}", file=sys.stderr)
        raise SystemExit(2)
