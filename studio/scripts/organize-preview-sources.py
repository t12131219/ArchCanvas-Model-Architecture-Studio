#!/usr/bin/env python3
"""Build self-contained, evidence-preserving Python packages for preset cases.

Snapshots remain immutable provenance. Runtime/editor sources live in sources/;
only logical filenames change, never Python bytes or evidence line numbers.
No model is imported or executed.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import importlib.util
import json
import keyword
import os
import re
import shutil
from pathlib import Path, PurePosixPath


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def identifier(value: str) -> str:
    value = re.sub(r'[^a-zA-Z0-9_]', '_', value)
    if not value or value[0].isdigit() or keyword.iskeyword(value):
        value = '_' + value
    return value


def logical_path(path: str, prefix: str = '') -> str:
    relative = PurePosixPath(path).relative_to(prefix) if prefix else PurePosixPath(path)
    return '/'.join([identifier(p) for p in relative.parts[:-1]] +
                    [identifier(relative.stem) + '.py'])


def entry_file(entry: str | None) -> str | None:
    if not entry:
        return None
    if '::' in entry:
        return entry.split('::', 1)[0]
    return entry.split(':', 1)[0].replace('.', '/') + '.py'


def source_root(target: Path, file: dict) -> Path | None:
    origin = file.get('originalAsset', file['asset'])
    path = file.get('originalPath', file['path'])
    if origin.endswith('/' + path):
        return target / origin[:-len(path)]
    return None


def dependency_closure(target: Path, files: list[dict]) -> list[dict]:
    """Copy only statically named imports available in the same source snapshot.

    Do not choose a similarly named file from a different repository/version.
    Unprovided external libraries continue to be opaque parser boundaries.
    """
    found = {file['path']: dict(file) for file in files}
    roots = {source_root(target, file) for file in files} - {None}
    if len(roots) != 1:
        return list(found.values())
    root = next(iter(roots))
    # Per-case generated sources sometimes omit a helper retained in the
    # enclosing collection's original source snapshot. Accept that collection
    # only when its copies of this package's declared files have identical bytes.
    search_roots = [root]
    for ancestor in root.parents:
        if not ancestor.is_relative_to(target / 'snapshots'):
            break
        candidate = ancestor / 'sources'
        if candidate == root or not candidate.is_dir():
            continue
        matches = [(candidate / f['path'], f['sha256']) for f in files if (candidate / f['path']).is_file()]
        if matches and all(sha(p.read_bytes()) == expected for p, expected in matches):
            search_roots.append(candidate)
    directories = [str(PurePosixPath(path).parent) for path in found]
    common = os.path.commonpath(directories) if directories else ''
    if common == '.':
        common = ''
    queue = list(found)
    while queue:
        path = queue.pop(0)
        tree = ast.parse((target / found[path]['asset']).read_text(encoding='utf-8-sig'))
        for node in ast.walk(tree):
            modules: list[tuple[str, int]] = []
            if isinstance(node, ast.Import):
                modules = [(alias.name, 0) for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                modules = [(node.module or '', node.level)]
                modules += [('.'.join(filter(None, [node.module, a.name])), node.level)
                            for a in node.names if a.name != '*']
            for module, level in modules:
                relative = module.replace('.', '/')
                if level:
                    base = PurePosixPath(path).parent
                    for _ in range(level - 1):
                        base = base.parent
                    bases = [base / relative]
                else:
                    bases = [PurePosixPath(relative)]
                    if common:
                        bases.append(PurePosixPath(common) / relative)
                for base in bases:
                    for candidate in [str(base) + '.py', str(base / '__init__.py')]:
                        asset = next((r / candidate for r in search_roots
                                      if (r / candidate).is_file() and (r / candidate).resolve().is_relative_to(r.resolve())), None)
                        if candidate in found or asset is None:
                            continue
                        data = asset.read_bytes()
                        ast.parse(data.decode('utf-8-sig'), filename=candidate)
                        found[candidate] = {'path': candidate, 'asset': asset.relative_to(target).as_posix(),
                                            'sha256': sha(data), 'dependency': True}
                        queue.append(candidate)
    return [found[path] for path in sorted(found)]


def organize(target: Path, index: dict) -> dict:
    manifest_path = target / 'data/source-packages.json'
    previous = json.loads(manifest_path.read_text()).get('packages', {}) if manifest_path.is_file() else {}
    packages: dict[str, dict] = {}
    result = {'schema': index['schema'], 'sourceLayout': 'python-packages/1', 'cases': {}}
    for case_id, original in index['cases'].items():
        descriptor = dict(original)
        if not original['files']:
            descriptor['unavailableReason'] = 'routing-experiment' if case_id == 'routing-lab' else 'source-free-teaching-svg'
            result['cases'][case_id] = descriptor
            continue
        files = dependency_closure(target, original['files'])
        # Shared repository root removal also makes absolute local imports
        # (layers.*, fc, etc.) resolve without changing source statements.
        prefix = os.path.commonpath([str(PurePosixPath(f['path']).parent) for f in files]) if len(files) > 1 else ''
        if prefix == '.':
            prefix = ''
        names = {f['path']: logical_path(f['path'], prefix) for f in files}
        if len(set(names.values())) != len(names):
            raise ValueError(f'Normalized source path collision: {case_id}')
        fingerprint = sha(json.dumps([(names[f['path']], f['sha256']) for f in files],
                                    ensure_ascii=False, sort_keys=True).encode())
        package_id = identifier(original['title'].lower()) + '_' + fingerprint[:12]
        directory = target / 'sources/packages' / package_id
        packaged = []
        for file in files:
            data = (target / file['asset']).read_bytes()
            if sha(data) != file['sha256']:
                raise ValueError(f'Source digest mismatch: {file["asset"]}')
            ast.parse(data.decode('utf-8-sig'), filename=file['path'])
            asset = directory / names[file['path']]
            asset.parent.mkdir(parents=True, exist_ok=True)
            asset.write_bytes(data)
            packaged.append({'path': names[file['path']], 'originalPath': file['path'],
                             'asset': asset.relative_to(target).as_posix(),
                             'originalAsset': file['asset'], 'sha256': file['sha256'],
                             **({'dependency': True} if file.get('dependency') else {})})
        entry = original.get('entry')
        if entry and '::' in entry:
            path, symbol = entry.split('::', 1)
            if path not in names:
                raise ValueError(f'Entry source missing: {case_id} {entry}')
            entry = names[path] + '::' + symbol
        descriptor.update(files=packaged, entry=entry, originalEntry=original.get('entry'),
                          sourcePackage=package_id, sourceRoot=prefix)
        # Copy the exact declared licenses alongside the readable source tree.
        licenses = []
        evidence = json.loads((target / original['evidence']).read_text()) if original.get('evidence') else {}
        root = source_root(target, files[0])
        for path in evidence.get('license_files', []):
            asset = root / path if root else None
            if not asset or not asset.is_file():
                raise ValueError(f'Declared license missing: {case_id} {path}')
            destination = directory / 'licenses' / path
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(asset.read_bytes())
            licenses.append({'path': path, 'asset': destination.relative_to(target).as_posix(),
                             'originalAsset': asset.relative_to(target).as_posix(), 'sha256': sha(asset.read_bytes())})
        descriptor['licenses'] = licenses
        result['cases'][case_id] = descriptor
        package = packages.setdefault(package_id, {'files': packaged, 'licenses': licenses, 'cases': [], 'evidence': []})
        package['cases'].append(case_id)
        if original.get('evidence') not in package['evidence']:
            package['evidence'].append(original.get('evidence'))
    manifest = {'schema': 'archcanvas-preview-source-packages/1', 'packages': packages,
                'counts': {'cases': len(result['cases']), 'available': sum(bool(c['files']) for c in result['cases'].values()),
                           'packages': len(packages), 'pythonFiles': sum(len(p['files']) for p in packages.values()),
                           'dependenciesAdded': sum(bool(f.get('dependency')) for p in packages.values() for f in p['files'])}}
    for old in previous.keys() - packages.keys():
        directory = target / 'sources/packages' / old
        if directory.is_dir() and directory.resolve().parent == (target / 'sources/packages').resolve():
            shutil.rmtree(directory)
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
    (target / 'data/catalog-sources.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    return manifest['counts']


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--target', type=Path, default=Path(__file__).resolve().parents[1] / 'public/preview')
    args = parser.parse_args()
    target = args.target.resolve()
    spec = importlib.util.spec_from_file_location('preview_vendor', Path(__file__).with_name('vendor-summary-preview.py'))
    vendor = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(vendor)
    catalog = json.loads((target / 'data/catalog.json').read_text())
    print(json.dumps(organize(target, vendor.source_index(target, catalog)), ensure_ascii=False))


if __name__ == '__main__':
    main()
