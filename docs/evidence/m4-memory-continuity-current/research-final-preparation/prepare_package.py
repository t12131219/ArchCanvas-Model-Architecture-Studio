"""Run authorized frozen trial preparation only after the exact final checks.

Only prepare/verify and runtime provenance are invoked; this runner does not
assign, collect, serve HTTP, inspect ports or execute generated model source.
"""
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
PACKAGE = ROOT / '.archcanvas/m4-research-trial-memory-continuity-current'

def write(name, value):
    (HERE / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')

def run(label, command):
    started = datetime.now(timezone.utc).isoformat()
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
    (HERE / f'{label}.stdout.json').write_text(result.stdout)
    (HERE / f'{label}.stderr.txt').write_text(result.stderr)
    receipt = {'command': command, 'cwd': str(ROOT), 'startedUtc': started,
               'exitCode': result.returncode, 'pythonMode': 'formal-venv'}
    write(f'{label}.process.json', receipt)
    if result.returncode:
        raise RuntimeError(f'{label} failed: {result.stderr[-1000:]}')
    return json.loads(result.stdout)

def main():
    checks = json.loads((HERE.parent / 'checks-final-attempt-2/receipt.json').read_bytes())
    assert checks['inputsUnchanged'] and checks['publicationInputsUnchanged']
    assert [c['label'] for c in checks['checks']] == ['studio', 'strict-build', 'publication']
    assert all(c['exitCode'] == 0 for c in checks['checks'])
    assert len(checks['inputs']) == 115 and len(checks['build']) == 3 and len(checks['publicationInputs']) == 11
    for row in checks['inputs'] + checks['build'] + checks['publicationInputs']:
        raw = (ROOT / row['path']).read_bytes()
        assert len(raw) == row['bytes'] and hashlib.sha256(raw).hexdigest() == row['sha256'], row['path']
    old = json.loads((HERE / 'old-packages-before.json').read_bytes())
    assert old and len({r['path'].split('/')[1] for r in old}) == 25 and len(old) == 427
    for row in old:
        raw = (ROOT / row['path']).read_bytes()
        assert len(raw) == row['bytes'] and hashlib.sha256(raw).hexdigest() == row['sha256'], row['path']
    assert not PACKAGE.exists() and not PACKAGE.is_symlink()
    formal = str(ROOT / '.venv/bin/python')
    provenance = run('runtime-provenance', [formal, '-c',
        "from pathlib import Path; import json,sys; "
        "sys.path.insert(0,str(Path.cwd()/'src')); "
        "import archcanvas_python; "
        "print(json.dumps({'executable':sys.executable,'prefix':sys.prefix,'basePrefix':sys.base_prefix,"
        "'analyzerOrigin':archcanvas_python.__file__,'pythonVersion':sys.version}))"])
    assert Path(provenance['executable']) == ROOT / '.venv/bin/python'
    assert Path(provenance['prefix']) == ROOT / '.venv'
    assert Path(provenance['analyzerOrigin']).resolve() == ROOT / 'src/archcanvas_python/__init__.py'
    prepared = run('prepare', [formal, 'scripts/research_trial.py', 'prepare', '--output', str(PACKAGE), '--slots', '5', '--first-port', '43631'])
    verified = run('verify-initial', [formal, 'scripts/research_trial.py', 'verify', '--package', str(PACKAGE)])
    write('process.json', {'preparedManifestSha256': hashlib.sha256((PACKAGE/'manifest.json').read_bytes()).hexdigest(),
                          'runtime': provenance, 'prepareExitCode': 0, 'initialVerifyExitCode': 0,
                          'implementationBindings': len(prepared['implementationFiles']), 'officialVerify': verified})
    print(json.dumps({'prepared': str(PACKAGE), 'implementationBindings': len(prepared['implementationFiles']), 'verifyExitCode': 0}))

if __name__ == '__main__':
    main()
