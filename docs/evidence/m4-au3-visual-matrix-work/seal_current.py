"""Freeze this collection and explicitly resolve preceding mutable paths through archive."""
from pathlib import Path
import datetime, hashlib, json

ROOT = Path(__file__).resolve().parents[3]
WORK = ROOT / 'docs/evidence/m4-au3-visual-matrix-work'
SEAL = ROOT / 'docs/evidence/m4-au3-current-matrix-verification-sealed.json'
READ_BINDINGS = {}
EXTERNAL_BINDINGS = {}
EXTERNAL_SEMANTIC_PATHS = {
    Path('/home/fzg/.codex/skills/.system/skill-creator/scripts/quick_validate.py'),
    ROOT.parent / 'ArchCanvas_双向模型可视化与编辑框架_技术计划书.md',
}

def regular(path):
    assert path.is_relative_to(ROOT), path
    assert path.is_file() and not path.is_symlink(), path
    assert not any(parent.is_symlink() for parent in path.parents if parent.is_relative_to(ROOT)), path
    return path

def binding(path):
    regular(path)
    body = path.read_bytes()
    return {'path': str(path.relative_to(ROOT)), 'bytes': len(body),
            'sha256': hashlib.sha256(body).hexdigest()}

def read_json(path):
    regular(path)
    body = path.read_bytes()
    before = {'path': str(path.relative_to(ROOT)), 'bytes': len(body),
              'sha256': hashlib.sha256(body).hexdigest()}
    if path in READ_BINDINGS:
        assert READ_BINDINGS[path] == before, path
    READ_BINDINGS[path] = before
    return json.loads(body)

def files(directory):
    assert directory.is_relative_to(ROOT) and not directory.is_symlink()
    items = list(directory.rglob('*'))
    assert not any(path.is_symlink() for path in items), directory
    return {regular(path) for path in items if path.is_file()}

def matches(path, expected):
    actual = binding(path)
    if path in READ_BINDINGS:
        assert READ_BINDINGS[path] == actual, path
    READ_BINDINGS[path] = actual
    return actual['bytes'] == expected['bytes'] and actual['sha256'] == expected['sha256']

def external_binding(path):
    assert path in EXTERNAL_SEMANTIC_PATHS and path.is_file() and not path.is_symlink(), path
    assert not any(parent.is_symlink() for parent in path.parents), path
    body = path.read_bytes()
    return {'path': str(path), 'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()}

def main():
    assert not SEAL.exists()
    status_path = ROOT / 'docs/evidence/m4-human-review-handoff-status.json'
    status = read_json(status_path)
    assert status['schemaVersion'] == 10 and status['phaseStatus'] == 'partial'
    assert status['nextPhaseStarted'] is False and status['humanAcceptanceCertified'] is False
    assert status['research']['humanResearcherCount'] == 0
    assert status['currentBrowser']['baselineCases'] == 36 and status['currentBrowser']['editedCases'] == 3
    archive_path = ROOT / 'docs/evidence/before-m4-au3-full-matrix/manifest.json'
    archive = read_json(archive_path)
    assert archive['contentFileCount'] == 4259 and archive['fileSetExact'] and archive['sourceBeforeAfterExact']
    archive_run = read_json(WORK / 'archive-before-matrix-attempt-2.json')
    assert archive_run['exitCode'] == 0 and matches(archive_path, archive_run['manifest'])
    assert status['historicalArchive']['manifestSha256'] == READ_BINDINGS[archive_path]['sha256']
    previous_seal_path = ROOT / 'docs/evidence/m4-ancestor-corridor-current-verification-sealed.json'
    previous_final_path = ROOT / 'docs/evidence/m4-ancestor-corridor-work/acceptance/final-seal-attempt-1/final-receipt.json'
    previous_seal = read_json(previous_seal_path)
    previous_final = read_json(previous_final_path)
    assert matches(previous_seal_path, previous_final['seal'])
    previous_expected = {}
    for row in previous_seal['bindings'] + previous_final['supplementalBindings'] + [binding(previous_seal_path), binding(previous_final_path)]:
        name = row['path']
        assert not Path(name).is_absolute() and '..' not in Path(name).parts
        assert name not in previous_expected, name
        previous_expected[name] = row
    assert len(previous_expected) == 4259
    mapping = archive['mapping']
    assert len(mapping) == len(previous_expected)
    assert len({row['sourcePath'] for row in mapping}) == len(mapping)
    assert len({row['archivePath'] for row in mapping}) == len(mapping)
    assert {row['sourcePath'] for row in mapping} == set(previous_expected)
    for row in mapping:
        source, copied = row['sourcePath'], row['archivePath']
        assert copied == 'files/' + source and '..' not in Path(copied).parts
        expected = previous_expected[source]
        assert row['bytes'] == expected['bytes'] and row['sha256'] == expected['sha256']
        path = archive_path.parent / copied
        assert matches(path, expected), (source, copied)
    archive_file_set = files(archive_path.parent / 'files')
    assert {str(p.relative_to(archive_path.parent)) for p in archive_file_set} == {row['archivePath'] for row in mapping}
    prior_test = ROOT / 'docs/evidence/m4-ancestor-corridor-work/root/full-studio-attempt-2/receipt.json'
    tests = read_json(prior_test)
    assert tests['exitCode'] == 0 and tests['sourceBeforeAfterExact']
    assert all(matches(ROOT / row['path'], row) for row in tests['bindings'])
    prep = read_json(WORK / 'preparation-receipt.json')
    assert all(matches(ROOT / row['path'], row) for row in prep['inputBindings'])
    for ref in status['evidenceRefs']:
        assert matches(ROOT / ref['path'], ref), ref['path']
    collected_path = ROOT / 'docs/evidence/browser-visual-matrix-au3-current/manifest.json'
    collected = read_json(collected_path)
    assert collected['artifactCoverage'] == 'complete' and collected['visualAcceptance'] == 'pending-human-review'
    assert not collected['humanAcceptanceCertified'] and not collected['missingBaselineVariants'] and not collected['editedAfterModelsMissing']
    assert len(collected['captures']) == 39 and len({item['caseId'] for item in collected['captures']}) == 39
    assert sum(item['state'] == 'baseline' for item in collected['captures']) == 36
    assert {item['fixture'] for item in collected['captures'] if item['state'] == 'edited'} == {'transformer', 'mlp', 'residual_cnn'}
    assert sum(len(item['files']) for item in collected['captures']) == 234
    stored_count, tolerance_count, export_only = 0, 0, []
    for item in collected['captures']:
        for row in item['files'].values():
            assert matches(collected_path.parent / row['path'], row)
        receipt = read_json(WORK / 'bound' / item['caseId'] / 'binding-receipt.json')
        stored_count += bool(receipt.get('savedExportCanvasExact'))
        if not receipt.get('savedExportCanvasExact'):
            export_only.append(item['caseId'])
        # Parse actual capture metadata independently of its derived height serialization.
        observed = read_json(WORK / 'raw' / item['caseId'] / 'public-observation.json')
        import xml.etree.ElementTree as ET
        embedded = json.loads(ET.fromstring(observed['svg']).find('{http://www.w3.org/2000/svg}metadata').text)
        if embedded != observed['metadata']:
            left, right = dict(embedded), dict(observed['metadata'])
            a, b = left.pop('heightMm'), right.pop('heightMm')
            assert left == right and abs(a - b) <= 1e-10
            tolerance_count += 1
    assert stored_count == status['currentBrowser']['storedSnapshotCases'] == 38
    assert export_only == ['transformer-level0-paper-180']
    assert tolerance_count == status['currentBrowser']['heightMmOnlyToleranceCases'] == 6
    fit = read_json(WORK / 'pixel-audit/all-36-fit.receipt.json')
    local = read_json(WORK / 'pixel-audit/gestures/three-model-local-and-edited.receipt.json')
    assert fit['caseCount'] == fit['reviewedOriginalWholeWindowScreenshots'] == 36 and fit['exactSpecVariantCoverage']
    assert local['reviewCount'] == local['originalScreenshotsPersonallyViewed'] == 19
    assert local['matchedImageStates'] == 18 and local['mismatchImageStates'] == 1
    semantic_path = WORK / 'docs-semantic-audit-attempt1/final-readback.json'
    semantic_expected = {'bytes': 566931, 'sha256': 'a9dbf2d67cae3427ad9c73e86309f3a26aa0ebb9dd5e281e6faba046469cf3ad'}
    assert matches(semantic_path, semantic_expected)
    semantic = read_json(semantic_path)
    assert semantic['status'] == 'passed-with-stated-scope'
    assert semantic['currentDocumentCount'] == len(semantic['auditedDocuments']) == 21
    assert len(semantic['semanticChecks']) == 17 and all(row['passed'] for row in semantic['semanticChecks'])
    assert semantic['inputsUnchanged'] and semantic['inputsBefore'] == semantic['inputsAfter']
    assert len(semantic['inputsAfter']) == 500 and not semantic['remainingSemanticContradictionsFound']
    for row in semantic['inputsAfter']:
        path = Path(row['path'])
        if path.is_absolute():
            actual = external_binding(path)
            assert actual == row, path
            EXTERNAL_BINDINGS[path] = actual
        else:
            assert '..' not in path.parts
            assert matches(ROOT / path, row), path
    assert set(EXTERNAL_BINDINGS) == EXTERNAL_SEMANTIC_PATHS
    for row in semantic['auditedDocuments']:
        assert row['source']['bytes'] == row['snapshot']['bytes']
        assert row['source']['sha256'] == row['snapshot']['sha256']
        assert matches(ROOT / row['source']['path'], row['source'])
        assert matches(ROOT / row['snapshot']['path'], row['snapshot'])
    roots = [WORK, ROOT / 'docs/evidence/browser-visual-matrix-au3-current',
             ROOT / 'docs/evidence/visual-golds-au3-matrix']
    root_sets = {directory: files(directory) for directory in roots}
    paths = set().union(*root_sets.values())
    paths.update(ROOT / row['path'] for row in tests['bindings'])
    paths.update(ROOT / row['path'] for row in prep['inputBindings'])
    paths.update(ROOT / ref['path'] for ref in status['evidenceRefs'])
    paths.update([ROOT / '.archcanvas/browser-visual-matrix-au3/spec.json', ROOT / 'AGENTS.md',
                  ROOT / 'docs/m4-au3-current-matrix.md', status_path, archive_path,
                  ROOT / 'docs/m4-ancestor-corridors.md',
                  ROOT / 'docs/evidence/m4-ancestor-corridor-current-verification-sealed.json',
                  ROOT / 'docs/evidence/m4-ancestor-corridor-work/acceptance/final-seal-attempt-1/final-receipt.json'])
    mutations = read_json(WORK / 'docs-finalize-attempt-1/mutation-receipt.json')
    assert matches(archive_path, mutations['archive'])
    # These paths changed after the initial mutation receipt; current semantic audit binds final bytes.
    paths.update(ROOT / row['path'] for row in mutations['after'])
    paths.update(files(ROOT / 'skills/archcanvas'))
    paths.update(READ_BINDINGS.keys() - {archive_path.parent / row['archivePath'] for row in mapping})
    bindings = [binding(path) for path in sorted(paths)]
    # Final read in the same operation excludes an input changing during seal creation.
    assert bindings == [binding(path) for path in sorted(paths)]
    assert all(root_sets[directory] == files(directory) for directory in roots)
    assert archive_file_set == files(archive_path.parent / 'files')
    assert all(binding(path) == before for path, before in READ_BINDINGS.items())
    assert all(external_binding(path) == before for path, before in EXTERNAL_BINDINGS.items())
    result = {'schemaVersion': 1, 'sealedAt': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'state': 'au3-artifact-matrix-complete-M4-partial',
        'scope': 'Current 36-baseline+3-edited collection, bounded leaf four-direction/history/persistence, AI pixel findings and six-attempt input diagnostic. No product change, human, publication, presented performance or M5 certification.',
        'productionBuild': status['productionBuild'], 'productionJsSha256': status['productionJsSha256'],
        'productionCss': status['productionCss'], 'productionCssSha256': status['productionCssSha256'],
        'currentStatus': binding(status_path), 'priorArchive': binding(archive_path),
        'priorArchiveContentFiles': 4259, 'priorArchiveContentBytesVerified': True,
        'previous4233MutableBindingsResolvedByArchive': True,
        'existingStudioInputBindingsStillExact': len(tests['bindings']), 'existingStudioTests': 179,
        'productTestsRerunThisCollectionRound': False, 'preparationInputBindingsStillExact': len(prep['inputBindings']),
        'baselineCases': 36, 'editedCases': 3, 'captureFiles': 234,
        'fourDirectionOperations': 12, 'fourDirectionScope': status['currentBrowser']['scope'],
        'firstCaseExportOnly': status['currentBrowser']['firstCaseExportOnly'], 'storedEnvelopeCases': 38,
        'heightMmOnlyToleranceCases': 6, 'heightMmTolerance': 1e-10,
        'fitAiReviewed': 36, 'localAndEditedAiReviewed': 19, 'localAndEditedPixelMatched': 18,
        'retainedPixelMismatchAndSeparateRetry': True, 'humans': 0, 'currentResearchPrepared': False,
        'visualAcceptance': 'pending-human-review', 'globalRouteBeautyCertified': False,
        'physicalPublicationCertified': False, 'presentedPerformanceCertified': False,
        'activeHeldCancellationCertified': False, 'userModelExecuted': False, 'dependenciesInstalled': False,
        'inputDiagnostic': status['currentInputDiagnostic'],
        'currentDocumentationSemanticAudit': binding(semantic_path),
        'currentDocumentationCount': 21, 'semanticChecksPassed': 17,
        'semanticAuditInputsStillExact': 500,
        'externalSemanticInputBindings': [EXTERNAL_BINDINGS[path] for path in sorted(EXTERNAL_BINDINGS)],
        'bindingCount': len(bindings), 'bindings': bindings,
        'excludedMutablePaths': ['.archcanvas/m4-au3-visual-matrix-session', '.archcanvas/m4-au3-input-session'],
        'excludedByConstruction': ['this seal itself',
            'docs/evidence/m4-au3-post-seal-readback: seal execution receipts and later independent hash-only audit',
            'prior archive content files individually: mapped hashes verified above and inherited through bound archive manifest'],
        'limits': ['Artifact completeness is not pixel or human approval.',
            'Previous seal original hashes stay unchanged; mutable summaries resolve through the exact prior archive.',
            'Matrix UA/DPR are explicitly historical provenance; later actual observer data do not rewrite receipts.',
            'Leaf gesture tests do not cover every object, arbitrary displacement, nonempty pins or ancestor motion.',
            'Matched-subset p95 and rAF callback cadence do not certify overall INP or presented frames.',
            'Later Skill documents differ from the earlier standalone frozen release copy.']}
    with SEAL.open('x') as output:
        json.dump(result, output, indent=2, ensure_ascii=False)
        output.write('\n')
    print(json.dumps({'seal': binding(SEAL), 'bindingCount': len(bindings),
                      'archiveMappingsVerified': len(mapping), 'phase': 'partial'}, ensure_ascii=False))

if __name__ == '__main__':
    main()
