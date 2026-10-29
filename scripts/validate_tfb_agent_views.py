#!/usr/bin/env python3
"""Read-only holdout exercise; never import TFB, torch, or a model class."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from archcanvas_adapters import AdapterRegistry, scaffold_adapter_files
from archcanvas_adapters.handoff import build_handoff, starter_rules
from archcanvas_preview import analyze
from archcanvas_summary_semantic.schema import validate_ir


def sha(data):
    return hashlib.sha256(data).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def run(root, output):
    root, output = root.resolve(), output.resolve()
    if output.is_relative_to(root):
        raise ValueError('Evidence must be written outside the read-only TFB root.')
    before_hashes = {str(p.relative_to(root)): sha(p.read_bytes()) for p in root.rglob('*.py') if '.git' not in p.parts}
    output.mkdir(parents=True, exist_ok=True)
    if (root / 'LICENSE').is_file():
        (output / 'TFB-LICENSE.txt').write_bytes((root / 'LICENSE').read_bytes())
    rows = []
    models = [('mixlinear', 'models.MixLinear:Model', {}),
              ('timekan', 'layers.ChebyKANLayer:ChebyKANLinear', {'input_dim': 8, 'output_dim': 4, 'degree': 3}),
              ('phaseformer', 'models.PhaseFormer:Model', {})]
    rule = starter_rules()['attribute-call']
    # Authored from the holdout's decorated helper. This exposes the actual
    # return expression without executing the decorator or claiming its shape.
    return_rule = {
        'schema': 'archcanvas-source-rule/1', 'name': 'Source return expression',
        'match': {'type': 'Return', 'fields': {'value': {'type': 'Call'}}},
        'nodes': [{'key': 'return', 'at': [], 'parent': None, 'kind': 'SourceStatement'},
                  {'key': 'value', 'at': ['value'], 'parent': 'return', 'kind': 'SourceCall'}],
        'relations': [{'source': 'value', 'target': 'return', 'proof': 'expression-input'}],
    }
    write(output / 'attribute-call-rule.json', rule)
    write(output / 'return-expression-rule.json', return_rule)
    for project, relative_entry, config in models:
        prefix = 'ts_benchmark/baselines/' + project
        paths = sorted((root / prefix).rglob('*.py'))
        files = {str(p.relative_to(root)): p.read_text(encoding='utf-8-sig') for p in paths}
        entry = prefix.replace('/', '.') + '.' + relative_entry
        destination = output / project
        destination.mkdir(exist_ok=True)
        handoff = build_handoff(files, entry, config)
        write(destination / 'handoff.json', handoff)
        before = analyze(files, entry, config, semantic_mode='summary')
        definition = scaffold_adapter_files(files, entry, config=config, rules=[rule])
        registry = AdapterRegistry(destination / 'registry')
        registry.register_files(definition, files)
        if project == 'phaseformer':
            helper = scaffold_adapter_files(files, entry, method='_to_phase_series', config=config, rules=[rule, return_rule])
            registry.register_files(helper, files)
        after = registry.preview(before, files)
        native = after['ir']['semantic_ir']
        assert validate_ir(native)['ok'], validate_ir(native)
        original_nodes = {n['id']: n for n in before['ir']['semantic_ir']['nodes']}
        original_edges = {e['id']: e for e in before['ir']['semantic_ir']['edges']}
        assert original_nodes == {n['id']: n for n in native['nodes'] if n['id'] in original_nodes}
        assert original_edges == {e['id']: e for e in native['edges'] if e['id'] in original_edges}
        added = [n for n in native['nodes'] if n['id'] not in original_nodes]
        assert added and all(n['inspection_only'] and n['generationContract'] is None for n in added)
        write(destination / 'before.json', before)
        write(destination / 'preview.json', after)
        row = {'model': project, 'entry': entry, 'sourceFiles': handoff['sourceFiles'],
               'constructor': config, 'beforeNodes': len(original_nodes), 'afterNodes': len(native['nodes']),
               'computationalUnknowns': len(handoff['requests']), 'inspectionCardsAdded': len(added),
               'sourceRuleApplications': len(after.get('sourceRuleApplications', [])),
               'truncated': any(a['truncated'] for a in after.get('sourceRuleApplications', [])),
               'originalComputationUnchanged': True, 'modelExecuted': False,
               'probeRun': False, 'reason': 'Read-only source inspection; external dependencies remain opaque.',
               'ruleDiagnostics': after.get('ruleDiagnostics', [])}
        rows.append(row)
        print(json.dumps({key: value for key, value in row.items() if key not in {'sourceFiles', 'ruleDiagnostics'}}, ensure_ascii=False), flush=True)
    after_hashes = {str(p.relative_to(root)): sha(p.read_bytes()) for p in root.rglob('*.py') if '.git' not in p.parts}
    assert before_hashes == after_hashes, 'TFB source generation changed during the read-only exercise.'
    result = {'schema': 'archcanvas-tfb-agent-view-validation/1', 'sourceRoot': str(root),
              'pythonFilesChecked': len(before_hashes), 'allSourceHashesUnchanged': True,
              'probeRun': False, 'modelExecuted': False, 'models': rows,
              'sourceManifest': before_hashes,
              'scope': 'Three independently selected TFB components, same generic rule, native Summary import; not full benchmark or runtime coverage.'}
    write(output / 'report.json', result)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    run(args.source_root, args.output)
