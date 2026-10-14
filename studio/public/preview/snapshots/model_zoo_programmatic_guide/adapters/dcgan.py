"""Reviewed DCGAN two-entry caller composition; no DCGAN.forward is invented."""
from spec import chain, op, ref

SOURCE = 'deeplearning-models-batch2/pytorch_ipynb/gan/dcgan-celeba.py'


def build():
    init = ref(SOURCE, 'DCGAN.__init__')
    g_forward = ref(SOURCE, 'DCGAN.generator_forward')
    d_forward = ref(SOURCE, 'DCGAN.discriminator_forward')
    roles, fill = {}, []

    def g_stage(number, cin, cout, side, final=False):
        p = 'dcgan.g%d' % number
        # Sequential indexes follow ConvTranspose, BN, ReLU (except final Tanh).
        index = (number - 1) * 3
        first = number == 1
        items = [op(p + '.conv', 'ConvTranspose2d %d -> %d' % (cin, cout), 'conv_transpose2d', [init, g_forward],
                    '[B,%d,%d,%d]' % (cout, side, side),
                    ['kernel=4; stride=%d; padding=%d; bias=False' % (1 if first else 2, 0 if first else 1)],
                    parameter='generator.%d' % index,
                    kernel_size=4, stride=1 if first else 2, padding=0 if first else 1, bias=False)]
        roles[p + '.conv'] = 'conv'
        if not final:
            items.extend([
                op(p + '.bn', 'BatchNorm2d %d' % cout, 'batch_norm2d', [init, g_forward],
                   '[B,%d,%d,%d]' % (cout, side, side),
                   ['selected training call uses batch statistics'],
                   parameter='generator.%d' % (index + 1)),
                op(p + '.relu', 'ReLU', 'relu', [init, g_forward],
                   '[B,%d,%d,%d]' % (cout, side, side), ['inplace=True']),
            ])
            roles[p + '.bn'] = 'norm'; roles[p + '.relu'] = 'activation'
        else:
            items.append(op(p + '.tanh', 'Tanh image output', 'tanh', [init, g_forward],
                            '[B,3,64,64]', ['output range [-1,1] matches normalized real images']))
            roles[p + '.tanh'] = 'activation'
        roles[p] = 'conv'; fill.append(p)
        return chain(p, 'G stage %d / %dx%d' % (number, side, side), items,
                     [init, g_forward], '[B,%d,%d,%d]' % (cout, side, side),
                     expand=2 if number in (1, 5) else 3,
                     parameter_scope='generator.%d' % index)

    generator = chain('dcgan.generator', 'Entry 1: G(z)', [
        g_stage(1, 100, 512, 4),
        g_stage(2, 512, 256, 8),
        g_stage(3, 256, 128, 16),
        g_stage(4, 128, 64, 32),
        g_stage(5, 64, 3, 64, final=True),
    ], [init, g_forward], 'fake image: [B,3,64,64]',
       ['five independently parameterized transposed convolutions',
        'generator_forward returns self.generator(z)'], expand=1,
       parameter_scope='generator', entrypoint='DCGAN.generator_forward')

    def d_stage(number, cin, cout, side, final=False):
        p = 'dcgan.d%d' % number
        indexes = {1: 0, 2: 2, 3: 5, 4: 8, 5: 11}
        index = indexes[number]
        bias = number in (1, 5)
        items = [op(p + '.conv', 'Conv2d %d -> %d' % (cin, cout), 'conv2d', [init, d_forward],
                    '[B,%d,%d,%d]' % (cout, side, side),
                    ['kernel=4; stride=%d; padding=%d; bias=%s' % (1 if final else 2, 0 if final else 1, bias)],
                    parameter='discriminator.%d' % index,
                    kernel_size=4, stride=1 if final else 2, padding=0 if final else 1, bias=bias)]
        roles[p + '.conv'] = 'conv'
        if number in (2, 3, 4):
            items.append(op(p + '.bn', 'BatchNorm2d %d' % cout, 'batch_norm2d', [init, d_forward],
                            '[B,%d,%d,%d]' % (cout, side, side),
                            ['selected training call uses batch statistics'],
                            parameter='discriminator.%d' % (index + 1)))
            roles[p + '.bn'] = 'norm'
        if final:
            items.append(op(p + '.sigmoid', 'Sigmoid score', 'sigmoid', [init, d_forward],
                            'score: [B,1,1,1]', ['probability-like binary real/fake score; not class Softmax']))
            roles[p + '.sigmoid'] = 'softmax'
        else:
            items.append(op(p + '.leaky', 'LeakyReLU 0.2', 'leaky_relu', [init, d_forward],
                            '[B,%d,%d,%d]' % (cout, side, side), ['inplace=True'], negative_slope=0.2))
            roles[p + '.leaky'] = 'activation'
        roles[p] = 'conv'; fill.append(p)
        return chain(p, 'D stage %d / %dx%d' % (number, side, side), items,
                     [init, d_forward], '[B,%d,%d,%d]' % (cout, side, side),
                     expand=2 if number in (1, 5) else 3,
                     parameter_scope='discriminator.%d' % index)

    discriminator = chain('dcgan.discriminator', 'Entry 2: D(img)', [
        d_stage(1, 3, 64, 32),
        d_stage(2, 64, 128, 16),
        d_stage(3, 128, 256, 8),
        d_stage(4, 256, 512, 4),
        d_stage(5, 512, 1, 1, final=True),
    ], [init, d_forward], 'score: [B,1,1,1]',
       ['source calls global model.discriminator(img), not self.discriminator(img)',
        'selected notebook global model aliases the constructed DCGAN instance'],
       expand=1, parameter_scope='global model.discriminator',
       entrypoint='DCGAN.discriminator_forward',
       global_receiver='model', receiver_assumption='notebook global model is selected DCGAN instance')

    scoring = chain('dcgan.scoring', 'Caller: score generated image', [
        generator,
        op('dcgan.fake', 'Retain fake image / no detach', 'tensor', g_forward,
           '[B,3,64,64]', ['selected generator update call passes fake_images to D without detach',
                         'this label denotes the method result / caller boundary, not another operator'],
           boundary='caller', gradient_detach=False, producer='DCGAN.generator_forward'),
        discriminator,
    ], [g_forward, d_forward], 'z -> fake image -> score',
       ['two explicit method calls composed by notebook caller; no DCGAN.forward exists',
        'not a complete training or loss graph'], expand=0,
       diagram_scope='caller composition', caller_notebook_cells=[25],
       source_entrypoints=['DCGAN.generator_forward', 'DCGAN.discriminator_forward'])
    tree = chain('dcgan.root', 'DCGAN / selected G-to-D caller path', [
        op('dcgan.noise', 'Caller latent noise z', 'input', g_forward,
           '[B,100,1,1]', ['LATENT_DIM=100; notebook caller creates torch.randn tensors',
                          'batch_size setting 128; B kept symbolic'],
           origin='caller random_vec', stochastic=True, caller_notebook_cells=[25]),
        scoring,
        op('dcgan.score', 'Returned discriminator score', 'output', d_forward,
           '[B,1,1,1]', ['discriminator_forward returns pred without flattening',
                        'caller .view(-1), BCELoss and optimizers are outside this drawing']),
    ], [init, g_forward, d_forward], 'caller composition, not DCGAN.forward', expand=0,
       diagram_scope='caller composition: selected fake-image scoring for generator update',
       no_unified_forward=True,
       source_entrypoints=['DCGAN.generator_forward', 'DCGAN.discriminator_forward'])
    roles.update({'dcgan.root': 'root', 'dcgan.scoring': 'group',
                  'dcgan.generator': 'decoder', 'dcgan.discriminator': 'encoder',
                  'dcgan.noise': 'input', 'dcgan.fake': 'tensor', 'dcgan.score': 'output'})
    fill.extend(['dcgan.scoring', 'dcgan.generator', 'dcgan.discriminator'])
    return dict(
        key='dcgan', name='DCGAN (G-to-D caller)',
        source_project='deeplearning-models-batch2', entry=ref(SOURCE, 'DCGAN'),
        profile=dict(task='CelebA adversarial image generation', mode='selected training-mode generator scoring call',
                     diagram_scope='caller composition: fake_images = generator_forward(z); discriminator_forward(fake_images)',
                     source_entrypoints=['DCGAN.generator_forward', 'DCGAN.discriminator_forward'],
                     no_unified_forward=True, real_image_call_in_main_graph=False,
                     gradient_detach=False, latent_dim=100, num_maps_gen=64, num_maps_dis=64,
                     image_size=[64, 64, 3], image_layout='NCHW', batch_size_setting=128,
                     generator_channels=[100, 512, 256, 128, 64, 3],
                     generator_spatial=[1, 4, 8, 16, 32, 64],
                     discriminator_channels=[3, 64, 128, 256, 512, 1],
                     discriminator_spatial=[64, 32, 16, 8, 4, 1],
                     generator_batchnorm_count=4, discriminator_batchnorm_count=3,
                     generator_conv_bias=False, discriminator_conv_bias=[True, False, False, False, True],
                     discriminator_global_receiver='model',
                     global_model_alias_assumption='module global model is the same selected constructed DCGAN instance',
                     source_discriminator_uses_self=False,
                     output='[B,1,1,1] score; caller flatten is outside methods',
                     output_range='G Tanh [-1,1]; D Sigmoid [0,1]',
                     caller_notebook_cells=[9, 16, 21, 25],
                     training_losses_in_graph=False, model_executed=False),
        profile_label='CelebA 64x64 / latent 100 / maps 64 / explicit G-to-D caller path',
        tree=tree, aux_inputs=[], extra_edges=[], visual_roles=roles, fill_width=fill,
        facts=[
            'DCGAN defines generator_forward and discriminator_forward but has no forward method.',
            'The graph is the notebook caller composition for scoring generated images in a generator update, not a fabricated DCGAN.forward.',
            'discriminator_forward calls the module global model.discriminator(img); the selected notebook global model is assumed to alias the constructed DCGAN instance.',
            'Generator has five ConvTranspose2d layers, four BatchNorm2d layers, four ReLU calls and a final Tanh.',
            'Generator channels/spatial sizes are 100@1 -> 512@4 -> 256@8 -> 128@16 -> 64@32 -> 3@64.',
            'Every generator convolution has bias=False; the first is kernel4/stride1/padding0, the others kernel4/stride2/padding1.',
            'Discriminator has five Conv2d layers, three BatchNorm2d layers, four LeakyReLU(0.2) calls and a final Sigmoid.',
            'Discriminator channels/spatial sizes are 3@64 -> 64@32 -> 128@16 -> 256@8 -> 512@4 -> 1@1.',
            'Discriminator first/last Conv2d use default bias=True; middle three set bias=False. No BN follows first/last Conv2d.',
            'The selected generator update scores fake_images without detach. The separate discriminator update scores real_images and fake_images.detach().',
            'Real-image and fake-image calls share the same selected discriminator parameters; they are alternative calls, not a Concat/Add of images.',
            'The method returns [B,1,1,1]; the caller .view(-1), BCELoss labels and optimizer steps are outside this graph.',
            'BatchNorm uses training batch statistics in the selected call; a monitoring generator-only call is a different scope.',
            'Intermediate same-family stages are folded in detailed view; the IR retains every parameterized/functional module call.',
        ],
        corrections=[
            'Do not draw a single DCGAN.forward: this class exposes two custom entry methods, composed only by the notebook caller.',
            'Keep the source global model.discriminator receiver visible; do not silently rewrite it to self.discriminator.',
            'Do not fuse real and generated images into one simultaneous dataflow input; real scoring is a separate call.',
            'Do not place detach on the selected generator update path; detach appears on the fake branch of the discriminator update.',
            'Generator output uses Tanh and discriminator output uses Sigmoid; they are different activation/range semantics.',
            'Respect the asymmetry in BatchNorm and convolution bias placement; textbook defaults are not a substitute for this constructor.',
            'No model-specific reference PNG is supplied; source structure is rendered with the shared Transformer theme.',
        ],
        symbols={SOURCE: ['DCGAN', 'DCGAN.__init__', 'DCGAN.generator_forward',
                          'DCGAN.discriminator_forward', 'weights_init',
                          'CelebaDataset', 'CelebaDataset.__init__', 'CelebaDataset.__getitem__', 'CelebaDataset.__len__']},
        legend=['B: symbolic batch; latent 100x1x1 -> generated 3x64x64 -> D score 1x1x1',
                'selected G-to-D caller composition; no unified forward; no detach on this path',
                'real scoring and discriminator-update detach are separate calls explained in docs'],
        config_files=[SOURCE],
    )
