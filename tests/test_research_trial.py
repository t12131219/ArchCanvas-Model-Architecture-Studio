"""Trial package negative cases use explicit automation fixtures, never human evidence."""
import base64
import copy
import importlib.util
import json
import shutil
import tempfile
import unittest
import xml.etree.ElementTree as ET
from unittest import mock
from datetime import datetime, timedelta, timezone
from pathlib import Path

FORMAL = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('research_trial', FORMAL / 'scripts/research_trial.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
from archcanvas_cli.workspace import Workspace

PNG = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=')


class ResearchTrialTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='archcanvas-trial-test-')
        self.root = Path(self.temporary.name)
        # Freeze a test-owned formal copy so concurrent Studio work cannot alter
        # a trial's implementation while these binding counterexamples run.
        self.project = self.root / 'formal'
        for name in ('src', 'fixtures/transformer', 'studio/src/core', 'studio/dist'):
            shutil.copytree(FORMAL / name, self.project / name, ignore=shutil.ignore_patterns('__pycache__'))
        (self.project / 'scripts').mkdir()
        # ``export_canvas.mjs`` stages the artifact and receipt through the
        # paired commit helper. Keep the frozen test checkout complete so the
        # trial exercises the same export contract as the formal runtime.
        for name in ('research_trial.py', 'research_trial_core.mjs', 'summarize_research_tasks.py', 'export_canvas.mjs', 'atomic_export.mjs'):
            shutil.copyfile(FORMAL / 'scripts' / name, self.project / 'scripts' / name)
        self.old_root, module.ROOT = module.ROOT, self.project
        self.package = self.root / 'package'
        self.manifest = module.prepare(self.package, 3)
        self.slot = self.package / 'slots/S01'
        module.assign(self.package, 'S01', 'AUTOMATION_BINDING_TEST', 'automation')
        self.document = module.read_json(self.package / 'baseline/canvas.json')
        self.study_path = self.slot / 'incoming/automation.json'
        started = datetime(2026, 10, 4, 12, tzinfo=timezone.utc)
        self.study = {'schemaVersion': 1, 'protocol': 'archcanvas-m4-research-task/1',
            'participantCode': 'AUTOMATION_BINDING_TEST', 'participantKind': 'automation',
            'startedAt': started.isoformat(), 'finishedAt': (started + timedelta(seconds=120)).isoformat(),
            'outcome': 'completed', 'notes': 'Explicit test fixture; no researcher performed this task.',
            'checkpoints': [{'task': index + 1, 'selfReportedComplete': True, 'elapsedMs': (index + 1) * 20000,
                'observation': {'at': (started + timedelta(seconds=(index + 1) * 20)).isoformat(),
                    'documentId': self.document['id'], 'visualRevision': '0',
                    'sourceDigest': self.document['architecture']['sourceDigest'],
                    'irDigest': self.document['architecture']['irDigest'],
                    'visibleNodes': 8, 'expandedNodes': self.document['expandedIds'], 'exportLinks': []}}
                for index in range(5)]}
        self.save_study()
        self.shot = self.slot / 'incoming/test-fixture.png'
        self.shot.write_bytes(PNG)

    def tearDown(self):
        module.ROOT = self.old_root
        self.temporary.cleanup()

    def save_study(self):
        module.write_json(self.study_path, self.study)

    def export(self, document=None):
        return Workspace(self.slot / 'workspace', self.project).export(document or self.document, 'svg', 300)

    def collect(self, artifact=None, shots=None, code='AUTOMATION_BINDING_TEST'):
        return module.collect(self.package, 'S01', code, self.study_path,
            [artifact['id']] if artifact else [], shots if shots is not None else {'start': self.shot, 'final': self.shot})

    def test_unassigned_slots_have_separate_stores_and_identical_frozen_baselines(self):
        self.assertEqual(self.manifest['researcherCount'], 0)
        self.assertEqual(self.manifest['researchGate'], 'not_run')
        paths, hashes = [], []
        for slot in self.manifest['slots']:
            self.assertIsNone(slot['participantCode'])
            self.assertEqual(slot['assignment'], 'unassigned')
            paths.append(slot['dataDir'])
            hashes.append(slot['baselineEnvelope']['sha256'])
        self.assertEqual(len(set(paths)), 3)
        self.assertEqual(len(set(hashes)), 1)
        with self.assertRaisesRegex(ValueError, 'already exists'):
            module.prepare(self.package, 3)
        self.assertFalse(list(self.package.glob('slots/*/collected')))

    def test_actual_canvas_scene_export_and_screenshot_hashes_bound_without_human_pass(self):
        artifact = self.export()
        result = self.collect(artifact)
        self.assertEqual(result['researchGate'], 'not_run')
        self.assertEqual(result['reviewStatus'], 'self-report-pending-independent-review')
        self.assertFalse(result['humanSuccessCertified'])
        self.assertFalse(result['includedInSelfReportedResearcherDenominator'])
        bundle = self.slot / 'collected'
        for binding in result['canvasFiles'] + result['exports'][0]['files'] + result['screenshots']:
            self.assertEqual(binding['sha256'], module.sha((bundle / binding['path']).read_bytes()))
        self.assertEqual(result['exports'][0]['inputCanvasCanonicalDigest'], result['final']['canvasCanonicalDigest'])
        self.assertTrue(all(shot['contentReview'] == 'pending' for shot in result['screenshots']))
        with self.assertRaisesRegex(ValueError, 'already collected'):
            self.collect(artifact)

    def test_participant_document_digest_and_revision_mismatches_rejected(self):
        artifact = self.export()
        for field, invalid in (('documentId', 'wrong-document'), ('sourceDigest', '0' * 64),
                               ('irDigest', '0' * 64), ('visualRevision', '5')):
            with self.subTest(field=field):
                original = self.study['checkpoints'][-1]['observation'][field]
                self.study['checkpoints'][-1]['observation'][field] = invalid
                self.save_study()
                with self.assertRaisesRegex(ValueError, 'binding|changed'):
                    self.collect(artifact)
                self.study['checkpoints'][-1]['observation'][field] = original
        self.save_study()
        with self.assertRaisesRegex(ValueError, 'Participant assignment'):
            self.collect(artifact, code='A_DIFFERENT_PERSON')
        self.assertFalse((self.slot / 'collected').exists())

    def test_export_of_different_canvas_at_same_revision_is_rejected(self):
        changed = copy.deepcopy(self.document)
        changed['displayAliases'][changed['architecture']['nodes'][0]['id']] = 'Different actual Canvas'
        artifact = self.export(changed)
        with self.assertRaisesRegex(ValueError, 'exact final saved CanvasDocument'):
            self.collect(artifact)

    def test_export_file_hash_and_scene_receipt_mismatches_are_rejected(self):
        artifact = self.export()
        directory = self.slot / 'workspace/exports' / artifact['id']
        figure = directory / 'figure.svg'
        raw = figure.read_bytes()
        figure.write_bytes(raw + b'<!--tampered-->')
        with self.assertRaisesRegex(ValueError, 'output hash'):
            self.collect(artifact)
        figure.write_bytes(raw)
        receipt_path = directory / 'figure.svg.receipt.json'
        receipt = module.read_json(receipt_path)
        receipt['sceneSvgDigest'] = '0' * 64
        module.write_json(receipt_path, receipt)
        with self.assertRaisesRegex(ValueError, 'Scene digest'):
            self.collect(artifact)
        self.assertFalse((self.slot / 'collected').exists())
        self.assertFalse(list(self.slot.glob('.research-collect-*')))

    def test_missing_or_invalid_screenshots_and_missing_completed_export_rejected(self):
        artifact = self.export()
        with self.assertRaisesRegex(ValueError, 'start/final screenshots'):
            self.collect(artifact, shots={'start': self.shot})
        self.shot.write_bytes(b'not a screenshot')
        with self.assertRaisesRegex(ValueError, 'actual PNG'):
            self.collect(artifact)
        self.shot.write_bytes(PNG)
        with self.assertRaisesRegex(ValueError, 'actual SVG/PDF export'):
            self.collect()

    def test_changed_frozen_source_or_implementation_refuses_collection(self):
        path = self.package / 'baseline/source/model.py'
        raw = path.read_bytes()
        path.write_bytes(raw + b'\n# changed\n')
        with self.assertRaisesRegex(ValueError, 'Frozen baseline file hash'):
            self.collect()
        path.write_bytes(raw)
        path = self.project / 'scripts/export_canvas.mjs'
        path.write_text(path.read_text() + '\n// changed\n')
        with self.assertRaisesRegex(ValueError, 'implementation changed'):
            self.collect()

    def test_other_slot_exports_cannot_be_adopted_through_symlinks(self):
        artifact = self.export()
        source = self.slot / 'workspace/exports' / artifact['id']
        foreign = self.package / 'slots/S02/workspace/exports' / artifact['id']
        source.rename(foreign)
        source.symlink_to(foreign, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, 'symlink|escaped'):
            self.collect(artifact)

    def test_abandoned_session_still_collects_without_export_and_remains_pending(self):
        self.study['outcome'] = 'abandoned'
        self.study['checkpoints'] = []
        self.save_study()
        result = self.collect()
        self.assertEqual(result['selfReportedOutcome'], 'abandoned')
        self.assertEqual(result['exports'], [])
        self.assertFalse(result['humanSuccessCertified'])

    def test_assignment_refuses_used_baseline_duplicate_codes_and_reassignment(self):
        with self.assertRaisesRegex(ValueError, 'already assigned'):
            module.assign(self.package, 'S01', 'OTHER_AUTOMATION', 'automation')
        with self.assertRaisesRegex(ValueError, 'already assigned'):
            module.assign(self.package, 'S02', 'AUTOMATION_BINDING_TEST', 'automation')
        path = self.package / self.manifest['slots'][1]['baselineEnvelope']['path']
        envelope = module.read_json(path)
        envelope['document']['displayAliases'][self.document['architecture']['nodes'][0]['id']] = 'Prior trial edit'
        module.write_json(path, envelope)
        with self.assertRaisesRegex(ValueError, 'pristine frozen baseline'):
            module.assign(self.package, 'S02', 'OTHER_AUTOMATION', 'automation')
        self.assertFalse((self.package / 'slots/S02/assignment.json').exists())

    def test_core_wait_preserves_verified_snapshot_when_live_artifacts_change(self):
        artifact = self.export()
        directory = self.slot / 'workspace/exports' / artifact['id']
        document_path = self.slot / 'workspace/documents' / f"{self.document['id']}.json"
        expected_storage = document_path.read_bytes()
        expected_exports = {path.name: path.read_bytes() for path in directory.iterdir()}
        expected_assignment = (self.slot / 'assignment.json').read_bytes()
        expected_shot = self.shot.read_bytes()
        original_core = module.core

        def save_and_mutate_during_core(action, input_path, output_path):
            changed = copy.deepcopy(self.document)
            changed['revision'] = 1
            changed['displayAliases'][changed['architecture']['nodes'][0]['id']] = 'A later service save'
            module.DocumentStore(document_path.parent).put(changed['id'], changed, 1)
            for path in directory.iterdir():
                path.write_bytes(b'changed after the collector verified its bytes')
            self.shot.write_bytes(b'changed after screenshot signature validation')
            (self.slot / 'assignment.json').write_bytes(b'changed after assignment validation')
            return original_core(action, input_path, output_path)

        with mock.patch.object(module, 'core', side_effect=save_and_mutate_during_core):
            result = self.collect(artifact)
        bundle = self.slot / 'collected'
        self.assertEqual((bundle / 'final-storage.json').read_bytes(), expected_storage)
        self.assertEqual((bundle / 'assignment.json').read_bytes(), expected_assignment)
        for name, raw in expected_exports.items():
            self.assertEqual((bundle / 'exports' / artifact['id'] / name).read_bytes(), raw)
        for label in ('start', 'final'):
            self.assertEqual((bundle / 'screenshots' / f'{label}.png').read_bytes(), expected_shot)
        self.assertEqual(module.read_json(bundle / 'final-storage.json')['document'], module.read_json(bundle / 'final.canvas.json'))
        self.assertEqual(result['final']['storageRevision'], 1)
        self.assertEqual(result['final']['visualRevision'], 0)
        self.assertFalse(result['humanSuccessCertified'])

    def test_synchronized_svg_and_receipt_tampering_is_rejected(self):
        artifact = self.export()
        directory = self.slot / 'workspace/exports' / artifact['id']
        figure = directory / 'figure.svg'
        receipt_path = directory / 'figure.svg.receipt.json'
        receipt = module.read_json(receipt_path)
        # Real publisher XML normalization means these legitimately differ.
        self.assertNotEqual(receipt['outputDigest'], receipt['sceneSvgDigest'])
        root = ET.fromstring(figure.read_bytes())
        label = next(element for element in root.iter() if element.tag.endswith('}text') and element.text)
        label.text = 'SYNCHRONIZED FORGED FIGURE LABEL'
        forged = ET.tostring(root, encoding='utf-8')
        figure.write_bytes(forged)
        receipt['outputDigest'] = module.sha(forged)
        receipt['svgDigest'] = module.sha(forged)
        receipt['bytes'] = len(forged)
        module.write_json(receipt_path, receipt)
        with self.assertRaisesRegex(ValueError, 'independently regenerated published SVG'):
            self.collect(artifact)
        self.assertFalse((self.slot / 'collected').exists())


if __name__ == '__main__':
    unittest.main()
