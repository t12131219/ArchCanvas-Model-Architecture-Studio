"""Ordinary failed registration cannot leave a partly saved adaptation."""
import copy
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from archcanvas_adapters.registry import AdapterError, AdapterRegistry, merge_rules, scaffold_adapter_files


RULE = {'schema': 'archcanvas-source-rule/1', 'name': 'Atomic source loop',
        'match': {'type': 'ListComp', 'fields': {}},
        'nodes': [{'key': 'loop', 'at': [], 'parent': None, 'kind': 'SourceLoop'},
                  {'key': 'iter', 'at': ['generators', 0, 'iter'], 'parent': 'loop', 'kind': 'SourceExpression'},
                  {'key': 'body', 'at': ['elt'], 'parent': 'loop', 'kind': 'SourceExpression'}],
        'relations': [{'source': 'iter', 'target': 'body', 'proof': 'comprehension-iteration'}]}
FILES = {'model.py': 'from torch import nn\nclass A(nn.Module):\n def forward(self,x):\n  return [v.sin() for v in x]\n'}


def snapshot(directory):
    return {path.relative_to(directory).as_posix(): (path.read_bytes(), path.stat().st_mtime_ns)
            for path in directory.rglob('*.json') if path.is_file()}


class SourceRuleRegistryAtomicTests(unittest.TestCase):
    def setUp(self):
        self.first = scaffold_adapter_files(FILES, 'model:A', rules=[RULE])
        second_rule = copy.deepcopy(RULE); second_rule['name'] = 'Another independent source loop'
        self.multiple = scaffold_adapter_files(FILES, 'model:A', rules=[RULE, second_rule])

    def test_registry_directory_symlink_is_rejected_before_records_are_written(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); actual = root / 'actual'; actual.mkdir()
            link = root / 'registry'; link.symlink_to(actual, target_is_directory=True)
            with self.assertRaisesRegex(AdapterError, 'real directory'):
                AdapterRegistry(link).register_files(self.first, FILES)
            self.assertEqual(list(actual.iterdir()), [])

    def test_rule_directory_symlink_cannot_leave_a_saved_instance(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); registry = root / 'registry'; registry.mkdir()
            outside = root / 'outside'; outside.mkdir()
            (registry / 'rules').symlink_to(outside, target_is_directory=True)
            store = AdapterRegistry(registry)
            with self.assertRaises(AdapterError):
                store.register_files(self.first, FILES)
            self.assertEqual(list(registry.glob('adapter-*.json')), [])
            self.assertEqual(store.matching_files(FILES), [])
            self.assertEqual(list(outside.iterdir()), [])

    def test_all_destination_links_and_directories_are_prechecked(self):
        for invalid_kind in ('symlink', 'directory'):
            with self.subTest(invalid_kind=invalid_kind), tempfile.TemporaryDirectory() as temporary:
                registry = Path(temporary, 'registry'); (registry / 'rules').mkdir(parents=True)
                target = registry / 'rules' / (self.multiple['rules'][-1]['id'] + '.json')
                if invalid_kind == 'symlink':
                    outside = Path(temporary, 'outside.json'); outside.write_text('unchanged')
                    target.symlink_to(outside)
                else:
                    target.mkdir()
                with self.assertRaises(AdapterError):
                    AdapterRegistry(registry).register_files(self.multiple, FILES)
                self.assertEqual(list(registry.glob('adapter-*.json')), [])
                self.assertFalse((registry / 'rules' / (self.multiple['rules'][0]['id'] + '.json')).exists())
                if invalid_kind == 'symlink':
                    self.assertEqual(outside.read_text(), 'unchanged')

    def test_final_instance_commit_failure_rolls_back_new_and_overwritten_rules(self):
        with tempfile.TemporaryDirectory() as temporary:
            registry = Path(temporary); store = AdapterRegistry(registry)
            saved = store.register_files(self.first, FILES)
            # Different whitespace is valid registry JSON and must be restored
            # byte for byte, including its previous modification timestamp.
            rule_path = Path(saved['rules'][0]['path'])
            rule_path.write_text(rule_path.read_text() + '\n\n')
            os.utime(rule_path, ns=(1234567890000000000, 1234567890000000000))
            before = snapshot(registry)
            real_replace = os.replace
            def fail_instance(source, target):
                if Path(target).name == self.multiple['id'] + '.json':
                    raise OSError('injected instance commit failure')
                return real_replace(source, target)
            with patch('archcanvas_adapters.registry.os.replace', side_effect=fail_instance), self.assertRaisesRegex(AdapterError, 'rolled back'):
                store.register_files(self.multiple, FILES)
            self.assertEqual(snapshot(registry), before)
            self.assertFalse(list(registry.rglob('.registration-*.tmp')))
            self.assertEqual(store.matching_files(FILES), [self.first])

    def test_partial_staging_failure_changes_no_records(self):
        with tempfile.TemporaryDirectory() as temporary:
            registry = Path(temporary); store = AdapterRegistry(registry)
            store.register_files(self.first, FILES); before = snapshot(registry)
            real_mkstemp = tempfile.mkstemp
            calls = 0
            def fail_staging(*args, **kwargs):
                nonlocal calls
                calls += 1
                if calls == 3:
                    raise OSError('injected staging failure')
                return real_mkstemp(*args, **kwargs)
            with patch('archcanvas_adapters.registry.tempfile.mkstemp', side_effect=fail_staging), self.assertRaisesRegex(AdapterError, 'rolled back'):
                store.register_files(self.multiple, FILES)
            self.assertEqual(snapshot(registry), before)
            self.assertFalse(list(registry.rglob('.registration-*.tmp')))

    def test_standalone_rule_save_rolls_back_earlier_commits(self):
        with tempfile.TemporaryDirectory() as temporary:
            registry = Path(temporary); store = AdapterRegistry(registry)
            store._save_rules([self.first['rules'][0]])
            before = snapshot(registry)
            target_to_fail = registry / 'rules' / (self.multiple['rules'][1]['id'] + '.json')
            real_replace = os.replace
            failed = False
            def fail_once(source, target):
                nonlocal failed
                if Path(target) == target_to_fail and not failed:
                    failed = True
                    raise OSError('injected rule commit failure')
                return real_replace(source, target)
            with patch('archcanvas_adapters.registry.os.replace', side_effect=fail_once), self.assertRaisesRegex(AdapterError, 'rolled back'):
                store._save_rules(self.multiple['rules'])
            self.assertEqual(snapshot(registry), before)

    def test_success_saves_instance_and_templates_without_staging_files(self):
        with tempfile.TemporaryDirectory() as temporary:
            registry = Path(temporary); store = AdapterRegistry(registry)
            saved = store.register_files(self.multiple, FILES)
            self.assertEqual(saved['status'], 'registered')
            self.assertEqual(len(saved['rules']), 2)
            self.assertEqual(len(store.rule_definitions()), 2)
            self.assertEqual(store.matching_files(FILES), [self.multiple])
            self.assertFalse(list(registry.rglob('*.tmp')))

    def test_merge_rules_deduplicates_validated_canonical_templates(self):
        canonical = self.first['rules'][0]
        self.assertEqual(merge_rules([RULE], [canonical], None), [canonical])
        self.assertEqual(merge_rules(RULE, [RULE]), [canonical])
        self.assertEqual(len(merge_rules(self.multiple['rules'], [RULE])), 2)
        forged = copy.deepcopy(canonical); forged['nodes'][0]['kind'] = 'tensor'
        with self.assertRaises(AdapterError):
            merge_rules([canonical], [forged])

    def test_merge_rules_rejects_bad_collections_and_excess_distinct_rules(self):
        with self.assertRaises(AdapterError):
            merge_rules('python-hook.py')
        templates = []
        for index in range(17):
            template = copy.deepcopy(RULE); template['name'] = 'Rule ' + str(index)
            templates.append(template)
        with self.assertRaisesRegex(AdapterError, '16 distinct'):
            merge_rules(templates)


if __name__ == '__main__':
    unittest.main()
