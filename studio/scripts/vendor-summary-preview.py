#!/usr/bin/env python3
"""Copy Summary Merge assets into a self-contained Studio distribution.

This development-only tool never participates in Studio startup. Runtime paths
are relative to public/preview; the original prototype can be absent entirely.
Existing integration files are preserved when refreshing the upstream assets.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import shutil
from pathlib import Path

EXCLUDED = {'.git', '.rollback', '__pycache__', '.pytest_cache', 'node_modules'}
TREES = ('yworks_edge_router_lab', 'data', 'snapshots', 'verification')
CUSTOMIZED = {'yworks_edge_router_lab/app.js', 'yworks_edge_router_lab/index.html',
              'yworks_edge_router_lab/semantic-constraints.js',
              'yworks_edge_router_lab/graph-engine.js', 'yworks_edge_router_lab/recursive-graph.js',
              'yworks_edge_router_lab/router.js', 'yworks_edge_router_lab/routing-worker.js'}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_index(source: Path, catalog: dict) -> dict:
    candidates = list((source / 'snapshots').rglob('*.py'))
    result = {}
    for case in catalog['cases']:
        graphs = [json.loads((source / v['json']).read_text())
                  for v in case['views'] if v.get('json')]
        graph = next((g for g in graphs if g.get('sourceDocs')), graphs[0] if graphs else {})
        evidence_path = graph.get('sourceDocs', {}).get('source_evidence.json')
        if not evidence_path and graph.get('irSource'):
            relative = Path(graph['irSource']).parent / 'source_evidence.json'
            if (source / relative).is_file():
                evidence_path = relative.as_posix()
        evidence = json.loads((source / evidence_path).read_text()) if evidence_path else {}
        paths = [p for p in evidence.get('files', {}) if p.endswith('.py')]
        origin = evidence.get('origin')
        if not paths and origin:
            marker = '/prototype/'
            paths = [origin.split(marker, 1)[-1]]
        if case['id'] == 'pytorch-original':
            paths = ['transformer.py']
        files = []
        for path in paths:
            adjacent = (source / evidence_path).parent / 'sources' / path if evidence_path else None
            choices = [p for p in candidates if p.as_posix().endswith('/' + path)]
            if not choices and origin and evidence.get('sha256'):
                choices = [p for p in candidates if p.name == Path(path).name
                           and digest(p) == evidence['sha256']]
                if choices:
                    path = choices[0].name
            if case['id'] == 'pytorch-original':
                choices = [source / 'snapshots/pytorch_transformer_original/transformer.py']
            if adjacent and adjacent.is_file():
                chosen = adjacent
            elif choices:
                scope = str((source / evidence_path).parent) if evidence_path else ''
                chosen = max(choices, key=lambda p: len(os.path.commonpath([str(p), scope or str(source)])))
            else:
                continue
            files.append({'path': path, 'asset': chosen.relative_to(source).as_posix(), 'sha256': digest(chosen)})
        entry = evidence.get('entry')
        if case['id'] == 'pytorch-original':
            entry = 'transformer.py::Transformer'
        if not entry and origin and files:
            # Transformer is the explicit model entry in its reviewed evidence.
            symbol = 'Transformer' if 'Transformer' in evidence.get('symbols', {}) else None
            if symbol:
                entry = files[0]['path'] + '::' + symbol
        result[case['id']] = {'title': case['title'], 'entry': entry,
                              'files': files, 'evidence': evidence_path,
                              'profile': graph.get('sourceProfile', {}),
                              'available': bool(files)}
    return {'schema': 'archcanvas-preview-catalog-sources/1', 'cases': result}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--target', type=Path, required=True)
    args = parser.parse_args()
    source, target = args.source.resolve(), args.target.resolve()
    if not (source / 'data/catalog.json').is_file():
        parser.error('source is not a Summary Merge distribution')
    copied = []
    for tree in TREES:
        for path in sorted((source / tree).rglob('*')):
            if not path.is_file() or path.is_symlink() or EXCLUDED.intersection(path.relative_to(source).parts):
                continue
            if path.suffix in {'.pyc', '.pid'}:
                continue
            relative = path.relative_to(source)
            destination = target / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            if not (relative.as_posix() in CUSTOMIZED and destination.exists()):
                shutil.copy2(path, destination)
            copied.append({'path': relative.as_posix(), 'bytes': path.stat().st_size,
                           'sha256': digest(path)})
    for relative in ('README.md', 'source_adapter/README.md'):
        destination = target / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source / relative, destination)
        copied.append({'path': relative, 'bytes': (source / relative).stat().st_size,
                       'sha256': digest(source / relative)})
    catalog = json.loads((source / 'data/catalog.json').read_text())
    (target / 'data/catalog-sources.json').write_text(
        json.dumps(source_index(source, catalog), ensure_ascii=False, indent=2) + '\n')
    # Publish independent, legal Python paths after the immutable snapshots.
    # This keeps a future upstream refresh from reintroducing invalid entries.
    for name in ('organize-preview-sources', 'convert-preview-notebooks'):
        spec = importlib.util.spec_from_file_location(name.replace('-', '_'), Path(__file__).with_name(name + '.py'))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        if name == 'organize-preview-sources':
            module.organize(target, source_index(source, catalog))
        else:
            report, outputs = module.build_plan(target)
            for relative, data in outputs.items():
                destination = target / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(data)
            (target / 'data/notebook-conversions.json').write_bytes(module.ledger_bytes(report))
    manifest = {'schema': 'archcanvas-preview-vendor/1',
                'source': 'prototype/Summary_Merge',
                'reason': 'User requested full preview replacement; assets vendored independently for portable builds.',
                'catalog': catalog['counts'], 'files': copied,
                'totalBytes': sum(p['bytes'] for p in copied),
                'excluded': sorted(EXCLUDED) + ['*.pyc', '*.pid'],
                'customized': sorted(CUSTOMIZED),
                'integration': ['yworks_edge_router_lab/studio-bridge.js', 'yworks_edge_router_lab/studio-presentation.js', 'yworks_edge_router_lab/studio-embed.css', 'yworks_edge_router_lab/frontier-task.js'],
                'sourceAssets': ['data/catalog-sources.json', 'data/source-packages.json', 'data/notebook-conversions.json', 'sources/']}
    (target / 'vendor-manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'files': len(copied), 'bytes': manifest['totalBytes'],
                      'cases': catalog['counts'], 'target': str(target)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
