from __future__ import annotations

import hashlib
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


def _record(value: Any) -> dict[str, Any]:
    device = getattr(value, "device", None)
    if callable(device):
        device = device()
    return {
        "shape": [int(item) for item in value.shape],
        "dtype": str(value.dtype),
        "device": str(device or "jax"),
        "requires_grad": None,
        "trainable": None,
        "attributes": {"sharding": str(getattr(value, "sharding", ""))},
    }


def _tree_digest(tree: Any, jax: Any, numpy: Any) -> str:
    result = hashlib.sha256()
    for value in jax.tree_util.tree_leaves(tree):
        array = numpy.asarray(value)
        result.update(str(array.dtype).encode())
        result.update(str(tuple(array.shape)).encode())
        result.update(array.tobytes())
    return result.hexdigest()


def execute(request: dict[str, Any]) -> dict[str, Any]:
    import jax
    import jax.numpy as jnp
    import numpy as np

    spec = request["input_spec"]
    selected = spec.get("selected_target") or spec["device"]
    if selected == "auto":
        selected = jax.default_backend()
    available = sorted({device.platform for device in jax.devices()})
    if selected not in available:
        raise RuntimeError(f"JAX platform {selected!r} is unavailable; available platforms: {available}")
    target = resolve_entrypoint(Path(request["project_root"]).resolve(), request["entrypoint"])
    inputs = {
        item["name"]: jnp.asarray(numpy_input(item, np, spec["seed"] + index))
        for index, item in enumerate(spec["inputs"])
    }
    static_args = spec.get("static_args", {})
    params_digest = None
    state_digest = None
    limitations: list[str] = []
    try:
        from flax import linen as nn
    except ImportError:
        nn = None
    if inspect.isclass(target) and nn is not None and issubclass(target, nn.Module):
        module = target(**constructor_kwargs(target, request))
        key = jax.random.PRNGKey(spec["seed"])
        variables = module.init(key, **inputs, **static_args)
        params = variables.get("params", {})
        state = {name: value for name, value in variables.items() if name != "params"}
        params_digest = _tree_digest(params, jax, np)
        state_digest = _tree_digest(state, jax, np)

        def callable_target(**values: Any) -> Any:
            return module.apply(variables, **values, **static_args)

        limitations.append("Flax intermediates are represented by JAXPR primitives in this version.")
    else:
        callable_target = lambda **values: target(**values, **static_args)
    closed = jax.make_jaxpr(callable_target)(**inputs)
    shaped = jax.eval_shape(callable_target, **inputs)
    output = callable_target(**inputs)
    observations: list[dict[str, Any]] = []
    for index, equation in enumerate(closed.jaxpr.eqns):
        primitive = equation.primitive.name
        outputs = []
        for variable in equation.outvars:
            aval = getattr(variable, "aval", None)
            if aval is None or not hasattr(aval, "shape"):
                continue
            outputs.append(
                {
                    "shape": [int(item) for item in aval.shape],
                    "dtype": str(aval.dtype),
                    "device": selected,
                    "requires_grad": None,
                    "trainable": None,
                }
            )
        observations.append(
            {
                "module_path": f"jaxpr.{index}.{primitive}",
                "module_type": primitive,
                "input_tensors": [],
                "output_tensors": outputs,
                "matched_node_ids": matched_nodes(request, primitive, f"jaxpr.{primitive}"),
                "attributes": {"params": sorted(equation.params)},
            }
        )
    output_records = [
        _record(value)
        for value in flatten(output, lambda item: hasattr(item, "shape") and hasattr(item, "dtype"))
    ]
    observations.append(
        {
            "module_path": "<root>",
            "module_type": "jaxpr",
            "input_tensors": [_record(value) for value in inputs.values()],
            "output_tensors": output_records,
            "matched_node_ids": matched_nodes(request, "<root>"),
            "attributes": {"eval_shape": str(shaped)},
        }
    )
    return {
        "observations": observations,
        "output_tensors": output_records,
        "params_digest": params_digest,
        "state_digest": state_digest,
        "environment": {
            "python_version": request["runtime_python_version"],
            "platform": request["runtime_platform"],
            "adapter_id": "runtime:jaxpr-v1",
            "framework": "jax",
            "framework_version": jax.__version__,
            "backend": "xla",
            "backend_version": None,
            "selected_target": selected,
            "available_targets": [{"kind": "platform", "id": item} for item in available],
            "observation_mechanism": "jaxpr-eval-shape-v1",
        },
        "limitations": limitations,
    }
