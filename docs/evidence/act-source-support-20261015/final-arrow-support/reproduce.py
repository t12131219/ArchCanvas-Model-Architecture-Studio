"""Read act as text; regenerate source-only adapters and both static parsers."""
from pathlib import Path
import hashlib
import json
import time

from archcanvas_adapters import AdapterRegistry, scaffold_adapter_files, enrich_preview, validate_adapter_files
from archcanvas_preview.analyze import Analyzer as PreviewAnalyzer, analyze as preview_analyze
from archcanvas_python import analyze_project
from archcanvas_python.discovery import discover_files

PROJECT = Path(__file__).resolve().parents[4]
OUTPUT = Path(__file__).resolve().parent
SOURCE = PROJECT.parent / 'Constraint relationship of architecture diagram' / 'act'


def write(name, value):
    (OUTPUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n')


def inventory():
    return {str(path.relative_to(SOURCE)): {'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
             'bytes': path.stat().st_size, 'mtimeNs': path.stat().st_mtime_ns}
            for path in sorted(SOURCE.rglob('*')) if path.is_file()}


before = inventory()
files = {str(path.relative_to(SOURCE)): path.read_text() for path in sorted(SOURCE.rglob('*.py'))}
discovery = discover_files(files)
write('discovery.json', discovery)
registry = AdapterRegistry(OUTPUT / 'registry')
entries = ['policy:ACTPolicy', 'policy:CNNMLPPolicy', 'detr.models.detr_vae:DETRVAE', 'detr.models.detr_vae:reparametrize']
records = []
for entry in entries:
    start = time.perf_counter()
    adapter = scaffold_adapter_files(files, entry)
    registered = registry.register_files(adapter, files)
    reopened = registry.resolve_files(files, entry)
    assert adapter == reopened == validate_adapter_files(reopened, files)
    record = {'entry': entry, 'id': adapter['id'], 'generatorRevision': adapter['generatorRevision'],
              'children': len(adapter['children']), 'dependencies': len(adapter['dependencies']),
              'validatedAndReopened': True, 'registryPath': str(Path(registered['path']).relative_to(PROJECT))}
    if entry != entries[-1]:
        original = PreviewAnalyzer(files).run(entry)
        result = enrich_preview(original, files, [adapter])
        assert original['ir']['edges'] == result['ir']['edges'][:len(original['ir']['edges'])]
        write(entry.split(':')[1] + '-preview.json', result)
        record['preview'] = {'nodes': len(result['ir']['nodes']), 'edges': len(result['ir']['edges']),
                             'originalEdges': len(original['ir']['edges']), 'originalEdgesPreserved': True,
                             'syntaxEdges': sum(bool(edge.get('syntaxOnly')) for edge in result['ir']['edges']),
                             'coverage': result.get('coverage')}
        if entry == entries[0]:
            facts = {node['id']: node for node in result['ir']['nodes']}
            branch = next(node for node in facts.values() if node.get('sourceKind') == 'SourceBranch' and node['label'] == 'if actions is not None')
            immediate = {node['id'] for node in facts.values() if node.get('parent') == branch['id']}
            # Include frontier-projected source descendants when the producer
            # is inside a currently folded direct child definition.
            def frontier(identity):
                while identity not in immediate and identity in facts and facts[identity].get('parent'):
                    identity = facts[identity]['parent']
                return identity if identity in immediate else None
            detail = []
            for edge in result['ir']['edges']:
                left, right = frontier(edge['source']), frontier(edge['target'])
                if left and right and left != right:
                    detail.append({'source': facts[left]['label'], 'target': facts[right]['label'],
                                   'sourceId': edge['source'], 'targetId': edge['target'], 'syntaxOnly': edge.get('syntaxOnly', False)})
            write('ACTPolicy-training-branch-relations.json', {'branchId': branch['id'], 'children': len(immediate),
                  'immediateRelations': sum(edge['source'] in immediate and edge['target'] in immediate for edge in result['ir']['edges']),
                  'projectedRelations': detail})
    record['seconds'] = round(time.perf_counter() - start, 4)
    records.append(record)
    print('adapter', entry, record['children'], record['dependencies'], record.get('preview', {}), flush=True)

matrix = []
for entry in discovery['candidates']:
    row = {'entry': entry}
    for backend in ('formal', 'preview'):
        start = time.perf_counter()
        result = analyze_project(SOURCE, entry) if backend == 'formal' else preview_analyze(files, entry)
        graph = result if backend == 'formal' else result['ir']
        row[backend] = {'status': 'ok', 'nodes': len(graph['nodes']), 'edges': len(graph['edges']),
                        'sourceRelations': len(graph.get('sourceRelations', [])),
                        'seconds': round(time.perf_counter() - start, 4)}
    matrix.append(row)
    print('matrix', row, flush=True)

after = inventory()
assert before == after
old_registry = AdapterRegistry(PROJECT / 'docs/evidence/act-adapters-20261015/registry')
runtime = ['src/archcanvas_adapters/registry.py', 'src/archcanvas_python/source_structure.py',
           'src/archcanvas_python/source_dependencies.py', 'src/archcanvas_python/discovery.py',
           'src/archcanvas_python/frontend.py', 'src/archcanvas_preview/analyze.py', 'schemas/source-adapter-v1.schema.json']
write('receipt.json', {'schema': 'archcanvas-final-source-arrow-support/1', 'root': str(SOURCE),
      'modelExecuted': False, 'sourceEdited': False, 'sourceFileCount': len(before), 'pythonFileCount': len(files),
      'filesBefore': before, 'filesAfter': after, 'sourceUnchanged': before == after,
      'supersedes': ['../../act-adapters-20261015/receipt.json', '../discovery-final-verification.json'],
      'generatorRevision': 'source-inspection/2', 'adapters': records, 'registry': registry.list_files(files),
      'previousRegistryAfterUpgrade': old_registry.list_files(files), 'matrix': matrix,
      'all30StaticOpensPassed': len(matrix) == 15 and all(row[backend]['status'] == 'ok' for row in matrix for backend in ('formal', 'preview')),
      'runtimeFiles': {path: hashlib.sha256((PROJECT / path).read_bytes()).hexdigest() for path in runtime}})
