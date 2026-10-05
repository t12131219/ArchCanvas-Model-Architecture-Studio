"""Independent black-box runtime/isolation samples for full M3 acceptance.

Each project is handwritten under /tmp. Default restricted environments may
skip execution when the formal kernel sandbox is unavailable; the full-M3
acceptance script treats a skip as an unmet exit condition.
"""

from __future__ import annotations

import copy
import os
from pathlib import Path
import socket
import tempfile
import threading
import time
import unittest

from m3_runtime_oracle import (EXPECTED_OUTPUT, EXPECTED_PARAMETER_FACTS,
                               EXPECTED_ROLE_SHAPES, INPUT_SPEC, SOURCE)


ROOT = Path(__file__).resolve().parents[1]
UNARY_SOURCE = '''from torch import nn
class Model(nn.Module):
    def __init__(self):
        super().__init__()
        self.identity = nn.Identity()
    def forward(self, x):
        return self.identity(x)
'''
UNARY_SPEC = {'schemaVersion': 1, 'inputs': {'x': {'shape': [2, 4], 'dtype': 'float32', 'fill': 'ones'}},
              'constructor': {}, 'seed': 37, 'modes': ['eval', 'train']}


class M3RuntimeInvariantTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from archcanvas_runtime import verify_structural
        cls.verify = staticmethod(verify_structural)
        cls.config = {
            'interpreter': os.environ.get('ARCHCANVAS_RUNTIME_PYTHON', str(ROOT / '.venv-runtime/bin/python')),
            'dependencyLock': os.environ.get('ARCHCANVAS_RUNTIME_LOCK', str(ROOT / 'requirements-runtime.lock')),
            'timeoutSeconds': 20, 'memoryMb': 4096, 'cpuSeconds': 20,
        }
        with tempfile.TemporaryDirectory(prefix='archcanvas-m3-runtime-probe-', dir='/tmp') as directory:
            root = Path(directory)
            (root / 'model.py').write_text(UNARY_SOURCE, encoding='utf-8')
            receipt = cls.verify(root, 'model:Model', copy.deepcopy(UNARY_SPEC), dict(cls.config))
        if receipt['status'] == 'unavailable':
            if os.environ.get('ARCHCANVAS_REQUIRE_RUNTIME') == '1':
                raise AssertionError(f'Required formal runtime isolation is unavailable: {receipt}')
            raise unittest.SkipTest(f'Formal runtime isolation is unavailable: {receipt.get("reason", receipt.get("error", "unknown"))}')
        if receipt['status'] != 'passed':
            raise AssertionError(f'Formal runtime probe did not pass: {receipt}')

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix='archcanvas-m3-runtime-oracle-', dir='/tmp')
        self.base = Path(self.directory.name)
        self.project = self.base / 'project'
        self.project.mkdir()
        self.model = self.project / 'model.py'
        self.model.write_text(SOURCE, encoding='utf-8')

    def tearDown(self):
        self.directory.cleanup()

    def run_profile(self, source=SOURCE, entry='model:CrossAttention', spec=None, config=None):
        self.model.write_text(source, encoding='utf-8')
        before = self.model.read_bytes()
        result = self.verify(self.project, entry, copy.deepcopy(spec or INPUT_SPEC), dict(config or self.config))
        self.assertEqual(self.model.read_bytes(), before, 'Running cannot rewrite its source snapshot or original')
        return result

    def assert_failed(self, result):
        self.assertEqual(result['status'], 'failed', result)
        self.assertFalse(result.get('runtimeVerified', False))

    def tensor_contract(self, descriptor):
        self.assertEqual(descriptor['kind'], 'tensor')
        return {key: descriptor[key] for key in ('shape', 'dtype')}

    def test_mha_sample_roles_two_modes_replay_and_real_parameter_facts(self):
        result = self.run_profile()
        self.assertEqual(result['status'], 'passed', result)
        self.assertTrue(result['sourceDigest'])
        self.assertTrue(result['testedIRDigest'])
        self.assertTrue(result['inputSpecDigest'])
        self.assertTrue(result['environmentDigest'])
        manifest = result['manifest']
        self.assertEqual(manifest['inputSpec']['seed'], 37)
        self.assertEqual(manifest['inputSpec']['modes'], ['eval', 'train'])
        self.assertEqual(manifest['inputSpec']['inputs'], INPUT_SPEC['inputs'])
        modes = result['observation']['modes']
        self.assertEqual([mode['mode'] for mode in modes], ['eval', 'train'])
        for mode in modes:
            calls = {call['modulePath']: call for call in mode['calls']}
            self.assertIn('key_activation', calls)
            self.assertIn('attention', calls)
            attention = calls['attention']
            self.assertEqual(attention['moduleType'].rsplit('.', 1)[-1], 'MultiheadAttention')
            for role, expected in EXPECTED_ROLE_SHAPES.items():
                self.assertEqual(self.tensor_contract(attention['inputs'][role]), expected)
            self.assertEqual(attention['inputs']['query']['producer'], {'kind': 'input', 'name': 'q'})
            self.assertEqual(attention['inputs']['key']['producer'], {'kind': 'input', 'name': 'memory'})
            self.assertEqual(attention['inputs']['value']['producer'], {'kind': 'input', 'name': 'memory'})
            self.assertEqual(attention['inputs']['attn_mask']['producer'], {'kind': 'input', 'name': 'mask'})
            self.assertEqual(self.tensor_contract(attention['outputs']['output']), EXPECTED_OUTPUT)
            self.assertEqual(attention['outputs']['weights']['kind'], 'none')
            self.assertTrue(mode['finite'])
            self.assertTrue(mode['replay']['structureEqual'])
            self.assertTrue(mode['replay']['bindingsEqual'])
            self.assertTrue(mode['replay']['gradientsEqual'])
            self.assertTrue(mode['replay']['stateEqual'])
            self.assertNotIn('global', mode['replay']['claim'].lower())
            parameters = {item['key']: {key: item[key] for key in ('shape', 'dtype')}
                          for item in mode['state']['before']['entries'] if item['role'] == 'parameter'}
            self.assertEqual(parameters, EXPECTED_PARAMETER_FACTS)
            self.assertEqual([item for item in mode['state']['before']['entries'] if item['role'] == 'buffer'], [])
            self.assertEqual(mode['state']['before']['sharedGroups'], [])
            self.assertEqual(mode['state']['mutatedKeys'], [])
            self.assertEqual(mode['gradients']['status'], 'observed')
            self.assertTrue(mode['gradients']['finite'])
            gradients = {(item['kind'], item['name']): item for item in mode['gradients']['items']}
            for name, shape in {'q': [2, 3, 8], 'memory': [2, 5, 8]}.items():
                self.assertEqual(gradients[('input', name)]['status'], 'observed')
                self.assertEqual(gradients[('input', name)]['shape'], shape)
            for name, parameter in EXPECTED_PARAMETER_FACTS.items():
                self.assertEqual(gradients[('parameter', name)]['status'], 'observed')
                self.assertEqual(gradients[('parameter', name)]['shape'], parameter['shape'])
        # The worker must report actual state facts, not merely infer that a
        # rebind doesn't change constructor syntax. Wire adaptation happens
        # only after the independent expected keys/shapes above are frozen.
        self.assertIn('stateCompatibility', result)

    def test_mha_sample_invalid_feature_dtype_and_mask_shape_fail(self):
        variants = {
            'query-feature': ('q', {'shape': [2, 3, 7], 'dtype': 'float32', 'fill': 'normal'}),
            'query-dtype': ('q', {'shape': [2, 3, 8], 'dtype': 'int64', 'fill': 'ones'}),
            'mask-shape': ('mask', {'shape': [3, 4], 'dtype': 'bool', 'fill': 'zeros'}),
        }
        for reason, (name, replacement) in variants.items():
            with self.subTest(reason=reason):
                spec = copy.deepcopy(INPUT_SPEC)
                spec['inputs'][name] = replacement
                self.assert_failed(self.run_profile(spec=spec))

    def test_worker_blocks_host_reads_writes_and_source_writes(self):
        sentinel = self.base / 'private-host-input.txt'
        sentinel.write_text('independent host-only sentinel', encoding='utf-8')
        output = self.base / 'outside-worker-output.txt'
        source = UNARY_SOURCE.replace('        return self.identity(x)',
            f'        paths = [({str(sentinel)!r}, "r"), ({str(output)!r}, "w"), (__file__, "w")]\n'
            '        for path, mode in paths:\n'
            '            try:\n'
            '                with open(path, mode) as stream:\n'
            '                    if mode == "r":\n'
            '                        stream.read()\n'
            '                    else:\n'
            '                        stream.write("unauthorized write")\n'
            '            except OSError:\n'
            '                continue\n'
            '            raise RuntimeError("Isolation allowed a host/source access")\n'
            '        return self.identity(x)')
        result = self.run_profile(source, 'model:Model', UNARY_SPEC)
        self.assertEqual(result['status'], 'passed', result)
        self.assertEqual(sentinel.read_text(encoding='utf-8'), 'independent host-only sentinel')
        self.assertFalse(output.exists())

    def test_worker_cannot_connect_to_a_real_host_loopback_listener(self):
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            listener.bind(('127.0.0.1', 0))
            listener.listen()
            address = listener.getsockname()
            source = UNARY_SOURCE.replace('from torch import nn', 'from torch import nn\nimport socket').replace(
                '        return self.identity(x)',
                '        connection = None\n'
                '        try:\n'
                '            connection = socket.socket(socket.AF_INET, socket.SOCK_STREAM)\n'
                '            connection.settimeout(0.25)\n'
                f'            connection.connect({address!r})\n'
                '        except OSError:\n'
                '            return self.identity(x)\n'
                '        finally:\n'
                '            if connection is not None:\n'
                '                connection.close()\n'
                '        raise RuntimeError("Isolation connected to a host listener")')
            result = self.run_profile(source, 'model:Model', UNARY_SPEC)
            self.assertEqual(result['status'], 'passed', result)
        finally:
            listener.close()

    def test_worker_cannot_spawn_an_unrestricted_child_process(self):
        source = UNARY_SOURCE.replace('from torch import nn', 'from torch import nn\nimport subprocess\nimport sys').replace(
            '        return self.identity(x)',
            '        try:\n'
            '            subprocess.run([sys.executable, "-I", "-c", "pass"], check=True, timeout=1)\n'
            '        except (OSError, subprocess.SubprocessError):\n'
            '            return self.identity(x)\n'
            '        raise RuntimeError("Isolation allowed child process execution")')
        result = self.run_profile(source, 'model:Model', UNARY_SPEC)
        self.assertEqual(result['status'], 'passed', result)

    def test_kernel_virtual_memory_limit_blocks_a_large_allocation(self):
        source = UNARY_SOURCE.replace('from torch import nn', 'from torch import nn\nimport resource').replace(
            '        return self.identity(x)',
            '        requested = 5 * 1024**3\n'
            '        actual, hard = resource.getrlimit(resource.RLIMIT_AS)\n'
            '        if actual < 1 or actual >= requested or hard != actual:\n'
            '            raise RuntimeError("No bounded kernel address-space limit")\n'
            '        try:\n'
            '            bytearray(requested)\n'
            '        except MemoryError:\n'
            '            return self.identity(x)\n'
            '        raise RuntimeError("Allocation exceeded declared address-space limit")')
        result = self.run_profile(source, 'model:Model', UNARY_SPEC)
        self.assertEqual(result['status'], 'passed', result)
        self.assertEqual(result['manifest']['limits']['addressSpaceBytes'], 4096 * 1024**2)
        self.assertTrue(result['manifest']['isolation']['checks']['addressSpaceLimitApplied'])

    def test_timeout_and_cancel_are_failed_without_original_writes(self):
        source = UNARY_SOURCE.replace('        return self.identity(x)', '        while True:\n            pass')
        config = dict(self.config, timeoutSeconds=3)
        started = time.monotonic()
        self.assert_failed(self.run_profile(source, 'model:Model', UNARY_SPEC, config))
        self.assertLess(time.monotonic() - started, 10)
        cancel = threading.Event()
        timer = threading.Timer(0.2, cancel.set)
        timer.start()
        try:
            started = time.monotonic()
            result = self.run_profile(source, 'model:Model', UNARY_SPEC, dict(self.config, cancelEvent=cancel))
            self.assert_failed(result)
            self.assertIn('cancel', str(result).lower())
            self.assertLess(time.monotonic() - started, 10)
        finally:
            timer.cancel()


if __name__ == '__main__':
    unittest.main()
