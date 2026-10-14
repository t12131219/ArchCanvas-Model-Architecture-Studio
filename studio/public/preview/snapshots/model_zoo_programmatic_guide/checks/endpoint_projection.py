#!/usr/bin/env python3
"""Nested interface, field order, and actual-SVG tamper regression checks."""
from pathlib import Path
import copy,json,sys,tempfile,xml.etree.ElementTree as ET
HERE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(HERE))
from endpoint_binding import EndpointResolver
from verify import exported_view

def read(path):return json.loads(path.read_text())
def main():
    expectations=[
      ('unet','unet_enc1','skip','src',[('unet_enc1_block_relu2','out')]),
      ('alexnet','alex.classifier','out','src',[('alex.fc3','out')]),
      ('graphnet','graphnet.adjacency','out','src',[('graphnet.buffer','out')]),
      ('convvae','convvae.sample_args','out','src',[('convvae.retain_mu','out'),('convvae.noise_product','out')]),
      ('graphnet','graphnet.operands','out','src',[('graphnet.expand','out'),('graphnet.features_operand','out')]),
    ]
    positives=[]
    for key,node,port,direction,expected in expectations:
        ir=read(HERE/'generated'/key/'semantic_ir.json')
        for order in ('original','reversed-storage'):
            candidate=copy.deepcopy(ir)
            if order!='original':candidate['nodes'].reverse();candidate['edges'].reverse()
            resolver=EndpointResolver(candidate,[n['id'] for n in candidate['nodes']])
            actual=[(x['node'],x['port']) for x in resolver.resolve(node,port,direction)]
            assert actual==expected,(key,node,actual,expected)
            positives.append(dict(model=key,scope=node,port=port,storage_order=order,resolved=actual))
    folder=HERE/'generated/unet';ir=read(folder/'semantic_ir.json');ev=read(folder/'source_evidence.json')
    layout=read(folder/'layout_detailed.json');svg=folder/'figure3_detailed.svg'
    exported_view(svg,layout,ev,ir,True)
    negative=[]
    with tempfile.TemporaryDirectory(prefix='arrow-semantic-') as tmp:
        for label,kind in [('valid geometry but wrong producer field','field'),
                           ('route hidden by forged alias disposition','missing_route'),
                           ('layout and SVG agree on wrong nested glyph','glyph')]:
            bad=copy.deepcopy(layout);tree=ET.parse(svg)
            route=next(r for r in bad['routes'] if r['role']=='skip_concat' and r['semantic_src']=='unet_enc1')
            path=next(e for e in tree.getroot().iter() if e.get('data-route-id')==route['id'])
            if kind=='field':
                route['endpoint_binding']['source']['port']='wrong_tensor'
                path.set('data-endpoint-binding',json.dumps(route['endpoint_binding'],sort_keys=True))
            elif kind=='glyph':
                route['endpoint_binding']['source']['node']='unet_enc1_block_bn2'
                path.set('data-endpoint-binding',json.dumps(route['endpoint_binding'],sort_keys=True))
            else:
                bad['routes'].remove(route)
                for parent in tree.getroot().iter():
                    if path in list(parent):parent.remove(path);break
                for record in bad['endpoint_projections']:
                    if record.get('route')==route['id']:
                        record.update(status='alias',reason='forged hidden interface');record.pop('route',None)
            target=Path(tmp)/'bad.svg';tree.write(target)
            try:exported_view(target,bad,ev,ir)
            except ValueError as exc:negative.append(dict(case=label,rejected=True,reason=str(exc)))
            else:raise AssertionError('Accepted semantic endpoint corruption: '+label)
    report=dict(passed=True,positive=positives,negative=negative,model_executed=False,
                limitation='Static source contracts and actual SVG bindings; no numerical-equivalence claim.')
    out=HERE.parent/'arrow_semantic_audit/modelzoo/projection_negative_checks.json'
    out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print('PASS:',len(positives),'interface/order checks;',len(negative),'actual SVG corruptions rejected')
if __name__=='__main__':main()
