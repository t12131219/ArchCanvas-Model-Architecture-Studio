#!/usr/bin/env python3
"""Read-only check of archived documents and the original 1,872 bindings."""
from pathlib import Path
import argparse
import hashlib
import json


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def record(path):
    data = path.read_bytes()
    return {'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}


def require_record(path, expected):
    actual = record(path)
    assert actual['bytes'] == expected['bytes'], str(path)
    assert actual['sha256'] == expected['sha256'], str(path)
    return actual


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--compare-current', action='store_true',
                        help='also require current originals to remain byte-identical')
    args = parser.parse_args()
    manifest_path = HERE / 'manifest.json'
    manifest = json.loads(manifest_path.read_bytes())
    for item in manifest['files']:
        require_record(ROOT / item['archivePath'], item)
        if args.compare_current:
            require_record(ROOT / item['originalPath'], item)
    for item in manifest['companions']:
        require_record(ROOT / item['path'], item)
    require_record(ROOT / manifest['previousArchiveManifest']['path'],
                   manifest['previousArchiveManifest'])
    receipt_record = manifest['sourceReceipt']
    receipt_path = ROOT / receipt_record['archivePath']
    require_record(receipt_path, receipt_record)
    receipt = json.loads(receipt_path.read_bytes())
    resolution = json.loads((HERE / 'historical-resolution.json').read_bytes())
    rows = resolution['bindings']
    assert len(rows) == len(receipt['bindings']) == manifest['previousBindingsVerified']
    assert len({row['bindingPath'] for row in rows}) == len(rows)
    copied = {(item['originalPath'], item['sha256']): item['archivePath']
              for item in manifest['files']}
    archived_count = 0
    preserved_count = 0
    for row in rows:
        expected = receipt['bindings'][row['bindingPath']]
        assert expected == row['sha256'], row['bindingPath']
        intended_path = copied.get((row['bindingPath'], expected), row['bindingPath'])
        assert row['resolvedPath'] == intended_path, row['bindingPath']
        assert hashlib.sha256((ROOT / intended_path).read_bytes()).hexdigest() == expected, intended_path
        if intended_path != row['bindingPath']:
            archived_count += 1
        else:
            preserved_count += 1
    print(json.dumps({
        'status': 'passed-original-bytes-and-historical-bindings',
        'archiveManifest': str(manifest_path.relative_to(ROOT)),
        'archiveManifestSha256': record(manifest_path)['sha256'],
        'archivedFiles': len(manifest['files']),
        'historicalBindings': len(rows),
        'resolvedThroughNewArchive': archived_count,
        'existingBindingPathsPreserved': preserved_count,
        'currentOriginalsCompared': args.compare_current,
        'sourceReceiptSha256': receipt_record['sha256'],
        'scope': 'Archive and historical byte bindings only; no new matrix, performance, publication or human acceptance.'
    }, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
