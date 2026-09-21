"""Worker-local runtime trace providers.

This module intentionally imports PyTorch only inside the spawned worker process.
"""

from __future__ import annotations

from typing import Protocol

from archcanvas_core.models.runtime import (
    RuntimeNodeObservation,
    RuntimeProviderId,
    TraceCapability,
    TraceRequest,
)


class RuntimeTraceProvider(Protocol):
    provider_id: RuntimeProviderId

    def can_trace(self, request: TraceRequest) -> TraceCapability: ...

    def trace(self, model: object, inputs: tuple[object, ...]) -> list[RuntimeNodeObservation]: ...


def _tensor_spec(value: object):
    import torch

    from archcanvas_core.models.architecture import TensorSpec

    if not isinstance(value, torch.Tensor):
        return None
    return TensorSpec(
        shape=list(value.shape),
        dtype=str(value.dtype).removeprefix("torch."),
        device=str(value.device),
        requires_grad=value.requires_grad,
        semantic_axes=[],
    )


def _node_tensor_specs(node: object):
    meta = getattr(node, "meta", {})
    tensor_meta = meta.get("tensor_meta") if isinstance(meta, dict) else None
    if tensor_meta is None:
        return None, None
    shape = list(tensor_meta.shape)
    output = _tensor_spec_from_meta(shape, tensor_meta)
    return None, output


def _tensor_spec_from_meta(shape: list[int], tensor_meta: object):
    from archcanvas_core.models.architecture import TensorSpec

    dtype = getattr(tensor_meta, "dtype", None)
    return TensorSpec(
        shape=[int(dimension) for dimension in shape],
        dtype=str(dtype).removeprefix("torch.") if dtype is not None else None,
        device=None,
        requires_grad=getattr(tensor_meta, "requires_grad", None),
        semantic_axes=[],
    )


class FxTraceProvider:
    provider_id = RuntimeProviderId.TORCH_FX

    def can_trace(self, request: TraceRequest) -> TraceCapability:
        return TraceCapability(provider=self.provider_id, supported=True, reason=None)

    def trace(self, model: object, inputs: tuple[object, ...]) -> list[RuntimeNodeObservation]:
        from torch.fx import symbolic_trace
        from torch.fx.passes.shape_prop import ShapeProp

        graph_module = symbolic_trace(model)
        ShapeProp(graph_module).propagate(*inputs)
        observations: list[RuntimeNodeObservation] = []
        for node in graph_module.graph.nodes:
            if node.op not in {"placeholder", "call_module", "call_function", "call_method", "output"}:
                continue
            input_tensor, output_tensor = _node_tensor_specs(node)
            observations.append(
                RuntimeNodeObservation(
                    target=str(node.target),
                    operation=node.op,
                    input_tensor=input_tensor,
                    output_tensor=output_tensor,
                )
            )
        return observations


class TorchExportTraceProvider:
    provider_id = RuntimeProviderId.TORCH_EXPORT

    def can_trace(self, request: TraceRequest) -> TraceCapability:
        try:
            import torch

            supported = hasattr(torch, "export")
        except ImportError:
            supported = False
        return TraceCapability(
            provider=self.provider_id,
            supported=supported,
            reason=None if supported else "torch.export is unavailable in the configured environment",
        )

    def trace(self, model: object, inputs: tuple[object, ...]) -> list[RuntimeNodeObservation]:
        import torch

        exported = torch.export.export(model, inputs)
        observations: list[RuntimeNodeObservation] = []
        for node in exported.graph_module.graph.nodes:
            if node.op not in {"placeholder", "call_function", "output"}:
                continue
            input_tensor, output_tensor = _node_tensor_specs(node)
            observations.append(
                RuntimeNodeObservation(
                    target=str(node.target),
                    operation=node.op,
                    input_tensor=input_tensor,
                    output_tensor=output_tensor,
                )
            )
        return observations


def provider_for(provider_id: RuntimeProviderId) -> RuntimeTraceProvider:
    if provider_id is RuntimeProviderId.TORCH_FX:
        return FxTraceProvider()
    if provider_id is RuntimeProviderId.TORCH_EXPORT:
        return TorchExportTraceProvider()
    raise ValueError(f"unsupported runtime provider: {provider_id}")
