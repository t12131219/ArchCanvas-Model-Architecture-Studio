#!/usr/bin/env python3
"""Offline source-bound module-only gallery, reusing the sibling static engine."""
import bootstrap
import argparse,hashlib,html,importlib,json,shutil,subprocess
from pathlib import Path
from evidence import collect,semantic_ir
from layout import render,validate
from theme import configure,manifest
from generate import source_map as shared_source_map
from registry import KEYS,VIEWS,FAMILIES
HERE=Path(__file__).resolve().parent

def save(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')

def source_map(model,ir,evidence,folder):
    shared_source_map(model,ir,evidence,folder)
    # Literal indexed source expressions such as self.gate[layer](x) must not
    # become Markdown links to an imaginary file named x.
    target=folder/'source_map.md'
    lines=[line.replace('[','\\[').replace(']','\\]') if line.startswith('- ') else line
           for line in target.read_text().splitlines()]
    target.write_text('\n'.join(lines)+'\n')
STYLE='''body{font-family:DejaVu Sans,Arial,sans-serif;background:#edf0f5;color:#172336;margin:24px}main{max-width:1700px;margin:auto}nav{position:sticky;top:0;background:#edf0f5;padding:14px;z-index:1}a{color:#315479}section,article{background:white;padding:22px;border-radius:12px;margin:20px 0}img{width:100%;height:auto}pre{white-space:pre-wrap}button,select{font:inherit;padding:10px 15px;margin:4px;border:1px solid #718299;border-radius:8px;background:white;color:#172336;cursor:pointer}button.active{background:#263348;color:white}.grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:22px}.badge{background:#dfdff8;border-radius:6px;padding:4px 8px;font-size:13px}@media(max-width:850px){.grid{grid-template-columns:1fr}}'''

def gallery(out):
    cards=[]
    for key in KEYS:
        if not (out/key/'index.html').exists():continue
        model=importlib.import_module('module_adapters.'+key).build()
        family=FAMILIES[key];name=model['name'];scope=model['module_scope']
        cards.append(f'<article data-key="{key}" data-family="{html.escape(family,quote=True)}" data-search="{html.escape(name+" "+key+" "+family+" "+scope,quote=True)}"><span class="badge">{html.escape(family)}</span><h2>{html.escape(name)}</h2><p class="scope">{html.escape(scope)}</p><p><a href="{key}/index.html">三粒度与源码证据</a> · <a href="../docs/{model["doc"]}">对应与布局说明</a> · <a class="download" href="{key}/figure1_overview.svg">SVG</a></p><a class="image" href="{key}/figure1_overview.svg"><img loading="lazy" src="{key}/figure1_overview.svg" alt="{html.escape(name)}"></a></article>')
    options=''.join('<option>'+html.escape(f)+'</option>' for f in sorted(set(FAMILIES.values())))
    extra='input{font:inherit;padding:10px 12px;border:1px solid #718299;border-radius:8px;min-width:240px}.scope{font-size:14px;color:#344155;line-height:1.5}article[hidden]{display:none}.grid img{max-height:780px;object-fit:contain}.counter{font-size:14px;margin-left:12px}nav{box-shadow:0 4px 8px #26334815}'
    doc=f'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>模块适配专题</title><style>{STYLE}{extra}</style><main><h1>模块适配专题 · {len(cards)} 个模块案例</h1><p>从现有30个模型案例与前8个模块的覆盖盘点出发，补齐具有不同依赖、参数或状态机制的模块子图。每例保留概览、内部模块与算子详细三视图。</p><p>Transformer 字体、角色色与深色轮廓；所有主流程自底向上。颜色不代表参数共享，完整模型数与模块案例数分别统计。</p><p><a href="../README.md">使用说明</a> · <a href="../coverage.md">覆盖与新增差异</a> · <a href="../index_audit.md">两个目录的完整条目审计</a> · <a href="../module_catalog.json">模块来源清单</a> · <a href="../../model_zoo_programmatic_guide/generated/index.html">完整模型案例</a> · <a href="module_review.json">最终审阅</a></p><nav><div><input id="search" aria-label="搜索模块" placeholder="搜索名称、机制或 CLI key"><select id="family" aria-label="模块族筛选"><option value="">全部模块族</option>{options}</select><span id="count" class="counter"></span></div><div><button class="active" data-view="1_overview">概览</button><button data-view="2_modules">内部模块</button><button data-view="3_detailed">算子详细</button></div></nav><div class="grid">{''.join(cards)}</div></main><script>
const cards=[...document.querySelectorAll('article')];
function filter(){{const q=document.querySelector('#search').value.trim().toLowerCase(),f=document.querySelector('#family').value;let n=0;cards.forEach(a=>{{a.hidden=!!((f&&a.dataset.family!==f)||(q&&!a.dataset.search.toLowerCase().includes(q)));if(!a.hidden)n++}});document.querySelector('#count').textContent='显示 '+n+' / '+cards.length+' 个模块'}};
document.querySelector('#search').addEventListener('input',filter);document.querySelector('#family').addEventListener('change',filter);filter();
document.querySelectorAll('button[data-view]').forEach(b=>b.onclick=()=>{{document.querySelectorAll('button[data-view]').forEach(x=>x.classList.toggle('active',x===b));cards.forEach(a=>{{const path=a.dataset.key+'/figure'+b.dataset.view+'.svg';a.querySelector('img').src=path;a.querySelector('.image').href=path;a.querySelector('.download').href=path}})}});
</script></html>'''
    (out/'index.html').write_text(doc)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--module',choices=['all']+KEYS,default='all')
    parser.add_argument('--out',type=Path,default=HERE/'generated')
    parser.add_argument('--source-root',type=Path,default=HERE/'sources')
    parser.add_argument('--png',action='store_true')
    args=parser.parse_args();out=args.out.resolve();out.mkdir(parents=True,exist_ok=True)
    if args.png and not shutil.which('rsvg-convert'):parser.error('--png requires rsvg-convert')
    keys=KEYS if args.module=='all' else [args.module];reports=[]
    for key in keys:
        adapter=importlib.import_module('module_adapters.'+key);model=adapter.build()
        assert model['key']==key and model['artifact_scope']=='module'
        folder=out/key;folder.mkdir(parents=True,exist_ok=True);configure(model)
        evidence=collect(model,args.source_root,folder,manifest_path=HERE/'source_manifest.json')
        ir=semantic_ir(model,evidence);labels=adapter.validate_ir(ir)
        assert labels
        save(folder/'source_evidence.json',evidence);save(folder/'semantic_ir.json',ir)
        save(folder/'profile.json',model['profile']);save(folder/'visual_style.json',manifest())
        digest=hashlib.sha256(json.dumps(ir,sort_keys=True).encode()).hexdigest();checks=[]
        for level,view in enumerate(VIEWS):
            svg=folder/f'figure{level+1}_{view}.svg';layout=render(model,evidence,ir,level,svg)
            layout['semantic_ir_sha256']=digest;save(folder/f'layout_{view}.json',layout)
            check=validate(layout)|dict(view=view);checks.append(check)
            if args.png:subprocess.run(['rsvg-convert',str(svg),'-o',str(svg.with_suffix('.png'))],check=True)
            print(f'{key:18} {view:8} {layout["canvas"]} '+('PASS' if check['passed'] else 'FAIL'),flush=True)
            for e in check['errors'][:8]:print('  '+e,flush=True)
        save(folder/'layout_checks.json',checks)
        source_map(model,ir,evidence,folder)
        sections=''.join(f'<section id="{v}"><h2>{title}</h2><p><a href="figure{i}_{v}.svg">SVG</a> · <a href="layout_{v}.json">布局记录</a></p><img src="figure{i}_{v}.svg" alt="{v}"></section>' for i,(v,title) in enumerate(zip(VIEWS,['模块概览','内部模块','算子详细']),1))
        doc=f'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>{html.escape(model['name'])} 模块案例</title><style>{STYLE}</style><main><h1>{html.escape(model['name'])}</h1><p><span class="badge">模块案例</span> {html.escape(model['module_scope'])}</p><nav><a href="../index.html">模块总览</a> · <a href="../../docs/{model['doc']}">源码与排布说明</a> · <a href="source_map.md">逐节点对应</a> · <a href="source_evidence.json">源码证据</a> · <a href="semantic_ir.json">语义IR</a></nav><details><summary>选定模块边界与配置</summary><pre>{html.escape(json.dumps(model['profile'],ensure_ascii=False,indent=2))}</pre></details>{sections}</main></html>'''
        (folder/'index.html').write_text(doc)
        reports.append(dict(module=key,passed=all(c['passed'] for c in checks),semantic_checks=labels,views=checks))
    existing=json.loads((out/'validation_summary.json').read_text()) if (out/'validation_summary.json').exists() else []
    merged={r['module']:r for r in existing};merged.update({r['module']:r for r in reports})
    save(out/'validation_summary.json',[merged[k] for k in KEYS if k in merged]);gallery(out)
    if not all(r['passed'] for r in reports):raise SystemExit(1)

if __name__=='__main__':main()
