"""Explicit compatibility entrypoint for retired family-specific analyzers.

Production analysis uses ``analyze_project_v2`` or the generic v1 analyzer. This
module exists only to keep historical golden tests readable while the old
family analyzers remain as comparison oracles.
"""

from __future__ import annotations

from pathlib import Path

from .analyzer import AnalysisBundle, _parse_config, analyze_project


def analyze_project_legacy(
    project: Path,
    entrypoint: str,
    task: str,
    execution_mode: str,
    config_bytes: bytes = b"{}",
    config_path: Path | None = None,
    *,
    pattern_packs_enabled: bool = True,
    framework: str = "pytorch",
    execution_method: str | None = None,
) -> AnalysisBundle:
    """Run a retired family analyzer when an old golden explicitly requests it."""

    config = _parse_config(config_bytes, config_path)
    profile = config.get("architecture_profile")
    if framework == "pytorch" and pattern_packs_enabled and profile == "autoformer":
        from .autoformer import analyze_autoformer

        return analyze_autoformer(
            project,
            entrypoint,
            task,
            execution_mode,
            config,
            config_bytes,
            config_path,
        )
    if framework == "pytorch" and pattern_packs_enabled and profile == "itransformer":
        from .itransformer import analyze_itransformer

        return analyze_itransformer(
            project,
            entrypoint,
            task,
            execution_mode,
            config,
            config_bytes,
            config_path,
        )
    if framework == "pytorch" and pattern_packs_enabled and profile == "patchtst":
        from .patchtst import analyze_patchtst

        return analyze_patchtst(
            project,
            entrypoint,
            task,
            execution_mode,
            config,
            config_bytes,
            config_path,
        )
    if framework == "pytorch" and pattern_packs_enabled and profile == "timemixer":
        from .timemixer import analyze_timemixer

        return analyze_timemixer(
            project,
            entrypoint,
            task,
            execution_mode,
            config,
            config_bytes,
            config_path,
        )
    return analyze_project(
        project,
        entrypoint,
        task,
        execution_mode,
        config_bytes,
        config_path,
        pattern_packs_enabled=pattern_packs_enabled,
        framework=framework,
        execution_method=execution_method,
    )
