"""Independent readback only: never execute product, models, tests or seal writers."""
from pathlib import Path
from datetime import datetime, timezone
from urllib.parse import unquote
import hashlib
import json
import re

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
WORK = ROOT / 'docs/evidence/m4-authoring-interaction-work'
SEAL = ROOT / 'docs/evidence/m4-authoring-interaction-verification-sealed.json'
EXPECTED_SEAL_HASH = '332c05962c12a4d57f3d3cd1573178a19623c3498ef49123bb24746b9cc6af0d'
seal = json.loads(SEAL.read_text())
status_path = ROOT / 'docs/evidence/m4-human-review-handoff-status.json'
status = json.loads(status_path.read_text())
docs_receipt_path = WORK / 'doc-validation-attempt-2/receipt.json'
docs_receipt = json.loads(docs_receipt_path.read_text())
first_doc_receipt_path = WORK / 'doc-validation-attempt-1/receipt.json'
first_doc_receipt = json.loads(first_doc_receipt_path.read_text())
map1_path = WORK / 'before-implementation-attempt-1/manifest.json'
map2_path = WORK / 'before-current-doc-update-attempt-1/manifest.json'
map1 = json.loads(map1_path.read_text())
map2 = json.loads(map2_path.read_text())
old_map = {item['source']: item['copy'] for item in map1['records']}
old_map.update({item['source']['path']: item['copy']['path'] for item in map2['records']})
bk_path = ROOT / seal['priorBkSeal']['path']
cg_path = ROOT / seal['priorCgSeal']['path']
bk = json.loads(bk_path.read_text())
cg = json.loads(cg_path.read_text())


def resolve(path):
    candidate = Path(path)
    return candidate if candidate.is_absolute() else ROOT / candidate


def binding(path):
    data = path.read_bytes()
    return {'path': str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path),
            'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}


def exact(expected, actual):
    return expected['bytes'] == actual['bytes'] and expected['sha256'] == actual['sha256']


paths = {SEAL, status_path, docs_receipt_path, first_doc_receipt_path, map1_path, map2_path, bk_path, cg_path, Path(__file__)}
paths.update(resolve(item['path']) for item in seal['records'])
paths.update(resolve(old_map.get(item['path'], item['path'])) for item in bk['records'])
paths.update(resolve(item['path']) for item in cg['records'])
paths.update(resolve(item['path']) for item in docs_receipt['documents'])
paths.update(resolve(item['path']) for item in status['evidenceRefs'])
paths.update(resolve(docs_receipt['skillValidator'][key]['path']) for key in ['stdout','stderr','source','sourceCopy'])
before = [binding(path) for path in sorted(paths)]
before_lookup = {item['path']: item for item in before}


def current(path):
    return before_lookup[binding(resolve(path))['path']]


def readback(expected, target=None):
    actual = current(target or expected['path'])
    return {'expected': expected, 'actual': actual, 'exact': exact(expected, actual)}


current_records = [readback(item) for item in seal['records']]
bk_records = [readback(item, old_map.get(item['path'], item['path'])) for item in bk['records']]
cg_records = [readback(item) for item in cg['records']]
map1_copies = [readback({'path': item['copy'], 'bytes': item['bytes'], 'sha256': item['sha256']}) for item in map1['records']]
map2_copies = [readback(item['copy']) for item in map2['records']]
documents = [readback(item) for item in docs_receipt['documents']]
status_refs = [readback(item) for item in status['evidenceRefs']]
skill_refs = [readback(docs_receipt['skillValidator'][key]) for key in ['stdout','stderr','source','sourceCopy']]
links = []
for item in docs_receipt['documents']:
    path = resolve(item['path'])
    for match in re.finditer(r'\[[^\]\n]*\]\((<[^>]+>|[^\s)]+)(?:\s+"[^"]*")?\)', path.read_text()):
        raw = match.group(1).strip('<>')
        target = unquote(raw.split('#',1)[0])
        if not target or re.match(r'^[a-zA-Z][a-zA-Z0-9+.-]*:',target):
            continue
        resolved = Path(target) if target.startswith('/') else path.parent / target
        links.append({'document': item['path'], 'target': raw, 'exists': resolved.exists()})
selected_paths = set()
excluded_cache_paths = set()
for tree in seal['selectedTrees']:
    for path in (ROOT / tree).rglob('*'):
        if not path.is_file():
            continue
        if '__pycache__' in path.parts or path.suffix == '.pyc':
            excluded_cache_paths.add(path)
        else:
            selected_paths.add(path)
bound_paths = {resolve(item['path']) for item in seal['records']}
tree_files_unbound = sorted(selected_paths - bound_paths)
audit_paths = {
    'native': WORK / 'acceptance/native-audit-attempt-1/report.json',
    'source': WORK / 'acceptance/source-review-attempt-1/report.json',
    'checks': WORK / 'acceptance/final-check-readback-attempt-1/report.json',
    'pixels': WORK / 'visual-review-attempt-1/final-review-receipt.json',
    'artifacts': WORK / 'authoring-artifact-audit-attempt-1/attempt-2/receipt.json',
}
audits = {name: json.loads(path.read_text()) for name,path in audit_paths.items()}
native = audits['native']
pixels = audits['pixels']
artifact = audits['artifacts']
first_bad = [item for item in first_doc_receipt['priorBkResolved'] if not item['exact']]
lineage_docs_repair = {'firstAttempt': binding(first_doc_receipt_path),
    'firstAttemptUnresolvedBindings': first_bad,
    'firstAttemptKeptUnchanged': first_doc_receipt_path in bound_paths,
    'currentMap1Count': len(map1['records']), 'currentMap2Count': len(map2['records']),
    'combinedUniqueSourcePathCount': len(old_map),
    'resolvedFinalBkCount': len(bk_records)}
boundary_checks = {
    'M4PartialAndM5NotStarted': seal['milestones'] == {'M4':'partial','M5':'not_started','humans':0} and status['phaseStatus'] == 'partial' and status['nextPhaseStarted'] is False,
    'humanAcceptanceFalseAndResearch0': status['humanAcceptanceCertified'] is False and status['humanResearch'] == {'preparedForCurrentBuild':False,'verifiedForCurrentBuild':False,'assigned':0,'collected':0,'researchers':0,'aiCountedAsHuman':False},
    'threeAiRolesExplicitlyNonHuman': seal['aiReview']['reviewerRoleCount'] == 3 and seal['aiReview']['rolesAreHumanParticipants'] is False and status['aiReview'] == seal['aiReview'],
    'native46ScopedPass': native['pass'] is True and len(native['checks']) == 46 and sum(native['checks'].values()) == 46 and seal['interaction']['nativeScopedChecksPassed'] == 46,
    'native195Endpoints1424VisibleCenters11ObserverFailures': native['counts']['endpointPairs'] == 195 and native['counts']['completeVisiblePublicCenters'] == native['counts']['completeVisibleIdentityMatches'] == 1424 and native['counts']['knownObserverFailureSnapshots'] == 11,
    'mergeAestheticsRemainFalseAt614220': native['aestheticFindings']['strictCrossingFree'] is False and seal['interaction']['strictCrossingFree'] is False and seal['interaction']['strictCrossingPoints'] == [[614,220]] and status['authoringInteraction']['strictCrossingFree'] is False,
    'sixRepeatedCrossingObservationsRetained': len(native['aestheticFindings']['differentProducerStrictCrossingObservations']) == 6 and seal['interaction']['repeatCrossingObservations'] == 6,
    'panPixelsAndFullAestheticsUncertified': 'dedicated four-pan pixel validation' in seal['noClaims'] and seal['interaction']['fullAestheticsCertified'] is False and seal['interaction']['panInitialDownTimedOut'] is True and seal['interaction']['panRetryRestoredCamera'] is True,
    'pendingAndMerge100PixelsRemainUncertified': seal['interaction']['pendingPixelFooterCertified'] is False and seal['interaction']['merge100PercentPixelsCertified'] is False and pixels['pairAgreementDoesNotOverrideRasterFailures'] is True,
    'all14PixelsReviewedWithOpenPresentationGates': pixels['all14NativeJpegsViewed'] is True and pixels['personallyViewedCount'] == 20 and pixels['humanParticipants'] == 0 and len(pixels['remainingConcerns']) == 6,
    'artifactSixBoundedCasesAndNoRuntimeHumanPublicationCertification': artifact['passedCases'] == artifact['allCases'] == 6 and artifact['humanParticipantsCertified'] == 0 and artifact['runtimeTensorVerified'] is False and artifact['allCatalogModulesCertified'] is False and artifact['publicationSizeCertified'] is False and artifact['M4CompleteCertified'] is False,
    'module17Preset3DoesNotClaimPerModuleRuntime': seal['authoring']['baseModules'] == 17 and seal['authoring']['transparentStartingGraphs'] == 3 and seal['authoring']['catalogIncludes'] == 'SiLU, not Softmax; Attention/LSTM unsupported' and seal['authoring']['newPerModuleBrowserCertification'] is False and seal['authoring']['newRuntimeCertification'] is False and seal['authoring']['humanNoviceCertification'] is False,
    'test28And264CountsSeparate': seal['checks']['focusedSeparateRun']['passed'] == 28 and seal['checks']['studio']['passed'] == 264 and seal['checks']['suiteCountsCombined'] is False and seal['checks']['currentFullStandaloneReleaseCertified'] is False,
    'noPrototypeRuntimeFallbackReuseOrNewModelExecution': seal['implementationDirection']['failedPrototypeRuntimeUsed'] is False and seal['implementationDirection']['failedPrototypeFallback'] is False and seal['implementationDirection']['certifiedPrototypeReuseCandidates'] == 0 and seal['implementationDirection']['modelExecutionThisRound'] == 'not_run',
    'statusCopiesExactSealSections': all(status[key] == seal[target] for key,target in [('tests','checks'),('authoring','authoring'),('authoringInteraction','interaction'),('aiReview','aiReview'),('implementationDirection','implementationDirection'),('openItems','openItems'),('preservedFailures','preservedFailures')]),
}
checks = {
    'sealExpectedBytesAndHash': binding(SEAL)['bytes'] == 254770 and binding(SEAL)['sha256'] == EXPECTED_SEAL_HASH,
    'current1071BindingsAllExact': len(current_records) == seal['boundFileCount'] == 1071 and all(item['exact'] for item in current_records),
    'selectedTreesNoUnexpectedUnboundFilesUnderRecordedCacheExclusion': not tree_files_unbound,
    'priorBk1117ResolvedExact': len(bk_records) == seal['priorBkBindingsResolvedExact'] == 1117 and all(item['exact'] for item in bk_records),
    'priorCg981OriginalExact': len(cg_records) == seal['priorCgOriginalBindingsExact'] == 981 and all(item['exact'] for item in cg_records),
    'oldSealsExact': readback(seal['priorBkSeal'])['exact'] and readback(seal['priorCgSeal'])['exact'],
    'both226And13MapsCopiesExact': len(map1_copies) == 226 and len(map2_copies) == 13 and all(item['exact'] for item in map1_copies+map2_copies),
    'originalTwoBindingDocFailureRetained': len(first_bad) == 2 and lineage_docs_repair['firstAttemptKeptUnchanged'],
    'documents15ExactAndUnchangedAgainstReceipt': len(documents) == 15 and all(item['exact'] for item in documents) and docs_receipt['documentInputsUnchanged'] and docs_receipt['documents'] == docs_receipt['documentsAfter'],
    'links456ExistAndMatchRecordedInventory': len(links) == docs_receipt['localLinksCount'] == 456 and links == docs_receipt['inlineLocalLinks'] and all(item['exists'] for item in links),
    'SkillExit0AndOriginalCopyLogsExact': docs_receipt['skillValidator']['exitCode'] == 0 and all(item['exact'] for item in skill_refs),
    'schema12Status29RefsExact': status['schemaVersion'] == 12 and len(status_refs) == 29 and all(item['exact'] for item in status_refs),
    'documentationReceiptSealBindingExact': readback(seal['documentationReceipt'])['exact'],
    'allBoundaryChecksPass': all(boundary_checks.values()),
}
after = [binding(path) for path in sorted(paths)]
checks['allInputsUnchangedDuringReadback'] = before == after
checks['current1071BindingsRemainExactAfterReadback'] = all(exact(item, binding(resolve(item['path']))) for item in seal['records'])
report = {'protocol': 'archcanvas-authoring-interaction-independent-final-seal-readback/1',
          'reviewedAt': datetime.now(timezone.utc).isoformat(), 'pass': all(checks.values()), 'checks': checks,
          'boundaryChecks': boundary_checks,
          'counts': {'distinctInputs':len(before),'currentSealBindings':len(current_records),'priorBkBindingsResolved':len(bk_records),'priorCgOriginalBindings':len(cg_records),'map1Copies':len(map1_copies),'map2Copies':len(map2_copies),'combinedUniqueMappedSources':len(old_map),'documents':len(documents),'localLinks':len(links),'statusRefs':len(status_refs),'excludedGeneratedCaches':len(excluded_cache_paths)},
          'sealBefore': binding(SEAL), 'sealAfter': binding(SEAL),
          'inputsBefore': before, 'inputsAfter': after,
          'currentSealReadback': current_records, 'priorBkResolvedReadback': bk_records,
          'priorCgOriginalReadback': cg_records, 'map1CopyReadback':map1_copies,'map2CopyReadback':map2_copies,
          'documentsReadback':documents,'linksReadback':links,'statusReferencesReadback':status_refs,'skillReceiptReadback':skill_refs,
          'oldDocumentationMapRepair':lineage_docs_repair,
          'auditBindings':{name:binding(path) for name,path in audit_paths.items()},
          'selectedTreeUnboundPaths':[str(path.relative_to(ROOT)) for path in tree_files_unbound],
          'cacheExclusionBasis':'Explicit exclusions in bound seal_current_attempt_2.py: __pycache__ and .pyc. Their count is recorded; they are not silently added to the seal.',
          'excludedGeneratedCachePaths':[str(path.relative_to(ROOT)) for path in sorted(excluded_cache_paths)],
          'limits':['File bindings certify exact bytes, not all claims in every retained historical artifact.',
                    'Skill exit0 is read from its exact prior receipt/logs; the validator was not rerun.',
                    'Local links check target existence, not heading-anchor resolution or semantic document content.',
                    'Native46 scoped pass coexists with merge strict-crossing failure and unproven pan/pending/merge100 raster presentation.',
                    'Three AI roles remain zero actual researchers; M4 partial and M5 not started.',
                    'The immutable seal records final readback as pending. This separate outside-tree report completes the readback without rewriting that historical field.'],
          'productsTestsOrBuildRerun':False,'modelsExecuted':False,'dependenciesInstalled':False,'sealedFilesModified':False,
          'humanParticipants':0,'M4':'partial','M5':'not_started'}
target = OUT / 'report.json'
with target.open('x') as stream:
    json.dump(report,stream,ensure_ascii=False,indent=2)
    stream.write('\n')
print(json.dumps({'report':binding(target),'pass':report['pass'],'checks':checks,'boundaryChecks':boundary_checks,'counts':report['counts'],'seal':binding(SEAL)},ensure_ascii=False))
