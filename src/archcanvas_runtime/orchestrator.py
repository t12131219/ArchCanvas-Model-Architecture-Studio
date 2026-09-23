from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
from collections import defaultdict
from pathlib import Path
from typing import Any

from pydantic import TypeAdapter

from archcanvas_core.models import (
    ArchitectureIR,
    CommandReceipt,
    Confidence,
    Diagnostic,
    EvidenceKind,
    EvidenceRecord,
    GateResult,
    RuntimeBoundaryViolation,
    RuntimeCapabilityReport,
    RuntimeEnvironment,
    RuntimeInputSpec,
    RuntimeIsolation,
    RuntimeObservation,
    RuntimeTensorObservation,
    RuntimeTrace,
    SourceSnapshot,
)


class RuntimeTraceError(ValueError):
    """An invalid or stale runtime trace request."""


def _compact(value: Any) -> bytes:
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json")
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def _digest(value: Any) -> str:
    return hashlib.sha256(_compact(value)).hexdigest()


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json")
    text = json.dumps(
        value,
        default=lambda item: item.model_dump(mode="json"),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ) + "\n"
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, delete=False
    ) as handle:
        handle.write(text)
        temporary = Path(handle.name)
    temporary.replace(path)


def _verify_snapshot(snapshot: SourceSnapshot) -> None:
    project = Path(snapshot.project_root).resolve()
    if not project.is_dir():
        raise RuntimeTraceError("source snapshot project root is unavailable")
    for source in snapshot.source_files:
        path = (project / source.path).resolve()
        if not path.is_relative_to(project) or not path.is_file():
            raise RuntimeTraceError(f"source snapshot file is unavailable: {source.path}")
        if hashlib.sha256(path.read_bytes()).hexdigest() != source.sha256:
            raise RuntimeTraceError(f"source snapshot is stale: {source.path}")


def _protected_digests(artifact: Path, snapshot: SourceSnapshot) -> dict[Path, str]:
    project = Path(snapshot.project_root).resolve()
    candidates = [
        artifact,
        artifact.parent / "source-snapshot.json",
        artifact.parent / "evidence-ledger.json",
        artifact.parent / "module-ledger.json",
        artifact.parent / "tensor-ledger.json",
        artifact.parent / "edge-ledger.json",
        *((project / source.path).resolve() for source in snapshot.source_files),
    ]
    return {
        path: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in candidates
        if path.is_file()
    }


def _limit_process(spec: RuntimeInputSpec) -> Any:
    def apply() -> None:
        import resource

        memory_bytes = spec.memory_limit_mb * 1024 * 1024
        resource.setrlimit(resource.RLIMIT_AS, (memory_bytes, memory_bytes))
        resource.setrlimit(
            resource.RLIMIT_CPU,
            (spec.cpu_limit_seconds, spec.cpu_limit_seconds + 1),
        )
        resource.setrlimit(resource.RLIMIT_FSIZE, (16 * 1024 * 1024, 16 * 1024 * 1024))
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
        resource.setrlimit(resource.RLIMIT_NOFILE, (64, 64))

    return apply


def _worker_environment(sandbox: Path, device: str) -> dict[str, str]:
    allowed = {
        "CONDA_DEFAULT_ENV",
        "CONDA_PREFIX",
        "CUDA_VISIBLE_DEVICES",
        "LANG",
        "LC_ALL",
        "LD_LIBRARY_PATH",
        "MKL_NUM_THREADS",
        "OMP_NUM_THREADS",
        "PATH",
    }
    environment = {key: value for key, value in os.environ.items() if key in allowed}
    environment.update(
        {
            "HOME": str(sandbox),
            "XDG_CACHE_HOME": str(sandbox / "cache"),
            "TORCH_HOME": str(sandbox / "torch"),
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONHASHSEED": "0",
        }
    )
    if device == "cpu":
        environment["CUDA_VISIBLE_DEVICES"] = ""
    return environment


def _run_worker(
    ir: ArchitectureIR,
    snapshot: SourceSnapshot,
    spec: RuntimeInputSpec,
) -> dict[str, Any]:
    worker = Path(__file__).with_name("worker.py")
    with tempfile.TemporaryDirectory(prefix="archcanvas-runtime-") as directory:
        sandbox = Path(directory).resolve()
        request_path = sandbox / "request.json"
        response_path = sandbox / "response.json"
        log_path = sandbox / "worker.log"
        match_paths: dict[str, list[str]] = defaultdict(list)
        for node in ir.nodes:
            module_path = node.attributes.get("module_path")
            if isinstance(module_path, str):
                match_paths[module_path.removeprefix("self.")].append(node.node_id)
            if node.parent_id is None:
                match_paths["<root>"].append(node.node_id)
        request = {
            "project_root": snapshot.project_root,
            "entrypoint": snapshot.entrypoint,
            "execution_mode": snapshot.execution_mode,
            "resolved_config": snapshot.resolved_config,
            "input_spec": spec.model_dump(mode="json"),
            "match_paths": dict(match_paths),
            "sandbox_root": str(sandbox),
            "response_path": str(response_path),
        }
        request_path.write_bytes(_compact(request))
        try:
            with log_path.open("w", encoding="utf-8") as log:
                completed = subprocess.run(
                    [sys.executable, "-I", str(worker), str(request_path)],
                    cwd=sandbox,
                    env=_worker_environment(sandbox, spec.device),
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    text=True,
                    timeout=spec.timeout_seconds,
                    check=False,
                    preexec_fn=_limit_process(spec),
                )
        except subprocess.TimeoutExpired:
            return {
                "status": "failed",
                "error_type": "RuntimeTimeout",
                "message": f"runtime worker exceeded {spec.timeout_seconds} seconds",
                "violations": [],
            }
        if not response_path.is_file():
            log_text = log_path.read_text(encoding="utf-8", errors="replace")[-4096:]
            message = log_text.strip().splitlines()[-1] if log_text.strip() else ""
            return {
                "status": "failed",
                "error_type": "WorkerFailure",
                "message": message or f"runtime worker exited with code {completed.returncode}",
                "violations": [],
            }
        return json.loads(response_path.read_text(encoding="utf-8"))


def _isolation(spec: RuntimeInputSpec, response: dict[str, Any]) -> RuntimeIsolation:
    return RuntimeIsolation(
        timeout_seconds=spec.timeout_seconds,
        cpu_limit_seconds=spec.cpu_limit_seconds,
        memory_limit_mb=spec.memory_limit_mb,
        violations=TypeAdapter(list[RuntimeBoundaryViolation]).validate_python(
            response.get("violations", [])
        ),
    )


def _failure_receipt(
    out: Path,
    spec: RuntimeInputSpec,
    response: dict[str, Any],
    static_unchanged: bool,
) -> CommandReceipt:
    isolation = _isolation(spec, response)
    receipt = CommandReceipt(
        command="trace",
        status="failed",
        exit_code=1,
        artifacts={"runtime_receipt": str(out / "runtime-receipt.json")},
        gates=[
            GateResult(
                gate="G-runtime-isolation",
                status="passed" if static_unchanged else "failed",
                message=(
                    "Runtime failure was contained without changing static artifacts."
                    if static_unchanged
                    else "Runtime execution changed a static artifact."
                ),
            ),
            GateResult(
                gate="G-runtime-replay",
                status="skipped",
                message="Replay was not attempted because the runtime worker failed.",
            ),
            GateResult(
                gate="G-runtime-provenance",
                status="failed",
                message="No runtime-confirmed evidence was published.",
            ),
        ],
        diagnostics=[
            Diagnostic(
                code="RUNTIME_TRACE_FAILED",
                severity="blocking",
                message=f"{response.get('error_type', 'RuntimeError')}: {response.get('message', 'runtime worker failed')}",
            )
        ],
        details={
            "static_artifacts_unchanged": static_unchanged,
            "source_writes": False if static_unchanged else None,
            "isolation": isolation.model_dump(mode="json"),
        },
    )
    _write_json(out / "runtime-receipt.json", receipt)
    return receipt


def trace_runtime(
    artifact: Path,
    input_spec_path: Path,
    out: Path,
) -> CommandReceipt:
    if os.name != "posix":
        raise RuntimeTraceError("runtime tracing currently requires POSIX process resource limits")
    artifact = artifact.resolve()
    input_spec_path = input_spec_path.resolve()
    out = out.resolve()
    ir = ArchitectureIR.model_validate_json(artifact.read_text(encoding="utf-8"))
    snapshot_path = artifact.parent / "source-snapshot.json"
    if not snapshot_path.is_file():
        raise RuntimeTraceError("runtime trace requires source-snapshot.json beside architecture.json")
    snapshot = SourceSnapshot.model_validate_json(snapshot_path.read_text(encoding="utf-8"))
    if ir.source_snapshot_id != snapshot.snapshot_id or ir.entrypoint != snapshot.entrypoint:
        raise RuntimeTraceError("architecture and source snapshot bindings do not match")
    spec = RuntimeInputSpec.model_validate_json(input_spec_path.read_text(encoding="utf-8"))
    _verify_snapshot(snapshot)
    static_before = _protected_digests(artifact, snapshot)
    first = _run_worker(ir, snapshot, spec)
    static_unchanged = static_before == _protected_digests(artifact, snapshot)
    if first.get("status") != "completed":
        return _failure_receipt(out, spec, first, static_unchanged)

    second = _run_worker(ir, snapshot, spec)
    static_unchanged = static_before == _protected_digests(artifact, snapshot)
    if second.get("status") != "completed":
        return _failure_receipt(out, spec, second, static_unchanged)

    replay_payload = {
        "observations": first["observations"],
        "output_tensors": first["output_tensors"],
        "violations": first.get("violations", []),
    }
    replay_digest = _digest(replay_payload)
    second_replay_digest = _digest(
        {
            "observations": second["observations"],
            "output_tensors": second["output_tensors"],
            "violations": second.get("violations", []),
        }
    )
    replay_matches = replay_digest == second_replay_digest
    input_digest = _digest(spec)
    trace_suffix = hashlib.sha256(
        f"{ir.architecture_id}:{input_digest}:{replay_digest}".encode()
    ).hexdigest()[:16]
    trace_id = f"runtime-trace:{trace_suffix}"
    observations = [
        RuntimeObservation.model_validate(
            {
                **item,
                "observation_id": f"runtime-observation:{trace_suffix}.{index}",
                "sequence": index,
            }
        )
        for index, item in enumerate(first["observations"])
    ]
    isolation = _isolation(spec, first)
    environment = RuntimeEnvironment.model_validate(first["environment"])
    trace = RuntimeTrace(
        trace_id=trace_id,
        architecture_id=ir.architecture_id,
        source_snapshot_id=snapshot.snapshot_id,
        source_revision=snapshot.revision,
        entrypoint=snapshot.entrypoint,
        input_spec=spec,
        input_spec_digest=input_digest,
        replay_digest=replay_digest,
        observations=observations,
        output_tensors=TypeAdapter(list[RuntimeTensorObservation]).validate_python(
            first["output_tensors"]
        ),
        environment=environment,
        isolation=isolation,
    )
    observation_by_node: dict[str, list[RuntimeObservation]] = defaultdict(list)
    for observation in observations:
        for node_id in observation.matched_node_ids:
            observation_by_node[node_id].append(observation)
    evidence: list[EvidenceRecord] = []
    node_evidence: dict[str, list[str]] = {}
    for index, (node_id, items) in enumerate(sorted(observation_by_node.items())):
        evidence_id = f"evidence:runtime.{trace_suffix}.{index}"
        outputs = [tensor for item in items for tensor in item.output_tensors]
        summary = ", ".join(
            f"{tensor.dtype}{tensor.shape}" for tensor in outputs[:4]
        ) or "no tensor output"
        evidence.append(
            EvidenceRecord(
                evidence_id=evidence_id,
                kind=EvidenceKind.RUNTIME,
                path="runtime-trace.json",
                symbol=items[0].module_path,
                revision=snapshot.revision,
                claim=f"Observed {items[0].module_type} output {summary}.",
                confidence=Confidence.RUNTIME_CONFIRMED,
                execution_predicate=f"replay={trace_id}",
                runtime_trace_id=trace_id,
                runtime_observation_ids=[item.observation_id for item in items],
            )
        )
        node_evidence[node_id] = [evidence_id]
    capability = RuntimeCapabilityReport(
        runtime_available=True,
        torch_version=environment.torch_version,
        cuda_build=environment.cuda_build,
        cuda_available=environment.cuda_available,
        supported_devices=["cpu", "cuda"] if environment.cuda_available else ["cpu"],
        isolation=isolation,
        limitations=[
            "PyTorch module hooks observe module boundaries; functional operators remain static-only.",
            "Python socket and file APIs are guarded; this is not an OS container boundary.",
            "Entrypoints must accept JSON-compatible constructor and forward keyword arguments.",
        ],
    )
    artifacts = {
        "runtime_trace": str(out / "runtime-trace.json"),
        "runtime_evidence_ledger": str(out / "runtime-evidence-ledger.json"),
        "runtime_overlay": str(out / "runtime-evidence-overlay.json"),
        "runtime_capability_report": str(out / "runtime-capability-report.json"),
        "runtime_receipt": str(out / "runtime-receipt.json"),
    }
    _write_json(Path(artifacts["runtime_trace"]), trace)
    _write_json(Path(artifacts["runtime_evidence_ledger"]), evidence)
    _write_json(
        Path(artifacts["runtime_overlay"]),
        {
            "schema_version": "1.0",
            "architecture_id": ir.architecture_id,
            "trace_id": trace_id,
            "node_evidence": node_evidence,
        },
    )
    _write_json(Path(artifacts["runtime_capability_report"]), capability)
    gates = [
        GateResult(
            gate="G-runtime-isolation",
            status="passed" if static_unchanged else "failed",
            message=(
                "Worker ran in a bounded subprocess; static artifacts remained unchanged."
                if static_unchanged
                else "Runtime execution changed a static artifact."
            ),
        ),
        GateResult(
            gate="G-runtime-replay",
            status="passed" if replay_matches else "failed",
            message=(
                "Independent runs produced the same structural replay digest."
                if replay_matches
                else "Independent runs produced different structural replay digests."
            ),
        ),
        GateResult(
            gate="G-runtime-provenance",
            status="passed" if evidence else "failed",
            message=(
                "Runtime observations are linked to canonical nodes and a frozen input spec."
                if evidence
                else "Runtime observations could not be linked to canonical nodes."
            ),
        ),
    ]
    failed = any(gate.status == "failed" for gate in gates)
    receipt = CommandReceipt(
        command="trace",
        status="invalid" if failed else "ok",
        exit_code=2 if failed else 0,
        artifacts=artifacts,
        gates=gates,
        details={
            "trace_id": trace_id,
            "input_spec_digest": input_digest,
            "replay_digest": replay_digest,
            "replay_runs": 2,
            "observation_count": len(observations),
            "runtime_evidence_count": len(evidence),
            "selected_device": environment.selected_device,
            "blocked_boundary_attempts": len(isolation.violations),
            "static_artifacts_unchanged": static_unchanged,
            "source_writes": False,
        },
    )
    _write_json(Path(artifacts["runtime_receipt"]), receipt)
    return receipt
