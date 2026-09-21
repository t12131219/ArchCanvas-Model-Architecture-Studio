"""Run an explicitly authorized PyTorch runtime trace from a current source identity document."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from archcanvas_core.models.runtime import NetworkPolicy, RuntimeProviderId, RuntimeTensorInput
from archcanvas_core.models.source_identity import SourceIdentityDocument
from archcanvas_pytorch.runtime import IsolatedTraceWorker
from archcanvas_pytorch.runtime.request_factory import TraceRequestFactory, TraceRequestRejected


def _shape(value: str) -> list[int]:
    try:
        result = [int(part) for part in value.split(",")]
    except ValueError as error:
        raise argparse.ArgumentTypeError("shape must be comma-separated integers") from error
    if not result:
        raise argparse.ArgumentTypeError("shape must not be empty")
    return result


def _json_object(value: str) -> dict[str, object]:
    try:
        result = json.loads(value)
    except json.JSONDecodeError as error:
        raise argparse.ArgumentTypeError("constructor JSON must be valid") from error
    if not isinstance(result, dict):
        raise argparse.ArgumentTypeError("constructor JSON must be an object")
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true", help="acknowledge that this executes project code")
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--source-identity", type=Path, required=True)
    parser.add_argument("--entrypoint", required=True)
    parser.add_argument("--request-id", required=True)
    parser.add_argument("--python", dest="python_executable", default=sys.executable)
    parser.add_argument("--provider", choices=[item.value for item in RuntimeProviderId], default="torch_fx")
    parser.add_argument("--input-shape", type=_shape, required=True)
    parser.add_argument("--input-dtype", choices=["float32", "float64", "int64", "int32", "bool"], required=True)
    parser.add_argument("--constructor-json", type=_json_object, default={})
    parser.add_argument("--timeout-seconds", type=int, default=30)
    parser.add_argument("--memory-limit-mb", type=int, default=4096)
    parser.add_argument("--network-policy", choices=[item.value for item in NetworkPolicy], default="deny")
    parser.add_argument("--environment-name")
    parser.add_argument("--dependency-lockfile")
    return parser


def main(argv: list[str] | None = None) -> int:
    arguments = build_parser().parse_args(argv)
    if not arguments.execute:
        print(
            json.dumps(
                {
                    "status": "rejected",
                    "code": "EXECUTION_NOT_ACKNOWLEDGED",
                    "message": "pass --execute to run project code in an isolated worker",
                }
            ),
            file=sys.stderr,
        )
        return 2
    try:
        source = SourceIdentityDocument.model_validate_json(arguments.source_identity.read_bytes())
        request = TraceRequestFactory().build(
            request_id=arguments.request_id,
            project_root=arguments.project_root,
            source=source,
            entrypoint=arguments.entrypoint,
            python_executable=arguments.python_executable,
            inputs=[RuntimeTensorInput(shape=arguments.input_shape, dtype=arguments.input_dtype)],
            provider=RuntimeProviderId(arguments.provider),
            constructor_kwargs=arguments.constructor_json,
            timeout_seconds=arguments.timeout_seconds,
            memory_limit_mb=arguments.memory_limit_mb,
            network_policy=NetworkPolicy(arguments.network_policy),
            environment_name=arguments.environment_name,
            dependency_lockfile=arguments.dependency_lockfile,
        )
    except (OSError, TraceRequestRejected, ValueError) as error:
        code = error.code if isinstance(error, TraceRequestRejected) else "TRACE_REQUEST_INVALID"
        print(json.dumps({"status": "rejected", "code": code, "message": str(error)}), file=sys.stderr)
        return 2
    print(IsolatedTraceWorker().run(request).model_dump_json())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
