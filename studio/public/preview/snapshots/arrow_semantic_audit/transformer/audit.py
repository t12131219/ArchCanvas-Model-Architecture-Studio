#!/usr/bin/env python3
"""Independent source-specific contracts and actual SVG audit; no renderer imports."""
from __future__ import annotations
import argparse
import ast
import copy
import hashlib
import json
import math
import re
import subprocess
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path

HERE=Path(__file__).resolve().parent
GUIDE=HERE.parents[1]/'transformer_programmatic_guide'
NUM=r'[-+]?(?:\d*\.\d+|\d+\.?\d*)(?:[eE][-+]?\d+)?'


def expected_pairs(view):
    """Written from the supplied forward methods, independently of semantic_ir."""
    pairs=set()
    def edge(a,b):pairs.add((a,b))
    def norm_in(n,skip=False):
        return n+('.add:x' if skip else '.add:f') if view=='detailed' else n+(':skip' if skip else ':in')
    def norm_out(n):return n+('.layernorm:out' if view=='detailed' else ':out')
    def attn_in(n):
        return [n+'.'+r+':in' for r in 'qkv'] if view=='detailed' else [n+('.projection_summary:in' if view=='modules' else ':in')]
    def attn_out(n):return n+('.wo:out' if view=='detailed' else '.output_summary:out' if view=='modules' else ':out')
    def ffn_in(n):return n+('.linear1:in' if view!='overview' else ':in')
    def ffn_out(n):return n+('.linear2:out' if view!='overview' else ':out')
    for side,prefix,count in (('enc','src',2),('dec','tgt',3)):
        edge(prefix+'_tokens:out',prefix+'_embed:in')
        edge(prefix+'_embed:out',prefix+'_pe.add:x')
        edge(prefix+'_pe.buffer:out',prefix+'_pe.add:pe')
        state=prefix+'_pe.add:out'
        operations=['self','ffn'] if side=='enc' else ['self','cross','ffn']
        for i,operation in enumerate(operations,1):
            op=side+'.'+operation;n=side+'.norm'+str(i)
            inputs=ffn_in(op) if operation=='ffn' else (op+'.q:in' if operation=='cross' and view=='detailed' else attn_in(op))
            if isinstance(inputs,str):inputs=[inputs]
            for terminal in inputs:edge(state,terminal)
            edge(state,norm_in(n,True))
            edge(ffn_out(op) if operation=='ffn' else attn_out(op),norm_in(n))
            if view=='detailed':edge(n+'.add:out',n+'.layernorm:in')
            state=norm_out(n)
        if side=='dec':edge(state,'generator:in')
    memory=norm_out('enc.norm2')
    for terminal in (['dec.cross.k:in','dec.cross.v:in'] if view=='detailed' else
                     ['dec.cross.projection_summary:memory'] if view=='modules' else ['dec.cross:memory']):
        edge(memory,terminal)
    edge('generator:out','probabilities:in')
    if view!='overview':
        for side in ('enc','dec'):
            n=side+'.ffn';edge(n+'.linear1:out',n+'.relu:in');edge(n+'.relu:out',n+'.linear2:in')
        for n in ('enc.self','dec.self','dec.cross'):
            if view=='modules':
                for r in 'qkv':edge(n+'.projection_summary:'+r+'_out',n+'.sdpa:'+r)
                edge(n+'.sdpa:out',n+'.output_summary:in')
                continue
            for r in 'qkv':edge(n+'.'+r+':out',n+'.split:'+r+'_in')
            if n=='dec.cross':
                for r in 'qkv':edge(n+'.split:'+r+'_out',n+'.sdpa:'+r)
                edge(n+'.sdpa:out',n+'.merge:in')
            else:
                edge(n+'.split:q_out',n+'.sdpa.qkt:q');edge(n+'.split:k_out',n+'.sdpa.qkt:k')
                edge(n+'.split:v_out',n+'.sdpa.av:v')
                for a,b in zip(('qkt','scale','mask'),('scale','mask','softmax')):
                    edge(n+'.sdpa.'+a+':out',n+'.sdpa.'+b+':in')
                edge(n+'.sdpa.softmax:out',n+'.sdpa.av:a')
                edge(n+'.sdpa.av:out',n+'.merge:in')
            edge(n+'.merge:out',n+'.wo:in')
    return pairs


def points(element):
    values=[float(n) for n in re.findall(NUM,element.get('d',''))]
    return [values[i:i+2] for i in range(0,len(values),2)]


def inspect(layout,svg_root):
    errors=[];routes={r['id']:r for r in layout['routes']};seen=set()
    boxes={b['id']:b for b in layout['boxes']}
    aliases={a['id']:a for a in layout['semantic_projection']['value_aliases']}
    glyphs={e.get('data-node-id'):e for e in svg_root.iter() if e.get('data-node-id')}
    paths=[e for e in svg_root.iter() if e.tag.endswith('path') and e.get('fill')=='none']
    canonical=defaultdict(list)
    for e in paths:
        rid=e.get('data-route-id');r=routes.get(rid);actual=points(e)
        if r is None:errors.append('unregistered actual SVG path '+str(rid));continue
        if rid in seen:errors.append('duplicate actual SVG path '+rid)
        seen.add(rid)
        if len(actual)!=len(r['points']) or any(math.dist(a,b)>1e-6 for a,b in zip(actual,r['points'])):
            errors.append('actual SVG/layout path differs '+rid)
        if not e.get('marker-end'):errors.append('actual path has no arrow '+rid)
        for attr,key in (('data-src','src'),('data-dst','dst'),('data-canonical-src','canonical_src'),('data-canonical-dst','canonical_dst')):
            if e.get(attr)!=r.get(key):errors.append('actual SVG endpoint contract differs '+rid+' '+attr)
        try:trace=json.loads(e.get('data-semantic-edges','null'))
        except json.JSONDecodeError:trace=None
        if trace!=r.get('semantic_edges'):errors.append('actual SVG trace differs '+rid)
        key=r.get('canonical_src'),r.get('canonical_dst');canonical[key].append(r)
        for side,point in (('src',actual[0]),('dst',actual[-1])):
            identity,_,port=r[side].partition(':');box=boxes.get(identity)
            if not box or identity not in glyphs:errors.append('no actual glyph for '+r[side]);continue
            terminal=layout['ports'].get(identity,{}).get(port)
            if terminal is None or math.dist(point,terminal)>1e-6:errors.append('physical port mismatch '+rid)
            x,y,w,h=box['bbox']
            if not ((abs(point[0]-x)<1e-6 or abs(point[0]-x-w)<1e-6) and y<=point[1]<=y+h
                    or (abs(point[1]-y)<1e-6 or abs(point[1]-y-h)<1e-6) and x<=point[0]<=x+w):
                errors.append('not on actual glyph perimeter '+r[side])
            if identity not in aliases and r[side]!=r['canonical_'+side]:errors.append('physical/canonical glyph mismatch '+rid)
            if identity in aliases:
                owner=aliases[identity]['owner']
                if owner.endswith(':in'):
                    expected_owner=('enc.norm1.layernorm:out' if identity.startswith('enc.') else 'dec.norm2.layernorm:out')
                else:expected_owner=owner
                if r['canonical_src']!=expected_owner:errors.append('alias producer mismatch '+rid)
        if len(actual)<2 or math.dist(actual[-2],actual[-1])<18-1e-6:errors.append('short actual terminal '+rid)
    if seen!=set(routes):errors.append('layout/actual SVG coverage differs')
    expected=expected_pairs(layout['view'])
    for key in expected-set(canonical):errors.append('missing source-required connection '+str(key))
    for key in set(canonical)-expected:errors.append('source forbids canonical connection '+str(key))
    # Test complete chains across tensor value aliases; node IDs alone are insufficient.
    for key,rs in canonical.items():
        agenda=[key[0]];visited=set();used=set()
        while agenda:
            start=agenda.pop()
            if start in visited:continue
            visited.add(start)
            for r in rs:
                if r['src']!=start:continue
                used.add(r['id']);visited.add(r['dst'])
                aid,_,port=r['dst'].partition(':')
                if aid in aliases and port=='in':agenda.append(aid+':out')
        if key[1] not in visited or len(used)!=len(rs):errors.append('broken alias continuation '+str(key))
    return dict(passed=not errors,errors=errors,actual_paths=len(paths),canonical_connections=len(canonical),
                independently_expected_connections=len(expected),visible_glyphs=len(boxes),tensor_aliases=len(aliases))


def source_assertions(guide):
    source=guide/'sources/pytorch_transformer_original/transformer.py';text=source.read_text();tree=ast.parse(text)
    methods={n.name+'.'+f.name:ast.get_source_segment(text,f) for n in tree.body if isinstance(n,ast.ClassDef)
             for f in n.body if isinstance(f,ast.FunctionDef)}
    methods.update({n.name:ast.get_source_segment(text,n) for n in tree.body if isinstance(n,ast.FunctionDef)})
    guards={
        'scaled_dot_product_attention':['torch.matmul(q, k.transpose(-2, -1)) / math.sqrt(d_k)', 'scores.masked_fill(attn_mask, float("-inf"))', 'scores.masked_fill(padding, float("-inf"))', 'torch.softmax(scores, dim=-1)', 'torch.nan_to_num(attention_weights, nan=0.0)', 'torch.matmul(attention_weights, v)'],
        'PositionwiseFeedForward.__init__':['self.activation = nn.ReLU()'],
        'Transformer.forward':['memory = self.encode(src, src_key_padding_mask)', 'return self.generator(decoder_out)'],
        'MultiHeadAttention.forward':['self.w_q(query)','self.w_k(key)','self.w_v(value)','self._split_heads','self._combine_heads','self.w_o'],
        'PositionwiseFeedForward.forward':['self.linear2','self.activation','self.linear1'],
        'PositionalEncoding.forward':['x = x + self.pe','return self.dropout(x)'],
        'EncoderLayer.forward':['query=x, key=x, value=x','x + self.dropout1(attn_out)','x + self.dropout2(ffn_out)'],
        'DecoderLayer.forward':['query=x, key=x, value=x','query=x, key=memory, value=memory','x + self.dropout1(self_attn_out)','x + self.dropout2(cross_attn_out)','x + self.dropout3(ffn_out)'],
    }
    assertions=[]
    for method,tokens in guards.items():
        snippet=methods.get(method,'')
        for token in tokens:assertions.append(dict(method=method,requires=token,passed=re.sub(r'\s+','',token) in re.sub(r'\s+','',snippet)))
    sdpa=methods['scaled_dot_product_attention']
    assertions.append(dict(method='scaled_dot_product_attention',requires='mask before Softmax; Softmax before AV',passed=sdpa.index('scores = scores.masked_fill')<sdpa.index('attention_weights = torch.softmax')<sdpa.index('output = torch.matmul')))
    evidence=json.loads((guide/'generated/source_evidence.json').read_text())
    assertions.append(dict(method='source_sha256',passed=hashlib.sha256(source.read_bytes()).hexdigest()==evidence['sha256']))
    for symbol,data in evidence['symbols'].items():
        actual='\n'.join(text.splitlines()[data['start']-1:data['end']])
        assertions.append(dict(method=symbol,requires='evidence span matches original source',passed=actual==data['snippet']))
    return assertions


def run(guide):
    result=[];negatives=[];source=source_assertions(guide)
    for variant in (guide,guide/'variants/compact_mixed_flow'):
        for view,base in (('overview','figure1_overview'),('modules','figure2_modules'),('detailed','figure3_detailed')):
            layout=json.loads((variant/'generated'/('layout_'+view+'.json')).read_text())
            xml=ET.parse(variant/'generated'/(base+'.svg')).getroot()
            report=inspect(layout,xml)
            paths={'svg':variant/'generated'/(base+'.svg'),'png':variant/'generated'/(base+'.png'),
                   'layout':variant/'generated'/('layout_'+view+'.json'),'ir':variant/'generated/semantic_ir.json',
                   'evidence':variant/'generated/source_evidence.json'}
            hashes={name:hashlib.sha256(path.read_bytes()).hexdigest() for name,path in paths.items()}
            rerendered=hashlib.sha256(subprocess.check_output(['rsvg-convert',str(paths['svg'])])).hexdigest()
            if hashes['png']!=rerendered:report['errors'].append('PNG is not exact current SVG render');report['passed']=False
            ir=json.loads(paths['ir'].read_text());ids={e['id'] for e in ir['edges']};dispositions=layout['semantic_projection']['edge_dispositions']
            if len(dispositions)!=len(ids) or {d['edge'] for d in dispositions}!=ids:
                report['errors'].append('incomplete source edge dispositions');report['passed']=False
            traced={eid for r in layout['routes'] for eid in r['semantic_edges']}
            for d in dispositions:
                if d['status']=='rendered_source_connection' and d['edge'] not in traced:
                    report['errors'].append('disposition claims unrendered source edge '+d['edge']);report['passed']=False
                if d['status']=='declared_source_interface_alias' and next(e['kind'] for e in ir['edges'] if e['id']==d['edge'])!='interface_binding':
                    report['errors'].append('real dependency marked as interface '+d['edge']);report['passed']=False
            result.append(dict(variant='current' if variant==guide else 'compact',view=view,sha256=hashes,
                               artifacts={name:dict(path=str(path),sha256=hashes[name]) for name,path in paths.items()},
                               png_matches_fresh_svg_render=hashes['png']==rerendered,source_edge_dispositions=len(dispositions),**report))
            if view!='detailed':continue
            mutations={
                'memory_wrong_Q':lambda r:r['canonical_src']=='enc.norm2.layernorm:out' and r['canonical_dst']=='dec.cross.k:in',
                'residual_from_processed_output':lambda r:r['canonical_dst']=='enc.norm1.add:x',
                'PE_buffer_replaces_add':lambda r:r['canonical_src']=='src_pe.add:out',
                'K_Q_operands_swapped':lambda r:r['canonical_dst']=='enc.self.sdpa.qkt:k',
                'expanded_outer_frame':lambda r:r['canonical_dst']=='dec.cross.v:in',
                'FFN_bypasses_relu':lambda r:r['canonical_src']=='enc.ffn.linear1:out',
            }
            for name,predicate in mutations.items():
                mutant=copy.deepcopy(layout);route=next(r for r in mutant['routes'] if predicate(r))
                if name=='memory_wrong_Q':route['canonical_dst']='dec.cross.q:in'
                elif name=='residual_from_processed_output':route['canonical_src']='enc.self.wo:out'
                elif name=='PE_buffer_replaces_add':route['canonical_src']='src_pe.buffer:out'
                elif name=='K_Q_operands_swapped':route['canonical_dst']='enc.self.sdpa.qkt:q'
                elif name=='expanded_outer_frame':route['dst']='dec.cross:memory'
                elif name=='FFN_bypasses_relu':route['canonical_dst']='enc.ffn.linear2:in'
                report=inspect(mutant,xml);negatives.append(dict(variant=str(variant.relative_to(guide)) or 'current',mutation=name,rejected=not report['passed'],errors=report['errors']))
            # Mutate actual SVG only while keeping metadata/JSON untouched.
            for name in ('actual_svg_wrong_endpoint','actual_svg_missing_path','actual_svg_unregistered_path'):
                mutant=copy.deepcopy(xml);paths=[e for e in mutant if e.get('data-route-id')]
                if name=='actual_svg_wrong_endpoint':paths[0].set('d',paths[0].get('d')+' L 1,1')
                elif name=='actual_svg_missing_path':mutant.remove(paths[0])
                else:
                    extra=copy.deepcopy(paths[0]);extra.attrib.pop('data-route-id');mutant.append(extra)
                report=inspect(layout,mutant);negatives.append(dict(variant=str(variant.relative_to(guide)) or 'current',mutation=name,rejected=not report['passed'],errors=report['errors']))
            mutant=copy.deepcopy(layout);mutant['semantic_projection']['value_aliases'][0]['owner']='dec.cross.q:out'
            report=inspect(mutant,xml);negatives.append(dict(variant=str(variant.relative_to(guide)) or 'current',mutation='wrong_tensor_alias_owner',rejected=not report['passed'],errors=report['errors']))
    return dict(schema='independent-transformer-actual-svg-audit/1',source_assertions=source,views=result,
                negative_checks=negatives,passed=all(a['passed'] for a in source+result) and all(n['rejected'] for n in negatives),
                limitations=['Source contracts target the supplied adapter; not a universal semantic equivalence proof.',
                             'Historical snapshots and upstream reference SVG are excluded from certification.'])


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--guide',type=Path,default=GUIDE)
    ap.add_argument('--output',type=Path,default=HERE/'actual_transformer_audit.json');args=ap.parse_args()
    report=run(args.guide);args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(dict(passed=report['passed'],views=len(report['views']),paths=sum(v['actual_paths'] for v in report['views']),
                         source_assertions=len(report['source_assertions']),negative_checks=len(report['negative_checks'])),indent=2))
    if not report['passed']:raise SystemExit(1)


if __name__=='__main__':main()
