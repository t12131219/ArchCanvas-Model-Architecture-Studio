"""Close independently checked au3 evidence with hash-only final input readback."""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import hashlib
import json
import traceback

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
CACHE = {}


def read(path):
    path = Path(path).absolute()
    raw = path.read_bytes()
    assert path not in CACHE or CACHE[path] == raw, f'Input changed during readback: {path}'
    CACHE[path] = raw
    return raw


def binding(path, raw):
    return {'path': str(path.relative_to(ROOT)), 'bytes': len(raw),
            'sha256': hashlib.sha256(raw).hexdigest()}


def verify(record):
    path = ROOT / record['path']
    raw = read(path)
    assert len(raw) == record['bytes'] and hashlib.sha256(raw).hexdigest() == record['sha256'], record['path']
    return raw


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--label', required=True)
    parser.add_argument('--matrix-report', required=True, type=Path)
    args = parser.parse_args()
    destination = OUT / args.label
    assert not destination.exists() and '/' not in args.label and args.label not in ('.', '..')
    source = read(Path(__file__))
    result = {'protocol': 'archcanvas-au3-independent-final-readback/1',
              'startedAt': datetime.now(timezone.utc).isoformat(),
              'testsRun': False, 'buildRun': False, 'modelsRun': False, 'browserOperated': False,
              'imageDecodedAgain': False, 'rendererReexecuted': False,
              'humanAcceptanceCertified': False, 'pixelMatchingCertified': False,
              'performanceCertified': False, 'auditorSource': binding(Path(__file__).absolute(), source)}
    try:
        reports = [args.matrix_report.absolute()]
        reports += [OUT / 'gestures' / name / 'report.json' for name in (
            'residual-cnn-attempt-1', 'mlp-attempt-1', 'transformer-attempt-1',
            'residual-cnn-persistence-attempt-1', 'mlp-persistence-attempt-1', 'transformer-persistence-attempt-1')]
        unique_inputs, audits = {}, []
        for path in reports:
            raw = read(path)
            report = json.loads(raw)
            assert report['status'] == 'passed-with-stated-scope' and report['inputsUnchanged']
            assert report['inputsBefore'] == report['inputsAfter']
            assert read(path.parent / 'auditor-source.py') == verify(report['auditorSource'])
            for record in report['inputsBefore']:
                assert record['path'] not in unique_inputs or unique_inputs[record['path']] == record
                unique_inputs[record['path']] = record
                verify(record)
            audits.append({'report': binding(path, raw), 'status': report['status'],
                           'inputBindingsRechecked': len(report['inputsBefore'])})
        matrix = json.loads(read(reports[0]))
        assert matrix['previouslyValidatedCases'] == 25 and matrix['newlyValidatedCases'] == 14
        assert matrix['boundCasesChecked'] == matrix['collected']['captures'] == 39
        assert matrix['collected']['baselineVariants'] == 36
        assert matrix['collected']['artifactBindings'] == 234
        result['matrix'] = {'cases': 39, 'baselineVariants': 36, 'editedModels': matrix['collected']['editedModels'],
                            'artifactBindings': 234, 'priorCasesReusedWithoutCoreOrImageRepeat': 25,
                            'newCasesChecked': 14, 'staticRecomputed': matrix['staticRecomputed'],
                            'authorizedScreenReceiptHashTransitions': len(matrix['authorizedScreenReceiptHashTransitions']),
                            'humanAcceptanceCertified': False, 'artifactCoverage': 'complete'}
        result['audits'] = audits
        result['uniqueCheckedReportInputs'] = len(unique_inputs)
        result['scopeNotes'] = [
            'No renderer/model/product execution, browser operation or repeated old screenshot decoding.',
            'The two screen-receipt hash fields alone have explicitly disclosed authorized stamping transitions; exact previous unstamped bytes remain bound.',
            'MLP original right screenshot is an intermediate state and does not certify the public JSON endpoint pixel; geometric/history reports performed no pixel matching.',
            'CNN first reopen read returned null during loading and is preserved as failed attempt, not counted as successful reopen.',
            'MLP save DOM was busy; successful persistence is supported by saved envelope and later reopened UI/public SVG.',
            'Reopen fit camera changes are allowed; disabled undo/redo controls are public history evidence, not an internal history-state inspection.',
            'Transformer edge69 elbow stability and all aesthetics, current physical font/environment, event provenance and timing remain outside the geometry/hash contract.'
        ]
        # Bind all supplemental files, including failed reviewer attempts and exact
        # old auditor snapshots. This preserves their history without repeating audits.
        supplemental = []
        for path in sorted(OUT.rglob('*')):
            if path.is_file():
                supplemental.append(binding(path, read(path)))
        result['supplementalFiles'] = supplemental
        result['status'] = 'passed-with-stated-scope'
    except Exception as error:
        result['status'] = 'audit-failed'
        result['error'] = str(error)
        result['traceback'] = traceback.format_exc()
    before = [binding(path, raw) for path, raw in sorted(CACHE.items())]
    after = [binding(path, path.read_bytes()) for path in sorted(CACHE)]
    result.update({'inputsBefore': before, 'inputsAfter': after, 'inputsUnchanged': before == after,
                   'finishedAt': datetime.now(timezone.utc).isoformat()})
    if before != after:
        result['status'] = 'audit-failed-input-changed'
    destination.mkdir()
    (destination / 'auditor-source.py').open('xb').write(source)
    raw = (json.dumps(result, ensure_ascii=False, indent=2) + '\n').encode()
    (destination / 'receipt.json').open('xb').write(raw)
    print(json.dumps({'receipt': binding(destination / 'receipt.json', raw), 'status': result['status'],
                      'inputs': len(CACHE), 'unchanged': before == after, 'error': result.get('error')}, ensure_ascii=False))
    return 0 if result['status'] == 'passed-with-stated-scope' else 1


if __name__ == '__main__':
    raise SystemExit(main())
