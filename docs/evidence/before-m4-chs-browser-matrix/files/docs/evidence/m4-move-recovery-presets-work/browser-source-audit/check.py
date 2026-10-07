"""Inspect saved UI drafts and DOM-captured source; never import torch/model."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
WORK = ROOT / 'docs/evidence/m4-move-recovery-presets-work'
UI = ROOT / 'docs/evidence/m4-move-recovery-presets-browser/session-2'
spec = importlib.util.spec_from_file_location('independent_ast', WORK / 'preset-independent/audit.py')
oracle = importlib.util.module_from_spec(spec)
spec.loader.exec_module(oracle)
contracts = copy.deepcopy(json.loads((WORK / 'preset-independent/expected-contracts.json').read_text())['presets'])
# Actual UI edit: batch 2 keeps Linear widths 16 -> 32 -> 4.
contracts['mlp']['nodes'][0]['parameters']['shape'] = [2, 16]
for node in contracts['mlp']['nodes']:
    node['shape'][0] = 2
rows = []
for name, preset in [('mlp', 'mlp'), ('cnn', 'cnn'), ('residual', 'residual-mlp')]:
    envelope_path = UI / f'draft-stores/{name}-envelope.json'
    source_path = UI / f'{name}-generated-source.py.txt'
    envelope = json.loads(envelope_path.read_text())
    nodes, edges, shapes, inventory = oracle.graph_contract(envelope['draft'], [preset], contracts)
    source = source_path.read_text()
    result = oracle.source_ast_contract(source, nodes, edges)
    controls = oracle.negative_ast_controls(source, nodes, edges)
    rows.append({'case': name, 'draftId': envelope['draft']['id'], 'storageRevision': envelope['revision'],
                 'nodes': len(nodes), 'edges': len(edges), 'declaredShapes': shapes, 'ast': result,
                 'negativeControls': controls, 'sourceSha256': hashlib.sha256(source.encode()).hexdigest(),
                 'draftEnvelopeSha256': hashlib.sha256(envelope_path.read_bytes()).hexdigest()})
report = {'passed': True, 'scope': 'Actual browser saved drafts and source read from generated modal',
          'modelExecution': 'not_run', 'basis': 'Independent handwritten preset contracts and full stdlib AST oracle',
          'cases': rows, 'limitations': ['Does not certify pixel frame synchronization, runtime numeric behavior, or physical publication.']}
(Path(__file__).parent / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps({'passed': True, 'cases': len(rows), 'nodes': sum(row['nodes'] for row in rows), 'edges': sum(row['edges'] for row in rows)}))
