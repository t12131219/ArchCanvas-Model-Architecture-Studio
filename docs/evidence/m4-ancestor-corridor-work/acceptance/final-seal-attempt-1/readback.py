"""Post-seal independent exact readback; no tests/builds/browser/model execution."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import os
import re

ROOT = Path(__file__).resolve().parents[5]
OUT = Path(__file__).parent
OUT = OUT / 'completed-attempt-1'
OUT.mkdir(exist_ok=False)
WORK = ROOT / 'docs/evidence/m4-ancestor-corridor-work'
SEAL = ROOT / 'docs/evidence/m4-ancestor-corridor-current-verification-sealed.json'
EXPECTED = '83f2cf88d0ad40a28acf700f0fed5cea8ea0cbed7ce2e7d5935487f82a8ce76b'

def digest(path):
    value = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            value.update(block)
    return value.hexdigest()

def binding(path):
    try: label = str(path.relative_to(ROOT))
    except ValueError: label = str(path)
    return {'path': label, 'bytes': path.stat().st_size, 'sha256': digest(path)}

def read(path): return json.loads(path.read_text())
def new(name, value):
    with (OUT / name).open('x') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write('\n')

def check(row, key='path'):
    path = ROOT / row[key]
    try:
        actual = binding(path)
        exact = actual['sha256'] == row['sha256'] and ('bytes' not in row or actual['bytes'] == row['bytes'])
        return {**row, 'actual': actual, 'exact': exact}
    except (OSError, ValueError) as error:
        return {**row, 'exact': False, 'error': str(error)}

def checks(rows, key='path'):
    with ThreadPoolExecutor(max_workers=6) as pool:
        return list(pool.map(lambda row: check(row, key), rows))

def require_exact(rows):
    bad = [row for row in rows if not row['exact']]
    assert not bad, bad[:3]
    return True

def require_receipt(path):
    receipt = read(path)
    assert receipt['exitCode'] == 0 and receipt['sourceBeforeAfterExact']
    assert receipt['bindings'] == receipt['after']
    observed = checks(receipt['bindings'] + receipt['logs'])
    require_exact(observed)
    return receipt, {'receipt': binding(path), 'exitCode': 0, 'beforeAfterExact': True, 'bindingsAndLogsExact': True, 'checks': observed}

before = binding(SEAL)
assert before['bytes'] == 1051490 and before['sha256'] == EXPECTED
seal = read(SEAL)
new('seal-input-repaired-helper-before.json', {'scope': 'Supplemental independent audit after exclusive seal; absent from seal bindings, no self-cycle or reseal. Earlier helper failed on an overbroad historical final-directory substring, retained separately.', 'at': datetime.now(timezone.utc).isoformat(), 'seal': before})
bound = checks(seal['bindings'])
require_exact(bound)
assert len(bound) == seal['bindingCount'] == 4233 and len({row['path'] for row in bound}) == 4233
assert not any(row['path'].startswith(str(OUT.relative_to(ROOT)) + '/') for row in bound)
assert not any(row['path'] == str(SEAL.relative_to(ROOT)) for row in bound)
new('seal-bindings-readback.json', {'declared': 4233, 'actualCount': len(bound), 'uniquePaths': 4233, 'allExact': True, 'bindings': bound})
print(json.dumps({'stage': 'seal', 'bindings': len(bound), 'allExact': True}), flush=True)

status = read(ROOT / seal['currentStatus']['path'])
assert check(seal['currentStatus'])['exact']
assert seal['currentStatus']['sha256'] == '105c01115d7df4f2d51b68174b209083d9397c4c431ece93fd90df648069ac9b'
assert status['schemaVersion'] == 9 and isinstance(status['evidenceRefs'], list)
refs = checks(status['evidenceRefs']); require_exact(refs); assert len(refs) == 22
assert not any(row['path'] == str(SEAL.relative_to(ROOT)) for row in status['evidenceRefs'])
assert status['phaseStatus'] == 'partial' and status['nextPhaseStarted'] is False and status['humanAcceptanceCertified'] is False
research = status['research']
assert research['currentAu3PackagePrepared'] is False and research['currentAu3PackageVerified'] is False
assert research['assignedCount'] == research['collectedCount'] == research['humanResearcherCount'] == 0
assert research['aiCountsAsHuman'] is False and research['oldSlotsMayBeAssigned'] is False and research['oldBgChsPackagesStale'] is True
new('status-references-readback.json', {'schemaVersion': 9, 'evidenceRefsType': 'list', 'count': 22, 'allExact': True, 'phaseStatus': 'partial', 'nextPhaseStarted': False, 'research': research, 'humanAcceptanceCertified': False, 'references': refs})

archive_path = ROOT / seal['priorArchive']['path']; archive = read(archive_path)
assert check(seal['priorArchive'])['exact']
assert digest(archive_path) == 'c1969548ea2b2b1e9158c3f424b5e29f6910fe124879ce7f658b54d5e996df28'
archived = checks(archive['bindings'], 'archivePath'); require_exact(archived)
assert len(archived) == archive['bindingCount'] == 1911
actual_archive_files = {str(path.relative_to(ROOT)) for path in (archive_path.parent / 'files').rglob('*') if path.is_file()}
assert actual_archive_files == {row['archivePath'] for row in archive['bindings']}
lookup = {row['path']: row for row in archive['bindings']}
old_seal_path = ROOT / archive['previousSeal']; old_seal = read(old_seal_path)
assert digest(old_seal_path) == archive['previousSealSha256'] == '21086a9a305544d303bb5505a81b19ff070f08bceb727a7d93bb871f0f17a96e'
old_mappings = []
for row in old_seal['bindings']:
    archived_row = lookup[row['path']]
    exact = all(row[key] == archived_row[key] for key in ['path', 'bytes', 'sha256'])
    assert exact
    old_mappings.append({'path': row['path'], 'exactOldSealTuple': exact})
assert len(old_mappings) == old_seal['bindingCount'] == 1896
assert archive['sealedBindingsAndSeal'] == 1897 and archive['supplementalFinalReadbackFiles'] == 14
immutable = [row for row in archive['bindings'] if (row['path'].startswith('docs/evidence/') and row['path'] != 'docs/evidence/m4-human-review-handoff-status.json') or row['path'].startswith('.archcanvas/m4-research-trial-repeat-outline-current/')]
originals = checks(immutable); require_exact(originals)
assert len(originals) == seal['verification']['priorImmutableEvidenceAndResearchOriginalsExact'] == 1775
readme_row = lookup['docs/evidence/m4-repeat-outline-work/README.md']; assert check(readme_row)['exact']
old_test_checks = checks([row for row in archive['bindings'] if row['path'].startswith('studio/tests/')])
changed_old_tests = [row['path'] for row in old_test_checks if not row['exact']]
assert changed_old_tests == ['studio/tests/repeat-outline-independent.test.ts']
new('prior-archive-and-originals-readback.json', {'manifest': binding(archive_path), 'all1911ArchivedExact': True, 'archiveFileSetExact': True,
    'previousSeal': binding(old_seal_path), 'previousSealHashExact': True, 'old1896BindingMappingsExact': True, 'supplementalOldFinalFiles': 14,
    'all1775ImmutableCurrentOriginalsExact': True, 'oldRepeatReadmeRestoredExact': True, 'oldTestsUnchanged': sum(row['exact'] for row in old_test_checks),
    'authorizedCurrentOldTestChanges': changed_old_tests, 'archiveBindings': archived, 'originalBindings': originals, 'oldMappings': old_mappings})
print(json.dumps({'stage': 'historical', 'archive': 1911, 'immutableCurrentOriginals': 1775, 'allExact': True}), flush=True)

full, full_review = require_receipt(WORK / 'root/full-studio-attempt-2/receipt.json')
build, build_review = require_receipt(WORK / 'root/build-attempt-3/receipt.json')
focused, focused_review = require_receipt(WORK / 'root/acceptance-target-attempt-3/receipt.json')
assert full['bindings'] == build['bindings'] == focused['bindings']
full_stdout = (WORK / 'root/full-studio-attempt-2/stdout.log').read_text()
counts = {name: int(re.search(r'\b' + name + r' (\d+)\s*$', full_stdout, re.M).group(1)) for name in ['tests', 'pass', 'fail', 'skipped', 'cancelled']}
assert counts == {'tests': 179, 'pass': 179, 'fail': 0, 'skipped': 0, 'cancelled': 0}
focused_stdout = (WORK / 'root/acceptance-target-attempt-3/stdout.log').read_text()
assert re.search(r'\btests 26\s*$', focused_stdout, re.M) and re.search(r'\bpass 26\s*$', focused_stdout, re.M)
package = read(ROOT / 'studio/package.json'); assert package['scripts']['build'] == 'tsc --noEmit && vite build'
assert 'build' == build['argv'][-1]
assert 'tsc --noEmit && vite build' in (WORK / 'root/build-attempt-3/stdout.log').read_text()
js = binding(ROOT / 'studio/dist/assets/index-au3IB_0Q.js'); css = binding(ROOT / 'studio/dist/assets/index-B6WbMowt.css')
assert js['sha256'] == seal['productionJsSha256'] == status['productionJsSha256'] == 'dca15460bc9ed8def5ff80c9da5dfcf16bb49f7a230986e0ffeef1a6b0e7548b'
assert css['sha256'] == seal['productionCssSha256'] == status['productionCssSha256'] == '172a09a8c147e53c3bef426cf76b59b8cc4893e891eb6e920aa7b25a0bb024e0'

standalone_path = WORK / 'acceptance/standalone-attempt-1/run-1/process.json'; standalone = read(standalone_path)
assert standalone['exitCode'] == 0 and standalone['checkCount'] == 9 and standalone['allChecksPassed']
assert standalone['sourceBeforeAfterExact'] and standalone['dependenciesBeforeAfterExact']
standalone_receipt_checks = checks([standalone[key] for key in ['reportCopy', 'actualTemporaryReport', 'stdout', 'stderr', 'spaceBefore', 'checkScript', 'wrapper', 'apiHelpStdout', 'apiHelpStderr']]); require_exact(standalone_receipt_checks)
source_before = read(standalone_path.parent / 'source-bindings-before.json')['bindings']; source_after = read(standalone_path.parent / 'source-bindings-after.json')['bindings']; assert source_before == source_after
source_checks = checks(source_after); assert len(source_checks) == 209
source_drift = [row for row in source_checks if not row['exact']]
assert {row['path'] for row in source_drift} == {str(ROOT / 'skills/archcanvas/references/formal-alpha.md'), str(ROOT / 'skills/archcanvas/references/runtime-compatibility.md')}
standalone_copy = Path(standalone['standaloneCopy'])
source_snapshot_checks = checks([{'path': str(standalone_copy / Path(row['path']).relative_to(ROOT)), 'bytes': row['bytes'], 'sha256': row['sha256']} for row in source_after if not row['path'].endswith('/acceptance/standalone-attempt-1/run_check.py')])
# The running reviewer wrapper is created outside the copied RELEASE_ITEMS
# snapshot timeline; all actual copied formal source entries remain exact.
require_exact(source_snapshot_checks)
left_dep = read(standalone_path.parent / 'dependency-bindings-before.json'); right_dep = read(standalone_path.parent / 'dependency-bindings-after.json')
assert left_dep['bindings'] == right_dep['bindings']; dep_checks = checks(right_dep['bindings']); require_exact(dep_checks); assert len(dep_checks) == 654
actual_report = read(Path(standalone['reportCopy']['path'])); copy = Path(standalone['standaloneCopy']); assert copy.is_dir()
expected_check_names = ['package-provenance', 'capabilities', 'analyze-transformer', 'analyze-mlp', 'analyze-residual_cnn', 'analyze-holdout_vit', 'analyze-holdout_families', 'source-bytes-unchanged', 'studio-build']
assert [row['name'] for row in actual_report['checks']] == expected_check_names and all(row['passed'] for row in actual_report['checks'])
for name, origin in actual_report['checks'][0]['origins'].items():
    assert Path(origin).resolve().is_relative_to(copy / 'src') and 'Architecture Studio_Temp' not in origin
prior_standalone_review_path = WORK / 'acceptance/standalone-attempt-1/standalone-scope-review.json'
prior_standalone_review = read(prior_standalone_review_path)
assert prior_standalone_review['actualCopySourceManifestReadbackExact'] and prior_standalone_review['actualAnalyzeOutputReadbackExact']
assert prior_standalone_review['fullStandaloneSourceManifestEntries'] == len(actual_report['sourceManifest'])
for row in right_dep['bindings']:
    source = Path(row['path']); destination = copy / 'studio/node_modules' / source.relative_to(ROOT / 'studio/node_modules')
    assert destination.stat().st_size == row['bytes'] and digest(destination) == row['sha256']
for row in left_dep['symlinks']:
    source = Path(row['path']); destination = copy / 'studio/node_modules' / source.relative_to(ROOT / 'studio/node_modules')
    assert os.readlink(source) == os.readlink(destination) == row['target']
    assert source.resolve().is_relative_to(ROOT / 'studio/node_modules') and destination.resolve().is_relative_to(copy / 'studio/node_modules')
assert len(left_dep['symlinks']) == 5
new('critical-receipts-readback.json', {'full179': {**full_review, 'actualStdoutCounts': counts}, 'buildIncludesStrictTypescript': build_review,
    'focused26SeparateNotAddedTo179': focused_review, 'fullBuildFocusedSourceBindingsIdentical': True, 'productionJs': js, 'productionCss': css,
    'standalone': {'process': binding(standalone_path), 'allNineActualChecksExact': True, 'actualReport': binding(Path(standalone['reportCopy']['path'])),
        'source209RunBeforeAfterExact': True, 'source207StillCurrentExact': sum(row['exact'] for row in source_checks), 'twoSkillRefsUpdatedByLaterDocsFreeze': source_drift,
        'copiedSourceSnapshotBindingsExact': True, 'dependencies654Exact': True, 'dependencySymlinks5Exact': True, 'priorActualCopyManifestEntriesChecked': len(actual_report['sourceManifest']),
        'priorActualCopyAndAnalyzeReadbackBoundNow': binding(prior_standalone_review_path), 'moduleOriginsInsideStandaloneSrc': True, 'cleanInstallClaim': False, 'userModelExecution': False,
        'receiptChecks': standalone_receipt_checks, 'sourceChecks': source_checks, 'dependencyChecks': dep_checks}})
print(json.dumps({'stage': 'receipts', 'full': 179, 'focused': 26, 'standalone': 9, 'sourceAndLogsExact': True}), flush=True)

browser_path = ROOT / seal['currentBrowser']['path']; browser = read(browser_path)
assert check(seal['currentBrowser'])['exact']
assert digest(browser_path) == '1894404b99784276927356aed6506b5fdb21b29021e3dfa8f6f7481faccc4c29'
browser_checks = checks(browser['bindings'] + browser['source'] + browser['build']); require_exact(browser_checks); assert len(browser['bindings']) == 60
snapshot_checks = []; assert len(browser['snapshotBindings']) == 13
for row in browser['snapshotBindings']:
    actual = checks([row['original'], row['frozen']]); require_exact(actual); snapshot_checks += actual
    assert (ROOT / row['original']['path']).read_bytes() == (ROOT / row['frozen']['path']).read_bytes()
assert browser['humans'] == 0 and browser['aiCountsAsHuman'] is False and browser['phaseStatus'] == 'partial' and browser['nextPhaseStarted'] is False
assert browser['sourceBoundL3']['publicationCertified'] is False and browser['sourceBoundL3']['importedAliasSaveReopenRetested'] is False
assert browser['authoredWorkflow']['nodes'] == 4 and browser['authoredWorkflow']['edges'] == 3
assert browser['authoredWorkflow']['modelExecuted'] is False and browser['authoredWorkflow']['trainingRun'] is False
assert browser['authoredWorkflow']['draftSaveReopenObserved'] is True
assert browser['sourceBoundL3']['excludedPreview']['path'] == 'l3-export-preview.svg'
service = read(WORK / 'browser-final-attempt-1/service-lifecycle.json')
assert service['toolSessionId'] == 36749 and service['processes'] == []
assert service['processInventoryScope'] == 'Current sandbox PID namespace; escalated host service is not visible here.'
assert check(service['managedProcessPoll'])['exact'] and service['state'] == 'running-at-readback'
freeze_failure = read(WORK / 'root/freeze-browser-attempt-1/failure.json')
assert freeze_failure['exitCode'] != 0
readonly_receipts = []
for folder in ['browser-source-readback-attempt-1', 'authored-browser-readback-attempt-1']:
    path = WORK / 'acceptance' / folder / 'final-readback.json'; receipt = read(path)
    observed = checks(receipt['bindings']); require_exact(observed)
    readonly_receipts.append({'receipt': binding(path), 'bindingCount': len(observed), 'allExact': True, 'checks': observed})
current_views = read(WORK / 'acceptance/current-attempt-1/report.json')
assert current_views['sourceBeforeAfterExact'] and current_views['sourceBefore'] == current_views['sourceAfter']
current_source_checks = checks(current_views['sourceAfter']); require_exact(current_source_checks)
assert len(current_views['records']) == 12
for row in current_views['records']:
    viewchecks = checks([row[key] for key in ['input', 'baselineScene', 'baselineSvg', 'scene', 'svg']]); require_exact(viewchecks)
assert sum(row['unchangedScene'] and row['unchangedSvg'] for row in current_views['records']) == 9
l3 = next(row for row in current_views['records'] if row['key'] == 'transformer-level3-paper-180')
assert l3['after']['distinct']['crossingPairs'] == 20 and l3['after']['distinct']['crossingPoints'] == 23 and l3['after']['distinct']['overlapPairs'] == 17
assert all(row['noNewSameTensorPairCrossings'] and row['immutableNodesPortsSourceAndSemantics'] and not row['newBodyBackplateHeaderHits'] for row in current_views['records'])
new('browser-and-independent-readbacks.json', {'browser': binding(browser_path), 'raw60Exact': True, 'snapshots13OriginalFrozenExact': True,
    'currentBundleAndProductBindingExact': True, 'humanCountZero': True, 'phasePartialNextPhaseFalse': True,
    'sourceBoundL3AndActualExportsScoped': True, 'authoredDraft4Nodes3EdgesPersistenceScoped': True, 'importedCanvasAliasNotCertified': True,
    'service': {'receipt': binding(WORK / 'browser-final-attempt-1/service-lifecycle.json'), 'toolSessionId': 36749, 'processesInSandbox': 0,
        'hostPidUnobservedExplicit': True, 'existingManagedPollExact': True, 'newAvailabilityProbeRun': False},
    'firstFreezeCollectorFailurePreserved': {'receipt': binding(WORK / 'root/freeze-browser-attempt-1/failure.json'), 'exitCode': freeze_failure['exitCode'],
        'notAProductFailure': True, 'cause': 'Collector wrongly assumed host service PID visible inside sandbox namespace.'},
    'readonlyReceipts': readonly_receipts, 'currentTwelveViewsExact': True, 'unchangedSixFrontiersAndThreeDetails': 9, 'changedViewsOnly44And55': 3,
    'l3DistinctAfter': l3['after']['distinct'], 'browserChecks': browser_checks, 'snapshotChecks': snapshot_checks})

docs_path = WORK / 'root/docs-finalize-attempt-1/receipt.json'; docs = read(docs_path)
assert digest(docs_path) == 'dc185b15bdb6c0a546d6cedcd3df7ba3a72c59ba48c0540bb5da9626373e430e'
assert docs['exitCode'] == 0 and all(docs['checks'].values())
assert docs['markdownFilesChecked'] == 26 and docs['localLinksChecked'] == 546 and docs['statusEvidenceReferences'] == 22
assert not docs['missingLinks'] and not docs['badStatusReferences']
doc_bindings = read(WORK / 'root/docs-finalize-attempt-1/document-bindings.json'); doc_checks = checks(doc_bindings['files']); require_exact(doc_checks); assert len(doc_checks) == 27
skill = read(WORK / 'root/docs-finalize-attempt-1/skill-validation.json'); assert skill['exitCode'] == 0 and skill['skillBeforeAfterExact']
assert skill['skillFilesBefore'] == skill['skillFilesAfter']; skill_checks = checks(skill['skillFilesAfter'] + [skill['validator'], skill['stdout'], skill['stderr']]); require_exact(skill_checks)
new('docs-and-skill-readback.json', {'docs': binding(docs_path), 'markdown26Links546CurrentRefs22ChecksAllPassed': True, 'docs27FrozenBindingsExact': True,
    'skillValidationExit0ExistingReceiptExact': True, 'skillBeforeAfterExact': True, 'oldRepeatEvidenceReadmeRestoredExact': True, 'docChecks': doc_checks, 'skillChecks': skill_checks})

after = binding(SEAL); assert before == after
summary = {'schemaVersion': 1, 'checkedAt': datetime.now(timezone.utc).isoformat(), 'scope': 'Supplemental independent audit after seal; no test/build/browser/model execution or old/seal/doc mutation.',
    'sealBefore': before, 'sealAfter': after, 'sealUnchanged': True, 'expectedSealBytesAndHashExact': True, 'all4233UniqueSealBindingsExact': True,
    'statusSchema9List22ReferencesExact': True, 'priorArchive1911FileSetAndBytesExact': True, 'priorOldSeal1896MappingsAnd14SupplementsExact': True,
    'immutableOldCurrentEvidenceAndResearch1775Exact': True, 'oldRepeatReadmeRestoredExact': True, 'oldTests26UnchangedOnlyAuthorizedRepeatChanged': True,
    'full179SourceAndLogsExact': True, 'buildIncludesStrictTypescriptSourceAndLogsExact': True, 'fullBuildFocusedSourceInputsIdentical': True,
    'focused26IsSeparateNotAddedTo179': True, 'standaloneNineActualChecksStillExact': True, 'standaloneSource209RunBeforeAfterExact': True,
    'standalone207InputsStillCurrentAndTwoLaterSkillDocChangesRecorded': True, 'standaloneCopiedFormalSourceSnapshotExact': True, 'standaloneDependencies654Symlinks5Exact': True,
    'browser60Raw13SnapshotCopiesExact': True, 'previousReadonlyReportsStillExact': True, 'currentIndependentTwelveViewsExact': True,
    'docs26Markdown546Links27FrozenBindingsAndSkillExit0Exact': True, 'humanAndResearchParticipantCountsZero': True,
    'researchCurrentPrepareAndVerifyFalse': True, 'oldResearchSlotsUnassignable': True, 'phasePartialNextPhaseFalse': True,
    'postSealAuditAbsentFromSealBindings': True, 'noSelfCircularSealOrStatusReference': True,
    'semanticReview': 'semantic-review.json is written separately by the independent semantic reviewer before final-receipt.json',
    'limitations': ['Hashes certify observed frozen bytes, not human acceptance or performance/publication quality.',
        'Current browser evidence is one L3 figure/export plus one authored four-node/three-edge workflow; no full new matrix, imported Canvas alias retest or human review.',
        'Declared/static shape and dtype facts are not model execution results.', 'Existing generic router is preserved; same-tensor per-pair protection is scoped to new family proposals. Different-tensor aggregate crossing counts may exchange individual pairs.',
        '80 is a per-refinement candidate limit, not a lifetime per-route limit across passes. Fixed work caps are not performance certification.',
        'Host service PID is invisible in sandbox; processes0 does not contradict the separately bound managed-session poll. No new availability or post-termination promise.',
        'Old archives/raw/failure attempts remain historical; failed rapid-batch4/1 cause is undetermined and preview close icon is excluded.',
        'Standalone209 inputs were exact within its recorded run. Two Skill reference documents changed later in the declared final docs freeze;207 inputs still match current, and copied original source snapshot remains exact.']}
new('readback-summary.json', summary)
print(json.dumps({'stage': 'complete', 'sealUnchanged': True, 'bindings': 4233, 'statusRefs': 22, 'archive': 1911, 'immutableOriginals': 1775, 'fullPassed': 179, 'buildPassed': True, 'standalone': 9, 'humans': 0}), flush=True)
