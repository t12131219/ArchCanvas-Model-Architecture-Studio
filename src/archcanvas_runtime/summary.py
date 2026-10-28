"""Summary ATen observations on the formal runtime's mandatory frozen sandbox.

Only normalize_spec/finite_domain_check are reused from the old probe module;
its subprocess launcher is never invoked. The mounted original runtime_worker
owns observation semantics. This profile observes samples, not source writes.
"""
from __future__ import annotations

import copy
import json
import os
import platform
import tempfile
from pathlib import Path
from typing import Any

from archcanvas_preview.analyze import files_checked
from archcanvas_preview.semantic_bridge import analyze_summary
from archcanvas_summary_semantic.probe import normalize_spec, finite_domain_check
from archcanvas_summary_semantic.merge import merge
from archcanvas_summary_semantic.schema import digest, validate_ir
from .controller import RuntimeProfileError, _config, _environment, _limits, _execute, _seccomp


def normalize_summary_spec(value: Any) -> dict[str, Any]:
    try:
        # Reject NaN, mutable aliases and non-JSON values before any execution.
        spec = json.loads(json.dumps(value, allow_nan=False))
        normalize_spec(spec)
        for case in spec['cases']:
            if not 0 <= case.get('seed', 0) < 2**32:
                raise ValueError('case seed must be in [0, 2**32)')
            if len(case['inputs']) > 16:
                raise ValueError('at most 16 named inputs per case')
        finite_domain_check(spec)
        return spec
    except (ValueError, TypeError, OverflowError, RecursionError) as exc:
        raise RuntimeProfileError('Invalid Summary CPU profile: ' + str(exc)) from exc


def observe_summary(files: dict[str, str], entry: str, input_spec: dict[str, Any],
                    config: dict[str, Any] | None = None, source_sha256: str | None = None) -> dict[str, Any]:
    """Freeze explicit source/profile, probe isolation, observe, verify and merge.

    The result is a document with recorded observations. It is never an
    Architecture transaction or a claim of arbitrary-input execution coverage.
    """
    checked = files_checked(files)
    spec = normalize_summary_spec(input_spec)
    static = analyze_summary(checked, entry, spec.get('constructor', {}))
    if source_sha256 is not None and source_sha256 != static['sourceSha256']:
        raise RuntimeProfileError('Source bytes differ from the requested Summary generation.')
    semantic = static['ir']['semantic_ir']
    generation = {name: digest(text.encode('utf-8')) for name, text in sorted(checked.items())}
    source_file = semantic['entry']['file']
    receipt: dict[str, Any] = {
        'schema': 'semantic-runtime/1', 'profile': 'summary-aten-observed/1',
        'status': 'unavailable', 'model_executed': False, 'runtimeVerified': False,
        'input_spec': spec, 'source_files': checked,
        'binding': {'entry': static['entry'], 'source_root': '.', 'source_sha256': generation[source_file],
                    'source_generation': generation, 'source_manifest_sha256': static['sourceSha256'],
                    'static_ir_digest': semantic['ir_digest'], 'spec_digest': digest(spec), 'device': 'cpu'},
        'limitations': ['Declared samples and modes only; not arbitrary-input coverage or old/new equivalence.',
                        'Model and instrumentation share the isolated process; not adversarial attestation.',
                        'No checkpoint, optimizer or training progress is loaded or migrated.'],
    }
    result = {'receipt': receipt, 'document': None, 'source': static}
    try:
        settings = _config(config)
        if settings['cancelEvent'] is not None and settings['cancelEvent'].is_set():
            receipt.update(status='failed', reason='cancelled')
            return result
        if platform.system() != 'Linux' or not Path('/usr/bin/bwrap').is_file():
            raise RuntimeProfileError('Mandatory Linux Bubblewrap isolation unavailable; no subprocess fallback.')
        _seccomp()
        environment = _environment(settings)
    except (RuntimeProfileError, OSError) as exc:
        receipt['reason'] = str(exc)
        return result
    frozen_environment = digest(environment)
    # Original Summary worker uses 96 descriptors and an 8 MB output budget.
    # All remaining limits are the formal profile, including denied new tasks.
    limits = {**_limits(settings), 'openFiles': 96}
    receipt['manifest'] = {'environment': environment, 'limits': limits,
                           'sourceGeneration': generation, 'inputSpecDigest': digest(spec),
                           'observationMechanism': 'original Summary AST branches + nn.Module calls + TorchDispatchMode ATen operands/source stack'}
    receipt['binding'].update(interpreter=environment['interpreter'],
                              executable_sha256=environment['executableDigest'],
                              worker_digest=environment['summaryWorkerDigest'])
    with tempfile.TemporaryDirectory(prefix='archcanvas-summary-runtime-') as directory:
        temporary = Path(directory)
        source = temporary / 'source'; source.mkdir()
        for logical, text in checked.items():
            path = source / logical; path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(text.encode('utf-8'))
        sentinel = temporary / 'host-sentinel'; sentinel.write_text('must remain outside the sandbox')
        base = {'limits': limits, 'environment': environment,
                'hostNamespaces': {name: os.readlink('/proc/self/ns/' + name) for name in ('mnt', 'net', 'pid', 'user')},
                'hostSentinel': str(sentinel), 'sourceProbe': source_file}
        probe, error = _execute(environment, temporary, source, {**base, 'action': 'probe'}, settings)
        receipt['isolation'] = {'status': 'passed' if probe and probe.get('available') else 'failed',
                                'formalProbe': probe or {'reason': error}}
        if not probe or not probe.get('available'):
            receipt.update(status='failed' if error == 'cancelled' else 'unavailable', reason=error or 'Mandatory isolation probes failed.')
            return result
        description, error = _execute(environment, temporary, source, {**base, 'action': 'environment'}, settings)
        if not description or not description.get('valid'):
            receipt.update(status='failed' if error == 'cancelled' else 'unavailable', reason=error or (description or {}).get('reason', 'Dependency environment mismatch.'))
            return result
        environment.update(description['environment'])
        receipt['environmentDigest'] = digest(environment)
        request = {'entry': static['entry'], 'constructor': spec.get('constructor', {}), 'cases': spec['cases'],
                   'modes': spec['modes'], 'export': spec.get('export', False),
                   'limits': {'memory_mb': settings['memoryMb'], 'cpu_seconds': settings['cpuSeconds'],
                              'max_events': 6000, 'wall_seconds': settings['timeoutSeconds']}}
        observed, error = _execute(environment, temporary, source,
                                   {**base, 'environment': environment, 'action': 'summary-observe', 'summaryRequest': request}, settings)
        if not observed:
            receipt.update(status='failed', model_executed=None, reason=error)
            return result
        # Retain partial/failed observation details; controller-owned bindings
        # and isolation cannot be overwritten by worker JSON.
        for key in ('status', 'model_executed', 'framework', 'framework_origin', 'device', 'runs', 'instrumentation', 'reason', 'traceback'):
            if key in observed: receipt[key] = observed[key]
        receipt['source_unchanged'] = generation == {
            name: digest((source / name).read_bytes()) for name in generation if (source / name).is_file()}
        if not receipt['source_unchanged'] or digest(_environment(settings)) != frozen_environment:
            receipt.update(status='failed', reason='Frozen source or runtime environment bytes changed during observation.')
            return result
    expected = {(case['id'], mode) for case in spec['cases'] for mode in spec['modes']}
    runs = receipt.get('runs', [])
    actual = [(run.get('case'), run.get('mode')) for run in runs]
    complete = (receipt['status'] == 'passed' and receipt.get('model_executed') is True
                and set(actual) == expected and len(actual) == len(expected)
                and all(run.get('status') == 'passed' and not run.get('truncated') and run.get('replay', {}).get('matched') is True for run in runs))
    receipt['finite_domain'] = finite_domain_check(spec)
    receipt['runtimeVerified'] = bool(complete)
    receipt['trace_digest'] = digest(receipt)
    if not complete:
        receipt.update(status='failed', reason=receipt.get('reason', 'Observation/replay did not cover every declared case and mode.'))
        receipt['trace_digest'] = digest({k: v for k, v in receipt.items() if k != 'trace_digest'})
        return result
    document = merge(copy.deepcopy(semantic), receipt)
    validation = validate_ir(document)
    raw = json.dumps(document, ensure_ascii=False, allow_nan=False).encode('utf-8')
    if not validation['ok'] or len(document['nodes']) > 4000 or len(document['edges']) > 5000 or len(raw) > 64_000_000:
        receipt.update(status='failed', runtimeVerified=False, reason='Observed document failed native validation or its 4000-node/5000-edge/64 MB budget.')
        receipt['trace_digest'] = digest({k: v for k, v in receipt.items() if k != 'trace_digest'})
        return result
    result['document'] = document
    return result
