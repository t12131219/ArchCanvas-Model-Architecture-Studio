"""Create or verify a new receipt; never rewrite the earlier hierarchy seal."""
from pathlib import Path
import argparse
import datetime
import hashlib
import json

ROOT = Path(__file__).resolve().parents[3]
OUTPUT = ROOT / 'docs/evidence/m4-hierarchy-final-verification.json'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def gate_audit_bindings():
    resolution = json.loads((ROOT / 'docs/evidence/m4-hierarchy-matrix-work/gate-audit-input-resolution.json').read_bytes())
    audit = json.loads((ROOT / 'docs/evidence/m4-hierarchy-matrix-work/full-gate-audit.json').read_bytes())
    assert len(resolution['bindings']) == len(audit['sourceBindings']) == 1909
    expected = {(row['path'], row['sha256'], row['bytes']) for row in audit['sourceBindings']}
    assert {(row['originalPath'], row['sha256'], row['bytes']) for row in resolution['bindings']} == expected
    bindings = {}
    for row in resolution['bindings']:
        path = ROOT / row['resolvedPath']
        assert path.stat().st_size == row['bytes'] and digest(path) == row['sha256'], str(path)
        if row['resolvedPath'] in bindings:
            assert bindings[row['resolvedPath']] == row['sha256']
        bindings[row['resolvedPath']] = row['sha256']
    return bindings


def historical_bindings():
    archive_dir = ROOT / 'docs/evidence/before-hierarchy-final-matrix'
    resolution = json.loads((archive_dir / 'historical-resolution.json').read_bytes())
    archive = json.loads((archive_dir / 'manifest.json').read_bytes())
    source = resolution['sourceReceipt']
    assert source == archive['sourceReceipt']
    assert source['sha256'] == 'd16215dc87cb8d8209bf40369fdaeb2805020e59a8813dabfc83dc0d31048748'
    source_path = ROOT / source['archivePath']
    assert source_path.stat().st_size == source['bytes'] and digest(source_path) == source['sha256']
    receipt = json.loads(source_path.read_bytes())
    bindings = {}
    assert len(resolution['bindings']) == len(receipt['bindings']) == 1872
    assert len({row['bindingPath'] for row in resolution['bindings']}) == 1872
    assert {row['bindingPath'] for row in resolution['bindings']} == set(receipt['bindings'])
    copied = {(item['originalPath'], item['sha256']): item['archivePath'] for item in archive['files']}
    for row in resolution['bindings']:
        assert receipt['bindings'][row['bindingPath']] == row['sha256']
        assert row['resolvedPath'] == copied.get((row['bindingPath'], row['sha256']), row['bindingPath'])
        path = ROOT / row['resolvedPath']
        assert digest(path) == row['sha256'], str(path)
        if row['resolvedPath'] in bindings:
            assert bindings[row['resolvedPath']] == row['sha256']
        bindings[row['resolvedPath']] = row['sha256']
    return bindings


def create():
    if OUTPUT.exists():
        raise SystemExit('Receipt exists; use verify. No overwrite or hash refresh is allowed.')
    bindings = historical_bindings()
    for relative, expected in gate_audit_bindings().items():
        if relative in bindings:
            assert bindings[relative] == expected, relative
        bindings[relative] = expected
    roots = [
        'docs/evidence/before-hierarchy-final-matrix',
        'docs/evidence/m4-hierarchy-matrix-work',
        'docs/evidence/m4-hierarchy-visible-performance',
        'docs/evidence/browser-visual-matrix-hierarchy-final',
        '.archcanvas/browser-visual-matrix-hierarchy-final',
        '.archcanvas/m4-hierarchy-matrix/exports',
        '.archcanvas/m4-research-trial-hierarchy-final',
    ]
    live_logs = {'service-raw.txt', 'deliverable-service-raw.txt'}
    for directory in roots:
        for path in sorted((ROOT / directory).rglob('*')):
            if not path.is_file() or '__pycache__' in path.parts or path.name in live_logs:
                continue
            relative = str(path.relative_to(ROOT))
            actual = digest(path)
            if relative in bindings:
                assert bindings[relative] == actual, relative
            bindings[relative] = actual
    archive = json.loads((ROOT / 'docs/evidence/before-hierarchy-final-matrix/manifest.json').read_bytes())
    for item in archive['files']:
        path = ROOT / item['originalPath']
        if path.name == 'm4-hierarchy-verification.json':
            # Its unchanged original is also retained in the new archive.
            assert digest(path) == item['sha256']
        bindings[str(path.relative_to(ROOT))] = digest(path)
    for relative in ['scripts/prepare_hierarchy_matrix_capture.py', 'docs/m4-hierarchy-final-matrix.md']:
        bindings[relative] = digest(ROOT / relative)
    result = {
        'schemaVersion': 1,
        'createdAt': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'status': 'verified-byte-bindings-only',
        'previousBindingsPreserved': 1872,
        'preMatrixGateAuditInputsPreserved': 1909,
        'historicalResolution': 'docs/evidence/before-hierarchy-final-matrix/historical-resolution.json',
        'bindingCount': len(bindings),
        'bindings': dict(sorted(bindings.items())),
        'matrix': {'baselineCases': 36, 'editedModels': 3, 'cases': 39, 'artifacts': 234,
                   'artifactCoverage': 'complete', 'humanAcceptanceCertified': False},
        'limitations': [
            'Hashes bind bytes, not native capture provenance, aesthetics, human researchers or presented performance.',
            'Live logs are excluded; explicit cutoff snapshots and lifecycle observations are bound.',
            'Prior receipts and original hashes are preserved through explicit archive resolution.',
        ],
    }
    for relative, expected in bindings.items():
        assert digest(ROOT / relative) == expected, relative
    with OUTPUT.open('x') as stream:
        stream.write(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    return result


def verify():
    result = json.loads(OUTPUT.read_bytes())
    assert len(result['bindings']) == result['bindingCount']
    for relative, expected in result['bindings'].items():
        assert digest(ROOT / relative) == expected, relative
    assert result['previousBindingsPreserved'] == 1872
    for relative, expected in historical_bindings().items():
        assert result['bindings'].get(relative) == expected, relative
    for relative, expected in gate_audit_bindings().items():
        assert result['bindings'].get(relative) == expected, relative
    matrix = json.loads((ROOT / 'docs/evidence/browser-visual-matrix-hierarchy-final/manifest.json').read_bytes())
    assert matrix['capturedBaselineCount'] == 36
    assert matrix['missingBaselineVariants'] == [] and matrix['editedAfterModelsMissing'] == []
    assert len(matrix['captures']) == 39
    assert sum(len(case['files']) for case in matrix['captures']) == 234
    for case in matrix['captures']:
        for record in case['files'].values():
            path = ROOT / 'docs/evidence/browser-visual-matrix-hierarchy-final' / record['path']
            assert path.stat().st_size == record['bytes'] and digest(path) == record['sha256']
    assert matrix['humanAcceptanceCertified'] is False
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['create', 'verify'])
    args = parser.parse_args()
    receipt = create() if args.mode == 'create' else verify()
    print(json.dumps({'status': receipt['status'], 'bindings': receipt['bindingCount'],
                      'previousBindingsPreserved': receipt['previousBindingsPreserved'],
                      'receipt': str(OUTPUT.relative_to(ROOT)), 'receiptSha256': digest(OUTPUT)}, indent=2))
