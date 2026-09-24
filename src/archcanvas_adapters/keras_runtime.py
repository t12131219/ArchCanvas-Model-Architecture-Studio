from __future__ import annotations

import hashlib
import importlib.metadata
import inspect
from pathlib import Path
from typing import Any

from .runtime_common import (
    constructor_kwargs,
    flatten,
    matched_nodes,
    numpy_input,
    resolve_entrypoint,
)


def _record(value: Any, keras: Any) -> dict[str, Any]:
    backend = keras.backend.backend()
    return {
        "shape": [int(item) for item in value.shape],
        "dtype": str(value.dtype).removeprefix("torch."),
        "device": str(getattr(value, "device", backend)),
        "requires_grad": bool(getattr(value, "requires_grad", False)),
        "trainable": bool(getattr(value, "requires_grad", False)),
    }


def execute(request: dict[str, Any]) -> dict[str, Any]:
    import keras
    import numpy as np

    spec = request["input_spec"]
    keras.utils.set_random_seed(spec["seed"])
    backend = keras.backend.backend()
    determinism_limitations: list[str] = []
    if backend == "torch":
        import torch

        torch.use_deterministic_algorithms(True)
    else:
        determinism_limitations.append(
            f"Deterministic kernel enforcement is not registered for the {backend} backend."
        )
    target = resolve_entrypoint(Path(request["project_root"]).resolve(), request["entrypoint"])
    form = "subclassed-model-call" if inspect.isclass(target) else "functional-builder"
    if inspect.isclass(target):
        model = target(**constructor_kwargs(target, request))
    else:
        built = target(**constructor_kwargs(target, request))
        if isinstance(built, keras.Model):
            model = built
        elif keras.backend.is_keras_tensor(built):
            model = keras.Model(keras.utils.get_source_inputs(built), built)
        else:
            output_leaves = flatten(built, keras.backend.is_keras_tensor)
            if not output_leaves:
                raise RuntimeError(
                    "Keras entrypoint must construct a Model or return KerasTensor outputs"
                )
            source_inputs: list[Any] = []
            seen_sources: set[int] = set()
            for output_leaf in output_leaves:
                for source_input in keras.utils.get_source_inputs(output_leaf):
                    if id(source_input) not in seen_sources:
                        source_inputs.append(source_input)
                        seen_sources.add(id(source_input))
            model = keras.Model(source_inputs, built)
    numpy_inputs = {
        item["name"]: numpy_input(item, np, spec["seed"] + index)
        for index, item in enumerate(spec["inputs"])
    }
    inputs = {name: keras.ops.convert_to_tensor(value) for name, value in numpy_inputs.items()}
    observations: list[dict[str, Any]] = []
    original_calls: list[tuple[Any, Any]] = []

    def wrap(layer: Any, path: str) -> None:
        original = layer.call

        def observed_call(*args: Any, **kwargs: Any) -> Any:
            output = original(*args, **kwargs)
            observations.append(
                {
                    "module_path": path,
                    "module_type": layer.__class__.__name__,
                    "input_tensors": [
                        _record(value, keras)
                        for value in flatten(args, lambda item: keras.ops.is_tensor(item))
                    ],
                    "output_tensors": [
                        _record(value, keras)
                        for value in flatten(output, lambda item: keras.ops.is_tensor(item))
                    ],
                    "matched_node_ids": matched_nodes(request, path, f"self.{path}", layer.name),
                }
            )
            return output

        original_calls.append((layer, original))
        layer.call = observed_call

    for layer in getattr(model, "layers", []):
        wrap(layer, layer.name)
    try:
        training = request["execution_mode"] == "train"
        if getattr(model, "inputs", None):
            call_value: Any = next(iter(inputs.values())) if len(inputs) == 1 else inputs
            output = model(call_value, training=training, **spec.get("forward_kwargs", {}))
        else:
            output = model(**inputs, training=training, **spec.get("forward_kwargs", {}))
    finally:
        for layer, original in original_calls:
            layer.call = original
    output_records = [
        _record(value, keras)
        for value in flatten(output, lambda item: keras.ops.is_tensor(item))
    ]
    observations.append(
        {
            "module_path": "<root>",
            "module_type": model.__class__.__name__,
            "input_tensors": [
                _record(value, keras)
                for value in flatten(inputs, lambda item: keras.ops.is_tensor(item))
            ],
            "output_tensors": output_records,
            "matched_node_ids": matched_nodes(request, "<root>"),
        }
    )
    parameter_hash = hashlib.sha256()
    for weight in sorted(model.weights, key=lambda item: item.path):
        array = keras.ops.convert_to_numpy(weight)
        parameter_hash.update(weight.path.encode())
        parameter_hash.update(str(array.dtype).encode())
        parameter_hash.update(str(tuple(array.shape)).encode())
        parameter_hash.update(array.tobytes())
    return {
        "observations": observations,
        "output_tensors": output_records,
        "params_digest": parameter_hash.hexdigest(),
        "environment": {
            "python_version": request["runtime_python_version"],
            "platform": request["runtime_platform"],
            "adapter_id": "runtime:keras-call-v1",
            "framework": "keras",
            "framework_version": keras.__version__,
            "backend": backend,
            "backend_version": importlib.metadata.version(backend),
            "selected_target": spec.get("selected_target") or spec["device"],
            "available_targets": [{"kind": "device", "id": "cpu"}],
            "observation_mechanism": "keras-layer-call-v1",
            "determinism_achieved": not determinism_limitations,
            "determinism_limitations": determinism_limitations,
            "runtime_context": {
                "form": form,
                "training": training,
                "custom_train_step_observed": False,
                "input_structure": "single" if len(inputs) == 1 else "mapping",
                "output_count": len(output_records),
            },
        },
        "limitations": [
            "Custom train_step is outside this adapter; runtime evidence covers Model.call only."
        ],
    }
