"""Source-reviewed local module profiles. Nothing imports or executes upstream code."""
CASES={}
G='glow-modules/model.py';D='density-flow-modules/flows.py';B='biggan-modules/layers.py'

def N(id,label,kind='tensor',shape='',**kw):return dict(id=id,label=label,kind=kind,shape=shape,**kw)
def S(id,label,ops,shape='',role='attention',**kw):return dict(id=id,label=label,ops=ops,shape=shape,role=role,**kw)
def add(key,name,family,source,entry,symbols,inputs,outputs,stages,ranks,edges,contracts,profile,scope,facts,corrections):
 CASES[key]=dict(name=name,family=family,source=source,entry=entry,symbols=symbols,inputs=inputs,outputs=outputs,
 stages=stages,ranks=ranks,edges=edges,contracts=contracts,profile=profile,scope=scope,facts=facts,corrections=corrections,
 body=name.split(' / ')[0]+' module',profile_label=profile.get('label','static module / explicit profile'),output_shape=outputs[0].get('shape',''))

add('glow_actnorm','Glow ActNorm / data-initialized affine','可逆归一化',G,'ActNorm.forward',
 ['ActNorm.__init__','ActNorm.initialize','ActNorm.forward','ActNorm.reverse'],
 [N('x','Input x',shape='[B,8,8,8]'),N('state','loc / scale + init flag',shape='[1,8,1,1]',symbols=['ActNorm.__init__'],parameters=['loc','scale'],buffers=['initialized'])],
 [N('y','Affine output y',shape='[B,8,8,8]'),N('ld','logdet / scalar',shape='scalar')],
 [S('init','One-time initialization',[
 N('guard','If initialized == 0','control',condition='initialized.item()==0'),
 N('stats','Channel mean / std','statistics','[1,8,1,1]',symbols=['ActNorm.initialize'],axes=[0,2,3],std_correction='torch.std default; version boundary'),
 N('copy','Copy loc=-mean; scale=1/(std+eps)','control',symbols=['ActNorm.initialize','ActNorm.forward'],epsilon=1e-6,updates=['loc.data','scale.data','initialized=1'],once_only=True)],role='control'),
 S('affine','Broadcast affine',[N('shift','x + loc','add','[B,8,8,8]',expression='input + self.loc'),N('scale','scale * shifted x','multiply','[B,8,8,8]',expression='self.scale * (input + self.loc)',parameters=['scale','loc'])]),
 S('det','Log-volume contribution',[N('abslog','log(abs(scale))','tensor','[1,8,1,1]',expression='logabs(self.scale)'),N('sum','H*W * sum log(abs(scale))','density','scalar',spatial_factor=64,expression='height * width * torch.sum(log_abs)')],role='norm')],
 [['init'],['affine','det']],
 [('x','init'),('state','init',{'role':'state'}),('init','affine',{'role':'state'}),('x','affine'),('init','det',{'role':'state'}),('affine','y'),('det','ld')],
 [('ActNorm.forward','self.scale * (input + self.loc)'),('ActNorm.forward','height * width * torch.sum(log_abs)'),('ActNorm.initialize','1 / (std + 1e-6)')],
 dict(channels=8,input_shape=['B',8,8,8],logdet=True,initialization='one-time data-dependent',parameters=['loc','scale'],buffers=['initialized'],logdet_shape='scalar'),
 'Only ActNorm with logdet=True; reverse is documented, not drawn as forward.',
 ['loc and scale are learned Parameters, initialized from the first input under no_grad; initialized is a uint8 buffer.',
  'Returned logdet is one scalar shared across batch, not a per-example vector. The data stream and determinant are separate outputs.',
  'Reverse is output/scale-loc. Source torch.std default is left version-dependent.'],
 ['Do not draw logscale as the stored parameter: this implementation stores scale directly.','No batch-statistics recomputation after initialized becomes 1.'])

for lu in [False,True]:
 key='glow_invconv_lu' if lu else 'glow_invconv';cls='InvConv2dLU' if lu else 'InvConv2d'
 params=['w_l','w_s','w_u'] if lu else ['weight'];buffers=['w_p','u_mask','l_mask','s_sign','l_eye'] if lu else []
 weight_ops=([N('lower','L = w_l*mask + I','multiply','[8,8]',symbols=[cls+'.calc_weight'],parameters=['w_l'],buffers=['l_mask','l_eye']),
 N('upper','U + diag(sign*exp(w_s))','tensor','[8,8]',symbols=[cls+'.calc_weight'],parameters=['w_u','w_s'],buffers=['u_mask','s_sign']),
 N('reconstruct','P @ L @ U; unsqueeze','matmul','[8,8,1,1]',symbols=[cls+'.calc_weight'],expression='self.w_p @ (self.w_l * self.l_mask + self.l_eye) @ (self.w_u * self.u_mask + torch.diag(self.s_sign * torch.exp(self.w_s)))')]
 if lu else [N('weight_read','Read QR-initialized Parameter W','tensor','[8,8,1,1]',symbols=[cls+'.__init__'],parameters=['weight'],initialization='QR only at construction')])
 # L and U above are independent terms, not a sequential tensor chain: use one reconstruction stage glyph with separate identities.
 if lu:weight_ops=[N('factors','Read L/U/logdiag + fixed buffers','tensor','[8,8]',symbols=[cls+'.__init__'],parameters=params,buffers=buffers),
 N('reconstruct','P @ L @ U; unsqueeze','matmul','[8,8,1,1]',symbols=[cls+'.calc_weight'],expression='self.w_p @ (self.w_l * self.l_mask + self.l_eye) @ (self.w_u * self.u_mask + torch.diag(self.s_sign * torch.exp(self.w_s)))',lower='w_l*l_mask+l_eye',upper='w_u*u_mask+diag(s_sign*exp(w_s))')]
 detexp='height * width * torch.sum(self.w_s)' if lu else 'height * width * torch.slogdet(self.weight.squeeze().double())[1].float()'
 add(key,('LU' if lu else 'Direct')+' invertible 1x1 convolution','可逆通道混合',G,cls+'.forward',
 [cls+'.__init__',cls+'.forward',cls+'.reverse']+([cls+'.calc_weight'] if lu else []),
 [N('x','Input x',shape='[B,8,8,8]'),N('p','Weight state',shape='C=8',symbols=[cls+'.__init__'],parameters=params,buffers=buffers)],
 [N('y','Convolved y',shape='[B,8,8,8]'),N('ld','Log determinant',shape='scalar')],
 [S('weight','Weight materialization',weight_ops,role='ffn'),
 S('conv','Channel mixing',[N('convop','F.conv2d / 1x1','conv2d','[B,8,8,8]',kernel_size=[1,1],bias=False,expression='F.conv2d(input, weight)' if lu else 'F.conv2d(input, self.weight)')]),
 S('det','Determinant branch',[N('detop','H*W * sum(logdiag)' if lu else 'H*W * slogdet(W)','density','scalar',expression=detexp,spatial_factor=64)],role='norm')],
 [['weight'],['conv','det']],[('p','weight'),('weight','conv',{'role':'weight'}),('x','conv'),('p' if lu else 'weight','det',{'role':'weight'}),('conv','y'),('det','ld')],
 [(cls+'.forward',detexp),(cls+'.forward','F.conv2d(input, weight)' if lu else 'F.conv2d(input, self.weight)')],
 dict(channels=8,parameters=params,buffers=buffers,lu=lu,kernel_size=[1,1],logdet_shape='scalar'),
 cls+' only; initialization is state provenance, not a repeated forward QR/LU.',
 ['The 1x1 weight is square and mixes channels at each pixel; determinant scales by H*W.',
 'LU source learns strict-triangular factors and log absolute diagonal; permutation, masks, signs and identity are buffers.' if lu else 'The learned weight is initialized with QR once. Forward uses slogdet in float64 then casts the logabsdet to float32.',
 'Reverse uses an explicit matrix inverse, outside the selected forward view.'],
 ['No attention, spatial kernel3 or extra bias is present.','Do not count fixed LU buffers as learned parameters.'])

add('zero_conv','ZeroConv2d / zero-initialized conditioner','特殊卷积初始化',G,'ZeroConv2d.forward',
 ['ZeroConv2d.__init__','ZeroConv2d.forward'],[N('x','Input features',shape='[B,16,8,8]')],[N('y','Conditioner output',shape='[B,8,8,8]')],
 [S('pad','Explicit boundary padding',[N('padop','F.pad / constant value 1','tensor','[B,16,10,10]',expression='F.pad(input, [1, 1, 1, 1], value=1)',padding=[1,1,1,1],padding_value=1)]),
 S('conv','Zero-initialized Conv3x3',[N('convop','Conv 16 -> 8; padding0','conv2d','[B,8,8,8]',symbols=['ZeroConv2d.__init__','ZeroConv2d.forward'],parameters=['conv.weight','conv.bias'],kernel_size=3,padding=0,weight_init='zero',bias_init='zero')],role='ffn'),
 S('scale','Learned output scaling',[N('scaleop','out * exp(scale * 3)','multiply','[B,8,8,8]',expression='out * torch.exp(self.scale * 3)',parameters=['scale'],initial_scale=0)])],
 [['pad'],['conv'],['scale']],[('x','pad'),('pad','conv'),('conv','scale'),('scale','y')],
 [('ZeroConv2d.forward','F.pad(input, [1, 1, 1, 1], value=1)'),('ZeroConv2d.forward','out * torch.exp(self.scale * 3)')],
 dict(in_channels=16,out_channels=8,padding_value=1,conv_padding=0,parameters=['conv.weight','conv.bias','scale'],initial_output='zero before learning'),
 'ZeroConv2d only; no surrounding Glow model or coupling input split.',
 ['The argument named padding in the constructor is unused; actual forward pads all four sides with value 1.',
 'Conv weight and bias start at zero but remain learnable; exp(scale*3) starts at 1.'],
 ['Do not substitute standard zero padding or permanently frozen convolution.'])

for affine in [True,False]:
 key='glow_affine_coupling' if affine else 'glow_additive_coupling'
 stages=[S('split','Channel split',[N('splitop','chunk(2, dim=1)','tensor','a,b: [B,4,8,8]',expression='input.chunk(2, 1)',split_dim=1)]),
 S('net','Conditioner / a only',[
 N('conv1','Conv3x3 4 -> 16','conv2d','[B,16,8,8]',symbols=['AffineCoupling.__init__'],parameters=['net.0.weight','net.0.bias'],kernel=3,padding=1),
 N('relu1','ReLU inplace','activation','[B,16,8,8]',symbols=['AffineCoupling.__init__'],inplace=True),
 N('conv2','Conv1x1 16 -> 16','conv2d','[B,16,8,8]',symbols=['AffineCoupling.__init__'],parameters=['net.2.weight','net.2.bias'],kernel=1),
 N('relu2','ReLU inplace','activation','[B,16,8,8]',symbols=['AffineCoupling.__init__'],inplace=True),
 N('zero','ZeroConv2d 16 -> '+str(8 if affine else 4),'conv2d','[B,'+str(8 if affine else 4)+',8,8]',symbols=['ZeroConv2d.__init__','ZeroConv2d.forward','AffineCoupling.__init__'],module_identity='net.4',padding_value=1,opaque_local_expansion='see zero_conv case')],role='ffn')]
 if affine:
  stages += [S('heads','Split scale / translation',[N('headsop','chunk -> log_s, t','tensor','each [B,4,8,8]',expression='self.net(in_a).chunk(2, 1)',head_order=['log_s','t'])]),
  S('scale','Positive scale',[N('scaleop','sigmoid(log_s + 2)','sigmoid','[B,4,8,8]',expression='F.sigmoid(log_s + 2)',scale_function='sigmoid',offset=2)]),
  S('shift','Shift b',[N('shiftop','in_b + t','add','[B,4,8,8]',expression='in_b + t')]),
  S('transform','Scale shifted b',[N('mulop','(in_b + t) * s','multiply','[B,4,8,8]',expression='(in_b + t) * s',affine_order='shift_then_scale')]),
  S('det','Per-example logdet',[N('detop','sum log(s) / C,H,W','density','[B]',expression='torch.sum(torch.log(s).view(input.shape[0], -1), 1)',reduce_axes=['C/2','H','W'])],role='norm')]
  ranks=[['split'],['net'],['heads'],['shift','scale'],['transform','det'],['join']]
  edges=[('x','split'),('split','net',{'src_port':'a'}),('net','heads'),('heads','shift',{'src_port':'t'}),('heads','scale',{'src_port':'log_s'}),('split','shift',{'src_port':'b'}),('shift','transform'),('scale','transform',{'dst_port':'scale'}),('scale','det'),('transform','join',{'dst_port':'out_b'}),('split','join',{'src_port':'a','dst_port':'in_a','role':'retained_value'}),('join','y'),('det','ld')]
  contracts=[('AffineCoupling.forward','(in_b + t) * s'),('AffineCoupling.forward','F.sigmoid(log_s + 2)')]
 else:
  stages += [S('transform','Additive update',[N('addop','in_b + net_out','add','[B,4,8,8]',expression='in_b + net_out')]),S('det','No scale determinant',[N('none','logdet = None','control','None',literal=None)],role='control')]
  ranks=[['split'],['net'],['transform','det'],['join']]
  edges=[('x','split'),('split','net',{'src_port':'a'}),('net','transform'),('split','transform',{'src_port':'b'}),('transform','join',{'dst_port':'out_b'}),('split','join',{'src_port':'a','dst_port':'in_a','role':'retained_value'}),('join','y'),('det','ld')]
  contracts=[('AffineCoupling.forward','in_b + net_out')]
 stages.append(S('join','Retain a + transformed b',[N('catop','cat([in_a,out_b],dim=1)','concat','[B,8,8,8]',expression='torch.cat([in_a, out_b], 1)',operand_order=['in_a','out_b'],dim=1)]))
 add(key,'Glow '+('affine' if affine else 'additive')+' coupling','可逆耦合',G,'AffineCoupling.forward',
 ['AffineCoupling.__init__','AffineCoupling.forward','AffineCoupling.reverse','ZeroConv2d.__init__','ZeroConv2d.forward'],
 [N('x','Input x',shape='[B,8,8,8]')],[N('y','Retained / updated channels',shape='[B,8,8,8]'),N('ld','logdet' if affine else 'logdet=None',shape='[B]' if affine else 'None')],
 stages,ranks,edges,contracts,dict(affine=affine,channels=8,filter_size=16,split_dim=1,head_order=['log_s','t'] if affine else ['net_out'],logdet_type='per_batch' if affine else 'None'),
 'One AffineCoupling with affine='+str(affine)+'; forward only, independent reviewed branch profile.',
 ['Conditioner consumes only a; b is retained through a separate update path. The two channel halves are rejoined in original order.',
 'Affine branch uses sigmoid(log_s+2) and (b+t)*s; it does not use exp(log_s).' if affine else 'Additive branch returns None as logdet, rather than constructing a numeric zero tensor.',
 'ZeroConv2d remains a source-defined call boundary; its expanded module is available separately.'],
 ['Do not exchange shift/scale order or feed b into the conditioner.','This is one coupling block, not the Glow architecture.'])

add('glow_squeeze','Squeeze / space-to-channel','张量重排',G,'Block.forward',['Block.forward'],
 [N('x','Input x',shape='[B,2,8,8]')],[N('y','Squeezed features',shape='[B,8,4,4]')],
 [S('factor','Factor spatial offsets',[N('view1','view B,C,H/2,2,W/2,2','tensor','[B,2,4,2,4,2]',expression='input.view(b_size, n_channel, height // 2, 2, width // 2, 2)')]),
 S('permute','Move 2x2 offsets to channels',[N('perm','permute(0,1,3,5,2,4)','tensor','[B,2,2,2,4,4]',axes=[0,1,3,5,2,4],expression='squeezed.permute(0, 1, 3, 5, 2, 4)')]),
 S('merge','Materialize and merge',[N('contig','contiguous()','tensor','[B,2,2,2,4,4]'),N('view2','view B,4C,H/2,W/2','tensor','[B,8,4,4]',expression='squeezed.contiguous().view(b_size, n_channel * 4, height // 2, width // 2)')])],
 [['factor'],['permute'],['merge']],[('x','factor'),('factor','permute'),('permute','merge'),('merge','y')],
 [('Block.forward','squeezed.permute(0, 1, 3, 5, 2, 4)'),('Block.forward','squeezed.contiguous().view(b_size, n_channel * 4, height // 2, width // 2)')],
 dict(input_shape=['B',2,8,8],output_shape=['B',8,4,4],factor=2,parameters=[],require_even_spatial=True),
 'Only the first three squeeze assignments in Block.forward; flow loop and prior are excluded.',
 ['This is a parameter-free bijective rearrangement of 2x2 offsets into channels.', 'H and W must be even for this selected profile. It is the space-to-channel direction, opposite to PixelShuffle.'],
 ['Do not add pooling, learned convolution or drop spatial entries.'])

add('glow_split_prior','Split prior / conditional Gaussian density','条件密度头',G,'Block.forward',
 ['Block.__init__','Block.forward','ZeroConv2d.__init__','ZeroConv2d.forward','gaussian_log_p'],
 [N('x','Features after omitted flows',shape='[B,8,4,4]')],
 [N('keep','Retained out',shape='[B,4,4,4]'),N('z','Split latent z_new',shape='[B,4,4,4]'),N('lp','Conditional log_p',shape='[B]')],
 [S('split','Split channel halves',[N('splitop','out.chunk(2,dim=1)','tensor','two [B,4,4,4]',expression='out.chunk(2, 1)',operand_order=['out','z_new'])]),
 S('prior','Prior on retained half',[N('priorop','ZeroConv2d prior 4 -> 8','conv2d','[B,8,4,4]',symbols=['Block.__init__','Block.forward','ZeroConv2d.forward'],module_identity='prior',input_operand='out',padding_value=1)]),
 S('heads','Mean / log standard deviation',[N('headsop','chunk -> mean, log_sd','tensor','each [B,4,4,4]',expression='self.prior(out).chunk(2, 1)',head_order=['mean','log_sd'])]),
 S('density','Elementwise Gaussian log_p',[N('gauss','gaussian_log_p(z_new,mean,log_sd)','density','[B,4,4,4]',symbols=['Block.forward','gaussian_log_p'],expression='-0.5 * log(2 * pi) - log_sd - 0.5 * (x - mean) ** 2 / torch.exp(2 * log_sd)',scale_parameterization='log_standard_deviation')]),
 S('reduce','Per-example sum',[N('sum','view(B,-1).sum(1)','density','[B]',expression='log_p.view(b_size, -1).sum(1)',reduce_axes=['C','H','W'])])],
 [['split'],['prior'],['heads'],['density'],['reduce']],
 [('x','split'),('split','prior',{'src_port':'out'}),('split','keep',{'src_port':'out','role':'retained_value'}),('split','z',{'src_port':'z_new','role':'retained_value'}),('prior','heads'),('heads','density',{'src_port':'mean_log_sd','dst_port':'parameters'}),('split','density',{'src_port':'z_new','dst_port':'sample'}),('density','reduce'),('reduce','lp')],
 [('Block.forward','self.prior(out).chunk(2, 1)'),('gaussian_log_p','-0.5 * log(2 * pi) - log_sd - 0.5 * (x - mean) ** 2 / torch.exp(2 * log_sd)')],
 dict(split=True,input_channels_after_squeeze=8,retained_channels=4,prior_channels=8,head_order=['mean','log_sd'],sampling=False,logdet_excluded=True),
 'Only split=True prior subgraph after the omitted Flow loop; excludes squeeze, flow logdet and reverse sampling.',
 ['Prior sees retained out, whereas density is evaluated on z_new; these operands cannot be interchanged.',
 'log_sd denotes log standard deviation; density denominator is exp(2*log_sd), not exp(log_sd).',
 'The three outputs are independent values; there is no z-to-retained tensor chain.'],
 ['Do not call this a whole Glow block or add a reparameterization sample to forward.'])

add('masked_linear','MaskedLinear / conditional projection','掩码投影',D,'MaskedLinear.forward',
 ['MaskedLinear.__init__','MaskedLinear.forward','get_mask'],
 [N('x','Main input x',shape='[B,4]'),N('cond','Condition vector c',shape='[B,3]'),N('mask','Registered degree mask',shape='[8,4]',symbols=['MaskedLinear.__init__','get_mask'],storage_kind='buffer')],
 [N('y','Combined projection',shape='[B,8]')],
 [S('masked','Main masked affine',[N('w_mask','W * mask','multiply','[8,4]',expression='self.linear.weight * self.mask',parameters=['linear.weight'],storage_kind='mask buffer'),N('linear','F.linear(x,W*mask,b)','masked_linear','[B,8]',expression='F.linear(inputs, self.linear.weight * self.mask, self.linear.bias)',parameters=['linear.weight','linear.bias'],bias=True)],role='ffn'),
 S('conditional','Independent condition affine',[N('condlinear','Linear 3 -> 8 / bias=False','linear','[B,8]',symbols=['MaskedLinear.__init__','MaskedLinear.forward'],parameters=['cond_linear.weight'],bias=False,expression='self.cond_linear(cond_inputs)')],role='ffn'),
 S('sum','Add condition projection',[N('add','output += cond_linear(c)','add','[B,8]',expression='self.cond_linear(cond_inputs)',operation='inplace_add')])],
 [['masked','conditional'],['sum']],
 [('x','masked'),('mask','masked',{'role':'weight_mask'}),('cond','conditional'),('masked','sum'),('conditional','sum',{'dst_port':'condition'}),('sum','y')],
 [('MaskedLinear.forward','F.linear(inputs, self.linear.weight * self.mask, self.linear.bias)'),('MaskedLinear.__init__','nn.Linear(cond_in_features, out_features, bias=False)')],
 dict(in_features=4,out_features=8,cond_in_features=3,mask_storage='buffer',main_bias=True,conditional_bias=False),
 'One conditional MaskedLinear; get_mask supplies construction provenance, not a learned attention mask.',
 ['Main and condition projections have distinct weights; only the main weight is masked.',
 'Source constructor accepts bias but does not pass it to the main Linear, which retains its default bias.',
 'get_mask compares output and input degrees; a strict autoregressive output mask requires the output degree offset.'],
 ['No Softmax, dropout or trainable mask is present.','Do not apply the same mask to the conditional projection.'])

for split in [False,True]:
 key='made_split' if split else 'made_affine';cls='MADESplit' if split else 'MADE'
 def trunk(id,label,activation,out,identity):
  return S(id,label,[N(id+'join','MaskedLinear 4 -> 8','masked_linear','[B,8]',symbols=[cls+'.__init__','MaskedLinear.forward'],parameters=[identity+'joiner.linear.weight',identity+'joiner.linear.bias'],mask='input'),
   N(id+'act1',activation,'tanh' if activation=='Tanh' else 'activation','[B,8]',symbols=[cls+'.__init__']),
   N(id+'hidden','MaskedLinear 8 -> 8','masked_linear','[B,8]',symbols=[cls+'.__init__','MaskedLinear.forward'],parameters=[identity+'trunk.1.linear.weight',identity+'trunk.1.linear.bias'],mask='hidden'),
   N(id+'act2',activation,'tanh' if activation=='Tanh' else 'activation','[B,8]',symbols=[cls+'.__init__']),
   N(id+'out','MaskedLinear 8 -> '+str(out),'masked_linear','[B,'+str(out)+']',symbols=[cls+'.__init__','MaskedLinear.forward'],parameters=[identity+'trunk.3.linear.weight',identity+'trunk.3.linear.bias'],mask='output')],role='ffn')
 if split:
  stages=[trunk('mnet','s_* network -> m','Tanh',4,'s_'),trunk('anet','t_* network -> a','ReLU',4,'t_')]
  edges=[('x','mnet'),('x','anet'),('mnet','shift',{'dst_port':'m'}),('anet','scale'),('anet','det')]
  ranks=[['mnet','anet'],['shift','scale','det'],['affine']]
 else:
  stages=[trunk('net','Shared masked network','ReLU',8,''),S('heads','Split m and a',[N('chunk','chunk(2,dim=1)','tensor','each [B,4]',expression='self.trunk(h).chunk(2, 1)',head_order=['m','a'])])]
  edges=[('x','net'),('net','heads'),('heads','shift',{'src_port':'m','dst_port':'m'}),('heads','scale',{'src_port':'a'}),('heads','det',{'src_port':'a'})]
  ranks=[['net'],['heads'],['shift','scale','det'],['affine']]
 stages += [S('shift','Subtract conditional mean',[N('sub','inputs - m','subtract','[B,4]',expression='inputs - m')]),
 S('scale','Inverse scale',[N('exp','exp(-a)','tensor','[B,4]',expression='torch.exp(-a)')]),
 S('affine','Affine output',[N('mul','(inputs-m) * exp(-a)','multiply','[B,4]',expression='(inputs - m) * torch.exp(-a)')]),
 S('det','Log determinant',[N('sum','-a.sum(-1,keepdim=True)','density','[B,1]',expression='-a.sum(-1, keepdim=True)',dim=-1,keepdim=True)],role='norm')]
 edges += [('x','shift',{'role':'retained_value'}),('shift','affine'),('scale','affine',{'dst_port':'scale'}),('affine','u'),('det','ld')]
 add(key,cls+' / autoregressive affine','自回归流',D,cls+'.forward',
 [cls+'.__init__',cls+'.forward','MaskedLinear.__init__','MaskedLinear.forward','get_mask'],
 [N('x','Input x',shape='[B,4]')],[N('u','Transformed u',shape='[B,4]'),N('ld','Logdet per example',shape='[B,1]')],
 stages,ranks,edges,[(cls+'.forward','(inputs - m) * torch.exp(-a)'),(cls+'.forward','-a.sum(-1, keepdim=True)')],
 dict(num_inputs=4,num_hidden=8,num_cond_inputs=None,mode='direct',pre_exp_tanh=False,independent_networks=split,head_order=['m','a'],inverse='sequential coordinate loop; same parameters'),
 cls+' forward direct branch only; inverse loop is documented rather than falsely parallelized.',
 ['Degree masks enforce strict autoregressive dependence through the output degree offset; masks are registered buffers.',
 'MADESplit uses independent s_* and t_* networks. Despite their names, s_* predicts m with Tanh and t_* predicts a with ReLU.' if split else 'MADE shares a masked trunk and chunks its 2D output into m then a; pre_exp_tanh is accepted but unused by this class.',
 'Inverse builds coordinates one at a time with the same learned networks; the direct view is a DAG, not that inverse execution.',
 'The returned logdet follows the exact source expression. It is not a third sequential layer applied to u.'],
 ['Do not swap m/a, use dense unmasked hidden layers, or claim pre_exp_tanh acts in MADE.'])

add('flow_batchnorm','BatchNormFlow / affine + logdet','可逆归一化',D,'BatchNormFlow.forward',
 ['BatchNormFlow.__init__','BatchNormFlow.forward'],
 [N('x','Batch input x',shape='[B,4]')],[N('y','Normalized affine y',shape='[B,4]'),N('ld','Logdet / length-one tensor',shape='[1]')],
 [S('stats','Training statistics',[N('mean','mean over batch','statistics','[4]',expression='inputs.mean(0)',axes=[0]),N('var','mean((x-mean)^2) + eps','statistics','[4]',expression='(inputs - self.batch_mean).pow(2).mean(0) + self.eps',epsilon=1e-5,biased=True)],role='norm'),
 S('running','Update persistent statistics',[N('ema','old*m + batch*(1-m)','control','[4]',symbols=['BatchNormFlow.__init__','BatchNormFlow.forward'],buffers=['running_mean','running_var'],momentum=0.0,old_weight=0.0,new_weight=1.0)],role='control'),
 S('normalize','Standardize current batch',[N('norm','(inputs-mean) / sqrt(var)','norm','[B,4]',expression='(inputs - mean) / var.sqrt()')],role='norm'),
 S('affine','Learned logscale / shift',[N('out','exp(log_gamma)*x_hat + beta','multiply','[B,4]',expression='torch.exp(self.log_gamma) * x_hat + self.beta',parameters=['log_gamma','beta'])]),
 S('det','Jacobian contribution',[N('detop','sum(log_gamma - .5*log(var))','density','[1]',expression='(self.log_gamma - 0.5 * torch.log(var)).sum(-1, keepdim=True)',parameters=['log_gamma'])],role='norm')],
 [['stats'],['normalize','running','det'],['affine']],
 [('x','stats'),('stats','normalize',{'role':'statistics'}),('stats','running',{'role':'state_update'}),('x','normalize'),('normalize','affine'),('stats','det',{'role':'statistics'}),('affine','y'),('det','ld')],
 [('BatchNormFlow.forward','(inputs - self.batch_mean).pow(2).mean(0) + self.eps'),('BatchNormFlow.forward','torch.exp(self.log_gamma) * x_hat + self.beta')],
 dict(num_inputs=4,mode='direct',training=True,momentum=0.0,epsilon=1e-5,parameters=['log_gamma','beta'],buffers=['running_mean','running_var'],det_shape=[1]),
 'BatchNormFlow direct training profile. Evaluation reads running statistics; inverse training requires saved batch statistics.',
 ['Mean/variance are vectors of length D. Source returns determinant shape [1], broadcastable across B.',
 'Variance uses biased mean squared deviations and adds eps before sqrt; momentum weights the old value, unlike common PyTorch momentum naming.',
 'State-update arrows indicate mutation; they are not the input used to normalize this batch.'],
 ['Do not invent unbiased variance or per-example [B,1] determinant as the literal source return.'])

add('realnvp_coupling','RealNVP / masked coupling','可逆耦合',D,'CouplingLayer.forward',
 ['CouplingLayer.__init__','CouplingLayer.forward'],
 [N('x','Input x',shape='[B,4]'),N('mask','Fixed mask [1,0,1,0]',shape='[4]',symbols=['CouplingLayer.__init__'],storage_kind='ordinary_tensor_attribute',learnable=False)],
 [N('y','Masked affine output',shape='[B,4]'),N('ld','Logdet per example',shape='[B,1]')],
 [S('masked','Condition from retained entries',[N('maskedop','inputs * mask','multiply','[B,4]',expression='inputs * mask')]),
 S('snet','Independent scale network',[N('smlp','Linear4->8->8->4 / Tanh','linear','[B,4]',symbols=['CouplingLayer.__init__','CouplingLayer.forward'],parameters=['scale_net.0','scale_net.2','scale_net.4'],activation='Tanh'),N('smask','log_s * (1-mask)','multiply','[B,4]',expression='self.scale_net(masked_inputs) * (1 - mask)')],role='ffn'),
 S('tnet','Independent translation network',[N('tmlp','Linear4->8->8->4 / ReLU','linear','[B,4]',symbols=['CouplingLayer.__init__','CouplingLayer.forward'],parameters=['translate_net.0','translate_net.2','translate_net.4'],activation='ReLU'),N('tmask','t * (1-mask)','multiply','[B,4]',expression='self.translate_net(masked_inputs) * (1 - mask)')],role='ffn'),
 S('scale','Positive scale',[N('exp','exp(log_s)','tensor','[B,4]',expression='torch.exp(log_s)')]),
 S('affine','Scale then shift',[N('mul','inputs * s + t','multiply','[B,4]',expression='inputs * s + t',affine_order='scale_then_shift')]),
 S('det','Changed-entry logdet',[N('sum','log_s.sum(-1,keepdim=True)','density','[B,1]',expression='log_s.sum(-1, keepdim=True)')],role='norm')],
 [['masked'],['snet','tnet'],['scale','det'],['affine']],
 [('x','masked'),('mask','masked'),('masked','snet'),('masked','tnet'),('snet','scale'),('snet','det'),('scale','affine',{'dst_port':'scale'}),('tnet','affine',{'dst_port':'t'}),('x','affine',{'role':'retained_value'}),('affine','y'),('det','ld')],
 [('CouplingLayer.forward','self.scale_net(masked_inputs) * (1 - mask)'),('CouplingLayer.forward','inputs * s + t')],
 dict(num_inputs=4,num_hidden=8,num_cond_inputs=None,mask=[1,0,1,0],mask_storage='ordinary_tensor_attribute',mode='direct',affine_order='scale_then_shift'),
 'One CouplingLayer direct profile; optional condition concat and inverse are excluded.',
 ['Source mask is an ordinary tensor attribute, not a registered buffer. Selected mask retains entries 0 and 2.',
 'The two MLPs are independent. Their outputs are masked with 1-mask, which makes the retained entries identity.',
 'This implementation uses exp(log_s) and x*s+t, unlike the Glow sigmoid and shift-then-scale form.',
 'Inner init(m) is defined but never applied; do not claim orthogonal initialization.'],
 ['Do not share the scale/translation parameters or reorder affine operations.'])

add('sigmoid_bijector','Sigmoid bijector / Jacobian branch','逐元素可逆变换',D,'Sigmoid.forward',
 ['Sigmoid.forward','Logit.forward'],[N('x','Real-valued x',shape='[B,4]')],[N('y','s(x) in (0,1)',shape='[B,4]'),N('ld','Logdet per example',shape='[B,1]')],
 [S('nonlinear','Elementwise transform',[N('sigmoid','sigmoid(inputs)','sigmoid','[B,4]',expression='s(inputs)',learnable=False)]),
 S('jacobian','Derivative and log-volume',[N('derivative','s(x) * (1-s(x))','multiply','[B,4]',expression='s(inputs) * (1 - s(inputs))'),N('logsum','log then sum over D','density','[B,1]',expression='torch.log(s(inputs) * (1 - s(inputs))).sum(-1, keepdim=True)',dim=-1,keepdim=True)],role='norm')],
 [['nonlinear'],['jacobian']],[('x','nonlinear'),('nonlinear','y'),('nonlinear','jacobian'),('jacobian','ld')],
 [('Sigmoid.forward','torch.log(s(inputs) * (1 - s(inputs))).sum(-1, keepdim=True)'),('Logit.forward',"super(Logit, self).forward(inputs, 'inverse')")],
 dict(mode='direct',input_features=4,parameters=[],inverse='log(x/(1-x))',logit_subclass_bug=True),
 'Sigmoid.forward direct branch only. The separate Logit subclass argument bug is explicitly documented.',
 ['Sigmoid source implements a real direct/inverse bijector and returns the sum of log derivative.',
 'Logit subclass passes inverse as the second positional cond_inputs argument, leaving mode=direct. It is therefore not drawn as a correctly implemented logit wrapper.'],
 ['Do not silently replace the actual buggy Logit.forward by the textbook logit implementation.'])

add('spectral_norm_linear','Spectral normalization / Linear wrapper','权重约束',B,'SNLinear.forward',
 ['SN.__init__','SN.W_','SNLinear.__init__','SNLinear.forward','power_iteration','gram_schmidt','proj'],
 [N('x','Data x',shape='[B,16]'),N('weight','Learned W and u buffer',shape='W [8,16]; u0 [1,8]',symbols=['SNLinear.__init__','SN.__init__'],parameters=['weight','bias'],buffers=['u0','sv0'])],
 [N('y','Spectrally normalized output',shape='[B,8]')],
 [S('estimate','Power iteration / 1 SV',[
 N('flatten','W.view(out_channels,-1)','tensor','[8,16]',symbols=['SN.W_'],expression='self.weight.view(self.weight.size(0), -1)'),
 N('vectors','v=norm(uW); u=norm(vW.T)','tensor','v[1,16]; u[1,8]',symbols=['power_iteration','gram_schmidt'],no_grad=True,eps=1e-12,orthogonalization='Gram-Schmidt; vacuous with num_svs=1',update_u='only training=True'),
 N('sigma','sigma = squeeze(v W.T u.T)','matmul','scalar',symbols=['power_iteration'],expression='torch.squeeze(torch.matmul(torch.matmul(v, W.t()), u.t()))',sigma_no_grad=False)],role='ffn'),
 S('normalize','Normalize learned weight',[N('divide','weight / svs[0]','norm','[8,16]',symbols=['SN.W_'],expression='self.weight / svs[0]',parameters=['weight'])],role='norm'),
 S('state','Training-only buffer writes',[N('write','Update u0 and logging sv0','control',symbols=['SN.W_','power_iteration'],buffers=['u0','sv0'],condition='training',sv0_used_for_weight=False)],role='control'),
 S('linear','F.linear with normalized weight',[N('linearop','F.linear(x,W_,bias)','linear','[B,8]',expression='F.linear(x, self.W_(), self.bias)',parameters=['bias'],bias=True)],role='ffn')],
 [['estimate'],['normalize','state'],['linear']],
 [('weight','estimate'),('estimate','normalize',{'role':'weight'}),('weight','normalize',{'role':'weight'}),('estimate','state',{'role':'state_update'}),('normalize','linear',{'role':'weight'}),('x','linear'),('linear','y')],
 [('SN.W_','self.weight / svs[0]'),('SNLinear.forward','F.linear(x, self.W_(), self.bias)'),('power_iteration','torch.squeeze(torch.matmul(torch.matmul(v, W.t()), u.t()))')],
 dict(in_features=16,out_features=8,num_svs=1,num_itrs=1,transpose=False,training=True,buffers=['u0','sv0'],parameters=['weight','bias'],sv_logging_only=True),
 'One SNLinear with one power iteration/singular value; conv and embedding wrappers are excluded.',
 ['Power vectors are estimated under no_grad, but the singular value calculation occurs outside that context.',
 'u0 and sv0 are buffers. sv0 is for logging, whereas division uses current svs[0]; replacing the denominator by the buffer changes semantics.',
 'Every forward normalizes W. Training controls the state writes, not whether normalization happens.'],
 ['Do not turn spectral normalization into an activation normalization layer.'])

add('manual_fused_bn','Manual / fused BatchNorm arithmetic','归一化统计展开',B,'manual_bn',
 ['manual_bn','fused_bn'],
 [N('x','Feature tensor x',shape='[B,8,8,8]'),N('gain','Provided gain / bias',shape='[1,8,1,1]',argument_origin='caller-supplied; not locally registered')],
 [N('y','Normalized affine output',shape='[B,8,8,8]')],
 [S('stats','Statistics from float32 x',[
 N('cast','x.float()','tensor','[B,8,8,8]',expression='x.float()',dtype='float32'),
 N('moments','m=E[x]; m2=E[x^2]','statistics','each [1,8,1,1]',expressions=['torch.mean(float_x, [0, 2, 3], keepdim=True)','torch.mean(float_x ** 2, [0, 2, 3], keepdim=True)'],axes=[0,2,3],keepdim=True),
 N('variance','var=m2-m^2; cast back','statistics','[1,8,1,1]',expression='m2 - m ** 2',clamp=False,dtype='same as x')],role='norm'),
 S('scale','Fuse gain into scale',[
 N('rsqrt','rsqrt(var+eps)','norm','[1,8,1,1]',symbols=['fused_bn'],expression='torch.rsqrt(var + eps)',epsilon=1e-5),
 N('gainop','scale *= gain','multiply','[1,8,1,1]',symbols=['fused_bn'],expression='scale * gain')],role='norm'),
 S('shift','Fuse bias into shift',[N('shiftop','shift = mean*scale - bias','subtract','[1,8,1,1]',symbols=['fused_bn'],expression='shift - bias',expanded_formula='mean*scale-bias')]),
 S('affine','Apply fused arithmetic',[N('out','x*scale - shift','multiply','[B,8,8,8]',symbols=['fused_bn'],expression='x * scale - shift')])],
 [['stats'],['scale'],['shift'],['affine']],
 [('x','stats'),('stats','scale',{'src_port':'var'}),('gain','scale',{'src_port':'gain','dst_port':'gain'}),('stats','shift',{'src_port':'mean','dst_port':'mean'}),('scale','shift',{'dst_port':'scale'}),('gain','shift',{'src_port':'bias','dst_port':'bias'}),('scale','affine',{'dst_port':'scale'}),('shift','affine',{'dst_port':'shift'}),('x','affine',{'role':'retained_value'}),('affine','y')],
 [('manual_bn','m2 - m ** 2'),('fused_bn','x * scale - shift'),('manual_bn','torch.mean(float_x, [0, 2, 3], keepdim=True)')],
 dict(channels=8,epsilon=1e-5,return_mean_var=False,gain_provided=True,bias_provided=True,variance='E[x²]-E[x]²',clamp=False,parameters=[]),
 'manual_bn calling fused_bn; gain/bias supplied by caller, no running-statistics module.',
 ['Statistics are accumulated in float32, then mean and variance are cast to the original dtype.',
 'The source uses E[x²]-E[x]² without clamping. Both moment reductions read the same input; their glyph is a compound statistics operation.',
 'gain and bias are input arguments, not parameters declared by these functions.'],
 ['Do not add running EMA or locally learned gain/bias to this function-only subgraph.'])

add('conditional_bn','Conditional BatchNorm / two condition heads','条件归一化',B,'ccbn.forward',
 ['ccbn.__init__','ccbn.forward'],
 [N('x','Feature x',shape='[B,8,8,8]'),N('condition','Condition y',shape='[B,16]')],
 [N('y','Conditioned features',shape='[B,8,8,8]')],
 [S('norm','BatchNorm without affine',[N('bn','F.batch_norm / affine=None','norm','[B,8,8,8]',expression='F.batch_norm(x, self.stored_mean, self.stored_var, None, None, self.training, 0.1, self.eps)',buffers=['stored_mean','stored_var'],momentum=0.1,epsilon=1e-5,affine=False)],role='norm'),
 S('gain','Gain from condition',[N('gainlinear','Independent Linear 16 -> 8','linear','[B,8]',symbols=['ccbn.__init__','ccbn.forward'],parameters=['gain.weight','gain.bias'],module_identity='gain'),N('gainview','1+gain(y); view B,C,1,1','tensor','[B,8,1,1]',expression='(1 + self.gain(y)).view(y.size(0), -1, 1, 1)',offset=1)],role='ffn'),
 S('bias','Bias from condition',[N('biaslinear','Independent Linear 16 -> 8','linear','[B,8]',symbols=['ccbn.__init__','ccbn.forward'],parameters=['bias.weight','bias.bias'],module_identity='bias'),N('biasview','bias(y); view B,C,1,1','tensor','[B,8,1,1]',expression='self.bias(y).view(y.size(0), -1, 1, 1)')],role='ffn'),
 S('multiply','Condition scale',[N('mul','out * gain','multiply','[B,8,8,8]',expression='out * gain')]),
 S('add','Condition shift',[N('addop','scaled + bias','add','[B,8,8,8]',expression='out * gain + bias')])],
 [['norm','gain','bias'],['multiply'],['add']],
 [('x','norm'),('condition','gain'),('condition','bias'),('norm','multiply'),('gain','multiply',{'dst_port':'gain'}),('multiply','add'),('bias','add',{'dst_port':'bias'}),('add','y')],
 [('ccbn.forward','(1 + self.gain(y)).view(y.size(0), -1, 1, 1)'),('ccbn.forward','F.batch_norm(x, self.stored_mean, self.stored_var, None, None, self.training, 0.1, self.eps)'),('ccbn.forward','out * gain + bias')],
 dict(output_size=8,input_size=16,which_linear='nn.Linear explicitly selected',cross_replica=False,mybn=False,norm_style='bn',training=True,source_momentum_literal=0.1),
 'ccbn with norm_style=bn, mybn=False, cross_replica=False, which_linear=nn.Linear selected.',
 ['Two independent condition heads predict per-example gain and bias; gain has an explicit +1 offset.',
 'Feature normalization has no affine parameters. stored_mean/var are buffers and the selected training call may update them inside the library.',
 'F.batch_norm receives literal momentum .1, irrespective of the constructor self.momentum attribute.',
 'Other branches are excluded. The GN path references self.normstyle, a source typo, and is not silently repaired.'],
 ['Do not replace conditional y by class indices or one-hot embeddings absent from this boundary.'])

add('nonlocal_attention','Non-local 2D attention / pooled keys-values','非局部空间注意力',B,'Attention.forward',
 ['Attention.__init__','Attention.forward','SNConv2d.__init__','SNConv2d.forward'],
 [N('x','Feature map x',shape='[B,32,8,8]')],[N('y','Residual attention output',shape='[B,32,8,8]')],
 [S('theta','Full-resolution theta',[
 N('theta_conv','SNConv1x1 32 -> 4','conv2d','[B,4,8,8]',symbols=['Attention.__init__','Attention.forward','SNConv2d.forward'],parameters=['theta.weight'],bias=False,module_identity='theta'),
 N('theta_view','view B,4,64','tensor','[B,4,64]',expression='theta.view(-1, self.ch // 8, x.shape[2] * x.shape[3])')],role='ffn'),
 S('phi','Pooled phi',[
 N('phi_conv','SNConv1x1 32 -> 4','conv2d','[B,4,8,8]',symbols=['Attention.__init__','Attention.forward','SNConv2d.forward'],parameters=['phi.weight'],bias=False,module_identity='phi'),
 N('phi_pool','MaxPool2x2; view B,4,16','tensor','[B,4,16]',expression='F.max_pool2d(self.phi(x), [2, 2])',pool_size=[2,2])],role='ffn'),
 S('g','Pooled values g',[
 N('g_conv','SNConv1x1 32 -> 16','conv2d','[B,16,8,8]',symbols=['Attention.__init__','Attention.forward','SNConv2d.forward'],parameters=['g.weight'],bias=False,module_identity='g'),
 N('g_pool','MaxPool2x2; view B,16,16','tensor','[B,16,16]',expression='F.max_pool2d(self.g(x), [2, 2])',pool_size=[2,2])],role='ffn'),
 S('beta','Spatial similarity',[
 N('score','theta.T @ phi','matmul','[B,64,16]',expression='torch.bmm(theta.transpose(1, 2), phi)'),
 N('softmax','Softmax over pooled positions','softmax','[B,64,16]',expression='F.softmax(torch.bmm(theta.transpose(1, 2), phi), -1)',dim=-1)],role='attention'),
 S('aggregate','Attend and restore space',[
 N('bmm','g @ beta.T','matmul','[B,16,64]',expression='torch.bmm(g, beta.transpose(1, 2))'),
 N('view','view B,16,8,8','tensor','[B,16,8,8]'),
 N('o_conv','SNConv1x1 16 -> 32','conv2d','[B,32,8,8]',symbols=['Attention.__init__','Attention.forward','SNConv2d.forward'],parameters=['o.weight'],module_identity='o',bias=False)],role='ffn'),
 S('residual','Learned residual gain',[
 N('gain','gamma * o','multiply','[B,32,8,8]',symbols=['Attention.__init__','Attention.forward'],expression='self.gamma * o',parameters=['gamma'],initial_gamma=0.0),
 N('add','gamma*o + x','add','[B,32,8,8]',expression='self.gamma * o + x')])],
 [['theta','phi','g'],['beta'],['aggregate'],['residual']],
 [('x','theta'),('x','phi'),('x','g'),('theta','beta',{'dst_port':'theta'}),('phi','beta',{'dst_port':'phi'}),('beta','aggregate',{'dst_port':'beta'}),('g','aggregate',{'dst_port':'values'}),('aggregate','residual'),('x','residual',{'role':'retained_value','dst_port':'x'}),('residual','y')],
 [('Attention.forward','F.softmax(torch.bmm(theta.transpose(1, 2), phi), -1)'),('Attention.forward','self.gamma * o + x')],
 dict(ch=32,input_shape=['B',32,8,8],which_conv='SNConv2d default',theta_positions=64,phi_positions=16,g_positions=16,softmax_dim=-1,gamma_initial=0.0,attention_scaling=None),
 'One BigGAN Attention module; SNConv2d is a normalized-weight call boundary, see separate SNLinear mechanism.',
 ['Theta remains full-resolution; phi and g use max pooling and therefore have four times fewer spatial positions.',
 'Softmax normalizes the last pooled-position axis. No 1/sqrt(d) scale or positional embedding appears.',
 'theta,phi,g,o weights are four independent instances; gamma is a learned scalar initialized zero.',
 'Source y argument is unused. It is not an additional condition input in this attention view.'],
 ['Do not label this standard full-resolution Transformer Q/K/V attention or permanently zero residual.'])

O='rasbt-ordinal-modules/pytorch_ipynb/ordinal/CORAL_cement.py'
add('coral_head','CORAL / shared ordinal score head','序数输出头',O,'CoralLayer.forward',
 ['CoralLayer.__init__','CoralLayer.forward'],
 [N('x','Features after omitted MLP',shape='[B,16]'),N('bias','Learned threshold biases',shape='[4]',symbols=['CoralLayer.__init__'],parameters=['coral_bias'])],
 [N('y','Ordinal threshold logits',shape='[B,4]')],
 [S('score','Single shared score',[N('linear','Linear 16 -> 1 / no bias','linear','[B,1]',symbols=['CoralLayer.__init__','CoralLayer.forward'],parameters=['coral_weights.weight'],in_features=16,out_features=1,bias=False)],role='ffn'),
 S('broadcast','Broadcast across K-1 thresholds',[N('add','score + coral_bias','add','[B,4]',expression='self.coral_weights(x) + self.coral_bias',threshold_count=4,score_shared=True)])],
 [['score'],['broadcast']],[('x','score'),('score','broadcast'),('bias','broadcast',{'dst_port':'threshold_bias'}),('broadcast','y')],
 [('CoralLayer.__init__','torch.nn.Linear(self.size_in, 1, bias=False)'),('CoralLayer.forward','self.coral_weights(x) + self.coral_bias')],
 dict(size_in=16,num_classes=5,thresholds=4,preinit_bias=True,score_weights_shared=True,parameters=['coral_weights.weight','coral_bias']),
 'Local CoralLayer class only. It overrides the imported same-name class; upstream MLP and training losses excluded.',
 ['A single biasless linear score is shared by all K-1 logits, then each threshold receives its own learned bias.',
 'Default preinitialized bias is arange(K-1,0,-1)/(K-1), here [1,.75,.5,.25]; the source does not impose a hard sorted-bias constraint after updates.',
 'This view stops at logits. Sigmoid decoding and loss calls are outside the class.'],
 ['Do not draw K-1 independent score weight vectors or import an unreviewed external CoralLayer implementation.'])
O='rasbt-ordinal-modules/pytorch_ipynb/ordinal/CORN_cement.py'
add('corn_decoder','CORN / conditional probability decoder','序数概率解码',O,'__module__',
 ['__module__','MLP.__init__','MLP.forward'],
 [N('x','Logits from omitted MLP.fc',shape='[B,4]',scope_boundary='caller logits; ordinary Linear has 4 independent output rows')],
 [N('y','Cumulative tail probabilities',shape='[B,4]')],
 [S('conditional','Convert logits to conditionals',[N('sigmoid','torch.sigmoid(logits)','sigmoid','[B,4]',expression='torch.sigmoid(logits)',parameters=[])],role='attention'),
 S('cumulative','Ordered cumulative product',[N('cumprod','cumprod(probas,dim=1)','tensor','[B,4]',expression='torch.cumprod(probas, dim=1)',dim=1,operation='cumulative_product')])],
 [['conditional'],['cumulative']],[('x','conditional'),('conditional','cumulative'),('cumulative','y')],
 [('__module__','torch.sigmoid(logits)'),('__module__','torch.cumprod(probas, dim=1)')],
 dict(num_classes=5,thresholds=4,scope='Notebook caller cell',parameters=[],output='tail probabilities',threshold_dim=1),
 'Notebook caller sigmoid and cumprod subgraph only; not a custom nn.Module, not the MLP or external loss.',
 ['MLP.fc is an ordinary K-1-output Linear. Its logits enter this separate caller decoding block.',
 'The j-th tail probability is the product of conditional probabilities through threshold j; sigmoid alone is insufficient.',
 'Evidence uses Notebook module scope and preserved cell mappings, rather than inventing a CORNDecoder class.'],
 ['Do not share all output score weights as in CORAL or replace cumprod by Softmax/sum.'])

# Operand reads are distinct from applying the masked affine to x.
CASES['masked_linear']['stages'][0]['suppress_input_boundary']=True
CASES['masked_linear']['edges'][0]=('x','linear',{'dst_port':'input'})
CASES['masked_linear']['edges'][1]=('mask','w_mask',{'role':'weight_mask'})

CASES['zero_conv']['name']='ZeroConv2d conditioner'
CASES['corn_decoder']['name']='CORN probability decoder'
CASES['masked_linear']['edges'][0]=('x','linear',{'dst_port':'input','src_side':'right','dst_side':'right'})
CASES['masked_linear']['edges'][1]=('mask','w_mask',{'role':'weight_mask','src_side':'right','dst_side':'right'})

add('flow_sequential','FlowSequential / dual-stream composition','双流容器',D,'FlowSequential.forward',
 ['FlowSequential.forward','Sigmoid.forward','Reverse.__init__','Reverse.forward'],
 [N('x','Input features',shape='[B,4]')],[N('y','Composed transform output',shape='[B,4]'),N('ld','Accumulated logdet',shape='[B,1]')],
 [S('init','Initialize accumulator',[N('zeros','zeros(B,1) if logdets=None','control','[B,1]',expression='torch.zeros(inputs.size(0), 1, device=inputs.device)',condition='logdets is None',learnable=False)],role='control'),
 S('first','Registered component 0',[N('call0','Sigmoid call -> u, det0','sigmoid','u[B,4]; det0[B,1]',symbols=['Sigmoid.forward','FlowSequential.forward'],module_identity='0',opaque_local_expansion='see sigmoid_bijector case',selected_component='Sigmoid')]),
 S('second','Registered component 1',[N('call1','Reverse call -> v, det1=0','tensor','v[B,4]; det1[B,1]',symbols=['Reverse.forward','Reverse.__init__','FlowSequential.forward'],module_identity='1',selected_component='Reverse',permutation=[3,2,1,0],parameters=[]) ]),
 S('add0','Accumulate component 0',[N('sum0','logdets += det0','add','[B,1]',expression='logdet',operation='inplace accumulator add',iteration=0)]),
 S('add1','Accumulate component 1',[N('sum1','logdets += det1','add','[B,1]',expression='logdet',operation='inplace accumulator add',iteration=1)])],
 [['init'],['first'],['second','add0'],['add1']],
 [('x','first'),('first','second',{'src_port':'features','dst_port':'features'}),('init','add0',{'dst_port':'accumulator'}),('first','add0',{'src_port':'logdet','dst_port':'increment'}),('add0','add1',{'dst_port':'accumulator'}),('second','add1',{'src_port':'logdet','dst_port':'increment'}),('second','y',{'src_port':'features'}),('add1','ld')],
 [('FlowSequential.forward','torch.zeros(inputs.size(0), 1, device=inputs.device)'),('FlowSequential.forward','module(inputs, cond_inputs, mode)'),('FlowSequential.forward','reversed(self._modules.values())')],
 dict(mode='direct',num_inputs=4,logdets=None,component_order=['Sigmoid','Reverse'],component_instances=['0','1'],inverse_order=['Reverse','Sigmoid']),
 'FlowSequential container with explicitly chosen two registered child instances Sigmoid then Reverse; not a source training configuration.',
 ['Registration order controls direct traversal; inverse uses reversed(self._modules.values()) and asks each same instance for its inverse branch.',
 'Each component returns a feature tensor and a logdet tensor. Feature composition and logdet accumulation are two distinct streams.',
 'Selected Sigmoid/Reverse components are an illustrative constructor profile, not a claim that an upstream callsite instantiates this exact pair.',
 'Reverse perm and inv_perm are ordinary NumPy attributes; no learned parameters. Their scalar Jacobian is zero.'],
 ['Do not chain component logdet into the next feature tensor or imply duplicate instances on inverse traversal.'])
CASES['masked_linear']['stages'][0]['flow_role']='weight'
CASES['glow_actnorm']['stages'][0]['flow_role']='control'
# Gamma-scaled attention output and original x meet only at residual Add.
for i,e in enumerate(CASES['nonlocal_attention']['edges']):
 if e[0]=='x' and e[1]=='residual':
  CASES['nonlocal_attention']['edges'][i]=('x','add',{'role':'retained_value','dst_port':'x','src_side':'right','dst_side':'right'})
# The singular-value estimate also reads W, independently of vector estimation.
CASES['spectral_norm_linear']['edges'].append(('flatten','sigma',{'role':'weight','dst_port':'weight','src_side':'right','dst_side':'right'}))

add('autoregressive_mask','Degree mask / strict autoregressive topology','掩码拓扑构造',D,'get_mask',['get_mask'],
 [N('dims','Static constructor dimensions',shape='in=8; out=8; flowD=4',configuration_input=True)],
 [N('mask','Output-layer mask',shape='[8,8]',storage_origin='return tensor; MaskedLinear registers caller mask separately')],
 [S('inputdegree','Hidden-input degrees',[
 N('i_arange','arange(in_features)','tensor','[8]',expression='torch.arange(in_features)'),
 N('i_mod','modulo (flowD - 1)','tensor','[8]',expression='torch.arange(in_features) % (in_flow_features - 1)',modulus=3)]),
 S('outputdegree','Strict output degrees',[
 N('o_arange','arange(out_features)','tensor','[8]',expression='torch.arange(out_features)'),
 N('o_mod','modulo flowD; subtract 1','tensor','[8]',expression='torch.arange(out_features) % in_flow_features - 1',modulus=4,offset=-1)]),
 S('compare','Broadcast dependency comparison',[
 N('ge','out_deg[:,None] >= in_deg[None,:]','tensor','[8,8]',expression='out_degrees.unsqueeze(-1) >= in_degrees.unsqueeze(0)',comparison='greater_or_equal',output_degree_offset=-1),
 N('float','float() / binary connectivity','tensor','[8,8]',expression='(out_degrees.unsqueeze(-1) >= in_degrees.unsqueeze(0)).float()',dtype='float32',learnable=False)])],
 [['inputdegree','outputdegree'],['compare']],
 [('dims','inputdegree',{'role':'configuration'}),('dims','outputdegree',{'role':'configuration'}),('inputdegree','compare',{'dst_port':'input_degrees'}),('outputdegree','compare',{'dst_port':'output_degrees'}),('compare','mask')],
 [('get_mask','torch.arange(in_features) % (in_flow_features - 1)'),('get_mask','torch.arange(out_features) % in_flow_features - 1'),('get_mask','(out_degrees.unsqueeze(-1) >= in_degrees.unsqueeze(0)).float()')],
 dict(in_features=8,out_features=8,in_flow_features=4,mask_type='output',parameters=[],dtype='float32',input_degrees=[0,1,2,0,1,2,0,1],output_degrees=[-1,0,1,2,-1,0,1,2]),
 'get_mask(mask_type=output) construction function only; no MaskedLinear forward or MADE model.',
 ['Input degrees use modulo D-1 for hidden units. Output degrees use modulo D then minus1, so output coordinate i can only depend on preceding input degrees.',
 'Comparison result has row=output unit and column=input unit. The float mask is fixed topology, not an attention probability or learned parameter.',
 'This function merely returns a tensor; register_buffer belongs to its MaskedLinear caller. Input/hidden mask types are alternate source branches not mixed into this selected view.'],
 ['Do not omit output degree minus1, transpose the mask, or treat the >= comparison as a Softmax.'])
CASES['glow_actnorm']['stages'][0]['suppress_input_boundary']=True
CASES['glow_actnorm']['edges'][0]=('x','stats',{'dst_port':'input','src_side':'left','dst_side':'left'})
CASES['glow_actnorm']['edges'][1]=('state','guard',{'role':'state','src_side':'right','dst_side':'right'})
CASES['flow_batchnorm']['edges'].append(('x','var',{'dst_port':'input','src_side':'left','dst_side':'left'}))
for i,e in enumerate(CASES['flow_batchnorm']['edges']):
 if e[0]=='stats' and e[1]=='normalize':CASES['flow_batchnorm']['edges'][i]=('stats','normalize',{'role':'statistics','src_port':'mean_var'})
 if e[0]=='stats' and e[1]=='det':CASES['flow_batchnorm']['edges'][i]=('stats','det',{'role':'statistics','src_port':'var'})
CASES['realnvp_coupling']['edges'] += [('mask','smask',{'role':'fixed_mask','dst_port':'mask','src_side':'left','dst_side':'left'}),('mask','tmask',{'role':'fixed_mask','dst_port':'mask','src_side':'right','dst_side':'right'})]
CASES['spectral_norm_linear']['stages'][2]['ops'][0]['operand_bundle']=['new_u','sigma']
CASES['spectral_norm_linear']['edges']=[e for e in CASES['spectral_norm_linear']['edges'] if not(e[0]=='estimate' and e[1]=='state')]
CASES['spectral_norm_linear']['edges'] += [('vectors','write',{'role':'state_update','dst_port':'u','src_side':'out','dst_side':'in'}),('sigma','write',{'role':'state_update','dst_port':'sv','src_side':'out','dst_side':'in'})]
for i,e in enumerate(CASES['spectral_norm_linear']['edges']):
 if e[0] in ['vectors','sigma'] and e[1]=='write':
  o=e[2].copy();o.update(src_side='right',dst_side='right');CASES['spectral_norm_linear']['edges'][i]=(e[0],e[1],o)
# Source shape reads are separate from Parameter/state and transformed values.
for key,dst in [('glow_actnorm','sum'),('glow_invconv','detop'),('glow_invconv_lu','detop'),('glow_affine_coupling','detop')]:
 CASES[key]['edges'].append(('x',dst,{'role':'shape_dependency','src_port':'shape','dst_port':'shape','src_side':'left','dst_side':'left'}))
for dst in ['theta_view','phi_pool','g_pool','view']:
 CASES['nonlocal_attention']['edges'].append(('x',dst,{'role':'shape_dependency','src_port':'shape','dst_port':'shape','src_side':'left','dst_side':'left'}))

# Explicit source interfaces: a statistics scope does not synthesize a tuple
# after its final variance operation. Mean and variance remain separate values.
_fb=CASES['flow_batchnorm']
_fb['edges']=[e for e in _fb['edges'] if not(e[0]=='stats' and e[1] in ('normalize','running','det'))]
_fb['edges'] += [
 ('stats','normalize',{'role':'statistics','src_port':'mean','dst_port':'mean'}),
 ('stats','normalize',{'role':'statistics','src_port':'var','dst_port':'var'}),
 ('stats','running',{'role':'state_update','src_port':'mean','dst_port':'mean'}),
 ('stats','running',{'role':'state_update','src_port':'var','dst_port':'var'}),
 ('stats','det',{'role':'statistics','src_port':'var','dst_port':'var'}),
]
_fb['facts'].append('Mean and variance have separate source producers and consumer ports; the variance glyph does not output a mean_var bundle.')

# Parameters are read whether initialization is skipped or performed. Copy is a
# mutation of the original Parameter state, not an activation input to affine.
_an=CASES['glow_actnorm']
_an['edges']=[e for e in _an['edges'] if not(e[0]=='init' and e[1] in ('affine','det'))]
_an['edges'] += [
 ('state','affine',{'role':'state','src_port':'loc','dst_port':'loc'}),
 ('state','affine',{'role':'state','src_port':'scale','dst_port':'scale'}),
 ('state','det',{'role':'state','src_port':'scale','dst_port':'scale'}),
 ('copy','state',{'role':'state_update','src_port':'loc','dst_port':'loc','src_side':'left','dst_side':'left'}),
 ('copy','state',{'role':'state_update','src_port':'scale','dst_port':'scale','src_side':'right','dst_side':'right'}),
]
_an['facts'].append('Initialization mutates the original loc/scale Parameter state. The affine shift, scale multiplication and determinant read named loc/scale state ports, including calls where initialization is skipped.')

# A learned weight is a separate operand of conv2d / determinant, not the image
# tensor entering their generic activation port.
for _key in ('glow_invconv','glow_invconv_lu'):
 for _i,_edge in enumerate(CASES[_key]['edges']):
  if _edge[1] in ('conv','det') and len(_edge)>2 and _edge[2].get('role')=='weight':
   _opts=dict(_edge[2],dst_port='weight')
   CASES[_key]['edges'][_i]=(_edge[0],_edge[1],_opts)

# Compound leaf glyphs keep their real field identities too. Named scope ports
# may select a field, but may not silently turn a tuple into its final member.
for _key in ('glow_affine_coupling','glow_additive_coupling'):
 CASES[_key]['stages'][0]['ops'][0]['return_fields']=['a','b']
CASES['glow_split_prior']['stages'][0]['ops'][0]['return_fields']=['retained','z_new']
CASES['glow_split_prior']['stages'][2]['ops'][0]['return_fields']=['mean','log_sd']
CASES['glow_split_prior']['stages'][2]['ops'][0]['output_bundle']=['mean','log_sd']
for _stage in CASES['flow_sequential']['stages']:
 if _stage['id'] in ('first','second'):
  _stage['ops'][0]['return_fields']=['features','logdet']
CASES['manual_fused_bn']['stages'][0]['ops'][1]['mean_output_expression']='m.type(x.type())'
CASES['manual_fused_bn']['stages'][0]['ops'][1]['mean_output_dtype']='same as x; cast in manual_bn before fused_bn'
CASES['manual_fused_bn']['contracts'].append(('manual_bn','m.type(x.type())'))
