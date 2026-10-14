"""Reviewed MNIST convolutional WGAN and shared static drawing template."""
from spec import chain, graph, op, ref

SOURCE = "deeplearning-models-batch4/pytorch_ipynb/gan/dc-wgan-1.py"


def _build(key, source, wasserstein=True):
    def nid(s): return key + "." + s
    init = ref(source, "GAN.__init__")
    gen = ref(source, "GAN.generator_forward")
    dis = ref(source, "GAN.discriminator_forward")
    caller = ref(source, "__module__")
    flatten = ref(source, "Flatten.forward")
    reshape = ref(source, "Reshape1.forward")
    roles, fill, edges = {}, [], []
    low = 0.0 if wasserstein else -1.0
    depth = 3 if wasserstein else 2
    dchannels = [1, 8, 16, 32] if wasserstein else [1, 8, 32]
    dspatial = [28, 14, 7, 4] if wasserstein else [28, 14, 7]
    dlinear = 512 if wasserstein else 1568

    def edge(a, b, role="tensor", sp="out", dp="in", label="", source_side="out", destination_side="in"):
        edges.append(dict(src=nid(a), dst=nid(b), role=role, src_port=sp, dst_port=dp,
                          label=label, src_side=source_side, dst_side=destination_side,
                          dashed=role=="shape_dependency"))

    def bn(identity, parameter, channels, shape, dimensions, scope):
        roles[identity] = "norm"
        return op(identity, "BatchNorm%d / %d" % (dimensions, channels), "normalization", [init, scope], shape,
                  ["train mode: current-batch statistics; affine=True, track_running_stats=True",
                   "eps=1e-5, momentum=0.1 from API defaults; repeated D calls reuse buffers"],
                  parameter=parameter, instance_identity=parameter, num_features=channels,
                  dimensionality=dimensions, affine=True, track_running_stats=True, mode="train")

    def leaky(identity, shape, scope):
        roles[identity] = "activation"
        return op(identity, "LeakyReLU 0.0001", "activation", [init, scope], shape,
                  ["inplace=True; actual explicitly configured slope"],
                  negative_slope=0.0001, inplace=True)

    def generator_stage(i, cin, cout, side, kernel, stride, padding, seq_index):
        identity = nid("generator.stage%d" % i)
        shape = "[B,%d,%d,%d]" % (cout, side, side)
        conv = op(identity + ".conv", "ConvTranspose2d %d -> %d" % (cin, cout), "conv", [init, gen], shape,
                  ["kernel=%d; stride=%d; padding=%d; output_padding=0; bias=False" % (kernel, stride, padding)],
                  parameter="generator.%d" % seq_index, in_channels=cin, out_channels=cout,
                  kernel_size=kernel, stride=stride, padding=padding, output_padding=0, bias=False,
                  convolution_type="ConvTranspose2d")
        roles[identity], roles[conv["id"]] = "conv", "conv"; fill.append(identity)
        items = [conv]
        if i < 4:
            items += [bn(identity + ".bn", "generator.%d" % (seq_index+1), cout, shape, 2, gen),
                      leaky(identity + ".activation", shape, gen)]
        else:
            items.append(op(nid("generator.tanh"), "Tanh generated pixels", "activation", [init, gen], shape,
                            ["generator_forward returns this image tensor; values in [-1,1]"],
                            activation="tanh", output_range=[-1,1]))
            roles[nid("generator.tanh")] = "softmax"
        return chain(identity, "Generator upsample %d" % i, items, [init, gen], shape,
                     ["Sequential indices retained; different stages have independent weights"],
                     expand=2 if i in (1,4) else 3)

    projection = chain(nid("generator.projection"), "Latent projection / reshape", [
        op(nid("generator.linear"), "Linear 100 -> 3136", "linear", [init, gen], "[B,3136]",
           ["LATENT_DIM=100; bias=False"], parameter="generator.0", in_features=100, out_features=3136, bias=False),
        bn(nid("generator.bn1d"), "generator.1", 3136, "[B,3136]", 1, gen),
        leaky(nid("generator.projection_activation"), "[B,3136]", gen),
        op(nid("generator.reshape"), "Reshape1: 64 x 7 x 7", "tensor", [reshape, init, gen], "[B,64,7,7]",
           ["input.view(input.size(0),64,7,7); registered as generator.3"],
           expression="input.view(input.size(0),64,7,7)", instance_identity="generator.3"),
    ], [init, gen, reshape], "[B,64,7,7]", expand=2)
    roles[nid("generator.projection")] = "ffn"; fill.append(nid("generator.projection"))
    roles[nid("generator.linear")] = "linear"; roles[nid("generator.reshape")] = "tensor"
    generator = chain(nid("generator"), "Generator G", [projection,
        generator_stage(1,64,32,13,3,2,1,4),
        generator_stage(2,32,16,25,3,2,1,7),
        generator_stage(3,16,8,27,3,1,0,10),
        generator_stage(4,8,1,28,2,1,0,13),
    ], [init, gen], "generated_features: [B,1,28,28]", expand=1,
        instance_identity="model.generator", parameter_scope="generator", entry_point="GAN.generator_forward")
    roles[nid("generator")] = "decoder"; fill.append(nid("generator"))

    def discriminator_call(call, title, expand, objective, detached=False):
        base = nid(call)
        stages = []
        for i in range(1,depth+1):
            seq_index = (i-1)*3
            identity = base + ".stage%d" % i
            shape = "[B,%d,%d,%d]" % (dchannels[i],dspatial[i],dspatial[i])
            conv = op(identity+".conv", "Conv2d %d -> %d" % (dchannels[i-1],dchannels[i]), "conv", [init, dis], shape,
                      ["kernel=3; stride=2; padding=1; bias=False; same D instance at all call sites"],
                      parameter="discriminator.%d" % seq_index, instance_identity="model.discriminator",
                      in_channels=dchannels[i-1], out_channels=dchannels[i], kernel_size=3, stride=2, padding=1,
                      bias=False, convolution_type="Conv2d", call_site=call)
            stages.append(chain(identity, "%s stage %d" % ("Critic" if wasserstein else "Discriminator",i), [
                conv,
                bn(identity+".bn", "discriminator.%d" % (seq_index+1), dchannels[i], shape, 2, dis),
                leaky(identity+".activation", shape, dis),
            ], [init,dis],shape,expand=2 if i==1 else 3,parameter_scope="discriminator.%d" % seq_index))
            roles[identity],roles[conv['id']] = "conv","conv";fill.append(identity)
        items = stages + [
            op(base+".flatten", "Flatten feature map", "tensor", [flatten,init,dis], "[B,%d]" % dlinear,
               ["input.view(input.size(0),-1); actual Flatten module"],
               expression="input.view(input.size(0),-1)", instance_identity="discriminator.%d" % (depth*3)),
            op(base+".linear", "Linear %d -> 1" % dlinear, "linear", [init,dis], "[B,1]",
               ["bias=True from default; Sigmoid is commented out"],
               parameter="discriminator.%d" % (depth*3+1),instance_identity="model.discriminator",
               in_features=dlinear,out_features=1,bias=True,call_site=call),
            op(base+".return", "view(-1): %s" % ("critic scores" if wasserstein else "raw logits"), "output", dis, "[B]",
               ["discriminator_forward calls GLOBAL model.discriminator(img), then pred.view(-1)",
                "No Sigmoid or Softmax in either discriminator variant"],
               expression="pred.view(-1)", receiver="model.discriminator",output_semantics="critic_score" if wasserstein else "binary_logit"),
        ]
        roles[base],roles[base+".linear"],roles[base+".return"] = "encoder","linear","output"
        roles[base+".flatten"] = "tensor";fill.append(base)
        return chain(base,title,items,[init,dis,flatten],"[B] raw scores / SAME D parameters",expand=expand,
                     instance_identity="model.discriminator",parameter_scope="discriminator",call_site=call,
                     entry_point="GAN.discriminator_forward",objective=objective,gradient_to_generator=not detached and objective=="generator")

    def image_view(identity, source_name):
        roles[identity] = "tensor"
        return op(identity,"Caller view as image","tensor",caller,"[B,1,28,28]",
                  ["%s.view(targets.size(0),1,28,28); already matches shape for generated images" % source_name],
                  expression=source_name+".view(targets.size(0),1,28,28)",boundary="caller")

    gcall = discriminator_call("d_for_g","D call / generator objective",2,"generator")
    fakecall = discriminator_call("d_fake","D call / detached fake",3,"discriminator_fake",True)
    realcall = discriminator_call("d_real","D call / real image",3,"discriminator_real",True)
    gphase = chain(nid("g_score_path"),"G objective / D(fake)",[
        image_view(nid("g_image_view"),"generated_features"),gcall,
    ],caller,"score [B] / no detach",expand=1,boundary="caller",phase="generator_step",gradient_to_generator=True)
    fakephase = chain(nid("fake_score_path"),"D objective / detached fake",[
        image_view(nid("fake_image_view"),"generated_features"),
        op(nid("detach"),"detach: block gradient to G","control",caller,"[B,1,28,28]",
           ["Same previously generated tensor; detach changes autograd, not pixel values",
            "No fresh generator sample inside the discriminator loop"],
           expression="generated_features.view(targets.size(0),1,28,28).detach()",boundary="caller",
           gradient_to_generator=False,value_preserved=True),
        fakecall,
    ],caller,"fake score: [B]",expand=1,boundary="caller",phase="discriminator_step",gradient_to_generator=False)
    realphase = chain(nid("real_score_path"),"D objective / real image",[
        image_view(nid("real_image_view"),"features"),realcall,
    ],caller,"real score: [B]",expand=1,boundary="caller",phase="discriminator_step",gradient_to_generator=False)
    for suffix in ("g_score_path","fake_score_path","real_score_path"):
        roles[nid(suffix)] = "group";fill.append(nid(suffix))
    roles[nid("detach")] = "control"
    prepare = chain(nid("real_prepare"),"Caller real-image preparation",[
        op(nid("normalize"),"Normalize pixels to [-1,1]","tensor",caller,"[B,1,28,28]",
           expression="(features - 0.5)*2.",boundary="caller"),
        op(nid("real_flatten"),"view(-1, IMG_SIZE) + to(device)","tensor",caller,"[B,784]",
           ["IMG_SIZE=1*28*28; discriminator call later views this back to image"],
           expression="features.view(-1, IMG_SIZE).to(device)",boundary="caller"),
    ],caller,"features: [B,784]",expand=2,boundary="caller")
    roles[nid("real_prepare")] = "inner";roles[nid("normalize")] = "tensor";roles[nid("real_flatten")] = "tensor"
    noise = op(nid("noise"),"Caller Uniform [%g,1) noise" % low,"sampling",caller,"z: [B,100]",
               ["zeros((targets.size(0),LATENT_DIM)).uniform_(%s,1.0).to(device)" % ("0.0" if wasserstein else "-1.0"),
                "External to generator; MNIST target values are not conditioning labels"],
               origin="caller_uniform_random_source",distribution="uniform",low=low,high=1.0,
               latent_dim=100,stochastic=True,learnable=False,boundary="caller",batch_size_from="targets.size(0)")
    real = op(nid("real_input"),"Real MNIST image / ToTensor","input",caller,"[B,1,28,28] in [0,1]",
              ["Caller dataset image; not generated by G"],origin="train_loader features")
    targets = op(nid("batch_targets"),"Batch targets / size only","input",caller,"targets: [B]",
                 ["Only targets.size(0) sizes z and validity vectors; class values do not condition G or D"],
                 origin="train_loader targets",learnable=False,value_used_for_conditioning=False)
    roles[nid("noise")]="sampling";roles[nid("real_input")]="input";roles[nid("batch_targets")]="input"
    tree = graph(nid("root"),"DC-WGAN / training call paths" if wasserstein else "ConvGAN / training call paths",
                 [noise,real,generator,prepare,gphase,fakephase,realphase],caller,
                 "two model entries / three D calls / no joint forward",
                 ["DAG of caller data dependencies, not one GAN.forward method or a three-field return"],
                 ranks=[[nid("noise"),nid("real_input")],[nid("generator"),nid("real_prepare")],
                        [nid("g_score_path"),nid("fake_score_path"),nid("real_score_path")]],
                 expand=0,rank_gap=72,column_gap=64,
                 align_x={nid("noise"):nid("generator"),nid("generator"):nid("g_score_path"),
                          nid("real_input"):nid("real_prepare"),nid("real_prepare"):nid("real_score_path")},
                 semantic_scope="caller_training_forward_paths",literal_tuple=False,joint_forward_defined=False)
    roles[nid("root")]="root"
    edge("noise","generator")
    edge("real_input","real_prepare")
    edge("generator.tanh","g_score_path",label="fake / no detach")
    edge("generator.tanh","fake_score_path",label="same generated tensor")
    edge("real_flatten","real_score_path")
    edge("batch_targets","noise",role="shape_dependency",sp="shape",dp="batch_shape",label="B=targets.size(0)",
         source_side="right",destination_side="left")
    facts = [
        "GAN defines generator_forward and discriminator_forward, without its own forward override; this figure is a caller data-flow DAG, not a joint model return.",
        "generator_forward uses self.generator; discriminator_forward actually uses global model.discriminator, not self.discriminator.",
        "Generator Sequential is Linear100->3136(bias=False), BN1d, LeakyReLU .0001, Reshape64x7x7, four transposed convolutions, Tanh.",
        "Generator ConvTranspose kernels/strides/padding are (3,2,1),(3,2,1),(3,1,0),(2,1,0); channels64->32->16->8->1 and spatial7->13->25->27->28.",
        "Generator BN2d and LeakyReLU follow its first three transposed convolutions; final ConvTranspose is followed directly by Tanh.",
        "All Conv/ConvTranspose layers and generator Linear use bias=False; discriminator Linear keeps default bias=True. LeakyReLU slope .0001 is explicit and inplace=True.",
        "All BatchNorm layers use default affine/running-stat settings; selected train profile uses batch statistics and updates same D buffers at each call site.",
        "Both discriminators have a commented-out Sigmoid, so they return pred.view(-1) raw scores [B], never probabilities.",
        "Caller noise is externally sampled Uniform(%g,1) with width100; targets values never provide class conditioning." % low,
        "Caller normalizes real image via (features-.5)*2, flattens to784, then views it back to[B,1,28,28] at discriminator entry.",
        "Generator objective calls D(generated.view(...)) without detach; D fake objective uses the same previously computed image.detach(), blocking only gradient to G.",
        "Three visible D call sites share one model.discriminator parameter family and BatchNorm buffers; they are not independent discriminators.",
        "Source updates G before D. The fake tensor is reused after G optimizer.step; no fresh G forward occurs inside the D update block.",
        "Losses, optimizers, backward, clipping and update order are caller operations outside the selected forward-data paths; graph ranks do not imply parallel Python execution.",
        "Dropout2d and debug hooks appear only in comments/string literals and are not executed model operators.",
        "The final visualization sets eval and calls generator_forward only; its different BatchNorm mode is not mixed into this selected training graph.",
    ]
    corrections = [
        "Retain true7->13->25->27->28 generator geometry rather than textbook7->14->28 upsampling.",
        "Do not add GAN.forward, a shared tuple output, conditioning embedding, attention, Dropout2d or debug hooks absent from executed source.",
        "Keep raw discriminator scores; the commented Sigmoid is not an actual layer, including in the BCE GAN variant.",
        "Distinguish three D call sites from three D instances; retain shared parameter identities and the caller-only detach boundary.",
        "Do not detach the generator-objective path or regenerate fake samples for every D call when source reuses generated_features.",
        "Preserve the actual global model.discriminator receiver; drawing does not silently repair it to self.discriminator.",
    ]
    if wasserstein:
        facts += [
            "WGAN critic has three Conv stages1->8->16->32 with spatial28->14->7->4, Flatten512, Linear512->1 and no Sigmoid.",
            "Caller Wasserstein loss is mean(y_true*y_pred), with valid=-1 and fake=+1; generator minimizes negative mean critic score.",
            "Caller uses RMSprop lr5e-5, num_iter_critic=5 and clamps all discriminator parameters to[-.01,.01] after each critic step; no gradient penalty.",
        ]
        corrections += ["WGAN uses uniform[0,1) noise, a three-stage critic and weight clipping, not Gaussian noise, Sigmoid/BCE or WGAN-GP."]
    else:
        facts += [
            "ConvGAN discriminator has two Conv stages1->8->32, spatial28->14->7, Flatten1568 and Linear1568->1.",
            "Caller BCEWithLogits uses valid=1 and fake=0; logits remain unnormalized until loss calculation.",
            "Caller uses Adam lr1e-4 and one D update per batch, with no clipping or gradient penalty.",
        ]
        corrections += ["ConvGAN uses uniform[-1,1) noise and two D Conv stages; do not import WGAN's third stage, signed labels or clipping."]
    return dict(key=key,name="DC-WGAN (MNIST)" if wasserstein else "Convolutional GAN (MNIST)",source_project="deeplearning-models-batch4",
                entry=gen,entry_points=[gen,dis],
                profile=dict(task="MNIST adversarial generation",mode="train caller forward paths",latent_dim=100,
                    noise_distribution="uniform",noise_range=[low,1.0],batch_size_setting=128,conditioning=False,
                    generator_channels=[64,32,16,8,1],generator_spatial=[7,13,25,27,28],generator_output_range=[-1,1],
                    discriminator_channels=dchannels,discriminator_spatial=dspatial,discriminator_conv_stages=depth,
                    discriminator_linear_input=dlinear,discriminator_sigmoid=False,discriminator_output="critic_score" if wasserstein else "binary_logit",
                    discriminator_receiver="global model.discriminator",discriminator_call_site_count=3,
                    discriminator_invocations_per_batch=11 if wasserstein else 3,discriminator_instance_count=1,
                    selected_entries=["GAN.generator_forward","GAN.discriminator_forward"],joint_forward_defined=False,
                    generator_objective_detached=False,discriminator_fake_detached=True,fake_reused_after_generator_step=True,
                    loss="mean(y_true*y_pred)" if wasserstein else "binary_cross_entropy_with_logits",
                    valid_target=-1 if wasserstein else 1,fake_target=1 if wasserstein else 0,
                    optimizer="RMSprop" if wasserstein else "Adam",learning_rate=0.00005 if wasserstein else 0.0001,
                    discriminator_iterations=5 if wasserstein else 1,weight_clipping=0.01 if wasserstein else None,
                    gradient_penalty=False,model_executed=False,symbolic_shapes=True),
                profile_label="MNIST / z100 Uniform[%g,1) / %d D stages / raw scores / training calls" % (low,depth),
                tree=tree,aux_inputs=[targets],extra_edges=edges,visual_roles=roles,fill_width=fill,facts=facts,corrections=corrections,
                symbols={source:["GAN","GAN.__init__","GAN.generator_forward","GAN.discriminator_forward",
                                 "Flatten","Flatten.forward","Reshape1","Reshape1.forward","__module__"] + (["wasserstein_loss"] if wasserstein else [])},
                config_files=[source],legend=[
                    "B: batch; z[B,100]; generated and real images[B,1,28,28]; every D score[B]",
                    "G output Tanh[-1,1]; D raw score; BN is in train mode; dropout lines are comments",
                    "Three D call sites / one shared parameter instance; detach only on D fake-objective path",
                    "Graph ranks show data dependence; no GAN.forward or joint tuple; losses/updates outside scope"])


def build():
    return _build("dcwgan",SOURCE,True)


def _validate(ir, key, wasserstein):
    nodes = {n['id']:n for n in ir['nodes']};edges=ir['edges'];p=ir['profile'];checks=[]
    def n(s):
        try:return nodes[key+"."+s]
        except KeyError:raise ValueError(key+": missing critical node "+s)
    def check(test,label):
        if not test:raise ValueError(key+": "+label)
        checks.append(label)
    def has(a,b,sp=None,dp=None,role=None):
        return any(e['src']==key+'.'+a and e['dst']==key+'.'+b and (sp is None or e['src_port']==sp) and
                   (dp is None or e['dst_port']==dp) and (role is None or e['role']==role) for e in edges)
    low=0.0 if wasserstein else -1.0;depth=3 if wasserstein else 2;linear=512 if wasserstein else 1568
    for suffix in ('root','noise','batch_targets','real_input','generator','generator.linear','generator.reshape','generator.tanh',
                   'g_score_path','fake_score_path','real_score_path','g_image_view','fake_image_view','real_image_view','detach',
                   'real_prepare','normalize','real_flatten','d_for_g','d_fake','d_real'):
        n(suffix)
    check(n('root').get('mode')=='graph' and n('root').get('joint_forward_defined') is False and p['joint_forward_defined'] is False,
          'caller DAG preserves two model entry points without invented joint forward')
    check(n('noise').get('origin')=='caller_uniform_random_source' and n('noise').get('distribution')=='uniform' and
          (n('noise').get('low'),n('noise').get('high'),n('noise').get('latent_dim'))==(low,1.0,100) and p['noise_range']==[low,1.0],
          'correct external uniform noise and latent width')
    check(has('batch_targets','noise','shape','batch_shape','shape_dependency') and n('batch_targets').get('value_used_for_conditioning') is False,
          'targets size-only dependency without class conditioning')
    check(n('generator.linear').get('parameter')=='generator.0' and n('generator.linear').get('bias') is False and
          n('generator.reshape').get('expression')=='input.view(input.size(0),64,7,7)',
          'real latent projection and Reshape1')
    for i,(cin,cout,side,kernel,stride,padding,index) in enumerate([
        (64,32,13,3,2,1,4),(32,16,25,3,2,1,7),(16,8,27,3,1,0,10),(8,1,28,2,1,0,13)],1):
        conv=n('generator.stage%d.conv'%i)
        check((conv.get('in_channels'),conv.get('out_channels'),conv.get('kernel_size'),conv.get('stride'),conv.get('padding'),conv.get('bias'))==
              (cin,cout,kernel,stride,padding,False) and conv.get('shape')=='[B,%d,%d,%d]'%(cout,side,side) and conv.get('parameter')=='generator.%d'%index,
              'generator stage%d exact geometry and independent parameter'%i)
        if i<4:
            check(n('generator.stage%d.bn'%i).get('mode')=='train' and n('generator.stage%d.activation'%i).get('negative_slope')==0.0001,
                  'generator stage%d real BatchNorm and activation'%i)
    check(n('generator.tanh').get('activation')=='tanh' and has('generator.stage4.conv','generator.tanh'),
          'final generator convolution directly followed by Tanh')
    channels=[1,8,16,32] if wasserstein else [1,8,32];spatial=[28,14,7,4] if wasserstein else [28,14,7]
    for call in ('d_for_g','d_fake','d_real'):
        check(n(call).get('instance_identity')=='model.discriminator' and n(call).get('parameter_scope')=='discriminator',
              call+' shares actual discriminator instance')
        for i in range(1,depth+1):
            conv=n(call+'.stage%d.conv'%i)
            check(conv.get('parameter')=='discriminator.%d'%((i-1)*3) and
                  (conv.get('in_channels'),conv.get('out_channels'),conv.get('kernel_size'),conv.get('stride'),conv.get('padding'),conv.get('bias'))==
                  (channels[i-1],channels[i],3,2,1,False) and conv.get('shape')=='[B,%d,%d,%d]'%(channels[i],spatial[i],spatial[i]),
                  call+' stage%d exact convolution identity'%i)
            check(n(call+'.stage%d.bn'%i).get('parameter')=='discriminator.%d'%((i-1)*3+1) and
                  n(call+'.stage%d.activation'%i).get('negative_slope')==0.0001,
                  call+' stage%d shared BatchNorm and actual slope'%i)
        check(n(call+'.linear').get('in_features')==linear and n(call+'.linear').get('parameter')=='discriminator.%d'%(depth*3+1) and
              n(call+'.return').get('receiver')=='model.discriminator' and n(call+'.return').get('expression')=='pred.view(-1)' and
              n(call+'.return').get('output_semantics')==('critic_score' if wasserstein else 'binary_logit'),
              call+' raw score width and actual global receiver')
    check(p['discriminator_conv_stages']==depth and p['discriminator_linear_input']==linear and p['discriminator_sigmoid'] is False and
          not any(n_.get('activation') in ('sigmoid','softmax') or 'sigmoid' in n_['id'] for n_ in nodes.values()),
          'correct discriminator depth without invented Sigmoid')
    check(p['discriminator_call_site_count']==3 and p['discriminator_invocations_per_batch']==(11 if wasserstein else 3) and
          p['discriminator_instance_count']==1,
          'three shared-instance call sites with exact per-batch invocation count')
    check(n('detach').get('gradient_to_generator') is False and n('detach').get('value_preserved') is True and
          n('detach').get('boundary')=='caller' and has('fake_image_view','detach') and has('detach','d_fake') and
          n('g_score_path').get('gradient_to_generator') is True and has('g_image_view','d_for_g') and
          has('generator.tanh','g_score_path') and has('generator.tanh','fake_score_path'),
          'shared fake values with caller detach only on discriminator objective')
    check(has('real_input','real_prepare') and has('real_flatten','real_score_path') and
          n('normalize').get('expression')=='(features - 0.5)*2.' and n('real_flatten').get('shape')=='[B,784]',
          'independent real image normalization and caller views')
    check(not any('dropout' in n_['id'].lower() for n_ in nodes.values()),'commented Dropout is not a source operator')
    check(p['valid_target']==(-1 if wasserstein else 1) and p['fake_target']==(1 if wasserstein else 0) and
          p['discriminator_iterations']==(5 if wasserstein else 1) and p['optimizer']==('RMSprop' if wasserstein else 'Adam') and
          p['weight_clipping']==(0.01 if wasserstein else None) and p['gradient_penalty'] is False,
          'correct caller objective settings without invented gradient penalty')
    return checks


def validate_ir(ir):
    return _validate(ir,"dcwgan",True)
