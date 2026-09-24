from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from .runtime_common import constructor_kwargs, flatten, matched_nodes, resolve_entrypoint


def _state_digest(model: Any) -> str:
    result = hashlib.sha256()
    for name, value in sorted(model.state_dict().items()):
        array = value.detach().cpu().numpy()
        result.update(name.encode())
        result.update(str(array.dtype).encode())
        result.update(str(tuple(array.shape)).encode())
        result.update(array.tobytes())
    return result.hexdigest()


def _tensor_record(tensor: Any) -> dict[str, Any]:
    return {
        "shape": list(tensor.shape),
        "dtype": str(tensor.dtype).removeprefix("torch."),
        "device": str(tensor.device),
        "requires_grad": bool(tensor.requires_grad),
        "trainable": bool(tensor.requires_grad),
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
    return torch.randint(int(item["low"]), int(item["high"]), shape, dtype=dtype, device=device)


def execute(request: dict[str, Any]) -> dict[str, Any]:
    import torch

    spec = request["input_spec"]
    torch.manual_seed(spec["seed"])
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(spec["seed"])
    torch.use_deterministic_algorithms(True)
    selected = spec.get("selected_target") or spec["device"]
    if selected == "auto":
        selected = "cuda" if torch.cuda.is_available() else "cpu"
    if selected == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA was requested but is not available to the runtime worker")
    device = torch.device(selected)
    target = resolve_entrypoint(Path(request["project_root"]).resolve(), request["entrypoint"])
    model = target(**constructor_kwargs(target, request)).to(device)
    model.train(request["execution_mode"] == "train")
    observations: list[dict[str, Any]] = []
    handles = []

    def hook_for(path: str, module: Any) -> Any:
        def hook(_module: Any, inputs: Any, output: Any) -> None:
            observations.append(
                {
                    "module_path": path,
                    "module_type": module.__class__.__name__,
                    "input_tensors": [
                        _tensor_record(tensor)
                        for tensor in flatten(inputs, lambda value: isinstance(value, torch.Tensor))
                    ],
                    "output_tensors": [
                        _tensor_record(tensor)
                        for tensor in flatten(output, lambda value: isinstance(value, torch.Tensor))
                    ],
                    "matched_node_ids": matched_nodes(request, path, f"self.{path}"),
                }
            )

        return hook

    for name, module in model.named_modules():
        path = name or "<root>"
        handles.append(module.register_forward_hook(hook_for(path, module)))
    inputs = {item["name"]: _make_tensor(item, device, torch) for item in spec["inputs"]}
    with torch.inference_mode(mode=request["execution_mode"] == "eval"):
        output = model(**inputs, **spec.get("forward_kwargs", {}))
    for handle in handles:
        handle.remove()
    return {
        "observations": observations,
        "output_tensors": [
            _tensor_record(tensor)
            for tensor in flatten(output, lambda value: isinstance(value, torch.Tensor))
        ],
        "params_digest": _state_digest(model),
        "environment": {
            "python_version": request["runtime_python_version"],
            "platform": request["runtime_platform"],
            "adapter_id": "runtime:pytorch-hooks-v1",
            "framework": "pytorch",
            "framework_version": torch.__version__,
            "backend": "torch",
            "backend_version": torch.__version__,
            "selected_target": str(device),
            "available_targets": [
                {"kind": "device", "id": item}
                for item in (["cpu", "cuda"] if torch.cuda.is_available() else ["cpu"])
            ],
            "observation_mechanism": "pytorch-module-hooks-v1",
            "torch_version": torch.__version__,
            "cuda_build": torch.version.cuda,
            "cuda_available": torch.cuda.is_available(),
            "selected_device": str(device),
            "deterministic_algorithms": torch.are_deterministic_algorithms_enabled(),
        },
        "limitations": [
            "Module hooks observe module boundaries; functional operators remain static-only."
        ],
    }
