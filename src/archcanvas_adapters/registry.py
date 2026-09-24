from __future__ import annotations

import importlib.metadata
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from archcanvas_core.models import FrameworkAdapterCapability
from archcanvas_python import AnalysisBundle, AnalysisError, analyze_project

from .onnx_adapter import analyze_onnx

ADAPTER_VERSION = "0.1.0"


class StaticAdapter(Protocol):
    framework: str
    adapter_version: str

    def analyze(self, *args: Any, **kwargs: Any) -> AnalysisBundle: ...


class RuntimeAdapter(Protocol):
    framework: str
    adapter_id: str
    adapter_version: str

    def execute(self, request: dict[str, Any]) -> dict[str, Any]: ...


class TransactionAdapter(Protocol):
    framework: str
    adapter_id: str
    adapter_version: str


@dataclass(frozen=True)
class RuntimeAdapterRegistration:
    framework: str
    adapter_id: str
    adapter_version: str
    worker_module: str
    required_packages: tuple[str, ...]
    observation_mechanism: str
    environment: tuple[tuple[str, str], ...] = ()


RUNTIME_ADAPTERS = {
    "pytorch": RuntimeAdapterRegistration(
        framework="pytorch",
        adapter_id="runtime:pytorch-hooks-v1",
        adapter_version=ADAPTER_VERSION,
        worker_module="archcanvas_adapters.pytorch_runtime",
        required_packages=("torch",),
        observation_mechanism="pytorch-module-hooks-v1",
    ),
    "keras": RuntimeAdapterRegistration(
        framework="keras",
        adapter_id="runtime:keras-call-v1",
        adapter_version=ADAPTER_VERSION,
        worker_module="archcanvas_adapters.keras_runtime",
        required_packages=("keras",),
        observation_mechanism="keras-layer-call-v1",
        environment=(("KERAS_BACKEND", "torch"),),
    ),
    "jax": RuntimeAdapterRegistration(
        framework="jax",
        adapter_id="runtime:jaxpr-v1",
        adapter_version=ADAPTER_VERSION,
        worker_module="archcanvas_adapters.jax_runtime",
        required_packages=("jax",),
        observation_mechanism="jaxpr-eval-shape-v1",
    ),
    "onnx": RuntimeAdapterRegistration(
        framework="onnx",
        adapter_id="runtime:onnxruntime-v1",
        adapter_version=ADAPTER_VERSION,
        worker_module="archcanvas_adapters.onnx_runtime",
        required_packages=("onnx", "onnxruntime"),
        observation_mechanism="onnx-graph-outputs-v1",
    ),
}


def _package_version(name: str) -> str | None:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return None


def adapter_capabilities() -> list[FrameworkAdapterCapability]:
    onnx_version = _package_version("onnx")
    onnxruntime_version = _package_version("onnxruntime")
    keras_version = _package_version("keras")
    jax_version = _package_version("jax")
    flax_version = _package_version("flax")
    torch_version = _package_version("torch")
    return [
        FrameworkAdapterCapability(
            adapter_id="adapter:pytorch-source",
            framework="pytorch",
            adapter_version=ADAPTER_VERSION,
            status="verified",
            static_analysis=True,
            runtime_evidence=True,
            source_transactions=True,
            parameter_transactions=True,
            structural_transactions=True,
            artifact_commit=True,
            capability_status={
                "static": "verified",
                "runtime": "verified" if torch_version else "unavailable",
                "parameter_transaction": "verified",
                "structural_transaction": "verified",
                "artifact_commit": "verified",
            },
            supported_targets=["cpu", "cuda"] if torch_version else [],
            supported_forms=["nn.Module.forward", "source-only generic recovery"],
            verified_fixtures=["tier_a/*", "holdout/residual_mlp"],
            required_packages={"torch": torch_version},
        ),
        FrameworkAdapterCapability(
            adapter_id="adapter:keras-source",
            framework="keras",
            adapter_version=ADAPTER_VERSION,
            status="partial",
            static_analysis=True,
            runtime_evidence=keras_version is not None,
            source_transactions=True,
            parameter_transactions=True,
            structural_transactions=True,
            artifact_commit=True,
            capability_status={
                "static": "partial",
                "runtime": "experimental" if keras_version else "unavailable",
                "parameter_transaction": "partial",
                "structural_transaction": "partial",
                "artifact_commit": "verified",
            },
            supported_targets=["cpu"] if keras_version else [],
            supported_forms=["Model.call", "Functional builder dataflow"],
            verified_fixtures=["cross_framework/keras_subclass", "cross_framework/keras_functional"],
            required_packages={"keras": keras_version},
            limitations=[
                "Static analysis does not import TensorFlow or Keras.",
                "Runtime support is experimental until the full Functional/subclass matrix passes.",
            ],
        ),
        FrameworkAdapterCapability(
            adapter_id="adapter:jax-source",
            framework="jax",
            adapter_version=ADAPTER_VERSION,
            status="partial",
            static_analysis=True,
            runtime_evidence=jax_version is not None,
            source_transactions=True,
            parameter_transactions=True,
            structural_transactions=True,
            artifact_commit=True,
            capability_status={
                "static": "partial",
                "runtime": "experimental" if jax_version else "unavailable",
                "parameter_transaction": "partial",
                "structural_transaction": "partial",
                "artifact_commit": "verified",
            },
            supported_targets=["cpu"] if jax_version else [],
            supported_forms=["Flax-style __call__", "pure function dataflow"],
            verified_fixtures=["cross_framework/jax_flax", "cross_framework/jax_function"],
            required_packages={"jax": jax_version, "flax": flax_version},
            limitations=[
                "Static analysis does not import JAX, Flax, or Haiku.",
                "Runtime support is experimental until PRNG/state/jit/vmap/scan gates pass.",
            ],
        ),
        FrameworkAdapterCapability(
            adapter_id="adapter:onnx-graph",
            framework="onnx",
            adapter_version=ADAPTER_VERSION,
            status="partial" if onnx_version else "unavailable",
            static_analysis=onnx_version is not None,
            runtime_evidence=onnxruntime_version is not None,
            source_transactions=False,
            parameter_transactions=onnx_version is not None,
            structural_transactions=onnx_version is not None,
            artifact_commit=onnx_version is not None,
            capability_status={
                "static": "verified" if onnx_version else "unavailable",
                "runtime": "experimental" if onnxruntime_version else "unavailable",
                "parameter_transaction": "partial" if onnx_version else "unavailable",
                "structural_transaction": "partial" if onnx_version else "unavailable",
                "artifact_commit": "verified" if onnx_version else "unavailable",
            },
            supported_targets=["CPUExecutionProvider"] if onnxruntime_version else [],
            supported_forms=["ModelProto execution graph", "initializers", "symbolic shapes"],
            verified_fixtures=["cross_framework/onnx_residual"] if onnx_version else [],
            required_packages={"onnx": onnx_version, "onnxruntime": onnxruntime_version},
            limitations=[
                "External-data mutation is rejected until multi-file atomic commit is implemented.",
                "Custom operators require their provider library and are never rewritten implicitly.",
            ],
        ),
    ]


def runtime_adapter(framework: str) -> RuntimeAdapterRegistration:
    try:
        registration = RUNTIME_ADAPTERS[framework]
    except KeyError as error:
        raise AnalysisError(
            "RUNTIME_ADAPTER_UNAVAILABLE", f"no runtime adapter is registered for {framework}"
        ) from error
    missing = [name for name in registration.required_packages if _package_version(name) is None]
    if missing:
        raise AnalysisError(
            "ADAPTER_DEPENDENCY_MISSING",
            f"{framework} runtime requires optional packages: {', '.join(missing)}",
        )
    return registration


def apply_model_transaction(request: Any, architecture: Any, snapshot: Any) -> Any:
    if architecture.framework != "onnx":
        raise AnalysisError(
            "MODEL_TRANSACTION_UNAVAILABLE",
            f"no model-artifact transaction adapter is registered for {architecture.framework}",
        )
    from .onnx_transactions import apply_transaction

    return apply_transaction(request, architecture, snapshot)


def validate_model_transaction_delta(
    request: Any, before: Any, after: Any, delta: Any
) -> None:
    if before.framework != "onnx":
        raise AnalysisError(
            "MODEL_TRANSACTION_UNAVAILABLE",
            f"no model-artifact delta validator is registered for {before.framework}",
        )
    from .onnx_transactions import validate_delta

    validate_delta(request, before, after, delta)


def validate_model_artifact(framework: str, path: Path) -> None:
    if framework != "onnx":
        raise AnalysisError(
            "MODEL_TRANSACTION_UNAVAILABLE",
            f"no model-artifact validator is registered for {framework}",
        )
    from .onnx_transactions import validate_artifact

    validate_artifact(path)


def transaction_artifact_kind(framework: str) -> str:
    if framework == "onnx":
        return "model-artifact"
    if framework in {"pytorch", "keras", "jax"}:
        return "source-artifact"
    raise AnalysisError(
        "TRANSACTION_ADAPTER_UNAVAILABLE",
        f"no transaction artifact kind is registered for {framework}",
    )


def transaction_adapter_id(framework: str) -> str:
    suffix = "modelproto" if framework == "onnx" else "source"
    transaction_artifact_kind(framework)
    return f"transaction:{framework}-{suffix}-v1"


def resolve_framework(project: Path, entrypoint: str, requested: str) -> str:
    if requested != "auto":
        return requested
    if entrypoint.lower().endswith(".onnx") or project.suffix.lower() == ".onnx":
        return "onnx"
    raise AnalysisError(
        "FRAMEWORK_REQUIRED",
        "auto detection is deterministic only for .onnx; pass --framework for Python source",
    )


def analyze_with_adapter(
    project: Path,
    entrypoint: str,
    task: str,
    execution_mode: str,
    config_bytes: bytes,
    config_path: Path | None,
    *,
    framework: str,
    pattern_packs_enabled: bool,
) -> AnalysisBundle:
    selected = resolve_framework(project, entrypoint, framework)
    if selected == "onnx":
        return analyze_onnx(
            project,
            entrypoint,
            task,
            execution_mode,
            config_bytes,
            config_path,
        )
    if selected not in {"pytorch", "keras", "jax"}:
        raise AnalysisError("FRAMEWORK_UNSUPPORTED", f"unsupported framework: {selected}")
    return analyze_project(
        project,
        entrypoint,
        task,
        execution_mode,
        config_bytes,
        config_path,
        pattern_packs_enabled=pattern_packs_enabled,
        framework=selected,
    )
