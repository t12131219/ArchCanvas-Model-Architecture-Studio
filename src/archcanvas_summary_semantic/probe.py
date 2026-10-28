"""Explicit CPU observations in a narrow Linux Bubblewrap process.

This profile supports a conda environment or venv, including GPU-capable torch
builds, but exposes no GPU devices and creates all inputs/model tensors on CPU.
No dependency installation, model download, weights, or notebook execution.
"""
import itertools
import json
import os
from pathlib import Path
import platform
import signal
import struct
import subprocess
import tempfile
from .schema import digest


def normalize_spec(spec):
    allowed = {'schema', 'modes', 'constructor', 'cases', 'finite_domain', 'export'}
    if not isinstance(spec, dict) or set(spec) - allowed or spec.get('schema') != 'semantic-inputs/1':
        raise ValueError('expected semantic-inputs/1 with declared cases/modes')
    modes = spec.get('modes')
    if not isinstance(modes, list) or not modes or len(set(modes)) != len(modes) or any(m not in ('eval', 'train') for m in modes):
        raise ValueError('modes must be unique eval/train values')
    cases = spec.get('cases', [])
    if not isinstance(cases, list) or not 1 <= len(cases) <= 64:
        raise ValueError('provide 1–64 explicit input cases')
    if any(not isinstance(c, dict) or set(c) - {'id', 'inputs', 'seed'} or not isinstance(c.get('id'), str) or not c['id'] or type(c.get('seed', 0)) != int for c in cases):
        raise ValueError('cases require a nonempty string id, integer seed and inputs')
    if len({c['id'] for c in cases}) != len(cases): raise ValueError('duplicate case IDs')
    for case in cases:
        if not isinstance(case.get('inputs'), dict) or not case['inputs']: raise ValueError('named inputs required')
        total = 0
        for name, value in case['inputs'].items():
            if not name.isidentifier(): raise ValueError('invalid argument name')
            if not isinstance(value, dict) or set(value) - {'value', 'shape', 'dtype', 'fill'}: raise ValueError('unsupported input descriptor')
            if 'value' in value:
                if set(value) != {'value'}: raise ValueError('scalar and tensor descriptors are mutually exclusive')
                if type(value['value']) not in (bool, int, float, str, type(None)): raise ValueError('scalar value only')
                continue
            shape = value.get('shape')
            if not isinstance(shape, list) or len(shape) > 8 or any(type(n) != int or n < 1 or n > 4096 for n in shape): raise ValueError('bounded shape required')
            count = 1
            for n in shape: count *= n
            total += count
            if total > 1_000_000: raise ValueError('one million input element limit')
            if value.get('dtype', 'float32') not in ('float32', 'float64', 'int64', 'bool'): raise ValueError('unsupported dtype')
            if value.get('fill', 'zeros') not in ('zeros', 'ones', 'normal'): raise ValueError('unsupported fill')
            if value.get('fill') == 'normal' and value.get('dtype', 'float32') in ('int64', 'bool'): raise ValueError('normal fill needs float dtype')
    if not isinstance(spec.get('constructor', {}), dict): raise ValueError('constructor must be JSON object')
    if type(spec.get('export', False)) is not bool: raise ValueError('export must be boolean')
    if spec.get('finite_domain') is not None and not isinstance(spec['finite_domain'], dict): raise ValueError('finite_domain must be object')
    return spec


def finite_domain_check(spec):
    """A finite set is not a continuous range; random normal fill isn't finite."""
    domain = spec.get('finite_domain')
    if not domain: return {'exhaustive': False, 'reason': 'no explicit finite input set'}
    # Input descriptors include scalar values or fully determined zeros/ones
    # tensors. A shape range or a random seed is never an exhaustive value set.
    if domain.get('kind') != 'explicit-input-set': return {'exhaustive': False, 'reason': 'unsupported finite-domain kind'}
    requested = domain.get('inputs', [])
    actual = [c['inputs'] for c in spec['cases']]
    deterministic = all(v.get('fill', 'zeros') != 'normal' for c in spec['cases'] for v in c['inputs'].values())
    match = set(map(digest, requested)) == set(map(digest, actual)) and len(requested) == len(set(map(digest, requested)))
    return {'exhaustive': bool(match and deterministic), 'reason': 'all declared concrete inputs × declared modes enumerated' if match and deterministic else 'input set mismatch or nondeterministic tensors',
            'inputs': len(requested), 'modes': spec['modes'], 'scope': 'explicit concrete input set only; not all tensors of these shapes'}


def seccomp_policy():
    if platform.machine() != 'x86_64': raise ValueError('isolated runtime currently requires Linux x86-64')
    # AUDIT_ARCH_X86_64, reject x32 and every process/thread creation syscall.
    program = [(0x20, 0, 0, 4), (0x15, 1, 0, 0xC000003E), (0x06, 0, 0, 0x80000000), (0x20, 0, 0, 0)]
    for number in (41, 53, 56, 57, 58, 101, 155, 165, 166, 272, 308, 310, 311, 321, 323):
        program.extend([(0x15, 0, 1, number), (0x06, 0, 0, 0x00050001)])
    program.extend([(0x15, 0, 1, 435), (0x06, 0, 0, 0x00050026),
                    (0x35, 0, 1, 0x40000000), (0x06, 0, 0, 0x00050001), (0x06, 0, 0, 0x7fff0000)])
    return b''.join(struct.pack('HBBI', *x) for x in program)


def observe(source, entry, spec, interpreter, source_root=None, timeout=45, memory_mb=8192):
    spec = normalize_spec(spec)
    source = Path(source).resolve()
    if source.suffix != '.py': raise ValueError('runtime requires original .py; notebooks remain static-only')
    root = Path(source_root).resolve() if source_root else source.parent
    if not source.is_relative_to(root): raise ValueError('source must be within --source-root')
    logical = source.relative_to(root).with_suffix('').as_posix().replace('/', '.')
    python = Path(interpreter).absolute()
    if not python.is_file(): raise ValueError('explicit interpreter unavailable')
    env = python.parent.parent
    if env in (Path('/'), Path('/usr'), Path('/home')): raise ValueError('select a narrow conda or virtual environment')
    binding = {'interpreter': str(python), 'executable_sha256': digest(python.read_bytes()), 'environment': str(env),
               'source_root': str(root), 'source_sha256': digest(source.read_bytes()), 'spec_digest': digest(spec),
               'worker_digest': digest(Path(__file__).with_name('runtime_worker.py').read_bytes()), 'device': 'cpu'}
    receipt = {'schema': 'semantic-runtime/1', 'status': 'unavailable', 'model_executed': False, 'binding': binding, 'input_spec': spec}
    if platform.system() != 'Linux' or not Path('/usr/bin/bwrap').is_file():
        return {**receipt, 'reason': 'mandatory Linux Bubblewrap unavailable; no ordinary subprocess fallback'}
    # No complete host HOME/project mount. Original source is mounted read-only,
    # and never extracted/copied to the application. Bind source generation to
    # all Python files under the explicitly selected root.
    files = sorted(p for p in root.rglob('*.py') if not any(x in {'.git', '.venv', '__pycache__'} for x in p.relative_to(root).parts))
    if len(files) > 500: raise ValueError('runtime source root exceeds 500 Python files; select a narrower root')
    before = {str(p.relative_to(root)): digest(p.read_bytes()) for p in files}
    binding['source_generation'] = before
    limits = {'memory_mb': memory_mb, 'cpu_seconds': min(120, timeout), 'max_events': 6000, 'wall_seconds': timeout}
    request = {'entry': logical + ':' + entry.split(':')[-1], 'constructor': spec.get('constructor', {}),
               'cases': spec['cases'], 'modes': spec['modes'], 'export': spec.get('export', False), 'limits': limits}
    with tempfile.TemporaryDirectory(prefix='summary-semantic-') as temp:
        folder = Path(temp)
        policy = folder / 'policy.bpf'; policy.write_bytes(seccomp_policy())
        request_path = folder / 'request.json'
        passwd = folder / 'passwd'; passwd.write_text(f'archcanvas:x:{os.getuid()}:{os.getgid()}:CPU probe:/work:/bin/false\n')
        def execute(data):
            request_path.write_text(json.dumps(data))
            with policy.open('rb') as fd, (folder / 'out').open('wb') as out, (folder / 'err').open('wb') as err:
                command = ['/usr/bin/bwrap', '--unshare-all', '--die-with-parent', '--cap-drop', 'ALL', '--clearenv',
                           '--ro-bind', str(env), str(env), '--ro-bind', '/usr/lib', '/usr/lib', '--symlink', 'usr/lib', '/lib']
                if Path('/usr/lib64').is_dir(): command += ['--ro-bind', '/usr/lib64', '/usr/lib64', '--symlink', 'usr/lib64', '/lib64']
                command += ['--ro-bind', str(passwd), '/etc/passwd', '--proc', '/proc', '--dev', '/dev', '--tmpfs', '/tmp', '--tmpfs', '/work',
                            '--ro-bind', str(root), '/model', '--ro-bind', str(Path(__file__).with_name('runtime_worker.py')), '/worker.py',
                            '--ro-bind', str(request_path), '/request.json', '--chdir', '/work']
                for name, value in {'HOME': '/work', 'TMPDIR': '/tmp', 'OMP_NUM_THREADS': '1', 'MKL_NUM_THREADS': '1',
                                    'OPENBLAS_NUM_THREADS': '1', 'CUDA_VISIBLE_DEVICES': '', 'PYTHONDONTWRITEBYTECODE': '1',
                                    'PYTHONHASHSEED': '0', 'LD_LIBRARY_PATH': str(env / 'lib')}.items(): command += ['--setenv', name, value]
                command += ['--seccomp', str(fd.fileno()), str(python), '-I', '-B', '/worker.py', '/request.json']
                proc = subprocess.Popen(command, stdout=out, stderr=err, pass_fds=(fd.fileno(),), start_new_session=True)
                try: proc.wait(timeout=timeout)
                except subprocess.TimeoutExpired:
                    os.killpg(proc.pid, signal.SIGKILL); proc.wait()
                    return {'status': 'failed', 'model_executed': None, 'reason': 'wall timeout'}
            if proc.returncode: return {'status': 'unavailable', 'model_executed': False, 'reason': (folder / 'err').read_text(errors='replace')[:3000]}
            if (folder / 'out').stat().st_size > 8_000_000: return {'status': 'failed', 'reason': 'receipt budget exceeded', 'model_executed': True}
            try: return json.loads((folder / 'out').read_text())
            except ValueError: return {'status': 'failed', 'reason': 'worker returned invalid JSON', 'model_executed': None}
        isolation = execute({'action': 'probe', 'source_probe': source.relative_to(root).as_posix(), 'host_root': str(root),
                             'host_namespaces': {n: os.readlink('/proc/self/ns/' + n) for n in ('mnt', 'net', 'pid', 'user')}, 'limits': limits})
        receipt['isolation'] = isolation
        if isolation.get('status') != 'passed': return {**receipt, 'reason': isolation.get('reason', 'mandatory isolation probes failed')}
        observed = execute(request)
    after = {str(p.relative_to(root)): digest(p.read_bytes()) for p in files if p.exists()}
    receipt.update(observed)
    receipt['binding'] = binding
    receipt['limits'] = limits
    receipt['source_unchanged'] = before == after
    if before != after: receipt.update(status='failed', reason='source changed during observation')
    receipt['finite_domain'] = finite_domain_check(spec)
    receipt['trace_digest'] = digest(receipt)
    return receipt
