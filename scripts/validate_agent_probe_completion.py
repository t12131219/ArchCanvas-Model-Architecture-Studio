#!/usr/bin/env python3
"""Explicit isolated CPU runs followed by source-only view completion.

TFB is read only. A copied logical model.py retains the original source bytes;
no benchmark package initialization, weights or dependencies are downloaded.
"""
from __future__ import annotations
import argparse
import copy
import hashlib
import json
from pathlib import Path
import sys

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from archcanvas_adapters import AdapterRegistry, scaffold_adapter_files
from archcanvas_adapters.handoff import build_handoff, starter_rules
from archcanvas_preview import analyze
from archcanvas_runtime.summary import observe_summary
from archcanvas_summary_semantic.schema import validate_ir


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2) + '\n')


def run(source_root, output):
    source_root, output = source_root.resolve(), output.resolve()
    if output.is_relative_to(source_root) or output.exists():
        raise ValueError('Choose a new evidence directory outside the read-only model project.')
    output.mkdir(parents=True)
    hashes = lambda: {str(p.relative_to(source_root)): hashlib.sha256(p.read_bytes()).hexdigest()
                      for p in sorted(source_root.rglob('*.py')) if '.git' not in p.parts}
    original = hashes()
    relative = 'ts_benchmark/baselines/timekan/layers/ChebyKANLayer.py'
    raw = (source_root / relative).read_bytes()
    files = {'model.py': raw.decode('utf-8')}
    entry = 'model:ChebyKANLinear'
    ctor = {'input_dim': 8, 'output_dim': 4, 'degree': 3}
    spec = {'schema': 'semantic-inputs/1', 'constructor': ctor, 'modes': ['eval'],
            'cases': [{'id': 'small-cpu', 'seed': 7, 'inputs': {
                'x': {'shape': [2, 8], 'dtype': 'float32', 'fill': 'ones'}}}]}
    config = {'interpreter': str(ROOT / '.venv-runtime/bin/python'),
              'dependencyLock': str(ROOT / 'requirements-runtime.lock'), 'timeoutSeconds': 30}
    rows = []
    for name in ('passed', 'model-error', 'environment-unavailable'):
        folder = output / name; folder.mkdir()
        selected = copy.deepcopy(spec)
        if name == 'model-error': selected['cases'][0]['inputs']['x']['shape'] = [2, 7]
        runtime_config = config if name != 'environment-unavailable' else {
            **config, 'interpreter': str(output / 'missing-runtime/bin/python')}
        result = observe_summary(files, entry, selected, runtime_config)
        receipt = result['receipt']
        expected = {'passed': 'passed', 'model-error': 'failed', 'environment-unavailable': 'unavailable'}[name]
        assert receipt['status'] == expected, receipt.get('reason')
        assert receipt['model_executed'] is (name != 'environment-unavailable'), receipt
        handoff = build_handoff(files, entry, ctor, probe_result=result)
        assert handoff['requests'], 'The probe must not erase unresolved static boundaries.'
        before = analyze(files, entry, ctor, semantic_mode='summary')
        registry = AdapterRegistry(folder / 'registry')
        definition = scaffold_adapter_files(files, entry, config=ctor, rules=[starter_rules()['attribute-call']])
        registry.register_files(definition, files)
        after = registry.preview(before, files)
        native = after['ir']['semantic_ir']
        assert validate_ir(native)['ok']
        for field in ('nodes', 'edges'):
            originals = {n['id']: n for n in before['ir']['semantic_ir'][field]}
            assert originals == {n['id']: n for n in native[field] if n['id'] in originals}
        cards = [n for n in native['nodes'] if n.get('inspection_only')]
        assert cards and all(n['generationContract'] is None for n in cards)
        if name != 'passed':
            assert result['document'] is None
            assert not receipt['runtimeVerified']
        write(folder / 'probe.json', result)
        write(folder / 'handoff.json', handoff)
        write(folder / 'preview.json', after)
        write(folder / 'input-spec.json', selected)
        row = {'scenario': name, 'status': receipt['status'], 'modelExecuted': receipt['model_executed'],
               'runtimeVerified': receipt['runtimeVerified'], 'reason': receipt.get('reason'),
               'runs': len(receipt.get('runs', [])), 'inspectionCardsAdded': len(cards),
               'computationalUnknownsRetained': len(handoff['requests']),
               'originalComputationUnchanged': True, 'handoffContinued': True}
        rows.append(row); print(json.dumps(row), flush=True)
    assert original == hashes(), 'Source changed during read-only validation.'
    report = {'schema': 'archcanvas-agent-probe-completion-validation/1', 'results': rows,
              'pythonFilesChecked': len(original), 'allSourceHashesUnchanged': True,
              'source': {'root': str(source_root), 'path': relative,
                         'sha256': hashlib.sha256(raw).hexdigest(), 'logicalPath': 'model.py'},
              'sourceHashes': original,
              'scope': 'One unchanged TFB component, declared CPU sample, actual model exception and unavailable runtime; no arbitrary-input equivalence.'}
    write(output / 'report.json', report)
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    run(args.source_root, args.output)
