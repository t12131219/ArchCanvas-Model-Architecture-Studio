"""Explicit CPU execution audit; requires an installed PyTorch, never auto-installs it."""
import importlib.util
import base64
import io
import zipfile
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from copy import deepcopy

from archcanvas_preview.authoring_bridge import compile_source_module, generate_python, inspect_source

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / 'tests/fixtures/executable_rebuild'
try:
    import torch
except ImportError:
    torch = None


def document(module=None, atomic=False, **options):
    request = {'module': module, 'atomic': atomic, **options}
    result = subprocess.run(['node', str(ROOT / 'studio/scripts/rebuild-python-document.mjs')], input=json.dumps(request), text=True, capture_output=True, check=True)
    return json.loads(result.stdout)


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def tensors(value):
    if isinstance(value, torch.Tensor):
        return [value]
    if isinstance(value, (list, tuple)):
        return [t for item in value for t in tensors(item)]
    if isinstance(value, dict):
        return [t for item in value.values() for t in tensors(item)]
    return []


@unittest.skipIf(torch is None, 'Run with a verified PyTorch environment for execution evidence')
class ExecutionTests(unittest.TestCase):
    def test_five_existing_models_module_and_atomic_rebuild_execute_equivalently(self):
        torch.set_num_threads(1)
        cases = [('BranchMLP', 'models.py', '4ab8c787e32daeac'), ('TinyCNN', 'models.py', '9e10a966b99ab3ef'),
                 ('ReusedRecurrent', 'models.py', '61b219f6938bacfb'), ('VectorResidual', 'design_compositions.py', 'd188e6e78567c2cd'),
                 ('ConditionalResidual', 'design_compositions.py', '43822e6ee9898ff3')]
        reports = []
        evidence = Path(os.environ.get('ARCHCANVAS_EXECUTION_EVIDENCE', tempfile.mkdtemp(prefix='archcanvas-python-evidence-')))
        evidence.mkdir(parents=True, exist_ok=True)
        catalog_root = ROOT / 'studio/public/preview/data/semantic'
        catalog = json.loads((catalog_root / 'studio-catalog.json').read_text())['models']
        for entry, file, catalog_id in cases:
            original_module = load(FIXTURES / file, 'reference_' + entry)
            compiled = compile_source_module((FIXTURES / file).read_text(), entry)
            shipped = json.loads((catalog_root / next(c for c in catalog if c['id'] == catalog_id)['ir']['path']).read_text())
            # Check that these are the existing catalog architectures, not five new toy aliases.
            signature = lambda ir: sorted((e['source'], e['target'], e['kind']) for e in ir['edges'] if not e['source'].startswith('runtime:') and not e['target'].startswith('runtime:') and e['source'] != 'runtime-observations' and e['target'] != 'runtime-observations')
            self.assertEqual(signature(shipped), signature(compiled['ir']))
            port_differences = [{'edge': e['id'], 'catalog': old['source_port'], 'current': e['source_port']} for e in compiled['ir']['edges'] for old in shipped['edges'] if old['id'] == e['id'] and old['source_port'] != e['source_port']]
            report = {'catalogOperandUpdates': port_differences, 'entry': entry, 'catalogId': catalog_id, 'catalogTopologyMatches': True, 'checks': []}
            for atomic in [False, True]:
                doc = document(compiled, atomic)
                # JSON save/reload is part of the tested route.
                result = generate_python(json.loads(json.dumps(doc)))
                self.assertFalse(result['analysis']['modelExecuted'])
                folder = evidence / entry / ('atomic' if atomic else 'modules'); folder.mkdir(parents=True, exist_ok=True)
                for name, source in result['files'].items():
                    (folder / name).write_text(source)
                generated = load(folder / 'generated_model.py', 'generated_' + entry)
                factory = getattr(generated, result['entry'].split(':')[1])
                for train in [False, True]:
                    for seed in [17, 41, 89]:
                        for branch in ([False, True] if entry in {'BranchMLP', 'ConditionalResidual'} else [None]):
                            torch.manual_seed(seed)
                            reference = getattr(original_module, entry)()
                            candidate = factory(); candidate.load_state_dict(reference.state_dict(), strict=True)
                            reference.train(train); candidate.train(train)
                            if entry == 'BranchMLP': args = [torch.randn(3, 4), branch]
                            elif entry == 'TinyCNN': args = [torch.randn(2, 1, 9, 9)]
                            elif entry == 'ReusedRecurrent': args = [torch.randn(2, 5, 3)]
                            elif entry == 'ConditionalResidual': args = [torch.randn(2, 8), torch.randn(2, 8), branch]
                            else: args = [torch.randn(2, 4, 8)]
                            clone = lambda: [a.detach().clone().requires_grad_(True) if isinstance(a, torch.Tensor) else a for a in args]
                            a, b = clone(), clone()
                            torch.manual_seed(seed + 1000); left = reference(*a)
                            torch.manual_seed(seed + 1000); right = candidate(*b)
                            self.assertEqual(str(type(left)), str(type(right)))
                            self.assertEqual(len(tensors(left)), len(tensors(right)))
                            errors = []
                            for expected, actual in zip(tensors(left), tensors(right)):
                                torch.testing.assert_close(expected, actual, rtol=0, atol=0)
                                errors.append(float((expected - actual).abs().max()))
                            sum(v.sum() for v in tensors(left)).backward(); sum(v.sum() for v in tensors(right)).backward()
                            for x, y in zip(a, b):
                                if isinstance(x, torch.Tensor): torch.testing.assert_close(x.grad, y.grad, rtol=0, atol=0)
                            for (name, x), (other, y) in zip(reference.named_parameters(), candidate.named_parameters()):
                                self.assertEqual(name, other)
                                self.assertEqual(x.grad is None, y.grad is None)
                                if x.grad is not None: torch.testing.assert_close(x.grad, y.grad, rtol=0, atol=0)
                            for key, value in reference.state_dict().items(): torch.testing.assert_close(value, candidate.state_dict()[key], rtol=0, atol=0)
                            if entry == 'ReusedRecurrent': self.assertIs(candidate.shared, candidate.alias)
                            report['checks'].append({'level': 'atomic' if atomic else 'modules', 'mode': 'train' if train else 'eval', 'seed': seed, 'branch': branch, 'maxOutputError': max(errors), 'inputAndParameterGradientsExact': True})
                broken = deepcopy(doc); broken['edges'].pop()
                with self.assertRaisesRegex(Exception, '不能导出旧源码'): generate_python(broken)
                broken = deepcopy(doc); broken['nodes'][1]['label'] = 'changed'
                with self.assertRaisesRegex(Exception, '不能导出旧源码'): generate_python(broken)
            reports.append(report)
        (evidence / 'execution-report.json').write_text(json.dumps({'torch': torch.__version__, 'device': 'cpu', 'models': reports, 'scope': 'Source-preserving reconstruction, not arbitrary atom-to-Python synthesis.'}, indent=2))

    def test_new_composition_follows_current_wiring_and_refuses_stale_internal_code(self):
        sources = [f'from torch import nn\nclass Block(nn.Module):\n def forward(self,x):\n  return {expression}\n' for expression in ['x + 2', 'x * 3']]
        modules = [compile_source_module(source, 'Block') for source in sources]
        for reverse, expected in [(False, 9), (True, 5)]:
            doc = document(modules=modules, reverse=reverse)
            result = generate_python(doc)
            with tempfile.TemporaryDirectory() as folder:
                for name, source in result['files'].items(): Path(folder, name).write_text(source)
                sys.path.insert(0, folder)
                try:
                    for name in ['component_0', 'component_1']: sys.modules.pop(name, None)
                    generated = load(Path(folder, 'generated_model.py'), 'composition_generated')
                    self.assertEqual(float(generated.build_model()(torch.tensor(1.))), expected)
                finally:
                    sys.path.remove(folder)
                    for name in ['component_0', 'component_1']: sys.modules.pop(name, None)
            broken = deepcopy(doc); broken['edges'] = [e for e in broken['edges'] if e.get('evidence') != 'authored-dependency']
            with self.assertRaisesRegex(Exception, '未连接输入'): generate_python(broken)
            broken = deepcopy(doc); broken['nodes'][2]['label'] = 'stale'
            with self.assertRaisesRegex(Exception, '内部结构已修改'): generate_python(broken)


class DiscoveryTests(unittest.TestCase):
    def test_python_generation_never_imports_top_level_source(self):
        source = 'from torch import nn\nraise RuntimeError("AST_ONLY_EXPORT")\nclass Block(nn.Module):\n def forward(self,x): return x\n'
        module = compile_source_module(source, 'Block')
        result = generate_python(document(module))
        self.assertFalse(result['analysis']['modelExecuted'])
        self.assertIn('AST_ONLY_EXPORT', result['source'])
        self.assertTrue(result['analysis']['syntaxValidated'])
        with zipfile.ZipFile(io.BytesIO(base64.b64decode(result['archiveBase64']))) as archive:
            self.assertIsNone(archive.testzip())
            self.assertEqual(archive.read('generated_model.py').decode(), result['source'])
        required = source.replace('def forward(self,x):', 'def __init__(self,width): pass\n def forward(self,x):')
        with self.assertRaisesRegex(Exception, '构造参数'):
            generate_python(document(compile_source_module(required, 'Block')))

    def test_full_model_helper_class_and_syntax_error_are_static(self):
        source = 'from torch import nn\nraise RuntimeError("must not execute")\nclass Cell(nn.Module):\n def forward(self,x): return x\nclass Net(nn.Module):\n def __init__(self,width=8):\n  super().__init__()\n  self.a=Cell()\n def forward(self,x): return self.a(x)\n'
        result = inspect_source(source)
        self.assertEqual(result['recommended'], 'Net')
        net = next(c for c in result['candidates'] if c['entry'] == 'Net')
        self.assertEqual(net['suggestedMode'], 'model'); self.assertEqual(net['constructor'], {'width': 8})
        self.assertFalse(result['executed'])
        self.assertTrue(inspect_source('class Bad(')['diagnostics'])
        self.assertIsNone(inspect_source('from torch import nn\nclass A(nn.Module): pass\nclass B(nn.Module): pass')['recommended'])


if __name__ == '__main__': unittest.main()
