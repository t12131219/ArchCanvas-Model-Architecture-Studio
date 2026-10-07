"""Final bounded seal readback; explicit input paths only, no product execution."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import re
import traceback

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
SEAL = ROOT / 'docs/evidence/m4-collapsed-residual-verification-sealed.json'
SEAL_SHA = '43457fb22c7871466fa8563efd44525ccd5168a625312ad424c5c82536f34aa6'
EXPECTED = {
    'scene': '46ef39a60cdc5778e49536007d3a0c7807d3e6cb26a5fadaa2a07d37a40be75a',
    'router': '45dcc36189cfc2be0264a566b3349f15a8cff598de5e7156362c496558d35eb2',
    'js': '5ee22dbd8bc61cc586f499f132910adcf77aa55fe85fead1600aa206d46b149f',
    'css': '172a09a8c147e53c3bef426cf76b59b8cc4893e891eb6e920aa7b25a0bb024e0',
    'acceptance': '60812423d1e3dbd10d7e979e73d001a7bb8e0e62ffcb5494c551ec58612c72d6',
    'closure': '5eb35989515416f5d9067bb7655e0112a2d7d03fa44473ea0bf4425608b0c14d',
}
DOCS = [
    'README.md', 'docs/m4-completion.md', 'docs/m4-human-review-handoff.md',
    'docs/m4-collapsed-residual.md', 'docs/evidence/README.md',
    'docs/evidence/m4-collapsed-residual-work/README.md',
    'skills/archcanvas/references/formal-alpha.md',
    'skills/archcanvas/references/runtime-compatibility.md',
    'docs/evidence/m4-human-review-handoff-status.json',
]
FIRST = {}


def read(path):
    path = Path(path).absolute()
    assert path.is_file() and not path.is_symlink(), path
    raw = path.read_bytes()
    if path in FIRST:
        assert FIRST[path] == raw, f'Input changed during read {path}'
    FIRST[path] = raw
    return raw


def load(path):
    return json.loads(read(path))


def binding(path, raw=None):
    path = Path(path).absolute()
    raw = read(path) if raw is None else raw
    return {'path': str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path),
            'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def verify(row):
    path = Path(row['path'])
    if not path.is_absolute():
        assert '..' not in path.parts
        path = ROOT / path
    actual = binding(path)
    assert actual['bytes'] == row['bytes'] and actual['sha256'] == row['sha256'], row
    return path


def formal_checks(seal, current):
    records = []
    for name, row in seal['checks'].items():
        receipt = load(verify(row))
        assert receipt['exitCode'] == 0 and receipt['sourceBeforeAfterExact'] is True
        assert receipt['inputsBefore'] == receipt['inputsAfter']
        log_map = {Path(item['path']).name: item for item in receipt['logs']}
        stdout = read(verify(log_map['stdout.txt'])).decode()
        assert read(verify(log_map['stderr.txt'])) == b''
        source = {item['path']: item for item in receipt['inputsAfter']}
        # Explicit selected final product/test/oracle identities, not a second
        # traversal of every old receipt's historical dependency closure.
        selected = []
        for path in ('studio/src/core/scene.ts', 'studio/src/core/orthogonalRouter.ts',
                     'studio/tests/collapsed-residual-independent.test.ts',
                     'studio/tests/repeat-outline-independent.test.ts',
                     'docs/evidence/m4-collapsed-residual-work/acceptance/oracle.ts',
                     'docs/evidence/m4-collapsed-residual-work/acceptance/fixtures.ts'):
            assert source[path] == current[path]
            selected.append(source[path])
        counts = None
        if name != 'build-attempt-2':
            counts = {key: int(re.search(r'^ℹ ' + key + r' (\d+)$', stdout, re.M)[1])
                      for key in ('tests', 'pass', 'fail', 'skipped')}
            expected = 24 if name == 'target-attempt-3' else 203
            assert counts == {'tests': expected, 'pass': expected, 'fail': 0, 'skipped': 0}
        else:
            assert receipt['argv'][-3:] == ['studio', 'run', 'build']
            for built in receipt['builtFiles']:
                assert built == current[built['path']]
        records.append({'name': name, 'receipt': row, 'exitCode': 0,
                        'sourceBeforeAfterExact': True, 'stdoutCounts': counts,
                        'selectedCurrentSourcesExact': selected,
                        'checksRerunByReviewer': False})
    return records


def status_semantics(status, seal):
    assert status['phaseStatus'] == 'partial' and status['nextPhaseStarted'] is False
    assert status['humanAcceptanceCertified'] is False
    direction = status['implementationDirection']
    assert direction['formalProductBuiltFromScratch'] is True
    assert direction['failedPrototypeRuntimeUsed'] is False and direction['failedPrototypeFallback'] is False
    assert direction['certifiedPrototypeReuseCandidates'] == 0
    assert direction['modelExecutionThisRound'] == 'not_run' and direction['dependenciesInstalledThisRound'] is False
    assert status['productionBuild'] == seal['productionBuild'] == 'index-Dzp9we5t.js'
    assert status['productionCss'] == seal['productionCss'] == 'index-B6WbMowt.css'
    assert status['productionJsSha256'] == EXPECTED['js'] and status['productionCssSha256'] == EXPECTED['css']
    assert status['collapsedResidual']['scene']['sha256'] == EXPECTED['scene']
    assert status['collapsedResidual']['router']['sha256'] == EXPECTED['router']
    test = status['tests']
    assert test['studio']['passed'] == 203 and test['focusedSeparateRun']['passed'] == 24
    assert test['suiteCountsCombined'] is False and test['pythonFullSuiteRerunThisRound'] is False
    assert test['standalone']['currentFullReleaseCertified'] is False
    browser = status['currentBrowser']
    assert browser['currentValidatedCases'] == 12 and browser['manifestFiles'] == 128
    assert browser['fitImages'] == 12 and browser['localImages'] == 9
    for key in ('full39MatrixCertified', 'humanAcceptanceCertified', 'publicationCertified',
                'globalRouteBeautyCertified', 'nativeFourDirectionScopeInherited',
                'oldAuthoredChainInherited', 'onlineClaim', 'serviceStartupRawStdoutPreserved'):
        assert browser[key] is False, key
    pix = browser['pixelObservations']
    assert pix['newJpegsOpened'] == 21 and pix['oldL0Opened'] == 4
    assert pix['observerIsAi'] is True and pix['humanAcceptanceCertified'] is False
    assert pix['aestheticsCertified'] is False and pix['physicalPublicationCertified'] is False
    assert pix['actualPublicationPixelsReviewed'] is False
    assert pix['inputBindingsUnchanged'] == 151 and pix['actualFilesInventoryExact'] == 128
    assert pix['machineComparisonCount'] == 142 and pix['trueComparisons'] == 134
    assert pix['retainedFalseNodeSubtreeComparisons'] == 8 and len(pix['fitOnlyCases']) == 5
    assert pix['publicationNodeDifference']['publicationDeltaXWorldUnits'] == 30
    assert pix['publicationNodeDifference']['falseChecksPreserved'] is True
    assert pix['publicationNodeDifference']['expectedRewritten'] is False
    assert pix['publicationNodeDifference']['completeCrossModeXmlEqualityClaimed'] is False
    height = browser['metadataHeightMmExceptions']
    assert height['observations'] == 4 and height['absoluteDeltaMm'] == 5.684341886080802e-14
    assert height['toleranceMm'] == 1e-10 and height['rawInputsModifiedOrNormalized'] is False
    diagnostic = status['currentInputDiagnostic']
    assert diagnostic['status'] == 'not-measured-this-product-round'
    for key in ('oldAu3ObserverInherited', 'presentedPerformanceCertified', 'overallInpCertified',
                'activeCancellationCertified', 'resolvedFontsHardwareCertified', 'nonemptyPinsActualProtectionCertified'):
        assert diagnostic[key] is False
    research = status['research']
    for key in ('currentPackagePrepared', 'currentPackageVerified', 'oldSlotsMayBeAssigned', 'aiCountsAsHuman'):
        assert research[key] is False
    assert research['assignedCount'] == research['collectedCount'] == research['humanResearcherCount'] == 0
    assert status['previousAu3FrozenScope']['currentRendererCertified'] is False
    assert status['authoring']['newPerModuleBrowserCertification'] is False
    assert status['authoring']['historicalAu3AuthoredChainInherited'] is False
    return {'m4': 'partial', 'm5Started': False, 'humans': 0,
            'currentScope': 'CNN12 bounded artifact/canonical geometry/export/save plus separate bounded AI image review',
            'historicalEvidenceInheritedAsCurrent': False,
            'retainedFindings': ['Five fit-only cases', 'Monochrome role tracing', 'Expanded header detours',
                                 'Tall L2 page', 'Repeat publication count-text +30; eight false cross-mode subtree comparisons'],
            'globalAestheticsPhysicalFontsPresentedPerformanceHumanAcceptance': 'not certified'}


def main():
    target = OUT / 'receipt-repair-attempt-1.json'
    assert not target.exists()
    result = {'protocol': 'archcanvas-collapsed-residual-final-bounded-readback/1',
              'startedAt': datetime.now(timezone.utc).isoformat(), 'verdict': 'incomplete',
              'scope': 'Exact current seal689 bindings and its2883 explicit prior byte resolutions,9 current docs/status semantics and essential selected final checks. No broad archive traversal or new acceptance execution.',
              'productCodeExecuted': False, 'modelsExecuted': False, 'browserOperated': False,
              'testsRun': False, 'buildRun': False, 'validatorRun': False,
              'docsStatusSealEdited': False, 'oldBytePreservationUpgradedToCurrentAcceptance': False,
              'limits': 'Read-only bounded closure. No new pixel, global/full39, human, performance, publication, font, liveness, standalone or numerical model certification.'}
    try:
        raw = read(SEAL)
        assert len(raw) == 1269822 and hashlib.sha256(raw).hexdigest() == SEAL_SHA
        seal = json.loads(raw)
        assert seal['bindingCount'] == len(seal['bindings']) == 689
        current = {row['path']: row for row in seal['bindings']}
        assert len(current) == 689
        for row in seal['bindings']:
            verify(row)
        assert seal['state'] == 'progress' and seal['m4'] == 'partial' and seal['m5Started'] is False
        assert seal['priorBytePreservationOnly'] is True and seal['humans'] == 0
        for key in ('presentedPerformanceCertified', 'physicalPublicationCertified', 'globalRouteBeautyCertified',
                    'full39CaseCurrentBrowserCoverage', 'userModelsExecuted', 'dependenciesInstalled'):
            assert seal[key] is False
        prior = load(verify(seal['preservedPriorSeal']))
        assert seal['preservedPriorSeal']['sha256'] == '360685f78ecc6d29875854a00ba9d8be19d1b2212483382aff78144dc4cc8225'
        old = {row['path']: row for row in prior['bindings']}
        assert len(old) == len(prior['bindings']) == 2883
        resolution = {row['originalPath']: row['resolved'] for row in seal['priorByteResolutions']}
        assert len(resolution) == len(seal['priorByteResolutions']) == 2883 and set(resolution) == set(old)
        changed_path = []
        for original_path, resolved in resolution.items():
            assert resolved['bytes'] == old[original_path]['bytes'] and resolved['sha256'] == old[original_path]['sha256']
            verify(resolved)
            if original_path != resolved['path']:
                changed_path.append({'original': old[original_path], 'explicitUnchangedByteResolution': resolved})
        result['seal'] = binding(SEAL)
        result['currentBindingsVerified'] = 689
        result['priorBindingsResolvedExact'] = 2883
        result['priorResolvedViaDifferentExplicitPath'] = changed_path
        result['oldArchiveFileEnumerationPerformed'] = False
        result['preservedPriorSeal'] = seal['preservedPriorSeal']
        identity = {name: current[path] for name, path in {
            'scene': 'studio/src/core/scene.ts', 'router': 'studio/src/core/orthogonalRouter.ts',
            'js': 'studio/dist/assets/index-Dzp9we5t.js', 'css': 'studio/dist/assets/index-B6WbMowt.css',
            'acceptance': seal['independentAcceptance']['path'], 'closure': seal['independentClosure']['path'],
        }.items()}
        for name, row in identity.items():
            assert row['sha256'] == EXPECTED[name]
        assert seal['independentAcceptance'] == identity['acceptance'] and seal['independentClosure'] == identity['closure']
        result['finalSourceBuildAndOwnReports'] = identity
        result['formalChecks'] = formal_checks(seal, current)
        own_report = load(ROOT / seal['independentAcceptance']['path'])
        own_closure = load(ROOT / seal['independentClosure']['path'])
        assert own_report['verdict'].startswith('pass-') and len(own_report['cases']) == 12 and own_report['allInputsReadTwiceExact']
        assert len(own_report['inputsAfter']) == 882 and len(own_report['heightMmJsonRoundtripExceptions']) == 4
        assert own_closure['verdict'].startswith('pass-') and own_closure['inputCount'] == 890 and own_closure['inputsUnchanged']
        pix = load(verify(seal['aiPixelReview']))
        assert seal['aiPixelReview']['sha256'] == 'b2e18274290ae2b2c4042e3b6c47b6bb44e444ee535b1c25966e4c6d8f1e1464'
        assert pix['AIOnly'] is True and pix['humanParticipantsAdded'] == 0
        assert pix['finalFitCases'] == 12 and pix['finalLocalImages'] == 9
        assert pix['visibleStateMatchedOriginals'] == 21 and len(pix['fitOnlyLimitCases']) == 5
        for row in pix['artifacts']:
            assert row == current[row['path']]
        result['aiImageReview'] = {'receipt': seal['aiPixelReview'], 'reviewerThisClosureViewedImages': False,
                                   'status': pix['status'], 'retainedBoundedConclusion': pix['boundedConclusion']}
        skill = load(verify(seal['hostSkillValidation']))
        assert seal['hostSkillValidation']['sha256'] == 'b1c0ada4757adfb02e85cdc3ccb30a9d9d9e8d5329c9dd4b5a19bdb1492da0ce'
        assert skill['exitCode'] == 0 and skill['inputsExact'] is True and skill['inputsBefore'] == skill['inputsAfter']
        for row in skill['inputsAfter'] + skill['logs'] + [skill['validator'], skill['resolvedInterpreter'], skill['runner']]:
            verify(row)
        result['hostSkillValidation'] = {'receipt': seal['hostSkillValidation'], 'exitCode': 0,
                                         'inputBytesExact': True, 'validatorExecutedByThisClosure': False}
        status = load(ROOT / DOCS[-1])
        assert len(status['evidenceRefs']) == 24
        for row in status['evidenceRefs']:
            verify(row)
            if row['path'] in current:
                assert row == current[row['path']]
        result['statusEvidenceRefsExact'] = 24
        result['statusSemanticReview'] = status_semantics(status, seal)
        reviewed = load(OUT / 'semantic-review.json')
        assert reviewed['verdict'] == 'pass-bounded-current-documents-and-status-scope'
        assert sorted(row['path'] for row in reviewed['documents']) == sorted(DOCS)
        for row in reviewed['documents']:
            verify(row)
            assert row == current[row['path']]
        result['independentNineDocumentSemanticReview'] = {'artifact': binding(OUT / 'semantic-review.json'),
                                                          'documentCount': 9, 'conclusions': reviewed['conclusions'],
                                                          'historicalBodyClaimsRevalidated': False}
        result['verdict'] = 'pass-final-bounded-seal-bytes-docs-status-source-build-closure'
    except Exception as error:
        result['verdict'] = 'fail-retained'
        result['failure'] = {'type': type(error).__name__, 'message': str(error), 'traceback': traceback.format_exc()}
    read(Path(__file__).resolve())
    before = [binding(path, body) for path, body in sorted(FIRST.items())]
    after, changed = [], []
    for path, body in sorted(FIRST.items()):
        actual = binding(path, path.read_bytes())
        after.append(actual)
        if actual != binding(path, body):
            changed.append(str(path))
    result['inputsBefore'] = before
    result['inputsAfter'] = after
    result['inputCount'] = len(before)
    result['inputsBeforeAfterExact'] = not changed
    result['changedInputs'] = changed
    result['finishedAt'] = datetime.now(timezone.utc).isoformat()
    if changed:
        result['verdict'] = 'fail-input-mutation-retained'
    with target.open('x') as output:
        json.dump(result, output, ensure_ascii=False, indent=2)
        output.write('\n')
    print(json.dumps({'receipt': binding(target), 'verdict': result['verdict'],
                      'currentBindingsVerified': result.get('currentBindingsVerified'),
                      'priorBindingsResolvedExact': result.get('priorBindingsResolvedExact'),
                      'uniqueInputsReadTwice': len(before), 'inputsExact': not changed}, ensure_ascii=False))
    return 0 if result['verdict'].startswith('pass-') else 1


if __name__ == '__main__':
    raise SystemExit(main())
