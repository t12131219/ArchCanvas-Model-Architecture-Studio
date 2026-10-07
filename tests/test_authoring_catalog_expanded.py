"""Official tensor contracts, hand-derived shapes, exact output identities.

Generated model source is data; these tests never execute a user model or import
PyTorch. Expected dimensions are independent numeric examples rather than the
implementation's formulas.
"""
from copy import deepcopy
import unittest
from archcanvas_authoring import module_catalog, generate_model, validate_draft, verify_generated, DraftError
from archcanvas_python import analyze_source
from tests.test_authoring import node, edge, graph


def unary(kind, shape=(2, 16), params=None, dtype='float32'):
    return graph([node('x', 'Input', {'shape': list(shape), 'dtype': dtype}), node('op', kind, params), node('out', 'Output')],
                 [edge('x-op', 'x', 'op'), edge('op-out', 'op', 'out')])


def case_for(kind):
    if kind in ('Input', 'Output'):
        return graph([node('x', 'Input'), node('out', 'Output')], [edge('x-out', 'x', 'out')])
    if kind in ('Add', 'Subtract', 'Multiply', 'Divide', 'MatMul', 'Concat'):
        shape = [2, 16] if kind != 'MatMul' else [2, 2]
        ports = ['a', 'b'] if kind == 'Concat' else ['left', 'right']
        return graph([node('x', 'Input', {'shape': shape}), node('op', kind), node('out', 'Output')],
            [edge('a', 'x', 'op', ports[0]), edge('b', 'x', 'op', ports[1]), edge('c', 'op', 'out')])
    if kind.startswith('Conv'): return unary(kind, [2, 3] + [8] * int(kind[-2]))
    if 'Pool' in kind: return unary(kind, [2, 3] + [8] * int(kind[-2]))
    if kind.startswith(('BatchNorm', 'InstanceNorm')): return unary(kind, [2, 16] + [8] * int(kind[-2]))
    if kind in ('Dropout1d', 'Dropout2d', 'Dropout3d'): return unary(kind, [2, 16] + [8] * int(kind[-2]))
    if kind == 'Embedding': return unary(kind, [2, 5], dtype='int64')
    if kind in ('GRU', 'LSTM', 'RNN'): return unary(kind, [2, 5, 16])
    if kind == 'MultiheadAttention':
        return graph([node('x', 'Input', {'shape': [2, 5, 16]}), node('op', kind), node('out', 'Output')],
            [edge(p, 'x', 'op', p) for p in ('query', 'key', 'value')] + [edge('out', 'op', 'out')])
    if kind == 'Permute': return unary(kind, [2, 5, 16])
    if kind == 'Squeeze': return unary(kind, [2, 1, 16])
    if kind == 'Upsample': return unary(kind, [2, 3, 8, 8])
    return unary(kind)


class ExpandedCatalogTests(unittest.TestCase):
    def test_every_advertised_atom_generates_reanalyzes_without_opaque_node(self):
        kinds = {m['kind'] for m in module_catalog()['modules']}
        self.assertEqual(len(kinds), 74)
        for kind in sorted(kinds):
            with self.subTest(kind=kind):
                result = generate_model(case_for(kind))
                self.assertEqual(result['verification']['status'], 'passed')
                self.assertEqual(result['verification']['modelExecution'], 'not_run')
                self.assertFalse(any(n['evidence'] == 'opaque' for n in result['architecture']['nodes']))

    def test_reshape_transpose_reductions_have_independent_exact_shapes(self):
        cases = [('Reshape', [2, 3, 4], {'shape': [3, -1]}, [3, 8]),
                 ('Transpose', [2, 3, 4], {'dim0': 0, 'dim1': -1}, [4, 3, 2]),
                 ('Permute', [2, 3, 4], {'dims': [2, 0, 1]}, [4, 2, 3]),
                 ('Unsqueeze', [2, 3], {'dim': -1}, [2, 3, 1]),
                 ('Squeeze', [2, 1, 3], {'dim': 1}, [2, 3]),
                 ('Unflatten', [2, 12], {'dim': 1, 'unflattened_size': [3, 4]}, [2, 3, 4]),
                 ('Mean', [2, 3, 4], {'dim': 1, 'keepdim': False}, [2, 4]),
                 ('Sum', [2, 3, 4], {'dim': -1, 'keepdim': True}, [2, 3, 1])]
        for kind, shape, params, expected in cases:
            with self.subTest(kind=kind):
                self.assertEqual(generate_model(unary(kind, shape, params))['tensors']['out']['shape'], expected)

    def test_conv_transpose_and_pool_dimensional_contracts(self):
        cases = [('Conv1d', [2, 3, 11], {'out_channels': 7, 'kernel_size': [3], 'stride': [2], 'padding': [1]}, [2, 7, 6]),
                 ('Conv3d', [2, 3, 7, 9, 11], {'out_channels': 4, 'kernel_size': [3, 3, 3], 'stride': [2, 2, 2], 'padding': [1, 1, 1]}, [2, 4, 4, 5, 6]),
                 ('ConvTranspose2d', [2, 3, 4, 5], {'out_channels': 8, 'kernel_size': [3, 3], 'stride': [2, 2], 'padding': [1, 1], 'output_padding': [1, 0]}, [2, 8, 8, 9]),
                 ('AvgPool1d', [2, 3, 9], {'kernel_size': [3], 'stride': [2], 'padding': [1]}, [2, 3, 5]),
                 ('AdaptiveMaxPool3d', [2, 3, 5, 7, 9], {'output_size': [2, 3, 4]}, [2, 3, 2, 3, 4])]
        for kind, shape, params, expected in cases:
            with self.subTest(kind=kind): self.assertEqual(generate_model(unary(kind, shape, params))['tensors']['out']['shape'], expected)

    def test_recurrent_all_outputs_are_real_tensor_slots_and_can_feed_downstream(self):
        for kind in ('RNN', 'GRU', 'LSTM'):
            with self.subTest(kind=kind):
                draft = unary(kind, [3, 5, 16], {'hidden_size': 7, 'num_layers': 2, 'bidirectional': True})
                draft['nodes'].append(node('hidden', 'Output'))
                draft['edges'].append({'id': 'h', 'source': {'nodeId': 'op', 'portId': 'h_n'}, 'target': {'nodeId': 'hidden', 'portId': 'input'}})
                if kind == 'LSTM':
                    draft['nodes'].append(node('cell', 'Output'))
                    draft['edges'].append({'id': 'c', 'source': {'nodeId': 'op', 'portId': 'c_n'}, 'target': {'nodeId': 'cell', 'portId': 'input'}})
                result = generate_model(draft)
                self.assertEqual(result['tensors']['out']['shape'], [3, 5, 14])
                self.assertEqual(result['tensors']['hidden']['shape'], [4, 3, 7])
                tensor_ids = {e['tensorId'] for e in result['architecture']['edges'] if e['source']['nodeId'] == result['nodeBindings']['op']}
                self.assertEqual(len(tensor_ids), 3 if kind == 'LSTM' else 2)

    def test_cross_attention_weights_memory_roles_and_seq_axes(self):
        draft = graph([node('q', 'Input', {'shape': [3, 2, 16]}), node('kv', 'Input', {'shape': [7, 2, 16]}),
                       node('mha', 'MultiheadAttention', {'batch_first': False}), node('out', 'Output'), node('weights', 'Output')],
                      [edge('q', 'q', 'mha', 'query'), edge('k', 'kv', 'mha', 'key'), edge('v', 'kv', 'mha', 'value'), edge('o', 'mha', 'out'),
                       {'id': 'w', 'source': {'nodeId': 'mha', 'portId': 'weights'}, 'target': {'nodeId': 'weights', 'portId': 'input'}}])
        result = generate_model(draft)
        self.assertEqual(result['tensors']['out']['shape'], [3, 2, 16])
        self.assertEqual(result['tensors']['weights']['shape'], [2, 3, 7])
        self.assertEqual([p['role'] for p in next(n for n in result['architecture']['nodes'] if n['kind'] == 'MultiheadAttention')['ports'][:3]], ['data', 'memory', 'memory'])

    def test_rejects_false_static_claims(self):
        cases = [('Reshape', [2, 3], {'shape': [4, -1]}), ('Permute', [2, 3], {'dims': [0, 0]}),
                 ('Squeeze', [2, 3], {'dim': 1}), ('Unflatten', [2, 16], {'unflattened_size': [3, 3]}),
                 ('GroupNorm', [2, 16], {'num_groups': 3}), ('MultiheadAttention', [2, 5, 16], {'num_heads': 3}),
                 ('ConvTranspose1d', [2, 3, 5], {'output_padding': [1]}), ('GRU', [2, 5, 16], {'dropout': 0.1})]
        for kind, shape, params in cases:
            with self.subTest(kind=kind), self.assertRaises(DraftError):
                draft = unary(kind, shape, params)
                if kind == 'MultiheadAttention':
                    draft = case_for(kind); draft['nodes'][1]['parameters'] = params
                generate_model(draft)

    def test_secondary_output_shape_is_used_by_reshape_and_source_normalization(self):
        draft = unary('LSTM', [2, 7, 16], {'hidden_size': 4, 'num_layers': 3})
        draft['nodes'] += [node('flat', 'Reshape', {'shape': [2, -1]}), node('hout', 'Output')]
        draft['edges'] += [{'id': 'hf', 'source': {'nodeId': 'op', 'portId': 'h_n'}, 'target': {'nodeId': 'flat', 'portId': 'input'}}, edge('fo', 'flat', 'hout')]
        result = generate_model(draft)
        self.assertEqual(result['tensors']['hout']['shape'], [2, 12])
        self.assertIn('.reshape((2, 12))', result['source'])

    def test_hand_calculated_batched_matmul_and_multiply(self):
        draft = graph([node('a', 'Input', {'shape': [2, 3, 4]}), node('b', 'Input', {'shape': [2, 4, 5]}), node('mm', 'MatMul'), node('out', 'Output')],
            [edge('a', 'a', 'mm', 'left'), edge('b', 'b', 'mm', 'right'), edge('o', 'mm', 'out')])
        self.assertEqual(generate_model(draft)['tensors']['out']['shape'], [2, 3, 5])
        draft['nodes'][1]['parameters']['shape'] = [1, 4, 5]
        with self.assertRaises(DraftError): generate_model(draft)

    def test_tampered_source_and_output_slot_swaps_are_rejected(self):
        result = generate_model(case_for('LSTM'))
        damaged = deepcopy(result['architecture'])
        call = next(n for n in damaged['nodes'] if n['kind'] == 'LSTM')
        call['ports'][1]['name'] = 'c_n'
        with self.assertRaises(DraftError): verify_generated(case_for('LSTM'), damaged)
        source = result['source'].replace('hidden_size=32', 'hidden_size=31')
        with self.assertRaises(DraftError): verify_generated(case_for('LSTM'), analyze_source(source, result['entry']))
