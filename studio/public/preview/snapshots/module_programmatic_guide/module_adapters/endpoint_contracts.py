"""Reviewed interfaces of visual scopes, independent of routing coordinates.

These aliases state which source operand/result a scope port denotes when its
operators are expanded. They are not inferred from labels, ranks or colors.
Ordinary serial boundaries stay with the shared IR resolver; only source-specific
named ports, selected tuple fields and graph helper results are declared here.
"""
from __future__ import annotations


# scope, exposed port, actual source-bound child, child's operand/result port.
# Every target is declared by the adapter and carries its original AST evidence.
CONTRACTS = {
    'autoregressive_mask': [
        ('compare', 'input_degrees', 'ge', 'input_degrees'),
        ('compare', 'output_degrees', 'ge', 'output_degrees'),
    ],
    'conditional_bn': [
        ('multiply', 'gain', 'mul', 'gain'),
        ('add', 'bias', 'addop', 'bias'),
    ],
    'coral_head': [('broadcast', 'threshold_bias', 'add', 'threshold_bias')],
    'flow_batchnorm': [
        ('stats', 'mean', 'mean', 'out'),
        ('stats', 'var', 'var', 'out'),
        ('normalize', 'mean', 'norm', 'mean'),
        ('normalize', 'var', 'norm', 'var'),
        ('running', 'mean', 'ema', 'mean'),
        ('running', 'var', 'ema', 'var'),
        ('det', 'var', 'detop', 'var'),
    ],
    'flow_sequential': [
        ('first', 'features', 'call0', 'features'),
        ('first', 'logdet', 'call0', 'logdet'),
        ('second', 'features', 'call1', 'features'),
        ('second', 'logdet', 'call1', 'logdet'),
        ('add0', 'accumulator', 'sum0', 'accumulator'),
        ('add0', 'increment', 'sum0', 'increment'),
        ('add1', 'accumulator', 'sum1', 'accumulator'),
        ('add1', 'increment', 'sum1', 'increment'),
    ],
    'glow_actnorm': [
        ('affine', 'loc', 'shift', 'loc'),
        ('affine', 'scale', 'scale', 'scale'),
        ('det', 'scale', 'abslog', 'scale'),
    ],
    'glow_invconv': [
        ('conv', 'weight', 'convop', 'weight'),
        ('det', 'weight', 'detop', 'weight'),
    ],
    'glow_invconv_lu': [
        ('conv', 'weight', 'convop', 'weight'),
        ('det', 'weight', 'detop', 'weight'),
    ],
    'glow_additive_coupling': [
        ('split', 'a', 'splitop', 'a'),
        ('split', 'b', 'splitop', 'b'),
        ('join', 'out_b', 'catop', 'out_b'),
        ('join', 'in_a', 'catop', 'in_a'),
    ],
    'glow_affine_coupling': [
        ('split', 'a', 'splitop', 'a'),
        ('split', 'b', 'splitop', 'b'),
        ('heads', 't', 'headsop', 't'),
        ('heads', 'log_s', 'headsop', 'log_s'),
        ('transform', 'scale', 'mulop', 'scale'),
        ('join', 'out_b', 'catop', 'out_b'),
        ('join', 'in_a', 'catop', 'in_a'),
    ],
    'glow_split_prior': [
        # Source's `out` is the retained first chunk, not the whole chunk tuple.
        ('split', 'out', 'splitop', 'retained'),
        ('split', 'z_new', 'splitop', 'z_new'),
        # The actual chunk operator returns both Gaussian parameters together.
        ('heads', 'mean_log_sd', 'headsop', 'mean_log_sd'),
        ('density', 'parameters', 'gauss', 'parameters'),
        ('density', 'sample', 'gauss', 'sample'),
    ],
    'made_affine': [
        ('heads', 'm', 'chunk', 'm'),
        ('heads', 'a', 'chunk', 'a'),
        ('shift', 'm', 'sub', 'm'),
        ('affine', 'scale', 'mul', 'scale'),
    ],
    'made_split': [
        ('shift', 'm', 'sub', 'm'),
        ('affine', 'scale', 'mul', 'scale'),
    ],
    'manual_fused_bn': [
        # m is retained from the compound moments operation; variance does not
        # produce m. The adapter records accumulation/cast semantics on moments.
        ('stats', 'mean', 'moments', 'mean'),
        ('stats', 'var', 'variance', 'out'),
        ('scale', 'gain', 'gainop', 'gain'),
        ('shift', 'mean', 'shiftop', 'mean'),
        ('shift', 'scale', 'shiftop', 'scale'),
        ('shift', 'bias', 'shiftop', 'bias'),
        ('affine', 'scale', 'out', 'scale'),
        ('affine', 'shift', 'out', 'shift'),
    ],
    'masked_linear': [('sum', 'condition', 'add', 'condition')],
    'nonlocal_attention': [
        ('beta', 'theta', 'score', 'theta'),
        ('beta', 'phi', 'score', 'phi'),
        ('aggregate', 'beta', 'bmm', 'beta'),
        ('aggregate', 'values', 'bmm', 'values'),
    ],
    'realnvp_coupling': [
        ('affine', 'scale', 'mul', 'scale'),
        ('affine', 't', 'mul', 't'),
    ],
}


def _walk(node):
    yield node
    for child in node.get('items', []):
        yield from _walk(child)


def annotate(model):
    """Attach source-bound scope interfaces to a local declaration in place."""
    nodes = {n['id']: n for tree in [model['tree'], *model.get('aux_inputs', [])]
             for n in _walk(tree)}
    key = model['key']

    def bind(scope, port, target, target_port, why):
        if scope not in nodes or target not in nodes:
            raise ValueError('Unknown reviewed port binding: ' + repr((scope, target)))
        scope_node = nodes[scope]
        target_node = nodes[target]
        if target == scope:
            raise ValueError('Self-referential scope port binding')
        value = {'node': target, 'port': target_port}
        existing = scope_node.setdefault('port_bindings', {}).get(port)
        if existing is not None and existing != value:
            raise ValueError('Conflicting source interface: ' + scope + ':' + port)
        scope_node['port_bindings'][port] = value
        scope_node.setdefault('port_binding_evidence', {})[port] = {
            'source': list(target_node['source']), 'reason': why,
        }

    for scope, port, child, child_port in CONTRACTS.get(key, []):
        prefix = key + '.'
        bind(prefix + scope, port, prefix + child, child_port,
             'Reviewed source operand/result; target AST symbol is carried by the child.')

    if key == 'edge_predictor':
        bind('edge.init', 'out', 'edge.buffer', 'out',
             "GraphNet.__init__ registers make_coordinate_array result as buffer 'coord'.")
    elif key == 'spectral_filter':
        bind('spectral.basis_init', 'out', 'spectral.vbuffer', 'out',
             "GraphNet.__init__ registers the selected eigsh eigenvectors as buffer 'V'.")
        bind('spectral.w_init', 'out', 'spectral.wbuffer', 'out',
             "GraphNet.__init__ registers node-domain W_spectral; forward reads that buffer.")
    elif key == 'transformer_xl_relative':
        bind('txl.shift', 'out', 'txl.shift_slice', 'out',
             'RelMultiHeadAttn._rel_shift returns x_padded[1:].view_as(x) in the selected zero_triu=False profile.')

    return model
