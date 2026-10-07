#!/usr/bin/env python3
"""One independent hash-only final read, with output outside every sealed root."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

OUTPUT = Path(__file__).resolve().parent
ROOT = OUTPUT.parents[3]
WORK = ROOT / 'docs/evidence/m4-au3-visual-matrix-work'
SEAL = ROOT / 'docs/evidence/m4-au3-current-matrix-verification-sealed.json'
SEAL_EXPECTED = {'path': str(SEAL.relative_to(ROOT)), 'bytes': 669929,
                 'sha256': '360685f78ecc6d29875854a00ba9d8be19d1b2212483382aff78144dc4cc8225'}
ROOT_RECEIPT = ROOT / 'docs/evidence/m4-au3-post-seal-readback/root-seal-attempt-2/receipt.json'
ROOT_RECEIPT_EXPECTED = {'path': str(ROOT_RECEIPT.relative_to(ROOT)), 'bytes': 1752,
                        'sha256': '245ef5c2b75444a0d03815ddad465086f1aaa1ee59469a45979f089240dfb218'}
EXTERNAL = {Path('/home/fzg/.codex/skills/.system/skill-creator/scripts/quick_validate.py'),
            ROOT.parent / 'ArchCanvas_双向模型可视化与编辑框架_技术计划书.md'}
OBSERVED = {}


def now():
    return datetime.now(timezone.utc).isoformat()


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2) + '\n').encode()


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def resolve(name):
    path = Path(name)
    if path.is_absolute():
        require(path in EXTERNAL, 'Unexpected external semantic path: ' + name)
        return path
    require('..' not in path.parts and bool(path.parts), 'Unsafe relative input path.')
    return ROOT / path


def regular(path):
    require(path.is_absolute() and (path.is_relative_to(ROOT) or path in EXTERNAL), 'Input outside authorized actual paths.')
    require(path.is_file(), 'Missing input: ' + str(path))
    require(not path.is_symlink() and not any(p.is_symlink() for p in path.parents), 'Input symlink forbidden: ' + str(path))
    return path


def binding(path, raw):
    return {'path': str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path),
            'bytes': len(raw), 'sha256': digest(raw)}


def read(path):
    raw = regular(path).read_bytes()
    actual = binding(path, raw)
    require(path not in OBSERVED or OBSERVED[path] == actual, 'Input changed between reads: ' + str(path))
    OBSERVED[path] = actual
    return raw


def check(row, path=None):
    path = path or resolve(row['path'])
    actual = binding(path, read(path))
    require(actual['bytes'] == row['bytes'] and actual['sha256'] == row['sha256'], 'Expected bytes/hash mismatch: ' + str(path))
    return actual


def data(path, expected=None):
    if expected is not None:
        check(expected, path)
    return json.loads(read(path))


def write_new(name, value):
    with (OUTPUT / name).open('xb') as handle:
        handle.write(encoded(value))


def file_set(directory):
    require(directory.is_relative_to(ROOT) and directory.is_dir(), 'Missing formal root directory.')
    items = list(directory.rglob('*'))
    require(not any(p.is_symlink() for p in items), 'Directory contains symlink: ' + str(directory))
    return sorted(str(regular(p).relative_to(ROOT)) for p in items if p.is_file())


def main():
    started = now()
    require(not (OUTPUT / 'final-receipt.json').exists(), 'Independent attempt already frozen; no overwrite.')
    try:
        seal = data(SEAL, SEAL_EXPECTED)
        rows = seal['bindings']
        require(seal['bindingCount'] == len(rows) == 2883, 'Seal binding count differs.')
        require(len({r['path'] for r in rows}) == len(rows), 'Duplicate seal input path.')
        require(all(not Path(r['path']).is_absolute() for r in rows), 'Internal seal path is external.')
        sealed = {r['path']: r for r in rows}
        require(str(SEAL.relative_to(ROOT)) not in sealed, 'Seal self bound unexpectedly.')
        for row in rows:
            check(row)
        require(len(seal['externalSemanticInputBindings']) == 2
                and {resolve(r['path']) for r in seal['externalSemanticInputBindings']} == EXTERNAL, 'External inputs differ from fixed two.')
        for row in seal['externalSemanticInputBindings']:
            check(row)
        root = data(ROOT_RECEIPT, ROOT_RECEIPT_EXPECTED)
        require(root['exitCode'] == 0 and root['seal'] == SEAL_EXPECTED, 'Root seal success receipt differs.')
        for key in ('helper', 'helperSnapshot', 'stdout', 'stderr', 'seal'):
            check(root[key])
        failed = data(resolve(root['priorFailedAttemptRetained']))
        require(failed['exitCode'] != 0, 'Prior failed seal attempt missing.')
        for key in ('helperSnapshot', 'stdout', 'stderr'):
            check(failed[key])
        print('2883 internal seal bindings and two external inputs exact.', flush=True)

        archive_path = resolve(seal['priorArchive']['path'])
        archive = data(archive_path, seal['priorArchive'])
        archive_root = archive_path.parent
        previous_path = ROOT / 'docs/evidence/m4-ancestor-corridor-current-verification-sealed.json'
        previous_final_path = ROOT / 'docs/evidence/m4-ancestor-corridor-work/acceptance/final-seal-attempt-1/final-receipt.json'
        previous, previous_final = data(previous_path), data(previous_final_path)
        check(previous_final['seal'])
        require(previous['bindingCount'] == len(previous['bindings']) == 4233, 'Prior seal count differs.')
        require(previous_final['supplementalBindingCount'] == len(previous_final['supplementalBindings']) == 24, 'Prior final supplemental count differs.')
        union = {}
        for row in previous['bindings'] + previous_final['supplementalBindings'] + [OBSERVED[previous_path], OBSERVED[previous_final_path]]:
            require(row['path'] not in union, 'Duplicate old union path.')
            require(not Path(row['path']).is_absolute() and '..' not in Path(row['path']).parts, 'Unsafe old union source.')
            union[row['path']] = row
        require(len(union) == archive['contentFileCount'] == 4259, 'Archive union count differs.')
        mapping = archive['mapping']
        require(len(mapping) == len({r['sourcePath'] for r in mapping}) == len({r['archivePath'] for r in mapping}) == 4259,
                'Archive mapping count or uniqueness differs.')
        require({r['sourcePath'] for r in mapping} == set(union), 'Archive sources differ from complete prior union.')
        archive_set_before = file_set(archive_root / 'files')
        require({str((archive_root / r['archivePath']).relative_to(ROOT)) for r in mapping} == set(archive_set_before), 'Archive exact copy file-set differs.')
        changed_sources, mapping_readback = [], []
        for row in mapping:
            expected = union[row['sourcePath']]
            require(row['archivePath'] == 'files/' + row['sourcePath'], 'Archive source/destination mapping differs.')
            require(row['bytes'] == expected['bytes'] and row['sha256'] == expected['sha256'], 'Archive mapping differs from prior binding.')
            copy_path = archive_root / row['archivePath']
            actual_copy = check(expected, copy_path)
            require(actual_copy['path'] not in sealed, 'Archive copy unexpectedly duplicated in internal new seal bindings.')
            actual_source = binding(resolve(row['sourcePath']), read(resolve(row['sourcePath'])))
            if actual_source != expected:
                require(row['sourcePath'] in sealed and sealed[row['sourcePath']] == actual_source,
                        'Changed old source is not resolved by exact current seal: ' + row['sourcePath'])
                changed_sources.append({'sourcePath': row['sourcePath'], 'oldBinding': expected, 'currentBinding': actual_source,
                                        'historicalArchiveCopy': actual_copy, 'currentBytesBoundByNewSeal': True})
            mapping_readback.append({'sourcePath': row['sourcePath'], 'archiveBinding': actual_copy, 'expectedOldBinding': expected, 'exact': True})
        require(sum(r['bytes'] for r in mapping) == archive['contentBytes'] == 300995336, 'Archive byte sum differs.')
        require(digest(encoded(mapping)) == archive['mappingSha256'], 'Archive mapping digest differs.')
        require(digest(encoded(sorted(union))) == archive['sourceFileSetSha256'], 'Archive source file-set digest differs.')
        archive_run = data(WORK / 'archive-before-matrix-attempt-2.json')
        require(archive_run['exitCode'] == 0 and archive_run['manifest'] == seal['priorArchive'], 'Archive attempt 2 receipt differs.')
        for row in archive_run['archiveBindings']:
            check(row)
        require(archive_run['overallFileCount'] == len(archive_run['archiveBindings']) == 4268, 'Archive overall count differs.')
        write_new('prior-archive-readback.json', {'mappingCount': 4259, 'contentBytes': 300995336,
                  'exactPriorUnion': True, 'newSealInheritsCopiesThroughManifest': True,
                  'changedLiveSourcesResolvedByArchiveAndCurrentSeal': changed_sources, 'mappingReadback': mapping_readback})
        print('4259 archive mappings/copies and 4268 complete archive files exact.', flush=True)

        status = data(resolve(seal['currentStatus']['path']), seal['currentStatus'])
        require(status['schemaVersion'] == 10 and status['phaseStatus'] == 'partial'
                and status['nextPhaseStarted'] is False and status['humanAcceptanceCertified'] is False, 'Current M4 phase/certification differs.')
        require(status['research']['humanResearcherCount'] == status['research']['assignedCount'] == status['research']['collectedCount'] == 0
                and not status['research']['currentAu3PackagePrepared'] and not status['research']['currentAu3PackageVerified']
                and not status['research']['aiCountsAsHuman'], 'Research/human scope differs.')
        for row in status['evidenceRefs']:
            check(row)
            require(row['path'] in sealed and sealed[row['path']] == row, 'Status reference not exactly bound in seal.')
        collected_path = resolve(status['currentBrowser']['manifest'])
        collected = data(collected_path)
        require(collected['artifactCoverage'] == 'complete' and collected['visualAcceptance'] == 'pending-human-review'
                and not collected['humanAcceptanceCertified'], 'Artifact/human scope differs.')
        captures = collected['captures']
        require(len(captures) == len({r['caseId'] for r in captures}) == 39, 'Collector capture count differs.')
        require(sum(r['state'] == 'baseline' for r in captures) == 36
                and sum(r['state'] == 'edited' for r in captures) == 3
                and {r['fixture'] for r in captures if r['state'] == 'edited'} == {'transformer', 'mlp', 'residual_cnn'}, 'Collector baseline/edited coverage differs.')
        require(not collected['missingBaselineVariants'] and not collected['editedAfterModelsMissing'], 'Collector artifacts missing.')
        stored, export_only, capture_rows = 0, [], []
        for capture in captures:
            require(set(capture['files']) == {'canvas', 'svg', 'exportReceipt', 'screenshot', 'browserScene', 'screenReceipt'}, 'Six collector fields differ.')
            for row in capture['files'].values():
                check(row, collected_path.parent / row['path'])
            bound_dir = WORK / 'bound' / capture['caseId']
            bound = data(bound_dir / 'binding-receipt.json')
            for row in bound['copiedFiles']:
                check(row, bound_dir / row['path'])
            for field, row in capture['files'].items():
                actual_bound = binding(bound_dir / bound['capture'][field], read(bound_dir / bound['capture'][field]))
                require(actual_bound['bytes'] == row['bytes'] and actual_bound['sha256'] == row['sha256'], 'Collector/bound source copy differs.')
            if bound['savedExportCanvasExact']:
                stored += 1
            else:
                export_only.append(capture['caseId'])
            capture_rows.append({'caseId': capture['caseId'], 'state': capture['state'], 'sixCollectorFilesExact': True,
                                 'savedExportCanvasExact': bound['savedExportCanvasExact'], 'visualReview': capture['visualReview']})
        require(stored == seal['storedEnvelopeCases'] == status['currentBrowser']['storedSnapshotCases'] == 38
                and export_only == [seal['firstCaseExportOnly']] == ['transformer-level0-paper-180'], 'Saved/export-only scope differs.')
        template = data(collected_path.parent / 'review-template.json')
        require(template['status'] == 'pending-human-review' and not template['humanAcceptanceCertified']
                and len(template['cases']) == 39 and all(r['status'] == 'pending' for r in template['cases']), 'Human review template scope differs.')
        write_new('current-matrix-readback.json', {'caseCount': 39, 'baselineCount': 36, 'editedCount': 3,
                  'captureFiles': 234, 'storedEnvelopeCases': stored, 'exportOnlyCases': export_only,
                  'artifactCoverage': collected['artifactCoverage'], 'visualAcceptance': collected['visualAcceptance'],
                  'humanAcceptanceCertified': False, 'rows': capture_rows})

        semantic_path = resolve(seal['currentDocumentationSemanticAudit']['path'])
        semantic = data(semantic_path, seal['currentDocumentationSemanticAudit'])
        require(semantic['status'] == 'passed-with-stated-scope' and semantic['inputsUnchanged']
                and semantic['inputsBefore'] == semantic['inputsAfter'] and len(semantic['inputsAfter']) == 500, 'Semantic freeze differs.')
        require(len(semantic['auditedDocuments']) == semantic['currentDocumentCount'] == 21
                and len(semantic['semanticChecks']) == 17 and all(r['passed'] for r in semantic['semanticChecks'])
                and not semantic['remainingSemanticContradictionsFound'], 'Semantic scope/counts differ.')
        for row in semantic['inputsAfter']:
            check(row)
        for row in semantic['auditedDocuments']:
            check(row['source']); check(row['snapshot'])
            require(row['source']['bytes'] == row['snapshot']['bytes'] and row['source']['sha256'] == row['snapshot']['sha256'], 'Frozen document snapshot differs.')
        require(not semantic['currentCompleteReleaseBytesCertified'], 'Current standalone release is overcertified.')
        require(status['tests']['studio']['passed'] == seal['existingStudioTests'] == 179
                and not status['tests']['suiteCountsCombined'] and not status['tests']['rerunThisCollectionRound'], 'Existing test scope differs.')
        require(status['tests']['focusedSeparateRun']['passed'] == 26
                and status['tests']['standalone']['currentFullReleaseFilesStillExact'] is False
                and status['tests']['standalone']['laterSkillReferenceEdits'] is True, 'Focused/standalone time scope differs.')
        require(not seal['productTestsRerunThisCollectionRound'] and seal['humans'] == 0
                and not any(seal[k] for k in ('currentResearchPrepared', 'globalRouteBeautyCertified', 'physicalPublicationCertified',
                                               'presentedPerformanceCertified', 'activeHeldCancellationCertified', 'userModelExecuted', 'dependenciesInstalled')),
                'Seal certification scope differs.')
        input_scope = status['currentInputDiagnostic']
        require(seal['inputDiagnostic'] == input_scope and input_scope['attempts'] == 6
                and input_scope['completedOperations'] == 5 and input_scope['noInputAttempts'] == 1
                and not input_scope['presentedPerformanceCertified'] and not input_scope['overallInpCertified']
                and not input_scope['activeCancellationCertified'], 'Input diagnostic scope differs.')
        write_new('semantic-and-phase-readback.json', {'schema10M4Partial': True, 'nextPhaseStarted': False,
                  'semanticAuditInputsExact': 500, 'internalSemanticInputs': 498, 'externalSemanticInputs': 2,
                  'documentsExact': 21, 'semanticChecksRecordedPassed': 17, 'humans': 0,
                  'currentResearchPrepared': False, 'currentCompleteReleaseBytesCertified': False,
                  'existingStudioTests': 179, 'focusedTestsKeptSeparate': 26,
                  'testsRerunThisAudit': False, 'inputDiagnostic': input_scope,
                  'scope': 'Recorded semantic conclusions and references read back by hash; no semantic review rerun, validator, tests, model, UI, renderer, or image decoding.'})

        tracked_roots = [WORK, collected_path.parent, ROOT / 'docs/evidence/visual-golds-au3-matrix', ROOT / 'skills/archcanvas']
        root_sets_before = {str(directory.relative_to(ROOT)): file_set(directory) for directory in tracked_roots}
        require(all(set(paths).issubset(sealed) for paths in root_sets_before.values()), 'Frozen root has an unbound extra file.')
        observed_before = [OBSERVED[path] for path in sorted(OBSERVED)]
        write_new('inputs-before.json', observed_before)
        observed_after = [binding(regular(path), path.read_bytes()) for path in sorted(OBSERVED)]
        require(observed_before == observed_after, 'Audit inputs changed during independent readback.')
        require(file_set(archive_root / 'files') == archive_set_before, 'Archive file-set changed during audit.')
        root_sets_after = {str(directory.relative_to(ROOT)): file_set(directory) for directory in tracked_roots}
        require(root_sets_after == root_sets_before, 'Frozen root file-set changed during independent readback.')
        write_new('inputs-after.json', observed_after)
        write_new('file-sets-readback.json', {'before': root_sets_before, 'after': root_sets_after,
                  'unchanged': True, 'archiveCopiesBeforeAfterExactFileSet': True})
        require(binding(SEAL, SEAL.read_bytes()) == SEAL_EXPECTED, 'Seal changed after final audit read.')
        supplemental = [binding(p, p.read_bytes()) for p in sorted(OUTPUT.iterdir()) if p.is_file()]
        result = {'protocol': 'archcanvas-au3-post-seal-independent-hash-readback/1',
                  'startedAt': started, 'finishedAt': now(), 'status': 'passed-with-stated-scope', 'exitCode': 0,
                  'argv': sys.argv, 'cwd': str(Path.cwd()), 'auditor': 'AI subagent /root/corridor_design',
                  'scope': 'One independent read-only byte/hash/reference/file-set final audit. No product, current docs/status, sealed inputs, old audit or old seal changed.',
                  'seal': SEAL_EXPECTED, 'rootSealExecutionReceipt': ROOT_RECEIPT_EXPECTED,
                  'all2883UniqueInternalSealBindingsExact': True, 'twoFixedExternalSemanticBindingsExact': True,
                  'all4259ArchiveMappingsAndCopiesExact': True, 'all4268CompleteArchiveFilesExact': True,
                  'archive4259CopiesInheritedThroughManifestNotDuplicatedInSeal': True,
                  'changedOldLiveSourceCount': len(changed_sources), 'changedOldLiveSourcesResolvedThroughArchiveAndNewSeal': True,
                  'collectorCases': 39, 'collectorFilesExact': 234, 'baselineCases': 36, 'editedCases': 3,
                  'storedEnvelopeCases': 38, 'exportOnlyCases': export_only,
                  'semanticAudit500InputsAnd21DocsExact': True, 'schema10M4PartialNoNextPhase': True,
                  'existing179TestsAndSeparate26TimeScopePreserved': True,
                  'uniqueInputsRead': len(observed_before), 'inputsBeforeAfterExact': True, 'fileSetsBeforeAfterExact': True,
                  'testsRun': False, 'buildRun': False, 'validatorRun': False, 'modelsRun': False,
                  'browserOperated': False, 'rendererReexecuted': False, 'imagesDecodedOrReviewed': False,
                  'humanAcceptanceCertified': False, 'pixelAcceptanceCertified': False,
                  'publicationCertified': False, 'performanceCertified': False, 'humans': 0,
                  'supplementalFiles': supplemental,
                  'selfBindingExcluded': True, 'postSealRootExplicitlyExcludedBySeal': True,
                  'limits': seal['limits']}
        write_new('final-receipt.json', result)
        print(json.dumps({k: v for k, v in result.items() if k != 'supplementalFiles'}, ensure_ascii=False, indent=2), flush=True)
        print(json.dumps({'finalReceipt': binding(OUTPUT / 'final-receipt.json', (OUTPUT / 'final-receipt.json').read_bytes())}, indent=2), flush=True)
        return 0
    except Exception as error:
        write_new('failed-receipt.json', {'startedAt': started, 'finishedAt': now(), 'exitCode': 1,
                                        'error': str(error), 'inputsObserved': list(OBSERVED.values()),
                                        'scope': 'Failure preserved; no frozen inputs modified.'})
        print(str(error), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
