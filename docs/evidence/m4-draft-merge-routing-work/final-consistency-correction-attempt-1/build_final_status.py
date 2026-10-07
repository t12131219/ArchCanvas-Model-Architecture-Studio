"""Write standalone current status; earlier status/seals remain archived inputs."""
from pathlib import Path
import datetime
import hashlib
import json

ROOT = Path(__file__).resolve().parents[4]
WORK = Path('docs/evidence/m4-draft-merge-routing-work')
CORRECTION = WORK / 'final-consistency-correction-attempt-1'


def binding(path):
    path = Path(path)
    data = (ROOT / path).read_bytes()
    return {'path': path.as_posix(), 'bytes': len(data),
            'sha256': hashlib.sha256(data).hexdigest()}


def main():
    refs = [
        'docs/m4-draft-merge-routing.md', 'docs/m4-completion.md',
        'studio/src/draftRouting.ts', 'studio/src/authoring.ts',
        'studio/tests/draft-merge-routing-independent.test.ts',
        'studio/dist/index.html', 'studio/dist/assets/index-BSA5RjBV.js',
        'studio/dist/assets/index-C769d2rm.css',
        str(WORK / 'browser-attempt-2/manifest.json'),
        str(WORK / 'checks/target-attempt-2/receipt.json'),
        str(WORK / 'checks/suite-attempt-1/receipt.json'),
        str(WORK / 'checks/build-attempt-1/receipt.json'),
        str(WORK / 'independent-contract-attempt-1/source-review-attempt-1/report.json'),
        str(WORK / 'independent-contract-attempt-1/final-check-readback-attempt-1/report.json'),
        str(WORK / 'visual-review-attempt-1/final-review-receipt.json'),
        str(WORK / 'saved-artifact-audit-attempt-1/receipt.json'),
        str(WORK / 'novice-palette-review-attempt-1/receipt.json'),
        'docs/evidence/m4-performance-next-audit-attempt-1/receipt.json',
    ]
    before = json.loads((ROOT / CORRECTION / 'before-manifest.json').read_text())
    prior13 = next(r for r in before['records']
                   if r['path'].endswith('status-followup.json'))
    status = {
        'schemaVersion': 14,
        'protocol': 'archcanvas-m4-current-bounded-followup/1',
        'generatedAt': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'productionBuild': 'index-BSA5RjBV.js',
        'productionJsSha256': binding('studio/dist/assets/index-BSA5RjBV.js')['sha256'],
        'productionCss': 'index-C769d2rm.css',
        'productionCssSha256': binding('studio/dist/assets/index-C769d2rm.css')['sha256'],
        'productionIndexSha256': binding('studio/dist/index.html')['sha256'],
        'phaseStatus': 'M4 partial after draft merge routing follow-up',
        'nextPhaseStarted': False,
        'humanAcceptanceCertified': False,
        'scope': 'Standalone current draft-only small-graph route follow-up. Historical stage fields are not inherited as current results.',
        'implementationDirection': {
            'formalProductBuiltFromScratch': True,
            'failedPrototypeRuntimeUsed': False,
            'failedPrototypeFallback': False,
            'certifiedPrototypeReuseCandidates': 0,
            'modelExecutionThisRound': False,
            'dependenciesInstalledThisRound': False,
        },
        'tests': {
            'studio': {'passed': 275, 'failed': 0, 'skipped': 0, 'exitCode': 0,
                       'receipt': str(WORK / 'checks/suite-attempt-1/receipt.json')},
            'focusedSeparateRun': {'passed': 39, 'failed': 0, 'skipped': 0, 'exitCode': 0,
                                   'receipt': str(WORK / 'checks/target-attempt-2/receipt.json')},
            'focusedIsSuiteSubset': True,
            'suiteCountsCombined': False,
            'independentRouteContractCases': 11,
            'baseline': {'passed': 7, 'failed': 4},
            'sourceReviewPassed': 9,
            'independentCheckReadbackPassed': 6,
            'strictTypescriptExitCode': 0,
            'buildExitCode': 0,
            'buildReceipt': str(WORK / 'checks/build-attempt-1/receipt.json'),
            'pythonFullSuiteRerunThisRound': False,
            'currentFullStandaloneReleaseCertified': False,
        },
        'authoring': {
            'baseModules': 17,
            'transparentStartingGraphs': 3,
            'currentBrowserGraph': {'nodes': 5, 'edges': 5,
                                   'description': 'Input A/B → Add → Concat → Output'},
            'currentNativeActions': ['five port-button connections',
                                     'Add right/left/up/down16', 'pan right/left/up/down40',
                                     'undo/redo', 'save/reopen draft', 'static source generation'],
            'observedPriorCrossing614220Resolved': True,
            'draftIdentityAndSourceFactsPreserved': True,
            'currentMergeManagedModelOpened': False,
            'currentMergePublicationExported': False,
            'savedDraftId': 'draft-7c9ff26a-8ab1-4d90-8bb7-a65e26728a7f',
            'savedDraftRevision': 33,
            'savedDraftStorageRevision': 1,
            'staticGeneratedSourceBytes': 530,
            'independentPublicGeometryCasesPassed': 11,
            'currentPerModuleBrowserCertification': False,
            'runtimeOrTrainingCertification': False,
            'humanNoviceCertification': False,
            'priorPresetUiEvidence': 'MLP/residual click and CNN drag are retained at the ye build stage; not recertified by current route evidence.',
        },
        'routeBounds': {
            'nodes': 24, 'edges': 64, 'gridCells': 16000,
            'expandedStatesPerSearch': 64000, 'searches': 8,
            'clearanceChecks': 250000, 'conflictChecks': 100000,
            'coordinateDecimals': 2, 'independentEndpointTolerance': 0.025,
            'onExhaustion': 'retain prior visible routes',
            'sharedSceneCanvasExportRouterChangedThisRound': False,
            'arbitraryCrossingFreeOrMinimumBendGuaranteed': False,
        },
        'browser': {
            'browser': '2', 'tab': '60', 'url': 'http://127.0.0.1:40875/',
            'manifest': str(WORK / 'browser-attempt-2/manifest.json'),
            'records': 60, 'jpegCount': 14,
            'pixelVerdict': 'partial-visual-pass-with-clear-overview',
            'fourNodeMovePixelEvidence': True,
            'wholeNetworkHorizontalPanPixelsCertified': False,
            '100PercentRasterPairCertified': False,
            'fullAestheticsCertified': False,
            'rawAttempt1FrozenBeforeAllFiles': False,
            'rawAttempt2': 'exact copy of 58 initially listed files plus two supplemental clear-frame files; now frozen',
        },
        'aiReview': {
            'roles': ['independent route contract/source/checks', 'actual JPEG pixels',
                      'performance capability/next-step audit', 'saved draft/generated source',
                      'novice module/preset scope'],
            'reviewerRoleCount': 5,
            'nativeOperator': 'root through CUA',
            'rolesAreHumanParticipants': False,
        },
        'humanResearch': {'preparedForCurrentBuild': False, 'verifiedForCurrentBuild': False,
                          'assigned': 0, 'collected': 0, 'researchers': 0,
                          'aiCountedAsHuman': False},
        'performance': {
            'currentStudioAbMeasured': False,
            'threeReplicateMatrixComplete': False,
            'presentedFpsCertified': False,
            'actualHostForegroundCertified': False,
            'currentBrowserTraceCdpAvailable': False,
            'audit': 'docs/evidence/m4-performance-next-audit-attempt-1/receipt.json',
            'scope': 'Older controls show alternating callback intervals; callbacks do not certify frame presentation or product/background-throttling causation.',
        },
        'openItems': [
            'long exterior A→Concat.b route and complex CNN return routes',
            'small port text/targets at fit; novice parameter and declared-shape guidance',
            'only three starting graphs; broader module/preset coverage needs independent contracts',
            '100-percent screenshot/state pairing and whole-network horizontal pan coverage',
            'arbitrary layouts, imported Canvas/Transformer routing and global publication aesthetics',
            'stale pending notice after Escape and arbitrary label hit width',
            'held-pointer cancellation and expansion screen-anchor evidence',
            'width4 monochrome role dash gaps and actual physical-size publication review',
            'matched Studio A/B, three repeats and legal presentation trace',
            'real researcher tasks remain zero; AI simulation cannot certify this gate',
        ],
        'preservedCurrentFailures': [
            'first independent fixture observer overstrict tiny rounding seam then corrected',
            'initial target test attempt and witness-reader failure retained',
            'merge-100-local pixels56/DOM100 and reopened-settled pixels100/DOM56',
            'old final-fit screenshot still contains generated-source modal',
            'horizontal pan endpoint cropping',
            'initial seal1/current-doc and schema13 status inconsistency, archived before correction',
            'doc correction attempts1/2 retain stale intermediate current-file claims',
        ],
        'historicalStatus': binding('docs/evidence/m4-human-review-handoff-status.json'),
        'replacedFollowupStatus': prior13,
        'historicalScope': 'schema12 retains ye-stage tests/browser/preset and earlier stages; schema13 is archived as an intermediate shallow-clone result. Neither is current BSA5 certification.',
        'evidenceRefs': [binding(r) for r in refs],
    }
    dest = ROOT / 'docs/evidence/m4-human-review-handoff-status-followup.json'
    dest.write_text(json.dumps(status, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(binding(dest.relative_to(ROOT)), ensure_ascii=False))


if __name__ == '__main__':
    main()
