#!/usr/bin/env python3
"""Compare final static IR/core with one real, earlier-backend browser document.

This is a source/core replay, not new browser coverage for the final Python
backend. All comparisons retain every architecture field and SVG element.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[3]
WORK = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'src'))
from archcanvas_python import analyze_project
from archcanvas_cli.server import validate_document

EXPECTED_FRONTEND = 'ce7f7f733da28cb31ecff80ca029a53094e88f8451bffc3874f8167f80a07d00'


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def write_new(path, raw):
    with path.open('xb') as stream:
        stream.write(raw)


def json_new(path, value):
    write_new(path, (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode())


def xml_tree(raw):
    if re.search(rb'<!\s*(?:DOCTYPE|ENTITY)|<\?', raw, re.I):
        raise ValueError('Unexpected SVG declarations.')
    root = ET.fromstring(raw)
    if root.tag != '{http://www.w3.org/2000/svg}svg':
        raise ValueError('Expected full SVG.')
    def element(item):
        return [item.tag, sorted(item.attrib.items()), item.text or '', item.tail or '',
                [element(child) for child in item]]
    return element(root)


def main():
    paths = [WORK / 'actual-document-store.json', WORK / 'browser-journal.json',
             WORK / 'browser-backend-initial-receipt.json', WORK / 'browser-backend-initial.py.txt',
             ROOT / 'src/archcanvas_python/frontend.py', Path(__file__), WORK / 'replay-final-canvas.mjs']
    paths.extend(sorted((ROOT / 'studio/src/core').glob('*.ts')))
    paths.extend(sorted((ROOT / 'fixtures/transformer').glob('*.py')))
    frozen = {path: path.read_bytes() for path in paths}
    envelope = json.loads(frozen[WORK / 'actual-document-store.json'])
    document = envelope['document']
    journal = json.loads(frozen[WORK / 'browser-journal.json'])
    backend = json.loads(frozen[WORK / 'browser-backend-initial-receipt.json'])
    assert sha(frozen[ROOT / 'src/archcanvas_python/frontend.py']) == EXPECTED_FRONTEND
    validate_document(document, document['id'])
    fresh = analyze_project(ROOT / 'fixtures/transformer', 'model:Transformer')
    json_new(WORK / 'final-static-transformer-architecture.json', fresh)
    browser_svg = journal['final']['svg'].encode()
    write_new(WORK / 'final-observed-browser-scene.svg', browser_svg)
    node = shutil.which('node')
    assert node is not None
    arguments = [node, '--experimental-strip-types', str(WORK / 'replay-final-canvas.mjs'),
                 str(WORK / 'actual-document-store.json'), str(WORK)]
    started = datetime.now(timezone.utc).isoformat()
    result = subprocess.run(arguments, cwd=ROOT, capture_output=True, timeout=60)
    ended = datetime.now(timezone.utc).isoformat()
    write_new(WORK / 'final-canvas-replay.stdout.txt', result.stdout)
    write_new(WORK / 'final-canvas-replay.stderr.txt', result.stderr)
    assert result.returncode == 0, result.stderr.decode()
    process = json.loads(result.stdout)
    replayed_svg = (WORK / 'final-canvas-replayed-interactive.svg').read_bytes()
    scene = json.loads((WORK / 'final-canvas-replayed-scene.json').read_bytes())
    observed_metadata = json.loads(ET.fromstring(browser_svg).find('{http://www.w3.org/2000/svg}metadata').text)
    replayed_metadata = json.loads(ET.fromstring(replayed_svg).find('{http://www.w3.org/2000/svg}metadata').text)
    js_url = journal['final']['scripts'][0]
    js = ROOT / 'studio/dist/assets' / js_url.rsplit('/', 1)[1]
    frozen[js] = js.read_bytes()
    checks = {
        'finalFrontendExactlyExpected': sha(frozen[ROOT / 'src/archcanvas_python/frontend.py']) == EXPECTED_FRONTEND,
        'browserBackendSnapshotExact': sha(frozen[WORK / 'browser-backend-initial.py.txt']) == backend['sha256'],
        'browserBackendIsEarlierDistinctSnapshot': backend['sha256'] != EXPECTED_FRONTEND,
        'savedArchitectureCompleteEqualsFreshFinalAnalysis': document['architecture'] == fresh,
        'savedSourceBindingEqualsFreshFinalAnalysis': document['sourceBindingDigest'] == fresh['sourceDigest'],
        'completeInteractiveSvgTreeExactlyEqualsObservedFinal': xml_tree(replayed_svg) == xml_tree(browser_svg),
        'completeMetadataExactlyEqualsObservedFinal': replayed_metadata == observed_metadata,
        'visualRevisionExactlyMatchesSavedAndObserved': scene['revision'] == document['revision'] == observed_metadata['revision'],
        'sourceDigestExactlyMatchesSavedAndObserved': fresh['sourceDigest'] == observed_metadata['sourceDigest'],
        'irDigestExactlyMatchesSavedAndObserved': fresh['irDigest'] == observed_metadata['irDigest'],
        'documentIdExactlyMatchesSavedAndObserved': document['id'] == observed_metadata['documentId'] == process['documentId'],
        'negativeRootCoordinatePreserved': document['layout']['call:instance:model.Transformer']['x'] == -98,
        'observedJsIsCurrentBuild': js_url.endswith('/assets/index-Cr_xKW9U.js'),
        'replayProcessPassed': process['passed'] is True,
    }
    for path, raw in frozen.items():
        assert path.read_bytes() == raw, 'Input changed: ' + str(path)
    def binding(path, raw=None):
        raw = path.read_bytes() if raw is None else raw
        return {'path': str(path.relative_to(ROOT)), 'sha256': sha(raw), 'bytes': len(raw)}
    outputs = [WORK / name for name in ('final-static-transformer-architecture.json',
               'final-observed-browser-scene.svg', 'final-canvas-replayed-scene.json',
               'final-canvas-replayed-interactive.svg', 'final-canvas-replay.stdout.txt',
               'final-canvas-replay.stderr.txt')]
    report = {'schemaVersion': 1, 'passed': all(checks.values()), 'scope': 'final-static-IR-and-complete-core-replay-of-earlier-backend-browser-document',
              'generatedAt': ended, 'checks': checks, 'checkCount': len(checks),
              'browserEvidenceFrontendSha256': backend['sha256'], 'replayFrontendSha256': EXPECTED_FRONTEND,
              'browserBackendFinalCoverageCertified': False,
              'architectureComparedFields': sorted(fresh),
              'svgComparison': {'rawBytesEqual': replayed_svg == browser_svg, 'completeXmlTreeEqual': checks['completeInteractiveSvgTreeExactlyEqualsObservedFinal'],
                                'normalization': 'XML parsing resolves entities and self-closing tags and disregards attribute order only; no fields, revisions, text, metadata or elements removed.',
                                'ignoredFields': []},
              'document': {'id': document['id'], 'visualRevision': document['revision'], 'storageRevision': envelope['revision'],
                           'sourceDigest': fresh['sourceDigest'], 'irDigest': fresh['irDigest'],
                           'rootLayout': document['layout']['call:instance:model.Transformer'], 'bounds': scene['bounds']},
              'process': {'argv': arguments, 'cwd': str(ROOT), 'startedAt': started, 'endedAt': ended, 'exitCode': result.returncode},
              'inputBindings': [binding(path, raw) for path, raw in sorted(frozen.items())],
              'outputBindings': [binding(path) for path in outputs],
              'limitations': ['Fresh final source was analyzed as AST only; fixture models were not imported or executed.',
                              'The actual browser backend was the retained earlier d884 snapshot. Exact unchanged Transformer replay does not certify final-backend unknown-boundary browser coverage.',
                              'One saved Transformer document only; no matrix coverage, performance, cancellation, calibrated publication or human acceptance.']}
    json_new(WORK / 'final-source-and-canvas-replay.json', report)
    print(json.dumps({'passed': report['passed'], 'checks': len(checks), 'report': str(WORK / 'final-source-and-canvas-replay.json'),
                      'rawSvgBytesEqual': replayed_svg == browser_svg}, indent=2))
    if not report['passed']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
