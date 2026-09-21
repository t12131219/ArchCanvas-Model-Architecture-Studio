"""Strict protocol documents for isolated runtime evidence collection."""

from __future__ import annotations

from enum import Enum
from typing import Annotated, Literal

from pydantic import Field, model_validator

from .architecture import JsonValue, TensorSpec
from .common import StrictModel
from .source_identity import Sha256

TraceId = Annotated[str, Field(pattern=r"^trace:[A-Za-z0-9._-]+$")]
TraceRequestId = Annotated[str, Field(pattern=r"^trace-request:[A-Za-z0-9._-]+$")]


class RuntimeProviderId(str, Enum):
    TORCH_FX = "torch_fx"
    TORCH_EXPORT = "torch_export"


class NetworkPolicy(str, Enum):
    DENY = "deny"
    INHERIT = "inherit"


class TraceStatus(str, Enum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    TIMED_OUT = "timed_out"
    REJECTED = "rejected"


class TraceFailureCode(str, Enum):
    INVALID_REQUEST = "INVALID_REQUEST"
    STALE_ENTRYPOINT_REVISION = "STALE_ENTRYPOINT_REVISION"
    ENTRYPOINT_NOT_FOUND = "ENTRYPOINT_NOT_FOUND"
    MODEL_IMPORT_FAILED = "MODEL_IMPORT_FAILED"
    MODEL_CONSTRUCTION_FAILED = "MODEL_CONSTRUCTION_FAILED"
    INPUT_CONSTRUCTION_FAILED = "INPUT_CONSTRUCTION_FAILED"
    PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"
    TRACE_UNSUPPORTED = "TRACE_UNSUPPORTED"
    WORKER_TIMEOUT = "WORKER_TIMEOUT"
    WORKER_PROTOCOL_ERROR = "WORKER_PROTOCOL_ERROR"
    WORKER_EXITED = "WORKER_EXITED"


class RuntimeTensorInput(StrictModel):
    kind: Literal["tensor"] = "tensor"
    shape: list[int] = Field(min_length=1, max_length=8)
    dtype: Literal["float32", "float64", "int64", "int32", "bool"]

    @model_validator(mode="after")
    def shape_is_bounded(self) -> RuntimeTensorInput:
        if any(dimension < 1 or dimension > 1_000_000 for dimension in self.shape):
            raise ValueError("tensor dimensions must be between 1 and 1000000")
        return self


class TraceRequest(StrictModel):
    """An explicit opt-in request that permits a worker to execute selected project code."""

    request_id: TraceRequestId
    project_root: str = Field(min_length=1)
    python_executable: str = Field(min_length=1)
    entrypoint: str = Field(pattern=r"^[A-Za-z0-9_./-]+\.py:[A-Za-z_][A-Za-z0-9_]*$")
    entrypoint_file_revision: Sha256
    source_revision: Sha256
    environment_name: str | None = None
    dependency_lockfile: str | None = None
    constructor_kwargs: dict[str, JsonValue] = Field(default_factory=dict)
    inputs: list[RuntimeTensorInput] = Field(min_length=1, max_length=8)
    provider: RuntimeProviderId
    timeout_seconds: int = Field(ge=1, le=120)
    memory_limit_mb: int = Field(ge=128, le=16_384)
    network_policy: NetworkPolicy = NetworkPolicy.DENY

    @model_validator(mode="after")
    def entrypoint_path_is_relative(self) -> TraceRequest:
        relative_file, _ = self.entrypoint.split(":", maxsplit=1)
        if relative_file.startswith("/") or ".." in relative_file.split("/"):
            raise ValueError("entrypoint source path must remain inside project_root")
        return self

    @model_validator(mode="after")
    def dependency_lockfile_is_relative(self) -> TraceRequest:
        if self.dependency_lockfile is None:
            return self
        if (
            self.dependency_lockfile.startswith("/")
            or ".." in self.dependency_lockfile.split("/")
            or "\\" in self.dependency_lockfile
        ):
            raise ValueError("dependency_lockfile must be a normalized project-relative path")
        return self


class TraceCapability(StrictModel):
    provider: RuntimeProviderId
    supported: bool
    reason: str | None


class RuntimeEnvironment(StrictModel):
    python_executable: str
    python_version: str | None
    torch_version: str | None
    cuda_version: str | None
    device: str | None
    network_policy: NetworkPolicy
    network_enforcement: Literal["best_effort", "not_requested"]
    environment_name: str | None
    dependency_lockfile: str | None


class RuntimeNodeObservation(StrictModel):
    target: str
    operation: str
    input_tensor: TensorSpec | None
    output_tensor: TensorSpec | None


class RuntimeTraceResult(StrictModel):
    trace_id: TraceId
    request_id: TraceRequestId
    provider: RuntimeProviderId
    source_revision: Sha256
    status: TraceStatus
    failure_code: TraceFailureCode | None
    message: str | None
    environment: RuntimeEnvironment
    observations: list[RuntimeNodeObservation]
    coverage_gaps: list[str]
    elapsed_ms: int = Field(ge=0)
    peak_memory_bytes: int | None = Field(default=None, ge=0)
    worker_exit_code: int | None
    stdout: str
    stderr: str
    stderr_truncated: bool

    @model_validator(mode="after")
    def result_status_is_consistent(self) -> RuntimeTraceResult:
        if self.status is TraceStatus.SUCCEEDED and self.failure_code is not None:
            raise ValueError("successful trace must not have a failure_code")
        if self.status is not TraceStatus.SUCCEEDED and self.failure_code is None:
            raise ValueError("unsuccessful trace requires a failure_code")
        return self


class RuntimeResolution(StrictModel):
    trace_id: TraceId
    observed_node_ids: list[str]
    unobserved_node_ids: list[str]
    unmatched_runtime_targets: list[str]
