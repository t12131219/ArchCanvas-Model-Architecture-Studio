"""Seal final boundary evidence once, preserving the earlier receipt's bytes.

This is a byte binding check. It does not turn static candidates, slots, or
bounded browser observations into full browser or human acceptance.
"""
from pathlib import Path
import argparse
import datetime
import hashlib
import json

ROOT = Path(__file__).resolve().parents[3]
ARCHIVE = ROOT / 'docs/evidence/before-m4-boundary-corrections'
WORK = ROOT / 'docs/evidence/m4-boundary-corrections-work'
OUTPUT = ROOT / 'docs/evidence/m4-boundary-final-verification.json'
PREVIOUS_SHA = 'cc959215145fdefd6959b366cac8d3dedd06d72832aa411c882f733bd9a12bf9'
FRONTEND_SHA = 'ce7f7f733da28cb31ecff80ca029a53094e88f8451bffc3874f8167f80a07d00'
JS_SHA = '1f4f51f9818e523916dacea184a7005fa7459bd3f2c4c8bfe6bfc83006e5be29'


def read(path):
    path = path.absolute()
    assert path.is_relative_to(ROOT), str(path)
    current = path
    while current != ROOT:
        assert not current.is_symlink(), str(current)
        current = current.parent
    assert path.is_file(), str(path)
    return path.read_bytes()


def digest(path):
    return hashlib.sha256(read(path)).hexdigest()


def load(path):
    return json.loads(read(path))


def historical_bindings():
    manifest = load(ARCHIVE / 'manifest.json')
    resolution = load(ARCHIVE / 'historical-resolution.json')
    source = manifest['sourceReceipt']
    assert source == resolution['sourceReceipt']
    assert source['sha256'] == PREVIOUS_SHA
    source_path = ROOT / source['archivePath']
    assert len(read(source_path)) == source['bytes'] and digest(source_path) == PREVIOUS_SHA
    previous = load(source_path)
    assert len(previous['bindings']) == len(resolution['bindings']) == 3188
    assert {row['bindingPath'] for row in resolution['bindings']} == set(previous['bindings'])
    copies = {}
    for item in manifest['files']:
        path = ROOT / item['archivePath']
        assert len(read(path)) == item['bytes'] and digest(path) == item['sha256'], str(path)
        copies[(item['originalPath'], item['sha256'])] = item['archivePath']
    bindings = {}
    for row in resolution['bindings']:
        assert previous['bindings'][row['bindingPath']] == row['sha256']
        assert row['resolvedPath'] == copies.get((row['bindingPath'], row['sha256']), row['bindingPath'])
        path = ROOT / row['resolvedPath']
        assert len(read(path)) == row['bytes'] and digest(path) == row['sha256'], str(path)
        assert bindings.get(row['resolvedPath'], row['sha256']) == row['sha256']
        bindings[row['resolvedPath']] = row['sha256']
    assert digest(ROOT / source['originalPath']) == PREVIOUS_SHA
    return bindings


def current_facts():
    assert digest(ROOT / 'src/archcanvas_python/frontend.py') == FRONTEND_SHA
    assert digest(ROOT / 'studio/dist/assets/index-Cr_xKW9U.js') == JS_SHA
    work = load(WORK / 'verification.json')
    for binding in work['bindings']:
        path = ROOT / binding['path']
        assert len(read(path)) == binding['bytes'] and digest(path) == binding['sha256'], str(path)
    assert work['tests']['pythonBoundary'] == '62 passed, 0 skipped'
    assert work['tests']['pythonStaticRegression'] == '21 passed, 0 skipped'
    assert work['tests']['studio'] == '88 passed, 0 failed, 0 skipped'
    spec = load(ROOT / '.archcanvas/browser-visual-matrix-boundary-final/spec.json')
    assert spec['expectedBaselineCount'] == len(spec['variants']) == 36
    assert spec['visualAcceptance'] == 'pending-human-and-browser-review'
    research = load(ROOT / '.archcanvas/m4-research-trial-boundary-final/manifest.json')
    assert research['state'] == 'prepared-no-participants'
    assert research['researchGate'] == 'not_run' and research['researcherCount'] == 0
    assert len(research['slots']) == 5
    for slot in research['slots']:
        assert slot['assignment'] == 'unassigned' and slot['participantCode'] is None
        directory = ROOT / '.archcanvas/m4-research-trial-boundary-final/slots' / slot['slotId']
        assert not (directory / 'assignment.json').exists() and not (directory / 'collected').exists()
    return {'finalFrontendSha256': FRONTEND_SHA, 'studioJsSha256': JS_SHA,
            'staticVisualVariants': 36, 'browserMatrixCollected': 0,
            'boundedBrowserChecks': 11, 'researchSlots': 5, 'humanResearchers': 0,
            'presentedPerformanceCertified': False, 'activeCancellationCertified': False,
            'humanPublicationAcceptanceCertified': False, 'm4Status': 'partial'}


def create():
    assert not OUTPUT.exists(), 'Final receipt exists; verify it. Never refresh its hashes.'
    facts = current_facts()
    bindings = historical_bindings()
    directories = [ARCHIVE, WORK, ROOT / 'docs/evidence/visual-golds-boundary-current',
                   ROOT / '.archcanvas/browser-visual-matrix-boundary-final',
                   ROOT / '.archcanvas/m4-research-trial-boundary-final',
                   *(ROOT / name for name in ['src', 'schemas', 'fixtures', 'scripts', 'tests',
                                              'studio/src', 'studio/tests', 'studio/dist', 'skills/archcanvas'])]
    paths = {path for directory in directories for path in directory.rglob('*')
             if path.is_file() and '__pycache__' not in path.parts and path.suffix != '.pyc'}
    archive = load(ARCHIVE / 'manifest.json')
    # Vite removes the prior hashed assets. Their bytes remain bound through
    # historical resolution; only extant current files have live bindings.
    paths.update(ROOT / item['originalPath'] for item in archive['files']
                 if (ROOT / item['originalPath']).is_file())
    paths.update(ROOT / relative for relative in ['docs/m4-boundary-corrections.md', 'README.md',
                 'AGENTS.md', 'pyproject.toml', 'studio/package.json', 'studio/package-lock.json'])
    for path in sorted(paths):
        relative = str(path.relative_to(ROOT))
        actual = digest(path)
        assert bindings.get(relative, actual) == actual, relative
        bindings[relative] = actual
    result = {'schemaVersion': 1,
              'createdAt': datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'status': 'verified-byte-bindings-only', 'previousBindingsPreserved': 3188,
              'previousReceiptSha256': PREVIOUS_SHA,
              'historicalResolution': str((ARCHIVE / 'historical-resolution.json').relative_to(ROOT)),
              'bindingCount': len(bindings), 'bindings': dict(sorted(bindings.items())),
              'currentFacts': facts,
              'limitations': ['The old 39-case matrix is historical; current static preparation inherits no browser coverage.',
                             'The browser journal used an intermediate Python backend; final fixture reconstruction is separate evidence.',
                             'Hashes and automated checks do not certify pixels, physical-size publication review, humans, or presented performance.']}
    for relative, expected in bindings.items():
        assert digest(ROOT / relative) == expected, relative
    assert current_facts() == facts
    with OUTPUT.open('x') as stream:
        stream.write(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    return result


def verify():
    result = load(OUTPUT)
    assert len(result['bindings']) == result['bindingCount']
    assert result['previousBindingsPreserved'] == 3188 and result['previousReceiptSha256'] == PREVIOUS_SHA
    for relative, expected in result['bindings'].items():
        assert digest(ROOT / relative) == expected, relative
    for relative, expected in historical_bindings().items():
        assert result['bindings'].get(relative) == expected, relative
    assert result['currentFacts'] == current_facts()
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['create', 'verify'])
    args = parser.parse_args()
    result = create() if args.mode == 'create' else verify()
    print(json.dumps({'status': result['status'], 'bindings': result['bindingCount'],
                      'previousBindingsPreserved': result['previousBindingsPreserved'],
                      'receipt': str(OUTPUT.relative_to(ROOT)), 'receiptSha256': digest(OUTPUT)}, indent=2))
