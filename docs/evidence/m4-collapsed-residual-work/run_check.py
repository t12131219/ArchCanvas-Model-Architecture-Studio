"""Record a local Studio check without mutating or executing model source."""
from pathlib import Path
import argparse
import datetime
import hashlib
import json
import os
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
WORK = Path(__file__).resolve().parent
NODE = Path('/home/fzg/.nvm/versions/node/v24.19.0/bin/node')
NPM = NODE.parent.parent / 'lib/node_modules/npm/bin/npm-cli.js'


def binding(path):
    assert path.is_file() and not path.is_symlink(), path
    body = path.read_bytes()
    name = str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path)
    return {'path': name, 'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()}


def sources():
    paths = set((ROOT / 'studio/src').rglob('*.ts')) | set((ROOT / 'studio/src').rglob('*.tsx'))
    paths |= set((ROOT / 'studio/src').rglob('*.css')) | set((ROOT / 'studio/tests').rglob('*.ts'))
    paths |= {ROOT / 'studio/package.json', ROOT / 'studio/package-lock.json', ROOT / 'studio/tsconfig.json'}
    # Existing tests use explicit independent evidence oracles. Record all their
    # TS source inputs while keeping old evidence unchanged in place.
    paths |= set((ROOT / 'docs/evidence').glob('m4-*/**/*.ts'))
    paths |= set((WORK / 'acceptance/baseline').rglob('*'))
    paths |= {WORK / 'acceptance/acceptance-contract.json'}
    paths = {path for path in paths if path.is_file()}
    return paths


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('kind', choices=['target', 'suite', 'build'])
    parser.add_argument('--attempt', required=True)
    args = parser.parse_args()
    assert '/' not in args.attempt and '..' not in args.attempt
    directory = WORK / 'checks' / args.attempt
    directory.mkdir(parents=True, exist_ok=False)
    paths = sources()
    before = [binding(path) for path in sorted(paths)]
    infrastructure = [binding(path) for path in [NODE, NPM, Path(__file__).resolve()]]
    if args.kind == 'target':
        argv = [str(NODE), '--experimental-strip-types', '--test', '--test-isolation=none',
                'studio/tests/collapsed-residual-independent.test.ts']
    else:
        argv = [str(NODE), str(NPM), '--prefix', 'studio', *(['test'] if args.kind == 'suite' else ['run', 'build'])]
    environment = dict(os.environ)
    environment['PATH'] = str(NODE.parent) + os.pathsep + environment.get('PATH', '')
    started = datetime.datetime.now(datetime.timezone.utc).isoformat()
    run = subprocess.run(argv, cwd=ROOT, env=environment, capture_output=True)
    for name, body in [('stdout.txt', run.stdout), ('stderr.txt', run.stderr)]:
        with (directory / name).open('xb') as output:
            output.write(body)
    after = [binding(path) for path in sorted(paths)]
    exact = before == after and paths == sources()
    receipt = {
        'protocol': 'archcanvas-collapsed-residual-check/1', 'kind': args.kind,
        'argv': argv, 'cwd': str(ROOT), 'startedAt': started,
        'finishedAt': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'exitCode': run.returncode, 'sourceBeforeAfterExact': exact,
        'inputsBefore': before, 'inputsAfter': after, 'infrastructure': infrastructure,
        'inputsScope': 'Studio source/tests/config, evidence TS helpers, and this round independent acceptance contract/baseline. The initial target-attempt-1 omitted fixtures.ts; its limits and exact pre-repair source copy are retained separately.',
        'logs': [binding(directory / name) for name in ['stdout.txt', 'stderr.txt']],
        'dependenciesInstalled': False, 'modelsExecuted': False,
        'testCountScope': 'Actual stdout only; do not add prior or targeted counts to suite totals.',
    }
    if args.kind == 'build':
        receipt['builtFiles'] = [binding(path) for path in sorted((ROOT / 'studio/dist').rglob('*')) if path.is_file()]
    target = directory / 'receipt.json'
    with target.open('x') as output:
        json.dump(receipt, output, ensure_ascii=False, indent=2)
        output.write('\n')
    print(json.dumps({'receipt': binding(target), 'exitCode': run.returncode,
                      'sourceBeforeAfterExact': exact}, ensure_ascii=False))
    sys.exit(run.returncode if run.returncode else (0 if exact else 3))


if __name__ == '__main__':
    main()
