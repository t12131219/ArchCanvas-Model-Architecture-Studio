from __future__ import annotations

import hashlib
import inspect
import json
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
    input_prng_digests = {
        name: hashlib.sha256(np.asarray(value).tobytes()).hexdigest()
        for name, value in inputs.items()
        if "key" in name.lower() or "prng" in name.lower()
    }
    static_args = spec.get("static_args", {})
    params_digest = None
    state_digest = None
    prng_digest = None
    params_tree = None
    state_tree = None
    limitations: list[str] = []
    try:
        from flax import linen as nn
    except ImportError:
        nn = None
    if inspect.isclass(target) and nn is not None and issubclass(target, nn.Module):
        module = target(**constructor_kwargs(target, request))
        key = jax.random.PRNGKey(spec["seed"])
        prng_digest = hashlib.sha256(np.asarray(key).tobytes()).hexdigest()
        variables = module.init(key, **inputs, **static_args)
        params = variables.get("params", {})
        state = {name: value for name, value in variables.items() if name != "params"}
        params_digest = _tree_digest(params, jax, np)
        state_digest = _tree_digest(state, jax, np)
        params_tree = str(jax.tree_util.tree_structure(params))
        state_tree = str(jax.tree_util.tree_structure(state))

        def callable_target(**values: Any) -> Any:
            return module.apply(variables, **values, **static_args)

        limitations.append("Flax intermediates are represented by JAXPR primitives in this version.")
    else:
        callable_target = lambda **values: target(**values, **static_args)
    closed = jax.make_jaxpr(callable_target)(**inputs)
    shaped = jax.eval_shape(callable_target, **inputs)
    output = callable_target(**inputs)
    output_tree = str(jax.tree_util.tree_structure(output))
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
            "runtime_context": {
                "form": "flax-module" if inspect.isclass(target) else "pure-function",
                "prng_seed": spec["seed"],
                "prng_digest": prng_digest,
                "input_prng_digests": input_prng_digests,
                "static_args_digest": hashlib.sha256(
                    json.dumps(static_args, sort_keys=True, separators=(",", ":")).encode()
                ).hexdigest(),
                "params_pytree": params_tree,
                "state_pytree": state_tree,
                "output_pytree": output_tree,
                "transform_primitives": sorted(
                    {
                        equation.primitive.name
                        for equation in closed.jaxpr.eqns
                        if equation.primitive.name in {"jit", "pjit", "scan", "while", "xla_call"}
                    }
                ),
            },
        },
        "limitations": limitations,
    }
