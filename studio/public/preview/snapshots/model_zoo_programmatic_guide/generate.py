#!/usr/bin/env python3
"""Generate reviewed source-backed architecture batches, entirely offline."""
from __future__ import annotations
import argparse
import hashlib
import html
import importlib
import json
from pathlib import Path
import shutil
import subprocess
from evidence import collect,semantic_ir
from layout import render,validate
from theme import configure,manifest
from models import KEYS,VIEWS,BATCHES,BATCH_LABELS,selected

HERE=Path(__file__).resolve().parent


def save(path,data):path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')


def gallery(out,models,filename='index.html'):
    cards=[]
    for model in models:
        key,name=model['key'],html.escape(model['name'])
        cards.append(f'<article><h2>{name}</h2><p><a href="{key}/index.html">三种粒度与源码证据</a> · <a class="download" href="{key}/figure1_overview.svg">打开 SVG</a></p><a class="image" href="{key}/figure1_overview.svg"><img src="{key}/figure1_overview.svg" alt="{name} 程序化图"></a></article>')
    doc='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>跨模型架构图原型</title><style>body{font-family:DejaVu Sans,Arial,sans-serif;background:#edf0f5;color:#172336;margin:32px}main{max-width:1800px;margin:auto}nav{display:flex;gap:12px;position:sticky;top:0;background:#edf0f5;padding:16px 0;z-index:1}button,a{color:#315479}button{border:1px solid #718299;border-radius:8px;padding:10px 20px;background:white;cursor:pointer}button.active{background:#263348;color:white}.grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:24px}article{padding:24px;background:white;border-radius:12px}img{display:block;width:100%;height:auto}h2{margin-top:0}@media(max-width:900px){.grid{grid-template-columns:1fr}}</style><main><h1>六类模型，共享 Transformer 风格</h1><p>固定版本源码 · 显式适配器 · 自底向上 · 模块与参数身份可追溯。</p><nav><button class="active" data-view="1_overview">概览</button><button data-view="2_modules">模块</button><button data-view="3_detailed">详细</button></nav><div class="grid">'''+''.join(cards)+'''</div></main><script>document.querySelectorAll('button').forEach(b=>b.onclick=()=>{document.querySelectorAll('button').forEach(x=>x.classList.toggle('active',x===b));document.querySelectorAll('article').forEach(a=>{const i=a.querySelector('img'),key=i.getAttribute('src').split('/')[0],path=key+'/figure'+b.dataset.view+'.svg';i.src=path;a.querySelector('.image').href=path;a.querySelector('.download').href=path})});</script></html>'''
    label=next((BATCH_LABELS[b]+' · ' for b in BATCHES if filename=='index_'+b+'.html'),'')
    doc=doc.replace('六类模型，共享 Transformer 风格',f'{label}{len(models)} 个模型，共享 Transformer 风格')
    doc=doc.replace('固定版本源码 · 显式适配器', '<a href="../README.md">使用说明</a> · <a href="../../arrow_semantic_audit/箭头语义审查报告.md">嵌套箭头语义审查</a> · <a href="../catalog/index.html">资源清单</a> · 固定版本源码 · 显式适配器')
    available={key for key in KEYS if (out/key/'index.html').exists()}
    links=['<a href="index.html">全部模型</a>']
    links += [f'<a href="index_{b}.html">{BATCH_LABELS[b]}</a>' for b,keys in BATCHES.items() if available.intersection(keys)]
    doc=doc.replace('<nav><button', '<p>'+' · '.join(links)+'</p><nav><button',1)
    (out/filename).write_text(doc)


def model_index(model,folder,evidence):
    sections=''.join(f'<section id="{view}"><h2>{title}</h2><p><a href="figure{i}_{view}.svg">SVG</a> · <a href="layout_{view}.json">布局记录</a></p><img src="figure{i}_{view}.svg" alt="{view}"></section>' for i,(view,title) in enumerate(zip(VIEWS,['概览','模块','详细']),1))
    name=html.escape(model['name'])
    doc=f'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>{name} 源码架构图</title><style>body{{font-family:DejaVu Sans,Arial,sans-serif;background:#edf0f5;color:#172336;margin:24px}}main{{max-width:1600px;margin:auto}}section{{background:white;padding:24px;margin-top:24px;border-radius:12px}}img{{width:100%;height:auto}}a{{color:#315479}}nav{{position:sticky;top:0;background:#edf0f5;padding:16px 0}}pre{{white-space:pre-wrap}}</style><main><h1>{name}</h1><p>{html.escape(evidence['repository'])} @ {evidence['commit'][:12]}</p><nav><a href="../index.html">六模型总览</a> · <a href="#overview">概览</a> · <a href="#modules">模块</a> · <a href="#detailed">详细</a> · <a href="source_map.md">逐节点源码映射</a> · <a href="source_evidence.json">源码证据</a> · <a href="semantic_ir.json">语义 IR</a> · <a href="layout_checks.json">检查</a></nav><details><summary>选定配置与边界</summary><pre>{html.escape(json.dumps(model['profile'],ensure_ascii=False,indent=2))}</pre></details>{sections}</main></html>'''
    (folder/'index.html').write_text(doc.replace('六模型总览','模型总览'))


def source_map(model,ir,evidence,folder):
    lines=[f'# {model["name"]}：源码与图框对应','',
           f'来源：`{evidence["repository"]}`，固定提交 `{evidence["commit"]}`。','',
           '静态审阅适配器；没有导入或执行模型。Notebook 的行号指派生 Python，原始 cell 索引见下表与证据 JSON。','',
           '| 证据 | 文件与符号 | 行号 | 原始 Notebook cell（0起） |','|---|---|---|---|']
    if evidence.get('source_projects'):
        origins=['','本图联合取证以下独立快照：','']
        origins += [f'- `{key}`：`{p["repository"]}` @ `{p["commit"]}`。' for key,p in evidence['source_projects'].items()]
        lines[4:4]=origins+['']
    for span in evidence['symbols'].values():
        lines.append(f'| {span["evidence_id"]} | [{span["path"]}](sources/{span["path"]}) · `{span["symbol"]}` | {span["start"]}–{span["end"]} | {span["notebook_cells"] or "—"} |')
    lines+=['','| 稳定节点 ID | 图框 | 静态 shape | 证据 | 参数 / 实例族 |','|---|---|---|---|---|']
    for node in ir['nodes']:
        parameter=node.get('param_identity',node.get('parameter',node.get('parameter_scope','—')))
        instance=node.get('instance_identity',node.get('module_identity'))
        if instance:
            parameter=('' if parameter=='—' else str(parameter)+'; ')+'instance='+str(instance)
            if node.get('learnable') is False:parameter+='; no learned parameters'
        if node.get('repeat'):parameter=str(parameter)+'; '+str(node['repeat'])
        lines.append('| '+' | '.join(str(value).replace('|',' / ').replace('\n',' ') for value in [node['id'],node['label'],node.get('shape',''),','.join(node['source_evidence']),parameter])+' |')
    lines+=['','## 与教科书/通用基础图的区别','']+['- '+item for item in model['corrections']]
    lines+=['','## 源码事实与边界','']+['- '+item for item in model['facts']]
    (folder/'source_map.md').write_text('\n'.join(lines)+'\n')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--model',choices=['all']+KEYS,default='all')
    p.add_argument('--batch',choices=['all']+list(BATCHES),default='all',help='generate a batch while preserving other existing models')
    p.add_argument('--source-root',type=Path,default=HERE/'sources')
    p.add_argument('--out',type=Path,default=HERE/'generated')
    p.add_argument('--png',action='store_true')
    args=p.parse_args()
    if args.png and not shutil.which('rsvg-convert'):p.error('--png requires rsvg-convert')
    out=args.out.resolve();out.mkdir(parents=True,exist_ok=True)
    try:keys=selected(args.batch,args.model)
    except ValueError as exc:p.error(str(exc))
    models=[];reports=[]
    for key in keys:
        model=importlib.import_module('adapters.'+key).build()
        from adapters.endpoint_contracts import annotate
        model=annotate(model)
        model.setdefault('view_overrides',{})
        configure(model)
        folder=out/key;folder.mkdir(parents=True,exist_ok=True)
        evidence=collect(model,args.source_root,folder);ir=semantic_ir(model,evidence)
        ir_digest=hashlib.sha256(json.dumps(ir,sort_keys=True).encode()).hexdigest()
        save(folder/'source_evidence.json',evidence);save(folder/'semantic_ir.json',ir)
        save(folder/'profile.json',model['profile']);save(folder/'visual_style.json',manifest())
        checks=[]
        for level,view in enumerate(VIEWS):
            svg=folder/f'figure{level+1}_{view}.svg'
            layout=render(model,evidence,ir,level,svg)
            layout['semantic_ir_sha256']=ir_digest;save(folder/f'layout_{view}.json',layout)
            check=validate(layout)|dict(view=view,semantic_ir_sha256=ir_digest);checks.append(check)
            if args.png:subprocess.run(['rsvg-convert',str(svg),'-o',str(svg.with_suffix('.png'))],check=True)
            print(f'{key:12} {view:8} {layout["canvas"]} '+('PASS' if check['passed'] else f'FAIL {len(check["errors"])}'),flush=True)
            for error in check['errors'][:12]:print('  '+error,flush=True)
        save(folder/'layout_checks.json',checks);source_map(model,ir,evidence,folder);model_index(model,folder,evidence)
        models.append(model);reports.append(dict(model=key,passed=all(c['passed'] for c in checks),views=checks))
    previous=json.loads((out/'validation_summary.json').read_text()) if (out/'validation_summary.json').exists() else []
    merged={r['model']:r for r in previous};merged.update({r['model']:r for r in reports})
    save(out/'validation_summary.json',[merged[k] for k in KEYS if k in merged])
    # Preserve existing batch exports and include them in the common gallery.
    gallery_models=[dict(key=k,name=importlib.import_module('adapters.'+k).build()['name']) for k in KEYS if (out/k/'index.html').exists()]
    gallery(out,gallery_models)
    for batch,keys_in_batch in BATCHES.items():
        members=[m for m in gallery_models if m['key'] in keys_in_batch]
        if members:gallery(out,members,'index_'+batch+'.html')
    print('Preview:',out/'index.html')
    if not all(r['passed'] for r in reports):raise SystemExit(1)


if __name__=='__main__':main()
