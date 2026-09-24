from __future__ import annotations

import importlib.metadata
from pathlib import Path

from archcanvas_core.models import FrameworkAdapterCapability
from archcanvas_python import AnalysisBundle, AnalysisError, analyze_project

from .onnx_adapter import analyze_onnx

ADAPTER_VERSION = "0.1.0"


def _package_version(name: str) -> str | None:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return None


def adapter_capabilities() -> list[FrameworkAdapterCapability]:
    onnx_version = _package_version("onnx")
    return [
        FrameworkAdapterCapability(
            adapter_id="adapter:pytorch-source",
            framework="pytorch",
            adapter_version=ADAPTER_VERSION,
            status="supported",
            static_analysis=True,
            runtime_evidence=True,
            source_transactions=True,
            supported_forms=["nn.Module.forward", "source-only generic recovery"],
            verified_fixtures=["tier_a/*", "holdout/residual_mlp"],
            required_packages={"torch": _package_version("torch")},
        ),
        FrameworkAdapterCapability(
            adapter_id="adapter:keras-source",
            framework="keras",
            adapter_version=ADAPTER_VERSION,
            status="partial",
            static_analysis=True,
            runtime_evidence=False,
            source_transactions=False,
            supported_forms=["Model.call", "Functional builder dataflow"],
            verified_fixtures=["cross_framework/keras_subclass", "cross_framework/keras_functional"],
            required_packages={"tensorflow-or-keras": None},
            limitations=[
                "Static analysis does not import TensorFlow or Keras.",
                "Dynamic layers and framework runtime shape inference remain unresolved.",
            ],
        ),
        FrameworkAdapterCapability(
            adapter_id="adapter:jax-source",
            framework="jax",
            adapter_version=ADAPTER_VERSION,
            status="partial",
            static_analysis=True,
            runtime_evidence=False,
            source_transactions=False,
            supported_forms=["Flax-style __call__", "pure function dataflow"],
            verified_fixtures=["cross_framework/jax_flax", "cross_framework/jax_function"],
            required_packages={"jax-or-flax": None},
            limitations=[
                "Static analysis does not import JAX, Flax, or Haiku.",
                "scan bodies and parameter-tree sharing are preserved as unresolved when not explicit.",
            ],
        ),
        FrameworkAdapterCapability(
            adapter_id="adapter:onnx-graph",
            framework="onnx",
            adapter_version=ADAPTER_VERSION,
            status="supported" if onnx_version else "unavailable",
            static_analysis=onnx_version is not None,
            runtime_evidence=False,
            source_transactions=False,
            supported_forms=["ModelProto execution graph", "initializers", "symbolic shapes"],
            verified_fixtures=["cross_framework/onnx_residual"] if onnx_version else [],
            required_packages={"onnx": onnx_version},
            limitations=["External-data tensors are not loaded or executed."],
        ),
    ]


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
