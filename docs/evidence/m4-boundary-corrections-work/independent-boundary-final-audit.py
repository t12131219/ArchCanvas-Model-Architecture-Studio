#!/usr/bin/env python3
"""Read-only evidence audit; only the optional final report is newly written.

No model execution, services, browser interaction, test reruns, old-receipt
refresh, or human acceptance assertion. Run --preview before the final seal;
run without it after the root has sealed current bytes. Existing output is
never replaced. The final report is intentionally outside the receipt chain.
"""
from __future__ import annotations

import argparse
import ast
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sys
from urllib.parse import unquote, urlsplit
import xml.etree.ElementTree as ET

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[3]
WORK = Path(__file__).resolve().parent
SEAL = ROOT / 'docs/evidence/m4-boundary-final-verification.json'
OUTPUT = WORK / 'independent-boundary-final-audit.json'
ARCHIVE = ROOT / 'docs/evidence/before-m4-boundary-corrections'
OLD_SHA = 'cc959215145fdefd6959b366cac8d3dedd06d72832aa411c882f733bd9a12bf9'
FRONTEND_SHA = 'ce7f7f733da28cb31ecff80ca029a53094e88f8451bffc3874f8167f80a07d00'
NEW_TEST_SHA = '7234d21e22350639404ff6ce11d4852a74b1ecfcf592375053e4ff0ea476578c'
JS_SHA = '1f4f51f9818e523916dacea184a7005fa7459bd3f2c4c8bfe6bfc83006e5be29'


def raw(path):
    path = Path(path)
    if not path.is_absolute():
        path = ROOT / path
    assert path.is_relative_to(ROOT), str(path)
    assert path.is_file() and not path.is_symlink(), str(path)
    return path.read_bytes()


def load(path):
    return json.loads(raw(path))


def sha(path):
    return hashlib.sha256(raw(path)).hexdigest()


def binding(item, base=ROOT):
    path = base / item['path']
    assert len(raw(path)) == item['bytes'], str(path)
    assert sha(path) == item['sha256'], str(path)


def xml_tree(svg, revisions=False):
    root = ET.fromstring(svg)
    if revisions:
        del root.attrib['data-revision']
        metadata = root.find('{http://www.w3.org/2000/svg}metadata')
        value = json.loads(metadata.text)
        del value['revision']
        metadata.text = json.dumps(value, sort_keys=True, separators=(',', ':'))
    def visit(node):
        return [node.tag, sorted(node.attrib.items()), node.text or '', node.tail or '',
                [visit(child) for child in node]]
    return visit(root)


def historical():
    manifest = load(ARCHIVE / 'manifest.json')
    resolution = load(ARCHIVE / 'historical-resolution.json')
    source = manifest['sourceReceipt']
    assert source == resolution['sourceReceipt']
    assert source['sha256'] == OLD_SHA
    assert sha(source['archivePath']) == sha(source['originalPath']) == OLD_SHA
    assert len(raw(source['archivePath'])) == source['bytes']
    previous = load(source['archivePath'])
    assert previous['bindingCount'] == len(previous['bindings']) == 3188
    assert len(manifest['files']) == 165
    copies = {}
    for item in manifest['files']:
        archived = ROOT / item['archivePath']
        assert sha(archived) == item['sha256'] and len(raw(archived)) == item['bytes']
        copies[(item['originalPath'], item['sha256'])] = item['archivePath']
    rows = resolution['bindings']
    assert len(rows) == len({row['bindingPath'] for row in rows}) == 3188
    assert {row['bindingPath'] for row in rows} == set(previous['bindings'])
    archived_count = 0
    for row in rows:
        assert previous['bindings'][row['bindingPath']] == row['sha256']
        expected = copies.get((row['bindingPath'], row['sha256']), row['bindingPath'])
        assert row['resolvedPath'] == expected
        assert sha(expected) == row['sha256'] and len(raw(expected)) == row['bytes']
        archived_count += expected != row['bindingPath']
    assert archived_count == 106
    return {'snapshots': 165, 'historicalBindings': 3188, 'archiveResolved': 106,
            'retained': 3082, 'oldReceiptSha256': OLD_SHA}


def frozen_and_work():
    assert sha('src/archcanvas_python/frontend.py') == FRONTEND_SHA
    assert sha('tests/test_m4_unknown_boundaries.py') == NEW_TEST_SHA
    assert sha('studio/dist/assets/index-Cr_xKW9U.js') == JS_SHA
    work = load(WORK / 'verification.json')
    assert len({item['path'] for item in work['bindings']}) == len(work['bindings'])
    for item in work['bindings']:
        binding(item)
    return {'workBindings': len(work['bindings']), 'frontendSha256': FRONTEND_SHA,
            'newTestSha256': NEW_TEST_SHA, 'jsSha256': JS_SHA}


def tests():
    receipts = load(WORK / 'python-final-command-receipts.json')
    assert receipts['passed'] and len(receipts['processes']) == 2
    for row, count in zip(receipts['processes'], [62, 21]):
        assert row['exitCode'] == 0 and row['passed']
        assert row['expectedTests'] == row['observedTests'] == count
        assert row['argv'][0] == row['pythonExecutable'] == '/home/fzg/anaconda3/bin/python'
        assert row['argv'][1:3] == ['-m', 'unittest']
        assert row['environmentOverrides'] == {'PYTHONDONTWRITEBYTECODE': '1', 'PYTHONPATH': 'src:tests'}
        assert row['cwd'] == str(ROOT)
        for name in ['stdout', 'stderr']:
            binding(row[name])
        log = raw(row['stderr']['path']).decode()
        assert re.search(rf'Ran {count} tests? in ', log)
        assert re.search(r'\nOK\s*$', log) and 'skipped=' not in log
        for item in row['implementationBindings']:
            binding(item)
    tree = ast.parse(raw('tests/test_m4_unknown_boundaries.py'))
    new_tests = [node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name.startswith('test_')]
    assert len(new_tests) == 18
    studio = raw(WORK / 'studio-tests.log').decode()
    for value in ['tests 88', 'pass 88', 'fail 0', 'skipped 0']:
        assert value in studio, value
    build = raw(WORK / 'build.log').decode()
    assert 'tsc --noEmit && vite build' in build and 'index-Cr_xKW9U.js' in build and 'built in' in build
    standalone = load(WORK / 'final-independence-report.json')
    assert standalone['passed'] and len(standalone['checks']) == 9
    assert all(row['passed'] for row in standalone['checks'])
    provenance = standalone['checks'][0]['origins']
    assert all(path.startswith(standalone['standaloneCopy'] + '/src/') for path in provenance.values())
    assert all('Studio_Temp' not in path and 'Architecture Studio_Temp' not in path for path in provenance.values())
    source_manifest = {row['path']: row['sha256'] for row in standalone['sourceManifest']}
    assert source_manifest['src/archcanvas_python/frontend.py'] == FRONTEND_SHA
    base = load(WORK / 'final-base-models-report.json')
    assert base['passed'] and base['independentSuite']['passed']
    assert str(base['independentSuite']['tests']) in ['11', '11/11'] and base['independentSuite']['skipped'] == 0
    holdout = load(WORK / 'independent-holdout-final/m4-holdout-report.json')
    assert holdout['passed'] and all(row['passed'] for row in holdout['checks'])
    assert holdout['checks'][0]['tests'] == '28/28'
    assert sha(WORK / 'independent-holdout-final/release/src/archcanvas_python/frontend.py') == FRONTEND_SHA
    assert sha(WORK / 'independent-holdout-final/release/tests/test_m4_unknown_boundaries.py') == NEW_TEST_SHA
    return {'finalPythonCommands': [62, 21], 'newBoundaryTests': 18, 'studio': 88,
            'independenceChecks': 9, 'baseModelTests': 11, 'holdoutTests': 28,
            'note': 'Read receipts and exact logs; suites were not rerun by this audit.'}


def browser_and_replay():
    validation = load(WORK / 'browser-validation.json')
    journal = load(WORK / 'browser-journal.json')
    assert validation['checkCount'] == len(validation['checks']) == 11 and all(validation['checks'].values())
    for item in validation['bindings']:
        binding(item)
    assert journal['action']['kind'] == 'native-root-drag'
    assert journal['before']['viewBox'].split()[0] == '0'
    assert journal['after']['viewBox'].split()[0] == '-128'
    assert journal['before']['legends'] == journal['after']['legends']
    delta = journal['after']['root']['x'] - journal['before']['root']['x']
    assert abs(delta - (-148 * 7 / 13)) < 0.001
    for first, second in [('before', 'undo'), ('after', 'redo'), ('after', 'edgeUndo')]:
        assert xml_tree(journal[first]['svg'], True) == xml_tree(journal[second]['svg'], True)
    assert journal['saved']['svg'] == journal['reopened']['svg']
    assert journal['inspector']['color'] == '#a194a8' and journal['inspector']['dashed'] is True
    assert journal['inspector']['width'] == '1.5' and journal['edgeEdited']['dashed'] is False
    assert 'stroke-dasharray' not in journal['edgeEdited']['path']
    assert journal['final']['dashed'] is True and journal['final']['scripts'] == ['http://127.0.0.1:8900/assets/index-Cr_xKW9U.js']
    backend = load(WORK / 'browser-backend-initial-receipt.json')
    assert sha(backend['snapshotPath']) == backend['sha256'] != FRONTEND_SHA
    replay = load(WORK / 'final-source-and-canvas-replay.json')
    assert replay['checkCount'] == len(replay['checks']) == 14 and all(replay['checks'].values())
    assert replay['browserBackendFinalCoverageCertified'] is False
    assert replay['browserEvidenceFrontendSha256'] == backend['sha256']
    assert replay['replayFrontendSha256'] == FRONTEND_SHA
    for collection in ['inputBindings', 'outputBindings']:
        for item in replay[collection]:
            binding(item)
    store = load(WORK / 'actual-document-store.json')
    final_architecture = load(WORK / 'final-static-transformer-architecture.json')
    assert store['document']['architecture'] == final_architecture
    assert store['document']['sourceBindingDigest'] == final_architecture['sourceDigest']
    assert store['revision'] == 2 and store['document']['revision'] == 5
    assert store['document']['pinnedObjects'] == [] and store['document']['edgeStyleOverrides'] == {}
    observed = raw(WORK / 'final-observed-browser-scene.svg')
    rebuilt = raw(WORK / 'final-canvas-replayed-interactive.svg')
    assert observed == journal['final']['svg'].encode()
    assert observed != rebuilt and xml_tree(observed) == xml_tree(rebuilt)
    assert replay['svgComparison']['ignoredFields'] == []
    assert replay['svgComparison']['completeXmlTreeEqual'] is True
    assert validation['service']['onlineClaim'] is False and validation['service']['exitCode'] == 0
    return {'browserChecks': 11, 'finalStaticReplayChecks': 14, 'completeXmlEqual': True,
            'rawSvgEqual': False, 'finalBackendNativeCoverageCertified': False,
            'scope': 'One Transformer document; no performance, cancellation, pins, matrix or human gate.'}


def visual_and_research():
    visual = load(WORK / 'visual-static-preparation.json')
    assert visual['sourceInputsUnchanged'] and visual['core']['variantCount'] == 36
    assert visual['core']['frontierCount'] == 9 and visual['matrix']['collectedCases'] == 0
    for item in visual['sourceInputs'] + visual['buildFiles'] + visual['core']['files'] + visual['matrix']['files']:
        binding(item)
    spec = load('.archcanvas/browser-visual-matrix-boundary-final/spec.json')
    assert spec['expectedBaselineCount'] == len(spec['variants']) == 36 and len(spec['frontiers']) == 9
    assert len(spec['coreFiles']) == 72 and len(spec['implementationFiles']) == 21 and len(spec['buildFiles']) == 3
    for item in spec['coreFiles']:
        binding(item, Path(spec['coreDirectory']))
    for item in spec['implementationFiles']:
        binding(item)
    for item in spec['buildFiles']:
        binding(item, ROOT / 'studio/dist')
    assert not (ROOT / '.archcanvas/browser-visual-matrix-boundary-final/manifest.json').exists()
    package = ROOT / '.archcanvas/m4-research-trial-boundary-final'
    manifest = load(package / 'manifest.json')
    assert len(manifest['implementationFiles']) == 61 and len(manifest['baseline']['files']) == 4
    for item in manifest['implementationFiles']:
        binding(item)
    for item in manifest['baseline']['files']:
        binding(item, package)
    assert manifest['state'] == 'prepared-no-participants' and manifest['researcherCount'] == 0
    assert manifest['researchGate'] == 'not_run' and len(manifest['slots']) == 5
    baseline = load(package / 'baseline/canvas.json')
    assert baseline['revision'] == 0
    assert [row['port'] for row in manifest['slots']] == list(range(8901, 8906))
    for row in manifest['slots']:
        assert row['assignment'] == 'unassigned' and row['participantCode'] is None
        binding(row['baselineEnvelope'], package)
        envelope = load(package / row['baselineEnvelope']['path'])
        assert envelope['document'] == baseline and envelope['revision'] == 1
        slot = package / 'slots' / row['slotId']
        assert not (slot / 'assignment.json').exists() and not (slot / 'collected').exists()
        assert not any(slot.rglob('history*.json'))
        for name in ['exports', 'projects', 'transactions']:
            directory = slot / 'workspace' / name
            assert not directory.exists() or not list(directory.iterdir())
    preparation = load(WORK / 'research-current-preparation.json')
    assert preparation['sourceBuildInputsBefore'] == preparation['sourceBuildInputsAfter']
    for path, item in preparation['sourceBuildInputsAfter'].items():
        binding({'path': path, **item})
    assert preparation['assignments'] == preparation['collectedBundles'] == preparation['researcherCount'] == 0
    return {'staticVariants': 36, 'frontiers': 9, 'browserCollected': 0,
            'researchImplementationBindings': 61, 'baselineBindings': 4, 'slots': 5,
            'assigned': 0, 'collected': 0, 'humanResearchers': 0}


def current_docs():
    manifest = load(ARCHIVE / 'manifest.json')
    docs = {ROOT / row['originalPath'] for row in manifest['files'] if row['originalPath'].endswith('.md')}
    docs |= {ROOT / 'docs/m4-boundary-corrections.md', WORK / 'README.md'}
    count = 0
    for doc in sorted(docs):
        text = raw(doc).decode()
        destinations = re.findall(r'\]\((<[^>]+>|[^\s\)]+)(?:\s+[^\)]*)?\)', text)
        destinations += re.findall(r'^\s*\[[^\]]+\]:\s*(<[^>]+>|\S+)', text, re.M)
        for destination in destinations:
            target = destination.strip('<>')
            if target.startswith('#') or urlsplit(target).scheme:
                continue
            target = unquote(target.split('#', 1)[0].split('?', 1)[0])
            if not target:
                continue
            resolved = Path(target) if target.startswith('/') else doc.parent / target
            assert resolved.exists(), f'{doc.relative_to(ROOT)} -> {target}'
            count += 1
    status = load('docs/evidence/m4-human-review-handoff-status.json')
    assert status['productionBuild'] == 'index-Cr_xKW9U.js' and status['productionJsSha256'] == JS_SHA
    assert status['phaseStatus'] == 'partial' and status['humanAcceptanceCertified'] is False
    assert status['currentMatrix']['spec'] == '.archcanvas/browser-visual-matrix-boundary-final/spec.json'
    assert status['currentMatrix']['cases'] == 0
    assert status['research']['package'] == '.archcanvas/m4-research-trial-boundary-final'
    assert status['research']['researchers'] == status['research']['assigned'] == status['research']['collected'] == 0
    assert status['performance']['nativeGestureCancellationCertified'] is False
    assert status['performance']['continuousPresentedPaintCertified'] is False
    overview = raw('docs/m4-boundary-corrections.md').decode()
    assert '62/62' in overview and '21/21' in overview and 'd884' in overview
    assert '14项' in overview and '浏览器collect仍0' in overview and '0分配/收集/真人' in overview
    return {'markdownFilesChecked': len(docs), 'existingLocalLinksChecked': count,
            'currentM4Status': 'partial', 'humanAcceptanceCertified': False,
            'note': 'Historical sections retain their explicitly frozen build scope.'}


def final_seal():
    seal = load(SEAL)
    assert seal['bindingCount'] == len(seal['bindings'])
    assert seal['previousBindingsPreserved'] == 3188 and seal['previousReceiptSha256'] == OLD_SHA
    for path, expected in seal['bindings'].items():
        assert sha(path) == expected, path
    required = ['src/archcanvas_python/frontend.py', 'tests/test_m4_unknown_boundaries.py',
                'studio/src/cameraProjection.ts', 'studio/src/edgeAppearance.ts',
                'studio/dist/assets/index-Cr_xKW9U.js',
                '.archcanvas/browser-visual-matrix-boundary-final/spec.json',
                '.archcanvas/m4-research-trial-boundary-final/manifest.json',
                'docs/evidence/m4-human-review-handoff-status.json', 'docs/m4-boundary-corrections.md',
                str(Path(__file__).relative_to(ROOT))]
    assert all(path in seal['bindings'] for path in required)
    resolution = load(ARCHIVE / 'historical-resolution.json')
    assert all(seal['bindings'][row['resolvedPath']] == row['sha256'] for row in resolution['bindings'])
    facts = seal['currentFacts']
    assert facts['m4Status'] == 'partial' and facts['browserMatrixCollected'] == facts['humanResearchers'] == 0
    assert facts['presentedPerformanceCertified'] is facts['activeCancellationCertified'] is False
    return {'bindingCount': seal['bindingCount'], 'sealSha256': sha(SEAL),
            'allCurrentAndHistoricalBindingsExact': True, 'requiredCurrentBindingsPresent': True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--preview', action='store_true')
    args = parser.parse_args()
    if not args.preview:
        assert SEAL.exists(), 'Wait for final seal before writing final audit report.'
        assert not OUTPUT.exists(), 'Do not overwrite an earlier audit report.'
    results, issues = {}, []
    checks = [('historical', historical), ('frozenAndWork', frozen_and_work), ('tests', tests),
              ('browserAndReplay', browser_and_replay), ('visualAndResearch', visual_and_research),
              ('currentDocs', current_docs)]
    if not args.preview:
        checks.append(('finalSeal', final_seal))
    for name, operation in checks:
        try:
            results[name] = operation()
        except Exception as error:
            issues.append({'check': name, 'type': type(error).__name__, 'message': str(error)})
    report = {'schemaVersion': 1, 'createdAt': datetime.now(timezone.utc).isoformat(),
              'status': 'preview' if args.preview else 'passed-read-only-evidence-audit' if not issues else 'issues-found',
              'passed': not issues, 'results': results, 'issues': issues,
              'limitations': ['Byte and recorded contract checks do not certify actual capture provenance beyond preserved journal scope.',
                              'One browser document and separate static replay do not establish matrix, presented performance, cancellation, pins or human acceptance.',
                              'No source/build/docs edits, tests, services, model execution or participant operations were performed by this audit.']}
    if not args.preview:
        with OUTPUT.open('x') as stream:
            stream.write(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if issues:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
