"""Automation-only fixtures verify matrix bindings; none are real browser evidence."""
import base64
import copy
import importlib.util
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

FORMAL = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('browser_visual_matrix', FORMAL / 'scripts/browser_visual_matrix.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
PNG = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=')


class BrowserVisualMatrixTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.shared = tempfile.TemporaryDirectory(prefix='archcanvas-matrix-test-')
        cls.project = Path(cls.shared.name) / 'formal'
        for name in ('src', 'fixtures/transformer', 'fixtures/mlp', 'fixtures/residual_cnn', 'studio/src/core', 'studio/dist'):
            shutil.copytree(FORMAL / name, cls.project / name, ignore=shutil.ignore_patterns('__pycache__'))
        (cls.project / 'scripts').mkdir()
        for name in ('browser_visual_matrix.py', 'browser_visual_core.mjs', 'check_visual_golds.py', 'check_independence.py', 'check_stage2.py'):
            shutil.copyfile(FORMAL / 'scripts' / name, cls.project / 'scripts' / name)
        cls.core_dir = Path(cls.shared.name) / 'core-golds'
        python = str(FORMAL / '.venv/bin/python') if (FORMAL / '.venv/bin/python').exists() else shutil.which('python3')
        result = subprocess.run([python, str(cls.project / 'scripts/check_visual_golds.py'),
            '--project', str(cls.project), '--python', python, '--output', str(cls.core_dir)],
            capture_output=True, text=True, timeout=30)
        if result.returncode:
            raise RuntimeError(result.stderr)

    @classmethod
    def tearDownClass(cls):
        cls.shared.cleanup()

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='archcanvas-matrix-case-')
        self.root = Path(self.temporary.name)
        self.old_root, module.ROOT = module.ROOT, self.project
        self.matrix = self.root / 'matrix'
        self.specification = module.prepare(self.core_dir, self.matrix)
        self.input = self.root / 'input'
        self.input.mkdir()
        self.list_path = self.input / 'captures.json'
        self.output = self.root / 'collected'
        self.records = {'schemaVersion': 1, 'protocol': module.PROTOCOL, 'captures': []}
        self.save_list()

    def tearDown(self):
        module.ROOT = self.old_root
        self.temporary.cleanup()

    def save_list(self):
        module.write(self.list_path, self.records)

    def capture(self, state='baseline', alias=None):
        variant = next(item for item in self.specification['variants'] if item['variantId'] == 'mlp-level1-paper-180')
        document = module.read(Path(variant['canvasFile']))
        document['revision'] = 99  # A real UI traversal need not match candidate revision.
        if alias:
            document['displayAliases'][document['architecture']['nodes'][0]['id']] = alias
        case = 'AUTOMATION_MATRIX_' + state
        directory = self.input / case
        directory.mkdir()
        helper_input = directory / 'helper.json'
        module.write(helper_input, [{'document': document}])
        result = subprocess.run([shutil.which('node'), str(self.project / 'scripts/browser_visual_core.mjs'),
            str(helper_input), str(directory / 'expected')], capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        browser_scene = (directory / 'expected/0.interactive.svg').read_bytes()
        original = (directory / 'expected/0.publication.svg').read_bytes()
        publication = module.export_svg(original.decode(), format='svg', width_mm=180, dpi=300)
        receipt = {**publication['receipt'], 'documentId': document['id'], 'revision': document['revision'],
            'sourceDigest': variant['sourceDigest'], 'irDigest': variant['irDigest'],
            'sceneSvgDigest': module.sha(original), 'exportScope': {'kind': 'document'}}
        module.write(directory / 'canvas.json', {'revision': 7, 'document': document})
        (directory / 'figure.svg').write_bytes(publication['data'])
        module.write(directory / 'export-receipt.json', receipt)
        (directory / 'screenshot.png').write_bytes(PNG)
        (directory / 'browser-scene.svg').write_bytes(browser_scene)
        screen = {'schemaVersion': 1, 'protocol': module.CAPTURE_PROTOCOL, 'caseId': case,
            'variantId': variant['variantId'], 'state': state, 'captureKind': 'studio-browser',
            'capturedAt': '2026-10-04T12:00:00Z', 'captureScope': 'automation-test-fixture',
            'documentBinding': {'documentId': document['id'], 'revision': 99, 'sourceDigest': variant['sourceDigest'], 'irDigest': variant['irDigest']},
            'pageSpec': {'widthMm': 180, 'preset': 'paper'}, 'expandedIds': document['expandedIds'],
            'screenshotDigest': module.sha(PNG), 'browserSceneDigest': module.semantic_svg_digest(browser_scene),
            'environment': {'userAgent': 'AUTOMATION TEST FIXTURE; NO ACTUAL BROWSER', 'viewport': {'width': 1000, 'height': 800}, 'devicePixelRatio': 1},
            'camera': {'transform': 'matrix(1,0,0,1,0,0)', 'sceneScreenBounds': {'x': 0, 'y': 0, 'width': 800, 'height': 600}},
            'loadedBuildAssets': [{'path': item['path'], 'url': 'http://127.0.0.1:8769/' + item['path'], 'sha256': item['sha256']}
                for item in self.specification['buildFiles'] if item['path'].endswith(('.js', '.css'))],
            'limitations': ['Explicit automation fixture; no actual browser capture or human visual acceptance.']}
        module.write(directory / 'screen-receipt.json', screen)
        record = {'caseId': case, 'variantId': variant['variantId'], 'state': state,
            **{field: f'{case}/{name}' for field, name in {'canvas': 'canvas.json', 'svg': 'figure.svg',
                'exportReceipt': 'export-receipt.json', 'screenshot': 'screenshot.png',
                'browserScene': 'browser-scene.svg', 'screenReceipt': 'screen-receipt.json'}.items()}}
        self.records['captures'].append(record)
        self.save_list()
        return directory, record

    def collect(self):
        return module.collect(self.matrix, self.list_path, self.output)

    def test_actual_authored_frontiers_are_36_without_fabricated_shallow_depths(self):
        self.assertEqual(len(self.specification['variants']), 36)
        levels = {fixture: [item['level'] for item in self.specification['frontiers'] if item['fixture'] == fixture] for fixture in module.FIXTURES}
        self.assertEqual(levels, {'transformer': [0, 1, 2, 3], 'mlp': [0, 1], 'residual_cnn': [0, 1, 2]})
        with self.assertRaisesRegex(ValueError, 'already exists'):
            module.prepare(self.core_dir, self.matrix)

    def test_empty_index_marks_every_preview_missing_and_human_gate_pending(self):
        result = self.collect()
        self.assertEqual(result['capturedBaselineCount'], 0)
        self.assertEqual(len(result['missingBaselineVariants']), 36)
        self.assertEqual(result['visualAcceptance'], 'pending-human-review')
        self.assertFalse(result['humanAcceptanceCertified'])
        index = (self.output / 'index.html').read_text()
        self.assertEqual(index.count('缺浏览器截图 · 正式 core 候选预览</p>'), 36)
        self.assertIn('浏览器基线 0/36', index)

    def test_exact_bound_files_allow_actual_ui_revision_and_still_cannot_grant_acceptance(self):
        directory, record = self.capture()
        result = self.collect()
        self.assertEqual(result['capturedBaselineCount'], 1)
        self.assertEqual(result['captures'][0]['documentBinding']['revision'], 99)
        self.assertEqual(result['artifactCoverage'], 'incomplete')
        self.assertFalse(result['humanAcceptanceCertified'])
        for field, expected in result['captures'][0]['files'].items():
            self.assertEqual((self.output / expected['path']).read_bytes(), (self.input / record[field]).read_bytes())

    def test_wrong_frontier_page_source_and_screenshot_binding_rejected(self):
        directory, _ = self.capture()
        canvas_path = directory / 'canvas.json'
        canvas = module.read(canvas_path)
        for mutate in (lambda d: d.update(expandedIds=[]), lambda d: d['pageSpec'].update(widthMm=85),
                       lambda d: d['architecture'].update(irDigest='0' * 64)):
            corrupt = copy.deepcopy(canvas)
            mutate(corrupt['document'])
            module.write(canvas_path, corrupt)
            with self.assertRaisesRegex(ValueError, 'declared source/frontier/page'):
                self.collect()
        module.write(canvas_path, canvas)
        screen_path = directory / 'screen-receipt.json'
        screen = module.read(screen_path)
        screen['screenshotDigest'] = '0' * 64
        module.write(screen_path, screen)
        with self.assertRaisesRegex(ValueError, 'Screen receipt differs'):
            self.collect()

    def test_dom_and_synchronized_publication_tampering_rejected(self):
        directory, _ = self.capture()
        dom_path = directory / 'browser-scene.svg'
        dom = dom_path.read_bytes()
        forged = dom.replace(b'>MLP<', b'>FORGED MODEL<', 1)
        self.assertNotEqual(forged, dom)
        dom_path.write_bytes(forged)
        screen_path = directory / 'screen-receipt.json'
        screen = module.read(screen_path)
        screen['browserSceneDigest'] = module.semantic_svg_digest(forged)
        module.write(screen_path, screen)
        with self.assertRaisesRegex(ValueError, 'browser Scene differs'):
            self.collect()
        dom_path.write_bytes(dom)
        screen['browserSceneDigest'] = module.semantic_svg_digest(dom)
        module.write(screen_path, screen)
        figure = directory / 'figure.svg'
        forged = figure.read_bytes().replace(b'>MLP<', b'>FORGED MODEL<', 1)
        figure.write_bytes(forged)
        receipt_path = directory / 'export-receipt.json'
        receipt = module.read(receipt_path)
        receipt.update(outputDigest=module.sha(forged), svgDigest=module.sha(forged), bytes=len(forged))
        module.write(receipt_path, receipt)
        with self.assertRaisesRegex(ValueError, 'independent formal normalization'):
            self.collect()

    def test_old_loaded_build_and_edited_baseline_labels_rejected(self):
        directory, _ = self.capture()
        screen_path = directory / 'screen-receipt.json'
        screen = module.read(screen_path)
        screen['loadedBuildAssets'][0]['sha256'] = '0' * 64
        module.write(screen_path, screen)
        with self.assertRaisesRegex(ValueError, 'frozen JS/CSS build'):
            self.collect()
        canvas_path = directory / 'canvas.json'
        canvas = module.read(canvas_path)
        canvas['document']['displayAliases'][canvas['document']['architecture']['nodes'][0]['id']] = 'Prior participant edit'
        module.write(canvas_path, canvas)
        with self.assertRaisesRegex(ValueError, 'unedited baseline'):
            self.collect()

    def test_edited_case_is_separate_from_baseline_and_pending(self):
        self.capture(state='edited', alias='Actual edited test alias')
        result = self.collect()
        self.assertEqual(result['capturedBaselineCount'], 0)
        self.assertEqual(result['editedAfterModelsCaptured'], ['mlp'])
        self.assertEqual(result['captures'][0]['changedVisualFields'], ['displayAliases'])
        self.assertFalse(result['humanAcceptanceCertified'])

    def test_live_changes_during_core_do_not_mix_verified_artifact_snapshot(self):
        directory, record = self.capture()
        expected = {field: (self.input / record[field]).read_bytes() for field in ('canvas', 'svg', 'exportReceipt', 'screenshot', 'browserScene', 'screenReceipt')}
        original_run = subprocess.run
        def mutate_then_run(*args, **kwargs):
            for field in expected:
                (self.input / record[field]).write_bytes(b'changed after validation')
            return original_run(*args, **kwargs)
        with mock.patch.object(module.subprocess, 'run', side_effect=mutate_then_run):
            result = self.collect()
        for field, bound in result['captures'][0]['files'].items():
            self.assertEqual((self.output / bound['path']).read_bytes(), expected[field])


if __name__ == '__main__':
    unittest.main()
