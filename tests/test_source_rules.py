"""Independent rule evidence, negative relations and cross-symbol reuse."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from archcanvas_adapters.registry import AdapterError, scaffold_adapter_files
from archcanvas_adapters.source_rules import (
    validate_rule, compile_rule_adapter_files, validate_rule_adapter_files,
)


def comprehension_rule():
    return {
        'schema': 'archcanvas-source-rule/1', 'name': 'One authored comprehension',
        'match': {'type': 'ListComp', 'fields': {'generators': [
            {'type': 'comprehension', 'fields': {'is_async': 0}},
        ]}},
        'nodes': [
            {'key': 'comp', 'at': [], 'parent': None, 'kind': 'SourceLoop'},
            {'key': 'iterable', 'at': ['generators', 0, 'iter'], 'parent': 'comp', 'kind': 'SourceExpression'},
            {'key': 'body', 'at': ['elt'], 'parent': 'comp', 'kind': 'SourceExpression'},
        ],
        'relations': [{'source': 'iterable', 'target': 'body', 'proof': 'comprehension-iteration'}],
    }


SOURCE = '''from torch import nn
class Uncatalogued(nn.Module):
 def forward(self, batch):
  values=[token.sin() for token in batch if token is not None]
  return values
'''
FILES = {'unseen.py': SOURCE}


def compile_source(expression, rule=None):
    source = 'from torch import nn\nclass A(nn.Module):\n def forward(self, xs, other):\n  return ' + expression + '\n'
    return compile_rule_adapter_files({'model.py': source}, 'model:A', rules=[rule or comprehension_rule()])


class SourceRuleTests(unittest.TestCase):
    def test_template_is_canonical_and_content_identified(self):
        first = validate_rule(comprehension_rule())
        self.assertRegex(first['id'], r'^rule-[a-f0-9]{24}$')
        self.assertEqual(first, validate_rule(first))
        changed = comprehension_rule()
        changed['name'] = 'Another reviewed source template'
        self.assertNotEqual(first['id'], validate_rule(changed)['id'])

    def test_new_comprehension_structure_is_not_old_parser_output(self):
        old = scaffold_adapter_files(FILES, 'unseen:Uncatalogued')
        self.assertFalse(any(node['kind'] == 'SourceLoop' for node in old['children']))
        new = compile_rule_adapter_files(FILES, 'unseen:Uncatalogued', rules=[comprehension_rule()])
        self.assertEqual(len(new['children']), 3)
        self.assertEqual(len(new['dependencies']), 1)
        root, iterable, body = new['children']
        self.assertEqual(root['label'], 'ListComp')
        self.assertEqual(root['source']['expression'], '[token.sin() for token in batch if token is not None]')
        self.assertEqual(iterable['source']['expression'], 'batch')
        self.assertEqual(body['source']['expression'], 'token.sin()')
        self.assertEqual(new['dependencies'][0]['kind'], 'source-data-dependency')
        self.assertTrue(new['dependencies'][0]['syntaxOnly'])
        self.assertEqual(root['parameters']['guards'], ['for token in batch', 'if token is not None'])
        self.assertTrue(all(node['ports'] == [] and node['sourceStructure'] for node in new['children']))
        self.assertIsNone(new['generationContract'])
        self.assertEqual(new, validate_rule_adapter_files(new, FILES))

    def test_interpreter_is_independent_of_source_structure_and_scaffold(self):
        with patch('archcanvas_python.source_structure.SourceStructure.populate', side_effect=AssertionError('Old inspector forbidden')), \
             patch('archcanvas_adapters.registry.scaffold_adapter_files', side_effect=AssertionError('Old scaffold forbidden')):
            result = compile_rule_adapter_files(FILES, 'unseen:Uncatalogued', rules=[comprehension_rule()])
            self.assertEqual(result, validate_rule_adapter_files(result, FILES))

    def test_one_template_reused_across_files_classes_methods_and_variable_names(self):
        first = compile_rule_adapter_files(FILES, 'unseen:Uncatalogued', rules=[comprehension_rule()])
        renamed = {'package/other.py': '''from torch import nn
class RenamedElsewhere(nn.Module):
 def __call__(self, incoming):
  return [piece.cos() for piece in incoming if piece is not None]
'''}
        second = compile_rule_adapter_files(renamed, 'package.other:RenamedElsewhere', rules=first['rules'])
        self.assertEqual(first['rules'], second['rules'])
        self.assertNotEqual(first['id'], second['id'])
        self.assertNotEqual(first['applications'][0]['matchKey'], second['applications'][0]['matchKey'])
        self.assertEqual(second['binding']['method'], '__call__')
        self.assertTrue(all(node['source']['path'] == 'package/other.py' for node in second['children']))
        self.assertTrue(any(node['source']['expression'] == 'incoming' for node in second['children']))

    def test_does_not_execute_source_constructor_or_forward(self):
        with tempfile.TemporaryDirectory() as temporary:
            marker = Path(temporary, 'executed')
            source = f"open({str(marker)!r}, 'w').write('top-level')\n" + SOURCE.replace(
                '  values=', f"  open({str(marker)!r}, 'w').write('forward')\n  values=")
            files = {'unseen.py': source}
            result = compile_rule_adapter_files(files, 'unseen:Uncatalogued', rules=[comprehension_rule()])
            validate_rule_adapter_files(result, files)
            self.assertFalse(marker.exists())

    def test_no_match_is_an_explicit_empty_instance(self):
        result = compile_source('xs.sin()')
        self.assertEqual(result['children'], [])
        self.assertEqual(result['applications'], [])
        self.assertEqual(result['dependencies'], [])

    def test_application_receipt_binds_every_selected_fact(self):
        result = compile_rule_adapter_files(FILES, 'unseen:Uncatalogued', rules=[comprehension_rule()])
        application = result['applications'][0]
        self.assertEqual(application['rootId'], result['children'][0]['id'])
        self.assertEqual(application['nodeIds'], [node['id'] for node in result['children']])
        self.assertEqual(application['source'], result['children'][0]['source'])
        self.assertTrue(all(node['parameters']['sourceRuleId'] == application['ruleId'] for node in result['children']))

    def test_unknown_executable_or_semantic_claim_fields_are_rejected(self):
        for name, value in [('python', "__import__('os')"), ('shape', [2, 3]), ('tensorPorts', []), ('replacement', 'x + y')]:
            with self.subTest(name=name):
                rule = comprehension_rule()
                rule[name] = value
                with self.assertRaises(AdapterError):
                    validate_rule(rule)
        for location in ('match', 'nodes', 'relations'):
            rule = comprehension_rule()
            target = rule['match'] if location == 'match' else rule[location][0]
            target['pythonHook'] = 'hook.py'
            with self.subTest(location=location), self.assertRaises(AdapterError):
                validate_rule(rule)

    def test_stale_or_forged_rule_id_is_rejected(self):
        rule = validate_rule(comprehension_rule())
        rule['id'] = 'rule-' + '0' * 24
        with self.assertRaisesRegex(AdapterError, 'ID'):
            validate_rule(rule)

    def test_ast_fields_and_selected_paths_are_checked(self):
        rule = comprehension_rule()
        rule['match']['fields']['invented'] = 4
        with self.assertRaisesRegex(AdapterError, 'actual fields'):
            validate_rule(rule)
        for path in (['generators', 10, 'iter'], ['generators', 0], ['__class__'], ['elt', 'lineno']):
            rule = comprehension_rule()
            rule['nodes'][1]['at'] = path
            with self.subTest(path=path), self.assertRaises(AdapterError):
                compile_rule_adapter_files(FILES, 'unseen:Uncatalogued', rules=[rule])

    def test_exact_primitive_types_do_not_confuse_bool_with_integer(self):
        rule = {'schema': 'archcanvas-source-rule/1', 'name': 'Integer literal only',
                'match': {'type': 'Constant', 'fields': {'value': 1}},
                'nodes': [{'key': 'literal', 'at': [], 'parent': None, 'kind': 'SourceExpression'}], 'relations': []}
        result = compile_source('(True, 1, 1.0)', rule)
        self.assertEqual([node['source']['expression'] for node in result['children']], ['1'])

    def test_comprehension_exact_list_pattern_does_not_match_two_generators(self):
        self.assertEqual(compile_source('[x + y for x in xs for y in other]')['children'], [])

    def test_unused_or_shadowed_comprehension_bindings_cannot_prove_edges(self):
        for expression in ('[42 for x in xs]', '[[x for x in other] for x in xs]', '[(lambda x: x)(1) for x in xs]'):
            with self.subTest(expression=expression), self.assertRaisesRegex(AdapterError, 'does not read'):
                compile_source(expression)

    def test_nested_scope_can_read_outer_binding_without_shadowing_it(self):
        result = compile_source('[[x + y for y in other] for x in xs]')
        # The template also matches the nested one-generator comprehension.
        self.assertEqual(len(result['applications']), 2)
        self.assertEqual(len(result['dependencies']), 2)

    def test_later_generator_shadowing_is_not_treated_as_original_binding(self):
        rule = comprehension_rule()
        rule['match']['fields'] = {}
        with self.assertRaisesRegex(AdapterError, 'shadowing'):
            compile_source('[x for x in xs for x in other]', rule)

    def test_later_generator_iteration_uses_its_own_lexical_binding(self):
        rule = comprehension_rule()
        rule['match']['fields'] = {}
        rule['nodes'][1]['at'] = ['generators', 1, 'iter']
        result = compile_source('[y for x in xs for y in x]', rule)
        self.assertEqual(len(result['dependencies']), 1)
        self.assertEqual(result['children'][1]['source']['expression'], 'x')

    def test_dict_set_and_generator_comprehensions_are_evidence_based(self):
        for kind, expression, output in [
            ('DictComp', '{x: x.sin() for x in xs}', 'value'),
            ('SetComp', '{x.sin() for x in xs}', 'elt'),
            ('GeneratorExp', '(x.sin() for x in xs)', 'elt'),
        ]:
            rule = comprehension_rule()
            rule['match']['type'] = kind
            rule['nodes'][2]['at'] = [output]
            with self.subTest(kind=kind):
                result = compile_source(expression, rule)
                self.assertEqual(len(result['dependencies']), 1)

    def test_expression_input_only_accepts_immediate_value_operands(self):
        rule = {'schema': 'archcanvas-source-rule/1', 'name': 'Binary expression operands',
                'match': {'type': 'BinOp', 'fields': {}},
                'nodes': [{'key': 'expression', 'at': [], 'parent': None, 'kind': 'SourceExpression'},
                          {'key': 'left', 'at': ['left'], 'parent': 'expression', 'kind': 'SourceExpression'}],
                'relations': [{'source': 'left', 'target': 'expression', 'proof': 'expression-input'}]}
        self.assertEqual(len(compile_source('xs.sin() + other', rule)['dependencies']), 1)
        rule['relations'][0].update(source='expression', target='left')
        with self.assertRaisesRegex(AdapterError, 'immediate value operand'):
            compile_source('xs.sin() + other', rule)

    def test_call_keyword_and_computed_function_operands_are_supported(self):
        for path, expression in [(['keywords', 0, 'value'], 'apply(value=xs)'), (['func'], 'factory(xs)(other)')]:
            rule = {'schema': 'archcanvas-source-rule/1', 'name': 'Direct call value',
                    'match': {'type': 'Call', 'fields': {'args': []} if path[0] == 'keywords' else {'func': {'type': 'Call', 'fields': {}}}},
                    'nodes': [{'key': 'call', 'at': [], 'parent': None, 'kind': 'SourceCall'},
                              {'key': 'operand', 'at': path, 'parent': 'call', 'kind': 'SourceExpression'}],
                    'relations': [{'source': 'operand', 'target': 'call', 'proof': 'expression-input'}]}
            with self.subTest(path=path):
                self.assertEqual(len(compile_source(expression, rule)['dependencies']), 1)

    def test_conditional_branches_cannot_be_joined_by_syntax_order(self):
        rule = {'schema': 'archcanvas-source-rule/1', 'name': 'Conditional expressions stay distinct',
                'match': {'type': 'IfExp', 'fields': {}},
                'nodes': [{'key': 'condition', 'at': [], 'parent': None, 'kind': 'SourceBranch'},
                          {'key': 'yes', 'at': ['body'], 'parent': 'condition', 'kind': 'SourceExpression'},
                          {'key': 'no', 'at': ['orelse'], 'parent': 'condition', 'kind': 'SourceExpression'}],
                'relations': [{'source': 'yes', 'target': 'no', 'proof': 'expression-input'}]}
        with self.assertRaisesRegex(AdapterError, 'immediate value operand'):
            compile_source('xs.sin() if other else xs.cos()', rule)
        rule['relations'][0]['target'] = 'condition'
        with self.assertRaisesRegex(AdapterError, 'immediate value operand'):
            compile_source('xs.sin() if other else xs.cos()', rule)

    def test_assignment_store_is_not_a_producer(self):
        rule = {'schema': 'archcanvas-source-rule/1', 'name': 'Assignment source read',
                'match': {'type': 'Assign', 'fields': {}},
                'nodes': [{'key': 'statement', 'at': [], 'parent': None, 'kind': 'SourceStatement'},
                          {'key': 'store', 'at': ['targets', 0], 'parent': 'statement', 'kind': 'SourceExpression'}],
                'relations': [{'source': 'store', 'target': 'statement', 'proof': 'expression-input'}]}
        with self.assertRaisesRegex(AdapterError, 'assignment stores'):
            compile_rule_adapter_files(FILES, 'unseen:Uncatalogued', rules=[rule])

    def test_guards_preserve_both_authored_paths_without_executing_them(self):
        files = {'model.py': '''from torch import nn
class A(nn.Module):
 def forward(self, xs, enabled):
  if enabled:
   return [x.sin() for x in xs if x]
  else:
   return [x.cos() for x in xs if x]
'''}
        result = compile_rule_adapter_files(files, 'model:A', rules=[comprehension_rule()])
        guards = [node['parameters']['guards'] for node in result['children'] if node['parentId'] is None]
        self.assertEqual(guards, [['if enabled', 'for x in xs', 'if x'], ['else of (enabled)', 'for x in xs', 'if x']])

    def test_selected_iterable_and_body_have_their_actual_guard_scopes(self):
        result = compile_rule_adapter_files(FILES, 'unseen:Uncatalogued', rules=[comprehension_rule()])
        self.assertEqual(result['children'][1]['parameters']['guards'], [])
        self.assertEqual(result['children'][2]['parameters']['guards'], ['for token in batch', 'if token is not None'])
        self.assertEqual(result['dependencies'][0]['guards'], result['children'][2]['parameters']['guards'])

    def test_match_container_does_not_merge_guards_from_different_branches(self):
        rule = {'schema': 'archcanvas-source-rule/1', 'name': 'Authored branches',
                'match': {'type': 'If', 'fields': {}},
                'nodes': [{'key': 'condition', 'at': [], 'parent': None, 'kind': 'SourceBranch'},
                          {'key': 'yes', 'at': ['body', 0, 'value'], 'parent': 'condition', 'kind': 'SourceExpression'},
                          {'key': 'no', 'at': ['orelse', 0, 'value'], 'parent': 'condition', 'kind': 'SourceExpression'}],
                'relations': []}
        files = {'model.py': '''from torch import nn
class A(nn.Module):
 def forward(self, xs, enabled):
  if enabled:
   return xs.sin()
  else:
   return xs.cos()
'''}
        result = compile_rule_adapter_files(files, 'model:A', rules=[rule])
        self.assertEqual([node['parameters']['guards'] for node in result['children']], [[], ['if enabled'], ['else of (enabled)']])

    def test_short_circuit_scope_only_applies_to_later_operands(self):
        rule = {'schema': 'archcanvas-source-rule/1', 'name': 'Short circuit syntax',
                'match': {'type': 'BoolOp', 'fields': {}},
                'nodes': [{'key': 'root', 'at': [], 'parent': None, 'kind': 'SourceExpression'},
                          {'key': 'first', 'at': ['values', 0], 'parent': 'root', 'kind': 'SourceExpression'},
                          {'key': 'second', 'at': ['values', 1], 'parent': 'root', 'kind': 'SourceExpression'}], 'relations': []}
        result = compile_source('xs and other', rule)
        self.assertEqual(result['children'][1]['parameters']['guards'], [])
        self.assertEqual(result['children'][2]['parameters']['guards'], ['short-circuit And: preceding operands (xs) truthy'])

    def test_identical_f_string_parts_with_shared_spans_have_unique_match_ids(self):
        rule = {'schema': 'archcanvas-source-rule/1', 'name': 'Formatted source parts',
                'match': {'type': 'FormattedValue', 'fields': {}},
                'nodes': [{'key': 'part', 'at': [], 'parent': None, 'kind': 'SourceExpression'}], 'relations': []}
        result = compile_source("f'{xs}{xs}'", rule)
        self.assertEqual(len(result['applications']), 2)
        self.assertEqual(len({node['id'] for node in result['children']}), 2)
        self.assertNotEqual(result['applications'][0]['matchKey'], result['applications'][1]['matchKey'])

    def test_invalid_field_types_report_adapter_error_not_unhashable_exception(self):
        for target, field in [('nodes', 'kind'), ('relations', 'source'), ('relations', 'target'), ('relations', 'proof')]:
            for invalid in ([], {}):
                rule = comprehension_rule()
                rule[target][0][field] = invalid
                with self.subTest(field=field, invalid=invalid), self.assertRaises(AdapterError):
                    validate_rule(rule)

    def test_parent_selector_must_actually_contain_its_child(self):
        rule = comprehension_rule()
        rule['nodes'][2]['parent'] = 'iterable'
        with self.assertRaisesRegex(AdapterError, 'contain its child'):
            validate_rule(rule)

    def test_root_keys_paths_and_relation_proofs_are_bounded(self):
        mutations = [
            lambda rule: rule['nodes'][0].update(parent='body'),
            lambda rule: rule['nodes'][1].update(key='comp'),
            lambda rule: rule['nodes'][1].update(at=[]),
            lambda rule: rule['relations'][0].update(proof='runtime-tensor'),
            lambda rule: rule['relations'][0].update(source='unknown'),
            lambda rule: rule['nodes'][1].update(at=['value'] * 17),
            lambda rule: rule.update(nodes=rule['nodes'] * 30),
            lambda rule: rule.update(relations=rule['relations'] * 129),
        ]
        for mutation in mutations:
            rule = comprehension_rule()
            mutation(rule)
            with self.subTest(mutation=mutation), self.assertRaises(AdapterError):
                validate_rule(rule)

    def test_source_evidence_rules_edges_and_authority_are_rebuilt_not_trusted(self):
        original = compile_rule_adapter_files(FILES, 'unseen:Uncatalogued', rules=[comprehension_rule()])
        mutations = [
            lambda result: result['children'][0]['source'].update(line=99),
            lambda result: result['applications'][0]['source'].update(expression='invented'),
            lambda result: result['dependencies'][0].update(sourceId=result['children'][0]['id']),
            lambda result: result['children'][1].update(ports=[{'id': 'tensor'}]),
            lambda result: result.update(generationContract={'execute': True}),
            lambda result: result.update(authority='tensor execution'),
            lambda result: result.update(pythonPlugin='foreign.py'),
        ]
        for mutation in mutations:
            forged = copy.deepcopy(original)
            mutation(forged)
            with self.subTest(mutation=mutation), self.assertRaises(AdapterError):
                validate_rule_adapter_files(forged, FILES)

    def test_stale_instance_rejected_but_template_recompiles(self):
        original = compile_rule_adapter_files(FILES, 'unseen:Uncatalogued', rules=[comprehension_rule()])
        changed = {'unseen.py': SOURCE.replace('token.sin()', 'token.cos()')}
        with self.assertRaisesRegex(AdapterError, 'stale'):
            validate_rule_adapter_files(original, changed)
        current = compile_rule_adapter_files(changed, 'unseen:Uncatalogued', rules=original['rules'])
        self.assertEqual(current['rules'], original['rules'])
        self.assertNotEqual(current['id'], original['id'])

    def test_only_presentation_can_change_without_recompiling(self):
        original = compile_rule_adapter_files(FILES, 'unseen:Uncatalogued', rules=[comprehension_rule()])
        original['presentation']['labels'][original['children'][0]['id']] = 'Reviewed list comprehension'
        original['presentation']['notes'] = ['The filter remains source syntax.']
        self.assertEqual(original, validate_rule_adapter_files(original, FILES))

    def test_compilation_output_budget_is_explicit(self):
        source = 'from torch import nn\nclass A(nn.Module):\n def forward(self, xs):\n' + ''.join(
            f'  a{index}=[x.sin() for x in xs]\n' for index in range(161)) + '  return xs\n'
        with self.assertRaisesRegex(AdapterError, '480-match/480-child'):
            compile_rule_adapter_files({'model.py': source}, 'model:A', rules=[comprehension_rule()])

    def test_machine_schemas_are_json_and_name_current_contracts(self):
        root = Path(__file__).resolve().parents[1]
        rule = json.loads((root / 'schemas/source-rule-v1.schema.json').read_text())
        adapter = json.loads((root / 'schemas/source-adapter-v2.schema.json').read_text())
        self.assertEqual(rule['properties']['schema']['const'], 'archcanvas-source-rule/1')
        self.assertEqual(adapter['properties']['schema']['const'], 'archcanvas-source-adapter/2')
        self.assertFalse(rule['additionalProperties'])
        self.assertFalse(adapter['additionalProperties'])


if __name__ == '__main__':
    unittest.main()
