from __future__ import annotations

import argparse
import json
import shutil
import signal
import sys
import tempfile
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY / "src"))


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Serve the isolated Studio browser fixture.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=4311)
    parser.add_argument(
        "--fixture",
        choices=("transformer", "frontend-v2"),
        default="transformer",
    )
    return parser


def _write_json(path: Path, value: object) -> None:
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json")
    elif isinstance(value, list):
        value = [
            item.model_dump(mode="json") if hasattr(item, "model_dump") else item
            for item in value
        ]
    path.write_text(json.dumps(value, sort_keys=True), encoding="utf-8")


def main() -> int:
    from archcanvas_python import analyze_project, analyze_project_v2
    from archcanvas_studio import prepare_studio_bundle
    from archcanvas_studio.server import create_studio_server

    args = _parser().parse_args()
    fixture = (
        REPOSITORY / "fixtures" / "tier_a" / "transformer"
        if args.fixture == "transformer"
        else REPOSITORY / "tests" / "fixtures" / "frontend_v2" / "conv_relu"
    )
    temporary_root = Path(tempfile.mkdtemp(prefix="archcanvas-studio-e2e-"))
    project = temporary_root / "project"
    analysis = temporary_root / "analysis"
    workspace = temporary_root / "workspace"
    shutil.copytree(fixture, project)
    analysis.mkdir()

    if args.fixture == "transformer":
        analyzed = analyze_project(
            project,
            "model:Transformer",
            "inference",
            "eval",
            (project / "config.json").read_bytes(),
            project / "config.json",
        )
        _write_json(analysis / "architecture.json", analyzed.architecture)
        _write_json(analysis / "source-snapshot.json", analyzed.snapshot)
        _write_json(analysis / "evidence-ledger.json", analyzed.evidence)
    else:
        analyzed_v2 = analyze_project_v2(
            project,
            "app.model:Model",
            "inference",
            "eval",
            analysis / ".frontend-v2",
        )
        _write_json(analysis / "architecture.json", analyzed_v2.compatibility.architecture)
        _write_json(analysis / "source-snapshot.json", analyzed_v2.compatibility.snapshot)
        _write_json(analysis / "evidence-ledger.json", analyzed_v2.compatibility.evidence)
        _write_json(analysis / "project-manifest-v2.json", analyzed_v2.manifest)
        _write_json(analysis / "source-corpus-v2.json", analyzed_v2.corpus)
        _write_json(
            analysis / "analysis-environment-manifest-v1.json",
            analyzed_v2.environment_manifest,
        )
        _write_json(analysis / "analysis-input-v2.json", analyzed_v2.analysis_input)
        _write_json(analysis / "semantic-graph-v2.json", analyzed_v2.semantic_graph)
        _write_json(analysis / "architecture-v2.json", analyzed_v2.exact_ir)
    bundle = prepare_studio_bundle(analysis / "architecture.json", workspace)
    server = create_studio_server(bundle, args.host, args.port)

    def stop_server(_signum: int, _frame: object) -> None:
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, stop_server)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        shutil.rmtree(temporary_root, ignore_errors=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
