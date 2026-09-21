"""Parent-process client for the short-lived PyTorch runtime worker."""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

from archcanvas_core.models.runtime import (
    NetworkPolicy,
    RuntimeEnvironment,
    RuntimeTraceResult,
    TraceFailureCode,
    TraceRequest,
    TraceStatus,
)

_MAX_CAPTURED_OUTPUT = 16_384


def _bounded_output(value: bytes) -> tuple[str, bool]:
    text = value.decode("utf-8", errors="replace")
    return (text[:_MAX_CAPTURED_OUTPUT], len(text) > _MAX_CAPTURED_OUTPUT)


def _parent_environment(request: TraceRequest) -> RuntimeEnvironment:
    return RuntimeEnvironment(
        python_executable=sys.executable,
        python_version=sys.version.split()[0],
        torch_version=None,
        cuda_version=None,
        device=None,
        network_policy=request.network_policy,
        network_enforcement=(
            "best_effort" if request.network_policy is NetworkPolicy.DENY else "not_requested"
        ),
        environment_name=request.environment_name,
        dependency_lockfile=request.dependency_lockfile,
    )


class IsolatedTraceWorker:
    """Execute a trace in a fresh configured interpreter, never in the engine process."""

    def run(self, request: TraceRequest) -> RuntimeTraceResult:
        executable = Path(request.python_executable)
        root = Path(request.project_root)
        if not executable.is_file() or not os.access(executable, os.X_OK):
            return self._rejected(request, TraceFailureCode.INVALID_REQUEST, "python_executable is not executable")
        if not root.is_dir():
            return self._rejected(request, TraceFailureCode.INVALID_REQUEST, "project_root is not a directory")

        started = time.monotonic()
        environment = os.environ.copy()
        source_root = str(Path(__file__).resolve().parents[2])
        environment["PYTHONPATH"] = os.pathsep.join(
            part for part in (source_root, environment.get("PYTHONPATH")) if part
        )
        # Keep each short-lived trace within a predictable CPU/thread budget. This also prevents
        # parallel fixture traces from exhausting a host's OpenMP thread quota.
        environment.update(
            {
                "OMP_NUM_THREADS": "1",
                "MKL_NUM_THREADS": "1",
                "OPENBLAS_NUM_THREADS": "1",
                "NUMEXPR_NUM_THREADS": "1",
            }
        )
        try:
            completed = subprocess.run(
                [str(executable), "-m", "archcanvas_pytorch.runtime.worker"],
                input=request.model_dump_json().encode("utf-8"),
                capture_output=True,
                cwd=root,
                env=environment,
                timeout=request.timeout_seconds + 2,
                check=False,
            )
        except subprocess.TimeoutExpired as error:
            stdout, _ = _bounded_output(error.stdout or b"")
            stderr, truncated = _bounded_output(error.stderr or b"")
            return RuntimeTraceResult(
                trace_id=f"trace:{request.request_id.removeprefix('trace-request:')}",
                request_id=request.request_id,
                provider=request.provider,
                source_revision=request.source_revision,
                status=TraceStatus.TIMED_OUT,
                failure_code=TraceFailureCode.WORKER_TIMEOUT,
                message="runtime worker exceeded the configured timeout",
                environment=_parent_environment(request),
                observations=[],
                coverage_gaps=["worker-timeout"],
                elapsed_ms=int((time.monotonic() - started) * 1000),
                peak_memory_bytes=None,
                worker_exit_code=None,
                stdout=stdout,
                stderr=stderr,
                stderr_truncated=truncated,
            )

        stdout, stdout_truncated = _bounded_output(completed.stdout)
        stderr, stderr_truncated = _bounded_output(completed.stderr)
        try:
            result = RuntimeTraceResult.model_validate_json(completed.stdout)
        except ValueError:
            return RuntimeTraceResult(
                trace_id=f"trace:{request.request_id.removeprefix('trace-request:')}",
                request_id=request.request_id,
                provider=request.provider,
                source_revision=request.source_revision,
                status=TraceStatus.FAILED,
                failure_code=TraceFailureCode.WORKER_PROTOCOL_ERROR,
                message="runtime worker did not return a valid protocol document",
                environment=_parent_environment(request),
                observations=[],
                coverage_gaps=["worker-protocol-error"],
                elapsed_ms=int((time.monotonic() - started) * 1000),
                peak_memory_bytes=None,
                worker_exit_code=completed.returncode,
                stdout=stdout,
                stderr=stderr,
                stderr_truncated=stdout_truncated or stderr_truncated,
            )
        return result.model_copy(
            update={
                "worker_exit_code": completed.returncode,
                "stderr": result.stderr + stderr,
                "stderr_truncated": result.stderr_truncated or stderr_truncated,
            }
        )

    @staticmethod
    def _rejected(
        request: TraceRequest, code: TraceFailureCode, message: str
    ) -> RuntimeTraceResult:
        return RuntimeTraceResult(
            trace_id=f"trace:{request.request_id.removeprefix('trace-request:')}",
            request_id=request.request_id,
            provider=request.provider,
            source_revision=request.source_revision,
            status=TraceStatus.REJECTED,
            failure_code=code,
            message=message,
            environment=_parent_environment(request),
            observations=[],
            coverage_gaps=["request-rejected"],
            elapsed_ms=0,
            peak_memory_bytes=None,
            worker_exit_code=None,
            stdout="",
            stderr="",
            stderr_truncated=False,
        )
