"""Data-only closure: new manifest, second local views and reopen export copies."""
from pathlib import Path
from datetime import datetime, timezone
import json
import hashlib
import traceback
import audit as reviewer

ROOT, WORK, OUT = reviewer.ROOT, reviewer.WORK, reviewer.OUT
FIRST = {}


def read(path):
    path = Path(path).absolute()
    assert path.is_file() and not path.is_symlink(), path
    raw = path.read_bytes()
    if path in FIRST:
        assert FIRST[path] == raw, f'Input changed {path}'
    FIRST[path] = raw
    return raw


def bind(path, raw=None):
    path = Path(path).absolute()
    raw = read(path) if raw is None else raw
    return {'path': str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path),
            'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def verify(row):
    path = Path(row['path'])
    if not path.is_absolute():
        path = ROOT / path
    actual = bind(path)
    assert actual['bytes'] == row['bytes'] and actual['sha256'] == row['sha256'], row
    return path


def main():
    target = OUT / 'final-readback-supplement.json'
    assert not target.exists()
    result = {'protocol': 'archcanvas-after-union-browser-readback-supplement/1',
              'startedAt': datetime.now(timezone.utc).isoformat(), 'verdict': 'incomplete',
              'productExecutedByReviewer': False, 'browserOperatedByReviewer': False,
              'testsRun': False, 'buildRun': False, 'modelsRun': False,
              'existingReportOrInputsEdited': False, 'pixelAcceptanceCertified': False,
              'limits': ['Service lifecycle receipt is retrospective, not independently reconstructed raw startup stdout.',
                         'No current-process liveness, resolved font, physical publication, presented performance or human usability claim.',
                         'JPEGs are byte bound and public state bracketed; pixels are assessed by separate visual reviewer.']}
    try:
        report_raw = read(OUT / 'report.json')
        assert hashlib.sha256(report_raw).hexdigest() == '60812423d1e3dbd10d7e979e73d001a7bb8e0e62ffcb5494c551ec58612c72d6'
        report = json.loads(report_raw)
        assert report['verdict'].startswith('pass-') and len(report['cases']) == 12 and report['allInputsReadTwiceExact']
        for row in report['inputsAfter']:
            verify(row)
        result['boundedReport'] = bind(OUT / 'report.json')
        result['boundedReportInputCountStillExact'] = len(report['inputsAfter'])
        manifest_path = WORK / 'browser-after-union-manifest.json'
        assert bind(manifest_path)['sha256'] == 'eb4db4f30b0abbc80ec20a0ef0b63a6a69292f4bbbecbf364bf63f03a66e0b2f'
        manifest = json.loads(read(manifest_path))
        assert manifest['build'] == 'index-Dzp9we5t.js'
        cases = sorted(row['caseId'] for row in report['cases'])
        assert manifest['cases'] == cases and manifest['fitCount'] == 12 and manifest['localImageCount'] == 9
        paths = sorted(path for path in reviewer.BROWSER.rglob('*') if path.is_file())
        assert len(paths) == 128
        assert sorted(row['path'] for row in manifest['files']) == sorted(str(path.relative_to(ROOT)) for path in paths)
        for row in manifest['files']:
            verify(row)
        fit = sorted(reviewer.BROWSER.glob('*/fit.jpg'))
        local = sorted(reviewer.BROWSER.glob('*/local*.jpg'))
        assert len(fit) == 12 and len(local) == 9
        for path in fit + local:
            assert read(path).startswith(b'\xff\xd8')
        result['manifest'] = {'binding': bind(manifest_path), 'fileCount': 128,
                              'fitImages': [bind(path) for path in fit],
                              'localImages': [bind(path) for path in local],
                              'byteBindingsIndependentlyVerified': True}
        blocks = []
        for case_id in ('cnn-level2-paper-180', 'cnn-level2-monochrome-180'):
            directory = reviewer.BROWSER / case_id
            document = json.loads(read(directory / 'document.json'))
            scene = json.loads(read(reviewer.CORE / case_id / 'scene.json'))
            interactive = read(reviewer.CORE / case_id / 'interactive.svg')
            before = reviewer.public_observation(directory / 'local-block2-before.json', document, scene, interactive)
            after = reviewer.public_observation(directory / 'local-block2-after.json', document, scene, interactive)
            assert datetime.fromisoformat(before['capturedAt'].replace('Z', '+00:00')) <= datetime.fromisoformat(after['capturedAt'].replace('Z', '+00:00'))
            reviewer.exact(reviewer.without(before, ('capturedAt',)), reviewer.without(after, ('capturedAt',)),
                           'Second block local view bracketed by exact complete public state')
            reference = json.loads(read(directory / 'fit-before.json'))
            reviewer.exact(reviewer.without(before, ('capturedAt', 'paperTransform', 'zoom')),
                           reviewer.without(reference, ('capturedAt', 'paperTransform', 'zoom')),
                           'Second block view differs only in time/camera from already verified fit')
            blocks.append({'caseId': case_id, 'before': bind(directory / 'local-block2-before.json'),
                           'after': bind(directory / 'local-block2-after.json'),
                           'image': bind(directory / 'local-block2.jpg'), 'zoom': before['zoom'],
                           'paperTransform': before['paperTransform'], 'completeXmlAndMetadataExact': True})
        result['additionalSecondBlockLocalViews'] = blocks
        case_dir = reviewer.BROWSER / 'cnn-level0-paper-180'
        copy_dir = case_dir / 'reopen-export-files'
        scene = json.loads(read(reviewer.CORE / 'cnn-level0-paper-180/scene.json'))
        document = json.loads(read(case_dir / 'document.json'))
        publication = read(reviewer.CORE / 'cnn-level0-paper-180/publication.svg')
        reopened_record = next(row for row in report['cases'] if row['caseId'] == 'cnn-level0-paper-180')['reopenedExport']
        copied = reviewer.export_files(copy_dir, scene, publication, document, reopened_record['uuid'])
        result['actualReopenExportCopies'] = copied
        lifecycle_path = WORK / 'service-lifecycle-record-attempt-1/receipt.json'
        lifecycle = json.loads(read(lifecycle_path))
        for row in lifecycle['currentFiles']:
            verify(row)
        assert lifecycle['url'] == 'http://127.0.0.1:43725/' and lifecycle['execSession'] == 26316
        assert 'retrospective' in lifecycle['startupEvidenceLimit'] and 'not reconstructed raw stdout' in lifecycle['startupEvidenceLimit']
        result['serviceLifecycle'] = {'receipt': bind(lifecycle_path),
                                      'startupEvidenceLimit': lifecycle['startupEvidenceLimit'],
                                      'currentFilesVerified': lifecycle['currentFiles'],
                                      'scope': 'Historical tool response accounted for by root; this audit reads receipt/files, does not poll/reconstruct service.'}
        result['additionalHeightRoundtripExceptions'] = reviewer.HEIGHT_ROUNDTRIPS
        result['additionalChecks'] = reviewer.CHECKS
        result['verdict'] = 'pass-bounded-readback-with-complete-manifest-local-block2-and-reopen-copies'
    except Exception as error:
        result['verdict'] = 'fail-retained'
        result['failure'] = {'type': type(error).__name__, 'message': str(error), 'traceback': traceback.format_exc()}
    for path, raw in reviewer.CACHE.items():
        if path in FIRST:
            assert FIRST[path] == raw
        FIRST[path] = raw
    for name in ('supplement.py', 'audit.py', 'geometry.py', 'expected-final-build.json'):
        read(OUT / name)
    all_before = [bind(path, raw) for path, raw in sorted(FIRST.items())]
    all_after, changed = [], []
    for path, raw in sorted(FIRST.items()):
        actual = bind(path, path.read_bytes())
        all_after.append(actual)
        if actual != bind(path, raw):
            changed.append(str(path))
    result['inputsBefore'] = all_before
    result['inputsAfter'] = all_after
    result['inputsUnchanged'] = not changed
    result['inputCount'] = len(all_before)
    result['changedInputs'] = changed
    result['finishedAt'] = datetime.now(timezone.utc).isoformat()
    if changed:
        result['verdict'] = 'fail-input-mutation-retained'
    with target.open('x') as output:
        json.dump(result, output, ensure_ascii=False, indent=2)
        output.write('\n')
    print(json.dumps({'receipt': bind(target), 'verdict': result['verdict'],
                      'inputCount': len(all_before), 'inputsExact': not changed}, ensure_ascii=False))
    return 0 if result['verdict'].startswith('pass-') else 1


if __name__ == '__main__':
    raise SystemExit(main())
