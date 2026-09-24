from __future__ import annotations

from archcanvas_adapters import adapter_capabilities
from archcanvas_core.models import HostSupport, PlatformSupport, ReleaseSupportMatrix


def release_support_matrix() -> ReleaseSupportMatrix:
    return ReleaseSupportMatrix(
        release="0.1.0-stage9",
        adapters=adapter_capabilities(),
        hosts=[
            HostSupport(
                host="codex-local",
                status="verified",
                install_target=".agents/skills/archcanvas",
                limitations=["Requires Python 3.11+ and declared Python dependencies."],
            ),
            HostSupport(
                host="claude-code-local",
                status="installer-tested",
                install_target=".claude/skills/archcanvas",
                limitations=["Filesystem installer tested; Claude Code host execution not present in CI."],
            ),
            HostSupport(
                host="claude-api",
                status="unsupported",
                limitations=["No verified self-contained API runtime or dependency image."],
            ),
            HostSupport(
                host="claude.ai",
                status="unsupported",
                limitations=["Local skill installation does not synchronize to claude.ai."],
            ),
        ],
        platforms=[
            PlatformSupport(platform="linux", status="verified"),
            PlatformSupport(
                platform="macos",
                status="ci-configured",
                limitations=["Not executed on the current development host."],
            ),
            PlatformSupport(
                platform="windows",
                status="ci-configured",
                limitations=["Not executed on the current development host."],
            ),
        ],
        notes=[
            "Static analysis and artifact generation do not require network access.",
            "PyTorch remains the only framework with an entirely verified capability row.",
            "Keras, JAX, and ONNX report runtime and transaction status per declared form.",
        ],
    )
