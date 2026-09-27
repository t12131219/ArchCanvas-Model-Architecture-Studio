from __future__ import annotations

import os
from dataclasses import dataclass

ROUTING_MODES = ("legacy", "shadow", "atomic-v1")


@dataclass(frozen=True)
class RoutingRuntimeConfig:
    mode: str
    shadow_sample_rate: float


def routing_runtime_config(
    mode: str | None = None,
    shadow_sample_rate: float | None = None,
) -> RoutingRuntimeConfig:
    selected = mode or os.environ.get("ARCHCANVAS_ROUTING_ENGINE", "legacy")
    if selected not in ROUTING_MODES:
        raise ValueError(f"unknown routing engine mode: {selected}")
    raw_rate = (
        str(shadow_sample_rate)
        if shadow_sample_rate is not None
        else os.environ.get("ARCHCANVAS_ROUTING_SHADOW_SAMPLE_RATE", "1.0")
    )
    try:
        rate = float(raw_rate)
    except ValueError as error:
        raise ValueError("routing shadow sample rate must be a number") from error
    if not 0.0 <= rate <= 1.0:
        raise ValueError("routing shadow sample rate must be between 0 and 1")
    return RoutingRuntimeConfig(mode=selected, shadow_sample_rate=rate)
