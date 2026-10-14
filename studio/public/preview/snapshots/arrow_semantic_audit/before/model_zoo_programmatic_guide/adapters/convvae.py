"""Reviewed convolutional MNIST VAE; shared helper also grounds the CCVAE variant."""
from spec import chain, op, parallel, ref

SOURCE = "deeplearning-models-batch3/pytorch_ipynb/autoencoder/ae-conv-var.py"


def _build(key, source, class_name, latent, conditional=False):
    p = key
    def nid(suffix): return p + "." + suffix
    def r(method): return ref(source, class_name + "." + method)
    init, enc, dec, sample, forward = [r(s) for s in ("__init__", "encoder", "decoder", "reparameterize", "forward")]
    roles, fill, extra = {}, [], []
    out_channels = 11 if conditional else 1

    def convolution(stage, i, cin, cout, side, kernel, stride, padding):
        name = nid("%s%d" % (stage, i))
        is_encoder = stage == "enc"
        parameter = "enc_conv_%d" % i if is_encoder else "dec_deconv_%d" % i
        scope = enc if is_encoder else dec
        label = "Conv2d" if is_encoder else "ConvTranspose2d"
        roles[name] = "conv"; fill.append(name)
        roles[name + ".conv"] = "conv"; roles[name + ".activation"] = "activation"
        return chain(name, "%s stage %d" % ("Encode" if is_encoder else "Decode", i), [
            op(name + ".conv", "%s %d -> %d" % (label, cin, cout), "conv", [init, scope],
               "[B,%d,%d,%d]" % (cout, side, side),
               ["kernel=%d; stride=%d; padding=%d; default bias=True" % (kernel, stride, padding)],
               parameter=parameter, kernel_size=kernel, stride=stride, padding=padding,
               convolution_type="Conv2d" if is_encoder else "ConvTranspose2d"),
            op(name + ".activation", "LeakyReLU 0.01", "activation", scope,
               "[B,%d,%d,%d]" % (cout, side, side),
               ["F.leaky_relu(x); slope from API default", "Also applied after the final decoder convolution"],
               negative_slope=0.01),
        ], [init, scope], "[B,%d,%d,%d]" % (cout, side, side),
            expand=3 if i == 2 else 2, parameter_scope=parameter)

    input_node = op(nid("input"), "MNIST grayscale image", "input", forward, "[B,1,28,28]",
                    ["Caller ToTensor scales pixels to [0,1]; input is not flattened"])
    encoder_items = []
    if conditional:
        helper = ref(source, "to_onehot")
        condition = chain(nid("encoder_condition"), "Encoder label maps", [
            op(nid("encoder_onehot"), "One-hot labels / 10 classes", "tensor", [helper, enc], "[B,10]",
               ["to_onehot: zeros + scatter_(1,targets.view(-1,1),1)", "Separate helper call in encoder"],
               input_ports=["labels"], input_relation=dict(role="external", producer=nid("labels"), src_port="out")),
            op(nid("condition_view"), "View one-hot as channels", "tensor", enc, "[B,10,1,1]"),
            op(nid("condition_maps"), "Ones times one-hot / broadcast H,W", "mixing", enc, "[B,10,28,28]",
               ["ones=ones(B,K,H,W,dtype=features.dtype).to(device)", "ones * onehot_targets; spatially constant label channels"],
               expression="torch.ones(B,K,H,W,dtype=features.dtype).to(device) * onehot_targets",
               shape_producer=nid("input")),
        ], [helper, enc], "[B,10,28,28]", expand=2, suppress_input_boundary=True,
            input_relation=dict(role="external", producer=nid("labels"), src_port="out"))
        encoder_args = parallel(nid("encoder_args"), "Image / condition operands", [
            op(nid("retain_image"), "Retain image values", "tensor", enc, "[B,1,28,28]"),
            condition,
        ], enc, "image + 10 label maps", expand=2,
            semantic_mode="operand_bundle", literal_tuple=False,
            child_inputs={nid("retain_image"):dict(role="value",producer=nid("input"),src_port="out"),
                          nid("encoder_condition"):dict(role="external",producer=nid("labels"),src_port="out")})
        encoder_items.extend([encoder_args,
            op(nid("encoder_concat"), "Concat image + label channels", "concat", enc, "[B,11,28,28]",
               ["torch.cat((features,ones),dim=1)", "Condition enters BEFORE enc_conv_1"], concat_dim=1,
               operands=[nid("input"),nid("condition_maps")])])
        extra.extend([
            dict(src=nid("labels"),dst=nid("encoder_onehot"),role="condition",label="targets / encoder",
                 src_port="out",dst_port="labels"),
            dict(src=nid("input"),dst=nid("condition_maps"),role="shape_dependency",label="image B,H,W + dtype",
                 src_port="shape",dst_port="image_shape"),
        ])
        roles.update({nid("encoder_args"):"inner",nid("encoder_condition"):"group",nid("encoder_concat"):"concat",
                      nid("encoder_onehot"):"tensor",nid("condition_view"):"tensor",nid("condition_maps"):"tensor",
                      nid("retain_image"):"tensor"})
    encoder_items.extend([
        convolution("enc",1,11 if conditional else 1,16,12,6,2,0),
        convolution("enc",2,16,32,5,4,2,0),
        convolution("enc",3,32,64,2,2,2,0),
    ])
    heads = []
    for suffix, symbol, label in [("mean","z_mean","Mean"),("logvar","z_log_var","Log-variance")]:
        h = nid(suffix + "_head")
        heads.append(chain(h, label + " head", [
            op(nid(suffix + "_view"), "View 64x2x2 -> 256", "tensor", enc, "[B,256]",
               ["A separate x.view(-1,64*2*2) expression appears for each head"]),
            op(nid("mu" if suffix == "mean" else "logvar"), "Linear 256 -> %d" % latent, "linear", [init,enc],
               "%s: [B,%d]" % ("mu" if suffix == "mean" else "logvar",latent),
               ["No activation after the posterior head"], parameter=symbol),
        ], [init,enc], "[B,%d]" % latent, expand=2, parameter_scope=symbol))
        roles[h] = "inner"; roles[nid(suffix + "_view")] = "tensor"
    posterior = parallel(nid("posterior"), "Independent posterior heads", heads, [init,enc],
        "mu + logvar results", ["Logical head-result group; no source tuple is created at this point"],
        expand=2, semantic_mode="operand_bundle", literal_tuple=False,
        child_inputs={h['id']:dict(role="value",producer=nid("enc3.activation"),src_port="out") for h in heads})
    scaled = chain(nid("scaled_noise"), "Scale Gaussian noise", [
        op(nid("half_logvar"), "Divide logvar by 2", "tensor", sample, "[B,%d]" % latent),
        op(nid("std"), "exp(logvar / 2)", "activation", sample, "std: [B,%d]" % latent,
           expression="torch.exp(z_log_var/2.)"),
        op(nid("noise_product"), "Multiply std times epsilon", "mixing", sample, "[B,%d]" % latent,
           ["Elementwise product; independent internal noise enters epsilon port"],
           expression="eps * torch.exp(z_log_var/2.)"),
    ], sample, "std * epsilon: [B,%d]" % latent, expand=2)
    sample_args = parallel(nid("sample_args"), "Mean / scaled-noise operands", [
        op(nid("retain_mu"), "Retain mu values", "tensor", sample, "[B,%d]" % latent), scaled,
    ], sample, "mu + noise operands", expand=2, semantic_mode="operand_bundle",literal_tuple=False,
        child_inputs={nid("retain_mu"):dict(role="value",producer=nid("mu"),src_port="out"),
                      nid("scaled_noise"):dict(role="value",producer=nid("logvar"),src_port="out")})
    sampling = chain(nid("sampling"), "Reparameterization / single latent", [sample_args,
        op(nid("z"), "Add mu + std * epsilon", "mixing", sample, "z: [B,%d]" % latent,
           expression="z_mu + eps * torch.exp(z_log_var/2.)")],
        sample, "z: [B,%d]" % latent, ["No training/eval conditional; sampling always runs"], expand=2,
        stochastic=True, training_gate=False, latent_levels=1)
    encoder_items.extend([posterior,sampling,
        op(nid("encoder_return"), "Return (mu, logvar, z)", "output", enc, "3 tensors [B,%d]" % latent,
           ["Actual encoder return tuple; no feature concatenation"],output_tuple=["mu","logvar","z"])])
    encoder = chain(nid("encoder"), "Conditional encoder" if conditional else "Convolutional encoder",
                    encoder_items,[init,enc],"(mu,logvar,z): [B,%d] x 3" % latent,expand=1)
    decoder_items = []
    if conditional:
        helper = ref(source,"to_onehot")
        decoder_args = parallel(nid("decoder_args"), "Latent / decoder-label operands", [
            op(nid("retain_z"), "Retain sampled z", "tensor", dec, "[B,50]"),
            op(nid("decoder_onehot"), "One-hot labels again", "tensor", [helper,dec], "[B,10]",
               ["Fresh to_onehot(targets,self.num_classes,device) call", "Not reuse of the spatial encoder maps"],
               input_ports=["labels"], input_relation=dict(role="external",producer=nid("labels"),src_port="out")),
        ], dec, "z + 10 label entries",expand=2,semantic_mode="operand_bundle",literal_tuple=False,
            child_inputs={nid("retain_z"):dict(role="value",producer=nid("select_z"),src_port="out"),
                          nid("decoder_onehot"):dict(role="external",producer=nid("labels"),src_port="out")})
        decoder_items.extend([decoder_args,
            op(nid("decoder_concat"), "Concat z + one-hot labels", "concat", dec,"[B,60]",
               ["torch.cat((encoded,onehot_targets),dim=1)","Condition enters BEFORE dec_linear_1"],concat_dim=1,
               operands=[nid("select_z"),nid("decoder_onehot")])])
        extra.append(dict(src=nid("labels"),dst=nid("decoder_onehot"),role="condition",label="targets / decoder",
                          src_port="out",dst_port="labels"))
        roles.update({nid("decoder_args"):"inner",nid("retain_z"):"tensor",nid("decoder_onehot"):"tensor",
                      nid("decoder_concat"):"concat"})
    decoder_items.extend([
        chain(nid("latent_projection"),"Latent projection + reshape",[
            op(nid("decoder_linear"),"Linear %d -> 256" % (latent+10 if conditional else latent),"linear",[init,dec],
               "[B,256]",parameter="dec_linear_1",in_features=latent+10 if conditional else latent,out_features=256),
            op(nid("decoder_view"),"View as 64x2x2 feature map","tensor",dec,"[B,64,2,2]",
               ["x.view(-1,64,2,2)"])], [init,dec],"[B,64,2,2]",expand=2),
        convolution("dec",1,64,32,4,2,2,0),
        convolution("dec",2,32,16,11,4,3,1),
        convolution("dec",3,16,out_channels,28,6,3,4),
        op(nid("sigmoid"),"Sigmoid decoded pixels","activation",dec,"[B,%d,28,28]" % out_channels,
           ["Follows final LeakyReLU, not the raw final convolution"],expression="torch.sigmoid(x)"),
    ])
    decoder = chain(nid("decoder"),"Conditional decoder" if conditional else "Convolutional decoder",decoder_items,
                    [init,dec],"decoded: [B,%d,28,28]" % out_channels,expand=1)
    model_forward = chain(nid("forward"),"Model forward",[
        encoder,
        op(nid("select_z"),"Select encoded z from tuple","tensor",forward,"[B,%d]" % latent,
           ["Decoder receives only encoded, plus targets in conditional variant"],input_selector="encoded"),
        decoder,
        op(nid("return"),"Return (mu, logvar, z, decoded)","output",forward,
           "[B,%d] x 3; [B,%d,28,28]" % (latent,out_channels),
           ["Actual four-field forward return; no image-only implicit output"],output_tuple=["mu","logvar","z","decoded"]),
    ],forward,"four-tensor tuple",expand=0)
    tree = chain(nid("root"),"Conditional ConvVAE / MNIST" if conditional else "ConvVAE / MNIST",[input_node,model_forward],
                 ref(source,class_name),"image + labels -> tuple" if conditional else "image -> tuple",expand=0)
    aux = [op(nid("epsilon"),"Internal Gaussian epsilon","sampling",sample,"[B,%d]" % latent,
              ["torch.randn(z_mu.size(0),z_mu.size(1)).to(device)","Created inside reparameterize in train and eval"],
              origin="internal_random_source",stochastic=True,learnable=False,
              shape_producer=nid("mu"),input_ports=["shape"])]
    if conditional:
        aux.append(op(nid("labels"),"External MNIST class labels","input",forward,"targets: [B]",
                      ["Integer digit labels 0...9; supplied to BOTH encoder and decoder"],origin="caller targets",learnable=False))
    extra.append(dict(src=nid("epsilon"),dst=nid("noise_product"),role="random_sample",label="epsilon",
                      src_port="out",dst_port="epsilon"))
    extra.append(dict(src=nid("mu"),dst=nid("epsilon"),role="shape_dependency",label="mu B,latent / shape only",
                      src_port="shape",dst_port="shape"))
    for item in ("mu","logvar"):
        for dst in ("encoder_return","return"):
            extra.append(dict(src=nid(item),dst=nid(dst),role="retained_value",label=item,src_port="out",dst_port=item))
    extra.append(dict(src=nid("z"),dst=nid("return"),role="retained_value",label="encoded z",src_port="out",dst_port="encoded"))
    roles.update({nid("root"):"root",nid("forward"):"group",nid("encoder"):"encoder",nid("decoder"):"decoder",
                  nid("input"):"input",nid("posterior"):"ffn",nid("mu"):"linear",nid("logvar"):"linear",
                  nid("sample_args"):"inner",nid("sampling"):"sampling",nid("scaled_noise"):"inner",
                  nid("retain_mu"):"tensor",nid("half_logvar"):"tensor",nid("std"):"activation",
                  nid("noise_product"):"norm",nid("z"):"norm",nid("encoder_return"):"output",
                  nid("select_z"):"tensor",nid("latent_projection"):"ffn",nid("decoder_linear"):"linear",
                  nid("decoder_view"):"tensor",nid("sigmoid"):"softmax",nid("return"):"output",
                  nid("epsilon"):"sampling",nid("labels"):"input"})
    fill.extend([nid(s) for s in ("forward","encoder","decoder","posterior","sampling","latent_projection")])
    facts = [
        "Encoder convolutions use kernels 6/4/2, strides 2/2/2, zero padding, and channels 16/32/64; 28->12->5->2 spatial sizes.",
        "Two independent Linear(256,latent) posterior heads each call x.view(-1,64*2*2); no intermediate hidden latent hierarchy exists.",
        "Internal epsilon is randn(B,latent).to(module global device); z=mu+epsilon*exp(logvar/2) with no train/eval gate.",
        "randn dimensions read z_mu.size(0/1); mu->epsilon is a shape dependency only, not a feature-value input.",
        "encoder returns (mu,logvar,encoded), and forward returns (mu,logvar,encoded,decoded); decoder receives selected z.",
        "Decoder Linear projects to 256 before reshape to 64x2x2; transposed convolutions use (k,s,p)=(2,2,0),(4,3,1),(6,3,4).",
        "Decoder spatial sizes are 2->4->11->28; LeakyReLU follows all three transposed convolutions, then Sigmoid.",
        "All six convolution calls use default bias=True; all six LeakyReLU calls use API default negative_slope=0.01; no BatchNorm or Dropout.",
        "num_features constructor argument is unused; source fixes posterior/decoder base map at 64x2x2.",
        "Losses, label-map reconstruction targets and standalone random decoder calls belong to notebook caller cells, outside forward.",
    ]
    corrections = [
        "No model-specific reference PNG is supplied; this graph follows the fixed notebook rather than a generic VAE illustration.",
        "Retain asymmetric decoder strides 2/3/3 and padding 0/1/4, rather than inventing a mirror of encoder stride 2.",
        "Draw one latent level and distinct mean/log-variance heads; logical operand bundles are not literal source tuples.",
        "Do not replace final LeakyReLU+Sigmoid by Sigmoid directly after convolution or by Softmax.",
        "Evaluation still samples epsilon; no deterministic z=mu path is present in this source.",
    ]
    if conditional:
        facts.extend([
            "Encoder one-hot labels broadcast to 10 constant spatial maps and concatenate with the image before Conv2d(11,16).",
            "Decoder calls to_onehot again and concatenates 50 latent entries with 10 label entries before Linear(60,256).",
            "Final decoder ConvTranspose2d outputs 11 hard-coded channels, not a one-channel image; training BCE reconstructs augmented image+label maps.",
            "Only visualization slices decoded[:,0]; forward returns all 11 channels, with no label inference or Softmax head.",
        ])
        corrections.extend([
            "Preserve encoder spatial condition injection and decoder latent-vector condition injection as two separate calls, not a single shared embedding.",
            "The returned decoded tensor has 11 channels; do not silently fix it to one image channel merely because the visualization selects channel zero.",
            "Changing num_classes changes encoder/Linear dimensions but does not change hard-coded decoder out_channels=11.",
        ])
    return dict(key=key,name="Conditional ConvVAE" if conditional else "Convolutional VAE",source_project="deeplearning-models-batch3",
        entry=forward,profile=dict(task="MNIST conditioned augmented reconstruction" if conditional else "MNIST reconstruction",
            mode="forward with stochastic sampling in train and eval",latent_dim=latent,latent_levels=1,
            num_classes=10 if conditional else None,input_shape=["B",1,28,28],encoder_input_channels=11 if conditional else 1,
            encoder_channels=[16,32,64],encoder_spatial=[28,12,5,2],decoder_channels=[64,32,16,out_channels],
            decoder_spatial=[2,4,11,28],decoder_convtranspose=[dict(kernel=2,stride=2,padding=0),dict(kernel=4,stride=3,padding=1),dict(kernel=6,stride=3,padding=4)],
            decoder_linear_input=latent+10 if conditional else latent,decoder_output_channels=out_channels,
            negative_slope=0.01,batch_size_setting=128,training_sampling_gate=False,num_features_argument_used=False,
            conditional=conditional,output_tuple=["mu","logvar","z","decoded"],symbolic_shapes=True,model_executed=False),
        profile_label="MNIST 28x28 / latent=%d / %s / stochastic forward" % (latent,"10 labels + 11-channel output" if conditional else "1 image channel"),
        tree=tree,aux_inputs=aux,extra_edges=extra,visual_roles=roles,fill_width=fill,facts=facts,corrections=corrections,
        symbols={source:[class_name,class_name+".__init__",class_name+".encoder",class_name+".decoder",class_name+".reparameterize",class_name+".forward"] + (["to_onehot"] if conditional else [])},
        config_files=[source],legend=["B batch; image [B,1,28,28]; one latent vector per example",
            "mu/logvar/z each [B,%d]; decoder output [B,%d,28,28]" % (latent,out_channels),
            "Internal Gaussian sampling always runs; no deterministic eval branch",
            "Logical operand bundles are not source tuples; actual tuple appears at returns",
            "Same glyph type is not shared parameters; middle Conv stages folded in detailed view"])


def build():
    return _build("convvae",SOURCE,"ConvVariationalAutoencoder",15)


def _validate(ir, key, latent, conditional):
    nodes={n['id']:n for n in ir['nodes']};edges=ir['edges']
    def node(s):
        try:return nodes[key+"."+s]
        except KeyError:raise ValueError(key+": missing critical node "+s)
    def require(test,message):
        if not test:raise ValueError(key+": "+message)
    def has(src,dst,port=None,role=None):
        return any(e['src']==key+'.'+src and e['dst']==key+'.'+dst and (port is None or e['dst_port']==port) and
                   (role is None or e['role']==role) for e in edges)
    for suffix in ('input','encoder','decoder','posterior','mean_view','logvar_view','sampling','sample_args',
                   'half_logvar','std','noise_product','epsilon','z','encoder_return','select_z','decoder_linear',
                   'decoder_view','sigmoid','return'):
        node(suffix)
    require(ir['profile']['latent_dim']==latent and ir['profile']['latent_levels']==1,"wrong latent profile")
    require(node('mu').get('parameter')=='z_mean' and node('logvar').get('parameter')=='z_log_var',"posterior heads need distinct real parameters")
    for head in ('mean_head','logvar_head'):
        require(has('enc3.activation',head),'posterior head input must be final encoder feature map')
    require(node('posterior').get('semantic_mode')=='operand_bundle' and node('posterior').get('literal_tuple') is False,"posterior is logical argument group, not source tuple")
    require(node('sample_args').get('semantic_mode')=='operand_bundle' and node('sample_args')['child_inputs'][key+'.retain_mu']['producer']==key+'.mu' and
            node('sample_args')['child_inputs'][key+'.scaled_noise']['producer']==key+'.logvar',"sampling operand producers incorrect")
    require(node('epsilon').get('origin')=='internal_random_source' and has('epsilon','noise_product','epsilon'),"sampling epsilon must be internal independent operand")
    epsilon_inputs=[e for e in edges if e['dst']==key+'.epsilon']
    require(len(epsilon_inputs)==1 and has('mu','epsilon','shape','shape_dependency') and epsilon_inputs[0]['src_port']=='shape',
            "internal epsilon uses mu shape only, never caller feature values")
    require(node('std').get('expression')=='torch.exp(z_log_var/2.)' and node('z').get('expression')=='z_mu + eps * torch.exp(z_log_var/2.)',"reparameterization formula incorrect")
    require(node('sampling').get('training_gate') is False and node('sampling').get('latent_levels')==1,"invented deterministic eval path or multi-level latent")
    require(node('encoder_return').get('output_tuple')==['mu','logvar','z'] and node('return').get('output_tuple')==['mu','logvar','z','decoded'],"actual return fields lost")
    for value in ('mu','logvar'):
        for target in ('encoder_return','return'):require(has(value,target,value),"retained posterior field missing")
    require(has('z','return','encoded') and node('select_z').get('input_selector')=='encoded',"latent selection/retention missing")
    for i,(kernel,side) in enumerate([(6,12),(4,5),(2,2)],1):
        n=node('enc%d.conv'%i)
        require((n.get('kernel_size'),n.get('stride'),n.get('padding'),n.get('convolution_type'))==(kernel,2,0,'Conv2d'),"encoder convolution geometry changed")
        channels=(16,32,64)[i-1]
        require(n.get('shape')=='[B,%d,%d,%d]'%(channels,side,side) and
                node('enc%d.activation'%i).get('negative_slope')==0.01,"encoder output/LeakyReLU wrong")
    for i,(kernel,stride,padding) in enumerate([(2,2,0),(4,3,1),(6,3,4)],1):
        n=node('dec%d.conv'%i)
        require((n.get('kernel_size'),n.get('stride'),n.get('padding'),n.get('convolution_type'))==(kernel,stride,padding,'ConvTranspose2d'),"decoder convolution geometry changed")
        require(node('dec%d.activation'%i).get('negative_slope')==0.01,"decoder LeakyReLU missing/wrong")
    require(node('sigmoid').get('expression')=='torch.sigmoid(x)' and has('dec3','sigmoid'),"Sigmoid must follow final activated stage")
    labels=['independent posterior parameters','internal stochastic single latent','random source reads mu shape only','exact reparameterization formula','retained tuple fields',
            'asymmetric ConvTranspose geometry and final activation']
    if conditional:
        require(node('encoder_concat').get('operands')==[key+'.input',key+'.condition_maps'] and node('encoder_concat').get('shape')=='[B,11,28,28]',"wrong spatial condition injection")
        require(has('labels','encoder_onehot','labels') and has('labels','decoder_onehot','labels'),"both condition calls must read caller labels")
        require(has('input','condition_maps','image_shape'),"condition broadcasting must use image shape")
        require(node('decoder_concat').get('operands')==[key+'.select_z',key+'.decoder_onehot'] and node('decoder_concat').get('shape')=='[B,60]',"wrong latent condition injection")
        require(node('decoder_linear').get('in_features')==60 and node('dec3.conv').get('shape')=='[B,11,28,28]' and ir['profile']['decoder_output_channels']==11,"source returns 11 augmented channels")
        for target in ('encoder_onehot','decoder_onehot'):
            incoming=[e for e in edges if e['dst']==key+'.'+target]
            require(len(incoming)==1 and incoming[0]['src']==key+'.labels',"one-hot must only consume external targets")
        labels+=['encoder spatial-label concatenation','decoder latent-label concatenation','11-channel augmented return']
    else:
        require(node('decoder_linear').get('in_features')==15 and node('dec3.conv').get('shape')=='[B,1,28,28]',"unconditional output geometry wrong")
        require(not any(n['id'].endswith('.labels') or 'condition' in n['id'] for n in nodes.values()),"unconditional graph has invented labels")
    return labels


def validate_ir(ir):
    return _validate(ir,"convvae",15,False)
