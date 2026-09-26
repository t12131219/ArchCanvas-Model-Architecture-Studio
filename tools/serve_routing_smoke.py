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
    parser = argparse.ArgumentParser(description="Serve the isolated routing browser fixture.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=4311)
    return parser


def main() -> int:
    from archcanvas_python import analyze_project
    from archcanvas_studio import prepare_studio_bundle
    from archcanvas_studio.server import create_studio_server

    args = _parser().parse_args()
    fixture = REPOSITORY / "fixtures" / "tier_a" / "transformer"
    temporary_root = Path(tempfile.mkdtemp(prefix="archcanvas-routing-smoke-"))
    project = temporary_root / "project"
    analysis = temporary_root / "analysis"
    workspace = temporary_root / "workspace"
    shutil.copytree(fixture, project)
    analysis.mkdir()

    analyzed = analyze_project(
        project,
        "model:Transformer",
        "inference",
        "eval",
        (project / "config.json").read_bytes(),
        project / "config.json",
    )
    (analysis / "architecture.json").write_text(
        analyzed.architecture.model_dump_json(), encoding="utf-8"
    )
    (analysis / "source-snapshot.json").write_text(
        analyzed.snapshot.model_dump_json(), encoding="utf-8"
    )
    (analysis / "evidence-ledger.json").write_text(
        json.dumps(
            [record.model_dump(mode="json") for record in analyzed.evidence],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    bundle = prepare_studio_bundle(
        analysis / "architecture.json",
        workspace,
        routing_mode="atomic-v1",
    )
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
