"""Project imports preserve source names, deduplicate, and persist atomically."""
import hashlib
from pathlib import Path
import tempfile
import unittest

from archcanvas_preview.component_library import packed, validate_module
from archcanvas_preview.component_store import ComponentStore
from test_preview_backend import FILES
import test_preview_backend as backend


class ProjectComponentLibraryTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name) / 'components'
        self.store = ComponentStore(self.root)

    def tearDown(self):
        self.temporary.cleanup()

    def test_multifile_import_reuses_versions_and_survives_restart(self):
        result = self.store.import_project(FILES, 'net.model:TwinPath', {'width': 24}, 'Independent Project')
        self.assertEqual(result['added'], 5)
        self.assertEqual(result['candidates'], 6)
        self.assertFalse(result['analysis']['modelExecuted'])
        catalog = ComponentStore(self.root).catalog()
        self.assertEqual(catalog['stats']['variants'], 5)
        self.assertIn('TwinPath', [f['title'] for f in catalog['families']])
        for family in catalog['families']:
            for variant in family['variants']:
                module = self.store.module(variant['id'])
                self.assertTrue(validate_module(module))
                raw = packed(module)
                self.assertEqual(len(raw), variant['bytes'])
                self.assertEqual(hashlib.sha256(raw).hexdigest(), variant['sha256'])
                self.assertEqual(module['title'], module['ir']['nodes'][0]['label'])
        before = self.store.path.read_bytes()
        again = self.store.import_project(FILES, 'net.model:TwinPath', {'width': 24}, 'Independent Project')
        self.assertEqual((again['added'], again['reused']), (0, 5))
        self.assertEqual(before, self.store.path.read_bytes(), 'identical import cannot grow duplicate provenance')
        changed = self.store.import_project(FILES, 'net.model:TwinPath', {'width': 32}, 'Independent Project')
        self.assertGreater(changed['added'], 0)
        self.assertGreater(changed['reused'], 0)

    def test_invalid_import_preserves_existing_library(self):
        self.store.import_project(FILES, 'net.model:TwinPath')
        before = self.store.path.read_bytes()
        for files, entry in [({'../model.py': 'x = 1'}, 'model:Bad'), (FILES, 'missing:NoModel')]:
            with self.assertRaises(ValueError):
                self.store.import_project(files, entry)
            self.assertEqual(self.store.path.read_bytes(), before)
        with self.assertRaises(ValueError):
            self.store.module('../library.json')

    def test_source_is_never_executed_and_original_class_name_is_used(self):
        sentinel = Path(self.temporary.name) / 'executed'
        files = {'model.py': f'''from torch import nn
from pathlib import Path
Path({str(sentinel)!r}).write_text('should never run')
class PositionwiseFeedForward(nn.Module):
    def forward(self, x):
        return x + x
'''}
        self.store.import_project(files, 'model:PositionwiseFeedForward')
        self.assertFalse(sentinel.exists())
        family = next(f for f in self.store.catalog()['families'] if f['title'] == 'PositionwiseFeedForward')
        module = self.store.module(family['variants'][0]['id'])
        self.assertEqual(module['ir']['nodes'][0]['label'], 'PositionwiseFeedForward')


class ProjectComponentHTTPTests(unittest.TestCase):
    setUp = backend.PreviewHTTPTests.setUp
    tearDown = backend.PreviewHTTPTests.tearDown
    request = backend.PreviewHTTPTests.request

    def test_import_requires_session_and_serves_hash_bound_assets(self):
        path = '/api/preview/source-components/import'
        payload = dict(files=FILES, entry='net.model:TwinPath', config={'width': 24}, title='Project')
        self.assertEqual(self.request(path, payload, token=False)[0], 403)
        self.assertEqual(self.request(path, payload, origin='https://untrusted.invalid')[0], 403)
        self.assertEqual(self.request(path, {**payload, 'root': '/etc'})[0], 400)
        status, imported = self.request(path, payload)
        self.assertEqual(status, 201, imported)
        status, catalog = self.request('/api/preview/source-components')
        self.assertEqual(status, 200)
        variant = catalog['families'][0]['variants'][0]
        status, module = self.request('/api/preview/source-components/' + variant['id'])
        self.assertEqual(status, 200)
        self.assertEqual(hashlib.sha256(packed(module)).hexdigest(), variant['sha256'])


if __name__ == '__main__':
    unittest.main()
