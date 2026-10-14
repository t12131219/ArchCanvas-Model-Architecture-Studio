#!/usr/bin/env python3
"""Actual SVG residual teaching-annotation endpoint and misbinding checks."""
import copy
import hashlib
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]/'transformer_programmatic_guide'
EXPECTED={'main-F-to-norm':('F:out','add_norm:in','transformed_value'),
          'input-to-F':('input_x:out','F:in','tensor'),
          'retained-x-to-norm':('input_x:out','add_norm:skip','retained_input')}


def verify(svg,layout):
    errors=[]
    nodes={n.get('data-node-id'):n for n in svg.iter() if n.get('data-node-id')}
    paths={p.get('data-route-id'):p for p in svg.iter() if p.get('data-route-id')}
    for identity,bbox in layout['boxes'].items():
        g=nodes.get(identity)
        rect=next((r for r in g if r.tag.endswith('rect')),None) if g is not None else None
        actual=[float(rect.get(k)) for k in ('x','y','width','height')] if rect is not None else []
        if actual!=bbox:errors.append('actual glyph bbox '+identity)
    def point(value):
        node,port=value.split(':');x,y,w,h=layout['boxes'][node]
        # Derive true glyph ports from actual measured rectangles, not a label.
        return {'in':[x+w/2,y+h],'out':[x+w/2,y],'skip':[x,y+h/2]}[port]
    if set(paths)!=set(EXPECTED):errors.append('SVG route inventory')
    routes={r['id']:r for r in layout['routes']}
    if set(routes)!=set(EXPECTED):errors.append('layout route inventory')
    for identity,expected in EXPECTED.items():
        p=paths[identity];r=routes[identity]
        actual=(p.get('data-src'),p.get('data-dst'),p.get('data-role'))
        if actual!=expected:errors.append('actual SVG semantic binding '+identity)
        if (r['src'],r['dst'],r['role'])!=expected:errors.append('layout semantic binding '+identity)
        numbers=[float(x) for x in re.findall(r'-?\d+(?:\.\d+)?',p.get('d',''))]
        coords=[numbers[i:i+2] for i in range(0,len(numbers),2)]
        if coords!=r['points']:errors.append('actual SVG polyline '+identity)
        if coords[0]!=point(expected[0]) or coords[-1]!=point(expected[1]):errors.append('actual SVG glyph endpoint '+identity)
        if not p.get('marker-end'):errors.append('missing actual arrow marker '+identity)
        if any(a[0]!=b[0] and a[1]!=b[1] for a,b in zip(coords,coords[1:])):errors.append('nonorthogonal route '+identity)
        a,b=coords[-2:]
        if abs(a[0]-b[0])+abs(a[1]-b[1])<18:errors.append('late final turn '+identity)
    contract=next(e for e in svg.iter() if e.get('id')=='annotation-contract')
    if json.loads(contract.text)!=layout:errors.append('actual SVG annotation contract')
    return errors


def main():
    records=[];negatives=[]
    for variant,folder in [('current',ROOT),('compact_mixed_flow',ROOT/'variants/compact_mixed_flow')]:
        svgpath=folder/'mini_residual.svg';layoutpath=folder/'mini_residual_layout.json'
        svg=ET.fromstring(svgpath.read_text());layout=json.loads(layoutpath.read_text())
        errors=verify(svg,layout);assert not errors,errors
        records.append({'variant':variant,'passed':True,'scope':'Teaching annotation, not a specific model source graph',
                        'canvas':layout['canvas'],'actual_glyphs':len(layout['boxes']),'actual_typed_routes':len(layout['routes']),
                        'svg':str(svgpath),'svg_sha256':hashlib.sha256(svgpath.read_bytes()).hexdigest(),
                        'layout_sha256':hashlib.sha256(layoutpath.read_bytes()).hexdigest(),'model_executed':False})
        def mutate_case(name,fn):
            s=copy.deepcopy(svg);l=copy.deepcopy(layout);fn(s,l);found=verify(s,l)
            assert found,(variant,name)
            negatives.append({'variant':variant,'case':name,'rejected':True,'detected':found})
        def path(s,identity):return next(p for p in s.iter() if p.get('data-route-id')==identity)
        mutate_case('SVG retained input falsely bound to transformed F.out',
                    lambda s,l:path(s,'retained-x-to-norm').set('data-src','F:out'))
        def consistent_wrong(s,l):
            p=path(s,'retained-x-to-norm');p.set('data-src','F:out')
            r=next(r for r in l['routes'] if r['id']=='retained-x-to-norm');r['src']='F:out'
            r['points'][0]=l['ports']['F']['out'];p.set('d','M '+' L '.join(f'{x},{y}' for x,y in r['points']))
            next(e for e in s.iter() if e.get('id')=='annotation-contract').text=json.dumps(l)
        mutate_case('matching layout and SVG place residual origin at wrong real glyph',consistent_wrong)
        mutate_case('residual delivered to transformed input port',lambda s,l:path(s,'retained-x-to-norm').set('data-dst','add_norm:in'))
        def missing_input(s,l):
            g=next(g for g in s if g.get('data-node-id')=='input_x');s.remove(g)
        mutate_case('visible input x glyph omitted but annotation retained',missing_input)
    report={'passed':True,'annotation_count':len(records),'actual_typed_routes':sum(r['actual_typed_routes'] for r in records),
            'negative_case_count':len(negatives),'records':records,'negative_cases':negatives,
            'method':'Independent actual SVG XML rectangles, path endpoints, data-src/dst, arrow markers and layout comparison; source claim intentionally limited to a teaching equation.'}
    (HERE/'actual_mini_residual_audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k not in ('records','negative_cases')},ensure_ascii=False,indent=2))


if __name__=='__main__':main()
