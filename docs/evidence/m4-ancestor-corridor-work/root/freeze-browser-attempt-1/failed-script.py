"""Freeze bounded CUA observations; never turn AI observations into human gates."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json

ROOT = Path(__file__).resolve().parents[4]
WORK = ROOT / 'docs/evidence/m4-ancestor-corridor-work'
BROWSER = WORK / 'browser-final-attempt-1'


def binding(path):
    raw = path.read_bytes()
    return {'path': str(path.relative_to(ROOT)), 'bytes': len(raw),
            'sha256': hashlib.sha256(raw).hexdigest()}


def save(path, value):
    with path.open('x') as stream:
        stream.write(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def main():
    assert not (BROWSER / 'report.json').exists(), 'Never overwrite a frozen report'
    snapshots = BROWSER / 'session-snapshots'
    snapshots.mkdir(exist_ok=False)
    session = ROOT / '.archcanvas/m4-ancestor-corridor-session'
    copies = []
    # Test source/documents/exports only. Do not copy transaction approval keys.
    for name in ['documents', 'drafts', 'projects', 'exports']:
        for path in sorted((session / name).rglob('*')):
            if not path.is_file() or path.suffix in ('.pyc', '.pyo'):
                continue
            relative = path.relative_to(session)
            copy = snapshots / relative
            copy.parent.mkdir(parents=True, exist_ok=True)
            raw = path.read_bytes()
            with copy.open('xb') as stream:
                stream.write(raw)
            assert copy.read_bytes() == raw == path.read_bytes(), path
            copies.append({'original': binding(path), 'frozen': binding(copy)})
    processes = []
    for directory in sorted(Path('/proc').iterdir()):
        if not directory.name.isdigit():
            continue
        try:
            argv = [s.decode() for s in (directory / 'cmdline').read_bytes().split(b'\0') if s]
            if 'archcanvas_cli' not in argv or 'serve' not in argv or '8987' not in argv:
                continue
            state = next(line for line in (directory / 'status').read_text().splitlines()
                         if line.startswith('State:'))
            processes.append({'pid': int(directory.name), 'argv': argv,
                              'cwd': str((directory / 'cwd').resolve()), 'state': state})
        except (OSError, StopIteration, UnicodeDecodeError):
            continue
    assert len(processes) == 1, processes
    lifecycle = {'observedAt': datetime.now(timezone.utc).isoformat(),
                 'url': 'http://127.0.0.1:8987/', 'toolSessionId': 36749,
                 'processes': processes, 'state': 'running-at-readback',
                 'scope': 'Process snapshot and current public CUA page; no availability promise after host termination.',
                 'user8765Touched': False}
    save(BROWSER / 'service-lifecycle.json', lifecycle)
    raw_paths = sorted(p for p in BROWSER.rglob('*') if p.is_file())
    report = {
        'schemaVersion': 1, 'frozenAt': datetime.now(timezone.utc).isoformat(),
        'scope': 'AI-only root CUA retest on current au3/B6 build. One source-bound L3 figure/export and one fresh four-module authored workflow; not a new full visual matrix, performance trial or human publication review.',
        'url': 'http://127.0.0.1:8987/', 'browserId': '2', 'tabId': '54',
        'build': [binding(ROOT / 'studio/dist/assets/index-au3IB_0Q.js'),
                  binding(ROOT / 'studio/dist/assets/index-B6WbMowt.css'),
                  binding(ROOT / 'studio/dist/index.html')],
        'source': [binding(ROOT / 'studio/src/AuthoringStudio.css'),
                   binding(ROOT / 'studio/src/core/orthogonalRouter.ts'),
                   binding(ROOT / 'studio/src/core/scene.ts'),
                   binding(ROOT / 'studio/src/core/exportScene.ts')],
        'sourceBoundL3': {
            'documentId': 'canvas-architecture-model.Transformer-01ac6cd61f05-b0bd5bf0',
            'canvasRevision': 27, 'storageRevision': 1,
            'svgExportUuid': '72f21096acbc4dc1a3d98e1193baa8c9',
            'pdfExportUuid': '187559f6e5984e84bddbf16eff24a613',
            'independentReadback': binding(WORK / 'acceptance/browser-source-readback-attempt-1/final-readback.json'),
            'actualExportsBound': True, 'importedAliasSaveReopenRetested': False,
            'fitScreenshotScalePercent': 14, 'publicationCertified': False,
            'physicalSizeMm': [180, 605.611052],
            'excludedPreview': {'path': 'l3-export-preview.svg', 'reason': '211-byte 18x18 modal close icon; not a model preview.'}},
        'authoredWorkflow': {
            'draftId': 'draft-859cef62-6bbe-45c6-a166-b5f519d7e600',
            'draftRevision': 16, 'storageRevision': 1,
            'model': ['Input', 'Linear', 'ReLU', 'Output'],
            'nodes': 4, 'edges': 3, 'inputShapeDeclared': [1, 16],
            'inputDtypeDeclared': 'float32', 'linearInFeatures': 16, 'linearOutFeatures': 32,
            'roleTextClickObserved': True, 'nativeTextCenterClickObserved': True,
            'edgeUndoRedoObserved': True, 'draftSaveReopenObserved': True,
            'staticGeneratedSourceReviewObserved': True,
            'newManagedModelOpened': True, 'generatedCanvasSaveObserved': True,
            'modelExecuted': False, 'trainingRun': False,
            'freshImportedAliasMatrixCertified': False,
            'independentReadback': binding(WORK / 'acceptance/authored-browser-readback-attempt-1/final-readback.json')},
        'retainedNonSuccesses': [
            'First batched Linear/ReLU/Output role connection attempt left 4 nodes/1 edge (from-zero-complete.*); subsequent state-observed individual actions reached 3 edges. Cause not established.',
            'getAttribute(outerHTML) returned null and the write failed; a read-only DOM evaluate later captured the actual SVG. This was a collector failure, not a product result.',
            'Earlier fs/promises mkdirSync misuse was a collector failure; no product assertion derives from it.',
            'Sub-agent fresh-port-hit-attempt-1 could not inventory its browser; root CUA operated the actual current page separately.',
            'Default export selection produced PDF before explicit SVG selection; both actual UUIDs and receipts are retained.'
        ],
        'openGates': ['physical publication size and glyph/font/pixel review',
                      'current complete four-direction visual matrix',
                      'fixed-host input-to-presentation performance trials',
                      'real researcher five-task review'],
        'humans': 0, 'aiCountsAsHuman': False, 'phaseStatus': 'partial',
        'nextPhaseStarted': False, 'snapshotBindings': copies,
        'bindings': [binding(p) for p in raw_paths],
        'user8765Touched': False}
    save(BROWSER / 'report.json', report)
    print(json.dumps({'report': binding(BROWSER / 'report.json'),
                      'rawBindings': len(raw_paths), 'snapshots': len(copies),
                      'processes': len(processes)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
