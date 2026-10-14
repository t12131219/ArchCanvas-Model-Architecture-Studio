#!/usr/bin/env python3
"""Generate four source-reviewed time-series model diagrams, without model execution."""
from __future__ import annotations
import argparse
import hashlib
import html
import importlib
import json
from pathlib import Path
import shutil
import subprocess

from evidence import collect, semantic_ir
from layout import render, validate
from arrow_semantics import source_endpoint_contracts, view_endpoint_checks

HERE=Path(__file__).resolve().parent
KEYS=['autoformer','itransformer','patchtst','timemixer']
VIEWS=['overview','modules','detailed']
CONFIG_FILES={
 'autoformer':['Autoformer-main/run.py'],
 'itransformer':['iTransformer/run.py','iTransformer/scripts/multivariate_forecasting/ETT/iTransformer_ETTh1.sh'],
 'patchtst':['PatchTST/PatchTST_supervised/run_longExp.py'],
}
VIEW_OVERRIDES={
 'autoformer':{'2':{'af_dec_self':3,'af_dec_cross':3,'af_dec_ffn':3,'af_dec_embedding':3,
                   'af_dec_norm':3,'af_memory':3,'af_enc_decomp2':3,
                   'af_dec_decomp1':3,'af_dec_decomp2':3,'af_dec_decomp3':3}},
 'timemixer':{'2':{f'tm.pdm1.{kind}.step{step}':3 for kind in ('season','trend') for step in (1,2)}},
}


def save(path,data):
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')


def gallery(out,models):
    cards=[]
    for model in models:
        key,name=model['key'],model['name']
        cards.append(f'<article><h2>{html.escape(name)}</h2><p><a href="{key}/index.html">三种粒度与证据</a> · <a class="download" href="{key}/figure1_overview.svg">打开 SVG</a></p><a class="image" href="{key}/figure1_overview.svg"><img loading="lazy" src="{key}/figure1_overview.svg" alt="{name} 程序化源码架构图"></a></article>')
    doc='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>时间序列模型 · 源码架构图原型</title>
<style>body{font-family:system-ui,sans-serif;background:#edf0f5;color:#263348;margin:32px}main{max-width:1800px;margin:auto}h1{font-size:30px}nav{display:flex;gap:12px;position:sticky;top:0;background:#edf0f5;padding:16px 0;z-index:1}button,a{color:#315479}button{border:1px solid #a7b8cd;border-radius:8px;padding:10px 20px;background:white;cursor:pointer}button.active{background:#263348;color:white}.grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:24px}article{padding:24px;background:white;border-radius:12px}img{display:block;width:100%;height:auto}h2{margin-top:0}@media(max-width:900px){.grid{grid-template-columns:1fr}}</style>
<main><h1>四种模型，共享一套程序化绘图引擎</h1><p>源码静态取证 · 显式模型适配器 · 统一自底向上 · 逐图源码标记。配置与折叠边界见各模型说明。</p>
<nav><button class="active" data-view="1_overview">概览</button><button data-view="2_modules">模块</button><button data-view="3_detailed">详细</button></nav><div class="grid">'''+''.join(cards)+'''</div></main><script>
document.querySelectorAll('button').forEach(b=>b.onclick=()=>{document.querySelectorAll('button').forEach(x=>x.classList.toggle('active',x===b));document.querySelectorAll('article').forEach(a=>{const i=a.querySelector('img');const key=i.getAttribute('src').split('/')[0];const path=key+'/figure'+b.dataset.view+'.svg';i.src=path;a.querySelector('.image').href=path;a.querySelector('.download').href=path;});});
</script></html>'''
    (out/'index.html').write_text(doc,encoding='utf-8')


def model_index(model,folder,evidence):
    cards=''.join(f'<section id="{view}"><h2>{title}</h2><p><a href="figure{i}_{view}.svg">SVG</a> · <a href="layout_{view}.json">布局记录</a></p><img src="figure{i}_{view}.svg" alt="{view}"></section>' for i,(view,title) in enumerate(zip(VIEWS,['概览','模块','详细']),1))
    doc=f'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>{model['name']} 源码架构图</title>
<style>body{{font-family:system-ui;background:#edf0f5;color:#263348;margin:24px}}main{{max-width:1600px;margin:auto}}section{{background:white;padding:24px;margin-top:24px;border-radius:12px}}img{{width:100%;height:auto}}a{{color:#315479}}nav{{position:sticky;top:0;background:#edf0f5;padding:16px 0}}pre{{white-space:pre-wrap}}</style><main>
<h1>{model['name']} · 三种展示粒度</h1><nav><a href="../index.html">四模型总览</a> · <a href="#overview">概览</a> · <a href="#modules">模块</a> · <a href="#detailed">详细</a> · <a href="source_evidence.json">源码证据</a> · <a href="semantic_ir.json">语义 IR</a> · <a href="layout_checks.json">布局检查</a> · <a href="source_map.md">逐节点源码映射</a></nav>
<details><summary>所选预测配置</summary><pre>{html.escape(json.dumps(model['profile'],ensure_ascii=False,indent=2))}</pre></details>{cards}</main></html>'''
    (folder/'index.html').write_text(doc,encoding='utf-8')


def source_map(model,ir,evidence,folder):
    lines=[f'# {model["name"]}：逐节点源码映射','',
           '每个图框的 `E###` 对应下表中的源码范围；SVG 悬停可查看来源。节点 ID 跨视图稳定。展开接口通过 IR 边递归绑定到实际内部算子；隐藏的整个模块才投影到最近可见祖先。',
           '这些是人工审阅适配器的绑定，不是模型执行轨迹。完整片段及文件摘要见 `source_evidence.json`。','',
           '| 证据 ID | 文件与符号 | 行号 |','|---|---|---|']
    for key,e in evidence['symbols'].items():
        lines.append(f'| {e["evidence_id"]} | [{e["path"]}](sources/{e["path"]}) · `{e["symbol"]}` | {e["start"]}–{e["end"]} |')
    lines+=['','| 节点 ID | 图中名称 | 静态 shape | 源码证据 | 参数身份 / 实例族 |','|---|---|---|---|---|']
    for n in ir['nodes']:
        parameter=n.get('param_identity',n.get('parameter',n.get('parameter_scope','—')))
        if n.get('repeat'):parameter+='; '+str(n['repeat'])
        lines.append('| '+' | '.join(str(v).replace('|',' / ').replace('\n',' ') for v in [n['id'],n['label'],n.get('shape',''),','.join(n['source_evidence']),parameter])+' |')
    lines+=['','## 参考图修正','']+[f'- {c}' for c in model['corrections']]
    lines+=['','## 模型事实','']+[f'- {f}' for f in model['facts']]
    (folder/'source_map.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--model',choices=['all']+KEYS,default='all')
    p.add_argument('--archive-dir',type=Path,default=HERE.parent,help='directory containing the four reviewed zip archives')
    p.add_argument('--out',type=Path,default=HERE/'generated')
    p.add_argument('--png',action='store_true',help='also render PNG previews using rsvg-convert')
    args=p.parse_args()
    if args.png and shutil.which('rsvg-convert') is None:p.error('--png requires rsvg-convert')
    out=args.out.resolve();out.mkdir(parents=True,exist_ok=True)
    models=[];reports=[]
    for key in (KEYS if args.model=='all' else [args.model]):
        model=importlib.import_module('adapters.'+key).build()
        model['profile'].setdefault('mode','eval')
        model['view_overrides']=VIEW_OVERRIDES.get(key,{})
        # Fold display-only details of minor operators; retain every node in the IR.
        # Axis inversions at the model interface and patch construction remain visible.
        def fold_minor(node):
            label=node['label'].lower()
            if not node.get('items') and (label in ('dropout','attention dropout','residual dropout','output dropout','embedding dropout','head dropout') or
                (key=='itransformer' and node['id'].split('.')[-1] in ('ffn_transpose_in','ffn_transpose_out'))):
                node['fold_inline']=True
            for child in node.get('items',[]):fold_minor(child)
        fold_minor(model['tree'])
        model['config_files']=model.get('config_files',CONFIG_FILES.get(key,[]))
        folder=out/key;folder.mkdir(parents=True,exist_ok=True)
        evidence=collect(model,args.archive_dir,folder)
        ir=semantic_ir(model,evidence)
        source_endpoint_contracts(ir,evidence)
        ir_digest=hashlib.sha256(json.dumps(ir,sort_keys=True).encode()).hexdigest()
        save(folder/'source_evidence.json',evidence);save(folder/'semantic_ir.json',ir)
        save(folder/'profile.json',model['profile'])
        checks=[]
        for level,view in enumerate(VIEWS):
            svg=folder/f'figure{level+1}_{view}.svg'
            layout=render(model,evidence,ir,level,svg)
            layout['semantic_ir_sha256']=ir_digest
            save(folder/f'layout_{view}.json',layout)
            check=validate(layout)|dict(view=view,semantic_ir_sha256=ir_digest,
                                       semantic_endpoints=view_endpoint_checks(layout,ir))
            checks.append(check)
            if args.png:
                subprocess.run(['rsvg-convert',str(svg),'-o',str(svg.with_suffix('.png'))],check=True)
            print(f'{key:13} {view:8} {layout["canvas"]}  '+('PASS' if check['passed'] else f'FAIL {len(check["errors"])}'))
            for error in check['errors'][:15]:print('  '+error)
        save(folder/'layout_checks.json',checks)
        model_index(model,folder,evidence);source_map(model,ir,evidence,folder)
        models.append(model);reports.append(dict(model=key,passed=all(c['passed'] for c in checks),views=checks))
    save(out/'validation_summary.json',reports);gallery(out,models)
    print('Preview:',out/'index.html')
    if not all(r['passed'] for r in reports):raise SystemExit(1)


if __name__=='__main__':main()
