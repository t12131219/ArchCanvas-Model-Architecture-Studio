"""Independent AST contracts and semantic/source mutation checks for sequences.

No upstream model imports, training, torch execution, or saved-preview dependency.
"""
from __future__ import annotations
import ast
import copy
import importlib
import json
from pathlib import Path
import shutil
import sys
from tempfile import TemporaryDirectory

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
import bootstrap  # noqa: E402,F401
from evidence import collect,semantic_ir  # noqa: E402
from verify import source_checks  # noqa: E402

KEYS=['gru_cell','layernorm_lstm_cell','wavenet_block','tcn_block','structured_attention',
      'seq2seq_attention','seq2seq_additive_attention','qanet_context_query_attention','transformer_xl_relative',
      'milstm_projection','childsum_treelstm']


def symbols(source):
    tree=ast.parse(source);result={'__module__':tree}
    def visit(body,prefix=''):
        for n in body:
            if isinstance(n,(ast.ClassDef,ast.FunctionDef)):
                result[prefix+n.name]=n
                if isinstance(n,ast.ClassDef):visit(n.body,prefix+n.name+'.')
    visit(tree.body);return result


def statements(node):return [ast.unparse(s) for s in node.body]
def nmap(ir):return {n['id']:n for n in ir['nodes']}


def audit(irs):
    results=[]
    def check(key,name,condition):results.append(dict(module=key,name=name,passed=bool(condition)))
    def source(key):
        a=importlib.import_module('module_adapters.'+key)
        return symbols((ROOT/'sources'/a.SOURCE).read_text())
    def expressions(key,symbol,required):
        rows=statements(source(key)[symbol])
        for expression in required:check(key,symbol+': '+expression,expression in rows)
        return rows
    key='gru_cell';ir=irs[key];n=nmap(ir)
    rows=expressions(key,'gru_cell',[
        'gi = torch.mm(input, w_ih.t()) + b_ih','gh = torch.mm(hidden, w_hh.t()) + b_hh',
        'i_r, i_i, i_n = gi.chunk(3, 1)','h_r, h_i, h_n = gh.chunk(3, 1)',
        'resetgate = torch.sigmoid(i_r + h_r)','inputgate = torch.sigmoid(i_i + h_i)',
        'newgate = torch.tanh(i_n + resetgate * h_n)',
        'hy = newgate + inputgate * (hidden - newgate)','return hy'])
    check(key,'functional parameters are arguments; no Parameter constructor',
          [a.arg for a in source(key)['gru_cell'].args.args]==['input','hidden','w_ih','w_hh','b_ih','b_hh']
          and not any('Parameter(' in row for row in rows))
    check(key,'independent affine parameters and r/z/n slots',
          n['gru.gi']['parameters']==['w_ih','b_ih'] and n['gru.gh']['parameters']==['w_hh','b_hh']
          and n['gru.ci']['fields']==['i_r','i_i','i_n'])
    key='layernorm_lstm_cell';ir=irs[key];n=nmap(ir);sy=source(key)
    rows=expressions(key,'LayerNormLSTMCell.forward',[
        'hx, cx = state','igates = self.layernorm_i(torch.mm(input, self.weight_ih.t()))',
        'hgates = self.layernorm_h(torch.mm(hx, self.weight_hh.t()))','gates = igates + hgates',
        'ingate, forgetgate, cellgate, outgate = gates.chunk(4, 1)',
        'cy = self.layernorm_c(forgetgate * cx + ingate * cellgate)',
        'hy = outgate * torch.tanh(cy)','return (hy, (hy, cy))'])
    expressions(key,'LayerNorm.compute_layernorm_stats',[
        'mu = input.mean(-1, keepdim=True)','sigma = input.std(-1, keepdim=True, unbiased=False)','return (mu, sigma)'])
    expressions(key,'LayerNorm.forward',['mu, sigma = self.compute_layernorm_stats(input)',
        'return (input - mu) / sigma * self.weight + self.bias'])
    init=ast.unparse(sy['LayerNormLSTMCell.__init__'])
    check(key,'explicit branch=True selects source custom LayerNorm',
          'if decompose_layernorm:\n        ln = LayerNorm' in init and ir['profile']['decompose_layernorm'] is True)
    check(key,'source has no matrix biases; three independent norm weight/bias families',
          'self.bias_ih' not in init and 'self.bias_hh' not in init
          and [n[x]['parameters'] for x in ['lnlstm.lni.affine','lnlstm.lnh.affine','lnlstm.lnc.affine']]==
          [[owner+'.weight',owner+'.bias'] for owner in ['layernorm_i','layernorm_h','layernorm_c']])
    key='wavenet_block';ir=irs[key];n=nmap(ir);sy=source(key)
    loop=next(node for node in sy['WaveNetModel.wavenet'].body if isinstance(node,ast.For))
    rows=statements(loop)
    for expression in ['residual = dilation_func(x, dilation, init_dilation, i)',
                       'filter = self.filter_convs[i](residual)','filter = F.tanh(filter)',
                       'gate = self.gate_convs[i](residual)','gate = F.sigmoid(gate)',
                       'x = filter * gate','s = self.skip_convs[i](s)','skip = s + skip',
                       'x = self.residual_convs[i](x)','x = x + residual[:, :, self.kernel_size - 1:]']:
        check(key,'literal loop: '+expression,expression in rows)
    helper=symbols((ROOT/'sources/pytorch-wavenet-sequence/wavenet_modules.py').read_text())['dilate']
    for expression in ['x = x.permute(1, 2, 0).contiguous()','x = x.view(c, l, n)','x = x.permute(2, 0, 1).contiguous()']:
        check(key,'actual dilation helper: '+expression,expression in statements(helper))
    convs=[call for call in ast.walk(sy['WaveNetModel.__init__']) if isinstance(call,ast.Call) and ast.unparse(call.func)=='nn.Conv1d']
    gateconvs=[call for call in convs if any(kw.arg=='kernel_size' and ast.unparse(kw.value)=='kernel_size' for kw in call.keywords)]
    check(key,'filter/gate convs omit dilation kwargs; phase helper implements dilation',
          len(gateconvs)==2 and all(not any(kw.arg=='dilation' for kw in call.keywords) for call in gateconvs))
    check(key,'independent phase and skip shapes from selected N1/L18/d2/k2',
          n['wave.dilate']['shape']=='[2,32,9]' and n['wave.filter_conv']['shape']=='[2,32,8]'
          and n['wave.undilate']['shape']=='[1,32,16]' and n['wave.res_crop']['crop_side']=='left')
    check(key,'loop-state output explicitly distinguished from actual model return',
          all(n[x]['actual_return'] is False for x in ['wave.output_x','wave.output_skip']))
    key='tcn_block';ir=irs[key];n=nmap(ir);sy=source(key)
    expressions(key,'Chomp1d.forward',['return x[:, :, :-self.chomp_size].contiguous()'])
    expressions(key,'TemporalBlock.forward',['out = self.net(x)','res = x if self.downsample is None else self.downsample(x)','return self.relu(out + res)'])
    init=sy['TemporalBlock.__init__'];assignments={ast.unparse(s.targets[0]):s.value for s in init.body if isinstance(s,ast.Assign)}
    check(key,'literal Sequential stage order',
          [ast.unparse(a) for a in assignments['self.net'].args]==
          ['self.conv1','self.chomp1','self.relu1','self.dropout1','self.conv2','self.chomp2','self.relu2','self.dropout2'])
    for i,ci in [(1,16),(2,32)]:
        call=assignments['self.conv'+str(i)]
        check(key,'conv'+str(i)+' actual legacy weight_norm and dilation kwarg',
              ast.unparse(call.func)=='weight_norm' and ast.unparse(call.args[0].func)=='nn.Conv1d'
              and {kw.arg:ast.unparse(kw.value) for kw in call.args[0].keywords}=={'stride':'stride','padding':'padding','dilation':'dilation'})
        check(key,'conv'+str(i)+' calculated length20 then rightcrop16',
              (16+2*4-2*(3-1)-1)//1+1==20 and n[f'tcn.stage{i}.conv']['shape']=='[B,32,20]'
              and n[f'tcn.stage{i}.chomp']['shape']=='[B,32,16]')
    check(key,'projection selected by different input/output widths',
          isinstance(assignments['self.downsample'],ast.IfExp)
          and ast.unparse(assignments['self.downsample'].test)=='n_inputs != n_outputs'
          and ir['profile']['n_inputs']!=ir['profile']['n_outputs'])
    key='structured_attention';ir=irs[key];n=nmap(ir);sy=source(key)
    expressions(key,'StructuredSelfAttention.forward',[
        'x = F.tanh(self.linear_first(outputs))','x = self.linear_second(x)','x = self.softmax(x, 1)',
        'attention = x.transpose(1, 2)','sentence_embeddings = attention @ outputs',
        'avg_sentence_embeddings = torch.sum(sentence_embeddings, 1) / self.r'])
    expressions(key,'StructuredSelfAttention.softmax',[
        'trans_input = input.transpose(axis, len(input_size) - 1)',
        'input_2d = trans_input.contiguous().view(-1, trans_size[-1])',
        'soft_max_2d = F.softmax(input_2d)','return soft_max_nd.transpose(axis, len(input_size) - 1)'])
    init=sy['StructuredSelfAttention.__init__']
    lstm=next(c for c in ast.walk(init) if isinstance(c,ast.Call) and ast.unparse(c.func)=='torch.nn.LSTM')
    check(key,'actual unidirectional LSTM; no invented2H features',
          not any(kw.arg=='bidirectional' for kw in lstm.keywords) and n['struct.input']['bidirectional'] is False)
    check(key,'no source mask and both bias zero-initializations remain learnable',
          not any(isinstance(v,ast.Attribute) and 'mask' in v.attr for v in ast.walk(sy['StructuredSelfAttention.forward']))
          and all('self.'+name+'.bias.data.fill_(0)' in ast.unparse(init) for name in ['linear_first','linear_second'])
          and ir['profile']['padding_mask'] is False)
    key='seq2seq_attention';n=nmap(irs[key]);sy=source(key)
    expressions(key,'Attention.forward',[
        'attn = torch.bmm(output, context.transpose(1, 2))',
        'attn = F.softmax(attn.view(-1, input_size), dim=1).view(batch_size, -1, input_size)',
        'mix = torch.bmm(attn, context)','combined = torch.cat((mix, output), dim=2)',
        'output = F.tanh(self.linear_out(combined.view(-1, 2 * hidden_size))).view(batch_size, -1, hidden_size)',
        'return (output, attn)'])
    check(key,'actual optional .data mask uses-inf; no score scaling/Dropout',
          "attn.data.masked_fill_(self.mask, -float('inf'))" in ast.unparse(sy['Attention.forward'])
          and 'Dropout' not in ast.unparse(sy['Attention.__init__']) and n['ibm.score']['scale'] is None)
    key='seq2seq_additive_attention';n=nmap(irs[key]);sy=source(key)
    score=sy['AttentionLayer.calc_score'];branch=next(s for s in score.body if isinstance(s,ast.If))
    expected=['att_query = att_query.unsqueeze(2).expand(b, t_q, t_k, n)',
              'att_keys = att_keys.unsqueeze(1).expand(b, t_q, t_k, n)','sum_qk = att_query + att_keys',
              'sum_qk = sum_qk.view(b * t_k * t_q, n)',
              'out = self.linear_att(F.tanh(sum_qk)).view(b, t_q, t_k)']
    check(key,'entire real bahdanau branch pair expansion/add/tanh/scalar projection',
          ast.unparse(branch.test)=="self.mode == 'bahdanau'" and statements(branch)==expected)
    expressions(key,'AttentionLayer.forward',[
        'values = keys if values is None else values','scores = self.calc_score(att_query, keys)',
        'scores_normalized = F.softmax(scores, dim=2)','scores_normalized = self.dropout(scores_normalized)',
        'context = torch.bmm(scores_normalized, values)','return (context, scores_normalized)'])
    text=ast.unparse(sy['AttentionLayer.forward'])
    check(key,'finite mask and query-first output fusion',
          'scores.masked_fill_(mask, -1000000000000.0)' in text
          and 'self.linear_out(torch.cat([query, context], 2))' in text
          and n['addatt.concat']['ordered_operands']==['query','context'])
    key='qanet_context_query_attention';n=nmap(irs[key]);sy=source(key)
    expressions(key,'mask_logits',['return target * (1 - mask) + mask * -1e+30'])
    expressions(key,'CQAttention.forward',[
        'C = C.transpose(1, 2)','Q = Q.transpose(1, 2)','cmask = cmask.unsqueeze(2)','qmask = qmask.unsqueeze(1)',
        'Ct = C.unsqueeze(2).expand(shape)','Qt = Q.unsqueeze(1).expand(shape)','CQ = torch.mul(Ct, Qt)',
        'S = torch.cat([Ct, Qt, CQ], dim=3)','S = torch.matmul(S, self.w)',
        'S1 = F.softmax(mask_logits(S, qmask), dim=2)','S2 = F.softmax(mask_logits(S, cmask), dim=1)',
        'A = torch.bmm(S1, Q)','B = torch.bmm(torch.bmm(S1, S2.transpose(1, 2)), C)',
        'out = torch.cat([C, A, torch.mul(C, A), torch.mul(C, B)], dim=2)',
        'out = F.dropout(out, p=dropout, training=self.training)','return out.transpose(1, 2)'])
    config=ast.parse((ROOT/'sources/qanet-attention-sequence/config.py').read_text())
    literals={s.targets[0].id:ast.literal_eval(s.value) for s in config.body if isinstance(s,ast.Assign)
              and isinstance(s.targets[0],ast.Name) and s.targets[0].id in ['d_model','dropout']}
    check(key,'frozen configuration D96,dropout.1 and3D vector288',
          literals=={'d_model':96,'dropout':0.1} and n['cq.score']['parameter_shape']==[3*literals['d_model']])
    key='transformer_xl_relative';n=nmap(irs[key]);sy=source(key)
    expressions(key,'RelMultiHeadAttn._rel_shift',[
        'zero_pad = torch.zeros((x.size(0), 1, *x.size()[2:]), device=x.device, dtype=x.dtype)',
        'x_padded = torch.cat([zero_pad, x], dim=1)',
        'x_padded = x_padded.view(x.size(1) + 1, x.size(0), *x.size()[2:])',
        'x = x_padded[1:].view_as(x)','return x'])
    expressions(key,'RelPartialLearnableMultiHeadAttn.forward',[
        'rw_head_q = w_head_q + r_w_bias',"AC = torch.einsum('ibnd,jbnd->ijbn', (rw_head_q, w_head_k))",
        'rr_head_q = w_head_q + r_r_bias',"BD = torch.einsum('ibnd,jnd->ijbn', (rr_head_q, r_head_k))",
        'BD = self._rel_shift(BD)','attn_score = AC + BD','attn_score.mul_(self.scale)',
        'attn_prob = F.softmax(attn_score, dim=1)','attn_prob = self.dropatt(attn_prob)',
        "attn_vec = torch.einsum('ijbn,jbnd->ibnd', (attn_prob, w_head_v))",'return output'])
    fwd=sy['RelPartialLearnableMultiHeadAttn.forward'];membranch=next(s for s in fwd.body if isinstance(s,ast.If))
    check(key,'selected memory branch projects concat then keeps only current Q',
          ast.unparse(membranch.test)=='mems is not None'
          and 'cat = torch.cat([mems, w], 0)' in statements(membranch)
          and 'w_head_q = w_head_q[-qlen:]' in statements(membranch))
    check(key,'selected postnorm residual uses current w; memory not updated here',
          'output = self.layer_norm(w + attn_out)' in ast.unparse(fwd)
          and not any(isinstance(v,ast.Attribute) and v.attr=='detach' for v in ast.walk(fwd))
          and n['txl.residual']['memory_not_residual'] is True)
    key='milstm_projection';ir=irs[key];n=nmap(ir);sy=source(key)
    rows=expressions(key,'milstm_cell',[
        'Wx = x.mm(w_ih.t())','Uz = hx.mm(w_hh.t())',
        'gates = alpha * Wx * Uz + beta_i * Wx + beta_h * Uz + bias',
        'ingate, forgetgate, cellgate, outgate = gates.chunk(4, 1)','return (hy, cy)'])
    fwd=sy['milstm_cell'];assignment=next(v for v in fwd.body if isinstance(v,ast.Assign) and ast.unparse(v.targets[0])=='gates')
    coupling=assignment.value.left.left.left
    check(key,'left-associated alpha*Wx then multiply Uz, before additive terms',
          isinstance(coupling,ast.BinOp) and isinstance(coupling.op,ast.Mult)
          and isinstance(coupling.left,ast.BinOp) and isinstance(coupling.left.op,ast.Mult)
          and ast.unparse(coupling.left)=='alpha * Wx' and ast.unparse(coupling.right)=='Uz')
    check(key,'all parameters and coefficients are supplied functional Tensor arguments',
          [a.arg for a in fwd.args.args]==['x','hx','cx','w_ih','w_hh','alpha','beta_i','beta_h','bias']
          and not any('Parameter(' in row for row in rows))
    check(key,'matrix projections have no bias; single gate bias after3 terms',
          n['mi.wx']['bias'] is False and n['mi.uz']['bias'] is False
          and n['mi.bias']['parameters']==['bias'] and n['mi.bias']['parameter_shape']==[64])
    check(key,'different input/hidden matrix dimensions and4H gate shape',
          n['mi.wx']['weight_shape']==[64,12] and n['mi.uz']['weight_shape']==[64,16]
          and 4*ir['profile']['hidden_size']==64 and n['mi.output']['shape']=='[B,64]')
    check(key,'subgraph boundary is gates; actual function continues and returns hy,cy',
          n['mi.output']['actual_return'] is False and n['mi.output']['boundary_variable']=='gates'
          and n['mi.output']['actual_function_return']==['hy','cy']
          and 'cy = forgetgate * cx + ingate * cellgate' in rows)
    key='childsum_treelstm';ir=irs[key];n=nmap(ir);sy=source(key)
    expressions(key,'ChildSumTreeLSTM.node_forward',[
        'child_h_sum = torch.sum(child_h, dim=0, keepdim=True)',
        'iou = self.ioux(inputs) + self.iouh(child_h_sum)',
        'i, o, u = torch.split(iou, iou.size(1) // 3, dim=1)',
        'i, o, u = (F.sigmoid(i), F.sigmoid(o), F.tanh(u))',
        'f = F.sigmoid(self.fh(child_h) + self.fx(inputs).repeat(len(child_h), 1))',
        'fc = torch.mul(f, child_c)','c = torch.mul(i, u) + torch.sum(fc, dim=0, keepdim=True)',
        'h = torch.mul(o, F.tanh(c))','return (c, h)'])
    init=sy['ChildSumTreeLSTM.__init__'];linears=[v for v in init.body if isinstance(v,ast.Assign) and isinstance(v.value,ast.Call) and ast.unparse(v.value.func)=='nn.Linear']
    check(key,'actual4 independent Linear instances and default bias kwargs',
          [ast.unparse(v.targets[0]) for v in linears]==['self.ioux','self.iouh','self.fx','self.fh']
          and all(not v.value.keywords for v in linears)
          and all(n['tree.'+owner]['parameters']==[owner+'.weight',owner+'.bias'] and n['tree.'+owner]['bias']
                  for owner in ['ioux','iouh','fx','fh']))
    check(key,'node rank1 input taken by actual recursive caller, broadcasts with summed-child projection',
          'self.node_forward(inputs[tree.idx], child_c, child_h)' in ast.unparse(sy['ChildSumTreeLSTM.forward'])
          and n['tree.x']['shape']=='[12]' and n['tree.ioux']['shape']=='[48]' and n['tree.iouh']['shape']=='[1,48]')
    check(key,'K separate forget rows, not a gate computed from child_h_sum',
          n['tree.fh']['shape']=='[3,16]' and n['tree.f']['gate_count_per_node']==3
          and n['tree.fsum']['keepdim'] is True and n['tree.fsum']['dim']==0)
    check(key,'repeat reuses one fx instance across children and exact i,o,u gate ordering',
          n['tree.repeat']['new_parameter_instances'] is False and n['tree.repeat']['repeats']==[3,1]
          and n['tree.split']['fields']==['i','o','u'])
    check(key,'selected nonleaf3 children; leaf zero-state alternative is explicitly excluded',
          ir['profile']['children']==3 and ir['profile']['leaf_zero_initializer_selected'] is False
          and 'tree.num_children == 0' in ast.unparse(sy['ChildSumTreeLSTM.forward']))
    check(key,'actual method returns c then h, not hy,cy order',
          n['tree.output']['actual_return'] is True and n['tree.output']['return_fields']==['c','h'])
    return results


MUTATIONS={
 'gru_cell':([('gru.ch','gru.rhn','hidden_n'),('gru.z','gru.zdelta','update')],
             [('gru.ci','fields',['i_n','i_i','i_r']),('gru.hy','expression','newgate + resetgate * (hidden - newgate)')]),
 'layernorm_lstm_cell':([('lnlstm.lni.affine','lnlstm.gates','input_affine'),('lnlstm.lnc.affine','lnlstm.output','state_cell')],
                       [('lnlstm.lni.std','epsilon',1e-5),('lnlstm.wi','bias',True)]),
 'wavenet_block':([('wave.dilate','wave.res_crop','residual'),('wave.product','wave.skip','in')],
                 [('wave.filter_conv','dilation',2),('wave.res_crop','crop_side','right')]),
 'tcn_block':([('tcn.projection','tcn.add','residual'),('tcn.add','tcn.relu','in')],
              [('tcn.stage1.chomp','crop_side','left'),('tcn.stage2.conv','dilation',1)]),
 'structured_attention':([('struct.input','struct.pool','values'),('struct.attention','struct.output','attention')],
                         [('struct.attention','padding_mask',True),('struct.normalize','original_normalized_axis',2)]),
 'seq2seq_attention':([('ibm.context','ibm.mix','values'),('ibm.query','ibm.concat','output')],
                     [('ibm.score','scale','1/sqrt(16)'),('ibm.concat','ordered_operands',['output','mix'])]),
 'seq2seq_additive_attention':([('addatt.input_v','addatt.context','values'),('addatt.drop','addatt.output','weights')],
                              [('addatt.mask','fill','-inf'),('addatt.output','weight_origin','pre_dropout')]),
 'qanet_context_query_attention':([('cq.input_qm','cq.qmask','mask'),('cq.c','cq.b','values')],
                                 [('cq.softmax2','dim',2),('cq.fuse','ordered_operands',['C','A','C*A','C*A'])]),
 'transformer_xl_relative':([('txl.shift','txl.score','relative'),('txl.w','txl.residual','current')],
                           [('txl.q','output_length',7),('txl.norm','pre_lnorm',True)]),
 'milstm_projection':([('mi.uz','mi.product','Uz'),('mi.wx','mi.input_term','Wx')],
                      [('mi.hidden_term','parameters',['beta_i']),('mi.output','actual_return',True)]),
 'childsum_treelstm':([('tree.child_h','tree.fh','per_child_hidden'),('tree.child_c','tree.fc','child_cell')],
                     [('tree.split','fields',['i','u','o']),('tree.output','return_fields',['h','c'])]),
}


def negatives(irs,temporary_root,manifest_path):
    results=[]
    for key in KEYS:
        a=importlib.import_module('module_adapters.'+key);edges,fields=MUTATIONS[key]
        for src,dst,port in edges:
            changed=copy.deepcopy(irs[key]);target=next(e for e in changed['edges'] if e['src']==src and e['dst']==dst and e['dst_port']==port)
            alternative=next(n['id'] for n in changed['nodes'] if n['id'] not in [src,dst] and n['kind']!='group')
            target['src']=alternative
            try:a.validate_ir(changed)
            except (ValueError,AssertionError) as exc:results.append(dict(module=key,kind='wrong_real_edge',name=src+' -> '+dst+':'+port,rejected=True,reason=str(exc)))
            else:results.append(dict(module=key,kind='wrong_real_edge',name=src+' -> '+dst+':'+port,rejected=False))
        for identity,field,value in fields:
            changed=copy.deepcopy(irs[key]);nmap(changed)[identity][field]=value
            try:a.validate_ir(changed)
            except (ValueError,AssertionError) as exc:results.append(dict(module=key,kind='wrong_semantic_field',name=identity+'.'+field,rejected=True,reason=str(exc)))
            else:results.append(dict(module=key,kind='wrong_semantic_field',name=identity+'.'+field,rejected=False))
        model=a.build();slug=model['source_project'];dest=temporary_root/('source-negative-'+key)
        shutil.copytree(ROOT/'sources'/slug,dest/slug)
        original=dest/a.SOURCE;original.write_bytes(original.read_bytes()+b'\n# deliberately changed frozen source\n')
        try:collect(model,dest,dest/'evidence',manifest_path=manifest_path)
        except ValueError as exc:
            reason=str(exc);results.append(dict(module=key,kind='frozen_source',name='changed fixed-commit file bytes',rejected=reason.startswith('Source changed; review adapter before drawing:'),reason=reason))
        else:results.append(dict(module=key,kind='frozen_source',name='changed fixed-commit file bytes',rejected=False))
    return results


def run():
    manifest=json.loads((ROOT/'source_manifest.json').read_text())
    partial=ROOT/'staging/sequence_source_manifest.json'
    if partial.exists():
        for slug,record in json.loads(partial.read_text()).items():
            if slug in manifest and manifest[slug]['commit']!=record['commit']:raise ValueError('Conflicting fixed commit: '+slug)
            manifest[slug]=record
    irs={};guards={};sources={}
    with TemporaryDirectory(prefix='archcanvas-sequence-check-') as directory:
        tmp=Path(directory);mp=tmp/'manifest.json';mp.write_text(json.dumps(manifest))
        for key in KEYS:
            adapter=importlib.import_module('module_adapters.'+key);model=adapter.build();folder=tmp/key
            evidence=collect(model,ROOT/'sources',folder,manifest_path=mp);ir=semantic_ir(model,evidence)
            guards[key]=adapter.validate_ir(ir);sources[key]=source_checks(folder,evidence,ir,manifest_path=mp,source_root=ROOT/'sources');irs[key]=ir
        contracts=audit(irs);wrong=negatives(irs,tmp,mp)
    failures=[r['module']+': '+r['name'] for r in contracts if not r['passed']]
    failures += [r['module']+': unrejected '+r['name'] for r in wrong if not r['rejected']]
    return dict(passed=not failures,failures=failures,module_count=len(KEYS),upstream_code_executed=False,
                source_contract_count=len(contracts),source_contracts=contracts,
                adapter_guard_count=sum(len(v) for v in guards.values()),adapter_guards=guards,
                negative_count=len(wrong),negative_cases=wrong,source_checks=sources)


if __name__=='__main__':
    report=run();print(json.dumps(report,ensure_ascii=False,indent=2));raise SystemExit(0 if report['passed'] else 1)
