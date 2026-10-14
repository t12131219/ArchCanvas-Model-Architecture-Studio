"""Reviewed MNIST convolutional AE; decoder uses nearest interpolation + Conv2d."""
from spec import chain, op, parallel, ref

SOURCE = 'deeplearning-models-batch2/pytorch_ipynb/autoencoder/ae-conv-nneighbor.py'


def build():
    init = ref(SOURCE, 'ConvolutionalAutoencoder.__init__')
    forward = ref(SOURCE, 'ConvolutionalAutoencoder.forward')
    roles = {'convae.root': 'root', 'convae.encoder': 'encoder', 'convae.decoder': 'decoder',
             'convae.input': 'input', 'convae.returns': 'group', 'convae.output': 'output',
             'convae.logits': 'tensor', 'convae.sigmoid': 'softmax', 'convae.code': 'tensor'}
    fill = ['convae.encoder', 'convae.decoder', 'convae.returns']

    def stage(prefix, label, items, shape):
        roles[prefix] = 'conv'; fill.append(prefix)
        return chain(prefix, label, items, [init, forward], shape, expand=2)

    def conv(identity, cin, cout, side):
        roles[identity] = 'conv'
        return op(identity, 'Conv2d %d -> %d' % (cin, cout), 'conv2d', [init, forward],
                  '[B,%d,%d,%d]' % (cout, side, side),
                  ['kernel=3; stride=1; padding=1; bias=True'],
                  parameter='conv_' + identity.rsplit('conv', 1)[1])

    def activation(identity, channels, side):
        roles[identity] = 'activation'
        return op(identity, 'LeakyReLU', 'leaky_relu', forward,
                  '[B,%d,%d,%d]' % (channels, side, side),
                  ['F.leaky_relu default negative_slope=0.01'], negative_slope=0.01)

    encoder = chain('convae.encoder', 'Encoder: convolution + pooling', [
        stage('convae.enc1', 'Encode stage 1 / 1 -> 4', [
            conv('convae.conv1', 1, 4, 28),
            activation('convae.act1', 4, 28),
            op('convae.pool1', 'MaxPool2d 2x2 / 2', 'max_pool2d', [init, forward],
               '[B,4,14,14]', ['padding=0; pool indices are not returned']),
        ], '[B,4,14,14]'),
        stage('convae.enc2', 'Encode stage 2 / 4 -> 8', [
            conv('convae.conv2', 4, 8, 14),
            activation('convae.act2', 8, 14),
            op('convae.pool2', 'MaxPool2d 2x2 / 2', 'max_pool2d', [init, forward],
               '[B,8,7,7]', ['padding=0; no retained max-pool indices']),
        ], '[B,8,7,7]'),
    ], [init, forward], '[B,8,7,7]', expand=1)
    roles.update({'convae.pool1': 'pool', 'convae.pool2': 'pool'})

    decoder = chain('convae.decoder', 'Decoder: resize then convolution', [
        stage('convae.dec1', 'Decode stage 1 / nearest + 8 -> 4', [
            op('convae.resize1', 'Nearest interpolation x 2', 'interpolate', forward,
               '[B,8,14,14]', ["F.interpolate(scale_factor=2, mode='nearest')",
                              'not MaxUnpool2d; no learned upsampling weights'],
               scale_factor=2, mode='nearest', learnable=False),
            conv('convae.conv3', 8, 4, 14),
            activation('convae.act3', 4, 14),
        ], '[B,4,14,14]'),
        stage('convae.dec2', 'Decode stage 2 / nearest + 4 -> 1', [
            op('convae.resize2', 'Nearest interpolation x 2', 'interpolate', forward,
               '[B,4,28,28]', ["F.interpolate(scale_factor=2, mode='nearest')"],
               scale_factor=2, mode='nearest', learnable=False),
            conv('convae.conv4', 4, 1, 28),
            op('convae.act4', 'LeakyReLU -> logits', 'leaky_relu', forward,
               'logits: [B,1,28,28]', ['source applies activation AFTER final Conv2d',
                                       'F.leaky_relu default negative_slope=0.01'],
               negative_slope=0.01),
        ], '[B,1,28,28]'),
    ], [init, forward], 'logits: [B,1,28,28]', expand=1)
    roles.update({'convae.resize1': 'tensor', 'convae.resize2': 'tensor', 'convae.act4': 'activation'})
    returns = parallel('convae.returns', 'Return logits / decoded probabilities', [
        op('convae.logits', 'Retain activated logits', 'identity', forward,
           '[B,1,28,28]', ['return first field; used by binary_cross_entropy_with_logits']),
        op('convae.sigmoid', 'Sigmoid', 'sigmoid', forward,
           'probas: [B,1,28,28]', ['torch.sigmoid(logits); reconstruction in [0,1]']),
    ], forward, '(logits, probas)', expand=1,
       detail=['same logits tensor goes to both branches; tuple collection is not arithmetic addition'])
    tree = chain('convae.root', 'ConvolutionalAutoencoder / MNIST', [
        op('convae.input', 'MNIST grayscale image', 'input', forward,
           '[B,1,28,28]', ['caller ToTensor gives [0,1]; no image flattening']),
        encoder,
        op('convae.code', 'Encoded feature map', 'tensor', forward,
           '[B,8,7,7]', ['logical label for pool_2 output; not an extra source computation']),
        decoder, returns,
        op('convae.output', 'Forward return tuple', 'output', forward,
           '2 x [B,1,28,28]', ['return logits, probas; output is not only reconstruction']),
    ], forward, '(logits, probas)', expand=0)
    return dict(
        key='convae', name='ConvAE (nearest-neighbor MNIST)',
        source_project='deeplearning-models-batch2', entry=forward,
        profile=dict(task='MNIST image reconstruction', mode='eval', input_channels=1,
                     input_size=[28, 28], encoder_channels=[4, 8], decoder_channels=[4, 1],
                     conv_kernel=3, conv_stride=1, conv_padding=1, conv_bias=True,
                     encoder_pool='MaxPool2d(kernel=2,stride=2)',
                     decoder_upsampling="F.interpolate(scale_factor=2, mode='nearest')",
                     activation='LeakyReLU', negative_slope=0.01,
                     encoded_shape='[B,8,7,7]', output='(logits, probas)',
                     batch_size_setting=128, training_loss_in_forward=False,
                     config_source=SOURCE + ' notebook cells 7,9,11'),
        profile_label='MNIST / 28x28 / 4-8-4-1 channels / nearest interpolation',
        tree=tree, aux_inputs=[], extra_edges=[], visual_roles=roles, fill_width=fill,
        facts=[
            'Encoder is Conv1->LeakyReLU->MaxPool1->Conv2->LeakyReLU->MaxPool2.',
            'The code map has shape [B,8,7,7]; no fully connected latent layer or image flattening is present.',
            'Decoder performs two nearest-neighbor F.interpolate calls followed by ordinary Conv2d.',
            'conv_3 actually maps 8 to 4 channels; its nearby 14x14x8 comment is stale.',
            'MaxPool2d does not return indices, so no MaxUnpool2d or pooling-index dependency exists.',
            'Both F.leaky_relu calls in encoder and both in decoder use the API default negative_slope=0.01.',
            'The final Conv2d output is passed through LeakyReLU before being named logits and then Sigmoid.',
            'forward returns both activated logits and sigmoid probabilities; the loss uses logits in the caller.',
            'Four Conv2d modules have independent weights, with default bias=True; there is no BatchNorm.',
        ],
        corrections=[
            'The decoder comments say Unpool, but executed code is nearest interpolation; draw the actual function.',
            'Correct conv_3 channel label from the stale comment to the constructed 8->4 mapping.',
            'Do not substitute ConvTranspose2d, MaxUnpool2d or learned upsampling for this implementation.',
            'Keep the final LeakyReLU before Sigmoid, even though many other autoencoders omit it.',
            'Retain both forward outputs and keep binary_cross_entropy_with_logits outside the architecture.',
            'No model-specific reference PNG is supplied; the diagram follows source and the shared Transformer theme.',
        ],
        symbols={SOURCE: ['ConvolutionalAutoencoder', 'ConvolutionalAutoencoder.__init__',
                          'ConvolutionalAutoencoder.forward']},
        legend=['B: batch; [B,C,H,W] tensors; image 28x28; code 8x7x7',
                'nearest interpolation has no weights; decoder Conv2d has independent parameters',
                'same color = visual family; logits and probas are returned tuple fields'],
        config_files=[SOURCE],
    )
