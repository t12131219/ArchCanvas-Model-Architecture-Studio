#!/usr/bin/env python3
"""Add route-owned captions to expanded audit views using adapter contracts.

Match the same canonical auxiliary dependency and the emitted text, not a
nearby route. Retain the expanded view's geometry and all model facts.
"""
import copy,json,xml.etree.ElementTree as ET
from pathlib import Path
HERE=Path(__file__).resolve().parent
PROTO=HERE.parents[1]
ET.register_namespace('','http://www.w3.org/2000/svg')

def main():
    count=0
    fields=['semantic_src','semantic_dst','semantic_src_port','semantic_dst_port','semantic_trace']
    for folder in (HERE/'expanded_views').iterdir():
        lp=folder/'layout_detailed.json';sp=folder/'figure3_detailed.svg'
        if not lp.exists():continue
        original=json.loads(lp.read_text())
        native=json.loads((PROTO/'timeseries_programmatic_guide/generated'/folder.name/'layout_detailed.json').read_text())
        tree=ET.parse(sp);labels=[]
        for source in native.get('edge_labels',[]):
            route=next(r for r in native['routes'] if r['id']==source['route'])
            refs=[r for r in original['routes'] if all(r.get(k)==route.get(k) for k in fields)]
            texts=[e for e in tree.getroot() if e.tag.endswith('}text') and ' | '.join(''.join(t.itertext()) for t in e)==source['text']]
            if not refs or not texts:continue # an audit frontier may fold this dependency
            if len(refs)!=1 or len(texts)!=1:raise ValueError('Ambiguous caption '+folder.name+' '+source['text'])
            element=texts[0];r=refs[0];size=float(element.get('font-size'));x,y=float(element.get('x')),float(element.get('y'))
            lines=list(element);w=max(len(''.join(t.itertext())) for t in lines)*size*.62
            left=x-w/2 if element.get('text-anchor')=='middle' else x-w if element.get('text-anchor')=='end' else x
            label=dict(id=source['id'],route=r['id'],bbox=[left,y-size,w,size*1.18*len(lines)],text=source['text'],
                       source_binding={k:r[k] for k in fields if k in r},
                       authority=dict(adapter='timeseries_programmatic_guide/layout.py',native_caption=source['id'],canonical_trace=copy.deepcopy(r['semantic_trace'])))
            element.set('data-edge-label-id',label['id']);element.set('data-follow-edge',label['route']);labels.append(label)
        original['edge_labels']=labels;lp.write_text(json.dumps(original,ensure_ascii=False,indent=2)+'\n');tree.write(sp,encoding='unicode');count+=len(labels)
    print('Registered expanded-view route captions:',count)
if __name__=='__main__':main()
