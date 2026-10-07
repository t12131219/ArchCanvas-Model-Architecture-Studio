"""Record collapse continuity round's actual Studio checks with immutable logs and input bytes."""
from pathlib import Path
import argparse
import datetime
import hashlib
import json
import os
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
WORK = Path(__file__).resolve().parent
NODE = Path('/home/fzg/.nvm/versions/node/v24.19.0/bin/node')
NPM = NODE.parent.parent / 'lib/node_modules/npm/bin/npm-cli.js'


def binding(path):
    data = path.read_bytes()
    return {'path': str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path),
            'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}


def sources():
    paths = {p for d in ['studio/src', 'studio/tests'] for p in (ROOT / d).rglob('*') if p.is_file()}
    paths.update(ROOT / p for p in ['studio/package.json', 'studio/package-lock.json', 'studio/tsconfig.json', 'studio/vite.config.ts', 'studio/index.html'])
    paths.update(p for p in (WORK / 'acceptance').rglob('*') if p.is_file())
    # Follow relative TS helpers directly imported by existing tests. Snapshot
    # duplicates are not used as executable inputs and are not collected here.
    pending = [p for p in paths if p.suffix in ['.ts', '.tsx']]
    visited = set()
    while pending:
        p = pending.pop()
        if p in visited:
            continue
        visited.add(p)
        for rel in re.findall(r"(?:from\s*|import\s*)['\"](\.[^'\"]+)['\"]", p.read_text()):
            candidate = (p.parent / rel).resolve()
            if candidate.is_file() and candidate not in paths:
                paths.add(candidate)
                if candidate.suffix in ['.ts', '.tsx']:
                    pending.append(candidate)
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
    before = [binding(p) for p in sorted(paths)]
    argv = ([str(NODE), '--experimental-strip-types', '--test', '--test-isolation=none',
             'studio/tests/collapse-continuity-independent.test.ts'] if args.kind == 'target'
            else [str(NODE), str(NPM), '--prefix', 'studio', *(['test'] if args.kind == 'suite' else ['run', 'build'])])
    environment = dict(os.environ)
    environment['PATH'] = str(NODE.parent) + os.pathsep + environment.get('PATH', '')
    started = datetime.datetime.now(datetime.timezone.utc).isoformat()
    result = subprocess.run(argv, cwd=ROOT, env=environment, capture_output=True)
    for filename, data in [('stdout.txt', result.stdout), ('stderr.txt', result.stderr)]:
        (directory / filename).write_bytes(data)
    after = [binding(p) for p in sorted(paths)]
    exact = before == after and paths == sources()
    receipt = {'protocol': 'archcanvas-collapse-continuity-check/1', 'kind': args.kind, 'argv': argv,
               'cwd': str(ROOT), 'startedAt': started,
               'finishedAt': datetime.datetime.now(datetime.timezone.utc).isoformat(),
               'exitCode': result.returncode, 'sourceBeforeAfterExact': exact,
               'inputsBefore': before, 'inputsAfter': after,
               'infrastructure': [binding(p) for p in [NODE, NPM, Path(__file__).resolve()]],
               'logs': [binding(directory / p) for p in ['stdout.txt', 'stderr.txt']],
               'scope': 'Studio source/tests/config, directly imported TS helpers, and independent collapse-continuity acceptance artifacts. Runtime data beyond these bindings must be bound by its own receipt.',
               'dependenciesInstalled': False, 'modelsExecuted': False}
    if args.kind == 'build':
        receipt['builtFiles'] = [binding(p) for p in sorted((ROOT / 'studio/dist').rglob('*')) if p.is_file()]
    path = directory / 'receipt.json'
    path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'receipt': binding(path), 'exitCode': result.returncode, 'sourceBeforeAfterExact': exact}, ensure_ascii=False))
    sys.exit(result.returncode or (0 if exact else 3))


if __name__ == '__main__':
    main()
