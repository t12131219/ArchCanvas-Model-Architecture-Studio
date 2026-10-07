"""Static deductions from declared tensors; never imports torch or executes a model."""
import math
from .catalog import FLOAT_MODULES


def validate_parameters(node, fail):
    p, kind, identity = node['parameters'], node['kind'], node['id']
    def error(code, message, parameter):
        fail(message, code, message, nodeId=identity, parameter=parameter)
    if kind.startswith('Conv') and (p['in_channels'] % p['groups'] or p['out_channels'] % p['groups']):
        error('conv_groups_mismatch', f'{kind} 的 groups 必须整除输入和输出通道。', 'groups')
    if kind.startswith('ConvTranspose') and any(o >= s and o >= d for o, s, d in zip(p['output_padding'], p['stride'], p['dilation'])):
        error('conv_output_padding_out_of_range', 'output_padding 必须小于对应 stride 或 dilation。', 'output_padding')
    if kind.startswith(('MaxPool', 'AvgPool')) and any(pad > k // 2 for pad, k in zip(p['padding'], p['kernel_size'])):
        error('pool_padding_out_of_range', f'{kind} 的填充不能超过池化核的一半。', 'padding')
    if kind == 'GroupNorm' and p['num_channels'] % p['num_groups']:
        error('group_norm_groups_mismatch', 'num_groups 必须整除 num_channels。', 'num_groups')
    if kind == 'MultiheadAttention' and p['embed_dim'] % p['num_heads']:
        error('attention_heads_mismatch', 'num_heads 必须整除 embed_dim。', 'num_heads')
    if kind in ('RNN', 'GRU', 'LSTM') and p['num_layers'] == 1 and p['dropout'] != 0:
        error('recurrent_dropout_layers', '单层循环模块没有层间 dropout；请设为 0 或增加 num_layers。', 'dropout')
    if kind == 'Reshape' and (p['shape'].count(-1) > 1 or 0 in p['shape']):
        error('reshape_shape_invalid', '形状必须为正整数，最多可含一个 -1 推导维度。', 'shape')


def infer_outputs(node, inputs, fail, axis):
    kind, p, name = node['kind'], node['parameters'], node['label']
    def error(code, message, *, parameter=None, port='input', expected=None, actual=None):
        fail(f'{name}: {message}', code, message, nodeId=node['id'], parameter=parameter,
             portId=port, expected=expected, actual=actual)
    def rank(expected):
        if len(shape) not in expected:
            error('input_rank_mismatch', f'{kind} 需要 {expected} 维输入，当前为 {len(shape)} 维。', expected=expected[0] if len(expected) == 1 else expected, actual=len(shape))
    def channel(expected, actual, code='conv_input_channels_mismatch', parameter='in_channels'):
        if expected != actual:
            error(code, f'{kind} 的声明通道 {expected} 与输入通道 {actual} 不一致。', parameter=parameter, expected=expected, actual=actual)
    def floating(port='input', tensor=None):
        value = tensor or {'dtype': dtype}
        if value['dtype'] not in ('float32', 'float64'):
            error('input_dtype_mismatch', f'{kind} 需要浮点输入。', port=port, expected=['float32', 'float64'], actual=value['dtype'])
    if kind == 'Input':
        return check_budget({'output': {'shape': p['shape'][:], 'dtype': p['dtype']}}, name, fail)
    shape, dtype = inputs[0]['shape'][:], inputs[0]['dtype']
    if kind in FLOAT_MODULES - {'Embedding'} and dtype != 'float32':
        error('input_dtype_mismatch', f'{kind} 参数明确使用 float32，需要 float32 输入。', expected='float32', actual=dtype)
    if kind in ('Linear',):
        if not shape: rank([1, 2, 3, 4, 5, 6, 7, 8])
        if p['in_features'] != shape[-1]:
            fail(f"{name}: final input dimension {shape[-1]} does not equal in_features {p['in_features']}.",
                 'linear_input_features_mismatch', f"Linear 的输入末维为 {shape[-1]}，但 in_features 为 {p['in_features']}。请让 in_features 与上游末维一致。", nodeId=node['id'],
                 parameter='in_features', portId='input', expected=p['in_features'], actual=shape[-1])
        shape[-1] = p['out_features']
    elif kind == 'Embedding':
        if dtype != 'int64': error('input_dtype_mismatch', 'Embedding 需要 int64 索引。', expected='int64', actual=dtype)
        shape.append(p['embedding_dim']); dtype = 'float32'
    elif kind in ('LayerNorm', 'RMSNorm'):
        n = p['normalized_shape']
        if shape[-len(n):] != n: error('layer_norm_shape_mismatch', '归一化末尾形状不匹配。', parameter='normalized_shape', expected=n, actual=shape[-len(n):])
    elif kind.startswith(('BatchNorm', 'InstanceNorm')):
        dim = int(kind[-2]); batch = kind.startswith('Batch')
        rank([2, 3] if batch and dim == 1 else [dim + 2] if batch else [dim + 1, dim + 2])
        ci = 1 if batch or len(shape) == dim + 2 else 0
        channel(p['num_features'], shape[ci], 'batch_norm_channels_mismatch' if batch else 'instance_norm_channels_mismatch', 'num_features')
        samples = math.prod(shape) // shape[ci] if batch else math.prod(shape[-dim:])
        if samples <= 1:
            error('batch_norm_channel_samples' if batch else 'instance_norm_spatial_samples', '训练兼容归一化需要每个通道至少两个采样值。', expected={'min': 2}, actual=samples)
    elif kind == 'GroupNorm':
        if len(shape) < 2: rank([2, 3, 4, 5, 6, 7, 8])
        channel(p['num_channels'], shape[1], 'group_norm_channels_mismatch', 'num_channels')
        if math.prod(shape) // p['num_groups'] <= 1: error('group_norm_group_samples', '每组需要至少两个采样值。')
    elif kind.startswith('Conv') or kind.startswith(('MaxPool', 'AvgPool', 'AdaptiveMaxPool', 'AdaptiveAvgPool')):
        dim = int(kind[-2])
        if not kind.startswith('Conv'): floating()
        rank([dim + 1, dim + 2])
        if kind.startswith('Conv'):
            channel(p['in_channels'], shape[-dim - 1]); shape[-dim - 1] = p['out_channels']
        else: floating()
        if kind.startswith('Adaptive'):
            shape[-dim:] = p['output_size'][:]
        else:
            spatial = []
            for size, k, s, pad, d, extra in zip(shape[-dim:], p['kernel_size'], p['stride'], p['padding'], p.get('dilation', [1] * dim), p.get('output_padding', [0] * dim)):
                if kind.startswith('ConvTranspose'):
                    out = (size - 1) * s - 2 * pad + d * (k - 1) + extra + 1
                else:
                    numerator = size + 2 * pad - d * (k - 1) - 1
                    out = (numerator + (s - 1 if p.get('ceil_mode') else 0)) // s + 1
                    if p.get('ceil_mode') and (out - 1) * s >= size + pad: out -= 1
                if out <= 0: error('nonpositive_spatial_output', '参数产生非正空间尺寸，请调整核、步长、填充或输入。', expected={'min': 1}, actual=out)
                spatial.append(out)
            shape[-dim:] = spatial
    elif kind == 'Upsample':
        floating(); dim = len(p['size']); rank([dim + 2]); shape[-dim:] = p['size'][:]
    elif kind in ('Flatten', 'Unflatten', 'Reshape', 'Transpose', 'Permute', 'Unsqueeze', 'Squeeze'):
        if kind == 'Flatten':
            start, end = axis(p['start_dim'], len(shape), node, 'start_dim'), axis(p['end_dim'], len(shape), node, 'end_dim')
            if start > end: error('flatten_dimension_order', 'start_dim 必须不晚于 end_dim。', parameter='start_dim', expected={'max': end}, actual=start)
            shape = shape[:start] + [math.prod(shape[start:end + 1])] + shape[end + 1:]
        elif kind == 'Unflatten':
            d = axis(p['dim'], len(shape), node, 'dim'); sizes = p['unflattened_size']
            if math.prod(sizes) != shape[d]: error('unflatten_element_count', '恢复的尺寸乘积必须等于输入轴。', parameter='unflattened_size', expected=shape[d], actual=math.prod(sizes))
            shape = shape[:d] + sizes + shape[d + 1:]
        elif kind == 'Reshape':
            sizes = p['shape'][:]; total = math.prod(shape); known = math.prod(s for s in sizes if s != -1)
            if -1 in sizes:
                if total % known: error('reshape_element_count', '无法整除推导的形状尺寸。', parameter='shape', expected=total, actual=known)
                sizes[sizes.index(-1)] = total // known
            elif total != known: error('reshape_element_count', '重塑前后元素数必须一致。', parameter='shape', expected=total, actual=known)
            shape = sizes
        elif kind == 'Transpose':
            a, b = axis(p['dim0'], len(shape), node, 'dim0'), axis(p['dim1'], len(shape), node, 'dim1'); shape[a], shape[b] = shape[b], shape[a]
        elif kind == 'Permute':
            if sorted(p['dims']) != list(range(len(shape))): error('permute_dimension_inventory', 'dims 必须恰好列出输入的所有轴一次。', parameter='dims', expected=list(range(len(shape))), actual=p['dims'])
            shape = [shape[d] for d in p['dims']]
        elif kind == 'Unsqueeze':
            d = axis(p['dim'], len(shape) + 1, node, 'dim'); shape.insert(d, 1)
        else:
            d = axis(p['dim'], len(shape), node, 'dim')
            if shape[d] != 1: error('squeeze_nonunit_axis', '指定移除的轴必须大小为 1。', parameter='dim', expected=1, actual=shape[d])
            shape.pop(d)
    elif kind in ('RNN', 'GRU', 'LSTM'):
        rank([3]); channel(p['input_size'], shape[-1], 'recurrent_input_size_mismatch', 'input_size')
        directions = 2 if p['bidirectional'] else 1
        batch = shape[0 if p['batch_first'] else 1]; shape[-1] = directions * p['hidden_size']
        hidden = {'shape': [directions * p['num_layers'], batch, p['hidden_size']], 'dtype': dtype}
        result = {'output': {'shape': shape, 'dtype': dtype}, 'h_n': hidden}
        if kind == 'LSTM': result['c_n'] = {'shape': hidden['shape'][:], 'dtype': dtype}
        return check_budget(result, name, fail)
    elif kind == 'MultiheadAttention':
        rank([3]); q, k, v = inputs
        for port, tensor in zip(('query', 'key', 'value'), inputs):
            if tensor['dtype'] != 'float32': error('input_dtype_mismatch', '注意力需要 float32 Q/K/V。', port=port, expected='float32', actual=tensor['dtype'])
            if len(tensor['shape']) != 3: error('input_rank_mismatch', '注意力需要三维 Q/K/V。', port=port, expected=3, actual=len(tensor['shape']))
            if tensor['shape'][-1] != p['embed_dim']: error('attention_embed_dim_mismatch', 'Q/K/V 末维必须匹配 embed_dim。', port=port, parameter='embed_dim', expected=p['embed_dim'], actual=tensor['shape'][-1])
        ba = 0 if p['batch_first'] else 1; sa = 1 - ba
        if len({t['shape'][ba] for t in inputs}) != 1: error('attention_batch_mismatch', 'Q/K/V 批次数必须相同。', port='key')
        if k['shape'][sa] != v['shape'][sa]: error('attention_key_value_length', 'K/V 序列长度必须相同。', port='value', expected=k['shape'][sa], actual=v['shape'][sa])
        return check_budget({'output': {'shape': shape, 'dtype': dtype}, 'weights': {'shape': [q['shape'][ba], q['shape'][sa], k['shape'][sa]], 'dtype': dtype}}, name, fail)
    elif kind in ('Add', 'Subtract', 'Multiply', 'Divide', 'Concat', 'MatMul'):
        other = inputs[1]; port = 'b' if kind == 'Concat' else 'right'
        if dtype != other['dtype']: error('merge_input_dtype_mismatch', '两路输入类型必须相同。', port=port, expected=dtype, actual=other['dtype'])
        if len(shape) != len(other['shape']): error('merge_input_rank_mismatch', '两路输入维数必须相同。', port=port, expected=len(shape), actual=len(other['shape']))
        if kind == 'Concat':
            d = axis(p['dim'], len(shape), node, 'dim')
            if any(a != b for i, (a, b) in enumerate(zip(shape, other['shape'])) if i != d): error('concat_input_shape_mismatch', '拼接轴之外的维度必须一致。', parameter='dim', port='b', expected={'shape': shape, 'exceptAxis': d}, actual=other['shape'])
            shape[d] += other['shape'][d]
        elif kind == 'MatMul':
            floating()
            if len(shape) < 2 or shape[:-2] != other['shape'][:-2] or shape[-1] != other['shape'][-2]: error('matmul_shape_mismatch', '矩阵批次轴必须相同，左末维等于右倒数第二维。', port=port, actual=other['shape'])
            shape[-1] = other['shape'][-1]
        elif shape != other['shape']: error('add_input_shape_mismatch' if kind == 'Add' else 'elementwise_input_shape_mismatch', '逐元素两路形状必须一致，不隐式广播。', port=port, expected=shape, actual=other['shape'])
        elif kind == 'Divide': floating()
    elif kind in ('Mean', 'Sum'):
        if kind == 'Mean': floating()
        d = axis(p['dim'], len(shape), node, 'dim')
        if p['keepdim']: shape[d] = 1
        else: shape.pop(d)
    elif kind == 'Output' or kind == 'Identity': pass
    else:
        floating()
        if kind in ('Softmax', 'LogSoftmax'): axis(p['dim'], len(shape), node, 'dim')
        if kind == 'PReLU' and p['num_parameters'] not in (1, shape[1] if len(shape) >= 2 else 1): error('prelu_channels_mismatch', 'PReLU 参数数量须为 1 或输入通道数。', parameter='num_parameters')
        ranks = {'Dropout1d': [2, 3], 'Dropout2d': [4], 'Dropout3d': [5]}
        if kind in ranks: rank(ranks[kind])
        if kind == 'FeatureAlphaDropout' and len(shape) < 2: rank([2, 3, 4, 5, 6, 7, 8])
    return check_budget({'output': {'shape': shape, 'dtype': dtype}}, name, fail)


def check_budget(outputs, name, fail):
    for tensor in outputs.values():
        if len(tensor['shape']) > 8 or any(s < 1 for s in tensor['shape']) or math.prod(tensor['shape']) > 1000000000:
            fail(f'{name}: declared tensor exceeds the rank-8 / one-billion-element authoring budget.',
                 'tensor_budget_exceeded', '声明张量最多 8 维、十亿个元素，尺寸必须为正。')
    return outputs
