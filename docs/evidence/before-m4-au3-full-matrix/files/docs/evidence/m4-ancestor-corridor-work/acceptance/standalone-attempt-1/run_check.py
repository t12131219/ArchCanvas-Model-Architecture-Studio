"""Capture the unmodified formal standalone check and bind its actual inputs."""
from pathlib import Path
import datetime
import hashlib
import json
import os
import shutil
import subprocess
import time

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[4]
OUT = OUT / 'run-1'
OUT.mkdir(parents=True, exist_ok=False)
NODE = Path('/home/fzg/.nvm/versions/node/v24.19.0/bin/node')
PYTHON = ROOT / '.venv/bin/python'
CHECK = ROOT / 'scripts/check_independence.py'
EXCLUDED = {'.git', '.venv', 'venv', 'node_modules', 'dist', 'build', '__pycache__', '.pytest_cache', '.mypy_cache', '.archcanvas', '.DS_Store', '.env', '.env.local'}


def binding(path):
    raw = path.read_bytes()
    return {'path': str(path.resolve()), 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def write(path, value):
    with path.open('x') as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2)
        handle.write('\n')


def files_under(directory, dependency=False):
    return sorted(path for path in directory.rglob('*') if path.is_file() and not path.is_symlink() and
        (dependency or not any(part in EXCLUDED or part.endswith(('.pyc', '.pyo', '.egg-info', '.tsbuildinfo')) for part in path.relative_to(directory).parts)))


def source_paths():
    paths = []
    for name in ['src', 'studio/src', 'studio/tests', 'scripts', 'schemas', 'fixtures', 'skills', 'tests']:
        paths.extend(files_under(ROOT / name))
    for name in ['AGENTS.md', 'pyproject.toml', 'requirements.lock', 'requirements-runtime.lock', 'studio/package.json', 'studio/package-lock.json', 'studio/tsconfig.json', 'studio/vite.config.ts', 'studio/index.html']:
        if (ROOT / name).is_file(): paths.append(ROOT / name)
    paths.append(ROOT / 'docs/evidence/m4-ancestor-corridor-work/ancestor-corridor-oracle.ts')
    paths.append(Path(__file__).resolve())
    return sorted(set(paths))


requested_release = ['pyproject.toml', 'requirements.lock', 'requirements-runtime.lock', 'README.md', 'AGENTS.md', 'LICENSE', 'LICENSE.md', '.gitignore', 'src', 'fixtures', 'studio', 'docs', 'scripts', 'skills', 'tests', 'schemas']
allocated = 0
release_file_count = 0
for name in requested_release:
    item = ROOT / name
    paths = files_under(item) if item.is_dir() else [item] if item.is_file() else []
    for path in paths:
        # Count destination allocation in4KiB blocks rather than apparent bytes.
        allocated += ((path.stat().st_size + 4095) // 4096) * 4096
        release_file_count += 1
dependency_paths = files_under(ROOT / 'studio/node_modules', dependency=True)
dependency_allocation = sum(((path.stat().st_size + 4095) // 4096) * 4096 for path in dependency_paths)
disk = shutil.disk_usage('/tmp')
reserve = 512 * 1024 * 1024
space = {'filesystem': '/tmp', 'freeBytes': disk.free, 'releaseEstimatedAllocatedBytes': allocated, 'releaseRegularFileCount': release_file_count,
    'copiedInstalledDependenciesEstimatedAllocatedBytes': dependency_allocation, 'dependencyRegularFileCount': len(dependency_paths),
    'reservedBuildReportHeadroomBytes': reserve, 'enough': disk.free > allocated + dependency_allocation + reserve,
    'scope': 'Unmodified check copies full RELEASE_ITEMS including historical docs; no reduced copy or check modification.'}
write(OUT / 'space-before.json', space)
assert space['enough'], 'Insufficient /tmp space for full unmodified standalone check'
sources = source_paths()
before = [binding(path) for path in sources]
deps_before = [binding(path) for path in dependency_paths]
symlinks = [{'path': str(path), 'target': os.readlink(path), 'resolved': str(path.resolve()), 'resolvedWithinProjectDependencies': path.resolve().is_relative_to((ROOT / 'studio/node_modules').resolve())} for path in (ROOT / 'studio/node_modules').rglob('*') if path.is_symlink()]
assert all(item['resolvedWithinProjectDependencies'] for item in symlinks)
write(OUT / 'source-bindings-before.json', {'bindings': before})
write(OUT / 'dependency-bindings-before.json', {'bindings': deps_before, 'symlinks': symlinks})
environment = os.environ.copy()
environment['PATH'] = str(NODE.parent) + os.pathsep + environment.get('PATH', '')
help_command = [str(PYTHON), str(CHECK), '--help']
with (OUT / 'api-help.stdout.log').open('x') as stdout, (OUT / 'api-help.stderr.log').open('x') as stderr:
    help_result = subprocess.run(help_command, cwd=ROOT, env=environment, stdout=stdout, stderr=stderr, timeout=30)
assert help_result.returncode == 0
command = [str(PYTHON), str(CHECK), '--project', str(ROOT), '--build']
start = datetime.datetime.now(datetime.timezone.utc).isoformat()
t0 = time.monotonic()
with (OUT / 'stdout.json').open('x') as stdout, (OUT / 'stderr.log').open('x') as stderr:
    process = subprocess.run(command, cwd=ROOT, env=environment, stdout=stdout, stderr=stderr, timeout=600)
finish = datetime.datetime.now(datetime.timezone.utc).isoformat()
after = [binding(path) for path in sources]
deps_after = [binding(path) for path in dependency_paths]
write(OUT / 'source-bindings-after.json', {'bindings': after, 'exactBeforeAfter': before == after})
write(OUT / 'dependency-bindings-after.json', {'bindings': deps_after, 'exactBeforeAfter': deps_before == deps_after})
receipt = {'argv': command, 'cwd': str(ROOT), 'startedAt': start, 'finishedAt': finish, 'elapsedSeconds': time.monotonic() - t0, 'exitCode': process.returncode,
    'requestedFormalVenvInterpreter': str(PYTHON), 'resolvedPythonInterpreter': str(PYTHON.resolve()), 'requestedNode24': binding(NODE),
    'pythonRuntime': subprocess.check_output([str(PYTHON), '--version'], text=True).strip(), 'nodeRuntime': subprocess.check_output([str(NODE), '--version'], text=True).strip(),
    'checkScript': binding(CHECK), 'wrapper': binding(Path(__file__).resolve()), 'apiHelpArgv': help_command, 'apiHelpStdout': binding(OUT / 'api-help.stdout.log'), 'apiHelpStderr': binding(OUT / 'api-help.stderr.log'), 'sourceFilesBound': len(before), 'sourceBeforeAfterExact': before == after, 'dependencyFilesBound': len(deps_before), 'dependenciesBeforeAfterExact': deps_before == deps_after,
    'stdout': binding(OUT / 'stdout.json'), 'stderr': binding(OUT / 'stderr.log'), 'spaceBefore': binding(OUT / 'space-before.json'), 'modelExecution': 'not_run', 'productSuite': 'not_run'}
if process.returncode == 0:
    returned = json.loads((OUT / 'stdout.json').read_text())
    report_path = Path(returned['report'])
    raw = report_path.read_bytes()
    report = json.loads(raw)
    destination = OUT / 'actual-independence-report.json'
    with destination.open('xb') as handle: handle.write(raw)
    assert destination.read_bytes() == raw
    receipt.update({'standaloneCopy': returned['standaloneCopy'], 'actualTemporaryReport': binding(report_path), 'reportCopy': binding(destination), 'reportCopiedExact': True,
        'checks': [{'name': item['name'], 'passed': item['passed']} for item in report['checks']], 'checkCount': len(report['checks']), 'allChecksPassed': all(item['passed'] for item in report['checks']),
        'scope': 'Five static analyze fixtures + package provenance + capabilities declaration + copied source bytes + standalone Studio build using copied installed project-local npm dependencies. No clean install or model execution.'})
    assert len(report['checks']) == 9 and all(item['passed'] for item in report['checks'])
write(OUT / 'process.json', receipt)
for path in [OUT / 'process.json', OUT / 'actual-independence-report.json']:
    if path.exists(): print(json.dumps(binding(path), ensure_ascii=False))
print(json.dumps({'exitCode': process.returncode, 'sourceBeforeAfterExact': before == after, 'dependenciesBeforeAfterExact': deps_before == deps_after, 'checks': receipt.get('checkCount'), 'standaloneCopy': receipt.get('standaloneCopy')}, ensure_ascii=False))
