"""Final independent readback: saved bytes and named narrative boundaries only."""
from pathlib import Path
from datetime import datetime, timezone
from urllib.parse import unquote
import hashlib
import json
import re

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
WORK = ROOT / 'docs/evidence/m4-draft-merge-routing-work'
SEAL = ROOT / 'docs/evidence/m4-draft-merge-routing-verification-sealed-attempt-2.json'
EXPECTED_HASH = '45ce5cbff406d115035469ea7df4b27962b894ae612d5dc168743f39473a867b'
seal = json.loads(SEAL.read_text())
status_path = ROOT / seal['currentStatus']['path']
status = json.loads(status_path.read_text())
consistency_path = ROOT / seal['finalConsistencyReceipt']['path']
consistency = json.loads(consistency_path.read_text())
prior_path = ROOT / seal['preservedIntermediateSeal']['path']
prior = json.loads(prior_path.read_text())
before_manifest_path = ROOT / consistency['beforeManifest']['path']
before_manifest = json.loads(before_manifest_path.read_text())
archive_map = {item['path']:item['resolvedPath'] for item in seal['priorSealArchiveResolution']}
doc_paths = [ROOT/item['path'] for item in consistency['currentDocuments']]
check_paths = [ROOT/status['tests'][key]['receipt'] for key in ['focusedSeparateRun','studio']]
check_paths.append(ROOT/status['tests']['buildReceipt'])
check_data = [json.loads(path.read_text()) for path in check_paths]


def resolve(value):
    path = Path(value)
    return path if path.is_absolute() else ROOT/path


def binding(path):
    data = path.read_bytes()
    return {'path':str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path),
            'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}


def exact(expected, actual):
    return expected['bytes']==actual['bytes'] and expected['sha256']==actual['sha256']


paths = {SEAL,status_path,consistency_path,prior_path,before_manifest_path,Path(__file__),OUT/'before-archive-readback.json'}
paths.update(resolve(item['path']) for item in seal['records'])
paths.update(resolve(archive_map.get(item['path'],item['path'])) for item in prior['records'])
paths.update(resolve(item['path']) for item in status['evidenceRefs'])
paths.update(resolve(item['archive']) for item in before_manifest['records'])
paths.update(doc_paths)
paths.update(check_paths)
for receipt in check_data:
    for category in ['inputsBefore','inputsAfter','infrastructure','logs','builtFiles']:
        paths.update(resolve(item['path']) for item in receipt.get(category,[]))
before = [binding(path) for path in sorted(paths)]
lookup = {item['path']:item for item in before}


def readback(expected,target=None):
    actual = lookup[binding(resolve(target or expected['path']))['path']]
    return {'expected':expected,'actual':actual,'exact':exact(expected,actual)}


new_records = [readback(item) for item in seal['records']]
prior_records = [readback(item,archive_map.get(item['path'],item['path'])) for item in prior['records']]
references = [readback(item) for item in status['evidenceRefs']]
archive_records = [readback({'path':item['path'],'bytes':item['bytes'],'sha256':item['sha256']},item['archive']) for item in before_manifest['records']]
document_readback = [readback(item) for item in consistency['currentDocuments']]
links = []
for path in doc_paths:
    for match in re.finditer(r'\[[^\]\n]*\]\((<[^>]+>|[^\s)]+)(?:\s+"[^"]*")?\)',path.read_text()):
        raw=match.group(1).strip('<>');target=unquote(raw.split('#',1)[0])
        if not target or re.match(r'^[a-zA-Z][a-zA-Z0-9+.-]*:',target):
            continue
        destination=Path(target) if target.startswith('/') else path.parent/target
        links.append({'doc':str(path.relative_to(ROOT)),'target':raw,'exists':destination.exists()})
checks_readback = []
for path,receipt in zip(check_paths,check_data):
    fields = {category:[readback(item) for item in receipt.get(category,[])] for category in ['inputsBefore','inputsAfter','infrastructure','logs','builtFiles']}
    stdout=(path.parent/'stdout.txt').read_text()
    counts = {key:int(re.search(r'^. '+key+r' (\d+)$',stdout,re.MULTILINE).group(1)) for key in ['tests','pass','fail']} if receipt['kind']!='build' else None
    checks_readback.append({'receipt':binding(path),'kind':receipt['kind'],'exitCode':receipt['exitCode'],
        'sourceBeforeAfterExact':receipt['sourceBeforeAfterExact'],'counts':counts,
        'declaredReadback':fields,'allRecordedBytesExact':all(item['exact'] for values in fields.values() for item in values)})
completion = (ROOT/'docs/m4-completion.md').read_text()
current_lead = completion.split('历史版本说明：',1)[0]
current_table = completion.split('## 当前 M4 状态',1)[1].split('## 本轮草稿合并路由跟进',1)[0]
route_doc = (ROOT/'docs/m4-draft-merge-routing.md').read_text()
pixel_path = WORK/'visual-review-attempt-1/final-review-receipt.json'
pixels = json.loads(pixel_path.read_text())
boundary = {
    'currentBuildBsa39Focused275SuiteWithSeparatedCounts':seal['currentBuild']==status['productionBuild']=='index-BSA5RjBV.js' and status['tests']['focusedSeparateRun']['passed']==39 and status['tests']['studio']['passed']==275 and status['tests']['focusedIsSuiteSubset'] is True and status['tests']['suiteCountsCombined'] is False,
    'currentLeadAndTableUseBsa39And275':all(token in current_lead for token in ['index-BSA5RjBV.js','专项39/39','Studio275/275','只按旧ye构建范围']) and '专项39/39、Studio275/275' in current_table,
    'standaloneSchema14WithoutInheritedOldStageObjects':status['schemaVersion']==14 and all(key not in status for key in ['authoringInteraction','priorCollapseStage','priorRoleStage','widthOverride']) and 'Neither is current BSA5 certification' in status['historicalScope'],
    'oldYeActionsRemainHistorical': 'retained at the ye build stage; not recertified' in status['authoring']['priorPresetUiEvidence'] and '未为这张合流图打开新managed或导出论文图' in current_lead,
    'currentMergeStaticOnlyNoManagedOrExport':status['authoring']['currentMergeManagedModelOpened'] is False and status['authoring']['currentMergePublicationExported'] is False and '未为本次合流图打开新managed model、执行模型或导出论文图' in route_doc,
    'fiveAiRolesRootOperatorAreNotHumans':status['aiReview']['reviewerRoleCount']==len(status['aiReview']['roles'])==5 and status['aiReview']['rolesAreHumanParticipants'] is False and 'root' in status['aiReview']['nativeOperator'],
    'zeroActualResearchAndM4PartialM5NotStarted':seal['M4']=='partial' and seal['M5']=='not_started' and seal['humanParticipants']==0 and status['nextPhaseStarted'] is False and status['humanAcceptanceCertified'] is False and all(status['humanResearch'][key]==0 for key in ['assigned','collected','researchers']) and status['humanResearch']['aiCountedAsHuman'] is False,
    '100PercentRasterMismatchAndHorizontalPanLimitsRemainUncertified':status['browser']['100PercentRasterPairCertified'] is False and status['browser']['wholeNetworkHorizontalPanPixelsCertified'] is False and seal['browser']['100PercentRasterPairCertified'] is False and seal['browser']['wholeNetworkHorizontalPanPixelsCertified'] is False and any('pixels56/DOM100' in item for item in status['preservedCurrentFailures']),
    'longRouteAndGlobalAestheticsStillOpen':status['browser']['fullAestheticsCertified'] is False and seal['browser']['fullAestheticsCertified'] is False and any('long exterior A→Concat.b' in item for item in status['openItems']) and 'A→Concat.b 多弯长绕行仍是审美问题' in route_doc,
    'smallDraftScopeNoSharedCanvasRouterClaim':status['routeBounds']['sharedSceneCanvasExportRouterChangedThisRound'] is False and status['routeBounds']['arbitraryCrossingFreeOrMinimumBendGuaranteed'] is False and '未改共享Scene/Canvas/export路由' in route_doc and '不宣称位级端点相等' in route_doc,
    '17Kinds3StartersNotPerModuleRuntimeOrHumanCertification':status['authoring']['baseModules']==17 and status['authoring']['transparentStartingGraphs']==3 and status['authoring']['currentPerModuleBrowserCertification'] is False and status['authoring']['runtimeOrTrainingCertification'] is False and status['authoring']['humanNoviceCertification'] is False,
    'performanceFullReleaseAndPhysicalPublicationNotRaised':status['performance']['currentStudioAbMeasured'] is False and status['performance']['threeReplicateMatrixComplete'] is False and status['performance']['presentedFpsCertified'] is False and status['tests']['currentFullStandaloneReleaseCertified'] is False and '不认证性能、物理出版或真人研究任务' in route_doc,
    'pixelReceiptRetainsMismatchesAnd14ActualImages':len(pixels['imageReviews'])==14 and len(pixels['knownMismatchesAndLimits'])==5 and pixels['humanParticipants']==0,
    'oldSealAndSchema13IntermediateFailuresExplicitlyPreserved':len(seal['intermediateFailureScope'])==5 and any('schema13' in item for item in seal['intermediateFailureScope']) and any('stale intermediate current-file claims' in item for item in status['preservedCurrentFailures']),
    'noPrototypeRuntimeFallbackOrModelExecution':status['implementationDirection']['failedPrototypeRuntimeUsed'] is False and status['implementationDirection']['failedPrototypeFallback'] is False and status['implementationDirection']['certifiedPrototypeReuseCandidates']==0 and status['implementationDirection']['modelExecutionThisRound'] is False,
    'currentStatusBrowserAndFinalSealBrowserSame':status['browser']==seal['browser'],
}
checks = {
    'seal431ExpectedBytesHashAndRecords':binding(SEAL)['bytes']==107131 and binding(SEAL)['sha256']==EXPECTED_HASH and len(new_records)==seal['boundFileCount']==431 and all(item['exact'] for item in new_records),
    'oldSeal1OriginalBytesAnd318ResolvedRecordsExact':readback(seal['preservedIntermediateSeal'])['exact'] and len(prior_records)==seal['priorSealBindingsResolved']==318 and all(item['exact'] for item in prior_records),
    'old318OnlyThreeExplicitArchives':sum(item['expected']['path']!=item['actual']['path'] for item in prior_records)==3 and len(archive_map)==3,
    'beforeManifestFiveArchivesRemainExact':len(archive_records)==5 and all(item['exact'] for item in archive_records),
    'schema14All18CurrentReferencesExact':status['schemaVersion']==14 and len(references)==18 and all(item['exact'] for item in references),
    'currentDoc2StatusAndConsistencyReceiptExact':len(document_readback)==2 and all(item['exact'] for item in document_readback) and readback(seal['currentStatus'])['exact'] and readback(seal['finalConsistencyReceipt'])['exact'],
    'all84LocalLinksExistAndMatchRecordedInventory':len(links)==consistency['localLinkCount']==84 and links==consistency['links'] and all(item['exists'] for item in links),
    'alreadyRunFinal39And275LogsAndBuildExit0Read':checks_readback[0]['counts']=={'tests':39,'pass':39,'fail':0} and checks_readback[1]['counts']=={'tests':275,'pass':275,'fail':0} and all(item['exitCode']==0 and item['sourceBeforeAfterExact'] and item['allRecordedBytesExact'] for item in checks_readback),
    'allNamedNarrativeBoundaryChecksPass':all(boundary.values()),
}
after = [binding(path) for path in sorted(paths)]
checks['allReadbackInputsUnchanged'] = before==after
checks['current431AndOld318StillExactAfterReadback'] = all(exact(item,binding(resolve(item['path']))) for item in seal['records']) and all(exact(item,binding(resolve(archive_map.get(item['path'],item['path'])))) for item in prior['records'])
payload = {'inputsBefore':before,'inputsAfter':after,'current431Readback':new_records,'old318ResolvedReadback':prior_records,
    'beforeManifestFiveArchiveReadback':archive_records,'current18ReferenceReadback':references,
    'currentDocumentsReadback':document_readback,'localLinksReadback':links,'alreadyRunChecksReadback':checks_readback}
payload_path=OUT/'bindings-readback.json'
with payload_path.open('x') as stream:
    json.dump(payload,stream,ensure_ascii=False,indent=2);stream.write('\n')
report = {'protocol':'archcanvas-draft-merge-routing-independent-final-readback/2','reviewedAt':datetime.now(timezone.utc).isoformat(),
    'pass':all(checks.values()),'checks':checks,'boundaryChecks':boundary,
    'counts':{'distinctInputs':len(before),'currentSealBindings':len(new_records),'oldSeal1BindingsResolved':len(prior_records),'oldMutableArchives':len(archive_map),'correctionBeforeArchives':len(archive_records),'currentDocuments':len(document_readback),'localLinks':len(links),'currentStatusEvidenceRefs':len(references),'namedBoundaryChecks':len(boundary)},
    'currentSeal':binding(SEAL),'preservedOldSeal1':binding(prior_path),'currentStatus':binding(status_path),'finalConsistencyReceipt':binding(consistency_path),
    'bindingsReadback':binding(payload_path),'preliminaryArchiveReadback':binding(OUT/'before-archive-readback.json'),
    'scope':'Exact final431/old318 bytes, named current narrative/status boundary fields and saved already-run check receipts only. No wholesale approval of every preserved intermediate statement.',
    'textReview':'Independent source_contract_review read current completion lead/table, merge page, schema14 and seal2. No remaining current BSA/ye scope mix found; its reported limits agree with this reader.',
    'remainingLimits':['The current bounded five-edge draft crossing was resolved; long exterior fanout and arbitrary layouts remain outside aesthetic certification.',
        'The current merge generated static source only. Prior ye managed/export/preset browser trials do not become BSA certification.',
        '100-percent raster/state pairing and whole-network horizontal-pan pixels remain uncertified; rawAttempt1 was not frozen before every file existed.',
        '18 current references have homogeneous exact records. Archived schema13 and intermediate current-document claims retain their recorded failures.',
        'Local links check target existence, not heading anchors. Byte identity does not certify every semantic assertion in all retained files.',
        'Five AI review roles remain zero actual researchers; M4 is partial and M5 has not started.'],
    'productsTestsOrBuildRerun':False,'modelsExecuted':False,'browserOperated':False,'oldOrCurrentSealedFilesModified':False,
    'humanParticipants':0,'M4':'partial','M5':'not_started'}
target=OUT/'report.json'
with target.open('x') as stream:
    json.dump(report,stream,ensure_ascii=False,indent=2);stream.write('\n')
print(json.dumps({'report':binding(target),'pass':report['pass'],'checks':checks,'boundaryChecks':boundary,'counts':report['counts'],'bindingsReadback':binding(payload_path)},ensure_ascii=False))
