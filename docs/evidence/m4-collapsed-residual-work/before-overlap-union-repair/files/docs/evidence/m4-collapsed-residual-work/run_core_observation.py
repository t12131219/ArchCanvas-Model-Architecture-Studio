"""Bind trusted core observations to their actual inputs and infrastructure."""
from pathlib import Path
import datetime
import hashlib
import json
import os
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
WORK = Path(__file__).resolve().parent
NODE = Path('/home/fzg/.nvm/versions/node/v24.19.0/bin/node')


def binding(path):
    assert path.is_file() and not path.is_symlink(), path
    data = path.read_bytes()
    return {'path': str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path),
            'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}


def sources():
    paths = set((ROOT / 'studio/src/core').rglob('*.ts'))
    paths |= set((WORK / 'browser').glob('cnn-level*-*/document.json'))
    paths |= {WORK / 'observe_core.ts', Path(__file__).resolve()}
    assert len(list((WORK / 'browser').glob('cnn-level*-*/document.json'))) == 12
    return paths


def main():
    directory = WORK / 'core-observation-run-attempt-1'
    directory.mkdir(exist_ok=False)
    paths = sources()
    before = [binding(path) for path in sorted(paths)]
    infrastructure = [binding(NODE), binding(Path(__file__).resolve())]
    argv = [str(NODE), '--experimental-strip-types', str(WORK / 'observe_core.ts')]
    environment = dict(os.environ)
    environment['PATH'] = str(NODE.parent) + os.pathsep + environment.get('PATH', '')
    started = datetime.datetime.now(datetime.timezone.utc).isoformat()
    run = subprocess.run(argv, cwd=ROOT, env=environment, capture_output=True)
    for name, data in [('stdout.txt', run.stdout), ('stderr.txt', run.stderr)]:
        with (directory / name).open('xb') as output:
            output.write(data)
    after = [binding(path) for path in sorted(paths)]
    exact = before == after and paths == sources()
    receipt = {
        'protocol': 'archcanvas-collapsed-residual-core-observation-run/1',
        'argv': argv, 'cwd': str(ROOT), 'startedAt': started,
        'finishedAt': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'exitCode': run.returncode, 'sourceBeforeAfterExact': exact,
        'inputsBefore': before, 'inputsAfter': after, 'infrastructure': infrastructure,
        'logs': [binding(directory / name) for name in ['stdout.txt', 'stderr.txt']],
        'outputs': [binding(path) for path in sorted((WORK / 'core-observation').rglob('*')) if path.is_file()],
        'dependenciesInstalled': False, 'modelsExecuted': False,
        'scope': 'Product renderer observations only; independent acceptance remains separate.',
    }
    with (directory / 'receipt.json').open('x') as output:
        json.dump(receipt, output, ensure_ascii=False, indent=2)
        output.write('\n')
    print(json.dumps({'receipt': binding(directory / 'receipt.json'),
                      'exitCode': run.returncode, 'sourceBeforeAfterExact': exact}))
    sys.exit(run.returncode if run.returncode else (0 if exact else 3))


if __name__ == '__main__':
    main()
