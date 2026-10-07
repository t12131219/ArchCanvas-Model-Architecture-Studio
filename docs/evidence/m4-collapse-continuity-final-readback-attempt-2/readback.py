"""Independent final seal, scope and link readback; no product execution.

This lives outside all sealed selectedTrees. It checks actual bytes and
retained receipts, without mutating any sealed document or evidence.
"""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import re
import sys
import traceback
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
SEAL_PATH = 'docs/evidence/m4-collapse-continuity-verification-sealed.json'
SEAL_HASH = 'fce55435e143ad500e9b777e543ea6ef41df13d7bcbef683a503f3d2558ca5a5'
JS_HASH = 'd106d5525baf288f966a1e61ebd1a115c6f3190d0b2bf62594d11dba58be8b66'
NATIVE_HASH = 'cd2919c1fc8aa447777d0360da2af09a9d11b57333926c35ee45baf751d411b5'
ROLE_HASH = 'fd2130b066262fbc6a6fefcd17c378040c68512fb05e6c5dbd73ff0ba9a74541'
DOCS = [
    'README.md', 'docs/m4-completion.md', 'docs/m4-exit-audit.md',
    'docs/m4-ai-usability-audit.md', 'docs/m4-human-review-handoff.md',
    'docs/m4-performance.md', 'docs/m4-authoring.md', 'docs/acceptance.md',
    'docs/capability-matrix.md', 'docs/evidence/README.md',
    'skills/archcanvas/SKILL.md', 'skills/archcanvas/references/formal-alpha.md',
    'skills/archcanvas/references/runtime-compatibility.md',
    'docs/m4-collapse-continuity.md', 'docs/evidence/m4-collapse-continuity-work/README.md',
]
inputs = {}
results = {}


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def path(value):
    p = Path(value)
    return p if p.is_absolute() else ROOT / p


def read(value):
    p = path(value)
    raw = p.read_bytes()
    key = str(p.relative_to(ROOT)) if p.is_relative_to(ROOT) else str(p)
    b = {'path': key, 'bytes': len(raw), 'sha256': sha(raw)}
    if key in inputs:
        assert inputs[key] == b, f'Input changed during readback: {key}'
    inputs[key] = b
    return raw


def load(value):
    return json.loads(read(value))


def verify(b):
    actual = read(b['path'])
    assert len(actual) == b['bytes'] and sha(actual) == b['sha256'], b['path']


def audit():
    read(__file__)
    seal_raw = read(SEAL_PATH)
    assert len(seal_raw) == 267853 and sha(seal_raw) == SEAL_HASH
    seal = json.loads(seal_raw)
    assert seal['protocol'] == 'm4-collapse-continuity-bounded-verification-seal/1'
    assert seal['boundFileCount'] == len(seal['records']) == 1117
    indexed = {b['path']: b for b in seal['records']}
    assert len(indexed) == 1117
    for b in seal['records']:
        verify(b)
    external = [b for b in seal['records'] if Path(b['path']).is_absolute()]
    assert len(external) == 1 and external[0]['path'] == '/home/fzg/.nvm/versions/node/v24.19.0/bin/node'
    inventories = []
    seal_script = read('docs/evidence/m4-collapse-continuity-work/seal_current.py').decode()
    assert "if path.is_file() and '__pycache__' not in path.parts and path.suffix != '.pyc':" in seal_script
    for d in seal['selectedTrees']:
        found = {str(p.relative_to(ROOT)) for p in (ROOT / d).rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix != '.pyc'}
        excluded = [str(p.relative_to(ROOT)) for p in (ROOT / d).rglob('*') if p.is_file() and ('__pycache__' in p.parts or p.suffix == '.pyc')]
        recorded = {name for name in indexed if name.startswith(d + '/')}
        assert found == recorded, f'sealed tree inventory mismatch: {d}'
        inventories.append({'tree': d, 'files': len(found), 'exact': True, 'declaredExcludedFiles': excluded})
    assert seal['allSelectedBytesBeforeAfterExact'] is True
    assert seal['modelExecution'] is False and seal['dependenciesInstalled'] is False
    assert seal['oldRoleEvidenceModified'] is False
    assert seal['milestones'] == {'M4': 'partial', 'M5': 'not_started', 'humans': 0}
    assert seal['currentBuild'] == 'index-BKbgeBjI.js' and seal['currentJsSha256'] == JS_HASH
    assert sha(read('studio/dist/assets/index-BKbgeBjI.js')) == JS_HASH
    assert b'index-BKbgeBjI.js' in read('studio/dist/index.html')
    assert b'index-B6WbMowt.css' in read('studio/dist/index.html')
    results['seal'] = {'binding': inputs[SEAL_PATH], 'recordsVerified': 1117,
        'selectedTreeInventories': inventories, 'externalExecutableBindings': external,
        'sealChanged': False, 'certificationScope': seal['scope'],
        'pendingReadbackFieldRetained': seal['independentFinalReadback']}

    status = load('docs/evidence/m4-human-review-handoff-status.json')
    assert status['schemaVersion'] == 11 and status['productionBuild'] == seal['currentBuild']
    assert status['productionJsSha256'] == JS_HASH
    assert status['productionCssSha256'] == sha(read('studio/dist/assets/index-B6WbMowt.css'))
    assert status['productionIndexSha256'] == sha(read('studio/dist/index.html'))
    assert status['phaseStatus'] == 'partial' and status['nextPhaseStarted'] is False
    assert status['humanAcceptanceCertified'] is False
    for status_key, seal_key in [
        ('implementationDirection', 'sourceDirection'), ('tests', 'checks'),
        ('collapseContinuity', 'native'), ('authoring', 'authoring'),
        ('aiReview', 'independentAiRoles'), ('performance', 'historicalPerformanceControlScope'),
        ('widthOverride', 'widthSupplementScope'),
    ]:
        assert status[status_key] == seal[seal_key], (status_key, seal_key)
    for b in status['evidenceRefs']:
        verify(b)
        assert indexed[b['path']] == b
    assert len(status['evidenceRefs']) == 20
    humans = status['humanResearch']
    assert all(humans[k] == 0 for k in ['assigned', 'collected', 'researchers'])
    assert humans['aiCountedAsHuman'] is False
    assert humans['preparedForCurrentBuild'] is False and humans['verifiedForCurrentBuild'] is False
    assert status['aiReview']['reviewerRoleCount'] == 3
    assert status['aiReview']['rolesAreHumanParticipants'] is False
    results['machineStatus'] = {'schemaVersion': 11, 'evidenceRefsVerified': 20,
        'sealScopesExact': True, 'currentAssetsExact': True,
        'humanParticipants': 0, 'M4': 'partial', 'M5': 'not_started'}

    tests = status['tests']
    assert tests['studio']['passed'] == 247 and tests['focusedSeparateRun']['passed'] == 13
    assert tests['suiteCountsCombined'] is False
    assert tests['strictTypescriptExitCode'] == tests['buildExitCode'] == 0
    assert tests['pythonFullSuiteRerunThisRound'] is False
    assert tests['currentFullStandaloneReleaseCertified'] is False
    receipts = []
    for spec, count in [(tests['focusedSeparateRun'], 13), (tests['studio'], 247)]:
        r = load(spec['receipt'])
        assert r['exitCode'] == 0 and r['inputsBefore'] == r['inputsAfter']
        assert r['sourceBeforeAfterExact'] is True
        text = read(str(Path(spec['receipt']).parent / 'stdout.txt')).decode()
        for key, value in [('tests', count), ('pass', count), ('fail', 0), ('skipped', 0)]:
            assert re.search(rf'(?:ℹ|#)\s+{key}\s+{value}(?:\s|$)', text)
        receipts.append({'path': spec['receipt'], 'count': count, 'recordedExitCode': 0})
    build = load(tests['buildReceipt'])
    assert build['exitCode'] == 0 and build['inputsBefore'] == build['inputsAfter']
    read(str(Path(tests['buildReceipt']).parent / 'stdout.txt'))
    check_audit = load(tests['independentCheckAudit'])
    assert check_audit['status'] == 'bounded-final-recorded-checks-pass'
    assert check_audit['auditInputBytesUnchanged'] is True
    # A check receipt's input tree can include earlier workflow files. Their
    # recorded-before equality is read here; immutable final audit copies bind
    # final executable/config/test bytes rather than fabricating old live docs.
    results['recordedProductChecks'] = {'receipts': receipts, 'strictBuildRecordedExitCode': 0,
        'independentCheckAuditPass': True, 'testsRerunByThisAuditor': False,
        'countsAddedTogether': False, 'completeEnvironmentOrReleaseCertified': False}

    native = load(status['collapseContinuity']['independentNativeAudit'])
    assert native['status'] == 'bounded-pass' and native['auditInputBytesUnchanged'] is True
    assert sha(read(status['collapseContinuity']['independentNativeAudit'])) == NATIVE_HASH
    assert len(native['inputsBefore']) == 107 and native['inputsBefore'] == native['inputsAfter']
    for b in native['inputsBefore']: verify(b)
    assert native['results']['nativeObservations']['count'] == 18
    assert native['results']['nativeObservations']['endpointCount'] == 142
    assert len(native['results']['screenshotBrackets']) == 6
    assert native['results']['compactGeometry']['gap'] == 31
    assert native['results']['compactGeometry']['historicalGap'] == 1607
    assert native['results']['completeSavedCanvas']['hiddenLocalPositionsPreserved'] == 16
    assert native['results']['completeSavedCanvas']['legacyEntriesPreserved'] == 4
    assert native['results']['actualExport']['uuid'] == '1367fc7fa1034519b3de845b083c566a'
    assert native['results']['gestures']['expandScreenAnchorCertified'] is False
    manifest = load('docs/evidence/m4-collapse-continuity-work/browser-final-manifest-attempt-1.json')
    assert manifest['rootSummaryIsRetrospective'] is True and manifest['humanParticipants'] == 0
    for b in manifest['records']: verify(b)
    raw_directory = ROOT / 'docs/evidence/m4-collapse-continuity-work/browser-current-attempt-2'
    raw_files = {str(p.relative_to(ROOT)) for p in raw_directory.rglob('*') if p.is_file()}
    assert raw_files == {b['path'] for b in manifest['records']} and len(raw_files) == 31
    results['nativeEvidence'] = {'priorIndependentReportUnchanged': True, 'boundInputsVerified': 107,
        'rawInventoryExact': 31, 'observations': 18, 'edgeEndpointPairs': 142, 'endpointPoints': 284,
        'brackets': 6, 'upMoveOverlapKept': True, 'ancestorWidthFormulaKept': True,
        'expandScreenAnchorCertified': False, 'currentFullMatrixCertified': False}

    authoring = load(status['authoring']['independentArtifactAudit'])
    assert authoring['allCasesPassed'] is True and len(authoring['cases']) == 5
    assert authoring['inputsUnchanged'] is True and authoring['allInputsCopiedExact'] is True
    assert authoring['inputBindingsBefore'] == authoring['inputBindingsAfter']
    assert len(authoring['inputBindingsBefore']) == 42
    assert authoring['humanParticipants'] == 0 and authoring['modelsExecuted'] is False
    assert authoring['runtimeCertified'] is False and authoring['publicationCertified'] is False
    for b in authoring['inputBindingsBefore']: verify(b)
    results['authoringReceiptScope'] = {'path': status['authoring']['independentArtifactAudit'],
        'bytesExactAgainstSealAndStatus': True, 'checksReported': 5, 'inputsReported': 42,
        'independentAuthoringAuditor': 'performance_controls',
        'noDuplicateAstAuditHere': True, 'perModuleRuntimeAndHumanCertified': False,
        'remainingIssues': status['authoring']['remainingIssues']}

    verify(seal['documentationReceipt'])
    doc_receipt = load(seal['documentationReceipt']['path'])
    assert doc_receipt['documents'] == doc_receipt['documentsAfter']
    assert doc_receipt['documentInputsUnchanged'] is True
    assert [b['path'] for b in doc_receipt['documents']] == DOCS
    for b in doc_receipt['documents']: verify(b)
    links = []
    for name in DOCS:
        text = read(name).decode()
        for match in re.finditer(r'\[[^\]]*\]\(([^)]+)\)', text):
            target = match[1].split(' "', 1)[0].strip('<>')
            parsed = urlsplit(target)
            if parsed.scheme or not parsed.path: continue
            destination = (ROOT / name).parent / unquote(parsed.path)
            assert destination.exists(), (name, target)
            if destination.is_file(): read(destination.resolve())
            links.append({'document': name, 'target': target, 'exists': True})
    assert len(links) == 460 and links == doc_receipt['inlineLocalLinks']
    skill = doc_receipt['skillValidator']
    assert skill['exitCode'] == 0
    for key in ['stdout', 'stderr', 'sourceCopy']: verify(skill[key])
    assert read(skill['stdout']['path']).decode().strip() == 'Skill is valid!'
    assert read(skill['stderr']['path']) == b''
    assert read(skill['argv'][1]) == read(skill['sourceCopy']['path'])
    results['documentsAndSkill'] = {'documents': 15, 'inlineLocalLinks': 460,
        'allLinkTargetsExist': True, 'rootLinkScanExact': True,
        'skillRecordedExitCode': 0, 'skillValidatorSourceCopyExact': True,
        'skillValidationRerun': False, 'skillValidationScope': skill['scope'],
        'validatorInterpreterFullyEnvironmentCertified': False}

    stage = read('docs/m4-collapse-continuity.md').decode()
    for fragment in ['index-BKbgeBjI.js', '13/13', '247/247', '1607', '31世界单位',
        '正常展开仍可新增节点并撑开邻居', '284个端点', 'root宽度由254增至294',
        '不认证展开屏幕锚点', '未认证CNN managed打开', 'actual17模块包含SiLU，无Softmax',
        '不是逐模块生成', '三个AI角色', 'M4仍partial、真人0、M5未开始']:
        assert fragment in stage, fragment
    assert '284个端点点' not in stage
    for name in DOCS:
        if name in ['skills/archcanvas/SKILL.md', 'docs/m4-collapse-continuity.md',
                    'docs/evidence/m4-collapse-continuity-work/README.md']:
            continue
        text = read(name).decode()
        assert 'BKbgeBjI' in text and '247' in text and '13' in text
        assert ('partial' in text) and ('M5' in text)
        assert ('0' in text) and ('AI' in text)
    results['claimsReview'] = {
        'currentBuildAndCountsMatchReceipts': True,
        'historyAndPriorRoleScopesPreserved': True,
        'threeAiRolesCountAsAutomationOnly': True,
        'nativeUpMoveOverlapAndDerivedAncestorResizeNotHidden': True,
        'authoringPortHitFailuresRepeatedBendsAndOutputSubtitleIssuePreserved': True,
        'publicationPerformanceHumanAndFullMatrixClaimsRemainOpen': True,
        'cacheReaderInterpretation': 'Direct current effective key and exact legacy key have priority. Only the compatible projected fallback requires all visible positions to agree; this audit does not certify arbitrary conflicting caches.',
        'interpretationBasis': 'Manual review of final document.ts and frozen independent source/check/native audit scope; no product execution.',
    }

    verify(seal['priorRoleSeal'])
    assert seal['priorRoleSeal']['sha256'] == ROLE_HASH
    role = load(seal['priorRoleSeal']['path'])
    assert len(role['records']) == 981
    for b in role['records']: verify(b)
    assert seal['priorRoleBindingsReadExact'] == 981
    assert role['milestones'] == {'M4': 'partial', 'M5': 'not started', 'humanParticipants': 0}
    results['historicalRoleSeal'] = {'sealUnchanged': True, 'resolvedRecordsVerified': 981,
        'currentBkCertificationInherited': False}


error = None
try:
    audit()
except Exception as exc:
    error = {'name': type(exc).__name__, 'message': str(exc), 'traceback': traceback.format_exc()}
before = sorted(inputs.values(), key=lambda b: b['path'])
after = []
for b in before:
    raw = path(b['path']).read_bytes()
    after.append({'path': b['path'], 'bytes': len(raw), 'sha256': sha(raw)})
exact = before == after
report = {'protocol': 'm4-collapse-independent-final-seal-scope-links-readback/1',
    'finishedAt': datetime.now(timezone.utc).isoformat(),
    'status': 'bounded-pass' if error is None and exact else 'failed',
    'results': results, 'error': error, 'inputsBefore': before, 'inputsAfter': after,
    'allReadInputBytesUnchanged': exact, 'existingSealedFilesModified': False,
    'productTestsRerun': False, 'modelsExecuted': False, 'dependenciesInstalled': False,
    'pixelsReviewedByThisScript': False, 'humanParticipants': 0,
    'M4': 'partial', 'M5': 'not_started',
    'limits': ['Bounded byte/receipt/scope/link review, not new arbitrary-model or numerical runtime certification.',
        'Link existence and retained byte identity do not approve all historical claims in linked files.',
        'Recorded Skill validator success does not certify the full system Python environment.',
        'Native/authoring/pixel results retain their own independent receipts and explicit scope.',
        'The original seal stays immutable with independentFinalReadback=pending; this separate report supplies the readback.']}
with (OUT / 'report.json').open('x') as f:
    json.dump(report, f, ensure_ascii=False, indent=2)
    f.write('\n')
print(json.dumps({'status': report['status'], 'results': list(results), 'inputBindings': len(before),
                  'allInputBytesUnchanged': exact, 'error': error}, ensure_ascii=False))
if report['status'] != 'bounded-pass': sys.exit(1)
