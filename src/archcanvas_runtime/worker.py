from __future__ import annotations

import builtins
import importlib
import inspect
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

    def guarded_mkdir(path: Any, *args: Any, **kwargs: Any) -> None:
        if not allowed(path):
            deny_write(path)
        original_mkdir(path, *args, **kwargs)

    def guarded_makedirs(name: Any, *args: Any, **kwargs: Any) -> None:
        if not allowed(name):
            deny_write(name)
        original_makedirs(name, *args, **kwargs)

    def guarded_remove(path: Any, *args: Any, **kwargs: Any) -> None:
        if not allowed(path):
            deny_write(path)
        original_remove(path, *args, **kwargs)

    def guarded_unlink(path: Any, *args: Any, **kwargs: Any) -> None:
        if not allowed(path):
            deny_write(path)
        original_unlink(path, *args, **kwargs)

    def guarded_rename(source: Any, target: Any, *args: Any, **kwargs: Any) -> None:
        if not allowed(source) or not allowed(target):
            deny_write(f"{source} -> {target}")
        original_rename(source, target, *args, **kwargs)

    def guarded_replace(source: Any, target: Any, *args: Any, **kwargs: Any) -> None:
        if not allowed(source) or not allowed(target):
            deny_write(f"{source} -> {target}")
        original_replace(source, target, *args, **kwargs)

    def guarded_rmdir(path: Any, *args: Any, **kwargs: Any) -> None:
        if not allowed(path):
            deny_write(path)
        original_rmdir(path, *args, **kwargs)

    def deny_process(target: Any, *args: Any, **kwargs: Any) -> None:
        violations.append({"operation": "process", "target": str(target)})
        raise PermissionError("runtime worker child process creation denied")

    class GuardedSocket(socket.socket):
        def connect(self, address: Any) -> None:
            violations.append({"operation": "network", "target": repr(address)})
            raise PermissionError("runtime worker network access denied")

        def connect_ex(self, address: Any) -> int:
            violations.append({"operation": "network", "target": repr(address)})
            raise PermissionError("runtime worker network access denied")

        def bind(self, address: Any) -> None:
            violations.append({"operation": "network", "target": repr(address)})
            raise PermissionError("runtime worker network access denied")

        def listen(self, backlog: int = 0) -> None:
            violations.append({"operation": "network", "target": f"listen:{backlog}"})
            raise PermissionError("runtime worker network access denied")

        def sendto(self, data: Any, address: Any, *args: Any) -> None:
            violations.append({"operation": "network", "target": repr(address)})
            raise PermissionError("runtime worker network access denied")

    def denied_connection(address: Any, *args: Any, **kwargs: Any) -> None:
        violations.append({"operation": "network", "target": repr(address)})
        raise PermissionError("runtime worker network access denied")

    builtins.open = guarded_open
    io.open = guarded_io_open
    os.open = guarded_os_open
    os.mkdir = guarded_mkdir
    os.makedirs = guarded_makedirs
    os.remove = guarded_remove
    os.unlink = guarded_unlink
    os.rename = guarded_rename
    os.replace = guarded_replace
    os.rmdir = guarded_rmdir
    os.system = deny_process
    for name in (
        "execl",
        "execle",
        "execlp",
        "execlpe",
        "execv",
        "execve",
        "execvp",
        "execvpe",
        "fork",
        "forkpty",
        "posix_spawn",
        "posix_spawnp",
        "spawnl",
        "spawnle",
        "spawnlp",
        "spawnlpe",
        "spawnv",
        "spawnve",
        "spawnvp",
        "spawnvpe",
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


def _flatten_tensors(value: Any, torch: Any) -> list[Any]:
    if isinstance(value, torch.Tensor):
        return [value]
    if isinstance(value, dict):
        return [tensor for item in value.values() for tensor in _flatten_tensors(item, torch)]
    if isinstance(value, (list, tuple)):
        return [tensor for item in value for tensor in _flatten_tensors(item, torch)]
    return []


def _tensor_record(tensor: Any) -> dict[str, Any]:
    return {
        "shape": list(tensor.shape),
        "dtype": str(tensor.dtype).removeprefix("torch."),
        "device": str(tensor.device),
        "requires_grad": bool(tensor.requires_grad),
    }


def _make_tensor(item: dict[str, Any], device: Any, torch: Any) -> Any:
    dtype = getattr(torch, item["dtype"])
    shape = tuple(item["shape"])
    generator = item["generator"]
    if generator == "zeros":
        return torch.zeros(shape, dtype=dtype, device=device)
    if generator == "ones":
        return torch.ones(shape, dtype=dtype, device=device)
    if generator == "normal":
        return torch.randn(shape, dtype=dtype, device=device)
    if generator == "uniform":
        return torch.rand(shape, dtype=dtype, device=device)
    return torch.randint(
        int(item["low"]),
        int(item["high"]),
        shape,
        dtype=dtype,
        device=device,
    )


def _resolve_entrypoint(project: Path, entrypoint: str) -> Any:
    module_name, symbol_path = entrypoint.split(":", 1)
    sys.path.insert(0, str(project))
    value: Any = importlib.import_module(module_name)
    for segment in symbol_path.split("."):
        value = getattr(value, segment)
    return value


def _constructor_kwargs(target: Any, request: dict[str, Any]) -> dict[str, Any]:
    signature = inspect.signature(target)
    configured = request.get("resolved_config", {})
    explicit = request["input_spec"].get("constructor_kwargs", {})
    candidates = {**configured, **explicit}
    return {
        name: value
        for name, value in candidates.items()
        if name in signature.parameters and name != "self"
    }


def main() -> int:
    request_path = Path(sys.argv[1]).resolve()
    request = json.loads(request_path.read_text(encoding="utf-8"))
    response_path = Path(request["response_path"]).resolve()
    violations: list[dict[str, str]] = []
    environment: dict[str, Any] | None = None
    try:
        import torch

        spec = request["input_spec"]
        torch.manual_seed(spec["seed"])
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(spec["seed"])
        torch.use_deterministic_algorithms(True)
        selected = spec["device"]
        if selected == "auto":
            selected = "cuda" if torch.cuda.is_available() else "cpu"
        if selected == "cuda" and not torch.cuda.is_available():
            raise RuntimeError("CUDA was requested but is not available to the runtime worker")
        device = torch.device(selected)
        environment = {
            "python_version": platform.python_version(),
            "platform": platform.platform(),
            "torch_version": torch.__version__,
            "cuda_build": torch.version.cuda,
            "cuda_available": torch.cuda.is_available(),
            "selected_device": str(device),
            "deterministic_algorithms": torch.are_deterministic_algorithms_enabled(),
        }
        violations = _install_boundaries(Path(request["sandbox_root"]).resolve())
        target = _resolve_entrypoint(Path(request["project_root"]).resolve(), request["entrypoint"])
        model = target(**_constructor_kwargs(target, request)).to(device)
        model.train(request["execution_mode"] == "train")
        observations: list[dict[str, Any]] = []
        handles = []
        match_paths = request.get("match_paths", {})

        def hook_for(path: str, module: Any) -> Any:
            def hook(_module: Any, inputs: Any, output: Any) -> None:
                observations.append(
                    {
                        "module_path": path,
                        "module_type": module.__class__.__name__,
                        "input_tensors": [
                            _tensor_record(tensor) for tensor in _flatten_tensors(inputs, torch)
                        ],
                        "output_tensors": [
                            _tensor_record(tensor) for tensor in _flatten_tensors(output, torch)
                        ],
                        "matched_node_ids": match_paths.get(path, []),
                    }
                )

            return hook

        for name, module in model.named_modules():
            path = name or "<root>"
            handles.append(module.register_forward_hook(hook_for(path, module)))
        inputs = {
            item["name"]: _make_tensor(item, device, torch) for item in spec["inputs"]
        }
        with torch.inference_mode(mode=request["execution_mode"] == "eval"):
            output = model(**inputs, **spec.get("forward_kwargs", {}))
        for handle in handles:
            handle.remove()
        payload = {
            "status": "completed",
            "observations": observations,
            "output_tensors": [
                _tensor_record(tensor) for tensor in _flatten_tensors(output, torch)
            ],
            "environment": environment,
            "violations": violations,
        }
        _write_response(response_path, payload)
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
