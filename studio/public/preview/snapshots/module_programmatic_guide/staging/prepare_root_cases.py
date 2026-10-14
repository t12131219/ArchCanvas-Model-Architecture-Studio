from pathlib import Path
import sys,ast,json
HERE=Path(__file__).resolve().parents[1];sys.path.insert(0,str(HERE))
import bootstrap
from evidence import symbols_in
from module_adapters.root_definitions import CASES
manifest=json.loads((HERE/'staging/root_source_manifest.json').read_text())
for key,c in CASES.items():
 src=(HERE/'sources'/c['source']).read_text();syms=symbols_in(src,c['source'],set(c['symbols']))
 for symbol,expr in c['contracts']:
  wanted=ast.dump(ast.parse(expr,mode='eval').body,include_attributes=False)
  assert any(ast.dump(n,include_attributes=False)==wanted for n in ast.walk(syms[symbol])),(key,symbol,expr)
 (HERE/'module_adapters'/f'{key}.py').write_text('"""Reviewed '+c['name']+' module profile."""\nfrom module_adapters.root_support import build_case,validate_case\n\ndef build():return build_case('+repr(key)+')\n\ndef validate_ir(ir):return validate_case('+repr(key)+',ir)\n')
 p=c['source'].split('/')[0];record=manifest[p];path=c['source'].split('/',1)[1];derived=record.get('derived',{}).get(path)
 raw=derived['original'] if derived else path;url=record['files'][raw]['url'].replace('raw.githubusercontent.com/','github.com/').replace('/'+record['commit']+'/', '/blob/'+record['commit']+'/')
 index='deeplearning-models' if p=='rasbt-ordinal-modules' else 'Awesome-pytorch-list'
 line=164 if key=='coral_head' else 165 if key=='corn_decoder' else 695 if p=='glow-modules' else 631 if p=='density-flow-modules' else 681
 readme=(HERE/'upstream'/index/'README.md').read_text().splitlines()[line-1]
 commit='59beda3aa25337e576564f1c18c6edd26f9f30e3' if index=='deeplearning-models' else '06e9786eb64392cbe233d1a9ab7489256c0ac521'
 c['catalog']=dict(key=key,name=c['name'],family=c['family'],artifact_scope='module',previous_coverage='not_drawn_as_this_module_subgraph_in_existing_cases',
   existing_comparison='已有 Conv/Linear、一般注意力和 VAE 等基础运算；未展开本例特定参数、端口、状态与公式组合。',
   new_adaptation='；'.join(c['facts'][:2]),scope=c['scope'],profile=c['profile'],directory_provenance=dict(index=index,commit=commit,readme_path='upstream/'+index+'/README.md',line=line,text=readme,url='https://github.com/'+('rasbt/' if index=='deeplearning-models' else 'bharathgs/')+index+'/blob/'+commit+'/README.md#L'+str(line),relationship='direct Notebook caller/class entry' if derived else 'listed repository contains selected module; symbol is source-reviewed'),
   sources=[dict(local_path='sources/'+c['source'],repository=record['repository'],commit=record['commit'],symbols=c['symbols'],raw_path=raw,url=url,sha256=(derived or record['files'][path])['sha256'],derived_from_notebook=bool(derived))],documentation='docs/'+key+'.md',gallery='generated/'+key+'/index.html',status='reviewed_module_adapter')
 lines=['# '+c['name'],'', '本例补充的是 **模块/选定子图**，范围：`'+c['scope']+'`。','',
  '入口：[三粒度图](../generated/'+key+'/index.html) · [逐节点源码映射](../generated/'+key+'/source_map.md) · [语义 IR](../generated/'+key+'/semantic_ir.json)。','',
  '## 固定源码与配置','',f'- 索引：{index} README 第 {line} 行。',f'- 实现：[{record["repository"]}@{record["commit"][:12]}]({url})。',
  '- 选取入口：`'+c['entry']+'`。Notebook 原单元/派生行映射保存在证据中。',
  '- 配置均为静态代表值，不是张量实际执行记录；不运行训练、源码 import 或模型。','', '```json',json.dumps(c['profile'],ensure_ascii=False,indent=2),'```','',
  '## 源码结构到图元','', '| 分组 / 节点 | 源码调用或公式 | 参数与状态身份 | 为何对应 |','| --- | --- | --- | --- |']
 for s in c['stages']:
  for n in s['ops']:
   expression=n.get('expression') or '; '.join(n.get('expressions',[])) or ', '.join(n.get('symbols',[c['entry']]))
   storage='Parameter: '+str(n.get('parameters',[]))+'; buffer: '+str(n.get('buffers',[]))
   if 'storage_kind' in n:storage+='; '+n['storage_kind']
   lines.append('| '+s['label']+' / `'+n['id']+'` | `'+expression.replace('|','\\|')+'` | '+storage+' | '+n['label']+'；`kind='+n['kind']+'` 表示真实操作类别，颜色单独表示视觉角色 |')
 lines += ['', '## 依赖、并列与参数对应','']+['- '+v for v in c['facts']]
 lines += ['', '| 源节点端口 | 目标节点端口 | 含义 |','| --- | --- | --- |']
 for a,b,*r in c['edges']:
  o=r[0] if r else {};lines.append('| `'+a+':'+o.get('src_port','out')+'` | `'+b+':'+o.get('dst_port','in')+'` | '+o.get('role','tensor')+' |')
 lines += ['', '## 程序化排布','',
 '三个粒度使用同一个完整语义 IR：概览折叠 body，模块图展开阶段容器，详细图展开每阶段内的调用。折叠只投影视图端点，不改变数据依赖。',
 '底到顶 ranks 依次是：`'+str(c['ranks'])+'`。每行并列的阶段具有独立支路或输出；rank 本身不生成任何数据边。root 输入在底部、返回值在顶部，同一 tuple 的输出保持并列。',
 '每个阶段尺寸由文字/形状标签与子节点尺寸计算。阶段间距 76px、列间距 58px 为两端各 24px 的箭头预留通道；路由器以 bbox 和真实端口避让边框，末段至少 18px。内部顺序调用自底向上；旁路/权重/状态使用 typed edge，不因并列或同色而暗示共享参数。',
 '紫色用于 Linear/矩阵，蓝色用于卷积和重排，黄色用于归一化或算术，绿色用于概率/非线性，灰色用于状态。一个类别可以跨不同模块复用；共享与独立身份以 IR 的 parameters/module_identity 为准。',
 '', '## 避免教科书模板替代源码','']+['- '+v for v in c['corrections']]
 lines += ['', '## 复用与验证','',
 '`module_adapters/'+key+'.py` 调用 `root_support.build_case()`，显式配置集中在 `root_definitions.py`。这复用图元和布局机制，仍不是任意源码自动识别。',
 '`checks/flow_generative_extended.py` 使用独立 AST 子树对照关键公式，并注入删除关键依赖、改变参数/操作、错误配置等负例；`verify.py --png` 对实际 SVG、PNG、源码副本及哈希核验。',
 'PyTorch/SciPy 算子的内部 kernel 为调用边界；初始化、反向分支和训练状态只按明确选定 profile 展示。更换 commit 或 profile 必须先复查语义与来源。','']
 (HERE/'docs'/f'{key}.md').write_text('\n'.join(lines))
(HERE/'staging/root_catalog.json').write_text(json.dumps([c['catalog'] for c in CASES.values()],ensure_ascii=False,indent=2)+'\n')
print('AST contracts and docs:',len(CASES))
