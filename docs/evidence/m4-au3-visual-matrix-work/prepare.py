from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import os
import subprocess

ROOT = Path(__file__).resolve().parents[3]
WORK = Path(__file__).resolve().parent
CORE = ROOT / 'docs/evidence/visual-golds-au3-matrix'
MATRIX = ROOT / '.archcanvas/browser-visual-matrix-au3'
PYTHON = ROOT / '.venv/bin/python'
NODEBIN = Path('/home/fzg/.nvm/versions/node/v24.19.0/bin')


def bind(path):
    raw = path.read_bytes()
    return {'path': str(path.relative_to(ROOT)), 'bytes': len(raw),
            'sha256': hashlib.sha256(raw).hexdigest()}


def main():
    assert not CORE.exists() and not MATRIX.exists()
    inputs = [p for directory in ['studio/src', 'studio/dist', 'src', 'fixtures']
              for p in (ROOT / directory).rglob('*')
              if p.is_file() and '__pycache__' not in p.parts and
              p.suffix in ('.ts', '.tsx', '.css', '.html', '.js', '.py')]
    inputs += [ROOT / 'scripts' / name for name in
               ['check_visual_golds.py', 'browser_visual_matrix.py',
                'browser_visual_core.mjs', 'prepare_hierarchy_matrix_capture.py']]
    before = [bind(p) for p in sorted(inputs)]
    env = os.environ.copy()
    env['PATH'] = str(NODEBIN) + os.pathsep + env.get('PATH', '')
    commands = [
        [str(PYTHON), '-B', 'scripts/check_visual_golds.py', '--output', str(CORE)],
        [str(PYTHON), '-B', 'scripts/browser_visual_matrix.py', 'prepare',
         '--core-dir', str(CORE), '--output', str(MATRIX)],
        [str(PYTHON), '-B', 'scripts/browser_visual_matrix.py', 'verify',
         '--matrix', str(MATRIX)]]
    runs = []
    for index, argv in enumerate(commands, 1):
        prefix = WORK / f'prepare-command-{index}'
        start = datetime.now(timezone.utc).isoformat()
        print(f'Running preparation command {index}', flush=True)
        with prefix.with_suffix('.stdout.log').open('xb') as out, \
                prefix.with_suffix('.stderr.log').open('xb') as err:
            process = subprocess.run(argv, cwd=ROOT, env=env, stdout=out, stderr=err)
        row = {'argv': argv, 'cwd': str(ROOT), 'startedAt': start,
               'finishedAt': datetime.now(timezone.utc).isoformat(),
               'exitCode': process.returncode,
               'logs': [bind(prefix.with_suffix('.stdout.log')),
                        bind(prefix.with_suffix('.stderr.log'))]}
        runs.append(row)
        with prefix.with_suffix('.json').open('x') as stream:
            stream.write(json.dumps(row, ensure_ascii=False, indent=2) + '\n')
        if process.returncode:
            raise RuntimeError(f'Preparation command {index} failed; original logs retained')
    after = [bind(p) for p in sorted(inputs)]
    assert before == after
    report = json.loads((CORE / 'visual-gold-report.json').read_text())
    spec = json.loads((MATRIX / 'spec.json').read_text())
    assert len(report['variants']) == 36 and len(spec['frontiers']) == 9
    assert report['geometryPassed'] and report['spatialCorePassed']
    assert spec['expectedBaselineCount'] == 36
    value = {'schemaVersion': 1, 'scope': 'Current au3 static core candidates and immutable 36-case matrix preparation only; no browser or human captures implied.',
             'runs': runs, 'sourceAndBuildBeforeAfterExact': True,
             'inputBindings': before, 'afterBindings': after,
             'coreReport': bind(CORE / 'visual-gold-report.json'),
             'matrixSpec': bind(MATRIX / 'spec.json'),
             'modelExecuted': False, 'dependenciesInstalled': False,
             'browserCasesCollected': 0, 'humans': 0,
             'nextPhaseStarted': False, 'phaseStatus': 'partial'}
    with (WORK / 'preparation-receipt.json').open('x') as stream:
        stream.write(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'preparation': bind(WORK / 'preparation-receipt.json'),
                      'variants': len(spec['variants']), 'frontiers': len(spec['frontiers'])}), flush=True)


if __name__ == '__main__':
    main()
