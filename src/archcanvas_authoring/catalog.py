"""Independently authored, executable PyTorch constructor and tensor contracts.

Public API inventory researched against the official documentation on 2026-10-07.
This module contains no code from DL-Playground or the failed prototype.
"""
from copy import deepcopy


def field(name, type, default, **constraints):
    return {'name': name, 'type': type, 'default': default, **constraints}


def module(kind, category, label, description, fields=(), inputs=('input',), outputs=('output',)):
    return {'kind': kind, 'category': category, 'label': label, 'description': description,
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
    module('Input', 'io', '输入', '声明输入形状与类型；声明不是实测数据。', [
        field('shape', 'integer-array', [1, 16], **SHAPE),
        field('dtype', 'choice', 'float32', options=['float32', 'float64', 'int64'])], inputs=()),
    module('Output', 'io', '输出', '将一条张量连接为命名输出。', outputs=()),
    module('Linear', 'dense', '全连接', '变换输入的最后一维，需要 float32。', [
        field('in_features', 'integer', 16, **POS), field('out_features', 'integer', 32, **POS), field('bias', 'boolean', True)]),
    module('Identity', 'operator', '恒等映射', '保留张量形状与类型。'),
    module('Flatten', 'reshape', '展平', '将起止维度之间的轴合并，默认保留批次轴。', [
        field('start_dim', 'integer', 1, **AXIS), field('end_dim', 'integer', -1, **AXIS)]),
    module('Unflatten', 'reshape', '恢复多维', '把一个轴恢复为指定的多个尺寸，元素总数必须一致。', [
        field('dim', 'integer', -1, **AXIS), field('unflattened_size', 'integer-array', [4, 4], **SHAPE)]),
    module('Reshape', 'reshape', '重塑形状', '显式声明整个输出形状；允许一个 -1 推导轴，元素总数不变。', [
        field('shape', 'integer-array', [1, -1], min=-1, max=1000000, minLength=1, maxLength=8)]),
    module('Transpose', 'reshape', '交换两轴', '交换两个指定维度，保留元素与类型。', [
        field('dim0', 'integer', -2, **AXIS), field('dim1', 'integer', -1, **AXIS)]),
    module('Permute', 'reshape', '重排维度', '完整列出维度顺序，每个轴必须恰好出现一次。', [
        field('dims', 'integer-array', [0, 2, 1], min=0, max=7, minLength=1, maxLength=8)]),
    module('Unsqueeze', 'reshape', '新增单位轴', '在指定位置插入大小为 1 的轴。', [field('dim', 'integer', 1, min=-9, max=8)]),
    module('Squeeze', 'reshape', '移除单位轴', '仅移除指定大小为 1 的轴，避免隐式丢失批次。', [field('dim', 'integer', 1, **AXIS)]),
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
    CATALOG.append(module(kind, 'activation', label, '逐元素浮点激活，保留形状；Softmax 按指定轴归一化。', fields))
for kind in ['Dropout', 'Dropout1d', 'Dropout2d', 'Dropout3d', 'AlphaDropout', 'FeatureAlphaDropout']:
    CATALOG.append(module(kind, 'regularization', kind + ' 随机失活',
                          '非原地随机失活；训练与评估行为不同，不证明数值效果。', [field('p', 'number', 0.1, min=0, max=1)]))
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
                              'float32 通道优先张量，支持批次或无批次；分组须整除输入输出通道。', fields))
        FLOAT_MODULES.add(kind)
    for operation in ['Max', 'Avg']:
        fields = [field('kernel_size', 'integer-array', [2] * dim, **spatial),
                  field('stride', 'integer-array', [2] * dim, **spatial),
                  field('padding', 'integer-array', [0] * dim, **zero)]
        if operation == 'Max': fields.append(field('dilation', 'integer-array', [1] * dim, **spatial))
        fields.append(field('ceil_mode', 'boolean', False))
        if operation == 'Avg': fields.append(field('count_include_pad', 'boolean', True))
        CATALOG.append(module(f'{operation}Pool{dim}d', 'pooling', f'{dim}维' + ('最大池化' if operation == 'Max' else '平均池化'),
                              '浮点通道优先张量，显式窗口与步长；最大池化仅返回结果张量。', fields))
        CATALOG.append(module(f'Adaptive{operation}Pool{dim}d', 'pooling', f'{dim}维自适应' + ('最大池化' if operation == 'Max' else '平均池化'),
                              '固定输出空间尺寸；仅返回结果张量，不返回最大值索引。', [field('output_size', 'integer-array', [1] * dim, **spatial)]))
    for norm in ['Batch', 'Instance']:
        kind = f'{norm}Norm{dim}d'
        fields = [field('num_features', 'integer', 16, **POS), deepcopy(EPS),
                  field('momentum', 'number', 0.1, min=0, max=1), field('affine', 'boolean', norm == 'Batch'),
                  field('track_running_stats', 'boolean', norm == 'Batch')]
        CATALOG.append(module(kind, 'normalization', f'{dim}维' + ('批归一化' if norm == 'Batch' else '实例归一化'),
                              'float32 通道归一化；训练兼容静态检查要求足够的通道采样。', fields))
        FLOAT_MODULES.add(kind)
CATALOG += [
    module('LayerNorm', 'normalization', '层归一化', '归一化匹配的末尾维度。', [
        field('normalized_shape', 'integer-array', [16], **SHAPE), deepcopy(EPS), field('elementwise_affine', 'boolean', True)]),
    module('RMSNorm', 'normalization', 'RMS 归一化', '按末尾维度均方根归一化；需要支持 RMSNorm 的 PyTorch 版本。', [
        field('normalized_shape', 'integer-array', [16], **SHAPE), deepcopy(EPS), field('elementwise_affine', 'boolean', True)]),
    module('GroupNorm', 'normalization', '分组归一化', 'N,C,... 布局，分组必须整除通道数。', [
        field('num_groups', 'integer', 4, **POS), field('num_channels', 'integer', 16, **POS), deepcopy(EPS), deepcopy(AFFINE)]),
    module('Embedding', 'embedding', '词嵌入', 'int64 索引转 float32 向量；实际索引范围需要数据验证。', [
        field('num_embeddings', 'integer', 1000, **POS), field('embedding_dim', 'integer', 16, **POS)]),
    module('MultiheadAttention', 'attention', '多头注意力', '三路 float32 Q/K/V；固定返回注意力结果与平均权重，无掩码，无缓存。', [
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
                          '批次三维序列，默认零初态；返回序列与末态，不支持 PackedSequence 或 LSTM 投影。', fields,
                          outputs=('output', 'h_n', 'c_n') if kind == 'LSTM' else ('output', 'h_n')))
for kind, label in [('Add', '张量相加'), ('Subtract', '张量相减'), ('Multiply', '张量相乘'), ('Divide', '张量相除')]:
    CATALOG.append(module(kind, 'merge', label, '两路形状与类型必须完全相同；不隐式广播，数值域未验证。', inputs=('left', 'right')))
CATALOG += [
    module('Concat', 'merge', '张量拼接', '沿一个轴拼接两路相同类型张量，其他轴相同。', [field('dim', 'integer', 1, **AXIS)], inputs=('a', 'b')),
    module('MatMul', 'operator', '矩阵乘法', '相同类型的二维或批次矩阵；批次轴严格相同，不隐式广播。', inputs=('left', 'right')),
    module('Mean', 'operator', '按轴平均', '沿一个指定轴求浮点均值。', [field('dim', 'integer', 1, **AXIS), field('keepdim', 'boolean', True)]),
    module('Sum', 'operator', '按轴求和', '沿一个指定轴求和，保留声明类型。', [field('dim', 'integer', 1, **AXIS), field('keepdim', 'boolean', True)]),
    module('Upsample', 'reshape', '固定尺寸上采样', '按显式目标空间尺寸最近邻插值；支持 1–3 维空间。', [
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
