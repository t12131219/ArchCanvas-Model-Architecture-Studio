from __future__ import annotations

import builtins
import importlib
import io
import json
import os
import platform
import socket
import subprocess
import sys
from pathlib import Path
from typing import Any


def _write_response(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )


def _install_boundaries(root: Path) -> list[dict[str, str]]:
    violations: list[dict[str, str]] = []
    original_open = builtins.open
    original_io_open = io.open
    original_os_open = os.open
    original_mkdir = os.mkdir
    original_makedirs = os.makedirs
    original_remove = os.remove
    original_unlink = os.unlink
    original_rename = os.rename
    original_replace = os.replace
    original_rmdir = os.rmdir

    def allowed(path: Any) -> bool:
        if isinstance(path, int):
            return True
        try:
            return Path(path).resolve().is_relative_to(root)
        except (OSError, TypeError, ValueError):
            return False

    def deny_write(path: Any) -> None:
        violations.append({"operation": "write", "target": str(path)})
        raise PermissionError(f"runtime worker write denied outside sandbox: {path}")

    def guarded_open(file: Any, mode: str = "r", *args: Any, **kwargs: Any) -> Any:
        if any(flag in mode for flag in "wax+") and not allowed(file):
            deny_write(file)
        return original_open(file, mode, *args, **kwargs)

    def guarded_io_open(file: Any, mode: str = "r", *args: Any, **kwargs: Any) -> Any:
        if any(flag in mode for flag in "wax+") and not allowed(file):
            deny_write(file)
        return original_io_open(file, mode, *args, **kwargs)

    def guarded_os_open(path: Any, flags: int, *args: Any, **kwargs: Any) -> int:
        write_flags = os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND
        if flags & write_flags and not allowed(path):
            deny_write(path)
        return original_os_open(path, flags, *args, **kwargs)

    def guarded_path_call(original: Any, path: Any, *args: Any, **kwargs: Any) -> Any:
        if not allowed(path):
            deny_write(path)
        return original(path, *args, **kwargs)

    builtins.open = guarded_open
    io.open = guarded_io_open
    os.open = guarded_os_open
    os.mkdir = lambda path, *args, **kwargs: guarded_path_call(original_mkdir, path, *args, **kwargs)
    os.makedirs = lambda path, *args, **kwargs: guarded_path_call(original_makedirs, path, *args, **kwargs)
    os.remove = lambda path, *args, **kwargs: guarded_path_call(original_remove, path, *args, **kwargs)
    os.unlink = lambda path, *args, **kwargs: guarded_path_call(original_unlink, path, *args, **kwargs)
    os.rmdir = lambda path, *args, **kwargs: guarded_path_call(original_rmdir, path, *args, **kwargs)

    def guarded_move(original: Any, source: Any, target: Any, *args: Any, **kwargs: Any) -> Any:
        if not allowed(source) or not allowed(target):
            deny_write(f"{source} -> {target}")
        return original(source, target, *args, **kwargs)

    os.rename = lambda source, target, *args, **kwargs: guarded_move(
        original_rename, source, target, *args, **kwargs
    )
    os.replace = lambda source, target, *args, **kwargs: guarded_move(
        original_replace, source, target, *args, **kwargs
    )

    def deny_process(target: Any, *args: Any, **kwargs: Any) -> None:
        violations.append({"operation": "process", "target": str(target)})
        raise PermissionError("runtime worker child process creation denied")

    class GuardedSocket(socket.socket):
        def _deny(self, target: Any) -> None:
            violations.append({"operation": "network", "target": repr(target)})
            raise PermissionError("runtime worker network access denied")

        def connect(self, address: Any) -> None:
            self._deny(address)

        def connect_ex(self, address: Any) -> int:
            self._deny(address)
            return 1

        def bind(self, address: Any) -> None:
            self._deny(address)

        def listen(self, backlog: int = 0) -> None:
            self._deny(f"listen:{backlog}")

        def sendto(self, data: Any, address: Any, *args: Any) -> None:
            self._deny(address)

    def denied_connection(address: Any, *args: Any, **kwargs: Any) -> None:
        violations.append({"operation": "network", "target": repr(address)})
        raise PermissionError("runtime worker network access denied")

    os.system = deny_process
    for name in (
        "execl", "execle", "execlp", "execlpe", "execv", "execve", "execvp", "execvpe",
        "fork", "forkpty", "posix_spawn", "posix_spawnp", "spawnl", "spawnle", "spawnlp",
        "spawnlpe", "spawnv", "spawnve", "spawnvp", "spawnvpe",
    ):
        if hasattr(os, name):
            setattr(os, name, deny_process)
    subprocess.Popen = deny_process
    subprocess.run = deny_process
    subprocess.call = deny_process
    subprocess.check_call = deny_process
    subprocess.check_output = deny_process
    socket.socket = GuardedSocket
    socket.create_connection = denied_connection
    socket.getaddrinfo = denied_connection
    socket.gethostbyname = denied_connection
    socket.gethostbyaddr = denied_connection
    return violations


def main() -> int:
    request_path = Path(sys.argv[1]).resolve()
    request = json.loads(request_path.read_text(encoding="utf-8"))
    response_path = Path(request["response_path"]).resolve()
    violations: list[dict[str, str]] = []
    environment: dict[str, Any] | None = None
    try:
        module = importlib.import_module(request["worker_module"])
        request["runtime_python_version"] = platform.python_version()
        request["runtime_platform"] = platform.platform()
        violations = _install_boundaries(Path(request["sandbox_root"]).resolve())
        payload = module.execute(request)
        violations = [
            dict(items)
            for items in dict.fromkeys(tuple(sorted(item.items())) for item in violations)
        ]
        environment = payload.get("environment")
        _write_response(response_path, {"status": "completed", **payload, "violations": violations})
        return 0
    except BaseException as error:  # noqa: BLE001
        _write_response(
            response_path,
            {
                "status": "failed",
                "error_type": error.__class__.__name__,
                "message": str(error),
                "environment": environment,
                "violations": violations,
            },
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
