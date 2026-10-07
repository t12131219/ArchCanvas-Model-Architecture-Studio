"""Seal actual CUA observations; do not infer pixels or performance from DOM."""
from pathlib import Path
import hashlib
import json
import datetime

ROOT = Path(__file__).resolve().parents[3]
STAGE = Path(__file__).resolve().parent
OUT = STAGE / 'final-browser'
OUT.mkdir(exist_ok=False)

def bound(path):
    raw = path.read_bytes()
    return {'path': str(path.relative_to(ROOT)), 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}

check_path = STAGE / 'checks-final-attempt-4/receipt.json'
checks = json.loads(check_path.read_text())
for item in checks['inputs'] + checks['build'] + checks['publicationInputs']:
    actual = bound(ROOT / item['path'])
    assert all(actual[key] == item[key] for key in ('path', 'bytes', 'sha256')), item['path']
assert checks['inputsUnchanged'] and checks['publicationInputsUnchanged']
assert all(item['exitCode'] == 0 for item in checks['checks'])

gesture = STAGE / 'browser-gesture-final/report.json'
exports = STAGE / 'browser-export-final/report.json'
gap = STAGE / 'browser-caption-investigation/report.json'
research = STAGE / 'research-export-final-preparation/report.json'
for path in (gesture, exports, gap, research):
    assert path.is_file(), path

receipt = {
    'schema': 'archcanvas-caption-route-browser/1',
    'createdUtc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
    'url': 'http://127.0.0.1:42937/',
    'build': 'index-Divs1MJA.js',
    'checks': str(check_path.relative_to(ROOT)),
    'studioTests': 389, 'publicationTests': 11,
    'sourceBuildBindings': 108, 'publicationInputs': 11,
    'documentId': 'canvas-architecture-model.Transformer-01ac6cd61f05-b0bd5bf0',
    'initialDocumentRevision': 0, 'finalDocumentRevision': 20,
    'initialStorageCounter': 1, 'finalStorageCounter': 3,
    'finalStoredDocumentChangedFields': ['revision'],
    'gestureReview': str(gesture.relative_to(ROOT)),
    'exportReview': str(exports.relative_to(ROOT)),
    'memoryLabelInvestigation': str(gap.relative_to(ROOT)),
    'researchReadiness': str(research.relative_to(ROOT)),
    'cameraDirections': ['right', 'down', 'left', 'up'],
    'cameraDeltaPixels': 32,
    'selectedLeafNodeDirections': ['right', 'down', 'left', 'up'],
    'leafNodeDeltaWorld': 32,
    'undoRedoAndBaselineRecoveryObserved': True,
    'sourceIrCanonicalBindingsChanged': False,
    'currentCaption': {'x': 288.5, 'y': 484.1, 'nominalOwnedGuideLengthWorld': 29,
                       'guideHasArrow': False, 'canonicalBinding': False},
    'personallyViewedRootScreenshots': [
        {'capture': '04-divs-100-settled', 'observation': '100% pixel control agrees with DOM; memory and thin guide visible'},
        {'capture': '21-up-redo-settled', 'observation': 'leaf up 32; memory caption moves left/down; guide remains visible'},
        {'capture': '22-encoder-down-association', 'observation': 'encoder down 24; old rule removes memory text and guide'},
        {'capture': '31-monochrome-settled', 'observation': 'black/white screen overview shows memory guide and role patterns'},
        {'capture': '39-final-100-settled', 'observation': '100% pixel control agrees; final color baseline restored and saved revision20'},
        {'capture': '../browser-export-final/detail-pdf.png', 'observation': 'actual generated PDF rendered with system Poppler; memory text and unarrowed guide visible'},
    ],
    'knownObservationFailuresPreserved': [
        '03-divs-100-first has 100% DOM but stale 68% screenshot; superseded by 04',
        'camera batch timed out after files05-07; actual recovered camera at baseline before capture08',
        'first zoom locator error and first monochrome selector error retained',
        '27 export generating state did not prove success; 28 actual publication attribute rejection retained',
        'export first unavailable controls were observed before service capability settled',
    ],
    'actualUiExports': [
        {'id': 'ea42cd05c8a344348ed5751da24276ec', 'format': 'svg', 'scope': 'whole', 'widthMm': 180, 'revision': 20},
        {'id': 'a0a6f9b4d5b74acfa9c9b032175c14ca', 'format': 'svg', 'scope': 'root-detail', 'widthMm': 180, 'revision': 20},
        {'id': 'a6a82fd6101e451ab7e09caec69e035b', 'format': 'pdf', 'scope': 'root-detail', 'widthMm': 180, 'revision': 20},
    ],
    'roundedUiPreflightPt': {'whole180Min': 6.60, 'whole85Min': 3.12, 'detail180Min': 7.42},
    'unresolvedExperienceGap': {'encoderDownWorld': 24, 'memoryLabelAndGuideDisappear': True,
                               'ownedTensorEdgeStillPresent': True, 'undoRestores': True,
                               'existingThreshold': 'default memory label only when abs(source.y-target.y)<15'},
    'cameraPreservedAfterReload': False,
    'continuousInputPerformanceCertified': False,
    'presentedFpsCertified': False, 'allModelVisualQualityApproved': False,
    'humanParticipants': 0, 'physicalPublicationApproved': False,
    'scope': 'Bounded current figure gestures and export integration. Three earlier AI roles remain simulated users; reviewers are not additional users. No model execution or semantic writeback.',
}
(OUT / 'receipt.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + '\n')
(OUT / 'README.md').write_text('''# Current browser and export receipt

This receipt binds actual CUA input, DOM, SVG, screenshots, saved envelopes and the final publication repair. Read the independent gesture/export reports for their observation limits. Stored geometry and model facts were restored; only document revision changed. Camera reset on reopen is observed.

The Encoder +24 move still hides the default memory caption under an existing coordinate threshold. This is an unresolved experience gap, not successful caption reassociation. The publication rejection from the first real UI export is preserved; repaired whole/detail SVG and detail PDF were then actually generated.

Only explicitly personally viewed screenshots are described as pixel observations. Same-name DOM and JPEG may represent different instants. Discrete CUA drags do not establish continuous interaction latency, presented FPS, global routing aesthetics or human publication approval. M4 remains partial; human participants remain zero.
''')
external = sorted({Path(__file__), check_path, gesture, exports, gap, research,
                   STAGE / 'service-continuation/export-restart-receipt.json',
                   *[p for p in (STAGE / 'browser').rglob('*') if p.is_file()]})
manifest = {'schema': 'archcanvas-browser-evidence-manifest/1',
            'artifacts': [bound(p) for p in sorted(OUT.rglob('*')) if p.is_file()],
            'externalInputs': [bound(p) for p in external]}
(OUT / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
for item in manifest['artifacts'] + manifest['externalInputs']:
    assert bound(ROOT / item['path']) == item
print(json.dumps({'receipt': str((OUT / 'receipt.json').relative_to(ROOT)),
                  'manifest': bound(OUT / 'manifest.json'),
                  'bindings': len(manifest['artifacts']) + len(manifest['externalInputs'])}, indent=2))
