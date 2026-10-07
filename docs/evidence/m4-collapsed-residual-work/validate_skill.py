"""Read-only host Skill validation with exact input and output receipts."""
from pathlib import Path
import datetime
import hashlib
import json
import subprocess

ROOT = Path(__file__).resolve().parents[3]
WORK = Path(__file__).resolve().parent
VALIDATOR = Path('/home/fzg/.codex/skills/.system/skill-creator/scripts/quick_validate.py')
PYTHON = Path('/home/fzg/anaconda3/bin/python')


def binding(path):
    data = path.read_bytes()
    return {'path': str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path),
            'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}


def main():
    out = WORK / 'skill-validation-attempt-1'
    out.mkdir(exist_ok=False)
    paths = sorted(path for path in (ROOT / 'skills/archcanvas').rglob('*') if path.is_file())
    before = [binding(path) for path in paths]
    argv = [str(PYTHON), str(VALIDATOR), 'skills/archcanvas']
    started = datetime.datetime.now(datetime.timezone.utc).isoformat()
    command = subprocess.run(argv, cwd=ROOT, capture_output=True)
    for name, data in [('stdout.txt', command.stdout), ('stderr.txt', command.stderr)]:
        with (out / name).open('xb') as handle:
            handle.write(data)
    after = [binding(path) for path in paths]
    exact = before == after
    receipt = {
        'protocol': 'archcanvas-collapsed-residual-skill-validation/1',
        'argv': argv, 'cwd': str(ROOT), 'startedAt': started,
        'finishedAt': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'exitCode': command.returncode, 'inputsBefore': before, 'inputsAfter': after,
        'inputsExact': exact, 'validator': binding(VALIDATOR),
        'resolvedInterpreter': binding(PYTHON.resolve()),
        'runner': binding(Path(__file__).resolve()),
        'logs': [binding(out / name) for name in ['stdout.txt', 'stderr.txt']],
        'scope': 'Host Markdown/YAML Skill validation only. No installation, model execution, product tests or browser operation.',
    }
    target = out / 'receipt.json'
    with target.open('x') as output:
        json.dump(receipt, output, ensure_ascii=False, indent=2)
        output.write('\n')
    print(json.dumps({'receipt': binding(target), 'exitCode': command.returncode, 'inputsExact': exact}))
    raise SystemExit(command.returncode if command.returncode else (0 if exact else 3))


if __name__ == '__main__':
    main()
