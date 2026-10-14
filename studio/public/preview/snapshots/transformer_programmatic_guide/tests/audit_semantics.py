#!/usr/bin/env python3
"""Source/IR/layout/XML mutation regression; never imports the model."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import xml.etree.ElementTree as ET
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from source_semantics import derive_contracts, validate_source_semantics
from semantic_routes import validate_semantics
from check_svg_routes import diagnose

HERE=Path(__file__).resolve().parents[1]
read=lambda p:json.loads(p.read_text())
def run():
    folder=HERE/'generated'
    ir=read(folder/'semantic_ir.json');evidence=read(folder/'source_evidence.json')
    assert not validate_source_semantics(ir,evidence)
    records=[]
    def reject(name,issues):
        assert issues, 'wrong semantic accepted: '+name
        records.append(dict(case=name,rejected=True,reason=issues[0]))
    def node(data,id):return next(n for n in data['nodes'] if n['id']==id)
    for name,modify in [
        ('cross Q incorrectly comes from memory', lambda d:node(d,'dec.cross.q').update(input_identity='memory')),
        ('cross source interface sends memory into Q',lambda d:next(e for e in d['edges'] if e['src']=='dec.cross' and e['dst']=='dec.cross.q' and e['kind']=='interface_binding').update(src_port='memory')),
        ('cross cached alias sends decoder state into K',lambda d:node(d,'dec.cross')['port_bindings']['in'].update(node='dec.cross.k')),
        ('cross mask incorrectly uses target padding',lambda d:node(d,'dec.cross.sdpa.mask').update(mask_inputs=['tgt_key_padding_mask'])),
        ('cross K length incorrectly becomes T',lambda d:node(d,'dec.cross.k').update(output_shape='[B,T,D]')),
        ('residual tap incorrectly moves to branch output',lambda d:next(e for e in d['edges'] if e['dst']=='dec.norm2' and e['dst_port']=='skip').update(src='dec.cross')),
        ('explanatory probability Softmax becomes forward',lambda d:node(d,'probabilities').update(executed_in_forward=True)),
        ('attention incorrectly escapes decoder layer',lambda d:node(d,'dec.cross').update(parent='model')),
    ]:
        bad=copy.deepcopy(ir);modify(bad);reject(name,validate_source_semantics(bad,evidence))
    for name,symbol,old,new in [
        ('source Q/K/V swap','DecoderLayer.forward','query=x,\n            key=memory','query=memory,\n            key=x'),
        ('source target mask replaces memory mask','DecoderLayer.forward','key_padding_mask=memory_key_padding_mask','key_padding_mask=tgt_key_padding_mask'),
        ('source residual becomes Pre-LN','DecoderLayer.forward','self.norm2(x + self.dropout2(cross_attn_out))','x + self.dropout2(self.norm2(cross_attn_out))'),
    ]:
        bad=copy.deepcopy(evidence['symbols']);assert old in bad[symbol]['snippet']
        bad[symbol]['snippet']=bad[symbol]['snippet'].replace(old,new)
        try:derive_contracts(bad)
        except ValueError as exc:reject(name,[str(exc)])
        else:raise AssertionError('bad source AST accepted '+name)
    layout=read(folder/'layout_detailed.json')
    bad=copy.deepcopy(layout);bad['semantic_projection']['junction_markers'][0]['canonical_src']='forged:out'
    reject('junction claims a different source tensor',validate_semantics(bad,ir))
    bad=copy.deepcopy(layout);bad['semantic_projection']['junction_markers'][0]['point'][0]+=12
    reject('junction leaves its registered routes',validate_semantics(bad,ir))
    bad=copy.deepcopy(layout);bad['semantic_projection']['physical_routing']['binding_authority']='geometry'
    reject('physical routing attempts to replace source authority',validate_semantics(bad,ir))
    bad=copy.deepcopy(layout);bad['routes'][0]['port_authority']['target']='src_pe.add:x'
    reject('physical presentation claims a different canonical field',validate_semantics(bad,ir))
    bad=copy.deepcopy(layout);next(b for b in bad['boxes'] if b['id']=='dec.cross.q')['parent']=None
    reject('layout drops source containment',validate_semantics(bad,ir))
    bad=copy.deepcopy(layout);next(r for r in bad['routes'] if r['canonical_dst']=='dec.cross.k:in')['canonical_dst']='dec.cross.q:in'
    reject('actual cross memory route claims Q',validate_semantics(bad,ir))
    bad=copy.deepcopy(layout)
    next(v for v in bad['semantic_projection']['value_aliases'] if v['id']=='enc.memory.value')['owner']='dec.norm3:out'
    reject('Memory box aliases the wrong producing value',validate_semantics(bad,ir))
    bad=copy.deepcopy(layout)
    for r in bad['routes']:
        if r['src']=='enc.memory.value:out':r['src']=r['canonical_src']
    reject('memory line bypasses the displayed Memory box',validate_semantics(bad,ir))
    bad=copy.deepcopy(layout)
    next(a for a in bad['attachments'] if a['owner']=='enc.self.k.value')['owner']='enc.self.q.value'
    reject('K label follows a different source value',validate_semantics(bad,ir))
    bad=copy.deepcopy(layout)
    next(a for a in bad['attachments'] if a['kind']=='value-snapshot')['owner']='enc.ffn'
    reject('hidden snapshot loses its producing operator',validate_semantics(bad,ir))
    with tempfile.TemporaryDirectory(prefix='transformer-semantic-negative-') as tmp:
        out=Path(tmp)
        for name in ['semantic_ir.json','source_evidence.json','layout_detailed.json']:(out/name).write_bytes((folder/name).read_bytes())
        for name,change in [
            ('SVG node claims wrong mask domain',lambda tree:next(e for e in tree.iter() if e.get('data-node-id')=='dec.cross.sdpa').set('data-mask-inputs','["tgt_mask"]')),
            ('SVG loses source digest',lambda tree:next(e for e in tree.iter() if e.get('id')=='source-binding').clear()),
            ('SVG rounded shaft protrudes past arrow endpoint',lambda tree:next(e for e in tree.iter() if e.get('data-route-id')).set('stroke-linecap','round')),
            ('SVG label follows wrong glyph',lambda tree:next(e for e in tree.iter() if e.get('data-follow-owner')=='enc.self.k.value').set('data-follow-owner','enc.self.q.value')),
            ('SVG edge caption claims a different wire',lambda tree:next(e for e in tree.iter() if e.get('data-follow-kind')=='edge-label').set('data-follow-edge','forged-route')),
            ('SVG junction retains a stale coordinate',lambda tree:next(e for e in tree.iter() if e.get('data-junction-id')).set('cx','0')),
            ('SVG junction claims another tensor',lambda tree:next(e for e in tree.iter() if e.get('data-junction-id')).set('data-junction-source','forged:out')),
        ]:
            tree=ET.parse(folder/'figure3_detailed.svg');change(tree);path=out/'figure3_detailed.svg';tree.write(path)
            result=diagnose(path,18,.1);reject(name,result['semantic_errors']+result['svg_layout_errors'])
    bad=copy.deepcopy(layout)
    next(a for a in bad['attachments'] if a['kind']=='edge-label')['route']='forged-route'
    reject('caption claims another source connection',validate_semantics(bad,ir))
    bad=copy.deepcopy(layout);bad['semantic_projection']['physical_routing'].pop('caption_policy')
    reject('caption source authority policy removed',validate_semantics(bad,ir))
    bad=copy.deepcopy(layout);bad['semantic_projection']['physical_routing'].pop('border_policy')
    reject('painted border clearance policy removed',validate_semantics(bad,ir))
    positive=[]
    for i,view in enumerate(['overview','modules','detailed'],1):
        result=diagnose(folder/f'figure{i}_{view}.svg',18,.1)
        for key in ['short_terminal','border_collinear','endpoint_errors','endpoint_unregistered','semantic_errors','svg_layout_errors','downward_dependency_segments']:assert not result[key],(view,key,result[key])
        positive.append(dict(view=view,paths=result['path_count'],passed=True))
    result=dict(passed=True,model_executed=False,positive_views=positive,negative_cases=records,negative_count=len(records))
    (folder/'semantic_negative_checks.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print('PASS:',len(positive),'views;',len(records),'source/IR/layout/SVG corruptions rejected')
if __name__=='__main__':run()
