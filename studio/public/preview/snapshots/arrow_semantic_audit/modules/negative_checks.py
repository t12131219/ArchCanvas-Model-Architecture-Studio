#!/usr/bin/env python3
"""Mutate actual SVG endpoints/typed receipts while retaining valid geometry."""
from __future__ import annotations
import copy
import importlib.util
import json
from pathlib import Path
import re
import shutil
import tempfile
import xml.etree.ElementTree as ET

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('independent_module_endpoint_audit',HERE/'audit.py')
audit=importlib.util.module_from_spec(spec);spec.loader.exec_module(audit)


def run():
    results=[]
    with tempfile.TemporaryDirectory(prefix='module-arrow-negatives-') as temp:
        temp=Path(temp)
        def case(name,key,mutate,expected):
            folder=temp/name
            shutil.copytree(audit.GUIDE/'generated'/key,folder)
            path=folder/'layout_detailed.json';layout=json.loads(path.read_text())
            svgpath=folder/'figure3_detailed.svg';svg=ET.parse(svgpath)
            mutate(layout,svg)
            path.write_text(json.dumps(layout,ensure_ascii=False,indent=2)+'\n')
            svg.write(svgpath,encoding='unicode',xml_declaration=False)
            report=next(v for v in audit.audit_folder(folder) if v['view']=='detailed')
            kinds={p['kind'] for p in report['problems']}
            rejected=not report['passed'] and expected in kinds
            assert rejected,(name,report['problems'])
            results.append({'case':name,'module':key,'rejected':rejected,
                            'expected_detection':expected,'actual_detections':sorted(kinds),
                            'diagram_source_unchanged':True,'canvas_and_boxes_unchanged':True})
        def route(layout,src=None,dst=None,port=None):
            return next(r for r in layout['routes'] if (src is None or r['semantic_src']==src)
                        and (dst is None or r['semantic_dst']==dst) and (port is None or r['semantic_src_port']==port))
        def svg_route(svg,r):return next(p for p in svg.iter() if p.get('data-route-id')==r['id'])
        def sync_svg(svg,r):
            p=svg_route(svg,r);p.set('data-endpoint-binding',json.dumps(r['endpoint_binding']))
            p.set('d','M '+' L '.join(f'{x},{y}' for x,y in r['points']))
        def false_receipt(layout,svg):
            r=route(layout,'manual_fused_bn.stats','manual_fused_bn.shift','mean')
            p=svg_route(svg,r);binding=copy.deepcopy(r['endpoint_binding'])
            binding['source']['node']='manual_fused_bn.variance';p.set('data-endpoint-binding',json.dumps(binding))
        case('actual_svg_receipt_points_to_wrong_sibling','manual_fused_bn',false_receipt,'SVG endpoint binding mismatch')
        def wrong_result_field(layout,svg):
            r=route(layout,'flow_batchnorm.stats','flow_batchnorm.normalize','var')
            r['endpoint_binding']['source']['port']='mean'
            node,side=audit.endpoint(r['src']);layout['port_fields'][node][side]['field']='mean'
            sync_svg(svg,r)
        case('consistent_svg_layout_receipt_var_confused_with_mean','flow_batchnorm',wrong_result_field,'wrong typed field at actual glyph')
        def sibling(layout,svg):
            r=route(layout,'manual_fused_bn.stats','manual_fused_bn.shift','mean')
            # Same x and valid upward polyline: only its source is moved from
            # moments to the distinct visible variance output.
            replacement='manual_fused_bn.variance';side='out'
            point=list(layout['ports'][replacement][side]);r['points'][0]=point
            r['src']=replacement+':'+side;r['projected_src']=replacement
            r['endpoint_binding']['source']={'node':replacement,'port':'out','projection':'exact'}
            r['endpoint_binding']['rendered_src']=r['src']
            layout['port_fields'].setdefault(replacement,{})[side]={'field':'out','side':'out','slot_field':'out'}
            sync_svg(svg,r)
        case('physical_svg_endpoint_moved_to_wrong_real_leaf','manual_fused_bn',sibling,'wrong or unbound visible endpoint')
        def split_output(layout,svg):
            r=route(layout,'flow_sequential.first','flow_sequential.add0','logdet')
            r['endpoint_binding']['source']['port']='features'
            node,side=audit.endpoint(r['src']);layout['port_fields'][node][side]['field']='features'
            sync_svg(svg,r)
        case('logdet_uses_feature_field_with_same_geometry','flow_sequential',split_output,'wrong typed field at actual glyph')
        def folded_output(layout,svg):
            r=route(layout,'highway.layer1.add','highway.output')
            binding=r['endpoint_binding']['source'];binding['port']='highway.layer1.carry:out'
            node,side=audit.endpoint(r['src']);layout['port_fields'][node][side]['field']=binding['port']
            sync_svg(svg,r)
        case('folded_output_alias_replaced_by_wrong_hidden_field','highway',folded_output,'wrong typed field at actual glyph')
        def retained_value(layout,svg):
            r=next(r for r in layout['routes'] if r['role']=='retained_input')
            r['endpoint_binding']['source']['node']='frn.square'
            sync_svg(svg,r)
        case('retained_original_x_replaced_by_squared_x','frn_tlu',retained_value,'wrong typed field at actual glyph')
        def shape_operand(layout,svg):
            r=next(r for r in layout['routes'] if r['role']=='shape_dependency')
            r['endpoint_binding']['source']['port']='out'
            node,side=audit.endpoint(r['src']);layout['port_fields'][node][side]['field']='out'
            sync_svg(svg,r)
        case('shape_dependency_changed_to_tensor_value_at_same_slot','glow_affine_coupling',shape_operand,'wrong typed field at actual glyph')
        def missing_disposition(layout,svg):layout['endpoint_projections'].pop()
        case('ir_dependency_disappears_without_folded_or_rendered_disposition','layernorm_lstm_cell',missing_disposition,'IR disposition coverage')
    report={'passed':True,'negative_case_count':len(results),'cases':results,'source_executed':False,
            'method':'Copy real generated files; change actual SVG XML and/or matching layout receipts; audit independently recomputes the valid endpoint from fixed IR.'}
    (HERE/'actual_svg_negative_checks.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(report,ensure_ascii=False,indent=2))


if __name__=='__main__':run()
