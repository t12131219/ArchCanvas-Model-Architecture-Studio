"""Reviewed source interfaces for the static 25-model example adapters.

This module never imports or runs upstream models.  Chain traversal belongs to
the shared renderer; named interfaces here are facts established from the saved
source expressions, never from visual ranks or bounding boxes.  ``out`` lists
describe separate returned/operand values, not their arithmetic reduction.
"""
from __future__ import annotations


def annotate(model):
    """Add explicit endpoint contracts in place and return the adapter model.

    Idempotent and usable before/after styling.  Only existing adapter nodes are
    referenced.  Source files and the modeled upstream implementation are not
    changed.  A missing node in a named contract is an adapter error.
    """
    nodes = {}

    def visit(node):
        if node['id'] in nodes:
            raise ValueError('duplicate endpoint-contract node: ' + node['id'])
        nodes[node['id']] = node
        for child in node.get('items', []):
            visit(child)

    visit(model['tree'])
    for auxiliary in model.get('aux_inputs', []):
        visit(auxiliary)

    def endpoint(identity, port='out'):
        if identity not in nodes:
            raise ValueError('unknown endpoint-contract target: ' + identity)
        return dict(node=identity, port=port)

    def bind(identity, **ports):
        if identity not in nodes:
            raise ValueError('unknown endpoint-contract scope: ' + identity)
        if not nodes[identity].get('items'):
            # Return.mu is a consuming terminal when an arrow enters Return,
            # but an alias for the retained tensor when Return is a producer.
            # Applying that output alias to a destination would erase its wire.
            ports = {name: ([dict(value, direction='src') for value in binding]
                            if isinstance(binding, list) else dict(binding, direction='src'))
                     for name, binding in ports.items()}
        nodes[identity].setdefault('port_bindings', {}).update(ports)

    def pair(identity, first, second, first_name='logits', second_name='probas'):
        """Two source return fields; their common input is a separate fact."""
        first, second = endpoint(first), endpoint(second)
        bind(identity, out=[first, second], **{
            'item[0]': first, 'item[1]': second,
            first_name: first, second_name: second,
        })

    key = model['key']
    returns = {
        'lenet': ('lenet', 'softmax'), 'resnet': ('resnet', 'softmax'),
        'resnet50': ('r50', 'softmax'), 'resnet101': ('r101', 'softmax'),
        'vgg16': ('vgg', 'softmax'), 'vgg19': ('v19', 'softmax'),
        'nin': ('nin', 'softmax'), 'convae': ('convae', 'sigmoid'),
        'graphnet': ('graphnet', 'softmax'),
    }
    if key in returns:
        prefix, activation = returns[key]
        pair(prefix + '.returns', prefix + '.logits', prefix + '.' + activation)

    if key == 'unet':
        # UNet.forward: encN=self.encoderN(...), then cat((decN,encN),1).
        # The pool is a sibling, so these aliases must never resolve to poolN.
        for stage in range(1, 5):
            bind('unet_enc%d' % stage,
                 skip=endpoint('unet_enc%d_block' % stage))

    if key == 'densenet':
        # Bottleneck.forward: torch.cat((x,out),1). Retained is this very x.
        for stage in range(1, 4):
            identity = 'dense_b%d_input' % stage
            bind(identity, retained=endpoint(identity))

    if key == 'resnet':
        # BasicBlock.forward uses two values in out += residual, no Python tuple.
        for stage in range(2, 5):
            base = 'resnet.stage%d.downsample' % stage
            paths = nodes[base + '.paths']
            paths.update(semantic_mode='operand_bundle', literal_tuple=False,
                         shape='two matching Add operands',
                         child_inputs={child['id']: dict(role='value', producer=base,
                                                        src_port='in')
                                       for child in paths['items']})

    if key in ('vae', 'convvae', 'ccvae'):
        p = key + '.'
        if key == 'vae':
            # encoder calls reparameterize(z_mean,z_log_var), not a tuple fork.
            posterior = nodes[p + 'posterior']
            posterior.update(semantic_mode='operand_bundle', literal_tuple=False,
                             shape='mu / logvar: independent operands',
                             child_inputs={child['id']: dict(role='value',
                                                            producer=p + 'enc_activation',
                                                            src_port='out')
                                           for child in posterior['items']})
            args = nodes[p + 'sample_operands']
            args.update(semantic_mode='operand_bundle', literal_tuple=False,
                        dispatch=False, shape='two Add operands', child_inputs={
                            p + 'mean_operand': dict(role='value', producer=p + 'mu', src_port='out'),
                            p + 'scaled_noise': dict(role='value', producer=p + 'logvar', src_port='out'),
                        })
            shape_edge = dict(src=p + 'mu', dst=p + 'epsilon',
                              role='shape_dependency', label='mu B,latent / shape only',
                              src_port='shape', dst_port='shape')
            if not any(edge.get('src') == shape_edge['src']
                       and edge.get('dst') == shape_edge['dst']
                       and edge.get('role') == 'shape_dependency'
                       for edge in model.setdefault('extra_edges', [])):
                # reparameterize constructs randn(z_mu.size(0),z_mu.size(1)).
                model['extra_edges'].append(shape_edge)
            mean_arg = p + 'mean_operand'
            args_id = p + 'sample_operands'
            decoder_output = p + 'dec_sigmoid'
        else:
            mean_arg = p + 'retain_mu'
            args_id = p + 'sample_args'
            decoder_output = p + 'sigmoid'
        # Head scopes yield distinct tensor values; operand grouping is display.
        pair(p + 'posterior', p + 'mu', p + 'logvar', 'mu', 'logvar')
        pair(args_id, mean_arg, p + 'noise_product', 'mu', 'scaled_noise')
        bind(p + 'sampling', out=endpoint(p + 'z'))
        # Actual encoder result is (z_mean,z_log_var,encoded).
        values = {name: endpoint(p + leaf) for name, leaf in (
            ('mu', 'mu'), ('z_mean', 'mu'), ('logvar', 'logvar'),
            ('z_log_var', 'logvar'), ('z', 'z'), ('encoded', 'z'))}
        for scope in (p + 'encoder', p + 'encoder_return'):
            bind(scope, **values, **{
                'item[0]': values['mu'], 'item[1]': values['logvar'],
                'item[2]': values['encoded'],
            })
        decoded = endpoint(decoder_output)
        for scope in (p + 'forward', p + 'return'):
            bind(scope, **values, decoded=decoded, **{
                'item[0]': values['mu'], 'item[1]': values['logvar'],
                'item[2]': values['encoded'], 'item[3]': decoded,
            })

    if key == 'graphnet':
        # Construction: register_buffer('A', A); forward: self.A.expand(...).
        bind('graphnet.adjacency', out=endpoint('graphnet.buffer'),
             A=endpoint('graphnet.buffer'))
        # torch.bmm(A_tensor,x_reshape) is ordered, unlike addition.
        pair('graphnet.operands', 'graphnet.expand', 'graphnet.features_operand', 'A', 'X')

    if key == 'bilstm':
        # RNN.forward explicitly cats hidden[-2] followed by hidden[-1].
        pair('bilstm.last_layer', 'bilstm.forward_state', 'bilstm.reverse_state',
             'forward_hidden', 'reverse_hidden')

    if key == 'textcnn':
        # TextCNN.forward widths are source ModuleList order (3,4,5).
        for slot, width in enumerate((3, 4, 5)):
            base = 'textcnn.k%d' % width
            bind('textcnn.branches', **{'item[%d]' % slot: endpoint(base + '.amax')})
            pair(base + '.operands', base + '.features_operand', base + '.mask',
                 'features', 'mask')
            # positions[None,:] >= valid_windows[:,None] is ordered.
            pair(base + '.mask_operands', base + '.positions', base + '.clamp',
                 'positions', 'valid_windows')

    if key == 'lstmcell':
        # custom_lstms.py: LSTMLayer calls one cell, passing both state fields.
        # Each graph is containment only; no rank-derived default input exists.
        for step in range(3):
            base = 'lstmcell.step%d' % step
            ep = lambda name, port='out': endpoint(base + '.' + name, port)
            bind(base, input=ep('x', 'in'), previous_hidden=ep('hx', 'in'),
                 previous_cell=ep('cx', 'in'), out=ep('return'),
                 output_hidden=ep('hy'), state_hidden=ep('hy'), state_cell=ep('cy'),
                 **{'item[0]': ep('hy'), 'item[1][0]': ep('hy'), 'item[1][1]': ep('cy')})
            bind(base + '.affine', input=ep('x_mm', 'in'),
                 previous_hidden=ep('h_mm', 'in'), out=ep('b_hh'))
            for slot, gate in enumerate(('i', 'f', 'g', 'o')):
                bind(base + '.gates', **{
                    'item[%d]' % slot: ep(gate, 'in'), gate: ep(gate),
                })
            bind(base + '.cell_update', forget_gate=ep('forget_mul', 'f'),
                 previous_cell=ep('forget_mul', 'previous_c'),
                 input_gate=ep('input_mul', 'i'), candidate=ep('input_mul', 'g'),
                 out=ep('cy'), cell=ep('cy'))
            bind(base + '.hidden_update', cell=ep('tanh_c', 'in'),
                 output_gate=ep('hy', 'o'), out=ep('hy'), hidden=ep('hy'))
            bind(base + '.return', output_hidden=ep('hy'), state_hidden=ep('hy'),
                 state_cell=ep('cy'), **{
                     'item[0]': ep('hy'), 'item[1][0]': ep('hy'), 'item[1][1]': ep('cy')})
        # The root remains a display scope: sequence and supplied h/c are
        # separate inputs, returned stack/final state are explicitly wired.

    if key in ('vae', 'resnet'):
        correction = ('Independent source operands are routed from their actual producers; '
                      'a display scope does not invent a Python tuple or shared-value fork.')
        if correction not in model.setdefault('corrections', []):
            model['corrections'].append(correction)
    return model
