"""Static, reviewed Transformer contracts reconstructed from Python AST.

This validates the supported educational implementation, not arbitrary Python.
No model module is imported, and source bytes are never changed by diagram edits.
"""
import ast
import textwrap
import hashlib
from pathlib import Path
import zipfile


def require(condition, message):
    if not condition:
        raise ValueError('source semantic contract: ' + message)


def expression(node):
    return ast.unparse(node)


def derive_contracts(symbols):
    """Read actual forward calls and x assignments, including each residual tap."""
    contracts = {}
    for side, symbol, operations, length in [
        ('enc', 'EncoderLayer.forward', ['self', 'ffn'], 'S'),
        ('dec', 'DecoderLayer.forward', ['self', 'cross', 'ffn'], 'T'),
    ]:
        span = symbols[symbol]
        tree = ast.parse(textwrap.dedent(span['snippet']))
        function = tree.body[0]
        state = 'src_pe' if side == 'enc' else 'tgt_pe'
        stage = 0
        for statement in function.body:
            if not isinstance(statement, ast.Assign):
                continue
            call = statement.value
            if not isinstance(call, ast.Call) or not isinstance(call.func, ast.Attribute):
                continue
            target, method = expression(statement.targets[0]), expression(call.func)
            op = 'self' if method == 'self.self_attn' else 'cross' if method == 'self.cross_attn' else 'ffn' if method == 'self.ffn' else None
            if op:
                require(stage < len(operations) and op == operations[stage], symbol + ' sublayer order changed')
                identity = side + '.' + op
                record = dict(input_identity=state, branch_result=target, stage=stage + 1,
                              source_symbol=symbol,
                              source_line=span['start'] + statement.lineno - 1,
                              source_expression=expression(call))
                if op != 'ffn':
                    args = {kw.arg: expression(kw.value) for kw in call.keywords}
                    expected_masks = ({'key_padding_mask': 'src_key_padding_mask'} if side == 'enc' else
                                      {'attn_mask': 'tgt_mask', 'key_padding_mask': 'tgt_key_padding_mask'} if op == 'self' else
                                      {'key_padding_mask': 'memory_key_padding_mask'})
                    require(args == dict(query='x', key='memory' if op == 'cross' else 'x',
                                         value='memory' if op == 'cross' else 'x', **expected_masks),
                            identity + ' Q/K/V or mask argument changed')
                    record.update(role='encoder_decoder_cross' if op == 'cross' else 'encoder_self' if side == 'enc' else 'decoder_masked_self',
                                  query_source=state, key_source='enc.output' if op == 'cross' else state,
                                  value_source='enc.output' if op == 'cross' else state,
                                  mask_args=list(expected_masks.values()), mask_bindings=expected_masks,
                                  mask_semantics='boolean True masks scores with -inf before Softmax; causal only when tgt_mask is supplied',
                                  q_shape=f'[B,{length},D]', k_shape='[B,S,D]' if op == 'cross' else f'[B,{length},D]',
                                  v_shape='[B,S,D]' if op == 'cross' else f'[B,{length},D]')
                else:
                    require([expression(a) for a in call.args] == ['x'], identity + ' input changed')
                contracts[identity] = record
            elif method.startswith('self.norm'):
                require(stage < len(operations) and target == 'x', symbol + ' residual state assignment changed')
                identity = side + '.norm' + str(stage + 1)
                op_record = contracts.get(side + '.' + operations[stage])
                require(op_record is not None, identity + ' missing sublayer')
                expected = f"self.norm{stage + 1}(x + self.dropout{stage + 1}({op_record['branch_result']}))"
                require(expression(call) == expected, identity + ' residual source, dropout or Post-LN ordering changed')
                contracts[identity] = dict(stage=stage + 1, ordering='post_layer_norm', skip_source=state,
                                          branch_dropout=f'dropout{stage + 1}',
                                          formula='LayerNorm(x + Dropout(sublayer(x)))', source_symbol=symbol,
                                          source_line=span['start'] + statement.lineno - 1,
                                          source_expression=expression(call))
                state = identity
                stage += 1
        require(stage == len(operations), symbol + ' incomplete sublayer sequence')
        require(any(isinstance(s, ast.Return) and expression(s.value) == 'x' for s in function.body), symbol + ' return changed')
    return contracts


def validate_source_semantics(ir, evidence):
    """Compare IR with AST, independently of its routes or cached contracts."""
    errors = []
    try:
        require(ir.get('source_sha256')==evidence.get('sha256'), 'IR/source evidence digest differs')
        origin=evidence['origin']
        if '!' in origin:
            archive,member=origin.split('!',1)
            with zipfile.ZipFile(archive) as z:source=z.read(member).decode('utf-8')
        else:source=Path(origin).read_text()
        require(hashlib.sha256(source.encode()).hexdigest()==evidence['sha256'], 'source bytes differ from reviewed evidence')
        lines=source.splitlines()
        for symbol in evidence['symbols'].values():
            require('\n'.join(lines[symbol['start']-1:symbol['end']])==symbol['snippet'], 'source snippet differs '+symbol['symbol'])
        expected = derive_contracts(evidence['symbols'])
        nodes = {n['id']: n for n in ir['nodes']}
        edges = {(e['src'], e['src_port'], e['dst'], e['dst_port'], e['kind']) for e in ir['edges']}
        for identity, contract in expected.items():
            n = nodes[identity]
            require(n.get('semantic_contract') == contract, identity + ' IR contract differs from source AST')
            require(n['parent'] == identity.split('.')[0] + '.layer_i', identity + ' source containment changed')
            if '.norm' in identity:
                require((contract['skip_source'], 'out', identity, 'skip', 'residual') in edges, identity + ' wrong residual producer')
                require(n.get('residual_source') == contract['skip_source'], identity + ' residual metadata differs')
                require(nodes[identity]['port_bindings']['out']==dict(node=identity+'.layernorm',port='out'), identity+' output must be LayerNorm output')
                require((identity+'.add','out',identity+'.layernorm','in','tensor') in edges, identity+' Add must precede LayerNorm')
            else:
                require((contract['input_identity'], 'out', identity, 'in', 'tensor') in edges, identity + ' input producer changed')
                if identity.endswith('.ffn'):
                    for left,right in [('linear1','relu'),('relu','dropout'),('dropout','linear2')]:
                        require((identity+'.'+left,'out',identity+'.'+right,'in','tensor') in edges, identity+' FFN operation order differs')
                    continue
                bindings=[e for e in ir['edges'] if e['src']==identity and e['kind']=='interface_binding' and e['src_port'] in ('in','memory')]
                expected_bindings={(identity,'memory' if identity=='dec.cross' and role in 'kv' else 'in',identity+'.'+role,'in','interface_binding') for role in 'qkv'}
                require({(e['src'],e['src_port'],e['dst'],e['dst_port'],e['kind']) for e in bindings}==expected_bindings, identity+' Q/K/V source interfaces differ')
                for role in 'qkv':
                    projection = nodes[identity + '.' + role]
                    expected_input = 'memory' if identity == 'dec.cross' and role in 'kv' else contract['input_identity']
                    require(projection.get('input_identity') == expected_input, identity + '.' + role + ' input identity differs')
                    require(projection.get('input_source') == contract[{'q':'query_source','k':'key_source','v':'value_source'}[role]], identity + '.' + role + ' value origin differs')
                    require(projection.get('output_shape') == contract[role + '_shape'], identity + '.' + role + ' length domain differs')
                    port='memory' if identity=='dec.cross' and role in 'kv' else 'in'
                    raw=n['port_bindings'].get(port,[])
                    aliases=raw if isinstance(raw,list) else [raw]
                    require(dict(node=identity+'.'+role,port='in') in aliases, identity+' Q/K/V interface aliases differ')
                mask = nodes[identity + '.sdpa.mask']
                require(mask.get('mask_inputs') == contract['mask_args'], identity + ' wrong mask domain')
                for left,right in [('qkt','scale'),('scale','mask'),('mask','softmax')]:
                    require((identity+'.sdpa.'+left,'out',identity+'.sdpa.'+right,'in','tensor') in edges, identity+' mask/Softmax ordering differs')
        require(('enc.output','out','dec.cross','memory','memory') in edges, 'cross memory must come from final encoder output')
        require(nodes['probabilities'].get('executed_in_forward') is False, 'probability Softmax cannot become forward computation')
    except (ValueError, KeyError, TypeError, OSError) as exc:
        errors.append(str(exc))
    return errors
