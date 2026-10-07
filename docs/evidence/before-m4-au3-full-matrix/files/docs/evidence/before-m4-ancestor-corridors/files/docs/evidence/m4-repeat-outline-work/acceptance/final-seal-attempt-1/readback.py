"""Post-seal read-only binding/receipt audit. No tests or product execution."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib, json, re

ROOT = Path(__file__).resolve().parents[5]
OUT = Path(__file__).resolve().parent
WORK = ROOT / 'docs/evidence/m4-repeat-outline-work'
SEAL = ROOT / 'docs/evidence/m4-repeat-outline-current-verification-sealed.json'
EXPECTED_SEAL_HASH = '21086a9a305544d303bb5505a81b19ff070f08bceb727a7d93bb871f0f17a96e'

def sha_file(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''): h.update(block)
    return h.hexdigest()
def binding(path): return {'path': str(path.relative_to(ROOT)), 'bytes': path.stat().st_size, 'sha256': sha_file(path)}
def read(path): return json.loads(path.read_text())
def new(name, value):
    with (OUT / name).open('x') as stream: json.dump(value, stream, ensure_ascii=False, indent=2); stream.write('\n')
def check(record, path_key='path'):
    path = ROOT / record[path_key]
    try:
        got = binding(path)
        exact = got['sha256'] == record['sha256'] and ('bytes' not in record or got['bytes'] == record['bytes'])
        return {**record, 'actual': got, 'exact': exact}
    except (OSError, ValueError) as exc: return {**record, 'exact': False, 'error': str(exc)}
def parallel_check(records, key='path'):
    with ThreadPoolExecutor(max_workers=6) as pool: return list(pool.map(lambda record: check(record, key), records))
def all_exact(records): return all(x['exact'] for x in records)

before = binding(SEAL)
seal = read(SEAL)
new('seal-input-before.json', {'scope': 'Supplemental final independent readback created after the seal. This directory is deliberately absent from the seal; no self-cycle or new seal.', 'at': datetime.now(timezone.utc).isoformat(), 'binding': before})
bound = parallel_check(seal['bindings'])
new('seal-bindings-readback.json', {'declared': seal['bindingCount'], 'actualRecordCount': len(bound), 'uniquePaths': len({x['path'] for x in bound}), 'allExact': all_exact(bound), 'bindings': bound})
print(json.dumps({'stage': 'new-seal', 'count': len(bound), 'allExact': all_exact(bound)}), flush=True)

status = read(ROOT / seal['currentStatus']['path'])
status_refs = parallel_check(status['evidenceRefs'])
new('status-references-readback.json', {'schemaVersion': status['schemaVersion'], 'evidenceRefsType': 'list', 'count': len(status_refs), 'allExact': all_exact(status_refs), 'references': status_refs})
archive_path = ROOT / seal['priorArchive']['path']; archive = read(archive_path)
archived = parallel_check(archive['bindings'], 'archivePath')
old_seal_path = ROOT / archive['previousSeal']; old_seal = read(old_seal_path)
archive_lookup = {x['path']: x for x in archive['bindings']}
archive_old_mapping = []
for old in old_seal['bindings']:
    item = archive_lookup.get(old['path'])
    archive_old_mapping.append({'path': old['path'], 'exactOldSealTuple': item is not None and all(item[k] == old[k] for k in ('path', 'bytes', 'sha256'))})
archived_old_seal = archive_lookup[archive['previousSeal']]
old_raw_prefixes = ['docs/evidence/m4-chs-browser-matrix-work/raw/', 'docs/evidence/browser-visual-matrix-chs-current/']
old_raw_records = [x for x in old_seal['bindings'] if any(x['path'].startswith(prefix) for prefix in old_raw_prefixes)]
old_raw = parallel_check(old_raw_records)
actual_old_raw = {str(p.relative_to(ROOT)) for prefix in old_raw_prefixes for p in (ROOT / prefix).rglob('*') if p.is_file()}
actual_archived = {str(p.relative_to(ROOT)) for p in (archive_path.parent / 'files').rglob('*') if p.is_file()}
archive_report = {'manifest': binding(archive_path), 'originalSeal': binding(old_seal_path), 'expectedOldSealHashExact': sha_file(old_seal_path) == archive['previousSealSha256'] == '332f9b84a085efa95ef0cb09fdfd152bbbef072fc97c5268f355191a597a4581', 'archivedBindingCount': len(archived), 'all2916ArchivedExact': len(archived) == archive['bindingCount'] == 2916 and all_exact(archived), 'archiveFileSetExact': actual_archived == {x['archivePath'] for x in archive['bindings']}, 'oldSealMapping2915Exact': len(archive_old_mapping) == 2915 and all(x['exactOldSealTuple'] for x in archive_old_mapping), 'archiveExtraOnlyOriginalSeal': set(archive_lookup) - {x['path'] for x in old_seal['bindings']} == {archive['previousSeal']}, 'archivedOriginalSealTupleExact': archived_old_seal['sha256'] == archive['previousSealSha256'] and archived_old_seal['bytes'] == old_seal_path.stat().st_size, 'currentOld806Exact': len(old_raw) == 806 and all_exact(old_raw), 'currentOld806FileSetExact': actual_old_raw == {x['path'] for x in old_raw_records}, 'currentOldCountsByPrefix': {prefix: sum(x['path'].startswith(prefix) for x in old_raw) for prefix in old_raw_prefixes}, 'archiveBindings': archived, 'oldSealMappings': archive_old_mapping, 'currentOldBindings': old_raw}
new('prior-archive-and-old-matrix-readback.json', archive_report)
print(json.dumps({'stage': 'historical', 'archived': len(archived), 'archiveExact': archive_report['all2916ArchivedExact'], 'rawCollected': len(old_raw), 'oldExact': archive_report['currentOld806Exact']}), flush=True)

full = read(WORK / 'root/full-studio-attempt-2/receipt.json')
build = read(WORK / 'root/build-attempt-1/receipt.json')
strict = read(WORK / 'root/strict-ts-attempt-1/receipt.json')
adapter = read(WORK / 'oracle/historical-adapter-final.json')
oracle = read(WORK / 'oracle/summary.json')
standalone = read(WORK / 'acceptance/standalone-attempt-1/retry-1/process.json')
full_checks = parallel_check(full['bindings'] + full['logs'])
build_checks = parallel_check(build['sourceBindings'] + build['buildFiles'])
strict_checks = parallel_check(strict['adapterTestBindings'])
adapter_before = parallel_check(adapter['bindingsBefore']); adapter_after = parallel_check(adapter['bindingsAfter'])
stdout = (WORK / 'root/full-studio-attempt-2/stdout.log').read_text()
full_counts = {name: int(re.search(r'\b' + name + r' (\d+)\s*$', stdout, re.MULTILINE).group(1)) for name in ('tests', 'pass', 'fail', 'skipped', 'cancelled')}
full_map = {x['path']: x for x in full['bindings']}
build_full_source_same = all(x['path'] in full_map and all(x[k] == full_map[x['path']][k] for k in ('bytes', 'sha256')) for x in build['sourceBindings'])
strict_adapter_same = all(any(x['path'] == a['path'] and x['sha256'] == a['sha256'] for a in adapter['bindingsBefore']) for x in strict['adapterTestBindings'])
full_adapter_same = full_map['studio/tests/routing-readability-independent.test.ts']['sha256'] == next(x['sha256'] for x in strict['adapterTestBindings'] if x['path'] == 'studio/tests/routing-readability-independent.test.ts')
js = next(x for x in build['buildFiles'] if x['path'].endswith('/' + seal['productionBuild']))
standalone_process = {'exitCode': standalone['exitCode'], 'checkCount': standalone['checkCount'], 'allChecksPassed': standalone['allChecksPassed'], 'checks': standalone['checks'], 'scope': standalone['scope'], 'modelExecution': standalone['modelExecution'], 'reportCopyExactNow': sha_file(Path(standalone['reportCopy']['path'])) == standalone['reportCopy']['sha256'], 'standaloneIsolatedCopyExistsNow': Path(standalone['standaloneCopy']).is_dir()}
oracle_receipts = {name: sha_file(WORK / 'oracle' / name) == digest for name, digest in oracle['receiptHashes'].items()}
failure = read(WORK / 'root/seal-attempt-1/failure.json')
receipts = {'fullStudio': {'receipt': binding(WORK / 'root/full-studio-attempt-2/receipt.json'), 'exitCode': full['exitCode'], 'sourceBeforeAfterExact': full['sourceBeforeAfterExact'], 'countsParsedActualStdout': full_counts, 'bindingCount': len(full['bindings']), 'allCurrentSourceConfigTestsAndLogsExact': all_exact(full_checks), 'checks': full_checks}, 'build': {'receipt': binding(WORK / 'root/build-attempt-1/receipt.json'), 'exitCode': build['exitCode'], 'sourceBeforeAfterExact': build['sourceBeforeAfterExact'], 'allSourceAndDistExact': all_exact(build_checks), 'currentJsExactSealAndStatus': js['sha256'] == seal['productionJsSha256'] == status['productionJsSha256'] == sha_file(ROOT / js['path']), 'sourceBindingsSameAsFull170SourceRun': build_full_source_same, 'checks': build_checks}, 'strict': {'receipt': binding(WORK / 'root/strict-ts-attempt-1/receipt.json'), 'exitCode': strict['exitCode'], 'afterExact': strict['afterExact'], 'allCurrentAdapterTestBindingsExact': all_exact(strict_checks), 'sameAsFinalAdapterReceipt': strict_adapter_same, 'sameTestBindingAsFull170Run': full_adapter_same, 'checks': strict_checks}, 'historicalFinalAdapter': {'receipt': binding(WORK / 'oracle/historical-adapter-final.json'), 'exitCode': adapter['exitCode'], 'tests': adapter['tests'], 'passed': adapter['passed'], 'failed': adapter['failed'], 'sourceBeforeAfterEqual': adapter['bindingsBefore'] == adapter['bindingsAfter'], 'currentBeforeAfterAllExact': all_exact(adapter_before + adapter_after), 'stdoutExact': sha_file(WORK / 'oracle/historical-adapter-final.stdout.txt') == adapter['stdoutSha256'], 'stderrExact': sha_file(WORK / 'oracle/historical-adapter-final.stderr.txt') == adapter['stderrSha256'], 'oldRawUnmodifiedDeclared': adapter['historicalOracleOrRawModified'] is False, 'preservedExistingConflicts': adapter['preservedExistingConflicts']}, 'outlineOracle': {'currentTargeted': oracle['currentTargeted'], 'sealedChSNegativeTarget': oracle['sealedChSRegressionControl'], 'receiptHashesExact': oracle_receipts, 'allExact': all(oracle_receipts.values()), 'standaloneDistinctFromFullSuite': True}, 'standalone': standalone_process, 'firstSealFailurePreserved': {'receipt': binding(WORK / 'root/seal-attempt-1/failure.json'), 'content': failure, 'failedScriptHashExact': sha_file(WORK / 'root/seal-attempt-1/failed-script.py') == failure['failedScriptSha256'], 'failureBeforeSuccessfulSealChronology': failure['at'] < seal['sealedAt'], 'failedOutputSealNotCreatedRecorded': failure['outputSealCreated'] is False}}
new('critical-receipts-readback.json', receipts)

package = ROOT / status['research']['package']; manifest = read(package / 'manifest.json')
package_expected = read(WORK / 'research/attempt-1/preparation-verification.json')['packageBindings']
package_checks = parallel_check(package_expected)
implementation_checks = parallel_check(manifest['implementationFiles'])
baseline_checks = parallel_check([{**x, 'path': str((package / x['path']).relative_to(ROOT))} for x in manifest['baseline']['files']])
doc = read(package / 'baseline/canvas.json'); slots = []
for slot in manifest['slots']:
    sd = package / 'slots' / slot['slotId']; env = read(package / slot['baselineEnvelope']['path']); review = read(sd / 'review-template.json')
    slot_files = {str(x.relative_to(package)) for x in sd.rglob('*') if x.is_file()}
    pristine = review['participantCode'] is None and review['reviewer'] is None and review['status'] == 'pending-independent-review' and all(task == {'task': i, 'status': 'pending', 'evidencePaths': [], 'notes': ''} for i, task in enumerate(review['tasks'], 1)) and len(review['tasks']) == 5
    slots.append({'slotId': slot['slotId'], 'port': slot['port'], 'unassigned': slot['assignment'] == 'unassigned' and slot['participantCode'] is None, 'canvasDeepEqualBaseline': env['document'] == doc, 'storageRev1VisualRev0': env['revision'] == 1 and env['document']['revision'] == 0, 'blankReviewTemplate': pristine, 'noAssignmentOrCollection': not (sd / 'assignment.json').exists() and not (sd / 'collected').exists(), 'fileSetPristine': slot_files == {slot['baselineEnvelope']['path'], f"slots/{slot['slotId']}/review-template.json"}, 'incomingAndExportsEmpty': not any((sd / 'incoming').iterdir()) and not any((sd / 'workspace/exports').iterdir())})
research = {'manifest': binding(package / 'manifest.json'), 'implementationCount': len(implementation_checks), 'all73Exact': len(implementation_checks) == 73 and all_exact(implementation_checks), 'baselineCount': len(baseline_checks), 'all4Exact': len(baseline_checks) == 4 and all_exact(baseline_checks), 'packageCount': len(package_checks), 'all17Exact': len(package_checks) == 17 and all_exact(package_checks), 'packageFileSetExact': {str(x.relative_to(ROOT)) for x in package.rglob('*') if x.is_file()} == {x['path'] for x in package_expected}, 'slots': slots, 'fivePristineUnassigned': len(slots) == 5 and all(all(v for k, v in x.items() if k not in ('slotId', 'port')) for x in slots), 'ports': [x['port'] for x in slots], 'portAvailabilityChecked': False, 'researcherCount': manifest['researcherCount'], 'researchGate': manifest['researchGate'], 'statusHumanCountZero': status['research']['assignedParticipants'] == status['research']['collectedParticipants'] == status['research']['researcherCount'] == 0, 'humanSuccessCertified': False, 'sourceIrCanvasStillBoundToPriorIndependentReview': check(next(x for x in seal['bindings'] if x['path'].endswith('/acceptance/research-attempt-1/review.json')))['exact'], 'checks': implementation_checks + baseline_checks + package_checks}
new('research-package-readback.json', research)

after = binding(SEAL)
summary = {'schemaVersion': 1, 'at': datetime.now(timezone.utc).isoformat(), 'scope': 'Single final readback after final seal; supplemental report is outside the sealed set. No tests, builds, browser actions, model execution, assignments, collection, archive/seal/doc mutation or re-sealing.', 'sealBefore': before, 'sealAfter': after, 'sealUnchanged': before == after, 'expectedSealBytesAndHashExact': before['bytes'] == 430406 and before['sha256'] == EXPECTED_SEAL_HASH, 'all1896SealBindingsExact': len(bound) == seal['bindingCount'] == 1896 and all_exact(bound), 'sealPathsUnique': len({x['path'] for x in bound}) == 1896, 'statusBoundExact': check(seal['currentStatus'])['exact'], 'statusSchema8And27ReferencesExact': status['schemaVersion'] == 8 and len(status_refs) == 27 and all_exact(status_refs), 'priorArchive2916Exact': archive_report['all2916ArchivedExact'], 'archiveFileSetExact': archive_report['archiveFileSetExact'], 'oldSeal2915MappingExact': archive_report['oldSealMapping2915Exact'], 'old806CurrentExact': archive_report['currentOld806Exact'], 'old806FileSetExact': archive_report['currentOld806FileSetExact'], 'full170CurrentSourcesAndLogsExact': full['exitCode'] == 0 and full_counts == {'tests': 170, 'pass': 170, 'fail': 0, 'skipped': 0, 'cancelled': 0} and all_exact(full_checks), 'full170SameProductSourcesAsBuild': build_full_source_same, 'finalAdapterStrictAndFull170Same': strict_adapter_same and full_adapter_same and strict['exitCode'] == adapter['exitCode'] == 0 and all_exact(strict_checks + adapter_before + adapter_after), 'productionBuildShaMatchesSealStatusAndCurrentDist': receipts['build']['currentJsExactSealAndStatus'] and all_exact(build_checks), 'standaloneNineActualReportStillExact': standalone['exitCode'] == 0 and standalone['checkCount'] == 9 and standalone['allChecksPassed'] and standalone_process['reportCopyExactNow'], 'research73And4And17AndFivePristineExact': research['all73Exact'] and research['all4Exact'] and research['all17Exact'] and research['fivePristineUnassigned'] and research['packageFileSetExact'], 'humanCountStillZero': research['statusHumanCountZero'] and seal['verification']['humans'] == 0 and status['humanAcceptanceCertified'] is False, 'firstFailedSealAttemptPreserved': receipts['firstSealFailurePreserved'], 'postSealReportsAbsentFromBindings': not any('/acceptance/final-seal-attempt-1/' in x['path'] for x in seal['bindings']), 'noSelfCircularSealBinding': not any(x['path'] == str(SEAL.relative_to(ROOT)) for x in seal['bindings']) and all(x['path'] != str(SEAL.relative_to(ROOT)) for x in status['evidenceRefs']), 'semanticScopeReview': 'semantic-child/review.json is a separately written read-only semantic consistency review; no new tests.', 'limits': ['Hashes certify frozen bytes, not human acceptance or native performance/publication quality.', 'Old39 ChS remains historical/stale for BG; four representatives are not a full fresh matrix.', '229 route and458 endpoint observations include repeated artifacts; up3body segment hits/2pairs remain real and explicitly blocked, despite zero Repeat/backplate/endpoint failures.', 'Stored source-bound canonical/static facts remain unchanged; tests and static preparation do not establish model execution. Current human/research participant counts remain0.', 'No test suite rerun. Final conclusion is based on actual existing source/build/test receipts and current hashes.']}
new('readback-summary.json', summary)
print(json.dumps({k: v for k, v in summary.items() if isinstance(v, bool)}, ensure_ascii=False), flush=True)
