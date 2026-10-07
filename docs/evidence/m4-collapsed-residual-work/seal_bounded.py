"""Freeze the completed, bounded renderer work without rewriting old evidence."""
from pathlib import Path
import datetime
import hashlib
import json

ROOT = Path(__file__).resolve().parents[3]
WORK = Path(__file__).resolve().parent
OUTPUT = ROOT / 'docs/evidence/m4-collapsed-residual-verification-sealed.json'


def binding(path):
    assert path.is_file() and not path.is_symlink(), path
    data = path.read_bytes()
    return {'path': str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path),
            'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}


def matches(path, expected):
    value = binding(path)
    return value['bytes'] == expected['bytes'] and value['sha256'] == expected['sha256']


def main():
    assert not OUTPUT.exists(), 'Seal is create-only'
    prior_path = ROOT / 'docs/evidence/m4-au3-current-matrix-verification-sealed.json'
    prior = json.loads(prior_path.read_text())
    archive = ROOT / 'docs/evidence/before-m4-collapsed-residual'
    manifest = json.loads((archive / 'manifest.json').read_text())
    mapping = {row['sourcePath']: archive / row['archivePath'] for row in manifest['mapping']}
    supplement = WORK / 'before-current-evidence-doc-update-attempt-2'
    extra = json.loads((supplement / 'manifest.json').read_text())
    mapping.update({row['path']: ROOT / row['copy'] for row in extra['files']})
    resolutions = []
    for row in prior['bindings']:
        direct = Path(row['path']) if Path(row['path']).is_absolute() else ROOT / row['path']
        if direct.is_file() and matches(direct, row):
            chosen = direct
        else:
            chosen = mapping.get(row['path'])
            assert chosen is not None and matches(chosen, row), row['path']
        resolutions.append({'originalPath': row['path'], 'resolved': binding(chosen)})
    # This verifies preservation of old bytes only, never new-build browser
    # coverage, old standalone checks, or a re-run of old independent review.
    materials = set(path for path in WORK.rglob('*') if path.is_file())
    materials |= set(path for path in (ROOT / 'skills/archcanvas').rglob('*') if path.is_file())
    materials |= set(path for path in (ROOT / 'studio/src').rglob('*') if path.is_file())
    materials |= set((ROOT / 'studio/tests').glob('*.ts'))
    materials |= set(path for path in (ROOT / 'studio/dist').rglob('*') if path.is_file())
    materials |= {ROOT / name for name in [
        'README.md', 'AGENTS.md', 'docs/m4-completion.md', 'docs/m4-human-review-handoff.md',
        'docs/m4-collapsed-residual.md', 'docs/evidence/README.md',
        'docs/evidence/m4-human-review-handoff-status.json', 'studio/package.json',
        'studio/package-lock.json', 'studio/tsconfig.json']}
    before = [binding(path) for path in sorted(materials)]
    checks = {}
    for name in ['target-attempt-3', 'suite-attempt-3', 'build-attempt-2']:
        path = WORK / 'checks' / name / 'receipt.json'
        receipt = json.loads(path.read_text())
        assert receipt['exitCode'] == 0 and receipt['sourceBeforeAfterExact']
        # Helpers/baselines may be snapshotted later; source/test inputs that
        # these commands actually consumed must still have those exact bytes.
        for row in receipt['inputsBefore'] + receipt['infrastructure'] + receipt['logs'] + receipt.get('builtFiles', []):
            candidate = Path(row['path']) if Path(row['path']).is_absolute() else ROOT / row['path']
            assert matches(candidate, row), row['path']
        checks[name] = binding(path)
    collection_path = WORK / 'browser-after-union-manifest.json'
    collection = json.loads(collection_path.read_text())
    assert len(collection['cases']) == 12 and collection['fitCount'] == 12 and collection['localImageCount'] == 9
    for row in collection['files']:
        assert matches(ROOT / row['path'], row), row['path']
    acceptance_path = WORK / 'acceptance/browser-readback-attempt-3/report.json'
    acceptance = json.loads(acceptance_path.read_text())
    assert acceptance['verdict'] == 'pass-bounded-artifact-canonical-geometry-export-save-readback'
    assert len(acceptance['cases']) == 12 and acceptance['allInputsReadTwiceExact']
    closure_path = WORK / 'acceptance/browser-readback-attempt-3/final-readback-supplement.json'
    closure = json.loads(closure_path.read_text())
    assert closure['inputsUnchanged'] and closure['inputCount'] == 890
    for row in closure['inputsAfter']:
        candidate = Path(row['path']) if Path(row['path']).is_absolute() else ROOT / row['path']
        assert matches(candidate, row), row['path']
    pixel_path = WORK / 'pixel-after-union-attempt-1/receipt.json'
    pixel = json.loads(pixel_path.read_text())
    assert pixel['status'] == 'bounded-ai-pixel-review-complete-with-retained-findings'
    assert pixel['AIOnly'] and pixel['humanParticipantsAdded'] == 0
    assert pixel['visibleStateMatchedOriginals'] == 21
    pixel_readback = json.loads((WORK / 'pixel-after-union-attempt-1/final-readback.json').read_text())
    assert pixel_readback['unchangedInputCount'] == 151 and pixel_readback['actualInventoryExact']
    for row in json.loads((WORK / 'pixel-after-union-attempt-1/inputs-before.json').read_text())['inputs']:
        candidate = Path(row['path']) if Path(row['path']).is_absolute() else ROOT / row['path']
        assert matches(candidate, row), row['path']
    skill_path = WORK / 'skill-validation-attempt-1/receipt.json'
    skill = json.loads(skill_path.read_text())
    assert skill['exitCode'] == 0 and skill['inputsExact']
    for row in skill['inputsAfter']:
        assert matches(ROOT / row['path'], row), row['path']
    after = [binding(path) for path in sorted(materials)]
    assert before == after
    value = {
        'protocol': 'archcanvas-collapsed-residual-bounded-seal/1',
        'sealedAt': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'state': 'progress', 'm4': 'partial', 'm5Started': False,
        'productionBuild': 'index-Dzp9we5t.js', 'productionCss': 'index-B6WbMowt.css',
        'tests': {'target': 24, 'suite': 203, 'failed': 0, 'skipped': 0, 'strictBuildExitCode': 0},
        'checks': checks, 'browserCollection': binding(collection_path),
        'independentAcceptance': binding(acceptance_path), 'independentClosure': binding(closure_path),
        'aiPixelReview': binding(pixel_path),
        'hostSkillValidation': binding(skill_path),
        'retainedVisualFindings': 'Monochrome role ambiguity, expanded title-boundary routes, long L2 page, five fit-only cases, and Repeat count text publication placement +30 units versus interaction. No global visual acceptance claimed.',
        'scope': 'Current collapsed-residual implementation, independent regression and bounded CNN12 artifact/AI image review. Consult the bound final reports for conclusions and limits. File hashes do not certify visual quality or performance.',
        'preservedPriorSeal': binding(prior_path), 'priorByteResolutions': resolutions,
        'priorBytePreservationOnly': True, 'currentInputBytesExact': True,
        'bindingCount': len(before), 'bindings': before,
        'humans': 0, 'dependenciesInstalled': False, 'userModelsExecuted': False,
        'presentedPerformanceCertified': False, 'physicalPublicationCertified': False,
        'globalRouteBeautyCertified': False, 'full39CaseCurrentBrowserCoverage': False,
        'limits': 'Old au3 four-direction/authoring/performance evidence keeps its own version. Current CNN12 evidence does not certify human usability, all models/modules, held cancellation, nonempty-pin native protection, fonts, hardware or full model numerical correctness.',
    }
    with OUTPUT.open('x') as output:
        json.dump(value, output, ensure_ascii=False, indent=2)
        output.write('\n')
    print(json.dumps({'seal': binding(OUTPUT), 'currentBindings': len(before),
                      'priorByteBindingsPreserved': len(resolutions)}))


if __name__ == '__main__':
    main()
