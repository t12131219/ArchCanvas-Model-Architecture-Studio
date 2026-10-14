#!/usr/bin/env python3
"""Static source/IR/actual-SVG arrow audit with deliberate wrong-operand cases.

Only our checker code is imported. Upstream model code is parsed as AST, never
imported or executed. Negative SVG cases change geometry AND its registration;
passing coordinate checks cannot hide a wrong producing/consuming operator.
"""
import argparse
import ast
import copy
import hashlib
import importlib
import json
import subprocess
import tempfile
import textwrap
import xml.etree.ElementTree as ET
from pathlib import Path
from arrow_semantics import source_endpoint_contracts, view_endpoint_checks
from verify import exported_view, read_json, source_checks

MODELS=('autoformer','itransformer','patchtst','timemixer')
VIEWS=('overview','modules','detailed')


def run(root,audit_root):
    cases=[];positive=[];records={}
    for key in MODELS:
        folder=root/key;ir=read_json(folder/'semantic_ir.json');ev=read_json(folder/'source_evidence.json')
        source=source_checks(folder,ev,ir);views={}
        for i,view in enumerate(VIEWS,1):
            layout=read_json(folder/f'layout_{view}.json')
            result=exported_view(folder/f'figure{i}_{view}.svg',layout,ev,ir,png=True)
            views[view]=layout;positive.append(dict(model=key,view=view,**result))
        records[key]=(ir,ev,views)

    # Exercise recursively expanded operand endpoints as well as the compact
    # formal views. These are audit fixtures, not a replacement layout preset.
    from layout import render
    expanded=[]
    for key in MODELS:
        ir,ev,_=records[key];model=importlib.import_module('adapters.'+key).build()
        model['view_overrides']={'2':{n['id']:2 for n in ir['nodes'] if n.get('mode')}}
        nodes={n['id']:n for n in ir['nodes']}
        def preserve_folds(node):
            if nodes[node['id']].get('fold_inline'):node['fold_inline']=True
            for child in node.get('items',[]):preserve_folds(child)
        preserve_folds(model['tree'])
        folder=audit_root/'expanded_views'/key;folder.mkdir(parents=True,exist_ok=True)
        svg=folder/'figure3_detailed.svg';layout=render(model,ev,ir,2,svg)
        layout['semantic_ir_sha256']=hashlib.sha256(json.dumps(ir,sort_keys=True).encode()).hexdigest()
        (folder/'layout_detailed.json').write_text(json.dumps(layout,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        subprocess.run(['rsvg-convert',str(svg),'-o',str(svg.with_suffix('.png'))],check=True)
        result=exported_view(svg,layout,ev,ir,png=True)
        expanded.append(dict(model=key,svg=str(svg),**result))
        records[key+'-expanded']=(ir,ev,{'detailed':layout})

    def reject(name,call):
        try:call()
        except (ValueError,KeyError) as exc:
            cases.append(dict(case=name,passed=True,rejection=str(exc)));return
        raise AssertionError('Negative case unexpectedly accepted: '+name)

    def mutate_ir(key,name,modify):
        ir,ev,_=records[key];bad=copy.deepcopy(ir);modify(bad)
        reject(name,lambda:source_endpoint_contracts(bad,ev))

    def edge_with(ir,**fields):
        return next(e for e in ir['edges'] if all(e.get(k)==v for k,v in fields.items()))
    def node_with(ir,identity):return next(n for n in ir['nodes'] if n['id']==identity)
    mutate_ir('itransformer','statistics replaced by normalized tensor',lambda ir:edge_with(ir,role='statistics').update(src_port='out'))
    mutate_ir('autoformer','cross memory mistakenly supplies Q',lambda ir:edge_with(ir,role='memory').update(dst_port='Q'))
    mutate_ir('autoformer','trend producer replaced by seasonal subtraction',lambda ir:node_with(ir,'af_dec_decomp1')['output_bindings'].update(trend='af_dec_decomp1_subtract'))
    mutate_ir('patchtst','previous scores replaced by Softmax weights',lambda ir:edge_with(ir,role='scores').update(src='patch_layer1_softmax',src_port='out'))
    mutate_ir('timemixer','wrong original component scale',lambda ir:edge_with(ir,role='component').update(src_port='season[0]'))
    mutate_ir('timemixer','retained intermediate missing',lambda ir:ir['edges'].remove(edge_with(ir,role='retained_scale')))
    mutate_ir('timemixer','final list input has wrong scale',lambda ir:node_with(ir,'tm.pdm1.season.list').update(main_input_operand='scale[0]'))
    mutate_ir('timemixer','season branch selects trend tuple field',lambda ir:edge_with(ir,role='dispatch',dst='tm.pdm1.season').update(src_port='trend'))

    def mutate_ast(key,name,symbol,old,new):
        ir,ev,_=records[key];bad=copy.deepcopy(ev)
        span=next(s for s in bad['symbols'].values() if s['symbol']==symbol)
        target=ast.dump(ast.parse(old,mode='eval').body,include_attributes=False)
        class Replace(ast.NodeTransformer):
            changed=0
            def visit(self,node):
                if ast.dump(node,include_attributes=False)==target:
                    self.changed+=1;return ast.copy_location(ast.parse(new,mode='eval').body,node)
                return super().visit(node)
        transform=Replace();tree=transform.visit(ast.parse(textwrap.dedent(span['snippet'])))
        if not transform.changed:raise AssertionError('AST negative target not present')
        span['snippet']=ast.unparse(ast.fix_missing_locations(tree))
        reject(name,lambda:source_endpoint_contracts(ir,bad))
    mutate_ast('autoformer','source cross operands changed','DecoderLayer.forward','self.cross_attention(x, cross, cross, attn_mask=cross_mask)','self.cross_attention(cross, x, x, attn_mask=cross_mask)')
    mutate_ast('autoformer','source decomposition return order changed','series_decomp.forward','(res, moving_mean)','(moving_mean, res)')
    mutate_ast('itransformer','source mean broadcast operand changed','Model.forecast','means[:, 0, :].unsqueeze(1).repeat(1, self.pred_len, 1)','x_enc[:, 0, :].unsqueeze(1).repeat(1, self.pred_len, 1)')
    mutate_ast('patchtst','source returns weights in score slot','_ScaledDotProductAttention.forward','(output, attn_weights, attn_scores)','(output, attn_scores, attn_weights)')
    mutate_ast('timemixer','source no longer retains season recurrence','MultiScaleSeasonMixing.forward','out_season_list.append(out_high.permute(0, 2, 1))','out_season_list.append(out_low.permute(0, 2, 1))')
    mutate_ast('timemixer','source trend output order not restored','MultiScaleTrendMixing.forward','out_trend_list.reverse()','out_trend_list.copy()')

    def mutate_svg(key,name,role,end,wrong,semantic_src=None):
        ir,ev,views=records[key];layout=copy.deepcopy(views['detailed'])
        route=next(r for r in layout['routes'] if r.get('role')==role and r.get('representation')=='typed_auxiliary' and (semantic_src is None or r.get('semantic_src')==semantic_src))
        port=route[end].rsplit(':',1)[1];point=layout['ports'][wrong][port]
        route[end]=wrong+':'+port;route['projected_'+end]=wrong
        route['points'][0 if end=='src' else -1]=point
        source_svg=(audit_root/'expanded_views'/key.removesuffix('-expanded') if key.endswith('-expanded') else root/key)/'figure3_detailed.svg'
        tree=ET.parse(source_svg)
        path=next(e for e in tree.iter() if e.get('data-route-id')==route['id'])
        path.set('d','M '+' L '.join(f'{x},{y}' for x,y in route['points']))
        # Both exported geometry and JSON now point at a registered wrong glyph.
        with tempfile.TemporaryDirectory(prefix='timeseries-wrong-operand-') as tmp:
            svg=Path(tmp)/'figure3_detailed.svg';tree.write(svg,encoding='utf-8',xml_declaration=True)
            reject(name,lambda:exported_view(svg,layout,ev,ir,png=False))
    mutate_svg('autoformer','actual trend arrow starts at seasonal residual','trend','src','af_dec_cross_add','af_dec_decomp1')
    mutate_svg('autoformer','actual memory arrow lands at cross residual Add','memory','dst','af_dec_cross_add')
    mutate_svg('itransformer','actual statistics arrow starts at embedding','statistics','src','it.embed_linear')
    mutate_svg('patchtst','actual previous score arrow starts at Softmax','scores','src','patch_layer1_softmax')
    mutate_svg('timemixer','actual original season arrow lands at MLP','component','dst','tm.pdm1.season.step0.linear2')
    mutate_svg('timemixer','actual retained scale arrow starts at activation','retained_scale','src','tm.pdm1.season.step0.gelu')
    mutate_svg('autoformer-expanded','expanded trend arrow starts at seasonal subtraction','trend','src','af_dec_decomp1_split','af_dec_decomp1')
    mutate_svg('autoformer-expanded','expanded memory arrow lands at lag correlation','memory','dst','af_dec_cross_corr')
    mutate_svg('patchtst-expanded','expanded previous scores enter weighted values','scores','dst','patch_layer2_weighted_values')
    mutate_svg('timemixer-expanded','expanded retained second recurrence originates at MLP','retained_scale','src','tm.pdm1.season.step1.linear2','tm.pdm1.season.step1')

    ir,ev,views=records['timemixer'];bad=copy.deepcopy(views['detailed'])
    first=next(r for r in bad['routes'] if r['representation']=='fork_branch' and r['dst']=='tm.pdm1.season:in')
    other=next(r for r in bad['routes'] if r['representation']=='fork_branch' and r['dst']=='tm.pdm1.trend:in')
    first.update(semantic_trace=other['semantic_trace'],dst=other['dst'],points=other['points'])
    reject('duplicate tuple branch omits season operand',lambda:view_endpoint_checks(bad,ir))

    ir,ev,views=records['patchtst'];bad=copy.deepcopy(views['detailed'])
    route=next(r for r in bad['routes'] if r['representation']=='dependency' and r['src']=='patch_layer1_raw_scores:out')
    route['semantic_trace']+=next(r['semantic_trace'] for r in bad['routes'] if r['representation']=='dependency' and r['src']=='patch_layer1_softmax:out')
    reject('contracted route skips exposed Softmax',lambda:view_endpoint_checks(bad,ir))

    # Reordering metadata alone must not affect interfaces: semantic edges,
    # rather than node-list position/rank, determine expanded endpoints.
    invariance=0
    for key,(ir,ev,views) in records.items():
        permuted=copy.deepcopy(ir);permuted['nodes'].reverse()
        for n in permuted['nodes']:n['rank']=-999
        for view,layout in views.items():view_endpoint_checks(layout,permuted);invariance+=1
    return dict(passed=True,mode='static AST + actual SVG/XML + independent source endpoint reconstruction',
                upstream_model_execution=False,positive_views=positive,
                expanded_audit_views=expanded,negative_cases=cases,negative_count=len(cases),node_order_invariance_views=invariance)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('generated',type=Path);p.add_argument('--report',type=Path,required=True)
    args=p.parse_args();args.report.parent.mkdir(parents=True,exist_ok=True);result=run(args.generated.resolve(),args.report.parent.resolve())
    args.report.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(f'PASS: {len(result["positive_views"])} formal + {len(result["expanded_audit_views"])} fully expanded SVG views, {result["negative_count"]} rejected wrong-operand cases, {result["node_order_invariance_views"]} node-order invariance checks')
    print(args.report)
if __name__=='__main__':main()
