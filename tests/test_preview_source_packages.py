import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / 'studio/scripts/organize-preview-sources.py'
SPEC = importlib.util.spec_from_file_location('source_packages', SCRIPT)
packages = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(packages)


class SourcePackagesTest(unittest.TestCase):
    def test_legal_module_names_preserve_python_files_and_init(self):
        self.assertEqual(packages.logical_path('repo-v1.2/class/3-layer.py'), 'repo_v1_2/_class/_3_layer.py')
        self.assertEqual(packages.logical_path('repo/__init__.py', 'repo'), '__init__.py')

    def test_package_keeps_exact_lines_entry_alias_licenses_and_shared_cases(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'data').mkdir()
            source = root / 'snapshots/guide/sources/repo-v1.2'
            source.mkdir(parents=True)
            data = b'# evidence starts at line 2\nclass Model:\n    pass\n'
            (source / 'net-file.py').write_bytes(data)
            (source / 'LICENSE').write_text('license-text')
            evidence = root / 'snapshots/guide/evidence.json'
            evidence.write_text(json.dumps({'license_files': ['repo-v1.2/LICENSE']}))
            case = {'title': 'Model', 'available': True, 'entry': 'repo-v1.2/net-file.py::Model',
                    'evidence': 'snapshots/guide/evidence.json', 'files': [
                        {'path': 'repo-v1.2/net-file.py', 'asset': 'snapshots/guide/sources/repo-v1.2/net-file.py',
                         'sha256': hashlib.sha256(data).hexdigest()}]}
            packages.organize(root, {'schema': 'index', 'cases': {'active': case, 'historical': case}})
            index = json.loads((root / 'data/catalog-sources.json').read_text())
            active, historical = index['cases'].values()
            self.assertEqual(active['entry'], 'repo_v1_2/net_file.py::Model')
            self.assertEqual(active['files'][0]['originalPath'], 'repo-v1.2/net-file.py')
            self.assertEqual(active['files'], historical['files'])
            self.assertEqual((root / active['files'][0]['asset']).read_bytes(), data)
            self.assertEqual((root / active['licenses'][0]['asset']).read_text(), 'license-text')
            self.assertEqual(json.loads((root / 'data/source-packages.json').read_text())['counts']['packages'], 1)

    def test_dependency_must_belong_to_identical_collection_snapshot(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            original = root / 'snapshots/guide/sources/repo'
            generated = root / 'snapshots/guide/generated/case/sources/repo'
            original.mkdir(parents=True)
            generated.mkdir(parents=True)
            data = b'from .utils import helper\n'
            (generated / 'net.py').write_bytes(data)
            (original / 'net.py').write_bytes(data)
            (original / 'utils.py').write_bytes(b'def helper():\n    return 1\n')
            files = [{'path': 'repo/net.py', 'asset': 'snapshots/guide/generated/case/sources/repo/net.py',
                      'sha256': hashlib.sha256(data).hexdigest()}]
            self.assertEqual([f['path'] for f in packages.dependency_closure(root, files)], ['repo/net.py', 'repo/utils.py'])
            (original / 'net.py').write_bytes(b'# different repository version\n')
            self.assertEqual([f['path'] for f in packages.dependency_closure(root, files)], ['repo/net.py'])

    def test_source_hash_and_normalization_collisions_reject(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'data').mkdir()
            (root / 'snapshots').mkdir()
            for name in ['a-b.py', 'a_b.py']:
                (root / 'snapshots' / name).write_text('pass\n')
            digest = hashlib.sha256(b'pass\n').hexdigest()
            case = {'title': 'model', 'available': True, 'files': [
                {'path': name, 'asset': 'snapshots/' + name, 'sha256': digest}
                for name in ['a-b.py', 'a_b.py']]}
            with self.assertRaisesRegex(ValueError, 'collision'):
                packages.organize(root, {'schema': 'index', 'cases': {'model': case}})
            case['files'] = [dict(case['files'][0], sha256='invalid')]
            with self.assertRaisesRegex(ValueError, 'digest mismatch'):
                packages.organize(root, {'schema': 'index', 'cases': {'model': case}})


if __name__ == '__main__':
    unittest.main()
