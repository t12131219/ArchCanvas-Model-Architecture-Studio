"""Independently authored, executable PyTorch constructor and tensor contracts.

Public API inventory researched against the official documentation on 2026-10-07.
This module contains no code from DL-Playground or the failed prototype.
"""
from copy import deepcopy


def field(name, type, default, **constraints):
    return {'name': name, 'type': type, 'default': default, **constraints}


def module(kind, category, label, description, fields=(), inputs=('input',), outputs=('output',)):
    return {'kind': kind, 'category': category, 'label': kind, 'description': description,
            'defaults': {f['name']: deepcopy(f['default']) for f in fields}, 'parameters': list(fields),
            'ports': [{'id': p, 'name': p, 'direction': d, 'type': 'tensor'}
                      for d, ports in [('in', inputs), ('out', outputs)] for p in ports]}


POS = {'min': 1, 'max': 1000000}
AXIS = {'min': -8, 'max': 7}
SHAPE = {'min': 1, 'max': 1000000, 'minLength': 1, 'maxLength': 8}
EPS = field('eps', 'number', 1e-5, min=1e-12, max=1)
AFFINE = field('affine', 'boolean', True)
FLOAT_MODULES = {'Linear', 'Embedding', 'PReLU', 'LayerNorm', 'RMSNorm', 'GroupNorm',
                 'MultiheadAttention', 'RNN', 'GRU', 'LSTM'}
FUNCTIONAL = {'Add', 'Subtract', 'Multiply', 'Divide', 'Concat', 'MatMul', 'Reshape', 'Transpose',
              'Permute', 'Unsqueeze', 'Squeeze', 'Mean', 'Sum'}
CATALOG = [
    module('Input', 'io', '输入', 'Declare the input shape and dtype; declarations are not runtime observations.', [
        field('shape', 'integer-array', [1, 16], **SHAPE),
        field('dtype', 'choice', 'float32', options=['float32', 'float64', 'int64', 'bool'])], inputs=()),
    module('Output', 'io', '输出', 'Expose a tensor as a named model output.', outputs=()),
    module('Linear', 'dense', '全连接', 'Transform the last input dimension; requires float32.', [
        field('in_features', 'integer', 16, **POS), field('out_features', 'integer', 32, **POS), field('bias', 'boolean', True)]),
    module('Identity', 'operator', '恒等映射', 'Preserve the tensor shape and dtype.'),
    module('Flatten', 'reshape', '展平', 'Flatten dimensions from start_dim to end_dim; preserve the batch axis by default.', [
        field('start_dim', 'integer', 1, **AXIS), field('end_dim', 'integer', -1, **AXIS)]),
    module('Unflatten', 'reshape', '恢复多维', 'Expand one axis into the specified sizes; the element count must match.', [
        field('dim', 'integer', -1, **AXIS), field('unflattened_size', 'integer-array', [4, 4], **SHAPE)]),
    module('Reshape', 'reshape', '重塑形状', 'Specify the output shape; one -1 dimension may be inferred, with the element count unchanged.', [
        field('shape', 'integer-array', [1, -1], min=-1, max=1000000, minLength=1, maxLength=8)]),
    module('Transpose', 'reshape', '交换两轴', 'Swap two dimensions while preserving elements and dtype.', [
        field('dim0', 'integer', -2, **AXIS), field('dim1', 'integer', -1, **AXIS)]),
    module('Permute', 'reshape', '重排维度', 'Specify the full dimension order; each axis must occur exactly once.', [
        field('dims', 'integer-array', [0, 2, 1], min=0, max=7, minLength=1, maxLength=8)]),
    module('Unsqueeze', 'reshape', '新增单位轴', 'Insert an axis of size 1 at the specified position.', [field('dim', 'integer', 1, min=-9, max=8)]),
    module('Squeeze', 'reshape', '移除单位轴', 'Remove only the specified axis of size 1; preserve the batch dimension.', [field('dim', 'integer', 1, **AXIS)]),
]
for kind, label, fields in [
    ('ReLU', 'ReLU 激活', []), ('GELU', 'GELU 激活', [field('approximate', 'choice', 'none', options=['none', 'tanh'])]),
    ('SiLU', 'SiLU / Swish 激活', []), ('Sigmoid', 'Sigmoid 激活', []), ('Tanh', 'Tanh 激活', []),
    ('ReLU6', 'ReLU6 激活', []), ('LeakyReLU', 'Leaky ReLU 激活', [field('negative_slope', 'number', 0.01, min=0, max=100)]),
    ('ELU', 'ELU 激活', [field('alpha', 'number', 1., min=0, max=100)]), ('SELU', 'SELU 激活', []),
    ('Softplus', 'Softplus 激活', [field('beta', 'number', 1., min=1e-6, max=100), field('threshold', 'number', 20., min=1e-6, max=1000)]),
    ('Softsign', 'Softsign 激活', []), ('Hardsigmoid', 'Hard Sigmoid 激活', []), ('Hardswish', 'Hard Swish 激活', []),
    ('PReLU', '可学习 PReLU', [field('num_parameters', 'integer', 1, **POS), field('init', 'number', 0.25, min=-100, max=100)]),
    ('Softmax', 'Softmax 概率', [field('dim', 'integer', -1, **AXIS)]),
    ('LogSoftmax', 'Log Softmax', [field('dim', 'integer', -1, **AXIS)]),
]:
    CATALOG.append(module(kind, 'activation', label, 'Apply a floating-point activation and preserve shape; Softmax normalizes along the specified axis.', fields))
for kind in ['Dropout', 'Dropout1d', 'Dropout2d', 'Dropout3d', 'AlphaDropout', 'FeatureAlphaDropout']:
    CATALOG.append(module(kind, 'regularization', kind + ' 随机失活',
                          'Apply dropout without modifying the input in place; behavior differs between training and evaluation.', [field('p', 'number', 0.1, min=0, max=1)]))
for dim in [1, 2, 3]:
    spatial = {'min': 1, 'max': 10000, 'length': dim}
    zero = {'min': 0, 'max': 10000, 'length': dim}
    for transpose in [False, True]:
        kind = f'Conv{"Transpose" if transpose else ""}{dim}d'
        fields = [field('in_channels', 'integer', 3, **POS), field('out_channels', 'integer', 16, **POS),
                  field('kernel_size', 'integer-array', [3] * dim, **spatial),
                  field('stride', 'integer-array', [1] * dim, **spatial),
                  field('padding', 'integer-array', [0] * dim, **zero)]
        if transpose: fields.append(field('output_padding', 'integer-array', [0] * dim, **zero))
        fields += [field('dilation', 'integer-array', [1] * dim, **spatial), field('groups', 'integer', 1, **POS), field('bias', 'boolean', True)]
        CATALOG.append(module(kind, 'convolution', f'{dim}维' + ('转置卷积' if transpose else '卷积'),
                              'Convolve float32 tensors in channels-first format, batched or unbatched; groups must divide both channel counts.', fields))
        FLOAT_MODULES.add(kind)
    for operation in ['Max', 'Avg']:
        fields = [field('kernel_size', 'integer-array', [2] * dim, **spatial),
                  field('stride', 'integer-array', [2] * dim, **spatial),
                  field('padding', 'integer-array', [0] * dim, **zero)]
        if operation == 'Max': fields.append(field('dilation', 'integer-array', [1] * dim, **spatial))
        fields.append(field('ceil_mode', 'boolean', False))
        if operation == 'Avg': fields.append(field('count_include_pad', 'boolean', True))
        CATALOG.append(module(f'{operation}Pool{dim}d', 'pooling', f'{dim}维' + ('最大池化' if operation == 'Max' else '平均池化'),
                              f'{operation} pooling on floating-point channels-first tensors with explicit kernel and stride; return only the output tensor.', fields))
        CATALOG.append(module(f'Adaptive{operation}Pool{dim}d', 'pooling', f'{dim}维自适应' + ('最大池化' if operation == 'Max' else '平均池化'),
                              f'Adaptive {operation} pooling to a fixed spatial output size; return only the output tensor.', [field('output_size', 'integer-array', [1] * dim, **spatial)]))
    for norm in ['Batch', 'Instance']:
        kind = f'{norm}Norm{dim}d'
        fields = [field('num_features', 'integer', 16, **POS), deepcopy(EPS),
                  field('momentum', 'number', 0.1, min=0, max=1), field('affine', 'boolean', norm == 'Batch'),
                  field('track_running_stats', 'boolean', norm == 'Batch')]
        CATALOG.append(module(kind, 'normalization', f'{dim}维' + ('批归一化' if norm == 'Batch' else '实例归一化'),
                              'Normalize float32 channels; static training checks require enough samples per channel.', fields))
        FLOAT_MODULES.add(kind)
CATALOG += [
    module('LayerNorm', 'normalization', '层归一化', 'Normalize the matching trailing dimensions.', [
        field('normalized_shape', 'integer-array', [16], **SHAPE), deepcopy(EPS), field('elementwise_affine', 'boolean', True)]),
    module('RMSNorm', 'normalization', 'RMS 归一化', 'Normalize trailing dimensions by their root mean square; requires a PyTorch version with RMSNorm.', [
        field('normalized_shape', 'integer-array', [16], **SHAPE), deepcopy(EPS), field('elementwise_affine', 'boolean', True)]),
    module('GroupNorm', 'normalization', '分组归一化', 'Normalize groups in N,C,... format; the group count must divide the channel count.', [
        field('num_groups', 'integer', 4, **POS), field('num_channels', 'integer', 16, **POS), deepcopy(EPS), deepcopy(AFFINE)]),
    module('Embedding', 'embedding', '词嵌入', 'Map int64 indices to float32 vectors; actual index ranges require data validation.', [
        field('num_embeddings', 'integer', 1000, **POS), field('embedding_dim', 'integer', 16, **POS)]),
    module('MultiheadAttention', 'attention', '多头注意力', 'Use float32 query, key and value tensors; return attention output and averaged weights, without masks or caching.', [
        field('embed_dim', 'integer', 16, **POS), field('num_heads', 'integer', 4, **POS),
        field('dropout', 'number', 0.1, min=0, max=1), field('bias', 'boolean', True), field('batch_first', 'boolean', True)],
        inputs=('query', 'key', 'value'), outputs=('output', 'weights')),
]
for kind in ['RNN', 'GRU', 'LSTM']:
    fields = [field('input_size', 'integer', 16, **POS), field('hidden_size', 'integer', 32, **POS),
              field('num_layers', 'integer', 1, min=1, max=128), field('bias', 'boolean', True),
              field('batch_first', 'boolean', True), field('dropout', 'number', 0., min=0, max=1),
              field('bidirectional', 'boolean', False)]
    if kind == 'RNN': fields.append(field('nonlinearity', 'choice', 'tanh', options=['tanh', 'relu']))
    CATALOG.append(module(kind, 'recurrent', kind + ' 循环层',
                          'Process batched 3D sequences from a zero initial state; return sequence and final states, without PackedSequence or LSTM projections.', fields,
                          outputs=('output', 'h_n', 'c_n') if kind == 'LSTM' else ('output', 'h_n')))
for kind, label in [('Add', '张量相加'), ('Subtract', '张量相减'), ('Multiply', '张量相乘'), ('Divide', '张量相除')]:
    CATALOG.append(module(kind, 'merge', label, 'Both inputs must have identical shapes and dtypes; no implicit broadcasting or numerical domain validation.', inputs=('left', 'right')))
CATALOG += [
    module('Concat', 'merge', '张量拼接', 'Concatenate two tensors of the same dtype along one axis; all other dimensions must match.', [field('dim', 'integer', 1, **AXIS)], inputs=('a', 'b')),
    module('MatMul', 'operator', '矩阵乘法', 'Multiply 2D or batched matrices of the same dtype; batch dimensions must match without implicit broadcasting.', inputs=('left', 'right')),
    module('Mean', 'operator', '按轴平均', 'Compute the floating-point mean along the specified axis.', [field('dim', 'integer', 1, **AXIS), field('keepdim', 'boolean', True)]),
    module('Sum', 'operator', '按轴求和', 'Sum along the specified axis while preserving the declared dtype.', [field('dim', 'integer', 1, **AXIS), field('keepdim', 'boolean', True)]),
    module('Upsample', 'reshape', '固定尺寸上采样', 'Resize to an explicit spatial size using nearest-neighbor interpolation; supports 1D, 2D and 3D spatial tensors.', [
        field('size', 'integer-array', [64, 64], min=1, max=10000, minLength=1, maxLength=3),
        field('mode', 'choice', 'nearest', options=['nearest', 'nearest-exact'])]),
]
BY_KIND = {m['kind']: m for m in CATALOG}
IR_CATEGORIES = {m['kind']: {'io': 'input' if m['kind'] == 'Input' else 'output', 'dense': 'linear',
    'normalization': 'norm', 'reshape': 'operator', 'merge': 'operator'}.get(m['category'], m['category']) for m in CATALOG}


def module_catalog():
    return deepcopy({'schemaVersion': 1, 'mode': 'authored-draft', 'modules': CATALOG,
        'unsupported': ['PackedSequence', 'AttentionMask', 'DynamicControlFlow', 'LossAndOptimizer', 'CustomPythonExecution'],
        'limits': {'nodes': 128, 'edges': 384},
        'verification': 'static-declared-tensors; no model import or execution'})
