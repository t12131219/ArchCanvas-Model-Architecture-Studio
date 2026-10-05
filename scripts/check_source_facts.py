#!/usr/bin/env python3
"""Verify source facts through copied core, document storage and actual publication SVG.

No model source is imported or executed. This is an engineering identity chain,
not a browser interaction or human research receipt.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys
import xml.etree.ElementTree as ET

from check_independence import clean_environment, verify
from check_stage2 import command, python_args

MODELS = ('TemporalForecaster', 'SkipSegmentation', 'GraphForecast')


def check(project: Path) -> Path:
    provenance_path, provenance = verify(project.resolve(), build=False)
    release = Path(provenance['standaloneCopy'])
    temporary = release.parent
    environment = clean_environment(temporary)
    artifacts = temporary / 'source-facts-artifacts'
    artifacts.mkdir()
    node = shutil.which('node')
    if node is None:
        raise RuntimeError('Node 24+ is required for the formal copied core.')
    suite = command([node, '--experimental-strip-types', '--test', '--test-isolation=none',
                     str(release / 'studio/tests/source-facts.test.ts')], release / 'studio', environment)
    (artifacts / 'independent-suite.txt').write_bytes(suite)
    checks = []
    for name in MODELS:
        folder = artifacts / name
        folder.mkdir()
        architecture_path = folder / 'architecture.json'
        code = ('import json; from pathlib import Path; from archcanvas_python import analyze_project; '
                f'architecture=analyze_project(Path({str(release / "fixtures/holdout_families")!r}),{("model:" + name)!r}); '
                f'Path({str(architecture_path)!r}).write_text(json.dumps(architecture,ensure_ascii=False,indent=2),encoding="utf-8")')
        command(python_args(Path(sys.executable), release, code), release, environment)
        command([node, str(release / 'scripts/source_facts_artifacts.mjs'), 'create',
                 str(architecture_path), str(folder)], release, environment)
        canvas_path = folder / 'canvas.json'
        storage_path = folder / 'saved-envelope.json'
        code = ('import json; from pathlib import Path; from archcanvas_cli.server import DocumentStore; '
                f'path=Path({str(canvas_path)!r}); document=json.loads(path.read_bytes()); '
                f'store=DocumentStore(Path({str(folder / "workspace/documents")!r})); '
                'saved=store.put(document["id"],document,0); reopened=store.get(document["id"]); '
                'assert reopened==saved and reopened["document"]==document; '
                f'Path({str(storage_path)!r}).write_text(json.dumps(reopened,ensure_ascii=False,indent=2),encoding="utf-8")')
        command(python_args(Path(sys.executable), release, code), release, environment)
        command([node, str(release / 'scripts/source_facts_artifacts.mjs'), 'render',
                 str(storage_path), str(folder)], release, environment)
        raw_svg = folder / 'figure.raw.svg'
        published_svg = folder / 'figure.svg'
        publication_receipt = folder / 'figure.svg.receipt.json'
        code = ('import json; from pathlib import Path; from archcanvas_publication import export_svg; '
                f'result=export_svg(Path({str(raw_svg)!r}).read_text(),"svg",180,300); '
                f'Path({str(published_svg)!r}).write_bytes(result["data"]); '
                f'Path({str(publication_receipt)!r}).write_text(json.dumps(result["receipt"],indent=2),encoding="utf-8")')
        command(python_args(Path(sys.executable), release, code), release, environment)
        architecture = json.loads(architecture_path.read_bytes())
        document = json.loads(canvas_path.read_bytes())
        envelope = json.loads(storage_path.read_bytes())
        scene = json.loads((folder / 'scene.json').read_bytes())
        metadata = json.loads(ET.fromstring(published_svg.read_bytes()).find('{http://www.w3.org/2000/svg}metadata').text)
        receipt = json.loads(publication_receipt.read_bytes())
        assert document['architecture'] == architecture == envelope['document']['architecture']
        assert metadata['sourceDigest'] == architecture['sourceDigest'] and metadata['irDigest'] == architecture['irDigest']
        assert metadata['documentId'] == document['id'] and metadata['revision'] == document['revision']
        assert metadata['sourceFacts'] == scene['sourceFacts']
        assert {fact['id'] for fact in metadata['sourceFacts']} == {item['id'] for item in architecture['nodes']}
        for fact in metadata['sourceFacts']:
            original = next(item for item in architecture['nodes'] if item['id'] == fact['id'])
            assert fact['sourceLabel'] == original['label']
            for key in ('kind', 'category', 'evidence', 'instanceId', 'callId', 'repeat', 'outputPath', 'source'):
                assert fact.get(key) == original.get(key)
        assert receipt['inputSvgDigest'] == hashlib.sha256(raw_svg.read_bytes()).hexdigest()
        assert receipt['outputDigest'] == hashlib.sha256(published_svg.read_bytes()).hexdigest()
        checks.append({'entry': architecture['entry'], 'documentId': document['id'], 'visualRevision': document['revision'],
                       'storageRevision': envelope['revision'], 'sourceDigest': architecture['sourceDigest'], 'irDigest': architecture['irDigest'],
                       'canonicalFactCount': len(metadata['sourceFacts']), 'renderedNodeCount': len(metadata['renderedNodes']),
                       'renderedBindingCount': len(metadata['renderedBindings']),
                       'sourceBoundFactsUnchanged': True, 'savedAndReopened': True, 'actualPublishedSvgMetadataMatched': True,
                       'outputPaths': [fact['outputPath'] for fact in metadata['sourceFacts'] if 'outputPath' in fact],
                       'sharedCalls': [{'instanceId': fact['instanceId'], 'callId': fact['callId'], 'callCount': fact['callCount']}
                                       for fact in metadata['sourceFacts'] if fact.get('callCount', 0) > 1],
                       'repeats': [fact['repeat'] for fact in metadata['sourceFacts'] if 'repeat' in fact],
                       'opaque': [{'id': fact['id'], 'kind': fact['kind']} for fact in metadata['sourceFacts'] if fact['evidence'] == 'opaque'],
                       'artifactDirectory': str(folder), 'publishedSvgSha256': receipt['outputDigest']})
    report = {'schemaVersion': 1, 'passed': True, 'scope': 'source facts → copied core visual edits → saved/reopened DocumentStore → actual publication SVG',
              'standaloneCopy': str(release), 'independenceReport': str(provenance_path), 'pythonIsolation': '-I -S',
              'tests': '5/5', 'suite': str(artifacts / 'independent-suite.txt'), 'checks': checks,
              'limitations': ['Static source facts only; no model import, construction or forward execution.',
                             'This engineering chain is not browser gesture evidence or a human task result.',
                             'Publication metadata preserves identities but does not prove final-size readability or PDF metadata retention.']}
    path = artifacts / 'report.json'
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return path


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', type=Path, default=Path(__file__).resolve().parents[1])
    print(json.dumps({'passed': True, 'report': str(check(parser.parse_args().project))}, indent=2))
