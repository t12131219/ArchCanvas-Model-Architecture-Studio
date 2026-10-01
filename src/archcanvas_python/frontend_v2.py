from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import libcst as cst

from archcanvas_core.architecture_v2 import (
    SEMANTIC_GRAPH_DIGEST_DOMAIN,
    ExactArchitectureIRV2,
    PythonSemanticGraph,
    semantic_graph_payload,
)
from archcanvas_core.builtin_registry import BuiltinModuleRegistry
from archcanvas_core.digest_protocol import domain_digest
from archcanvas_core.models import Diagnostic
from archcanvas_core.source_v2 import (
    ANALYSIS_INPUT_DIGEST_DOMAIN,
    AnalysisBudget,
    AnalysisInputManifest,
    DiscoveryBudget,
    ProjectManifest,
    ResolverManifest,
    SourceCorpus,
    analysis_input_digest_payload,
)
from archcanvas_engine.source_blob_store import SourceBlobStore

from .analyzer import AnalysisBundle
from .corpus import capture_source_corpus
from .cst_frontend import ParsedRepository, parse_frozen_corpus
from .pattern_packs_v2 import apply_builtin_pattern_packs, builtin_pattern_pack_digests
from .project_manifest import discover_project_manifest
from .pyright_client import (
    PyrightClient,
    PyrightUnavailableError,
    ResolverBatchResult,
    ResolverFact,
    ResolverQuery,
    StdioJsonRpcTransport,
    lsp_utf16_column,
)
from .registry_binding import build_exact_ir_v2
from .semantic_graph import build_semantic_graph
from .v1_compat import project_v1_compatibility

FRONTEND_V2_VERSION = "0.2.1"


@dataclass(frozen=True)
class FrontendV2Bundle:
    manifest: ProjectManifest
    corpus: SourceCorpus
    snapshot_root: Path
    repository: ParsedRepository
    analysis_input: AnalysisInputManifest
    semantic_graph: PythonSemanticGraph
    exact_ir: ExactArchitectureIRV2
    compatibility: AnalysisBundle


@dataclass(frozen=True)
class _ResolverRun:
    manifest: ResolverManifest
    budget_exceeded: bool = False
    facts: tuple[ResolverFact, ...] = ()


def _resolver_queries(repository: ParsedRepository) -> list[ResolverQuery]:
    queries: dict[tuple[str, int, int], ResolverQuery] = {}
    for logical_path, unit in sorted(repository.units.items()):
        for node, position in unit.positions.items():
            if not isinstance(node, cst.Call):
                continue
            function_position = unit.positions.get(node.func, position)
            key = (
                logical_path,
                function_position.start.line - 1,
                lsp_utf16_column(
                    unit.module.code,
                    function_position.start.line - 1,
                    function_position.start.column,
                ),
            )
            queries[key] = ResolverQuery(
                method="typeServer/getDeclaredType",
                logical_path=logical_path,
                line=key[1],
                column=key[2],
            )
    return [queries[key] for key in sorted(queries)]


def _resolver_payload_digest(domain: str, value: Any) -> str:
    return domain_digest(domain, value)


def _run_resolver(
    repository: ParsedRepository,
    manifest: ProjectManifest,
    *,
    config_digest: str,
    budget: AnalysisBudget,
    client: PyrightClient | None,
    executable: Path | None,
    executable_digest: str | None,
) -> _ResolverRun:
    owned_client: PyrightClient | None = None
    if client is not None and executable is not None:
        raise ValueError("provide either a Pyright client or executable, not both")
    if executable is not None:
        resolved_executable = executable.resolve()
        try:
            payload = resolved_executable.read_bytes()
            executable_digest = hashlib.sha256(payload).hexdigest()
            owned_client = PyrightClient(
                StdioJsonRpcTransport(resolved_executable, repository.root),
                repository.root,
            )
            client = owned_client
        except (OSError, PyrightUnavailableError):
            client = None

    if client is None:
        resolver = ResolverManifest(
            resolver_id="resolver:libcst-only",
            resolver_version="1.0.0",
            resolver_digest=hashlib.sha256(b"libcst-only-v1").hexdigest(),
            kind="libcst-only",
            capability_status="degraded",
            diagnostic_code="PYRIGHT_UNAVAILABLE",
            config_digest=config_digest,
            python_target=manifest.python_target,
            platform_target=manifest.platform_target,
        )
        return _ResolverRun(manifest=resolver)

    all_queries = _resolver_queries(repository)
    budget_exceeded = len(all_queries) > budget.max_resolver_queries
    queries = all_queries[: budget.max_resolver_queries]
    try:
        if budget_exceeded and not queries:
            result = ResolverBatchResult(
                status="budget-exceeded",
                snapshot=None,
                results=(),
                diagnostic_code="ANALYSIS_BUDGET_EXCEEDED",
            )
        else:
            result = client.query_batch(queries)
    finally:
        if owned_client is not None:
            owned_client.close()

    query_payload = [
        {
            "method": item.method,
            "logical_path": item.logical_path,
            "line": item.line,
            "column": item.column,
            "extra": item.extra,
        }
        for item in queries
    ]
    query_digest = _resolver_payload_digest(
        "archcanvas:pyright-query-batch:v1",
        query_payload,
    )
    result_digest = _resolver_payload_digest(
        "archcanvas:pyright-query-results:v1",
        list(result.results),
    )
    diagnostic_code = (
        "ANALYSIS_BUDGET_EXCEEDED" if budget_exceeded else result.diagnostic_code
    )
    active = result.status == "ok" and not budget_exceeded
    executable_digest = executable_digest or hashlib.sha256(
        b"injected-pyright-client"
    ).hexdigest()
    resolver_values = {
        "kind": "pyright-typeserver",
        "resolver_version": "1.0.0",
        "executable_digest": executable_digest,
        "config_digest": config_digest,
        "python_target": manifest.python_target,
        "platform_target": manifest.platform_target,
        "snapshot_id": result.snapshot,
        "query_count": len(queries),
        "query_digest": query_digest,
        "result_digest": result_digest,
        "capability_status": "active" if active else "degraded",
        "diagnostic_code": None if active else diagnostic_code or "PYRIGHT_UNAVAILABLE",
    }
    resolver_digest = _resolver_payload_digest(
        "archcanvas:resolver-manifest:v1",
        resolver_values,
    )
    return _ResolverRun(
        manifest=ResolverManifest(
            resolver_id="resolver:pyright-typeserver",
            resolver_digest=resolver_digest,
            **resolver_values,
        ),
        budget_exceeded=budget_exceeded,
        facts=(
            tuple(
                ResolverFact(query=query, snapshot=result.snapshot, result=value)
                for query, value in zip(queries, result.results, strict=True)
            )
            if active and result.snapshot is not None
            else ()
        ),
    )


def _analysis_input(
    corpus: SourceCorpus,
    registry: BuiltinModuleRegistry,
    *,
    manifest: ProjectManifest,
    entrypoint: str,
    task: str,
    execution_mode: str,
    config_digest: str,
    resolver: ResolverManifest,
    analysis_budget: AnalysisBudget,
    pattern_packs_enabled: bool,
) -> AnalysisInputManifest:
    analyzer_digest = hashlib.sha256(FRONTEND_V2_VERSION.encode()).hexdigest()
    values = {
        "source_corpus_digest": corpus.source_corpus_digest,
        "registry_digest": registry.bundle.bundle_digest,
        "analyzer_build_digest": analyzer_digest,
        "pattern_pack_digests": (
            builtin_pattern_pack_digests() if pattern_packs_enabled else []
        ),
        "resolver": resolver,
        "task": task,
        "execution_mode": execution_mode,
        "entrypoint": entrypoint,
        "config_digest": config_digest,
        "analysis_budget": analysis_budget,
    }
    digest = domain_digest(
        ANALYSIS_INPUT_DIGEST_DOMAIN,
        analysis_input_digest_payload(**values),
    )
    return AnalysisInputManifest(analysis_input_digest=digest, **values)


def _record_resolver_degradation(
    graph: PythonSemanticGraph,
    analysis_input: AnalysisInputManifest,
) -> PythonSemanticGraph:
    resolver = analysis_input.resolver
    if resolver.capability_status != "degraded":
        return graph
    diagnostic_code = resolver.diagnostic_code or "RESOLVER_DEGRADED"
    if any(item.code == diagnostic_code for item in graph.diagnostics):
        return graph
    message = {
        "PYRIGHT_UNAVAILABLE": (
            "Pyright Type Server is unavailable; analysis used deterministic "
            "LibCST/local-symbol resolution only."
        ),
        "PYRIGHT_SNAPSHOT_CHANGED": (
            "Pyright changed snapshots during the resolver batch; the entire batch was "
            "discarded and local LibCST analysis continued."
        ),
        "PYRIGHT_TIMEOUT": (
            "Pyright Type Server exceeded its request timeout; analysis used "
            "deterministic LibCST/local-symbol resolution only."
        ),
        "ANALYSIS_BUDGET_EXCEEDED": (
            "Pyright resolver queries exceeded the configured analysis budget; local "
            "LibCST analysis continued."
        ),
    }.get(diagnostic_code, "Resolver capability degraded; local LibCST analysis continued.")
    diagnostic = Diagnostic(
        code=diagnostic_code,
        severity="warning",
        message=message,
        target_ids=[graph.graph_id],
    )
    values = {
        "schema_version": graph.schema_version,
        "graph_id": graph.graph_id,
        "source_corpus_digest": graph.source_corpus_digest,
        "entrypoint": graph.entrypoint,
        "definitions": graph.definitions,
        "instances": graph.instances,
        "calls": graph.calls,
        "values": graph.values,
        "control_regions": graph.control_regions,
        "parameter_groups": graph.parameter_groups,
        "repeats": graph.repeats,
        "pattern_bindings": graph.pattern_bindings,
        "evidence": graph.evidence,
        "diagnostics": [*graph.diagnostics, diagnostic],
    }
    prototype = PythonSemanticGraph.model_construct(
        semantic_graph_digest="0" * 64,
        **values,
    )
    digest = domain_digest(
        SEMANTIC_GRAPH_DIGEST_DOMAIN,
        semantic_graph_payload(prototype),
    )
    return PythonSemanticGraph(semantic_graph_digest=digest, **values)


def analyze_project_v2(
    project_root: Path,
    entrypoint: str,
    task: str,
    execution_mode: str,
    workspace: Path,
    *,
    config_bytes: bytes = b"{}",
    registry: BuiltinModuleRegistry | None = None,
    discovery_budget: DiscoveryBudget | None = None,
    analysis_budget: AnalysisBudget | None = None,
    pyright_client: PyrightClient | None = None,
    pyright_executable: Path | None = None,
    pyright_executable_digest: str | None = None,
    pattern_packs_enabled: bool = True,
) -> FrontendV2Bundle:
    root = project_root.resolve()
    workspace = workspace.resolve()
    workspace.mkdir(parents=True, exist_ok=True)
    registry = registry or BuiltinModuleRegistry()
    analysis_budget = analysis_budget or AnalysisBudget()
    manifest = discover_project_manifest(
        root,
        "project:frontend-v2",
        budget=discovery_budget,
    )
    store = SourceBlobStore(workspace / "source-blobs")
    corpus = capture_source_corpus(root, manifest, store)
    snapshot_root = workspace / "snapshots" / corpus.source_corpus_digest
    if not snapshot_root.exists():
        store.materialize(corpus, snapshot_root)
    repository = parse_frozen_corpus(corpus, snapshot_root)
    config_digest = hashlib.sha256(config_bytes).hexdigest()
    resolver_run = _run_resolver(
        repository,
        manifest,
        config_digest=config_digest,
        budget=analysis_budget,
        client=pyright_client,
        executable=pyright_executable,
        executable_digest=pyright_executable_digest,
    )
    analysis_input = _analysis_input(
        corpus,
        registry,
        manifest=manifest,
        entrypoint=entrypoint,
        task=task,
        execution_mode=execution_mode,
        config_digest=config_digest,
        resolver=resolver_run.manifest,
        analysis_budget=analysis_budget,
        pattern_packs_enabled=pattern_packs_enabled,
    )
    semantic_graph = _record_resolver_degradation(
        build_semantic_graph(
            corpus,
            repository,
            registry,
            entrypoint,
            budget=analysis_budget,
            resolver_budget_exceeded=resolver_run.budget_exceeded,
            resolver_facts=resolver_run.facts,
        ),
        analysis_input,
    )
    if pattern_packs_enabled:
        semantic_graph = apply_builtin_pattern_packs(semantic_graph)
    exact_ir = build_exact_ir_v2(semantic_graph, analysis_input, registry)
    compatibility = project_v1_compatibility(
        exact_ir,
        corpus,
        analysis_input,
        registry,
        snapshot_root,
        task=task,
        execution_mode=execution_mode,
    )
    return FrontendV2Bundle(
        manifest=manifest,
        corpus=corpus,
        snapshot_root=snapshot_root,
        repository=repository,
        analysis_input=analysis_input,
        semantic_graph=semantic_graph,
        exact_ir=exact_ir,
        compatibility=compatibility,
    )
