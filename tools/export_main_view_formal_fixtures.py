from __future__ import annotations

import argparse
import json
import shutil
import tempfile
from pathlib import Path
from typing import Any

from archcanvas_patterns import apply_pattern_packs, load_registry
from archcanvas_python.legacy_profiles import analyze_project_legacy as analyze_project
from archcanvas_studio import prepare_studio_bundle

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "studio" / "src" / "scene-studio" / "fixtures"
PROFILES = (
    ("transformer", "model:Transformer", "inference", True),
    ("autoformer", "models.Autoformer:Model", "long_term_forecast", True),
    ("itransformer", "model.iTransformer:Model", "long_term_forecast", True),
    ("patchtst", "models.PatchTST:Model", "long_term_forecast", True),
    ("timemixer", "models.TimeMixer:Model", "long_term_forecast", True),
    ("generic", "model:Transformer", "inference", False),
)


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )


def _formal_state(state: dict[str, Any]) -> dict[str, Any]:
    return {
        "architecture": state["architecture"],
        "hierarchy": state["hierarchy"],
        "document": {"source_digest": state["document"]["source_digest"]},
        "view_state": state["view_state"],
        "semantic_overlay": state["semantic_overlay"],
    }


def _build_profile(
    output: Path,
    name: str,
    entrypoint: str,
    task: str,
    patterns_enabled: bool,
) -> None:
    fixture_name = "transformer" if name == "generic" else name
    fixture = ROOT / "fixtures" / "tier_a" / fixture_name
    analyzed = analyze_project(
        fixture,
        entrypoint,
        task,
        "eval",
        (fixture / "config.json").read_bytes(),
        fixture / "config.json",
        pattern_packs_enabled=patterns_enabled,
    )
    overlay, _ = apply_pattern_packs(
        analyzed.architecture,
        load_registry(),
        enabled=patterns_enabled,
    )
    temporary_root = Path(tempfile.mkdtemp(prefix=f"archcanvas-formal-{name}-"))
    try:
        analysis = temporary_root / "analysis"
        analysis.mkdir()
        _write_json(analysis / "architecture.json", analyzed.architecture.model_dump(mode="json"))
        _write_json(analysis / "source-snapshot.json", analyzed.snapshot.model_dump(mode="json"))
        _write_json(
            analysis / "evidence-ledger.json",
            [record.model_dump(mode="json") for record in analyzed.evidence],
        )
        _write_json(analysis / "semantic-annotation-overlay.json", overlay.model_dump(mode="json"))
        bundle = prepare_studio_bundle(analysis / "architecture.json", temporary_root / "workspace")
        state = bundle.state()
        expandable = [
            row["id"]
            for row in state["navigation"]["projections"]["module"]["nodes"]
            if row["child_count"] > 0
        ]
        bundle.set_navigation_view(
            "module",
            expansions={"module": expandable, "source": []},
        )
        _write_json(output / f"{name}.json", _formal_state(bundle.state()))
    finally:
        shutil.rmtree(temporary_root, ignore_errors=True)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Export deterministic formal-state fixtures for the TypeScript main view."
    )
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    for profile in PROFILES:
        _build_profile(args.output, *profile)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
