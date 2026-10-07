"""Version-bound checks for the frontier status v2 UI feedback fix."""
from pathlib import Path
import concurrent.futures, datetime, hashlib, json, os, shutil, subprocess, sys

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / 'docs/evidence/m4-frontier-move-current' / sys.argv[1]
OUT.mkdir(exist_ok=False)

def binding(path):
    raw = path.read_bytes()
    return {'path': str(path.relative_to(ROOT)), 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}

sources = sorted({*(ROOT / 'studio/src').rglob('*'), *(ROOT / 'studio/tests').rglob('*.ts'), *(ROOT / 'studio').glob('*.json'), *(ROOT / 'studio').glob('*.ts'), ROOT / 'studio/index.html'})
sources = [path for path in sources if path.is_file()]
inputs = [binding(path) for path in sources]
publication_paths = sorted({*(ROOT / 'src/archcanvas_publication').glob('*.py'), *(ROOT / 'src/archcanvas_python').glob('*.py'), ROOT / 'tests/test_publication_export.py', ROOT / 'scripts/export_canvas.mjs', *(ROOT / 'fixtures/residual_cnn').glob('*.py')})
publication_inputs = [binding(path) for path in publication_paths]
commands = [('studio', ['npm', 'test'], ROOT / 'studio'), ('strict-build', ['npm', 'run', 'build'], ROOT / 'studio'), ('publication', [str(ROOT / '.venv/bin/python'), '-m', 'unittest', 'discover', '-s', 'tests', '-p', 'test_publication_export.py', '-v'], ROOT)]

def check(item):
    label, command, cwd = item
    started = datetime.datetime.now(datetime.timezone.utc).isoformat()
    environment = dict(os.environ)
    if label == 'publication': environment['PYTHONPATH'] = str(ROOT / 'src')
    result = subprocess.run(command, cwd=cwd, env=environment, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    log = OUT / f'{label}.txt'; log.write_text(result.stdout)
    return {'label': label, 'command': command, 'cwd': str(cwd), 'startedUtc': started, 'exitCode': result.returncode, 'log': str(log.relative_to(ROOT))}

with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
    checks = list(executor.map(check, commands))
build = []
for path in sorted((ROOT / 'studio/dist').rglob('*')):
    if path.is_file():
        copy = OUT / 'build' / path.relative_to(ROOT / 'studio/dist'); copy.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(path, copy)
        build.append({**binding(path), 'snapshot': str(copy.relative_to(ROOT))})
unchanged = inputs == [binding(path) for path in sources]
publication_unchanged = publication_inputs == [binding(path) for path in publication_paths]
receipt = {'schema': 'archcanvas-frontier-status-v2-checks/1', 'createdUtc': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'inputs': inputs, 'inputsUnchanged': unchanged, 'checks': checks, 'build': build, 'publicationInputs': publication_inputs, 'publicationInputsUnchanged': publication_unchanged, 'scope': 'Current frontier move build after authoring busy-state labels; no model execution, human participation, physical publication approval or presented FPS certification.'}
(OUT / 'receipt.json').write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + '\n')
print(json.dumps({'receipt': str((OUT / 'receipt.json').relative_to(ROOT)), 'sourceBindings': len(inputs), 'buildBindings': len(build), 'inputsUnchanged': unchanged, 'checks': checks}, indent=2))
sys.exit(0 if unchanged and publication_unchanged and all(item['exitCode'] == 0 for item in checks) else 1)
