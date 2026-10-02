from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RETIRED_FAMILIES = ("autoformer", "itransformer", "patchtst", "timemixer")
PRODUCTION_ANALYSIS_PATHS = (
    ROOT / "src" / "archcanvas_python" / "analyzer.py",
    ROOT / "src" / "archcanvas_python" / "frontend_v2.py",
    ROOT / "src" / "archcanvas_adapters" / "registry.py",
    ROOT / "src" / "archcanvas_engine" / "cli.py",
    ROOT / "src" / "archcanvas_studio" / "server.py",
)


def test_production_analysis_does_not_import_retired_family_analyzers() -> None:
    for path in PRODUCTION_ANALYSIS_PATHS:
        source = path.read_text(encoding="utf-8")
        for family in RETIRED_FAMILIES:
            assert f"from .{family} import" not in source, path
            assert f"analyze_{family}(" not in source, path


def test_legacy_family_dispatch_is_isolated_from_package_exports() -> None:
    package_source = (ROOT / "src" / "archcanvas_python" / "__init__.py").read_text(
        encoding="utf-8"
    )
    assert "legacy_profiles" not in package_source
    assert "analyze_project_legacy" not in package_source
