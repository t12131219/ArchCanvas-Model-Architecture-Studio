#!/usr/bin/env python3
"""Complete frozen index-entry audit, not a claim of recursive model coverage."""
from pathlib import Path
from collections import Counter,defaultdict
import ast,hashlib,json,sys
HERE=Path(__file__).resolve().parent
import bootstrap
from evidence import symbols_in

def write(p,d):p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
def main():
 catalog=json.loads((HERE/'../model_zoo_programmatic_guide/catalog/models.json').read_text())
 modules=json.loads((HERE/'module_catalog.json').read_text())['modules']
 manifest=json.loads((HERE/'source_manifest.json').read_text())
 mapped=defaultdict(list);paths=defaultdict(list);repos=defaultdict(list)
 for m in modules:
  provenance=m['directory_provenance'];origin=provenance.get('index',provenance.get('origin'))
  line=provenance.get('line',provenance.get('readme_line'))
  if origin and line:mapped[(origin,line)].append(m['key'])
  for src in m['sources']:
   repos[src['repository'].lower()].append(m['key']);paths[src['raw_path']].append(m['key'])
 entries=[]
 for e in catalog['entries']:
  same=mapped[(e['origin'],e['readme_line'])];old=e.get('diagram')
  repo=e.get('url','').replace('https://github.com/','').replace('http://github.com/','').split('/')[:2]
  related=sorted(set(repos['/'.join(repo).lower()])) if len(repo)==2 else []
  if same:status='selected_module_subgraphs_drawn'
  elif old:status='existing_whole_model_case_has_module_inventory'
  elif e.get('path_status')=='all_missing':status='upstream_reference_missing'
  elif e['origin']=='Awesome-pytorch-list' and e['resource_type']=='resource_reference':status='resource_entry_no_exhaustive_module_audit'
  else:status='indexed_not_source_reviewed_for_new_modules'
  entries.append(dict(id=e['id'],origin=e['origin'],title=e['title'],resource_type=e['resource_type'],category=e['category'],
   readme_line=e['readme_line'],url=e['url'],status=status,drawn_module_keys=sorted(set(same)),existing_model_key=old,
   related_selected_repo_module_keys=related,related_repo_does_not_prove_whole_entry_coverage=True,path_status=e.get('path_status'),paths=e.get('paths',[]),path_checks=e.get('path_checks',[]),missing_paths=[p['path'] for p in e.get('path_checks',[]) if not p.get('exists_in_frozen_tree',True)]))
 notebooks=[]
 for e in catalog['notebooks']:
  selected=sorted(set(paths[e['path']]))
  notebooks.append(dict(path=e['path'],framework=e['framework'],tree_status=e['path_status'],readme_listed=e['readme_listed'],
   drawn_module_keys=selected,existing_model_key=e.get('diagram'),status='selected_module_subgraph_drawn' if selected else 'existing_model_case' if e.get('diagram') else 'tree_index_only_not_reviewed'))
 census=[]
 for slug,p in manifest.items():
  for inner in list(p['files'])+list(p.get('derived',{})):
   if not inner.endswith('.py'):continue
   member=slug+'/'+inner;text=(HERE/'sources'/member).read_text()
   required=set()
   for m in modules:
    for s in m['sources']:
     if s['local_path']=='sources/'+member:required.update(s['symbols'])
   symbols=symbols_in(text,member,required=required)
   definitions=[]
   for name,n in symbols.items():
    if name=='__module__' or '.' in name:continue
    selected=[m['key'] for m in modules if any(s['local_path']=='sources/'+member and any(x==name or x.startswith(name+'.') for x in s['symbols']) for s in m['sources'])]
    definitions.append(dict(symbol=name,kind=type(n).__name__,line=n.lineno,end=n.end_lineno,
     status='has_selected_source_symbol_or_subgraph' if selected else 'acquired_definition_not_individually_adapted',module_keys=selected,
     semantic_completeness=False,reason='Classes/functions can be model containers, helpers, alternate profiles, opaque library wrappers or duplicate primitives; symbol existence alone does not define a new module family.'))
   census.append(dict(source=member,repository=p['repository'],commit=p['commit'],sha256=hashlib.sha256((HERE/'sources'/member).read_bytes()).hexdigest(),definitions=definitions))
 counts=dict(index_entries=len(entries),by_status=dict(Counter(e['status'] for e in entries)),notebook_paths=len(notebooks),
  notebook_statuses=dict(Counter(n['status'] for n in notebooks)),readme_entries_with_missing_references=sum(bool(e['missing_paths']) for e in entries),module_cases=len(modules),module_families=len(set(m['family'] for m in modules)),
  svg_views=3*len(modules),png_views=3*len(modules),acquired_python_files=len(census),acquired_top_level_definitions=sum(len(c['definitions']) for c in census))
 notes={}
 for p in (HERE/'staging').glob('*_catalog.json'):
  data=json.loads(p.read_text())
  if isinstance(data,dict):notes[p.name]={k:v for k,v in data.items() if k in ('deferred','deduplicated','limitations')}
 write(HERE/'module_boundary_notes.json',notes)
 audit=dict(module_boundary_notes='module_boundary_notes.json',schema='module-index-audit/1',counts=counts,provenance=catalog['provenance'],entries=entries,notebooks=notebooks,acquired_definition_census=census,
  scope='Every 832 frozen README entry and 183 Notebook tree path is given a status. Linked external repositories are not exhaustively recursively fetched or semantically enumerated. Only selected module profiles have source-grounded drawings.',
  completeness=dict(index_entries=True,notebook_tree_paths=True,all_modules_in_all_external_repositories=False,all_runtime_profiles=False,all_library_kernels=False),
  model_executed=False)
 write(HERE/'index_audit.json',audit)
 lines=['# 两个目录的完整条目审计','',
  f'本轮共 **{len(modules)} 个模块案例 / {len(set(m["family"] for m in modules))} 个模块族标签 / {3*len(modules)} 个主 SVG 视图**。模块族标签是适配分类，不是数学模块的唯一标准。',
  '','已逐条给冻结 README 中的 **832 个条目（Awesome 706、rasbt 126）** 和 rasbt Git tree 中 **183 个 Notebook 路径** 赋予状态；完整机器清单见 [index_audit.json](index_audit.json)。',
  '', '**“完整”在这里指索引条目都有记录；不能称全部外链仓库的所有模块已画完。** 两个目录含工具、教程、数据集、完整模型与重复实现，外链数量和动态配置没有封闭的模块总数。尚未读过的实现保留未核实状态，普通算子 kernel 仍是调用边界。',
  '', '| 条目状态 | 数量 | 含义 |','| --- | ---: | --- |']
 descriptions={'selected_module_subgraphs_drawn':'已绘制所选模块边界，未声称整个条目所有模块覆盖','existing_whole_model_case_has_module_inventory':'已有完整模型与逐节点覆盖盘点','upstream_reference_missing':'冻结 tree 中引用缺失','resource_entry_no_exhaustive_module_audit':'资源目录条目；未对整仓库做模块穷举','indexed_not_source_reviewed_for_new_modules':'已收录，尚未获取/审阅新模块实现'}
 for status,count in counts['by_status'].items():lines.append(f'| `{status}` | {count} | {descriptions[status]} |')
 lines += ['', '## 本轮可闭合的覆盖边界','',
  '- 新绘制模块都有固定 commit、源码符号、输入输出边界、参数/状态、三粒度图和语义核验。现有案例中的同构结构作为已覆盖依据保留。',
  '- 对已取得 Python 文件，JSON 同时列出顶层类/函数的源码符号 census。未单画的 helper、整个模型容器、另一配置或同构原子操作，不能直接计为缺失的新模块。',
  '- 同仓库出现于多条目录引用，只能说明选定实现来自该仓库；不能据此把整条目录或所有分支打成完成。',
  '- 已审阅但未单画的同构/整模型/另一配置边界见 [module_boundary_notes.json](module_boundary_notes.json)，不计成新模块。',
  '- 源码特有分支分别作为案例：如 Shuffle stride1/2、SignedSAGE Base/Deep、MixHop Sparse/Dense、Glow affine/additive；它们不是新增完整模型。',
  '', '## 已绘制模块目录','', '| CLI key | 模块 | 模块族 | 图与源码说明 |','| --- | --- | --- | --- |']
 for m in modules:lines.append(f'| `{m["key"]}` | {m["name"]} | {m["family"]} | [三图]({m["gallery"]}) · [对应]({m["documentation"]}) |')
 (HERE/'index_audit.md').write_text('\n'.join(lines)+'\n')
 coverage=json.loads((HERE/'coverage.json').read_text());coverage['new_module_cases']=modules;coverage['current_totals']=counts
 alias={'gru_cell_gates':'gru_cell','wavenet_gated_residual':'wavenet_block','structured_sentence_attention':'structured_attention','ggnn_gated_propagation':'ggnn_step'}
 for c in coverage['pending_candidates']:
  key=alias.get(c['key'],c['key']);m=next((m for m in modules if m['key']==key),None)
  if m:
   c.update(status='reviewed_module_adapter_drawn',implemented_key=key,selected_implementation=m['sources'],gallery=m['gallery'])
   c['historical_candidate_note']=c.pop('note','');c['note']='此前候选已落地，实际边界与错误修正以当前模块文档为准；初始目录预想不是源码证据。'
 coverage['caveats']+=['Expanded audit: full README entry indexing is not exhaustive semantic inspection of linked repositories.'] if 'Expanded audit: full README entry indexing is not exhaustive semantic inspection of linked repositories.' not in coverage['caveats'] else []
 write(HERE/'coverage.json',coverage)
 cv=['# 现有覆盖与模块扩展','',
  f'现有模型盘点为 30 个主案例 / 90 个视图；原模块专题为 8 个案例，本次新增 {len(modules)-8} 个，共 {len(modules)} 个模块案例 / {len(modules)*3} 个 SVG 与同数 PNG。',
  '', '[现有逐节点盘点](existing_coverage.json) · [完整索引审计](index_audit.md) · [覆盖 JSON](coverage.json) · [交互画廊](generated/index.html)',
  '', '## 已有模块族','', '| 模块族 | 原案例覆盖状态 | 依据 |','| --- | --- | --- |']
 for f in coverage['baseline_families']:
  cv.append('| '+f['label']+' | '+f['coverage']+' | '+f.get('note','').replace('|','\\|')+' |')
 cv += ['', '## 模块机制与边界（含原8例）','', '| 模块 | 原覆盖的区别 | 新依赖 / 身份机制 | 范围 |','| --- | --- | --- | --- |']
 for m in modules:
  cv.append('| ['+m['name']+']('+m['gallery']+') | '+m['existing_comparison'].replace('|','\\|')+' | '+m['new_adaptation'].replace('|','\\|')+' | '+m['scope'].replace('|','\\|')+' |')
 cv += ['', '## 完整性与未展开项','',
  '原 14 项候选按 actual key 映射到实现；来源发生变化时保留原候选记录和当前所选仓库。初始注释中的 masked/BiLSTM/offset predictor 等猜测不能覆盖实际源码边界。',
  '其余目录资源的审阅状态在 [完整索引审计](index_audit.md) 单独列出，不用标题关键词认定一个模块已适配。kernel、整模型容器、另一训练/反向配置和未取得实现都保留边界。',
  '主图与内部图都自底向上；语义由显式适配器与固定证据决定，布局规则只计算几何，不从源码中假造视觉排列。颜色相同不等于参数共享。']
 (HERE/'coverage.md').write_text('\n'.join(cv)+'\n')
 print(json.dumps(counts,ensure_ascii=False))
if __name__=='__main__':main()
