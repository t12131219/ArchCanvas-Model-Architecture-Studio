"""Short-lived subprocess entrypoint that is the only Stage 3 code-import boundary."""

from __future__ import annotations

import contextlib
import importlib.util
import io
import resource
import socket
import sys
import time
import traceback
from pathlib import Path
from typing import NoReturn

from archcanvas_core.models.runtime import (
    NetworkPolicy,
    RuntimeEnvironment,
    RuntimeTraceResult,
    TraceFailureCode,
    TraceRequest,
    TraceStatus,
)
from archcanvas_python.source_revision import file_revision

from .providers import provider_for


class _TraceWorkerFailure(RuntimeError):
    def __init__(self, code: TraceFailureCode, message: str) -> None:
        super().__init__(message)
        self.code = code


def _trace_id(request: TraceRequest) -> str:
    return f"trace:{request.request_id.removeprefix('trace-request:')}"


def _limited_text(value: str, limit: int = 16_384) -> tuple[str, bool]:
    return value[:limit], len(value) > limit


def _environment(request: TraceRequest) -> RuntimeEnvironment:
    import torch

    return RuntimeEnvironment(
        python_executable=sys.executable,
        python_version=sys.version.split()[0],
        torch_version=torch.__version__,
        cuda_version=torch.version.cuda,
        device="cpu",
        network_policy=request.network_policy,
        network_enforcement="best_effort"
        if request.network_policy is NetworkPolicy.DENY
        else "not_requested",
        environment_name=request.environment_name,
        dependency_lockfile=request.dependency_lockfile,
    )


def _apply_resource_limits(request: TraceRequest) -> None:
    try:
        cpu_limit = max(1, request.timeout_seconds)
        resource.setrlimit(resource.RLIMIT_CPU, (cpu_limit, cpu_limit + 1))
        memory_limit = request.memory_limit_mb * 1024 * 1024
        resource.setrlimit(resource.RLIMIT_AS, (memory_limit, memory_limit))
    except (OSError, ValueError):
        # The report documents a best-effort worker boundary. Unsupported operating systems do not
        # change source or permit a fallback import in the engine process.
        return


def _deny_network() -> None:
    def blocked_socket(*args: object, **kwargs: object) -> NoReturn:
        del args, kwargs
        raise OSError("network access is disabled for this runtime trace")

    socket.socket = blocked_socket  # type: ignore[assignment]
    socket.create_connection = blocked_socket  # type: ignore[assignment]


def _entrypoint_path(request: TraceRequest) -> Path:
    relative_file, _ = request.entrypoint.split(":", maxsplit=1)
    root = Path(request.project_root).resolve(strict=True)
    candidate = (root / relative_file).resolve(strict=False)
    if not candidate.is_file() or not candidate.is_relative_to(root):
        raise _TraceWorkerFailure(
            TraceFailureCode.ENTRYPOINT_NOT_FOUND,
            "entrypoint source file does not exist inside project_root",
        )
    if file_revision(candidate.read_bytes()) != request.entrypoint_file_revision:
        raise _TraceWorkerFailure(
            TraceFailureCode.STALE_ENTRYPOINT_REVISION,
            "entrypoint source revision changed after the trace request was created",
        )
    return candidate


def _load_model(request: TraceRequest) -> object:
    source_path = _entrypoint_path(request)
    _, class_name = request.entrypoint.split(":", maxsplit=1)
    sys.path.insert(0, str(Path(request.project_root).resolve()))
    spec = importlib.util.spec_from_file_location(
        f"_archcanvas_trace_{request.request_id.removeprefix('trace-request:')}", source_path
    )
    if spec is None or spec.loader is None:
        raise _TraceWorkerFailure(TraceFailureCode.MODEL_IMPORT_FAILED, "cannot load entrypoint module")
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception as error:
        raise _TraceWorkerFailure(TraceFailureCode.MODEL_IMPORT_FAILED, str(error)) from error
    model_class = getattr(module, class_name, None)
    if model_class is None:
        raise _TraceWorkerFailure(
            TraceFailureCode.MODEL_IMPORT_FAILED, "entrypoint class is absent from source module"
        )
    try:
        model = model_class(**request.constructor_kwargs)
        model.eval()
        return model.cpu()
    except Exception as error:
        raise _TraceWorkerFailure(TraceFailureCode.MODEL_CONSTRUCTION_FAILED, str(error)) from error


def _inputs(request: TraceRequest) -> tuple[object, ...]:
    import torch

    dtypes = {
        "float32": torch.float32,
        "float64": torch.float64,
        "int64": torch.int64,
        "int32": torch.int32,
        "bool": torch.bool,
    }
    try:
        return tuple(torch.zeros(item.shape, dtype=dtypes[item.dtype]) for item in request.inputs)
    except (KeyError, RuntimeError) as error:
        raise _TraceWorkerFailure(TraceFailureCode.INPUT_CONSTRUCTION_FAILED, str(error)) from error


def _peak_memory_bytes() -> int | None:
    try:
        # Linux reports KiB; macOS reports bytes. The project CI target is Linux.
        peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        return peak * 1024 if sys.platform.startswith("linux") else peak
    except OSError:
        return None


def _failure_result(
    request: TraceRequest,
    *,
    environment: RuntimeEnvironment,
    started: float,
    code: TraceFailureCode,
    message: str,
    stdout: str,
    stderr: str,
) -> RuntimeTraceResult:
    bounded_stderr, truncated = _limited_text(stderr)
    return RuntimeTraceResult(
        trace_id=_trace_id(request),
        request_id=request.request_id,
        provider=request.provider,
        source_revision=request.source_revision,
        status=TraceStatus.FAILED,
        failure_code=code,
        message=message[:512],
        environment=environment,
        observations=[],
        coverage_gaps=["runtime-trace-unavailable"],
        elapsed_ms=int((time.monotonic() - started) * 1000),
        peak_memory_bytes=_peak_memory_bytes(),
        worker_exit_code=0,
        stdout=stdout,
        stderr=bounded_stderr,
        stderr_truncated=truncated,
    )


def run(request: TraceRequest) -> RuntimeTraceResult:
    started = time.monotonic()
    _apply_resource_limits(request)
    environment = _environment(request)
    if request.network_policy is NetworkPolicy.DENY:
        _deny_network()
    stdout_capture, stderr_capture = io.StringIO(), io.StringIO()
    try:
        with contextlib.redirect_stdout(stdout_capture), contextlib.redirect_stderr(stderr_capture):
            model = _load_model(request)
            inputs = _inputs(request)
            provider = provider_for(request.provider)
            capability = provider.can_trace(request)
            if not capability.supported:
                raise _TraceWorkerFailure(
                    TraceFailureCode.PROVIDER_UNAVAILABLE,
                    capability.reason or "runtime provider is unavailable",
                )
            observations = provider.trace(model, inputs)
    except _TraceWorkerFailure as error:
        return _failure_result(
            request,
            environment=environment,
            started=started,
            code=error.code,
            message=str(error),
            stdout=stdout_capture.getvalue(),
            stderr=stderr_capture.getvalue(),
        )
    except Exception as error:  # noqa: BLE001 - model code and provider exceptions cross this boundary.
        return _failure_result(
            request,
            environment=environment,
            started=started,
            code=TraceFailureCode.TRACE_UNSUPPORTED,
            message=str(error),
            stdout=stdout_capture.getvalue(),
            stderr=stderr_capture.getvalue() + traceback.format_exc(),
        )
    bounded_stderr, truncated = _limited_text(stderr_capture.getvalue())
    return RuntimeTraceResult(
        trace_id=_trace_id(request),
        request_id=request.request_id,
        provider=request.provider,
        source_revision=request.source_revision,
        status=TraceStatus.SUCCEEDED,
        failure_code=None,
        message=None,
        environment=environment,
        observations=observations,
        coverage_gaps=[],
        elapsed_ms=int((time.monotonic() - started) * 1000),
        peak_memory_bytes=_peak_memory_bytes(),
        worker_exit_code=0,
        stdout=stdout_capture.getvalue(),
        stderr=bounded_stderr,
        stderr_truncated=truncated,
    )


def main() -> int:
    request = TraceRequest.model_validate_json(sys.stdin.buffer.read())
    result = run(request)
    sys.__stdout__.write(result.model_dump_json())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
