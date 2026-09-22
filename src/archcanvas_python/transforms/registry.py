"""Explicit allow-list for Stage 7 literal parameter transforms.

The source transform remains generic and CST-backed, but Engine transactions must only expose
parameter families that have a reviewed semantic contract.  Aliases preserve existing Exact IR
field names while allowing the UI to present a stable user-facing capability.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite


@dataclass(frozen=True)
class ParameterTransformSpec:
    transform_id: str
    names: frozenset[str]
    label: str
    runtime_validation_required: bool = False

    def validate_values(self, before: object, after: object) -> str | None:
        if self.transform_id in {"num_heads", "hidden_size"}:
            if any(isinstance(value, bool) or not isinstance(value, int) or value < 1 for value in (before, after)):
                return "value must be a positive integer"
        elif self.transform_id == "dropout":
            if any(
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not isfinite(float(value))
                or not 0 <= float(value) <= 1
                for value in (before, after)
            ):
                return "value must be a finite number between 0 and 1"
        elif self.transform_id == "activation":
            supported = {"relu", "gelu"}
            if any(not isinstance(value, str) or value not in supported for value in (before, after)):
                return f"value must be one of {', '.join(sorted(supported))}"
        return None


_REGISTRY = (
    ParameterTransformSpec("num_heads", frozenset({"num_heads"}), "Number of attention heads"),
    ParameterTransformSpec("dropout", frozenset({"dropout"}), "Dropout probability"),
    ParameterTransformSpec(
        "hidden_size",
        frozenset({"hidden_size", "hidden_dim", "d_model", "dim_feedforward"}),
        "Hidden size",
        runtime_validation_required=True,
    ),
    ParameterTransformSpec("activation", frozenset({"activation"}), "Activation"),
)

_BY_NAME = {name: spec for spec in _REGISTRY for name in spec.names}


def resolve_parameter_transform(name: str) -> ParameterTransformSpec | None:
    return _BY_NAME.get(name)


def registered_parameter_names() -> frozenset[str]:
    return frozenset(_BY_NAME)


def available_parameter_names(*, runtime_validation_available: bool) -> frozenset[str]:
    """Return names that can create candidates under the active Engine capabilities."""

    return frozenset(
        name
        for name, spec in _BY_NAME.items()
        if runtime_validation_available or not spec.runtime_validation_required
    )
