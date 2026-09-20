"""Machine-readable capability declaration for the PyTorch static adapter."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class StaticCapabilityReport:
    adapter: str
    version: str
    supported: tuple[str, ...]
    unresolved: tuple[str, ...]
    excluded: tuple[str, ...]

    def as_dict(self) -> dict[str, object]:
        return {
            "adapter": self.adapter,
            "version": self.version,
            "supported": list(self.supported),
            "unresolved": list(self.unresolved),
            "excluded": list(self.excluded),
        }


def static_capability_report() -> StaticCapabilityReport:
    return StaticCapabilityReport(
        adapter="pytorch-static",
        version="1.0",
        supported=(
            "torch.nn import aliases",
            "direct torch.nn symbol imports",
            "single nn.Module entrypoint",
            "read-only project entrypoint discovery",
            "self module assignments",
            "ModuleList and Sequential member discovery",
            "ordered forward calls",
            "direct return through self module",
            "add residual edges with known operands",
            "torch.cat and torch.stack with known list/tuple inputs",
        ),
        unresolved=(
            "dynamic if control flow",
            "eval or exec in forward",
            "residual or merge inputs without known producers",
        ),
        excluded=(
            "arbitrary Python metaprogramming",
            "cross-file custom module topology",
            "dynamic module construction in forward",
            "runtime shape inference",
            "Keras and ONNX adapters",
        ),
    )
